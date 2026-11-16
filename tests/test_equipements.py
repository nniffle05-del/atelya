"""Les équipements du logement posés d'après la lecture des photos (moteur/equipements.py, 16/11/2026)."""
import json
import math
from pathlib import Path

import numpy as np

from moteur import equipements as eq
from moteur.logement import Logement

RACINE = Path(__file__).resolve().parents[1]


def logement() -> dict:
    """Deux pièces de 4 × 3 m côte à côte, un mur entre elles (percé d'une porte), une fenêtre et une porte-fenêtre."""
    mur = lambda i, a, b, ep=0.2: {"id": i, "debut": a, "fin": b, "epaisseur": ep, "statut": "mesure", "source": "essai"}
    return {
        "schema": "logement/0.1", "projet_id": "essai", "unites": "m", "hauteur_sous_plafond": 2.5,
        "murs": [mur("sud", [-0.1, -0.1], [8.2, -0.1]), mur("nord", [-0.1, 3.1], [8.2, 3.1]), mur("ouest", [-0.1, -0.1], [-0.1, 3.1]),
                 mur("est", [8.2, -0.1], [8.2, 3.1]), mur("milieu", [4.05, -0.1], [4.05, 3.1], 0.1)],
        "ouvertures": [
            {"id": "porte", "type": "porte", "mur": "milieu", "position": 0.3, "largeur": 0.8, "hauteur": 2.04, "statut": "mesure", "source": "essai"},
            {"id": "fenetre", "type": "fenetre", "mur": "ouest", "position": 1.0, "largeur": 1.2, "hauteur": 1.3, "allege": 0.95,
             "statut": "mesure", "source": "essai"},
            {"id": "baie", "type": "porte_fenetre", "mur": "est", "position": 1.0, "largeur": 1.2, "hauteur": 2.15, "statut": "mesure",
             "source": "essai"}],
        "pieces": [{"id": "sejour", "nom": "Séjour", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]], "statut": "mesure", "source": "essai"},
                   {"id": "cuisine", "nom": "Cuisine", "contour": [[4.1, 0], [8.1, 0], [8.1, 3], [4.1, 3]], "statut": "mesure", "source": "essai"}],
        "meubles": [],
    }


def vue(sorte: str, point, piece: str, photo: int = 0, **k) -> dict:
    return {"lu": sorte, "sorte": sorte, "photo": photo, "dit": None, "poids": 1000.0, "note": 0.6, "couleur": None, "couleur_vue": None,
            "piece": piece, "point": list(point) if point is not None else None, "bas": 0.1, "haut": 0.7, "largeur": 0.9, **k}


def meuble(ident: str, categorie: str, position, face: float, dims, source: str = "repérage par lecture des photos (2 photo(s))") -> dict:
    return {"id": ident, "categorie": categorie, "piece": "cuisine", "position": list(position), "face": face, "dimensions": list(dims),
            "statut": "estime", "source": source, "confiance": 0.6}


def test_la_sorte_precise_vient_de_la_note_de_la_lecture():
    assert eq.preciser("electromenager", "four encastré") == "four"
    assert eq.preciser("electromenager", "réfrigérateur inox") == "refrigerateur"
    assert eq.preciser("electromenager", "micro-ondes encastré") == "micro_ondes"
    assert eq.preciser("electromenager", "plaque de cuisson") == "plaque"
    assert eq.preciser("electromenager", None) is None  # un appareil sans nom : compris, pas dessiné
    assert eq.preciser("radiateur", "sèche-serviettes") == "seche_serviettes"
    assert eq.preciser("plafonnier", "rampe de spots") == "rampe"
    assert eq.preciser("etagere_murale", "niche à étagères") == "niche"
    assert eq.preciser("rideaux", "voilages blancs") == "voilage"
    assert eq.preciser("lave_linge", None) == "electromenager"
    assert eq.preciser("store", None) is None
    assert eq.couleur_dite("blanc cassé, étroite") == eq.COULEURS["blanc cassé"]
    assert eq.couleur_dite("réfrigérateur inox") == eq.COULEURS["inox"]
    assert eq.couleur_dite("grande") is None


