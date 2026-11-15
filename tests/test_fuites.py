"""Lignes de fuite (moteur/fuites.py) : sur une pièce dessinée à zoom et cap connus, on retrouve le zoom et l'orientation."""
import math

import cv2
import numpy as np

from moteur import fuites
from moteur.camera_photo import projeter


def _piece(cap, f, largeur=1206, hauteur=670):
    image = np.full((hauteur, largeur, 3), 235, np.uint8)
    cam = [2.0, 1.5, 1.3, cap, 0.0, f, largeur / 2, hauteur / 2]
    lignes = []
    for z in (2.2, 2.5, 2.9):  # corniches et hauts de portes sur les quatre murs d'une pièce de 6 m × 5 m
        lignes += [((0, 0, z), (6, 0, z)), ((6, 0, z), (6, 5, z)), ((6, 5, z), (0, 5, z)), ((0, 5, z), (0, 0, z))]
    for x in np.arange(0.5, 6, 0.5):  # poutres
        lignes.append(((x, 0, 2.9), (x, 5, 2.9)))
    for a, b in lignes:
        a, b = np.array(a, float), np.array(b, float)
        vue = np.array([math.cos(math.radians(cap)), math.sin(math.radians(cap)), 0.0])
        pts = [a + (b - a) * k / 40 for k in range(41)]
        pts = [projeter(q, cam) if (q - np.array(cam[:3])) @ vue > 0.3 else None for q in pts]
        for p, q in zip(pts, pts[1:]):
            if p is not None and q is not None:
                cv2.line(image, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), (40, 40, 40), 2)
    return image


def test_zoom_et_orientation_retrouves():
    m = fuites.mesurer(_piece(cap=32.0, f=390.0))
    assert m["net"] and m["oriente"]
    assert abs(m["f"] - 390.0) < 12
    assert abs((m["alpha"] - 32.0 + 45) % 90 - 45) < 0.6


def test_photo_de_face_zoom_pas_net():
    m = fuites.mesurer(_piece(cap=0.0, f=390.0))
    assert not m["net"]
    assert abs((m["alpha"] + 45) % 90 - 45) < 1.0


def test_zoom_du_lot_seulement_si_accord():
    lot = lambda fs: {str(i): {"f": f, "largeur": 1000, "net": True} for i, f in enumerate(fs)}
    assert math.isclose(fuites.zoom_du_lot(lot([380, 390, 400, 385])), 0.3875)
    assert fuites.zoom_du_lot(lot([280, 460, 630, 720])) is None
    assert fuites.zoom_du_lot(lot([380, 390])) is None


def test_orientation_refaite_au_zoom_impose():
    """Une seule famille de fuyantes bien visible (photo presque de face) : le zoom propre n'est pas net, mais une fois le
    vrai zoom donné l'orientation est retrouvée."""
    image = _piece(cap=8.0, f=390.0)
    m = fuites.mesurer(image)
    o = fuites.orienter_au_zoom(m, 390.0, image.shape[1], image.shape[0])
    assert o["oriente"]
    assert abs((o["alpha"] - 8.0 + 45) % 90 - 45) < 0.8
    assert abs(o["v0"] - image.shape[0] / 2) < 12
