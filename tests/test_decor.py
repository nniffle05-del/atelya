"""Décor proposé par Atelya (moteur/decor.py)."""
import math

from moteur.decor import decorer

LOGEMENT = {
    "hauteur_sous_plafond": 2.6,
    "pieces": [{"id": "sejour", "contour": [[0, 0], [5, 0], [5, 4], [0, 4]]}],
    "meubles": [
        {"id": "canape", "categorie": "canape", "piece": "sejour", "position": [2.5, 0.45], "face": 90, "dimensions": [2.2, 0.9, 0.85]},
        {"id": "table", "categorie": "table_basse", "piece": "sejour", "position": [2.5, 1.6], "face": 90, "dimensions": [1.2, 0.6, 0.4]},
    ],
}


def test_decor_autour_des_meubles():
    ajouts = decorer(LOGEMENT, graine=3)
    coussins = [o for o in ajouts if o["categorie"] == "coussin"]
    assert 2 <= len(coussins) <= 4
    assert all(o["altitude"] == 0.42 and o["position"][1] < 0.45 for o in coussins)  # sur l'assise, côté dossier (sud)
    (vase,) = [o for o in ajouts if o["categorie"] == "vase"]
    assert vase["position"] == [2.5, 1.6] and vase["altitude"] == 0.4
    (tableau,) = [o for o in ajouts if o["categorie"] == "tableau"]
    assert tableau["position"][1] < 0.05 and tableau["altitude"] >= 1.1  # contre le mur sud, au-dessus du canapé
    assert all(o["statut"] == "ajoute" and o["source"] == "décor proposé par Atelya" for o in ajouts)
    assert len({o["id"] for o in ajouts}) == len(ajouts)


def test_decor_stable_et_plante_dans_un_coin_libre():
    assert decorer(LOGEMENT, graine=7) == decorer(LOGEMENT, graine=7)
    for g in range(1, 20):
        for p in [o for o in decorer(LOGEMENT, graine=g) if o["categorie"] == "plante"]:
            assert all(math.dist(p["position"], m["position"]) > 0.7 for m in LOGEMENT["meubles"])
