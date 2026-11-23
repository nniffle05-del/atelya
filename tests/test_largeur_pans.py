"""La largeur de chaque pan de rideau, la part qui pend devant la baie, tiré ou ouvert, d'après les photos (22/11/2026,
rideaux 2e temps, étape b). Avant : toujours 45 cm, à cheval sur le bord de la fenêtre, alors que les photos montrent un pan
de 25 cm ramassé à côté de la fenêtre (app-004) ou des pans de 60 à 90 cm à demi tirés (chambres d'app-001)."""
import pytest

from moteur import collisions as co
from moteur import equipements as eq
from moteur import pans_rideaux as pr
from moteur.habillage import rideaux_du_plan
from moteur.logement import Logement
from tests.test_equipements import logement
from tests.test_pans_rideaux import LARGEUR, appareil, baie_du_logement, vue


def pans(vues: list[dict], lg: dict) -> dict[str, dict]:
    return {p["cote"]: p for p in eq.rideaux_des_fenetres(vues, lg)["baie"]["pans"]}


def test_un_pan_vu_contre_sa_fenetre_est_mesure_en_parts_de_celle_ci():
    """Un pan de 25 cm, à côté de la fenêtre (5 cm devant elle) : mesuré contre la fenêtre lue sur la même photo."""
    lg = logement()
    baie = baie_du_logement(lg)  # largeur 1,20 m
    v = vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.80, fenetre=(-0.6, 0.6))
    p = pans([v], lg)["fin"]
    assert p["largeur"] == pytest.approx(0.25, abs=0.02) and p["recouvre"] == pytest.approx(0.05, abs=0.03)
    assert p["etat"] == "ouvert"


def test_la_place_fausse_de_l_appareil_ne_change_pas_la_mesure():
    """app-004 : les photos sont calées seules, à ~0,5 m. L'appareil est CRU 40 cm plus loin le long du mur et 50 cm plus
    près : le pan mesuré contre sa fenêtre garde sa largeur et sa place à 5 cm près (il pend 16 cm devant le mur : un peu de
    parallaxe reste), alors que le report sur le mur du plan le mettait plus de 20 cm à côté."""
    lg = logement()
    baie = baie_du_logement(lg)
    v = vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.80, fenetre=(-0.6, 0.6))
    v["appareil"] = appareil(6.0, 1.9, 0.0)  # la place que le calage croit
    p = pans([v], lg)["fin"]
    assert p["largeur"] == pytest.approx(0.25, abs=0.05) and p["recouvre"] == pytest.approx(0.05, abs=0.05)
    assert abs(v["pan"]["s"][0] - 0.55) > 0.2  # le report sur le mur, lui, est faux


def test_un_seul_vantail_lu_ne_sert_pas_d_etalon():
    """photo-12 d'app-004 : le détecteur ne rend qu'un vantail de la fenêtre (le tiers de la baie du plan). Il ne sert pas
    d'étalon : la largeur est celle mesurée sur le mur."""
    lg = logement()
    baie = baie_du_logement(lg)
    v = vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.80, fenetre=(0.1, 0.5))
    p = pans([v, vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.80, photo=1, fenetre=(0.1, 0.5))], lg)["fin"]
    assert v["pan"]["part"] is None and p["largeur"] == pytest.approx(0.25, abs=0.02) and "recouvre" not in p


def test_deux_pans_sans_fenetre_vue_sont_centres_sur_la_baie():
    """Chambres d'app-001 : la fenêtre est derrière un voilage, rien à lire. Les deux pans vus sur une photo : l'ensemble est
    centré sur la baie (comme une tringle), ce qui retire le décalage de l'appareil ; larges, ils sont « tirés »."""
    lg = logement()
    baie = baie_du_logement(lg)
    cam = appareil(5.0, 1.5, 0.0)
    decale = 0.10  # tout est vu 10 cm trop vers la fin du mur
    p = pans([vue(cam, baie, -0.65 + decale, -0.05 + decale), vue(cam, baie, 0.25 + decale, 0.65 + decale)], lg)
    # ensemble de −0,65 à +0,65, centré : le pan « début » couvre la baie sur 0,55 m, le pan « fin » sur 0,35 m
    assert p["debut"]["recouvre"] == pytest.approx(0.55, abs=0.02) and p["fin"]["recouvre"] == pytest.approx(0.35, abs=0.02)
    # chacun pend jusqu'au bord de la baie, et 5 cm au-delà
    assert p["debut"]["largeur"] == pytest.approx(0.60, abs=0.02) and p["fin"]["largeur"] == pytest.approx(0.40, abs=0.02)
    assert p["debut"]["etat"] == "tire" and p["fin"]["etat"] == "ouvert"


def test_un_pan_coupe_par_le_cadre_ne_donne_qu_un_minimum():
    lg = logement()
    baie = baie_du_logement(lg)
    coupe = vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.70, photo=0)
    coupe["image"] = (int(coupe["boite"][2]) + 5, 800)  # le rectangle touche le bord droit de l'image
    entier = vue(appareil(5.2, 1.4, 0.0), baie, 0.55, 0.85, photo=1, fenetre=(-0.6, 0.6))
    assert pans([coupe, entier], lg)["fin"]["largeur"] == pytest.approx(0.30, abs=0.02)
    # seul, un pan coupé plus étroit que 45 cm ne dit rien de sa largeur : le pan garde ses 45 cm
    seul = eq.rideaux_des_fenetres([coupe], lg)["baie"]
    assert all("largeur" not in p for p in seul.get("pans") or [])


