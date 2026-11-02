"""Habille la maquette : menuiseries, matériaux, lumières et points de vue.

Comme moteur/geometrie.py, ce module ne dépend pas de Blender : il calcule
tout (où poser chaque morceau de porte ou de fenêtre, quel matériau mettre
sur chaque brique, où placer les caméras et les lampes) et écrit le
résultat dans le plan de construction. Blender n'a plus qu'à exécuter.

Ce que la version 0.2 sait faire :
- une menuiserie dans chaque ouverture : cadre (dormant) et vitre pour les
  fenêtres et portes-fenêtres, coupées en deux vantaux si elles sont larges ;
  encadrement, battant (fermé) et poignées pour les portes ;
- un matériau pour chaque brique : parquet ou carrelage selon le nom de la
  pièce, murs et plafonds blancs, menuiseries blanches, verre ;
- un soleil, un plafonnier par pièce, et deux points de vue : la maquette
  vue de dessus (sans plafonds) et l'intérieur de la pièce principale.

Tout ce qui est ajouté ici est de la décoration supposée (statut « ajouté ») :
le plan ne dit ni la couleur des murs ni le type de sol.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import asdict, replace

from moteur.geometrie import Brique, Point, _rectangle, calculer_briques
from moteur.logement import Logement, Mur, Ouverture, Piece

VERSION_PLAN = "construction/0.2"

# Menuiseries (en mètres).
PROFIL = 0.06  # largeur vue de face d'un montant de cadre
PROFONDEUR_CADRE = 0.07  # épaisseur d'un cadre de fenêtre, dans l'épaisseur du mur
EPAISSEUR_VITRE = 0.01
EPAISSEUR_PORTE = 0.04
DEBORD_CHAMBRANLE = 0.01  # l'encadrement de porte dépasse un peu du mur, de chaque côté
JEU_SOL = 0.01  # espace sous le battant de porte
LARGEUR_DEUX_VANTAUX = 1.0  # à partir de cette largeur, une fenêtre a deux vantaux
HAUTEUR_POIGNEE = 1.00

# Mots du nom d'une pièce → matériau du sol. On cherche dans l'ordre :
# « Séjour + cuisine » a du parquet, car le séjour passe avant la cuisine.
SOLS = [
    (("sejour", "salon", "chambre", "bureau", "living", "salle a manger"), "parquet"),
    (("salle d'eau", "salle de bain", "sdb", "bain", "douche", "wc", "toilette",
      "cuisine", "entree", "degagement", "couloir", "cellier", "buanderie"), "carrelage"),
]
SOL_PAR_DEFAUT = "parquet"

# Pièce filmée de l'intérieur : la première dont le nom contient un de ces
# mots, sinon la plus grande.
PIECES_PRINCIPALES = ("sejour", "salon", "living")

# Vue de dessus : on regarde depuis le sud-ouest, en plongée.
DESSUS_AZIMUT = -120.0  # degrés, depuis l'est, sens inverse des aiguilles d'une montre
DESSUS_PLONGEE = 60.0  # degrés sous l'horizontale
MARGE_CADRAGE = 1.08

# Vue intérieure : un photographe dans un coin de la pièce, à hauteur d'œil.
RETRAIT_COIN = 0.35  # distance aux murs
HAUTEUR_OEIL = 1.50
HAUTEUR_CIBLE = 1.15
FOCALE_INTERIEUR = 18.0  # mm, objectif grand angle (capteur de 36 mm : 90° de champ)
CAPTEUR = 36.0
FORMAT = (1600, 1000)  # largeur, hauteur des images en pixels

# Soleil : vient de l'ouest-sud-ouest, 50° au-dessus de l'horizon.
SOLEIL_AZIMUT = 200.0
SOLEIL_HAUTEUR = 50.0
SOLEIL_FORCE = 3.0
# Plafonnier : une lampe plate sous le plafond, puissance selon la surface.
PUISSANCE_PAR_M2 = 6.0  # watts (unité Blender)


def plan_habille(logement: Logement) -> dict:
    """Le plan de construction complet, habillé, prêt pour Blender."""
    briques = [replace(b, materiau=materiau_de(b, logement)) for b in calculer_briques(logement)]
    briques += menuiseries(logement)
    return {
        "schema": VERSION_PLAN,
        "projet_id": logement.projet_id,
        "briques": [asdict(b) for b in briques],
        "lumieres": lumieres(logement),
        "vues": vues(logement),
    }


# ---------------------------------------------------------------- matériaux


def sans_accents(texte: str) -> str:
    """« Séjour » → « sejour » : pour comparer les noms sans souci d'accents."""
    decompose = unicodedata.normalize("NFD", texte.lower().replace("’", "'"))
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def sol_de_la_piece(nom: str) -> str:
    nom = sans_accents(nom)
    for mots, materiau in SOLS:
        if any(mot in nom for mot in mots):
            return materiau
    return SOL_PAR_DEFAUT


