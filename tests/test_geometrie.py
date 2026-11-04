"""Tests du calcul des briques (sans Blender)."""

import copy
import json
from itertools import combinations
from pathlib import Path

import pytest

from moteur.geometrie import calculer_briques, plan_de_construction
from moteur.logement import Logement, charger_logement

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"


@pytest.fixture
def logement():
    return charger_logement(CAS_TEST_00)


@pytest.fixture
def briques(logement):
    return calculer_briques(logement)


def boite(brique):
    """Boîte englobante (x, y, z mini et maxi) d'une brique."""
    xs = [p[0] for p in brique.contour]
    ys = [p[1] for p in brique.contour]
    return (min(xs), min(ys), brique.z_bas), (max(xs), max(ys), brique.z_haut)


def volume_commun(a, b):
    (a_min, a_max), (b_min, b_max) = a, b
    v = 1.0
    for i in range(3):
        v *= max(0.0, min(a_max[i], b_max[i]) - max(a_min[i], b_min[i]))
    return v


def volume(b):
    return volume_commun(b, b)


def aire(brique):
    (x_min, y_min, _), (x_max, y_max, _) = boite(brique)
    return (x_max - x_min) * (y_max - y_min)


def test_nombre_de_briques(briques):
    categories = [b.categorie for b in briques]
    assert categories.count("mur") == 23
    assert categories.count("sol") == 4 + 5  # 4 pièces + 5 seuils de porte
    assert categories.count("plafond") == 4


def test_les_murs_ne_se_chevauchent_pas(briques):
    murs = [boite(b) for b in briques if b.categorie == "mur"]
    for a, b in combinations(murs, 2):
        assert volume_commun(a, b) == pytest.approx(0, abs=1e-9)


def test_enveloppe_exterieure(briques):
    """Les murs extérieurs font 0,20 : de -0,20 à 8,20 en x, de -0,20 à 5,60 en y."""
    boites = [boite(b) for b in briques if b.categorie == "mur"]
    assert min(b[0][0] for b in boites) == pytest.approx(-0.20)
    assert max(b[1][0] for b in boites) == pytest.approx(8.20)
    assert min(b[0][1] for b in boites) == pytest.approx(-0.20)
    assert max(b[1][1] for b in boites) == pytest.approx(5.60)
    assert min(b[0][2] for b in boites) == pytest.approx(0)
    assert max(b[1][2] for b in boites) == pytest.approx(2.50)


def test_volume_des_murs(briques):
    """Calcul indépendant : enveloppe moins intérieur, plus cloisons, moins ouvertures."""
    exterieurs = (8.40 * 5.80 - 8.00 * 5.40) * 2.50
    cloisons = (5.40 + 3.10 + 2.10) * 0.10 * 2.50
    ouvertures = (
        0.90 * 2.04 * 0.20  # porte d'entrée
        + 1.40 * 2.15 * 0.20  # porte-fenêtre du séjour
        + 1.20 * 1.35 * 0.20  # fenêtre ouest du séjour
        + 1.00 * 1.35 * 0.20  # fenêtre de la chambre
        + 3 * 0.80 * 2.04 * 0.10  # trois portes intérieures
    )
    total = sum(volume(boite(b)) for b in briques if b.categorie == "mur")
    assert total == pytest.approx(exterieurs + cloisons - ouvertures)


def test_chaque_ouverture_est_un_vrai_trou(logement, briques):
    murs = {m.id: m for m in logement.murs}
    boites_murs = [boite(b) for b in briques if b.categorie == "mur"]
    for o in logement.ouvertures:
        mur = murs[o.mur]
        (x1, y1), (x2, y2) = mur.debut, mur.fin
        ux, uy = (x2 - x1) / mur.longueur, (y2 - y1) / mur.longueur
        a = (x1 + ux * o.position, y1 + uy * o.position)
        b = (x1 + ux * (o.position + o.largeur), y1 + uy * (o.position + o.largeur))
        demi = mur.epaisseur / 2
        trou = (
            (min(a[0], b[0]) - abs(uy) * demi, min(a[1], b[1]) - abs(ux) * demi, o.allege),
            (max(a[0], b[0]) + abs(uy) * demi, max(a[1], b[1]) + abs(ux) * demi,
             o.allege + o.hauteur),
        )
        assert volume(trou) == pytest.approx(o.largeur * o.hauteur * mur.epaisseur)
        for bm in boites_murs:
            assert volume_commun(trou, bm) == pytest.approx(0, abs=1e-9), o.id


def test_porte_entree_aux_bonnes_cotes(briques):
    """La porte d'entrée est à 5,20 du début du mur sud (x = -0,10) : de 5,10 à 6,00."""
    par_id = {b.id: b for b in briques}
    (x_min, _, z_min), (x_max, _, _) = boite(par_id["M_sud__linteau_P_entree"])
    assert (x_min, x_max, z_min) == pytest.approx((5.10, 6.00, 2.04))
    assert boite(par_id["M_sud__plein_1"])[1][0] == pytest.approx(5.10)
    assert boite(par_id["M_sud__plein_2"])[0][0] == pytest.approx(6.00)


def test_surface_des_sols(briques):
    seuils = 0.90 * 0.20 + 1.40 * 0.20 + 3 * 0.80 * 0.10
    total = sum(aire(b) for b in briques if b.categorie == "sol")
    assert total == pytest.approx(42.14 + seuils)


