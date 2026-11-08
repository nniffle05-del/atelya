"""Le traducteur de la lecture de Claude (moteur.traduire_claude 0.1.0) sur un plan dessiné exprès : deux pièces de 3,5 × 4 m
et 2,5 × 4 m (intérieur 6 × 4 m), murs de 20 cm, cloison de 10 cm, une porte, une fenêtre, deux cotes et deux surfaces écrites,
à 100 px/m. La fiche imite une lecture de Claude : bonnes informations, positions décalées de 3 px."""
from __future__ import annotations

import copy

import cv2
import numpy as np
import pytest

from moteur.doutes import PLUSIEURS_NIVEAUX, _surface
from moteur.lecture_claude import controler_fiche
from moteur.lecture_complete import PlanSource
from moteur.preparer_verification import projeter, verification_du_plan
from moteur.traduire_claude import traduire

S = 100
X0, Y0 = 150, 150


def X(m: float) -> int:
    return int(round(X0 + m * S))


def Y(m: float) -> int:
    return int(round(Y0 + (4 - m) * S))


YC, XC = Y(0) + 60, X(0) - 70  # lignes de cote


def _dessin(cotes: bool = True) -> np.ndarray:
    img = np.full((700, 900, 3), 255, np.uint8)
    cv2.rectangle(img, (X(0) - 20, Y(4) - 20), (X(6) + 20, Y(0) + 20), (0, 0, 0), -1)
    cv2.rectangle(img, (X(0), Y(4)), (X(6), Y(0)), (255, 255, 255), -1)
    cv2.rectangle(img, (X(3.5) - 5, Y(4)), (X(3.5) + 5, Y(0)), (0, 0, 0), -1)
    cv2.rectangle(img, (X(3.5) - 6, Y(1.9)), (X(3.5) + 6, Y(1.0)), (255, 255, 255), -1)  # porte
    cv2.rectangle(img, (X(1), Y(4) - 21), (X(2.2), Y(4) - 1), (255, 255, 255), -1)  # fenêtre
    cv2.line(img, (X(1), Y(4) - 10), (X(2.2), Y(4) - 10), (0, 0, 0), 1)
    if cotes:
        cv2.line(img, (X(0), YC), (X(6), YC), (0, 0, 0), 1)
        for x in (X(0), X(6)):
            cv2.line(img, (x - 6, YC + 6), (x + 6, YC - 6), (0, 0, 0), 2)
            cv2.line(img, (x, YC - 15), (x, YC + 15), (0, 0, 0), 1)
        cv2.putText(img, "6,00", (X(3) - 30, YC - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.line(img, (XC, Y(4)), (XC, Y(0)), (0, 0, 0), 1)
        for y in (Y(4), Y(0)):
            cv2.line(img, (XC - 6, y + 6), (XC + 6, y - 6), (0, 0, 0), 2)
            cv2.line(img, (XC - 15, y), (XC + 15, y), (0, 0, 0), 1)
        cv2.putText(img, "4,00", (XC - 60, Y(2) + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(img, "14,0 m2", (X(1.2), Y(2.5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        cv2.putText(img, "10,0 m2", (X(4.2), Y(2.5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@pytest.fixture(scope="module")
def plan():
    return PlanSource("studio", _dessin())


@pytest.fixture(scope="module")
def plan_sans_cotes():
    return PlanSource("studio", _dessin(cotes=False))


def _fiche(prop: float | None = 100.0, d: int = 3, k: float = 1.0) -> dict:
    """La fiche de Claude ; `k` : facteur de l'image envoyée (0,5 = image deux fois plus petite)."""
    def p(v):
        return round(v * k, 1)

    def seg(a, b, c, e):
        return [p(a), p(b), p(c), p(e)]

    return {
        "schema": "lecture-claude/0.1", "image": {"nom": "studio.png", "largeur": round(900 * k), "hauteur": round(700 * k)},
        "murs": [
            {"id": "M1", "axe": seg(X(0) - 20, Y(0) + 10 + d, X(6) + 20, Y(0) + 10 + d), "epaisseur_px": p(20)},
            {"id": "M2", "axe": seg(X(0) - 20, Y(4) - 10 - d, X(6) + 20, Y(4) - 10 - d), "epaisseur_px": p(20)},
            {"id": "M3", "axe": seg(X(0) - 10 + d, Y(4) - 20, X(0) - 10 + d, Y(0) + 20), "epaisseur_px": p(20)},
            {"id": "M4", "axe": seg(X(6) + 10 - d, Y(4) - 20, X(6) + 10 - d, Y(0) + 20), "epaisseur_px": p(20)},
            {"id": "M5", "axe": seg(X(3.5) + d, Y(4), X(3.5) + d, Y(0)), "epaisseur_px": p(10)}],
        "ouvertures": [
            {"id": "O1", "type": "porte", "bords": seg(X(3.5), Y(1.0), X(3.5), Y(1.9)), "mur": "M5"},
            {"id": "O2", "type": "fenetre", "bords": seg(X(1), Y(4) - 10, X(2.2), Y(4) - 10), "mur": "M2"}],
        "pieces": [{"id": "P1", "nom": "Séjour", "type": "sejour", "point": [p(X(1.5)), p(Y(1.5))]},
                   {"id": "P2", "nom": "Chambre", "type": "chambre", "point": [p(X(5)), p(Y(1.5))]}],
        "cotes": [
            {"texte": "6,00", "valeur_m": 6.0, "cadre": seg(X(3) - 30, YC - 28, X(3) + 30, YC - 6),
             "bouts": [[p(X(0)), p(YC)], [p(X(6)), p(YC)]]},
            {"texte": "4,00", "valeur_m": 4.0, "cadre": seg(XC - 60, Y(2) - 12, XC - 5, Y(2) + 10),
             "bouts": [[p(XC), p(Y(4))], [p(XC), p(Y(0))]]}],
        "surfaces": [
            {"texte": "14,0 m2", "valeur_m2": 14.0, "cadre": seg(X(1.2), Y(2.5) - 18, X(1.2) + 90, Y(2.5) + 4), "piece": "P1"},
            {"texte": "10,0 m2", "valeur_m2": 10.0, "cadre": seg(X(4.2), Y(2.5) - 18, X(4.2) + 90, Y(2.5) + 4), "piece": "P2"}],
        "echelle_proposee": {"px_par_m": p(prop) if prop else None, "source": "cotes" if prop else "aucune"},
        "doutes": [{"raison": "fenêtre peu lisible", "gravite": "faible", "element": "O2"}],
    }


def _lire(source, d, facteur=1.0):
    W, H = d["image"]["largeur"], d["image"]["hauteur"]
    return traduire(source, controler_fiche(d, (W, H)), facteur)


def _codes(plan_lu):
    return [d["code"] for d in plan_lu.gardee.examen["doutes"]]


def test_deux_cles_d_accord_lecture_juste(plan):
    lu = _lire(plan, _fiche())
    g = lu.gardee
    assert g.echelle["etat"] == "lue" and lu.decision == "lu"
    assert "confirmée par l'échelle de la lecture de Claude" in g.echelle["source"]
    assert g.infos["recalage_px_moyen"] == pytest.approx(3.0, abs=0.6)  # les 3 px de Claude rattrapés
    murs = {m["id"]: m for m in g.logement["murs"]}
    assert murs["M1"]["debut"][1] == pytest.approx(-0.10, abs=0.01) and murs["M2"]["debut"][1] == pytest.approx(4.10, abs=0.01)
    assert murs["M5"]["debut"][0] == pytest.approx(3.5, abs=0.015) and murs["M1"]["epaisseur"] == pytest.approx(0.20, abs=0.01)
    ouv = {o["type"]: o for o in g.logement["ouvertures"]}
    assert ouv["porte"]["mur"] == "M5" and ouv["porte"]["position"] == pytest.approx(1.0, abs=0.02)
    assert ouv["porte"]["largeur"] == pytest.approx(0.9, abs=0.02)
    assert ouv["fenetre"]["mur"] == "M2" and ouv["fenetre"]["largeur"] == pytest.approx(1.2, abs=0.02)
    surfaces = {p["nom"]: _surface(p["contour"]) for p in g.logement["pieces"]}
    assert surfaces["Séjour"] == pytest.approx(13.8, rel=0.02) and surfaces["Chambre"] == pytest.approx(9.8, rel=0.02)
    assert _codes(lu) == ["claude"]  # seul le doute faible de Claude


def test_ecran_dessine_la_lecture_sur_le_plan(plan):
    lu = _lire(plan, _fiche())
    v = verification_du_plan(lu, "studio.png")
    M = np.array(v["calage"]["matrice"])
    for m in lu.gardee.logement["murs"]:
        for bout in (m["debut"], m["fin"]):
            u, w = projeter(M, *bout)
            assert plan.image[min(int(w), 699), min(int(u), 899)].max() < 128  # chaque bout de mur tombe sur l'encre
    assert v["lecture"]["modele"] == "claude" and v["echelle"]["etat"] == "lue"
    doute = next(d for d in v["doutes"] if d["code"] == "claude")
    assert doute["element"] == "O2" and doute["gravite"] == "faible"


def test_deux_cles_en_desaccord(plan):
    lu = _lire(plan, _fiche(prop=120.0))
    assert lu.gardee.echelle["etat"] == "a_verifier" and lu.decision == "a_verifier"
    d = lu.gardee.examen["doutes"][0]
    assert d["code"] == "echelle_desaccord" and d["gravite"] == "fort" and "20 %" in d["raison"]
    surfaces = sorted(_surface(p["contour"]) for p in lu.gardee.logement["pieces"])
    assert surfaces[1] == pytest.approx(13.8, rel=0.02)  # le brouillon garde l'échelle retrouvée sur le dessin


def test_sans_cle_d_atelya_brouillon_a_verifier(plan_sans_cotes):
    d = _fiche()
    d["surfaces"] = []  # (les surfaces suffiraient à notre lecteur : elles se comparent aux pièces, sans marques à retrouver)
    lu = _lire(plan_sans_cotes, d)  # cotes lues par Claude, mais absentes du dessin
    g = lu.gardee
    assert g.echelle["etat"] == "a_verifier" and lu.decision == "a_verifier"
    assert "tirée de 2 cotes lues par Claude" in g.examen["doutes"][0]["raison"]
    assert sorted(_surface(p["contour"]) for p in g.logement["pieces"])[1] == pytest.approx(13.8, rel=0.02)
    d["cotes"] = []
    lu = _lire(plan_sans_cotes, d)  # ni cotes ni dessin : l'échelle proposée par Claude, à vérifier
    assert lu.gardee.echelle["etat"] == "a_verifier" and "proposée par la lecture de Claude" in lu.gardee.examen["doutes"][0]["raison"]


def test_image_envoyee_reduite(plan):
    lu = _lire(plan, _fiche(k=0.5), facteur=0.5)
    assert lu.gardee.echelle["etat"] == "lue"
    surfaces = sorted(_surface(p["contour"]) for p in lu.gardee.logement["pieces"])
    assert surfaces == pytest.approx([9.8, 13.8], rel=0.02)


def test_piece_non_fermee(plan):
    d = _fiche()
    d["murs"] = [m for m in d["murs"] if m["id"] != "M4"]  # mur est oublié : la chambre fuit vers le bord
    lu = _lire(plan, d)
    doute = next(x for x in lu.gardee.examen["doutes"] if x["code"] == "piece_ouverte")
    assert doute["gravite"] == "fort" and "Chambre" in doute["raison"]
    assert [p["nom"] for p in lu.gardee.logement["pieces"]] == ["Séjour"]
    d["pieces"][1]["contour"] = [[X(3.55), Y(4)], [X(6), Y(4)], [X(6), Y(0)], [X(3.55), Y(0)]]
    lu = _lire(plan, d)  # avec le contour de Claude : la pièce est gardée, doute faible
    doute = next(x for x in lu.gardee.examen["doutes"] if x["code"] == "piece_ouverte")
    assert doute["gravite"] == "faible" and len(lu.gardee.logement["pieces"]) == 2


def test_pieces_sans_mur_entre_elles_reunies(plan):
    d = _fiche()
    d["murs"] = [m for m in d["murs"] if m["id"] != "M5"]
    d["ouvertures"] = [o for o in d["ouvertures"] if o["id"] != "O1"]
    lu = _lire(plan, d)
    assert "pieces_reunies" in _codes(lu) and len(lu.gardee.logement["pieces"]) == 1


def test_ouverture_hors_mur(plan):
    d = _fiche()
    d["ouvertures"].append({"id": "O3", "type": "porte", "bords": [X(1), Y(2), X(1.9), Y(2)]})  # au milieu du séjour
    lu = _lire(plan, d)
    assert "ouverture_hors_mur" in _codes(lu) and len(lu.gardee.logement["ouvertures"]) == 2


def test_doutes_de_la_fiche_et_plusieurs_niveaux(plan):
    d = _fiche()
    d["cotes"][0]["valeur_m"] = 6.6  # « 6,00 » mal recopié
    d["autres_niveaux"] = [{"cadre": [700, 50, 880, 200], "nom": "Étage"}]
    lu = _lire(plan, d)
    codes = _codes(lu)
    assert codes[0] == PLUSIEURS_NIVEAUX and "cote_mal_recopiee" in codes and lu.decision == "a_verifier"
    assert lu.gardee.examen["doutes"][0]["blocs_px"] == [[700.0, 50.0, 180.0, 150.0]]


def test_fiche_refusee_pas_d_ecran(plan):
    d = _fiche()
    d["pieces"][0]["type"] = "garage"
    lu = _lire(plan, d)
    assert lu.decision == "refuse" and lu.gardee.logement is None
    assert verification_du_plan(lu) is None


def test_fiche_non_modifiee(plan):
    d = _fiche()
    avant = copy.deepcopy(d)
    _lire(plan, d)
    assert d == avant


# ---------------------------------------------------------------- doutes propres à la lecture de Claude (moteur.doutes_claude)

def _doute(plan_lu, code):
    return next((d for d in plan_lu.gardee.examen["doutes"] if d["code"] == code), None)


def test_texte_invente_sur_l_image(plan):
    d = _fiche()
    d["surfaces"].append({"texte": "8,0 m2", "valeur_m2": 8.0, "cadre": [780, 40, 870, 65]})  # coin vide de l'image
    doute = _doute(_lire(plan, d), "texte_introuvable")
    assert doute["gravite"] == "fort" and doute["zone_px"] == [780.0, 40.0, 90.0, 25.0]


def test_texte_invente_dans_un_pdf():
    from moteur.lecture_cotes import TexteLu

    def boite(x0, y0, x1, y1):
        return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)

    textes = [TexteLu("6,00", boite(X(3) - 30, YC - 28, X(3) + 30, YC - 6), 1.0),
              TexteLu("4,00", boite(XC - 60, Y(2) - 12, XC - 5, Y(2) + 10), 1.0)]
    source = PlanSource("studio", _dessin(), textes=textes)
    d = _fiche()
    d["surfaces"] = []
    d["cotes"][1]["texte"], d["cotes"][1]["valeur_m"] = "4,10", 4.1  # le PDF dit « 4,00 »
    doute = _doute(_lire(source, d), "texte_introuvable")
    assert doute["gravite"] == "fort" and "4,00" in doute["raison"]


def test_ocr_voit_un_autre_nombre(plan):
    d = _fiche()
    d["cotes"][0].update(texte="6,50", valeur_m=6.5)  # le dessin dit « 6,00 »
    lu = _lire(plan, d)
    doute = _doute(lu, "texte_different")
    assert doute["gravite"] == "faible" and "6,00" in doute["raison"]
    assert lu.decision == "a_verifier"


def test_cote_contre_le_dessin(plan):
    d = _fiche()
    d["cotes"][1]["bouts"] = [[XC, Y(4)], [XC, Y(1)]]  # « 4,00 » posé sur 3 m de dessin
    doute = _doute(_lire(plan, d), "cote_contre_dessin")
    assert doute["gravite"] == "fort" and "3.00 m" in doute["raison"] and "-25 %" in doute["raison"]


def test_surface_contre_la_piece(plan):
    d = _fiche()
    d["murs"] = [m for m in d["murs"] if m["id"] != "M5"]  # cloison oubliée : une seule pièce de 24 m²
    d["ouvertures"] = d["ouvertures"][1:]
    lu = _lire(plan, d)
    doute = _doute(lu, "surface_contre_piece")
    assert doute["gravite"] == "fort" and doute["element"] == "sejour_1" and "14 m²" in doute["raison"]
    assert _doute(lu, "pieces_reunies")["raison"].startswith("Chambre et Séjour")


def test_pas_de_controle_des_cotes_sans_echelle_lue(plan):
    lu = _lire(plan, _fiche(prop=120.0))  # échelle à vérifier : les cotes ne sont pas accusées une à une
    assert _doute(lu, "cote_contre_dessin") is None and _doute(lu, "surface_contre_piece") is None


def test_doutes_designent_les_elements_du_logement(plan):
    d = _fiche()
    d["pieces"][1]["contour"] = [[X(3.55), Y(4)], [X(6), Y(4)], [X(6), Y(0)], [X(3.55), Y(0)]]
    d["murs"] = [m for m in d["murs"] if m["id"] != "M4"]
    lu = _lire(plan, d)
    ids = {e["id"] for genre in ("murs", "ouvertures", "pieces") for e in lu.gardee.logement[genre]}
    for doute in lu.gardee.examen["doutes"]:
        assert doute["element"] is None or doute["element"] in ids, doute
    assert _doute(lu, "piece_ouverte")["element"] == "chambre_1"


def test_cuisine_ouverte_deux_pieces_cote_a_cote_sans_superposition(plan):
    """B1 (fr-031) : deux pièces dans la même zone, chacune avec son contour lu → deux sols côte à côte, sans se recouvrir
    (avant, la première gardait toute la zone : deux sols au même endroit, rendus noirs par Blender)."""
    from moteur.controle_maquette import controler
    from moteur.geometrie import calculer_briques
    from moteur.logement import Logement

    d = _fiche()
    d["murs"] = [m for m in d["murs"] if m["id"] != "M5"]
    d["ouvertures"] = [o for o in d["ouvertures"] if o["id"] != "O1"]
    d["pieces"][0]["contour"] = [[X(0), Y(4)], [X(3.5), Y(4)], [X(3.5), Y(0)], [X(0), Y(0)]]
    d["pieces"][1]["contour"] = [[X(3.5), Y(4)], [X(6), Y(4)], [X(6), Y(0)], [X(3.5), Y(0)]]
    lu = _lire(plan, d)
    surfaces = sorted(_surface(p["contour"]) for p in lu.gardee.logement["pieces"])
    assert surfaces == pytest.approx([10.0, 14.0], rel=0.03)
    log = Logement.model_validate(lu.gardee.logement)
    r = controler(calculer_briques(log), log.hauteur_sous_plafond)
    # 4 m de frontière commune comptés dans les deux pièces sur un rang de cases de 4 mm = 0,016 m² (bruit de la mesure) ;
    # avant B1, c'était toute la cuisine (~7 m² sur fr-031).
    assert r["sols_superposes_m2"] <= 0.02 and r["sol"]["trous"] == 0
