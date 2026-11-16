"""Zéro collision : le contrôle et la réparation de ce qui est posé dans un logement (moteur/collisions.py, 16/11/2026)."""
import math

import numpy as np

from moteur import collisions as co
from moteur.logement import Logement


def logement(meubles: list[dict], rideaux: dict | None = None) -> dict:
    """Une pièce de 5 × 4 m (murs de 20 cm), une porte au sud, une fenêtre à l'ouest, une porte-fenêtre au nord."""
    mur = lambda i, a, b: {"id": i, "debut": a, "fin": b, "epaisseur": 0.2, "statut": "mesure", "source": "essai"}
    ouv = lambda i, t, m, p, l, h, a=0.0: {"id": i, "type": t, "mur": m, "position": p, "largeur": l, "hauteur": h, "allege": a,
                                           "statut": "mesure", "source": "essai"}
    lg = {"schema": "logement/0.1", "projet_id": "essai", "unites": "m", "hauteur_sous_plafond": 2.5,
          "murs": [mur("sud", [-0.1, -0.1], [5.1, -0.1]), mur("nord", [-0.1, 4.1], [5.1, 4.1]), mur("ouest", [-0.1, -0.1], [-0.1, 4.1]),
                   mur("est", [5.1, -0.1], [5.1, 4.1])],
          "ouvertures": [ouv("porte", "porte", "sud", 0.5, 0.9, 2.04), ouv("fenetre", "fenetre", "ouest", 1.5, 1.2, 1.3, 0.95),
                         ouv("baie", "porte_fenetre", "nord", 2.0, 1.4, 2.15)],
          "pieces": [{"id": "sejour", "nom": "Séjour", "contour": [[0, 0], [5, 0], [5, 4], [0, 4]], "statut": "mesure", "source": "essai"}],
          "meubles": meubles}
    if rideaux:
        for o in lg["ouvertures"]:
            if o["id"] in rideaux:
                o["rideaux"] = {**rideaux[o["id"]], "statut": "estime", "source": "lecture des photos (1 photo(s))"}
    return lg


def meuble(ident: str, categorie: str, position, face: float, dims, altitude: float = 0.0, source: str = "repérage photos (2 photo(s))",
           statut: str = "estime") -> dict:
    return {"id": ident, "categorie": categorie, "piece": "sejour", "position": list(position), "face": face, "dimensions": list(dims),
            "altitude": altitude, "statut": statut, "source": source, "confiance": 0.6}


def par_id(lg: dict) -> dict:
    return {m["id"]: m for m in lg["meubles"]}


def test_deux_rectangles_tournes_se_penetrent_ou_non():
    a = co.rect_du_meuble(meuble("a", "table", [0.0, 0.0], 0.0, [1.0, 1.0, 0.75]))
    b = co.rect_du_meuble(meuble("b", "table", [0.9, 0.0], 0.0, [1.0, 1.0, 0.75]))
    prof, direction = co.penetration(a, b)
    assert abs(prof - 0.1) < 1e-9 and np.allclose(direction, [-1, 0])  # pousser `a` de 10 cm vers la gauche les sépare
    assert co.penetration(a, co.rect_du_meuble(meuble("c", "table", [1.01, 0.0], 0.0, [1.0, 1.0, 0.75]))) is None
    # tourné de 45°, le même carré dépasse de ses coins : il touche un voisin posé à 1,15 m
    tourne = co.rect_du_meuble(meuble("d", "table", [1.15, 0.0], 45.0, [1.0, 1.0, 0.75]))
    assert co.penetration(a, tourne) is not None and co.penetration(a, co.rect_du_meuble(meuble("e", "table", [1.15, 0.0], 0.0, [1.0, 1.0, 0.75]))) is None


