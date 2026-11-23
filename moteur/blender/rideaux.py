"""Script lu par Blender (importé par poser_briques.py) : voilages et rideaux des fenêtres (B4, 09/11/2026).

Un tissu suspendu fait des plis. Depuis le 19/11/2026 ils ne sont plus dessinés (vagues régulières : « une tôle », NT : « je
ne les trouve pas fous ») mais CALCULÉS : la collection moteur/modeles/rideaux/*.npz (outils/bibliotheque/fabriquer_rideaux.py :
un tissu froncé à sa tringle que Blender laisse tomber) donne une longue bande par sorte, dans laquelle chaque pan découpe sa
largeur ; le pas des plis reste le vrai. Sans la collection : l'ancienne surface ondulée. Une TRINGLE porte le tout.
- Voilage : un seul pan sur toute la largeur de la fenêtre (+ 15 cm de chaque côté), tissu fin et clair qui LAISSE PASSER la
  lumière en la diffusant (mélange « translucide » + « transparent ») : c'est ce qui donne la lumière douce des photos d'annonce.
- Rideaux : deux pans épais, ouverts sur les côtés (chacun couvre 45 cm, à cheval sur le bord de la fenêtre), tissu mat ;
  depuis le 19/11/2026, UN seul pan (et de quel côté) quand les photos n'en montrent qu'un (« pans ») ; depuis le 22/11/2026,
  chaque pan à la LARGEUR et à la PLACE vues sur les photos, ramassé sur le côté ou tiré (moteur/pans_rideaux.py).
Repère : milieu de la fenêtre sur la face intérieure du mur ; x le long du mur, y vers l'intérieur de la pièce.
"""
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).parent))
import tissus  # noqa: E402 : le calcul des nappes, sans Blender

ECART_VOILAGE, ECART_RIDEAUX = 0.10, 0.16  # distance au mur (m)
PAS_PLIS = {"voilage": 0.10, "rideaux": 0.16, "rideaux_tires": 0.16}
AMPLITUDE = {"voilage": 0.022, "rideaux": 0.04, "rideaux_tires": 0.04}


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
    # velouté LÉGER : à 0,4 il partait dans le paquet comme un reflet blanc à fond, qui délavait tout le tissu dans le film
    # (rideaux bruns affichés beige pâle, vu le 19/11/2026 ; moteur/unreal/preparer_cinematique.adoucir_le_veloute)
    for nom in ("Sheen Weight", "Sheen"):
        if nom in bsdf.inputs:
            bsdf.inputs[nom].default_value = 0.04
            break
    return m


def pan_calcule(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection, derriere=None):
    """Un pan découpé dans la bande calculée de sa sorte (tissus.nappe) : de x0 à x1 le long du mur, à la distance y du mur,
    de z0 à z1. `derriere` : la nappe du voilage de la même fenêtre : le rideau ne passe jamais derrière elle
    (tissus.passer_devant). Renvoie (objet, nappe) ; (None, None) si la collection manque."""
    n = tissus.nappe(nom, x0, x1, y, z0, z1, sorte)
    if n is None:
        return None, None
    if derriere is not None:
        tissus.passer_devant(n, derriere)
    import numpy as np
    x, yy, z = n["x"], n["y"], n["z"]
    lignes, colonnes = x.shape
    sommets = np.stack([x, yy, z], -1).reshape(-1, 3).tolist()
    faces = [(i * colonnes + j, i * colonnes + j + 1, (i + 1) * colonnes + j + 1, (i + 1) * colonnes + j)
             for i in range(lignes - 1) for j in range(colonnes - 1)]
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    # placage du tissu À PLAT, en mètres (u le long du tissu, v la hauteur) : un tissage posé dessus n'est pas étiré par les plis
    uv = me.uv_layers.new(name="tissu")
    u = n["u"]
    v = z - z0
    for boucle in me.loops:
        i, j = divmod(boucle.vertex_index, colonnes)
        uv.data[boucle.index].uv = (float(u[j]), float(v[i, j]))
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(materiau)
    o = bpy.data.objects.new(nom, me)
    o.parent = parent
    collection.objects.link(o)
    return o, n


def materiau_tringle():
    m = bpy.data.materials.get("Tringle")
    if m is None:
        m = bpy.data.materials.new("Tringle")
        m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (0.10, 0.09, 0.08, 1.0)  # métal sombre, le plus courant sur les photos
        bsdf.inputs["Metallic"].default_value = 0.8
        bsdf.inputs["Roughness"].default_value = 0.45
    return m


