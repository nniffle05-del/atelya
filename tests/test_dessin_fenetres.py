"""Le DESSIN de chaque fenêtre construit dans la maquette d'après les photos (F2 pièce 3, 20/11/2026) : moteur/dessin_fenetres.py
(de la lecture des photos aux parts de la baie), moteur/habillage.py (les briques), moteur/vitrages.py (le garde-corps retiré de
la vue lointaine)."""
import json

import numpy as np
import pytest

from moteur import dessin_fenetres as df
from moteur import vitrages as vt
from moteur.habillage import menuiseries
from moteur.logement import Logement

TAILLE = (1000, 700)


def deux_battants(**plus) -> list[dict]:
    """Une fenêtre vue de face : tour de 400 × 500 pixels, deux battants de 150 pixels de vitre, 20 pixels de bord, 60 de
    battement, une traverse par battant, garde-corps au tiers bas."""
    gauche = {"baie": "F1", "coins": [[320, 120], [470, 120], [470, 560], [320, 560]], "traverses": [[300, 310, 300, 310]],
              "cadre": [[300, 100], [700, 100], [700, 600], [300, 600]], "garde_corps": [420, 420], "genre_garde_corps": "fer_forge", **plus}
    droite = {"baie": "F1", "coins": [[530, 120], [680, 120], [680, 560], [530, 560]], "traverses": [[300, 310, 300, 310]],
              "garde_corps": [420, 420]}
    return [gauche, droite]


def logement(type_="fenetre", allege=0.9, hauteur=1.25, **dessin) -> dict:
    """Une pièce de 4 × 3 m, une fenêtre de 1 m au milieu du mur du bas (la pièce est à GAUCHE de ce mur, qui va vers +x)."""
    murs = [{"id": f"M{i}", "statut": "mesure", "source": "essai", "debut": a, "fin": b, "epaisseur": 0.2}
            for i, (a, b) in enumerate([((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))], start=1)]
    o = {"id": "F1", "statut": "mesure", "source": "essai", "type": type_, "mur": "M1", "position": 1.5, "largeur": 1.0,
         "hauteur": hauteur, "allege": allege}
    if dessin:
        o["dessin"] = dessin
    return {"schema": "logement/0.1", "projet_id": "essai", "hauteur_sous_plafond": 2.5, "murs": murs, "ouvertures": [o],
            "pieces": [{"id": "P1", "statut": "mesure", "source": "essai", "nom": "Séjour",
                        "contour": [(0.1, 0.1), (3.9, 0.1), (3.9, 2.9), (0.1, 2.9)]}]}


def test_une_photo_de_face_donne_les_parts_de_la_baie():
    d = df.d_une_photo(deux_battants(), largeur=1.0, hauteur=1.25, jusqu_au_sol=False)
    assert d["cadre_lu"] and len(d["vantaux"]) == 2
    assert d["vantaux"][0]["vitrage"] == pytest.approx((0.05, 0.425), abs=1e-3)  # 20 px de bord sur 400, puis 150 px de vitre
    assert d["vantaux"][1]["vitrage"] == pytest.approx((0.575, 0.95), abs=1e-3)
    assert d["vitrage_bas"] == pytest.approx(0.08, abs=1e-3) and d["vitrage_haut"] == pytest.approx(0.96, abs=1e-3)  # de bas en haut
    assert d["vantaux"][0]["traverses"] == [pytest.approx((0.58, 0.60), abs=1e-3)]
    assert d["garde_corps"] == pytest.approx(0.36, abs=1e-3) and d["genre_garde_corps"] == "fer_forge"
    assert d["soubassement"] == 0.0


def test_la_perspective_est_redressee():
    """La même fenêtre vue de biais (le côté droit deux fois plus loin) : les parts restent celles de la fenêtre."""
    import cv2

    de_biais = cv2.getPerspectiveTransform(np.array([[300, 100], [700, 100], [700, 600], [300, 600]], np.float32),
                                           np.array([[300, 100], [560, 220], [560, 480], [300, 600]], np.float32))

    def p(x, y):
        return [float(v) for v in cv2.perspectiveTransform(np.array([[[x, y]]], np.float32), de_biais)[0, 0]]

    vues = []
    for f in deux_battants():
        g = {**f, "coins": [p(*c) for c in f["coins"]]}
        (hg, hd, bd, bg) = f["coins"]
        g["traverses"] = [[p(hg[0], 300)[1], p(hg[0], 310)[1], p(hd[0], 300)[1], p(hd[0], 310)[1]]]
        g["garde_corps"] = [p(hg[0], 420)[1], p(hd[0], 420)[1]]
        if f.get("cadre"):
            g["cadre"] = [p(*c) for c in f["cadre"]]
        vues.append(g)
    d = df.d_une_photo(vues, 1.0, 1.25, False)
    assert d["vantaux"][0]["vitrage"] == pytest.approx((0.05, 0.425), abs=4e-3)
    assert d["vantaux"][1]["vitrage"] == pytest.approx((0.575, 0.95), abs=4e-3)
    assert d["vantaux"][1]["traverses"][0] == pytest.approx((0.58, 0.60), abs=4e-3)
    assert d["garde_corps"] == pytest.approx(0.36, abs=4e-3)


