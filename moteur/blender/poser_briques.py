"""Script lu par Blender : pose les briques d'un plan de construction.

Il tourne à l'intérieur de Blender, qui a son propre Python. Il n'utilise
donc que Blender (bpy), la bibliothèque standard et son voisin materiaux.py,
rien d'autre du projet.

Avec un plan habillé (construction/0.2), il donne aussi à chaque brique son
matériau, et pose le soleil, les plafonniers et les caméras.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup --python poser_briques.py -- construction.json maquette.blend [bibliotheque_matieres]

B2-3 : avec le dossier de la bibliothèque de matières, les sols sont peints avec les photos de vraies matières.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from materiaux import creer_materiaux  # noqa: E402
from poser_meubles import poser_meubles  # noqa: E402

COLLECTIONS = {"mur": "Murs", "sol": "Sols", "plafond": "Plafonds", "menuiserie": "Menuiseries"}
SCHEMAS = ("construction/0.1", "construction/0.2")


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1:]
    plan_json, sortie_blend = arguments[:2]
    bibliotheque = arguments[2] if len(arguments) > 2 else None
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

    materiaux = creer_materiaux(bibliotheque, plan.get("orientation_sols", 0.0))
    # B1 (08/11/2026) : deux murs qui se croisent (en X, murs épais) ont leurs dessus exactement à la même hauteur ; au rendu,
    # chacun fait de l'ombre à l'autre et la croisée sort NOIRE. Chaque mur monte donc d'un dixième de millimètre de plus que
    # le précédent (cycle de 10, au plus 0,9 mm) : invisible (caché dans le plafond, ou de quelques millimètres vu de dessus).
    rang_des_murs: dict[str, int] = {}
    for brique in plan["briques"]:
        if brique["categorie"] == "mur" and brique["z_haut"] > brique["z_bas"]:
            rang = rang_des_murs.setdefault(brique["element"], len(rang_des_murs))
            brique = {**brique, "z_haut": brique["z_haut"] + 0.0001 * (rang % 10)}
        maillage = creer_maillage(brique)
        if brique.get("materiau"):
            maillage.materials.append(materiaux[brique["materiau"]])
        objet = bpy.data.objects.new(brique["id"], maillage)
        objet["element"] = brique["element"]  # pour retrouver d'où vient chaque brique
        collections[brique["categorie"]].objects.link(objet)

    if plan.get("lumieres") or plan.get("vues"):
        eclairage = bpy.data.collections.new("Lumieres et cameras")
        scene.collection.children.link(eclairage)
        soleil = next((l for l in plan.get("lumieres", []) if l["type"] == "soleil"), None)
        poser_ciel(scene, soleil)
        for lumiere in plan.get("lumieres", []):
            objet = creer_lumiere(lumiere)
            if objet is not None:
                eclairage.objects.link(objet)
        for vue in plan.get("vues", []):
            eclairage.objects.link(creer_camera(vue))
        if plan.get("vues"):
            scene.camera = bpy.data.objects["Vue_" + plan["vues"][-1]["id"]]

    nb_meubles = poser_meubles(scene, plan.get("meubles", []))
    regler_apercu(scene)
    Path(sortie_blend).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(sortie_blend).resolve()))
    print(f"Maquette enregistrée : {sortie_blend} ({len(plan['briques'])} briques, {nb_meubles} meubles)")


def regler_apercu(scene) -> None:
    """Aperçu « Rendu » de la vue 3D propre quand NT ouvre la maquette (09/11/2026, NT : « l'image est un peu pixelisée »).

    Réglages par défaut de Blender = calcul sur le PROCESSEUR, sans débruitage, arrêt dès un bruit de 10 % : l'aperçu restait
    granuleux même « terminé ». Ici : carte graphique (Blender revient seul au processeur s'il n'en trouve pas), débruitage
    OpenImageDenoise dès la 1re passe, seuil de bruit 2 %, 256 passes. Ne touche pas au rendu final (réglé par rendre.py).
    """
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "GPU"
    c.use_preview_denoising = True
    try:
        c.preview_denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass  # Blender sans ce débruiteur : il garde le sien
    c.preview_denoising_input_passes = "RGB_ALBEDO_NORMAL"
    c.preview_denoising_start_sample = 1
    c.preview_adaptive_threshold = 0.02
    c.preview_samples = 256


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


def poser_ciel(scene: bpy.types.Scene, soleil: dict | None = None) -> None:
    """Le ciel. B2-4 : le ciel physique de Blender (diffusion de la lumière dans l'atmosphère), soleil compris, placé dans
    la direction du soleil du plan. Sans soleil : l'ancien ciel bleu uni."""
    monde = bpy.data.worlds.new("Ciel")
    if monde.node_tree is None:
        monde.use_nodes = True
    fond = monde.node_tree.nodes["Background"]
    if soleil is None:
        fond.inputs["Color"].default_value = (0.45, 0.62, 0.9, 1.0)
        fond.inputs["Strength"].default_value = 0.5
        scene.world = monde
        return
    vers_le_soleil = [-c for c in soleil["direction"]]
    ciel = monde.node_tree.nodes.new("ShaderNodeTexSky")
    ciel.sky_type = "MULTIPLE_SCATTERING"
    ciel.sun_disc = True
    horizontal = math.hypot(vers_le_soleil[0], vers_le_soleil[1])
    ciel.sun_elevation = math.atan2(vers_le_soleil[2], horizontal)
    # Convention de Blender (vérifiée par l'ombre d'un poteau) : rotation 0 = soleil vers +y, 90° = vers +x.
    ciel.sun_rotation = math.atan2(vers_le_soleil[0], vers_le_soleil[1])
    n, l = monde.node_tree.nodes, monde.node_tree.links
    # Sous l'horizon, le ciel physique de Blender est noir : vu par la caméra (vue de dessus, sol vu par une fenêtre), on le
    # remplace par un sol gris éclairé par le ciel (le ciel à l'horizon, sans sa couleur, × 0,35 : la part qu'un sol renvoie).
    coord = n.new("ShaderNodeTexCoord")
    xyz = n.new("ShaderNodeSeparateXYZ")
    l.new(coord.outputs["Generated"], xyz.inputs[0])
    horizon = n.new("ShaderNodeCombineXYZ")
    l.new(xyz.outputs["X"], horizon.inputs["X"])
    l.new(xyz.outputs["Y"], horizon.inputs["Y"])
    horizon.inputs["Z"].default_value = 0.05
    ciel_horizon = n.new("ShaderNodeTexSky")
    for attribut in ("sky_type", "sun_disc", "sun_elevation", "sun_rotation"):
        setattr(ciel_horizon, attribut, getattr(ciel, attribut))
    ciel_horizon.sun_disc = False
    l.new(horizon.outputs["Vector"], ciel_horizon.inputs["Vector"])
    gris = n.new("ShaderNodeRGBToBW")
    l.new(ciel_horizon.outputs["Color"], gris.inputs["Color"])
    sol = n.new("ShaderNodeMath")
    sol.operation = "MULTIPLY"
    l.new(gris.outputs["Val"], sol.inputs[0])
    sol.inputs[1].default_value = 0.35
    dessous = n.new("ShaderNodeMath")
    dessous.operation = "LESS_THAN"
    l.new(xyz.outputs["Z"], dessous.inputs[0])
    dessous.inputs[1].default_value = 0.0
    camera = n.new("ShaderNodeLightPath")
    choix = n.new("ShaderNodeMath")
    choix.operation = "MULTIPLY"
    l.new(dessous.outputs[0], choix.inputs[0])
    l.new(camera.outputs["Is Camera Ray"], choix.inputs[1])
    melange = n.new("ShaderNodeMix")
    melange.data_type = "RGBA"
    l.new(choix.outputs[0], melange.inputs["Factor"])
    l.new(ciel.outputs["Color"], next(e for e in melange.inputs if e.name == "A" and e.type == "RGBA"))
    l.new(sol.outputs[0], next(e for e in melange.inputs if e.name == "B" and e.type == "RGBA"))
    l.new(next(e for e in melange.outputs if e.name == "Result" and e.type == "RGBA"), fond.inputs["Color"])
    fond.inputs["Strength"].default_value = 1.0
    scene.world = monde
    scene["jour"] = True


def creer_lumiere(lumiere: dict) -> bpy.types.Object | None:
    if lumiere["type"] == "soleil":
        return None  # B2-4 : le soleil fait partie du ciel physique (poser_ciel)
    if lumiere["type"] == "portail":
        donnees = bpy.data.lights.new(lumiere["id"], "AREA")
        donnees.shape = "RECTANGLE"
        donnees.size, donnees.size_y = lumiere["taille"]
        donnees.cycles.is_portal = True  # n'éclaire pas : guide Blender vers la lumière du ciel qui entre par là
        objet = bpy.data.objects.new(lumiere["id"], donnees)
        objet.location = lumiere["position"]
        orienter(objet, lumiere["direction"])
        return objet
    # plafonnier : un panneau lumineux sous le plafond, qui éclaire vers le bas
    donnees = bpy.data.lights.new(lumiere["id"], "AREA")
    donnees.shape = "RECTANGLE"
    donnees.size, donnees.size_y = lumiere["taille"]
    donnees.energy = lumiere["puissance"]
    donnees.color = (1.0, 0.9, 0.78)  # blanc chaud
    objet = bpy.data.objects.new(lumiere["id"], donnees)
    objet.location = lumiere["position"]
    objet.visible_camera = False  # on voit la lumière, pas le panneau
    objet.hide_render = True  # B2-4 : de jour, les plafonniers sont éteints (rallumés pour une vue de nuit)
    objet.hide_viewport = True  # … aussi dans la vue 3D de Blender, qui ne lit pas hide_render (09/11 : vue toute blanche chez NT)
    objet["nuit"] = True
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


if __name__ == "__main__":  # lancé par Blender (--python) ; importé par un autre script : rien ne démarre
    main()
