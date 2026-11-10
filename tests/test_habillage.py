"""Tests de l'habillage : menuiseries, matériaux, lumières, caméras (sans Blender)."""

import json
import math
from pathlib import Path

import pytest

from moteur.geometrie import calculer_briques
from moteur.habillage import (
    EPAISSEUR_PLINTHE, FORMAT, HAUTEUR_PLINTHE, LARGEUR_CHAMBRANLE, _axes_camera, _dans, menuiseries, plan_habille,
    sol_de_la_piece,
)
from moteur.logement import Logement, charger_logement

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"


@pytest.fixture
def logement():
    return charger_logement(CAS_TEST_00)


@pytest.fixture
def plan(logement):
    return json.loads(json.dumps(plan_habille(logement)))


def boite(b):
    xs = [p[0] for p in b["contour"]]
    ys = [p[1] for p in b["contour"]]
    return (min(xs), min(ys), b["z_bas"]), (max(xs), max(ys), b["z_haut"])


def volume_commun(a, b):
    (a_min, a_max), (b_min, b_max) = a, b
    v = 1.0
    for i in range(3):
        v *= max(0.0, min(a_max[i], b_max[i]) - max(a_min[i], b_min[i]))
    return v


def test_plan_habille_lisible(plan):
    assert plan["schema"] == "construction/0.2"
    # les briques de l'étape 2 + les menuiseries + (B2-1) 24 chambranles, 4 appuis et 24 morceaux de plinthes
    # + (B2-3) une copie sous le sol de chacune des 4 pièces
    assert len(plan["briques"]) == 36 + 45 + 24 + 4 + 24 + 4
    assert all(b["materiau"] for b in plan["briques"])


def test_une_menuiserie_par_ouverture(logement):
    elements = {b.element for b in menuiseries(logement)}
    assert elements == {o.id for o in logement.ouvertures}


def test_vitres(logement):
    vitres = [b for b in menuiseries(logement) if b.materiau == "verre"]
    # 3 fenêtres ou portes-fenêtres d'au moins 1 m : deux vantaux chacune.
    assert len(vitres) == 6


def test_les_menuiseries_ne_rentrent_pas_dans_les_murs(plan):
    murs = [boite(b) for b in plan["briques"] if b["categorie"] == "mur"]
    for b in plan["briques"]:
        if b["categorie"] == "menuiserie":
            for mur in murs:
                assert volume_commun(boite(b), mur) == pytest.approx(0, abs=1e-9), b["id"]


def test_porte_d_entree_reconnue(plan):
    entrees = {b["element"] for b in plan["briques"] if b["materiau"] == "porte_entree"}
    assert entrees == {"P_entree"}


@pytest.mark.parametrize("nom, sol", [
    ("Séjour + cuisine", "parquet"),
    ("Chambre 2", "parquet"),
    ("Entrée", "carrelage"),
    ("Salle d'eau", "carrelage"),
    ("Salle de bains", "carrelage"),
    ("WC", "carrelage"),
    ("Cuisine", "carrelage"),
    ("Grenier", "parquet"),  # nom inconnu : parquet par défaut
])
def test_sol_selon_le_nom(nom, sol):
    assert sol_de_la_piece(nom) == sol


def test_sols_du_cas_test(plan):
    sols = {b["element"]: b["materiau"] for b in plan["briques"] if b["id"].startswith("sol__")}
    assert sols == {"sejour": "chene_naturel_photo", "chambre": "chene_naturel_photo",
                    "entree": "carrelage_interieur", "sdb": "carrelage_interieur"}


def test_un_plafonnier_par_piece_sous_le_plafond(plan, logement):
    plafonniers = [l for l in plan["lumieres"] if l["type"] == "plafonnier"]
    assert sorted(l["piece"] for l in plafonniers) == sorted(p.id for p in logement.pieces)
    pieces = {p.id: p for p in logement.pieces}
    for l in plafonniers:
        assert _dans(l["position"][:2], pieces[l["piece"]].contour)
        assert l["position"][2] < logement.hauteur_sous_plafond


