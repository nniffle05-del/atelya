"""Tests de la lecture automatique des pièces (contour, nom, surface)."""

from functools import cache

import pytest

from moteur.lecture_pieces import lire_surface, surface_vraisemblable
from moteur.lecture_plan import lire_plan, logement_depuis_plan
from moteur.logement import Logement, charger_logement
from test_lecture_plan import COPIES, DOSSIER

pytest.importorskip("rapidocr")


@cache
def _plan_lu(nom):
    """Chaque copie n'est lue qu'une fois (la lecture des textes prend environ une seconde)."""
    return lire_plan(COPIES[nom]()[0])


@pytest.mark.parametrize("nom", COPIES)
def test_pieces_retrouvees(nom):
    plan = _plan_lu(nom)
    logement = Logement.model_validate(logement_depuis_plan(plan, "LU"))
    reference = charger_logement(DOSSIER / "logement.json")

    assert sorted(p.nom for p in logement.pieces) == sorted(p.nom for p in reference.pieces)
    for ref in reference.pieces:
        lue = next(p for p in logement.pieces if p.nom == ref.nom)
        # Le contour est calé sur les faces des murs lus : même surface qu'en vrai, à 1 % près.
        assert lue.surface_calculee == pytest.approx(ref.surface_calculee, rel=0.01), ref.nom
    # Sur la plupart des pièces, la surface écrite sur le plan est relue et confirme le contour.
    confirmees = [p for p in plan.pieces if p.surfaces_d_accord]
    assert len(confirmees) >= 3
    assert not [p for p in plan.pieces if p.surfaces_d_accord is False]  # aucune fausse alerte


@pytest.mark.parametrize(
    "texte, attendu",
    [("9,92 m²", 9.92), ("2.73 m²", 2.73), ("357 m²", 357.0), ("25,92 m2", 25.92), ("Chambre", None), ("8,00", None)],
)
def test_lire_surface(texte, attendu):
    assert lire_surface(texte) == attendu


def test_virgule_perdue():
    """La lecture a perdu la virgule de « 3,57 m² » : on la remet si le contour confirme."""
    assert surface_vraisemblable(357.0, 3.57) == 3.57
    assert surface_vraisemblable(357.0, 12.0) == 357.0  # rien ne colle : on laisse, ce sera signalé
