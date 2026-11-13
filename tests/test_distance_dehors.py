"""Distance des immeubles d'en face mesurée seule sur les photos (moteur/distance_dehors.py, cinématique étape 6)."""
import numpy as np

from moteur import distance_dehors as dd
from moteur import vue_dehors as vd


def _logement():
    """Une pièce 5 × 4 m, une grande porte-fenêtre au sud (mur y = 0, dehors vers -y)."""
    return {
        "hauteur_sous_plafond": 2.5,
        "murs": [
            {"id": "S", "debut": [0, 0], "fin": [5, 0], "epaisseur": 0.2},
            {"id": "E", "debut": [5, 0], "fin": [5, 4], "epaisseur": 0.2},
            {"id": "N", "debut": [5, 4], "fin": [0, 4], "epaisseur": 0.2},
            {"id": "O", "debut": [0, 4], "fin": [0, 0], "epaisseur": 0.2},
        ],
        "ouvertures": [{"id": "PF", "type": "porte_fenetre", "mur": "S", "position": 1.0, "largeur": 3.0,
                        "hauteur": 2.15, "allege": 0.0}],
        "pieces": [{"id": "a", "contour": [[0, 0], [5, 0], [5, 4], [0, 4]]}],
    }


CAM = [2.5, 1.8, 1.3, -90.0, 0.0, 600.0, 600.0, 400.0]  # face au sud, à 1,8 m de la vitre, photo 1200 × 800


def _photo(distance: float | None, graine: int = 0) -> np.ndarray:
    """La photo d'une pièce blanche ; par la porte-fenêtre, une façade à `distance` m de notre mur (fenêtres sombres de
    0,9 à 2,4 m de chaque étage de 3 m, une tous les 2,5 m) ou un ciel blanc (distance None)."""
    rng = np.random.default_rng(graine)
    h, w = 800, 1200
    img = np.full((h, w, 3), 185.0)
    log = _logement()
    vue, _ = vd.masque_fenetres(CAM, (w, h), vd.ouvertures_vitrees(log), vd.murs_et_trous(log))
    vs, us = np.nonzero(vue)
    d = vd._rayons(CAM, us.astype(float), vs.astype(float))
    if distance is None:
        img[vs, us] = 245.0
    else:
        y_plan = -(0.1 + distance)
        t = (y_plan - CAM[1]) / d[:, 1]
        x = CAM[0] + t * d[:, 0]
        z = CAM[2] + t * d[:, 2]
        dans_etage = np.mod(z, 3.0)
        fenetre = (dans_etage > 0.9) & (dans_etage < 2.4) & (np.mod(x + 0.3, 2.5) < 1.2)
        img[vs, us] = np.where(fenetre, 70.0, 215.0)[:, None]
    img += rng.normal(0, 3, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def _mesure(distance):
    log = _logement()
    return dd.mesurer_logement(log, [{"nom": "p", "image": _photo(distance), "cam": CAM, "qualite": "bonne"}])["facade-sud"]


def test_facade_a_20_m_retrouvee():
    r = _mesure(20.0)
    assert r["statut"] == "mesuree"
    assert abs(r["distance_m"] - 20.0) / 20.0 < 0.06


def test_facade_a_45_m_retrouvee():
    r = _mesure(45.0)
    assert r["statut"] == "mesuree"
    assert abs(r["distance_m"] - 45.0) / 45.0 < 0.06


def test_ciel_vide_non_mesure():
    r = _mesure(None)
    assert r["statut"] == "non_mesuree" and r["distance_m"] is None


def _m(c0, d, accord=0.4):
    return {"colonne0": c0, "colonne1": c0 + 120, "distance_m": d, "accord": accord, "pixels": 5000}


def test_confirmation_par_deux_bandes_separees():
    # deux bandes qui se recouvrent ne se confirment pas (mêmes pixels pour moitié) ; deux bandes séparées oui
    assert dd.confirmees([_m(0, 30.0), _m(60, 30.5)]) == []
    assert len(dd.confirmees([_m(0, 30.0), _m(180, 31.0)])) == 2
    assert dd.confirmees([_m(0, 30.0), _m(180, 40.0)]) == []  # pas d'accord (33 % d'écart)


def test_choisir_moyenne_et_bornes():
    r = dd.choisir({"a": {"mesures": [_m(0, 30.0), _m(180, 30.0)], "qualite": "bonne"}})
    assert r["statut"] == "mesuree" and abs(r["distance_m"] - 30.0) < 0.1
    loin = dd.choisir({"a": {"mesures": [_m(0, 110.0), _m(180, 112.0)], "qualite": "bonne"}})
    assert loin["distance_m"] == dd.BORNES_M[1] and loin["brute_m"] > 100
    seul = dd.choisir({"a": {"mesures": [_m(0, 30.0)], "qualite": "bonne"}})
    assert seul["statut"] == "non_mesuree"
