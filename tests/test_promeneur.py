"""Le promeneur (moteur/promeneur.py) : une balade continue praticable (jamais dans un mur ni un meuble), qui passe les portes
ouvertes des pièces visitées, laisse fermés placards et porte palière, et une exposition qui s'adapte en douceur."""
import math

import numpy as np
import pytest

from moteur import photographe as ph
from moteur import promeneur as pm
from moteur import realisateur as r


def _logement():
    # entrée (porte palière au nord), séjour à l'ouest avec fenêtre et canapé, chambre à l'est avec fenêtre, placard
    murs = [{"id": "Ms", "debut": [0, 0], "fin": [10, 0], "epaisseur": 0.2}, {"id": "Mn", "debut": [0, 6], "fin": [10, 6], "epaisseur": 0.2},
            {"id": "Mo", "debut": [0, 0], "fin": [0, 6], "epaisseur": 0.2}, {"id": "Me", "debut": [10, 0], "fin": [10, 6], "epaisseur": 0.2},
            {"id": "M1", "debut": [6, 0], "fin": [6, 6], "epaisseur": 0.1}, {"id": "M2", "debut": [0, 4], "fin": [6, 4], "epaisseur": 0.1},
            {"id": "M3", "debut": [8.8, 4.6], "fin": [10, 4.6], "epaisseur": 0.1}, {"id": "M4", "debut": [8.8, 4.6], "fin": [8.8, 6], "epaisseur": 0.1}]
    ouvertures = [{"id": "F1", "type": "fenetre", "mur": "Ms", "position": 2.0, "largeur": 2.0, "hauteur": 1.4, "allege": 0.9},
                  {"id": "F2", "type": "fenetre", "mur": "Ms", "position": 7.5, "largeur": 1.2, "hauteur": 1.4, "allege": 0.9},
                  {"id": "Pal", "type": "porte", "mur": "Mn", "position": 2.5, "largeur": 0.9, "hauteur": 2.0},
                  {"id": "P1", "type": "porte", "mur": "M2", "position": 4.0, "largeur": 0.8, "hauteur": 2.0},
                  {"id": "P2", "type": "porte", "mur": "M1", "position": 1.5, "largeur": 0.75, "hauteur": 2.0},
                  {"id": "P3", "type": "porte", "mur": "M4", "position": 0.3, "largeur": 0.6, "hauteur": 2.0}]
    pieces = [{"id": "entree_1", "contour": [[0, 4], [6, 4], [6, 6], [0, 6]]},
              {"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]]},
              {"id": "chambre_1", "contour": [[6, 0], [10, 0], [10, 4.6], [8.8, 4.6], [8.8, 6], [6, 6]]},
              {"id": "placard_1", "contour": [[8.8, 4.6], [10, 4.6], [10, 6], [8.8, 6]]}]
    meubles = [{"id": "canape", "position": [3.0, 2.0], "face": 0.0, "dimensions": [2.0, 0.9, 0.8]}]
    return {"murs": murs, "ouvertures": ouvertures, "pieces": pieces, "meubles": meubles}


def test_portes_ouvertes_comme_un_agent():
    log = _logement()
    assert pm.porte_palliere(log) == "Pal"
    portes = {p["id"]: p for p in pm.portes_ouvertes(log, {"sejour_1", "chambre_1"})}
    assert set(portes) == {"P1", "P2"}  # ni la porte palière, ni le placard
    assert portes["P1"]["vers"] == "sejour_1"  # le battant s'ouvre dans la pièce, pas dans l'entrée (circulation)
    assert abs(abs(portes["P1"]["angle_deg"]) - 90) < 1e-6


def test_balade_praticable_et_complete():
    log = _logement()
    b = pm.balade(log)
    carte = pm.Carte(log, pm.portes_ouvertes(log, {"sejour_1", "chambre_1"}))
    genres = [(e["genre"], e["piece"]) for e in b["etapes"]]
    assert genres[0] == ("depart", "entree_1")
    assert ("point_de_vue", "sejour_1") in genres and ("point_de_vue", "chambre_1") in genres
    assert "placard_1" not in [e["piece"] for e in b["etapes"]]
    for x, y, z, cap, tangage in b["trajet"]["points"]:  # jamais dans un mur, un meuble ou un battant
        i, j = carte.case((x, y))
        assert carte.distance[i, j] >= pm.MARGE_M * 0.85
    # une marche fluide : pas de saut de plus de 1 m/s entre deux clés, la tête tourne doucement
    pts = np.array(b["trajet"]["points"])
    dt = pm.CLE_IMAGES / pm.IPS
    assert np.max(np.linalg.norm(np.diff(pts[:, :2], axis=0), axis=1)) / dt < 1.0
    tours = np.abs((np.diff(pts[:, 3]) + 180) % 360 - 180) / dt
    assert np.max(tours) <= pm.ROTATION_MAX + 0.1  # caps arrondis au centième
    assert b["trajet"]["images"] == (len(pts) - 1) * pm.CLE_IMAGES + 1


def test_exposition_en_marchant():
    images = list(range(0, 24 * 20, 24))  # 20 s d'essais, un par seconde
    voulues = [-8.0] * 10 + [-12.0] * 10  # on passe d'une pièce sombre à une pièce au soleil
    voulues[3] = None  # un essai sans murs vus
    cles = ph.exposition_en_marchant(images, voulues)
    expos = [c[1] for c in cles]
    assert expos[0] == pytest.approx(-8.0, abs=0.05) and expos[-1] == pytest.approx(-12.0, abs=0.05)
    assert max(abs(a - b) for a, b in zip(expos, expos[1:])) <= ph.ADAPTATION_MAX_CRAN_S + 1e-6  # adaptation bornée
    assert all(ph.EXPOSITION_UNREAL_BORNES[0] <= e <= ph.EXPOSITION_UNREAL_BORNES[1] for e in expos)
    with pytest.raises(ValueError):
        ph.exposition_en_marchant([0, 24], [None, None])
    # une embrasure sombre frôlée 0,5 s (2 essais à +2 crans) ne fait pas bouger l'exposition
    images = list(range(0, 24 * 10, 6))
    voulues = [-10.0] * len(images)
    voulues[20] = voulues[21] = -8.0
    expos = [c[1] for c in ph.exposition_en_marchant(images, voulues)]
    assert max(expos) == pytest.approx(-10.0, abs=0.01)


def test_preparation_unreal_balade():
    from pathlib import Path
    texte = (Path(__file__).resolve().parents[1] / "moteur" / "unreal" / "preparer_cinematique.py").read_text(encoding="utf-8")
    assert "def ouvrir_portes(" in texte and "refermer_portes()" in texte  # portes rouvertes / refermées sans cumul
    assert '"Settings.AutoExposureBias"' in texte  # exposition en clés sur la séquence
    assert math.isclose(pm.MARGE_M, 0.20)


def test_camera_volante_douce():
    """Le vol : une courbe lisse, jamais dans un obstacle, accélérations et rotations douces, regard qui voit loin."""
    log = _logement()
    v = pm.vol(log)
    pts = np.array(v["trajet"]["points"])
    dt = 2 / pm.IPS
    carte = pm.Carte(log, pm.portes_ouvertes(log, {"sejour_1", "chambre_1"}), hauteur_camera=pm.VOL_HAUTEUR_M)
    for x, y, *_ in pts:  # la finition dans le temps rapproche de quelques cm ; limite réelle : plan de coupe d'Unreal à 10 cm
        i, j = carte.case((x, y))
        assert carte.distance[i, j] >= pm.MARGE_M * 0.7
    vitesse = np.linalg.norm(np.diff(pts[:, :2], axis=0), axis=1) / dt
    assert vitesse.max() <= pm.VOL_VITESSE + 0.05
    rotation = np.abs(np.diff(pts[:, 3])) / dt
    assert rotation.max() <= pm.VOL_ROTATION_PIVOT + 3  # 30 °/s en vol, jusqu'à 60 °/s à l'arrêt (pivot)
    assert pm.VOL_HAUTEUR_M - 0.05 <= pts[0][2] <= pm.VOL_HAUTEUR_MAX_M and v["trajet"]["vol"] is True
    assert ("point_de_vue", "sejour_1") in [(e["genre"], e["piece"]) for e in v["etapes"]]


def test_travelling_sans_recul_ni_secousse():
    """Le vol ne recule jamais par rapport à son regard, et reste doux (accélération bornée, rotation bornée)."""
    log = _logement()
    pts = np.array(pm.vol(log)["trajet"]["points"])
    dt = 2 / pm.IPS
    vit = np.diff(pts[:, :2], axis=0) / dt
    v = np.linalg.norm(vit, axis=1)
    mouvement = np.degrees(np.arctan2(vit[:, 1], vit[:, 0]))
    ecart = np.abs((pts[:-1, 3] - mouvement + 180) % 360 - 180)
    assert (ecart[v > 0.1] > 100).mean() < 0.02  # la caméra avance là où elle regarde
    acc = np.linalg.norm(np.diff(vit, axis=0) / dt, axis=1)
    assert np.percentile(acc, 95) < 2.0


def test_survol_des_meubles_bas():
    """La caméra volante survole un canapé (0,8 m) mais contourne une armoire (2 m) ; sa hauteur reste sous le plafond."""
    log = _logement()
    log["meubles"].append({"id": "armoire", "position": [1.0, 1.0], "face": 0.0, "dimensions": [1.0, 0.6, 2.0]})
    log["hauteur_sous_plafond"] = 2.5
    portes = pm.portes_ouvertes(log, {"sejour_1", "chambre_1"})
    a_pied, en_vol = pm.Carte(log, portes), pm.Carte(log, portes, hauteur_camera=pm.VOL_HAUTEUR_M)
    canape = a_pied.case((3.0, 2.0))
    armoire = a_pied.case((1.0, 1.0))
    assert not a_pied.libre[canape] and en_vol.libre[canape]  # survolé en vol, contourné à pied
    assert not en_vol.libre[armoire]  # une armoire haute bloque toujours
    pts = np.array(pm.vol(log)["trajet"]["points"])
    assert pts[:, 2].max() <= 2.5 - pm.VOL_SOUS_PLAFOND_M + 1e-6 and pts[:, 2].min() >= pm.VOL_HAUTEUR_M - 0.05
    assert (pts[:, 4] <= pm.VOL_TANGAGE_DEG + 1e-6).all()  # plus haut, regard plus plongeant (jamais vers le haut)


def test_portes_franchies_droit_option():
    """L'option « portes franchies droit » (écartée par défaut, 12/11/2026) garde un chemin continu, praticable, de mêmes bouts."""
    from moteur.cinema import navigation as nav
    log = _logement()
    carte = nav.Carte(log, nav.portes_ouvertes(log))
    depart, arrivee = carte.plus_proche_libre((3.0, 5.0)), carte.plus_proche_libre((3.0, 1.0))
    chemin = carte.chemin(depart, arrivee)
    droit = nav.redresser_aux_portes(chemin, carte, log, nav.portes_ouvertes(log), [])
    assert droit[0] == chemin[0] and droit[-1] == chemin[-1]
    assert all(carte.libre[c] for c in droit)
    assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 for a, b in zip(droit, droit[1:]))  # pas de saut entre cases
