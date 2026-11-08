"""Recaler un mur saisi à l'œil sur l'ENCRE du plan : l'axe et l'épaisseur glissent sur la bande sombre la plus proche.

Pourquoi : une position donnée à l'œil (vérités faites par Claude dans outils/verite/faire_verite.py, ou lecture de Claude par
l'API, moteur.traduire_claude) est approximative de quelques pixels ; le trait du plan, lui, est exact. Code déplacé tel quel
depuis outils/verite/faire_verite.py le 08/11/2026 (aucun changement de calcul : les vérités restent identiques).
"""
from __future__ import annotations

import math

import numpy as np

def _profil(gris: np.ndarray, x0: float, y0: float, x1: float, y1: float, demi: int) -> np.ndarray:
    """Noirceur médiane le long du mur, pour chaque décalage perpendiculaire de −demi à +demi pixels."""
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L))
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    t = np.linspace(0.1, 0.9, n)  # on évite les bouts (angles, murs voisins)
    xs = x0 + t * (x1 - x0)
    ys = y0 + t * (y1 - y0)
    prof = []
    for k in range(-demi, demi + 1):
        px = np.clip(np.round(xs + k * nx).astype(int), 0, gris.shape[1] - 1)
        py = np.clip(np.round(ys + k * ny).astype(int), 0, gris.shape[0] - 1)
        prof.append(float(np.median(255 - gris[py, px])))
    return np.array(prof)


def affiner_mur(gris: np.ndarray, mur: list[float], marge: int = 6) -> list[float]:
    """Recale l'axe et l'épaisseur d'un mur sur la bande d'encre la plus proche (le trait du plan vaut mieux que mon œil)."""
    x0, y0, x1, y1, ep = mur
    demi = int(ep / 2 + marge)
    prof = _profil(gris, x0, y0, x1, y1, demi)
    papier = float(np.percentile(prof, 20))
    encre = papier + 0.5 * (prof.max() - papier)
    if prof.max() - papier < 40:  # pas d'encre nette : on garde la saisie
        return mur
    sombre = prof >= encre
    # la bande sombre qui contient (ou est la plus proche de) l'axe saisi
    centre = demi
    bandes = []
    k = 0
    while k < len(sombre):
        if sombre[k]:
            j = k
            while j + 1 < len(sombre) and sombre[j + 1]:
                j += 1
            bandes.append((k, j))
            k = j + 1
        else:
            k += 1
    if not bandes:
        return mur
    a, b = min(bandes, key=lambda ab: 0 if ab[0] <= centre <= ab[1] else min(abs(ab[0] - centre), abs(ab[1] - centre)))
    if min(abs(a - centre), abs(b - centre)) > marge and not (a <= centre <= b):
        return mur
    decal = (a + b) / 2 - centre
    nouvelle_ep = b - a + 1
    if abs(nouvelle_ep - ep) > max(3, 0.35 * ep):  # bande trop différente (trait de fenêtre, hachures) : axe seul
        nouvelle_ep = ep
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    return [x0 + decal * nx, y0 + decal * ny, x1 + decal * nx, y1 + decal * ny, float(nouvelle_ep)]
