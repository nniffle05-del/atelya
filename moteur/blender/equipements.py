"""Script lu par Blender (importé par sur_mesure.py) : les ÉQUIPEMENTS du logement dessinés par Atelya (16/11/2026).

Pourquoi : une cheminée, un radiateur, un évier, une baignoire, un WC ne sont ni des murs ni des meubles de catalogue ; sans
eux, la cuisine et la salle de bains de la maquette sont vides et le séjour n'a pas sa cheminée (demande de NT du 16/11/2026 :
« dessiner les équipements que la lecture a compris », sans rien télécharger). Chaque sorte a sa forme, faite de boîtes et de
cylindres aux dimensions du meuble (moteur/equipements.py décide la place et la taille ; ici on ne fait que dessiner).

Repère local, comme sur_mesure.py : largeur le long de x (centrée), profondeur le long de y (l'avant vers -y, le dos — le mur —
vers +y), hauteur le long de z (0 = bas de l'objet). Le premier morceau de chaque équipement s'appelle « Bloc_<id> ».
"""
import math

import bpy

from sur_mesure import JOINT, boite, materiau

BLANC = (238, 238, 234)
INOX = (196, 198, 201)
# Un métal « pur » (métal = 1) ne renvoie que ce qui l'entoure : dans une cuisine sans fenêtre, l'évier et le réfrigérateur
# sortaient NOIRS (vu sur app-004 le 16/11/2026). Un inox brossé garde donc une part de couleur propre (métal 0,55, peu brillant).
METAL_INOX, RUGOSITE_INOX = 0.55, 0.42
NOIR = (22, 22, 24)


def _teinte(m, defaut):
    return tuple(m.get("couleur") or defaut)


def prisme(nom, centre, rayons, z, mat, racine, collection, cotes=28, pied=1.0):
    """Un cylindre droit à base ovale (centre x, y ; rayons le long de x et de y ; z du bas et du haut) ; `pied` < 1 resserre le
    bas (une cuvette, un abat-jour)."""
    (cx, cy), (rx, ry), (z0, z1) = centre, rayons, z
    sommets = []
    for k in range(cotes):
        a = 2 * math.pi * k / cotes
        sommets.append((cx + rx * pied * math.cos(a), cy + ry * pied * math.sin(a), z0))
    for k in range(cotes):
        a = 2 * math.pi * k / cotes
        sommets.append((cx + rx * math.cos(a), cy + ry * math.sin(a), z1))
    faces = [tuple(reversed(range(cotes))), tuple(range(cotes, 2 * cotes))]
    faces += [(k, (k + 1) % cotes, cotes + (k + 1) % cotes, cotes + k) for k in range(cotes)]
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    for f in me.polygons[2:]:
        f.use_smooth = True
    me.materials.append(mat)
    o = bpy.data.objects.new(nom, me)
    o.parent = racine
    collection.objects.link(o)
    return o


def disque_de_face(nom, centre, rayon, y, mat, racine, collection, cotes=28):
    """Un disque debout, tourné vers l'avant (centre x, z ; de y[0] à y[1] dans la profondeur) : un hublot, un bouton."""
    (cx, cz), (y0, y1) = centre, y
    sommets = []
    for yy in (y0, y1):
        for k in range(cotes):
            a = 2 * math.pi * k / cotes
            sommets.append((cx + rayon * math.cos(a), yy, cz + rayon * math.sin(a)))
    faces = [tuple(range(cotes)), tuple(reversed(range(cotes, 2 * cotes)))]
    faces += [(k, cotes + k, cotes + (k + 1) % cotes, (k + 1) % cotes) for k in range(cotes)]
    me = bpy.data.meshes.new(nom)
    me.from_pydata(sommets, [], faces)
    me.update()
    me.materials.append(mat)
    o = bpy.data.objects.new(nom, me)
    o.parent = racine
    collection.objects.link(o)
    return o


def _inox():
    return materiau("Inox", INOX, RUGOSITE_INOX, METAL_INOX)


def _ceramique():
    return materiau("Ceramique", (244, 244, 241), 0.12)


def _chrome():
    return materiau("Chrome", (214, 216, 219), 0.2, 0.8)


