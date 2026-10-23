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
# Les lectures essayées tant que l'échelle n'est pas sûre : (enlever le grain, agrandir).
ESSAIS_LECTURE = ((False, 1), (True, 1), (True, 2))
ECRASEMENT_MIN = 0.004  # en dessous de 0,4 % d'écart entre largeur et hauteur, on ne touche à rien
ECRASEMENT_MAX = 0.10  # au-delà de 10 %, ce n'est pas un écrasement mais des cotes mal lues
TRAINEE_MIN = 0.4  # une marque foncée à plus de 40 %, loin des deux côtés du trait de cote, est une traînée
TRAINEE_PORTEE = 150  # en pixels : jusqu'où on regarde de chaque côté
COTE_MIN = 0.30  # une « cote » plus petite (« 0,00 » lu dans une tache) n'en est pas une
TROU_MAX = 4  # trou toléré (en pixels) dans un trait de cote abîmé (photocopie, compression)

FORME_COTE = re.compile(r"^\d{1,2}[,.]\d{2}$")
# « Murs extérieurs : 20 cm », « Cloisons : 7 cm » (le modèle de lecture abîme souvent les mots, pas les nombres).
FORME_EPAISSEUR = re.compile(r"^\s*(murs?|cl\w*)\b\D*?(\d{1,2})\s*cm\b", re.IGNORECASE)
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


def lire_textes(gris: np.ndarray, agrandir: int = 1) -> list[TexteLu]:
    """Tous les textes du plan, avec leur position (lus sur l'image agrandie si demandé)."""
    if agrandir > 1:
        gris = cv2.resize(gris, None, fx=agrandir, fy=agrandir, interpolation=cv2.INTER_CUBIC)
    resultat = _moteur_ocr()(cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR))
    if resultat.txts is None:
        return []
    return [
        TexteLu(t.strip(), np.asarray(b, dtype=float) / agrandir, float(s))
        for b, t, s in zip(resultat.boxes, resultat.txts, resultat.scores)
    ]


def lire_textes_et_echelle(gris: np.ndarray) -> tuple[list[TexteLu], Echelle]:
    """Les textes et l'échelle d'un plan, en insistant si les cotes sont mal lues.

    Sur une photocopie granuleuse ou une image floue, le modèle de lecture rate
    des cotes. On recommence alors sur l'image débarrassée de son grain, puis
    agrandie deux fois, et on garde la lecture qui donne l'échelle la plus sûre.
    """
    meilleure = None
    for debruiter, agrandir in ESSAIS_LECTURE:
        image = cv2.fastNlMeansDenoising(gris, None, 10, 7, 21) if debruiter else gris
        textes = lire_textes(image, agrandir)
        echelle = lire_echelle(gris, textes)
        score = (echelle.sure, echelle.px_par_m is not None, len(echelle.retenues))
        if meilleure is None or score > meilleure[0]:
            meilleure = (score, textes, echelle)
        if echelle.sure:
            break
    return meilleure[1], meilleure[2]


def egaliser_les_echelles(
    gris: np.ndarray, textes: list[TexteLu], echelle: Echelle, photo: bool = False
) -> tuple[np.ndarray, list[TexteLu], Echelle, float]:
    """Rend l'échelle égale en largeur et en hauteur, si les cotes disent qu'elle ne l'est pas.

    Une photo remise à plat peut rester un peu écrasée : 100 pixels par mètre en
    largeur mais 97 en hauteur. Les cotes horizontales donnent l'échelle en largeur,
    les verticales en hauteur ; si elles diffèrent, on étire l'image en hauteur.
    Il faut deux cotes dans chaque sens ; une seule suffit sur une photo (`photo`),
    où l'écrasement est attendu.
    Renvoie l'image, les textes et l'échelle corrigés, et l'étirement appliqué (1 : aucun).
    """
    cotes = echelle.retenues + echelle.ecartees
    horizontales = [c.px_par_m for c in cotes if not c.verticale]
    verticales = [c.px_par_m for c in cotes if c.verticale]
    minimum = 1 if photo else 2
    if len(horizontales) < minimum or len(verticales) < minimum:
        return gris, textes, echelle, 1.0
    etirement = float(np.median(horizontales) / np.median(verticales))
    if abs(etirement - 1) <= ECRASEMENT_MIN or abs(etirement - 1) > ECRASEMENT_MAX:
        return gris, textes, echelle, 1.0
    h, w = gris.shape
    etire = cv2.resize(gris, (w, round(h * etirement)), interpolation=cv2.INTER_CUBIC)
    for t in textes:
        t.boite = t.boite * np.array([1.0, etirement])
    return etire, textes, lire_echelle(etire, textes), etirement


