"""Script lu par Blender (importé par poser_meubles.py) : les meubles SUR MESURE dessinés en détail (B4, 09/11/2026).

Pourquoi : un bloc uni « fait maquette » ; ce qui rend une cuisine ou un placard crédible, ce sont les portes (découpées en
modules de ~60 cm avec un joint de 4 mm), le plan de travail qui dépasse, le socle en retrait, la porte du four, les poignées,
les miroirs. Tout est fait de boîtes : simple, rapide à rendre, sans texture.

Repère local d'un meuble (le même que poser_meubles.bloc) : largeur le long de x (centrée), profondeur le long de y (avant du
meuble vers -y), hauteur le long de z (0 = bas). L'objet « Bloc_<id> » reste le CORPS aux dimensions exactes du meuble (les tests
et la mesure s'y fient) ; portes, plan, socle, poignées sont des objets à part, rattachés au même meuble.
"""
import bpy

JOINT = 0.004  # m entre deux portes
EPAISSEUR_PORTE = 0.018
SAILLIE = 0.001  # la porte affleure à 1 mm devant le corps
SOCLE = 0.12  # hauteur du socle d'une cuisine (en retrait)
RETRAIT_SOCLE = 0.05
MODULE = 0.6  # largeur habituelle d'une porte de cuisine


def lineaire(rgb255):
    c = [v / 255.0 for v in rgb255]
    return [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]


def materiau(nom, rgb255, rugosite=0.5, metal=0.0):
    m = bpy.data.materials.get(nom)
    if m is not None:
        return m
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lineaire(rgb255), 1.0)
    bsdf.inputs["Roughness"].default_value = rugosite
    bsdf.inputs["Metallic"].default_value = metal
    return m


