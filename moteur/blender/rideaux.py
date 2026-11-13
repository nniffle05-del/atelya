"""Script lu par Blender (importé par poser_briques.py) : voilages et rideaux des fenêtres (B4, 09/11/2026).

Un tissu suspendu fait des plis : on le dessine comme une surface ondulée (vagues régulières), de la tringle au sol.
- Voilage : un seul pan sur toute la largeur de la fenêtre (+ 15 cm de chaque côté), tissu fin et clair qui LAISSE PASSER la
  lumière en la diffusant (mélange « translucide » + « transparent ») : c'est ce qui donne la lumière douce des photos d'annonce.
- Rideaux : deux pans épais, ouverts sur les côtés (chacun couvre 45 cm, à cheval sur le bord de la fenêtre), tissu mat.
Repère : milieu de la fenêtre sur la face intérieure du mur ; x le long du mur, y vers l'intérieur de la pièce.
"""
import math

import bpy

ECART_VOILAGE, ECART_RIDEAUX = 0.10, 0.16  # distance au mur (m)
PAS_PLIS = {"voilage": 0.10, "rideaux": 0.16}
AMPLITUDE = {"voilage": 0.022, "rideaux": 0.04}


def lineaire(rgb255):
    return [((v / 255 + 0.055) / 1.055) ** 2.4 if v / 255 > 0.04045 else v / 255 / 12.92 for v in rgb255]


def materiau_voilage(rgb):
    m = bpy.data.materials.new("Voilage")
    m.use_nodes = True
    arbre = m.node_tree
    for n in list(arbre.nodes):
        arbre.nodes.remove(n)
    sortie = arbre.nodes.new("ShaderNodeOutputMaterial")
    melange = arbre.nodes.new("ShaderNodeMixShader")
    translucide = arbre.nodes.new("ShaderNodeBsdfTranslucent")
    transparent = arbre.nodes.new("ShaderNodeBsdfTransparent")
    translucide.inputs["Color"].default_value = (*lineaire(rgb), 1.0)
    melange.inputs[0].default_value = 0.45  # part de lumière qui traverse sans être diffusée
    arbre.links.new(translucide.outputs[0], melange.inputs[1])
    arbre.links.new(transparent.outputs[0], melange.inputs[2])
    arbre.links.new(melange.outputs[0], sortie.inputs["Surface"])
    return m


def materiau_rideaux(rgb):
    m = bpy.data.materials.new("Rideaux")
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lineaire(rgb), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    for nom in ("Sheen Weight", "Sheen"):
        if nom in bsdf.inputs:
            bsdf.inputs[nom].default_value = 0.4
            break
    return m


def pan(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection):
    """Une surface plissée de x0 à x1 (le long du mur), à la distance y du mur, de z0 à z1."""
    pas, amp = PAS_PLIS[sorte], AMPLITUDE[sorte]
    n = max(2, int((x1 - x0) / 0.01))
    sommets, faces = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        dy = amp * math.sin(2 * math.pi * (x - x0) / pas)
        sommets += [(x, y + dy, z0), (x, y + dy, z1)]
        if i:
            a = 2 * (i - 1)
            faces.append((a, a + 2, a + 3, a + 1))
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(materiau)
    o = bpy.data.objects.new(nom, me)
    o.parent = parent
    collection.objects.link(o)
    return o


def poser_rideaux(scene, rideaux: list[dict]) -> int:
    if not rideaux:
        return 0
    collection = bpy.data.collections.new("Rideaux")
    scene.collection.children.link(collection)
    for r in rideaux:
        racine = bpy.data.objects.new("Fenetre_" + r["id"], None)
        collection.objects.link(racine)
        racine.location = (r["centre"][0], r["centre"][1], 0.0)
        racine.rotation_euler = (0.0, 0.0, math.radians(r["normale_deg"] - 90.0))  # y local = vers l'intérieur
        demi = r["largeur"] / 2
        haut = r["z_tringle"]
        if r.get("voilage"):
            pan(f"Voilage_{r['id']}", -demi - 0.15, demi + 0.15, ECART_VOILAGE, 0.01, haut, "voilage",
                materiau_voilage(r["voilage"]), racine, collection)
        if r.get("rideaux"):
            mat = materiau_rideaux(r["rideaux"])
            for cote in (-1, 1):
                bord = cote * (demi + 0.15)
                x0, x1 = sorted((bord, bord - cote * 0.45))
                pan(f"Rideau_{r['id']}_{'g' if cote < 0 else 'd'}", x0, x1, ECART_RIDEAUX, 0.01, haut, "rideaux", mat, racine,
                    collection)
    return len(rideaux)
