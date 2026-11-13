"""Script lu par Blender : pour chaque caméra, une image noir et blanc des MEUBLES (blanc = un meuble est vu à cet endroit).

Pourquoi (brique photos, 09/11/2026) : pour apprendre à l'œil à dire « ceci n'est pas du sol », il faut savoir, sur chaque
photo d'essai, quels pixels montrent un meuble. Le moteur Workbench (dessin à plat, sans lumière) le fait en moins d'une seconde
par image : chaque objet de la collection « Meubles » (et ses instances) en blanc, tout le reste en noir.

    blender -b maquette-photos.blend --python masques_meubles.py -- dossier_masques
"""
import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    dossier = Path(sys.argv[sys.argv.index("--") + 1:][0])
    prefixe = "categories" if len(sys.argv[sys.argv.index("--") + 1:]) > 1 else "masque"
    dossier.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e:
        raise RuntimeError(f"Workbench introuvable : {e}")
    ombrage = scene.display.shading
    ombrage.light = "FLAT"
    ombrage.color_type = "OBJECT"
    for nom in ("show_shadows", "show_cavity", "show_object_outline", "show_outline", "show_specular_highlight"):
        if hasattr(ombrage, nom):  # les noms changent selon les versions de Blender
            setattr(ombrage, nom, False)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0.0, 1.0
    scene.view_settings.use_curve_mapping = False
    scene.render.film_transparent = False
    scene.world.color = (0, 0, 0)
    scene.display.render_aa = "OFF"
    arguments = sys.argv[sys.argv.index("--") + 1:]
    # 2e argument facultatif : la liste des catégories (JSON) → chaque pixel vaut le n° de la catégorie du meuble vu (1, 2…),
    # 0 = pas de meuble (repérage des meubles, 09/11/2026) ; sinon blanc = meuble, noir = le reste
    categories = json.loads(arguments[1]) if len(arguments) > 1 else None
    meubles = bpy.data.collections.get("Meubles")
    valeur_de = {}  # nom d'objet → valeur du pixel (0..255)
    if meubles is not None:
        for racine in meubles.objects:
            if "categorie" not in racine:
                continue
            v = 255 if categories is None else (categories.index(racine["categorie"]) + 1
                                                 if racine["categorie"] in categories else 0)
            for o in [racine, *racine.children_recursive]:
                valeur_de[o.name] = v
                if o.instance_type == "COLLECTION" and o.instance_collection is not None:
                    for x in o.instance_collection.all_objects:
                        valeur_de[x.name] = v
    for o in bpy.data.objects:
        v = valeur_de.get(o.name, 0) / 255.0
        lin = v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4  # « Standard » remet en sRGB : on vise la valeur exacte
        o.color = (lin, lin, lin, 1)
        if o.type == "LIGHT":
            o.hide_render = True
    for c in scene.collection.children:
        c.hide_render = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "BW"
    scene.render.resolution_percentage = 100
    for camera in sorted((o for o in scene.objects if o.type == "CAMERA"), key=lambda o: o.name):
        scene.camera = camera
        largeur, hauteur = camera.get("format", (1600, 1000))
        scene.render.resolution_x, scene.render.resolution_y = largeur, hauteur
        scene.render.filepath = str((dossier / f"{prefixe}-{camera.name.removeprefix('Vue_')}.png").resolve())
        bpy.ops.render.render(write_still=True)
    print(f"Masques des meubles : {dossier}")


if __name__ == "__main__":
    main()