def boite(nom, centre, taille, mat, racine, collection, biseau=0.002):
    """Une boîte (centre x, y ; z du bas ; taille largeur, profondeur, hauteur), rattachée au meuble."""
    (cx, cy, z0), (lx, ly, lz) = centre, taille
    x, y = lx / 2, ly / 2
    me = bpy.data.meshes.new(nom)
    me.from_pydata([(cx - x, cy - y, z0), (cx + x, cy - y, z0), (cx + x, cy + y, z0), (cx - x, cy + y, z0),
                    (cx - x, cy - y, z0 + lz), (cx + x, cy - y, z0 + lz), (cx + x, cy + y, z0 + lz), (cx - x, cy + y, z0 + lz)],
                   [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    me.update()
    me.materials.append(mat)
    o = bpy.data.objects.new(nom, me)
    o.parent = racine
    collection.objects.link(o)
    if biseau > 0 and min(taille) > 3 * biseau:
        b = o.modifiers.new("Arrondi", "BEVEL")
        b.width, b.segments = biseau, 2
    return o


def portes(m, racine, collection, mat, z0, z1, cote=-1, n=None, prefixe="Porte"):
    """Une rangée de portes sur la face avant (cote = -1) ou arrière (+1), de z0 à z1, en n modules égaux."""
    largeur, profondeur, _ = m["dimensions"]
    n = n or max(1, round(largeur / MODULE))
    pas = largeur / n
    y = cote * (profondeur / 2 + SAILLIE + EPAISSEUR_PORTE / 2)
    objets = []
    for i in range(n):
        cx = -largeur / 2 + (i + 0.5) * pas
        objets.append(boite(f"{prefixe}_{m['id']}_{'av' if cote < 0 else 'ar'}{i + 1}", (cx, y, z0 + JOINT / 2),
                            (pas - JOINT, EPAISSEUR_PORTE, z1 - z0 - JOINT), mat, racine, collection))
    return objets


def corps(m, racine, collection, mat):
    largeur, profondeur, hauteur = m["dimensions"]
    return boite("Bloc_" + m["id"], (0, 0, 0), (largeur, profondeur, hauteur), mat, racine, collection, biseau=0.0)


def couleurs(m, defaut=(200, 200, 200)):
    rgb = tuple(m.get("couleur") or defaut)
    # le corps (vu dans les joints et sur les CÔTÉS du meuble) : à peine plus sombre que les façades ; les joints sont
    # assombris par leur propre ombre (corps à 0,55 : flancs presque marron, vu sur app-001 le 09/11/2026)
    sombre = tuple(int(v * 0.9) for v in rgb)
    return rgb, sombre


def cuisine_basse(m, racine, collection):
    largeur, profondeur, hauteur = m["dimensions"]
    rgb, sombre = couleurs(m)
    corps(m, racine, collection, materiau(f"Corps_{m['id']}", sombre, 0.6))
    facade = materiau(f"Facade_{m['id']}", rgb, 0.35)
    plan = 0.04
    portes(m, racine, collection, facade, SOCLE, hauteur - plan)
    boite(f"Socle_{m['id']}", (0, -RETRAIT_SOCLE / 2 - 0.001, 0), (largeur - 0.01, profondeur - RETRAIT_SOCLE, SOCLE - 0.002),
          materiau("Socle_cuisine", (60, 60, 62), 0.6), racine, collection, biseau=0.0)
    boite(f"Plan_{m['id']}", (0, -0.01, hauteur - plan), (largeur + 0.01, profondeur + 0.02 + 2 * SAILLIE + EPAISSEUR_PORTE, plan),
          materiau("Plan_de_travail", (236, 236, 233), 0.18), racine, collection)


def cuisine_haute(m, racine, collection):
    _, _, hauteur = m["dimensions"]
    rgb, sombre = couleurs(m)
    corps(m, racine, collection, materiau(f"Corps_{m['id']}", sombre, 0.6))
    portes(m, racine, collection, materiau(f"Facade_{m['id']}", rgb, 0.35), 0.0, hauteur)


def colonnes(m, racine, collection):
    largeur, profondeur, hauteur = m["dimensions"]
    rgb, sombre = couleurs(m)
    corps(m, racine, collection, materiau(f"Corps_{m['id']}", sombre, 0.6))
    facade = materiau(f"Facade_{m['id']}", rgb, 0.35)
    n = max(1, round(largeur / MODULE))
    pas = largeur / n
    y = -(profondeur / 2 + SAILLIE + EPAISSEUR_PORTE / 2)
    four_bas, four_haut = 0.85, 1.45
    for i in range(n):
        cx = -largeur / 2 + (i + 0.5) * pas
        if i == 0 and hauteur > 1.8:  # une colonne four : porte basse, four (verre noir), porte haute
            morceaux = [(SOCLE, four_bas, facade), (four_bas, four_haut, materiau("Four", (25, 25, 27), 0.08)),
                        (four_haut, hauteur, facade)]
        else:  # une colonne réfrigérateur ou rangement : deux portes
            coupe = min(hauteur - 0.4, 1.8)
            morceaux = [(SOCLE, coupe, facade), (coupe, hauteur, facade)]
        for k, (z0, z1, mat) in enumerate(morceaux):
            boite(f"Porte_{m['id']}_c{i + 1}_{k + 1}", (cx, y, z0 + JOINT / 2), (pas - JOINT, EPAISSEUR_PORTE, z1 - z0 - JOINT),
                  mat, racine, collection)
    boite(f"Socle_{m['id']}", (0, -RETRAIT_SOCLE / 2 - 0.001, 0), (largeur - 0.01, profondeur - RETRAIT_SOCLE, SOCLE - 0.002),
          materiau("Socle_cuisine", (60, 60, 62), 0.6), racine, collection, biseau=0.0)


def ilot(m, racine, collection):
    _, _, hauteur = m["dimensions"]
    rgb, sombre = couleurs(m)
    if hauteur < 0.1:  # un plan de travail seul (posé en meuble à part, comme « plan_ilot » d'app-001)
        corps(m, racine, collection, materiau(f"Plan_{m['id']}", rgb, 0.18))
        return
    corps(m, racine, collection, materiau(f"Corps_{m['id']}", sombre, 0.6))
    facade = materiau(f"Facade_{m['id']}", rgb, 0.35)
    for cote in (-1, 1):
        portes(m, racine, collection, facade, SOCLE, hauteur, cote=cote)


def placard(m, racine, collection):
    largeur, profondeur, hauteur = m["dimensions"]
    rgb, sombre = couleurs(m, (225, 215, 195))
    corps(m, racine, collection, materiau(f"Corps_{m['id']}", sombre, 0.6))
    facade = materiau(f"Facade_{m['id']}", rgb, 0.45)
    miroir = materiau("Miroir", (235, 235, 235), 0.02, 1.0)
    n = max(2, round(largeur / 0.5))
    avec_miroirs = "miroir" in (m.get("description") or "").lower()
    pas = largeur / n
    y = -(profondeur / 2 + SAILLIE + EPAISSEUR_PORTE / 2)
    metal = materiau("Poignee", (70, 70, 72), 0.3, 1.0)
    for i in range(n):
        cx = -largeur / 2 + (i + 0.5) * pas
        mat = miroir if avec_miroirs and 0 < i < n - 1 else facade
        boite(f"Porte_{m['id']}_{i + 1}", (cx, y, 0.02), (pas - JOINT, EPAISSEUR_PORTE, hauteur - 0.04), mat, racine, collection)
        # poignée verticale du côté de la porte voisine (les portes s'ouvrent par paires)
        bord = cx + (pas / 2 - 0.05) * (1 if i % 2 == 0 else -1)
        boite(f"Poignee_{m['id']}_{i + 1}", (bord, y - EPAISSEUR_PORTE / 2 - 0.012, hauteur * 0.45), (0.012, 0.02, 0.3),
              metal, racine, collection, biseau=0.0)


def television(m, racine, collection):
    largeur, profondeur, hauteur = m["dimensions"]
    corps(m, racine, collection, materiau("Television", (18, 18, 20), 0.4))
    boite(f"Ecran_{m['id']}", (0, -profondeur / 2 - 0.001, 0.012), (largeur - 0.024, 0.002, hauteur - 0.024),
          materiau("Ecran", (6, 6, 8), 0.06), racine, collection, biseau=0.0)


DESSINS = {"meuble_cuisine_bas": cuisine_basse, "meuble_cuisine_haut": cuisine_haute, "colonne_cuisine": colonnes,
           "ilot": ilot, "placard": placard, "television": television}
