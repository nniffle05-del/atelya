import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
import etape_a as ea, etape_b as eb
app, nom = sys.argv[1], sys.argv[2]
d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
mod = eb.modele(log)
im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
gris = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); h, w = gris.shape
seg, L = ea.segments(gris)
car = eb.cartes(seg, h, w)
k = d["cameras"][nom]["camera"]
main = np.array([k[x] for x in ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")])
dedans = main.copy()
t = np.radians(main[3])
while eb.piece_de(mod, dedans[None, :2])[0] < 0 or eb.dist_seg(dedans[None, :2], mod["A"], mod["B"]).min() < 0.12:
    dedans[:2] += 0.05 * np.array([np.cos(t), np.sin(t)])
print("main dedans", dedans[:4].round(2), "note", eb.noter(mod, car, dedans, pas_col=4))
fin, n = eb.affiner(mod, car, dedans)
print("affinée", fin.round(2), n)
sg = im.copy()
for x1, y1, x2, y2 in seg:
    cv2.line(sg, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 255), 1)
vis = np.vstack([np.hstack([eb.dessiner(im.copy(), mod, car, dedans, (0, 200, 0)), eb.dessiner(im.copy(), mod, car, fin, (0, 0, 255))]), np.hstack([sg, im])])
ecrire_image(Path(sys.argv[3]), cv2.resize(vis, None, fx=0.6, fy=0.6))
