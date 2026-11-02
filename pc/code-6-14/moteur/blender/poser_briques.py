"""Script lu par Blender : pose les briques d'un plan de construction.

Il tourne à l'intérieur de Blender, qui a son propre Python. Il n'utilise
donc que Blender (bpy), la bibliothèque standard et son voisin materiaux.py,
rien d'autre du projet.

Avec un plan habillé (construction/0.2), il donne aussi à chaque brique son
matériau, et pose le soleil, les plafonniers et les caméras.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup --python poser_briques.py -- construction.json maquette.blend
"""

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from materiaux import creer_materiaux  # noqa: E402

COLLECTIONS = {"mur": "Murs", "sol": "Sols", "plafond": "Plafonds", "menuiserie": "Menuiseries"}
SCHEMAS = ("construction/0.1", "construction/0.2")


def main() -> None:
    plan_json, sortie_blend = sys.argv[sys.argv.index("--") + 1:][:2]
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))
    if plan.get("schema") not in SCHEMAS:
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

    materiaux = creer_materiaux()
    for brique in plan["briques"]:
        maillage = creer_maillage(brique)
        if brique.get("materiau"):
            maillage.materials.append(materiaux[brique["materiau"]])
        objet = bpy.data.objects.new(brique["id"], maillage)
        objet["element"] = brique["element"]  # pour retrouver d'où vient chaque brique
        collections[brique["categorie"]].objects.link(objet)

    if plan.get("lumieres") or plan.get("vues"):
        eclairage = bpy.data.collections.new("Lumieres et cameras")
        scene.collection.children.link(eclairage)
        poser_ciel(scene)
        for lumiere in plan.get("lumieres", []):
            eclairage.objects.link(creer_lumiere(lumiere))
        for vue in plan.get("vues", []):
            eclairage.objects.link(creer_camera(vue))
        if plan.get("vues"):
            scene.camera = bpy.data.objects["Vue_" + plan["vues"][-1]["id"]]

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


def orienter(objet: bpy.types.Object, direction) -> None:
    """Tourne une caméra ou une lampe pour qu'elle regarde dans cette direction."""
    objet.rotation_mode = "QUATERNION"
    objet.rotation_quaternion = Vector(direction).to_track_quat("-Z", "Y")


def poser_ciel(scene: bpy.types.Scene) -> None:
    """Le fond : un ciel bleu clair uni, qui éclaire aussi un peu la scène."""
    monde = bpy.data.worlds.new("Ciel")
    if monde.node_tree is None:
        monde.use_nodes = True
    fond = monde.node_tree.nodes["Background"]
    fond.inputs["Color"].default_value = (0.45, 0.62, 0.9, 1.0)
    fond.inputs["Strength"].default_value = 0.5
    scene.world = monde


def creer_lumiere(lumiere: dict) -> bpy.types.Object:
    if lumiere["type"] == "soleil":
        donnees = bpy.data.lights.new(lumiere["id"], "SUN")
        donnees.energy = lumiere["force"]
        donnees.angle = 0.03  # taille apparente du soleil : des ombres un peu douces
        donnees.color = (1.0, 0.96, 0.9)
        objet = bpy.data.objects.new(lumiere["id"], donnees)
        objet.location = (0.0, 0.0, 10.0)
        orienter(objet, lumiere["direction"])
    else:  # plafonnier : un panneau lumineux sous le plafond, qui éclaire vers le bas
        donnees = bpy.data.lights.new(lumiere["id"], "AREA")
        donnees.shape = "RECTANGLE"
        donnees.size, donnees.size_y = lumiere["taille"]
        donnees.energy = lumiere["puissance"]
        donnees.color = (1.0, 0.9, 0.78)  # blanc chaud
        objet = bpy.data.objects.new(lumiere["id"], donnees)
        objet.location = lumiere["position"]
        objet.visible_camera = False  # on voit la lumière, pas le panneau
    objet["piece"] = lumiere.get("piece", "")
    return objet


def creer_camera(vue: dict) -> bpy.types.Object:
    donnees = bpy.data.cameras.new("Vue_" + vue["id"])
    if vue["projection"] == "orthographique":
        donnees.type = "ORTHO"
        donnees.ortho_scale = vue["echelle"]
    else:
        donnees.lens = vue["focale"]
        donnees.sensor_width = vue["capteur"]
        donnees.sensor_fit = "HORIZONTAL"
    donnees.clip_start = 0.05
    donnees.clip_end = 200.0
    objet = bpy.data.objects.new("Vue_" + vue["id"], donnees)
    objet.location = vue["position"]
    orienter(objet, [c - p for p, c in zip(vue["position"], vue["cible"])])
    # Ce que rendre.py doit savoir pour faire l'image de cette vue.
    objet["masquer"] = vue["masquer"]
    objet["format"] = vue["format"]
    return objet


main()
