"""Tests des proportions retrouvées par l'optique sur une photo de biais sans cotes (étape 6-14) :
moteur/redressement.py (rapport_par_optique), le générateur « vraie caméra » et echelle_plan.decider."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from moteur.echelle_plan import decider
from moteur.generateur.exportateur import Options, style_pour
from moteur.generateur.logements import generer
from moteur.generateur.rendu import _vue_par_camera, rendre
from moteur.redressement import (FOCALE_TELEPHONE, corriger_proportions, estimer_redressement, focale_par_fuite, lire_focale,
                                 photo_entiere, rapport_par_optique)
from tests.test_coloriage import coloriage_t2
from tests.test_redressement import echelles


def photo_par_camera(c: np.ndarray, inclinaison: tuple[float, float], focale_photo: float = 0.77):
    """La page `c` photographiée par un téléphone penché, photo non recadrée (son centre = l'axe de l'objectif)."""
    h, w = c.shape
    coins = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    cam = SimpleNamespace(focale=1.1, inclinaison=inclinaison, centre_optique=(0.0, 0.0))
    vus = _vue_par_camera(coins, (w / 2, h / 2), max(w, h), cam)
    demi = np.abs(vus - (w / 2, h / 2)).max(axis=0)
    demi = np.maximum(demi, demi * (1.1 * max(w, h) / focale_photo / 2) / demi.max())
    vus = np.float32(vus - (w / 2, h / 2) + demi)
    taille = (int(round(2 * demi[0])), int(round(2 * demi[1])))
    W = cv2.getPerspectiveTransform(coins, vus).astype(np.float64)
    return cv2.warpPerspective(c, W, taille, flags=cv2.INTER_NEAREST), W, 1.1 * max(w, h)


def test_proportions_retrouvees_par_l_optique():
    """Page penchée dans les deux sens : la focale se calcule sur la photo et les proportions reviennent à ~1 %."""
    vue, W, f = photo_par_camera(coloriage_t2(), (22.0, 12.0))
    r = estimer_redressement(vue)
    assert r is not None and r.de_biais
    sx, sy = echelles(r.H @ W, 420, 320)
    assert abs(sx / sy - 1) > 0.03  # sans rien faire, la photo écrase le plan de plus de 3 %
    assert focale_par_fuite(r, vue.shape) == pytest.approx(f, rel=0.08)
    assert rapport_par_optique(r, vue.shape) == pytest.approx(sx / sy, rel=0.01)
    r2 = corriger_proportions(r, rapport_par_optique(r, vue.shape))
    sx2, sy2 = echelles(r2.H @ W, 420, 320)
    assert sx2 / sy2 == pytest.approx(1.0, abs=0.01)


def test_une_seule_inclinaison_focale_du_telephone():
    """Téléphone penché vers l'avant seulement : la photo ne dit pas sa focale, on prend celle d'un téléphone."""
    vue, W, f = photo_par_camera(coloriage_t2(), (24.0, 0.0))
    r = estimer_redressement(vue)
    assert r is not None and r.de_biais
    assert lire_focale(r, vue.shape) == (None, "un seul sens")
    assert f / max(vue.shape) == pytest.approx(FOCALE_TELEPHONE, rel=0.02)
    sx, sy = echelles(r.H @ W, 420, 320)
    assert abs(sx / sy - 1) > 0.03
    assert rapport_par_optique(r, vue.shape) == pytest.approx(sx / sy, rel=0.015)


def test_photo_recadree_reconnue():
    """Une photo de téléphone entière est au format 4:3 ou 16:9 ; recadrée sur la page, elle ne l'est presque jamais."""
    assert photo_entiere(4032, 3024) and photo_entiere(3024, 4032) and photo_entiere(1920, 1080) and photo_entiere(1001, 750)
    assert not photo_entiere(4000, 2900) and not photo_entiere(1197, 870)


def test_barre_et_surfaces_utilisables_sur_photo_aux_proportions_retrouvees():
    interieur = (600, 400)
    assert decider(None, None, False, None, None, interieur, True, 100.0) == (100.0, None, "barre")
    assert decider(None, None, False, None, None, interieur, True, 100.0, None, True) == (100.0, 100.0, "barre")
    assert decider(None, None, False, None, None, interieur, True, None, 100.0)[2] == "à vérifier"
    assert decider(None, None, False, None, None, interieur, True, None, 100.0, True) == (100.0, 100.0, "surfaces")
    assert decider(None, None, False, None, None, interieur, True, 80.0, 100.0, True)[2] == "à vérifier"  # en désaccord


def test_generateur_vraie_camera_sans_cotes():
    """Les options --vraie-camera et --sans-cotes : style tiré à part, photo centrée sur l'axe de l'objectif."""
    opt = Options(familles=["photo"], vraie_camera=True, sans_cotes=True)
    style = style_pour(7, 0, opt)
    assert style.focale > 0 and 0.72 <= style.focale_photo <= 0.82 and not style.cotes
    ancien = style_pour(7, 0, Options(familles=["photo"]))
    assert ancien.focale == 0 and ancien.cotes and ancien.rotation == style.rotation  # les anciens jeux ne changent pas
    log = generer(2)
    rendu = rendre(log, log.niveaux[0], style)
    image = rendu.annotations["image"]
    assert not image["a_plat"] and photo_entiere(image["largeur"], image["hauteur"])
    pieces = rendu.images["masque_pieces"]
    for p in rendu.annotations["pieces"]:
        cx, cy = np.array(p["polygone_px"], np.float32).mean(axis=0)
        assert pieces[int(round(cy)), int(round(cx))] == p["valeur_masque"], p["id"]


def test_garde_fous_photo_coloriage_douteux():
    """Rapport optique extrême ou échelle loin de celle des portes : la photo part à la vérification."""
    from moteur.redressement import rapport_plausible
    assert rapport_plausible(1.09) and rapport_plausible(0.92) and not rapport_plausible(1.16)
    interieur = (600, 400)
    assert decider(None, None, False, None, None, interieur, True, None, 100.0, True, 90.0)[2] == "surfaces"
    assert decider(None, None, False, None, None, interieur, True, None, 160.0, True, 100.0)[2] == "à vérifier"
    assert decider(None, None, False, None, None, interieur, True, 140.0, None, True, 100.0)[2] == "à vérifier"
    assert decider(None, None, False, None, None, interieur, False, None, 160.0, False, 100.0)[2] == "surfaces"  # à plat : inchangé
