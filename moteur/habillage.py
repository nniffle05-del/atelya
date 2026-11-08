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

B2-1 (08/11/2026), les finitions qu'on voit dans tout vrai logement (version 0.3) :
- des PLINTHES au pied des murs, dans chaque pièce : seulement le long d'un vrai mur au niveau du sol (rien devant une
  porte, une porte-fenêtre ou une cuisine ouverte), arrêtées contre l'encadrement des portes, coupées en biseau dans les
  angles (rentrants et sortants) ;
- un ENCADREMENT (chambranle) sur les deux faces du mur autour de chaque porte : la moulure plate qui cache le joint ;
- les fenêtres et portes-fenêtres posées près de la face intérieure du mur (comme en France : la profondeur est côté rue),
  et un APPUI (la tablette) sous chaque fenêtre, côté pièce.
Le plan ne dit rien de tout ça : règle fixe (mêmes mesures partout), statut « ajouté ». Au temps 2 de B2, les photos du
client pourront changer hauteur, couleur ou matière.

Version 0.4 (08/11/2026, demande de NT : « il doit savoir le faire en fonction du logement, s'il voit qu'il y en a ou pas ») :
les plinthes se décident PIÈCE PAR PIÈCE (champ `plinthes` de chaque pièce du logement : en bois, en carrelage comme le sol,
ou aucune). Quand rien ne l'a vu, la règle par défaut (plinthes_par_defaut) : en carrelage dans une pièce carrelée, en bois
ailleurs ; elle est écrite dans le fichier de l'écran de vérification (completer_plinthes) pour qu'une personne la voie et la
change. Au temps 2, Atelya la remplira d'après les photos du client.

Version 0.5 (08/11/2026, B2-2) : les PORTES DE PLACARD, sur le même principe (champ `placard` de la pièce : battantes,
coulissantes ou aucune). Un placard = une pièce dont le nom dit placard / rangement / dressing / penderie, de moins de
PLACARD_MAX m² (un dressing plus grand est une pièce : il garde une porte ordinaire). Deux cas :
- le placard est ouvert sur une pièce voisine, sans mur (la « façade ») : les portes ferment la façade, du sol au plafond ;
- le plan dessine sa façade comme une porte dans un mur : les portes de placard remplacent le battant de cette porte.
Règle par défaut quand rien ne l'a vu : battantes pour une façade de moins de 1 m, coulissantes au-delà.

Tout ce qui est ajouté ici est de la décoration supposée (statut « ajouté ») :
le plan ne dit ni la couleur des murs ni le type de sol.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import asdict, replace

from moteur.geometrie import Brique, Point, _arrondi, _rectangle, _sens_direct, calculer_briques
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
# B2-1 : finitions (en mètres). Règle fixe, la même partout (voir la tête du module).
HAUTEUR_PLINTHE = 0.10
EPAISSEUR_PLINTHE = 0.015
HAUTEUR_PLINTHE_CARRELAGE = 0.08  # une plinthe carrelée : un carreau coupé, plus bas et plus fin qu'une plinthe en bois
EPAISSEUR_PLINTHE_CARRELAGE = 0.01
PLINTHE_MIN = 0.03  # un morceau de plinthe plus court n'est pas posé
SONDE_MUR = 0.02  # on cherche le mur à cette distance derrière le bord de la pièce
LARGEUR_CHAMBRANLE = 0.065  # vue de face
EPAISSEUR_CHAMBRANLE = 0.02  # plus épais que la plinthe : la plinthe vient buter dessus
JEU_PLINTHE = 0.001  # la plinthe s'arrête à 1 mm de l'encadrement (deux faces collées scintillent au rendu)
RETRAIT_FENETRE = 0.05  # le cadre de fenêtre est à 5 cm derrière la face intérieure du mur
EPAISSEUR_APPUI = 0.025
DEBORD_APPUI = 0.03  # l'appui dépasse du mur côté pièce, et de chaque côté de la fenêtre
ALLEGE_MIN_APPUI = 0.30  # pas d'appui sous une ouverture plus basse (porte-fenêtre)
# B2-2 : portes de placard (en mètres).
MOTS_PLACARD = ("placard", "rangement", "dressing", "penderie")
PLACARD_MAX = 4.0  # m² : un dressing plus grand est une vraie pièce, avec une porte ordinaire
FACADE_MIN = 0.40  # une façade ouverte plus courte n'est pas fermée (bout de mur, encoche)
COULISSANTES_DES = 1.0  # par défaut : battantes en dessous de cette largeur, coulissantes au-delà
VANTAIL_MAX = 0.60  # largeur maximale d'une porte battante de placard
PANNEAU_MAX = 1.00  # largeur maximale d'un panneau coulissant
RECOUVREMENT = 0.03  # deux panneaux coulissants voisins se recouvrent un peu
EPAISSEUR_VANTAIL = 0.019
JEU_VANTAUX = 0.003  # fente entre deux portes battantes
HAUTEUR_RAIL = 0.04

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
    briques += plinthes(briques, logement)
    briques += portes_de_placard(briques, logement)
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


