"""Tests de la lecture automatique des portes et fenêtres, sur le plan du cas test n°0 et ses copies abîmées."""

import math

from functools import cache

import pytest

from moteur.geometrie import calculer_briques
from moteur.lecture_plan import lire_plan, logement_depuis_plan
from moteur.logement import Logement, charger_logement
from test_lecture_plan import COPIES, DOSSIER

pytest.importorskip("rapidocr")


@cache
def _plan_lu(nom):
    """Chaque copie n'est lue qu'une fois (la lecture des textes prend environ une seconde)."""
    return lire_plan(COPIES[nom]()[0])

TOLERANCE_OUVERTURE = 0.035  # 3,5 cm sur la position et la largeur


def _centre(logement, o):
    """Le milieu d'une ouverture, en mètres dans le repère du logement."""
    m = next(w for w in logement.murs if w.id == o.mur)
    ux, uy = (m.fin[0] - m.debut[0]) / m.longueur, (m.fin[1] - m.debut[1]) / m.longueur
    t = o.position + o.largeur / 2
    return (m.debut[0] + ux * t, m.debut[1] + uy * t)


@pytest.mark.parametrize("nom", COPIES)
def test_portes_et_fenetres_retrouvees(nom):
    logement = Logement.model_validate(logement_depuis_plan(_plan_lu(nom), "LU"))
    reference = charger_logement(DOSSIER / "logement.json")

    assert len(logement.ouvertures) == len(reference.ouvertures)
    for ref in reference.ouvertures:
        lu = min(logement.ouvertures, key=lambda o: math.dist(_centre(logement, o), _centre(reference, ref)))
        assert lu.type == ref.type, ref.id
        assert math.dist(_centre(logement, lu), _centre(reference, ref)) <= TOLERANCE_OUVERTURE, ref.id
        assert abs(lu.largeur - ref.largeur) <= TOLERANCE_OUVERTURE, ref.id
        assert lu.statut.value == "estime"  # les hauteurs ne sont pas sur le plan
    calculer_briques(logement)  # le moteur sait percer les murs


def test_hauteurs_courantes():
    logement = logement_depuis_plan(_plan_lu("plan d'origine"), "LU")
    fenetre = next(o for o in logement["ouvertures"] if o["type"] == "fenetre")
    porte = next(o for o in logement["ouvertures"] if o["type"] == "porte")
    assert (fenetre["hauteur"], fenetre["allege"]) == (1.35, 0.95)
    assert (porte["hauteur"], porte["allege"]) == (2.04, 0.0)
