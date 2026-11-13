r"""Ajoute à un logement meublé le décor proposé par Atelya (coussins, vases, lampes, plantes, tableaux ; moteur/decor.py).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\decorer.py logement.json sortie.json [--graine 1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.decor import decorer  # noqa: E402
from moteur.logement import Logement  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Décor proposé par Atelya")
    ap.add_argument("logement", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--graine", type=int, default=1)
    a = ap.parse_args()
    if not a.logement.is_file():
        print(f"PLANTÉ : fichier introuvable : {a.logement}", flush=True)
        return 2
    logement = json.loads(a.logement.read_text(encoding="utf-8"))
    ajouts = decorer(logement, a.graine)
    logement["meubles"] = logement.get("meubles", []) + ajouts
    Logement.model_validate(logement)
    a.sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"Décor ajouté : {dict(Counter(o['categorie'] for o in ajouts))} dans {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