def test_vue_de_dessus_cadre_tout_le_logement(plan, logement):
    vue = next(v for v in plan["vues"] if v["id"] == "dessus")
    droite, haut = _axes_camera(vue["position"], vue["cible"])
    demi_largeur = vue["echelle"] / 2
    demi_hauteur = demi_largeur * FORMAT[1] / FORMAT[0]
    for b in calculer_briques(logement):
        for x, y in b.contour:
            for z in (b.z_bas, b.z_haut):
                v = [x - vue["cible"][0], y - vue["cible"][1], z - vue["cible"][2]]
                assert abs(sum(a * c for a, c in zip(v, droite))) < demi_largeur
                assert abs(sum(a * c for a, c in zip(v, haut))) < demi_hauteur


def test_vue_interieure_du_sejour(plan, logement):
    vue = next(v for v in plan["vues"] if v["projection"] == "perspective")
    assert vue["piece"] == "sejour"
    sejour = next(p for p in logement.pieces if p.id == "sejour")
    assert _dans(vue["position"][:2], sejour.contour)
    assert 1.2 < vue["position"][2] < 1.8  # hauteur d'œil
    # Le coin choisi (sud-est) voit la fenêtre ouest et la porte-fenêtre nord.
    (cx, cy, _), (tx, ty, _) = vue["position"], vue["cible"]
    visee = math.atan2(ty - cy, tx - cx)
    for fx, fy in [(-0.10, 2.80), (2.20, 5.50)]:
        ecart = (math.atan2(fy - cy, fx - cx) - visee + math.pi) % (2 * math.pi) - math.pi
        assert abs(ecart) < math.radians(45)


# ------------------------------------------------------------------ B2-1 : plinthes, chambranles, appuis


def _piece_simple(nom="Séjour", plinthes=None, **ouvertures_en_plus):
    """Une pièce de 4 × 3 m (murs de 20 cm, axes à ±0,1 m du bord) : porte au sud, fenêtre à l'est, porte-fenêtre au nord."""
    mur = lambda i, d, f: {"id": i, "debut": d, "fin": f, "epaisseur": 0.2, "statut": "mesure", "source": "test"}
    ouv = lambda i, t, m, pos, l, h, a: {"id": i, "type": t, "mur": m, "position": pos, "largeur": l, "hauteur": h,
                                         "allege": a, "statut": "mesure", "source": "test"}
    return Logement.model_validate({
        "schema": "logement/0.1", "projet_id": "PIECE", "hauteur_sous_plafond": 2.5,
        "murs": [mur("S", [-0.1, -0.1], [4.1, -0.1]), mur("E", [4.1, -0.1], [4.1, 3.1]),
                 mur("N", [-0.1, 3.1], [4.1, 3.1]), mur("O", [-0.1, -0.1], [-0.1, 3.1])],
        "ouvertures": [ouv("porte", "porte", "S", 1.0, 0.9, 2.04, 0.0),
                       ouv("fenetre", "fenetre", "E", 1.0, 1.2, 1.3, 0.9),
                       ouv("pf", "porte_fenetre", "N", 2.0, 1.4, 2.15, 0.0)],
        "pieces": [{"id": "sejour", "nom": nom, "contour": [[0, 0], [4, 0], [4, 3], [0, 3]],
                    "statut": "mesure", "source": "test", **({"plinthes": plinthes} if plinthes else {})}],
    })


def _aire(contour):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]))) / 2


