"""Script lu par Blender : fait une image par caméra de la maquette.

Le « rendu », c'est le calcul de l'image : Blender suit le trajet de la
lumière (moteur Cycles), depuis le soleil et les lampes jusqu'à la caméra.
Plus on suit de rayons (les « échantillons »), plus l'image est propre ;
un « débruiteur » nettoie ensuite le grain qui reste.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup maquette.blend --python rendre.py -- dossier_images echantillons pourcentage
"""

import sys
import time
from pathlib import Path

import bpy


def main() -> None:
    dossier, echantillons, pourcentage = sys.argv[sys.argv.index("--") + 1:][:3]
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(echantillons)
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = int(pourcentage)
    scene.render.image_settings.file_format = "PNG"
    print(f"Calcul sur : {choisir_processeur(scene)}")

    cameras = sorted((o for o in scene.objects if o.type == "CAMERA"), key=lambda o: o.name)
    for camera in cameras:
        debut = time.time()
        scene.camera = camera
        masquer = set(camera.get("masquer", []))
        for collection in scene.collection.children:
            collection.hide_render = collection.name in masquer
        largeur, hauteur = camera.get("format", (1600, 1000))
        scene.render.resolution_x, scene.render.resolution_y = largeur, hauteur
        nom = camera.name.removeprefix("Vue_")
        scene.render.filepath = str(Path(dossier).resolve() / f"vue-{nom}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Image {scene.render.filepath} en {time.time() - debut:.0f} s")

    for collection in scene.collection.children:
        collection.hide_render = False


def choisir_processeur(scene) -> str:
    """Utilise la carte graphique si Blender en trouve une (Metal sur Mac), sinon le processeur."""
    reglages = bpy.context.preferences.addons["cycles"].preferences
    for type_ in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            reglages.compute_device_type = type_
        except TypeError:
            continue  # ce type n'existe pas sur cette machine
        reglages.get_devices()
        cartes = [d for d in reglages.devices if d.type == type_]
        if cartes:
            for d in reglages.devices:
                d.use = d.type == type_
            scene.cycles.device = "GPU"
            return f"carte graphique ({type_} : {', '.join(d.name for d in cartes)})"
    scene.cycles.device = "CPU"
    return "processeur"


main()