def test_les_faces_d_une_piece_viennent_de_ses_murs():
    lg = logement()
    faces = eq.faces_de_la_piece(lg["pieces"][0], lg)
    assert sorted(f["mur"] for f in faces) == ["milieu", "nord", "ouest", "sud"]
    nord = next(f for f in faces if f["mur"] == "nord")
    assert abs(nord["longueur"] - 4.0) < 0.11 and np.allclose(nord["n"], [0, -1])  # le morceau du mur nord qui borde le séjour
    proches = eq.faces_proches([0.3, 1.5], lg["pieces"][0], lg)
    assert proches[0]["mur"] == "ouest"


def test_un_radiateur_passe_sous_la_fenetre_une_cheminee_non():
    lg = logement()
    ouest = next(f for f in eq.faces_proches([0.1, 1.6], lg["pieces"][0], lg) if f["mur"] == "ouest")
    # la fenêtre va de 1,0 à 2,2 m le long du mur ouest (appui à 0,95 m) ; le point est en face d'elle
    s = eq.place_libre(ouest, ouest["s"], (0.9, 0.1, 0.6), 0.12, lg)
    assert s is not None and abs(s - ouest["s"]) < 1e-6  # le radiateur reste sous la fenêtre
    s = eq.place_libre(ouest, ouest["s"], (0.5, 0.25, 1.2), 0.9, lg)
    assert s is None or abs(s - ouest["s"]) > 0.4  # des étagères qui montent devant la vitre glissent à côté (ou renoncent)


def test_la_cheminee_est_posee_d_abord_et_le_meuble_qui_la_traverse_s_ecarte():
    lg = logement()
    chaise = {**meuble("chaise_1", "chaise", [2.0, 2.7], -90.0, [0.5, 0.55, 0.85]), "piece": "sejour"}
    vues = [vue("cheminee", [2.0 + 0.05 * k, 2.6], "sejour", photo=k, bas=0.0, haut=1.1, largeur=1.3) for k in range(3)]
    r = eq.poser(vues, lg, [chaise])
    (cheminee,) = r["meubles"]
    assert cheminee["categorie"] == "cheminee" and cheminee["altitude"] == 0.0 and "3 photo(s)" in cheminee["source"]
    assert abs(cheminee["position"][1] - (3.0 - 0.35 / 2 - 0.01)) < 0.02 and abs(cheminee["face"] + 90.0) < 1e-6  # adossée au mur nord
    (apres,) = r["meubles_ranges"]
    assert math.dist(apres["position"], chaise["position"]) > 0.2  # la chaise a cédé la place
    Logement.model_validate(eq.appliquer({**lg, "meubles": r["meubles_ranges"]}, r))


def test_sans_cheminee_les_meubles_ne_bougent_pas_et_le_volume_se_glisse_a_cote():
    lg = logement()
    bas = meuble("bas_1", "meuble_cuisine_bas", [6.0, 2.69], -90.0, [1.8, 0.6, 0.9])
    r = eq.poser([vue("refrigerateur", [6.2, 2.6], "cuisine", dit="réfrigérateur inox", couleur=eq.COULEURS["inox"])], lg, [bas])
    assert r["meubles_ranges"] == [bas]
    (frigo,) = r["meubles"]
    assert frigo["categorie"] == "refrigerateur" and frigo["couleur"] == list(eq.COULEURS["inox"])
    assert abs(frigo["position"][0] - 6.0) >= 0.9 + 0.3 - 0.05  # à côté du meuble bas, pas dedans