def _robinet(ident, x, y, z, racine, collection, hauteur=0.22, portee=0.14):
    """Un mitigeur : un fût debout et un bec qui avance vers l'avant (-y)."""
    chrome = _chrome()
    prisme(f"Robinet_{ident}_fut", (x, y), (0.014, 0.014), (z, z + hauteur), chrome, racine, collection, cotes=12)
    boite(f"Robinet_{ident}_bec", (x, y - portee / 2, z + hauteur - 0.022), (0.022, portee, 0.022), chrome, racine, collection, biseau=0.004)


# ------------------------------------------------------------------ séjour, chambres
def cheminee(m, racine, collection):
    """Une cheminée à manteau : deux jambages, un linteau, une tablette qui dépasse, le foyer noir, la plaque de sol devant."""
    L, P, H = m["dimensions"]
    pierre = materiau(f"Cheminee_{m['id']}", _teinte(m, (232, 229, 222)), 0.3)
    jambage, tablette = min(0.2, L * 0.16), 0.045
    linteau = min(0.24, H * 0.2)
    boite("Bloc_" + m["id"], (0, 0, H - tablette - linteau), (L, P, linteau), pierre, racine, collection, biseau=0.004)
    for cote in (-1, 1):
        boite(f"Jambage_{m['id']}_{'g' if cote < 0 else 'd'}", (cote * (L - jambage) / 2, 0, 0), (jambage, P, H - tablette - linteau),
              pierre, racine, collection, biseau=0.004)
    boite(f"Tablette_{m['id']}", (0, -0.02, H - tablette), (L + 0.08, P + 0.04, tablette), pierre, racine, collection, biseau=0.006)
    suie = materiau("Foyer", (16, 15, 14), 0.9)
    boite(f"Foyer_{m['id']}", (0, 0.03, 0), (L - 2 * jambage, P - 0.06, H - tablette - linteau), suie, racine, collection, biseau=0.0)
    boite(f"Atre_{m['id']}", (0, -P / 2 - 0.2, 0), (L - 2 * jambage + 0.1, 0.4, 0.012), materiau("Atre", (58, 54, 50), 0.4), racine,
          collection, biseau=0.002)


def radiateur(m, racine, collection):
    """Un radiateur à eau : un corps plat et ses éléments verticaux ; haut et étroit (plus de 1 m) : un sèche-serviettes, deux
    montants et des barreaux."""
    L, P, H = m["dimensions"]
    email = materiau("Radiateur", _teinte(m, (240, 240, 237)), 0.3)
    if H > 1.0:
        boite("Bloc_" + m["id"], (-L / 2 + 0.02, 0, 0), (0.04, min(P, 0.04), H), email, racine, collection, biseau=0.006)
        boite(f"Montant_{m['id']}", (L / 2 - 0.02, 0, 0), (0.04, min(P, 0.04), H), email, racine, collection, biseau=0.006)
        n = max(4, int(H / 0.09))
        for k in range(n):
            if k % 6 == 5:
                continue  # un vide tous les cinq barreaux, où pend la serviette
            boite(f"Barreau_{m['id']}_{k + 1}", (0, -0.012, 0.05 + k * (H - 0.1) / max(n - 1, 1) - 0.011), (L - 0.06, 0.022, 0.022), email,
                  racine, collection, biseau=0.006)
        return
    boite("Bloc_" + m["id"], (0, P * 0.2, 0.02), (L, P * 0.6, H - 0.04), email, racine, collection, biseau=0.004)
    n = max(3, round(L / 0.075))
    pas = L / n
    for k in range(n):
        boite(f"Element_{m['id']}_{k + 1}", (-L / 2 + (k + 0.5) * pas, -P * 0.2, 0), (pas * 0.62, P * 0.6, H), email, racine, collection,
              biseau=0.008)