def test_plinthes_font_le_tour_sauf_devant_les_ouvertures_basses():
    plan = plan_habille(_piece_simple())
    plinthes = [b for b in plan["briques"] if b["id"].startswith("plinthe__")]
    assert plinthes and all(b["z_bas"] == 0 and b["z_haut"] == HAUTEUR_PLINTHE for b in plinthes)
    # Aire exacte de l'anneau de plinthes : tour complet (biseaux sans trou ni recouvrement dans les 4 angles), moins la
    # porte et ses deux chambranles (+ 1 mm de jeu de chaque côté), moins la porte-fenêtre ; la fenêtre ne coupe rien.
    e = EPAISSEUR_PLINTHE
    anneau = 4 * 3 - (4 - 2 * e) * (3 - 2 * e)
    trou_porte = (0.9 + 2 * (LARGEUR_CHAMBRANLE + 0.001)) * e
    trou_pf = 1.4 * e
    assert sum(_aire(b["contour"]) for b in plinthes) == pytest.approx(anneau - trou_porte - trou_pf, abs=1e-6)
    # rien au droit de la porte-fenêtre (x de 1,9 à 3,3 sur le mur nord, y proche de 3)
    for b in plinthes:
        xs = [p[0] for p in b["contour"]]
        ys = [p[1] for p in b["contour"]]
        if min(ys) > 2.9:
            assert max(xs) <= 1.9 + 1e-6 or min(xs) >= 3.3 - 1e-6


def test_chambranles_sur_les_deux_faces_de_chaque_porte():
    plan = plan_habille(_piece_simple())
    chambranles = [b for b in plan["briques"] if "chambranle" in b["id"]]
    assert {b["element"] for b in chambranles} == {"porte"}
    assert len(chambranles) == 6  # deux montants et une traverse, sur chaque face
    ys = sorted({round(min(p[1] for p in b["contour"]), 3) for b in chambranles})
    assert ys == [-0.22, 0.0]  # posés sur la face extérieure (y = -0,2) et intérieure (y = 0) du mur sud


def test_fenetre_pres_de_la_face_interieure_avec_appui():
    plan = plan_habille(_piece_simple())
    briques = {b["id"]: b for b in plan["briques"]}
    cadre = briques["fenetre__montant_1"]
    xs = [p[0] for p in cadre["contour"]]
    centre_mur = 4.1
    assert sum(xs) / len(xs) < centre_mur  # la pièce est à l'ouest du mur est : le cadre s'y décale
    assert "fenetre__appui" in briques and "fenetre__appui_nez" in briques
    nez = briques["fenetre__appui_nez"]
    assert min(p[0] for p in nez["contour"]) == pytest.approx(4.0 - 0.03)  # dépasse de 3 cm dans la pièce
    assert nez["z_bas"] == pytest.approx(0.9)
    assert not any(i.startswith("pf__appui") for i in briques)  # pas d'appui sous une porte-fenêtre


# ---- Plinthes décidées pièce par pièce (habillage 0.4) ----

def _plinthes_de(plan):
    return [b for b in plan["briques"] if b["id"].startswith("plinthe__")]


def test_une_piece_sans_plinthes_n_en_a_pas():
    vu = {"choix": "aucune", "statut": "estime", "source": "photo_03"}
    assert _plinthes_de(plan_habille(_piece_simple(plinthes=vu))) == []


def test_plinthes_en_carrelage_plus_basses_et_comme_le_sol():
    from moteur.habillage import EPAISSEUR_PLINTHE_CARRELAGE, HAUTEUR_PLINTHE_CARRELAGE

    choisi = {"choix": "carrelage", "statut": "mesure", "source": "verification"}
    plinthes = _plinthes_de(plan_habille(_piece_simple(nom="Salle de bain", plinthes=choisi)))
    assert plinthes and all(b["z_haut"] == HAUTEUR_PLINTHE_CARRELAGE and b["materiau"] == "carrelage_interieur"
                            for b in plinthes)
    e = EPAISSEUR_PLINTHE_CARRELAGE  # même tour exact que les plinthes en bois, avec l'épaisseur d'un carreau
    anneau = 4 * 3 - (4 - 2 * e) * (3 - 2 * e)
    trous = (0.9 + 2 * (LARGEUR_CHAMBRANLE + 0.001)) * e + 1.4 * e
    assert sum(_aire(b["contour"]) for b in plinthes) == pytest.approx(anneau - trous, abs=1e-6)
    # dans un séjour en parquet, des plinthes carrelées choisies restent en carrelage (pas en parquet)
    plinthes = _plinthes_de(plan_habille(_piece_simple(plinthes=choisi)))
    assert {b["materiau"] for b in plinthes} == {"carrelage_interieur"}


