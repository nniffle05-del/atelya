"""Prépare le paquet Unreal d'une maquette d'Atelya, en une commande (11/11/2026).

    python outils/unreal/exporter_pour_unreal.py <dossier_3d> <sortie> [--verifier]

<dossier_3d> : le dossier de la maquette faite par Atelya (maquette.blend, construction.json, eclairages.json…).
1. Blender exporte la forme en glTF (moteur/blender/exporter_gltf.py : placages calculés, brillances cuites, verre lisible) ;
2. Atelya écrit la fiche de scène et copie les photos des matières (moteur/export_unreal.py) ;
3. avec --verifier : la maquette est refaite depuis le glTF relu, sous la même lumière et avec les mêmes caméras, et comparée
   image par image à l'originale (moteur/blender/verifier_gltf.py, outils/unreal/comparer_export.py) ; dossier
   <sortie>/../verification.
"""
import argparse
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comparer_export import comparer  # noqa: E402
from moteur.construire import DOSSIER_SCRIPTS, lancer_blender, trouver_matieres  # noqa: E402
from moteur.export_unreal import ecrire_fiche  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier_3d")
    p.add_argument("sortie")
    p.add_argument("--verifier", action="store_true", help="comparer la maquette d'origine et celle relue depuis le glTF")
    p.add_argument("--echantillons", type=int, default=64)
    a = p.parse_args()
    dossier_3d, sortie = Path(a.dossier_3d).resolve(), Path(a.sortie).resolve()
    maquette = dossier_3d / "maquette.blend"
    if not maquette.is_file():
        sys.exit(f"PLANTÉ : maquette introuvable : {maquette}")
    debut = time.time()
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "exporter_gltf.py"), "--", str(sortie))
    print(f"1. Forme exportée en glTF ({time.time() - debut:.0f} s)")
    fiche = ecrire_fiche(dossier_3d, sortie, trouver_matieres())
    print(f"2. Fiche de scène : {fiche}")
    if a.verifier:
        verification = sortie.parent / "verification"
        lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "verifier_gltf.py"), "--",
                       str(sortie / "maquette.gltf"), str(verification), str(a.echantillons))
        for vue, e in comparer(verification).items():
            print(f"3. {vue} : écart moyen {e['ecart_moyen']} / 255, pixels nettement changés {e['pixels_changes_pct']} %")
        print(f"   Planches : {verification}")
    print(f"Paquet Unreal prêt en {time.time() - debut:.0f} s : {sortie}")


if __name__ == "__main__":
    main()
