"""Tests de l'habillage : menuiseries, matériaux, lumières, caméras (sans Blender)."""

import json
import math
from pathlib import Path

import pytest

from moteur.geometrie import calculer_briques
from moteur.habillage import (
    EPAISSEUR_PLINTHE, FORMAT, HAUTEUR_PLINTHE, LARGEUR_CHAMBRANLE, _axes_camera, _dans, menuiseries, plan_habille,
    sol_de_la_piece,
)
from moteur.logement import Logement, charger_logement

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
    # les briques de l'étape 2 + les menuiseries + (B2-1) 24 chambranles, 4 appuis et 24 morceaux de plinthes
    assert len(plan["briques"]) == 36 + 45 + 24 + 4 + 24
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


# ------------------------------------------------------------------ B2-1 : plinthes, chambranles, appuis


def _piece_simple(**ouvertures_en_plus):
    """Une pièce de 4 × 3 m (murs de 20 cm, axes à ±0,1 m du bord) : porte au sud, fenêtre à l'est, porte-fenêtre au nord."""
    mur = lambda i, d, f: {"id": i, "debut": d, "fin": f, "epaisseur": 0.2, "statut": "mesure", "source": "test"}
    ouv = lambda i, t, m, pos, l, h, a: {"id": i, "type": t, "mur": m, "position": pos, "largeur": l, "hauteur": h,
                                         "allege": a, "statut": "mesure", "source": "test"}
    return Logement.model_validate({
        "schema": "logement/0.1", "projet_id": "PIECE", "hauteur_sous_plafond": 2.5,
        "murs": [mur("S", [-0.1, -0.1], [4.1, -0.1]), mur("E", [4.1, -0.1], [4.1, 3.1]),
                 mur("N", [-0.1, 3.1], [4.1, 3.1]), mur("O", [-0.1, -0.1], [-0.1, 3.1])],
        "ouvertures": [ouv("porte", "porte", "S", 1.0, 0.9, 2.04, 0.0),
                       ouv("fenetre", "fenetre", "E", 1.0, 1.2, 1.3, 0.9),
                       ouv("pf", "porte_fenetre", "N", 2.0, 1.4, 2.15, 0.0)],
        "pieces": [{"id": "sejour", "nom": "Séjour", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]],
                    "statut": "mesure", "source": "test"}],
    })


def _aire(contour):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]))) / 2


def test_plinthes_font_le_tour_sauf_devant_les_ouvertures_basses():
    plan = plan_habille(_piece_simple())
    plinthes = [b for b in plan["briques"] if b["id"].startswith("plinthe__")]
    assert plinthes and all(b["z_bas"] == 0 and b["z_haut"] == HAUTEUR_PLINTHE for b in plinthes)
    # Aire exacte de l'anneau de plinthes : tour complet (biseaux sans trou ni recouvrement dans les 4 angles), moins la
    # porte et ses deux chambranles (+ 1 mm de jeu de chaque côté), moins la porte-fenêtre ; la fenêtre ne coupe rien.
    e = EPAISSEUR_PLINTHE
    anneau = 4 * 3 - (4 - 2 * e) * (3 - 2 * e)
    trou_porte = (0.9 + 2 * (LARGEUR_CHAMBRANLE + 0.001)) * e
    trou_pf = 1.4 * e
    assert sum(_aire(b["contour"]) for b in plinthes) == pytest.approx(anneau - trou_porte - trou_pf, abs=1e-6)
    # rien au droit de la porte-fenêtre (x de 1,9 à 3,3 sur le mur nord, y proche de 3)
    for b in plinthes:
        xs = [p[0] for p in b["contour"]]
        ys = [p[1] for p in b["contour"]]
        if min(ys) > 2.9:
            assert max(xs) <= 1.9 + 1e-6 or min(xs) >= 3.3 - 1e-6


def test_chambranles_sur_les_deux_faces_de_chaque_porte():
    plan = plan_habille(_piece_simple())
    chambranles = [b for b in plan["briques"] if "chambranle" in b["id"]]
    assert {b["element"] for b in chambranles} == {"porte"}
    assert len(chambranles) == 6  # deux montants et une traverse, sur chaque face
    ys = sorted({round(min(p[1] for p in b["contour"]), 3) for b in chambranles})
    assert ys == [-0.22, 0.0]  # posés sur la face extérieure (y = -0,2) et intérieure (y = 0) du mur sud


def test_fenetre_pres_de_la_face_interieure_avec_appui():
    plan = plan_habille(_piece_simple())
    briques = {b["id"]: b for b in plan["briques"]}
    cadre = briques["fenetre__montant_1"]
    xs = [p[0] for p in cadre["contour"]]
    centre_mur = 4.1
    assert sum(xs) / len(xs) < centre_mur  # la pièce est à l'ouest du mur est : le cadre s'y décale
    assert "fenetre__appui" in briques and "fenetre__appui_nez" in briques
    nez = briques["fenetre__appui_nez"]
    assert min(p[0] for p in nez["contour"]) == pytest.approx(4.0 - 0.03)  # dépasse de 3 cm dans la pièce
    assert nez["z_bas"] == pytest.approx(0.9)
    assert not any(i.startswith("pf__appui") for i in briques)  # pas d'appui sous une porte-fenêtre
