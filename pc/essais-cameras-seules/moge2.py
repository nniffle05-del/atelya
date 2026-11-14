"""Poser chaque photo sur le plan avec MoGe-2 : le haut des murs vu par la photo (au-dessus des portes et des meubles),
mesuré en mètres, comparé à ce qu'on verrait de chaque endroit du logement."""
import json, sys, time
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
import etape_b as eb
from moge1 import verticale, pic

src, sortie = Path(sys.argv[1]), Path(sys.argv[2]); sortie.mkdir(parents=True, exist_ok=True)
PAS, BAS = 0.2, 2.1


def profil(z, hsp, gris=None):
    """Ce que la photo voit : pour chaque direction (degré, + = gauche), distance au mur, en mètres. → (phi°, r), infos."""
    P, N, M = z["points"].astype(np.float32)[::2, ::2], z["normales"].astype(np.float32)[::2, ::2], z["masque"][::2, ::2]
    r = {"points": P, "normales": N, "masque": M}
    haut = verticale(r)
    av = np.array([0, 0, 1.0]) - haut * haut[2]; av /= np.linalg.norm(av)
    dr = np.cross(av, haut)  # droite ? on fixe le signe pour que la droite de l'image soit positive
    if dr[0] < 0:
        dr = -dr
    p, n = P[M], N[M]
    h, a, b = p @ haut, p @ dr, p @ av
    horiz = np.abs(n @ haut) > 0.95
    sol, plaf = pic(h[horiz & (h < -0.4)]), pic(h[horiz & (h > 0.3)])
    ech = 1.0
    if sol is not None and plaf is not None and 0.75 < hsp / (plaf - sol) < 1.33:
        ech = hsp / (plaf - sol)
    elif sol is None and plaf is None:
        return None
    if sol is None:
        sol = plaf - hsp / ech
    ha = (h - sol) * ech
    mur = (np.abs(n @ haut) < 0.35) & (b > 0.2)
    bande = mur & (ha > BAS) & (ha < hsp - 0.04)
    if bande.sum() < 400:
        bande = mur & (ha > 1.5) & (ha < hsp - 0.04)
    phi = np.degrees(np.arctan2(-a[bande], b[bande])); ray = np.hypot(a[bande], b[bande]) * ech
    k = np.round(phi).astype(int)
    ph, rr = [], []
    for d in np.unique(k):
        v = ray[k == d]
        if len(v) >= 12:
            ph.append(d); rr.append(np.median(v))
    ph, rr = np.array(ph, float), np.array(rr)
    # à mi-hauteur (1,0 à 1,9 m) : voit-on PLUS LOIN que le mur (fenêtre, porte ouverte) ? points sans mesure = ciel
    H, W = M.shape
    f = float(z["focale"]) / 2
    cols = np.degrees(np.arctan2(-(np.arange(W) + 0.5 - W / 2), f)).round().astype(int)
    zc = -sol * ech
    hA = np.full(M.shape, np.nan, np.float32); hA[M] = ha
    rA = np.full(M.shape, np.nan, np.float32); rA[M] = np.hypot(a, b) * ech
    lig = np.arange(H) + 0.5 - H / 2
    trou = np.zeros(len(ph), bool)
    for i, (d, rw) in enumerate(zip(ph, rr)):
        cc = np.where(cols == int(d))[0]
        if not len(cc):
            continue
        prof = rw * np.cos(np.radians(d))
        l0, l1 = -f * (1.9 - zc) / prof, -f * (1.0 - zc) / prof
        dedans = (lig > l0) & (lig < l1)
        if dedans.sum() < 3:
            continue
        m_, r_, h_ = M[dedans][:, cc], rA[dedans][:, cc], hA[dedans][:, cc]
        loin = (~m_) | (m_ & (r_ > rw + 1.0))
        if gris is not None:
            loin = loin | (gris[dedans][:, cc] > 232)  # vitre au grand jour : blanc brûlé
        trou[i] = loin.mean() > 0.4
    return ph, rr, trou, {"z": -sol * ech, "ech": ech, "sol": sol, "plaf": plaf, "n": int(bande.sum())}


def tirs(mod, P, angles):
    """→ distances (n, R), sorte de la face touchée (0 mur, 1 porte, 2 fenêtre)."""
    D = np.stack([np.cos(np.radians(angles)), np.sin(np.radians(angles))], 1)[None].repeat(len(P), 0)
    out, g = [], []
    for i in range(0, len(P), 200):
        t, j = eb.lancer(mod, P[i:i + 200], D[i:i + 200])
        out.append(t); g.append(mod["sorte"][j])
    return np.concatenate(out), np.concatenate(g)


POIDS_TROU = float(__import__("os").environ.get("POIDS_TROU", 0.6))


def note(rm, rp, trou=None, sorte=None):
    rp = np.minimum(rp, 40.0)
    s = 0.10 + 0.04 * rp
    v = np.exp(-0.5 * ((rm - rp) / s) ** 2)
    if trou is not None and trou.any():
        # là où la photo voit à travers, le plan doit avoir une fenêtre ou une porte ; une fenêtre du plan doit se voir
        v = v * np.where(trou & (sorte == 0), 1 - POIDS_TROU, 1.0) * np.where(~trou & (sorte == 2), 1 - POIDS_TROU / 2, 1.0)
    return v.mean(-1)


def grille(mod):
    c = np.concatenate(mod["pieces"]); x0, y0 = c.min(0); x1, y1 = c.max(0)
    G = np.stack(np.meshgrid(np.arange(x0, x1, PAS), np.arange(y0, y1, PAS)), -1).reshape(-1, 2)
    ok = (eb.piece_de(mod, G) >= 0) & (eb.dist_seg(G, mod["A"], mod["B"]).min(1) > 0.06)
    return G[ok]


