"""Script lu par Blender (importé par poser_meubles.py) : le linge d'un lit (10/11/2026).

Sur une vraie photo de chambre, un lit c'est surtout une COUETTE (souvent blanche, molle, plissée qui retombe sur les côtés),
des oreillers et parfois un plaid. Les modèles ABO sont des cadres de lit (parfois avec un matelas lisse) : sans linge, les
photos d'essai ne ressemblent pas aux vraies, et Atelya n'apprend pas à écarter les lits.

1. Hauteur du matelas : des rayons tirés verticalement sur le milieu du lit (pas sur la tête de lit) ; on garde la médiane des
   points touchés au-dessus de 12 cm (en dessous : le sol ou un tapis). Cadre seul (< 20 cm) ou rien touché : on ajoute un
   matelas jusqu'à 45-50 cm.
2. Tête de lit : un rayon horizontal tiré du milieu vers la tête, juste au-dessus du matelas, donne où s'arrêtent les oreillers.
3. Couette : boîte arrondie (biseau + subdivision) qui couvre le matelas depuis le pied et retombe sur les côtés, bosselée par
   un bruit (plis). Oreillers : coussins arrondis contre la tête de lit. Plaid : bande fine en travers du pied.
Tout est enfant de la racine du meuble : le masque des meubles compte le linge comme le lit.
"""
import random
import zlib

import bpy
from mathutils import Vector

HAUT_MIN = 0.12  # en dessous : sol, tapis
CADRE_SEUL = 0.20


def _lineaire(rgb):
    c = [v / 255.0 for v in rgb]
    return [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]


def _tissu(nom, rgb, alea):
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*_lineaire(rgb), 1.0)
    b.inputs["Roughness"].default_value = 0.85
    for nom_entree, valeur in (("Sheen Weight", 0.5), ("Sheen", 0.5)):  # le léger voile clair du tissu en lumière rasante
        if nom_entree in b.inputs:
            b.inputs[nom_entree].default_value = valeur
            break
    # trame du tissu : petite bosse de bruit
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bruit = nodes.new("ShaderNodeTexNoise")
    bruit.inputs["Scale"].default_value = alea.uniform(250, 450)
    bosse = nodes.new("ShaderNodeBump")
    bosse.inputs["Strength"].default_value = 0.08
    links.new(bruit.outputs["Fac"], bosse.inputs["Height"])
    links.new(bosse.outputs["Normal"], b.inputs["Normal"])
    return m


