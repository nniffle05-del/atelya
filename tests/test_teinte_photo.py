"""La teinte d'un sol se calcule d'après la photo, étalonnée sur un mur blanc (moteur/teinte_photo.py)."""

import numpy as np
import pytest

from moteur.teinte_photo import (ALBEDO_MAX, BLANC_PEINTURE, albedo_du_sol, ecart_de_couleur, lineaire, teinte_pour)


def _photo(sol_srgb, mur_srgb):
    """Une « photo » de 100 × 100 : le mur en haut, le sol en bas."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:50] = mur_srgb
    image[50:] = sol_srgb
    return image


def test_le_mur_blanc_sert_d_etalon():
    # même sol, photo deux fois plus sombre (mur gris au lieu de blanc) : même couleur de sol trouvée
    clair = albedo_du_sol(_photo((200, 140, 90), (255, 255, 255)), (0, 1, 0.6, 1), (0, 1, 0, 0.4))
    mur_sombre = lineaire(np.array([255, 255, 255])) * 0.5
    sombre_srgb = (np.where(mur_sombre <= 0.0031308, mur_sombre * 12.92, 1.055 * mur_sombre ** (1 / 2.4) - 0.055) * 255).round()
    sol_sombre = lineaire(np.array([200, 140, 90])) * 0.5
    sol_srgb = (np.where(sol_sombre <= 0.0031308, sol_sombre * 12.92, 1.055 * sol_sombre ** (1 / 2.4) - 0.055) * 255).round()
    sombre = albedo_du_sol(_photo(sol_srgb, sombre_srgb), (0, 1, 0.6, 1), (0, 1, 0, 0.4))
    assert sombre == pytest.approx(clair, rel=0.03)
    assert clair[0] == pytest.approx(lineaire(np.array([200]))[0] * BLANC_PEINTURE, rel=1e-6)


def test_teinte_bornee():
    assert teinte_pour([0.2, 0.1, 0.05], [0.4, 0.2, 0.1]) == (2.0, 2.0, 2.0)
    assert teinte_pour([0.5, 0.5, 0.5], [0.99, 0.5, 0.5])[0] == pytest.approx(ALBEDO_MAX / 0.5, abs=0.01)  # pas plus clair
    assert teinte_pour([0.001, 0.5, 0.5], [0.9, 0.5, 0.5])[0] == 4.0  # pas plus de ×4


def test_ecart_de_couleur_ignore_la_clarte():
    assert ecart_de_couleur([0.2, 0.1, 0.05], [0.4, 0.2, 0.1]) == pytest.approx(0.0)
    assert ecart_de_couleur([0.3, 0.3, 0.3], [0.5, 0.2, 0.1]) > 0.2