def precis(mod, ph, rm, trou, cam):
    def f(c):
        if eb.piece_de(mod, c[None, :2])[0] < 0:
            return -1
        t, g = tirs(mod, c[None, :2], c[2] + ph)
        return float(note(rm * c[3], t, trou, g)[0])
    best, pas = f(cam), np.array([0.1, 0.1, 2.0, 0.03])
    for _ in range(40):
        bouge = False
        for i in range(4):
            for s in (-1, 1):
                c = cam.copy(); c[i] += s * pas[i]
                if i == 3 and not 0.85 <= c[3] <= 1.15:
                    continue
                v = f(c)
                if v > best + 1e-6:
                    best, cam, bouge = v, c, True
        if not bouge:
            pas = pas / 2
            if pas[0] < 0.005:
                break
    return cam, best


if __name__ == "__main__":
    bilan = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        mod = eb.modele(log); mod = dict(mod, sorte=mod["genre"].copy(), genre=np.zeros_like(mod["genre"]))  # en haut des murs, tout est fermé
        G = grille(mod)
        tour, tsorte = tirs(mod, G, np.arange(360.0))  # (n, 360)
        for nom, c in d["cameras"].items():
            k = c["camera"]; t0 = time.time()
            z = np.load(src / f"{app}-{nom}.npz")
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            pr = profil(z, mod["hsp"], cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[::2, ::2] if __import__("os").environ.get("BLANC") else None)  # « blanc brûlé = vitre » : essayé, pire (4 → 2 / 22)
            if pr is None or len(pr[0]) < 15:
                print(f"{app} {nom} : pas assez de murs vus"); bilan.append((np.nan, np.nan, 0, 0)); continue
            ph, rm, trou, info = pr
            ip = ph.astype(int)
            ECH = (0.85, 0.92, 1.0, 1.08)
            notes = np.stack([np.stack([note(rm[None] * e, tour[:, (cap + ip) % 360], trou[None], tsorte[:, (cap + ip) % 360]) for cap in range(360)], 1) for e in ECH], 2)
            ordre = np.argsort(notes.ravel())[::-1]
            cands = []
            for o in ordre[:20000]:
                g, reste = divmod(int(o), 360 * len(ECH)); cap, ie = divmod(reste, len(ECH))
                if all(np.hypot(*(G[g] - q[:2])) > 0.6 or abs((cap - q[2] + 180) % 360 - 180) > 20 for q in cands):
                    cands.append(np.array([G[g][0], G[g][1], float(cap), ECH[ie]]))
                if len(cands) == 8:
                    break
            fins = sorted((precis(mod, ph, rm, trou, q) for q in cands), key=lambda x: -x[1])
            cam, n1 = fins[0]; n2 = fins[1][1] if len(fins) > 1 else 0
            ecart = float(np.hypot(cam[0] - k["x"], cam[1] - k["y"])); dcap = float(abs((cam[2] - k["cap"] + 180) % 360 - 180))
            rang = next((i + 1 for i, (q, _) in enumerate(fins) if np.hypot(q[0] - k["x"], q[1] - k["y"]) < 0.6 and abs((q[2] - k["cap"] + 180) % 360 - 180) < 10), 0)
            pm = mod["ids"][eb.piece_de(mod, cam[None, :2])[0]]
            print(f"{app} {nom} [{c.get('qualite')}] écart {ecart:5.2f} m, cap {dcap:5.1f}°, dans {pm} | note {n1:.2f} (2e {n2:.2f}) | bonne place au rang {rang} | "
                  f"hauteur {info['z']:.2f}/{k['z']:.2f}, échelle {info['ech']:.2f}×{cam[3]:.2f}, {len(ph)}° vus dont {int(trou.sum())}° à travers | {time.time() - t0:.0f} s", flush=True)
            bilan.append((ecart, dcap, rang, n1 - n2))
            # image de contrôle : le plan, les murs vus posés à la place trouvée (rouge) et à la place de la main (vert)
            E = 60; cc = np.concatenate(mod["pieces"]); o0 = cc.min(0) - 0.5; taille = ((cc.max(0) - o0 + 0.5) * E).astype(int)
            vis = np.full((taille[1], taille[0], 3), 255, np.uint8)
            px = lambda p: (int((p[0] - o0[0]) * E), int(taille[1] - (p[1] - o0[1]) * E))
            for a, b, g in zip(mod["A"], mod["B"], mod["sorte"]):
                cv2.line(vis, px(a), px(b), ((0, 0, 0), (0, 160, 255), (255, 160, 0))[g], 2)
            for q, coul in ((np.array([k["x"], k["y"], k["cap"], 1.0]), (0, 160, 0)), (cam, (0, 0, 255))):
                for p_, r_, tr in zip(ph, rm * q[3], trou):
                    t = np.radians(q[2] + p_)
                    cv2.circle(vis, px(q[:2] + r_ * np.array([np.cos(t), np.sin(t)])), 4 if tr else 2, (255, 0, 0) if tr and coul[2] else coul, -1)
                cv2.circle(vis, px(q[:2]), 6, coul, -1)
                t = np.radians(q[2]); cv2.line(vis, px(q[:2]), px(q[:2] + 0.6 * np.array([np.cos(t), np.sin(t)])), coul, 2)
            ecrire_image(sortie / f"{app}-{nom}.png", vis)
    t = np.array(bilan)
    ok = (t[:, 0] < 0.5) & (t[:, 1] < 8)
    print("bien placées (< 0,5 m et < 8°) :", int(ok.sum()), "/", len(t), "| app-002 :", int(ok[:11].sum()), "/ 11 | bonne place dans les 8 premières :", int((t[:, 2] > 0).sum()))
