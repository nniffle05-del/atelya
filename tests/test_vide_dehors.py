"""Combien de vide la caméra du film cadre par les fenêtres (moteur/cinema/vide_dehors.py)."""
import numpy as np

from moteur import vue_dehors as vd
from moteur.cinema import vide_dehors as vv
from tests.test_vue_dehors import _logement


def _decor(log, ligne_sous):
    """Une toile au sud à 15 m ; « sous la vue » à partir de la ligne `ligne_sous` (sur 32 : 1 m par ligne, haut à 26 m)."""
    sud = next(f for f in vd.facades(log, 15.0) if f["id"] == "facade-sud")
    m = np.zeros((32, 64), bool)
    m[ligne_sous:] = True
    return {"niveau_rue": vd.Z_BAS_M, "toiles": [{"id": "facade-sud", "n": np.array(sud["n"], float),
            "decalage": sud["decalage"], "origine": np.array(sud["origine"], float), "axe_u": np.array(sud["axe_u"], float),
            "longueur_u": sud["longueur_u"], "longueur_v": sud["longueur_v"], "masque": m}]}


def test_part_de_vide():
    log = _logement()
    ouv, murs = vd.ouvertures_vitrees(log), vd.murs_et_trous(log)
    cam = [2.0, 2.2, 1.5, -90.0, 0.0, 96.0, 96.0, 54.0]  # face à la fenêtre sud F1 (allège 0,9), image 192 × 108
    tout_vu = vv.part_de_vide(cam, (192, 108), ouv, murs, None, _decor(log, 32))
    moitie = vv.part_de_vide(cam, (192, 108), ouv, murs, None, _decor(log, 26))  # sous la vue dès z = 0
    assert tout_vu == 0.0 and moitie > 0.005
    # dos à la fenêtre : aucun dehors dans l'image
    assert vv.part_de_vide([2.0, 2.2, 1.5, 90.0, 0.0, 96.0, 96.0, 54.0], (192, 108), ouv, murs, None, _decor(log, 0)) == 0.0
    # plus près de la vitre, on voit plus bas : plus de vide
    pres = vv.part_de_vide([2.0, 0.8, 1.5, -90.0, 0.0, 96.0, 96.0, 54.0], (192, 108), ouv, murs, None, _decor(log, 26))
    assert pres > moitie
