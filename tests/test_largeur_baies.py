"""La largeur d'une fenêtre lue sur les photos (étape F1, 20/11/2026, moteur/largeur_baies.py) : les photos peuvent ÉLARGIR
une fenêtre du plan quand elles le contredisent nettement (accord de NT), jamais la rétrécir, et dans la limite du mur libre."""
from moteur import equipements as eq
from moteur import largeur_baies as lb
from moteur.camera_photo import projeter
from moteur.logement import Logement
from tests.test_equipements import logement as logement_cote

LARGEUR, HAUTEUR = 1200, 800


def logement() -> dict:
    """Le logement d'essai, lu sur un plan SANS cotes (ses baies sont « estimées » : les photos peuvent les contredire)."""
    lg = logement_cote()
    for o in lg["ouvertures"]:
        o.update(statut="estime", source="lecture_claude")
    return lg


def appareil(x: float, y: float, cap: float) -> list[float]:
    return [x, y, 1.4, cap, 0.0, 500.0, LARGEUR / 2, HAUTEUR / 2]


def baie_du_logement(lg: dict, ident: str = "baie") -> dict:
    return eq.repere_de_la_baie(next(o for o in lg["ouvertures"] if o["id"] == ident), lg)


def objet(cam, baie: dict, s0: float, s1: float, sorte: str = "porte_fenetre", dit: str | None = None, ecart: float = 0.0) -> dict:
    """Ce qu'une photo encadre sur le mur de la baie, entre les abscisses s0 et s1 (depuis le milieu de la baie du plan)."""
    coins = [projeter([*(baie["centre"] + baie["n"] * ecart + baie["t"] * s), z], cam)[:2] for s in (s0, s1) for z in (0.1, 2.2)]
    us, vs = [c[0] for c in coins], [c[1] for c in coins]
    return {"sorte": sorte, "dit": dit, "boite": [min(us), min(vs), max(us), max(vs)]}


def mesures(lg: dict, cam, objets: list[dict], photo: str = "photo-01") -> list[dict]:
    return lb.mesures_d_une_photo(objets, cam, LARGEUR, lg, photo=photo)


def largeur_de(lg: dict, ident: str = "baie") -> float:
    return next(o for o in lg["ouvertures"] if o["id"] == ident)["largeur"]


def test_une_baie_vue_nettement_plus_large_que_le_plan_est_elargie():
    """Le coin repas d'app-001 : 1,2 m sur le plan, la photo montre une baie de 2,2 m. Elle est élargie là où la photo la voit."""
    lg = logement()
    baie = baie_du_logement(lg)  # mur est, de [8.2, -0.1] vers [8.2, 3.1] ; la baie du plan : 1,2 m, milieu à 1,6 m
    cam = appareil(5.0, 1.5, 0.0)
    m = mesures(lg, cam, [objet(cam, baie, -1.1, 1.1)])
    assert len(m) == 1 and m[0]["baie"] == "baie" and m[0]["par"] == "fenetre" and m[0]["francs"] == [True, True]
    assert abs(m[0]["s"][0] + 1.1) < 0.02 and abs(m[0]["s"][1] - 1.1) < 0.02
    apres, changes, doutes = lb.elargir(lg, m)
    o = next(o for o in apres["ouvertures"] if o["id"] == "baie")
    assert abs(o["largeur"] - 2.2) < 0.03 and abs(o["position"] - 0.5) < 0.03
    assert o["statut"] == "estime" and o["source"].startswith("photos") and "1.20" in o["source"]
    assert changes[0]["avant"] == {"position": 1.0, "largeur": 1.2} and changes[0]["photos"] == ["photo-01"] and not doutes
    assert largeur_de(lg) == 1.2  # le logement donné n'est pas touché
    Logement.model_validate(apres)


def test_une_baie_vue_comme_le_plan_ou_plus_etroite_ne_change_pas():
    """La mesure vaut 30 à 50 cm : un petit écart n'est pas une contradiction. Et les photos ne rétrécissent jamais une baie."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    for s0, s1 in ((-0.8, 0.8), (-0.6, 0.6), (-0.3, 0.4)):
        apres, changes, doutes = lb.elargir(lg, mesures(lg, cam, [objet(cam, baie, s0, s1)]))
        assert largeur_de(apres) == 1.2 and not changes and not doutes


def test_la_baie_elargie_s_arrete_au_coin_de_la_piece_et_avant_une_autre_ouverture():
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(4.6, 1.5, 0.0)
    apres, changes, _ = lb.elargir(lg, mesures(lg, cam, [objet(cam, baie, -1.7, 1.7)]))
    o = next(o for o in apres["ouvertures"] if o["id"] == "baie")
    # la pièce va de y = 0 à y = 3 (abscisses 0,1 à 3,1 du mur) : il reste 10 cm de mur à chaque coin
    assert abs(o["position"] - 0.2) < 0.04 and abs(o["position"] + o["largeur"] - 3.0) < 0.04
    Logement.model_validate(apres)
    lg["ouvertures"].append({"id": "petite", "type": "fenetre", "mur": "est", "position": 2.6, "largeur": 0.4, "hauteur": 1.0, "allege": 1.0,
                             "statut": "mesure", "source": "essai"})
    portee = lb.portee_libre(next(o for o in lg["ouvertures"] if o["id"] == "baie"), lg)
    assert abs(portee[1] - (2.6 - 1.6 - lb.ENTRE_BAIES)) < 1e-6 and abs(portee[0] + 1.4) < 0.04


def test_un_voilage_ne_prouve_rien_sans_la_baie_vue_derriere_lui():
    """Un voilage peut courir d'un mur à l'autre devant une petite fenêtre : il ne mesure la baie que si la lecture dit qu'on
    la voit derrière lui sur toute la largeur ; la baie est alors le voilage moins ce qu'il déborde."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    nu = objet(cam, baie, -1.2, 1.2, "rideaux", "voilages blancs", eq.ECART_RIDEAUX_M)
    assert mesures(lg, cam, [nu]) == []
    assert mesures(lg, cam, [objet(cam, baie, -1.2, 1.2, "rideaux", "beige, avec voilages", eq.ECART_RIDEAUX_M)]) == []
    dit = objet(cam, baie, -1.2, 1.2, "rideaux", "voilages blancs, baie sur toute la largeur", eq.ECART_RIDEAUX_M)
    m = mesures(lg, cam, [dit])
    assert m[0]["par"] == "voilage" and abs(m[0]["s"][0] + 1.2 - lb.MARGE_VOILAGE) < 0.02 and abs(m[0]["s"][1] - 1.2 + lb.MARGE_VOILAGE) < 0.02
    apres, changes, _ = lb.elargir(lg, m)
    assert abs(largeur_de(apres) - 2.1) < 0.04 and changes[0]["par"] == ["voilage"]


