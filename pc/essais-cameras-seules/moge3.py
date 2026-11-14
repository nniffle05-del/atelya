"""Qui a raison, MoGe-2 ou le plan ? Distances entre repères verticaux (coins, montants) relevés à la main sur les photos :
mesurées par MoGe-2 contre celles du plan. Indépendant de la caméra faite à la main."""
import json, sys
from pathlib import Path
import numpy as np
from moge1 import verticale, pic

src = Path(sys.argv[1]); tout = []
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    hsp = float(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")).get("hauteur_sous_plafond", 2.5))
    for nom, c in d["cameras"].items():
        z = np.load(src / f"{app}-{nom}.npz"); P, N, M = z["points"].astype(np.float32), z["normales"].astype(np.float32), z["masque"]
        H, W = M.shape; ex, ey = W / c["largeur"], H / c["hauteur"]
        haut = verticale({"points": P, "normales": N, "masque": M})
        av = np.array([0, 0, 1.0]) - haut * haut[2]; av /= np.linalg.norm(av); dr = np.cross(av, haut); dr = dr if dr[0] > 0 else -dr
        p = P[::4, ::4][M[::4, ::4]]; n = N[::4, ::4][M[::4, ::4]]; h = p @ haut; hz = np.abs(n @ haut) > 0.95
        sol, plaf = pic(h[hz & (h < -0.4)]), pic(h[hz & (h > 0.3)])
        pts = []
        for r in c["reperes"]:
            if r["type"] != "ligne" or abs(r["a"][0] - r["b"][0]) > 0.01 or abs(r["a"][1] - r["b"][1]) > 0.01:
                continue
            (u1, v1), (u2, v2) = r["p1"], r["p2"]
            q = []
            for t in np.linspace(0.1, 0.9, 25):
                for du in (-4, 4):  # de part et d'autre de l'arête
                    u, v = int((u1 + t * (u2 - u1)) * ex + du), int((v1 + t * (v2 - v1)) * ey)
                    if 0 <= u < W and 0 <= v < H and M[v, u]:
                        q.append(P[v, u])
            if len(q) < 10:
                continue
            q = np.array(q); prof = q @ av
            q = q[prof >= np.percentile(prof, 60)]  # le mur est derrière les meubles
            pts.append((np.array(r["a"][:2]), np.array([np.median(q @ dr), np.median(q @ av)])))
        rap = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dp = np.linalg.norm(pts[i][0] - pts[j][0]); dm = pts[i][1] - pts[j][1]
                if dp > 0.8:
                    rap.append((np.linalg.norm(dm) / dp, abs(dm[1]) > abs(dm[0])))
        rap = np.array(rap) if rap else np.zeros((0, 2))
        lat, pro = rap[rap[:, 1] == 0, 0], rap[rap[:, 1] == 1, 0]
        hp = (plaf - sol) / hsp if sol and plaf else np.nan
        print(f"{app} {nom} : hauteur MoGe/plan {hp:.2f} | largeurs {np.median(lat) if len(lat) else np.nan:.2f} ({len(lat)}) | profondeurs {np.median(pro) if len(pro) else np.nan:.2f} ({len(pro)}) | focale MoGe/main {float(z['focale']) / c['camera']['f'] * c['largeur'] / W:.2f}")
        tout.append((hp, np.median(lat) if len(lat) else np.nan, np.median(pro) if len(pro) else np.nan))
t = np.array(tout)
print("MÉDIANES MoGe / plan : hauteur %.2f, largeurs %.2f, profondeurs %.2f" % tuple(np.nanmedian(t, 0)))
