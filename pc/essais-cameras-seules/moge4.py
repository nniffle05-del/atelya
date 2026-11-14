"""Portes et fenêtres vues par leur RELIEF : sur chaque photo, ce qui est EN RETRAIT du mur (embrasure d'une fenêtre,
porte ouverte, baie) d'après les points en mètres de MoGe-2. Image de contrôle : le relief en couleurs, avec les portes et
fenêtres du plan dessinées à la place que donne la caméra faite à la main (le corrigé)."""
import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
from moteur import camera_photo as cp
import etape_b as eb
from moge1 import verticale, pic

BAS = 2.1


def repere(z, hsp):
    """Chaque point de la photo dans le repère de la pièce : hauteur au-dessus du sol, direction (degrés, + = gauche),
    distance horizontale à l'appareil ; et s'il appartient à une surface verticale. → dict ou None."""
    P, N, M = z["points"].astype(np.float32), z["normales"].astype(np.float32), z["masque"]
    haut = verticale({"points": P, "normales": N, "masque": M})
    av = np.array([0, 0, 1.0]) - haut * haut[2]; av /= np.linalg.norm(av)
    dr = np.cross(av, haut)
    if dr[0] < 0:
        dr = -dr
    h, a, b = P @ haut, P @ dr, P @ av
    nh = N @ haut
    horiz = M & (np.abs(nh) > 0.95)
    sol, plaf = pic(h[horiz & (h < -0.4)]), pic(h[horiz & (h > 0.3)])
    ech = 1.0
    if sol is not None and plaf is not None and 0.75 < hsp / (plaf - sol) < 1.33:
        ech = hsp / (plaf - sol)
    elif sol is None and plaf is None:
        return None
    if sol is None:
        sol = plaf - hsp / ech
    return {"h": (h - sol) * ech, "phi": np.degrees(np.arctan2(-a, b)), "r": np.hypot(a, b) * ech, "M": M,
            "vert": np.abs(nh) < 0.35, "devant": b > 0.2, "ech": ech, "z": -sol * ech,
            "n_a": N @ dr, "n_b": N @ av}


def mur_par_direction(R, hsp):
    """Pour chaque degré de direction : la distance du mur, mesurée en haut (au-dessus des portes et des meubles)."""
    bande = R["M"] & R["vert"] & R["devant"] & (R["h"] > BAS) & (R["h"] < hsp - 0.04)
    if bande.sum() < 1600:
        bande = R["M"] & R["vert"] & R["devant"] & (R["h"] > 1.5) & (R["h"] < hsp - 0.04)
    k = np.round(R["phi"][bande]).astype(int); ray = R["r"][bande]
    mur = {}
    for d in np.unique(k):
        v = ray[k == d]
        if len(v) >= 40:
            mur[int(d)] = float(np.median(v))
    return mur


def relief(R, mur):
    """Pour chaque point : de combien il est DERRIÈRE le mur de sa direction (m ; négatif = devant : meuble, rideau)."""
    d = np.array(sorted(mur)); v = np.array([mur[i] for i in d])
    rw = np.interp(R["phi"], d, v, left=np.nan, right=np.nan).astype(np.float32)  # entre deux degrés : mur vu de côté
    saut = np.interp(R["phi"], d[:-1] + 0.5, np.diff(d), left=1, right=1) > 3    # pas de mur mesuré entre les deux
    rw[saut] = np.nan
    rel = R["r"] - rw
    rel[~R["M"]] = np.where(np.isnan(rw[~R["M"]]), np.nan, 9.0)  # pas de mesure = ciel : très loin
    return rel, rw


def creux_propres(R, rel, hsp, seuil=0.05):
    """Les points nettement en retrait du mur, en taches larges (les rayures fines d'un mur vu de côté sont retirées)."""
    m = (~np.isnan(rel)) & (rel > seuil) & (R["h"] > 0.05) & (R["h"] < hsp - 0.05)
    k = max(5, int(R["M"].shape[1] / 80)) | 1
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)) > 0


