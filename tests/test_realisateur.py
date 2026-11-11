"""Le réalisateur (moteur/realisateur.py) : il choisit seul des plans possibles (dans la pièce, loin des murs et des meubles),
qui montrent la pièce et sa fenêtre, dans l'ordre d'une visite, sans filmer les placards."""
import math

import numpy as np

from moteur import realisateur as r


def _logement():
    # un séjour de 6 × 4 m (fenêtre au sud), une chambre de 3 × 4 m à l'est, un placard ; un canapé dans le séjour
    murs = [{"id": "Ms", "debut": [0, 0], "fin": [9, 0], "epaisseur": 0.2}, {"id": "Mn", "debut": [0, 4], "fin": [9, 4], "epaisseur": 0.2},
            {"id": "Mo", "debut": [0, 0], "fin": [0, 4], "epaisseur": 0.2}, {"id": "Me", "debut": [9, 0], "fin": [9, 4], "epaisseur": 0.2},
            {"id": "Mc", "debut": [6, 0], "fin": [6, 4], "epaisseur": 0.1}]
    ouvertures = [{"id": "F1", "type": "fenetre", "mur": "Ms", "position": 2.0, "largeur": 2.0, "hauteur": 1.4, "allege": 0.9},
                  {"id": "F2", "type": "fenetre", "mur": "Ms", "position": 7.0, "largeur": 1.2, "hauteur": 1.4, "allege": 0.9},
                  {"id": "P1", "type": "porte", "mur": "Mc", "position": 3.0, "largeur": 0.8, "hauteur": 2.0}]
    pieces = [{"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]]},
              {"id": "chambre_1", "contour": [[6, 0], [9, 0], [9, 4], [6, 4]]},
              {"id": "placard_1", "contour": [[8.4, 3.4], [9, 3.4], [9, 4], [8.4, 4]]}]
    meubles = [{"id": "canape", "position": [3.0, 2.6], "face": 0.0, "dimensions": [2.0, 0.9, 0.8]}]
    return {"murs": murs, "ouvertures": ouvertures, "pieces": pieces, "meubles": meubles}


def test_plans_possibles_et_dans_l_ordre():
    log = _logement()
    plans = r.realiser(log)
    assert [p["piece"] for p in plans] == ["sejour_1", "chambre_1"]  # la visite ; pas le placard
    scene = r.Scene2D(log)
    for plan in plans:
        piece = next(p for p in log["pieces"] if p["id"] == plan["piece"])
        assert len(plan["points"]) == 3 and plan["images"] == round(r.DUREE_S * r.IPS)
        for x, y, z, cap, tangage in plan["points"]:
            assert r._dedans((x, y), piece["contour"])
            d_mur, d_meuble = scene.distance_aux_obstacles((x, y))
            assert d_mur >= r.MARGE_MUR_PETITE - 1e-6 and d_meuble >= r.MARGE_MEUBLE - 1e-6
            assert z == r.HAUTEUR_M and tangage == r.TANGAGE_DEG


def test_le_cadrage_montre_la_piece_et_la_lumiere():
    log = _logement()
    plan = r.realiser(log)[0]
    assert plan["pourquoi"]["fenetre"] > 0  # une fenêtre dans le champ
    assert plan["pourquoi"]["face_m"] > 2.2  # pas le nez contre un mur
    # la caméra regarde vers l'intérieur de la pièce : le centre du séjour est dans le champ au départ
    x, y, _, cap, _ = plan["points"][0]
    vers_centre = math.degrees(math.atan2(2.0 - y, 3.0 - x))
    assert abs((vers_centre - cap + 180) % 360 - 180) < r.CHAMP_DEG / 2


def test_dessin(tmp_path):
    log = _logement()
    r.dessiner(log, r.realiser(log), tmp_path / "plans.png")
    assert (tmp_path / "plans.png").stat().st_size > 1000


def test_apprendre_des_avis(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils" / "atelya"))
    import noter_film
    appris = tmp_path / "appris.json"
    assert r.savoir_faire(appris) == r.SAVOIR_DEFAUT  # rien appris : réglages de départ
    plans = [{"numero": 1, "piece": "sejour_1"}, {"numero": 2, "piece": "chambre_1"}]
    avis = noter_film.avis_depuis_arguments(plans, ["1:trop près,ennuyeux", "tous:bien"], "film-essai")
    assert [a["avis"] for a in avis] == [["trop_pres", "ennuyeux"], ["bien"], ["bien"]]
    s = r.apprendre(avis, appris)
    assert s["marge_mur"] == r.SAVOIR_DEFAUT["marge_mur"] + 0.1 and s["avancee_m"] > r.SAVOIR_DEFAUT["avancee_m"]
    assert r.savoir_faire(appris)["marge_mur"] == s["marge_mur"]  # gardé : sert aux films suivants
    for _ in range(30):  # beaucoup d'avis : les réglages restent dans des bornes raisonnables
        s = r.apprendre([{"avis": ["trop_pres"]}], appris)
    assert s["marge_mur"] == r.BORNES["marge_mur"][1]
    import pytest
    with pytest.raises(ValueError):
        r.apprendre([{"avis": ["n_importe_quoi"]}], appris)
    # le savoir-faire appris change vraiment les plans : plus loin des murs
    plans_appris = r.realiser(_logement(), s=r.savoir_faire(appris))
    scene = r.Scene2D(_logement())
    for plan in plans_appris:
        if plan["piece"] == "sejour_1":
            for x, y, *_ in plan["points"]:
                assert scene.distance_aux_obstacles((x, y))[0] >= r.BORNES["marge_mur"][1] - 1e-6


def test_portes_fermees_et_pieces_sans_fenetre():
    log = _logement()
    scene = r.Scene2D(log)
    # depuis le séjour, regarder vers la porte P1 (mur Mc, x = 6, y de 3 à 3,8) : la porte fermée arrête la vue
    rayons = scene.rayons((5.0, 3.4))
    est = int(np.argmin(np.abs(rayons["angles"] - 0.0)))
    assert rayons["distance"][est] < 1.2
    assert scene.a_une_fenetre(log["pieces"][0]) and scene.a_une_fenetre(log["pieces"][1])
    assert not scene.a_une_fenetre(log["pieces"][2])  # le placard : pas de fenêtre
    assert all("lumiere_du_jour" in p for p in r.realiser(log))


def test_piece_vide_sans_fenetre_pas_filmee():
    log = _logement()
    log["pieces"].append({"id": "salle_d_eau_1", "contour": [[0, 4.2], [2.5, 4.2], [2.5, 6.5], [0, 6.5]]})
    log["murs"] += [{"id": "Mx", "debut": [0, 6.6], "fin": [2.6, 6.6], "epaisseur": 0.2},
                    {"id": "My", "debut": [2.6, 4.0], "fin": [2.6, 6.6], "epaisseur": 0.2},
                    {"id": "Mz", "debut": [0, 4.0], "fin": [0, 6.6], "epaisseur": 0.2}]
    assert "salle_d_eau_1" not in [p["piece"] for p in r.realiser(log)]  # vide et sans fenêtre : rien à montrer
