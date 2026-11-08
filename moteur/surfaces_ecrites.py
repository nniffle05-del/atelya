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

Version 0.2 (08/11/2026) : EchelleSurfaces.groupe donne le centre des zones du groupe d'accord. Sur une image qui dessine plusieurs
niveaux côte à côte, moteur.echelle_plan vérifie ainsi que l'accord vient d'au moins deux niveaux (voir echelle_plan, version 0.14).
Rien d'autre ne change.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import cv2
import numpy as np

from moteur.lecture_cotes import TexteLu

# « 12,50 m² », « 2,10m2 », « 3,61Lm² » (une lettre parasite lue entre le nombre et l'unité), « (14,13 m2) » (fr-009),
# « 1,9m2 » (fr-004 : une seule décimale). Le nombre doit avoir une décimale au moins : « T2 de 45 m² » (titre) et « 2 m »
# (barre d'échelle) ne sont pas des surfaces de pièce.
FORME_SURFACE = re.compile(r"^\(?(\d{1,3}[,.]\d{1,2})\s*[^\d\s]?\s*m\s*[²2]\)?$", re.IGNORECASE)
# « 4,32m × 5,17m » (fr-012) : les deux dimensions d'une pièce ; leur produit vaut une surface écrite.
FORME_DIMENSIONS = re.compile(r"^\(?(\d{1,2}[,.]\d{1,2})\s*m?\s*[x×X*]\s*(\d{1,2}[,.]\d{1,2})\s*m\)?$", re.IGNORECASE)
# Une ligne de légende : un nom de pièce éventuel, puis une surface (« Chambre 12,05 m² », « Séjour : 22,45 m2 »).
FORME_LEGENDE = re.compile(r"^(?P<nom>.*?)\s*[:\-]?\s*\(?(?P<v>\d{1,3}[,.]\d{1,2})\s*[^\d\s]?\s*m\s*[²2]\)?\s*$", re.IGNORECASE)
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
    groupe: list[tuple[float, float]] = field(default_factory=list)  # centres (x, y) des zones du groupe d'accord (version 0.2)
    blocs: int = 0  # image à plusieurs niveaux : de combien de blocs viennent les zones du groupe (rempli par moteur.echelle_plan)


def surfaces_dans_textes(textes: list[TexteLu]) -> list[tuple[float, float, float]]:
    """Les surfaces de pièce écrites sur le plan : (m², x, y) au centre du texte, en pixels de l'image lue."""
    lues = []
    for t in textes:
        texte = t.texte.strip()
        m = FORME_SURFACE.match(texte)
        if m:
            v = float(m.group(1).replace(",", "."))
        elif (d := FORME_DIMENSIONS.match(texte)):
            v = float(d.group(1).replace(",", ".")) * float(d.group(2).replace(",", "."))
        else:
            continue
        if SURFACE_MIN <= v <= SURFACE_MAX:
            cx, cy = np.asarray(t.boite, np.float64).mean(axis=0)
            lues.append((v, float(cx), float(cy)))
    return lues