def tringle(nom, x0, x1, y, z, parent, collection, rayon=0.011, cotes=10):
    """La tringle : une barre ronde de x0 à x1 (le long du mur), à la distance y du mur et à la hauteur z, avec un embout à
    chaque bout."""
    sommets, faces = [], []

    def anneau(x, r):
        base = len(sommets)
        for k in range(cotes):
            a = 2 * math.pi * k / cotes
            sommets.append((x, y + r * math.cos(a), z + r * math.sin(a)))
        return base

    profil = [(x0 - 0.035, 0.0), (x0 - 0.03, 1.9 * rayon), (x0, 1.9 * rayon), (x0 + 0.005, rayon), (x1 - 0.005, rayon),
              (x1, 1.9 * rayon), (x1 + 0.03, 1.9 * rayon), (x1 + 0.035, 0.0)]
    anneaux = [anneau(x, max(r, 1e-4)) for x, r in profil]
    for a, b in zip(anneaux, anneaux[1:]):
        for k in range(cotes):
            faces.append((a + k, a + (k + 1) % cotes, b + (k + 1) % cotes, b + k))
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(materiau_tringle())
    o = bpy.data.objects.new(nom, me)
    o.parent = parent
    collection.objects.link(o)
    return o


def pan(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection, derriere=None):
    """Un pan de tissu de x0 à x1 (le long du mur), à la distance y du mur, de z0 à z1 : découpé dans la collection calculée
    (pan_calcule) ; sans elle, l'ancienne surface ondulée. `derriere` : la nappe du voilage, que le pan ne traverse pas.
    Renvoie la nappe calculée (None avec l'ancienne surface)."""
    o, nappe = pan_calcule(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection, derriere)
    if o is not None:
        return nappe
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
    return None


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
        # zéro collision (16/11/2026, moteur/collisions.py) : la nappe peut être écartée du mur pour passer devant un radiateur
        # (« ecart » : distance du voilage ; les rideaux pendent 6 cm plus loin), ou s'arrêter au-dessus d'un objet (« bas »)
        ecart_voilage = r.get("ecart") or ECART_VOILAGE
        ecart_rideaux = ecart_voilage + (ECART_RIDEAUX - ECART_VOILAGE) if r.get("ecart") else ECART_RIDEAUX
        bas = r.get("bas") or 0.01
        # les pans de rideaux épais : un de chaque côté, ou les seuls pans vus sur les photos ; depuis le 22/11/2026 chacun a
        # SA largeur, SA place et SON état (moteur.habillage.rideaux_du_plan : « cote » −1 / +1, « x0 » et « x1 » = ses bords
        # intérieur et extérieur depuis le milieu de la fenêtre, « etat »). Un simple −1 / +1 : l'ancien pan de 45 cm.
        pans = []
        if r.get("rideaux"):
            for p in r.get("pans") or (-1, 1):
                if not isinstance(p, dict):
                    p = {"cote": p, "x0": demi - 0.30, "x1": demi + 0.15, "etat": "ouvert"}
                pans.append(p)
        # la tringle : au-dessus du tissu, à la distance du pan le plus loin du mur, 8 cm plus large que lui de chaque côté
        bouts = {cote: max([demi + 0.23] + [p["x1"] + 0.08 for p in pans if p["cote"] == cote]) for cote in (-1, 1)}
        tringle(f"Tringle_{r['id']}", -bouts[-1], bouts[1], ecart_rideaux if r.get("rideaux") else ecart_voilage,
                haut + 0.012, racine, collection)
        voilage = None
        if r.get("voilage"):
            voilage = pan(f"Voilage_{r['id']}", -demi - 0.15, demi + 0.15, ecart_voilage, bas, haut, "voilage",
                          materiau_voilage(r["voilage"]), racine, collection)
        if r.get("rideaux"):
            mat = materiau_rideaux(r["rideaux"])
            for p in pans:
                x0, x1 = sorted((p["cote"] * p["x0"], p["cote"] * p["x1"]))
                # ramassé sur le côté : plis serrés ; tiré devant la fenêtre : plis larges (deux bandes de la collection)
                pan(f"Rideau_{r['id']}_{'g' if p['cote'] < 0 else 'd'}", x0, x1, ecart_rideaux, bas, haut,
                    "rideaux_tires" if p.get("etat") == "tire" else "rideaux", mat, racine, collection, derriere=voilage)
    return len(rideaux)
