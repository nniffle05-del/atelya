"""La collection de rideaux calculés (moteur/modeles/rideaux/*.npz, outils/bibliotheque/fabriquer_rideaux.py, 19/11/2026)."""
from pathlib import Path

import numpy as np
import pytest

COLLECTION = Path(__file__).resolve().parents[1] / "moteur" / "modeles" / "rideaux"
# sorte : (largeur de tringle de la bande, ampleur = mètres de tissu par mètre de tringle)
ATTENDU = {"voilage": (4.0, 2.0), "rideau": (4.0, 2.0), "rideau_ouvert": (1.6, 3.2)}


@pytest.mark.parametrize("sorte", sorted(ATTENDU))
def test_la_bande_est_un_vrai_tissu_pendu(sorte):
    d = np.load(COLLECTION / f"{sorte}.npz")
    p, tissu, hauteur = d["points"].astype(np.float64), d["tissu"].astype(np.float64), float(d["hauteur"])
    lignes, colonnes = p.shape[:2]
    assert p.shape[2] == 3 and len(tissu) == colonnes and lignes > 40 and colonnes > 200
    tringle, ampleur = ATTENDU[sorte]
    # la ligne 0 est la tringle : en haut, sur toute la largeur de la bande ; le bas touche 0
    assert abs(p[0, :, 2].mean() - hauteur) < 0.01 and abs(np.ptp(p[0, :, 0]) - tringle) < 0.02
    assert abs(float(p[..., 2].min())) < 0.01
    # le tissu À PLAT fait `ampleur` fois la tringle, ses colonnes sont à pas égal, et il n'est PAS étiré à la tringle
    assert abs(tissu[-1] / tringle / ampleur - 1.0) < 0.05  # (les plis de profondeur inégale ajoutent un peu de tissu)
    pas = np.diff(tissu)
    assert pas.min() > 0 and np.ptp(pas) < 1e-3
    le_long = np.hypot(np.diff(p[0, :, 0]), np.diff(p[0, :, 1]))
    assert abs(le_long.sum() / tissu[-1] - 1.0) < 0.03
    # de vrais plis : profonds, et PAS réguliers en bas (la surface ondulée d'avant l'était partout)
    assert np.ptp(p[..., 1]) > 0.05
    bas = p[-3, :, 1] - p[-3, :, 1].mean()
    croisements = np.nonzero(np.diff(np.sign(bas)))[0]
    ecarts = np.diff(p[-3, croisements, 0])
    assert len(ecarts) > 10 and ecarts.std() / ecarts.mean() > 0.15
    # le tissu ne s'est pas déchiré ni envolé : chaque colonne descend à peu près d'aplomb
    assert np.abs(p[-1, :, 0] - p[0, :, 0]).max() < 0.25