def applique(m, racine, collection):
    """Une applique murale : une platine au mur, un abat-jour clair devant."""
    L, P, H = m["dimensions"]
    boite("Bloc_" + m["id"], (0, P / 2 - 0.012, H * 0.3), (min(0.09, L * 0.6), 0.024, H * 0.4), materiau("Platine", (150, 150, 152), 0.35, 0.6),
          racine, collection, biseau=0.003)
    prisme(f"Abat_jour_{m['id']}", (0, -P * 0.1), (L / 2, P * 0.4), (H * 0.1, H * 0.9), materiau("Abat_jour", _teinte(m, (244, 238, 222)), 0.7),
           racine, collection, pied=0.8)


def plafonnier(m, racine, collection):
    """Un plafonnier collé au plafond (un disque opalin) ; très allongé : une rampe de spots."""
    L, P, H = m["dimensions"]
    if L > 2.2 * P:
        metal = materiau("Rampe", _teinte(m, (236, 236, 233)), 0.35)
        boite("Bloc_" + m["id"], (0, 0, H - 0.03), (L, min(P, 0.06), 0.03), metal, racine, collection, biseau=0.004)
        n = max(2, round(L / 0.35))
        for k in range(n):
            x = -L / 2 + (k + 0.5) * L / n
            prisme(f"Spot_{m['id']}_{k + 1}", (x, 0), (0.04, 0.04), (0.0, H - 0.03), metal, racine, collection, cotes=16, pied=1.15)
        return
    prisme("Bloc_" + m["id"], (0, 0), (L / 2, P / 2), (0.0, H), materiau("Opalin", (247, 245, 238), 0.5), racine, collection, pied=0.86)


def etagere_murale(m, racine, collection):
    """Des étagères au mur (ou une niche à étagères) : un fond, deux joues, des tablettes tous les 30-35 cm."""
    L, P, H = m["dimensions"]
    rgb = _teinte(m, (240, 239, 235))
    bois = materiau(f"Etagere_{m['id']}", rgb, 0.45)
    fond = materiau(f"Etagere_fond_{m['id']}", tuple(int(v * 0.88) for v in rgb), 0.6)
    ep = 0.022
    boite("Bloc_" + m["id"], (0, P / 2 - 0.006, 0), (L, 0.012, H), fond, racine, collection, biseau=0.0)
    for cote in (-1, 1):
        boite(f"Joue_{m['id']}_{'g' if cote < 0 else 'd'}", (cote * (L - ep) / 2, 0, 0), (ep, P, H), bois, racine, collection, biseau=0.002)
    n = max(2, round(H / 0.33) + 1)
    for k in range(n):
        boite(f"Tablette_{m['id']}_{k + 1}", (0, 0, k * (H - ep) / (n - 1)), (L - 2 * ep, P, ep), bois, racine, collection, biseau=0.002)


# ------------------------------------------------------------------ cuisine
def refrigerateur(m, racine, collection):
    """Un réfrigérateur posé : un corps, deux portes (congélateur en bas), deux poignées."""
    L, P, H = m["dimensions"]
    rgb = _teinte(m, INOX)
    metal = METAL_INOX if max(rgb) - min(rgb) < 12 and 150 < sum(rgb) / 3 < 215 else 0.0  # un gris neutre moyen : de l'inox
    boite("Bloc_" + m["id"], (0, 0.012, 0), (L, P - 0.024, H), materiau(f"Frigo_corps_{m['id']}", tuple(int(v * 0.85) for v in rgb), 0.5, metal),
          racine, collection, biseau=0.0)
    porte = materiau(f"Frigo_{m['id']}", rgb, 0.4, metal)
    coupe = H * 0.36
    y = -P / 2 + 0.012
    for k, (z0, z1) in enumerate(((0.05, coupe), (coupe, H)), start=1):
        boite(f"Porte_{m['id']}_{k}", (0, y, z0 + JOINT / 2), (L - JOINT, 0.024, z1 - z0 - JOINT), porte, racine, collection, biseau=0.006)
    poignee = materiau("Poignee_frigo", (120, 121, 124), 0.35, 0.6)
    boite(f"Poignee_{m['id']}_1", (-L / 2 + 0.05, y - 0.03, coupe - 0.32), (0.02, 0.03, 0.28), poignee, racine, collection, biseau=0.004)
    boite(f"Poignee_{m['id']}_2", (-L / 2 + 0.05, y - 0.03, coupe + 0.06), (0.02, 0.03, 0.5), poignee, racine, collection, biseau=0.004)


