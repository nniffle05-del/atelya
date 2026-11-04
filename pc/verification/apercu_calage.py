"""Aperçu : dessine les murs et ouvertures d'un verification.json sur son plan.png, avec le calage du fichier.
    python pc\\verification\\apercu_calage.py ..\\atelya\\lectures-verification\\fr-006 sortie.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

dossier, sortie = Path(sys.argv[1]), Path(sys.argv[2])
v = json.loads((dossier / "verification.json").read_text(encoding="utf-8"))
M = np.array(v["calage"]["matrice"])


def px(p):
    u, w, t = M @ (p[0], p[1], 1.0)
    return (u / t, w / t)


img = Image.open(dossier / "plan.png").convert("RGB")
d = ImageDraw.Draw(img)
ep = max(1, max(img.size) // 700)
murs = {m["id"]: m for m in v["logement"]["murs"]}
for m in murs.values():
    d.line([px(m["debut"]), px(m["fin"])], fill=(230, 30, 30), width=ep)
for o in v["logement"]["ouvertures"]:
    m = murs[o["mur"]]
    a, b = np.array(m["debut"]), np.array(m["fin"])
    e = (b - a) / np.linalg.norm(b - a)
    d.line([px(a + e * o["position"]), px(a + e * (o["position"] + o["largeur"]))], fill=(30, 90, 230), width=2 * ep)
for p in v["logement"]["pieces"]:
    d.line([px(q) for q in p["contour"] + p["contour"][:1]], fill=(30, 170, 80), width=ep)
img.thumbnail((1400, 1400))
img.save(sortie)
