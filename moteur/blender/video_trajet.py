"""Script lu par Blender : un PLAN VIDÉO, une caméra qui glisse d'un point à l'autre de la maquette (10/11/2026, premier pas
vers la cinématique : NT « avant de se projeter sur la visite, il faut d'abord penser cinématique »).

    blender -b maquette.blend --python video_trajet.py -- trajet.json dossier_images echantillons [image,image,…]

trajet.json : {"points": [[x, y, z, cap, tangage], …] (repère du logement, degrés comme les caméras des photos),
               "images": 96, "focale_mm": 18, "format": [1280, 720], "scene": "2 Jour voilé"}
Les points sont répartis régulièrement sur le plan, mouvement adouci au départ et à l'arrivée (courbes de Bézier).
Pas de scintillement d'une image à l'autre : exposition et balance des blancs réglées UNE fois (première image), bruit de
rendu figé (même graine à chaque image), débruiteur, lucioles écrêtées.
Dernier argument facultatif : les seules images à rendre (« 48 » pour chronométrer une image).
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rendre import appliquer_reglage, choisir_processeur, reglage_de_photographe  # noqa: E402


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1:]
    trajet = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
    dossier = Path(arguments[1]).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    echantillons = int(arguments[2])
    seulement = [int(v) for v in arguments[3].split(",")] if len(arguments) > 3 and arguments[3] else None
    scene = bpy.data.scenes[trajet["scene"]] if trajet.get("scene") in bpy.data.scenes else bpy.context.scene
    if bpy.context.window is not None:
        bpy.context.window.scene = scene
    n = int(trajet.get("images", 96))
    largeur, hauteur = trajet.get("format", [1280, 720])

    donnees = bpy.data.cameras.new("Trajet")
    donnees.sensor_fit = "HORIZONTAL"
    donnees.sensor_width = 36.0
    donnees.lens = float(trajet.get("focale_mm", 18))
    donnees.clip_start = 0.05
    camera = bpy.data.objects.new("Trajet", donnees)
    scene.collection.objects.link(camera)
    camera.rotation_mode = "XYZ"
    points = trajet["points"]
    for k, (x, y, z, cap, tangage) in enumerate(points):
        image = 1 + round(k * (n - 1) / max(len(points) - 1, 1))
        camera.location = (x, y, z)
        camera.rotation_euler = (math.radians(90.0 + tangage), 0.0, math.radians(cap - 90.0))
        camera.keyframe_insert("location", frame=image)
        camera.keyframe_insert("rotation_euler", frame=image)
    # images clés : Bézier par défaut dans Blender (départ et arrivée adoucis)
    scene.camera = camera
    scene.frame_start, scene.frame_end = 1, n
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = largeur, hauteur
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.cycles.samples = echantillons
    scene.cycles.use_denoising = True
    scene.cycles.seed = 7
    scene.cycles.use_animated_seed = False  # même grain d'une image à l'autre : le débruiteur ne « bouillonne » pas
    scene.cycles.sample_clamp_indirect = 10.0
    print(f"Calcul sur : {choisir_processeur(scene)}")
    scene.frame_set(1)
    if scene.get("jour"):
        exposition, blanc = reglage_de_photographe(scene, dossier)
        appliquer_reglage(scene, exposition, blanc)
        print(f"Réglage du plan (une fois) : exposition {exposition:+.2f}")
    for f in (seulement or range(1, n + 1)):
        debut = time.time()
        scene.frame_set(f)
        scene.render.filepath = str(dossier / f"image-{f:04d}.png")
        bpy.ops.render.render(write_still=True, scene=scene.name)
        print(f"Image {f}/{n} en {time.time() - debut:.1f} s", flush=True)


if __name__ == "__main__":
    main()
