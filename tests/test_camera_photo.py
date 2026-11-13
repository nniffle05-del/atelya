"""Caméra d'une photo du client (moteur/camera_photo.py, B2 temps 2, étape 4)."""
import json
import math
from pathlib import Path

import numpy as np

from moteur.camera_photo import ajuster, camera_depuis_dict, pour_blender, projeter, residus

VRAIE = [11.6, 7.9, 1.3, -117.7, 0.0, 620.0, 603.0, 323.0]  # caméra de la photo 03 d'app-001 (arrondie)


def _ligne(a, b, cam, t1=0.2, t2=0.8):
    """Repère « ligne » relevé sur l'image fabriquée par la vraie caméra, entre deux points de l'arête (pas à ses bouts)."""
    a, b = np.array(a, float), np.array(b, float)
    p1 = projeter(a + (b - a) * t1, cam)[:2]
    p2 = projeter(a + (b - a) * t2, cam)[:2]
    return {"type": "ligne", "a": list(a), "b": list(b), "p1": list(p1), "p2": list(p2)}


def _reperes(cam):
    return [
        _ligne((8.07, 2.65, 0), (8.07, 2.65, 3), cam),     # angle vertical
        _ligne((10.66, 2.65, 0), (10.66, 2.65, 3), cam),   # autre angle vertical
        _ligne((8.07, 2.65, 3), (10.66, 2.65, 3), cam),    # haut de mur
        _ligne((10.68, 1.61, 0), (12.33, 0.02, 0), cam),   # pied de mur
        _ligne((8.07, 2.65, 0), (8.07, 7.0, 0), cam),      # pied d'un autre mur
    ]


def test_projection_sens():
    # un point droit devant, à hauteur de l'appareil, tombe sur le centre optique ; à gauche → u plus petit ; plus haut → v plus petit
    cam = [0, 0, 1.5, 0.0, 0.0, 500.0, 600.0, 400.0]
    u, v, p = projeter((5, 0, 1.5), cam)
    assert (round(u, 6), round(v, 6), p) == (600.0, 400.0, 5.0)
    assert projeter((5, 1, 1.5), cam)[0] < 600  # +y est à gauche quand on regarde vers +x
    assert projeter((5, 0, 2.5), cam)[1] < 400
    assert projeter((-5, 0, 1.5), cam)[2] < 0  # derrière l'appareil


def test_ajustement_retrouve_la_camera():
    reperes = _reperes(VRAIE)
    assert np.abs(residus(VRAIE, reperes)).max() < 1e-9
    depart = [10.8, 6.6, 1.3, -112.0, 0.0, 500.0, 603.0, 402.0]
    cam, ecarts = ajuster(depart, reperes)
    assert np.abs(ecarts).max() < 0.05
    assert math.dist(cam[:3], VRAIE[:3]) < 0.01
    assert abs(cam[3] - VRAIE[3]) < 0.05 and abs(cam[5] - VRAIE[5]) < 0.5 and abs(cam[7] - VRAIE[7]) < 0.5


def test_rappel_tient_un_parametre_mal_fixe():
    # avec deux angles verticaux seulement, la hauteur n'est pas fixée : le rappel la garde près de la valeur donnée
    reperes = _reperes(VRAIE)[:2]
    cam, _ = ajuster([10.8, 6.6, 1.3, -112.0, 0.0, 500.0, 603.0, 402.0], reperes, rappels={2: (1.45, 100.0)})
    assert abs(cam[2] - 1.45) < 0.01


def test_reglages_blender():
    r = pour_blender(VRAIE, 1206, 802)
    assert r["rotation_deg"] == [90.0, 0.0, -207.7]
    assert abs(r["focale_mm"] - 620 * 36 / 1206) < 1e-9
    assert r["decentrement"][0] == 0.0 and abs(r["decentrement"][1] - (323 - 401) / 1206) < 1e-12


def test_releve_app001_coherent():
    # le relevé d'app-001 : chaque caméra recalculée colle à ses repères comme annoncé
    chemin = Path(__file__).resolve().parents[1] / "verites" / "app-001" / "cameras-photos.json"
    releve = json.loads(chemin.read_text(encoding="utf-8"))
    assert "photo-09" in releve["non_calees"] and len(releve["cameras"]) == 11
    for nom, c in releve["cameras"].items():
        ecart = float(np.sqrt((residus(camera_depuis_dict(c["camera"]), c["reperes"]) ** 2).mean()))
        assert abs(ecart - c["ecart_moyen_px"]) < 0.1, nom
        assert ecart < 12, nom
