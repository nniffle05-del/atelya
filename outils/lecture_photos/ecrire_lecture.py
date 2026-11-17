r"""LA LECTURE DES PHOTOS PAR CLAUDE, sans appeler l'API : écrire la fiche d'un logement depuis les notes prises dans la conversation.

    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\ecrire_lecture.py app-004 [app-002 …]

Lit verites/<logement>/lecture_des_photos.py (NOTES), contrôle chaque photo contre la liste numérotée envoyée
(..\atelya\lectures-photos\<logement>\envoi\<photo>.json) et écrit ..\atelya\lectures-photos\<logement>\lecture.json
(format lecture-photos/0.1, moteur/lecture_photos.py). S'arrête au premier défaut.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"

from moteur import lecture_photos as lp  # noqa: E402


def notes_de(cas: str) -> dict:
    spec = importlib.util.spec_from_file_location(f"lecture_{cas.replace('-', '_')}", RACINE / "verites" / cas / "lecture_des_photos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NOTES


def ecrire(cas: str) -> Path:
    dossier = PC / "lectures-photos" / cas
    lecture = lp.lecture_depuis_notes(notes_de(cas))
    defauts, sortes = [], Counter()
    for nom, fiche in lecture["photos"].items():
        liste = json.loads((dossier / "envoi" / f"{nom}.json").read_text(encoding="utf-8"))
        defauts += [f"{nom} : {d}" for d in lp.controler(fiche, {o["numero"] for o in liste})]
        sortes.update(o["sorte"] for o in lp.objets_lus(fiche, liste))
    oubliees = sorted(p.stem for p in (dossier / "envoi").glob("photo-*.json") if p.stem not in lecture["photos"])
    defauts += [f"{p} : photo non lue" for p in oubliees]
    if defauts:
        raise SystemExit(f"PLANTÉ : lecture de {cas} à corriger\n  " + "\n  ".join(defauts))
    (dossier / "lecture.json").write_text(json.dumps(lecture, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{cas} : {len(lecture['photos'])} photos lues → {dossier / 'lecture.json'}")
    print("  " + ", ".join(f"{n} {s}" for s, n in sortes.most_common()), flush=True)
    return dossier / "lecture.json"


if __name__ == "__main__":
    for cas in sys.argv[1:]:
        ecrire(cas)
