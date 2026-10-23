"""Lecture automatique des portes et fenêtres d'un plan (version 0.1).

La lecture des murs (lecture_plan.py) laisse des « trous » : les endroits où
un mur est interrompu. Chaque trou est une ouverture possible. On regarde le
dessin dans le trou et autour pour savoir de quoi il s'agit, selon les
conventions des plans d'architecte :

- une PORTE : le trou est vide, et un battant (trait droit, aussi long que
  le trou est large) part d'un bord du trou, perpendiculaire au mur ;
- une PORTE-FENÊTRE : un battant, et en plus un trait fin le long du mur
  dans le trou (le vitrage) ;
- une FENÊTRE : pas de battant, mais plusieurs traits fins parallèles au mur
  dans le trou (le cadre et le vitrage).

Un plan ne donne pas les hauteurs : on met les hauteurs courantes en France,
avec le statut « estimé ».
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Hauteurs courantes (en mètres) : (hauteur de l'ouverture, hauteur d'allège)
HAUTEURS = {
    "porte": (2.04, 0.0),
    "porte_fenetre": (2.15, 0.0),
    "fenetre": (1.35, 0.95),
}
CONFIANCE = {True: 0.7, False: 0.4}  # selon que le dessin est clair ou non

BATTANT_MIN = 0.7  # un battant fait au moins 70 % de la largeur du trou
TRAIT_PLEIN = 0.8  # un trait de vitrage couvre au moins 80 % du trou
MARGE_BOUT = 0.06  # en mètres : un battant part à moins de 6 cm d'un bord du trou


@dataclass
class OuvertureLue:
    mur: int  # numéro du mur dans la lecture
    type: str  # porte, porte_fenetre ou fenetre
    debut: float  # en pixels, le long du mur (x pour un mur horizontal, y pour un vertical)
    fin: float
    sure: bool  # le dessin correspond nettement à un type


def lire_ouvertures(
    gris: np.ndarray,
    murs_epais: np.ndarray,
    bandes: list[tuple[bool, float, float]],
    trous: list[tuple[int, float, float]],
    px_par_m: float,
) -> list[OuvertureLue]:
    """Donne un type à chaque trou des murs.

    gris : le plan redressé ; murs_epais : le masque des murs (blanc = mur) ;
    bandes : pour chaque mur, (horizontal, face 1, face 2) en pixels ;
    trous : (n° du mur, début, fin) en pixels le long du mur.
    """
    _, traits = cv2.threshold(gris, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Les traits fins seulement : on enlève les murs (un peu élargis, pour leurs bords flous).
    murs = cv2.dilate(murs_epais, np.ones((5, 5), np.uint8)) > 0
    fins = traits.copy()
    fins[murs] = 0

    resultat = []
    for i, debut, fin in trous:
        horizontal, face1, face2 = bandes[i]
        t, f = (traits, fins) if horizontal else (traits.T, fins.T)  # un mur vertical est retourné
        battant = _a_un_battant(f, debut, fin, face1, face2, px_par_m)
        vitrages = _traits_le_long(t, debut, fin, face1, face2)
        if battant:
            type_, sure = ("porte_fenetre" if vitrages >= 1 else "porte"), True
        elif vitrages >= 2:
            type_, sure = "fenetre", True
        else:
            type_, sure = "porte", False  # trou sans dessin clair : à vérifier
        resultat.append(OuvertureLue(i, type_, debut, fin, sure))
    return resultat


def _a_un_battant(fins: np.ndarray, debut: float, fin: float, face1: float, face2: float, px_par_m: float) -> bool:
    """Cherche un trait perpendiculaire au mur, partant d'un bord du trou, d'un côté ou de l'autre.

    Une ouverture large (porte-fenêtre) a souvent deux battants, chacun de la
    moitié de la largeur, partant des deux bords du trou du même côté du mur.
    """
    h, w = fins.shape
    largeur = fin - debut
    marge = max(2, round(MARGE_BOUT * px_par_m))
    for r0, r1 in ((face1 - 1.3 * largeur, face1), (face2, face2 + 1.3 * largeur)):
        r0, r1 = max(0, round(r0)), min(h, round(r1))
        if r1 - r0 < 3:
            continue
        longueurs = []
        for bout in (debut, fin):
            c0, c1 = max(0, round(bout) - marge), min(w, round(bout) + marge + 1)
            longueurs.append(_plus_longue_suite(fins[r0:r1, c0:c1]) if c1 > c0 else 0)
        if max(longueurs) >= BATTANT_MIN * largeur:
            return True  # un seul battant
        if min(longueurs) >= BATTANT_MIN * largeur / 2:
            return True  # deux battants
    return False


def _traits_le_long(traits: np.ndarray, debut: float, fin: float, face1: float, face2: float) -> int:
    """Nombre de traits parallèles au mur qui traversent tout le trou."""
    r0, r1 = max(0, round(face1) - 2), min(traits.shape[0], round(face2) + 3)
    c0, c1 = round(debut) + 3, round(fin) - 3
    if c1 - c0 < 3 or r1 <= r0:
        return 0
    pleines = traits[r0:r1, c0:c1].mean(axis=1) >= TRAIT_PLEIN
    # Des lignes pleines voisines forment un seul trait (un trait épais ou flou en couvre plusieurs).
    return int(np.count_nonzero(pleines[1:] & ~pleines[:-1]) + pleines[0])


def _plus_longue_suite(bande: np.ndarray) -> int:
    """La plus longue suite verticale de pixels foncés, toutes colonnes confondues (petits trous tolérés)."""
    colonne_max = bande.max(axis=1) > 0  # une rangée compte si l'une des colonnes est foncée
    meilleur = courant = trou = 0
    for fonce in colonne_max:
        if fonce:
            courant += 1 + trou
            trou = 0
        elif courant and trou < 2:
            trou += 1
        else:
            courant = trou = 0
        meilleur = max(meilleur, courant)
    return meilleur
