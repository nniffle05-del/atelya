"""Les chaises et tabourets rangés autour de leur table, tournés vers elle (étape 3, 17/11/2026, moteur/tablees.py).

Pourquoi ces tests (NT : « mettre les chaises sous les tables, comme sur les photos, vu que là ça n'a pas trop de sens ») : les
chaises étaient posées une à une là où tombait leur pied, tournées au hasard. Chaque test pose une table et des chaises « vues »
de travers, et vérifie la tablée rangée : bons côtés, face à la table, pas égaux, rien dans un mur, zéro collision.
"""
import math

from moteur import collisions, tablees
from moteur.ranger_meubles import chevauchements

PIECE = {"id": "sejour_1", "contour": [[0.0, 0.0], [6.0, 0.0], [6.0, 5.0], [0.0, 5.0]]}
LOGEMENT = {"pieces": [PIECE], "murs": [], "ouvertures": [], "hauteur_sous_plafond": 2.5}
SOURCE = "repérage par lecture des photos (1 photo(s))"


def meuble(ident, categorie, position, dimensions, face=0.0, **plus):
    return {"id": ident, "categorie": categorie, "piece": "sejour_1", "position": list(position), "face": face,
            "dimensions": list(dimensions), "statut": "estime", "source": SOURCE, "confiance": 0.5, **plus}


def chaise(ident, x, y, face=37.0, categorie="chaise"):
    return meuble(ident, categorie, (x, y), (0.5, 0.55, 0.85) if categorie == "chaise" else (0.45, 0.45, 1.0), face)


def vers(m, cible) -> float:
    """L'angle (degrés) entre le regard du siège et la direction de la cible."""
    a = math.degrees(math.atan2(cible[1] - m["position"][1], cible[0] - m["position"][0]))
    return abs((a - m["face"] + 180.0) % 360.0 - 180.0)


def test_six_chaises_autour_d_une_grande_table():
    table = meuble("table", "table", (3.0, 2.5), (1.95, 1.0, 0.75), 90.0)  # son grand côté le long de x
    vues = [chaise("a", 2.4, 1.6), chaise("b", 3.5, 1.75), chaise("c", 2.6, 3.4), chaise("d", 3.6, 3.2),  # deux de chaque grand côté
            chaise("e", 1.7, 2.6), chaise("f", 4.4, 2.4)]  # une à chaque bout
    ranges, actions = tablees.ranger([table, *vues], LOGEMENT)
    par_id = {m["id"]: m for m in ranges}
    assert sorted(actions[0]["sieges"]) == list("abcdef") and not actions[0]["restes"]
    t = par_id["table"]["position"]
    assert all(vers(par_id[i], t) < 50 for i in "abcdef")  # toutes regardent la table
    assert par_id["a"]["face"] == par_id["b"]["face"] == 90.0 and par_id["c"]["face"] == par_id["d"]["face"] == -90.0
    assert par_id["e"]["face"] == 0.0 and abs(abs(par_id["f"]["face"]) - 180.0) < 0.1
    # du même côté : à la même distance de la table ; d'un côté à l'autre : face à face
    assert abs(par_id["a"]["position"][1] - par_id["b"]["position"][1]) < 1e-6
    assert abs(par_id["a"]["position"][0] - par_id["c"]["position"][0]) < 1e-6
    assert chevauchements(ranges) == []  # rentrées, mais pas plus que le contrôle des collisions ne le tolère
    assert collisions.mesurer({**LOGEMENT, "meubles": ranges}) == []


def test_ranger_deux_fois_ne_change_plus_rien():
    table = meuble("table", "table", (3.0, 2.5), (1.8, 0.96, 0.75), 90.0)
    vues = [chaise("a", 2.4, 1.6), chaise("b", 3.5, 1.75), chaise("c", 2.6, 3.4), chaise("d", 4.3, 2.5)]
    une_fois, _ = tablees.ranger([table, *vues], LOGEMENT)
    deux_fois, _ = tablees.ranger(une_fois, LOGEMENT)
    for a, b in zip(une_fois, deux_fois):
        assert math.dist(a["position"], b["position"]) < 0.02 and abs((a["face"] - b["face"] + 180) % 360 - 180) < 0.1


def test_les_tabourets_d_un_ilot_sont_du_meme_cote_et_l_allongent():
    ilot = meuble("ilot", "ilot", (3.0, 3.0), (2.0, 0.9, 0.9), -90.0)
    vus = [chaise(f"t{k}", x, y, categorie="tabouret_haut") for k, (x, y) in enumerate([(2.1, 2.2), (2.7, 2.3), (3.3, 2.1), (3.2, 3.7)])]
    ranges, _ = tablees.ranger([ilot, *vus], LOGEMENT)
    par_id = {m["id"]: m for m in ranges}
    assert par_id["ilot"]["dimensions"][0] == 2.4  # quatre tabourets : l'îlot fait au moins 2,40 m
    ys = {round(par_id[f"t{k}"]["position"][1], 2) for k in range(4)}
    assert len(ys) == 1 and ys.pop() < par_id["ilot"]["position"][1]  # tous en rang du côté où la plupart sont vus
    assert all(par_id[f"t{k}"]["face"] == 90.0 for k in range(4))
    assert collisions.mesurer({**LOGEMENT, "meubles": ranges}) == []  # un tabouret ne passe pas sous son îlot