def test_le_mot_de_la_lecture_dit_tire_ou_ouvert():
    lg = logement()
    baie = baie_du_logement(lg)
    v = vue(appareil(5.5, 1.5, 0.0), baie, 0.55, 0.80, fenetre=(-0.6, 0.6))
    v["dit"] = "gris, tirés"
    assert pans([v], lg)["fin"]["etat"] == "tire"
    assert eq.TIRES.search("beige, fermes") and eq.OUVERTS.search("retenus par une embrasse") and not eq.TIRES.search("commode a tiroirs")


def test_le_pan_ne_depasse_pas_le_coin_de_la_piece():
    """Une baie à 20 cm du coin : le pan vu large de 90 cm ne peut pas entrer dans le mur d'à côté, le tissu se ramasse."""
    lg = logement()
    for o in lg["ouvertures"]:
        if o["id"] == "baie":
            o["position"] = 1.8  # de 1,8 à 3,0 le long d'un mur de 3,2 m : le coin de la pièce est à 10 cm du bord de la baie
    baie = baie_du_logement(lg)
    p = pans([vue(appareil(5.5, 2.3, 0.0), baie, 0.55, 1.45, fenetre=(-0.6, 0.6))], lg)["fin"]
    interieur, exterieur = pr.etendue(baie["demi"], p)
    assert exterieur <= baie["demi"] + pr.DEBORD_RIDEAUX + 1e-6 and p["largeur"] < 0.9


def test_sans_mesure_le_pan_d_avant():
    """Un pan jamais mesuré : 45 cm, dont 30 devant la baie et 15 sur le mur, ouvert (rien ne change pour les anciens logements)."""
    assert pr.etendue(0.6, None) == pytest.approx((0.30, 0.75)) and pr.etendue(0.6, {"cote": "fin"}) == pytest.approx((0.30, 0.75))
    assert pr.etat(None, 0.6) == "ouvert"
    assert pr.cotes(None) == [(-1, None), (1, None)]


def test_la_maquette_et_le_controle_des_collisions_suivent_la_mesure():
    lg = logement()
    for o in lg["ouvertures"]:
        if o["id"] == "baie":
            o["rideaux"] = {"rideaux": [150, 140, 130], "statut": "estime", "source": "lecture des photos (2 photo(s))",
                            "pans": [{"cote": "debut", "largeur": 0.25, "recouvre": 0.05, "etat": "ouvert"},
                                     {"cote": "fin", "largeur": 0.80, "recouvre": 0.50, "etat": "tire"}]}
    (r,) = rideaux_du_plan(Logement.model_validate(lg))
    par_etat = {p["etat"]: p for p in r["pans"]}
    assert (par_etat["ouvert"]["x0"], par_etat["ouvert"]["x1"]) == pytest.approx((0.55, 0.80))
    assert (par_etat["tire"]["x0"], par_etat["tire"]["x1"]) == pytest.approx((0.10, 0.90))
    assert par_etat["ouvert"]["cote"] == -par_etat["tire"]["cote"]
    (f,) = co.fenetres_habillees(lg)
    nappes = {n["cote"]: n for n in co.nappes(f)}
    assert nappes[-1]["rect"].h1 == pytest.approx(0.125) and float((nappes[-1]["rect"].c - f["centre"]) @ f["t"]) == pytest.approx(-0.675)
    assert nappes[1]["rect"].h1 == pytest.approx(0.40) and float((nappes[1]["rect"].c - f["centre"]) @ f["t"]) == pytest.approx(0.50)
    assert LARGEUR  # (import gardé : la largeur d'image des vues d'essai)


def test_un_pan_gene_par_un_objet_fixe_se_resserre_au_lieu_d_etre_retire():
    """Zéro collision : un réfrigérateur posé contre le mur de la baie, là où pend le bout d'un pan large. Le pan se resserre
    (le tissu se ramasse) : le rideau n'est ni retiré, ni coupé au-dessus du réfrigérateur, et le réfrigérateur ne bouge pas."""
    from tests.test_collisions import logement as piece, meuble

    frigo = meuble("frigo", "refrigerateur", [3.80, 3.67], 270.0, [0.6, 0.65, 1.8], source="lecture des photos, équipement (1 photo(s))")
    pans_lus = [{"cote": "debut", "largeur": 0.30, "recouvre": 0.05, "etat": "ouvert"}, {"cote": "fin", "largeur": 0.90, "recouvre": 0.20, "etat": "tire"}]
    lg = piece([frigo], rideaux={"baie": {"rideaux": [170, 140, 190], "pans": pans_lus}})  # baie de 1,40 m : milieu en x = 2,60
    assert {c["type"] for c in co.mesurer(lg)} == {"rideau"}  # le pan « fin » va de x = 3,10 à 4,00 ; le réfrigérateur de 3,50 à 4,10
    repare, actions = co.reparer(lg)
    assert co.mesurer(repare) == [] and any(a["action"] == "rideau rétréci" for a in actions)
    r = next(o for o in repare["ouvertures"] if o["id"] == "baie")["rideaux"]
    assert r is not None and not r.get("bas")
    par_cote = {p["cote"]: p for p in r["pans"]}
    assert par_cote["debut"] == pans_lus[0]  # l'autre pan n'a pas changé
    interieur, exterieur = pr.etendue(0.7, par_cote["fin"])
    assert interieur == pytest.approx(0.50, abs=0.002) and 0.75 <= exterieur <= 0.90 - co.JEU + 0.002
    assert next(m for m in repare["meubles"] if m["id"] == "frigo")["position"] == [3.80, 3.67]
    Logement.model_validate(repare)