def _boite(nom, racine, collection, centre, taille, materiau, biseau, niveaux, plis=0.0, graine=0):
    """Boîte (centre et taille dans le repère du lit) arrondie, éventuellement bosselée (plis = amplitude en m)."""
    sx, sy, sz = (t / 2 for t in taille)
    sommets = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
               (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    o = bpy.data.objects.new(nom, me)
    collection.objects.link(o)
    o.parent = racine
    o.location = centre
    me.materials.append(materiau)
    b = o.modifiers.new("Arrondi", "BEVEL")
    b.width, b.segments, b.limit_method = biseau, 4, "NONE"
    s = o.modifiers.new("Lisse", "SUBSURF")
    s.levels = s.render_levels = niveaux
    if plis > 0:
        vide = bpy.data.objects.new(nom + "_repere", None)  # décale le bruit d'un lit à l'autre
        collection.objects.link(vide)
        vide.parent = racine
        vide.location = (graine % 7 * 0.37, graine % 5 * 0.53, 0)
        vide.hide_render = vide.hide_viewport = True
        # deux bruits : grandes ondulations (la couette posée) et petits froissements
        for k, (echelle, force) in enumerate(((0.16, plis), (0.045, plis * 0.3))):
            tex = bpy.data.textures.new(f"{nom}_plis{k}", "CLOUDS")
            tex.noise_scale, tex.noise_depth = echelle, 2
            d = o.modifiers.new(f"Plis{k}", "DISPLACE")
            d.texture, d.strength, d.mid_level = tex, force, 0.5
            d.texture_coords, d.texture_coords_object = "OBJECT", vide
    for p in me.polygons:
        p.use_smooth = True
    return o


def _rayon(scene, depsgraph, origine, direction, distance):
    ok, lieu, _, _, objet, _ = scene.ray_cast(depsgraph, origine, direction, distance=distance)
    return lieu if ok else None


def habiller(scene, m: dict, racine, collection) -> None:
    lit = m["literie"]
    alea = random.Random(zlib.crc32(m["id"].encode()))
    largeur, profondeur, hauteur = m["dimensions"]
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    monde = racine.matrix_world
    # repère du lit : x en travers, y de la tête (+) au pied (-) (le modèle regarde vers -y), z vers le haut
    hauts = []
    for fx in (-0.25, 0.0, 0.25):
        for fy in (-0.3, -0.1, 0.1):
            o = monde @ Vector((fx * largeur, fy * profondeur, hauteur + 0.05))
            p = _rayon(scene, depsgraph, o, Vector((0, 0, -1)), hauteur + 0.1)
            if p is not None and p.z >= HAUT_MIN:
                hauts.append(p.z)
    dessus = sorted(hauts)[len(hauts) // 2] if hauts else 0.0
    if dessus < CADRE_SEUL:  # cadre seul : un matelas
        haut_matelas = alea.uniform(0.45, 0.52)
        bas = max(dessus, 0.15)
        matelas = _tissu(f"Matelas_{m['id']}", (235, 235, 230), alea)
        _boite(f"Matelas_{m['id']}", racine, collection, (0, 0, (bas + haut_matelas) / 2),
               (largeur - 0.06, profondeur - 0.08, haut_matelas - bas), matelas, 0.03, 2)
        dessus = haut_matelas
    dessus = min(dessus, 0.75)
    # tête de lit : rayon horizontal du milieu vers +y, juste au-dessus du matelas
    o = monde @ Vector((0, 0, dessus + 0.12))
    vers_tete = (monde.to_3x3() @ Vector((0, 1, 0))).normalized()
    p = _rayon(scene, depsgraph, o, vers_tete, profondeur)
    tete = (p - o).length if p is not None else profondeur / 2
    tete = min(tete, profondeur / 2) - 0.02
    pied = -profondeur / 2
    # couette : du pied jusqu'aux oreillers, retombe de ~18 cm sur les côtés et au pied
    n_or = lit.get("oreillers", 2)
    zone_oreillers = 0.45 if n_or else 0.12
    long_couette = (tete - zone_oreillers + 0.05) - (pied - 0.04)
    couette = _tissu(f"Couette_{m['id']}", lit["couette"], alea)
    retombe = alea.uniform(0.14, 0.22)
    epaisseur = alea.uniform(0.05, 0.09)
    _boite(f"Couette_{m['id']}", racine, collection,
           (0, (pied - 0.04 + tete - zone_oreillers + 0.05) / 2, dessus + epaisseur - (retombe + epaisseur) / 2),
           (largeur + 0.08, long_couette, retombe + epaisseur), couette, 0.06, 3, plis=alea.uniform(0.04, 0.07), graine=alea.randrange(1000))
    # oreillers contre la tête de lit
    if n_or:
        couleur = lit.get("couleur_oreillers") or lit["couette"]
        mat_o = _tissu(f"Oreillers_{m['id']}", couleur, alea)
        par_rang = 2 if (n_or >= 2 and largeur >= 1.2) else 1
        rangs = [0] * min(n_or, par_rang) + ([1] * (n_or - par_rang) if n_or > par_rang else [])
        l_or = min(0.65, (largeur - 0.1) / par_rang - 0.04)
        for k, rang in enumerate(rangs):
            i = k if rang == 0 else k - par_rang
            x = 0.0 if par_rang == 1 else (i - 0.5) * (l_or + 0.04)
            y = tete - 0.22 - rang * 0.12
            _boite(f"Oreiller_{m['id']}_{k}", racine, collection, (x, y, dessus + 0.07 + rang * 0.05),
                   (l_or, 0.40, 0.15), mat_o, 0.065, 2, plis=0.02, graine=k)
    # plaid replié au pied
    if lit.get("plaid"):
        mat_p = _tissu(f"Plaid_{m['id']}", lit["plaid"], alea)
        _boite(f"Plaid_{m['id']}", racine, collection, (0, pied + 0.35, dessus + epaisseur + 0.012 - 0.1),
               (largeur + 0.1, alea.uniform(0.35, 0.55), 0.22), mat_p, 0.02, 3, plis=0.03, graine=7)
