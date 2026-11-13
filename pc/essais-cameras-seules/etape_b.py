"""Étape B : la place de l'appareil, par essais : la 3D du logement (murs, plafond, sol, portes, fenêtres) posée sur les lignes
de la photo ; on garde la caméra qui colle le mieux."""
import json, sys, time
from pathlib import Path
import cv2
import numpy as np
from moteur.images import lire_image, ecrire_image
import etape_a as ea

TAU = 8.0  # px : au-delà, une ligne prévue n'est pas « sur » une ligne de la photo
SEUIL = 0.3
NB = 12  # classes d'orientation (15°)


# ---------- le logement : faces de murs coupées aux ouvertures ----------
def modele(logement):
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    murs = {m["id"]: m for m in logement["murs"]}
    ouv = []
    for o in logement.get("ouvertures", []):
        m = murs.get(o.get("mur"))
        if m is None:
            continue
        a, b = np.array(m["debut"], float), np.array(m["fin"], float)
        L = np.linalg.norm(b - a)
        if L < 1e-6:
            continue
        t = (b - a) / L
        z0 = float(o.get("allege", 0.0) or 0.0)
        ouv.append({"a": a + t * float(o["position"]), "b": a + t * (float(o["position"]) + float(o["largeur"])),
                    "ep": float(m.get("epaisseur", 0.2)), "porte": o["type"] == "porte", "bas": z0,
                    "haut": min(z0 + float(o.get("hauteur", 2.1)), hsp)})
    A, B, genre, bas, haut, portes = [], [], [], [], [], []
    sommets = {}  # (x, y) arrondi → (bas, haut)

    def sommet(p, b0, h0):
        k = (round(float(p[0]), 2), round(float(p[1]), 2))
        if k in sommets:
            b1, h1 = sommets[k]
            b0, h0 = min(b0, b1), max(h0, h1)
        sommets[k] = (b0, h0)
    for p in logement["pieces"]:
        c = np.array(p["contour"], float)
        for i in range(len(c)):
            a, b = c[i], c[(i + 1) % len(c)]
            L = np.linalg.norm(b - a)
            if L < 0.02:
                continue
            t = (b - a) / L
            n = np.array([-t[1], t[0]])
            sommet(a, 0.0, hsp)
            coupes = []
            for o in ouv:
                d = abs(float((o["a"] - a) @ n))
                if d > o["ep"] / 2 + 0.2 or abs(float((o["b"] - o["a"]) @ t)) < 0.9 * np.linalg.norm(o["b"] - o["a"]):
                    continue
                s0, s1 = sorted((float((o["a"] - a) @ t), float((o["b"] - a) @ t)))
                s0, s1 = max(s0, 0.0), min(s1, L)
                if s1 - s0 > 0.2:
                    coupes.append((s0, s1, o))
            coupes.sort(key=lambda x: x[0])
            cur = 0.0
            for s0, s1, o in coupes:
                if s0 < cur - 1e-6:
                    continue
                if s0 - cur > 0.02:
                    A.append(a + t * cur); B.append(a + t * s0); genre.append(0); bas.append(0.0); haut.append(hsp)
                A.append(a + t * s0); B.append(a + t * s1); genre.append(1 if o["porte"] else 2); bas.append(o["bas"]); haut.append(o["haut"])
                sommet(a + t * s0, o["bas"], o["haut"]); sommet(a + t * s1, o["bas"], o["haut"])
                cur = s1
            if L - cur > 0.02:
                A.append(a + t * cur); B.append(a + t * L); genre.append(0); bas.append(0.0); haut.append(hsp)
    S = np.array(list(sommets.keys()), float)
    SB = np.array([v[0] for v in sommets.values()]); SH = np.array([v[1] for v in sommets.values()])
    return {"hsp": hsp, "A": np.array(A), "B": np.array(B), "genre": np.array(genre), "bas": np.array(bas), "haut": np.array(haut),
            "S": S, "SB": SB, "SH": SH, "pieces": [np.array(p["contour"], float) for p in logement["pieces"]],
            "ids": [p["id"] for p in logement["pieces"]]}


