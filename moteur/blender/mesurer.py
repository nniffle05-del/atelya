"""Script lu par Blender : mesure chaque objet d'une maquette.

Sert aux tests : on mesure ce que Blender a réellement construit, pour le
comparer au plan. Écrit, pour chaque objet, sa boîte englobante (les
coordonnées mini et maxi de ses sommets), sa collection et son nombre de faces.

Utilisation :
    blender -b --factory-startup maquette.blend --python mesurer.py -- mesures.json
"""

import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    sortie = sys.argv[sys.argv.index("--") + 1]
    mesures = {}
    for objet in bpy.data.objects:
        points = [objet.matrix_world @ v.co for v in objet.data.vertices]
        mesures[objet.name] = {
            "collection": objet.users_collection[0].name,
            "element": objet.get("element"),
            "min": [min(p[i] for p in points) for i in range(3)],
            "max": [max(p[i] for p in points) for i in range(3)],
            "faces": len(objet.data.polygons),
            "normales": [list(f.normal) for f in objet.data.polygons],
        }
    Path(sortie).write_text(json.dumps(mesures, indent=2), encoding="utf-8")


main()