def test_le_controle_compte_ce_qui_se_touche_et_seulement_cela():
    dans_le_mur = meuble("canape", "canape", [2.5, 0.35], 90.0, [2.0, 0.9, 0.85])  # son dos à 10 cm DANS le mur sud
    assert [(c["type"], c["b"], c["profondeur_cm"]) for c in co.mesurer(logement([dans_le_mur]))] == [("mur", "sud", 10.0)]
    sains = [meuble("canape", "canape", [2.5, 0.48], 90.0, [2.0, 0.9, 0.85]),  # à 3 cm du mur
             meuble("tapis", "tapis", [2.5, 1.0], 0.0, [2.0, 1.4, 0.02]),  # à plat sous le canapé
             meuble("commode", "commode", [4.74, 2.0], 180.0, [0.9, 0.45, 0.85]),
             meuble("tableau", "tableau", [4.975, 2.0], 180.0, [0.8, 0.03, 0.6], 1.2),  # AU-DESSUS de la commode
             meuble("table", "table", [2.5, 2.6], 90.0, [1.4, 0.8, 0.75]),
             meuble("chaise", "chaise", [2.5, 2.05], 90.0, [0.5, 0.55, 0.85]),  # glissée sous la table (un quart de son assise)
             meuble("suspension", "suspension", [2.5, 2.6], 0.0, [0.5, 0.5, 0.6], 1.9),  # au-dessus de la table
             meuble("bas", "meuble_cuisine_bas", [0.33, 0.6], 0.0, [1.0, 0.6, 0.9], source="repérage par lecture des photos (2 photo(s))"),
             meuble("evier", "evier", [0.33, 0.6], 0.0, [0.8, 0.5, 0.02], 0.902, source="lecture des photos, équipement (1 photo(s))")]
    assert co.mesurer(logement(sains)) == []
    fautes = [meuble("armoire", "placard", [4.67, 2.0], 180.0, [1.5, 0.6, 2.2]),
              meuble("tableau", "tableau", [4.975, 2.0], 180.0, [0.8, 0.03, 0.6], 1.2),  # derrière l'armoire, à sa hauteur
              meuble("table", "table", [2.5, 2.6], 90.0, [1.4, 0.8, 0.75]),
              meuble("chaise", "chaise", [2.5, 2.4], 90.0, [0.5, 0.55, 0.85]),  # aux deux tiers DANS la table
              meuble("dehors", "plante", [7.0, 2.0], 0.0, [0.4, 0.4, 1.0])]
    vus = {(c["type"], c["a"], c["b"]) for c in co.mesurer(logement(fautes))}
    assert vus == {("objet", "armoire", "tableau"), ("objet", "table", "chaise"), ("dehors", "dehors", None)}
    assert co.resume(co.mesurer(logement(fautes)))["total"] == 3


def test_un_meuble_entre_dans_un_mur_en_ressort_et_deux_meubles_se_separent():
    lg = logement([meuble("canape", "canape", [2.5, 0.35], 90.0, [2.0, 0.9, 0.85]), meuble("commode", "commode", [3.4, 0.15], 90.0, [0.9, 0.45, 0.85])])
    assert len(co.mesurer(lg)) == 3  # le canapé dans le mur, la commode dans le mur, et l'un dans l'autre
    repare, actions = co.reparer(lg)
    assert co.mesurer(repare) == [] and len(repare["meubles"]) == 2
    canape, commode = par_id(repare)["canape"], par_id(repare)["commode"]
    assert canape["position"][1] - 0.45 >= co.JEU_MUR - 0.006  # à 2 cm du mur (la plinthe)
    assert all(math.dist(m["position"], o["position"]) < 0.6 for m, o in ((canape, lg["meubles"][0]), (commode, lg["meubles"][1])))
    assert lg["meubles"][0]["position"] == [2.5, 0.35]  # le logement reçu n'est pas modifié
    Logement.model_validate(repare)
    assert co.reparer(repare)[1] == []  # réparer deux fois ne change plus rien


def test_un_radiateur_ne_bouge_pas_c_est_le_meuble_qui_avance():
    radiateur = meuble("radiateur", "radiateur", [4.94, 2.0], 180.0, [0.9, 0.1, 0.6], 0.12, source="lecture des photos, équipement (1 photo(s))")
    canape = meuble("canape", "canape", [4.52, 2.0], 180.0, [2.0, 0.9, 0.85])  # dos à 3 cm du mur est : il traverse le radiateur
    repare, _ = co.reparer(logement([canape, radiateur]))
    assert co.mesurer(repare) == []
    assert par_id(repare)["radiateur"]["position"] == [4.94, 2.0]
    assert par_id(repare)["canape"]["position"][0] <= 4.52 - 0.07  # avancé d'au moins l'épaisseur du radiateur moins les 3 cm


