"""Commande unique : d'un logement.json à une maquette Blender.

    uv run python -m moteur.construire exemples/cas-test-00/logement.json sorties/cas-test-00

Produit dans le dossier de sortie :
- construction.json : la liste des briques calculées (lisible, utile pour vérifier) ;
- maquette.blend : la maquette, à ouvrir dans Blender.

Blender est lancé « sans écran » (en arrière-plan). Pour utiliser un autre
Blender que celui installé dans Applications, définir la variable
d'environnement BLENDER avec son chemin.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from moteur.geometrie import plan_de_construction
from moteur.logement import charger_logement

DOSSIER_SCRIPTS = Path(__file__).parent / "blender"
BLENDER_MAC = "/Applications/Blender.app/Contents/MacOS/Blender"


def trouver_blender() -> str | None:
    """Le chemin de Blender, ou None s'il est introuvable."""
    for candidat in (os.environ.get("BLENDER"), shutil.which("blender"), BLENDER_MAC):
        if candidat and Path(candidat).is_file():
            return candidat
    return None


def lancer_blender(*arguments: str) -> None:
    blender = trouver_blender()
    if blender is None:
        raise FileNotFoundError("Blender introuvable (définir la variable BLENDER)")
    # -b : sans écran ; --factory-startup : sans les réglages ni modules perso ;
    # --python-exit-code 1 : signaler l'échec si le script plante.
    commande = [blender, "-b", "--factory-startup", "--python-exit-code", "1", *arguments]
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        raise RuntimeError(f"Blender a échoué :\n{resultat.stdout}\n{resultat.stderr}")


def construire(chemin_logement: str | Path, dossier_sortie: str | Path) -> Path:
    """Lit et vérifie le logement, calcule les briques, fait construire Blender."""
    logement = charger_logement(chemin_logement)
    dossier = Path(dossier_sortie)
    dossier.mkdir(parents=True, exist_ok=True)

    plan = dossier / "construction.json"
    plan.write_text(json.dumps(plan_de_construction(logement), indent=2, ensure_ascii=False),
                    encoding="utf-8")

    maquette = dossier / "maquette.blend"
    lancer_blender("--python", str(DOSSIER_SCRIPTS / "poser_briques.py"),
                   "--", str(plan), str(maquette))
    return maquette


def mesurer(maquette: str | Path, sortie_json: str | Path) -> dict:
    """Fait mesurer par Blender chaque objet de la maquette (utilisé par les tests)."""
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "mesurer.py"),
                   "--", str(sortie_json))
    return json.loads(Path(sortie_json).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit la maquette Blender d'un logement.")
    parser.add_argument("logement", help="chemin du fichier logement.json")
    parser.add_argument("sortie", help="dossier où écrire construction.json et maquette.blend")
    args = parser.parse_args()
    try:
        maquette = construire(args.logement, args.sortie)
    except Exception as erreur:
        sys.exit(f"Échec : {erreur}")
    print(f"Maquette prête : {maquette}")


if __name__ == "__main__":
    main()
