"""Les nappes de tissu de la maquette (moteur/blender/tissus.py, 23/11/2026) : un rideau ne passe jamais derrière son voilage.
Vu dans le film d'app-001 : des points clairs dans les grands rideaux tirés, là où un pli du voilage traversait le rideau."""
import numpy as np
import pytest

from moteur.blender import tissus

HAUT = 2.6


def fenetre(demi: float = 1.05):
    """Le voilage d'une baie de 2,10 m et ses deux rideaux tirés, comme la maquette les découpe."""
    voilage = tissus.nappe("Voilage_O8", -demi - 0.15, demi + 0.15, 0.10, 0.01, HAUT, "voilage")
    gauche = tissus.nappe("Rideau_O8_g", -1.08, -0.40, 0.16, 0.01, HAUT, "rideaux_tires")
    droite = tissus.nappe("Rideau_O8_d", 0.14, 1.08, 0.16, 0.01, HAUT, "rideaux_tires")
    return voilage, gauche, droite


def test_la_collection_de_tissus_est_la():
    assert all(tissus.bande(sorte) is not None for sorte in tissus.BANDES)


def test_une_nappe_tient_dans_sa_place():
    voilage, gauche, _ = fenetre()
    assert float(gauche["x"][0].min()) == pytest.approx(-1.08, abs=0.02) and float(gauche["x"][0].max()) == pytest.approx(-0.40, abs=0.02)
    assert float(gauche["z"].max()) == pytest.approx(HAUT, abs=0.01) and float(gauche["z"].min()) >= 0.0
    # les plis restent dans la demi-profondeur de leur sorte (les mêmes que le contrôle des collisions)
    assert float(np.abs(gauche["y"] - 0.16).max()) <= 0.05 + 1e-4 and float(np.abs(voilage["y"] - 0.10).max()) <= 0.03 + 1e-4


def test_le_rideau_ne_passe_jamais_derriere_son_voilage():
    voilage, gauche, droite = fenetre()
    # sans la correction, les plis se croisent ou se frôlent (c'était le défaut vu dans le film)
    assert min(tissus.ecart_au_pire(gauche, voilage), tissus.ecart_au_pire(droite, voilage)) < 0.004
    for pan in (gauche, droite):
        avant = pan["y"].copy()
        bouges = tissus.passer_devant(pan, voilage)
        assert tissus.ecart_au_pire(pan, voilage) >= tissus.JEU_TISSUS - 1e-4
        # peu de points bougent, jamais vers le mur, et le rideau ne sort pas de sa place (zéro collision inchangé)
        assert 0 < bouges < 0.15 * avant.size and bool((pan["y"] >= avant - 1e-6).all())
        assert float(pan["y"].max()) == pytest.approx(float(avant.max()), abs=1e-6)


def test_sans_voilage_derriere_le_rideau_ne_change_pas():
    """Un rideau à côté de son voilage (aucun recouvrement) : rien à repousser."""
    voilage = tissus.nappe("Voilage_O6", -0.60, 0.60, 0.10, 0.01, HAUT, "voilage")
    pan = tissus.nappe("Rideau_O6_d", 0.70, 0.95, 0.16, 0.01, HAUT, "rideaux")
    avant = pan["y"].copy()
    assert tissus.passer_devant(pan, voilage) == 0 and bool((pan["y"] == avant).all())
    assert tissus.ecart_au_pire(pan, voilage) is None
