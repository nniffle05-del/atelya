"""Mesure de la lumière du film (moteur/cinema/lumiere.py) sur des images fabriquées dont on connaît la réponse."""
import numpy as np

from moteur import photographe
from moteur.cinema import lumiere


def _image(fond=0.75, h=40, w=60):
    return np.full((h, w, 3), fond, float)


def test_fenetre_brulee_et_laiteuse():
    rvb = _image()
    dehors = np.zeros((40, 60), bool)
    dehors[5:25, 10:30] = True  # 400 pixels de dehors
    rvb[5:15, 10:30] = 1.0  # moitié blanc pur
    rvb[15:25, 10:30] = [0.95, 0.96, 0.97]  # moitié presque blanche (laiteuse)
    m = lumiere.mesurer_image(rvb, None, dehors)
    assert m["dehors_part"] == round(400 / 2400, 4)
    assert m["dehors_brule"] == 0.5
    assert m["dehors_blanc"] == 1.0
    assert m["dehors_couleur"] < 0.05


def test_dehors_bleu_garde_sa_couleur():
    rvb = _image()
    dehors = np.zeros((40, 60), bool)
    dehors[:10, :] = True
    rvb[:10, :] = [0.45, 0.62, 0.85]
    m = lumiere.mesurer_image(rvb, None, dehors)
    assert m["dehors_brule"] == 0 and m["dehors_blanc"] == 0
    assert m["dehors_couleur"] > 0.4


def test_murs_a_la_clarte_visee():
    """Des murs affichés à la valeur que donne la pellicule pour la clarté visée : écart nul."""
    visee = 0.9
    valeur = float(photographe.courbe_unreal(visee, **photographe.PELLICULE))
    rvb = _image(valeur)
    murs = np.ones((40, 60), bool)
    m = lumiere.mesurer_image(rvb, murs, None, visee)
    assert abs(m["murs_ecart_crans"]) < 0.02
    plus_sombre = lumiere.mesurer_image(_image(float(photographe.courbe_unreal(visee / 2, **photographe.PELLICULE))), murs,
                                        None, visee)
    assert abs(plus_sombre["murs_ecart_crans"] - 1.0) < 0.02  # deux fois moins de lumière = 1 cran trop sombre


def test_zones_sombres():
    rvb = _image()
    rvb[:4, :] = 0.02  # 10 % presque noir
    rvb[4:8, :] = 0.15  # 10 % sombre
    m = lumiere.mesurer_image(rvb)
    assert m["bouche"] == 0.1
    assert m["sombre"] == 0.2


def test_sauts_d_exposition():
    temps = [i * 0.25 for i in range(40)]  # 10 s
    calme = lumiere.sauts(temps, [0.1 * (t / 10) for t in temps])
    assert calme["max_crans"] < 0.05 and calme["moments"] == []
    marche = [0.0 if t < 5 else 1.0 for t in temps]  # +1 cran d'un coup à 5 s
    s = lumiere.sauts(temps, marche)
    assert s["max_crans"] == 1.0
    assert len(s["moments"]) == 1 and s["moments"][0]["crans"] == 1.0
    bref = [1.5 if 5 <= t < 5.5 else 0.0 for t in temps]  # une embrasure sombre 0,5 s : pas un saut d'exposition
    assert lumiere.sauts(temps, bref)["max_crans"] == 0.0
    assert lumiere.sauts(temps, bref, mediane_s=0)["max_crans"] == 1.5


def test_resumer_par_piece():
    mesures = []
    for i in range(48):
        piece = "sejour" if i < 24 else "chambre"
        ecart = 0.0 if piece == "sejour" else 0.8
        mesures.append({"image": i * 6, "piece": piece, "murs_ecart_crans": ecart, "dehors_part": 0.1,
                        "dehors_brule": 0.2, "dehors_blanc": 0.6, "dehors_couleur": 0.05, "dehors_detail_crans": 1.0,
                        "sombre": 0.0, "bouche": 0.0, "etendue_crans": 3.0})
    b = lumiere.resumer(mesures, 24)
    assert b["pieces"]["chambre"]["murs_ecart_crans"] == 0.8
    assert b["exposition"]["ecart_entre_pieces_crans"] == 0.8
    assert b["exposition"]["saut_max_crans_par_s"] == 0.8  # passage du séjour à la chambre en < 1 s
    assert b["fenetres"]["images_fenetre_laiteuse"] == 48
    assert b["exposition"]["murs_trop_sombres"] == 0.5 and b["exposition"]["murs_trop_clairs"] == 0.0


def test_comparer_avant_apres():
    avant = {"fenetres": {"part_du_dehors_blanc": 0.8, "couleur_du_dehors": 0.05},
             "exposition": {"murs_ecart_median_crans": -0.3}}
    apres = {"fenetres": {"part_du_dehors_blanc": 0.3, "couleur_du_dehors": 0.05},
             "exposition": {"murs_ecart_median_crans": 0.5}}
    v = {l["chiffre"]: l["verdict"] for l in lumiere.comparer(avant, apres)}
    assert v["Fenêtres : part du dehors presque blanc (laiteux)"] == "mieux"
    assert v["Fenêtres : couleur gardée dans la vue (0..1)"] == "="
    assert v["Murs : écart médian à la visée (crans)"] == "moins bien"


def test_exposition_locale_pivot_sur_les_murs():
    assert photographe.exposition_locale(0.9) is None  # écartée par défaut (fenêtres sans vue réelle, 12/11/2026)
    r = photographe.exposition_locale(0.9, 0.5)
    assert r["pivot_crans"] == round(__import__("math").log2(0.9 / 0.18), 3)  # ~2,32 crans au-dessus du gris moyen
    assert r["hautes_lumieres"] == 0.5
