"""Tests du format logement : le cas test n°0 doit passer, les fichiers faux doivent être refusés."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from moteur.logement import Logement, charger_logement

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"


@pytest.fixture
def donnees():
    return json.loads(CAS_TEST_00.read_text(encoding="utf-8"))


def test_cas_test_00_est_valide():
    logement = charger_logement(CAS_TEST_00)
    assert len(logement.murs) == 7
    assert len(logement.ouvertures) == 7
    assert len(logement.pieces) == 4


def test_cas_test_00_dimensions_de_reference():
    logement = charger_logement(CAS_TEST_00)
    pieces = {p.id: p for p in logement.pieces}
    assert pieces["sejour"].surface_calculee == pytest.approx(25.92)
    assert pieces["chambre"].surface_calculee == pytest.approx(9.92)
    surface_totale = sum(p.surface_calculee for p in logement.pieces)
    assert surface_totale == pytest.approx(42.14)


def _modifie(donnees, modification):
    copie = copy.deepcopy(donnees)
    modification(copie)
    return copie


CAS_FAUX = {
    "longueur négative": lambda d: d["murs"][0].update(epaisseur=-0.20),
    "fenêtre qui dépasse du mur": lambda d: d["ouvertures"][3].update(position=7.90),
    "mur inconnu": lambda d: d["ouvertures"][0].update(mur="M_inexistant"),
    "identifiant en double": lambda d: d["pieces"][1].update(id="sejour"),
    "surface fausse": lambda d: d["pieces"][0].update(surface=30.0),
    "porte plus haute que le plafond": lambda d: d["ouvertures"][0].update(hauteur=2.80),
    "statut inconnu": lambda d: d["murs"][0].update(statut="devine"),
    "champ inconnu": lambda d: d["murs"][0].update(couleur="rouge"),
}


@pytest.mark.parametrize("nom", CAS_FAUX)
def test_fichier_faux_est_refuse(donnees, nom):
    with pytest.raises(ValidationError):
        Logement.model_validate(_modifie(donnees, CAS_FAUX[nom]))
