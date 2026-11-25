r"""LE DESSIN DES FENÊTRES LU PAR CLAUDE, sans appeler l'API : écrire la fiche d'un logement depuis les notes de la conversation.

    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\ecrire_vitrages.py app-004 [app-002 …]

Lit verites/<logement>/lecture_des_vitrages.py (VITRAGES), contrôle le format (moteur/vitrages.controler) et, si la liste
envoyée existe (..\atelya\lectures-photos\<logement>\envoi-vitrages\liste.json), que chaque fenêtre montrée a été lue ; écrit
..\atelya\lectures-photos\<logement>\vitrages.json (format vitrages-photos/0.1). S'arrête au premier défaut.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import vitrages  # noqa: E402


def notes_de(cas: str) -> dict:
    spec = importlib.util.spec_from_file_location(f"vitrages_{cas.replace('-', '_')}", RACINE / "verites" / cas / "lecture_des_vitrages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VITRAGES


def ecrire(cas: str) -> Path:
    dossier = PC / "lectures-photos" / cas
    lecture = {"format": vitrages.FORMAT, "photos": notes_de(cas)}
    tailles, defauts = {}, []
    liste = dossier / "envoi-vitrages" / "liste.json"
    if liste.is_file():
        a_lire = json.loads(liste.read_text(encoding="utf-8"))["a_lire"]
        tailles = {c["photo"]: tuple(c["taille"]) for c in a_lire}
        lues = {(photo, f["baie"]) for photo, fenetres in lecture["photos"].items() for f in fenetres}
        for c in a_lire:  # une fenêtre montrée et pas dite : la vue par elle reste comme avant (le trou du plan)
            if (c["photo"], c["baie"]) not in lues:
                print(f"  à noter : {c['photo']} {c['baie']} montrée mais pas lue" + (" (derrière un voilage)" if c.get("voilee") else ""), flush=True)
    defauts += vitrages.controler(lecture, tailles)
    if defauts:
        raise SystemExit(f"PLANTÉ : dessin des fenêtres de {cas} à corriger\n  " + "\n  ".join(defauts))
    (dossier / "vitrages.json").write_text(json.dumps(lecture, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(f) for f in lecture["photos"].values())
    print(f"{cas} : {len(lecture['photos'])} photos, {n} vitrages dits → {dossier / 'vitrages.json'}", flush=True)
    return dossier / "vitrages.json"


if __name__ == "__main__":
    for cas in sys.argv[1:]:
        ecrire(cas)