def test_la_partie_pleine_sous_la_menuiserie_est_gardee_si_le_plan_descend_au_sol():
    vus = deux_battants(sol=[[350, 700], [650, 700]])  # le sol est 100 pixels sous la menuiserie, haute de 500
    d = df.d_une_photo(vus, 1.0, 2.2, jusqu_au_sol=True)
    assert d["soubassement"] == pytest.approx(100 / 600, abs=1e-3) and d["sol_lu"]
    assert d["vitrage_bas"] == pytest.approx((100 + 40) / 600, abs=1e-3)  # la partie pleine puis la traverse du bas
    assert d["garde_corps"] == pytest.approx((100 + 180) / 600, abs=1e-3)
    # une fenêtre sur allège : le sol lu ne change rien (la baie du plan s'arrête à la menuiserie)
    assert df.d_une_photo(vus, 1.0, 1.25, jusqu_au_sol=False)["soubassement"] == 0.0


def test_sans_le_tour_de_la_menuiserie_les_bords_sont_supposes():
    vus = [{k: v for k, v in f.items() if k != "cadre"} for f in deux_battants()]
    d = df.d_une_photo(vus, largeur=1.0, hauteur=1.25, jusqu_au_sol=False)
    assert not d["cadre_lu"]
    assert d["vantaux"][0]["vitrage"][0] == pytest.approx(df.BORD_SUPPOSE_M / 1.0, abs=1e-3)
    assert d["vitrage_bas"] == pytest.approx(df.BAS_SUPPOSE_M / 1.25, abs=1e-3)


def test_plusieurs_photos_sont_accordees():
    a = df.d_une_photo(deux_battants(), 1.0, 2.2, True)  # ne voit pas le sol
    b = df.d_une_photo(deux_battants(sol=[350, 700]), 1.0, 2.2, True)  # le voit : partie pleine d'un sixième
    coupee = df.d_une_photo([{k: v for k, v in deux_battants()[0].items() if k != "cadre"}], 1.0, 2.2, True)  # un seul battant, sans tour
    d, photos = df.accorder([("photo-01", a), ("photo-02", b), ("photo-03", coupee)])
    assert photos == ["photo-01", "photo-02"] and len(d["vantaux"]) == 2  # la photo sans le tour ne compte pas
    assert d["soubassement"] == pytest.approx(1 / 6, abs=1e-3)
    # la photo qui n'a pas vu le sol est ramenée dans la même baie : les deux disent le même garde-corps
    assert d["garde_corps"] == pytest.approx((100 + 180) / 600, abs=1e-3)
    assert d["vitrage_bas"] == pytest.approx(140 / 600, abs=1e-3)
    # deux dessins différents à égalité : la photo la plus de face (la fenêtre la plus grande sur la photo) l'emporte
    petite = {**df.d_une_photo([{**f, "traverses": []} for f in deux_battants()], 1.0, 2.2, True), "face": 10.0}
    assert len(df.accorder([("photo-01", a), ("photo-02", petite)])[0]["vantaux"][0]["traverses"]) == 1


