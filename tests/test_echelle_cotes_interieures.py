"""Tests du lecteur d'échelle sur les plans à cotes dans les pièces (lecture_cotes 0.2, echelle_plan 0.12).

Pourquoi : ces plans (promoteurs, fr-090, fr-108, fr-110 ; lot 2 du générateur) donnaient des échelles fausses de −10 à −40 %, jugées
sûres. Les textes sont donnés aux tests (pas d'OCR) : ce qu'on vérifie ici, c'est la mesure des traits et la décision."""

import cv2
import numpy as np
import pytest

from moteur.echelle_plan import _echelle_des_surfaces, _sans_les_dimensions_en_double, decider
from moteur.lecture_cotes import CoteLue, TexteLu, _cotes_en_cm_admises, lire_echelle, valeur_de_cote
from moteur.surfaces_ecrites import SurfaceLue
from tests.test_coloriage import S, coloriage_t2

GRIS = 170  # le gris d'un trait de cote fin sur les plans de promoteur
NOIR = 20


def _texte(t: str, x0: float, y0: float, x1: float, y1: float) -> TexteLu:
    return TexteLu(t, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float), 1.0)


def _h(t: str, cx: float, y: int) -> TexteLu:
    """Un nombre écrit juste au-dessus du trait de la rangée y."""
    return _texte(t, cx - 16, y - 20, cx + 16, y - 4)


def _v(t: str, x: int, cy: float) -> TexteLu:
    """Un nombre écrit debout, juste à gauche du trait de la colonne x."""
    return _texte(t, x - 20, cy - 16, x - 4, cy + 16)


def _pieces(couleur_mur: int = NOIR) -> np.ndarray:
    """Deux pièces côte à côte, à 100 px/m, murs pleins de 20 px : 4,10 × 3,20 m et 4,20 × 3,20 m."""
    g = np.full((560, 1100), 255, np.uint8)
    cv2.rectangle(g, (80, 80), (970, 440), couleur_mur, -1)
    g[100:420, 100:510] = 255
    g[100:420, 530:950] = 255
    return g


def _ligne(g: np.ndarray, p: tuple[int, int], q: tuple[int, int], couleur: int = GRIS) -> None:
    cv2.line(g, p, q, couleur, 1)


def test_un_trait_de_cote_coupe_par_un_autre_garde_sa_vraie_longueur():
    """Le défaut d'origine : dans chaque pièce, le trait de la largeur et celui de la hauteur se croisent près d'un coin. Le croisement
    était pris pour la marque de fin : toutes les cotes étaient trop courtes d'à peu près autant, donc d'accord, donc « sûres »."""
    g = _pieces()
    _ligne(g, (100, 130), (510, 130)), _ligne(g, (470, 100), (470, 420))
    _ligne(g, (530, 390), (950, 390)), _ligne(g, (560, 100), (560, 420))
    textes = [_h("410", 305, 130), _v("320", 470, 260), _h("420", 740, 390), _v("320", 560, 260)]
    e = lire_echelle(g, textes)
    assert e.sure
    assert e.px_par_m == pytest.approx(100, rel=0.015)
    assert len(e.retenues) == 4


def test_un_meuble_ou_une_porte_qui_coupe_le_trait_n_est_pas_sa_fin():
    g = _pieces()
    _ligne(g, (100, 300), (510, 300)), _ligne(g, (530, 300), (950, 300))
    cv2.rectangle(g, (180, 240), (260, 360), 150, 1)  # un meuble, dont le bord coupe le trait de part et d'autre
    cv2.rectangle(g, (780, 240), (860, 360), 150, 1)
    e = lire_echelle(g, [_h("410", 400, 300), _h("420", 650, 300)])
    assert e.px_par_m == pytest.approx(100, rel=0.015)


def test_trait_gris_efface_contre_un_mur_noir_mesure_de_face_a_face():
    """À côté d'un mur noir, le masque des traits efface le trait gris sur 5 à 10 pixels : la cote semblait s'arrêter avant le mur."""
    g = _pieces()
    _ligne(g, (100, 300), (510, 300)), _ligne(g, (530, 300), (950, 300))
    e = lire_echelle(g, [_texte("410", 289, 280, 321, 300), _texte("420", 724, 280, 756, 300)])
    assert e.px_par_m == pytest.approx(100, rel=0.01)