def dans_poly(P, c):
    x, y = P[:, 0], P[:, 1]
    r = np.zeros(len(P), bool)
    for i in range(len(c)):
        x1, y1 = c[i]; x2, y2 = c[(i + 1) % len(c)]
        cond = (y1 > y) != (y2 > y)
        xi = x1 + (y - y1) * (x2 - x1) / np.where(y2 != y1, y2 - y1, 1.0)
        r ^= cond & (x < xi)
    return r


def piece_de(mod, P):
    r = np.full(len(P), -1)
    for i, c in enumerate(mod["pieces"]):
        r[dans_poly(P, c) & (r < 0)] = i
    return r


def dist_seg(P, A, B):
    """(n, E) distances des points aux segments."""
    e = B - A
    t = np.clip(((P[:, None, :] - A[None]) * e[None]).sum(2) / (e * e).sum(1)[None], 0, 1)
    q = A[None] + t[..., None] * e[None]
    return np.linalg.norm(P[:, None, :] - q, axis=2)


def lancer(mod, P, D):
    """Rayons : P (n, 2), D (n, R, 2) unitaires → distance (n, R), face touchée (n, R). Les portes à moins d'1 m sont ouvertes."""
    A, B = mod["A"], mod["B"]
    e = B - A
    ap = A[None] - P[:, None, :]  # (n, E, 2)
    den = D[:, :, None, 0] * e[None, None, :, 1] - D[:, :, None, 1] * e[None, None, :, 0]  # (n, R, E)
    ok = np.abs(den) > 1e-9
    den = np.where(ok, den, 1.0)
    t = (ap[:, None, :, 0] * e[None, None, :, 1] - ap[:, None, :, 1] * e[None, None, :, 0]) / den
    s = (ap[:, None, :, 0] * D[:, :, None, 1] - ap[:, None, :, 1] * D[:, :, None, 0]) / den
    ouverte = (mod["genre"][None] == 1) & (dist_seg(P, A, B) < 1.0)  # (n, E)
    ok &= (t > 0.03) & (s >= 0) & (s <= 1) & ~ouverte[:, None, :]
    t = np.where(ok, t, np.inf)
    i = np.argmin(t, 2)
    return np.take_along_axis(t, i[..., None], 2)[..., 0], i


# ---------- la photo : cartes « à quelle distance d'une ligne de telle orientation » ----------
def cartes(seg, h, w, tau=TAU):
    d = seg[:, 2:] - seg[:, :2]
    L = np.hypot(d[:, 0], d[:, 1])
    ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180
    C = np.zeros((NB, h, w), np.float32)
    for b in range(NB):
        e = np.abs((ang - b * 15.0 + 90) % 180 - 90)
        im = np.full((h, w), 255, np.uint8)
        for x1, y1, x2, y2 in seg[e <= 11.0]:
            cv2.line(im, (int(round(x1)), int(round(y1))), (int(round(x2)), int(round(y2))), 0, 1)
        dt = cv2.distanceTransform(im, cv2.DIST_L2, 3)
        C[b] = np.clip(1.0 - dt / tau, 0, 1)
    cum = np.concatenate([np.zeros((1, w), np.float32), np.cumsum(C[6], 0)], 0)  # verticales : somme le long des colonnes
    # les lignes de la photo À EXPLIQUER : points des lignes non verticales (tous les 8 px), et verticales longues
    vert = np.abs(ang - 90) < 4.0
    pu, pv, pb = [], [], []
    for (x1, y1, x2, y2), l, a in zip(seg[~vert], L[~vert], ang[~vert]):
        k = max(2, int(l / 8))
        pu.extend(np.linspace(x1, x2, k)); pv.extend(np.linspace(y1, y2, k)); pb.extend([int(round(a / 15.0)) % NB] * k)
    sv = seg[vert & (L >= 60)]
    return {"C": C, "cum": cum, "tau": tau, "pu": np.array(pu), "pv": np.array(pv), "pb": np.array(pb),
            "su": (sv[:, 0] + sv[:, 2]) / 2, "s1": np.minimum(sv[:, 1], sv[:, 3]), "s2": np.maximum(sv[:, 1], sv[:, 3])}


