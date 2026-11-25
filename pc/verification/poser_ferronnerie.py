"""Pose la FERRONNERIE recopiée des photos (moteur/ferronnerie.py) sur un logement DÉJÀ meublé et dessiné, sans refaire la chaîne.

    python pc/verification/poser_ferronnerie.py <logement-meuble.json> <vitrages.json> <dossier des photos> <logement de sortie>

La chaîne le fait seule à l'étape « baies » (outils/atelya/de_l_ecran_au_film.py) ; cet outil sert à refaire une maquette déjà
filmée en ne changeant QUE ses garde-corps (comparaison avant / après dans le film). Le logement de sortie est vérifié
(format du logement) ; vitrages.json est recopié à côté de lui (le décor du film le prend là).
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import ferronnerie  # noqa: E402
from moteur.logement import Logement  # noqa: E402


def main() -> None:
    depart, vitrages, photos, sortie = (Path(a) for a in sys.argv[1:5])
    logement = json.loads(depart.read_text(encoding="utf-8"))
    lecture = json.loads(vitrages.read_text(encoding="utf-8"))
    logement, poses = ferronnerie.appliquer(logement, lecture, photos, journal=print)
    Logement.model_validate(logement)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    if vitrages.resolve() != sortie.with_name("vitrages.json").resolve():
        shutil.copy2(vitrages, sortie.with_name("vitrages.json"))
    print(f"{len(poses)} garde-corps à la ferronnerie recopiée des photos → {sortie}")
    if not poses:
        print("AUCUN motif lisible : les garde-corps gardent leurs barreaux droits")


if __name__ == "__main__":
    main()
