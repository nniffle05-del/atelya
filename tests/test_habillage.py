"""Tests de l'habillage : menuiseries, matériaux, lumières, caméras (sans Blender)."""

import json
import math
from pathlib import Path

import pytest

from moteur.geometrie import calculer_briques
from moteur.habillage import (
    FORMAT, _axes_camera, _dans, menuiseries, plan_habille, sol_de_la_piece,
)
from moteur.logement import charger_logement

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"


@pytest.fixture
def logement():
    return charger_logement(CAS_TEST_00)


@pytest.fixture
def plan(logement):
    return json.loads(json.dumps(plan_habille(logement)))


def boite(b):
    xs = [p[0] for p in b["contour"]]
    ys = [p[1] for p in b["contour"]]
    return (min(xs), min(ys), b["z_bas"]), (max(xs), max(ys), b["z_haut"])


def volume_commun(a, b):
    (a_min, a_max), (b_min, b_max) = a, b
    v = 1.0
    for i in range(3):
        v *= max(0.0, min(a_max[i], b_max[i]) - max(a_min[i], b_min[i]))
    return v


def test_plan_habille_lisible(plan):
    assert plan["schema"] == "construction/0.2"
    assert len(plan["briques"]) == 36 + 45  # les briques de l'étape 2 + les menuiseries
    assert all(b["materiau"] for b in plan["briques"])


def test_une_menuiserie_par_ouverture(logement):
    elements = {b.element for b in menuiseries(logement)}
    assert elements == {o.id for o in logement.ouvertures}


def test_vitres(logement):
    vitres = [b for b in menuiseries(logement) if b.materiau == "verre"]
    # 3 fenêtres ou portes-fenêtres d'au moins 1 m : deux vantaux chacune.
    assert len(vitres) == 6


def test_les_menuiseries_ne_rentrent_pas_dans_les_murs(plan):
    murs = [boite(b) for b in plan["briques"] if b["categorie"] == "mur"]
    for b in plan["briques"]:
        if b["categorie"] == "menuiserie":
            for mur in murs:
                assert volume_commun(boite(b), mur) == pytest.approx(0, abs=1e-9), b["id"]


def test_porte_d_entree_reconnue(plan):
    entrees = {b["element"] for b in plan["briques"] if b["materiau"] == "porte_entree"}
    assert entrees == {"P_entree"}


@pytest.mark.parametrize("nom, sol", [
    ("Séjour + cuisine", "parquet"),
    ("Chambre 2", "parquet"),
    ("Entrée", "carrelage"),
    ("Salle d'eau", "carrelage"),
    ("Salle de bains", "carrelage"),
    ("WC", "carrelage"),
    ("Cuisine", "carrelage"),
    ("Grenier", "parquet"),  # nom inconnu : parquet par défaut
])
def test_sol_selon_le_nom(nom, sol):
    assert sol_de_la_piece(nom) == sol


def test_sols_du_cas_test(plan):
    sols = {b["element"]: b["materiau"] for b in plan["briques"] if b["id"].startswith("sol__")}
    assert sols == {"sejour": "parquet", "chambre": "parquet",
                    "entree": "carrelage", "sdb": "carrelage"}


def test_un_plafonnier_par_piece_sous_le_plafond(plan, logement):
    plafonniers = [l for l in plan["lumieres"] if l["type"] == "plafonnier"]
    assert sorted(l["piece"] for l in plafonniers) == sorted(p.id for p in logement.pieces)
    pieces = {p.id: p for p in logement.pieces}
    for l in plafonniers:
        assert _dans(l["position"][:2], pieces[l["piece"]].contour)
        assert l["position"][2] < logement.hauteur_sous_plafond


def test_vue_de_dessus_cadre_tout_le_logement(plan, logement):
    vue = next(v for v in plan["vues"] if v["id"] == "dessus")
    droite, haut = _axes_camera(vue["position"], vue["cible"])
    demi_largeur = vue["echelle"] / 2
    demi_hauteur = demi_largeur * FORMAT[1] / FORMAT[0]
    for b in calculer_briques(logement):
        for x, y in b.contour:
            for z in (b.z_bas, b.z_haut):
                v = [x - vue["cible"][0], y - vue["cible"][1], z - vue["cible"][2]]
                assert abs(sum(a * c for a, c in zip(v, droite))) < demi_largeur
                assert abs(sum(a * c for a, c in zip(v, haut))) < demi_hauteur


def test_vue_interieure_du_sejour(plan, logement):
    vue = next(v for v in plan["vues"] if v["projection"] == "perspective")
    assert vue["piece"] == "sejour"
    sejour = next(p for p in logement.pieces if p.id == "sejour")
    assert _dans(vue["position"][:2], sejour.contour)
    assert 1.2 < vue["position"][2] < 1.8  # hauteur d'œil
    # Le coin choisi (sud-est) voit la fenêtre ouest et la porte-fenêtre nord.
    (cx, cy, _), (tx, ty, _) = vue["position"], vue["cible"]
    visee = math.atan2(ty - cy, tx - cx)
    for fx, fy in [(-0.10, 2.80), (2.20, 5.50)]:
        ecart = (math.atan2(fy - cy, fx - cx) - visee + math.pi) % (2 * math.pi) - math.pi
        assert abs(ecart) < math.radians(45)
