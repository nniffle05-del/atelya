import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import ecrire_image
import etape_b as eb
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
    mod = eb.modele(log)
    E = 50
    tout = np.concatenate(mod["pieces"]); x0, y1 = tout[:, 0].min() - 1.5, tout[:, 1].max() + 1.5
    W, H = int((tout[:, 0].max() + 1.5 - x0) * E), int((y1 - tout[:, 1].min() + 1.5) * E)
    im = np.full((H, W, 3), 255, np.uint8)
    px = lambda p: (int((p[0] - x0) * E), int((y1 - p[1]) * E))
    for a, b, g in zip(mod["A"], mod["B"], mod["genre"]):
        cv2.line(im, px(a), px(b), [(0, 0, 0), (0, 160, 0), (255, 120, 0)][g], 2)
    for c, i in zip(mod["pieces"], mod["ids"]):
        cv2.putText(im, i, px(c.mean(0)), 0, 0.4, (120, 120, 120), 1)
    for nom, c in d["cameras"].items():
        k = c["camera"]; p = np.array([k["x"], k["y"]]); t = np.radians(k["cap"])
        cv2.circle(im, px(p), 4, (0, 0, 255), -1)
        cv2.line(im, px(p), px(p + 0.8 * np.array([np.cos(t), np.sin(t)])), (0, 0, 255), 1)
        cv2.putText(im, nom[-2:], px(p + [0.1, 0.1]), 0, 0.45, (0, 0, 255), 1)
        print(app, nom, "piece", eb.piece_de(mod, p[None])[0])
    ecrire_image(Path(sys.argv[1]) / f"plan-{app}.png", im)
