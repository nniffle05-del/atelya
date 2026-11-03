"""Aiguillage entre deux lectures d'Atelya (étape A3).

L'essai 5 lit le mieux les plans à murs droits ; l'essai 7b (œil DINOv2, murs en biais) lit bien mieux les
plans à murs en biais ou arrondis mais recule un peu sur les murs droits. On lit donc chaque plan avec les
deux, et on garde la lecture de l'essai 7b seulement si elle trouve assez de murs « libres » (en biais ou
arrondis) : au moins SEUIL_LIBRES_M mètres en tout. Sinon, c'est la lecture de l'essai 5.

Réglé sur les bancs du PC (2026-11-03, traducteur 0.4.1, variante « V2 ») : plans droits −0,1 à −0,2 point
de murs justes, plans en biais 68,7 → 73,8 %, photos de biais 52,1 → 59,4 %, 0 erreur d'échelle de plus,
erreurs silencieuses graves 321 → 306 sur les six bancs.
"""

from __future__ import annotations

import math

VERSION_AIGUILLAGE = "0.1.0"
SEUIL_LIBRES_M = 1.5  # m : longueur totale de murs en biais / arrondis lus par l'essai 7b pour prendre sa lecture
ANGLE_DROIT_MAX = 3.0  # degrés : au-delà, un mur n'est ni horizontal ni vertical (même règle que le banc)


def _murs(logement: dict) -> list[dict]:
    if "niveaux" in logement:
        return [m for n in logement["niveaux"] for m in n.get("murs", [])]
    return list(logement.get("murs", []))


def est_libre(m: dict) -> bool:
    """Mur en biais ou morceau d'arrondi : un id en « -k » (segment d'arrondi) ou un mur penché."""
    if "-" in str(m.get("id", "")):
        return True
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    a = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 90
    return min(a, 90 - a) > ANGLE_DROIT_MAX


def longueur_libre(logement: dict) -> float:
    """Longueur totale (m) des murs en biais / arrondis d'une lecture."""
    return sum(math.dist(m["debut"], m["fin"]) for m in _murs(logement) if est_libre(m))


def choisir(lecture_e5: dict, lecture_e7: dict, seuil: float = SEUIL_LIBRES_M) -> tuple[str, dict]:
    """Renvoie (« e5 » ou « e7 », lecture gardée)."""
    if longueur_libre(lecture_e7) >= seuil:
        return "e7", lecture_e7
    return "e5", lecture_e5
