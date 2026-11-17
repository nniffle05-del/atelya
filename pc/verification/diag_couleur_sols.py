r"""ÉTAPE 4 b (17/11/2026) : d'où vient la couleur de chaque sol ? Photo par photo, la part de lumière que le sol renvoie (contre le
blanc des murs de la même photo), pour chaque pièce et chaque zone décidées AVEC la lecture des photos.

    ..\atelya\.venv\Scripts\python.exe pc\verification\diag_couleur_sols.py [app-001 …]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol, photos_lues, reconnaitre_sols as rs  # noqa: E402
from moteur.oeil_dinov2 import charger  # noqa: E402

lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def main() -> int:
    clf = rs.Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
    oeil = charger(clf.oeil)
    pds = pas_du_sol.charger(avec_dino=False)
    for cas in sys.argv[1:] or list(CAS):
        releve, logement = lire(CAS[cas]["fiche"]), lire(CAS[cas]["logement"])
        logement = logement.get("logement", logement)
        for p in logement["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        lecture = lire(PC / "lectures-photos" / cas / "lecture.json")
        mesures = []
        rs.JOURNAL_COULEURS = mesures
        r = rs.reconnaitre(releve, logement, RACINE, oeil, clf, pas_du_sol=lambda n, rgb, cas=cas: pds.masque(f"{cas}/{n}", rgb),
                           lus=photos_lues.sols_lus(lecture, releve, logement), sols_des_photos=photos_lues.sols_des_photos(lecture))
        rs.JOURNAL_COULEURS = None
        print(f"== {cas}")
        for pid, s in r["pieces"].items():
            print(f"  {pid} {s['famille']} : couleur {s.get('couleur_photo')} sur {s.get('photos_couleur', 0)} photo(s)"
                  + (f" (seule : {s['couleur_photo_seule']})" if s.get("couleur_photo_seule") else ""))
            for k, z in enumerate(s["zones"]):
                print(f"     zone {k} {z['famille']} {z['surface_m2']} m² : couleur {z.get('couleur_photo')} sur {z.get('photos_couleur', 0)} photo(s)")
        for m in mesures:
            print(f"     {m['photo']} {m['region']} : {np.round(m['albedo'], 3).tolist()} sur {m['pixels']} points (blanc des murs {np.round(m['blanc'], 3).tolist()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
