"""Les RANGÉES de cuisine (17/11/2026) : la lecture des photos dit la suite des éléments le long de chaque mur, Atelya les range
bout à bout depuis le coin, par modules de 60 cm (moteur/rangees.py)."""
import math

import numpy as np

from moteur import caler_photos as cp
from moteur import lecture_photos as lp
from moteur import rangees as rg

MUR = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
LOGEMENT = {"hauteur_sous_plafond": 2.5,
            "murs": [MUR("M1", (10.1, 0), (10.1, 6)), MUR("M3", (0, -0.1), (10, -0.1)), MUR("M4", (0, 6.1), (10, 6.1)), MUR("M5", (-0.1, 0), (-0.1, 6))],
            # un sommet de trop au milieu du mur nord (5, 6) : il ne coupe pas le mur en deux
            "ouvertures": [], "pieces": [{"id": "cuisine_1", "contour": [[0, 0], [10, 0], [10, 6], [5, 6], [0, 6]]}]}
PLAN = cp.plan_du_logement(LOGEMENT)
# appareil au milieu de la pièce, qui regarde le mur nord (cap 90) : à l'image, la gauche est l'ouest
CAM = [5.0, 3.0, 1.3, 90.0, 0.0, 600.0, 600.0, 400.0]
BOITES = {1: [550, 300, 650, 500], 2: [100, 100, 200, 600], 3: [20, 100, 80, 700]}


def test_les_notes_et_le_controle():
    fiche = lp.fiche_depuis_notes("1 meuble_cuisine_bas ; 2 colonne_cuisine ; 3 colonne_cuisine",
                                  rangees="vers1 : coin colonne(2) bas*(1) coin ; gauche1 : cadre colonne(3) colonne angle")
    assert lp.controler(fiche, {1, 2, 3}) == []
    un, deux = fiche["rangees"]
    assert un["mur"] == {"repere": "vers", "numero": 1} and deux["mur"]["repere"] == "gauche"
    assert un["suite"][2] == {"sorte": "meuble_cuisine_bas", "reste": True, "numeros": [1]}
    assert [e["sorte"] for e in deux["suite"]] == ["cadre", "colonne_cuisine", "colonne_cuisine", "angle"]
    assert lp.rangees_depuis_notes("vers1 : coin basx3(1,2) frigo cadre")[0]["suite"][1] == {"sorte": "meuble_cuisine_bas", "modules": 3.0, "numeros": [1, 2]}
    # une rangée qu'aucun coin ne cale, ou qui cite un rectangle inconnu, est refusée
    sans_coin = {"objets": {"1": {"sorte": "meuble_cuisine_bas"}}, "rangees": lp.rangees_depuis_notes("vers1 : cadre bas(9) cadre")}
    defauts = lp.controler(sans_coin, {1})
    assert any("aucun bout calé" in d for d in defauts) and any("numéro 9" in d for d in defauts)


def test_ranger_une_suite_sur_un_mur():
    suite = lambda texte: lp.rangees_depuis_notes(f"vers1 : {texte}")[0]["suite"]
    # deux coins : la colonne dans le coin, le meuble bas remplit le reste
    r = rg.ranger(suite("coin colonne(4) bas*(24) coin"), 4.27)
    assert [(x["sorte"], round(x["debut"], 2), round(x["fin"], 2)) for x in r] == [("colonne_cuisine", 0.0, 0.6), ("meuble_cuisine_bas", 0.6, 4.27)]
    # calée à droite seulement, sur un angle pris par la rangée voisine : deux colonnes qui se suivent font UN meuble
    r = rg.ranger(suite("cadre colonne(3) colonne angle"), 3.61)
    assert len(r) == 1 and abs(r[0]["fin"] - (3.61 - rg.ANGLE_M)) < 1e-6 and abs(r[0]["fin"] - r[0]["debut"] - 1.2) < 1e-6
    # calée à gauche, des modules comptés ; un vide ne pose rien mais prend sa place
    r = rg.ranger(suite("coin basx3(7) vide colonne(3) frigo(1) cadre"), 5.0)
    assert [(x["sorte"], round(x["debut"], 2), round(x["fin"], 2)) for x in r] == [
        ("meuble_cuisine_bas", 0.0, 1.8), ("colonne_cuisine", 2.4, 3.0), ("refrigerateur", 3.0, 3.6)]
    # aucun coin, ou « le reste » qui ne tient pas entre deux coins : pas rangée (les rectangles sont alors posés comme avant)
    assert rg.ranger(suite("cadre bas colonne cadre"), 3.0) is None
    assert rg.ranger(suite("coin colonnex4 bas* coin"), 2.5) is None


