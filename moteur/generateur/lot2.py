"""Le lot 2 du générateur (option --lot2) : les styles vus sur les 103 vrais plans reçus.

Pourquoi : Atelya rate les styles jamais vus. Ce module apprend au générateur à les dessiner, pour que
l'essai 8 les apprenne sur des plans dont la vérité est exacte. Les traits sont ceux de
docs/projet/etapes/catalogue-styles-lot2.md ; ce qui est dessiné ici imite des plans d'ENTRAÎNEMENT
(ceux qu'ils citent : fr-075, fr-094, fr-096, fr-098, fr-108, fr-110, fr-106, fr-041, fr-062, fr-100, fr-102,
fr-070, fr-036, fr-037, fr-111, fr-086, fr-112, fr-059, fr-080, fr-093, fr-120, fr-048, fr-084, fr-055, fr-024, fr-040, fr-025,
fr-072, fr-118, fr-119…), jamais un plan d'examen.

Trois choses séparées, comme le lot 1 (variete.py) :

- le tirage (`lot2_au_hasard`) : un hasard à part, tout est rangé dans un `Lot2` ; sans l'option, aucun
  hasard existant n'est consommé et le dessin reste celui de la version précédente ;
- la recopie (`appliquer`) : sans aucun hasard, le `Lot2` est recopié dans les champs du `Style` ;
- le dessin : des fonctions qui reçoivent le `_Dessin` et ne touchent QUE son image. Jamais les masques :
  une étiquette, un tableau ou une cote reste du fond, une fenêtre bleue reste une fenêtre.

Les traits 12 et 13 (plusieurs niveaux, deux logements sur une image) ne sont pas un simple dessin : `composer` fabrique un
logement assemblé à UN seul niveau, que l'exportateur écrit comme un vrai exemple sœur `{ident}-ensemble/`. La vérité y reste
tramée depuis les polygones, le vide entre les blocs et le palier sont du fond, comme tout ce qui est hors du logement.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import random
from dataclasses import dataclass, field, fields

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from moteur.dessin_plan import _police
from moteur.generateur.annotations import rect_de_l_ouverture, rect_du_mur
from moteur.generateur.logements import LogementGenere, Niveau, Rect, _nommer, _transformer, surface_piece
from moteur.generateur.mobilier import Meuble, _libre, _rect, _zones_de_battement
from moteur.generateur.variete import Variete

RECUL_COTE = 60  # le même que rendu.RECUL_COTE (rendu importe ce module, pas l'inverse ; un test vérifie l'égalité)

# Les familles du catalogue et leurs poids (leurs fréquences sur 103 plans).
FAMILLES_LOT2 = ("agence_coloree", "promoteur_gris", "murs_noirs", "carrez_legende", "logiciel_public", "scan_ancien",
                 "cotes_rouges", "neutre")
POIDS_FAMILLES = {"agence_coloree": 14, "promoteur_gris": 14, "murs_noirs": 13, "carrez_legende": 8, "logiciel_public": 5,
                  "scan_ancien": 6, "cotes_rouges": 2, "neutre": 10}

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
    # Trait 6 : les logiciels grand public colorient les pièces, pas la page (fr-100, fr-102, fr-103 ; fr-070 en lilas).
    "creme": {**{s: (253, 248, 228) for s in _SORTES}, "placard": (196, 196, 196)},
    "lilas": {**{s: (244, 244, 252) for s in _SORTES}, "sdb": (232, 240, 250), "sde": (232, 240, 250), "wc": (232, 240, 250)},
    "gris_clair": {s: (234, 236, 236) for s in _SORTES},  # fr-041 : pièces gris clair, murs ardoise
    # fr-062 : le seul promoteur en couleurs franches, cuisine comprise.
    "promoteur_vif": {"sejour": (190, 220, 245), "principale": (190, 220, 245), "cuisine": (86, 145, 205), "chambre": (250, 205, 150),
                      "bureau": (250, 205, 150), "sdb": (90, 175, 230), "sde": (90, 175, 230), "wc": (90, 175, 230),
                      "entree": (190, 230, 190), "degagement": (190, 230, 190), "placard": (250, 250, 250),
                      "buanderie": (190, 230, 190), "escalier": (220, 220, 220)},
}

# Ce qui reste dessiné d'un plan d'agence sans « mobilier » (fr-075) : les équipements fixes, jamais lits ni canapés.
MEUBLES_FIXES = {"baignoire", "douche", "lavabo", "wc", "plan_de_travail", "lave_linge", "escalier"}

ABREVIATIONS = {"Dégagement": "Dgt", "Rangement": "Rgt", "Salle de bains": "SdB", "Salle de bain": "SdB", "Salle d'eau": "SdE",
                "Chambre": "Ch.", "Placard": "Pl.", "Cuisine": "Cuis.", "Toilettes": "WC", "Pièce principale": "Pièce"}
# Ce qui s'écrit à côté d'une fenêtre sur les plans de promoteur (fr-041, fr-108, fr-110) : volet roulant, porte-fenêtre.
MENTIONS = {"fenetre": "VR", "porte_fenetre": "PF"}
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
    format_dimensions: str = "3,05 m × 2,85 m"  # ou « 3.87 x 4.65 m », « 2.70×4.33 » (fr-037)
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
    barre_echelle: bool = False  # fr-070, fr-112 : la seule échelle du plan est une barre
    # ---- traits 3, 6, 9 : les cotes (une seule unité par plan, le lecteur n'admet les entiers que sans cote « d,dd »)
    unite_cotes: str = "m"  # m ou cm
    cotes_interieures: bool = False  # trait 3 : un trait de cote de mur à mur dans chaque pièce
    cotes_par_mur: bool = False  # trait 6 : une cote le long de chaque mur de chaque pièce
    sans_chaines: bool = False  # pas de chaîne autour du plan : les cotes sont dans les pièces (fr-108, fr-100)
    taille_cotes: float = 0.7  # part de la taille du texte
    # ---- trait 3 : promoteur
    cercles_pmr: bool = False
    sols: dict[str, str] = field(default_factory=dict)  # sorte de pièce → motif (V.sol)
    couleur_sol: tuple[int, int, int] = (205, 205, 205)
    pas_sol: float = 0.2
    numero_lot: str = ""  # « 45 », « A1 14 », « Lot 206 », « {type} G206 » (écrit avec la surface totale)
    abreviations: bool = False
    mentions_menuiseries: bool = False
    # ---- trait 18 (et balcons du 4) : extérieurs. Chaque dict : sorte, cote, part, position, profondeur_m, motif, contour, couleur
    exterieurs: list[dict] = field(default_factory=list)
    # ---- trait 7
    textes_verticaux: str = ""  # "", etroites (pièces où le nom ne tient pas à plat), toutes (fr-055)
    # ---- trait 9 : scan ancien. Seule cette famille pose sa page : voir _page_sage
    papier: int | None = None
    contraste: float | None = None
    salissure: str | None = None
    rotation: float | None = None
    teinte: tuple[float, float, float] | None = None
    # ---- trait 11
    manuscrit: str = ""  # "", surfaces (mesures au stylo), tout (les noms aussi)
    couleur_stylo: tuple[int, int, int] = (20, 20, 20)
    souligne: bool = False  # fr-112 : les noms à la main sont soulignés
    # ---- trait 15, 17, 14
    placards_fleches: bool = False
    escalier: str = ""  # "", colimacon, fleche_acces
    pastilles: str = ""  # "", avec_noms (fr-059), legende (le nom est dans une légende à droite)
    # ---- trait 10 : une page photographiée, vue à l'écran (fr-024, fr-040, fr-086)
    ecran: bool = False
    ecran_si_photo: bool = False  # sous --photo-realiste, l'écran prend la place de la table plus souvent : voir _tirer_ecran
    ecran_bordure: bool = False  # le bord noir de l'écran dans les marges (sans --photo-realiste)
    # ---- traits 12, 13 : tirés pour tout plan ; la composition elle-même remplit le reste (voir composer)
    composition: str = ""  # "", niveaux, deux_logements
    disposition: str = ""  # niveaux : empiles, cote_a_cote ; deux_logements : palier, mitoyen
    blocs: list[dict] = field(default_factory=list)  # titre, cadre (mm), pieces, surface, coins
    palier: dict | None = None  # cadre (mm) et texte du vide entre deux logements
    titres_place: str = ""  # "", haut, bas
    titre_tirets: bool = False  # fr-025, fr-072 : « ----- 1er étage ----- »
    titre_surface: bool = False  # fr-120 : « ETAGE 62 m² »
    filet: bool = False  # fr-072 : un trait qui sépare les deux niveaux


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
    elif famille == "promoteur_gris":
        _tirer_promoteur(l, rng)
    elif famille == "logiciel_public":
        _tirer_logiciel(l, rng)
    elif famille == "scan_ancien":
        _tirer_scan(l, rng)
    if transversaux:
        _tirer_transversaux(l, rng)
        _tirer_exterieurs(l, rng)
        # En dernier : ces tirages ne déplacent aucun de ceux d'au-dessus.
        _tirer_composition(l, rng)
        _tirer_ecran(l, rng)
    _accorder(l)
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


def _tirer_promoteur(l: Lot2, rng: random.Random) -> None:
    """Trait 3, plans de vente du neuf. Il n'y a pas « un » promoteur gris, d'où cinq manières de dessiner les murs."""
    forme = rng.choices(("noir", "gris", "double", "ardoise", "vif"), weights=(3, 3, 3, 2, 1))[0]
    trait = _gris(rng, 110, 150)
    if forme == "noir":  # fr-108
        l.couleur_murs = _gris(rng, 0, 20)
    elif forme == "gris":  # le catalogue, fr-109 : tout en gris moyen
        l.couleur_murs = _gris(rng, 105, 150)
    elif forme == "double":  # fr-106, fr-110 : les murs ne sont que leurs deux bords
        l.couleur_murs = _gris(rng, 40, 90)
        l.murs_dessin, l.epaisseur_trait_mur = "double", rng.uniform(0.08, 0.18)
    elif forme == "ardoise":  # fr-041
        g = rng.randint(55, 80)
        l.couleur_murs, l.palette = (g, g + 8, g + 12), "gris_clair"
        trait = _gris(rng, 50, 80)
    else:  # fr-062
        l.couleur_murs, l.palette = _gris(rng, 0, 20), "promoteur_vif"
        trait = _gris(rng, 40, 70)
    l.couleur_traits = trait
    l.couleur_textes = _gris(rng, 15, 60)
    l.couleur_fond = (255, 255, 255)
    l.px_par_m = rng.randint(85, 125)
    l.part_texte = rng.uniform(0.13, 0.17)
    l.epaisseur_trait = rng.uniform(0.008, 0.012)
    l.marges = (rng.randint(100, 170), rng.randint(100, 170), rng.randint(100, 170), rng.randint(100, 170))
    l.unite_cotes = "cm" if rng.random() < 0.8 else "m"  # fr-041 cote en mètres, avec un point
    l.cote_point = l.unite_cotes == "m"
    l.cotes_interieures = True
    l.sans_chaines = rng.random() < 0.7  # fr-108, fr-110 : aucune chaîne autour du plan
    l.cercles_pmr = rng.random() < 0.8
    l.sans_mobilier = rng.random() < 0.15
    if rng.random() < 0.35:
        for sorte in rng.sample(("sejour", "principale", "chambre", "bureau", "cuisine"), rng.randint(1, 3)):
            l.sols[sorte] = rng.choice(("parquet", "hachures"))
        l.couleur_sol = _gris(rng, 185, 220)  # assez clair pour ne pas devenir un mur sur l'image grise réduite
        l.pas_sol = rng.uniform(0.12, 0.3)
    if rng.random() < 0.6:
        l.numero_lot = rng.choice((str(rng.randint(11, 98)), f"A{rng.randint(1, 4)} {rng.randint(10, 60)}",
                                   f"Lot {rng.randint(100, 299)}", "{type} G" + str(rng.randint(100, 299))))
    l.abreviations = rng.random() < 0.6
    l.majuscules = rng.random() < 0.3
    l.mentions_menuiseries = rng.random() < 0.6
    l.noms_gras = rng.random() < 0.5
    l.noms_courts = rng.random() < 0.35
    l.vantail_fin = True
    l.arcs_pointilles = rng.random() < 0.2
    l.taille_cotes = rng.uniform(0.62, 0.8)


def _tirer_logiciel(l: Lot2, rng: random.Random) -> None:
    """Trait 6 : Kozikaza, HomeByMe, magicplan. Page blanche et pièces crème (fr-100, fr-102, fr-103) ou lilas (fr-070)."""
    if rng.random() < 0.75:
        l.palette = "creme"
        l.couleur_murs = _gris(rng, 140, 175)  # à 60 niveaux au moins du crème : le mur reste visible en gris
        l.couleur_cotes = _gris(rng, 95, 125)
    else:
        g = rng.randint(66, 84)
        l.palette, l.couleur_murs = "lilas", (g, g + 2, g + 30)
        l.couleur_cotes = (rng.randint(140, 165), rng.randint(140, 165), rng.randint(205, 225))
    l.couleur_fond = (255, 255, 255)
    l.couleur_traits = _gris(rng, 120, 165)
    l.couleur_textes = _gris(rng, 15, 40)
    l.couleur_surface = l.couleur_textes
    l.px_par_m = rng.randint(90, 125)
    l.part_texte = rng.uniform(0.14, 0.19)
    l.marges = (rng.randint(30, 110), rng.randint(30, 110), rng.randint(30, 110), rng.randint(30, 110))
    l.cotes_par_mur = l.sans_chaines = True
    l.taille_cotes = rng.uniform(0.6, 0.95)  # fr-100 écrit petit, fr-102 presque aussi gros que les noms
    l.textes_verticaux = "etroites" if rng.random() < 0.5 else ""
    l.sans_mobilier = rng.random() < 0.4  # fr-100, fr-102 : rien ; fr-103, fr-070 : meubles dessinés
    l.mobilier_couleur = not l.sans_mobilier
    l.fenetres_pleines = True  # fenêtres blanches cernées de gris, jamais de traits dans le mur
    l.couleur_fenetres, l.contour_fenetres = (255, 255, 255), _gris(rng, 120, 165)
    l.vantail_fin = True
    l.barre_echelle = rng.random() < 0.2  # fr-070


def _tirer_scan(l: Lot2, rng: random.Random) -> None:
    """Trait 9 : promoteur des années 80-2000. fr-036 (bleuté, cotes en cm, terrasse carrelée), fr-037, fr-111 (photocopie,
    surfaces en légende, dimensions dans les pièces). Une page sur deux reste blanche : fr-037, fr-111 le sont."""
    if rng.random() < 0.5:
        l.papier = rng.randint(215, 240)
        l.contraste = rng.uniform(0.8, 0.95)
        if rng.random() < 0.65:
            l.teinte = (rng.uniform(0.86, 0.94), rng.uniform(0.9, 0.97), 1.0)
        else:
            l.teinte = (1.0, rng.uniform(0.95, 0.98), rng.uniform(0.86, 0.92))
        l.salissure = rng.choices(("grain", "jpeg", "photocopie", "taches"), weights=(3, 1, 3, 1))[0]
    else:
        l.papier = rng.randint(245, 255)
        l.contraste = rng.uniform(0.95, 1.0)
        l.salissure = rng.choices(("grain", "jpeg"), weights=(5, 3))[0]  # le blanc d'une photocopie vaut 205 à 235 : pas ici
    l.sortie_jpeg = True
    if rng.random() < 0.3:  # la plupart des scans vus sont droits : fr-036, fr-037, fr-111
        l.rotation = rng.choice((-1, 1)) * rng.uniform(0.3, 1.5)
    l.couleur_murs = _gris(rng, 15, 60)
    l.couleur_traits = _gris(rng, 25, 70)
    l.couleur_textes = _gris(rng, 15, 50)
    l.couleur_fond = (255, 255, 255)
    l.px_par_m = rng.randint(80, 120)
    l.part_texte = rng.uniform(0.15, 0.2)
    l.epaisseur_trait = rng.uniform(0.01, 0.016)
    l.marges = (rng.randint(70, 150), rng.randint(70, 150), rng.randint(70, 150), rng.randint(70, 150))
    l.murs_dessin = rng.choices(("double", "hachure", ""), weights=(4, 3, 3))[0]
    l.epaisseur_trait_mur = rng.uniform(0.08, 0.2)
    l.majuscules = rng.random() < 0.6
    if rng.random() < 0.65:  # fr-036 : 409, 386, 423
        l.unite_cotes = "cm"
        l.cotes_interieures = True
        l.sans_chaines = rng.random() < 0.6
        l.noms_courts = True
    else:  # fr-037 : « 2.70×4.33 » dans la pièce, surfaces en légende
        l.dimensions = "remplace"
        l.format_dimensions = "2.70×4.33"
        l.sans_chaines = True
        if rng.random() < 0.7:
            l.tableau, l.tableau_decimales = rng.choice(("gauche", "droite")), 2
        l.barre_echelle = rng.random() < 0.25  # fr-112
    l.mobilier_fixes = rng.random() < 0.6
    l.cercles_pmr = rng.random() < 0.25  # fr-036
    if rng.random() < 1 / 3:  # fr-078 : « sol : parquet » à la main ; fr-112 : les noms aussi
        l.manuscrit = "surfaces" if rng.random() < 0.7 else "tout"
        _tirer_stylo(l, rng)


def _tirer_stylo(l: Lot2, rng: random.Random) -> None:
    l.couleur_stylo = (rng.randint(25, 60), rng.randint(40, 85), rng.randint(120, 175)) if rng.random() < 0.4 else _gris(rng, 10, 40)
    l.souligne = l.manuscrit == "tout" and rng.random() < 0.5


def _tirer_exterieurs(l: Lot2, rng: random.Random) -> None:
    """Trait 18 et balcons du trait 4. Un extérieur reste du fond (le générateur n'a pas de classe extérieur) : il ne se pose
    que dans une marge libre, en bas ou à droite, jamais là où passent déjà un tableau, une rose ou une colonne."""
    proba = {"murs_noirs": 0.35, "promoteur_gris": 0.35, "logiciel_public": 0.5, "scan_ancien": 0.4}.get(l.famille, 0.1)
    if l.recadre or l.triangles or rng.random() >= proba:
        return
    cotes = []
    if not (l.tableau == "bas" or l.legende_niveau or l.rose_des_vents):
        cotes.append("bas")
    if not (l.tableau == "droite" or l.surface_totale or l.pastilles == "legende"):
        cotes.append("droite")
    if not cotes:
        return
    for k in range(1 if rng.random() < 0.7 else 2):
        sorte, motif, contour, couleur = _forme_exterieur(l, rng)
        l.exterieurs.append({
            "sorte": sorte, "cote": rng.choice(cotes), "part": 1.0 if sorte == "jardin" else rng.uniform(0.35, 0.85),
            "position": rng.random(), "profondeur_m": rng.uniform(2.5, 4.5) if sorte == "jardin" else rng.uniform(1.0, 2.4),
            "motif": motif, "contour": contour, "couleur": couleur, "numero": k + 1,
        })


# Sur 103 plans, 11 ont plusieurs niveaux et 2 ont deux logements. Tiré ici pour tout plan, mais un plan de plain-pied ne
# compose des niveaux qu'une fois sur quatre (10 % des logements sont des duplex, qui composent toujours) : 0,33 × (0,10 + 0,90 / 4)
# donne les 11 % voulus. 3 % plutôt que 2 % pour les deux logements : le cas n'existe qu'à l'examen, il ne doit pas être oublié.
PART_NIVEAUX, PART_DEUX_LOGEMENTS = 0.33, 0.03
PLAIN_PIED_EMPILE = 0.25


def _tirer_composition(l: Lot2, rng: random.Random) -> None:
    u = rng.random()
    if u < PART_NIVEAUX:
        l.composition = "niveaux"
        l.disposition = "empiles" if rng.random() < 0.75 else "cote_a_cote"  # fr-025, fr-072, fr-118, fr-119, fr-120, fr-075 sont empilés
    elif u < PART_NIVEAUX + PART_DEUX_LOGEMENTS:
        l.composition = "deux_logements"
        l.disposition = "palier" if rng.random() < 0.6 else "mitoyen"


def _tirer_ecran(l: Lot2, rng: random.Random) -> None:
    """Trait 10, 6 plans sur 103. Ce que montrent fr-024, fr-040, fr-086 : papier grisé, un peu flou, très peu penché (1 à 3°, 2 à 8
    au catalogue : les plus forts n'existent pas dans ces trois plans), verso qui transparaît, texte gros, jamais de table.
    `ecran_si_photo` : parmi des plans qui sont tous des photos (--photo-realiste), le cas pèse bien plus que 6 %."""
    l.ecran_si_photo = rng.random() < 0.3
    if not l.recadre and rng.random() < 0.06:
        _tirer_ecran_force(l, rng)


def _tirer_ecran_force(l: Lot2, rng: random.Random) -> None:
    l.ecran = True
    l.ecran_bordure = rng.random() < 0.5  # fr-024, fr-040, fr-086 n'en montrent pas : le catalogue la demande, d'autres captures l'ont
    l.part_texte = max(l.part_texte or 0.0, rng.uniform(0.19, 0.26))
    l.sortie_jpeg = True
    if rng.random() < 0.75:
        l.rotation = rng.choice((-1, 1)) * rng.uniform(0.5, 4.0)
    if l.famille == "scan_ancien":
        return  # il a déjà son papier
    l.papier = rng.randint(222, 245)
    l.contraste = rng.uniform(0.8, 0.95)
    l.salissure = rng.choice(("grain", "telephone", "telephone"))
    if rng.random() < 0.5:  # fr-024, fr-040 : un gris légèrement bleuté
        l.teinte = (rng.uniform(0.94, 0.98), rng.uniform(0.95, 0.98), 1.0)


def _forme_exterieur(l: Lot2, rng: random.Random) -> tuple[str, str, str, tuple[int, int, int] | None]:
    """(sorte, motif, contour, couleur de fond) selon les habitudes de chaque famille."""
    if l.famille == "murs_noirs":  # catalogue, trait 4 : trait fin ou pointillé, rien dedans (fr-046, fr-085)
        return "balcon", "vide", rng.choice(("fin", "pointille")), None
    if l.famille == "scan_ancien":  # fr-036 : terrasse carrelée ; fr-037 : balcon en croisillons
        return rng.choice((("terrasse", "carrelage", "fin", None), ("balcon", "croisillons", "fin", None), ("balcon", "vide", "fin", None)))
    if l.famille == "logiciel_public":  # fr-102 : terrasse d'un vert franc
        vert = (rng.randint(115, 195), rng.randint(225, 240), rng.randint(95, 170))
        return rng.choice(("terrasse", "jardin")), "vert", "gris", vert
    if l.famille == "promoteur_gris":  # fr-108 : balcon vide ; fr-062 : terrasse carrelée ; fr-110 : lattes
        return rng.choice((("balcon", "vide", "moyen", None), ("terrasse", "carrelage", "fin", (222, 222, 200)), ("balcon", "lattes", "fin", None)))
    return rng.choice((("balcon", "vide", "fin", None), ("balcon", "hachures", "fin", None), ("balcon", "vide", "pointille", None),  # fr-080
                       ("terrasse", "lattes", "moyen", None), ("jardin", "herbe", "moyen", None),  # fr-084
                       ("jardin", "vert", "fin", (190, 222, 170))))


def _accorder(l: Lot2) -> None:
    """Ce qui ne doit jamais se trouver ensemble sur un plan, quel que soit l'ordre des tirages."""
    if l.unite_cotes == "cm":
        # Jamais de cm et de mètres sur le même plan : le lecteur n'admet les entiers que sans aucune cote « d,dd ».
        l.dimensions, l.cote_point = "", False
        if l.hsp == "HSP cercle":  # « 2.50 » seul dans son cercle a la forme d'une cote en mètres
            l.hsp = "hsp:"
    if l.tableau or l.surface_totale:  # les étiquettes de placard et la légende vont dans les mêmes marges
        l.placards_fleches = False
        if l.pastilles == "legende":
            l.pastilles = "avec_noms"
    if l.recadre:  # le logement touche les bords : plus de place pour ce qui s'écrit dehors
        l.placards_fleches, l.numero_lot, l.barre_echelle = False, "", False
        l.exterieurs = []
        if l.pastilles == "legende":
            l.pastilles = "avec_noms"


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
    l.sortie_jpeg = l.sortie_jpeg or rng.random() < 0.3
    if rng.random() < 0.15 and not l.textes_verticaux:  # trait 7 : fr-067 dans les pièces étroites, fr-055 partout
        l.textes_verticaux = "etroites" if rng.random() < 0.8 else "toutes"
    if rng.random() < 0.05 and not l.manuscrit and l.famille not in ("agence_coloree", "logiciel_public"):  # trait 11 : fr-086, fr-112
        l.manuscrit = "surfaces" if rng.random() < 0.7 else "tout"
        _tirer_stylo(l, rng)
    if rng.random() < 0.03:  # trait 14 : fr-059
        l.pastilles = "avec_noms" if rng.random() < 0.6 else "legende"
    if rng.random() < 0.05:  # trait 15 : fr-080, fr-086
        l.placards_fleches = True
    if rng.random() < 0.3:  # trait 17 : n'agit que sur un niveau qui a un escalier
        l.escalier = "colimacon" if rng.random() < 0.6 else "fleche_acces"


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
    if style.realisme is not None and (l.ecran or l.ecran_si_photo):
        l.ecran = style.realisme.ecran = True  # la vraie photo garde tout, seule la table devient un écran
    absurde = v is not None and (v.absurde or v.inverse)
    style.lot2 = l
    if absurde:  # un style absurde apprend qu'un mur reste un mur : on ne lui rend pas des couleurs sages
        l.couleur_murs = l.couleur_fond = l.couleur_traits = l.couleur_textes = l.couleur_cotes = None
        l.palette, l.fenetres_pleines, l.portes_boites, l.couleur_surface, l.mobilier_couleur = "", False, False, None, False
        l.tableau_couleur = l.teinte = None
    _page_sage(style, l)
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
    elif l.famille == "promoteur_gris":
        style.cotes = style.noms = style.surfaces = style.symboles = style.arcs = style.mobilier = True
        style.cartouche = style.titre = style.fleche_nord = style.echelle_graphique = False
    elif l.famille == "logiciel_public":
        style.cotes = style.noms = style.surfaces = style.symboles = style.arcs = style.mobilier = True
        style.cartouche = style.titre = style.fleche_nord = False
    elif l.famille == "scan_ancien":
        style.cotes = style.noms = style.surfaces = style.symboles = style.arcs = True
        style.mobilier = l.mobilier_fixes
        style.cartouche = style.titre = style.fleche_nord = style.echelle_graphique = False
    if l.famille in ("promoteur_gris", "scan_ancien"):
        style.pieces_colorees = bool(l.palette)  # pièces blanches, sauf fr-041 et fr-062 : pas le pastel tiré par le style de base
    if l.famille in ("logiciel_public", "scan_ancien"):
        style.echelle_graphique = l.barre_echelle
    if l.unite_cotes == "cm":  # le cartouche écrit « Cotes intérieures, en mètres » et des hauteurs en mètres
        style.cartouche = False
    if l.sans_noms:
        style.noms = False
    if l.sans_mobilier:
        style.mobilier = False
    if l.dimensions:
        style.surfaces = True  # écrire une dimension demande la permission des surfaces (--sans-cotes l'éteint plus bas)
    if l.pastilles:
        style.noms = True  # noms() dessine aussi les pastilles : sans lui, une légende renverrait à des numéros absents
    if l.couleur_murs is not None or l.palette or l.couleur_cotes is not None:
        # La photocopie et les taches passent l'image en gris : le trait disparaîtrait. Le scan ancien, lui, en vit.
        if style.salissure in ("photocopie", "taches") and l.famille != "scan_ancien":
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
    if l.exterieurs:
        # Un extérieur occupe la marge du bas ou de droite : les chaînes, la barre et le cartouche y passeraient par-dessus.
        style.cotes_partielles = False
        if any(e["cote"] == "bas" for e in l.exterieurs):
            style.echelle_graphique = False
        if any(e["cote"] == "droite" for e in l.exterieurs):
            style.cartouche = False
    if l.placards_fleches:  # le cartouche prend la marge de droite, où vont les étiquettes de placard
        style.cartouche = False
    if style.rotation or style.perspective or style.focale:
        # Défaut connu de contour_des_murs : contour calculé sur le masque tourné, dessiné à plat (double contour décalé).
        style.murs_contour = False
    if sans_cotes:
        style.cotes, style.surfaces = False, surfaces0
    if not style.cotes:
        style.cotes_partielles = False


def _page_sage(style, l: Lot2) -> None:
    """La page de base : droite et blanche, sauf si la page est le sujet.

    Pourquoi : la rotation, le papier gris, le contraste et la photocopie viennent du style de base (`style_au_hasard`), qui
    les tire pour des jeux où ils sont une épreuve. Mesuré au chantier 1 : 5 plans penchés sur 12, des pages grises. Sur les 59
    plans d'entraînement du catalogue, 3 sont nettement penchés (fr-024, fr-040, fr-086) et 3 de moins de 0,5°, soit 5 à 10 % ;
    4 ont une page franchement grise (7 %), tous des photos ou des scans. On garde donc la page d'une photo (famille « photo », vraie caméra) ; le scan ancien pose la sienne."""
    if style.focale or style.realisme is not None or style.famille == "photo":
        l.teinte = None  # la teinte du scan colorerait aussi la table de la photo
        return  # une photo reste une photo : son papier, sa perspective, sa lumière sont le sujet
    style.rotation, style.perspective = 0.0, 0.0
    style.papier = 255
    style.contraste = max(style.contraste, 1.0)  # un contraste < 1 grise le blanc de la page
    if style.salissure in ("photocopie", "taches"):
        style.salissure = "jpeg"  # le blanc d'une photocopie vaut 205 à 235
    if l.famille == "scan_ancien" or l.ecran:
        if l.papier is not None:
            style.papier = l.papier
        if l.contraste is not None:
            style.contraste = l.contraste
        if l.salissure:
            style.salissure = l.salissure
        if l.rotation is not None:
            style.rotation = l.rotation


def resume(l: Lot2) -> dict:
    """Pour le manifeste : la famille et les traits allumés, sans les couleurs."""
    ignores = {"famille", "marges", "px_par_m", "part_texte", "epaisseur_trait", "epaisseur_trait_mur", "surface_decimales",
               "tableau_decimales", "format_dimensions", "couleur_etiquette", "couleur_fenetres", "contour_fenetres",
               "surface_point", "cote_point", "sortie_jpeg", "noms_gras", "taille_cotes", "pas_sol", "papier", "contraste", "salissure",
               "ecran_si_photo", "ecran_bordure", "blocs", "palier", "titres_place", "titre_tirets", "titre_surface", "filet"}
    traits = []
    for f in fields(l):
        valeur = getattr(l, f.name)
        if f.name in ignores or f.name.startswith("couleur_") or f.name == "tableau_couleur":
            continue
        if valeur:
            traits.append(f.name)
    if l.unite_cotes == "m" and "unite_cotes" in traits:
        traits.remove("unite_cotes")  # le mètre est le cas ordinaire : seule l'unité cm est un trait
    return {"famille": l.famille, "traits": traits, "composition": l.composition}


def plans_de_travail_au_mur(meubles: dict[str, list[Meuble]], niveau) -> dict[str, list[Meuble]]:
    """Un plan de travail court le long d'un mur, il ne part pas de lui vers le milieu de la pièce.

    La cause : mobilier.pose choisit le sens du meuble d'après la forme de la pièce, puis _contre_un_mur tire le mur au hasard ;
    2,40 m × 0,60 m sur un mur « ouest » se retrouve en travers. On ne touche pas à mobilier.py (le hasard « mobilier- » fait les
    anciens jeux) : sous --lot2, le meuble posé de travers est retourné contre un mur. Sans hasard : plan et plan_sans_mobilier
    voient le même. S'il ne tient nulle part sans gêner une porte ou un autre meuble, il disparaît."""
    pieces = {p.id: p for p in niveau.pieces}
    sortie = {}
    for pid, lst in meubles.items():
        p = pieces[pid]
        sortie[pid] = list(lst)
        for i, m in enumerate(lst):
            if m.type != "plan_de_travail" or _longe_un_mur(m, p.rect):
                continue
            autres = [_boite_meuble(x) for j, x in enumerate(sortie[pid]) if j != i and x is not None]
            neuf = _le_long_d_un_mur(m, p, _zones_de_battement(p, niveau.ouvertures) + list(p.interdits), autres)
            sortie[pid][i] = Meuble(m.type, _rect(neuf.x0, neuf.y0, neuf.x1, neuf.y1), m.hauteur, m.forme) if neuf else None
        sortie[pid] = [m for m in sortie[pid] if m is not None]
    return sortie


def _boite_meuble(m: Meuble) -> Rect:
    xs, ys = [q[0] for q in m.contour], [q[1] for q in m.contour]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def _longe_un_mur(m: Meuble, r: Rect, jeu: int = 100) -> bool:
    b = _boite_meuble(m)
    if b.largeur >= b.hauteur:
        return b.y0 - r.y0 <= jeu or r.y1 - b.y1 <= jeu
    return b.x0 - r.x0 <= jeu or r.x1 - b.x1 <= jeu


def _le_long_d_un_mur(m: Meuble, p, interdits: list[Rect], autres: list[Rect], marge: int = 50) -> Rect | None:
    """Le rectangle retourné, le plus près possible de sa place d'origine."""
    b, r = _boite_meuble(m), p.rect
    long_, prof = max(b.largeur, b.hauteur), min(b.largeur, b.hauteur)
    centre_x, centre_y = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
    candidats = []
    if r.largeur >= long_ + 2 * marge:
        pas_x = range(int(r.x0 + marge), int(r.x1 - marge - long_) + 1, 100)
        for y in (r.y0 + marge, r.y1 - marge - prof):
            candidats += [Rect(x, y, x + long_, y + prof) for x in pas_x]
    if r.hauteur >= long_ + 2 * marge:
        pas_y = range(int(r.y0 + marge), int(r.y1 - marge - long_) + 1, 100)
        for x in (r.x0 + marge, r.x1 - marge - prof):
            candidats += [Rect(x, y, x + prof, y + long_) for y in pas_y]
    candidats.sort(key=lambda c: abs((c.x0 + c.x1) / 2 - centre_x) + abs((c.y0 + c.y1) / 2 - centre_y))
    for c in candidats:
        if _libre(c, interdits, autres):
            return c
    return None


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
    for e in l.exterieurs:  # la profondeur de l'extérieur, sans quoi il sortirait de l'image
        place = math.ceil(e["profondeur_m"] * style.px_par_m + 40)
        if e["cote"] == "bas":
            bas = max(bas, place)
        else:
            droite = max(droite, place)
    if l.blocs and l.titres_place == "haut":
        haut = max(haut, math.ceil(retrait_du_titre(style, "haut") + 1.2 * t))
    if l.blocs and l.titres_place == "bas":
        bas = max(bas, math.ceil(retrait_du_titre(style, "bas") + 1.2 * t))
    if l.numero_lot:
        lignes = 3.6 if "{type}" in l.numero_lot else 2.6
        depart = RECUL_COTE + 1.6 * t if style.cotes and not l.sans_chaines else 10
        haut = max(haut, math.ceil(depart + lignes * t + 8))
    if l.placards_fleches:
        place = math.ceil(_debut_tableau(style) + _police(style.police, _taille_placard(style)).getlength("Placard 10") + 14)
        gauche, droite = max(gauche, place), max(droite, place)
    if l.pastilles == "legende":
        droite = max(droite, math.ceil(_debut_tableau(style) + _largeur_colonne(style) + 2.2 * t + 20))
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


def _taille_placard(style) -> int:
    return max(9, round(style.taille_texte * 0.8))


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
    if forme.startswith("2.70"):
        return f"{a:.2f}×{b:.2f}"
    if forme.startswith("3.87"):
        return f"{a:.2f} x {b:.2f} m"
    return f"{_nombre(a, 2)} m × {_nombre(b, 2)} m"


def format_surface(metres_carres: float, l: Lot2, parentheses: bool = False) -> str:
    texte = f"{_nombre(metres_carres, l.surface_decimales, l.surface_point)} m²"
    return f"({texte})" if parentheses else texte


def abreger(nom: str) -> str:
    """fr-108, fr-041 : « Dgt », « Ch. 1 », « Pl. 2 ». Seul le dessin change : le nom et l'identifiant de la pièce restent."""
    if nom in ABREVIATIONS:
        return ABREVIATIONS[nom]
    mot, _, reste = nom.rpartition(" ")
    if mot in ABREVIATIONS and reste.isdigit():
        return f"{ABREVIATIONS[mot]} {reste}"
    return nom


def texte_cote(mm: float, l: Lot2) -> str:
    """Une seule unité sur tout le plan : le lecteur n'admet les centimètres entiers que sans aucune cote « d,dd »."""
    if l.unite_cotes == "cm":
        return str(round(mm / 10))
    return _nombre(mm / 1000, 2, l.cote_point)


def texte_metres(mm: float) -> str:
    """Les logiciels grand public écrivent « 4 m », « 1,8 m », « 4,86 m » (fr-100, fr-102)."""
    texte = f"{round(mm / 10) / 100:.2f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} m"


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
    # Le stylo écrit plus gros que la machine (fr-086).
    petit = t0 if l.manuscrit else max(8, t0 - 2)
    plus_petit = t0 - 1 if l.manuscrit else max(8, round(t0 * 0.75))
    entre_parentheses = l.parentheses_grises or (v is not None and v.parentheses)
    for k, p in enumerate(d.niv.pieces, 1):
        if l.placards_fleches and p.sorte == "placard":
            continue  # fr-080 : son nom est écrit dehors, relié par une flèche
        r = p.rect
        cx, cy = d.px((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        lignes = []  # (priorité, texte, taille, couleur, gras, sorte)
        nom = abreger(p.nom) if l.abreviations else p.nom
        nom = nom.upper() if l.majuscules or (v is not None and v.majuscules) else nom
        sens = _sens_du_texte(d, p, nom)
        cote_utile = r.hauteur if sens else r.largeur
        place = cote_utile * s * 0.9
        t = t0
        ecrit_dedans = l.pastilles != "legende"  # sinon le nom et la surface sont dans la légende
        if l.pastilles and min(r.largeur, r.hauteur) * s > 2.4 * t0:
            lignes.append((-1, str(k), max(9, round(t0 * 0.85)), couleur, False, "pastille"))
        if st.noms and ecrit_dedans:
            if l.noms_tronques:
                nom = tronquer(_police(st.police, t0), nom, place)
            else:
                if l.noms_courts and _police(st.police, t0).getlength(nom) > place:
                    nom = abreger(p.nom)
                    nom = nom.upper() if l.majuscules or (v is not None and v.majuscules) else nom
                while t > 9 and _police(st.police, t).getlength(nom) > place:
                    t -= 1
            lignes.append((0, nom, t, couleur, l.noms_gras, "nom"))
        if st.surfaces and not l.noms_courts and ecrit_dedans:
            surface = format_surface(surface_piece(p) / 1e6, l, entre_parentheses)
            dims = format_dimensions(r.largeur, r.hauteur, l.format_dimensions) if l.dimensions else ""
            if dims and _police(st.police, plus_petit).getlength(dims) > cote_utile * s * 0.95:
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
        _poser_lignes(d, p, lignes, cx, cy, sens)


def _sens_du_texte(d, p, nom: str) -> int:
    """0 : à plat ; +1 : se lit de bas en haut (fr-067, fr-102) ; -1 : de haut en bas (fr-055).

    Une pièce coupée en biais reste à plat : sa boîte déborde de son contour, le texte tourné y toucherait le mur."""
    st, l = d.style, d.style.lot2
    if not l.textes_verticaux or p.contour:
        return 0
    s = d.rep.s
    longueur = _police(st.police, st.taille_texte).getlength(nom)
    if longueur > p.rect.hauteur * s * 0.9:
        return 0  # il ne tiendrait pas non plus debout
    if l.textes_verticaux == "toutes":
        return -1
    return 1 if longueur > p.rect.largeur * s * 0.9 else 0


def _texte_hsp(d, l: Lot2) -> str:
    h = d.niv.hsp / 1000
    if l.hsp == "hsp:":
        return f"hsp: {h:.2f}"
    if l.hsp == "HsP :":
        return f"HsP : {h:.2f} m"
    return f"{h:.2f}"  # dans le cercle, sous « HSP »


def _hauteur_ligne(ligne: tuple) -> float:
    return ligne[2] * {"cercle": 3.4, "pastille": 2.3}.get(ligne[5], 1.25)


def _garder_lignes(lignes: list[tuple], dispo: float) -> tuple[list[tuple], float]:
    gardees, total = [], 0.0
    for ligne in sorted(lignes, key=lambda x: x[0]):
        h = _hauteur_ligne(ligne)
        if gardees and total + h > dispo:
            continue
        gardees.append(ligne)
        total += h
    return gardees, total


def _poser_lignes(d, p, lignes: list[tuple], cx: float, cy: float, sens: int = 0) -> None:
    """Écrit ce qui tient dans la hauteur de la pièce, par priorité, centré sur la pièce. `sens` : texte tourné, les
    lignes se rangent alors de gauche à droite (ou de droite à gauche), dans la largeur de la pièce."""
    st, l = d.style, d.style.lot2
    s = d.rep.s
    r = p.rect
    dispo = (r.largeur if sens else r.hauteur) * s * 0.95
    gardees, total = _garder_lignes(lignes, dispo)
    # Le cercle HSP dessine une forme de 3 lignes : il ne se pose que s'il ne touche ni une ouverture ni le battant d'une
    # porte (petites pièces). Sans lui, les autres lignes se recentrent.
    for ligne in gardees:
        if ligne[5] == "cercle":
            y = cy - total / 2 + sum(_hauteur_ligne(x) for x in gardees[:gardees.index(ligne)]) + _hauteur_ligne(ligne) / 2
            if sens or not cercle_tient(d, p, cx, y, _rayon_cercle_hsp(ligne[2])):
                gardees, total = _garder_lignes([x for x in lignes if x[5] != "cercle"], dispo)
            break
    if not gardees:
        return
    if l.etiquettes and not sens:
        _etiquette(d, p, gardees, cx, cy, total)
    position = -total / 2
    for _, texte, taille, couleur, gras, sorte in gardees:
        h = _hauteur_ligne((0, texte, taille, couleur, gras, sorte))
        milieu = position + h / 2
        position += h
        if sens:
            xy = (cx + sens * milieu, cy)
        else:
            xy = (cx, cy + milieu)
        if sorte == "cercle":
            _cercle_hsp(d, xy[0], xy[1], texte, taille, couleur)
        elif sorte == "pastille":
            _pastille(d, xy, texte, taille, couleur)
        elif _a_la_main(l, sorte):
            texte_main(d, xy, texte, taille, l.couleur_stylo, d.hasard_lot2, sens=sens, souligne=l.souligne and sorte == "nom")
        elif sens:
            _texte_tourne(d, xy, texte, taille, couleur, sens, gras)
        else:
            _ecrire(d, xy, texte, taille, couleur, gras)


def _a_la_main(l: Lot2, sorte: str) -> bool:
    return l.manuscrit == "tout" or (l.manuscrit == "surfaces" and sorte in ("mesure", "hsp", "sol"))


def _texte_tourne(d, xy, texte: str, taille: int, couleur, sens: int, gras: bool = False) -> None:
    """Comme _Dessin.texte(vertical=True), dans les deux sens : fr-055 se lit de haut en bas, fr-102 de bas en haut."""
    police = _police(d.style.police, taille)
    g, h, dr, b = police.getbbox(texte)
    vignette = Image.new("L", (dr - g + 4, b - h + 4), 0)
    dessin = ImageDraw.Draw(vignette)
    dessin.text((2 - g, 2 - h), texte, fill=255, font=police)
    if gras and taille >= 11:
        dessin.text((3 - g, 2 - h), texte, fill=255, font=police)
    _coller(d, xy, vignette.rotate(90 * sens, expand=True), couleur)


def _coller(d, xy, vignette: Image.Image, couleur) -> None:
    x, y = round(xy[0] - vignette.width / 2), round(xy[1] - vignette.height / 2)
    d.image.paste(Image.new("RGB", vignette.size, couleur), (x, y), vignette)


def _boite_px(d, r) -> tuple[float, float, float, float]:
    x0, y1 = d.px(r.x0, r.y0)
    x1, y0 = d.px(r.x1, r.y1)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _rayon_cercle_hsp(taille: int) -> float:
    return taille * 1.55


def cercle_tient(d, p, cx: float, cy: float, rayon: float) -> bool:
    """Le cercle reste dans la pièce sans toucher une ouverture ni le battant d'une porte. Boîtes comparées au cercle :
    2 pixels de marge, le trait du cercle a son épaisseur."""
    rayon += 2
    x0, y0, x1, y1 = _boite_px(d, p.rect)
    if cx - rayon < x0 or cx + rayon > x1 or cy - rayon < y0 or cy + rayon > y1:
        return False
    obstacles = [rect_de_l_ouverture(o) for o in d.niv.ouvertures] + _zones_de_battement(p, d.niv.ouvertures) + list(p.interdits)
    for r in obstacles:
        bx0, by0, bx1, by1 = _boite_px(d, r)
        ecart_x = max(bx0 - cx, 0.0, cx - bx1)
        ecart_y = max(by0 - cy, 0.0, cy - by1)
        if ecart_x * ecart_x + ecart_y * ecart_y < rayon * rayon:
            return False
    return True


def _pastille(d, xy, texte: str, taille: int, couleur) -> None:
    """fr-059 : un disque foncé, le numéro en blanc. Pas de glyphe ①② : Inter et Liberation ne l'ont pas."""
    rayon = taille * 1.05
    cx, cy = xy
    d.d.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), fill=couleur)
    d.texte(xy, texte, taille, (255, 255, 255))


# ---------------------------------------------------------------- l'écriture à la main


def _vignette_main(texte: str, taille: int, rng: random.Random) -> Image.Image:
    """Le mot, lettre par lettre : chaque glyphe de DejaVuSans (la seule police à avoir « ² » et « × ») tourné, décalé, un peu
    plus ou moins grand, sur une pente propre au mot. Aucune police téléchargée : c'est une écriture régulière, pas une vraie
    main (fr-086, fr-112 sont plus libres)."""
    cote = int(taille * 2.2) + 6
    toile = Image.new("L", (int(taille * 0.95 * (len(texte) + 2)) + 2 * cote, cote + 8), 0)
    pente = rng.uniform(0.08, 0.32)
    epais = taille >= 22 and rng.random() < 0.5  # DejaVu est déjà épaisse : en dessous, le filtre bouche les chiffres
    x, ondule = float(cote / 2), rng.uniform(0, 6.3)
    for i, lettre in enumerate(texte):
        if lettre == " ":
            x += taille * rng.uniform(0.3, 0.45)
            continue
        t = max(7, round(taille * rng.uniform(0.9, 1.1)))
        police = _police("DejaVuSans.ttf", t)
        g = Image.new("L", (cote, cote), 0)
        ImageDraw.Draw(g).text((cote / 2, cote * 0.62), lettre, fill=255, font=police, anchor="ms")
        g = g.rotate(rng.uniform(-7, 7), resample=Image.BILINEAR)
        g = g.transform(g.size, Image.AFFINE, (1, pente, -pente * cote * 0.62, 0, 1, 0), resample=Image.BILINEAR)
        if epais:
            g = g.filter(ImageFilter.MaxFilter(3))
        avance = police.getlength(lettre)
        gx = round(x + avance / 2 - cote / 2 + rng.uniform(-1, 1))
        gy = round(4 + taille * 0.1 * math.sin(ondule + i * 0.8) + rng.uniform(-1, 1))
        boite = (gx, gy, gx + cote, gy + cote)
        toile.paste(ImageChops.lighter(toile.crop(boite), g), boite)
        x += avance * rng.uniform(0.88, 1.02)
    zone = toile.getbbox()
    return toile.crop(zone) if zone else toile


def texte_main(d, xy, texte: str, taille: int, couleur, rng: random.Random, sens: int = 0, souligne: bool = False) -> None:
    """Écrit au stylo. `rng` vient de la clé « lot2-dessin- » : plan et plan_sans_mobilier ont le même tremblé."""
    vignette = _vignette_main(texte, taille, rng)
    if souligne:  # fr-112 : les noms soulignés d'un trait à la main
        large = Image.new("L", (vignette.width, vignette.height + 6), 0)
        large.paste(vignette, (0, 0))
        y = vignette.height + 2
        ImageDraw.Draw(large).line([(0, y + rng.randint(-1, 1)), (vignette.width // 2, y + rng.randint(-1, 1)),
                                    (vignette.width - 1, y + rng.randint(-1, 1))], fill=255, width=max(1, taille // 12))
        vignette = large
    if sens:
        vignette = vignette.rotate(90 * sens, expand=True)
    _coller(d, xy, vignette, couleur)


def ecrivain_cotes(d):
    """La fonction qui écrit les cotes : d.texte, ou le stylo. Même signature, pour que rendu.chaine n'ait qu'une ligne de plus."""
    l = d.style.lot2
    if not l.manuscrit:
        return d.texte

    def ecrire(xy, texte, taille, couleur, ancre="mm", vertical=False):
        texte_main(d, xy, texte, taille, l.couleur_stylo, d.hasard_lot2, sens=1 if vertical else 0)
    return ecrire


def _cercle_hsp(d, cx: float, cy: float, valeur: str, taille: int, couleur) -> None:
    """fr-105 : « HSP 2.50 » dans un cercle."""
    rayon = _rayon_cercle_hsp(taille)
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


def avant_tout(d, rng: random.Random) -> None:
    """Appelé au début de _Dessin.tout : ce qui se trouve sous les murs et les pièces."""
    if d.style.lot2.exterieurs:
        exterieurs(d, rng)


def apres_tout(d, rng: random.Random) -> None:
    """Appelé à la fin de _Dessin.tout : par-dessus le plan et dans les marges réservées."""
    st, l = d.style, d.style.lot2
    if l.triangles:
        triangles(d)
    if st.cotes and l.cotes_interieures:
        cotes_interieures(d, rng)
    if st.cotes and l.cotes_par_mur:
        cotes_par_mur(d, rng)
    if l.cercles_pmr:
        cercles_pmr(d, rng)
    if l.mentions_menuiseries:
        mentions_menuiseries(d)
    if l.placards_fleches:
        placards_fleches(d)
    if l.numero_lot:
        numero_lot(d)
    if l.pastilles == "legende":
        legende_pastilles(d)
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
    if l.blocs:
        titres_des_blocs(d)
    if l.filet:
        filet_entre_blocs(d)
    if l.palier and st.noms:
        palier_ecrit(d)


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


# ---------------------------------------------------------------- trait 3 : les plans de vente du neuf


def _cote_fine(d, a, b, horizontale: bool, texte: str, taille: int, couleur, ligne, sur_le_trait: bool = False) -> None:
    """Un trait de cote fin, de mur à mur, avec ses marques. `sur_le_trait` : le trait s'interrompt pour le nombre (fr-100) ;
    sinon le nombre est posé à côté (fr-108, fr-110)."""
    ecrire = ecrivain_cotes(d)
    longueur = _police(d.style.police, taille).getlength(texte)
    marque = max(3, round(taille * 0.3))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if horizontale:
        if sur_le_trait:
            d.d.line((a, (mx - longueur / 2 - 3, my)), fill=ligne, width=1)
            d.d.line(((mx + longueur / 2 + 3, my), b), fill=ligne, width=1)
        else:
            d.d.line((a, b), fill=ligne, width=1)
        for x, y in (a, b):
            d.d.line(((x, y - marque), (x, y + marque)), fill=ligne, width=1)
        ecrire((mx, my if sur_le_trait else my - taille * 0.75), texte, taille, couleur)
    else:
        if sur_le_trait:
            d.d.line((a, (mx, my + longueur / 2 + 3)), fill=ligne, width=1)
            d.d.line(((mx, my - longueur / 2 - 3), b), fill=ligne, width=1)
        else:
            d.d.line((a, b), fill=ligne, width=1)
        for x, y in (a, b):
            d.d.line(((x - marque, y), (x + marque, y)), fill=ligne, width=1)
        ecrire((mx if sur_le_trait else mx - taille * 0.75, my), texte, taille, couleur, vertical=True)


def _couleurs_cotes(d) -> tuple:
    l = d.style.lot2
    return (l.couleur_cotes or d.style.textes), (l.couleur_cotes or d.style.traits)


def cotes_interieures(d, rng: random.Random) -> None:
    """fr-108, fr-110 : dans chaque pièce, un trait de mur à mur dans chaque sens, près d'un bord (le centre est pour le nom).
    La longueur écrite est la vraie, dans l'unité du plan."""
    st, l = d.style, d.style.lot2
    taille = max(9, round(st.taille_texte * l.taille_cotes))
    couleur, ligne = _couleurs_cotes(d)
    police = _police(st.police, taille)
    for p in d.niv.pieces:
        if p.contour:
            continue  # le bout d'un trait tomberait dans le coin coupé : une cote fausse apprise
        r = p.rect
        if r.largeur > 1000 and r.largeur * d.rep.s > 2 * police.getlength(texte_cote(r.largeur, l)):
            recul = min(rng.uniform(220, 520), r.hauteur * 0.22)
            y = r.y1 - recul if rng.random() < 0.5 else r.y0 + recul
            _cote_fine(d, d.px(r.x0, y), d.px(r.x1, y), True, texte_cote(r.largeur, l), taille, couleur, ligne)
        if r.hauteur > 1000 and r.hauteur * d.rep.s > 2 * police.getlength(texte_cote(r.hauteur, l)):
            recul = min(rng.uniform(220, 520), r.largeur * 0.22)
            x = r.x1 - recul if rng.random() < 0.5 else r.x0 + recul
            _cote_fine(d, d.px(x, r.y0), d.px(x, r.y1), False, texte_cote(r.hauteur, l), taille, couleur, ligne)


def cercles_pmr(d, rng: random.Random) -> None:
    """Le cercle de giration de 1,50 m (fr-041, fr-108), en pointillé avec sa croix, décalé du nom. Du fond pour le masque."""
    r_mm = 750
    candidates = [p for p in d.niv.pieces if p.sorte in ("sdb", "sde", "wc", "chambre", "sejour", "principale", "cuisine")
                  and not p.contour and min(p.rect.largeur, p.rect.hauteur) >= 1600]
    rng.shuffle(candidates)
    couleur = d.style.traits
    for p in candidates[:rng.randint(1, 3)]:
        r = p.rect
        x = rng.uniform(r.x0 + r_mm + 40, r.x1 - r_mm - 40)
        y = rng.uniform(r.y0 + r_mm + 40, r.y1 - r_mm - 40)
        cx, cy = d.px(x, y)
        rr = r_mm * d.rep.s
        for a in range(0, 360, 20):
            d.d.arc((cx - rr, cy - rr, cx + rr, cy + rr), a, a + 10, fill=couleur, width=1)
        croix = max(3, rr * 0.08)
        d.d.line(((cx - croix, cy), (cx + croix, cy)), fill=couleur, width=1)
        d.d.line(((cx, cy - croix), (cx, cy + croix)), fill=couleur, width=1)


def mentions_menuiseries(d) -> None:
    """« VR », « PF » juste dehors, le long de chaque fenêtre d'un mur extérieur (fr-041, fr-110)."""
    st = d.style
    taille = max(8, round(st.taille_texte * 0.6))
    for o in d.niv.ouvertures:
        m = o.mur
        if o.type not in MENTIONS or not m.dehors:
            continue
        milieu = (o.u0 + o.u1) / 2
        ecart = m.epaisseur / 2 + taille * 0.9 / d.rep.s
        x, y = (m.axe + m.dehors * ecart, milieu) if m.vertical else (milieu, m.axe + m.dehors * ecart)
        d.texte(d.px(x, y), MENTIONS[o.type], taille, st.textes)


def numero_lot(d) -> None:
    """Le numéro de lot, gros, en haut de page (fr-106 : « 45 »). « T3 G206 60.44 m² » (fr-108) porte la vraie surface, et
    celle-ci demande la permission des surfaces : --sans-cotes n'écrit aucune mesure."""
    st, l = d.style, d.style.lot2
    t = st.taille_texte
    x, y = d.rep.largeur0 / 2, 4 + 1.3 * t
    if "{type}" not in l.numero_lot:
        _ecrire(d, (x, y), l.numero_lot, round(t * 2.2), st.textes, gras=True)
        return
    _ecrire(d, (x, y - 0.2 * t), l.numero_lot.replace("{type}", d.log.type), round(t * 1.4), st.textes, gras=True)
    if st.surfaces:
        total = sum(surface_piece(p) for p in d.log.pieces) / 1e6
        _ecrire(d, (x, y + 1.3 * t), f"{total:.2f} m²", round(t * 1.4), st.textes, gras=True)


# ---------------------------------------------------------------- trait 6 : les logiciels grand public


def cotes_par_mur(d, rng: random.Random) -> None:
    """fr-100, fr-102 : une cote le long de chaque mur de chaque pièce, le trait interrompu par le nombre. Par pièce plutôt que
    par mur (écart à la conception) : ces logiciels cotent l'intérieur de la pièce, de face à face, pas l'axe du mur."""
    st, l = d.style, d.style.lot2
    taille = max(9, round(st.taille_texte * l.taille_cotes))
    couleur, ligne = _couleurs_cotes(d)
    for p in d.niv.pieces:
        if p.contour:
            continue
        r = p.rect
        for y, garde in ((r.y1 - min(rng.uniform(120, 300), r.hauteur * 0.2), rng.random()),
                         (r.y0 + min(rng.uniform(120, 300), r.hauteur * 0.2), rng.random())):
            if r.largeur >= 800 and garde < 0.75:
                _cote_fine(d, d.px(r.x0, y), d.px(r.x1, y), True, texte_metres(r.largeur), taille, couleur, ligne, sur_le_trait=True)
        for x, garde in ((r.x0 + min(rng.uniform(120, 300), r.largeur * 0.2), rng.random()),
                         (r.x1 - min(rng.uniform(120, 300), r.largeur * 0.2), rng.random())):
            if r.hauteur >= 800 and garde < 0.75:
                _cote_fine(d, d.px(x, r.y0), d.px(x, r.y1), False, texte_metres(r.hauteur), taille, couleur, ligne, sur_le_trait=True)


# ---------------------------------------------------------------- trait 9 : la teinte du scan


def teinter(image: np.ndarray, teinte: tuple[float, float, float]) -> np.ndarray:
    """Après salir : la photocopie passe l'image en gris et effacerait la couleur du papier. Les masques ne passent pas par ici."""
    return np.clip(image.astype(np.float32) * np.array(teinte, np.float32), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- trait 14 : la légende des pastilles


def legende_pastilles(d) -> None:
    """« ① Séjour 17,85 m² » à droite du plan. La surface demande la permission des surfaces."""
    st, l = d.style, d.style.lot2
    taille = _taille_tableau(st)
    pas = taille * 2.3
    x = d.px(d.rep.xmax, 0)[0] + _debut_tableau(st) + taille * 1.2
    y = max(taille * 1.5, d.px(0, d.rep.ymax)[1])
    for k, p in enumerate(d.niv.pieces, 1):
        if y + pas > d.rep.hauteur0:
            break  # tronquée à la page : elle ne déborde jamais
        _pastille(d, (x, y + pas / 2), str(k), taille, st.textes)
        d.texte((x + taille * 1.6, y + pas / 2), p.nom, taille, st.textes, ancre="lm")
        if st.surfaces:
            d.texte((x + _largeur_colonne(st) + taille, y + pas / 2), format_surface(surface_piece(p) / 1e6, l), taille, st.textes, ancre="rm")
        y += pas


# ---------------------------------------------------------------- trait 15 : les placards fléchés


def placards_fleches(d) -> None:
    """fr-080, fr-086 : « Placard 2 » dans la marge, une flèche qui traverse les murs jusqu'au placard. Vrai sur les plans, et le
    masque reste le mur : seule l'image reçoit le trait."""
    st = d.style
    taille = _taille_placard(st)
    milieu = (d.px(d.rep.xmin, 0)[0] + d.px(d.rep.xmax, 0)[0]) / 2
    droite_prise = d.style.lot2.pastilles == "legende" or any(e["cote"] == "droite" for e, _ in places_des_exterieurs(d))
    pris: dict[str, list[float]] = {"gauche": [], "droite": []}
    for p in d.niv.pieces:
        if p.sorte != "placard":
            continue
        r = p.rect
        cible = d.px((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        cote = "gauche" if cible[0] < milieu or droite_prise else "droite"
        y = cible[1]
        while any(abs(y - q) < taille * 1.6 for q in pris[cote]):  # deux étiquettes ne se recouvrent pas
            y += taille * 1.6
        pris[cote].append(y)
        if cote == "gauche":
            x = d.px(d.rep.xmin, 0)[0] - _debut_tableau(st)
            d.texte((x, y), p.nom, taille, st.textes, ancre="rm")
        else:
            x = d.px(d.rep.xmax, 0)[0] + _debut_tableau(st)
            d.texte((x, y), p.nom, taille, st.textes, ancre="lm")
        _fleche(d, (x, y), cible, st.textes)


def _fleche(d, depart, pointe, couleur) -> None:
    d.d.line((depart, pointe), fill=couleur, width=max(1, d.fin))
    a = math.atan2(pointe[1] - depart[1], pointe[0] - depart[0])
    t = max(6, round(d.style.taille_texte * 0.45))
    d.d.polygon([pointe, (pointe[0] - t * math.cos(a - 0.4), pointe[1] - t * math.sin(a - 0.4)),
                 (pointe[0] - t * math.cos(a + 0.4), pointe[1] - t * math.sin(a + 0.4))], fill=couleur)


# ---------------------------------------------------------------- trait 17 : les escaliers


def colimacon(d, x0: float, y0: float, x1: float, y1: float) -> None:
    """fr-093 : un cercle de marches au bout de la cage, le reste en marches droites. Seul le dessin change : le meuble, ses
    annotations et la carte de hauteur (12 bandes droites, une approximation assumée) restent ceux de l'escalier droit."""
    couleur = d.style.traits
    gx, hy = d.px(x0, y1)
    dx, by = d.px(x1, y0)
    largeur, hauteur = dx - gx, by - hy
    rayon = min(largeur, hauteur) / 2 * 0.96
    au_debut = d.log.graine % 2 == 0  # sans hasard : un seul bout par logement, aux deux niveaux
    if largeur >= hauteur:
        cx, cy = (gx + rayon + 2, (hy + by) / 2) if au_debut else (dx - rayon - 2, (hy + by) / 2)
    else:
        cx, cy = ((gx + dx) / 2, hy + rayon + 2) if au_debut else ((gx + dx) / 2, by - rayon - 2)
    noyau = max(3.0, 75 * d.rep.s)
    d.d.ellipse((cx - rayon, cy - rayon, cx + rayon, cy + rayon), outline=couleur, width=d.fin)
    d.d.ellipse((cx - noyau, cy - noyau, cx + noyau, cy + noyau), outline=couleur, width=d.fin)
    n = 13
    for k in range(n):
        a = 2 * math.pi * k / n
        d.d.line(((cx + noyau * math.cos(a), cy + noyau * math.sin(a)), (cx + rayon * math.cos(a), cy + rayon * math.sin(a))),
                 fill=couleur, width=d.fin)
    # La flèche du sens de montée, courbe, à mi-marche.
    moyen = (rayon + noyau) / 2
    d.d.arc((cx - moyen, cy - moyen, cx + moyen, cy + moyen), 30, 250, fill=couleur, width=d.fin)
    bout = math.radians(250)
    px_, py_ = cx + moyen * math.cos(bout), cy + moyen * math.sin(bout)
    t = max(5, round(rayon * 0.14))
    d.d.polygon([(px_ + t * 0.9, py_ + t * 0.2), (px_ - t * 0.4, py_ - t * 0.6), (px_ - t * 0.4, py_ + t * 0.8)], fill=couleur)
    # 2 ou 3 marches droites de départ dans ce qui reste de la cage.
    pas = 260 * d.rep.s
    for k in range(1, 4):
        if largeur >= hauteur:
            x = (cx + rayon + k * pas) if au_debut else (cx - rayon - k * pas)
            if gx < x < dx:
                d.d.line(((x, hy), (x, by)), fill=couleur, width=d.fin)
        else:
            y = (cy + rayon + k * pas) if au_debut else (cy - rayon - k * pas)
            if hy < y < by:
                d.d.line(((gx, y), (dx, y)), fill=couleur, width=d.fin)


def fleche_acces(d, x0: float, y0: float, x1: float, y1: float) -> None:
    """fr-120 : les marches droites habituelles, une pointe au bout de la flèche et « ACCES ETAGE » écrit dans la cage, le long
    de la flèche, côté pointe (le nom de la pièce est au milieu)."""
    st = d.style
    couleur = st.traits
    gx, hy = d.px(x0, y1)
    dx, by = d.px(x1, y0)
    t = max(5, round(st.taille_texte * 0.4))
    taille = max(8, round(st.taille_texte * 0.7))
    texte = "ACCES ETAGE" if d.niv.index == 0 else "ACCES RDC"
    longueur = _police(st.police, taille).getlength(texte)
    if dx - gx >= by - hy:  # la flèche de mobilier._escalier suit le grand côté, au milieu de la cage
        pointe = (dx - 150 * d.rep.s, (hy + by) / 2)
        d.d.polygon([pointe, (pointe[0] - t, pointe[1] - t / 2), (pointe[0] - t, pointe[1] + t / 2)], fill=couleur)
        if longueur < (dx - gx) * 0.45:
            d.texte((dx - longueur / 2 - 4, (hy + by) / 2 - taille * 0.9), texte, taille, st.textes)
    else:
        pointe = ((gx + dx) / 2, hy + 150 * d.rep.s)
        d.d.polygon([pointe, (pointe[0] - t / 2, pointe[1] + t), (pointe[0] + t / 2, pointe[1] + t)], fill=couleur)
        if longueur < (by - hy) * 0.45:
            d.texte(((gx + dx) / 2 - taille * 0.9, hy + longueur / 2 + 4), texte, taille, st.textes, vertical=True)


# ---------------------------------------------------------------- trait 18 et balcons du trait 4 : les extérieurs


def places_des_exterieurs(d) -> list[tuple[dict, Rect]]:
    """Où tombe chaque extérieur, en mm : contre la face d'un mur extérieur droit, sans mordre sur rien. Sans hasard ; un
    extérieur qui ne trouve pas de place n'est pas dessiné (la marge réservée reste, ce n'est que du blanc)."""
    deja = getattr(d, "_places_exterieurs", None)
    if deja is not None:
        return deja
    obstacles = [p.rect for p in d.niv.pieces] + [rect_du_mur(m) for m in d.niv.murs]
    if d.style.lot2.blocs:  # le vide entre deux blocs porte leurs titres et le palier : pas un balcon
        obstacles += vides_entre_blocs(d.style.lot2.blocs)
    for m in d.niv.murs_libres:  # A3 : pas de balcon sur un pan coupé
        xs, ys = [q[0] for q in m.polygone], [q[1] for q in m.polygone]
        obstacles.append(Rect(min(xs), min(ys), max(xs), max(ys)))
    places = []
    for e in d.style.lot2.exterieurs:
        r = _place_exterieur(d.niv, e, obstacles)
        if r is not None:
            places.append((e, r))
            obstacles.append(r)
    d._places_exterieurs = places
    return places


def _place_exterieur(niv, e: dict, obstacles: list[Rect]) -> Rect | None:
    droite = e["cote"] == "droite"
    dehors = 1 if droite else -1
    murs = [m for m in niv.murs if m.dehors == dehors and m.vertical == droite and m.fin - m.debut >= 1500]

    def fenetres(m):
        return [o for o in niv.ouvertures if o.mur is m and o.type != "porte"]

    def rang(m):  # un balcon se trouve devant une porte-fenêtre, à défaut une fenêtre
        f = fenetres(m)
        return (any(o.type == "porte_fenetre" for o in f), bool(f), m.fin - m.debut)

    prof = e["profondeur_m"] * 1000
    for m in sorted(murs, key=rang, reverse=True):
        longueur_mur = m.fin - m.debut
        long_ = e["part"] * longueur_mur
        f = sorted(fenetres(m), key=lambda o: o.type != "porte_fenetre")
        if f:
            long_ = max(long_, f[0].u1 - f[0].u0 + 400)
            centre = (f[0].u0 + f[0].u1) / 2
        else:
            centre = m.debut + e["position"] * longueur_mur
        long_ = min(long_, longueur_mur)
        u0 = min(max(centre - long_ / 2, m.debut), m.fin - long_)
        face = m.axe + dehors * m.epaisseur / 2
        r = Rect(face, u0, face + prof, u0 + long_) if droite else Rect(u0, face - prof, u0 + long_, face)
        if all(r.x1 <= z.x0 + 1 or z.x1 <= r.x0 + 1 or r.y1 <= z.y0 + 1 or z.y1 <= r.y0 + 1 for z in obstacles):
            return r
    return None


def exterieurs(d, rng: random.Random) -> None:
    """Dessiné en premier : rien du logement n'est recouvert, et aucun masque n'est touché, l'extérieur reste du fond."""
    for e, r in places_des_exterieurs(d):
        boite = _boite_px(d, r)
        if e["couleur"]:
            d.d.rectangle(boite, fill=tuple(e["couleur"]))
        _motif_exterieur(d, boite, e, r, rng)
        _contour_exterieur(d, boite, e["contour"])
        _legende_exterieur(d, e, r, boite)


def _motif_exterieur(d, boite, e: dict, r: Rect, rng: random.Random) -> None:
    motif = e["motif"]
    x0, y0, x1, y1 = (round(v) for v in boite)
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    couche = Image.new("L", (w, h), 0)
    c = ImageDraw.Draw(couche)
    s = d.rep.s
    if motif == "lattes":  # fr-084, perpendiculaires au mur
        pas = max(4, round(150 * s))
        if e["cote"] == "bas":
            for k in range(0, w, pas):
                c.line([(k, 0), (k, h)], fill=255)
        else:
            for k in range(0, h, pas):
                c.line([(0, k), (w, k)], fill=255)
    elif motif == "carrelage":  # fr-036, fr-062
        pas = max(8, round(600 * s))
        for k in range(0, w, pas):
            c.line([(k, 0), (k, h)], fill=255)
        for k in range(0, h, pas):
            c.line([(0, k), (w, k)], fill=255)
    elif motif in ("hachures", "croisillons"):  # fr-037
        pas = max(5, round(250 * s))
        for k in range(-h, w, pas):
            c.line([(k, 0), (k + h, h)], fill=255)
            if motif == "croisillons":
                c.line([(k, h), (k + h, 0)], fill=255)
    elif motif == "herbe":  # fr-084 : des touffes semées
        for _ in range(max(6, round((r.x1 - r.x0) * (r.y1 - r.y0) / 1e6 * 2.5))):
            x, y = rng.uniform(8, max(9, w - 8)), rng.uniform(8, max(9, h - 8))
            for dx in (-4, 0, 4):
                c.line([(x, y), (x + dx, y - 7)], fill=255)
    couleur = tuple(min(v + 30, 150) for v in d.style.traits)
    d.image.paste(Image.new("RGB", (w, h), couleur), (x0, y0), couche)
    if e["sorte"] == "jardin":  # des arbres : cercles concentriques
        for _ in range(rng.randint(3, 8)):
            rayon = rng.uniform(300, 700) * s
            if w <= 2 * rayon + 4 or h <= 2 * rayon + 4:
                continue
            cx, cy = rng.uniform(x0 + rayon + 2, x1 - rayon - 2), rng.uniform(y0 + rayon + 2, y1 - rayon - 2)
            for k in (1.0, 0.6, 0.2):
                d.d.ellipse((cx - rayon * k, cy - rayon * k, cx + rayon * k, cy + rayon * k), outline=(90, 130, 80), width=1)


def _contour_exterieur(d, boite, contour: str) -> None:
    st = d.style
    x0, y0, x1, y1 = boite
    if contour == "pointille":  # fr-080 : gros pointillés noirs
        cotes = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        tiret = max(6, round(st.taille_texte * 0.5))
        for (a, b), (e, f) in cotes:
            n = math.hypot(e - a, f - b)
            for k in range(0, int(n), 2 * tiret):
                t0, t1 = k / max(n, 1), min(k + tiret, n) / max(n, 1)
                d.d.line(((a + (e - a) * t0, b + (f - b) * t0), (a + (e - a) * t1, b + (f - b) * t1)), fill=st.textes, width=2)
        return
    if contour == "gris":  # fr-102 : un large trait de la couleur des murs, en plus fin qu'un vrai mur
        d.d.rectangle(boite, outline=st.murs, width=max(2, round(st.px_par_m * 0.05)))
    elif contour == "moyen":  # fr-084
        d.d.rectangle(boite, outline=st.textes, width=2)
    else:
        d.d.rectangle(boite, outline=st.traits, width=1)


def _legende_exterieur(d, e: dict, r: Rect, boite) -> None:
    """« Balcon », et sa surface si le plan a le droit d'écrire des surfaces (fr-112, fr-065 : « Jardin (48 m²) »)."""
    st, l = d.style, d.style.lot2
    nom = {"balcon": "Balcon", "terrasse": "Terrasse", "jardin": "Jardin"}[e["sorte"]]
    if e.get("numero", 1) > 1:
        nom += f" {e['numero']}"
    nom = nom.upper() if l.majuscules else nom
    x0, y0, x1, y1 = boite
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    taille = max(9, round(st.taille_texte * 0.85))
    police = _police(st.police, taille)
    surface = format_surface((r.x1 - r.x0) * (r.y1 - r.y0) / 1e6, l) if st.surfaces and not l.noms_courts else ""
    if surface and police.getlength(surface) < (x1 - x0) * 0.9 and y1 - y0 > taille * 3:
        cy -= taille * 0.65
        _ecrire_exterieur(d, (cx, cy + taille * 1.3), surface, taille, "mesure")
    if police.getlength(nom) < (x1 - x0) * 0.9 and y1 - y0 > taille * 1.4:
        _ecrire_exterieur(d, (cx, cy), nom, taille, "nom")
    if st.cotes and l.cotes_interieures and x1 - x0 > 120 and y1 - y0 > 90:
        # fr-036 : la terrasse a aussi ses cotes, dans l'unité du plan.
        t = max(9, round(st.taille_texte * l.taille_cotes))
        couleur, ligne = _couleurs_cotes(d)
        _cote_fine(d, (x0 + 1, y1 - t), (x1 - 1, y1 - t), True, texte_cote(r.x1 - r.x0, l), t, couleur, ligne)
        _cote_fine(d, (x1 - t, y0 + 1), (x1 - t, y1 - 1), False, texte_cote(r.y1 - r.y0, l), t, couleur, ligne)


def _ecrire_exterieur(d, xy, texte: str, taille: int, sorte: str) -> None:
    st, l = d.style, d.style.lot2
    if _a_la_main(l, sorte):
        texte_main(d, xy, texte, taille, l.couleur_stylo, d.hasard_lot2)
    else:
        d.texte(xy, texte, taille, st.textes)


# ---------------------------------------------------------------- trait 10 : la page vue à l'écran


def _verso(h: int, w: int, rng: random.Random) -> np.ndarray:
    """Le texte du verso qui transparaît (fr-024) : des lignes de mots très floues, dont il ne reste qu'une ombre. 0 à 1."""
    pas = rng.randint(max(14, h // 45), max(20, h // 25))
    calque = Image.new("L", (w, h), 0)
    dessin = ImageDraw.Draw(calque)
    for y in range(rng.randint(0, pas), h, pas):
        if rng.random() < 0.25:
            continue
        x, fin = rng.randint(0, w // 6), rng.randint(w // 2, w)
        while x < fin:
            mot = rng.randint(pas, 5 * pas)
            dessin.rectangle((x, y, x + mot, y + max(2, pas // 3)), fill=255)
            x += mot + rng.randint(pas // 3, pas)
    return np.asarray(calque.filter(ImageFilter.GaussianBlur(pas / 3)), np.float32) / 255


def ecran_pixels(image: np.ndarray, semantique: np.ndarray, l: Lot2, rng: random.Random) -> np.ndarray:
    """La page vue à l'écran, sans --photo-realiste : verso, reflet doux, coins assombris, bord noir de l'écran.

    Pixels seulement. Le bord reste dans les marges, comme V.capture : posé sur le logement, il cacherait des murs que le masque
    affirme. `rng` a la même clé pour le plan et le plan sans mobilier : ils se regardent sur le même écran."""
    h, w = image.shape[:2]
    img = image.astype(np.float32)
    img *= 1 - rng.uniform(0.03, 0.09) * _verso(h, w, rng)[:, :, None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if rng.random() < 0.6:
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        rx, ry = rng.uniform(0.15, 0.4) * w, rng.uniform(0.1, 0.3) * h
        reflet = rng.uniform(0.12, 0.35) * np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2))
        img = img * (1 - reflet[:, :, None]) + 250 * reflet[:, :, None]
    rayon = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    img *= (1 - rng.uniform(0.04, 0.16) * np.clip(rayon - 0.5, 0, None) ** 2)[:, :, None]
    sortie = np.clip(img, 0, 255).astype(np.uint8)
    if not l.ecran_bordure:
        return sortie
    ys, xs = np.nonzero(semantique)
    haut, bas, gauche, droite = (ys.min(), h - 1 - ys.max(), xs.min(), w - 1 - xs.max()) if len(ys) else (h // 10, h // 10, w // 10, w // 10)
    noir = rng.randint(0, 14)
    for cote in rng.sample(("haut", "bas", "gauche", "droite"), rng.randint(1, 4)):
        e = rng.uniform(0.02, 0.06) * (h if cote in ("haut", "bas") else w)
        e = int(min(e, {"haut": haut, "bas": bas, "gauche": gauche, "droite": droite}[cote] - 3))
        if e <= 0:
            continue
        if cote == "haut":
            sortie[:e] = noir
        elif cote == "bas":
            sortie[h - e:] = noir
        elif cote == "gauche":
            sortie[:, :e] = noir
        else:
            sortie[:, w - e:] = noir
    return sortie


# ---------------------------------------------------------------- traits 12 et 13 : plusieurs blocs sur une image


TITRES_NIVEAUX = (("Rez-de-chaussée", "1er étage"), ("Rez de chaussée", "Étage"), ("RDC", "R+1"), ("Niveau 0", "Niveau 1"),
                  ("Rez de jardin", "1er étage"), ("1er étage", "2ème étage"), ("Rez de chaussée", "1er étage"))
TEXTES_PALIER = ("Palier", "Palier", "Palier d'étage", "Circulation", "Parties communes")


@dataclass
class Composition:
    """Un logement assemblé à un seul niveau, et ce qu'il faut pour l'écrire."""

    log: LogementGenere
    compose: str
    disposition: str
    blocs: list[dict]
    palier: dict | None = None
    titres_place: str = ""
    titre_tirets: bool = False
    titre_surface: bool = False
    filet: bool = False


def cadre_du_niveau(niv: Niveau) -> Rect:
    """Le cadre extérieur en mm, murs en biais compris (tous les nombres d'un Rect sont entiers)."""
    rects = [rect_du_mur(m) for m in niv.murs]
    xs = [r.x0 for r in rects] + [r.x1 for r in rects] + [q[0] for m in niv.murs_libres for q in m.polygone]
    ys = [r.y0 for r in rects] + [r.y1 for r in rects] + [q[1] for m in niv.murs_libres for q in m.polygone]
    return Rect(math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys)))


def _translater(niv: Niveau, dx: int, dy: int) -> None:
    for p in niv.pieces:
        r = p.rect
        p.rect = Rect(r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy)
        if p.contour:
            p.contour = [(x + dx, y + dy) for x, y in p.contour]
        p.interdits = [Rect(z.x0 + dx, z.y0 + dy, z.x1 + dx, z.y1 + dy) for z in p.interdits]
    for m in niv.murs:
        m.axe += dx if m.vertical else dy
        d = dy if m.vertical else dx
        m.debut, m.fin = m.debut + d, m.fin + d
    for m in niv.murs_libres:
        m.axe = [(x + dx, y + dy) for x, y in m.axe]
        m.polygone = [(x + dx, y + dy) for x, y in m.polygone]
    for o in niv.ouvertures:  # repérée le long de son mur, qui vient de glisser d'autant
        d = dy if o.mur.vertical else dx
        o.u0, o.u1 = o.u0 + d, o.u1 + d
    niv.coins = [(x + dx, y + dy) for x, y in niv.coins]


def _symetrie(niv: Niveau, n: int) -> None:
    """Une des 8 symétries (mêmes bits que logements._transformer), murs en biais et coins coupés compris, ce que
    _transformer ne sait pas faire : il tourne avant couper_angles, alors qu'ici le logement peut déjà être coupé."""
    if not n:
        return
    echange, mx, my = bool(n & 1), bool(n & 2), bool(n & 4)
    _transformer(niv, 0, 0, n)  # x → -x, y → -y selon les bits : le cadre est ramené ensuite, par _normaliser

    def f(x: float, y: float) -> tuple[float, float]:
        if echange:
            x, y = y, x
        return (-x if mx else x), (-y if my else y)

    inverse = echange != (mx != my)  # le même test que _transformer : garde le contour dans le sens direct
    for p in niv.pieces:
        if p.contour:
            p.contour = [f(x, y) for x, y in p.contour]
            if inverse:
                p.contour.reverse()
        zones = []
        for z in p.interdits:
            (a, b), (c, e) = f(z.x0, z.y0), f(z.x1, z.y1)
            zones.append(Rect(int(min(a, c)), int(min(b, e)), int(max(a, c)), int(max(b, e))))
        p.interdits = zones
    for m in niv.murs:
        if (my if m.vertical else mx):  # le mur est parcouru à l'envers : ses bouts s'échangent
            m.coupe_debut, m.coupe_fin = m.coupe_fin, m.coupe_debut
    for m in niv.murs_libres:
        m.axe = [f(x, y) for x, y in m.axe]
        m.polygone = [f(x, y) for x, y in m.polygone]


def _normaliser(niv: Niveau) -> None:
    c = cadre_du_niveau(niv)
    _translater(niv, -c.x0, -c.y0)


def _orienter(niveau: Niveau, dehors: int, mitoyen: bool, rc: random.Random) -> tuple[Niveau, int]:
    """Une copie du niveau, tournée pour présenter sa bonne face à l'autre logement : vers `dehors` (+1 est, -1 ouest).

    Palier : la porte d'entrée donne sur le palier (les deux logements s'y font face). Mitoyen : c'est le contraire, un mur
    mitoyen n'a ni porte ni fenêtre. Renvoie aussi le score : 100 ou plus dit que la porte reste du mauvais côté."""
    ordre = list(range(8))
    rc.shuffle(ordre)
    meilleur, score_min = None, None
    for n in ordre:
        c = copy.deepcopy(niveau)
        _symetrie(c, n)
        _normaliser(c)
        bord = cadre_du_niveau(c).x1 if dehors > 0 else 0
        sur_la_face = [o for o in c.ouvertures if o.mur.vertical and o.mur.dehors == dehors]
        if mitoyen:
            contact = [o for o in sur_la_face if (rect_du_mur(o.mur).x1 if dehors > 0 else rect_du_mur(o.mur).x0) == bord]
            score = (100 if any(o.sous_type == "porte_entree" for o in contact) else 0) + len(contact)
        else:
            score = 0 if any(o.sous_type == "porte_entree" for o in sur_la_face) else 1
        if score_min is None or score < score_min:
            meilleur, score_min = c, score
    return meilleur, score_min


def _sans_ouverture_au_contact(niv: Niveau, autre: Rect, contact: float, dehors: int) -> None:
    """Une fenêtre qui donne sur le voisin n'existe pas : elle est rebouchée. La pièce peut y perdre sa fenêtre, mais la
    vérité reste exacte, puisque le mur est plein sur l'image et dans le masque."""
    def bouche(o) -> bool:
        m = o.mur
        if not m.vertical or m.dehors != dehors or (rect_du_mur(m).x1 if dehors > 0 else rect_du_mur(m).x0) != contact:
            return False
        return o.u0 < autre.y1 and autre.y0 < o.u1
    niv.ouvertures = [o for o in niv.ouvertures if not bouche(o)]


def _suffixer(niv: Niveau, suffixe: str) -> None:
    """Identifiants distincts d'un bloc à l'autre. « chambre_n1 » (étage d'un duplex) le reste, sans redoubler le suffixe."""
    for e in [*niv.pieces, *niv.murs, *niv.murs_libres, *niv.ouvertures]:
        if not e.id.endswith(suffixe):
            e.id += suffixe


def assembler(log: LogementGenere, sources: list[tuple[Niveau, int, int, str]], titres: list[str] | None = None,
              hsp: int | None = None) -> tuple[LogementGenere, list[dict]]:
    """Un logement à UN seul niveau, fait des `sources` : (niveau, dx, dy, suffixe des identifiants).

    Chaque source est copiée : les niveaux du logement d'origine, déjà écrits sur le disque, ne bougent pas. L'index 0 fait que
    `rendre`, `valider_dossier` et le banc y voient un exemple ordinaire. `coins` n'est qu'une boîte (il sert à `signature`) : le
    vrai contour de chaque bloc est dans `blocs`."""
    pieces, murs, ouvertures, libres, blocs = [], [], [], [], []
    for k, (niveau, dx, dy, suffixe) in enumerate(sources):
        c = copy.deepcopy(niveau)  # une seule copie : chaque ouverture y garde son mur (même objet)
        _translater(c, dx, dy)
        _suffixer(c, suffixe)
        cadre = cadre_du_niveau(c)
        blocs.append({"titre": titres[k] if titres else "", "cadre": [cadre.x0, cadre.y0, cadre.x1, cadre.y1],
                      "pieces": [p.id for p in c.pieces], "surface": round(sum(surface_piece(p) for p in c.pieces) / 1e6, 2),
                      "coins": [list(q) for q in c.coins]})
        pieces += c.pieces
        murs += c.murs
        ouvertures += c.ouvertures
        libres += c.murs_libres
    x0, y0 = min(p.rect.x0 for p in pieces), min(p.rect.y0 for p in pieces)
    x1, y1 = max(p.rect.x1 for p in pieces), max(p.rect.y1 for p in pieces)
    hauteur = hsp if hsp is not None else max(n[0].hsp for n in sources)  # le plus haut : aucune ouverture ne dépasse le plafond
    niveau = Niveau(index=0, coins=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], pieces=pieces, murs=murs, ouvertures=ouvertures,
                    z_sol=0, hsp=hauteur, murs_libres=libres)
    return dataclasses.replace(log, niveaux=[niveau], hsp=hauteur), blocs


def _titres_niveaux(l: Lot2, rc: random.Random) -> list[str]:
    if l.famille == "agence_coloree":
        return ["Niveau 0", "Niveau 1"]  # fr-075
    return list(rc.choice(TITRES_NIVEAUX))


def _titres_logements(log, log_b, rc: random.Random) -> list[str]:
    if rc.random() < 0.5:
        n = rc.randint(10, 80)
        return [f"Lot {n}", f"Lot {n + 1}"]
    return [f"{log.type} A", f"{log_b.type} B"]


def _ecart_mm(style, rc: random.Random, a_titres: bool) -> int:
    """Le vide entre deux blocs : 1,5 à 3 m comme sur fr-025, fr-118, fr-119, et assez pour le titre et les chaînes de cotes."""
    t = style.taille_texte
    besoin = 2.8 * t if a_titres else 0.0
    if style.cotes and not style.lot2.sans_chaines:
        besoin += RECUL_COTE + 2 * t  # la chaîne du bloc d'en bas
        if style.cotes_partielles:
            besoin += RECUL_COTE + 2 * t  # et celle du bloc d'en haut
    return round(max(rc.uniform(1500, 3000), (besoin + 2 * t) / style.px_par_m * 1000))


def _decalage(rc: random.Random, a: int, b: int) -> tuple[int, int]:
    """Où poser deux longueurs a et b l'une par rapport à l'autre : même début, même milieu ou même fin."""
    place = rc.choice(("debut", "milieu", "fin"))
    grand = max(a, b)
    return {"debut": (0, 0), "milieu": ((grand - a) // 2, (grand - b) // 2), "fin": (grand - a, grand - b)}[place]


def composer(log: LogementGenere, log_b: LogementGenere | None, compose: str, disposition: str, style, rc: random.Random) -> Composition:
    """Traits 12 et 13. `log_b` : le second logement (deux logements, ou plain-pied empilé) ; None pour un duplex.

    Tout le hasard vient de `rc` (clé « lot2-compose-<graine> ») : le style, lui, doit rester celui du plan d'origine."""
    l = style.lot2
    place = "bas" if l.famille == "agence_coloree" else "haut"  # fr-075 ; fr-025, fr-072 écrivent au-dessus
    if rc.random() < (0.7 if l.triangles else 0.15):
        place = ""  # fr-118, fr-119 : les relevés d'appli n'écrivent rien entre les niveaux
    if place == "bas" and style.echelle_graphique:
        place = "haut"  # la barre d'échelle passe sous le plan
    tirets = rc.random() < 0.25  # fr-025, fr-072
    surface = rc.random() < 0.2 and bool(style.surfaces)  # fr-120
    if compose == "deux_logements":
        return _composer_logements(log, log_b, disposition, style, rc, place, surface)
    a, b = (log.niveaux[0], log.niveaux[1]) if log.duplex else (log.niveaux[0], log_b.niveaux[0])
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    _normaliser(a)
    _normaliser(b)
    ca, cb = cadre_du_niveau(a), cadre_du_niveau(b)
    ecart = _ecart_mm(style, rc, bool(place))
    filet = False
    if disposition == "cote_a_cote":
        da, db = _decalage(rc, ca.hauteur, cb.hauteur)
        sources = [(a, 0, da, "_n0"), (b, ca.largeur + ecart, db, "_n1")]
    else:
        da, db = _decalage(rc, ca.largeur, cb.largeur)
        filet = rc.random() < 0.2  # fr-072
        if filet:
            ecart += round(style.taille_texte * 1.5 / style.px_par_m * 1000)
        if rc.random() < 0.75:  # le rez-de-chaussée en haut : fr-025, fr-072, fr-075, fr-120
            sources = [(a, da, cb.hauteur + ecart, "_n0"), (b, db, 0, "_n1")]
        else:
            sources = [(a, da, 0, "_n0"), (b, db, ca.hauteur + ecart, "_n1")]
    assemble, blocs = assembler(log, sources, _titres_niveaux(l, rc) if place else None)
    return Composition(assemble, "niveaux", disposition, blocs, None, place, tirets and bool(place), surface and bool(place), filet)


def _composer_logements(log, log_b, disposition, style, rc, place, surface) -> Composition:
    """Trait 13. Fabriqué de toutes pièces, comme le demande le catalogue : aucun plan ne sert de modèle (les deux qui
    montrent le cas sont à l'examen). Palier : un vide de fond, et les portes d'entrée s'y font face. Mitoyen : les deux murs
    extérieurs accolés, deux éléments et une même classe, sans ouverture au contact."""
    mitoyen = disposition == "mitoyen"
    a, score_a = _orienter(log.niveaux[0], 1, mitoyen, rc)
    b, score_b = _orienter(log_b.niveaux[0], -1, mitoyen, rc)
    if mitoyen and (score_a >= 100 or score_b >= 100):  # la porte d'entrée ne peut pas donner sur le mur du voisin
        mitoyen, disposition = False, "palier"
        a, _ = _orienter(log.niveaux[0], 1, False, rc)
        b, _ = _orienter(log_b.niveaux[0], -1, False, rc)
    # Les étiquettes (M_est…) doivent dire ce qu'on voit après la symétrie.
    _nommer(dataclasses.replace(log, niveaux=[a]))
    _nommer(dataclasses.replace(log_b, niveaux=[b]))
    ca, cb = cadre_du_niveau(a), cadre_du_niveau(b)
    da, db = _decalage(rc, ca.hauteur, cb.hauteur)
    ecart = 0 if mitoyen else round(max(rc.uniform(1200, 2500), 3.2 * style.taille_texte / style.px_par_m * 1000))
    _translater(a, 0, da)
    _translater(b, ca.largeur + ecart, db)
    palier = None
    if mitoyen:
        contact = ca.largeur
        _sans_ouverture_au_contact(a, cadre_du_niveau(b), contact, 1)
        _sans_ouverture_au_contact(b, cadre_du_niveau(a), contact, -1)
    else:
        y0, y1 = max(da, db), min(da + ca.hauteur, db + cb.hauteur)
        palier = {"cadre": [ca.largeur, y0, ca.largeur + ecart, y1], "texte": rc.choice(TEXTES_PALIER)}
    assemble, blocs = assembler(log, [(a, 0, 0, "_a"), (b, 0, 0, "_b")], _titres_logements(log, log_b, rc) if place else None)
    return Composition(assemble, "deux_logements", disposition, blocs, palier, place, False, surface and bool(place))


def vers_ensemble(style, c: Composition) -> None:
    """Le style du plan d'origine, adapté à l'ensemble. Ce qui parlait d'UN niveau ou prenait la marge que réclament les titres s'efface ;
    le reste (couleurs, écriture, cotes) ne change pas, pour que l'ensemble ait le style de son plan."""
    style.lot2 = dataclasses.replace(style.lot2, composition=c.compose, disposition=c.disposition, blocs=c.blocs, palier=c.palier,
                                     titres_place=c.titres_place, titre_tirets=c.titre_tirets, titre_surface=c.titre_surface,
                                     filet=c.filet, legende_niveau=False, numero_lot="", echelle_ecrite="", recadre=False,
                                     placards_fleches=False)  # la flèche traverserait tout l'autre bloc
    style.titre = False


def vides_entre_blocs(blocs: list[dict]) -> list[Rect]:
    """La bande vide entre deux blocs, en mm (mitoyen : aucune)."""
    a, b = blocs[0]["cadre"], blocs[1]["cadre"]
    x0, y0, x1, y1 = min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])
    if a[2] < b[0] or b[2] < a[0]:
        return [Rect(min(a[2], b[2]), y0, max(a[0], b[0]), y1)]
    if a[3] < b[1] or b[3] < a[1]:
        return [Rect(x0, min(a[3], b[3]), x1, max(a[1], b[1]))]
    return []


def retrait_du_titre(style, place: str) -> float:
    """Du mur au milieu du titre, en pixels : au-delà de la chaîne de cotes s'il y en a une de ce côté."""
    t = style.taille_texte
    chaine = style.cotes and not style.lot2.sans_chaines and (place == "haut" or style.cotes_partielles)
    return RECUL_COTE + 14 + 2 * t if chaine else 1.5 * t


def titres_des_blocs(d) -> None:
    """« Rez-de-chaussée », « Lot 12 » : au-dessus (fr-025, fr-072) ou en dessous (fr-075, fr-120) de chaque bloc. Du fond pour le masque."""
    st, l = d.style, d.style.lot2
    if not l.titres_place:
        return
    t = round(st.taille_texte * 1.05)
    for b in l.blocs:
        texte = b["titre"].upper() if l.majuscules else b["titre"]
        if not texte:
            continue
        if l.titre_surface and st.surfaces:
            texte += f" {b['surface']:.0f} m²"
        if l.titre_tirets:
            texte = f"----- {texte} -----"
        x0, y0, x1, y1 = b["cadre"]
        x = (d.px(x0, 0)[0] + d.px(x1, 0)[0]) / 2
        if l.titres_place == "haut":
            y = d.px(0, y1)[1] - retrait_du_titre(st, "haut")
        else:
            y = d.px(0, y0)[1] + retrait_du_titre(st, "bas")
        _ecrire(d, (x, y), texte, t, st.textes, gras=l.noms_gras or l.titre_tirets)


def filet_entre_blocs(d) -> None:
    """fr-072 : un trait sur toute la largeur, entre les deux niveaux, à l'écart du titre."""
    st, l = d.style, d.style.lot2
    vides = vides_entre_blocs(l.blocs)
    if not vides or vides[0].largeur < vides[0].hauteur:
        return
    haut_px, bas_px = d.px(0, vides[0].y1)[1], d.px(0, vides[0].y0)[1]
    if l.titres_place == "haut":
        bas_px -= retrait_du_titre(st, "haut") + st.taille_texte
    elif l.titres_place == "bas":
        haut_px += retrait_du_titre(st, "bas") + st.taille_texte
    y = (haut_px + bas_px) / 2
    d.d.line(((d.px(d.rep.xmin, 0)[0], y), (d.px(d.rep.xmax, 0)[0], y)), fill=st.traits, width=max(1, d.fin))


def palier_ecrit(d) -> None:
    """« Palier » dans le vide entre deux logements. Écrit seulement : ce vide est du fond, sur l'image comme dans le masque."""
    st, l = d.style, d.style.lot2
    x0, y0, x1, y1 = l.palier["cadre"]
    cx, cy = d.px((x0 + x1) / 2, (y0 + y1) / 2)
    texte = l.palier["texte"].upper() if l.majuscules else l.palier["texte"]
    taille = max(9, round(st.taille_texte * 0.85))
    longueur = _police(st.police, taille).getlength(texte)
    largeur_px, hauteur_px = (x1 - x0) * d.rep.s, (y1 - y0) * d.rep.s
    if longueur < largeur_px * 0.9:
        d.texte((cx, cy), texte, taille, st.textes)
    elif longueur < hauteur_px * 0.9:
        d.texte((cx, cy), texte, taille, st.textes, vertical=True)


def cotes_des_blocs(d) -> None:
    """fr-072 : chaque niveau a ses chaînes de cotes, autour de lui. Une chaîne autour de l'image entière mesurerait du vide.

    Un côté n'a pas de chaîne si l'autre bloc est trop près pour la loger : deux logements mitoyens, un palier étroit."""
    st, l = d.style, d.style.lot2
    place_mm = (RECUL_COTE + 2 * st.taille_texte) / d.rep.s
    for k, b in enumerate(l.blocs):
        pieces = [p.rect for p in d.niv.pieces if p.id in b["pieces"]]
        x0, y0 = min(p.x0 for p in pieces), min(p.y0 for p in pieces)
        x1, y1 = max(p.x1 for p in pieces), max(p.y1 for p in pieces)
        gx0, gy0, gx1, gy1 = b["cadre"]
        ox0, oy0, ox1, oy1 = l.blocs[1 - k]["cadre"]
        recouvre_x, recouvre_y = gx0 < ox1 and ox0 < gx1, gy0 < oy1 and oy0 < gy1
        haut = not (recouvre_x and 0 <= oy0 - gy1 < place_mm)
        bas = not (recouvre_x and 0 <= gy0 - oy1 < place_mm)
        gauche = not (recouvre_y and 0 <= gx0 - ox1 < place_mm)
        droite = not (recouvre_y and 0 <= ox0 - gx1 < place_mm)
        if haut:
            d.chaine([(x0, x1)], d.px(0, gy1)[1] - RECUL_COTE, True, -1)
        if gauche:
            d.chaine([(y0, y1)], d.px(gx0, 0)[0] - RECUL_COTE, False, -1)
        if st.cotes_partielles:
            en_bas = sorted((p.x0, p.x1) for p in pieces if p.y0 == y0)
            a_droite = sorted((p.y0, p.y1) for p in pieces if p.x1 == x1)
            if bas and len(en_bas) > 1:
                d.chaine(en_bas, d.px(0, gy0)[1] + RECUL_COTE, True, 1)
            if droite and len(a_droite) > 1:
                d.chaine(a_droite, d.px(gx1, 0)[0] + RECUL_COTE, False, 1)
