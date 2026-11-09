"""Script lu par Blender (importé par poser_briques.py) : pose les meubles du plan de construction (B4, 09/11/2026).

Meuble du commerce (« fichier » = un modèle ABO .glb) : importé, mis aux dimensions demandées, tourné, posé. Un modèle ABO
arrive avant tourné vers -y, posé au sol (bas à z = 0), centré, largeur le long de x (vérifié le 09/11/2026 sur un canapé). On
le met à l'échelle sans trop le déformer : chaque sens suit la dimension demandée, mais sans s'écarter de plus de ECART_FORME de
l'échelle médiane (un canapé un peu plus long reste un canapé, pas un banc étiré).

Meuble sur mesure (cuisine, îlot, caisson…) ou modèle introuvable : un bloc aux dimensions et à la couleur relevées.

Collection « Meubles » à la racine de la scène : les scènes d'éclairage (copies liées) la partagent.
"""
import math

import bpy
from mathutils import Vector

ECART_FORME = 0.15
TEXTURE_RENDU, TEXTURE_VUE = "2048", "1024"  # les modèles ABO ont des photos de 4096 points : trop pour 8 Go de carte graphique


_MODELES: dict[str, tuple] = {}  # fichier .glb → (collection du modèle, sa taille) : importé une seule fois


def poser_meubles(scene, meubles: list[dict]) -> int:
    if not meubles:
        return 0
    _MODELES.clear()
    collection = bpy.data.collections.new("Meubles")
    scene.collection.children.link(collection)
    for m in meubles:
        racine = bpy.data.objects.new("Meuble_" + m["id"], None)
        collection.objects.link(racine)
        racine["categorie"] = m["categorie"]
        if m.get("modele"):
            racine["modele_abo"] = m["modele"]
        if m.get("fichier") and not m.get("sur_mesure"):
            instancier(scene, m, racine, collection)
        else:
            bloc(m, racine, collection)
        racine.location = (m["position"][0], m["position"][1], m.get("altitude", 0.0))
        racine.rotation_euler = (0.0, 0.0, math.radians(m.get("face", 0.0) + 90.0))  # avant du modèle : -y → direction « face »
    limiter_textures(scene)
    return len(meubles)


def modele(scene, fichier: str):
    """Importe un modèle ABO dans sa propre collection, recentré (milieu du pied à l'origine), hors de la scène : les meubles
    en sont des « instances » (4 chaises = un seul modèle en mémoire)."""
    if fichier in _MODELES:
        return _MODELES[fichier]
    coll = bpy.data.collections.new("ABO_" + fichier.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".glb"))
    scene.collection.children.link(coll)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[coll.name]
    avant = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=fichier)
    nouveaux = [o for o in bpy.data.objects if o not in avant]
    for o in nouveaux:
        if coll not in o.users_collection:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in nouveaux if o.type == "MESH" for c in o.bound_box]
    if pts:
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        centre = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
        for o in nouveaux:
            if o.parent is None:
                o.location = o.location - centre
        taille = mx - mn
    else:
        taille = Vector((1.0, 1.0, 1.0))
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
    scene.collection.children.unlink(coll)
    coll.use_fake_user = True  # gardée dans le fichier sans être dans la scène
    _MODELES[fichier] = (coll, taille)
    return _MODELES[fichier]


def instancier(scene, m: dict, racine, collection) -> None:
    coll, taille = modele(scene, m["fichier"])
    largeur, profondeur, hauteur = m["dimensions"]
    voulu = [largeur / max(taille.x, 1e-4), profondeur / max(taille.y, 1e-4), hauteur / max(taille.z, 1e-4)]
    med = sorted(voulu)[1]
    echelle = [min(max(s, med * (1 - ECART_FORME)), med * (1 + ECART_FORME)) for s in voulu]
    inst = bpy.data.objects.new("Modele_" + m["id"], None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = coll
    collection.objects.link(inst)
    inst.parent = racine
    inst.scale = echelle


def bloc(m: dict, racine, collection) -> None:
    from sur_mesure import DESSINS  # même dossier (poser_briques.py l'ajoute au chemin de Python)
    if m["categorie"] in DESSINS:
        DESSINS[m["categorie"]](m, racine, collection)
        return
    largeur, profondeur, hauteur = m["dimensions"]
    maillage = bpy.data.meshes.new("Bloc_" + m["id"])
    x, y = largeur / 2, profondeur / 2
    sommets = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, hauteur), (x, -y, hauteur), (x, y, hauteur), (-x, y, hauteur)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    maillage.from_pydata(sommets, [], faces)
    maillage.update()
    objet = bpy.data.objects.new("Bloc_" + m["id"], maillage)
    objet.parent = racine
    collection.objects.link(objet)
    biseau = objet.modifiers.new("Arrondi", "BEVEL")  # arêtes à peine adoucies : un meuble n'a pas d'arête au rasoir
    biseau.width, biseau.segments = 0.004, 2
    couleur = [c / 255.0 for c in (m.get("couleur") or (200, 200, 200))]
    lineaire = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in couleur]
    materiau = bpy.data.materials.new("Meuble_" + m["id"])
    materiau.use_nodes = True
    bsdf = next(n for n in materiau.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lineaire, 1.0)
    brillant = m["categorie"] in ("television", "ilot", "meuble_cuisine_bas", "meuble_cuisine_haut", "colonne_cuisine")
    bsdf.inputs["Roughness"].default_value = 0.25 if m["categorie"] == "television" else (0.35 if brillant else 0.6)
    maillage.materials.append(materiau)


def limiter_textures(scene) -> None:
    scene.render.use_simplify = True
    for nom, valeur in (("texture_limit_render", TEXTURE_RENDU), ("texture_limit", TEXTURE_VUE)):
        try:
            setattr(scene.cycles, nom, valeur)
        except (AttributeError, TypeError):
            pass
