r"""Le logement vu de dessus avec ses meubles et ses ÉQUIPEMENTS, pour contrôler leur pose à l'œil (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\plan_des_equipements.py <logement.json> <sortie.png> [<….equipements.json>]

Murs en gris, portes en brun, fenêtres en bleu, passe-plats en rose ; meubles en gris clair ; équipements en rouge (leur nom
à côté) ; avec le fichier des équipements : une croix orange à chaque endroit MESURÉ sur les photos (avant la pose).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur.meubles import EQUIPEMENTS  # noqa: E402

PX = 90  # pixels par mètre


def main() -> int:
    lg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    lg = lg.get("logement", lg)
    equip = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")) if len(sys.argv) > 3 else {}
    pts = [p for piece in lg["pieces"] for p in piece["contour"]] + [p for m in lg["murs"] for p in (m["debut"], m["fin"])]
    x0, y0 = min(p[0] for p in pts) - 0.6, min(p[1] for p in pts) - 0.6
    x1, y1 = max(p[0] for p in pts) + 0.6, max(p[1] for p in pts) + 0.6
    P = lambda p: ((p[0] - x0) * PX, (y1 - p[1]) * PX)
    im = Image.new("RGB", (int((x1 - x0) * PX), int((y1 - y0) * PX)), "white")
    d = ImageDraw.Draw(im)
    try:
        police = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        police = ImageFont.load_default()
    for piece in lg["pieces"]:
        d.polygon([P(p) for p in piece["contour"]], fill=(246, 244, 238))
        c = [sum(p[0] for p in piece["contour"]) / len(piece["contour"]), sum(p[1] for p in piece["contour"]) / len(piece["contour"])]
        d.text(P(c), piece["id"], fill=(150, 150, 150), font=police)
    murs = {m["id"]: m for m in lg["murs"]}
    for m in lg["murs"]:
        d.line([P(m["debut"]), P(m["fin"])], fill=(90, 90, 90), width=max(2, int(m.get("epaisseur", 0.2) * PX)))
        mil = [(m["debut"][0] + m["fin"][0]) / 2, (m["debut"][1] + m["fin"][1]) / 2]
        d.text(P(mil), m["id"], fill=(0, 120, 0), font=police)
    for o, couleur in [(o, (150, 100, 50) if o["type"] == "porte" else (60, 130, 230)) for o in lg.get("ouvertures", [])] + \
                      [(o, (240, 60, 160)) for o in lg.get("passe_plats", [])]:
        m = murs[o["mur"]]
        L = math.dist(m["debut"], m["fin"])
        u = [(m["fin"][0] - m["debut"][0]) / L, (m["fin"][1] - m["debut"][1]) / L]
        a = [m["debut"][0] + u[0] * o["position"], m["debut"][1] + u[1] * o["position"]]
        b = [a[0] + u[0] * o["largeur"], a[1] + u[1] * o["largeur"]]
        d.line([P(a), P(b)], fill=couleur, width=max(3, int(m.get("epaisseur", 0.2) * PX)))
        d.text(P(a), o["id"], fill=couleur, font=police)
    for m in lg.get("meubles", []):
        a = math.radians(m.get("face", 0.0))
        av, cote = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        l, p = m["dimensions"][0], m["dimensions"][1]
        coins = [(m["position"][0] + sl * l / 2 * cote[0] + sp * p / 2 * av[0], m["position"][1] + sl * l / 2 * cote[1] + sp * p / 2 * av[1])
                 for sl, sp in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        est_equipement = m["categorie"] in EQUIPEMENTS
        d.polygon([P(c) for c in coins], outline=(220, 30, 30) if est_equipement else (120, 120, 120),
                  fill=(255, 205, 205) if est_equipement else None)
        nez = (m["position"][0] + av[0] * p / 2, m["position"][1] + av[1] * p / 2)
        d.line([P(m["position"]), P(nez)], fill=(220, 30, 30) if est_equipement else (120, 120, 120))
        d.text(P(coins[3]), m["categorie"] if est_equipement else m["categorie"][:10], fill=(200, 0, 0) if est_equipement else (110, 110, 110),
               font=police)
    for e in equip.get("mesures", []):
        x, y = P(e["point"])
        d.line([(x - 5, y - 5), (x + 5, y + 5)], fill=(255, 140, 0), width=2)
        d.line([(x - 5, y + 5), (x + 5, y - 5)], fill=(255, 140, 0), width=2)
        d.text((x + 6, y - 6), f"{e['sorte']} ({e['vues']})", fill=(230, 120, 0), font=police)
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    im.save(sys.argv[2])
    print(sys.argv[2], im.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