def test_regle_par_defaut_quand_rien_n_est_vu():
    from moteur.habillage import plinthes_par_defaut

    assert plinthes_par_defaut("Salle de bain") == "carrelage"
    assert plinthes_par_defaut("WC") == "carrelage"
    assert plinthes_par_defaut("Chambre 2") == "bois"
    assert {b["materiau"] for b in _plinthes_de(plan_habille(_piece_simple()))} == {"menuiserie_blanche"}
    assert {b["materiau"] for b in _plinthes_de(plan_habille(_piece_simple(nom="Cuisine")))} == {"carrelage_interieur"}


def test_completer_plinthes_ecrit_la_regle_sans_toucher_un_choix_deja_fait():
    from moteur.habillage import completer_plinthes

    logement = _piece_simple().model_dump(by_alias=True, exclude_none=True)
    logement["pieces"].append({**logement["pieces"][0], "id": "sdb", "nom": "Salle de bain",
                               "plinthes": {"choix": "aucune", "statut": "estime", "source": "photo_05"}})
    complet = completer_plinthes(logement)
    assert "plinthes" not in logement["pieces"][0]  # l'original n'est pas modifié
    assert complet["pieces"][0]["plinthes"] == {"choix": "bois", "statut": "ajoute", "source": "regle_par_defaut",
                                                "confiance": 0.5}
    assert complet["pieces"][1]["plinthes"]["choix"] == "aucune"


def test_le_format_refuse_des_plinthes_inconnues():
    with pytest.raises(ValueError):
        _piece_simple(plinthes={"choix": "marbre", "statut": "mesure", "source": "verification"})


# ---- Portes de placard (habillage 0.5, B2-2) ----

def _chambre_et_placard(facade="ouverte", nom="Placard", placard=None):
    """Une chambre de 4 × 3 m et, au nord-ouest, un placard de 1,6 m de large : ouvert sur la chambre (pas de mur entre
    eux), ou fermé par un mur percé d'une porte de 1,2 m (la façade dessinée comme une porte)."""
    mur = lambda i, d, f: {"id": i, "debut": d, "fin": f, "epaisseur": 0.2, "statut": "mesure", "source": "test"}
    murs = [mur("S", [-0.1, -0.1], [4.1, -0.1]), mur("E", [4.1, -0.1], [4.1, 3.1])]
    ouvertures = []
    if facade == "ouverte":
        murs += [mur("O", [-0.1, -0.1], [-0.1, 3.7]), mur("N", [1.7, 3.1], [4.1, 3.1]),
                 mur("PE", [1.7, 3.1], [1.7, 3.7]), mur("PN", [-0.1, 3.7], [1.7, 3.7])]
        haut = 3.0
    else:
        murs += [mur("O", [-0.1, -0.1], [-0.1, 3.9]), mur("N", [-0.1, 3.1], [4.1, 3.1]),
                 mur("PE", [1.7, 3.1], [1.7, 3.9]), mur("PN", [-0.1, 3.9], [1.7, 3.9])]
        ouvertures = [{"id": "porte_placard", "type": "porte", "mur": "N", "position": 0.3, "largeur": 1.2,
                       "hauteur": 2.04, "statut": "mesure", "source": "test"}]
        haut = 3.2
    piece = {"id": "placard", "nom": nom, "contour": [[0, haut], [1.6, haut], [1.6, haut + 0.6], [0, haut + 0.6]],
             "statut": "mesure", "source": "test", **({"placard": placard} if placard else {})}
    return Logement.model_validate({
        "schema": "logement/0.1", "projet_id": "PLACARD", "hauteur_sous_plafond": 2.5, "murs": murs,
        "ouvertures": ouvertures,
        "pieces": [{"id": "chambre", "nom": "Chambre", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]],
                    "statut": "mesure", "source": "test"}, piece],
    })


