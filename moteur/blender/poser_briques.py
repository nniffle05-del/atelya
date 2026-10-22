"""Script lu par Blender : pose les briques d'un plan de construction.

Il tourne à l'intérieur de Blender, qui a son propre Python. Il n'utilise
donc que Blender (bpy) et la bibliothèque standard, rien du projet.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup --python poser_briques.py -- construction.json maquette.blend
"""

import json
import sys
from pathlib import Path

import bpy

COLLECTIONS = {"mur": "Murs", "sol": "Sols", "plafond": "Plafonds"}


def main() -> None:
    plan_json, sortie_blend = sys.argv[sys.argv.index("--") + 1:][:2]
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))
    if plan.get("schema") != "construction/0.1":
        raise ValueError(f"plan de construction inattendu : {plan.get('schema')}")

    # Part d'une scène vide (sans le cube, la caméra et la lampe par défaut).
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = plan["projet_id"]
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    collections = {}
    for categorie, nom in COLLECTIONS.items():
        collections[categorie] = bpy.data.collections.new(nom)
        scene.collection.children.link(collections[categorie])

    for brique in plan["briques"]:
        objet = bpy.data.objects.new(brique["id"], creer_maillage(brique))
        objet["element"] = brique["element"]  # pour retrouver d'où vient chaque brique
        collections[brique["categorie"]].objects.link(objet)

    Path(sortie_blend).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(sortie_blend).resolve()))
    print(f"Maquette enregistrée : {sortie_blend} ({len(plan['briques'])} briques)")


def creer_maillage(brique: dict) -> bpy.types.Mesh:
    """Un maillage = les sommets (points) et les faces d'un objet 3D."""
    contour = brique["contour"]  # sens inverse des aiguilles d'une montre
    n = len(contour)
    bas, haut = brique["z_bas"], brique["z_haut"]

    if haut == bas:
        # Une simple surface. Le sol regarde vers le haut, le plafond vers le bas.
        sommets = [(x, y, bas) for x, y in contour]
        face = list(range(n))
        faces = [face[::-1] if brique["categorie"] == "plafond" else face]
    else:
        # Un volume : le contour en bas, le même en haut, et les côtés.
        sommets = [(x, y, bas) for x, y in contour] + [(x, y, haut) for x, y in contour]
        faces = [list(range(n))[::-1], list(range(n, 2 * n))]
        faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]

    maillage = bpy.data.meshes.new(brique["id"])
    maillage.from_pydata(sommets, [], faces)
    maillage.validate()
    maillage.update()
    return maillage


main()