def test_les_encastres_se_logent_dans_les_meubles_de_cuisine():
    lg = logement()
    bas = meuble("bas_1", "meuble_cuisine_bas", [6.0, 2.69], -90.0, [2.4, 0.6, 0.9])
    colonne = meuble("col_1", "colonne_cuisine", [7.6, 2.69], -90.0, [0.6, 0.6, 2.2])
    vues = [vue("evier", [5.9, 2.6], "cuisine"), vue("plaque", [6.1, 2.7], "cuisine"), vue("four", [7.5, 2.3], "cuisine", bas=0.8, haut=1.4),
            vue("micro_ondes", [7.5, 2.3], "cuisine", bas=0.9, haut=1.3), vue("hotte", [6.6, 2.9], "cuisine", bas=1.6, haut=2.4, largeur=0.7)]
    r = eq.poser(vues, lg, [bas, colonne])
    par = {m["id"]: m for m in r["meubles"]}
    evier, plaque = par["evier_lu_1"], par["plaque_lu_1"]
    assert evier["altitude"] > 0.9 and plaque["altitude"] > 0.9 and evier["face"] == -90.0
    assert abs(evier["position"][0] - plaque["position"][0]) >= (0.8 + 0.6) / 2 + 0.1 - 1e-6  # ils ne se recouvrent pas
    assert all(4.8 <= m["position"][0] <= 7.2 and abs(m["position"][1] - 2.69) < 1e-6 for m in (evier, plaque))  # sur le plan du meuble
    fours = sorted((m for m in r["meubles"] if m["categorie"] == "four"), key=lambda m: m["altitude"])
    assert len(fours) == 2 and fours[1]["altitude"] >= fours[0]["altitude"] + fours[0]["dimensions"][2]  # le micro-ondes au-dessus du four
    assert all(abs(m["position"][0] - 7.6) < 1e-6 and m["position"][1] < 2.69 - 0.3 for m in fours)  # à fleur de la façade
    hotte = par["hotte_lu_1"]
    assert abs(hotte["position"][0] - plaque["position"][0]) < 0.31  # la plaque est à l'aplomb de la hotte
    assert r["colonnes"] == ["col_1"]
    lg2 = eq.appliquer({**lg, "meubles": r["meubles_ranges"]}, r)
    assert "sans four" in next(m for m in lg2["meubles"] if m["id"] == "col_1")["description"]
    Logement.model_validate(lg2)


def test_sans_meuble_pour_le_porter_un_evier_n_est_pas_pose():
    r = eq.poser([vue("evier", [6.0, 2.6], "cuisine")], logement(), [])
    assert r["meubles"] == [] and "aucun meuble" in r["non_poses"][0]["raison"]


def test_deux_vues_ne_se_fondent_jamais_a_travers_un_mur():
    vues = [vue("radiateur", [3.9, 1.5], "sejour", photo=0), vue("radiateur", [4.2, 1.5], "cuisine", photo=1),
            vue("radiateur", [3.85, 1.7], "sejour", photo=2)]
    fusion = eq.fusionner(vues)
    assert sorted((f["piece"], f["vues"]) for f in fusion) == [("cuisine", 1), ("sejour", 2)]
    r = eq.poser(vues, logement(), [])
    assert sorted(m["piece"] for m in r["meubles"]) == ["cuisine", "sejour"]
    for m in r["meubles"]:  # ni l'un ni l'autre devant la porte du mur du milieu (de 0,3 à 1,1 m)
        assert m["position"][1] - m["dimensions"][0] / 2 >= 1.0 + 0.05 - 1e-6


def test_les_rideaux_habillent_la_fenetre_la_plus_proche():
    lg = logement()
    vues = [vue("voilage", [0.2, 1.6], "sejour", photo=0, dit="voilages blancs"), vue("rideaux", [7.9, 1.5], "cuisine", photo=1, couleur=(170, 140, 190)),
            vue("rideaux", [2.0, 1.5], "sejour", photo=2)]
    r = eq.poser(vues, lg, [])
    assert r["rideaux"]["fenetre"]["voilage"] == list(eq.VOILAGE) and r["rideaux"]["fenetre"]["rideaux"] is None
    assert r["rideaux"]["baie"]["rideaux"] == [170, 140, 190]
    assert any("aucune fenêtre" in n["raison"] for n in r["non_poses"])  # le troisième, au milieu de la pièce
    lg2 = eq.appliquer(lg, r)
    assert next(o for o in lg2["ouvertures"] if o["id"] == "fenetre")["rideaux"]["statut"] == "estime"
    Logement.model_validate(lg2)