def _cle(texte: str) -> str:
    """« Chambre 2 » → « chambre 2 » : minuscules, sans accents ni ponctuation, mais avec le numéro."""
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def surfaces_de_legende(textes: list[TexteLu], vers_col, dedans: np.ndarray) -> list[SurfaceLue]:
    """Les surfaces écrites dans une légende (« Chambre 12,05 m² » sous le plan : diagnostiqueurs, Carrez), ramenées
    chacune dans la pièce qui porte le même nom sur le plan.

    Une surface qui n'est dans aucune pièce coloriée est une ligne de légende. Son nom est dans le même texte
    (« Chambre 12,05 m² ») ou dans le texte juste à sa gauche sur la même ligne. On la rattache à la zone du plan où un
    nom identique est écrit (« Chambre 2 » ↔ « Chambre 2 »), sinon à la seule zone de ce type de pièce. Une zone qui a
    déjà sa surface écrite dedans n'en reçoit pas une seconde. Rend des SurfaceLue au centre des zones rattachées."""
    from moteur.noms_pieces import type_depuis_nom

    n, etiq, stats, centres = cv2.connectedComponentsWithStats(dedans.astype(np.uint8), connectivity=4)
    h, w = dedans.shape

    def zone_de(t: TexteLu) -> int:
        cx, cy = np.asarray(t.boite, np.float64).mean(axis=0)
        x, y = vers_col(float(cx), float(cy))
        x, y = int(round(x)), int(round(y))
        return int(etiq[y, x]) if 0 <= y < h and 0 <= x < w else 0

    zones_avec_surface = set()
    legende = []  # (nom, type, surface)
    for t in textes:
        texte = t.texte.strip()
        m = FORME_LEGENDE.match(texte)
        if m:
            v = float(m.group("v").replace(",", "."))
            if not (SURFACE_MIN <= v <= SURFACE_MAX):
                continue
            if zone_de(t) > 0:
                zones_avec_surface.add(zone_de(t))
                continue
            nom = m.group("nom").strip(" :-")
            if not nom:  # « 12,05 m² » seul : le nom est le texte juste à gauche, sur la même ligne
                (x0, y0), (x1, y1) = t.boite.min(axis=0), t.boite.max(axis=0)
                voisins = [u for u in textes if u is not t and abs(u.boite.mean(axis=0)[1] - (y0 + y1) / 2) <= 0.6 * (y1 - y0)
                           and 0 <= x0 - u.boite.max(axis=0)[0] <= 6 * (y1 - y0) and type_depuis_nom(u.texte)
                           and not FORME_LEGENDE.match(u.texte.strip())]
                if not voisins:
                    continue
                nom = min(voisins, key=lambda u: x0 - u.boite.max(axis=0)[0]).texte
            type_ = type_depuis_nom(nom)
            if type_:
                legende.append((_cle(nom), type_, v))
    if not legende:
        return []

    noms_du_plan = {}  # zone → liste de (clé, type) des noms écrits dedans
    for t in textes:
        if FORME_LEGENDE.match(t.texte.strip()):
            continue
        type_ = type_depuis_nom(t.texte)
        z = zone_de(t) if type_ else 0
        if z > 0:
            noms_du_plan.setdefault(z, []).append((_cle(t.texte), type_))

    sortie, prises = [], set(zones_avec_surface)
    for cle, type_, v in legende:
        exactes = [z for z, noms in noms_du_plan.items() if z not in prises and any(c == cle for c, _ in noms)]
        if len(exactes) != 1:
            meme_type = [z for z, noms in noms_du_plan.items() if z not in prises and any(ty == type_ for _, ty in noms)]
            if len(meme_type) != 1 or sum(1 for _, ty, _ in legende if ty == type_) != 1:
                continue  # plusieurs pièces de ce type et pas de nom exact : on ne devine pas
            exactes = meme_type
        z = exactes[0]
        prises.add(z)
        sortie.append(SurfaceLue(v, float(centres[z][0]), float(centres[z][1])))
    return sortie


def echelle_par_surfaces(dedans: np.ndarray, surfaces: list[SurfaceLue]) -> EchelleSurfaces | None:
    """L'échelle sur laquelle les surfaces écrites s'accordent.

    `dedans` : l'intérieur du logement colorié (ni bâti ni dehors), remis droit ; ses zones fermées sont
    les pièces. `surfaces` : les surfaces lues, placées sur ce coloriage."""
    if not surfaces:
        return None
    n, etiq, stats, centres = cv2.connectedComponentsWithStats(dedans.astype(np.uint8), connectivity=4)
    h, w = dedans.shape
    par_zone: dict[int, float] = {}
    for s in surfaces:
        x, y = int(round(s.x)), int(round(s.y))
        if 0 <= y < h and 0 <= x < w and etiq[y, x] > 0:
            par_zone[int(etiq[y, x])] = par_zone.get(int(etiq[y, x]), 0.0) + s.valeur
    avis = [(ecrite, float(np.sqrt(stats[z, cv2.CC_STAT_AREA] / ecrite)), int(stats[z, cv2.CC_STAT_AREA]), z)
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
    return EchelleSurfaces(round(px_par_m, 3), sure, [(a[0], round(a[1], 3)) for a in avis], detail,
                           [(float(centres[a[3]][0]), float(centres[a[3]][1])) for a in groupe])