def four(m, racine, collection):
    """La façade d'un four (ou d'un micro-ondes) encastré : un bandeau de commande en inox, une porte en verre noir, une
    poignée. L'objet est mince (il est posé SUR la façade du meuble qui le porte)."""
    L, P, H = m["dimensions"]
    bandeau = min(0.1, H * 0.2)
    boite("Bloc_" + m["id"], (0, 0, 0), (L - 0.006, P, H - bandeau), materiau("Four", (25, 25, 27), 0.08), racine, collection, biseau=0.003)
    boite(f"Bandeau_{m['id']}", (0, 0, H - bandeau), (L - 0.006, P, bandeau - 0.003), _inox(), racine, collection,
          biseau=0.003)
    boite(f"Poignee_{m['id']}", (0, -P / 2 - 0.022, H - bandeau - 0.06), (L * 0.8, 0.018, 0.018), _inox(), racine,
          collection, biseau=0.006)
    for k in (-1, 1):
        disque_de_face(f"Bouton_{m['id']}_{'g' if k < 0 else 'd'}", (k * L * 0.32, H - bandeau / 2), min(0.018, bandeau * 0.3),
                       (-P / 2 - 0.012, -P / 2), materiau("Bouton", (60, 60, 62), 0.3, 0.8), racine, collection, cotes=16)


def plaque(m, racine, collection):
    """Une plaque de cuisson : une dalle de verre noir sur le plan de travail, quatre foyers marqués."""
    L, P, H = m["dimensions"]
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, H), materiau("Plaque", (14, 14, 16), 0.06), racine, collection, biseau=0.002)
    foyer = materiau("Foyer_plaque", (52, 52, 55), 0.25)
    for (sx, sy, r) in ((-1, 1, 0.095), (1, 1, 0.075), (-1, -1, 0.075), (1, -1, 0.095)):
        prisme(f"Foyer_{m['id']}_{'g' if sx < 0 else 'd'}{'h' if sy > 0 else 'b'}", (sx * L * 0.24, sy * P * 0.22), (min(r, L * 0.2), min(r, P * 0.2)),
               (H, H + 0.0012), foyer, racine, collection, cotes=24)


def hotte(m, racine, collection):
    """Une hotte : un caisson bas qui avance au-dessus de la plaque, et son conduit jusqu'au plafond s'il y a la hauteur."""
    L, P, H = m["dimensions"]
    rgb = _teinte(m, INOX)
    metal = METAL_INOX if max(rgb) - min(rgb) < 12 and 150 < sum(rgb) / 3 < 215 else 0.0
    mat = materiau(f"Hotte_{m['id']}", rgb, 0.3, metal)
    caisson = min(H, 0.09)
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, caisson), mat, racine, collection, biseau=0.004)
    boite(f"Filtre_{m['id']}", (0, 0, -0.004), (L - 0.08, P - 0.08, 0.004), materiau("Filtre_hotte", (120, 121, 124), 0.45, 0.5), racine,
          collection, biseau=0.0)
    if H > caisson + 0.1:
        cote = min(0.28, L * 0.5)
        boite(f"Conduit_{m['id']}", (0, P / 2 - cote / 2, caisson), (cote, cote, H - caisson), mat, racine, collection, biseau=0.004)


def evier(m, racine, collection):
    """Un évier encastré dans le plan de travail : son rebord en inox, la cuve (plus sombre, 1 mm sous le rebord), la bonde, le
    mitigeur. La cuve n'est pas creusée : à l'image, un rectangle plus sombre cerné d'inox se lit comme une cuve."""
    L, P, H = m["dimensions"]
    inox = _inox()
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, 0.006), inox, racine, collection, biseau=0.002)
    egouttoir = L > 0.75
    cuve_l = L * (0.52 if egouttoir else 0.86)
    cx = -L / 2 + 0.04 + cuve_l / 2
    boite(f"Cuve_{m['id']}", (cx, -0.015, 0.006), (cuve_l, P - 0.13, 0.0015), materiau("Cuve", (150, 152, 155), 0.35, METAL_INOX), racine, collection,
          biseau=0.0)
    prisme(f"Bonde_{m['id']}", (cx, -0.015), (0.03, 0.03), (0.0075, 0.009), materiau("Bonde", (70, 70, 72), 0.35, 0.6), racine, collection, cotes=16)
    if egouttoir:
        for k in range(5):
            boite(f"Rainure_{m['id']}_{k + 1}", (L / 2 - 0.06 - k * (L * 0.34 / 5), -0.015, 0.006), (0.008, P - 0.16, 0.0015),
                  materiau("Cuve", (150, 152, 155), 0.35, METAL_INOX), racine, collection, biseau=0.0)
    _robinet(m["id"], cx, P / 2 - 0.045, 0.006, racine, collection, hauteur=0.26, portee=0.17)


