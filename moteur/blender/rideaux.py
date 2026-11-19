"""Script lu par Blender (importé par poser_briques.py) : voilages et rideaux des fenêtres (B4, 09/11/2026).

Un tissu suspendu fait des plis. Depuis le 19/11/2026 ils ne sont plus dessinés (vagues régulières : « une tôle », NT : « je
ne les trouve pas fous ») mais CALCULÉS : la collection moteur/modeles/rideaux/*.npz (outils/bibliotheque/fabriquer_rideaux.py :
un tissu froncé à sa tringle que Blender laisse tomber) donne une longue bande par sorte, dans laquelle chaque pan découpe sa
largeur ; le pas des plis reste le vrai. Sans la collection : l'ancienne surface ondulée. Une TRINGLE porte le tout.
- Voilage : un seul pan sur toute la largeur de la fenêtre (+ 15 cm de chaque côté), tissu fin et clair qui LAISSE PASSER la
  lumière en la diffusant (mélange « translucide » + « transparent ») : c'est ce qui donne la lumière douce des photos d'annonce.
- Rideaux : deux pans épais, ouverts sur les côtés (chacun couvre 45 cm, à cheval sur le bord de la fenêtre), tissu mat.
Repère : milieu de la fenêtre sur la face intérieure du mur ; x le long du mur, y vers l'intérieur de la pièce.
"""
import math
import zlib
from pathlib import Path

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
    # velouté LÉGER : à 0,4 il partait dans le paquet comme un reflet blanc à fond, qui délavait tout le tissu dans le film
    # (rideaux bruns affichés beige pâle, vu le 19/11/2026 ; moteur/unreal/preparer_cinematique.adoucir_le_veloute)
    for nom in ("Sheen Weight", "Sheen"):
        if nom in bsdf.inputs:
            bsdf.inputs[nom].default_value = 0.04
            break
    return m


COLLECTION = Path(__file__).resolve().parents[1] / "modeles" / "rideaux"
# la bande de la collection pour chaque nappe, et la demi-profondeur gardée pour ses plis (les mêmes que moteur/collisions.py :
# PLIS_VOILAGE, PLIS_RIDEAUX ; la bande calculée est plus profonde, on l'aplatit pour que rien ne touche le mur ni un meuble)
BANDES = {"voilage": ("voilage", 0.03), "rideaux": ("rideau_ouvert", 0.05), "rideaux_tires": ("rideau", 0.05)}
_bandes = {}


def bande(sorte):
    """La bande calculée d'une sorte : (points lignes × colonnes × 3, abscisses sur le tissu à plat, hauteur) ; None sans collection."""
    nom = BANDES.get(sorte, (None,))[0]
    if nom not in _bandes:
        chemin = COLLECTION / f"{nom}.npz"
        try:
            import numpy as np
            d = np.load(str(chemin))
            _bandes[nom] = (d["points"].astype("float32"), d["tissu"].astype("float32"), float(d["hauteur"]))
        except Exception:  # noqa: BLE001 : collection absente ou illisible : l'ancienne surface ondulée
            _bandes[nom] = None
    return _bandes[nom]


def pan_calcule(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection):
    """Un pan découpé dans la bande calculée de sa sorte : de x0 à x1 le long du mur, à la distance y du mur, de z0 à z1.
    L'endroit de la bande dépend du nom du pan (toujours le même pour un même pan, différent d'une fenêtre à l'autre).
    Renvoie None si la collection manque."""
    b = bande(sorte)
    if b is None:
        return None
    import numpy as np
    points, tissu, hauteur = b
    tringle = points[0, :, 0]
    largeur, dispo = x1 - x0, float(tringle.max() - tringle.min())
    echelle = max(1.0, largeur / (dispo - 0.02))  # un pan plus large que la bande : étiré (jamais vu : bande de 4 m)
    besoin = largeur / echelle
    depart = float(tringle.min()) + (zlib.crc32(nom.encode("utf-8")) % 1000) / 1000.0 * max(0.0, dispo - besoin)
    cols = np.nonzero((tringle >= depart) & (tringle <= depart + besoin))[0]
    if len(cols) < 4:
        return None
    p = points[:, cols[0]:cols[-1] + 1, :]
    demi = BANDES[sorte][1]
    profondeur = max(float(np.abs(p[..., 1] - np.median(p[..., 1])).max()), 1e-6)
    x = x0 + (p[..., 0] - depart) * echelle
    yy = y + (p[..., 1] - np.median(p[..., 1])) * min(1.0, demi / profondeur)
    z = z0 + p[..., 2] * ((z1 - z0) / hauteur)
    lignes, colonnes = x.shape
    sommets = np.stack([x, yy, z], -1).reshape(-1, 3).tolist()
    faces = [(i * colonnes + j, i * colonnes + j + 1, (i + 1) * colonnes + j + 1, (i + 1) * colonnes + j)
             for i in range(lignes - 1) for j in range(colonnes - 1)]
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    # placage du tissu À PLAT, en mètres (u le long du tissu, v la hauteur) : un tissage posé dessus n'est pas étiré par les plis
    uv = me.uv_layers.new(name="tissu")
    u = (tissu[cols[0]:cols[-1] + 1] - tissu[cols[0]]) * echelle
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
    return o


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


def pan(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection):
    """Un pan de tissu de x0 à x1 (le long du mur), à la distance y du mur, de z0 à z1 : découpé dans la collection calculée
    (pan_calcule) ; sans elle, l'ancienne surface ondulée."""
    o = pan_calcule(nom, x0, x1, y, z0, z1, sorte, materiau, parent, collection)
    if o is not None:
        return o
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
        # zéro collision (16/11/2026, moteur/collisions.py) : la nappe peut être écartée du mur pour passer devant un radiateur
        # (« ecart » : distance du voilage ; les rideaux pendent 6 cm plus loin), ou s'arrêter au-dessus d'un objet (« bas »)
        ecart_voilage = r.get("ecart") or ECART_VOILAGE
        ecart_rideaux = ecart_voilage + (ECART_RIDEAUX - ECART_VOILAGE) if r.get("ecart") else ECART_RIDEAUX
        bas = r.get("bas") or 0.01
        # la tringle : au-dessus du tissu, à la distance du pan le plus loin du mur, 8 cm plus large que lui de chaque côté
        tringle(f"Tringle_{r['id']}", -demi - 0.23, demi + 0.23, ecart_rideaux if r.get("rideaux") else ecart_voilage,
                haut + 0.012, racine, collection)
        if r.get("voilage"):
            pan(f"Voilage_{r['id']}", -demi - 0.15, demi + 0.15, ecart_voilage, bas, haut, "voilage",
                materiau_voilage(r["voilage"]), racine, collection)
        if r.get("rideaux"):
            mat = materiau_rideaux(r["rideaux"])
            for cote in (-1, 1):
                bord = cote * (demi + 0.15)
                x0, x1 = sorted((bord, bord - cote * 0.45))
                pan(f"Rideau_{r['id']}_{'g' if cote < 0 else 'd'}", x0, x1, ecart_rideaux, bas, haut, "rideaux", mat, racine,
                    collection)
    return len(rideaux)