def test_les_murs_d_une_piece_et_le_sens_de_l_image():
    toutes = rg.faces(LOGEMENT)
    assert len(toutes) == 4  # le sommet au milieu du mur nord ne compte pas
    nord = next(f for f in toutes if abs(f["normale"][1] + 1) < 1e-6)
    ouest = next(f for f in toutes if abs(f["normale"][0] - 1) < 1e-6)
    assert abs(np.linalg.norm(nord["b"] - nord["a"]) - 10.0) < 1e-6
    # mur de face : la droite de l'image est l'est ; mur de GAUCHE (il file le long du regard) : la droite de l'image s'éloigne
    est_a_droite = rg.sens_de_l_image(nord, CAM) * (1.0 if nord["b"][0] > nord["a"][0] else -1.0)
    nord_a_droite = rg.sens_de_l_image(ouest, CAM) * (1.0 if ouest["b"][1] > ouest["a"][1] else -1.0)
    assert est_a_droite == 1.0 and nord_a_droite == 1.0
    assert rg.voisine(nord, "gauche", CAM, toutes) is ouest


def test_poser_les_rangees_dites_par_deux_photos():
    decl = lambda photo, texte, cam=CAM: [{"photo": photo, "cam": cam, "mur": r["mur"], "suite": r["suite"], "boites": BOITES,
                                          "couleurs": {1: [120, 120, 120], 2: [100, 100, 100]}} for r in lp.rangees_depuis_notes(texte)]
    # la seconde photo voit le même mur du fond, moins bien calé (un bout sort du cadre) : c'est la première qui est rangée,
    # et les rectangles des DEUX photos sont pris
    r = rg.poser(decl("photo-a", "vers1 : coin colonne(2) bas*(1) coin ; gauche1 : cadre colonne(3) colonne angle")
                 + decl("photo-b", "vers1 : cadre bas*(1) coin"), LOGEMENT, PLAN)
    par_sorte = {(m["categorie"], m["face"]): m for m in r["meubles"]}
    assert len(r["meubles"]) == 3
    colonne, bas, cote = par_sorte[("colonne_cuisine", -90.0)], par_sorte[("meuble_cuisine_bas", -90.0)], par_sorte[("colonne_cuisine", 0.0)]
    assert math.dist(colonne["position"], (0.3, 5.68)) < 0.02 and colonne["dimensions"] == [0.59, 0.6, 2.2]
    assert math.dist(bas["position"], (5.3, 5.68)) < 0.02 and abs(bas["dimensions"][0] - 9.39) < 0.02 and bas["couleur"] == [120, 120, 120]
    # mur de gauche : deux colonnes, qui s'arrêtent à l'angle pris par la rangée du fond
    assert math.dist(cote["position"], (0.32, 4.76)) < 0.02 and cote["dimensions"][0] == 1.19
    assert r["pris"] == {("photo-a", 1), ("photo-a", 2), ("photo-a", 3), ("photo-b", 1)}
    assert all("repérage" not in m["source"] and "lecture" not in m["source"] for m in r["meubles"])  # la réparation ne les déplace pas
    # aucune collision entre les éléments rangés, ni avec les murs
    from moteur import collisions
    assert collisions.mesurer({**LOGEMENT, "meubles": r["meubles"]}) == []


def test_un_mur_a_pilier_et_petit_decroche():
    # une cuisine dont le mur nord porte un pilier (34 × 43 cm) puis un pan en retrait de 18 cm : le retrait est le même mur
    cuisine = {"pieces": [{"id": "cuisine_1", "contour": [[0, 5.85], [0, 4.3], [2.79, 4.3], [2.79, 5.85], [2.15, 5.85], [2.14, 5.67],
                                                          [1.79, 5.67], [1.78, 5.4], [1.44, 5.42], [1.44, 5.85]]}]}
    toutes = rg.faces(cuisine)
    assert len(toutes) == 8
    long = lambda f: float(np.linalg.norm(f["b"] - f["a"]))
    apres_le_pilier = next(f for f in toutes if abs(long(f) - 1.0) < 0.02)
    assert abs(apres_le_pilier["normale"][1] + 1) < 0.01 and abs(apres_le_pilier["a"][1] - 5.67) < 0.02  # le pan qui avance, prolongé
    # depuis l'entrée, l'appareil regarde vers la fenêtre (mur ouest) : à sa droite le mur de l'évier, puis, passé le pilier, ce pan
    cam = [2.73, 5.03, 1.37, 146.0, 0.0, 628.0, 603.0, 388.0]
    ouest = next(f for f in toutes if abs(f["normale"][0] - 1) < 0.01 and abs(long(f) - 1.55) < 0.02)
    evier = rg.voisine(ouest, "droite", cam, toutes)
    assert abs(long(evier) - 1.44) < 0.02
    assert rg.voisine(ouest, "droite", cam, toutes, saut=1) is apres_le_pilier
    mur = lp.rangees_depuis_notes("droite6+1 : coin colonnex1.5(2) cadre")[0]
    assert mur["mur"] == {"repere": "droite", "numero": 6, "saut": 1} and mur["suite"][1]["modules"] == 1.5
    # le placard est rangé depuis le pilier : de 1,79 à 2,69 m
    placard = rg.ranger(mur["suite"], long(apres_le_pilier))
    assert rg.sens_de_l_image(apres_le_pilier, cam) * (1.0 if apres_le_pilier["b"][0] > apres_le_pilier["a"][0] else -1.0) == 1.0  # la droite : l'est
    assert [(round(x["debut"], 2), round(x["fin"], 2)) for x in placard] == [(0.0, 0.9)]