def noter(mod, car, cams, pas_col=8, detail=False):
    """Note de chaque caméra (n, 8) [x, y, z, cap, tangage, f, u0, v0] : (1) les lignes prévues par la 3D tombent sur des lignes
    de la photo ; (2) les lignes de la photo au-dessus de l'horizon (plafond, hauts de portes et de fenêtres) et ses grandes
    verticales sont expliquées par la 3D. Note = moyenne harmonique des deux parts."""
    C, cum, tau = car["C"], car["cum"], car["tau"]
    h, w = C.shape[1:]
    cams = np.atleast_2d(np.asarray(cams, float))
    n = len(cams)
    P, z, cap, f, u0, v0 = cams[:, :2], cams[:, 2], np.radians(cams[:, 3]), cams[:, 5], cams[:, 6], cams[:, 7]
    us = np.arange(pas_col / 2, w, pas_col)
    delta = np.arctan((u0[:, None] - us[None]) / f[:, None])  # (n, Cc)
    th = cap[:, None] + delta
    D = np.stack([np.cos(th), np.sin(th)], 2)
    t, i = lancer(mod, P, D)
    prof = t * np.cos(delta)
    fini = np.isfinite(prof)
    prof = np.where(fini, prof, 1e6)
    g = mod["genre"][i]
    hsp = mod["hsp"]
    appui, prevu = np.zeros(n), np.zeros(n)
    trace = []
    cp = np.clip((car["pu"] / pas_col).astype(int), 0, len(us) - 1)  # colonne de chaque point de la photo
    explique = np.zeros((n, len(cp)))
    meme = (np.roll(i, -1, 1) == i); meme[:, -1] = False
    memeg = (np.roll(i, 1, 1) == i); memeg[:, 0] = False
    ui = np.broadcast_to(np.clip(np.round(us), 0, w - 1).astype(int)[None], i.shape)

    def courbe(v, valide, poids):
        nonlocal appui, prevu, explique
        pente = np.where(meme, np.roll(v, -1, 1) - v, np.where(memeg, v - np.roll(v, 1, 1), np.nan)) / pas_col
        ok = valide & fini & np.isfinite(pente) & (v >= 0) & (v <= h - 1)
        b = np.round((np.degrees(np.arctan(np.nan_to_num(pente))) % 180) / 15.0).astype(int) % NB
        vi = np.clip(np.round(v), 0, h - 1).astype(int)
        s = C[b, vi, ui]
        appui += poids * (s * ok).sum(1) * pas_col
        prevu += poids * ok.sum(1) * pas_col
        # dans l'autre sens : les points de la photo proches de cette courbe, de même orientation
        dv = np.abs(v[:, cp] - car["pv"][None])
        db = np.abs((b[:, cp] - car["pb"][None] + NB // 2) % NB - NB // 2)
        explique = np.maximum(explique, np.clip(1.0 - dv / tau, 0, 1) * (ok[:, cp] & (db <= 1)))
        if detail:
            trace.append((ui[ok], vi[ok], s[ok]))
    courbe(v0[:, None] - f[:, None] * (hsp - z[:, None]) / prof, np.ones_like(fini), 1.0)  # plafond
    courbe(v0[:, None] + f[:, None] * z[:, None] / prof, g != 1, 0.5)  # pied des murs (pas devant une porte)
    courbe(v0[:, None] - f[:, None] * (mod["haut"][i] - z[:, None]) / prof, g != 0, 1.0)  # haut des portes et fenêtres
    courbe(v0[:, None] - f[:, None] * (mod["bas"][i] - z[:, None]) / prof, (g == 2) & (mod["bas"][i] > 0.05), 1.0)  # appuis
    # verticales : angles des murs, montants des portes et fenêtres
    S = mod["S"]
    dv = S[None] - P[:, None, :]  # (n, V, 2)
    dist = np.linalg.norm(dv, axis=2)
    Dv = dv / np.maximum(dist, 1e-6)[..., None]
    tv, _ = lancer(mod, P, Dv)
    dth = (np.arctan2(dv[..., 1], dv[..., 0]) - cap[:, None] + np.pi) % (2 * np.pi) - np.pi
    vu = (tv >= dist - 0.06) & (np.abs(dth) < np.radians(80)) & (dist > 0.3)
    pr = np.where(vu, dist * np.cos(dth), 1.0)
    u = u0[:, None] - f[:, None] * np.tan(np.where(vu, dth, 0.0))
    v1 = v0[:, None] - f[:, None] * (mod["SH"][None] - z[:, None]) / pr
    v2 = v0[:, None] - f[:, None] * (mod["SB"][None] - z[:, None]) / pr
    vu &= (u >= 0) & (u <= w - 1)
    uv = np.clip(np.round(u), 0, w - 1).astype(int)
    a1 = np.clip(np.round(v1), 0, h).astype(int)
    a2 = np.clip(np.round(v2), 0, h).astype(int)
    appui += ((cum[a2, uv] - cum[a1, uv]) * vu).sum(1)
    prevu += ((a2 - a1) * vu).sum(1)
    part_prevue = appui / np.maximum(prevu, 1.5 * w)  # trop peu de lignes prévues dans l'image : la part baisse
    # ce que la photo montre et que la 3D explique
    haut = car["pv"][None] < v0[:, None] - 15  # au-dessus de l'horizon : presque toujours de l'architecture
    tot = haut.sum(1) * 8.0
    exp = (explique * haut).sum(1) * 8.0
    if len(car["su"]):
        pres = (np.abs(u[:, :, None] - car["su"][None, None]) < tau) & vu[:, :, None]  # (n, V, S)
        recouvre = np.clip(np.minimum(a2[:, :, None], car["s2"][None, None]) - np.maximum(a1[:, :, None], car["s1"][None, None]), 0, None)
        lon = (car["s2"] - car["s1"])[None]
        exp += np.minimum((recouvre * pres).max(1), lon).sum(1)
        tot = tot + lon.sum()
    part_photo = exp / np.maximum(tot, 1.0)
    note = 2 * part_prevue * part_photo / np.maximum(part_prevue + part_photo, 1e-9)
    if detail:
        return note, trace, [(uv[0][vu[0]], a1[0][vu[0]], a2[0][vu[0]])], float(part_prevue[0]), float(part_photo[0])
    return note


def chercher(mod, car, vh, f, alphas, base, w, pas=0.25, zs=(0.9, 1.15, 1.4)):
    """Toutes les places (grille de `pas` m dans les pièces), 4 orientations par angle candidat, plusieurs hauteurs."""
    tout = np.concatenate(mod["pieces"])
    xs = np.arange(tout[:, 0].min() + 0.1, tout[:, 0].max(), pas)
    ys = np.arange(tout[:, 1].min() + 0.1, tout[:, 1].max(), pas)
    G = np.array([(x, y) for x in xs for y in ys])
    G = G[(piece_de(mod, G) >= 0)]
    G = G[dist_seg(G, mod["A"][mod["genre"] != 1], mod["B"][mod["genre"] != 1]).min(1) > 0.12]
    caps = [(base - al + 90 * k) % 360 for al in alphas for k in range(4)]
    res = []
    for cap in caps:
        for z in zs:
            for k in range(0, len(G), 150):
                g = G[k:k + 150]
                cams = np.column_stack([g, np.full(len(g), z), np.full(len(g), cap), np.zeros(len(g)), np.full(len(g), f),
                                        np.full(len(g), w / 2), np.full(len(g), vh)])
                res.append(np.column_stack([cams, noter(mod, car, cams)]))
    return np.concatenate(res)


def affiner(mod, car, cam, tours=40, echelle=1.0):
    cam = np.array(cam, float)
    pas = np.array([0.2, 0.2, 0.15, 4.0, 0, 30.0, 0, 20.0]) * echelle
    best = float(noter(mod, car, cam, pas_col=4)[0])
    for _ in range(tours):
        bouge = False
        for j in (0, 1, 3, 2, 7, 5):
            essais = []
            for sgn in (-1, 1):
                c = cam.copy(); c[j] += sgn * pas[j]
                if j == 2 and not 0.6 <= c[2] <= 1.9: continue
                if j == 5 and not 300 <= c[5] <= 850: continue
                essais.append(c)
            if not essais:
                continue
            ns = noter(mod, car, np.array(essais), pas_col=4)
            k = int(np.argmax(ns))
            if ns[k] > best + 1e-6 and piece_de(mod, essais[k][None, :2])[0] >= 0:
                cam, best, bouge = essais[k], float(ns[k]), True
        if not bouge:
            pas *= 0.5
            if pas[0] < 0.01:
                break
    return cam, best


def dessiner(im, mod, car, cam, couleur):
    _, tr, vt, pp, ph = noter(mod, car, cam, pas_col=4, detail=True)
    cv2.putText(im, f'3D sur photo {pp:.2f} / photo par 3D {ph:.2f}', (20, im.shape[0] - 20), 0, 0.8, couleur, 2)
    for ui, vi, s in tr:
        for u, v in zip(ui, vi):
            cv2.circle(im, (int(u), int(v)), 2, couleur, -1)
    for ui, a1, a2 in vt:
        for u, v1, v2 in zip(ui, a1, a2):
            cv2.line(im, (int(u), int(v1)), (int(u), int(v2)), couleur, 2)
    return im


if __name__ == "__main__":
    sortie = Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
    seulement = sys.argv[2:] or None
    bilan = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        mod = modele(log)
        base = ea.direction_murs(log)
        for nom, c in d["cameras"].items():
            if seulement and f"{app}/{nom}" not in seulement and app not in seulement:
                continue
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            gris = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            h, w = gris.shape
            t0 = time.time()
            seg, L = ea.segments(gris)
            vh, f, al, *_ = ea.fuite(seg, L, w, h)
            car = cartes(seg, h, w)
            gros = cartes(seg, h, w, tau=24.0)
            k = c["camera"]
            main = np.array([k[x] for x in ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")])
            n_main = float(noter(mod, car, main, pas_col=4)[0])
            R = chercher(mod, gros, vh, f, [al], base, w)
            ordre = np.argsort(-R[:, 8])
            choisis = []
            for o in ordre:
                r = R[o]
                if all(np.linalg.norm(r[:2] - q[:2]) > 0.6 or abs((r[3] - q[3] + 180) % 360 - 180) > 45 for q in choisis):
                    choisis.append(r)
                if len(choisis) == 24:
                    break
            fins = [affiner(mod, car, affiner(mod, gros, r[:8], tours=12)[0], echelle=0.5) for r in choisis]
            fins.sort(key=lambda x: -x[1])
            cam, note = fins[0]
            second = fins[1][1] if len(fins) > 1 else 0.0
            dpos = float(np.linalg.norm(cam[:2] - main[:2]))
            dcap = abs((cam[3] - main[3] + 180) % 360 - 180)
            pm, pa = piece_de(mod, main[None, :2])[0], piece_de(mod, cam[None, :2])[0]
            ligne = (f"{app} {nom} [{c.get('qualite')}] écart place {dpos:5.2f} m, cap {dcap:5.1f}°, z {cam[2]:.2f}/{main[2]:.2f}, f {cam[5]:.0f}/{main[5]:.0f}, "
                     f"pièce {'OK ' if pm == pa else 'NON'} ({mod['ids'][pa]}) | note {note:.2f} (2e {second:.2f}, main {n_main:.2f}) | {time.time() - t0:.0f} s")
            print(ligne, flush=True)
            bilan.append({"app": app, "nom": nom, "dpos": dpos, "dcap": float(dcap), "piece": bool(pm == pa), "note": note, "second": second,
                          "note_main": n_main, "cam": [float(x) for x in cam]})
            vis = np.hstack([dessiner(im.copy(), mod, car, main, (0, 200, 0)), dessiner(im.copy(), mod, car, cam, (0, 0, 255))])
            ecrire_image(sortie / f"{app}-{nom}.jpg", cv2.resize(vis, None, fx=0.6, fy=0.6))
    (sortie / "bilan.json").write_text(json.dumps(bilan, indent=1), encoding="utf-8")
    ok = [b for b in bilan if b["dpos"] < 0.5 and b["dcap"] < 8]
    print(f"bien placées (< 0,5 m et < 8°) : {len(ok)}/{len(bilan)}")
