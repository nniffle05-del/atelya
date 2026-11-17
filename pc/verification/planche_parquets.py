r"""Tous les PARQUETS de la bibliothèque, vus de dessus à la même échelle (2 m × 2 m chacun), pour juger à l'œil ce qu'Atelya
peut poser (17/11/2026, NT : « je pense qu'on n'a pas assez de parquet »).

    ..\atelya\.venv\Scripts\python.exe pc\verification\planche_parquets.py <sortie.jpg>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur.matieres import CALCULEES, SOLS  # noqa: E402

BIB = RACINE.parent / "atelya" / "bibliotheque" / "matieres"
COTE_M, COTE_PX, COLONNES = 2.0, 360, 6


def main() -> int:
    infos = json.loads((BIB / "matieres.json").read_text(encoding="utf-8"))
    try:
        police = ImageFont.truetype("arialbd.ttf", 20)
    except OSError:
        police = ImageFont.load_default()
    cases = []
    for nom, (libelle, sorte) in SOLS.items():
        if sorte != "bois" or nom in CALCULEES or nom not in infos or not (BIB / nom / "couleur.jpg").is_file():
            continue
        tex = Image.open(BIB / nom / "couleur.jpg").convert("RGB")
        px_par_m = tex.width / infos[nom]["taille_image_m"][0]
        cote = int(COTE_M * px_par_m)
        copies = int(np.ceil(cote / min(tex.size))) + 1
        grand = Image.new("RGB", (tex.width * copies, tex.height * copies))
        for i in range(copies):
            for j in range(copies):
                grand.paste(tex, (i * tex.width, j * tex.height))
        vignette = grand.crop((0, 0, cote, cote)).resize((COTE_PX, COTE_PX), Image.LANCZOS)
        case = Image.new("RGB", (COTE_PX + 12, COTE_PX + 58), (255, 255, 255))
        case.paste(vignette, (6, 6))
        d = ImageDraw.Draw(case)
        d.text((8, COTE_PX + 8), libelle[:34], fill=(0, 0, 0), font=police)
        d.text((8, COTE_PX + 32), nom, fill=(110, 110, 110), font=police)
        cases.append(case)
    lignes = [cases[i:i + COLONNES] for i in range(0, len(cases), COLONNES)]
    w, h = cases[0].size
    planche = Image.new("RGB", (w * COLONNES, h * len(lignes) + 50), (255, 255, 255))
    ImageDraw.Draw(planche).text((10, 10), f"Les {len(cases)} parquets à lames de la bibliothèque, vus de dessus (chaque carré = 2 m × 2 m)", fill=(0, 0, 0), font=police)
    for l, ligne in enumerate(lignes):
        for c, case in enumerate(ligne):
            planche.paste(case, (c * w, 50 + l * h))
    planche.save(sys.argv[1], quality=90)
    print(f"{len(cases)} parquets : {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
