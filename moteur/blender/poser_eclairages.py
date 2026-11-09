"""Script lu par Blender : une SCÈNE par éclairage dans la maquette (B2 temps 2, demande NT du 09/11/2026).

    blender -b maquette.blend --python poser_eclairages.py -- eclairages.json sortie.blend

eclairages.json : la liste des ambiances (moteur/eclairages.py). La scène d'origine devient la première ambiance (celle où la
teinte des sols a été réglée) ; les autres en sont des « copies liées » (bpy.ops.scene.new LINK_COPY) : elles partagent les
collections (murs, sols, plafonds, menuiseries, portails, caméras), donc une matière changée l'est partout. Chaque scène a son
monde (ciel), sa collection de lampes allumées (copies des plafonniers) s'il y a lieu, et son exposition / balance des blancs
déjà réglées (comme le ferait rendre.py) : en changeant de scène dans Blender, l'image est juste tout de suite.
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
from rendre import appliquer_reglage, reglage_de_photographe  # noqa: E402


def main() -> None:
    eclairages_json, sortie = sys.argv[sys.argv.index("--") + 1:][:2]
    ambiances = json.loads(Path(eclairages_json).read_text(encoding="utf-8"))
    origine = bpy.context.scene
    if origine.get("ambiance"):
        raise RuntimeError("cette maquette a déjà ses éclairages")
    ciel_origine = origine.world
    plafonniers = [o for o in origine.objects if o.type == "LIGHT" and o.get("nuit")]
    for o in plafonniers:
        # éteints aussi dans la VUE 3D de Blender (elle ne lit pas hide_render) : sinon, de jour, chaque pièce a son
        # plafonnier allumé à l'écran et l'image est brûlée (vu par NT le 09/11 : « jour voilé c'est super blanc »)
        o.hide_viewport = True
    scenes = []
    for i, a in enumerate(ambiances):
        if i == 0:
            scene = origine
        else:
            avant = set(bpy.data.scenes)
            with bpy.context.temp_override(scene=origine):
                bpy.ops.scene.new(type="LINK_COPY")
            scene = (set(bpy.data.scenes) - avant).pop()
        scene.name = a["nom"]
        scene["ambiance"] = a["id"]
        scene["jour"] = True  # rendre.py : réglage « de photographe » (exposition, balance des blancs) à chaque image
        scene["clarte_murs"] = a["clarte_murs"]
        scene["force_balance"] = a["balance"]
        if i > 0:
            scene.world = monde(a, ciel_origine)
        if a["lampes"]:
            allumer(scene, a, plafonniers)
        scenes.append(scene)

    camera = camera_interieure(origine)
    for scene in scenes:
        if camera is not None:  # exposition enregistrée dans la scène, réglée depuis la vue de la pièce principale
            scene.camera = camera
            scene.render.resolution_x, scene.render.resolution_y = camera.get("format", (1600, 1000))
            dossier = Path(sortie).resolve().parent
            appliquer_reglage(scene, *reglage_de_photographe(scene, dossier))
            print(f"{scene.name} : exposition {scene.view_settings.exposure:+.2f}")
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(sortie).resolve()))
    print(f"Maquette avec {len(scenes)} éclairages : {sortie}")


def camera_interieure(scene):
    cameras = [o for o in scene.objects if o.type == "CAMERA" and o.data.type == "PERSP"]
    return sorted(cameras, key=lambda o: o.name)[0] if cameras else None


def monde(a: dict, ciel_origine) -> bpy.types.World:
    if a["ciel"] == "physique" and ciel_origine is not None and ciel_origine.use_nodes:
        ciel = ciel_origine.copy()
        ciel.name = "Ciel " + a["nom"]
        for noeud in ciel.node_tree.nodes:
            if noeud.type == "TEX_SKY":
                principal = noeud.sun_disc  # le ciel vu (avec son disque) ; l'autre sert au sol sous l'horizon
                noeud.sun_elevation = a["elevation_soleil"]
                noeud.sun_rotation = a["rotation_soleil"]
                if principal:
                    noeud.sun_disc = a["disque_soleil"]
        return ciel
    ciel = bpy.data.worlds.new("Ciel " + a["nom"])
    if ciel.node_tree is None:
        ciel.use_nodes = True
    n, l = ciel.node_tree.nodes, ciel.node_tree.links
    fond = n["Background"]
    if a["ciel"] == "couvert":
        # ciel couvert de la CIE : clarté (1 + 2 sin h) / 3, h = hauteur au-dessus de l'horizon (1/3 à l'horizon, 1 au zénith)
        coord = n.new("ShaderNodeTexCoord")
        # direction ramenée à une longueur 1 : la vue 3D de Blender ne le fait pas (le ciel y était ~20 fois trop fort, vu
        # par NT le 09/11 : « jour voilé c'est super blanc ») ; le calcul final, lui, la donnait déjà normée
        norme = n.new("ShaderNodeVectorMath")
        norme.operation = "NORMALIZE"
        l.new(coord.outputs["Generated"], norme.inputs[0])
        xyz = n.new("ShaderNodeSeparateXYZ")
        l.new(norme.outputs["Vector"], xyz.inputs[0])
        haut = n.new("ShaderNodeMath")
        haut.operation = "MAXIMUM"
        l.new(xyz.outputs["Z"], haut.inputs[0])
        haut.inputs[1].default_value = 0.0
        clarte = n.new("ShaderNodeMath")
        clarte.operation = "MULTIPLY_ADD"
        l.new(haut.outputs[0], clarte.inputs[0])
        clarte.inputs[1].default_value = 2.0 / 3.0
        clarte.inputs[2].default_value = 1.0 / 3.0
        teinte = n.new("ShaderNodeMix")
        teinte.data_type = "RGBA"
        teinte.blend_type = "MULTIPLY"
        next(e for e in teinte.inputs if e.name == "Factor").default_value = 1.0
        a_entree = next(e for e in teinte.inputs if e.name == "A" and e.type == "RGBA")
        b_entree = next(e for e in teinte.inputs if e.name == "B" and e.type == "RGBA")
        a_entree.default_value = (*a["couleur_couvert"], 1.0)
        l.new(clarte.outputs[0], b_entree)
        l.new(next(e for e in teinte.outputs if e.name == "Result" and e.type == "RGBA"), fond.inputs["Color"])
        fond.inputs["Strength"].default_value = a["force_couvert"]
    else:  # nuit
        fond.inputs["Color"].default_value = (*a["couleur_nuit"], 1.0)
        fond.inputs["Strength"].default_value = 1.0
    return ciel


def allumer(scene, a: dict, plafonniers: list) -> None:
    """Les plafonniers allumés, dans une collection propre à cette scène (les autres scènes ne les voient pas)."""
    lampes = bpy.data.collections.new("Lampes allumées " + a["nom"])
    scene.collection.children.link(lampes)
    for o in plafonniers:
        copie = o.copy()
        copie.data = o.data.copy()
        copie.data.color = a["couleur_lampes"]
        copie.hide_render = False
        copie.hide_viewport = False
        copie.name = o.name + " (" + a["id"] + ")"
        lampes.objects.link(copie)


if __name__ == "__main__":  # lancé par Blender (--python) ; importé par un autre script : rien ne démarre
    main()
