"""Tests de l'aiguillage essai 5 / essai 7b (moteur/aiguillage.py)."""

from moteur.aiguillage import choisir, longueur_libre


def mur(i, a, b):
    return {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}


DROITS = [mur("M1", (0, 0), (5, 0)), mur("M2", (5, 0), (5, 4))]


def test_plan_droit_garde_l_essai_5():
    e5, e7 = {"murs": DROITS}, {"murs": DROITS + [mur("M3", (0, 0), (0.5, 0.5))]}  # 0,7 m de biais : trop peu
    assert choisir(e5, e7)[0] == "e5"


def test_plan_en_biais_prend_l_essai_7():
    e7 = {"niveaux": [{"murs": DROITS + [mur("M3", (0, 0), (2, 2))]}]}
    assert choisir({"murs": DROITS}, e7) == ("e7", e7)


def test_arrondi_compte_par_ses_segments():
    arc = [mur(f"M_arrondi1-{k}", (k * 0.2, 0), ((k + 1) * 0.2, 0)) for k in range(10)]  # ids « -k »
    assert abs(longueur_libre({"murs": arc}) - 2.0) < 1e-9
