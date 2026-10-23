"""Lecture automatique de l'échelle d'un plan, à partir de ses cotes (version 0.1).

Une cote, c'est un trait fin avec une petite marque à chaque bout et un
nombre écrit à côté (par exemple « 4,80 ») : la distance réelle, en mètres,
entre les deux marques. Si on mesure ce trait en pixels sur l'image, on
connaît l'échelle : 480 pixels pour 4,80 m, c'est 100 pixels par mètre.

Principe :
1. Lire tous les textes du plan avec RapidOCR (un modèle de lecture de texte
   déjà entraîné, qui tourne sur l'ordinateur, sans Internet).
2. Garder les textes qui ressemblent à une cote (« 4,80 », « 12.35 »).
3. Pour chacun, retrouver le trait de cote juste à côté du texte, puis les
   marques qui le bornent, et mesurer la distance entre ces marques.
4. Chaque cote donne une échelle. On écarte celles qui ne sont pas d'accord
   avec les autres (texte mal lu, trait mal trouvé) et on fait la moyenne.

On lit aussi la hauteur sous plafond quand elle est écrite sur le plan
(« Hauteur sous plafond : 2,50 m » ou « HSP 2,50 »).

Limites de la version 0.1 : cotes en mètres avec deux décimales ; cotes
horizontales ou verticales ; il faut au moins deux cotes concordantes pour
que l'échelle soit jugée sûre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

ECART_MAX = 0.03  # une cote qui s'écarte de plus de 3 % des autres est écartée
ACCORD = 0.01  # deux cotes « concordantes » donnent la même échelle à 1 % près
MARQUE_MIN = 8  # une marque de bout de cote fait au moins 8 pixels de haut
TROU_MAX = 2  # trou toléré (en pixels) dans un trait de cote abîmé

FORME_COTE = re.compile(r"^\d{1,2}[,.]\d{2}$")
FORME_HSP = re.compile(r"(?:hauteur\s+sous\s+plafond|h\.?\s*s\.?\s*p\.?)\D*(\d+[,.]\d+)", re.IGNORECASE)


@dataclass
class TexteLu:
    texte: str
    boite: np.ndarray  # 4 coins (x, y) en pixels
    confiance: float


@dataclass
class CoteLue:
    valeur: float  # en mètres, telle qu'écrite sur le plan
    longueur_px: float  # distance mesurée entre les deux marques
    verticale: bool
    texte: TexteLu
    bouts: tuple[tuple[float, float], tuple[float, float]]  # les deux marques, en pixels (x, y)

    @property
    def px_par_m(self) -> float:
        return self.longueur_px / self.valeur


@dataclass
class Echelle:
    px_par_m: float | None
    sure: bool  # au moins deux cotes concordantes
    retenues: list[CoteLue] = field(default_factory=list)
    ecartees: list[CoteLue] = field(default_factory=list)
    hauteur_sous_plafond: float | None = None


def lire_textes(gris: np.ndarray) -> list[TexteLu]:
    """Tous les textes du plan, avec leur position."""
    resultat = _moteur_ocr()(cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR))
    if resultat.txts is None:
        return []
    return [
        TexteLu(t.strip(), np.asarray(b, dtype=float), float(s))
        for b, t, s in zip(resultat.boxes, resultat.txts, resultat.scores)
    ]


def lire_echelle(gris: np.ndarray, textes: list[TexteLu] | None = None) -> Echelle:
    """L'échelle (pixels par mètre) d'un plan déjà redressé, lue sur ses cotes."""
    if textes is None:
        textes = lire_textes(gris)
    noir = _traits(gris)
    cotes = [c for t in textes if FORME_COTE.match(t.texte) and (c := _mesurer_cote(noir, t))]
    hsp = lire_hauteur_sous_plafond(textes)
    if not cotes:
        return Echelle(None, False, hauteur_sous_plafond=hsp)

    mediane = float(np.median([c.px_par_m for c in cotes]))
    retenues = [c for c in cotes if abs(c.px_par_m - mediane) / mediane <= ECART_MAX]
    ecartees = [c for c in cotes if c not in retenues]
    # Moyenne pondérée par la longueur : une grande cote est plus précise qu'une petite.
    px_par_m = sum(c.longueur_px for c in retenues) / sum(c.valeur for c in retenues)
    concordantes = [c for c in retenues if abs(c.px_par_m - px_par_m) / px_par_m <= ACCORD]
    return Echelle(round(px_par_m, 3), len(concordantes) >= 2, retenues, ecartees, hsp)


def lire_hauteur_sous_plafond(textes: list[TexteLu]) -> float | None:
    for t in textes:
        trouve = FORME_HSP.search(t.texte)
        if trouve:
            valeur = float(trouve.group(1).replace(",", "."))
            if 1.8 <= valeur <= 6.0:  # au-delà, ce n'est sûrement pas une hauteur sous plafond
                return valeur
    return None


# ---------- Mesure d'une cote ----------


@lru_cache(maxsize=1)
def _moteur_ocr():
    from rapidocr import RapidOCR  # chargé seulement si on lit des textes (le modèle met ~1 s)

    return RapidOCR(params={"Global.log_level": "error"})


def _traits(gris: np.ndarray) -> np.ndarray:
    """Masque des traits, même fins ou pâles : un pixel nettement plus foncé que son voisinage."""
    return cv2.adaptiveThreshold(gris, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 20)


def _mesurer_cote(noir: np.ndarray, texte: TexteLu) -> CoteLue | None:
    """Retrouve le trait d'une cote à côté de son texte et mesure la distance entre ses marques."""
    x0, y0 = texte.boite.min(axis=0)
    x1, y1 = texte.boite.max(axis=0)
    verticale = (y1 - y0) > (x1 - x0)
    if verticale:  # on retourne l'image : la cote verticale devient horizontale
        noir = noir.T
        x0, y0, x1, y1 = y0, x0, y1, x1
    marques = _marques(noir, x0, y0, x1, y1)
    if marques is None:
        return None
    gauche, droite, ligne = marques
    bouts = ((gauche, ligne), (droite, ligne))
    if verticale:  # on remet les coordonnées à l'endroit
        bouts = ((ligne, gauche), (ligne, droite))
    return CoteLue(float(texte.texte.replace(",", ".")), droite - gauche, verticale, texte, bouts)