def test_un_passe_plat_perce_le_mur_entre_deux_pieces_jamais_vers_dehors():
    lg = logement()
    dedans = vue("passe_plat", None, "sejour", trou={"mur": "milieu", "s0": 1.9, "s1": 2.9, "bas": 1.05, "haut": 2.0})
    r = eq.poser([dedans], lg, [])
    (trou,) = r["passe_plats"]
    assert trou["mur"] == "milieu" and abs(trou["position"] - 1.9) < 0.01 and trou["allege"] == 1.05 and abs(trou["hauteur"] - 0.95) < 0.01
    lg2 = eq.appliquer(lg, r)
    Logement.model_validate(lg2)
    dehors = vue("passe_plat", None, "sejour", trou={"mur": "nord", "s0": 1.0, "s1": 2.0, "bas": 1.0, "haut": 2.0})
    r = eq.poser([dehors], lg, [])
    assert r["passe_plats"] == [] and any(n["sorte"] == "passe_plat" for n in r["non_poses"])
    # sur la porte : il glisse à côté, sans la toucher
    sur_la_porte = vue("passe_plat", None, "sejour", trou={"mur": "milieu", "s0": 0.6, "s1": 1.4, "bas": 1.0, "haut": 2.0})
    (trou,) = eq.poser([sur_la_porte], lg, [])["passe_plats"]
    assert trou["position"] >= 0.3 + 0.8 + 0.1 - 1e-6


def test_le_vide_du_plan_ou_les_photos_montrent_un_passe_plat_est_referme_en_muret():
    lg = logement()
    # le mur du milieu est coupé en deux : un vide de 1 m entre y = 1,5 et y = 2,5 (le plan a dessiné le passe-plat en passage)
    lg["murs"] = [m for m in lg["murs"] if m["id"] != "milieu"] + [
        {"id": "milieu_a", "debut": [4.05, -0.1], "fin": [4.05, 1.5], "epaisseur": 0.1, "statut": "mesure", "source": "essai"},
        {"id": "milieu_b", "debut": [4.05, 2.5], "fin": [4.05, 3.1], "epaisseur": 0.1, "statut": "mesure", "source": "essai"}]
    lg["ouvertures"][0]["mur"] = "milieu_a"
    vides = eq.vides_du_plan(lg)
    assert len(vides) == 1 and abs(float(np.linalg.norm(vides[0]["b"] - vides[0]["a"])) - 1.0) < 0.11
    cam = [1.0, 2.0, 1.4, 0.0, 0.0, 800.0, 600.0, 400.0]  # dans le séjour, regarde vers l'est, à 3 m du vide
    trou = eq.trou_d_une_photo([560, 250, 640, 480], cam, lg, vides, profondeur=3.1)
    assert trou is not None and trou.get("vide") == 0 and 0.9 < trou["bas"] < 1.2 and 1.8 < trou["haut"] < 2.1
    r = eq.poser([vue("passe_plat", None, "sejour", trou=trou), vue("passe_plat", None, "cuisine", photo=1, trou={**trou, "bas": 1.0})], lg, [], vides=vides)
    (muret,), (pp,) = r["murs"], r["passe_plats"]
    assert muret["debut"] == [4.05, 1.5] and muret["fin"] == [4.05, 2.5] and muret["epaisseur"] == 0.1
    assert pp["mur"] == muret["id"] and pp["position"] == 0.0 and abs(pp["largeur"] - 1.0) < 0.01
    lg2 = eq.appliquer(lg, r)
    Logement.model_validate(lg2)
    from moteur.habillage import plan_habille

    briques = plan_habille(Logement.model_validate(lg2))["briques"]
    du_muret = {b["id"]: b for b in briques if b["element"] == muret["id"]}
    assert f"{muret['id']}__allege_{pp['id']}" in du_muret and f"{muret['id']}__linteau_{pp['id']}" in du_muret
    assert not any("__plein_" in i for i in du_muret)  # percé sur toute sa longueur : un muret et un linteau, rien d'autre
    assert any(b["id"] == f"{pp['id']}__tablette" for b in briques)


def test_la_vue_la_plus_isolee_d_un_passe_plat_est_ecartee():
    lg = logement()
    bon = {"mur": "milieu", "s0": 1.9, "s1": 2.9, "bas": 1.05, "haut": 2.0}
    vues = [vue("passe_plat", None, "sejour", photo=k, trou=bon) for k in range(3)] + [
        vue("passe_plat", None, "sejour", photo=3, trou={"mur": "sud", "s0": 5.0, "s1": 6.0, "bas": 1.0, "haut": 2.0})]
    assert [t["mur"] for t in eq.poser(vues, lg, [])["passe_plats"]] == ["milieu"]


