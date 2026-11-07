"""Le lot 2 du générateur (option --lot2) : les styles vus sur les 103 vrais plans reçus.

Pourquoi : Atelya rate les styles jamais vus. Ce module apprend au générateur à les dessiner, pour que
l'essai 8 les apprenne sur des plans dont la vérité est exacte. Les traits sont ceux de
docs/projet/etapes/catalogue-styles-lot2.md ; ce qui est dessiné ici imite des plans d'ENTRAÎNEMENT
(fr-075, fr-094, fr-096, fr-098, fr-076, fr-117, fr-046, fr-063, fr-093, fr-074, fr-023, fr-035, fr-031,
fr-105, fr-067, fr-120, fr-027), jamais un plan d'examen.

Trois choses séparées, comme le lot 1 (variete.py) :

- le tirage (`lot2_au_hasard`) : un hasard à part, tout est rangé dans un `Lot2` ; sans l'option, aucun
  hasard existant n'est consommé et le dessin reste celui de la version précédente ;
- la recopie (`appliquer`) : sans aucun hasard, le `Lot2` est recopié dans les champs du `Style` ;
- le dessin : des fonctions qui reçoivent le `_Dessin` et ne touchent QUE son image. Jamais les masques :
  une étiquette, un tableau ou une cote reste du fond, une fenêtre bleue reste une fenêtre.

Chantier 1 : traits 1, 2, 4 (sans les balcons), 5, 8, 16, 19, 20. Les champs marqués « chantier 2 / 3 »
existent déjà pour que le format ne change plus, mais rien ne les tire ni ne les dessine encore.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, fields

from moteur.dessin_plan import _police
from moteur.generateur.annotations import rect_de_l_ouverture
from moteur.generateur.logements import surface_piece
from moteur.generateur.variete import Variete

RECUL_COTE = 60  # le même que rendu.RECUL_COTE (rendu importe ce module, pas l'inverse ; un test vérifie l'égalité)

# Toutes les familles du catalogue, et celles qui sont tirées aujourd'hui. Poids = fréquences sur 103 plans.
FAMILLES_LOT2 = ("agence_coloree", "promoteur_gris", "murs_noirs", "carrez_legende", "logiciel_public", "scan_ancien",
                 "cotes_rouges", "neutre")
POIDS_FAMILLES = {"agence_coloree": 14, "murs_noirs": 13, "carrez_legende": 8, "cotes_rouges": 2, "neutre": 10}

# Couleurs relevées sur fr-075, fr-094, fr-096, fr-116 : des pastels ternes, pas des couleurs vives.
_BEIGE, _PECHE, _BLEU, _ROSE, _GRIS = (238, 232, 214), (251, 238, 222), (222, 226, 239), (231, 213, 201), (211, 211, 211)
_SORTES = ("sejour", "principale", "cuisine", "chambre", "bureau", "sdb", "sde", "wc", "entree", "degagement", "placard",
           "buanderie", "escalier")
# Une table à part : variantes.PALETTES est tirée par le hasard de base, y ajouter une clé changerait les anciens jeux.
PALETTES_LOT2 = {
    "agence": {"sejour": _BEIGE, "principale": _BEIGE, "cuisine": _BEIGE, "chambre": _PECHE, "bureau": _ROSE, "sdb": _BLEU,
               "sde": _BLEU, "wc": _BLEU, "entree": _ROSE, "degagement": _ROSE, "placard": _GRIS, "buanderie": _GRIS,
               "escalier": _GRIS},
    "agence_grise": {"sejour": _BEIGE, "principale": _GRIS, "cuisine": _BEIGE, "chambre": _GRIS, "bureau": _GRIS, "sdb": _BLEU,
                     "sde": _BLEU, "wc": _BLEU, "entree": _PECHE, "degagement": _ROSE, "placard": _GRIS, "buanderie": _GRIS,
                     "escalier": _GRIS},
    "blanc": {s: (255, 255, 255) for s in _SORTES},  # fr-098, fr-076 : pièces blanches sur une page gris clair
    "bleu_uni": {s: (203, 225, 245) for s in _SORTES},  # fr-067 : toutes les pièces du même bleu
}

# Ce qui reste dessiné d'un plan d'agence sans « mobilier » (fr-075) : les équipements fixes, jamais lits ni canapés.
MEUBLES_FIXES = {"baignoire", "douche", "lavabo", "wc", "plan_de_travail", "lave_linge", "escalier"}

ABREVIATIONS = {"Dégagement": "Dgt", "Rangement": "Rgt", "Salle de bains": "SdB", "Salle de bain": "SdB", "Salle d'eau": "SdE",
                "Chambre": "Ch.", "Placard": "Pl.", "Cuisine": "Cuis.", "Toilettes": "WC", "Pièce principale": "Pièce"}
SOLS_ECRITS = {"sdb": ("carrelage",), "sde": ("carrelage",), "wc": ("carrelage",), "cuisine": ("carrelage", "lino"),
               "entree": ("carrelage",), "degagement": ("carrelage", "lino"), "buanderie": ("lino", "carrelage"),
               "chambre": ("parquet", "moquette", "carrelage"), "bureau": ("parquet", "moquette"),
               "sejour": ("parquet", "carrelage"), "principale": ("parquet", "carrelage"), "placard": (), "escalier": ()}


@dataclass
class Lot2:
    """Tout ce qui a été tiré pour un plan du lot 2 : enregistré avec le style (annotations.json)."""

    famille: str = "neutre"
    # ---- page (None : on garde la valeur du style de base)
    couleur_murs: tuple[int, int, int] | None = None
    couleur_fond: tuple[int, int, int] | None = None
    couleur_traits: tuple[int, int, int] | None = None
    couleur_textes: tuple[int, int, int] | None = None
    px_par_m: float | None = None
    part_texte: float | None = None  # taille du texte = part × px_par_m
    epaisseur_trait: float | None = None
    marges: tuple[int, int, int, int] | None = None  # haut, bas, gauche, droite
    murs_dessin: str = ""  # "" (plein), trait, double, hachure : le dessin des murs, le masque ne change pas
    epaisseur_trait_mur: float = 0.25  # trait / double : part de l'épaisseur du mur
    vantail_fin: bool = False  # battant de porte d'un trait fin (les logiciels d'agence)
    doubles_vantaux: bool = False  # fr-075, fr-096 : portes-fenêtres à deux battants
    sans_mobilier: bool = False  # fr-098, fr-067 : aucun meuble, quel que soit le style de base
    arcs_pointilles: bool = False  # fr-046
    # ---- trait 1 : agence colorée foncée
    palette: str = ""  # une clé de PALETTES_LOT2
    mobilier_fixes: bool = False  # seulement les équipements fixes
    mobilier_couleur: bool = False  # meubles remplis d'une couleur claire
    rose_des_vents: bool = False
    legende_niveau: bool = False  # « Niveau 0 » sous le plan
    surface_totale: bool = False  # colonne « Surface totale approximative » à droite
    # ---- écriture des pièces (traits 1, 2, 4, 5, 19)
    noms_gras: bool = False
    majuscules: bool = False
    noms_tronques: bool = False  # « Plac… » au lieu de réduire le texte (fr-076, fr-117)
    noms_courts: bool = False  # trait 5 : la surface n'est plus dans la pièce, seulement au tableau
    sans_noms: bool = False  # trait 5 : les pièces ne portent rien, tout est dans la légende
    surface_decimales: int = 2
    surface_point: bool = False  # « 14.5 m² » au lieu de « 14,5 m² »
    couleur_surface: tuple[int, int, int] | None = None
    parentheses_grises: bool = False  # trait 4 : « (12,2 m²) »
    # ---- trait 2 : dimensions de pièce
    dimensions: str = ""  # "", remplace, ajoute
    format_dimensions: str = "3,05 m × 2,85 m"  # ou « 3.87 x 4.65 m »
    etiquettes: str = ""  # "", bloc (tout le texte dans un cadre), surface (seule la surface, fr-063)
    couleur_etiquette: tuple[int, int, int] = (255, 255, 255)
    triangles: bool = False  # petits repères au milieu de chaque côté (fr-098, fr-117)
    portes_boites: bool = False  # portes en rectangles blancs cernés (fr-098, fr-076)
    # ---- trait 5 : légende / tableau de surfaces
    tableau: str = ""  # "", droite, gauche, bas
    tableau_bordures: bool = False
    tableau_prefixe: str = ""  # « 3ème étage - »
    tableau_decimales: int = 2
    tableau_couleur: tuple[int, int, int] | None = None
    # ---- trait 8 : fenêtres pleines
    fenetres_pleines: bool = False
    couleur_fenetres: tuple[int, int, int] = (64, 200, 215)
    contour_fenetres: tuple[int, int, int] = (40, 60, 90)
    # ---- trait 16 : cotes rouges
    couleur_cotes: tuple[int, int, int] | None = None
    cotes_interieures_rouges: bool = False  # chaînes tirées à l'intérieur des pièces (fr-031)
    cote_point: bool = False  # « 8.04 » au lieu de « 8,04 »
    echelle_ecrite: str = ""  # « Échelle : 1/50e »
    # ---- trait 19 : HSP et mention de sol
    hsp: str = ""  # "", « hsp: », « HsP : », « HSP cercle »
    mention_sol: str = ""  # "", « sol », « (sol) »
    # ---- trait 20 : image recadrée serrée
    recadre: bool = False
    # ---- socle
    sortie_jpeg: bool = False
    # ---- chantier 2 (pas encore tirés ni dessinés)
    unite_cotes: str = "m"
    cotes_par_mur: bool = False
    sans_chaines: bool = False
    cercles_pmr: bool = False
    numero_lot: str = ""
    abreviations: bool = False
    mentions_menuiseries: bool = False
    exterieurs: list[dict] = field(default_factory=list)
    textes_verticaux: bool = False
    teinte: tuple[float, float, float] | None = None
    manuscrit: str = ""
    placards_fleches: bool = False
    escalier: str = ""
    pastilles: bool = False
    # ---- chantier 3 (pas encore tirés ni dessinés)
    ecran: bool = False
    composition: str = ""
    disposition: str = ""


def _gris(rng: random.Random, a: int, b: int) -> tuple[int, int, int]:
    g = rng.randint(a, b)
    return (g, g, g)


def lot2_au_hasard(rng: random.Random, famille: str | None = None, transversaux: bool = True) -> Lot2:
    """Un tirage complet. `famille` l'impose et `transversaux=False` s'en tient à la famille (tests, planches)."""
    if famille is None:
        famille = rng.choices(list(POIDS_FAMILLES), weights=list(POIDS_FAMILLES.values()))[0]
    l = Lot2(famille=famille)
    if famille == "agence_coloree":
        _tirer_agence(l, rng)
    elif famille == "murs_noirs":
        _tirer_murs_noirs(l, rng)
    elif famille == "carrez_legende":
        _tirer_carrez(l, rng)
    elif famille == "cotes_rouges":
        _tirer_cotes_rouges(l, rng)
    if transversaux:
        _tirer_transversaux(l, rng)
    return l


def _tirer_agence(l: Lot2, rng: random.Random) -> None:
    """Trait 1. Murs bleu nuit presque noirs : sur fr-075 ils valent environ (26, 34, 52), pas un bleu franc."""
    if rng.random() < 0.8:
        l.couleur_murs = (rng.randint(18, 34), rng.randint(26, 44), rng.randint(44, 72))
    else:
        l.couleur_murs = _gris(rng, 10, 30)
    t = rng.randint(70, 100)
    l.couleur_traits = (t, t + 4, t + 12)
    l.couleur_textes = (rng.randint(25, 45), rng.randint(30, 50), rng.randint(50, 70))
    l.couleur_fond = (255, 255, 255)
    l.px_par_m = rng.randint(95, 130)
    l.part_texte = rng.uniform(0.14, 0.18)
    l.epaisseur_trait = rng.uniform(0.008, 0.012)
    l.marges = (rng.randint(30, 80), rng.randint(90, 140), rng.randint(40, 110), rng.randint(40, 120))
    l.palette = "agence" if rng.random() < 0.7 else "agence_grise"
    l.mobilier_fixes = l.mobilier_couleur = rng.random() < 0.75
    l.rose_des_vents = True
    l.legende_niveau = rng.random() < 0.85
    l.surface_totale = rng.random() < 0.6
    l.noms_gras = True
    l.surface_decimales, l.surface_point = 1, True
    g = rng.randint(100, 130)
    l.couleur_surface = (g, g, g + 8)
    l.vantail_fin = True
    l.doubles_vantaux = rng.random() < 0.6


def _tirer_murs_noirs(l: Lot2, rng: random.Random) -> None:
    """Trait 4 (sans les balcons, chantier 2) : fr-046, fr-063, fr-092."""
    l.couleur_murs = _gris(rng, 0, 25)
    l.couleur_traits = _gris(rng, 40, 70)
    l.couleur_textes = _gris(rng, 20, 50)
    l.couleur_fond = (255, 255, 255)
    l.px_par_m = rng.randint(100, 130)
    l.part_texte = rng.uniform(0.14, 0.19)
    l.marges = (rng.randint(30, 110), rng.randint(30, 110), rng.randint(30, 110), rng.randint(30, 110))
    l.parentheses_grises = rng.random() < 0.7
    l.couleur_surface = _gris(rng, 120, 150)
    l.surface_decimales = rng.choice((1, 2, 2))  # « (12,2 m²) » au catalogue, « (7,79 m²) » sur fr-046
    l.noms_gras = rng.random() < 0.6
    l.arcs_pointilles = rng.random() < 0.4
    l.vantail_fin = rng.random() < 0.5
    if not l.parentheses_grises and rng.random() < 0.5:  # fr-063 : la surface dans un petit cadre beige
        l.etiquettes = "surface"
        l.couleur_etiquette = (rng.randint(240, 248), rng.randint(228, 238), rng.randint(215, 228))


def _tirer_carrez(l: Lot2, rng: random.Random) -> None:
    """Trait 5 : fr-093 (tableau à bordures sous le plan), fr-074 (colonne sans bordure à gauche)."""
    l.tableau = rng.choice(("droite", "gauche", "bas", "bas"))
    l.tableau_bordures = l.tableau == "bas" and rng.random() < 0.8 or rng.random() < 0.3
    l.tableau_prefixe = rng.choice(("3ème étage - ", "RDC - ", "1er étage - ")) if l.tableau == "bas" and rng.random() < 0.4 else ""
    l.tableau_decimales = 1 if rng.random() < 0.2 else 2
    if rng.random() < 0.5:
        l.tableau_couleur = (rng.randint(20, 40), rng.randint(30, 50), rng.randint(90, 130))
    l.noms_courts = True
    l.sans_noms = rng.random() < 1 / 3
    if rng.random() < 0.3:
        l.couleur_murs = _gris(rng, 0, 20)


def _tirer_cotes_rouges(l: Lot2, rng: random.Random) -> None:
    """Trait 16 : fr-031 (rouge franc, à l'intérieur des pièces), fr-105 (rouge pâle)."""
    l.couleur_cotes = (rng.randint(170, 215), rng.randint(20, 50), rng.randint(20, 50))
    l.cotes_interieures_rouges = rng.random() < 0.8
    l.cote_point = rng.random() < 0.5
    l.echelle_ecrite = rng.choice(("Échelle : 1/50e", "Échelle : 1/50°", "Ech. 1/100"))
    l.murs_dessin = "double" if rng.random() < 0.7 else ""
    l.epaisseur_trait_mur = rng.uniform(0.1, 0.2)
    l.couleur_fond = (255, 255, 255)
    l.couleur_textes = _gris(rng, 20, 40)
    l.noms_courts = True  # fr-031 : des cotes partout, pas de surface écrite


def _tirer_transversaux(l: Lot2, rng: random.Random) -> None:
    """Les traits indépendants de la famille."""
    if rng.random() < 0.2:
        l.dimensions = rng.choice(("ajoute", "ajoute", "remplace"))
        l.format_dimensions = rng.choice(("3,05 m × 2,85 m", "3,05 m × 2,85 m", "3.87 x 4.65 m"))
        if not l.etiquettes and rng.random() < 0.25:
            l.etiquettes = "bloc"
        if l.famille in ("neutre", "murs_noirs") and rng.random() < 0.6:
            _tirer_releve(l, rng)
    if rng.random() < 0.1 and not l.fenetres_pleines:
        l.fenetres_pleines = True
        if rng.random() < 0.6:  # fr-035 : cyan ; fr-023, fr-027 : bleu clair
            l.couleur_fenetres = (rng.randint(50, 90), rng.randint(190, 215), rng.randint(205, 230))
        else:
            l.couleur_fenetres = (rng.randint(110, 170), rng.randint(175, 215), rng.randint(235, 250))
        if not l.murs_dessin and l.famille == "neutre" and rng.random() < 0.7:
            l.murs_dessin = "trait"  # sur fr-023 et fr-035 les murs sont un simple trait
            l.epaisseur_trait_mur = rng.uniform(0.2, 0.3)  # moins, une cloison de 7 cm ferait 1 px et s'effacerait à 768 px
    if rng.random() < 0.08:
        l.hsp = rng.choice(("hsp:", "HsP :", "HSP cercle"))
    if rng.random() < 0.05:
        l.mention_sol = rng.choice(("sol", "(sol)"))
    if l.hsp or l.mention_sol:
        l.majuscules = rng.random() < 0.4  # fr-105, fr-120
        if l.famille == "neutre" and rng.random() < 0.3:  # fr-067 : pièces bleues, murs gris clair, pas de meubles
            l.palette = "bleu_uni"
            l.couleur_murs = _gris(rng, 185, 205)
            l.couleur_fond = (255, 255, 255)
            l.couleur_textes = _gris(rng, 15, 40)
            l.sans_mobilier = True
    if rng.random() < 0.08 and l.famille in ("neutre", "murs_noirs"):
        l.recadre = True
        _tirer_marges_serrees(l, rng)
    l.sortie_jpeg = rng.random() < 0.3


def _tirer_releve(l: Lot2, rng: random.Random) -> None:
    """Le relevé d'appli (fr-098, fr-076, fr-117) : page gris clair, pièces blanches, murs noirs, repères, noms coupés."""
    g = rng.randint(238, 245)
    l.couleur_fond = (g, g, g - 2)
    l.palette = "blanc"
    l.couleur_murs = _gris(rng, 0, 20)
    l.couleur_textes = _gris(rng, 40, 70)
    l.couleur_surface = _gris(rng, 70, 95)
    l.noms_gras = True
    l.parentheses_grises = False
    l.dimensions = "ajoute"
    l.format_dimensions = "3,05 m × 2,85 m"
    l.etiquettes = ""
    l.surface_decimales = 1
    l.triangles = True
    l.sans_mobilier = True
    l.noms_tronques = True
    l.portes_boites = True
    l.fenetres_pleines = True
    l.couleur_fenetres = (255, 255, 255)
    l.contour_fenetres = (20, 20, 20)
    l.arcs_pointilles = False
    l.px_par_m = rng.randint(90, 125)
    l.part_texte = rng.uniform(0.14, 0.17)
    l.marges = (rng.randint(20, 60), rng.randint(20, 60), rng.randint(60, 200), rng.randint(60, 200))


def _tirer_marges_serrees(l: Lot2, rng: random.Random) -> None:
    """Trait 20. fr-027 n'est serré qu'en hauteur ; d'autres le sont des quatre côtés."""
    serre = [rng.randint(0, 12) for _ in range(4)]
    forme = rng.choice(("tout", "tout", "hauteur", "largeur"))
    if forme == "hauteur":
        serre[2], serre[3] = rng.randint(40, 200), rng.randint(40, 200)
    elif forme == "largeur":
        serre[0], serre[1] = rng.randint(40, 200), rng.randint(40, 200)
    l.marges = tuple(serre)  # type: ignore[assignment]


def appliquer(style, l: Lot2, sans_cotes: bool = False) -> None:
    """Recopie le tirage dans le style, sans aucun hasard.

    `sans_cotes` : --sans-cotes gagne toujours. Le banc « sans cotes » suppose qu'aucune cote n'est écrite ;
    une famille ne doit donc pas rallumer ce que l'option a éteint."""
    surfaces0 = style.surfaces
    v = style.variete
    absurde = v is not None and (v.absurde or v.inverse)
    style.lot2 = l
    if absurde:  # un style absurde apprend qu'un mur reste un mur : on ne lui rend pas des couleurs sages
        l.couleur_murs = l.couleur_fond = l.couleur_traits = l.couleur_textes = l.couleur_cotes = None
        l.palette, l.fenetres_pleines, l.portes_boites, l.couleur_surface, l.mobilier_couleur = "", False, False, None, False
        l.tableau_couleur = None
    for champ, attribut in (("couleur_murs", "murs"), ("couleur_fond", "fond"), ("couleur_traits", "traits"),
                            ("couleur_textes", "textes"), ("epaisseur_trait", "epaisseur_trait"), ("px_par_m", "px_par_m"),
                            ("marges", "marges")):
        valeur = getattr(l, champ)
        if valeur is not None:
            setattr(style, attribut, valeur)
    if l.part_texte is not None:
        style.taille_texte = round(style.px_par_m * l.part_texte)
    if l.palette:
        style.pieces_colorees = True
    if l.couleur_murs is not None:
        style.murs_contour = False  # des murs foncés pleins ne se cernent pas d'un trait
    if l.mobilier_fixes:
        style.mobilier = True
    if l.doubles_vantaux:
        style.doubles_vantaux = True
    if l.famille == "agence_coloree":
        style.mobilier = l.mobilier_fixes
        style.surfaces = style.noms = style.symboles = style.arcs = True
        style.cotes = style.cotes_partielles = style.cartouche = style.titre = style.fleche_nord = False
        style.echelle_graphique = False
    elif l.famille == "murs_noirs":
        style.mobilier = False
        style.pieces_colorees = bool(l.palette)  # fr-046, fr-063 : pièces blanches, sinon le noir ne ressort plus
        style.surfaces = style.noms = style.symboles = style.arcs = True
        style.cotes = style.cotes_partielles = style.cartouche = style.fleche_nord = False
        style.titre = False
        style.echelle_graphique = False
    elif l.famille == "carrez_legende":
        style.surfaces = style.noms = style.symboles = True
        style.cartouche = False  # la marge de droite est pour le tableau
        if l.tableau == "bas":
            style.echelle_graphique = False  # le tableau prend sa place
    elif l.famille == "cotes_rouges":
        style.cotes = style.noms = style.symboles = True
        style.mobilier = style.cartouche = style.titre = False
    if l.sans_noms:
        style.noms = False
    if l.sans_mobilier:
        style.mobilier = False
    if l.dimensions:
        style.surfaces = True  # écrire une dimension demande la permission des surfaces (--sans-cotes l'éteint plus bas)
    if l.couleur_murs is not None or l.palette or l.couleur_cotes is not None:
        # La photocopie et les taches passent l'image en gris : le trait disparaîtrait.
        if style.salissure in ("photocopie", "taches"):
            style.salissure = "jpeg"
    if l.triangles:  # le relevé d'appli n'a ni cotes, ni cartouche
        style.cotes = style.cotes_partielles = style.cartouche = style.titre = style.fleche_nord = False
        style.echelle_graphique = False
        style.noms = style.symboles = True
    if style.focale:  # une vraie photo n'est pas recadrée sur la page
        l.recadre = False
    if l.recadre:
        # Sinon le Repere élargirait lui-même les marges pour y loger ces éléments.
        style.cotes = style.cotes_partielles = style.cartouche = style.titre = style.echelle_graphique = False
        style.rotation, style.perspective = 0.0, 0.0  # le logement touche les bords : rien ne doit l'en éloigner
    if v is not None and not absurde:
        # Famille à murs pleins : un trait fin de --styles-monde contredirait le style imité.
        if l.famille in ("agence_coloree", "murs_noirs"):
            v.murs = "plein"
        elif l.murs_dessin:
            v.murs, v.epaisseur_trait_mur = l.murs_dessin, l.epaisseur_trait_mur
    if style.rotation or style.perspective or style.focale:
        # Défaut connu de contour_des_murs : contour calculé sur le masque tourné, dessiné à plat (double contour décalé).
        style.murs_contour = False
    if sans_cotes:
        style.cotes, style.surfaces = False, surfaces0
    if not style.cotes:
        style.cotes_partielles = False


def resume(l: Lot2) -> dict:
    """Pour le manifeste : la famille et les traits allumés, sans les couleurs."""
    ignores = {"famille", "marges", "px_par_m", "part_texte", "epaisseur_trait", "epaisseur_trait_mur", "surface_decimales",
               "tableau_decimales", "format_dimensions", "unite_cotes", "couleur_etiquette", "couleur_fenetres", "contour_fenetres",
               "surface_point", "cote_point", "sortie_jpeg", "noms_gras"}
    traits = []
    for f in fields(l):
        valeur = getattr(l, f.name)
        if f.name in ignores or f.name.startswith("couleur_") or f.name == "tableau_couleur":
            continue
        if valeur:
            traits.append(f.name)
    return {"famille": l.famille, "traits": traits, "composition": l.composition}


def garder_fixes(meubles: dict) -> dict:
    gardes = {pid: [m for m in lst if m.type in MEUBLES_FIXES] for pid, lst in meubles.items()}
    return {pid: lst for pid, lst in gardes.items() if lst}


# ---------------------------------------------------------------- marges (appelé par rendu.Repere)


def marges_lot2(style, marges: tuple[int, int, int, int], nb_pieces: int) -> tuple[int, int, int, int]:
    """La place à réserver dans la page pour ce qui s'écrit hors du logement.

    Elle est prise AVANT de calculer la taille de l'image : les masques ont donc la même taille que le plan."""
    l = style.lot2
    if l.recadre:
        return marges  # les marges tirées sont justement la mesure du trait
    haut, bas, gauche, droite = marges
    t = style.taille_texte
    if l.rose_des_vents:
        bas = max(bas, math.ceil(6 * t))
    if l.legende_niveau:
        bas = max(bas, math.ceil(3.5 * t))
    if l.surface_totale and style.surfaces:
        droite = max(droite, math.ceil(_largeur_colonne_surface(style) + 3 * t))
    if l.echelle_ecrite and style.cotes:
        haut = max(haut, RECUL_COTE + math.ceil(4.6 * t) + 10)
    if l.tableau and style.surfaces:
        if l.tableau == "bas":
            bas = max(bas, math.ceil(_debut_tableau(style) + _hauteur_tableau_bas(style, nb_pieces) + 20))
        else:
            place = math.ceil(_debut_tableau(style) + _largeur_colonne(style) + 20)
            if l.tableau == "droite":
                droite = max(droite, place)
            else:
                gauche = max(gauche, place)
    return haut, bas, gauche, droite


def _largeur_colonne_surface(style) -> float:
    return _police(style.police, max(8, round(style.taille_texte * 0.65))).getlength("Surface totale approximative") * 1.1


def _debut_tableau(style) -> float:
    """Le tableau commence au-delà des chaînes de cotes éventuelles."""
    return RECUL_COTE + 2.2 * style.taille_texte + 12 if style.cotes else 30


def _taille_tableau(style) -> int:
    return max(9, round(style.taille_texte * 0.85))


def _largeur_colonne(style) -> float:
    police = _police(style.police, _taille_tableau(style))
    return police.getlength("Chambre / bureau 2") + police.getlength("000,00 m²") + 2 * _taille_tableau(style)


def _hauteur_tableau_bas(style, nb_pieces: int) -> float:
    return (nb_pieces + 5) * _taille_tableau(style) * 1.5


# ---------------------------------------------------------------- écrire


def _nombre(valeur: float, decimales: int, point: bool = False) -> str:
    texte = f"{valeur:.{decimales}f}"
    return texte if point else texte.replace(".", ",")


def format_dimensions(largeur_mm: float, hauteur_mm: float, forme: str) -> str:
    a, b = largeur_mm / 1000, hauteur_mm / 1000
    if forme.startswith("3.87"):
        return f"{a:.2f} x {b:.2f} m"
    return f"{_nombre(a, 2)} m × {_nombre(b, 2)} m"


def format_surface(metres_carres: float, l: Lot2, parentheses: bool = False) -> str:
    texte = f"{_nombre(metres_carres, l.surface_decimales, l.surface_point)} m²"
    return f"({texte})" if parentheses else texte


def tronquer(police, nom: str, place: float) -> str:
    """fr-076 : « Plac… », « Local… » quand le nom ne tient pas."""
    if police.getlength(nom) <= place:
        return nom
    while len(nom) > 1 and police.getlength(nom + "…") > place:
        nom = nom[:-1]
    return nom.rstrip() + "…"


def _ecrire(d, xy, texte: str, taille: int, couleur, gras: bool = False) -> None:
    d.texte(xy, texte, taille, couleur)
    if gras and taille >= 11:  # aucune police grasse disponible : deux passages décalés d'un pixel font le gras
        d.texte((xy[0] + 1, xy[1]), texte, taille, couleur)


def noms(d) -> None:
    """Remplace _Dessin.noms sous --lot2 : nom, dimensions, surface, HSP et sol, dans cet ordre, selon la place."""
    st, l, v = d.style, d.style.lot2, d.style.variete
    s = d.rep.s
    t0 = st.taille_texte
    couleur = v.couleur_noms if v is not None and v.couleur_noms else st.textes
    gris = l.couleur_surface if l.couleur_surface is not None else tuple(min(c + 60, 150) for c in couleur)
    if l.etiquettes == "surface":  # fr-063 : dans son cadre, la surface est écrite foncée
        gris = couleur
    petit = max(8, t0 - 2)
    plus_petit = max(8, round(t0 * 0.75))
    entre_parentheses = l.parentheses_grises or (v is not None and v.parentheses)
    for p in d.niv.pieces:
        r = p.rect
        cx, cy = d.px((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        place = r.largeur * s * 0.9
        lignes = []  # (priorité, texte, taille, couleur, gras, sorte)
        nom = p.nom.upper() if l.majuscules or (v is not None and v.majuscules) else p.nom
        t = t0
        if st.noms:
            if l.noms_tronques:
                nom = tronquer(_police(st.police, t0), nom, place)
            else:
                if l.noms_courts and _police(st.police, t0).getlength(nom) > place:
                    nom = ABREVIATIONS.get(p.nom, nom)
                while t > 9 and _police(st.police, t).getlength(nom) > place:
                    t -= 1
            lignes.append((0, nom, t, couleur, l.noms_gras, "nom"))
        if st.surfaces and not l.noms_courts:
            surface = format_surface(surface_piece(p) / 1e6, l, entre_parentheses)
            dims = format_dimensions(r.largeur, r.hauteur, l.format_dimensions) if l.dimensions else ""
            if dims and _police(st.police, plus_petit).getlength(dims) > r.largeur * s * 0.95:
                dims = ""  # trop large pour la pièce : il déborderait sur le mur
            if dims:
                lignes.append((1, dims, plus_petit, gris, False, "mesure"))
            if not dims or l.dimensions == "ajoute":
                lignes.append((2, surface, plus_petit if dims else petit, gris, False, "mesure"))
        # Ces deux tirages ne dépendent pas de la place : plan et plan_sans_mobilier écrivent pareil.
        sol = d.hasard_lot2.choice(SOLS_ECRITS.get(p.sorte) or ("",)) if l.mention_sol else ""
        if l.hsp and p.sorte not in ("placard", "escalier"):
            lignes.append((3, _texte_hsp(d, l), plus_petit, gris, False, "cercle" if l.hsp == "HSP cercle" else "hsp"))
        if sol:
            mention = f"sol {sol}"
            lignes.append((4, f"({mention})" if l.mention_sol == "(sol)" else mention, plus_petit, gris, False, "sol"))
        _poser_lignes(d, p, lignes, cx, cy)


def _texte_hsp(d, l: Lot2) -> str:
    h = d.niv.hsp / 1000
    if l.hsp == "hsp:":
        return f"hsp: {h:.2f}"
    if l.hsp == "HsP :":
        return f"HsP : {h:.2f} m"
    return f"{h:.2f}"  # dans le cercle, sous « HSP »


def _hauteur_ligne(ligne: tuple) -> float:
    return ligne[2] * (3.4 if ligne[5] == "cercle" else 1.25)


def _poser_lignes(d, p, lignes: list[tuple], cx: float, cy: float) -> None:
    """Écrit ce qui tient dans la hauteur de la pièce, par priorité, centré sur la pièce."""
    st, l = d.style, d.style.lot2
    s = d.rep.s
    r = p.rect
    dispo = r.hauteur * s * 0.95
    gardees, total = [], 0.0
    for ligne in sorted(lignes, key=lambda x: x[0]):
        h = _hauteur_ligne(ligne)
        if gardees and total + h > dispo:
            continue
        gardees.append(ligne)
        total += h
    if not gardees:
        return
    gardees.sort(key=lambda x: x[0])
    if l.etiquettes:
        _etiquette(d, p, gardees, cx, cy, total)
    y = cy - total / 2
    for _, texte, taille, couleur, gras, sorte in gardees:
        h = _hauteur_ligne((0, texte, taille, couleur, gras, sorte))
        if sorte == "cercle":
            _cercle_hsp(d, cx, y + h / 2, texte, taille, couleur)
        else:
            _ecrire(d, (cx, y + h / 2), texte, taille, couleur, gras)
        y += h


def _cercle_hsp(d, cx: float, cy: float, valeur: str, taille: int, couleur) -> None:
    """fr-105 : « HSP 2.50 » dans un cercle."""
    rayon = taille * 1.55
    d.d.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), outline=couleur, width=1)
    d.texte((cx, cy - taille * 0.55), "HSP", taille, couleur)
    d.texte((cx, cy + taille * 0.55), valeur, taille, couleur)


def _etiquette(d, p, lignes: list[tuple], cx: float, cy: float, total: float) -> None:
    """Le cadre du trait 2. Seulement s'il tient dans une pièce à contour droit : posé sur un mur, un cadre
    opaque ferait apprendre un mur invisible (une pièce en biais a une boîte qui déborde de son contour)."""
    st, l = d.style, d.style.lot2
    if p.contour:
        return
    s = d.rep.s
    r = p.rect
    pad = max(3, round(st.taille_texte * 0.3))
    largeur = max(_police(st.police, ligne[2]).getlength(ligne[1]) for ligne in lignes) + 2 * pad
    if largeur > r.largeur * s * 0.85 or total + 2 * pad > r.hauteur * s * 0.85:
        return
    if l.etiquettes == "surface":  # fr-063 : le cadre n'entoure que la surface, sous le nom
        y = cy - total / 2
        for ligne in lignes:
            h = _hauteur_ligne(ligne)
            if ligne[5] == "mesure":
                l_mes = _police(st.police, ligne[2]).getlength(ligne[1]) + 2 * pad
                d.d.rectangle((cx - l_mes / 2, y - 2, cx + l_mes / 2, y + h + 2), fill=l.couleur_etiquette, outline=(110, 110, 110))
            y += h
        return
    d.d.rounded_rectangle((cx - largeur / 2, cy - total / 2 - pad, cx + largeur / 2, cy + total / 2 + pad), radius=pad,
                          fill=l.couleur_etiquette, outline=(130, 130, 130), width=1)


# ---------------------------------------------------------------- murs et ouvertures


def variete_des_murs(style) -> Variete | None:
    """La variété qui dessine les murs. Sans --styles-monde, une variété locale suffit : V.mur est pure."""
    if style.variete is not None:
        return style.variete
    if style.lot2.murs_dessin:
        return Variete(murs=style.lot2.murs_dessin, epaisseur_trait_mur=style.lot2.epaisseur_trait_mur)
    return None


def couleur_ouverture(style, o):
    """De quoi remplir le trou d'une ouverture dans le mur. La classe de l'ouverture, elle, ne change pas."""
    l = style.lot2
    if o.type == "porte":
        return (255, 255, 255) if l.portes_boites else style.fond
    return l.couleur_fenetres if l.fenetres_pleines else style.fond


def ouverture_en_boite(d, o) -> bool:
    """Dessine l'ouverture en rectangle cerné (fr-023, fr-035, fr-098). Faux : à l'appelant de la dessiner."""
    l = d.style.lot2
    if (o.type != "porte" and not l.fenetres_pleines) or (o.type == "porte" and not l.portes_boites):
        return False
    r = rect_de_l_ouverture(o)
    contour = d.rect_px(r)
    couleur = l.contour_fenetres if o.type != "porte" else d.style.murs
    d.d.polygon(contour, outline=couleur, width=max(1, d.fin))
    return True


def remplir_meuble(d, m, pts) -> None:
    """Fond clair d'un équipement : le trait, lui, reste dessiné par _Dessin.meuble."""
    if m.forme == "ellipse":
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        d.d.ellipse((min(xs), min(ys), max(xs), max(ys)), fill=(232, 234, 242))
    elif m.forme != "marches":
        d.d.polygon(pts, fill=(232, 234, 242))


# ---------------------------------------------------------------- ce qui se dessine à la fin


def apres_tout(d, rng: random.Random) -> None:
    """Appelé à la fin de _Dessin.tout : par-dessus le plan et dans les marges réservées."""
    st, l = d.style, d.style.lot2
    if l.triangles:
        triangles(d)
    if st.cotes and l.cotes_interieures_rouges and l.couleur_cotes is not None:
        cotes_interieures_rouges(d, rng)
    if st.cotes and l.echelle_ecrite:
        echelle_ecrite(d)
    if l.rose_des_vents:
        rose_des_vents(d, rng)
    if l.legende_niveau:
        legende_niveau(d)
    if l.surface_totale and st.surfaces:
        surface_totale(d)
    if l.tableau and st.surfaces:
        tableau(d)


def triangles(d) -> None:
    """Les petits repères de fr-098 : pointe vers le mur, au milieu de chaque côté de la pièce."""
    c = max(4, round(d.style.taille_texte * 0.3))
    couleur = d.style.murs
    for p in d.niv.pieces:
        if p.contour or min(p.rect.largeur, p.rect.hauteur) * d.rep.s < 4 * c:
            continue
        r = p.rect
        x0, y1 = d.px(r.x0, r.y0)
        x1, y0 = d.px(r.x1, r.y1)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        d.d.polygon([(mx, y0), (mx - c, y0 + c), (mx + c, y0 + c)], fill=couleur)
        d.d.polygon([(mx, y1), (mx - c, y1 - c), (mx + c, y1 - c)], fill=couleur)
        d.d.polygon([(x0, my), (x0 + c, my - c), (x0 + c, my + c)], fill=couleur)
        d.d.polygon([(x1, my), (x1 - c, my - c), (x1 - c, my + c)], fill=couleur)


def cotes_interieures_rouges(d, rng: random.Random) -> None:
    """fr-031 : des chaînes rouges en travers des pièces, flèches aux bouts. La longueur écrite est la vraie."""
    l = d.style.lot2
    couleur = l.couleur_cotes
    taille = max(9, round(d.style.taille_texte * 0.75))
    for p in d.niv.pieces:
        if p.contour:
            continue
        r = p.rect
        if r.largeur > 1000:
            # Près d'un bord : le centre est pour le nom de la pièce.
            y = r.y0 + r.hauteur * rng.choice((rng.uniform(0.1, 0.25), rng.uniform(0.75, 0.9)))
            a, b = d.px(r.x0, y), d.px(r.x1, y)
            _ligne_cotee(d, a, b, True, _nombre(r.largeur / 1000, 2, l.cote_point), taille, couleur)
        if r.hauteur > 1000:
            x = r.x0 + r.largeur * rng.choice((rng.uniform(0.1, 0.25), rng.uniform(0.75, 0.9)))
            a, b = d.px(x, r.y0), d.px(x, r.y1)
            _ligne_cotee(d, a, b, False, _nombre(r.hauteur / 1000, 2, l.cote_point), taille, couleur)


def _ligne_cotee(d, a, b, horizontale: bool, texte: str, taille: int, couleur) -> None:
    d.d.line((a, b), fill=couleur, width=1)
    f = 7
    if horizontale:
        g, e = (a, b) if a[0] < b[0] else (b, a)
        d.d.polygon([g, (g[0] + f, g[1] - f / 2), (g[0] + f, g[1] + f / 2)], fill=couleur)
        d.d.polygon([e, (e[0] - f, e[1] - f / 2), (e[0] - f, e[1] + f / 2)], fill=couleur)
        d.texte(((a[0] + b[0]) / 2, a[1] - taille * 0.75), texte, taille, couleur)
    else:
        h, e = (a, b) if a[1] < b[1] else (b, a)
        d.d.polygon([h, (h[0] - f / 2, h[1] + f), (h[0] + f / 2, h[1] + f)], fill=couleur)
        d.d.polygon([e, (e[0] - f / 2, e[1] - f), (e[0] + f / 2, e[1] - f)], fill=couleur)
        d.texte((a[0] - taille * 0.75, (a[1] + b[1]) / 2), texte, taille, couleur, vertical=True)


def echelle_ecrite(d) -> None:
    """fr-031 : l'échelle écrite en haut de page. Décoration : le lecteur ignore « 1/50 » sur une image."""
    st = d.style
    d.texte((d.rep.largeur0 / 2, d.px(0, d.rep.ymax)[1] - RECUL_COTE - 3.2 * st.taille_texte), st.lot2.echelle_ecrite,
            round(st.taille_texte * 1.15), st.textes)


def rose_des_vents(d, rng: random.Random) -> None:
    """fr-075, fr-096 : une petite étoile à huit branches en bas à gauche, lettres tournées selon le plan."""
    st = d.style
    t = st.taille_texte
    r = 1.5 * t
    cx, cy = r + 0.9 * t + 12, d.rep.hauteur0 - r - 0.9 * t - 12
    couleur = st.textes
    for k in range(8):
        a = math.radians(45 * k)
        long_ = r if k % 2 == 0 else r * 0.55
        pointe = (cx + long_ * math.sin(a), cy - long_ * math.cos(a))
        cotes = [(cx + r * 0.14 * math.sin(a + s), cy - r * 0.14 * math.cos(a + s)) for s in (math.pi / 2, -math.pi / 2)]
        d.d.polygon([pointe, cotes[0], cotes[1]], outline=couleur)
    lettres = rng.choice((("N", "E", "S", "O"), ("N", "E", "S", "W"), ("E", "S", "W", "N"), ("W", "N", "E", "S"), ("S", "W", "N", "E")))
    taille = max(8, round(t * 0.6))
    for k, lettre in enumerate(lettres):
        a = math.radians(90 * k)
        d.texte((cx + (r + taille * 0.8) * math.sin(a), cy - (r + taille * 0.8) * math.cos(a)), lettre, taille, couleur)


def legende_niveau(d) -> None:
    """« Niveau 0 » sous le plan, petit et gras (fr-075, fr-096)."""
    st = d.style
    x = (d.px(d.rep.xmin, 0)[0] + d.px(d.rep.xmax, 0)[0]) / 2
    y = d.px(0, d.rep.ymin)[1] + 2.2 * st.taille_texte
    _ecrire(d, (x, y), f"Niveau {d.niv.index}", max(9, round(st.taille_texte * 0.65)), st.textes, gras=True)


def surface_totale(d) -> None:
    """La colonne de droite de fr-094, fr-096 : « Surface totale approximative », séparée par un filet."""
    st, l = d.style, d.style.lot2
    t = st.taille_texte
    x = d.rep.largeur0 - _largeur_colonne_surface(st) - 1.5 * t
    d.d.line(((x, 0), (x, d.rep.hauteur0)), fill=(226, 226, 226), width=1)
    cx = (x + d.rep.largeur0) / 2
    y = d.rep.hauteur0 * 0.3
    total = sum(surface_piece(p) for p in d.log.pieces) / 1e6
    _ecrire(d, (cx, y), "Surface totale approximative", max(8, round(t * 0.65)), st.textes, gras=True)
    d.texte((cx, y + t * 1.1), format_surface(total, l), max(8, round(t * 0.65)), l.couleur_surface or st.textes)


def tableau(d) -> None:
    """Trait 5 : les surfaces hors du plan. Elles viennent des pièces dessinées : la somme est juste, et le
    lecteur d'échelle, qui sait lire une légende de surfaces, n'y trouve que des valeurs vraies."""
    st, l = d.style, d.style.lot2
    lignes = [(f"{l.tableau_prefixe}{p.nom}", _nombre(surface_piece(p) / 1e6, l.tableau_decimales)) for p in d.niv.pieces]
    total = _nombre(sum(surface_piece(p) for p in d.niv.pieces) / 1e6, l.tableau_decimales)
    if l.tableau == "bas":
        _tableau_bas(d, lignes, total)
    else:
        _tableau_cote(d, lignes, total)


def _tableau_cote(d, lignes: list[tuple[str, str]], total: str) -> None:
    """Une colonne à côté du plan (fr-074). Tronquée à la hauteur de la page : elle ne déborde jamais."""
    st, l = d.style, d.style.lot2
    taille = _taille_tableau(st)
    pas = taille * 1.5
    couleur = l.tableau_couleur or st.textes
    police = _police(st.police, taille)
    largeur = max(police.getlength(n) for n, _ in lignes) + max(police.getlength(v) for _, v in lignes) + 2 * taille
    largeur = max(largeur, police.getlength(f"TOTAL {total} m²") + taille)
    if l.tableau == "droite":
        x0 = d.px(d.rep.xmax, 0)[0] + _debut_tableau(st)
    else:
        x0 = d.px(d.rep.xmin, 0)[0] - _debut_tableau(st) - largeur
    y = max(10.0, d.px(0, d.rep.ymax)[1])
    y_haut = y
    n_max = max(1, int((d.rep.hauteur0 - y - 2.2 * pas) // pas))
    for nom, valeur in lignes[:n_max]:
        d.texte((x0 + taille * 0.4, y + pas / 2), nom, taille, couleur, ancre="lm")
        d.texte((x0 + largeur - taille * 0.4, y + pas / 2), valeur, taille, couleur, ancre="rm")
        y += pas
        if l.tableau_bordures:
            d.d.line(((x0, y), (x0 + largeur, y)), fill=couleur, width=1)
    if not l.tableau_bordures:
        d.d.line(((x0 + largeur * 0.55, y + 2), (x0 + largeur, y + 2)), fill=couleur, width=1)
    y += pas * 0.4
    _ecrire(d, (x0 + taille * 0.4 + police.getlength(f"TOTAL {total} m²") / 2, y + pas / 2), f"TOTAL {total} m²", taille, couleur, gras=True)
    if l.tableau_bordures:
        d.d.rectangle((x0, y_haut, x0 + largeur, y + pas), outline=couleur, width=1)


def _tableau_bas(d, lignes: list[tuple[str, str]], total: str) -> None:
    """Un tableau sous le plan (fr-093) : un en-tête, une ligne par pièce, le total en gras dessous."""
    st, l = d.style, d.style.lot2
    taille = _taille_tableau(st)
    pas = taille * 1.5
    couleur = l.tableau_couleur or st.textes
    police = _police(st.police, taille)
    en_tete = "Parties de l'immeuble bâties visitées"
    en_tete_val = "Superficie Carrez"
    if police.getlength(en_tete) > d.rep.largeur0 * 0.55:
        en_tete, en_tete_val = "Pièce", "Surface"
    col1 = max([police.getlength(n) for n, _ in lignes] + [police.getlength(en_tete)]) + taille
    col2 = max([police.getlength(v) for _, v in lignes] + [police.getlength(en_tete_val)]) + taille
    largeur = min(col1 + col2, d.rep.largeur0 - 20)
    x0 = max(10.0, (d.px(d.rep.xmin, 0)[0] + d.px(d.rep.xmax, 0)[0]) / 2 - largeur / 2)
    if x0 + largeur > d.rep.largeur0 - 10:
        x0 = d.rep.largeur0 - 10 - largeur
    y = d.px(0, d.rep.ymin)[1] + _debut_tableau(st)
    y_haut = y
    xc = x0 + largeur - col2
    n_max = max(1, int((d.rep.hauteur0 - y - 3 * pas) // pas) - 1)
    _ecrire(d, (x0 + largeur - col2 - col1 / 2, y + pas / 2), en_tete, taille, couleur, gras=True)
    _ecrire(d, (xc + col2 / 2, y + pas / 2), en_tete_val, taille, couleur, gras=True)
    y += pas
    if l.tableau_bordures:
        d.d.line(((x0, y), (x0 + largeur, y)), fill=couleur, width=1)
    for nom, valeur in lignes[:n_max]:
        d.texte((x0 + taille * 0.4, y + pas / 2), nom, taille, couleur, ancre="lm")
        d.texte((xc + col2 / 2, y + pas / 2), valeur, taille, couleur)
        y += pas
        if l.tableau_bordures:
            d.d.line(((x0, y), (x0 + largeur, y)), fill=couleur, width=1)
    if l.tableau_bordures:
        d.d.rectangle((x0, y_haut, x0 + largeur, y), outline=couleur, width=1)
        d.d.line(((xc, y_haut), (xc, y)), fill=couleur, width=1)
    ligne = f"Surface loi Carrez totale : {total} m²" if l.tableau_bordures else f"TOTAL {total} m²"
    _ecrire(d, (x0 + largeur / 2, y + pas * 0.9), ligne, taille, couleur, gras=True)