def _briques_placard(plan, prefixe="placard__"):
    return [b for b in plan["briques"] if b["id"].startswith(prefixe)]


def test_placard_ouvert_ferme_par_des_portes_coulissantes_par_defaut():
    plan = plan_habille(_chambre_et_placard())
    briques = _briques_placard(plan)
    panneaux = [b for b in briques if "__panneau_" in b["id"]]
    assert len(panneaux) == 2 and len([b for b in briques if "__rail_" in b["id"]]) == 2
    # dans la façade : de x = 0 à 1,6, juste derrière la ligne y = 3 (côté placard), du sol presque au plafond
    xs = [p[0] for b in panneaux for p in b["contour"]]
    ys = [p[1] for b in panneaux for p in b["contour"]]
    assert min(xs) == pytest.approx(0.0, abs=1e-3) and max(xs) == pytest.approx(1.6, abs=1e-3)
    assert 3.0 <= min(ys) and max(ys) <= 3.06
    assert all(b["z_haut"] > 2.4 for b in panneaux)
    # les deux panneaux se recouvrent un peu, sur deux plans différents
    (a, b) = sorted(panneaux, key=lambda x: min(p[0] for p in x["contour"]))
    assert max(p[0] for p in a["contour"]) > min(p[0] for p in b["contour"])
    assert max(p[1] for p in a["contour"]) <= min(p[1] for p in b["contour"]) + 1e-6
    # pas de plinthe dans la façade : le long du bord nord de la chambre, seulement contre le mur (x ≥ 1,6)
    nord = [p for p in _plinthes_de(plan) if p["element"] == "chambre" and min(q[1] for q in p["contour"]) > 2.9]
    assert nord and all(min(q[0] for q in p["contour"]) >= 1.6 - 0.02 for p in nord)


def test_placard_portes_battantes_ou_ouvert_selon_le_choix():
    battantes = {"choix": "battantes", "statut": "mesure", "source": "verification"}
    briques = _briques_placard(plan_habille(_chambre_et_placard(placard=battantes)))
    assert len([b for b in briques if "__vantail_" in b["id"]]) == 3  # 1,6 m : trois portes de 0,53 m
    assert len([b for b in briques if "__poignee_" in b["id"]]) == 3
    aucune = {"choix": "aucune", "statut": "estime", "source": "photo_02"}
    assert _briques_placard(plan_habille(_chambre_et_placard(placard=aucune))) == []


def test_facade_dessinee_comme_une_porte_recoit_des_portes_de_placard():
    plan = plan_habille(_chambre_et_placard(facade="porte"))
    porte = [b for b in plan["briques"] if b["element"] == "porte_placard"]
    noms = {b["id"].split("__", 1)[1] for b in porte}
    assert "battant" not in noms and "poignee_1" not in noms  # plus de porte de pièce
    assert {"montant_1", "chambranle_a_1", "chambranle_b_1"} <= noms  # le cadre reste
    panneaux = [b for b in porte if "__panneau_" in b["id"]]
    assert len(panneaux) == 2  # 1,2 m - 2 montants = 1,08 m : coulissantes par défaut
    ys = [p[1] for b in panneaux for p in b["contour"]]
    assert 3.0 - 1e-6 <= min(ys) and max(ys) <= 3.2 + 1e-6  # dans l'épaisseur du mur


def test_un_grand_dressing_n_est_pas_un_placard():
    from moteur.habillage import est_placard
    from moteur.logement import Piece

    carre = lambda c: [[0, 0], [c, 0], [c, c], [0, c]]
    piece = lambda nom, c: Piece(id="x", nom=nom, contour=carre(c), statut="mesure", source="test")
    assert est_placard(piece("Placard 2", 1.0)) and est_placard(piece("Pièce 4 (rangement)", 1.2))
    assert not est_placard(piece("Dressing", 3.0))  # 9 m² : une pièce, avec une porte ordinaire
    assert not est_placard(piece("Chambre", 1.0))