def materiau_de(brique: Brique, logement: Logement) -> str:
    """Le matériau d'une brique des murs, sols et plafonds."""
    if brique.categorie == "mur":
        return "mur_blanc"
    if brique.categorie == "plafond":
        return "plafond_blanc"
    pieces = {p.id: p for p in logement.pieces}
    if brique.element in pieces:
        return sol_de_la_piece(pieces[brique.element].nom)
    return "seuil"  # le sol sous une porte


# ------------------------------------------------------------- menuiseries


def menuiseries(logement: Logement) -> list[Brique]:
    murs = {m.id: m for m in logement.murs}
    briques: list[Brique] = []
    for o in logement.ouvertures:
        if o.type == "porte":
            briques += _porte(o, murs[o.mur], entree=_donne_dehors(o, murs[o.mur], logement))
        else:
            briques += _fenetre(o, murs[o.mur])
    return briques


def _boite(o: Ouverture, mur: Mur, nom: str, t: tuple[float, float],
           n: tuple[float, float], z: tuple[float, float], materiau: str) -> Brique:
    """Une boîte posée dans l'ouverture : t le long du mur, n dans son épaisseur."""
    contour = _rectangle(mur, o.position + t[0], o.position + t[1], n[0], n[1])
    return Brique(f"{o.id}__{nom}", "menuiserie", o.id, contour, z[0], z[1], materiau)


def _fenetre(o: Ouverture, mur: Mur) -> list[Brique]:
    """Cadre tout autour, une ou deux vitres, un montant au milieu si elle est large."""
    l, p = o.largeur, PROFIL
    bas, haut = o.allege, o.allege + o.hauteur
    cadre = (-PROFONDEUR_CADRE / 2, PROFONDEUR_CADRE / 2)
    vitre = (-EPAISSEUR_VITRE / 2, EPAISSEUR_VITRE / 2)
    m = "menuiserie_blanche"
    briques = [
        _boite(o, mur, "montant_1", (0, p), cadre, (bas, haut), m),
        _boite(o, mur, "montant_2", (l - p, l), cadre, (bas, haut), m),
        _boite(o, mur, "traverse_haut", (p, l - p), cadre, (haut - p, haut), m),
        _boite(o, mur, "traverse_bas", (p, l - p), cadre, (bas, bas + p), m),
    ]
    if l >= LARGEUR_DEUX_VANTAUX:
        milieu = l / 2
        briques.append(_boite(o, mur, "montant_milieu", (milieu - p / 2, milieu + p / 2),
                              cadre, (bas + p, haut - p), m))
        carreaux = [(p, milieu - p / 2), (milieu + p / 2, l - p)]
    else:
        carreaux = [(p, l - p)]
    for i, t in enumerate(carreaux, start=1):
        briques.append(_boite(o, mur, f"vitre_{i}", t, vitre, (bas + p, haut - p), "verre"))
    return briques