def plinthes_par_defaut(nom: str) -> str:
    """Les plinthes supposées quand rien ne les a vues : comme le sol dans une pièce carrelée, en bois ailleurs."""
    return "carrelage" if sol_de_la_piece(nom) == "carrelage" else "bois"


def choix_plinthes(piece: Piece) -> str:
    """« bois », « carrelage » ou « aucune » : ce que dit la pièce, sinon la règle par défaut."""
    return piece.plinthes.choix if piece.plinthes is not None else plinthes_par_defaut(piece.nom)


def completer_plinthes(logement: dict) -> dict:
    """Une copie du logement (forme JSON) où chaque pièce sans plinthes décidées reçoit la règle par défaut, marquée
    « ajoute » (supposé, personne ne l'a vu) : l'écran de vérification la montre et une personne peut la changer."""
    import copy

    sortie = copy.deepcopy(logement)
    for p in sortie.get("pieces") or []:
        if not p.get("plinthes"):
            p["plinthes"] = {"choix": plinthes_par_defaut(p.get("nom", "")), "statut": "ajoute",
                             "source": "regle_par_defaut", "confiance": 0.5}
    return sortie


def est_placard(piece: Piece) -> bool:
    """Un placard : son choix de portes est écrit, ou son nom le dit et il est petit (un grand dressing est une pièce)."""
    if piece.placard is not None:
        return True
    nom = sans_accents(piece.nom)
    return any(mot in nom for mot in MOTS_PLACARD) and piece.surface_calculee <= PLACARD_MAX


def choix_placard(piece: Piece, largeur: float) -> str:
    """« battantes », « coulissantes » ou « aucune » : ce que dit la pièce, sinon la règle par défaut selon la largeur."""
    if piece.placard is not None:
        return piece.placard.choix
    return "coulissantes" if largeur >= COULISSANTES_DES else "battantes"


def completer_finitions(logement: dict) -> dict:
    """Une copie du logement (forme JSON) où chaque finition non décidée reçoit la règle par défaut, marquée « ajoute »
    (supposé, personne ne l'a vu) : plinthes de chaque pièce, portes de chaque placard (d'après la largeur de sa façade).
    Si le logement ne se construit pas encore (à corriger à l'écran), seules les plinthes sont complétées."""
    sortie = completer_plinthes(logement)
    try:
        log = Logement.model_validate(sortie)
        largeurs = largeurs_des_facades(calculer_briques(log), log)
    except Exception:  # noqa: BLE001 — un logement impossible est signalé par ailleurs (doutes de construction)
        return sortie
    for p, piece in zip(sortie.get("pieces") or [], log.pieces):
        if not p.get("placard") and piece.id in largeurs:
            p["placard"] = {"choix": choix_placard(piece, largeurs[piece.id]), "statut": "ajoute",
                            "source": "regle_par_defaut", "confiance": 0.5}
    return sortie


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
        mur = murs[o.mur]
        if o.type == "porte":
            porte = _porte(o, mur, entree=_donne_dehors(o, mur, logement), hsp=logement.hauteur_sous_plafond,
                           libres=_place_de_chaque_cote(o, mur, logement))
            placard = _placard_derriere(o, mur, logement)
            if placard is not None:  # B2-2 : la façade du placard dessinée comme une porte
                piece, cote = placard
                porte = [b for b in porte if not b.id.endswith(("__battant", "__poignee_1", "__poignee_2"))]
                porte += _portes_de_placard_dans(o, mur, piece, cote)
            briques += porte
        else:
            gauche, droite = _cotes_dans_une_piece(o, mur, logement)
            briques += _fenetre(o, mur, cote_interieur=(1 if gauche else -1) if gauche != droite else 0)
    return briques


