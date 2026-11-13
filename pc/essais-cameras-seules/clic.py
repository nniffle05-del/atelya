"""Un clic approximatif (place à ±0,4 m, direction à ±8°) puis ajustement seul : retombe-t-on toujours au même endroit ?"""
import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
import etape_a as ea, etape_b as eb
rng = np.random.default_rng(1)
sortie = Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
tot = []
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
    mod = eb.modele(log)
    for nom, c in d["cameras"].items():
        im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
        gris = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); h, w = gris.shape
        seg, L = ea.segments(gris)
        vh, f, al, *_ = ea.fuite(seg, L, w, h)
        fin_c, gros = eb.cartes(seg, h, w), eb.cartes(seg, h, w, tau=24.0)
        k = c["camera"]
        main = np.array([k[x] for x in ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")])
        q = main.copy()
        while eb.piece_de(mod, q[None, :2])[0] < 0 or eb.dist_seg(q[None, :2], mod["A"], mod["B"]).min() < 0.15:
            q[:2] += 0.05 * np.array([np.cos(np.radians(q[3])), np.sin(np.radians(q[3]))])
        res = []
        for e in range(4):
            dep = q.copy()
            for _ in range(50):
                p = q[:2] + rng.uniform(-0.4, 0.4, 2)
                if eb.piece_de(mod, p[None])[0] >= 0 and eb.dist_seg(p[None], mod["A"], mod["B"]).min() > 0.12:
                    dep[:2] = p; break
            dep[3] += rng.uniform(-8, 8); dep[2] = 1.2; dep[5] = f; dep[7] = vh
            cam, note = eb.affiner(mod, fin_c, eb.affiner(mod, gros, dep, tours=15)[0], echelle=0.5)
            res.append(cam)
        res = np.array(res)
        ecarts = [float(np.linalg.norm(r[:2] - main[:2])) for r in res]
        caps = [float(abs((r[3] - main[3] + 180) % 360 - 180)) for r in res]
        disp = float(np.linalg.norm(res[:, :2] - res[:, :2].mean(0), axis=1).max())
        dcap = float(np.abs((res[:, 3] - res[0, 3] + 180) % 360 - 180).max())
        print(f"{app} {nom} [{c.get('qualite')}] écart à la main : place {np.round(ecarts, 2)} m, cap {np.round(caps, 1)}° | les 4 essais entre eux : {disp:.2f} m, {dcap:.1f}°", flush=True)
        tot.append((max(ecarts), max(caps), disp, dcap))
        vis = np.hstack([eb.dessiner(im.copy(), mod, fin_c, q, (0, 200, 0)), eb.dessiner(im.copy(), mod, fin_c, res[0], (0, 0, 255))])
        ecrire_image(sortie / f"{app}-{nom}.jpg", cv2.resize(vis, None, fx=0.6, fy=0.6))
t = np.array(tot)
print("toujours à < 0,6 m et < 6° de la main :", int(((t[:, 0] < 0.6) & (t[:, 1] < 6)).sum()), "/", len(t), "| 4 essais d'accord (< 0,2 m, < 2°) :", int(((t[:, 2] < 0.2) & (t[:, 3] < 2)).sum()))
