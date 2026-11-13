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


def test_cout_du_regard_vers_le_vide():
    """Le coût donné au choix du regard : nul dos à la fenêtre ou quand la vue des photos couvre tout, plein face au vide."""
    log = _logement()
    vide_partout = vv.regard_sans_vide(log, _decor(log, 0), 18.0, (1920, 1080), 1.5, 0.0)
    assert vide_partout((2.0, 1.0), -90.0) == 1.0  # tout près de la fenêtre sud, face à elle
    assert vide_partout((2.0, 1.0), 90.0) == 0.0  # dos à la fenêtre
    tout_vu = vv.regard_sans_vide(log, _decor(log, 32), 18.0, (1920, 1080), 1.5, 0.0)
    assert tout_vu((2.0, 1.0), -90.0) == 0.0
    # une frange de vide au bas de la fenêtre (sous VIDE_TOLERE) ne coûte rien : la pièce peut montrer sa fenêtre
    frange = vv.regard_sans_vide(log, _decor(log, 27), 18.0, (1920, 1080), 1.5, 0.0)
    v = vv.part_de_vide([2.0, 2.6, 1.5, -90.0, 0.0, 48.0, 48.0, 27.0], (96, 54), vd.ouvertures_vitrees(log),
                        vd.murs_et_trous(log), None, _decor(log, 27))
    assert 0.0 < v < vv.VIDE_TOLERE and frange((2.0, 2.6), -90.0) == 0.0


def test_le_vol_evite_le_vide_sauf_aux_cadrages(monkeypatch):
    """Avec le décor de la vraie vue (13/11/2026) : le regard fuit le vide en chemin, mais pas au moment où il MONTRE une
    pièce (NT : « il ne regarde vraiment pas la première chambre »). Dans ce logement, le vide n'est cadré qu'aux cadrages
    des pièces : la règle par défaut ne change donc rien au vol ; sans cette exception, les fenêtres seraient évitées."""
    from moteur import promeneur as pm
    from moteur.cinema import regard
    from tests.test_promeneur import _logement as logement_du_vol
    log = logement_du_vol()
    sud = next(f for f in vd.facades(log, 15.0) if f["id"] == "facade-sud")
    decor = {"niveau_rue": vd.Z_BAS_M, "toiles": [{"id": "facade-sud", "n": np.array(sud["n"], float),
             "decalage": sud["decalage"], "origine": np.array(sud["origine"], float), "axe_u": np.array(sud["axe_u"], float),
             "longueur_u": sud["longueur_u"], "longueur_v": sud["longueur_v"], "masque": np.ones((32, 64), bool)}]}
    sans = pm.vol(log)
    v_sans = vv.mesurer(sans["trajet"], log, decor)
    assert v_sans.max() > vv.VIDE_PLEIN  # ce vol montre ses fenêtres de près
    assert pm.vol(log, decor=decor)["trajet"]["points"] == sans["trajet"]["points"]  # … et continue de les montrer
    monkeypatch.setattr(regard, "VIDE_CADRAGE", 0.0)  # sans l'exception des cadrages : le regard se détourne partout
    strict = pm.vol(log, decor=decor)
    v_strict = vv.mesurer(strict["trajet"], log, decor)
    assert strict["trajet"]["points"] != sans["trajet"]["points"]
    assert v_strict.max() < 0.6 * v_sans.max() and v_strict.sum() < 0.9 * v_sans.sum()