def _boite(o: Ouverture, mur: Mur, nom: str, t: tuple[float, float],
           n: tuple[float, float], z: tuple[float, float], materiau: str) -> Brique:
    """Une boîte posée dans l'ouverture : t le long du mur, n dans son épaisseur."""
    contour = _rectangle(mur, o.position + t[0], o.position + t[1], n[0], n[1])
    return Brique(f"{o.id}__{nom}", "menuiserie", o.id, contour, z[0], z[1], materiau)


def _fenetre(o: Ouverture, mur: Mur, cote_interieur: int = 0) -> list[Brique]:
    """Cadre tout autour, une ou deux vitres, un montant au milieu si elle est large.

    cote_interieur : +1 si la pièce est à gauche du mur, -1 à droite, 0 si on ne sait pas (pièce des deux côtés ou
    d'aucun). Le cadre est alors posé RETRAIT_FENETRE derrière la face intérieure (sinon au milieu du mur), avec un appui
    sous une fenêtre (pas sous une porte-fenêtre).
    """
    l, p = o.largeur, PROFIL
    bas, haut = o.allege, o.allege + o.hauteur
    s = cote_interieur
    centre = s * max(0.0, mur.epaisseur / 2 - RETRAIT_FENETRE - PROFONDEUR_CADRE / 2)
    cadre = (centre - PROFONDEUR_CADRE / 2, centre + PROFONDEUR_CADRE / 2)
    vitre = (centre - EPAISSEUR_VITRE / 2, centre + EPAISSEUR_VITRE / 2)
    m = "menuiserie_blanche"
    appui = []
    if s and o.type == "fenetre" and bas >= ALLEGE_MIN_APPUI:
        face = s * mur.epaisseur / 2
        z = (bas, bas + EPAISSEUR_APPUI)
        # dans l'épaisseur du mur (entre le cadre et la face), puis le nez qui dépasse dans la pièce
        appui = [
            _boite(o, mur, "appui", (0, l), tuple(sorted((centre + s * PROFONDEUR_CADRE / 2, face))), z, m),
            _boite(o, mur, "appui_nez", (-DEBORD_APPUI, l + DEBORD_APPUI),
                   tuple(sorted((face, face + s * DEBORD_APPUI))), z, m),
        ]
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
    return briques + appui


def _place_de_chaque_cote(o: Ouverture, mur: Mur, logement: Logement) -> tuple[float, float]:
    """La place libre sur le mur à gauche et à droite de l'ouverture o : jusqu'au bout du mur, ou la moitié de l'écart
    avec l'ouverture voisine (deux portes proches se partagent le trumeau : leurs chambranles ne se recouvrent pas)."""
    gauche, droite = o.position, max(0.0, mur.longueur - o.position - o.largeur)
    for x in logement.ouvertures:
        if x is o or x.mur != o.mur:
            continue
        if x.position + x.largeur <= o.position + 1e-9:
            gauche = min(gauche, (o.position - x.position - x.largeur) / 2)
        elif x.position >= o.position + o.largeur - 1e-9:
            droite = min(droite, (x.position - o.position - o.largeur) / 2)
    return gauche, droite


def _porte(o: Ouverture, mur: Mur, entree: bool, hsp: float = 99.0,
           libres: tuple[float, float] | None = None) -> list[Brique]:
    """Dormant (sur toute l'épaisseur du mur), battant fermé, deux poignées, et un chambranle sur chaque face.

    libres : la place sur le mur de chaque côté (_place_de_chaque_cote) ; par défaut, jusqu'aux bouts du mur."""
    l, p = o.largeur, PROFIL
    haut = o.allege + o.hauteur
    e = mur.epaisseur / 2 + DEBORD_CHAMBRANLE
    m = "menuiserie_blanche"
    battant = "porte_entree" if entree else "porte_interieure"
    demi = EPAISSEUR_PORTE / 2
    # La poignée est du côté opposé aux gonds : on la met côté fin du mur.
    poignee = (l - p - 0.13, l - p - 0.03)
    z_poignee = (HAUTEUR_POIGNEE - 0.01, HAUTEUR_POIGNEE + 0.01)
    briques = [
        _boite(o, mur, "montant_1", (0, p), (-e, e), (0, haut), m),
        _boite(o, mur, "montant_2", (l - p, l), (-e, e), (0, haut), m),
        _boite(o, mur, "traverse_haut", (p, l - p), (-e, e), (haut - p, haut), m),
        _boite(o, mur, "battant", (p, l - p), (-demi, demi), (JEU_SOL, haut - p), battant),
        _boite(o, mur, "poignee_1", poignee, (demi, demi + 0.05), z_poignee, "metal"),
        _boite(o, mur, "poignee_2", poignee, (-demi - 0.05, -demi), z_poignee, "metal"),
    ]
    # Chambranle : deux montants et une traverse posés SUR chaque face du mur, qui recouvrent le joint du dormant d'un cm.
    # Les trois morceaux ne se recouvrent pas (deux faces au même endroit scintillent au rendu). Coupés au bout du mur.
    lc, recouvre = LARGEUR_CHAMBRANLE, 0.01
    libre_g, libre_d = libres if libres is not None else (o.position, max(0.0, mur.longueur - o.position - l))
    gauche = (-min(lc, libre_g), recouvre)
    droite = (l - recouvre, l + min(lc, libre_d))
    z_haut = min(haut + lc, hsp - 0.001)
    for nom, s in (("a", 1), ("b", -1)):
        n = tuple(sorted((s * mur.epaisseur / 2, s * (mur.epaisseur / 2 + EPAISSEUR_CHAMBRANLE))))
        briques += [
            _boite(o, mur, f"chambranle_{nom}_1", gauche, n, (0, z_haut), m),
            _boite(o, mur, f"chambranle_{nom}_2", droite, n, (0, z_haut), m),
        ]
        if z_haut > haut - recouvre + 0.005:
            briques.append(_boite(o, mur, f"chambranle_{nom}_haut", (recouvre, l - recouvre), n,
                                  (haut - recouvre, z_haut), m))
    return briques