def test_un_mur_plein_arrete_la_cote_a_sa_face_pas_a_son_milieu():
    """Un trait franc qui bute sur un mur plein : la cote intérieure va de face à face. Le milieu du mur l'allongeait d'une épaisseur."""
    g = _pieces()
    _ligne(g, (100, 300), (510, 300), NOIR), _ligne(g, (530, 300), (950, 300), NOIR)
    e = lire_echelle(g, [_h("410", 305, 300), _h("420", 740, 300)])
    assert e.px_par_m == pytest.approx(100, rel=0.01)


def _mur_hachure(g: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> None:
    g[y0:y1, x0:x1] = 255
    for k in range(y0 - (x1 - x0), y1, 6):
        cv2.line(g, (x0, k + (x1 - x0)), (x1, k), 60, 1)
    cv2.rectangle(g, (x0, y0), (x1, y1), 40, 1)


def test_un_mur_hachure_arrete_la_cote_a_sa_face_interieure():
    """Les hachures prolongent la rangée du trait : la face du mur ressemblait à un croisement, et la cote allait jusqu'à la face
    extérieure."""
    g = np.full((460, 1000), 255, np.uint8)
    for x0, x1 in ((70, 100), (510, 540), (950, 980)):
        _mur_hachure(g, x0, x1, 40, 420)
    _ligne(g, (100, 300), (510, 300), 60), _ligne(g, (540, 300), (950, 300), 60)
    e = lire_echelle(g, [_h("410", 305, 300), _h("410", 745, 300)])
    assert e.px_par_m == pytest.approx(100, rel=0.015)


def _chaine(g: np.ndarray, y: int, xs: list[int], attaches: int = 40) -> None:
    """Une chaîne de cotes autour du plan : un trait, et à chaque point une ligne d'attache qui dépasse de part et d'autre."""
    _ligne(g, (xs[0], y), (xs[-1], y), 40)
    for x in xs:
        _ligne(g, (x, y - attaches), (x, y + attaches), 40)
        cv2.line(g, (x - 7, y + 7), (x + 7, y - 7), 40, 2)


def test_une_chaine_de_cotes_reste_coupee_a_ses_marques():
    """Pas de fausse correction : une ligne d'attache qui dépasse des deux côtés reste une marque, car le trait continue au-delà
    pour porter une autre cote, avec son nombre."""
    g = np.full((300, 1000), 255, np.uint8)
    _chaine(g, 150, [100, 400, 650, 900])
    e = lire_echelle(g, [_h("3,00", 250, 150), _h("2,50", 525, 150), _h("2,50", 775, 150)])
    assert e.sure and e.px_par_m == pytest.approx(100, rel=0.01)
    assert sorted(round(c.longueur_px) for c in e.retenues) == [250, 250, 300]


def test_les_marques_courtes_ne_sont_pas_des_croisements():
    """Le style d'origine du générateur : marques de ±9 pixels et barre oblique. Rien ne change."""
    g = np.full((300, 800), 255, np.uint8)
    _chaine(g, 150, [100, 400, 700], attaches=9)
    e = lire_echelle(g, [_h("3,00", 250, 150), _h("3,00", 550, 150)])
    assert e.sure and e.px_par_m == pytest.approx(100, rel=0.01)


def test_une_trainee_de_photocopieuse_au_milieu_du_trait_reste_ignoree():
    g = np.full((500, 800), 255, np.uint8)
    _chaine(g, 250, [100, 400, 700], attaches=9)
    cv2.line(g, (250, 0), (250, 499), 90, 2)  # à gauche du chiffre « 3,00 » de la première cote
    e = lire_echelle(g, [_h("3,00", 300, 250), _h("3,00", 550, 250)])
    assert sorted(round(c.longueur_px) for c in e.retenues) == [300, 300]


def test_les_nombres_d_un_tableau_de_surfaces_ne_sont_pas_des_cotes():
    """Un tableau à bordures : chaque nombre a un trait au-dessus et une bordure de chaque côté. Sans ce filtre : −39 %, jugé sûr."""
    g = np.full((400, 700), 255, np.uint8)
    for y in range(100, 281, 30):
        _ligne(g, (100, y), (420, y), 40)
    for x in (100, 300, 420):
        _ligne(g, (x, 100), (x, 280), 40)
    textes = [_texte(v, 330, 104 + 30 * i, 390, 126 + 30 * i) for i, v in enumerate(("3,36", "3,06", "3,40", "9,28", "4,05", "1,62"))]
    assert lire_echelle(g, textes).px_par_m is None


def test_trois_cotes_dispersees_ne_font_pas_un_tableau():
    g = np.full((600, 800), 255, np.uint8)
    for y in (100, 300, 500):
        _chaine(g, y, [100, 400], attaches=9)
    e = lire_echelle(g, [_h("3,00", 250, 100), _h("3,00", 250, 300), _h("3,00", 250, 500)])
    assert len(e.retenues) == 3


def test_un_entier_qui_commence_par_zero_n_est_pas_une_cote():
    assert valeur_de_cote("098") is None and valeur_de_cote("405") == pytest.approx(4.05) and valeur_de_cote("85") == pytest.approx(0.85)


def _cote_cm(valeur: float, longueur: float) -> CoteLue:
    return CoteLue(valeur, longueur, False, _texte(str(round(valeur * 100)), 0, 0, 30, 15), ((0, 0), (longueur, 0)))


def test_deux_petits_entiers_d_accord_ne_font_pas_une_echelle():
    """Deux fois « 58 » (la fin de « 3,58 » mal lu) sur deux traits de même longueur s'accordaient parfaitement : +222 %."""
    assert _cotes_en_cm_admises([], [_cote_cm(0.58, 207), _cote_cm(0.58, 208)]) == []
    # Avec une vraie cote d'au moins un mètre, un petit entier d'accord compte, celui qui ne s'accorde pas est écarté.
    gardees = _cotes_en_cm_admises([], [_cote_cm(2.40, 240), _cote_cm(0.90, 90), _cote_cm(0.35, 292)])
    assert [c.valeur for c in gardees] == [2.40, 0.90]


def test_cotes_contradictoires_ne_passent_pas_par_la_cote_d_ensemble():
    """Le secours « cote d'ensemble » rapporte la plus grande cote lue au logement colorié. Si les cotes se contredisent, elle ne vaut
    rien : c'est lire_echelle_plan qui le retire (+86 % sur le plan fabriqué 80362, deux pièces prises pour le logement entier)."""
    from moteur.echelle_plan import lire_echelle_plan

    col = coloriage_t2()
    g = cv2.resize(np.where(col == 1, 30, 255).astype(np.uint8), None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    # Trois cotes franchement fausses contre une seule d'accord : contredite.
    x0, x1, y = 240, 1440, 140
    for k, (t, fin) in enumerate((("6,00", x1), ("3,00", x1), ("2,00", x1), ("1,00", x1))):
        yy = y - 30 * k
        cv2.line(g, (x0, yy), (fin, yy), 40, 1)
        for x in (x0, fin):
            cv2.line(g, (x, yy - 9), (x, yy + 9), 40, 1)
    # Décalés pour ne pas former une colonne de tableau.
    textes = [_texte(t, 500 + 150 * k, 140 - 30 * k - 24, 570 + 150 * k, 140 - 30 * k - 4) for k, t in enumerate(("6,00", "3,00", "2,00", "1,00"))]
    e = lire_echelle_plan(g, col, textes=textes, px_par_pt=None)
    assert e.contredite and e.cote_max_largeur is None and e.cote_max_hauteur is None
    assert e.decision(False)[2] != "cote d'ensemble"


# ---------------------------------------------------------------- les dimensions et la surface, écrites toutes les deux


def test_dimensions_et_surface_dans_la_meme_piece_ne_comptent_qu_une_fois():
    """« 2,95 m × 4,00 m » et « 11,80 m² » dans la même pièce : additionnés, ils donnaient 1/√2 de l'échelle, soit −29,3 %, jugé sûr."""
    col = coloriage_t2()

    def t(texte: str, x: float, y: float) -> TexteLu:
        return _texte(texte, x - 30, y - 6, x + 30, y + 6)

    textes = [t("11,80 m²", 250, 300), t("2,95 m × 4,00 m", 250, 330), t("11,80 m²", 550, 300), t("2,95 m × 4,00 m", 550, 330)]
    r = _echelle_des_surfaces(col, textes, np.eye(3), S)
    assert r.sure and r.px_par_m == pytest.approx(S, rel=0.01)


def test_dimensions_seules_donnent_toujours_une_surface():
    col = coloriage_t2()
    textes = [_texte("2,95 m × 4,00 m", 220, 294, 280, 306), _texte("2,95 m × 4,00 m", 520, 294, 580, 306)]
    r = _echelle_des_surfaces(col, textes, np.eye(3), S)
    assert r.sure and r.px_par_m == pytest.approx(S, rel=0.01)


def test_deux_surfaces_differentes_dans_une_zone_ouverte_s_additionnent_toujours():
    """Séjour et cuisine ouverte sans mur : la somme reste la règle. Seule une redite est retirée."""
    dedans = np.zeros((300, 300), bool)
    dedans[50:250, 50:250] = True
    z = [SurfaceLue(20.0, 100, 100)]
    assert [d.valeur for d in _sans_les_dimensions_en_double([SurfaceLue(9.0, 200, 200)], z, dedans)] == [9.0]
    assert _sans_les_dimensions_en_double([SurfaceLue(19.5, 200, 200)], z, dedans) == []


# ---------------------------------------------------------------- le garde-fou : cotes sûres contre surfaces sûres


def test_cotes_sures_contredites_par_des_surfaces_sures_partent_a_la_verification():
    """Le défaut d'origine, à la décision : des cotes fausses mais d'accord entre elles passaient sans alerte, car les surfaces n'étaient
    comparées qu'à des cotes peu sûres. 80 px/m lus, 100 px/m d'après les surfaces : un humain tranche, on n'en choisit aucune."""
    assert decider(80.0, 80.0, True, None, None, (600, 400), False, None, 100.0) == (None, None, "à vérifier")
    assert decider(100.0, 100.0, True, None, None, (600, 400), False, None, 80.0) == (None, None, "à vérifier")


def test_pas_de_fausse_alerte_quand_cotes_et_surfaces_s_accordent():
    """Écart mesuré entre cotes justes et surfaces sûres : 1,7 % au plus. Le vrai plan fr-110 : 3,4 %."""
    r = decider(100.0, 100.0, True, None, None, (600, 400), False, None, 101.7)
    assert r == (100.0, 100.0, "cotes")
    assert decider(100.0, 100.0, True, None, None, (600, 400), False, None, 96.6)[2] == "cotes"
    assert decider(100.0, 100.0, True, None, None, (600, 400), False, None, 105.0)[2] == "cotes"  # 5 % : encore toléré


def test_des_surfaces_peu_sures_ne_declenchent_pas_le_garde_fou():
    """Plans schématiques (fr-024, fr-029 : −17 à +51 % sur les petites pièces) : des surfaces en désaccord entre elles n'arrivent
    jamais à decider comme surfaces sûres (EchelleLue.decision). Elles ne doivent pas faire tomber des cotes sûres."""
    from moteur.echelle_plan import EchelleLue

    e = EchelleLue(100.0, 100.0, True, surfaces=70.0, surfaces_sure=False, interieur_px=(600.0, 400.0))
    assert e.decision(False)[2] == "cotes"
    e = EchelleLue(100.0, 100.0, True, surfaces=70.0, surfaces_sure=True, interieur_px=(600.0, 400.0))
    assert e.decision(False)[2] == "à vérifier"


def test_le_garde_fou_ne_change_rien_sur_une_photo_de_biais():
    """Sur une photo sans optique, la surface d'une pièce redressée est trop imprécise (jusqu'à 6 %) : elle ne contrôle rien."""
    assert decider(100.0, 100.0, True, None, None, (600, 400), True, None, 80.0)[2] == "cotes"


def test_une_cote_seule_sans_logement_colorie_n_est_controlee_par_rien():
    """Vrai plan d'entraînement fr-066 : une seule cote, mal mesurée (−74 %), et aucun logement colorié pour la contrôler. Elle passait."""
    assert decider(12.04, 12.04, False, 12.26, None, None, False) == (None, None, "à vérifier")
    assert decider(100.0, 100.0, True, None, None, None, False)[2] == "cotes"  # deux cotes d'accord : inchangé
    assert decider(100.0, 100.0, False, 6.0, 4.0, (600, 400), False)[2] == "cotes"  # une cote, mais contrôlée : inchangé