def _porte(o: Ouverture, mur: Mur, entree: bool) -> list[Brique]:
    """Encadrement (sur toute l'épaisseur du mur), battant fermé, deux poignées."""
    l, p = o.largeur, PROFIL
    haut = o.allege + o.hauteur
    e = mur.epaisseur / 2 + DEBORD_CHAMBRANLE
    m = "menuiserie_blanche"
    battant = "porte_entree" if entree else "porte_interieure"
    demi = EPAISSEUR_PORTE / 2
    # La poignée est du côté opposé aux gonds : on la met côté fin du mur.
    poignee = (l - p - 0.13, l - p - 0.03)
    z_poignee = (HAUTEUR_POIGNEE - 0.01, HAUTEUR_POIGNEE + 0.01)
    return [
        _boite(o, mur, "montant_1", (0, p), (-e, e), (0, haut), m),
        _boite(o, mur, "montant_2", (l - p, l), (-e, e), (0, haut), m),
        _boite(o, mur, "traverse_haut", (p, l - p), (-e, e), (haut - p, haut), m),
        _boite(o, mur, "battant", (p, l - p), (-demi, demi), (JEU_SOL, haut - p), battant),
        _boite(o, mur, "poignee_1", poignee, (demi, demi + 0.05), z_poignee, "metal"),
        _boite(o, mur, "poignee_2", poignee, (-demi - 0.05, -demi), z_poignee, "metal"),
    ]


def _donne_dehors(o: Ouverture, mur: Mur, logement: Logement) -> bool:
    """Une porte donne dehors si un seul de ses deux côtés est dans une pièce."""
    (x0, y0), (x1, y1) = mur.debut, mur.fin
    ux, uy = (x1 - x0) / mur.longueur, (y1 - y0) / mur.longueur
    t = o.position + o.largeur / 2
    cx, cy = x0 + ux * t, y0 + uy * t
    d = mur.epaisseur / 2 + 0.05
    cotes = [(cx - uy * d, cy + ux * d), (cx + uy * d, cy - ux * d)]
    dedans = [any(_dans(pt, p.contour) for p in logement.pieces) for pt in cotes]
    return dedans.count(True) == 1


# ---------------------------------------------------------- lumières, vues


def lumieres(logement: Logement) -> list[dict]:
    hsp = logement.hauteur_sous_plafond
    az, h = math.radians(SOLEIL_AZIMUT), math.radians(SOLEIL_HAUTEUR)
    vers_le_soleil = (math.cos(h) * math.cos(az), math.cos(h) * math.sin(az), math.sin(h))
    liste = [{"id": "Soleil", "type": "soleil", "force": SOLEIL_FORCE,
              "direction": _arrondi3([-c for c in vers_le_soleil])}]
    for p in logement.pieces:
        (x_min, y_min), (x_max, y_max) = _boite_plan(p.contour)
        liste.append({
            "id": f"Plafonnier_{p.id}", "type": "plafonnier", "piece": p.id,
            "position": _arrondi3([(x_min + x_max) / 2, (y_min + y_max) / 2, hsp - 0.02]),
            "taille": _arrondi3([(x_max - x_min) * 0.4, (y_max - y_min) * 0.4]),
            "puissance": round(PUISSANCE_PAR_M2 * p.surface_calculee, 1),
        })
    return liste


def vues(logement: Logement) -> list[dict]:
    liste = [vue_de_dessus(logement)]
    piece = piece_principale(logement)
    if piece is not None:
        liste.append(vue_interieure(logement, piece))
    return liste


def vue_de_dessus(logement: Logement) -> dict:
    """Caméra orthographique (sans perspective) qui cadre tout le logement."""
    hsp = logement.hauteur_sous_plafond
    points = [pt for m in logement.murs for pt in (m.debut, m.fin)]
    e = max(m.epaisseur for m in logement.murs) / 2
    (x_min, y_min), (x_max, y_max) = _boite_plan(points)
    x_min, y_min, x_max, y_max = x_min - e, y_min - e, x_max + e, y_max + e
    cible = ((x_min + x_max) / 2, (y_min + y_max) / 2, hsp / 2)

    az, pl = math.radians(DESSUS_AZIMUT), math.radians(DESSUS_PLONGEE)
    recul = (math.cos(pl) * math.cos(az), math.cos(pl) * math.sin(az), math.sin(pl))
    distance = 30.0
    position = tuple(c + distance * r for c, r in zip(cible, recul))

    # Largeur et hauteur du logement, vu depuis la caméra.
    droite, haut = _axes_camera(position, cible)
    coins = [(x, y, z) for x in (x_min, x_max) for y in (y_min, y_max) for z in (0.0, hsp)]
    largeur = _etendue(coins, droite)
    hauteur = _etendue(coins, haut)
    rapport = FORMAT[0] / FORMAT[1]
    return {
        "id": "dessus", "projection": "orthographique",
        "position": _arrondi3(position), "cible": _arrondi3(cible),
        "echelle": round(max(largeur, hauteur * rapport) * MARGE_CADRAGE, 3),
        "masquer": ["Plafonds"], "format": list(FORMAT),
    }