def _placard_derriere(o: Ouverture, mur: Mur, logement: Logement) -> tuple[Piece, int] | None:
    """(le placard, son côté du mur : +1 à gauche, -1 à droite) si la porte o donne dans un placard depuis une pièce."""
    (x0, y0), (x1, y1) = mur.debut, mur.fin
    ux, uy = (x1 - x0) / mur.longueur, (y1 - y0) / mur.longueur
    t = o.position + o.largeur / 2
    cx, cy = x0 + ux * t, y0 + uy * t
    d = mur.epaisseur / 2 + 0.05
    cotes = []
    for s in (1, -1):
        pt = (cx - uy * d * s, cy + ux * d * s)
        cotes.append(next((p for p in logement.pieces if _dans(pt, p.contour)), None))
    gauche, droite = cotes
    for placard, autre, s in ((gauche, droite, 1), (droite, gauche, -1)):
        if placard is not None and autre is not None and est_placard(placard) and not est_placard(autre):
            return placard, s
    return None


def _portes_de_placard_dans(o: Ouverture, mur: Mur, piece: Piece, cote: int) -> list[Brique]:
    """Les portes de placard posées dans l'ouverture o, entre les montants du dormant, près de la face côté pièce."""
    l, p = o.largeur, PROFIL
    haut = o.allege + o.hauteur
    ux, uy = (mur.fin[0] - mur.debut[0]) / mur.longueur, (mur.fin[1] - mur.debut[1]) / mur.longueur
    gauche = (-uy, ux)
    # face du mur côté pièce (opposée au placard), un peu en retrait ; « dedans » = vers le placard
    face = -cote * (mur.epaisseur / 2 - 0.005)
    debut = o.position + p
    origine = (mur.debut[0] + ux * debut + gauche[0] * face, mur.debut[1] + uy * debut + gauche[1] * face)
    dedans = (gauche[0] * cote, gauche[1] * cote)
    choix = choix_placard(piece, l - 2 * p)
    return _vantaux_placard(f"{o.id}__placard", o.id, origine, (ux, uy), dedans, l - 2 * p, JEU_SOL, haut - p, choix,
                            profondeur_max=mur.epaisseur - 0.01)


def portes_de_placard(briques: list[Brique], logement: Logement) -> list[Brique]:
    """B2-2 : les portes qui ferment la façade ouverte de chaque placard (là où il n'y a pas de mur, face à une pièce)."""
    sortie: list[Brique] = []
    hsp = logement.hauteur_sous_plafond
    for piece, facades in _facades_des_placards(briques, logement).values():
        for k, (origine, u, dedans, longueur) in enumerate(facades):
            choix = choix_placard(piece, longueur)
            sortie += _vantaux_placard(f"placard__{piece.id}__{k}", piece.id, origine, u, dedans, longueur, 0.0,
                                       hsp - 0.002, choix, rail=True)
    return sortie


