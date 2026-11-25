"""Script lu par Blender : des vues choisies d'une maquette, pour REGARDER un dessin (équipements, 16/11/2026).

    blender -b maquette.blend --python pc/verification/vues_d_essai.py -- vues.json <dossier des images> [échantillons] [largeur]

vues.json : [{"nom": "cuisine", "position": [x, y, z], "cible": [x, y, z], "focale": 20}, …] (focale en mm, capteur de 36 mm).
Rendu Cycles, lumière de la scène active ; rien n'est enregistré dans la maquette.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    vues = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    dossier = Path(args[1])
    dossier.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(args[2]) if len(args) > 2 else 96
    scene.cycles.use_denoising = True
    scene.cycles.sample_clamp_indirect = 10.0
    largeur = int(args[3]) if len(args) > 3 else 1200
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = largeur, int(largeur * 2 / 3), 100
    reglages = bpy.context.preferences.addons["cycles"].preferences
    for type_ in ("CUDA", "OPTIX"):
        try:
            reglages.compute_device_type = type_
            reglages.get_devices()
            cartes = [d for d in reglages.devices if d.type == type_]
            if cartes:
                for d in reglages.devices:
                    d.use = d.type == type_
                scene.cycles.device = "GPU"
                break
        except TypeError:
            continue
    for collection in scene.collection.children:
        collection.hide_render = False
    for v in vues:
        donnees = bpy.data.cameras.new("Essai_" + v["nom"])
        donnees.sensor_width, donnees.lens, donnees.clip_start = 36.0, float(v.get("focale", 20)), 0.05
        cam = bpy.data.objects.new("Essai_" + v["nom"], donnees)
        scene.collection.objects.link(cam)
        cam.location = v["position"]
        cam.rotation_euler = (Vector(v["cible"]) - Vector(v["position"])).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        scene.render.filepath = str((dossier / f"{v['nom']}.png").resolve())
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
        print(f"Image {scene.render.filepath}", flush=True)


main()
