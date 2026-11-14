"""MoGe-2 (moteur/moge.py) : le calcul du zoom et du recul, sans les poids ; le réseau entier si les poids sont là."""
import numpy as np
import pytest

from moteur import moge
from moteur.oeil_dinov2 import dossier_poids


def _nuage(focale, recul, n=400, graine=0):
    rng = np.random.default_rng(graine)
    uv = rng.uniform(-0.6, 0.6, (n, 2))
    z = rng.uniform(2.0, 6.0, n)
    xyz = np.concatenate([uv * z[:, None] / focale, (z - recul)[:, None]], 1)
    return uv, xyz


def test_focale_et_recul_retrouves():
    uv, xyz = _nuage(1.3, 0.8)
    f, d = moge.focale_et_decalage(uv, xyz)
    assert abs(f - 1.3) < 0.01 and abs(d - 0.8) < 0.01


def test_recul_seul_quand_la_focale_est_donnee():
    uv, xyz = _nuage(0.9, -0.5)
    f, d = moge.focale_et_decalage(uv, xyz, focale=0.9)
    assert f == 0.9 and abs(d + 0.5) < 0.01


def test_reseau_entier_si_les_poids_sont_la():
    if not (dossier_poids() / moge.DOSSIER / "model.pt").is_file():
        pytest.skip("poids MoGe-2 absents")
    m = moge.charger("cpu")
    rgb = np.full((140, 196, 3), 128, np.uint8)
    r = moge.lire(m, rgb, finesse=0)
    assert r["points"].shape == (140, 196, 3) and r["normales"].shape == (140, 196, 3) and r["focale_px"] > 0
    r2 = moge.relire(r, r["focale_px"] * 0.8)
    assert abs(r2["focale_px"] - r["focale_px"] * 0.8) < 1e-3
