"""Script lu par Blender : remplace UN meuble de la maquette par un objet fabriqué (GLB) et rend la pièce depuis les appareils des
photos du client (essais « meuble d'après photo » : le juge est la photo, vue par vue).

    blender -b maquette.blend --python pc/essais-meubles-photo/meuble_dans_maquette.py -- reglages.json <dossier des images>

reglages.json : {"meuble": "reperage_5", "glb": "<chemin>" ou null (null = la maquette telle quelle), "echelle": 1.478,
                 "suffixe": "trellis2", "cameras": {"photo-07": moteur.camera_photo.pour_blender(...), …}, "echantillons": 64}
L'objet fabriqué est posé au sol, au centre et dans le sens du meuble remplacé (avant = -Y, comme les modèles du catalogue).
Rien n'est enregistré dans la maquette.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def descendants(objet):
    for enfant in objet.children:
        yield enfant
        yield from descendants(enfant)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    r = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    dossier = Path(args[1]).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    racine = bpy.data.objects.get("Meuble_" + r["meuble"])
    if racine is None:
        sys.exit("PLANTÉ : meuble introuvable dans la maquette : " + r["meuble"])
    if r.get("glb"):
        for o in descendants(racine):
            o.hide_render = True
        avant = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(Path(r["glb"]).resolve()))
        nouveaux = [o for o in bpy.data.objects if o not in avant]
        mailles = [o for o in nouveaux if o.type == "MESH"]
        coins = [o.matrix_world @ Vector(c) for o in mailles for c in o.bound_box]
        mini = Vector([min(c[k] for c in coins) for k in range(3)])
        maxi = Vector([max(c[k] for c in coins) for k in range(3)])
        centre = Vector(((mini.x + maxi.x) / 2, (mini.y + maxi.y) / 2, mini.z))
        porte = bpy.data.objects.new("Fabrique_" + r["meuble"], None)
        racine.users_collection[0].objects.link(porte)
        porte.location, porte.rotation_euler = racine.location, racine.rotation_euler
        e = float(r.get("echelle", 1.0))
        porte.scale = (e, e, e)
        for o in nouveaux:
            if o.parent is None:
                o.parent = porte
                o.location = o.location - centre
            for c in list(o.users_collection):
                if c not in racine.users_collection:
                    racine.users_collection[0].objects.link(o)
                    c.objects.unlink(o)
            o.hide_render = False
        print("objet fabriqué :", [round(v * e, 3) for v in (maxi - mini)], "m")
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(r.get("echantillons", 64))
    scene.cycles.use_denoising = True
    scene.cycles.sample_clamp_indirect = 10.0
    reglages = bpy.context.preferences.addons["cycles"].preferences
    try:
        reglages.compute_device_type = "CUDA"
        reglages.get_devices()
        for d in reglages.devices:
            d.use = d.type == "CUDA"
        scene.cycles.device = "GPU"
    except TypeError:
        pass
    collection = bpy.data.collections.get("Lumieres et cameras") or scene.collection
    for nom, c in sorted(r["cameras"].items()):
        donnees = bpy.data.cameras.new("Essai_" + nom)
        donnees.sensor_fit = "HORIZONTAL"
        donnees.sensor_width, donnees.lens, donnees.clip_start = c["capteur_mm"], c["focale_mm"], 0.05
        donnees.shift_x, donnees.shift_y = c["decentrement"]
        objet = bpy.data.objects.new("Essai_" + nom, donnees)
        collection.objects.link(objet)
        objet.location = c["position"]
        objet.rotation_euler = [math.radians(a) for a in c["rotation_deg"]]
        largeur = int(r.get("largeur", 900))
        scene.render.resolution_x, scene.render.resolution_y = largeur, int(round(largeur * c["format"][1] / c["format"][0]))
        scene.render.resolution_percentage = 100
        scene.camera = objet
        scene.render.filepath = str(dossier / f"{nom}-{r['suffixe']}.png")
        bpy.ops.render.render(write_still=True)
    print("fini")


if __name__ == "__main__":
    main()
