"""Test de bout en bout : Blender construit la maquette, puis on la mesure.

Ce test lance vraiment Blender (sans écran). Il est sauté si Blender est
introuvable sur la machine.
"""

import json
from pathlib import Path

import pytest

from moteur.construire import construire, mesurer, trouver_blender

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"
MILLIMETRE = 0.001

pytestmark = pytest.mark.skipif(trouver_blender() is None, reason="Blender introuvable")


@pytest.fixture(scope="module")
def resultat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("cas-test-00")
    maquette = construire(CAS_TEST_00, dossier)
    plan = json.loads((dossier / "construction.json").read_text(encoding="utf-8"))
    return maquette, plan, mesurer(maquette, dossier / "mesures.json")


def test_la_maquette_existe(resultat):
    maquette, _, _ = resultat
    assert maquette.is_file()


def test_une_brique_un_objet(resultat):
    _, plan, mesures = resultat
    assert sorted(mesures) == sorted(b["id"] for b in plan["briques"])


def test_cotes_au_millimetre(resultat):
    _, plan, mesures = resultat
    collections = {"mur": "Murs", "sol": "Sols", "plafond": "Plafonds"}
    for brique in plan["briques"]:
        mesure = mesures[brique["id"]]
        xs = [p[0] for p in brique["contour"]]
        ys = [p[1] for p in brique["contour"]]
        attendu_min = [min(xs), min(ys), brique["z_bas"]]
        attendu_max = [max(xs), max(ys), brique["z_haut"]]
        assert mesure["min"] == pytest.approx(attendu_min, abs=MILLIMETRE), brique["id"]
        assert mesure["max"] == pytest.approx(attendu_max, abs=MILLIMETRE), brique["id"]
        assert mesure["collection"] == collections[brique["categorie"]]
        assert mesure["element"] == brique["element"]


def test_faces_bien_orientees(resultat):
    """Un sol regarde vers le haut, un plafond vers le bas, un mur a 6 faces."""
    _, plan, mesures = resultat
    for brique in plan["briques"]:
        mesure = mesures[brique["id"]]
        if brique["categorie"] == "mur":
            assert mesure["faces"] == 6
        elif brique["categorie"] == "sol":
            assert mesure["normales"] == [pytest.approx([0, 0, 1])]
        else:
            assert mesure["normales"] == [pytest.approx([0, 0, -1])]
