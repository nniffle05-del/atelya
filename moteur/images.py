"""Lire et écrire des images sans le piège des accents.

Sous Windows, cv2.imread et cv2.imwrite échouent EN SILENCE dès que le chemin contient un accent
(par exemple « D:\\Modélisation immobilière\\... ») : imread renvoie None, imwrite n'écrit rien.
Ici, Python lit ou écrit lui-même les octets du fichier et OpenCV ne fait que les décoder ou les
encoder : le chemin ne passe plus par OpenCV, donc les accents ne gênent plus.

Mêmes arguments que cv2.imread / cv2.imwrite, pour pouvoir les remplacer un pour un.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def lire_image(chemin, drapeau: int = cv2.IMREAD_COLOR):
    """Comme cv2.imread : l'image, ou None si le fichier manque ou n'est pas une image."""
    try:
        octets = np.fromfile(str(chemin), dtype=np.uint8)
    except OSError:
        return None
    if octets.size == 0:
        return None
    return cv2.imdecode(octets, drapeau)


def ecrire_image(chemin, image, params=None) -> bool:
    """Comme cv2.imwrite (format choisi d'après l'extension), mais lève une erreur si rien n'est
    écrit au lieu d'échouer en silence."""
    chemin = Path(chemin)
    ok, octets = cv2.imencode(chemin.suffix, image, [] if params is None else list(params))
    if not ok:
        raise OSError(f"image non encodée : {chemin}")
    octets.tofile(str(chemin))
    return True
