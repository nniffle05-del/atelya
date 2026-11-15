r"""« Même lieu » (Depth Anything 3) entre TOUTES les paires de photos de chaque logement : de quoi juger comment former
les groupes de photos d'une même pièce (15/11/2026). Sortie : ..\atelya\b2\cameras-seules\jumelles\accords-<logement>.json

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles_accords.py
"""
import json
import sys
from pathlib import Path

import cv2

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur import caler_photos as cp, da3  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from jumelles import LOGEMENTS, SORTIE  # noqa: E402

modele = da3.charger(appareil="cuda")
for nom, f in LOGEMENTS.items():
    photos = {n: cv2.cvtColor(lire_image(f["photos"] / f"{n}.{f['ext']}"), cv2.COLOR_BGR2RGB) for n in f["vrai"]}
    noms = list(photos)
    acc = {f"{a}|{b}": round(cp.meme_lieu(modele, photos[a], photos[b]), 3) for i, a in enumerate(noms) for b in noms[i + 1:]}
    (SORTIE / f"accords-{nom}.json").write_text(json.dumps(acc), encoding="utf-8")
    meme = [v for k, v in acc.items() if set(f["vrai"][k.split("|")[0]]) & set(f["vrai"][k.split("|")[1]])]
    autre = [v for k, v in acc.items() if not set(f["vrai"][k.split("|")[0]]) & set(f["vrai"][k.split("|")[1]])]
    print(f"{nom} : {len(meme)} paires de la même pièce, {len(autre)} de pièces différentes", flush=True)
    for s in (0.3, 0.4, 0.5, 0.6, 0.7):
        print(f"   accord ≥ {s} : même pièce {sum(v >= s for v in meme)}/{len(meme)}, pièces différentes {sum(v >= s for v in autre)}/{len(autre)}", flush=True)