def test_un_tableau_derriere_un_meuble_est_remonte_au_dessus():
    commode = meuble("commode", "commode", [4.745, 2.0], 180.0, [0.9, 0.45, 0.85])
    tableau = meuble("tableau", "tableau", [4.975, 2.0], 180.0, [0.8, 0.03, 0.6], 0.6, source="repérage par lecture des photos (1 photo(s))")
    repare, actions = co.reparer(logement([commode, tableau]))
    assert co.mesurer(repare) == []
    assert par_id(repare)["tableau"]["altitude"] >= 0.85 + 0.05 and par_id(repare)["commode"]["position"] == [4.745, 2.0]
    assert any(a["action"] == "remonté" for a in actions)


def test_une_television_sans_mur_libre_est_posee_sur_son_meuble_et_le_suit():
    # app-002 : le meuble télé et la télévision sont devant la porte-fenêtre ; aucune télévision ne s'accroche à une vitre
    stand = meuble("stand", "meuble_tv", [2.7, 3.8], -90.0, [1.4, 0.4, 0.5])  # dos à 0 cm du mur nord : il sera décollé
    tele = meuble("tele", "television", [2.7, 3.95], -90.0, [1.2, 0.08, 0.6], 0.9, source="repérage par lecture des photos (1 photo(s))")
    repare, actions = co.reparer(logement([stand, tele]))
    assert co.mesurer(repare) == []
    s, t = par_id(repare)["stand"], par_id(repare)["tele"]
    assert any(a["action"] == "posé sur son meuble" for a in actions)
    assert abs(t["altitude"] - 0.52) < 1e-6 and math.dist(t["position"], s["position"]) < 0.11  # sur le meuble, et déplacée avec lui


def test_un_miroir_trop_large_pour_son_pan_de_mur_est_retreci_ou_change_de_mur():
    miroir = meuble("miroir", "miroir", [4.975, 0.5], 180.0, [1.0, 0.04, 0.8], 1.0, source="repérage par lecture des photos (1 photo(s))")
    lg = logement([miroir])
    lg["ouvertures"] += [{"id": "p2", "type": "porte", "mur": "est", "position": 1.1, "largeur": 0.9, "hauteur": 2.04, "statut": "mesure", "source": "essai"}]
    repare, actions = co.reparer(lg)  # entre l'angle (y = 0) et la porte (y = 1,0 → 1,9) : 1,0 m de mur pour un miroir de 1,0 m + les marges
    m = par_id(repare)["miroir"]
    assert co.mesurer(repare) == [] and 0.75 <= m["dimensions"][0] < 1.0 and any(a["action"] == "rétréci" for a in actions)
    assert m["position"][1] + m["dimensions"][0] / 2 <= 1.0 - 0.02 + 1e-6  # il ne mord pas sur la porte


def test_ce_qu_une_personne_a_place_n_est_jamais_deplace():
    releve = meuble("releve", "canape", [2.5, 0.35], 90.0, [2.0, 0.9, 0.85], statut="mesure", source="écran de vérification")
    vu = meuble("vu", "table_basse", [2.5, 0.7], 0.0, [1.0, 0.6, 0.42])  # posé d'après une photo, DANS le canapé relevé
    repare, actions = co.reparer(logement([releve, vu]))
    assert par_id(repare)["releve"]["position"] == [2.5, 0.35]
    assert [(c["type"], c["a"]) for c in co.mesurer(repare)] == [("mur", "releve")]  # seule reste la faute de la personne, signalée
    assert any(a["action"] == "signalé" and a["id"] == "releve" for a in actions)
    assert co.heurts(par_id(repare)["vu"], repare["meubles"], co.murs_solides(repare), {}) == []