def test_plan_lisible_en_json(logement):
    plan = json.loads(json.dumps(plan_de_construction(logement)))
    assert plan["schema"] == "construction/0.1"
    assert plan["projet_id"] == "CAS-TEST-00"
    assert len(plan["briques"]) == 36


def _donnees():
    return json.loads(CAS_TEST_00.read_text(encoding="utf-8"))


CAS_NON_GERES = {
    "deux ouvertures qui se chevauchent": lambda d: d["ouvertures"][3].update(
        mur="M_nord", position=2.00
    ),
    "trois murs au même point": lambda d: d["murs"].append(
        {"id": "M_trop", "debut": [-0.10, -0.10], "fin": [-1.10, -0.10], "epaisseur": 0.20,
         "statut": "ajoute", "source": "test"}
    ),
}


@pytest.mark.parametrize("nom", CAS_NON_GERES)
def test_cas_non_geres_refuses(nom):
    donnees = copy.deepcopy(_donnees())
    CAS_NON_GERES[nom](donnees)
    logement = Logement.model_validate(donnees)  # le fichier est valide...
    with pytest.raises(ValueError):
        calculer_briques(logement)  # ...mais la géométrie n'est pas encore gérée


@pytest.mark.parametrize("fin_b", [(4.0, 3.0), (2.5, 3.0), (5.0, 0.5), (-1.0, 3.0), (3.0, -2.0)])
@pytest.mark.parametrize("ep_b", [0.20, 0.35])
def test_angle_en_biais_coupe_d_onglet(fin_b, ep_b):
    """A3 : deux murs qui se rejoignent en biais se touchent le long d'une même arête (onglet), sans trou."""
    from moteur.logement import Mur
    a = Mur(id="A", debut=(0.0, 0.0), fin=(2.0, 0.0), epaisseur=0.20, statut="ajoute", source="test")
    b = Mur(id="B", debut=(2.0, 0.0), fin=fin_b, epaisseur=ep_b, statut="ajoute", source="test")
    from moteur.geometrie import _ajustements_aux_angles, _briques_du_mur
    aj = _ajustements_aux_angles([a, b])
    ba = _briques_du_mur(a, 2.5, (-aj["A"][0][0], -aj["A"][0][1]),
                         (a.longueur + aj["A"][1][0], a.longueur + aj["A"][1][1]), [])
    bb = _briques_du_mur(b, 2.5, (-aj["B"][0][0], -aj["B"][0][1]),
                         (b.longueur + aj["B"][1][0], b.longueur + aj["B"][1][1]), [])
    communs = {tuple(round(v, 5) for v in p) for p in ba[0].contour} & {tuple(round(v, 5) for v in p) for p in bb[0].contour}
    assert len(communs) == 2  # l'arête d'onglet est partagée


def test_deux_murs_presque_alignes_ne_font_pas_exploser_l_angle():
    """Un bout de mur retouché à la main laisse parfois deux murs à 0,15° : la porte voisine doit rester constructible."""
    from moteur.geometrie import calculer_briques
    from moteur.logement import Logement

    donnees = {
        "schema": "logement/0.1", "projet_id": "T", "unites": "m", "hauteur_sous_plafond": 2.5,
        "murs": [
            {"id": "A", "debut": [0.01, 0.0], "fin": [0.0, 3.75], "epaisseur": 0.13, "statut": "estime", "source": "atelya"},
            {"id": "B", "debut": [0.0, 3.75], "fin": [0.0, 6.9], "epaisseur": 0.12, "statut": "estime", "source": "atelya"},
        ],
        "ouvertures": [{"id": "O", "type": "porte", "mur": "B", "position": 0.54, "largeur": 0.82, "hauteur": 2.04, "allege": 0,
                        "statut": "estime", "source": "atelya"}],
        "pieces": [],
    }
    briques = calculer_briques(Logement.model_validate(donnees))
    assert any(b.element == "B" for b in briques) and any(b.element == "A" for b in briques)


def test_deux_ouvertures_qui_se_touchent_a_un_millimetre_pres():
    """L'arrondi d'une lecture ne doit pas bloquer la 3D ; un vrai chevauchement, si."""
    from moteur.geometrie import calculer_briques
    from moteur.logement import Logement

    def avec(position):
        return Logement.model_validate({
            "schema": "logement/0.1", "projet_id": "T", "unites": "m", "hauteur_sous_plafond": 2.5,
            "murs": [{"id": "A", "debut": [0, 0], "fin": [6, 0], "epaisseur": 0.2, "statut": "estime", "source": "atelya"}],
            "ouvertures": [
                {"id": "F1", "type": "fenetre", "mur": "A", "position": 1, "largeur": 1, "hauteur": 1.2, "allege": 0.9, "statut": "estime", "source": "atelya"},
                {"id": "F2", "type": "fenetre", "mur": "A", "position": position, "largeur": 1, "hauteur": 1.2, "allege": 0.9, "statut": "estime", "source": "atelya"},
            ],
            "pieces": [],
        })

    assert calculer_briques(avec(1.999))
    with pytest.raises(ValueError, match="chevauche"):
        calculer_briques(avec(1.9))