def test_un_bord_coupe_par_le_cadre_ou_cache_par_un_meuble_n_est_pas_un_vrai_bout():
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    o = objet(cam, baie, -0.5, 1.0)
    o["boite"][0] = 10.0  # le rectangle va jusqu'au bord gauche de l'image : la baie sort du cadre de ce côté
    m = mesures(lg, cam, [o])
    assert m and m[0]["francs"] == [True, False]  # vu de la pièce, la fin de ce mur est à GAUCHE de l'image : ce bout-là est coupé
    fenetre = objet(cam, baie, -1.1, 1.1)
    buffet = {"sorte": "rangement", "dit": None, "boite": [fenetre["boite"][2] - 30, 300, fenetre["boite"][2] + 200, 700]}
    m = mesures(lg, cam, [fenetre, buffet])
    assert m[0]["francs"].count(False) == 1  # le bord que le buffet touche n'est pas un vrai bout


def test_des_photos_qui_ne_s_accordent_pas_ne_changent_rien():
    """Une photo voit la baie ENTIÈRE à la largeur du plan, une autre la voit bien plus large : doute, rien ne change."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    m = mesures(lg, cam, [objet(cam, baie, -1.1, 1.1)], "photo-01") + mesures(lg, cam, [objet(cam, baie, -0.62, 0.62)], "photo-02")
    apres, changes, doutes = lb.elargir(lg, m)
    assert largeur_de(apres) == 1.2 and not changes
    assert doutes[0]["id"] == "baie" and doutes[0]["comme_le_plan"][0][0] == "photo-02" and doutes[0]["plus_large"][0][0] == "photo-01"


def test_une_vue_rasante_ou_d_une_autre_piece_ne_mesure_pas():
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(7.9, 0.3, 80.0)  # le long du mur de la baie
    assert mesures(lg, cam, [objet(cam, baie, -1.1, 1.1)]) == []
    cam = appareil(2.0, 1.5, 0.0)  # dans le séjour : le mur du milieu est entre l'appareil et la baie
    assert mesures(lg, cam, [objet(cam, baie, -1.1, 1.1)]) == []


def test_deux_vantaux_encadres_separement_font_une_seule_baie():
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    m = mesures(lg, cam, [objet(cam, baie, -1.1, 0.0), objet(cam, baie, 0.02, 1.1)])
    assert len(m) == 1 and abs(m[0]["s"][0] + 1.1) < 0.02 and abs(m[0]["s"][1] - 1.1) < 0.02


def test_le_temoin_d_un_objet_lu():
    assert lb.temoin({"sorte": "fenetre"}) == "fenetre" and lb.temoin({"sorte": "porte_fenetre", "dit": "baie coulissante"}) == "fenetre"
    assert lb.temoin({"sorte": "rideaux", "dit": "voilages blancs, baie sur toute la largeur"}) == "voilage"
    assert lb.temoin({"sorte": "rideaux", "dit": "voilages blancs"}) is None
    assert lb.temoin({"sorte": "rideaux", "dit": "gris"}) is None and lb.temoin({"sorte": "canape"}) is None


def test_une_baie_cotee_ou_posee_par_une_personne_n_est_jamais_elargie():
    """« Ce qu'une personne a placé ne bouge jamais », et le plan coté fait foi : les photos ne font alors que lever un doute."""
    cam = appareil(5.0, 1.5, 0.0)
    for statut, source in (("mesure", "cote_plan"), ("estime", "lecture_claude+verification")):
        lg = logement()
        next(o for o in lg["ouvertures"] if o["id"] == "baie").update(statut=statut, source=source)
        apres, changes, doutes = lb.elargir(lg, mesures(lg, cam, [objet(cam, baie_du_logement(lg), -1.1, 1.1)]))
        assert largeur_de(apres) == 1.2 and not changes and doutes[0]["id"] == "baie" and "raison" in doutes[0]
    lg = logement()
    m = mesures(lg, cam, [objet(cam, baie_du_logement(lg), -1.1, 1.1)])
    apres, changes, doutes = lb.elargir(lg, m, refusees=["baie"])  # refusé à l'écran de vérification
    assert largeur_de(apres) == 1.2 and not changes and not doutes
