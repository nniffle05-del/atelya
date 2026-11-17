"""Script lu par Blender : regarder un objet 3D fabriqué (GLB) en tournant autour, sur fond neutre (essais « meuble d'après photo »).

    blender -b --factory-startup --python pc/essais-meubles-photo/voir_objet.py -- <objet.glb> <dossier des images> [vues=6] [largeur=700]

Écrit vue-0.png … vue-N.png (l'appareil tourne autour de l'objet, à hauteur d'œil un peu plongeante) et infos.json (taille, faces).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    glb, dossier = Path(args[0]).resolve(), Path(args[1]).resolve()
    n = int(args[2]) if len(args) > 2 else 6
    largeur = int(args[3]) if len(args) > 3 else 700
    dossier.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    mailles = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    coins = [o.matrix_world @ Vector(c) for o in mailles for c in o.bound_box]
    mini = Vector([min(c[k] for c in coins) for k in range(3)])
    maxi = Vector([max(c[k] for c in coins) for k in range(3)])
    centre, taille = (mini + maxi) / 2, maxi - mini
    faces = sum(len(o.data.polygons) for o in mailles)
    (dossier / "infos.json").write_text(json.dumps({"taille_xyz": [round(v, 4) for v in taille], "faces": faces,
                                                    "objets": len(mailles)}), encoding="utf-8")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    try:
        reglages = bpy.context.preferences.addons["cycles"].preferences
        reglages.compute_device_type = "CUDA"
        reglages.get_devices()
        for d in reglages.devices:
            d.use = d.type == "CUDA"
        scene.cycles.device = "GPU"
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = largeur, int(largeur * 0.75), 100
    monde = bpy.data.worlds.new("Monde")
    monde.use_nodes = True
    fond = next(x for x in monde.node_tree.nodes if x.type == "BACKGROUND")
    fond.inputs[0].default_value = (0.92, 0.92, 0.92, 1.0)
    fond.inputs[1].default_value = 1.0
    scene.world = monde
    soleil = bpy.data.objects.new("Soleil", bpy.data.lights.new("Soleil", "SUN"))
    soleil.data.energy, soleil.data.angle = 2.0, math.radians(20)
    soleil.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(soleil)
    sol = bpy.data.meshes.new("Sol")
    r = 6 * max(taille)
    sol.from_pydata([(-r, -r, mini.z), (r, -r, mini.z), (r, r, mini.z), (-r, r, mini.z)], [], [(0, 1, 2, 3)])
    scene.collection.objects.link(bpy.data.objects.new("Sol", sol))
    cam = bpy.data.objects.new("Appareil", bpy.data.cameras.new("Appareil"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    rayon = 2.6 * max(taille.x, taille.y, taille.z)
    for k in range(n):
        a = 2 * math.pi * k / n
        cam.location = centre + Vector((rayon * math.cos(a), rayon * math.sin(a), 0.45 * rayon))
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(dossier / f"vue-{k}.png")
        bpy.ops.render.render(write_still=True)
    print("fini", faces, "faces, taille", [round(v, 3) for v in taille])


if __name__ == "__main__":
    main()