def test_completer_finitions_ecrit_le_choix_par_defaut_des_placards():
    from moteur.habillage import completer_finitions

    logement = _chambre_et_placard().model_dump(by_alias=True, exclude_none=True)
    complet = completer_finitions(logement)
    pieces = {p["id"]: p for p in complet["pieces"]}
    assert pieces["placard"]["placard"] == {"choix": "coulissantes", "statut": "ajoute", "source": "regle_par_defaut",
                                            "confiance": 0.5}
    assert "placard" not in pieces["chambre"]
    assert pieces["chambre"]["plinthes"]["choix"] == "bois"


def test_deux_portes_proches_se_partagent_le_trumeau():
    from moteur.habillage import LARGEUR_CHAMBRANLE

    log = _piece_simple()
    d = log.model_dump(by_alias=True, exclude_none=True)
    d["ouvertures"].append({**d["ouvertures"][0], "id": "porte2", "position": 1.0 + 0.9 + 0.08})  # trumeau de 8 cm
    plan = plan_habille(Logement.model_validate(d))
    droite = [b for b in plan["briques"] if b["id"] == "porte__chambranle_a_2"][0]
    gauche = [b for b in plan["briques"] if b["id"] == "porte2__chambranle_a_1"][0]
    assert max(p[0] for p in droite["contour"]) <= min(p[0] for p in gauche["contour"]) + 1e-6  # ne se recouvrent pas
    assert LARGEUR_CHAMBRANLE > 0.04  # sans le partage, ils se recouvriraient


# ---- Sols en vraies matières (habillage 0.6, B2-3) ----

def test_le_sol_choisi_est_pose_et_les_plinthes_carrelees_le_suivent():
    tomettes = {"matiere": "tomettes", "statut": "estime", "source": "photo_04"}
    log = _piece_simple(plinthes=None)
    d = log.model_dump(by_alias=True, exclude_none=True)
    d["pieces"][0]["sol"] = tomettes
    plan = plan_habille(Logement.model_validate(d))
    assert {b["materiau"] for b in plan["briques"] if b["id"] == "sol__sejour"} == {"tomettes"}
    # sol carrelé choisi : les plinthes supposées deviennent carrelées, dans la matière du sol
    assert {b["materiau"] for b in _plinthes_de(plan)} == {"tomettes"}
    # sous des carreaux de ciment (motif), une plinthe unie
    d["pieces"][0]["sol"] = {**tomettes, "matiere": "carreaux_ciment"}
    assert {b["materiau"] for b in _plinthes_de(plan_habille(Logement.model_validate(d)))} == {"carrelage"}


def test_le_format_refuse_un_sol_inconnu():
    d = _piece_simple().model_dump(by_alias=True, exclude_none=True)
    d["pieces"][0]["sol"] = {"matiere": "moquette", "statut": "mesure", "source": "verification"}
    with pytest.raises(ValueError):
        Logement.model_validate(d)


def test_completer_ecrit_le_sol_par_defaut():
    from moteur.habillage import completer_finitions

    d = _piece_simple(nom="Salle de bain").model_dump(by_alias=True, exclude_none=True)
    p = completer_finitions(d)["pieces"][0]
    assert p["sol"]["matiere"] == "carrelage_interieur" and p["sol"]["statut"] == "ajoute"
    assert p["plinthes"]["choix"] == "carrelage"


def test_sous_chaque_sol_une_copie_un_peu_plus_large_et_plus_basse():
    plan = plan_habille(_piece_simple())
    sol = next(b for b in plan["briques"] if b["id"] == "sol__sejour")
    dessous = next(b for b in plan["briques"] if b["id"] == "sous_sol__sejour")
    assert dessous["z_haut"] == dessous["z_bas"] < 0 and dessous["materiau"] == sol["materiau"]
    xs = [p[0] for p in dessous["contour"]]
    assert min(xs) == pytest.approx(min(p[0] for p in sol["contour"]) - 0.02, abs=1e-3)
    assert _aire(dessous["contour"]) > _aire(sol["contour"])


