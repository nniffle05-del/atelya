"""Lecture automatique des pièces d'un plan (version 0.1).

Principe :
1. On redessine les murs lus, en bouchant les portes et fenêtres : chaque
   pièce devient un espace blanc complètement fermé.
2. Chaque espace fermé (hors l'extérieur) est une pièce. Son contour suit
   les faces intérieures des murs.
3. On donne à chaque pièce le nom écrit dedans sur le plan (« Chambre »), et
   on compare la surface écrite (« 9,92 m² ») à celle qu'on calcule : un
   écart signale une erreur de lecture, à faire vérifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

SURFACE_MIN = 0.8  # m² : en dessous, ce n'est pas une pièce (gaine, recoin)
ACCROCHE = 0.03  # m : un coin de pièce se cale sur la face de mur la plus proche
ACCORD_SURFACE = 0.02  # surfaces écrite et calculée d'accord à 2 % près

FORME_SURFACE = re.compile(r"^(\d+(?:[,.]\d+)?)\s*m\s*[²2]$", re.IGNORECASE)


@dataclass
class PieceLue:
    nom: str | None  # le nom écrit sur le plan, s'il y en a un
    contour: list[tuple[float, float]]  # en mètres, repère du logement
    surface_ecrite: float | None  # la surface écrite sur le plan, s'il y en a une

    @property
    def surface_calculee(self) -> float:
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.contour, self.contour[1:] + self.contour[:1]):
            total += x1 * y2 - x2 * y1
        return abs(total) / 2

    @property
    def surfaces_d_accord(self) -> bool | None:
        if self.surface_ecrite is None:
            return None
        return bool(abs(self.surface_ecrite - self.surface_calculee) <= ACCORD_SURFACE * self.surface_calculee)


def lire_pieces(
    taille: tuple[int, int],
    murs_m: list[tuple[tuple[float, float], tuple[float, float], float]],
    textes: list,
    px_par_m: float,
    origine: tuple[float, float],
) -> list[PieceLue]:
    """Trouve les pièces entre les murs.

    taille : (hauteur, largeur) de l'image redressée ;
    murs_m : les murs (début, fin, épaisseur) en mètres, repère du logement ;
    textes : les textes lus sur le plan redressé (lecture_cotes.lire_textes) ;
    origine : le pixel du point (0, 0).
    """
    ox, oy = origine

    def en_pixels(x: float, y: float) -> tuple[float, float]:
        return ox + x * px_par_m, oy - y * px_par_m

    def en_metres(px: float, py: float) -> tuple[float, float]:
        return (px - ox) / px_par_m, (oy - py) / px_par_m

    # 1. Les murs redessinés pleins, bouts prolongés d'une demi-épaisseur pour bien fermer les angles.
    plein = np.zeros(taille, np.uint8)
    faces_x: set[float] = set()
    faces_y: set[float] = set()
    for (x1, y1), (x2, y2), e in murs_m:
        demi = e / 2
        x_min, x_max = min(x1, x2) - demi, max(x1, x2) + demi
        y_min, y_max = min(y1, y2) - demi, max(y1, y2) + demi
        if abs(y1 - y2) < 1e-9:
            faces_y.update((y1 - demi, y1 + demi))
        else:
            faces_x.update((x1 - demi, x1 + demi))
        (px0, py1), (px1, py0) = en_pixels(x_min, y_min), en_pixels(x_max, y_max)
        cv2.rectangle(plein, (round(px0), round(py0)), (round(px1) - 1, round(py1) - 1), 255, -1)

    # 2. Les espaces fermés.
    n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(255 - plein, connectivity=4)
    h, w = taille
    pieces = []
    for k in range(1, n):
        x, y, lw, lh, surface_px = stats[k]
        if x == 0 or y == 0 or x + lw >= w or y + lh >= h:
            continue  # touche le bord de l'image : c'est l'extérieur
        if surface_px / px_par_m**2 < SURFACE_MIN:
            continue
        masque = (etiquettes == k).astype(np.uint8)
        contours, _ = cv2.findContours(masque, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        points = cv2.approxPolyDP(contours[0], 2, True)[:, 0, :]
        # Le contour suit le centre des pixels du bord : on le cale sur les faces des murs.
        contour = [
            (_accrocher(mx, faces_x, ACCROCHE), _accrocher(my, faces_y, ACCROCHE))
            for mx, my in (en_metres(px + 0.5, py + 0.5) for px, py in points)
        ]
        contour = _sans_doublons(contour)
        if len(contour) < 3:
            continue
        dedans = [t for t in textes if _dans_l_image(_centre(t), h, w) and masque[_centre(t)]]
        piece = PieceLue(_nom(dedans), contour, _surface_ecrite(dedans))
        if piece.surface_ecrite is not None:
            piece.surface_ecrite = surface_vraisemblable(piece.surface_ecrite, piece.surface_calculee)
        pieces.append(piece)
    return pieces


def lire_surface(texte: str) -> float | None:
    """« 9,92 m² » → 9.92 ; « 357 m² » (virgule perdue) → 357.0, à interpréter par l'appelant."""
    trouve = FORME_SURFACE.match(texte.strip())
    return float(trouve.group(1).replace(",", ".")) if trouve else None


def surface_vraisemblable(lue: float, calculee: float) -> float | None:
    """Corrige une virgule perdue par la lecture : 357 pour une pièce de 3,57 m² calculés.

    Un nombre sans aucun rapport (plus de 5 fois trop grand ou trop petit) est
    une erreur de lecture du texte : on l'ignore plutôt que de donner une
    fausse alerte. Un écart plus modéré est gardé : il sera signalé.
    """
    candidats = [lue, lue / 10, lue / 100]
    meilleur = min(candidats, key=lambda c: abs(c - calculee))
    if abs(meilleur - calculee) <= ACCORD_SURFACE * calculee:
        return meilleur
    return lue if calculee / 5 <= lue <= calculee * 5 else None


# ---------- Outils ----------


def _accrocher(valeur: float, faces: set[float], tolerance: float) -> float:
    proche = min(faces, key=lambda f: abs(f - valeur), default=None)
    v = proche if proche is not None and abs(proche - valeur) <= tolerance else valeur
    return round(float(v), 3) + 0.0


def _sans_doublons(contour: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Enlève les points répétés et les points au milieu d'un côté droit."""
    points = [p for i, p in enumerate(contour) if p != contour[i - 1]]
    garde = []
    for i, p in enumerate(points):
        a, b = points[i - 1], points[(i + 1) % len(points)]
        aligne = (a[0] == p[0] == b[0]) or (a[1] == p[1] == b[1])
        if not aligne:
            garde.append(p)
    return garde


def _centre(texte) -> tuple[int, int]:
    x, y = texte.boite.mean(axis=0)
    return int(round(y)), int(round(x))


def _dans_l_image(rc: tuple[int, int], h: int, w: int) -> bool:
    return 0 <= rc[0] < h and 0 <= rc[1] < w


def _nom(textes: list) -> str | None:
    noms = [t.texte for t in textes if lire_surface(t.texte) is None and re.search(r"[A-Za-zÀ-ÿ]{2}", t.texte)]
    return " ".join(noms) if noms else None


def _surface_ecrite(textes: list) -> float | None:
    for t in textes:
        s = lire_surface(t.texte)
        if s is not None:
            return s
    return None
