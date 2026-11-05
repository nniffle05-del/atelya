"""Tests du maillon coloriage → logement.json (moteur/coloriage.py)."""

import numpy as np
import pytest

from moteur.banc_coloriage import comparer
from moteur.coloriage import MUR, PORTE, FENETRE, estimer_rotation, lire_coloriage, redresser
from moteur.logement import Logement

S = 100  # pixels par mètre


def px(m: float) -> int:
    return int(round(m * S))


def coloriage_t2() -> np.ndarray:
    """Un T2 dessiné à la main : intérieur 6,00 × 4,00 m, murs extérieurs de 20 cm,
    une cloison de 10 cm à x = 3,00 m, une porte dans la cloison, une fenêtre au sud."""
    c = np.zeros((px(6), px(8)), np.uint8)
    o = (px(1), px(1))  # coin nord-ouest du mur extérieur, en pixels (x, y)

    def rect(x0, y0, x1, y1, v):  # en mètres, repère du plan (y vers le nord, origine sud-ouest intérieur)
        c[o[1] + px(4.2 - y1):o[1] + px(4.2 - y0), o[0] + px(x0 + 0.2):o[0] + px(x1 + 0.2)] = v

    rect(-0.2, -0.2, 6.2, 4.2, MUR)
    rect(0, 0, 2.95, 4, 5)  # séjour
    rect(3.05, 0, 6, 4, 7)  # chambre
    rect(1.0, -0.2, 2.2, 0, FENETRE)
    rect(2.95, 1.0, 3.05, 1.9, PORTE)
    return c


def test_lit_les_murs_ouvertures_et_pieces():
    log, details = lire_coloriage(coloriage_t2(), S)
    Logement.model_validate(log)
    assert abs(details["angle_deg"]) < 0.1
    murs = sorted(log["murs"], key=lambda m: m["epaisseur"])
    cloison = murs[0]
    assert cloison["epaisseur"] == pytest.approx(0.10, abs=0.01)
    assert cloison["debut"][0] == pytest.approx(3.0, abs=0.02)
    assert len(log["murs"]) == 5  # 4 murs extérieurs + la cloison
    types = sorted(o["type"] for o in log["ouvertures"])
    assert types == ["fenetre", "porte"]
    fen = next(o for o in log["ouvertures"] if o["type"] == "fenetre")
    assert fen["largeur"] == pytest.approx(1.2, abs=0.03)
    assert sorted(details["types_pieces"].values()) == ["chambre", "sejour"]
    surfaces = sorted(round(Logement.model_validate(log).pieces[i].surface_calculee, 1) for i in range(2))
    assert surfaces == pytest.approx([11.8, 11.8], abs=0.15)


def test_plan_penche_est_redresse():
    c = coloriage_t2()
    penche = redresser(c, -3.0)
    angle = estimer_rotation((penche >= MUR) & (penche <= 4))
    assert angle == pytest.approx(3.0, abs=0.1)  # tourner de +3° le remet droit
    log, _ = lire_coloriage(penche, S)
    assert len(log["murs"]) == 5


def test_taches_hors_du_logement_ignorees():
    c = coloriage_t2()
    c[10:30, 10:120] = MUR  # une barre d'échelle dans la marge
    log, _ = lire_coloriage(c, S)
    assert len(log["murs"]) == 5


def test_comparaison_parfaite_avec_soi_meme():
    log, d = lire_coloriage(coloriage_t2(), S)
    r = comparer(log, log, {}, {})
    assert all(m["juste"] for m in r["murs"])
    assert all(o["juste"] for o in r["ouvertures"])
    assert r["hors_tout"] == 0


def test_coin_un_peu_arrondi_reste_un_angle_droit():
    """A3 (0.4.1) : un coloriage bruité qui arrondit un peu un coin de mur (rayon ~30 cm) ne crée pas de mur
    courbe fait de douze bouts de 4 cm : c'est un angle droit (les vrais angles arrondis font 0,8 m et plus)."""
    from pathlib import Path
    from PIL import Image
    col = np.array(Image.open(Path(__file__).parent / "donnees" / "coin-arrondi-bruite.png"), np.uint8)
    _, d = lire_coloriage(col, 44.956)
    assert d["murs_libres"] == []


def test_deux_ouvertures_collees_de_types_differents_n_en_font_qu_une():
    """fr-006 : une fenêtre de 1,20 m lue en fenêtre de 0,33 m + porte-fenêtre de 0,84 m → une seule, du type de la plus large."""
    from moteur.coloriage import _fusionner_ouvertures_voisines

    def o(id_, type_, mur, pos, larg):
        return {"id": id_, "type": type_, "mur": mur, "position": pos, "largeur": larg, "hauteur": 2.15 if type_ != "fenetre" else 1.25,
                "allege": 0.0 if type_ != "fenetre" else 0.95, "statut": "estime", "source": "atelya"}

    lues = [o("O1", "fenetre", "M20", 2.071, 0.327), o("O2", "porte_fenetre", "M20", 2.40, 0.84), o("O3", "porte", "M20", 4.0, 0.8), o("O4", "porte", "M3", 0.5, 0.8)]
    sortie = _fusionner_ouvertures_voisines(lues)
    assert [(x["id"], x["type"], x["mur"], round(x["largeur"], 2)) for x in sortie] == [("O1", "porte_fenetre", "M20", 1.17), ("O2", "porte", "M20", 0.8), ("O3", "porte", "M3", 0.8)]
    assert sortie[0]["allege"] == 0.0 and sortie[0]["position"] == 2.071