def _marques(noir: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, int] | None:
    """Les deux marques qui bornent la cote (colonnes) et la ligne du trait de cote."""
    h, w = noir.shape
    hauteur = y1 - y0
    cx = int(round((x0 + x1) / 2))
    if not 0 <= cx < w:
        return None

    # 1. Le trait de cote : la ligne la plus proche du texte (au-dessus ou en dessous)
    #    qui porte un long trait passant sous le milieu du texte.
    lignes = []
    for d in range(1, int(2 * hauteur) + 1):
        lignes += [int(y0) - d, int(np.ceil(y1)) + d]
    for y in lignes:
        if not 0 <= y < h:
            continue
        debut, fin = _trait_autour(noir[y], cx)
        if fin - debut >= 1.2 * (x1 - x0):
            break
    else:
        return None

    # 2. Les marques : colonnes où un petit trait perpendiculaire traverse la ligne,
    #    en dehors des colonnes occupées par le texte.
    haut, bas = max(0, y - 12), min(h, y + 13)
    bande = noir[haut:bas, max(0, debut - 3):min(w, fin + 4)]
    decalage = max(0, debut - 3)
    plus_long = _plus_longue_suite(bande)
    colonnes = np.arange(len(plus_long)) + decalage
    hors_texte = (colonnes < x0 - 2) | (colonnes > x1 + 2)
    if not hors_texte.any():
        return None
    # Une marque floue déborde sur ses voisines : on ne garde que les colonnes
    # presque aussi hautes que la plus haute marque.
    seuil = max(MARQUE_MIN, 0.6 * plus_long[hors_texte].max())
    colonnes = colonnes[hors_texte & (plus_long >= seuil)]
    marques = _centres_des_groupes(colonnes, plus_long, decalage)
    gauche = [m for m in marques if m < cx]
    droite = [m for m in marques if m > cx]
    if not gauche or not droite:
        return None
    return max(gauche), min(droite), y


def _trait_autour(ligne: np.ndarray, cx: int) -> tuple[int, int]:
    """Début et fin du trait foncé qui passe par la colonne cx (petits trous tolérés)."""
    if not ligne[max(0, cx - TROU_MAX):cx + TROU_MAX + 1].any():
        return cx, cx
    debut = fin = cx
    trou = 0
    while debut > 0 and trou <= TROU_MAX:
        debut -= 1
        trou = 0 if ligne[debut] else trou + 1
    debut += trou
    trou = 0
    while fin < len(ligne) - 1 and trou <= TROU_MAX:
        fin += 1
        trou = 0 if ligne[fin] else trou + 1
    fin -= trou
    return debut, fin


def _plus_longue_suite(bande: np.ndarray) -> np.ndarray:
    """Pour chaque colonne, la plus longue suite de pixels foncés consécutifs."""
    meilleur = np.zeros(bande.shape[1], dtype=int)
    courant = np.zeros(bande.shape[1], dtype=int)
    for rangee in bande:
        courant = np.where(rangee > 0, courant + 1, 0)
        meilleur = np.maximum(meilleur, courant)
    return meilleur


def _centres_des_groupes(colonnes: np.ndarray, poids: np.ndarray, decalage: int) -> list[float]:
    """Regroupe les colonnes voisines (une marque floue en couvre plusieurs) et donne leur centre."""
    centres = []
    groupe: list[int] = []
    for c in list(colonnes) + [None]:
        if c is not None and groupe and c - groupe[-1] <= 1:
            groupe.append(c)
            continue
        if groupe:
            p = np.array([poids[g - decalage] for g in groupe], dtype=float)
            centres.append(float(np.dot(groupe, p) / p.sum()))
        groupe = [c] if c is not None else []
    return centres
