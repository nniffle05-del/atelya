"""Le même meuble d'une photo à l'autre (16/11/2026, « place et taille justes ») : une vue proche fait foi, une vue lointaine
rejoint le meuble qu'elle peut être au lieu d'en créer un second."""
import math

import numpy as np

from moteur import caler_photos as cp
from moteur import meubles_photos as mp
from moteur import objets_accroches as oa
from moteur import photos_lues as pl
from moteur import reperer_meubles as rm

MUR = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
# une grande pièce de 10 × 6 m et une chambre à l'est, derrière une cloison pleine
LOGEMENT = {
    "hauteur_sous_plafond": 2.5,
    "murs": [MUR("M1", (10.1, 0), (10.1, 6)), MUR("M2", (14.3, 0), (14.3, 6)), MUR("M3", (0, -0.1), (14.2, -0.1)), MUR("M4", (0, 6.1), (14.2, 6.1)),
             MUR("M5", (-0.1, 0), (-0.1, 6))],
    "ouvertures": [],
    "pieces": [{"id": "sejour_1", "contour": [[0, 0], [10, 0], [10, 6], [0, 6]]},
               {"id": "chambre_1", "contour": [[10.2, 0], [14.2, 0], [14.2, 6], [10.2, 6]]}],
}
PLAN = cp.plan_du_logement(LOGEMENT)


def vue(sorte, position, appareil, photo, groupe=None, piece="sejour_1", **plus):
    return {"groupe": groupe or rm.groupe(sorte), "categorie": sorte, "position": list(position), "appareil": list(appareil), "photo": photo,
            "distance": math.dist(position, appareil), "confiance": 0.5, "poids": 2.0, "largeur_vue": 0.5, "piece": piece, **plus}


def test_une_vue_lointaine_rejoint_le_meuble_vu_de_pres():
    # une chaise vue à 2 m, et la même vue de l'autre bout de la pièce (7 m), tombée 1,4 m trop près le long de son regard
    pres = vue("chaise", (8.0, 3.0), (8.0, 5.0), 0)
    loin = vue("chaise", (6.6, 3.0), (1.0, 3.0), 1)
    trouves = mp.associer([loin, pres])
    assert len(trouves) == 1 and trouves[0]["vues"] == 2
    assert math.dist(trouves[0]["position"], (8.0, 3.0)) < 0.15  # la place est celle de la vue proche
    assert len(mp.fusionner([loin, pres], par_sorte=True)) == 2  # l'ancienne règle (45 cm) en faisait deux chaises


def test_deux_chaises_voisines_vues_de_pres_restent_deux():
    a = [vue("chaise", (5.0, 3.0), (5.0, 1.0), 0), vue("chaise", (5.7, 3.0), (5.0, 1.0), 0)]
    b = [vue("chaise", (5.05, 3.05), (5.3, 5.2), 1), vue("chaise", (5.72, 2.95), (5.3, 5.2), 1)]
    trouves = mp.associer(a + b)
    assert len(trouves) == 2 and all(t["vues"] == 2 for t in trouves)


def test_deux_pieces_deux_meubles():
    # le meuble télé du séjour et celui de la chambre, de part et d'autre de la cloison, à 1 m l'un de l'autre
    a = vue("meuble_tv", (9.6, 3.0), (6.0, 3.0), 0)
    b = vue("meuble_tv", (10.6, 3.0), (13.5, 3.0), 1, piece="chambre_1")
    assert len(mp.associer([a, b])) == 2


def test_deux_armoires_sur_deux_murs_restent_deux():
    # deux armoires à 3,2 m l'une de l'autre, l'une vue à 2,5 m, l'autre à 4,5 m : la limite d'un grand meuble (2,5 m) ne s'allonge pas
    a = vue("placard", (0.4, 3.0), (2.9, 3.0), 0)
    b = vue("placard", (3.6, 3.0), (8.1, 3.0), 1)
    assert len(mp.associer([a, b])) == 2


def test_une_vue_coupee_par_le_bas_de_la_photo_rejoint_le_meuble_voisin():
    net = vue("fauteuil", (5.0, 3.0), (5.0, 0.8), 0)
    coupe = vue("fauteuil", (6.1, 3.3), (7.0, 3.6), 1, coupe=True)  # son pied est hors du cadre : place fausse d'un mètre
    trouves = mp.associer([coupe, net])
    assert len(trouves) == 1 and math.dist(trouves[0]["position"], (5.0, 3.0)) < 0.5
    assert len(mp.associer([vue("fauteuil", (6.1, 3.3), (7.0, 3.6), 1), net])) == 2  # entière, elle resterait un second fauteuil


def test_luminaires_reunis_des_plus_proches_aux_plus_lointains():
    pres = {"position": [5.0, 3.0], "distance": 2.0, "appareil": [5.0, 1.0], "photo": 0, "note": 0.5, "bas": 1.9, "haut": 2.4, "largeur": 0.5}
    loin = {"position": [3.7, 3.0], "distance": 6.3, "appareil": [-2.6 + 0.0, 3.0], "photo": 1, "note": 0.5, "bas": 1.9, "haut": 2.4, "largeur": 0.5}
    autre = {"position": [6.2, 3.0], "distance": 2.3, "appareil": [5.0, 1.0], "photo": 0, "note": 0.5, "bas": 1.9, "haut": 2.4, "largeur": 0.5}
    trouves = oa.fusionner([loin, pres, autre])
    assert len(trouves) == 2  # le lointain rejoint le proche ; les deux de la même photo restent deux
    assert any(t["vues"] == 2 and math.dist(t["position"], (5.0, 3.0)) < 0.2 for t in trouves)
    sans_appareil = [{k: v for k, v in x.items() if k != "appareil"} for x in (loin, pres)]
    assert len(oa.fusionner(sans_appareil)) == 2  # sans appareil connu : la limite fixe d'avant (90 cm)


