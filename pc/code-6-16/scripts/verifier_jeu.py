"""Vérifie qu'un jeu refabriqué (sur le PC) est identique à celui du cloud : même géométrie, même taille d'image."""
import json, sys
from pathlib import Path
jeu, ref = Path(sys.argv[1]), Path(sys.argv[2])
m = {x["id"]: x["empreinte"] for x in json.loads((jeu / "manifest.json").read_text(encoding="utf-8"))["exemples"]}
ok = diff = 0
for ligne in ref.read_text(encoding="utf-8").split("\n"):
    if not ligne.strip():
        continue
    i, niv, emp, w, h = ligne.split()
    f = jeu / "exemples" / i / niv / "annotations.json"
    if not f.exists() or m.get(i) != emp:
        diff += 1; print("différent :", i, niv); continue
    im = json.loads(f.read_text(encoding="utf-8"))["image"]
    if (im["largeur"], im["hauteur"]) != (int(w), int(h)):
        diff += 1; print("taille différente :", i, niv, im["largeur"], im["hauteur"], w, h); continue
    ok += 1
print(f"{ok} niveaux identiques, {diff} différents")