def piece_principale(logement: Logement) -> Piece | None:
    for p in logement.pieces:
        if any(mot in sans_accents(p.nom) for mot in PIECES_PRINCIPALES):
            return p
    return max(logement.pieces, key=lambda p: p.surface_calculee, default=None)


def vue_interieure(logement: Logement, piece: Piece) -> dict:
    """Depuis le coin de la pièce qui voit le plus de fenêtres, vers le coin opposé."""
    (x_min, y_min), (x_max, y_max) = _boite_plan(piece.contour)
    r = RETRAIT_COIN
    coins = [(x_min + r, y_min + r), (x_max - r, y_min + r),
             (x_max - r, y_max - r), (x_min + r, y_max - r)]
    candidats = []
    for i, coin in enumerate(coins):
        oppose = coins[(i + 2) % 4]
        if _dans(coin, piece.contour) and _dans(oppose, piece.contour):
            candidats.append((coin, oppose))
    if not candidats:  # pièce en L ou biscornue : on se met au milieu
        centre = ((x_min + x_max) / 2, (y_min + y_max) / 2)
        candidats = [(centre, coin) for coin in coins]

    fenetres = _centres_des_vitrages(logement, piece)
    champ = 2 * math.atan(CAPTEUR / 2 / FOCALE_INTERIEUR)

    def score(candidat):
        (cx, cy), (tx, ty) = candidat
        visee = math.atan2(ty - cy, tx - cx)
        vues = [largeur for (fx, fy), largeur in fenetres
                if abs(_angle(math.atan2(fy - cy, fx - cx) - visee)) < champ / 2 * 0.9]
        return (len(vues), sum(vues))

    (cx, cy), (tx, ty) = max(candidats, key=score)
    return {
        "id": piece.id, "projection": "perspective", "piece": piece.id,
        "position": _arrondi3((cx, cy, HAUTEUR_OEIL)),
        "cible": _arrondi3((tx, ty, HAUTEUR_CIBLE)),
        "focale": FOCALE_INTERIEUR, "capteur": CAPTEUR,
        "masquer": [], "format": list(FORMAT),
    }


def _centres_des_vitrages(logement: Logement, piece: Piece) -> list[tuple[Point, float]]:
    """Le milieu de chaque fenêtre ou porte-fenêtre qui borde la pièce, et sa largeur."""
    murs = {m.id: m for m in logement.murs}
    (x_min, y_min), (x_max, y_max) = _boite_plan(piece.contour)
    resultat = []
    for o in logement.ouvertures:
        if o.type == "porte":
            continue
        mur = murs[o.mur]
        (x0, y0), (x1, y1) = mur.debut, mur.fin
        t = (o.position + o.largeur / 2) / mur.longueur
        fx, fy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        marge = mur.epaisseur
        if x_min - marge <= fx <= x_max + marge and y_min - marge <= fy <= y_max + marge:
            resultat.append(((fx, fy), o.largeur))
    return resultat


# ------------------------------------------------------------ petits outils


def _boite_plan(points: list[Point]) -> tuple[Point, Point]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys)), (max(xs), max(ys))


def _dans(point: Point, contour: list[Point]) -> bool:
    """Le point est-il à l'intérieur du contour ? (on compte les traversées)"""
    x, y = point
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def _angle(a: float) -> float:
    """Ramène un angle entre -π et π."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def _axes_camera(position, cible):
    """Les directions « droite » et « haut » de l'image, pour une caméra bien droite."""
    f = _normer([c - p for p, c in zip(position, cible)])
    droite = _normer([f[1], -f[0], 0.0])  # f × z
    haut = [droite[1] * f[2] - droite[2] * f[1],
            droite[2] * f[0] - droite[0] * f[2],
            droite[0] * f[1] - droite[1] * f[0]]
    return droite, haut


def _etendue(points, axe) -> float:
    projections = [sum(a * b for a, b in zip(p, axe)) for p in points]
    return max(projections) - min(projections)


def _normer(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v]


def _arrondi3(v) -> list[float]:
    return [round(c, 4) + 0.0 for c in v]
