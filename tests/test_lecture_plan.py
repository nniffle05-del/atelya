"""Tests de la lecture automatique des murs, sur le plan du cas test n°0 et sur des copies abîmées."""

import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from moteur.geometrie import calculer_briques
from moteur.lecture_plan import lire_murs, logement_depuis_lecture
from moteur.logement import Logement, charger_logement

DOSSIER = Path(__file__).parent.parent / "exemples" / "cas-test-00"
ECHELLE = 100  # le plan d'exercice est dessiné à 100 pixels par mètre
TOLERANCE_LONGUEUR = 0.02  # ±2 % : le critère de l'étape 3
TOLERANCE_POSITION = 0.03  # 3 cm
TOLERANCE_EPAISSEUR = 0.015  # 1,5 cm


def _plan():
    return cv2.imread(str(DOSSIER / "plan.png"), cv2.IMREAD_GRAYSCALE)


def _tourner(img, angle):
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=255)


def _jpeg(img, qualite):
    _, donnees = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualite])
    return cv2.imdecode(donnees, cv2.IMREAD_GRAYSCALE)


def _bruit(img, ecart):
    aleatoire = np.random.default_rng(0).normal(0, ecart, img.shape)
    return np.clip(img + aleatoire, 0, 255).astype(np.uint8)


# Chaque copie : (image, échelle en pixels par mètre)
COPIES = {
    "plan d'origine": lambda: (_plan(), ECHELLE),
    "flou": lambda: (cv2.GaussianBlur(_plan(), (5, 5), 0), ECHELLE),
    "JPEG très compressé": lambda: (_jpeg(_plan(), 25), ECHELLE),
    "grain de scan": lambda: (_bruit(_plan(), 25), ECHELLE),
    "scan pâle": lambda: ((_plan() * 0.55 + 100).astype(np.uint8), ECHELLE),
    "de travers de 2°": lambda: (_tourner(_plan(), 2.0), ECHELLE),
    "de travers de -3,5° et compressé": lambda: (_jpeg(_tourner(_plan(), -3.5), 50), ECHELLE),
    "résolution réduite (60 px/m)": lambda: (cv2.resize(_plan(), None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA), 60),
}


def _milieu(m):
    return ((m.debut[0] + m.fin[0]) / 2, (m.debut[1] + m.fin[1]) / 2)


@pytest.mark.parametrize("nom", COPIES)
def test_murs_retrouves(nom):
    image, echelle = COPIES[nom]()
    lecture = lire_murs(image, echelle)
    logement = Logement.model_validate(logement_depuis_lecture(lecture, echelle, "LU"))
    reference = charger_logement(DOSSIER / "logement.json")

    assert len(logement.murs) == len(reference.murs), [m.id for m in logement.murs]
    for ref in reference.murs:
        lu = min(logement.murs, key=lambda m: math.dist(_milieu(m), _milieu(ref)))
        assert math.dist(_milieu(lu), _milieu(ref)) <= TOLERANCE_POSITION, ref.id
        assert abs(lu.longueur - ref.longueur) / ref.longueur <= TOLERANCE_LONGUEUR, ref.id
        assert abs(lu.epaisseur - ref.epaisseur) <= TOLERANCE_EPAISSEUR, ref.id
    calculer_briques(logement)  # les angles se raccordent : le moteur sait le construire


def test_le_plan_de_travers_est_redresse():
    lecture = lire_murs(_tourner(_plan(), 2.0), ECHELLE)
    assert lecture.angle == pytest.approx(-2.0, abs=0.1)


def test_les_portes_et_fenetres_laissent_des_trous():
    """Les 7 ouvertures du plan coupent un mur : ce sont les candidates pour l'étape 3d."""
    lecture = lire_murs(_plan(), ECHELLE)
    assert len(lecture.ouvertures_candidates) == 7


def test_une_image_vide_est_refusee():
    with pytest.raises(ValueError):
        lire_murs(np.full((400, 600), 255, np.uint8), ECHELLE)
