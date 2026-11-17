"""Meubles rangés (NT, 15/11/2026) : jamais deux meubles au même endroit, jamais un meuble dans un mur, moins de doublons."""
from moteur.ranger_meubles import chevauchements, ranger, recouvrement
from moteur.reperer_meubles import plafonner

PIECE = {"id": "sejour_1", "contour": [[0, 0], [5, 0], [5, 4], [0, 4]]}
LOGEMENT = {"pieces": [PIECE]}


def _m(ident, categorie, x, y, dims, face=90.0, vues=1, confiance=0.5, **plus):
    return {"id": ident, "categorie": categorie, "piece": "sejour_1", "position": [x, y], "face": face, "dimensions": list(dims),
            "statut": "estime", "source": f"repérage photos ({vues} photo(s))", "confiance": confiance, **plus}


def test_recouvrement_de_deux_meubles():
    table = _m("t", "table", 2.5, 2.0, (1.4, 0.8, 0.75))
    assert recouvrement(_m("c", "chaise", 2.5, 2.0, (0.5, 0.55, 0.85)), table) == 1.0  # la chaise est dans la table
    assert recouvrement(_m("c", "chaise", 4.5, 3.5, (0.5, 0.55, 0.85)), table) == 0.0


def test_chaise_plantee_dans_la_table_reculee_et_tournee_vers_elle():
    table = _m("t", "table", 2.5, 2.0, (1.4, 0.8, 0.75), vues=3)
    chaise = _m("c", "chaise", 2.5, 2.1, (0.5, 0.55, 0.85))
    ranges, actions = ranger([table, chaise], LOGEMENT)
    assert len(ranges) == 2 and chevauchements(ranges) == []
    assert ranges[0]["position"] == [2.5, 2.0]  # la table, plus sûre, ne bouge pas
    assert [a["action"] for a in actions] == ["déplacé"]


def test_meme_meuble_vu_deux_fois_garde_une_fois():
    a = _m("a", "canape", 2.0, 0.5, (2.1, 0.9, 0.85), vues=4)
    b = _m("b", "canape", 2.6, 0.6, (2.1, 0.9, 0.85), vues=1)
    ranges, actions = ranger([b, a], LOGEMENT)
    assert [m["id"] for m in ranges] == ["a"] and actions[0]["action"] == "retiré"


def test_deux_chaises_voisines_restent_deux_chaises():
    a = _m("a", "chaise", 2.0, 2.0, (0.5, 0.55, 0.85), vues=2)
    b = _m("b", "chaise", 2.4, 2.0, (0.5, 0.55, 0.85))  # 10 cm de recouvrement : deux vraies chaises côte à côte
    ranges, _ = ranger([a, b], LOGEMENT)
    assert len(ranges) == 2 and chevauchements(ranges) == []


def test_un_objet_pris_pour_deux_sortes_garde_le_plus_gros():
    rangement = _m("r", "rangement", 2.0, 0.3, (1.2, 0.45, 0.9), vues=2)
    table = _m("t", "table", 2.05, 0.35, (1.4, 0.8, 0.75), vues=2)  # le meuble télé, vu aussi comme « table »
    ranges, _ = ranger([table, rangement], LOGEMENT)
    assert [m["id"] for m in ranges] == ["r"]


def test_meuble_dans_le_mur_ramene_dans_la_piece():
    r = _m("r", "rangement", 4.95, 2.0, (1.2, 0.45, 0.9), face=180.0)  # à cheval sur le mur de droite
    ranges, actions = ranger([r], LOGEMENT)
    assert len(ranges) == 1 and ranges[0]["position"][0] < 4.85 and actions[0]["action"] == "déplacé"


def test_table_sans_place_devient_table_d_appoint():
    lit = _m("l", "lit", 2.5, 1.1, (1.6, 2.05, 1.0), vues=3)
    piece = {"id": "sejour_1", "contour": [[1.0, 0], [4.0, 0], [4.0, 2.4], [1.0, 2.4]]}  # 70 cm de chaque côté du lit seulement
    table = _m("t", "table", 3.3, 1.6, (1.4, 0.8, 0.75))
    ranges, _ = ranger([lit, table], {"pieces": [piece]})
    assert len(ranges) == 2 and chevauchements(ranges) == []
    assert ranges[1]["dimensions"][0] < 1.0  # rétrécie plutôt que retirée


def test_meuble_place_a_la_main_jamais_touche_et_tapis_ignore():
    a_la_main = _m("m", "table", 2.5, 2.0, (1.4, 0.8, 0.75), statut="mesure", source="verification")
    trouve = _m("t", "table", 2.6, 2.0, (1.4, 0.8, 0.75), vues=5)
    tapis = _m("p", "tapis", 2.5, 2.0, (1.8, 1.3, 0.02))
    ranges, _ = ranger([trouve, a_la_main, tapis], LOGEMENT)
    assert [m["id"] for m in ranges] == ["m", "p"] and ranges[0] == a_la_main


def _vu(groupe, x, y, vues=1, confiance=0.5):
    return {"groupe": groupe, "position": [x, y], "vues": vues, "confiance": confiance, "largeur_vue": 0.5}


def test_plafond_des_chaises_par_tablee():
    # deux vraies chaises autour d'une table, vues ensemble sur chaque photo, mais posées quatre fois (photos mal placées)
    trouves = [_vu("chaise", 1.0, 1.0, 3), _vu("chaise", 1.6, 1.0, 3), _vu("chaise", 1.3, 1.6, 1), _vu("chaise", 1.9, 1.5, 1),
               _vu("chaise", 4.5, 3.5, 1)]  # … et une chaise seule, loin : une autre grappe
    par_photo = [[_vu("chaise", 1.0, 1.0), _vu("chaise", 1.6, 1.0)], [_vu("chaise", 1.3, 1.6), _vu("chaise", 1.9, 1.5)],
                 [_vu("chaise", 4.5, 3.5)]]
    gardes = plafonner(trouves, par_photo, LOGEMENT)
    assert [m["position"] for m in gardes] == [[1.0, 1.0], [1.6, 1.0], [4.5, 3.5]]


def test_plafond_des_canapes_par_piece_tables_et_rangements_libres():
    trouves = [_vu("canape", 1.0, 1.0, 3), _vu("canape", 4.0, 3.0, 1), _vu("rangement", 2.0, 0.3), _vu("rangement", 4.0, 0.3),
               _vu("table", 2.0, 2.0, 2), _vu("table", 4.0, 1.0, 1)]
    par_photo = [[_vu("canape", 1.0, 1.0), _vu("rangement", 2.0, 0.3), _vu("table", 2.0, 2.0)], [_vu("canape", 4.0, 3.0), _vu("table", 4.0, 1.0)]]
    gardes = plafonner(trouves, par_photo, LOGEMENT)
    # un seul canapé par photo : un seul canapé dans la pièce (le plus vu) ; les deux tables restent (aucune photo ne montre
    # les deux à la fois, mais ce sont deux meubles : les tables ne sont plus plafonnées depuis le 16/11/2026)
    assert [m["groupe"] for m in gardes] == ["canape", "rangement", "rangement", "table", "table"] and gardes[0]["position"] == [1.0, 1.0]