def _trouves(*vues):
    return mp.associer(list(vues))


def test_un_meuble_vu_seulement_de_loin_que_la_photo_proche_ne_montre_pas_est_ecarte():
    # photo 0 : au fond de la pièce (x = 1), elle voit une chaise à 6 m ; photo 1 : à 2 m de cet endroit, elle le regarde
    loin = vue("chaise", (7.0, 3.0), (1.0, 3.0), 0)
    appareils = [([1.0, 3.0, 1.3, 0.0, 0.0, 600.0, 600.0, 400.0], (1200, 800)), ([7.0, 5.0, 1.3, -90.0, 0.0, 600.0, 600.0, 400.0], (1200, 800))]
    journal = []
    assert pl.confirmer_les_lointains(_trouves(loin), appareils, PLAN, LOGEMENT, journal.append, objets_par_photo={0: [], 1: []}) == []
    assert "écarté" in journal[0]
    # la photo proche a, dans cette direction, un rectangle lu « chaise » qu'Atelya n'a pas su poser : le meuble est gardé
    lus = {0: [], 1: [{"sorte": "chaise", "boite": [560, 500, 640, 700], "note": 0.5}]}
    assert len(pl.confirmer_les_lointains(_trouves(loin), appareils, PLAN, LOGEMENT, objets_par_photo=lus)) == 1
    # aucune photo plus proche ne regarde l'endroit : gardé, même de très loin (le seul témoin du fond d'une grande pièce)
    seul = [appareils[0], ([7.0, 5.0, 1.3, 90.0, 0.0, 600.0, 600.0, 400.0], (1200, 800))]
    assert len(pl.confirmer_les_lointains(_trouves(loin), seul, PLAN, LOGEMENT, objets_par_photo={})) == 1
    tres_loin = vue("chaise", (8.5, 3.0), (1.0, 3.0), 0)
    assert len(pl.confirmer_les_lointains(_trouves(tres_loin), seul, PLAN, LOGEMENT, objets_par_photo={})) == 1


def test_un_meuble_lointain_rejoint_le_meuble_de_son_groupe_vu_de_pres():
    # de loin « rangement », de près « commode » : même groupe, hauteurs voisines, à 1,5 m le long du regard lointain
    loin = vue("rangement", (7.0, 3.0), (1.0, 3.0), 0)
    pres = vue("commode", (8.5, 3.0), (8.5, 5.0), 1)
    appareils = [([1.0, 3.0, 1.3, 0.0, 0.0, 600.0, 600.0, 400.0], (1200, 800)), ([8.5, 5.0, 1.3, -90.0, 0.0, 600.0, 600.0, 400.0], (1200, 800))]
    gardes = pl.confirmer_les_lointains(_trouves(loin, pres), appareils, PLAN, LOGEMENT, objets_par_photo={})
    assert len(gardes) == 1 and gardes[0]["categorie"] == "commode" and gardes[0]["vues"] == 2
    # une bibliothèque (1,80 m) et un meuble télé (50 cm) ne sont pas le même meuble : le lointain est écarté, le proche reste
    loin, pres = vue("bibliotheque", (7.0, 3.0), (1.0, 3.0), 0), vue("meuble_tv", (8.5, 3.0), (8.5, 5.0), 1)
    gardes = pl.confirmer_les_lointains(_trouves(loin, pres), appareils, PLAN, LOGEMENT, objets_par_photo={})
    assert [g["categorie"] for g in gardes] == ["meuble_tv"]


def test_le_mur_corrige_dans_la_limite_de_l_incertitude_de_la_vue():
    piece = LOGEMENT["pieces"][0]
    commode = {"groupe": "rangement", "categorie": "commode", "position": [0.95, 3.0]}  # à 95 cm du mur ouest
    assert rm.coller_au_mur(commode, piece)["position"][0] < 0.3  # sans distance connue : collée, comme avant
    assert rm.coller_au_mur({**commode, "distance_min": 2.0}, piece)["position"] == [0.95, 3.0]  # vue à 2 m : elle est bien là
    assert rm.coller_au_mur({**commode, "distance_min": 5.0}, piece)["position"][0] < 0.3  # vue à 5 m : le mur corrige


def test_le_coeur_cache_par_un_meuble_de_devant_ne_mesure_rien():
    H, W = 80, 120
    h, phi, r = np.full((H, W), 0.6), np.zeros((H, W)), np.full((H, W), 2.0)
    repere = {"h": h, "phi": phi, "r": r, "M": np.ones((H, W), bool), "devant": np.ones((H, W), bool)}
    camera = {"x": 0.0, "y": 0.0, "z": 1.3, "cap": 0.0, "f": 600.0}
    boite = [500, 300, 700, 600]
    assert pl.place_d_un_meuble(boite, repere, camera, 1200, 800) is not None
    assert pl.place_d_un_meuble(boite, repere, camera, 1200, 800, devant=[[450, 320, 760, 790]]) is None


def test_le_plus_sur_est_garde_quand_il_y_en_a_trop():
    net = {"vues": 1, "confiance": 0.55, "distance_min": 2.3}
    devine = {"vues": 2, "confiance": 0.5, "distance_min": 6.0}
    assert rm.surete(net) > rm.surete(devine)
    assert rm.surete({"vues": 2, "confiance": 0.5}) > rm.surete({"vues": 1, "confiance": 0.55})  # sans distance : comme avant
