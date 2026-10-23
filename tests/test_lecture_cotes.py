"""Tests de la lecture automatique de l'échelle (cotes du plan) et de la hauteur sous plafond."""

import math

import numpy as np
import pytest

from moteur.lecture_cotes import TexteLu, lire_echelle, lire_hauteur_sous_plafond, lire_textes
from moteur.lecture_plan import en_gris, lire_plan, logement_depuis_lecture, redresser
from moteur.logement import Logement, charger_logement
from test_lecture_plan import COPIES, DOSSIER, TOLERANCE_LONGUEUR, _milieu, _plan

pytest.importorskip("rapidocr")

TOLERANCE_ECHELLE = 0.01  # ±1 % : le critère de l'étape 3c


@pytest.mark.parametrize("nom", COPIES)
def test_echelle_lue_sur_les_cotes(nom):
    image, attendue = COPIES[nom]()
    gris, _ = redresser(en_gris(image))
    echelle = lire_echelle(gris)
    assert echelle.sure
    assert abs(echelle.px_par_m - attendue) / attendue <= TOLERANCE_ECHELLE
    assert len(echelle.retenues) >= 5  # le plan porte 7 cotes
    assert echelle.hauteur_sous_plafond == 2.50


def test_une_cote_mal_lue_est_ecartee():
    """Si le texte « 3,20 » était lu « 3,80 », cette cote ne doit pas fausser l'échelle."""
    gris = _plan()
    textes = lire_textes(gris)
    for t in textes:
        if t.texte == "3,20":
            t.texte = "3,80"
    echelle = lire_echelle(gris, textes)
    assert [c.texte.texte for c in echelle.ecartees] == ["3,80"]
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)


def test_une_seule_cote_ne_suffit_pas():
    gris = _plan()
    textes = [t for t in lire_textes(gris) if t.texte == "8,00"]
    echelle = lire_echelle(gris, textes)
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)
    assert not echelle.sure  # à faire vérifier par un humain


def test_un_plan_sans_cote_est_signale():
    vide = np.full((400, 600), 255, np.uint8)
    assert lire_echelle(vide).px_par_m is None


@pytest.mark.parametrize(
    "texte, attendu",
    [
        ("Hauteur sous plafond : 2,50 m", 2.50),
        ("HSP 2.70", 2.70),
        ("H.S.P. = 2,45 m", 2.45),
        ("Séjour 25,92 m²", None),
    ],
)
def test_hauteur_sous_plafond(texte, attendu):
    assert lire_hauteur_sous_plafond([TexteLu(texte, np.zeros((4, 2)), 1.0)]) == attendu


@pytest.mark.parametrize("nom", ["plan d'origine", "de travers de -3,5° et compressé", "résolution réduite (60 px/m)"])
def test_plan_lu_sans_rien_donner(nom):
    """Le chemin complet : une image, et rien d'autre, donne les bons murs en mètres."""
    image, _ = COPIES[nom]()
    lecture, echelle = lire_plan(image)
    logement = Logement.model_validate(
        logement_depuis_lecture(lecture, echelle.px_par_m, "LU", echelle.hauteur_sous_plafond)
    )
    reference = charger_logement(DOSSIER / "logement.json")
    assert logement.hauteur_sous_plafond == reference.hauteur_sous_plafond
    assert len(logement.murs) == len(reference.murs)
    for ref in reference.murs:
        lu = min(logement.murs, key=lambda m: math.dist(_milieu(m), _milieu(ref)))
        assert abs(lu.longueur - ref.longueur) / ref.longueur <= TOLERANCE_LONGUEUR, ref.id