def test_les_lames_suivent_les_murs_les_plus_longs():
    from moteur.habillage import orientation_sols

    assert orientation_sols(_piece_simple()) == pytest.approx(0.0)  # 4 m est-ouest contre 3 m nord-sud
    d = _piece_simple().model_dump(by_alias=True, exclude_none=True)
    for m in d["murs"]:  # le même logement tourné d'un quart de tour
        m["debut"], m["fin"] = [-m["debut"][1], m["debut"][0]], [-m["fin"][1], m["fin"][0]]
    for p in d["pieces"]:
        p["contour"] = [[-y, x] for x, y in p["contour"]]
    import math
    assert orientation_sols(Logement.model_validate(d)) == pytest.approx(math.pi / 2)


def test_l_ecran_connait_les_memes_sols_que_le_moteur():
    import re
    from pathlib import Path

    from moteur.matieres import SOLS

    js = (Path(__file__).parent.parent / "outils" / "verification-plan" / "calculs-verif.js").read_text(encoding="utf-8")
    bloc = js[js.index("const SOLS = {"):]
    bloc = bloc[:bloc.index("};")]
    ecran = dict(re.findall(r'(\w+): "([^"]+)"', bloc))
    assert list(ecran) == list(SOLS)
    assert ecran == {k: v[0] for k, v in SOLS.items()}


# ---- Lumière du jour (habillage 0.7, B2-4) ----

def test_un_portail_devant_chaque_fenetre_qui_donne_dehors():
    plan = plan_habille(_piece_simple())
    portails = {l["id"]: l for l in plan["lumieres"] if l["type"] == "portail"}
    assert set(portails) == {"Portail_fenetre", "Portail_pf"}  # pas la porte
    f = portails["Portail_fenetre"]  # fenêtre du mur est (x = 4,1) : portail dehors (x > 4,2), tourné vers l'ouest
    assert f["position"][0] > 4.2 and f["direction"] == [-1.0, 0.0, 0.0]
    assert f["taille"] == [1.2, 1.3] and f["position"][2] == pytest.approx(0.9 + 1.3 / 2)
    assert portails["Portail_pf"]["direction"] == [0.0, -1.0, 0.0]  # mur nord : vers le sud


def test_sens_d_ouverture_d_une_porte():
    """10/11/2026 : gonds et côté d'ouverture réglables (écran de vérification) : la poignée passe du côté opposé aux gonds,
    le battant affleure la face du mur vers laquelle la porte s'ouvre ; sans réglage, rien ne change."""
    from moteur.logement import Logement
    lg = _piece_simple().model_dump(by_alias=True, mode="json")
    porte = next(o for o in lg["ouvertures"] if o["id"] == "porte")
    avant = {b["id"]: b for b in plan_habille(_piece_simple())["briques"]}
    porte["sens"] = {"charniere": "fin", "ouvre_vers": "droite"}
    apres = {b["id"]: b for b in plan_habille(Logement.model_validate(lg))["briques"]}
    centre = lambda b: [sum(q[i] for q in b["contour"]) / len(b["contour"]) for i in (0, 1)]  # noqa: E731
    # poignée : de l'autre côté de la porte le long du mur
    assert centre(apres["porte__poignee_1"]) != pytest.approx(centre(avant["porte__poignee_1"]), abs=0.05)
    # battant : décalé du milieu du mur vers une face
    assert centre(apres["porte__battant"]) != pytest.approx(centre(avant["porte__battant"]), abs=0.02)
    porte["sens"] = None
    assert {b["id"]: b["contour"] for b in plan_habille(Logement.model_validate(lg))["briques"]} == {i: b["contour"] for i, b in avant.items()}
