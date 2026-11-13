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


def _m(c0, d, accord=0.4, u0=0.0, u1=5.0):
    return {"colonne0": c0, "colonne1": c0 + 120, "distance_m": d, "accord": accord, "pixels": 5000, "u0": u0, "u1": u1}


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


def test_second_avis_d_une_autre_photo():
    # une mesure seule dans sa photo, confirmée par une autre photo (second_avis) : retenue
    m = _m(0, 30.0)
    m["confirmee_par"] = "b"
    r = dd.choisir({"a": {"mesures": [m], "qualite": "bonne"}})
    assert r["statut"] == "mesuree" and r["marches"][0]["photos"] == ["a", "b"]


def test_second_avis_retrouve_la_facade_vue_d_ailleurs():
    """La même façade (20 m) photographiée de deux endroits : une bande de la 1re photo est confirmée par la 2e."""
    log = _logement()
    toile = next(t for t in vd.facades(log, 35.0) if t["id"] == "facade-sud")
    ouv, murs = vd.ouvertures_vitrees(log), vd.murs_et_trous(log)
    cam_b = [1.6, 2.0, 1.3, -80.0, 0.0, 600.0, 600.0, 400.0]
    global CAM
    img_a = _photo(20.0)
    sauve, CAM = CAM, cam_b
    try:
        img_b = _photo(20.0, graine=1)
    finally:
        CAM = sauve
    ms = dd.mesurer_photo(img_a, CAM, toile, ouv, murs)
    ctx_b = dd.preparer_vue(img_b, cam_b, toile, ouv, murs)
    avis = [dd.second_avis(m, ctx_b) for m in ms]
    assert any(a is not None and abs(a["distance_m"] - 20.0) < 2.0 for a in avis)
    # à une fausse distance (le double), la 2e photo ne confirme pas
    faux = dict(ms[0], distance_m=40.0)
    assert dd.second_avis(faux, ctx_b) is None


def test_marches_deux_distances_sur_un_cote():
    r = dd.choisir({"a": {"mesures": [_m(0, 24.0, u0=-22, u1=-15), _m(200, 24.5, u0=-20, u1=-14)], "qualite": "bonne"},
                    "b": {"mesures": [_m(0, 44.0, u0=0, u1=9), _m(200, 45.0, u0=2, u1=10)], "qualite": "bonne"}})
    assert [m["distance_m"] for m in r["marches"]] == [24.2, 44.5]
    assert r["marches"][0]["u1"] == -14 and r["marches"][1]["u0"] == 0
