r"""MESURE (20/11/2026, fenêtres F1) : la largeur des fenêtres d'après les photos, sur tous les logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_largeur_baies.py [app-001 app-002 app-004]

Pour chaque baie du plan : ce que chaque photo en voit (moteur.largeur_baies.mesures_d_une_photo), puis ce que la règle en
conclut (moteur.largeur_baies.elargir). Rien n'est écrit dans les logements : on lit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def mesurer(cas: str) -> tuple[list, list]:
    from banc_ressemblance import CAS
    from moteur import largeur_baies as lb
    from poser_photos_lues import objets_des_photos
    from sonde_largeur_fenetres import CHAINES, PC

    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement = json.loads((CHAINES[cas] / "logement-depart.json").read_text(encoding="utf-8"))
    mesures = lb.lire(logement, fiche, objets_des_photos(fiche, PC / "lectures-photos" / cas))
    print(f"\n=== {cas}")
    for o in logement["ouvertures"]:
        if o["type"] == "porte":
            continue
        portee = lb.portee_libre(o, logement)
        print(f"  {o['id']:4s} {o['type']:13s} plan {o['largeur']:.2f} m ; le mur laisse "
              + ("?" if portee is None else f"{portee[1] - portee[0]:.2f} m"))
        for m in (m for m in mesures if m["baie"] == o["id"]):
            print(f"       {m['photo']} : vue {m['s'][1] - m['s'][0]:.2f} m [{m['s'][0]:+.2f} … {m['s'][1]:+.2f}] par {m['par']}, "
                  f"bouts francs {['non', 'oui'][m['francs'][0]]} / {['non', 'oui'][m['francs'][1]]}, à {m['distance']:.1f} m")
    _, changes, doutes = lb.elargir(logement, mesures, journal=print)
    print(f"  → {len(changes)} baie(s) élargie(s), {len(doutes)} doute(s)")
    return changes, doutes


if __name__ == "__main__":
    for cas in sys.argv[1:] or ["app-001", "app-002", "app-004"]:
        mesurer(cas)
