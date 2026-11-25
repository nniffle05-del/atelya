"""Script lu par Blender (importé par poser_briques.py) : les FERRONNERIES des garde-corps (20/11/2026).

Le motif d'un garde-corps en fonte est recopié des photos du client (moteur/ferronnerie.py) ; moteur.habillage
.ferronneries_du_plan le répète sur la largeur de la baie et donne ses morceaux en polygones (contour et trous, en mètres,
dans le plan du garde-corps). Ici chaque garde-corps devient UN objet de vrai métal : les polygones remplis de triangles sur
ses deux faces, et le chant tout autour (l'épaisseur de la fonte). Il tient quand la caméra bouge, il fait de l'ombre.
"""
import math

import bmesh
import bpy
from mathutils.geometry import tessellate_polygon


def _maillage(nom: str, f: dict):
    ox, oy = f["origine"]
    ux, uy = f["direction"]
    gx, gy = -uy, ux  # dans l'épaisseur du garde-corps
    demi = f["epaisseur"] / 2
    z_bas = f["z_bas"]
    sommets, faces = [], []
    for morceau in f["morceaux"]:
        boucles = [b for b in [morceau["contour"], *morceau.get("trous", [])] if len(b) >= 3]
        if not boucles:
            continue
        triangles = tessellate_polygon([[(t, z, 0.0) for t, z in b] for b in boucles])  # indices dans les points mis bout à bout
        points = [p for b in boucles for p in b]
        n, base = len(points), len(sommets)
        for d in (-demi, demi):
            sommets += [(ox + ux * t + gx * d, oy + uy * t + gy * d, z_bas + z) for t, z in points]
        for a, b, c in triangles:
            faces.append((base + a, base + b, base + c))
            faces.append((base + n + c, base + n + b, base + n + a))
        debut = 0
        for b in boucles:  # le chant : un rectangle par arête du contour
            k = len(b)
            for i in range(k):
                j = (i + 1) % k
                faces.append((base + debut + i, base + debut + j, base + n + debut + j, base + n + debut + i))
            debut += k
    maillage = bpy.data.meshes.new(nom)
    maillage.from_pydata(sommets, [], faces)
    maillage.validate()
    maillage.update()
    # les faces regardent dehors (le sens des contours n'est pas garanti), puis arêtes vives entre face et chant, chant lisse
    bm = bmesh.new()
    bm.from_mesh(maillage)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(maillage)
    bm.free()
    try:
        for p in maillage.polygons:
            p.use_smooth = True
        maillage.set_sharp_from_angle(angle=math.radians(50.0))
    except Exception:  # noqa: BLE001 : un Blender sans cette fonction : faces plates
        for p in maillage.polygons:
            p.use_smooth = False
    maillage.update()
    return maillage


def poser_ferronneries(scene, ferronneries: list[dict], materiaux) -> int:
    if not ferronneries:
        return 0
    collection = bpy.data.collections.new("Ferronneries")
    scene.collection.children.link(collection)
    for f in ferronneries:
        maillage = _maillage(f["id"], f)
        maillage.materials.append(materiaux[f.get("materiau") or "fer_forge"])
        objet = bpy.data.objects.new(f["id"], maillage)
        objet["element"] = f["element"]
        collection.objects.link(objet)
    return len(ferronneries)