def lire_echelle(gris: np.ndarray, textes: list[TexteLu] | None = None) -> Echelle:
    """L'échelle (pixels par mètre) d'un plan déjà redressé, lue sur ses cotes."""
    if textes is None:
        textes = lire_textes(gris)
    noir = _traits(gris)
    cotes = [
        c for t in textes
        if FORME_COTE.match(t.texte) and (c := _mesurer_cote(noir, t)) and c.valeur >= COTE_MIN
    ]
    hsp = lire_hauteur_sous_plafond(textes)
    if not cotes:
        return Echelle(None, False, hauteur_sous_plafond=hsp)

    mediane = float(np.median([c.px_par_m for c in cotes]))
    retenues = [c for c in cotes if abs(c.px_par_m - mediane) / mediane <= ECART_MAX]
    if not retenues:
        # Deux cotes (ou plus) en désaccord : la médiane tombe entre elles et n'en garde aucune.
        # On part alors de la cote qui a le plus de cotes d'accord avec elle (à égalité, la plus longue).
        def soutien(c: CoteLue) -> tuple[int, float]:
            return sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= ECART_MAX for d in cotes), c.longueur_px

        mediane = max(cotes, key=soutien).px_par_m
        retenues = [c for c in cotes if abs(c.px_par_m - mediane) / mediane <= ECART_MAX]
    # Tri par la même règle (et non « c not in retenues ») : comparer deux cotes
    # comparerait leurs boîtes de texte, des tableaux numpy, et ferait planter.
    ecartees = [c for c in cotes if abs(c.px_par_m - mediane) / mediane > ECART_MAX]
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


def lire_epaisseurs(textes: list[TexteLu]) -> list[float]:
    """Les épaisseurs de murs écrites sur le plan (cartouche), en mètres."""
    epaisseurs = []
    for t in textes:
        trouve = FORME_EPAISSEUR.match(t.texte)
        if trouve:
            valeur = int(trouve.group(2)) / 100
            if 0.04 <= valeur <= 0.50 and valeur not in epaisseurs:
                epaisseurs.append(valeur)
    return epaisseurs


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
    # Un trait de cote resté un peu penché (scan, photo) passe d'une rangée à l'autre :
    # on prend, autour de la rangée trouvée, les trois rangées réunies qui donnent le plus long trait.
    # À longueur égale, la rangée la plus proche de celle trouvée.
    trouvee = y
    y, debut, fin = max(
        ((r, *_trait_autour(noir[max(0, r - 1):r + 2].max(axis=0), cx)) for r in range(max(0, y - 2), min(h, y + 3))),
        key=lambda t: (t[2] - t[1], -abs(t[0] - trouvee)),
    )

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
    # Une traînée de photocopieuse traverse toute la feuille : ce n'est pas une marque.
    colonnes = [c for c in colonnes if not _trainee(noir[:, c], y)]
    marques = _centres_des_groupes(np.array(colonnes, dtype=int), plus_long, decalage)
    gauche = [m for m in marques if m < cx]
    droite = [m for m in marques if m > cx]
    if not gauche or not droite:
        return None
    return max(gauche), min(droite), y


def _trainee(colonne: np.ndarray, y: int) -> bool:
    """La colonne reste foncée loin au-dessus ET loin en dessous du trait de cote (une marque, elle, est courte)."""
    dessus = colonne[max(0, y - TRAINEE_PORTEE):max(0, y - 15)]
    dessous = colonne[y + 16:y + TRAINEE_PORTEE + 1]
    return len(dessus) > 0 and len(dessous) > 0 and dessus.mean() > TRAINEE_MIN and dessous.mean() > TRAINEE_MIN


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
