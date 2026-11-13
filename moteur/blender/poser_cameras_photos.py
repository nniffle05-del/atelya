"""Script lu par Blender : pose une caméra par photo du client dans une COPIE de la maquette (B2 temps 2, étape 4).

Les caméras d'Atelya (vue de dessus, vue de la pièce principale) sont retirées de la copie : rendre.py ne calcule alors que les
vues des photos. La maquette d'origine n'est pas touchée.

    blender -b maquette.blend --python poser_cameras_photos.py -- cameras-blender.json copie.blend

cameras-blender.json : {"<nom de la photo>": moteur.camera_photo.pour_blender(...)} (écrit par outils/habillage/caler_photos.py).
"""
import json
import math
import sys
from pathlib import Path

import bpy


def main() -> None:
    reglages_json, sortie = sys.argv[sys.argv.index("--") + 1:][:2]
    reglages = json.loads(Path(reglages_json).read_text(encoding="utf-8"))
    for objet in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(objet, do_unlink=True)
    collection = bpy.data.collections.get("Lumieres et cameras") or bpy.context.scene.collection
    for nom, r in sorted(reglages.items()):
        donnees = bpy.data.cameras.new("Vue_" + nom)
        donnees.sensor_fit = "HORIZONTAL"
        donnees.sensor_width = r["capteur_mm"]
        donnees.lens = r["focale_mm"]
        donnees.shift_x, donnees.shift_y = r["decentrement"]
        donnees.clip_start = 0.05
        donnees.clip_end = 200.0
        objet = bpy.data.objects.new("Vue_" + nom, donnees)
        objet.location = r["position"]
        objet.rotation_mode = "XYZ"
        objet.rotation_euler = [math.radians(a) for a in r["rotation_deg"]]
        objet["masquer"] = []
        objet["format"] = r["format"]
        collection.objects.link(objet)
    bpy.context.scene.camera = bpy.data.objects["Vue_" + sorted(reglages)[0]]
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(sortie).resolve()))
    print(f"Copie enregistrée : {sortie} ({len(reglages)} caméras)")


if __name__ == "__main__":  # lancé par Blender (--python) ; importé par un autre script : rien ne démarre
    main()