def largeurs_des_facades(briques: list[Brique], logement: Logement) -> dict[str, float]:
    """Pour chaque placard : la largeur de sa plus grande façade (ouverte, ou dessinée comme une porte)."""
    largeurs = {pid: max(f[3] for f in facades) for pid, (_, facades) in _facades_des_placards(briques, logement).items()}
    murs = {m.id: m for m in logement.murs}
    for o in logement.ouvertures:
        if o.type == "porte" and o.mur in murs:
            placard = _placard_derriere(o, murs[o.mur], logement)
            if placard is not None:
                pid = placard[0].id
                largeurs[pid] = max(largeurs.get(pid, 0.0), o.largeur - 2 * PROFIL)
    return largeurs


def _facades_des_placards(briques: list[Brique], logement: Logement) -> dict:
    """{id du placard: (placard, [(origine, u, dedans, longueur)])} : les morceaux du bord du sol d'un placard sans mur derrière, qui
    donnent sur une autre pièce (pas un bout de mur, pas une porte : celles-là sont traitées avec la porte)."""
    murs_au_sol = [b.contour for b in briques
                   if b.categorie == "mur" and b.z_bas <= 1e-6 and b.z_haut >= HAUTEUR_PLINTHE - 1e-6]
    boites = [_boite_plan(c) for c in murs_au_sol]
    sols = {b.element: b for b in briques if b.categorie == "sol" and b.id == f"sol__{b.element}"}
    murs = {m.id: m for m in logement.murs}
    portes = [(o, murs[o.mur]) for o in logement.ouvertures if o.mur in murs]
    resultat: dict = {}
    for piece in logement.pieces:
        if piece.id not in sols or not est_placard(piece):
            continue
        contour = sols[piece.id].contour  # sens direct : l'intérieur du placard est à gauche
        facades = []
        for i in range(len(contour)):
            a, b = contour[i], contour[(i + 1) % len(contour)]
            longueur = math.dist(a, b)
            if longueur < FACADE_MIN:
                continue
            u = ((b[0] - a[0]) / longueur, (b[1] - a[1]) / longueur)
            gauche = (-u[1], u[0])
            libres = [(0.0, longueur)]
            for m in _morceaux_contre_un_mur(a, u, gauche, longueur, murs_au_sol, boites):
                libres = _retirer(libres, m)
            for o, mur in portes:
                place = _place_du_chambranle(a, u, longueur, o, mur)
                if place:
                    libres = _retirer(libres, place)
            for s0, s1 in libres:
                if s1 - s0 < FACADE_MIN:
                    continue
                milieu = (a[0] + u[0] * (s0 + s1) / 2 - gauche[0] * 0.10, a[1] + u[1] * (s0 + s1) / 2 - gauche[1] * 0.10)
                if not any(q.id != piece.id and _dans(milieu, q.contour) for q in logement.pieces):
                    continue
                facades.append(((a[0] + u[0] * s0, a[1] + u[1] * s0), u, gauche, s1 - s0))
        if facades:
            resultat[piece.id] = (piece, facades)
    return resultat


