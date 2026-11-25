r"""Un coin de logement vu de dessus, HIER | AUJOURD'HUI, sans relevé fait à la main (17/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\plan_simple.py <logement hier.json> <logement aujourd'hui.json> <sortie.jpg> ^
        --zone x0 y0 x1 y1 [--titres "hier" "aujourd'hui"]

Pourquoi : montrer à NT le rangement d'une cuisine quand aucune vue « depuis la place de la photo » n'est lisible (appareil placé
dans un meuble) et que le logement n'a pas de relevé (plan_avant_apres.py en demande un). Murs en gris, chaque objet posé au sol
dans la zone en couleur avec son nom en clair ; les objets accrochés et les tapis ne sont pas dessinés.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NOMS = {"meuble_cuisine_bas": "meuble bas", "colonne_cuisine": "colonne", "refrigerateur": "réfrigérateur", "rangement": "buffet",
        "ilot": "îlot", "table": "table", "chaise": "chaise", "tabouret_haut": "tabouret", "placard": "placard", "etagere_cubes": "étagère"}
COULEURS = {"meuble_cuisine_bas": (40, 110, 200), "colonne_cuisine": (150, 95, 40), "refrigerateur": (110, 110, 120)}
ECHELLE = 170  # pixels par mètre


def dessiner(logement: dict, zone, titre: str) -> Image.Image:
    x0, y0, x1, y1 = zone
    L, H = int((x1 - x0) * ECHELLE), int((y1 - y0) * ECHELLE)
    im = Image.new("RGB", (L, H + 46), "white")
    g = ImageDraw.Draw(im)
    try:
        gras, petit = ImageFont.truetype("arialbd.ttf", 22), ImageFont.truetype("arial.ttf", 15)
    except OSError:
        gras = petit = ImageFont.load_default()
    P = lambda x, y: ((x - x0) * ECHELLE, 46 + (y1 - y) * ECHELLE)
    for p in logement["pieces"]:
        g.polygon([P(*c) for c in p["contour"]], fill=(244, 243, 238))
    for m in logement.get("murs", []):
        g.line([P(*m["debut"]), P(*m["fin"])], fill=(70, 70, 70), width=max(3, int(float(m.get("epaisseur", 0.2)) * ECHELLE)))
    for m in logement.get("meubles", []):
        x, y = m["position"]
        if not (x0 <= x <= x1 and y0 <= y <= y1) or float(m.get("altitude") or 0) > 0.3 or m["categorie"] in ("tapis", "evier", "plaque", "four"):
            continue
        a = math.radians(float(m.get("face", 0.0)))
        f, t = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        l, p = m["dimensions"][0] / 2, m["dimensions"][1] / 2
        coins = [P(x + s * t[0] * l + u * f[0] * p, y + s * t[1] * l + u * f[1] * p) for s, u in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        c = COULEURS.get(m["categorie"], (90, 150, 90))
        g.polygon(coins, outline=c, fill=tuple(int(255 - (255 - v) * 0.28) for v in c))
        g.line(coins + coins[:1], fill=c, width=3)
        g.text(P(x, y), NOMS.get(m["categorie"], m["categorie"].replace("_", " ")), fill=(20, 20, 20), font=petit, anchor="mm")
    g.rectangle([0, 0, L, 44], fill="white")  # le titre par-dessus tout (un mur du haut de la zone le recouvrait)
    g.text((8, 8), titre, fill="black", font=gras)
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hier", type=Path)
    ap.add_argument("aujourd_hui", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--zone", nargs=4, type=float, required=True)
    ap.add_argument("--titres", nargs=2, default=["hier", "aujourd'hui"])
    a = ap.parse_args()
    images = []
    for f, titre in zip((a.hier, a.aujourd_hui), a.titres):
        lg = json.loads(f.read_text(encoding="utf-8"))
        images.append(dessiner(lg.get("logement", lg), a.zone, titre))
    planche = Image.new("RGB", (images[0].width + images[1].width + 30, images[0].height), "white")
    planche.paste(images[0], (0, 0))
    planche.paste(images[1], (images[0].width + 30, 0))
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    planche.save(a.sortie, quality=90)
    print(a.sortie, planche.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
