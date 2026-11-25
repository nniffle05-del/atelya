r"""« PLACE ET TAILLE JUSTES » : d'où vient chaque meuble posé d'après la lecture des photos (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\trace_pose.py <dossier de l'essai> <logement> [version]

Refait la pose (moteur.photos_lues.poser) sur le logement des sols de l'essai et dit, pour chaque meuble trouvé : sa sorte, sa
place, et chacune de ses VUES (photo, numéro du rectangle, distance à l'appareil, place mesurée, rectangle approché ou non).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS, PC  # noqa: E402
import poser_photos_lues as ppl  # noqa: E402
from moteur import photos_lues  # noqa: E402


def main() -> int:
    dossier, cas = Path(sys.argv[1]), sys.argv[2]
    version = sys.argv[3] if len(sys.argv) > 3 else "c"
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement = json.loads((dossier / cas / version / "logement-sols.json").read_text(encoding="utf-8"))
    objets = ppl.objets_des_photos(fiche, PC / "lectures-photos" / cas)
    r = photos_lues.poser(fiche, logement, RACINE, objets)
    photos = r["trace"]["photos"]
    poses = {m["id"]: m for m in r["meubles"]}
    for k, t in enumerate(r["trace"]["trouves"], start=1):
        m = poses.get(f"reperage_{k}")
        fin = f"→ posé {m['position']} {m['dimensions']} face {m['face']}" if m else "→ RETIRÉ (rangement)"
        print(f"reperage_{k:<3d} {t['categorie']:18s} {t['position']} {t['vues']} vue(s) conf {t['confiance']} {fin}")
        for v in t["membres"]:
            print(f"      {photos[v['photo']]} n°{v['numero']} à {v['distance']:.1f} m  {[round(c, 2) for c in v['position']]}"
                  + ("  (rectangle approché)" if v["approche"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