def _vantaux_placard(nom: str, element: str, origine: Point, u: Point, dedans: Point, longueur: float,
                     z0: float, z1: float, choix: str, rail: bool = False, profondeur_max: float = 1.0) -> list[Brique]:
    """Les portes d'une façade de placard de `longueur` m, posées à partir d'origine le long de u, vers « dedans ».

    battantes : des portes de VANTAIL_MAX m au plus, séparées d'une fente, une poignée verticale près de chaque jonction ;
    coulissantes : des panneaux de PANNEAU_MAX m au plus (deux au moins) qui se recouvrent, sur deux plans, avec un rail
    en haut et en bas quand la façade va du sol au plafond ; aucune : rien (placard ouvert)."""
    m, metal = "menuiserie_blanche", "metal"

    def boite(suffixe, t0, t1, n0, n1, za, zb, materiau):
        pts = [(origine[0] + u[0] * t + dedans[0] * n, origine[1] + u[1] * t + dedans[1] * n)
               for t, n in ((t0, n0), (t1, n0), (t1, n1), (t0, n1))]
        return Brique(f"{nom}__{suffixe}", "menuiserie", element, _sens_direct([_arrondi(q) for q in pts]), za, zb,
                      materiau)

    briques: list[Brique] = []
    if choix == "aucune" or longueur <= 0.05:
        return briques
    if choix == "battantes":
        k = max(1, math.ceil(longueur / VANTAIL_MAX - 1e-9))
        largeur = (longueur - (k - 1) * JEU_VANTAUX) / k
        n0, n1 = 0.002, 0.002 + EPAISSEUR_VANTAIL
        for j in range(k):
            t0 = j * (largeur + JEU_VANTAUX)
            briques.append(boite(f"vantail_{j}", t0, t0 + largeur, n0, n1, z0 + 0.003, z1 - 0.003, m))
            # poignée près de la jonction de chaque paire (j pair : à droite, j impair : à gauche) ;
            # une porte seule, ou la dernière d'un nombre impair, l'a à gauche (côté opposé aux gonds)
            tp = t0 + largeur - 0.06 if j % 2 == 0 else t0 + 0.045
            if k % 2 == 1 and j == k - 1:
                tp = t0 + 0.045
            briques.append(boite(f"poignee_{j}", tp, tp + 0.015, -0.025, n0, 0.95, 1.25, metal))
        return briques
    # coulissantes
    k = max(2, math.ceil((longueur - RECOUVREMENT) / (PANNEAU_MAX - RECOUVREMENT) - 1e-9))
    largeur = (longueur + (k - 1) * RECOUVREMENT) / k
    plans = ((0.005, 0.005 + EPAISSEUR_VANTAIL), (0.030, 0.030 + EPAISSEUR_VANTAIL))
    if plans[1][1] > profondeur_max:  # cloison mince : les deux plans se serrent
        e = EPAISSEUR_VANTAIL * 0.6
        plans = ((0.002, 0.002 + e), (0.004 + e, 0.004 + 2 * e))
    za, zb = z0 + 0.003, z1 - 0.003
    if rail:
        za, zb = z0 + 0.012, z1 - HAUTEUR_RAIL
        fond = plans[1][1] + 0.005
        briques.append(boite("rail_haut", 0.0, longueur, 0.0, fond, z1 - HAUTEUR_RAIL, z1, metal))
        briques.append(boite("rail_bas", 0.0, longueur, 0.0, fond, z0, z0 + 0.008, metal))
    for j in range(k):
        t0 = j * (largeur - RECOUVREMENT)
        n0, n1 = plans[j % 2]
        briques.append(boite(f"panneau_{j}", t0, t0 + largeur, n0, n1, za, zb, m))
        # prise de main : une baguette verticale sur le bord extérieur du panneau, côté pièce
        tp = t0 + 0.02 if j < k / 2 else t0 + largeur - 0.032
        briques.append(boite(f"prise_{j}", tp, tp + 0.012, n0 - 0.004, n0, 0.80, 1.40, metal))
    return briques


def _donne_dehors(o: Ouverture, mur: Mur, logement: Logement) -> bool:
    """Une porte donne dehors si un seul de ses deux côtés est dans une pièce."""
    gauche, droite = _cotes_dans_une_piece(o, mur, logement)
    return gauche != droite


def _cotes_dans_une_piece(o: Ouverture, mur: Mur, logement: Logement) -> tuple[bool, bool]:
    """(gauche, droite) : y a-t-il une pièce juste à gauche du mur, juste à droite, au milieu de l'ouverture ?"""
    (x0, y0), (x1, y1) = mur.debut, mur.fin
    ux, uy = (x1 - x0) / mur.longueur, (y1 - y0) / mur.longueur
    t = o.position + o.largeur / 2
    cx, cy = x0 + ux * t, y0 + uy * t
    d = mur.epaisseur / 2 + 0.05
    cotes = [(cx - uy * d, cy + ux * d), (cx + uy * d, cy - ux * d)]
    gauche, droite = (any(_dans(pt, p.contour) for p in logement.pieces) for pt in cotes)
    return gauche, droite


# --------------------------------------------------------------- plinthes


