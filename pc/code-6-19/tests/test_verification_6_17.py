"""Moins de photos envoyées en vérification (moteur.echelle_plan, étape 6-17)."""

import numpy as np

from moteur.coloriage import FOND, MUR
from moteur.echelle_plan import coloriage_douteux, decider, sans_taches_au_bord


def _logement(col: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    col[y0:y0 + 6, x0:x1] = col[y1 - 6:y1, x0:x1] = MUR
    col[y0:y1, x0:x0 + 6] = col[y0:y1, x1 - 6:x1] = MUR


def test_tache_au_bord_separee_du_logement_effacee():
    col = np.zeros((600, 800), np.uint8)
    _logement(col, 150, 100, 650, 500)
    col[:6, 20:200] = MUR  # le bord de la feuille, en haut de l'image, colorié en mur
    assert coloriage_douteux(col)
    propre = sans_taches_au_bord(col)
    assert not coloriage_douteux(propre)
    assert (propre[:6, 20:200] == FOND).all()
    assert (propre[100:500, 150:650] == col[100:500, 150:650]).all()  # le logement est gardé tel quel


def test_logement_qui_touche_le_bord_reste_douteux():
    # le logement lui-même colle au bord (coloriage faux, cas des photos de l'essai 4) : rien n'est effacé
    col = np.zeros((600, 800), np.uint8)
    _logement(col, 0, 100, 650, 500)
    assert coloriage_douteux(col)
    assert coloriage_douteux(sans_taches_au_bord(col))


def test_tache_loin_du_bord_gardee():
    col = np.zeros((600, 800), np.uint8)
    _logement(col, 150, 100, 650, 500)
    col[300:306, 700:760] = MUR  # un morceau séparé, mais loin du bord : ce n'est pas la table
    assert (sans_taches_au_bord(col) == col).all()


def test_photo_cotes_un_seul_sens_confirmees_par_la_cote_d_ensemble():
    # cas 050224 : deux cotes horizontales d'accord ; la cote d'ensemble (8,65 m) sur 269 px redonne la même échelle
    r = decider(31.1306, None, True, 8.65, None, (269.0, 205.0), True, None, None, True, 31.325)
    assert r[2] == "cotes" and abs(r[0] - 31.1306) < 1e-6 and r[1] is None


def test_photo_cote_seule_confirmee_par_les_surfaces():
    # cas 050092 : une seule cote, surfaces peu sûres mais d'accord à 0,3 % près
    r = decider(34.2448, None, False, 5.6, None, (192.0, 275.0), True, None, None, True, 37.349, surfaces_lues=34.146)
    assert r[2] == "cotes"
    # sans les surfaces, la cote seule ne suffit pas
    assert decider(34.2448, None, False, 5.6, None, (192.0, 275.0), True, None, None, True, 37.349)[2] == "à vérifier"


def test_photo_cotes_un_seul_sens_fausses_restent_a_verifier():
    # cas 050161 (fausse de 6 %) et 050277 (fausse de 3,4 %) : aucune 2e mesure ne les confirme
    assert decider(45.94, None, True, 3.05, 3.13, (329.0, 287.0), True, None, None, True) == (None, None, "à vérifier")
    r = decider(28.8281, None, True, 24.44, 2.45, (200.0, 300.0), True, None, None, True, 30.723, surfaces_lues=30.064)
    assert r == (None, None, "à vérifier")
