"""Les grands meubles adossés (17/11/2026, « place et taille justes », étape 2) : mesurés SUR leur mur, par les deux bords de
leur rectangle."""
import math

import numpy as np

from moteur import caler_photos as cp
from moteur import lecture_photos as lp
from moteur import meubles_photos as mp
from moteur import photos_lues as pl
from moteur import reperer_meubles as rm

MUR = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
LOGEMENT = {"hauteur_sous_plafond": 2.5,
            "murs": [MUR("M1", (10.1, 0), (10.1, 6)), MUR("M3", (0, -0.1), (10, -0.1)), MUR("M4", (0, 6.1), (10, 6.1)), MUR("M5", (-0.1, 0), (-0.1, 6))],
            "ouvertures": [], "pieces": [{"id": "sejour_1", "contour": [[0, 0], [10, 0], [10, 6], [0, 6]]}]}
PLAN = cp.plan_du_logement(LOGEMENT)
# appareil au milieu de la pièce, qui regarde le mur nord (cap 90) ; photo de 1200 × 800, focale 600 px
CAM = [5.0, 3.0, 1.3, 90.0, 0.0, 600.0, 600.0, 400.0]


def test_une_armoire_de_deux_metres_mesuree_sur_son_mur():
    # ses coins de devant (x = 4 et 6, à 60 cm du mur) sont vus à 22,6° de part et d'autre : pixels 350 et 850
    sur = pl.contre_le_mur((5.0, 5.67), "placard", [350, 150, 850, 700], CAM, LOGEMENT, 1200, 2.67)
    assert abs(sur["largeur_mur"] - 2.0) < 0.1 and not sur["coupe_mur"]
    assert math.dist(sur["position"], (5.0, 5.67)) < 0.05 and sur["normale"] == [0.0, -1.0]
    # la largeur courante d'un placard (1,50 m) n'y est pour rien : une armoire d'un mètre sort à un mètre
    etroite = pl.contre_le_mur((5.0, 5.67), "placard", [475, 150, 725, 700], CAM, LOGEMENT, 1200, 2.67)
    assert abs(etroite["largeur_mur"] - 1.0) < 0.1


def test_coupee_par_le_cadre_ou_loin_du_mur():
    assert pl.contre_le_mur((1.5, 5.67), "placard", [0, 150, 400, 700], CAM, LOGEMENT, 1200, 4.4)["coupe_mur"]
    assert pl.contre_le_mur((5.0, 4.2), "placard", [350, 150, 850, 700], CAM, LOGEMENT, 1200, 1.2) is None  # au milieu de la pièce
    # un regard qui rase le mur ne mesure rien dessus
    rasante = [0.3, 5.5, 1.3, 0.0, 0.0, 600.0, 600.0, 400.0]
    assert pl.contre_le_mur((6.0, 5.67), "placard", [580, 150, 640, 700], rasante, LOGEMENT, 1200, 5.7) is None


def test_la_largeur_retenue_est_celle_de_la_vue_entiere_la_plus_large_parmi_les_proches():
    def vue(photo, large, appareil, coupe=False):
        return {"groupe": "rangement", "categorie": "etagere_cubes", "position": [5.0, 5.77], "appareil": appareil, "photo": photo,
                "distance": math.dist((5.0, 5.77), appareil), "confiance": 0.5, "poids": 2.0, "largeur_vue": 0.5, "piece": "sejour_1",
                "largeur_mur": large, "coupe_mur": coupe, "normale": [0.0, -1.0]}
    cachee, entiere = vue(0, 0.4, [5.0, 3.0]), vue(1, 1.4, [4.0, 2.5])
    assert mp.associer([cachee, entiere])[0]["largeur_mur"] == 1.4  # l'îlot cachait un bout sur la première
    lointaine = vue(2, 2.1, [5.0, -1.5])
    assert mp.associer([entiere, lointaine])[0]["largeur_mur"] == 1.4  # une vue à 7 m ne compte pas pour la largeur
    assert mp.associer([vue(0, 0.9, [5.0, 3.0], coupe=True)])[0]["largeur_mur"] == 1.5  # coupée seule : au moins la largeur courante
    meuble = rm.vers_meubles_du_logement(mp.associer([cachee, entiere]), LOGEMENT)[0]
    assert meuble["dimensions"][0] == 1.4 and meuble["face"] == -90.0  # la vraie largeur, dos au mur nord


def test_les_morceaux_d_un_meme_objet_sont_reunis():
    liste = [{"numero": 1, "boite": [100, 300, 400, 600], "note": 0.5, "detecteur": "cuisine"},
             {"numero": 2, "boite": [380, 320, 900, 620], "note": 0.4, "detecteur": "cuisine"}]
    fiche = {"objets": {"1": {"sorte": "meuble_cuisine_bas"}, "2": {"meme_que": 1}}}
    objets = lp.objets_lus(fiche, liste)
    assert len(objets) == 1 and objets[0]["boite"] == [100, 300, 900, 620]
    assert lp.objets_lus(fiche, liste, reunir=False)[0]["boite"] == [100, 300, 400, 600]


def test_une_bibliotheque_au_pied_cache_est_posee_contre_le_mur_que_son_regard_touche():
    # son rectangle s'arrête au-dessus d'un canapé : son bas, reporté au sol, tombe à 8 m, derrière le mur nord (à 5 m)
    cam = [5.0, 1.0, 1.3, 90.0, 0.0, 600.0, 600.0, 400.0]
    vide = np.zeros((80, 120), bool)
    repere = {"h": np.zeros((80, 120)), "phi": np.zeros((80, 120)), "r": np.zeros((80, 120)), "M": vide, "devant": vide}
    camera = {"x": 5.0, "y": 1.0, "z": 1.3, "cap": 90.0, "f": 600.0}
    objets = [{"numero": 1, "sorte": "bibliotheque", "boite": [560, 250, 640, 497], "note": 0.5}]
    vues = pl.au_sol_d_une_photo(objets, cam, 1200, 800, LOGEMENT["pieces"][0], repere=repere, camera=camera, plan=PLAN, logement=LOGEMENT)
    assert len(vues) == 1 and vues[0]["piece"] == "sejour_1"
    assert abs(vues[0]["position"][0] - 5.0) < 0.1 and abs(vues[0]["position"][1] - 5.82) < 0.1
    # une chaise dans le même cas n'est pas un meuble adossé : elle n'est pas inventée contre le mur
    chaise = [{"numero": 1, "sorte": "chaise", "boite": [560, 250, 640, 497], "note": 0.5}]
    assert pl.au_sol_d_une_photo(chaise, cam, 1200, 800, LOGEMENT["pieces"][0], repere=repere, camera=camera, plan=PLAN, logement=LOGEMENT) == []
