"""Tests de l'étape A1 : les doutes d'Atelya (moteur/doutes.py)."""

import numpy as np

from moteur.coloriage import FENETRE, MUR, PORTE, lire_coloriage
from moteur.doutes import controles_bon_sens, examiner

S = 100  # pixels par mètre


def px(m: float) -> int:
    return int(round(m * S))


def coloriage_t2(porte: bool = True, fenetre_cloison: bool = False) -> np.ndarray:
    """T2 de 6,00 × 4,00 m, murs de 20 cm, cloison de 10 cm à x = 3 m (comme tests/test_coloriage.py)."""
    c = np.zeros((px(6), px(8)), np.uint8)
    o = (px(1), px(1))

    def rect(x0, y0, x1, y1, v):
        c[o[1] + px(4.2 - y1):o[1] + px(4.2 - y0), o[0] + px(x0 + 0.2):o[0] + px(x1 + 0.2)] = v

    rect(-0.2, -0.2, 6.2, 4.2, MUR)
    rect(0, 0, 2.95, 4, 5)  # séjour
    rect(3.05, 0, 6, 4, 7)  # chambre
    rect(1.0, -0.2, 2.2, 0, FENETRE)
    if porte:
        rect(2.95, 1.0, 3.05, 1.9, PORTE)
    if fenetre_cloison:
        rect(2.95, 2.5, 3.05, 3.5, FENETRE)
    return c


def codes(doutes, gravite="fort"):
    return sorted({d["code"] for d in doutes if d["gravite"] == gravite})


def test_plan_juste_rien_a_signaler():
    log, det = lire_coloriage(coloriage_t2(), S)
    ex = examiner(log, det)
    assert ex["decision"] == "lu", ex["doutes"]
    assert codes(ex["doutes"]) == []


def test_piece_sans_porte():
    log, det = lire_coloriage(coloriage_t2(porte=False), S)
    assert "sans_acces" in codes(controles_bon_sens(log, det["types_pieces"]))
    assert examiner(log, det)["decision"] == "a_verifier"


def test_fenetre_entre_deux_pieces():
    log, det = lire_coloriage(coloriage_t2(fenetre_cloison=True), S)
    assert "fenetre_interieure" in codes(controles_bon_sens(log, det["types_pieces"]))


def test_epaisseur_et_surface_improbables():
    log, det = lire_coloriage(coloriage_t2(), S)
    log["murs"][0]["epaisseur"] = 1.2
    log["pieces"][1]["contour"] = [[3.05, 0], [3.6, 0], [3.6, 1.0], [3.05, 1.0]]  # chambre de 0,55 m²
    c = codes(controles_bon_sens(log, det["types_pieces"]))
    assert "epaisseur" in c and "surface" in c


def test_refus():
    assert examiner(None, erreur="aucun mur trouvé")["decision"] == "refuse"
    log, det = lire_coloriage(coloriage_t2(), S)
    log["pieces"] = []
    assert examiner(log, det)["decision"] == "refuse"


def test_carte_des_doutes():
    col = coloriage_t2()
    log, det = lire_coloriage(col, S)
    assert "origine_px" in det
    calme = np.zeros(col.shape, np.uint8)
    assert examiner(log, det, carte=calme)["decision"] == "lu"
    # Atelya hésite sur toute la cloison : le mur de la cloison devient douteux.
    carte = calme.copy()
    carte[px(1.2):px(5.2), px(4.15):px(4.25)] = 255
    ex = examiner(log, det, carte=carte)
    cloison = min(log["murs"], key=lambda m: m["epaisseur"])["id"]
    assert any(d["code"] == "carte" and d["element"] == cloison and d["gravite"] == "fort" for d in ex["doutes"])
    # Une tache d'hésitation dans le séjour, où rien n'est lu : zone douteuse orpheline.
    carte = calme.copy()
    carte[px(2.4):px(3.1), px(2.0):px(2.7)] = 255  # 0,49 m²
    ex = examiner(log, det, carte=carte)
    z = [d for d in ex["doutes"] if d["code"] == "zone_douteuse"]
    assert z and ex["decision"] == "a_verifier"
    x0, y0, x1, y1 = z[0]["zone_m"]
    assert 0.6 <= x0 <= 1.1 and 1.8 <= y0 <= 2.5  # (2,0 m ; 2,5 m) image → repère du logement