def test_le_dessin_est_ecrit_dans_le_sens_du_mur():
    """La pièce est à gauche du mur M1 : vue de la pièce, la GAUCHE de la fenêtre est du côté de la FIN du mur."""
    log = logement(type_="porte_fenetre", allege=0.0, hauteur=2.2)
    vus = deux_battants(sol=[350, 700])
    vus[0]["montants"] = [[380, 386, 380, 386]]  # un petit bois debout dans le battant de GAUCHE de la photo
    lecture = {"format": vt.FORMAT, "photos": {"photo-01": vus, "photo-02": [{"baie": "F1", "vue": "non"}]}}
    assert vt.controler(lecture, {"photo-01": TAILLE}, {"F1"}) == []
    assert not df.gauche_est_le_debut(log["ouvertures"][0], log)
    pose, poses = df.appliquer(log, lecture)
    d = pose["ouvertures"][0]["dessin"]
    assert [len(v["montants"]) for v in d["vantaux"]] == [0, 1]  # le battant de gauche de la photo est le SECOND le long du mur
    assert d["vantaux"][1]["montants"][0] == pytest.approx((1 - 0.215, 1 - 0.2), abs=2e-3)
    assert d["statut"] == "estime" and "photo-01" in d["source"] and d["garde_corps"]["genre"] == "fer_forge"
    assert poses[0]["baie"] == "F1" and poses[0]["partie_pleine_m"] == pytest.approx(2.2 / 6, abs=0.01)
    assert poses[0]["garde_corps_m"] == pytest.approx(2.2 * 280 / 600, abs=0.01)
    Logement.model_validate(pose)
    assert "dessin" not in log["ouvertures"][0]  # le logement donné n'est pas modifié
    # une fenêtre dont le dessin a été choisi par une personne n'est pas touchée
    pose["ouvertures"][0]["dessin"]["statut"] = "mesure"
    encore, poses = df.appliquer(pose, {"format": vt.FORMAT, "photos": {"photo-01": deux_battants()}})
    assert poses == [] and encore["ouvertures"][0]["dessin"] == pose["ouvertures"][0]["dessin"]


def test_un_dessin_douteux_laisse_le_cadre_d_avant():
    etroit = [{"baie": "F1", "coins": [[320, 120], [340, 120], [340, 560], [320, 560]],
               "cadre": [[300, 100], [700, 100], [700, 600], [300, 600]]}]  # une « vitre » de 5 cm : lecture douteuse
    lecture = {"format": vt.FORMAT, "photos": {"photo-01": etroit}}
    assert df.lire(logement(), lecture) == {}
    assert df.lire(logement(), None) == {} and df.lire(logement(), {"photos": {"photo-01": [{"baie": "F1", "vue": "non"}]}}) == {}


def briques_de(log: dict) -> dict:
    return {b.id.split("__", 1)[1]: b for b in menuiseries(Logement.model_validate(log))}


def etendue(brique, axe=0) -> tuple[float, float]:
    v = [p[axe] for p in brique.contour]
    return (round(min(v), 3), round(max(v), 3))


def test_sans_dessin_la_fenetre_garde_son_cadre():
    b = briques_de(logement())
    assert {"montant_1", "montant_2", "traverse_haut", "traverse_bas", "montant_milieu", "vitre_1", "vitre_2", "appui", "appui_nez"} == set(b)


def test_la_maquette_construit_la_fenetre_dessinee():
    dessin = {"vantaux": [{"debut": 0.08, "fin": 0.44, "traverses": [[0.5, 0.52]]}, {"debut": 0.56, "fin": 0.92, "traverses": [[0.5, 0.52]],
                                                                                   "montants": [[0.73, 0.75]]}],
              "vitrage_bas": 0.2, "vitrage_haut": 0.95, "soubassement": 0.15, "statut": "estime", "source": "photos",
              "garde_corps": {"bas": 0.15, "haut": 0.45, "genre": "fer_forge"}}
    b = briques_de(logement(type_="porte_fenetre", allege=0.0, hauteur=2.0, **dessin))
    # la partie pleine : un morceau de mur de 30 cm, de toute l'épaisseur du mur ; la menuiserie est posée dessus
    assert b["soubassement"].materiau == "mur_blanc" and (b["soubassement"].z_bas, b["soubassement"].z_haut) == (0.0, pytest.approx(0.30))
    assert etendue(b["soubassement"], 1) == (-0.1, 0.1) and b["montant_1"].z_bas == pytest.approx(0.30)
    assert "appui" in b and b["appui"].z_bas == pytest.approx(0.30)  # une allège basse a son appui
    # le cadre à sa vraie largeur : 8 cm de chaque côté, 12 cm de battement
    assert etendue(b["montant_1"]) == (1.5, 1.58) and etendue(b["montant_2"]) == (2.42, 2.5) and etendue(b["montant_milieu"]) == (1.94, 2.06)
    assert etendue(b["vitre_1"]) == (1.58, 1.94) and (b["vitre_1"].z_bas, b["vitre_1"].z_haut) == (pytest.approx(0.4), pytest.approx(1.9))
    assert b["vitre_1"].materiau == "verre" and b["traverse_bas"].z_haut == pytest.approx(0.4)
    # les petits bois : une traverse par vantail (sur sa largeur), un montant dans le second
    assert etendue(b["petit_bois_1_t1"]) == (1.58, 1.94) and b["petit_bois_1_t1"].z_bas == pytest.approx(1.0)
    assert etendue(b["petit_bois_2_m1"]) == (2.23, 2.25) and "petit_bois_1_m1" not in b
    # le garde-corps : DEHORS (la pièce est du côté des y positifs), de la partie pleine à 90 cm, barreaux à 11 cm au plus
    main = b["garde_corps_main_courante"]
    assert main.materiau == "fer_forge" and main.z_haut == pytest.approx(0.9) and etendue(main, 1)[1] < 0 and etendue(main, 1)[0] >= -0.1
    barreaux = sorted(etendue(x)[0] for k, x in b.items() if k.startswith("garde_corps_barreau"))
    assert len(barreaux) == 9 and max(q - p for p, q in zip(barreaux, barreaux[1:])) <= 0.11 + 1e-6
    assert "garde_corps_frise" in b and "garde_corps_lisse_basse" in b
    assert all(x.z_bas >= 0.30 for k, x in b.items() if k.startswith("garde_corps"))


