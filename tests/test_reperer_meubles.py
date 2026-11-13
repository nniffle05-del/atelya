"""Repérage des meubles sur les photos (moteur/reperer_meubles.py)."""
import numpy as np

from moteur.meubles import NOMS_MEUBLES
from moteur.reperer_meubles import (CLASSES_MEUBLES, TAILLE_ENTREE, etiquettes_carres, fusionner, noter_meubles, orienter,
                                    taches, vers_le_sol)


def test_etiquettes_par_carre_avec_groupes():
    masque = np.zeros((TAILLE_ENTREE[1], TAILLE_ENTREE[0]), np.uint8)
    masque[:, :56] = NOMS_MEUBLES.index("tabouret_haut") + 1  # 4 colonnes de carrés : groupe « chaise »
    masque[:, 56:70] = NOMS_MEUBLES.index("lit") + 1
    masque[:, 63:70] = NOMS_MEUBLES.index("canape") + 1  # carré moitié lit, moitié canapé : ni l'un ni l'autre à 60 %
    e = etiquettes_carres(masque, part_min=0.6)
    assert (e[:, :4] == CLASSES_MEUBLES.index("chaise")).all()
    assert (e[:, 4] == -1).all() and (e[:, 5:] == CLASSES_MEUBLES.index("rien")).all()


def test_une_tache_et_son_pied():
    p = np.zeros((32, 48, len(CLASSES_MEUBLES)))
    p[..., 0] = 1.0
    k = CLASSES_MEUBLES.index("canape")
    p[10:20, 5:15] = 0
    p[10:20, 5:15, k] = 0.9
    (t,) = taches(p)
    assert t["groupe"] == "canape" and t["carres"] == 100
    assert {l for _, l in t["pied"]} == {19} and len(t["pied"]) == 10


def test_vers_le_sol_et_fusion():
    cam = [0.0, 0.0, 1.5, 90.0, 0.0, 500.0, 400.0, 300.0]  # regarde vers +y
    x, y = vers_le_sol(400, 300 + 500 * 1.5 / 3.0, cam)  # 1,5 m sous l'horizon à 3 m de distance
    assert abs(x) < 1e-6 and abs(y - 3.0) < 1e-6
    vus = [{"groupe": "chaise", "position": [1.0, 1.0], "largeur_vue": 0.4, "confiance": 0.8, "poids": 5},
           {"groupe": "chaise", "position": [1.2, 1.1], "largeur_vue": 0.4, "confiance": 0.8, "poids": 5},
           {"groupe": "chaise", "position": [2.0, 1.0], "largeur_vue": 0.4, "confiance": 0.8, "poids": 5},
           {"groupe": "table", "position": [1.1, 1.0], "largeur_vue": 1.0, "confiance": 0.8, "poids": 9}]
    f = fusionner(vus)
    assert sorted((m["groupe"], m["vues"]) for m in f) == [("chaise", 1), ("chaise", 2), ("table", 1)]


def test_orientation_contre_un_mur_et_note():
    piece = {"contour": [[0, 0], [5, 0], [5, 4], [0, 4]]}
    assert abs(orienter({"groupe": "canape", "position": [2.5, 0.5]}, piece) - 90) < 1e-6  # dos au mur sud
    verite = [{"categorie": "canape", "position": [2.5, 0.45]}, {"categorie": "chaise", "position": [4, 3]},
              {"categorie": "tableau", "position": [0, 2], "altitude": 1.5}]
    trouves = [{"groupe": "canape", "position": [2.6, 0.6]}, {"groupe": "lit", "position": [1, 3]}]
    n = noter_meubles(trouves, verite)
    assert n["retrouves"] == "1/2" and n["en_trop"] == 1 and n["par_groupe"] == {"canape": "1/1", "chaise": "0/1"}