def plinthes(briques: list[Brique], logement: Logement) -> list[Brique]:
    """Les plinthes de chaque pièce (B2-1), posées sur le sol calé de la pièce (voir geometrie, B1).

    Chaque pièce suit son choix (choix_plinthes) : aucune, en bois (blanche), ou en carrelage (comme le sol, plus basse).
    Le long de chaque côté du sol, on garde les morceaux où il y a un mur au niveau du sol juste derrière (sonde à
    SONDE_MUR) : rien devant une porte, une porte-fenêtre ou un passage ouvert. On retire la place du chambranle autour de
    chaque porte. Dans un angle où deux morceaux se rejoignent, coupe en biseau (onglet) ; ailleurs, bout droit.
    """
    murs_au_sol = [b.contour for b in briques
                   if b.categorie == "mur" and b.z_bas <= 1e-6 and b.z_haut >= HAUTEUR_PLINTHE - 1e-6]
    boites = [_boite_plan(c) for c in murs_au_sol]
    murs = {m.id: m for m in logement.murs}
    portes = [(o, murs[o.mur]) for o in logement.ouvertures if o.type == "porte" and o.mur in murs]
    sols = {b.element: b for b in briques if b.categorie == "sol" and b.id == f"sol__{b.element}"}
    sortie: list[Brique] = []
    for piece in logement.pieces:
        choix = choix_plinthes(piece)
        if piece.id not in sols or choix == "aucune":
            continue
        if choix == "carrelage":
            epaisseur, hauteur = EPAISSEUR_PLINTHE_CARRELAGE, HAUTEUR_PLINTHE_CARRELAGE
            sol = sols[piece.id].materiau
            materiau = sol if sol != "parquet" else "carrelage"  # le carrelage du sol, ou un carrelage si le sol n'en a pas
        else:
            epaisseur, hauteur, materiau = EPAISSEUR_PLINTHE, HAUTEUR_PLINTHE, "menuiserie_blanche"
        contour = sols[piece.id].contour  # sens direct : l'intérieur de la pièce est à gauche de chaque côté
        n = len(contour)
        cotes = []  # par côté : (a, u, gauche, longueur, morceaux [(s0, s1)])
        for i in range(n):
            a, b = contour[i], contour[(i + 1) % n]
            longueur = math.dist(a, b)
            if longueur < 1e-6:
                cotes.append((a, (1.0, 0.0), (0.0, 1.0), 0.0, []))
                continue
            u = ((b[0] - a[0]) / longueur, (b[1] - a[1]) / longueur)
            gauche = (-u[1], u[0])
            morceaux = _morceaux_contre_un_mur(a, u, gauche, longueur, murs_au_sol, boites)
            for o, mur in portes:
                place = _place_du_chambranle(a, u, longueur, o, mur)
                if place:
                    morceaux = _retirer(morceaux, place)
            cotes.append((a, u, gauche, longueur, [m for m in morceaux if m[1] - m[0] >= PLINTHE_MIN]))

        onglets = [_onglet_plinthe(contour[i], cotes[i - 1][2], cotes[i][2], epaisseur) for i in range(n)]
        for i, (a, u, gauche, longueur, morceaux) in enumerate(cotes):
            precedent, suivant = cotes[i - 1][4], cotes[(i + 1) % n][4]
            for k, (s0, s1) in enumerate(morceaux):
                p0 = (a[0] + u[0] * s0, a[1] + u[1] * s0)
                p1 = (a[0] + u[0] * s1, a[1] + u[1] * s1)
                droit0 = (p0[0] + gauche[0] * epaisseur, p0[1] + gauche[1] * epaisseur)
                droit1 = (p1[0] + gauche[0] * epaisseur, p1[1] + gauche[1] * epaisseur)
                q0 = onglets[i] if (s0 <= 1e-6 and precedent and precedent[-1][1] >= cotes[i - 1][3] - 1e-6
                                    and onglets[i]) else droit0
                q1 = onglets[(i + 1) % n] if (s1 >= longueur - 1e-6 and suivant and suivant[0][0] <= 1e-6
                                               and onglets[(i + 1) % n]) else droit1
                quad = [p0, p1, q1, q0]
                if _aire_signee_plan(quad) <= 1e-9 or _projete(q1, a, u) < _projete(q0, a, u):
                    quad = [p0, p1, droit1, droit0]  # biseau impossible (morceau trop court) : bouts droits
                sortie.append(Brique(f"plinthe__{piece.id}__{i}_{k}", "menuiserie", piece.id,
                                     _sens_direct([_arrondi(q) for q in quad]), 0.0, hauteur, materiau))
    return sortie


def _morceaux_contre_un_mur(a: Point, u: Point, gauche: Point, longueur: float, murs_au_sol: list,
                            boites: list) -> list[tuple[float, float]]:
    """Les morceaux (s0, s1) du côté qui part de a le long de u où un mur au niveau du sol est juste derrière (à SONDE_MUR,
    du côté opposé à « gauche », l'intérieur de la pièce)."""
    a2 = (a[0] - gauche[0] * SONDE_MUR, a[1] - gauche[1] * SONDE_MUR)
    b2 = (a[0] + u[0] * longueur - gauche[0] * SONDE_MUR, a[1] + u[1] * longueur - gauche[1] * SONDE_MUR)
    (sx0, sy0), (sx1, sy1) = _boite_plan([a2, b2])
    morceaux: list[tuple[float, float]] = []
    for contour_mur, ((bx0, by0), (bx1, by1)) in zip(murs_au_sol, boites):
        if bx0 <= sx1 and sx0 <= bx1 and by0 <= sy1 and sy0 <= by1:
            morceaux += [(t0 * longueur, t1 * longueur) for t0, t1 in _segment_dans(a2, b2, contour_mur)]
    return _reunir(morceaux)


