"""Le blanc des murs sur une photo du client, trouvé seul grâce à la caméra calée (brique photos, 09/11/2026).

Pourquoi : la couleur d'un sol sur une photo dépend du réglage du photographe (plus clair, plus chaud…). On la compare donc à
celle d'un MUR BLANC de la même photo (moteur/teinte_photo.py : le mur de la photo vaut notre peinture blanche). Jusqu'ici, ce
morceau de mur était choisi à la main ; ici, Atelya sait où sont les murs sur la photo (la caméra et le plan) :
- points posés sur la face intérieure des murs de la pièce, entre HAUTEURS (assez haut pour passer au-dessus des meubles bas,
  assez bas pour éviter la corniche), en écartant fenêtres et portes (± MARGE_OUVERTURE) ;
- seuls les points visibles depuis l'appareil (devant lui, dans le cadre, pas cachés par un autre mur de la pièce) ;
- la couleur de chaque point = médiane d'un petit carré de pixels ; on garde les murs « bien éclairés mais pas éblouis »
  (clarté entre la médiane et le 9e dixième, comme moteur/blender/regler_teintes.py), et on en fait la moyenne.
Un mur de couleur (le gris de l'entrée d'app-001), un tableau ou une armoire faussent un peu l'étalon : la sélection par clarté
en écarte une partie ; il reste une source d'erreur connue.
"""
from __future__ import annotations

import numpy as np

from moteur.camera_photo import projeter
from moteur.sol_a_plat import visibles_depuis
from moteur.teinte_photo import lineaire

HAUTEURS = (1.3, 1.6, 1.9, 2.2)
PAS_M = 0.15
MARGE_OUVERTURE = 0.15
DEMI_CARRE = 3  # carré de 7 × 7 pixels
POINTS_MIN = 12


def ouvertures_sur_le_contour(logement: dict, contour) -> list[tuple[int, float, float]]:
    """Les ouvertures reportées sur les bords du contour d'une pièce : (n° du bord, début, fin) en mètres le long du bord. Une
    ouverture appartient à un bord si son mur est parallèle au bord et assez proche (moins que l'épaisseur du mur + 10 cm)."""
    murs = {m["id"]: m for m in logement["murs"]}
    c = np.asarray(contour, float)
    sorties = []
    for o in logement.get("ouvertures", []):
        m = murs.get(o["mur"])
        if m is None:
            continue
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        u = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        p0, p1 = a + u * o["position"], a + u * (o["position"] + o["largeur"])
        for i in range(len(c)):
            e0, e1 = c[i], c[(i + 1) % len(c)]
            longueur = np.linalg.norm(e1 - e0)
            if longueur < 1e-6:
                continue
            v = (e1 - e0) / longueur
            if abs(abs(float(u @ v)) - 1) > 0.02:
                continue
            n = np.array([-v[1], v[0]])
            if abs(float((p0 - e0) @ n)) > m["epaisseur"] + 0.1:
                continue
            t0, t1 = sorted((float((p0 - e0) @ v), float((p1 - e0) @ v)))
            if t1 > 0 and t0 < longueur:
                sorties.append((i, t0, t1))
    return sorties


def points_des_murs(logement: dict, piece: dict, pas: float = PAS_M) -> np.ndarray:
    """Points 3D (N, 3) sur la face intérieure des murs de la pièce, hors fenêtres et portes."""
    c = np.asarray(piece["contour"], float)
    ouvertures = ouvertures_sur_le_contour(logement, piece["contour"])
    centre = c.mean(axis=0)
    pts = []
    for i in range(len(c)):
        e0, e1 = c[i], c[(i + 1) % len(c)]
        longueur = float(np.linalg.norm(e1 - e0))
        if longueur < 0.3:
            continue
        v = (e1 - e0) / longueur
        n = np.array([-v[1], v[0]])
        if (centre - e0) @ n < 0:
            n = -n  # vers l'intérieur de la pièce (contour à peu près convexe localement)
        for t in np.arange(pas / 2, longueur, pas):
            if any(j == i and t0 - MARGE_OUVERTURE <= t <= t1 + MARGE_OUVERTURE for j, t0, t1 in ouvertures):
                continue
            q = e0 + v * t + n * 0.01
            for z in HAUTEURS:
                pts.append((q[0], q[1], z))
    return np.array(pts, float).reshape(-1, 3)


def blanc_des_murs(photo: np.ndarray, cam, logement: dict, piece: dict, point_de_vue=None) -> dict | None:
    """Le blanc des murs de la photo (RGB 0-255) : lumière linéaire moyenne (r, g, b) des murs bien éclairés, et le nombre de
    points retenus. None si trop peu de mur est vu."""
    pts = points_des_murs(logement, piece)
    if not len(pts):
        return None
    vue = point_de_vue or (float(cam[0]), float(cam[1]))
    # un point du mur est caché si le rayon depuis l'appareil traverse un autre bord de la pièce (on recule le point de 2 cm
    # vers l'intérieur pour que son propre mur ne le cache pas)
    visibles = visibles_depuis(pts[:, 0], pts[:, 1], vue, piece["contour"])
    h, w = photo.shape[:2]
    couleurs = []
    for (x, y, z), ok in zip(pts, visibles):
        if not ok:
            continue
        u, v, p = projeter((x, y, z), cam)
        if p <= 0.3 or not (DEMI_CARRE <= u < w - DEMI_CARRE and DEMI_CARRE <= v < h - DEMI_CARRE):
            continue
        carre = photo[int(v) - DEMI_CARRE:int(v) + DEMI_CARRE + 1, int(u) - DEMI_CARRE:int(u) + DEMI_CARRE + 1, :3]
        couleurs.append(np.median(lineaire(carre.reshape(-1, 3)), axis=0))
    if len(couleurs) < POINTS_MIN:
        return None
    couleurs = np.array(couleurs)
    clarte = couleurs @ np.array([0.2126, 0.7152, 0.0722])
    bas, haut = np.percentile(clarte, [50, 90])
    garde = (clarte >= bas) & (clarte <= haut)
    return {"blanc": couleurs[garde].mean(axis=0), "points": int(garde.sum()), "vus": len(couleurs)}
