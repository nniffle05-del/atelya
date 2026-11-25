"""Les pans de rideaux d'une fenêtre, mesurés sur les photos (19/11/2026, rideaux 2e temps, étape a) : un ou deux pans, et de
quel côté de la fenêtre. Avant : toujours deux pans, alors que les deux fenêtres d'app-004 n'en montrent qu'un."""
import numpy as np

from moteur import collisions as co
from moteur import equipements as eq
from moteur.camera_photo import projeter
from moteur.habillage import rideaux_du_plan
from moteur.logement import Logement
from tests.test_equipements import logement

LARGEUR, HAUTEUR = 1200, 800


def appareil(x: float, y: float, cap: float) -> list[float]:
    return [x, y, 1.4, cap, 0.0, 700.0, LARGEUR / 2, HAUTEUR / 2]


def boite(cam, baie: dict, s0: float, s1: float, z0: float = 0.1, z1: float = 2.3) -> list[float]:
    """Le rectangle, sur la photo, de ce qui pend devant le mur de la fenêtre entre les abscisses s0 et s1 (depuis son milieu)."""
    coins = [projeter([*(baie["centre"] + baie["n"] * eq.ECART_RIDEAUX_M + baie["t"] * s), z], cam)[:2] for s in (s0, s1) for z in (z0, z1)]
    us, vs = [c[0] for c in coins], [c[1] for c in coins]
    return [min(us), min(vs), max(us), max(vs)]


def vue(cam, baie: dict, s0: float, s1: float, photo: int = 0, fenetre: tuple | None = None) -> dict:
    """Un pan de rideau vu sur une photo ; `fenetre` : le rectangle de la fenêtre lu sur la même photo (ses abscisses)."""
    return {"sorte": "rideaux", "photo": photo, "dit": None, "couleur": None, "couleur_vue": (150, 140, 130),
            "point": [float(c) for c in baie["centre"] + baie["n"] * 0.16 + baie["t"] * (s0 + s1) / 2],
            "boite": boite(cam, baie, s0, s1), "appareil": cam, "image": (LARGEUR, HAUTEUR),
            "baies_vues": [boite(cam, baie, *fenetre, z0=0.0, z1=2.15)] if fenetre else []}


def cotes(rideaux: dict) -> list[str]:
    """Les côtés des pans retenus pour une fenêtre (sans leurs mesures : tests/test_largeur_pans.py)."""
    return [p["cote"] for p in rideaux.get("pans") or []]


def baie_du_logement(lg: dict, ident: str = "baie") -> dict:
    return eq.repere_de_la_baie(next(o for o in lg["ouvertures"] if o["id"] == ident), lg)


def test_un_seul_pan_vu_contre_sa_fenetre_et_de_quel_cote():
    """Chambre d'app-004 : toutes les photos montrent UN pan, du même côté de la fenêtre, et l'autre côté sans rideau."""
    lg = logement()
    baie = baie_du_logement(lg)  # mur est, de [8.2, -0.1] vers [8.2, 3.1] : « fin » = vers le nord
    cam = appareil(5.5, 1.5, 0.0)  # dans la cuisine, face à la porte-fenêtre
    vues = [vue(cam, baie, 0.55, 0.85, photo=0, fenetre=(-0.6, 0.6)), vue(appareil(5.0, 1.0, 10.0), baie, 0.55, 0.85, photo=1, fenetre=(-0.6, 0.6))]
    assert vues[0]["boite"][0] < vues[0]["baies_vues"][0][0]  # vu de la pièce, le côté « fin » de ce mur est à GAUCHE de l'image
    r = eq.rideaux_des_fenetres(vues, lg)
    assert cotes(r["baie"]) == ["fin"]
    assert vues[0]["pan"]["par"] == "image" and vues[0]["pan"]["autre_cote_visible"]


def test_deux_rectangles_sur_une_photo_sont_les_deux_pans():
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    r = eq.rideaux_des_fenetres([vue(cam, baie, 0.5, 0.95), vue(cam, baie, -0.95, -0.5)], lg)
    assert cotes(r["baie"]) == ["debut", "fin"]


