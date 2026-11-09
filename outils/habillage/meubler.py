r"""Ajoute à un logement les meubles et les rideaux relevés sur les photos (B4, 09/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\meubler.py logement.json verites\app-001\meubles.json sortie.json

Le fichier de meubles : {"meubles": [... format Meuble de moteur/logement.py ...],
                         "rideaux": {"<id de l'ouverture>": {"voilage": [r, g, b] | null, "rideaux": [r, g, b] | null,
                                                              "statut": "estime", "source": "photo 08"}}}
Les meubles déjà présents dans le logement sont remplacés ; le logement écrit est vérifié (format et cohérence).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.logement import Logement  # noqa: E402


def meubler(logement: dict, meubles: dict) -> dict:
    sortie = json.loads(json.dumps(logement))
    sortie["meubles"] = meubles.get("meubles", [])
    rideaux = meubles.get("rideaux", {})
    connus = {o["id"] for o in sortie.get("ouvertures", [])}
    inconnus = sorted(set(rideaux) - connus)
    if inconnus:
        raise KeyError(f"rideaux pour des ouvertures inconnues : {', '.join(inconnus)}")
    for o in sortie.get("ouvertures", []):
        if o["id"] in rideaux:
            o["rideaux"] = rideaux[o["id"]]
    Logement.model_validate(sortie)
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser(description="Ajoute meubles et rideaux relevés à un logement")
    ap.add_argument("logement", type=Path)
    ap.add_argument("meubles", type=Path)
    ap.add_argument("sortie", type=Path)
    a = ap.parse_args()
    for f in (a.logement, a.meubles):
        if not f.is_file():
            print(f"PLANTÉ : fichier introuvable : {f}", flush=True)
            return 2
    sortie = meubler(json.loads(a.logement.read_text(encoding="utf-8")), json.loads(a.meubles.read_text(encoding="utf-8")))
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    a.sortie.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(sortie['meubles'])} meubles, {sum(1 for o in sortie['ouvertures'] if o.get('rideaux'))} fenêtres habillées : {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
