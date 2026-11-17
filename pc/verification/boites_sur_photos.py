r"""Les meubles d'un relevé dessinés en BOÎTES sur les photos du client, pour contrôler le relevé à l'œil (17/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\boites_sur_photos.py <logement> <sortie> [--photos photo-04 photo-10 …] [--seuls id id …]

Pourquoi : le relevé fait à la main (verites/<logement>/meubles.json) est le juge de la pose des meubles ; il a été complété le
17/11/2026 (verites/<logement>/meubles-complement.json : vrais meubles oubliés, places corrigées). Un relevé se contrôle en
redessinant chaque meuble sur les photos avec les caméras relevées : la boîte doit tomber sur le vrai meuble.
Vert : relevé d'origine ; magenta : complément ; orange : meuble d'origine que le complément corrige (son ancienne place).
Écrit <sortie>/<logement>-<photo>.jpg (largeur 1206).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from banc_ressemblance import CAS, lire_photo  # noqa: E402
from moteur.camera_photo import camera_depuis_dict, projeter  # noqa: E402

ARETES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def coins(m: dict) -> list[tuple[float, float, float]]:
    a = math.radians(m.get("face", 0.0) or 0.0)
    av, cote = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    l, p, h = m["dimensions"][0] / 2, m["dimensions"][1] / 2, m["dimensions"][2]
    x, y = m["position"]
    z = float(m.get("altitude") or 0.0)
    bas = [(x + s * cote[0] * l + t * av[0] * p, y + s * cote[1] * l + t * av[1] * p) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return [(bx, by, z) for bx, by in bas] + [(bx, by, z + h) for bx, by in bas]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cas")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--photos", nargs="*")
    ap.add_argument("--seuls", nargs="*", help="ne dessiner que ces meubles (ids)")
    a = ap.parse_args()
    import essai_lecture_photos as essai

    fiche = json.loads(Path(CAS[a.cas]["fiche"]).read_text(encoding="utf-8"))
    origine = essai.lire(essai.VERITES[a.cas]["meubles"])["meubles"]
    comp_f = Path(essai.VERITES[a.cas]["meubles"]).with_name("meubles-complement.json")
    comp = essai.lire(comp_f) if comp_f.is_file() else {"meubles": [], "corrections": {}}
    corriges = set(comp.get("corrections", {}))
    lots = [((0, 170, 0), [m for m in origine if m["id"] not in corriges]), ((240, 140, 0), [m for m in origine if m["id"] in corriges]),
            ((230, 0, 200), comp["meubles"] + [{**next(m for m in origine if m["id"] == i), **c} for i, c in comp.get("corrections", {}).items()])]
    a.sortie.mkdir(parents=True, exist_ok=True)
    try:
        police = ImageFont.truetype("arialbd.ttf", 15)
    except OSError:
        police = ImageFont.load_default()
    for nom, d in fiche["cameras"].items():
        if a.photos and nom not in a.photos:
            continue
        cam = camera_depuis_dict(d["camera"])
        im = Image.fromarray(lire_photo(fiche, nom))
        g = ImageDraw.Draw(im)
        for couleur, meubles in lots:
            for m in meubles:
                if a.seuls and m["id"] not in a.seuls:
                    continue
                pts = [projeter(c, cam) for c in coins(m)]
                if any(p[2] < 0.25 for p in pts) or not any(0 <= p[0] < im.width and 0 <= p[1] < im.height for p in pts):
                    continue
                for i, j in ARETES:
                    g.line([pts[i][:2], pts[j][:2]], fill=couleur, width=3)
                cx, cy = sum(p[0] for p in pts[4:]) / 4, sum(p[1] for p in pts[4:]) / 4
                g.text((cx, cy), m["id"], fill=couleur, font=police, anchor="mm", stroke_width=2, stroke_fill="white")
        f = a.sortie / f"{a.cas}-{nom}.jpg"
        im.convert("RGB").save(f, quality=85)
        print(f, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
