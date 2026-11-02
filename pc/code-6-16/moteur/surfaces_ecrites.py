"""Lire l'échelle sur les surfaces écrites dans les pièces (version 0.1).

Beaucoup de plans d'agence n'ont ni cotes ni barre d'échelle, mais écrivent la surface de chaque
pièce : « Chambre 12,50 m² ». Atelya a déjà colorié la pièce : si elle couvre 50 000 pixels du
coloriage et que le plan dit 12,50 m², un mètre carré fait 4 000 pixels, donc un mètre fait
√4 000 ≈ 63 pixels. C'est l'échelle.

Une seule pièce peut tromper : surface mal lue (« 2,10 » lu « 2,70 »), pièce mal fermée par Atelya,
surface « habitable » qui ne compte pas un placard. Chaque pièce donne donc un « avis » (l'échelle que
sa surface implique), et l'échelle n'est gardée que si au moins deux pièces sont d'accord (à 3 % près)
et qu'elles réunissent au moins la moitié des surfaces lues. Sinon : « à vérifier ».

Une zone sans mur intérieur qui porte plusieurs surfaces (séjour et cuisine ouverte) compte pour la
somme de ses surfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np

from moteur.lecture_cotes import TexteLu

# « 12,50 m² », « 2,10m2 », « 3,61Lm² » (une lettre parasite lue entre le nombre et l'unité).
# Le nombre doit avoir ses deux décimales : « T2 de 45 m² » (titre) et « 2 m » (barre) ne sont pas des surfaces de pièce.
FORME_SURFACE = re.compile(r"^(\d{1,3}[,.]\d{2})\s*[^\d\s]?\s*m\s*[²2]$", re.IGNORECASE)
SURFACE_MIN, SURFACE_MAX = 0.5, 200.0  # m² : une pièce vraisemblable
ACCORD_PIECES = 0.03  # deux pièces sont d'accord quand leurs échelles diffèrent de moins de 3 %
PART_MIN = 0.5  # les pièces d'accord réunissent au moins la moitié des surfaces lues


@dataclass
class SurfaceLue:
    valeur: float  # m², telle qu'écrite
    x: float  # centre du texte, en pixels du coloriage remis droit
    y: float


@dataclass
class EchelleSurfaces:
    px_par_m: float  # pixels du coloriage remis droit, par mètre
    sure: bool
    avis: list[tuple[float, float]] = field(default_factory=list)  # (surface écrite de la zone, échelle qu'elle donne)
    detail: str = ""


def surfaces_dans_textes(textes: list[TexteLu]) -> list[tuple[float, float, float]]:
    """Les surfaces de pièce écrites sur le plan : (m², x, y) au centre du texte, en pixels de l'image lue."""
    lues = []
    for t in textes:
        m = FORME_SURFACE.match(t.texte.strip())
        if not m:
            continue
        v = float(m.group(1).replace(",", "."))
        if SURFACE_MIN <= v <= SURFACE_MAX:
            cx, cy = np.asarray(t.boite, np.float64).mean(axis=0)
            lues.append((v, float(cx), float(cy)))
    return lues


def echelle_par_surfaces(dedans: np.ndarray, surfaces: list[SurfaceLue]) -> EchelleSurfaces | None:
    """L'échelle sur laquelle les surfaces écrites s'accordent.

    `dedans` : l'intérieur du logement colorié (ni bâti ni dehors), remis droit ; ses zones fermées sont
    les pièces. `surfaces` : les surfaces lues, placées sur ce coloriage."""
    if not surfaces:
        return None
    n, etiq, stats, _ = cv2.connectedComponentsWithStats(dedans.astype(np.uint8), connectivity=4)
    h, w = dedans.shape
    par_zone: dict[int, float] = {}
    for s in surfaces:
        x, y = int(round(s.x)), int(round(s.y))
        if 0 <= y < h and 0 <= x < w and etiq[y, x] > 0:
            par_zone[int(etiq[y, x])] = par_zone.get(int(etiq[y, x]), 0.0) + s.valeur
    avis = [(ecrite, float(np.sqrt(stats[z, cv2.CC_STAT_AREA] / ecrite)), int(stats[z, cv2.CC_STAT_AREA]))
            for z, ecrite in par_zone.items()]
    if not avis:
        return None
    # Le plus grand groupe d'avis d'accord : le plus de zones, puis la plus grande surface écrite.
    groupes = [[a for a in avis if abs(a[1] - c[1]) / c[1] <= ACCORD_PIECES] for c in avis]
    groupe = max(groupes, key=lambda g: (len(g), sum(a[0] for a in g)))
    # Les grandes pièces pèsent plus : leur bord (un pixel de trop ou de moins) compte moins.
    px_par_m = float(np.sqrt(sum(a[2] for a in groupe) / sum(a[0] for a in groupe)))
    part = sum(a[0] for a in groupe) / sum(a[0] for a in avis)
    sure = len(groupe) >= 2 and part >= PART_MIN
    detail = f"{len(groupe)} pièce(s) d'accord sur {len(avis)}, {round(100 * part)} % des surfaces lues"
    return EchelleSurfaces(round(px_par_m, 3), sure, [(a[0], round(a[1], 3)) for a in avis], detail)