def _onglet_plinthe(sommet: Point, gauche_avant: Point, gauche_apres: Point,
                    epaisseur: float = EPAISSEUR_PLINTHE) -> Point | None:
    """Le coin intérieur de la plinthe dans l'angle : croisement des deux lignes décalées de l'épaisseur de la plinthe.

    None si l'angle est trop aigu (le biseau partirait trop loin)."""
    somme = (gauche_avant[0] + gauche_apres[0], gauche_avant[1] + gauche_apres[1])
    diviseur = 1 + gauche_avant[0] * gauche_apres[0] + gauche_avant[1] * gauche_apres[1]
    if diviseur < 0.15:
        return None
    return (sommet[0] + somme[0] * epaisseur / diviseur, sommet[1] + somme[1] * epaisseur / diviseur)


def _segment_dans(a: Point, b: Point, contour: list[Point]) -> list[tuple[float, float]]:
    """Les morceaux du segment a-b (en fractions de 0 à 1) qui sont à l'intérieur du contour."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    coupures = {0.0, 1.0}
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        ex, ey = x2 - x1, y2 - y1
        diviseur = dx * ey - dy * ex
        if abs(diviseur) < 1e-12:
            continue
        t = ((x1 - a[0]) * ey - (y1 - a[1]) * ex) / diviseur
        v = ((x1 - a[0]) * dy - (y1 - a[1]) * dx) / diviseur
        if 0 < t < 1 and -1e-9 <= v <= 1 + 1e-9:
            coupures.add(t)
    bornes = sorted(coupures)
    dedans = [(t0, t1) for t0, t1 in zip(bornes, bornes[1:])
              if t1 - t0 > 1e-9 and _dans((a[0] + dx * (t0 + t1) / 2, a[1] + dy * (t0 + t1) / 2), contour)]
    return _reunir(dedans)


def _place_du_chambranle(a: Point, u: Point, longueur: float, o: Ouverture, mur: Mur) -> tuple[float, float] | None:
    """La partie du côté de pièce (a, u) qui longe la porte o et ses chambranles, ou None si ce côté ne longe pas son mur."""
    w = ((mur.fin[0] - mur.debut[0]) / mur.longueur, (mur.fin[1] - mur.debut[1]) / mur.longueur)
    if abs(u[0] * w[1] - u[1] * w[0]) > math.sin(math.radians(5)):
        return None
    milieu = (a[0] + u[0] * longueur / 2 - mur.debut[0], a[1] + u[1] * longueur / 2 - mur.debut[1])
    if abs(-w[1] * milieu[0] + w[0] * milieu[1]) > mur.epaisseur / 2 + 0.05:
        return None
    t_a = (a[0] - mur.debut[0]) * w[0] + (a[1] - mur.debut[1]) * w[1]
    sens = u[0] * w[0] + u[1] * w[1]  # ±1 : le côté de pièce va dans le sens du mur ou à l'envers
    marge = LARGEUR_CHAMBRANLE + JEU_PLINTHE
    s1, s2 = ((o.position - marge - t_a) / sens, (o.position + o.largeur + marge - t_a) / sens)
    return min(s1, s2), max(s1, s2)


def _reunir(morceaux: list[tuple[float, float]]) -> list[tuple[float, float]]:
    sortie: list[tuple[float, float]] = []
    for d, f in sorted(morceaux):
        if sortie and d <= sortie[-1][1] + 1e-9:
            sortie[-1] = (sortie[-1][0], max(sortie[-1][1], f))
        else:
            sortie.append((d, f))
    return sortie


def _retirer(morceaux: list[tuple[float, float]], trou: tuple[float, float]) -> list[tuple[float, float]]:
    sortie = []
    for d, f in morceaux:
        if f <= trou[0] or d >= trou[1]:
            sortie.append((d, f))
            continue
        if d < trou[0]:
            sortie.append((d, trou[0]))
        if f > trou[1]:
            sortie.append((trou[1], f))
    return sortie


def _projete(point: Point, a: Point, u: Point) -> float:
    return (point[0] - a[0]) * u[0] + (point[1] - a[1]) * u[1]


def _aire_signee_plan(contour: list[Point]) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1])) / 2


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
