"""La lecture des photos par Claude (essai du 16/11/2026) : le format de la fiche et ce qu'Atelya en garde."""
from moteur import lecture_photos as lp

LISTE = [{"numero": 1, "detecteur": "table", "phrase": "a table", "note": 0.6, "boite": [100, 300, 500, 600]},
         {"numero": 2, "detecteur": "rangement", "phrase": "a wardrobe", "note": 0.4, "boite": [600, 100, 900, 700]},
         {"numero": 3, "detecteur": "rangement", "phrase": "a cabinet", "note": 0.3, "boite": [650, 400, 880, 690]},
         {"numero": 4, "detecteur": "miroir", "phrase": "a mirror", "note": 0.5, "boite": [20, 50, 90, 200]},
         {"numero": 5, "detecteur": "luminaire", "phrase": "a pendant lamp", "note": 0.7, "boite": [300, 0, 400, 90]}]


def test_notes_courtes_vers_la_fiche():
    f = lp.fiche_depuis_notes("1 table ronde, bois clair ; 2 placard armoire blanche ; 3 = 2 ; 4 faux reflet ; 5 suspension",
                              "lames + carreaux", "radiateur 0,600,215,790 ; canape 10,20,30,40 gris")
    assert f["objets"]["1"] == {"sorte": "table", "note": "ronde, bois clair", "couleur": "bois clair", "forme": "ronde"}
    assert f["objets"]["2"]["sorte"] == "placard" and f["objets"]["2"]["couleur"] == "blanche"
    assert f["objets"]["3"] == {"meme_que": 2} and f["objets"]["4"]["sorte"] == "faux"
    assert f["sol"] == {"famille": "lames", "uniforme": False, "autre_famille": "carreaux"}
    assert f["manquants"] == [{"sorte": "radiateur", "boite": [0, 600, 215, 790]},
                              {"sorte": "canape", "boite": [10, 20, 30, 40], "note": "gris", "couleur": "gris"}]
    assert lp.controler(f, {1, 2, 3, 4, 5}) == []


def test_un_seul_sol_et_pas_de_sol():
    assert lp.fiche_depuis_notes("1 lit", "point_de_hongrie")["sol"] == {"famille": "point_de_hongrie", "uniforme": True}
    assert lp.fiche_depuis_notes("1 lit")["sol"] == {"famille": None, "uniforme": True}


def test_controle_des_defauts():
    f = lp.fiche_depuis_notes("1 tabouret ; 2 placard ; 3 = 9 ; 7 chaise", "moquette", "cheminee 1,2,3,4")
    defauts = lp.controler(f, {1, 2, 3, 4})
    assert any("sorte 'tabouret' inconnue" in d for d in defauts)
    assert any("numéro 7 inconnu" in d for d in defauts)
    assert any("« meme_que » 9 inconnu" in d for d in defauts)
    assert any("numéro 4 oublié" in d for d in defauts)
    assert any("famille 'moquette' inconnue" in d for d in defauts)
    # un « même que » ne renvoie pas à un numéro qui renvoie lui-même ailleurs
    chaine = lp.fiche_depuis_notes("1 lit ; 2 = 1 ; 3 = 2")
    assert any("renvoie lui-même" in d for d in lp.controler(chaine, {1, 2, 3}))


def test_objets_lus_faux_doublons_et_manquants():
    f = lp.fiche_depuis_notes("1 bureau blanc ; 2 placard ; 3 = 2 ; 4 faux", manquants="lit_superpose 730,300,1206,640 bois")
    lus = lp.objets_lus(f, LISTE)
    assert [(o["numero"], o["sorte"]) for o in lus] == [(1, "bureau"), (2, "placard"), (5, "suspension"), (-1, "lit_superpose")]
    assert lus[0]["couleur_dite"] == "blanc" and lus[0]["boite"] == [100, 300, 500, 600]
    assert lus[3]["approche"] is True and lus[3]["boite"] == [730.0, 300.0, 1206.0, 640.0]
    # le numéro 5, que la lecture n'a pas rempli, garde ce que le détecteur croit
    assert lus[2]["sorte"] == "suspension"
    assert len(lp.objets_lus(f, LISTE, manquants=False)) == 3


def test_sans_lecture_la_sorte_du_detecteur():
    sortes = [o["sorte"] for o in lp.objets_du_detecteur(LISTE)]
    assert sortes == ["table", "placard", "rangement", "miroir", "suspension"]  # la phrase précise d'abord, sinon la sorte du banc


def test_la_consigne_nomme_toutes_les_sortes():
    texte = lp.consigne()
    assert all(s in texte for s in lp.SORTES) and all(f in texte for f in lp.FAMILLES_DE_SOL) and lp.SCHEMA in texte