def electromenager(m, racine, collection):
    """Un lave-linge ou un lave-vaisselle posé : une caisse blanche, un bandeau de commande, un hublot."""
    L, P, H = m["dimensions"]
    email = materiau(f"Electromenager_{m['id']}", _teinte(m, BLANC), 0.3)
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, H), email, racine, collection, biseau=0.008)
    boite(f"Bandeau_{m['id']}", (0, -P / 2 - 0.002, H - 0.13), (L - 0.03, 0.004, 0.1), materiau("Bandeau", (214, 214, 212), 0.3), racine,
          collection, biseau=0.0)
    disque_de_face(f"Hublot_{m['id']}_cercle", (0, H * 0.45), min(L, H) * 0.3, (-P / 2 - 0.02, -P / 2), _inox(), racine,
                   collection)
    disque_de_face(f"Hublot_{m['id']}", (0, H * 0.45), min(L, H) * 0.23, (-P / 2 - 0.024, -P / 2 - 0.02), materiau("Four", (25, 25, 27), 0.08),
                   racine, collection)


# ------------------------------------------------------------------ salle de bains
def lavabo(m, racine, collection):
    """Un lavabo. Haut (plus de 50 cm) : un meuble vasque à deux portes, son plan et sa vasque ; bas : la vasque seule, posée
    sur le meuble qui la porte. Dans les deux cas un mitigeur derrière la vasque."""
    L, P, H = m["dimensions"]
    blanc = _ceramique()
    z = 0.0
    if H > 0.5:
        rgb = _teinte(m, (236, 235, 231))
        corps_h = H - 0.14
        boite("Bloc_" + m["id"], (0, 0.01, 0.12), (L, P - 0.02, corps_h - 0.12), materiau(f"Meuble_vasque_{m['id']}", rgb, 0.4), racine,
              collection, biseau=0.003)
        n = 1 if L < 0.55 else 2
        for k in range(n):
            boite(f"Porte_{m['id']}_{k + 1}", (-L / 2 + (k + 0.5) * L / n, -P / 2 + 0.008, 0.125), (L / n - JOINT, 0.018, corps_h - 0.13),
                  materiau(f"Meuble_vasque_{m['id']}", rgb, 0.4), racine, collection, biseau=0.003)
        boite(f"Plan_{m['id']}", (0, -0.005, corps_h), (L + 0.01, P + 0.01, 0.025), blanc, racine, collection, biseau=0.004)
        z = corps_h + 0.025
    vasque_h = 0.115 if H > 0.5 else max(min(H, 0.14), 0.06)
    rx, ry = min(L * 0.36, 0.26), min(P * 0.36, 0.19)
    nom = f"Vasque_{m['id']}" if H > 0.5 else "Bloc_" + m["id"]
    prisme(nom, (0, -0.02), (rx, ry), (z, z + vasque_h), blanc, racine, collection, pied=0.72)
    prisme(f"Creux_{m['id']}", (0, -0.02), (rx - 0.018, ry - 0.018), (z + vasque_h, z + vasque_h + 0.001), materiau("Creux_vasque", (196, 198, 200), 0.1),
           racine, collection)
    prisme(f"Bonde_{m['id']}", (0, -0.02), (0.02, 0.02), (z + vasque_h + 0.001, z + vasque_h + 0.002), _chrome(), racine, collection, cotes=14)
    _robinet(m["id"], 0, min(P / 2 - 0.04, ry + 0.03), z, racine, collection, hauteur=vasque_h + 0.12, portee=0.13)


