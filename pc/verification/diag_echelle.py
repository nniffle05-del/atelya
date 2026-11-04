r"""Pourquoi l'échelle n'est-elle pas lue sur un vrai plan ? Pour chaque plan : les textes lus, ceux qui ressemblent à une
cote, ceux dont le trait a été mesuré, et les formes que la lecture ignore aujourd'hui (cotes en centimètres entiers,
surfaces à une décimale, « m2 » sans exposant…). Ne règle rien : il mesure.

    ..\atelya\.venv\Scripts\python.exe pc\verification\diag_echelle.py plan1.jpg plan2.pdf ...
"""
import collections
import re
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, ".")
from moteur.echelle_plan import _lire  # noqa: E402
from moteur.lecture_complete import plans_du_fichier  # noqa: E402
from moteur.lecture_cotes import FORME_COTE, lire_echelle  # noqa: E402
from moteur.surfaces_ecrites import FORME_SURFACE  # noqa: E402

ENTIER_CM = re.compile(r"^\d{2,4}$")  # « 405 », « 36 » : cotes en centimètres (fr-010), ou une virgule perdue (« 560 »)
SURFACE_LARGE = re.compile(r"(\d{1,3}[,.]\d{1,2})\s*(m²|m2|m\s*2|M2)", re.IGNORECASE)
ECHELLE = re.compile(r"1\s*[:/]\s*(\d{2,3})")


def resume(nom: str, gris: np.ndarray, textes_pdf=None) -> None:
    if textes_pdf is not None:
        echelle = lire_echelle(gris, textes_pdf)
        textes = textes_pdf
        nombres = [(float(t.texte.replace(",", ".")), False) for t in textes if FORME_COTE.match(t.texte)]
    else:
        echelle, nombres, textes = _lire(gris)
    mots = [t.texte for t in textes]
    formes = [m for m in mots if FORME_COTE.match(m)]
    entiers = [m for m in mots if ENTIER_CM.match(m)]
    surfaces_ok = [m for m in mots if FORME_SURFACE.search(m)]
    surfaces_larges = [m for m in mots if SURFACE_LARGE.search(m) and not FORME_SURFACE.search(m)]
    echelles = [m for m in mots if ECHELLE.search(m) and "m" not in m.lower()]
    retenues = [(c.valeur, round(c.px_par_m, 1)) for c in echelle.retenues]
    ecartees = [(c.valeur, round(c.px_par_m, 1)) for c in echelle.ecartees]
    print(f"== {nom} ({gris.shape[1]}×{gris.shape[0]} px) : {len(mots)} textes lus")
    print(f"   échelle : {echelle.px_par_m} px/m, sûre={echelle.sure}, contredite={echelle.contredite} ; retenues {retenues} ; écartées {ecartees}")
    print(f"   en forme de cote (d,dd) : {len(formes)} → {formes[:14]}")
    print(f"   sans trait mesuré : {len(formes) - len(retenues) - len(ecartees)}")
    print(f"   entiers (cm ?) : {len(entiers)} → {entiers[:14]}")
    print(f"   surfaces reconnues : {surfaces_ok[:6]} ; surfaces NON reconnues (1 décimale, m2…) : {surfaces_larges[:8]}")
    if echelles:
        print(f"   échelle écrite : {echelles}")
    autres = [m for m in mots if not (FORME_COTE.match(m) or ENTIER_CM.match(m) or FORME_SURFACE.search(m) or SURFACE_LARGE.search(m))]
    print(f"   autres : {autres[:12]}")


def main() -> int:
    for chemin in sys.argv[1:]:
        for source in plans_du_fichier(Path(chemin)):
            img = source.image
            gris = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            resume(source.nom, gris, source.textes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