def test_le_format_refuse_un_dessin_incoherent():
    bon = {"vantaux": [{"debut": 0.1, "fin": 0.9}], "vitrage_bas": 0.1, "vitrage_haut": 0.9, "statut": "estime", "source": "photos"}
    Logement.model_validate(logement(**bon))
    for faute in ({"vitrage_bas": 0.95}, {"soubassement": 0.5}, {"vantaux": [{"debut": 0.6, "fin": 0.4}]},
                  {"vantaux": [{"debut": 0.1, "fin": 0.6}, {"debut": 0.5, "fin": 0.9}]}):
        with pytest.raises(ValueError):
            Logement.model_validate(logement(**{**bon, **faute}))
    assert json.loads(Logement.model_validate(logement(**bon)).model_dump_json())["ouvertures"][0]["dessin"]["vitrage_haut"] == 0.9


def test_la_ferronnerie_du_garde_corps_est_effacee_de_la_photo():
    """Sous le dessus du garde-corps, les fers minces (sombres) sont retirés ; ce qui est large derrière eux reste ; rien
    n'est touché ailleurs."""
    f = {"baie": "F1", "coins": [[400, 200], [600, 200], [600, 500], [400, 500]], "garde_corps": [400, 400]}
    photo = np.full((700, 1000, 3), 230, np.uint8)
    photo[380:500, 450:453] = 40  # un barreau de 3 pixels, qui dépasse au-dessus du garde-corps
    photo[430:480, 500:560] = 90  # une fenêtre de l'immeuble d'en face (large)
    photo[250:260, 420:423] = 40  # un trait mince dans le HAUT de la vitre : pas le garde-corps
    zone = vt.zone_du_garde_corps(f, TAILLE)
    assert zone[450, 500] == 1 and zone[300, 500] == 0 and zone[450, 380] == 0
    assert vt.zone_du_garde_corps({**f, "garde_corps": None}, TAILLE).sum() == 0
    sans = vt.effacer_la_ferronnerie(photo, zone)
    assert sans[450, 451, 0] > 200  # le barreau a disparu
    assert sans[455, 530, 0] == 90  # la fenêtre d'en face est restée
    assert sans[255, 421, 0] == 40 and sans[385, 451, 0] == 40  # rien n'est touché au-dessus du garde-corps
    assert photo[450, 451, 0] == 40  # la photo donnée n'est pas modifiée
    lu = vt.d_une_photo({"photos": {"photo-01": [f]}}, "photo-01", TAILLE)
    assert lu["F1"]["garde_corps"][450, 500] == 1


def test_le_controle_dit_les_defauts_du_tour_et_du_sol():
    bon = {"format": vt.FORMAT, "photos": {"photo-01": deux_battants(sol=[350, 700])}}
    assert vt.controler(bon) == [] and vt.controler({**bon, "format": "vitrages-photos/0.1"}) == []
    for faute in ({"cadre": [[300, 100], [700, 100], [700, 600]]}, {"cadre": [[340, 100], [700, 100], [700, 600], [340, 600]]},
                  {"sol": "bas"}, {"genre_garde_corps": "bois"}, {"garde_corps": [900, 900]}):
        assert vt.controler({"format": vt.FORMAT, "photos": {"photo-01": deux_battants(**faute)}}), faute