def baignoire(m, racine, collection):
    """Une baignoire : quatre bords et un fond (on voit le creux), un mitigeur au bout."""
    L, P, H = m["dimensions"]
    blanc = _ceramique()
    bord, fond = 0.055, 0.14
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, fond), blanc, racine, collection, biseau=0.0)
    for cote in (-1, 1):
        boite(f"Bord_{m['id']}_{'av' if cote < 0 else 'ar'}", (0, cote * (P - bord) / 2, fond), (L, bord, H - fond), blanc, racine, collection,
              biseau=0.012)
        boite(f"Bout_{m['id']}_{'g' if cote < 0 else 'd'}", (cote * (L - bord * 1.6) / 2, 0, fond), (bord * 1.6, P - 2 * bord, H - fond), blanc,
              racine, collection, biseau=0.012)
    prisme(f"Bonde_{m['id']}", (L / 2 - 0.3, 0), (0.025, 0.025), (fond, fond + 0.002), _chrome(), racine, collection, cotes=14)
    _robinet(m["id"], L / 2 - 0.045, 0.0, H, racine, collection, hauteur=0.16, portee=0.12)


def douche(m, racine, collection):
    """Une douche : un receveur, une paroi de verre devant, une colonne de douche au mur."""
    L, P, H = m["dimensions"]
    boite("Bloc_" + m["id"], (0, 0, 0), (L, P, 0.05), _ceramique(), racine, collection, biseau=0.006)
    verre = bpy.data.materials.get("verre") or materiau("Verre_douche", (225, 235, 235), 0.02)
    boite(f"Paroi_{m['id']}", (0, -P / 2 + 0.01, 0.05), (L, 0.008, H - 0.05), verre, racine, collection, biseau=0.0)
    chrome = _chrome()
    prisme(f"Colonne_{m['id']}", (L * 0.25, P / 2 - 0.04), (0.012, 0.012), (0.9, H - 0.05), chrome, racine, collection, cotes=12)
    prisme(f"Pomme_{m['id']}", (L * 0.25, P / 2 - 0.2), (0.11, 0.11), (H - 0.07, H - 0.055), chrome, racine, collection, cotes=20)
    boite(f"Bras_{m['id']}", (L * 0.25, P / 2 - 0.12, H - 0.06), (0.02, 0.18, 0.02), chrome, racine, collection, biseau=0.004)


def wc(m, racine, collection):
    """Un WC : la cuvette (ovale, resserrée vers le bas), l'abattant, le réservoir adossé au mur et son bouton."""
    L, P, H = m["dimensions"]
    blanc = _ceramique()
    assise = min(0.41, H * 0.52)
    reservoir_p = min(0.19, P * 0.3)
    cy = -reservoir_p / 2
    ry = (P - reservoir_p) / 2
    prisme("Bloc_" + m["id"], (0, cy), (L / 2, ry), (0.0, assise), blanc, racine, collection, pied=0.68)
    prisme(f"Abattant_{m['id']}", (0, cy), (L / 2 + 0.008, ry + 0.008), (assise, assise + 0.024), materiau("Abattant", (248, 248, 246), 0.2), racine,
           collection)
    boite(f"Reservoir_{m['id']}", (0, P / 2 - reservoir_p / 2, assise - 0.03), (L - 0.02, reservoir_p, H - assise + 0.03), blanc, racine,
          collection, biseau=0.012)
    prisme(f"Bouton_{m['id']}", (0, P / 2 - reservoir_p / 2), (0.03, 0.03), (H, H + 0.006), _chrome(), racine, collection, cotes=16)


DESSINS = {"cheminee": cheminee, "radiateur": radiateur, "applique": applique, "plafonnier": plafonnier, "etagere_murale": etagere_murale,
           "refrigerateur": refrigerateur, "four": four, "plaque": plaque, "hotte": hotte, "evier": evier, "electromenager": electromenager,
           "lavabo": lavabo, "baignoire": baignoire, "douche": douche, "wc": wc}
