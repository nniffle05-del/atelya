"""Zoom et orientation d'une photo d'intérieur par ses LIGNES DE FUITE (15/11/2026).

POURQUOI : pour savoir d'où une photo est prise (moteur/caler_photos.py), il faut connaître le zoom de l'appareil. MoGe-2 le
voit trop serré de 14 à 30 % (mesuré sur le corrigé d'app-003), donc les pièces trop profondes et l'appareil mal placé le long
de son axe. Or la photo le dit elle-même : dans une pièce, les arêtes horizontales (corniches, poutres, hauts de portes et de
fenêtres) suivent deux directions à l'équerre, et chaque famille converge sur la photo vers un point de l'horizon. La place de
ces deux points donne le ZOOM (focale f) et l'ORIENTATION de l'appareil par rapport aux murs, à 90° près :
    point 1 en u0 + f·tan(alpha), point 2 en u0 − f/tan(alpha).
Appareil supposé de niveau (photos d'annonce : verticales droites), centre optique au milieu en largeur.

Limite : une photo prise bien en face d'un mur n'a qu'une famille de fuyantes ; l'orientation est connue (alpha ≈ 0) mais pas
le zoom (`net` = False).
"""
from __future__ import annotations

import cv2
import numpy as np

VERSION = "0.1.0"
TOLERANCE = 1.2          # degrés : un segment « suit » un point de fuite s'il le vise à mieux que cela
FOCALES = (0.21, 0.60)   # focales essayées, en part de la largeur de la photo (champ de 135° à 80°)
NET = 1.6                # le zoom est « net » si la meilleure note vaut au moins 1,6 fois la note médiane des autres zooms
PETITE = 250.0           # et si la plus petite des deux familles compte au moins 250 px de segments


def segments(rgb: np.ndarray, mini: float = 30.0) -> np.ndarray:
    gris = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if rgb.ndim == 3 else rgb
    s = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gris)[0]
    s = s.reshape(-1, 4) if s is not None else np.zeros((0, 4), np.float32)
    return s[np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]) >= mini]


def mesurer(rgb: np.ndarray) -> dict:
    """→ {"alpha": angle (degrés, −45 à 45) entre l'axe de visée et une direction des murs (+ = murs tournés vers la droite),
    "f": focale en pixels de la photo, "v0": horizon, "net": le zoom est-il fiable ?, "oriente": l'orientation l'est-elle ?,
    "note", "petite_famille", "segments", "famille"}. Seule la moitié HAUTE de la photo sert (le sol a ses propres fuyantes :
    parquet en chevrons, tapis, meubles)."""
    h, w = rgb.shape[:2]
    u0 = w / 2
    s = segments(rgb, mini=30.0 * w / 1206)
    dx, dy = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    pente = np.degrees(np.arctan2(dy, dx)) % 180          # 0 = horizontal, 90 = vertical
    my = (s[:, 1] + s[:, 3]) / 2
    garde = (np.abs(pente - 90) > 6) & (my < h / 2 - 15 * w / 1206)
    s, dx, dy, my = s[garde], dx[garde], dy[garde], my[garde]
    mx = (s[:, 0] + s[:, 2]) / 2
    direction = np.arctan2(dy, dx)
    poids = np.minimum(np.hypot(dx, dy), 150.0 * w / 1206)
    vide = {"alpha": 0.0, "f": 0.0, "v0": h / 2, "net": False, "oriente": False, "note": 0.0, "petite_famille": 0.0,
            "segments": s, "famille": np.full(len(s), -1)}
    if len(s) < 8:
        return vide

    def ecarts(alpha, f, v0):
        t = np.tan(np.radians(alpha))
        e = []
        for pu in (u0 + f * t, u0 - f / t if abs(t) > 1e-6 else 1e9):
            vers = np.arctan2(v0 - my, pu - mx)
            e.append(np.degrees(np.abs((direction - vers + np.pi / 2) % np.pi - np.pi / 2)))
        return np.array(e)

    def note(alpha, f, v0):
        e = ecarts(alpha, f, v0) < TOLERANCE
        n1, n2 = float((poids * e[0]).sum()), float((poids * e[1]).sum())
        return n1 + n2, min(n1, n2)

    focales = np.arange(FOCALES[0] * w, FOCALES[1] * w, w / 120)
    tableau = np.array([[note(a, f, h / 2)[0] for f in focales] for a in np.arange(-44.5, 45.01, 1.0)])
    ia, jf = np.unravel_index(tableau.argmax(), tableau.shape)
    meilleur = (tableau[ia, jf], -44.5 + ia, float(focales[jf]), h / 2)
    for a in np.arange(meilleur[1] - 1.0, meilleur[1] + 1.01, 0.1):
        for f in np.arange(meilleur[2] - w / 100, meilleur[2] + w / 100 + 0.1, w / 600):
            for v in np.arange(h / 2 - h / 55, h / 2 + h / 55 + 0.1, h / 220):
                n = note(a, f, v)[0]
                if n > meilleur[0]:
                    meilleur = (n, a, f, v)
    n, alpha, f, v0 = meilleur
    petite = note(alpha, f, v0)[1]
    courbe = tableau[max(0, ia - 1):ia + 2].max(0)
    loin = courbe[np.abs(focales - f) > 0.12 * f]
    e = ecarts(alpha, f, v0)
    return {"alpha": float(alpha), "f": float(f), "v0": float(v0), "note": float(n), "petite_famille": float(petite),
            "net": bool(len(loin) > 0 and n >= NET * max(float(np.median(loin)), 1.0) and petite >= PETITE * w / 1206),
            "oriente": bool(n >= 1500.0 * w / 1206),
            "segments": s, "famille": np.where(e.min(0) < TOLERANCE, e.argmin(0), -1)}


ACCORD = 0.06            # les zooms nets d'un lot « s'accordent » si leur écart médian à la médiane est sous 6 %


def zoom_du_lot(mesures: dict[str, dict]) -> float | None:
    """Le zoom commun aux photos d'un même logement, en part de la largeur de la photo (les photos d'une annonce viennent
    presque toujours du même appareil, au même réglage) : la médiane des zooms nets, SEULEMENT s'il y en a au moins trois et
    qu'ils s'accordent. Sinon None : on garde le zoom de MoGe-2 (pièces biscornues, peu de lignes : app-001)."""
    nets = np.array([m["f"] / m["largeur"] for m in mesures.values() if m["net"]])
    if len(nets) < 3:
        return None
    mediane = float(np.median(nets))
    return mediane if float(np.median(np.abs(nets - mediane))) < ACCORD * mediane else None
