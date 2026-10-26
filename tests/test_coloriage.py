"""Tests du maillon coloriage → logement.json (moteur/coloriage.py)."""

import numpy as np
import pytest

from moteur.banc_coloriage import comparer
from moteur.coloriage import MUR, PORTE, FENETRE, estimer_rotation, lire_coloriage, redresser
from moteur.logement import Logement

S = 100  # pixels par mètre


def px(m: float) -> int:
    return int(round(m * S))


def coloriage_t2() -> np.ndarray:
    """Un T2 dessiné à la main : intérieur 6,00 × 4,00 m, murs extérieurs de 20 cm,
    une cloison de 10 cm à x = 3,00 m, une porte dans la cloison, une fenêtre au sud."""
    c = np.zeros((px(6), px(8)), np.uint8)
    o = (px(1), px(1))  # coin nord-ouest du mur extérieur, en pixels (x, y)

    def rect(x0, y0, x1, y1, v):  # en mètres, repère du plan (y vers le nord, origine sud-ouest intérieur)
        c[o[1] + px(4.2 - y1):o[1] + px(4.2 - y0), o[0] + px(x0 + 0.2):o[0] + px(x1 + 0.2)] = v

    rect(-0.2, -0.2, 6.2, 4.2, MUR)
    rect(0, 0, 2.95, 4, 5)  # séjour
    rect(3.05, 0, 6, 4, 7)  # chambre
    rect(1.0, -0.2, 2.2, 0, FENETRE)
    rect(2.95, 1.0, 3.05, 1.9, PORTE)
    return c


def test_lit_les_murs_ouvertures_et_pieces():
    log, details = lire_coloriage(coloriage_t2(), S)
    Logement.model_validate(log)
    assert abs(details["angle_deg"]) < 0.1
    murs = sorted(log["murs"], key=lambda m: m["epaisseur"])
    cloison = murs[0]
    assert cloison["epaisseur"] == pytest.approx(0.10, abs=0.01)
    assert cloison["debut"][0] == pytest.approx(3.0, abs=0.02)
    assert len(log["murs"]) == 5  # 4 murs extérieurs + la cloison
    types = sorted(o["type"] for o in log["ouvertures"])
    assert types == ["fenetre", "porte"]
    fen = next(o for o in log["ouvertures"] if o["type"] == "fenetre")
    assert fen["largeur"] == pytest.approx(1.2, abs=0.03)
    assert sorted(details["types_pieces"].values()) == ["chambre", "sejour"]
    surfaces = sorted(round(Logement.model_validate(log).pieces[i].surface_calculee, 1) for i in range(2))
    assert surfaces == pytest.approx([11.8, 11.8], abs=0.15)


def test_plan_penche_est_redresse():
    c = coloriage_t2()
    penche = redresser(c, -3.0)
    angle = estimer_rotation((penche >= MUR) & (penche <= 4))
    assert angle == pytest.approx(3.0, abs=0.1)  # tourner de +3° le remet droit
    log, _ = lire_coloriage(penche, S)
    assert len(log["murs"]) == 5


def test_taches_hors_du_logement_ignorees():
    c = coloriage_t2()
    c[10:30, 10:120] = MUR  # une barre d'échelle dans la marge
    log, _ = lire_coloriage(c, S)
    assert len(log["murs"]) == 5


def test_comparaison_parfaite_avec_soi_meme():
    log, d = lire_coloriage(coloriage_t2(), S)
    r = comparer(log, log, {}, {})
    assert all(m["juste"] for m in r["murs"])
    assert all(o["juste"] for o in r["ouvertures"])
    assert r["hors_tout"] == 0
