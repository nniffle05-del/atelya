r"""POINT 2, ÉTAPE 3 (18/11/2026) : d'une prévision de réglages d'image à un ESSAI sur de vraies images du film.

    ..\atelya\.venv\Scripts\python.exe pc\verification\reglage_d_essai.py <prevision-reglages-image.json> <essai.json>

<prevision…json> : écrit par pc/verification/prevoir_reglages_image.py (crans d'exposition en plus, pente, pied, épaule de la
courbe des tons, vivacité). <essai.json> : le fichier que lit moteur/photographe.py quand la variable d'environnement
ATELYA_REGLAGE_IMAGE le nomme (clarté visée des murs par éclairage, pellicule, couleurs) ; il vaut alors pour le photographe, la
préparation Unreal, la vue par les fenêtres et le juge.

Les éclairages :
- « jour voilé » (le seul jugé contre les photos des clients) : clarté visée des murs × 2^crans ;
- les autres (soleil, fin de journée, soirée, nuit) : la clarté visée est recalculée pour que leurs murs s'AFFICHENT au même
  niveau qu'avant sous la nouvelle courbe (aucun changement voulu tant qu'ils ne sont pas jugés à leur tour).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur import photographe  # noqa: E402


def essai_depuis(prevision: dict) -> dict:
    avant = dict(photographe.PELLICULE)
    pellicule = {**avant, "film_slope": round(float(prevision["pente"]), 3), "film_toe": round(float(prevision["pied"]), 3),
                 "film_shoulder": round(float(prevision["epaule"]), 3)}
    if "blanc" in prevision:
        pellicule["film_white_clip"] = round(float(prevision["blanc"]), 4)
    clarte = {}
    for ident, visee in photographe.CLARTE_UNREAL.items():
        if ident == "jour_voile":
            clarte[ident] = round(float(visee) * 2.0 ** float(prevision["crans"]), 3)
        else:
            affiche = float(photographe.courbe_unreal(np.array([visee]), **avant)[0])
            clarte[ident] = round(float(photographe.lineaire_affiche(affiche, pellicule)), 3)
    return {"clarte": clarte, "pellicule": pellicule, "couleurs": {"saturation": round(float(prevision["vivacite"]), 3)}}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    essai = essai_depuis(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(essai, indent=1, ensure_ascii=False), encoding="utf-8")
    murs = float(photographe.courbe_unreal(np.array([essai["clarte"]["jour_voile"]]), **essai["pellicule"])[0])
    print(f"essai écrit : {sys.argv[2]}\n{json.dumps(essai, ensure_ascii=False)}\nmurs du jour voilé affichés à {255 * murs:.0f} sur 255 "
          f"(aujourd'hui {255 * float(photographe.courbe_unreal(np.array([photographe.CLARTE_UNREAL['jour_voile']]), **photographe.PELLICULE)[0]):.0f})",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
