"""Garde-fou « coloriage douteux » de moteur.echelle_plan (étape 6-16)."""

import numpy as np

from moteur.coloriage import MUR
from moteur.echelle_plan import coloriage_douteux, decider


def _logement(col: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    col[y0:y0 + 6, x0:x1] = col[y1 - 6:y1, x0:x1] = MUR
    col[y0:y1, x0:x0 + 6] = col[y0:y1, x1 - 6:x1] = MUR


def test_un_plan_avec_sa_marge_n_est_pas_douteux():
    col = np.zeros((600, 800), np.uint8)
    _logement(col, 150, 100, 650, 500)
    assert not coloriage_douteux(col)


def test_des_murs_colories_jusqu_au_bord_sont_douteux():
    col = np.zeros((600, 800), np.uint8)
    _logement(col, 150, 100, 650, 500)
    col[:, :8] = MUR  # le bord de la table pris pour un mur
    assert coloriage_douteux(col)


def test_un_coloriage_vide_n_est_pas_douteux():
    assert not coloriage_douteux(np.zeros((100, 100), np.uint8))


def test_douteux_envoie_toujours_a_la_verification():
    # des cotes sûres, une barre et des surfaces d'accord : sans le garde-fou, l'échelle serait retenue
    assert decider(100.0, 100.0, True, None, None, None, False)[2] == "cotes"
    assert decider(100.0, 100.0, True, None, None, None, False, 100.0, 100.0, douteux=True) == (None, None, "à vérifier")


def test_photo_optique_largeur_et_hauteur_en_desaccord():
    # proportions déjà vraies (optique) : 32 px/m en largeur et 5,7 en hauteur, une cote a été mal lue (cas 050314)
    assert decider(32.06, 5.68, True, None, None, None, True, proportions_optiques=True) == (None, None, "à vérifier")
    assert decider(32.06, 31.5, True, None, None, None, True, proportions_optiques=True)[2] == "cotes"


def test_photo_optique_surfaces_avant_cotes():
    # cas 050079 : cotes dans un seul sens fausses de 4 %, surfaces sûres justes : les surfaces l'emportent
    assert decider(38.68, None, True, 7.8, None, (316.0, 271.0), True, None, 40.175, True) == (40.175, 40.175, "surfaces")


def test_photo_optique_cotes_dans_un_seul_sens_ecartees():
    # cas 050161 : deux petites cotes horizontales seulement, ni surfaces ni barre → vérification
    assert decider(45.94, None, True, 3.05, 3.13, (329.0, 287.0), True, None, None, True) == (None, None, "à vérifier")
    # la même chose sur un plan à plat reste lue (le cas des photos seulement)
    assert decider(45.94, None, True, 3.05, 3.13, (329.0, 287.0), False)[2] == "cotes"


def test_photo_optique_cotes_fiables_gardees():
    # cotes sûres dans les deux sens, d'accord à moins de 3 % avec les surfaces : on garde les cotes (plus précises)
    r = decider(40.0, 40.4, True, 7.8, 6.7, (316.0, 271.0), True, None, 40.9, True)
    assert r[2] == "cotes" and abs(r[0] - 40.0) < 1e-9