def test_un_pan_dont_l_autre_cote_est_hors_du_cadre_ne_prouve_rien():
    """La photo ne montre qu'un pan, mais l'autre bord de la fenêtre sort de l'image : un second pan peut y pendre. Deux pans,
    comme avant."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(7.0, 2.6, -20.0)  # près du mur, tourné vers le côté « fin » : le côté « debut » est hors de l'image à droite
    v = vue(cam, baie, 0.55, 0.85, fenetre=(-0.6, 0.6))
    v["baies_vues"][0][2] = float(LARGEUR)  # la fenêtre est coupée par le bord droit de l'image
    r = eq.rideaux_des_fenetres([v], lg)
    # (depuis le 22/11/2026 la largeur vue vaut pour les deux pans : le NOMBRE reste deux, comme sans preuve)
    assert cotes(r["baie"]) == ["debut", "fin"] and not v["pan"]["autre_cote_visible"]


def test_sans_fenetre_lue_le_cote_se_mesure_sur_le_mur_du_plan():
    lg = logement()
    baie = baie_du_logement(lg)
    v = vue(appareil(5.0, 1.5, 0.0), baie, -0.9, -0.55)
    r = eq.rideaux_des_fenetres([v], lg)
    assert cotes(r["baie"]) == ["debut"] and v["pan"]["par"] == "mur"
    assert abs(v["pan"]["s"][0] + 0.9) < 0.02 and abs(v["pan"]["s"][1] + 0.55) < 0.02


def test_une_vue_rasante_ne_vote_pas():
    """photo-03 d'app-004 : le pan est vu presque le long de son mur ; le point où le regard coupe le mur ne veut rien dire
    (1,4 m à côté, du mauvais côté de la fenêtre). Cette vue ne dit rien : deux pans, comme avant."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(7.9, -0.0 + 0.2, 80.0)  # à 30 cm du mur de la fenêtre, regard le long de ce mur
    v = vue(cam, baie, 0.55, 0.85)
    r = eq.rideaux_des_fenetres([v], lg)
    assert "pans" not in r["baie"] and v["pan"]["cote"] is None


def test_l_image_fait_foi_contre_le_mur_du_plan():
    """Deux photos voient le pan contre sa fenêtre (côté « fin ») ; une troisième, sans fenêtre lue et mal placée, le met de
    l'autre côté par le calcul sur le plan : elle ne compte pas."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.5, 1.5, 0.0)
    fausse = vue(appareil(5.2, 1.4, 0.0), baie, -0.9, -0.6, photo=2)
    r = eq.rideaux_des_fenetres([vue(cam, baie, 0.55, 0.85, photo=0, fenetre=(-0.6, 0.6)), fausse], lg)
    assert cotes(r["baie"]) == ["fin"]


def test_le_pan_est_construit_et_controle_du_bon_cote():
    """Du logement à la maquette : le pan « fin » pend bien vers la fin du mur, dans Blender (repère de la fenêtre) comme dans
    le contrôle des collisions ; sans mesure, toujours deux pans."""
    lg = logement()
    for o in lg["ouvertures"]:
        if o["id"] in ("baie", "fenetre"):
            o["rideaux"] = {"rideaux": [150, 140, 130], "pans": [{"cote": "fin"}], "statut": "estime", "source": "lecture des photos (2 photo(s))"}
    modele = Logement.model_validate(lg)
    for r in rideaux_du_plan(modele):
        baie = baie_du_logement(lg, r["id"])
        n = np.array([np.cos(np.radians(r["normale_deg"])), np.sin(np.radians(r["normale_deg"]))])
        x_local = np.array([n[1], -n[0]])  # l'axe x que Blender donne à la fenêtre (moteur/blender/rideaux.py)
        assert len(r["pans"]) == 1 and float(x_local @ baie["t"]) * r["pans"][0]["cote"] > 0
    for f in co.fenetres_habillees(lg):
        (nappe,) = co.nappes(f)
        assert float((nappe["rect"].c - f["centre"]) @ f["t"]) > 0.3
    for o in lg["ouvertures"]:
        if o.get("rideaux"):
            del o["rideaux"]["pans"]
    assert all([p["cote"] for p in r["pans"]] == [-1, 1] for r in rideaux_du_plan(Logement.model_validate(lg)))
    assert all(len(co.nappes(f)) == 2 for f in co.fenetres_habillees(lg))
