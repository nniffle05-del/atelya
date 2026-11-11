"""Script lu par Unreal Engine (Python intégré) : importe le paquet d'une maquette d'Atelya dans un niveau (11/11/2026).

    UnrealEditor-Cmd.exe AtelyaStudio.uproject -run=pythonscript -script="importer_maquette.py <paquet> <nom>" -nullrhi -unattended

<paquet> : dossier fait par outils/unreal/exporter_pour_unreal.py (maquette.gltf, scene-atelya.json) ; <nom> : nom court du logement
(« app002 »). Crée le niveau /Game/Logements/<nom>/Carte, y importe toute la scène glTF (formes, matières, textures) dans
/Game/Logements/<nom>/Maquette, enregistre tout, puis écrit <paquet>/import-unreal.json : nombre d'acteurs, boîte englobante, et la
position Unreal de quelques meubles (pour vérifier le passage du repère d'Atelya au repère d'Unreal).
"""
import json
import sys
import time
from pathlib import Path

import unreal


def _args():
    # -script="fichier.py arg1 arg2" : Unreal met les arguments dans sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    return Path(args[0]), args[1]


def main():
    paquet, nom = _args()
    racine = f"/Game/Logements/{nom}"
    carte = f"{racine}/Carte"
    debut = time.time()
    niveaux = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(carte):
        unreal.EditorAssetLibrary.delete_directory(racine)
    unreal.EditorAssetLibrary.make_directory(racine)
    if not niveaux.new_level(carte):
        raise RuntimeError(f"PLANTÉ : niveau {carte} non créé")

    gestionnaire = unreal.InterchangeManager.get_interchange_manager_scripted()
    source = unreal.InterchangeManager.create_source_data(str(paquet / "maquette.gltf"))
    parametres = unreal.ImportAssetParameters()
    parametres.is_automated = True
    ok = gestionnaire.import_scene(f"{racine}/Maquette", source, parametres)
    unreal.log(f"ATELYA import_scene : {ok} en {time.time() - debut:.0f} s")

    acteurs = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    formes = [a for a in acteurs if isinstance(a, unreal.StaticMeshActor)]
    mini, maxi = [1e18] * 3, [-1e18] * 3
    for a in formes:
        origine, demi = a.get_actor_bounds(False)
        for i, (o, d) in enumerate(zip((origine.x, origine.y, origine.z), (demi.x, demi.y, demi.z))):
            mini[i], maxi[i] = min(mini[i], o - d), max(maxi[i], o + d)
    reperes = {}
    for a in acteurs:
        etiquette = a.get_actor_label()
        if etiquette.startswith("Meuble_") and len(reperes) < 6:
            p = a.get_actor_location()
            reperes[etiquette] = [round(p.x, 1), round(p.y, 1), round(p.z, 1)]
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    unreal.EditorAssetLibrary.save_directory(racine, only_if_is_dirty=False, recursive=True)
    bilan = {"carte": carte, "import_ok": bool(ok), "duree_s": round(time.time() - debut, 1), "acteurs": len(acteurs),
             "formes": len(formes), "boite_cm": {"min": [round(v, 1) for v in mini], "max": [round(v, 1) for v in maxi]},
             "meubles": reperes,
             "assets": len(unreal.EditorAssetLibrary.list_assets(racine, recursive=True, include_folder=False))}
    (paquet / "import-unreal.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    unreal.log("ATELYA bilan " + json.dumps(bilan, ensure_ascii=False))


main()
