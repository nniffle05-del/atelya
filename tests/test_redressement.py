"""Tests du redressement des plans photographiés de biais (moteur/redressement.py)."""

import cv2
import numpy as np
import pytest

from moteur.coloriage import lire_coloriage
from moteur.redressement import corriger_proportions, estimer_redressement
from tests.test_coloriage import S, coloriage_t2

# Une photo de biais : les quatre coins de la page bougent de quelques pour cent, et la page est penchée de 4°.
COINS = np.float32([[0, 0], [800, 0], [800, 600], [0, 600]])
VUS = np.float32([[30, 10], [790, 42], [770, 640], [8, 590]])


def photo(c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    W = cv2.getPerspectiveTransform(COINS, VUS).astype(np.float64)
    return cv2.warpPerspective(c, W, (820, 660), flags=cv2.INTER_NEAREST), W


def echelles(G: np.ndarray, x: float, y: float) -> tuple[float, float]:
    """Pixels par pixel d'origine, en largeur et en hauteur, au point (x, y) de l'image d'origine."""
    w = G[2] @ (x, y, 1)
    J = (G[:2, :2] * w - np.outer(G[:2] @ (x, y, 1), G[2, :2])) / w ** 2
    return float(np.hypot(*J[:, 0])), float(np.hypot(*J[:, 1]))


def test_les_murs_redeviennent_droits():
    vue, W = photo(coloriage_t2())
    r = estimer_redressement(vue)
    assert r is not None and r.perspective > 0.01 and r.de_biais
    G = r.H @ W  # plan d'origine → image redressée : ne doit plus être qu'un étirement le long des axes
    coins = np.array([[100, 100, 1], [740, 100, 1], [740, 540, 1], [100, 540, 1]], np.float64) @ G.T
    coins = coins[:, :2] / coins[:, 2:]
    assert coins[0, 1] == pytest.approx(coins[1, 1], abs=0.8)  # le mur nord est horizontal
    assert coins[3, 1] == pytest.approx(coins[2, 1], abs=0.8)
    assert coins[0, 0] == pytest.approx(coins[3, 0], abs=0.8)  # le mur ouest est vertical
    assert coins[1, 0] == pytest.approx(coins[2, 0], abs=0.8)


def test_plan_de_biais_lu_comme_a_plat():
    vue, W = photo(coloriage_t2())
    r = estimer_redressement(vue)
    sx, sy = echelles(r.H @ W, 420, 320)
    r = corriger_proportions(r, sx / sy)  # ce que diraient les cotes, lues en largeur et en hauteur
    log, details = lire_coloriage(vue, S * sx, redressement=r)
    assert details["redresse"]
    assert len(log["murs"]) == 5
    cloison = min(log["murs"], key=lambda m: m["epaisseur"])
    assert cloison["epaisseur"] == pytest.approx(0.10, abs=0.03)
    assert cloison["debut"][0] == pytest.approx(3.0, abs=0.04)
    fen = next(o for o in log["ouvertures"] if o["type"] == "fenetre")
    assert fen["largeur"] == pytest.approx(1.2, abs=0.05)
    assert sorted(details["types_pieces"].values()) == ["chambre", "sejour"]


def test_plan_a_plat_reste_a_plat():
    c = coloriage_t2()
    r = estimer_redressement(c)
    assert r is not None and r.perspective < 0.002 and not r.de_biais
    log, _ = lire_coloriage(c, S, redressement=r)
    assert len(log["murs"]) == 5
    cloison = min(log["murs"], key=lambda m: m["epaisseur"])
    assert cloison["debut"][0] == pytest.approx(3.0, abs=0.02)


def test_sans_murs_rien_a_redresser():
    assert estimer_redressement(np.zeros((200, 300), np.uint8)) is None