def test_la_chaise_de_bureau_devant_son_bureau():
    bureau = meuble("bureau", "bureau", (0.4, 2.5), (1.3, 0.65, 0.75), 0.0)  # contre le mur de gauche, devant tourné vers la pièce
    ch = chaise("c", 1.2, 2.9, face=120.0, categorie="chaise_de_bureau")
    ranges, _ = tablees.ranger([bureau, ch], LOGEMENT)
    c = {m["id"]: m for m in ranges}["c"]
    assert abs(abs(c["face"]) - 180.0) < 0.1 and c["position"][0] > 0.4 + 0.65 / 2  # devant le bureau, tournée vers lui


def test_table_ronde_les_chaises_en_couronne_sans_se_toucher():
    table = meuble("table", "table", (3.0, 2.5), (0.86, 0.86, 0.75))
    vues = [chaise("a", 3.6, 2.6), chaise("b", 3.5, 2.9), chaise("c", 2.5, 2.0)]  # a et b vues presque au même endroit
    ranges, _ = tablees.ranger([table, *vues], LOGEMENT)
    par_id = {m["id"]: m for m in ranges}
    assert all(vers(par_id[i], par_id["table"]["position"]) < 1.0 for i in "abc")
    assert chevauchements(ranges) == []


def test_un_cote_contre_un_mur_ne_recoit_personne_et_rien_de_fixe_ne_bouge():
    table = meuble("table", "table", (3.0, 0.55), (1.8, 0.9, 0.75), 90.0)  # collée au mur du bas
    vues = [chaise("a", 2.6, 0.3), chaise("b", 3.4, 1.5)]
    ranges, _ = tablees.ranger([table, *vues], LOGEMENT)
    par_id = {m["id"]: m for m in ranges}
    assert par_id["a"]["position"][1] >= par_id["table"]["position"][1]  # jamais du côté du mur : au bout ou du côté libre
    assert collisions.mesurer({**LOGEMENT, "meubles": ranges}) == []
    releve = {**chaise("r", 2.0, 2.0), "statut": "mesure", "source": "relevé"}  # placée par quelqu'un : jamais déplacée
    ranges, _ = tablees.ranger([meuble("table", "table", (3.0, 2.5), (1.8, 0.9, 0.75), 90.0), releve], LOGEMENT)
    assert {m["id"]: m for m in ranges}["r"]["position"] == [2.0, 2.0]
    loin = chaise("l", 0.6, 4.5)  # à plus de 80 cm de toute table : ce n'est pas une chaise de la tablée
    ranges, actions = tablees.ranger([meuble("table", "table", (3.0, 2.5), (1.8, 0.9, 0.75), 90.0), loin], LOGEMENT)
    assert {m["id"]: m for m in ranges}["l"]["position"] == [0.6, 4.5] and actions == []


def test_une_table_deplacee_par_la_reparation_emmene_ses_chaises():
    table = meuble("table", "table", (3.0, 2.5), (1.8, 0.96, 0.75), 90.0)
    vues = [chaise("a", 2.5, 1.7), chaise("b", 3.5, 1.7), chaise("c", 2.5, 3.3), chaise("d", 3.5, 3.3)]
    ranges, _ = tablees.ranger([table, *vues], LOGEMENT)
    # un poteau bâti traverse le bout de la table : la réparation pousse la table ; ses chaises restent autour d'elle
    poteau = {**meuble("poteau", "cheminee", (4.05, 2.5), (0.4, 0.4, 2.0)), "statut": "mesure", "source": "relevé"}
    repare, _ = collisions.reparer({**LOGEMENT, "meubles": [poteau, *ranges]})
    par_id = {m["id"]: m for m in repare["meubles"]}
    assert set("abcd") <= set(par_id) and math.dist(par_id["table"]["position"], (3.0, 2.5)) > 0.05
    assert tablees.sieges_ranges(repare["meubles"]).keys() >= {id(par_id[i]) for i in "abcd"}
    assert collisions.mesurer(repare) == []


def test_les_chaises_d_une_meme_table_sont_assorties():
    table = meuble("table", "table", (3.0, 2.5), (1.8, 0.96, 0.75), 90.0)
    vues = [{**chaise("a", 2.5, 1.7), "couleur": [90, 60, 40]}, {**chaise("b", 3.5, 1.7), "couleur": [100, 70, 50]},
            {**chaise("c", 2.5, 3.3), "couleur": [80, 50, 30]}, {**chaise("t", 3.5, 3.3, categorie="tabouret_haut"), "couleur": [200, 200, 200]}]
    ranges, _ = tablees.ranger([table, *vues], LOGEMENT)
    par_id = {m["id"]: m for m in ranges}
    assert par_id["a"]["couleur"] == par_id["b"]["couleur"] == par_id["c"]["couleur"] == [90, 60, 40]  # la médiane des trois chaises
    assert par_id["t"]["couleur"] == [200, 200, 200]  # une autre sorte de siège garde la sienne
