"""Le banc de fidélité de la maquette aux photos, objet par objet (moteur/fidelite_photos.py) : les calculs, sans détecteur."""
import numpy as np

from moteur import fidelite_photos as fp

W, H = 1200, 800
CAM = [0.0, 0.0, 1.3, 0.0, 0.0, 600.0, 600.0, 400.0]  # à l'origine, 1,30 m de haut, regarde vers +x


def _d(nom, note, boite):
    return {"nom": nom, "note": note, "boite": list(boite)}


def test_recouvrement_et_part_dedans():
    assert fp.recouvrement([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert fp.recouvrement([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert abs(fp.recouvrement([0, 0, 10, 10], [5, 0, 15, 10]) - 1 / 3) < 1e-9
    assert fp.part_dedans([2, 2, 4, 4], [0, 0, 10, 10]) == 1.0 and fp.part_dedans([0, 0, 10, 10], [2, 2, 4, 4]) == 0.04


def test_objets_de_la_photo_notes_minimales_et_sortes_ignorees():
    objets = fp.objets_de_la_photo([_d("a bed", 0.6, (100, 400, 600, 780)), _d("a sofa", 0.3, (700, 400, 1100, 700)),  # canapé : il faut 0,5
                                    _d("a pillow", 0.9, (200, 420, 300, 480)), _d("a fireplace", 0.45, (800, 300, 1000, 600)),
                                    _d("a chair", 0.5, (10, 10, 20, 20))], W, H)  # trop petit
    assert sorted(o["sorte"] for o in objets) == ["cheminee", "lit"]


def test_deux_phrases_pour_le_meme_meuble_ne_font_qu_un_objet():
    objets = fp.objets_de_la_photo([_d("a bed", 0.6, (100, 400, 600, 780)), _d("a bed with a duvet", 0.5, (110, 410, 590, 770))], W, H)
    assert len(objets) == 1 and objets[0]["phrase"] == "a bed"


def test_un_morceau_et_son_tout():
    armoire, tiroir = _d("a wardrobe", 0.5, (700, 100, 1100, 780)), _d("a cabinet", 0.6, (720, 600, 900, 760))
    assert [o["phrase"] for o in fp.objets_de_la_photo([armoire, tiroir], W, H)] == ["a wardrobe"]  # le tout remplace le morceau
    flou = _d("a cabinet", 0.26, (0, 0, 1200, 800))  # un grand rectangle peu sûr autour d'un meuble sûr : on garde le meuble
    assert [o["phrase"] for o in fp.objets_de_la_photo([tiroir, flou], W, H)] == ["a cabinet"]
    assert fp.objets_de_la_photo([tiroir, flou], W, H)[0]["boite"] == [720.0, 600.0, 900.0, 760.0]


def test_rectangle_d_un_meuble_devant_et_derriere_l_appareil():
    devant = fp._points_du_meuble({"position": [3.0, 0.0], "face": 180.0, "dimensions": [1.2, 0.5, 0.9]})
    b = fp.rectangle_dans_la_photo(devant, CAM, W, H)
    assert b is not None and b[0] < 600 < b[2] and b[1] > 400  # centré, sous l'horizon (le meuble est plus bas que l'appareil)
    derriere = fp._points_du_meuble({"position": [-3.0, 0.0], "face": 0.0, "dimensions": [1.2, 0.5, 0.9]})
    assert fp.rectangle_dans_la_photo(derriere, CAM, W, H) is None
    hors_cadre = fp._points_du_meuble({"position": [1.0, 6.0], "face": 0.0, "dimensions": [1.2, 0.5, 0.9]})
    assert fp.rectangle_dans_la_photo(hors_cadre, CAM, W, H) is None


LOGEMENT = {"hauteur_sous_plafond": 2.5,
            "murs": [{"id": "M1", "debut": [2.0, -3.0], "fin": [2.0, 3.0], "epaisseur": 0.1}],  # une cloison devant l'appareil
            "ouvertures": [{"id": "O1", "type": "porte", "mur": "M1", "position": 2.6, "largeur": 0.8, "hauteur": 2.04, "allege": 0.0}],
            "meubles": [{"id": "lit", "categorie": "lit", "position": [4.0, 0.0], "face": 180.0, "dimensions": [1.6, 2.0, 0.6]},  # par la porte
                        {"id": "canape", "categorie": "canape", "position": [4.0, 2.2], "face": 180.0, "dimensions": [2.0, 0.9, 0.8]},  # derrière le mur
                        {"id": "vase", "categorie": "vase", "position": [1.0, 0.0], "face": 0.0, "dimensions": [0.2, 0.2, 0.3]}]}


def test_un_mur_cache_une_porte_laisse_voir():
    murs = fp._murs_et_trous(LOGEMENT)
    assert not fp.cache_par_un_mur((0, 0), (4.0, 0.0), murs)  # à travers la porte (de −0,4 à +0,4 m sur le mur)
    assert fp.cache_par_un_mur((0, 0), (4.0, 2.2), murs)
    vus = fp.objets_de_la_maquette(LOGEMENT, CAM, W, H)
    assert sorted(o["id"] for o in vus) == ["O1", "lit"]  # le canapé est caché, le vase n'est pas jugé


def test_paires_et_bilan():
    photo = fp.objets_de_la_photo([_d("a bed", 0.7, (380, 420, 830, 640)), _d("a fireplace", 0.5, (900, 300, 1100, 600)),
                                   _d("a door", 0.5, (470, 150, 730, 610))], W, H)
    maquette = fp.objets_de_la_maquette(LOGEMENT, CAM, W, H)
    fp.apparier(photo, maquette)
    par_sorte = {o["sorte"]: o for o in photo}
    assert par_sorte["lit"]["paire"] == "lit" and par_sorte["cheminee"]["paire"] is None and par_sorte["porte"]["paire"] == "O1"
    bilan = fp.compter([{"largeur": W, "hauteur": H, "photo": photo, "maquette": maquette}])
    assert bilan["par_sorte"]["cheminee"] == {"vus": 1, "presents": 0, "bien_places": 0, "dans_la_maquette": 0, "en_trop": 0,
                                               "poids_manque": bilan["par_sorte"]["cheminee"]["poids_manque"]}
    assert bilan["par_sorte"]["lit"]["presents"] == 1 and bilan["justesse"] == 1.0 and 0.5 < bilan["couverture"] < 1.0
    assert 0 < bilan["fidelite"] < 100


def test_haute_fenetre_vue_porte_par_le_detecteur_forme_une_paire():
    photo = [{"sorte": "porte", "phrase": "a door", "note": 0.5, "boite": [100.0, 100.0, 300.0, 600.0]}]
    maquette = [{"id": "O7", "sorte": "baie", "categorie": "porte_fenetre", "boite": [110.0, 120.0, 310.0, 620.0]}]
    fp.apparier(photo, maquette)
    assert photo[0]["paire"] == "O7" and maquette[0]["paire"] is not None