def ouvertures_vues(R, rel, hsp, degres):
    """Pour chaque degré : y a-t-il un creux à hauteur de fenêtre (1,0-1,9 m) ? descend-il jusqu'au sol (porte, baie) ?"""
    c = creux_propres(R, rel, hsp)
    k = np.round(R["phi"]).astype(int)
    mesure = ~np.isnan(rel)
    mi = mesure & (R["h"] > 1.0) & (R["h"] < 1.9)
    ba = mesure & (R["h"] > 0.15) & (R["h"] < 0.8) & (rel > -0.12)  # en bas, on ne compte pas ce qu'un meuble cache
    creux, sol = np.zeros(len(degres), bool), np.zeros(len(degres), np.int8)  # sol : 1 oui, -1 non, 0 caché
    for i, d in enumerate(degres):
        col = k == int(d)
        n = (col & mi).sum()
        if n >= 20:
            creux[i] = (col & mi & c).sum() / n > 0.5
        nb = (col & ba).sum()
        if nb >= 20:
            sol[i] = 1 if (col & ba & c).sum() / nb > 0.5 else -1
    return creux, sol


def faces_vues(mod, cam):
    """Les portes et fenêtres du plan que la caméra voit (rayon vers le milieu non coupé par un mur)."""
    ferme = dict(mod, genre=np.zeros_like(mod["genre"]))
    vues = []
    P = np.array([[cam[0], cam[1]]])
    for i in np.where(mod["genre"] > 0)[0]:
        for t in (0.25, 0.5, 0.75):
            m = mod["A"][i] + t * (mod["B"][i] - mod["A"][i])
            d = m - P[0]; L = np.linalg.norm(d)
            if L < 0.05:
                continue
            tt, j = eb.lancer(ferme, P, (d / L)[None, None])
            if abs(tt[0, 0] - L) < 0.25:
                vues.append(i); break
    return vues


if __name__ == "__main__":
    src, sortie = Path(sys.argv[1]), Path(sys.argv[2]); sortie.mkdir(parents=True, exist_ok=True)
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        mod = eb.modele(log)
        for nom, c in d["cameras"].items():
            z = np.load(src / f"{app}-{nom}.npz")
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            R = repere(z, mod["hsp"])
            mur = mur_par_direction(R, mod["hsp"])
            rel, rw = relief(R, mur)
            # couleurs : bleu = devant le mur (meuble), gris = le mur, jaune → rouge = en retrait, violet = on voit à travers
            vis = (im * 0.35).astype(np.uint8)
            ok = ~np.isnan(rel) & (R["h"] > 0.05) & (R["h"] < mod["hsp"] - 0.05)
            cr = creux_propres(R, rel, mod["hsp"])
            for (lo, hi), coul in (((0.04, 0.10), (0, 255, 255)), ((0.10, 0.30), (0, 165, 255)), ((0.30, 1.0), (0, 0, 255)), ((1.0, 99), (255, 0, 200))):
                m = ok & cr & (rel > lo) & (rel <= hi)
                vis[m] = (0.5 * vis[m] + 0.5 * np.array(coul)).astype(np.uint8)
            m = ok & (rel < -0.15); vis[m] = (0.7 * vis[m] + 0.3 * np.array((255, 120, 0))).astype(np.uint8)
            k = c["camera"]; cam = [k[n] for n in cp.NOMS]
            for i in faces_vues(mod, cam):
                a, b = mod["A"][i], mod["B"][i]
                coins = [(a, mod["bas"][i]), (b, mod["bas"][i]), (b, mod["haut"][i]), (a, mod["haut"][i])]
                pts = [cp.projeter([p[0], p[1], zz], cam) for p, zz in coins]
                if min(p[2] for p in pts) < 0.3:
                    continue
                cv2.polylines(vis, [np.array([[p[0], p[1]] for p in pts], np.int32)], True, (0, 255, 0) if mod["genre"][i] == 2 else (255, 255, 255), 2)
            ecrire_image(sortie / f"{app}-{nom}.jpg", np.hstack([im, vis]))
            print(app, nom, f"{len(mur)}° de murs vus, échelle {R['ech']:.2f}", flush=True)