def test_les_rideaux_passent_devant_le_radiateur_et_le_meuble_recule():
    radiateur = meuble("radiateur", "radiateur", [0.06, 2.1], 0.0, [0.9, 0.1, 0.6], 0.12, source="lecture des photos, équipement (1 photo(s))")
    fauteuil = meuble("fauteuil", "fauteuil", [0.45, 2.1], 0.0, [0.8, 0.8, 0.85])  # collé au mur ouest, sous la fenêtre
    lg = logement([radiateur, fauteuil], rideaux={"fenetre": {"voilage": [244, 243, 238], "rideaux": [170, 140, 190]}})
    assert {c["type"] for c in co.mesurer(lg)} == {"objet", "rideau"}
    repare, actions = co.reparer(lg)
    assert co.mesurer(repare) == []
    r = next(o for o in repare["ouvertures"] if o["id"] == "fenetre")["rideaux"]
    assert r["ecart"] >= 0.11 + co.PLIS_VOILAGE and any(a["action"] == "rideau écarté" for a in actions)
    assert par_id(repare)["radiateur"]["position"] == [0.06, 2.1]
    assert par_id(repare)["fauteuil"]["position"][0] - 0.4 >= r["ecart"] + (co.ECART_RIDEAUX - co.ECART_VOILAGE) + co.PLIS_RIDEAUX - 0.006
    Logement.model_validate(repare)


def test_une_suspension_sort_du_mur_et_se_raccourcit_au_dessus_d_une_armoire():
    armoire = meuble("armoire", "placard", [4.67, 2.0], 180.0, [1.5, 0.6, 2.2])
    lampe = meuble("lampe", "suspension", [4.6, 2.0], 0.0, [0.5, 0.5, 0.6], 1.9, source="repérage photos (2 photo(s))")
    au_mur = meuble("au_mur", "suspension", [0.1, 3.0], 0.0, [0.6, 0.6, 0.6], 1.9, source="repérage photos (1 photo(s))")
    repare, actions = co.reparer(logement([armoire, lampe, au_mur]))
    assert co.mesurer(repare) == [] and len(repare["meubles"]) == 3
    lampe2 = par_id(repare)["lampe"]
    assert lampe2["altitude"] >= 2.2 + 0.09 or math.dist(lampe2["position"], [4.6, 2.0]) > 0.2  # raccourcie au-dessus, ou écartée
    assert par_id(repare)["au_mur"]["position"][0] >= 0.3 + co.JEU - 0.006


def test_un_meuble_et_ce_qu_il_porte_bougent_ensemble():
    bas = meuble("bas", "meuble_cuisine_bas", [1.0, 0.25], 90.0, [1.8, 0.6, 0.9], source="repérage par lecture des photos (2 photo(s))")  # 5 cm dans le mur
    evier = meuble("evier", "evier", [0.7, 0.25], 90.0, [0.8, 0.5, 0.02], 0.902, source="lecture des photos, équipement (1 photo(s))")
    repare, _ = co.reparer(logement([bas, evier]))
    b, e = par_id(repare)["bas"], par_id(repare)["evier"]
    assert co.mesurer(repare) == [] and b["position"][1] >= 0.32 - 0.006
    assert abs((e["position"][0] - b["position"][0]) + 0.3) < 1e-6 and abs(e["position"][1] - b["position"][1]) < 1e-6
    assert b["dimensions"] == [1.8, 0.6, 0.9]  # un meuble qui porte un évier n'est ni rétréci ni tourné


def test_sans_place_un_objet_est_retire_et_il_ne_reste_aucune_collision():
    # deux lits de 1,60 × 2,05 m dans une pièce de 5 × 4 m déjà pleine d'un îlot relevé à la main : ils ne tiennent nulle part
    ilot = meuble("ilot", "ilot", [2.5, 2.0], 0.0, [3.4, 4.4, 0.9], statut="mesure", source="relevé")  # 4,4 m d'est en ouest, 3,4 m du nord au sud
    lits = [meuble(f"lit_{k}", "lit", [2.5, 2.0], 0.0, [1.6, 2.05, 1.0]) for k in range(2)]
    repare, actions = co.reparer(logement([ilot, *lits]))
    assert co.mesurer(repare) == [] and [m["id"] for m in repare["meubles"]] == ["ilot"]
    assert sum(a["action"] == "retiré" for a in actions) == 2
