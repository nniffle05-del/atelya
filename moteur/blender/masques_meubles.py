"""Script lu par Blender : pour chaque caméra, une image noir et blanc des MEUBLES (blanc = un meuble est vu à cet endroit).

Pourquoi (brique photos, 09/11/2026) : pour apprendre à l'œil à dire « ceci n'est pas du sol », il faut savoir, sur chaque
photo d'essai, quels pixels montrent un meuble. Le moteur Workbench (dessin à plat, sans lumière) le fait en moins d'une seconde
par image : chaque objet de la collection « Meubles » (et ses instances) en blanc, tout le reste en noir.

    blender -b maquette-photos.blend --python masques_meubles.py -- dossier_masques
"""
import sys
from pathlib import Path

import bpy


def main() -> None:
    dossier = Path(sys.argv[sys.argv.index("--") + 1:][0])
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
    meubles = bpy.data.collections.get("Meubles")
    dans_meubles = set()
    if meubles is not None:
        for o in meubles.all_objects:
            dans_meubles.add(o.name)
            if o.instance_type == "COLLECTION" and o.instance_collection is not None:
                dans_meubles.update(x.name for x in o.instance_collection.all_objects)
    for o in bpy.data.objects:
        o.color = (1, 1, 1, 1) if o.name in dans_meubles else (0, 0, 0, 1)
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
        scene.render.filepath = str((dossier / f"masque-{camera.name.removeprefix('Vue_')}.png").resolve())
        bpy.ops.render.render(write_still=True)
    print(f"Masques des meubles : {dossier}")


if __name__ == "__main__":
    main()
