"""Depth Anything 3 « base » (moteur/da3.py) : les calculs sans les poids ; le réseau entier si les poids sont là."""
import numpy as np
import pytest
import torch

from moteur import da3
from moteur.oeil_dinov2 import dossier_poids


def test_quaternion_vers_matrice():
    assert torch.allclose(da3.quaternion_vers_matrice(torch.tensor([0.0, 0.0, 0.0, 1.0])), torch.eye(3), atol=1e-6)
    s = 2 ** -0.5  # quart de tour autour de z : x devient y
    R = da3.quaternion_vers_matrice(torch.tensor([0.0, 0.0, s, s]))
    assert torch.allclose(R @ torch.tensor([1.0, 0.0, 0.0]), torch.tensor([0.0, 1.0, 0.0]), atol=1e-6)
    R = da3.quaternion_vers_matrice(torch.tensor([0.3, -0.2, 0.5, 0.7]))  # non normé : reste une rotation
    assert torch.allclose(R @ R.T, torch.eye(3), atol=1e-5) and abs(float(torch.det(R)) - 1) < 1e-5


def test_preparer_cotes_multiples_de_14():
    for h, w in ((800, 1206), (1206, 800), (300, 300), (517, 911)):
        im = da3.preparer(np.zeros((h, w, 3), np.uint8))
        assert im.shape[0] % 14 == 0 and im.shape[1] % 14 == 0 and abs(max(im.shape[:2]) - 504) <= 7
        assert abs(im.shape[1] / im.shape[0] - w / h) < 0.05


def test_formes_du_reseau_sans_les_poids():
    torch.manual_seed(0)
    m = da3.DA3().eval()
    photos = [np.random.default_rng(i).integers(0, 255, (90, 120, 3), dtype=np.uint8) for i in range(3)]
    r = da3.lire(m, photos, cote=112)
    h, w = r["taille"]
    assert (h, w) == (84, 112)
    assert r["profondeur"].shape == (3, h, w) and r["confiance"].shape == (3, h, w) and r["appareils"].shape == (3, 3, 4)
    assert r["focale_px"].shape == (3, 2) and (r["profondeur"] > 0).all() and (r["confiance"] >= 1).all()
    for R in r["appareils"][:, :, :3]:
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-4)


def test_l_ordre_des_photos_est_rendu_tel_quel():
    """Le réseau met la photo de référence en tête en interne : la sortie doit rester dans l'ordre donné."""
    torch.manual_seed(1)
    m = da3.DA3().eval()
    rng = np.random.default_rng(0)
    photos = [rng.integers(0, 255, (84, 112, 3), dtype=np.uint8) for _ in range(3)]
    a = da3.lire(m, photos, cote=112, reference=2)
    b = da3.lire(m, [photos[2], photos[0], photos[1]], cote=112, reference=0)
    assert np.allclose(a["profondeur"][2], b["profondeur"][0], rtol=1e-3, atol=1e-4)
    assert np.allclose(a["profondeur"][0], b["profondeur"][1], rtol=1e-3, atol=1e-4)
    assert np.allclose(a["appareils"][1], b["appareils"][2], atol=1e-3)


def test_reseau_entier_si_les_poids_sont_la():
    if not (dossier_poids() / "da3-base" / "model.safetensors").is_file():
        pytest.skip("poids Depth Anything 3 absents")
    m = da3.charger(appareil="cpu")  # tous les poids utiles trouvent leur place, aucun en trop
    xx, yy = np.meshgrid(np.arange(196), np.arange(140))
    photo = np.stack([(xx * 255 // 196), (yy * 255 // 140), np.full_like(xx, 90)], -1).astype(np.uint8)
    r = da3.lire(m, [photo, photo[:, ::-1].copy()], cote=196)
    assert r["profondeur"].shape == (2, 140, 196) and np.isfinite(r["profondeur"]).all() and np.isfinite(r["appareils"]).all()
    assert (r["focale_px"] > 20).all()
    # la 1re photo sert de repère : son appareil est (presque) à l'origine, sans rotation
    assert np.allclose(r["appareils"][0][:, :3], np.eye(3), atol=0.15)