def test_une_vasque_lue_sur_un_meuble_est_portee_par_lui_sinon_c_est_un_lavabo():
    lg = logement()
    commode = {**meuble("meuble_vasque", "rangement", [6.0, 2.76], -90.0, [1.2, 0.45, 0.85])}
    r = eq.poser([vue("lavabo", [5.8, 2.7], "cuisine"), vue("lavabo", [6.3, 2.7], "cuisine")], lg, [commode])
    assert len(r["meubles"]) == 2 and all(m["categorie"] == "lavabo" and m["altitude"] > 0.8 and m["dimensions"][2] < 0.2 for m in r["meubles"])
    r = eq.poser([vue("lavabo", [5.8, 2.7], "cuisine")], lg, [])
    (lavabo,) = r["meubles"]
    assert lavabo["altitude"] == 0.0 and lavabo["dimensions"][2] > 0.8  # sur son propre meuble, adossé au mur


def test_les_equipements_sont_des_categories_que_le_format_et_l_ecran_connaissent():
    from moteur.meubles import CATEGORIES, EQUIPEMENTS, SUR_MESURE

    assert set(EQUIPEMENTS) <= SUR_MESURE
    for sorte in (*eq.AU_MUR, *eq.AU_SOL, *eq.ENCASTRES, *eq.AU_PLAFOND):
        assert eq.CATEGORIE.get(sorte, sorte) in CATEGORIES, sorte
    dessins = (RACINE / "moteur" / "blender" / "equipements.py").read_text(encoding="utf-8")
    for categorie in EQUIPEMENTS:  # chaque équipement a son dessin
        assert f'"{categorie}": {categorie}' in dessins, categorie
    from moteur import lecture_photos as lp

    assert {"refrigerateur", "four", "micro_ondes", "plaque", "passe_plat", "electromenager"} <= set(lp.SORTES)
    assert len(lp.SORTES) == len(set(lp.SORTES))
    fiche = lp.fiche_depuis_notes("1 refrigerateur inox ; 2 passe_plat ; 3 electromenager four encastré")
    assert lp.controler(fiche, {1, 2, 3}) == []
    json.dumps(fiche)


def test_seuls_les_meubles_au_sol_qui_touchent_la_cheminee_bougent():
    lg = logement()
    tele = {**meuble("tele", "television", [2.3, 2.95], -90.0, [1.1, 0.08, 0.65]), "piece": "sejour", "altitude": 0.9}
    loin = {**meuble("canape_1", "canape", [1.0, 0.5], 90.0, [2.0, 0.9, 0.85]), "piece": "sejour"}
    devant = {**meuble("chaise_2", "chaise", [2.0, 2.3], -90.0, [0.5, 0.55, 0.85]), "piece": "sejour"}  # sur le foyer, pas dans la cheminée
    vues = [vue("cheminee", [2.0, 2.6], "sejour", bas=0.0, haut=1.1, largeur=1.3)]
    apres = {m["id"]: m for m in eq.poser(vues, lg, [tele, loin, devant])["meubles_ranges"]}
    assert apres["tele"] == tele and apres["canape_1"] == loin  # ni l'objet accroché au mur ni le meuble éloigné ne bougent
    assert "chaise_2" not in apres or math.dist(apres["chaise_2"]["position"], devant["position"]) > 0.1  # rien ne reste sur le foyer


def test_le_meuble_mesure_dans_la_cheminee_glisse_le_long_du_regard_de_l_appareil():
    lg = logement()
    # l'appareil est à l'est, il regarde vers l'ouest : la chaise, mesurée dans la cheminée, était en vrai plus loin sur ce regard
    chaise = {**meuble("chaise_1", "chaise", [2.0, 2.7], -90.0, [0.5, 0.55, 0.85]), "piece": "sejour", "_appareils": [[3.8, 2.7, 1.4]]}
    vues = [vue("cheminee", [2.0, 2.6], "sejour", bas=0.0, haut=1.1, largeur=1.3)]
    (apres,) = eq.poser(vues, lg, [chaise])["meubles_ranges"]
    assert abs(apres["position"][1] - 2.7) < 1e-6 and abs(apres["position"][0] - 2.0) >= 0.65  # sur le même regard, hors de la cheminée
    sans = {k: v for k, v in chaise.items() if k != "_appareils"}
    (apres,) = eq.poser(vues, lg, [sans])["meubles_ranges"]
    assert math.dist(apres["position"], sans["position"]) > 0.2  # sans appareil connu : écartée au plus court
