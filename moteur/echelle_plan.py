"""Lire l'échelle d'un plan colorié par Atelya, sur les cotes du dessin d'origine (version 0.1).

Atelya colorie le plan mais ne sait pas combien de pixels font un mètre : il faut le lire sur
les cotes (« 4,80 » entre deux marques). Les cotes sont lues par moteur.lecture_cotes, sur le
dessin d'origine en pleine taille (le texte y est net), après l'avoir remis droit exactement
comme le coloriage :
- plan à plat mais penché (scan) : on le tourne du même angle ;
- plan photographié de biais : on lui applique le même redressement (moteur.redressement).
Les cotes horizontales donnent alors l'échelle en largeur, les verticales l'échelle en hauteur.
Sur une photo, les deux diffèrent souvent de quelques % : c'est ce qui permet de rendre au plan
ses vraies proportions.

Garde-fou (decider) : l'échelle doit s'accorder avec la plus grande cote lue (la cote d'ensemble) et la
taille du logement colorié. Sinon le plan part à la vérification humaine, au lieu d'être construit à
la mauvaise taille. Un plan sans cote lisible y part aussi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from moteur.coloriage import MUR, PORTE_FENETRE, _rotation, bati_du_logement, dehors_du_logement, estimer_rotation, redresser
from moteur.lecture_cotes import COTE_MIN, ECART_MAX, ESSAIS_LECTURE, FORME_COTE, CoteLue, Echelle, lire_echelle, lire_textes
from moteur.redressement import Redressement

VERSION_ECHELLE = "0.1.0"
ACCORD_ENSEMBLE = 0.05  # tolérance entre la taille du logement mesurée et la cote d'ensemble
ACCORD_SECOURS = 0.03  # sans cote mesurée : largeur et hauteur d'ensemble doivent s'accorder à 3 % près


@dataclass
class EchelleLue:
    """L'échelle du coloriage (pixels du coloriage, ou du coloriage redressé, par mètre)."""

    largeur: float | None  # px par m, d'après les cotes horizontales
    hauteur: float | None  # px par m, d'après les cotes verticales
    sure: bool  # au moins deux cotes concordantes
    cotes: list[CoteLue] = field(default_factory=list)
    hauteur_sous_plafond: float | None = None
    # Le contrôle par les cotes d'ensemble : la plus grande cote horizontale (verticale) lue sur le plan,
    # en mètres, et la largeur (hauteur) intérieure du logement colorié par Atelya, en pixels.
    cote_max_largeur: float | None = None
    cote_max_hauteur: float | None = None
    interieur_px: tuple[float, float] | None = None

    @property
    def px_par_m(self) -> float | None:
        """L'échelle d'ensemble : celle de la largeur, sinon celle de la hauteur."""
        return self.largeur if self.largeur is not None else self.hauteur

    def decision(self, de_biais: bool) -> tuple[float | None, float | None, str]:
        """L'échelle retenue (largeur, hauteur) et sa source, après contrôle (voir decider)."""
        return decider(self.largeur, self.hauteur, self.sure, self.cote_max_largeur, self.cote_max_hauteur,
                       self.interieur_px, de_biais)


def _plausible(echelle: float | None, interieur: float | None, cote_max: float | None, sure: bool) -> bool:
    """L'échelle est-elle compatible avec la plus grande cote lue dans ce sens ?

    Avec l'échelle, l'intérieur du logement colorié fait `interieur / echelle` mètres. Aucune cote
    partielle ne peut dépasser la cote d'ensemble : si le logement mesuré est plus petit que la plus
    grande cote lue, l'échelle est fausse. S'il est nettement plus grand, soit la cote d'ensemble n'a
    pas été lue (fréquent), soit l'échelle est fausse : on ne la garde que si elle est sûre (deux
    cotes concordantes)."""
    if not (echelle and interieur and cote_max):
        return True
    taille = interieur / echelle
    if taille < cote_max * (1 - ACCORD_ENSEMBLE):
        return False
    if taille > cote_max * (1 + ACCORD_ENSEMBLE):
        return sure
    return True


def decider(largeur: float | None, hauteur: float | None, sure: bool, cote_max_largeur: float | None,
            cote_max_hauteur: float | None, interieur_px: tuple[float, float] | None,
            de_biais: bool) -> tuple[float | None, float | None, str]:
    """Contrôle l'échelle lue sur les cotes par la cote d'ensemble.

    La plus grande cote d'un plan est presque toujours la cote d'ensemble du logement : rapportée à
    la largeur (ou la hauteur) intérieure du logement colorié, elle redonne l'échelle à ~0,3 % près.
    Une échelle qui ne s'accorde pas avec elle vient d'une cote mal lue (« 6,80 » lu « 0,80 », trait
    d'une autre cote) : le plan est alors envoyé à la vérification humaine plutôt que de construire
    un logement à la mauvaise taille (voir _plausible).
    Sans aucune cote mesurée, la cote d'ensemble sert de secours, si la largeur et la hauteur
    donnent la même échelle (plan à plat seulement : sur une photo elles diffèrent).

    Rend (largeur, hauteur, source) ; source = « cotes », « cote d'ensemble » ou « à vérifier »
    (échelles à None)."""
    il, ih = interieur_px or (None, None)
    if largeur or hauteur:
        if de_biais:
            bon = _plausible(largeur, il, cote_max_largeur, sure) and _plausible(hauteur, ih, cote_max_hauteur, sure)
        else:
            m = largeur or hauteur
            bon = _plausible(m, il, cote_max_largeur, sure) and _plausible(m, ih, cote_max_hauteur, sure)
        return (largeur, hauteur, "cotes") if bon else (None, None, "à vérifier")
    ctrl_l = il / cote_max_largeur if il and cote_max_largeur else None
    ctrl_h = ih / cote_max_hauteur if ih and cote_max_hauteur else None
    if not de_biais and ctrl_l and ctrl_h and abs(ctrl_l / ctrl_h - 1) <= ACCORD_SECOURS:
        e = (ctrl_l + ctrl_h) / 2
        return e, e, "cote d'ensemble"
    return None, None, "à vérifier"


def _mediane_accordee(valeurs: list[CoteLue]) -> float | None:
    """L'échelle donnée par un groupe de cotes, sans celles qui s'écartent de la médiane."""
    if not valeurs:
        return None
    m = float(np.median([c.px_par_m for c in valeurs]))
    gardees = [c for c in valeurs if abs(c.px_par_m - m) / m <= ECART_MAX] or valeurs
    return sum(c.longueur_px for c in gardees) / sum(c.valeur for c in gardees)  # les longues pèsent plus


def _cadre_entier(G: np.ndarray, forme: tuple[int, int], taille: tuple[int, int], k: float,
                  marge: float = 0.6) -> tuple[np.ndarray, tuple[int, int]]:
    """Le redressement recadre sur le logement, ce qui couperait les cotes dessinées autour.
    On garde ici toute la feuille redressée, sans dépasser `marge` × la taille du logement de chaque côté
    (près de l'horizon, une photo très penchée s'étirerait sans fin)."""
    h, w = forme[:2]
    coins = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], np.float64) @ G.T
    coins = coins[:, :2] / coins[:, 2:]
    W, H = taille[0] * k, taille[1] * k
    x0, y0 = max(coins[:, 0].min(), -marge * W), max(coins[:, 1].min(), -marge * H)
    x1, y1 = min(coins[:, 0].max(), (1 + marge) * W), min(coins[:, 1].max(), (1 + marge) * H)
    T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64)
    return T @ G, (int(np.ceil(x1 - x0)), int(np.ceil(y1 - y0)))


def _lire(gris: np.ndarray) -> tuple[Echelle, list[tuple[float, bool]]]:
    """Comme lecture_cotes.lire_textes_et_echelle, mais sans insister quand la première lecture ne trouve
    aucun nombre en forme de cote : le plan n'a pas de cotes, les lectures suivantes (plus lentes) n'en
    trouveraient pas davantage. Rend aussi tous les nombres en forme de cote lus (valeur, vertical),
    même ceux dont le trait n'a pas été retrouvé."""
    meilleure = None
    for debruiter, agrandir in ESSAIS_LECTURE:
        image = cv2.fastNlMeansDenoising(gris, None, 10, 7, 21) if debruiter else gris
        textes = lire_textes(image, agrandir)
        echelle = lire_echelle(gris, textes)
        score = (echelle.sure, echelle.px_par_m is not None, len(echelle.retenues))
        nombres = [(float(t.texte.replace(",", ".")), _vertical(t.boite)) for t in textes if FORME_COTE.match(t.texte)]
        if meilleure is None or score > meilleure[0]:
            meilleure = (score, echelle, nombres)
        if echelle.sure or not nombres:
            break
    return meilleure[1], meilleure[2]


def _vertical(boite: np.ndarray) -> bool:
    (x0, y0), (x1, y1) = boite.min(axis=0), boite.max(axis=0)
    return (y1 - y0) > (x1 - x0)


def interieur_du_logement(col: np.ndarray, px_par_m: float) -> tuple[float, float] | None:
    """Largeur et hauteur (pixels) de l'intérieur du logement colorié : du nu intérieur d'un mur
    extérieur à l'autre, ce que mesurent les cotes d'ensemble « intérieures »."""
    bati = bati_du_logement(col, px_par_m)
    if not bati.any():
        return None
    dedans = ~bati & ~dehors_du_logement(bati)
    ys, xs = np.nonzero(dedans)
    if not len(xs):
        return None
    return float(xs.max() + 1 - xs.min()), float(ys.max() + 1 - ys.min())


def lire_echelle_plan(dessin: np.ndarray, coloriage: np.ndarray, redressement: Redressement | None = None,
                      angle: float | None = None) -> EchelleLue:
    """L'échelle du coloriage, lue sur les cotes du dessin d'origine (gris ou couleurs, pleine taille).

    `redressement` : celui appliqué au coloriage (plan photographié de biais) ; l'échelle rendue
    est alors celle du coloriage redressé. Sinon le dessin est tourné de `angle` (estimé sur le
    coloriage s'il n'est pas donné), ce qui ne change pas l'échelle."""
    gris = dessin if dessin.ndim == 2 else cv2.cvtColor(dessin, cv2.COLOR_RGB2GRAY)
    r = coloriage.shape[1] / gris.shape[1]  # dessin → coloriage
    if redressement is not None:
        k = 1 / r  # on lit le dessin redressé à sa pleine taille, puis on revient à celle du coloriage
        G = np.diag([k, k, 1.0]) @ redressement.H @ np.diag([r, r, 1.0])
        G = _cadre_entier(G, gris.shape, redressement.taille, k)
        vu = cv2.warpPerspective(gris, G[0], G[1], flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=255)
        facteur = 1 / k
        col = redressement.appliquer(coloriage)
    else:
        if angle is None:
            angle = estimer_rotation((coloriage >= MUR) & (coloriage <= PORTE_FENETRE))
        vu = gris
        if abs(angle) >= 0.01:
            m, W, H = _rotation(gris.shape, angle)
            vu = cv2.warpAffine(gris, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=255)
        facteur = r
        col = redresser(coloriage, angle)
    echelle, nombres = _lire(vu)
    cotes = echelle.retenues + echelle.ecartees
    if redressement is not None:
        # Sur une photo, largeur et hauteur peuvent différer : chaque sens a sa propre médiane.
        largeur = _mediane_accordee([c for c in cotes if not c.verticale])
        hauteur = _mediane_accordee([c for c in cotes if c.verticale])
    else:
        largeur = hauteur = echelle.px_par_m
    largeur = largeur * facteur if largeur else None
    hauteur = hauteur * facteur if hauteur else None
    horiz = [v for v, vert in nombres if not vert and v >= COTE_MIN]
    verti = [v for v, vert in nombres if vert and v >= COTE_MIN]
    interieur = interieur_du_logement(col, largeur or hauteur or max(col.shape) / 15)
    return EchelleLue(largeur, hauteur, echelle.sure, cotes, echelle.hauteur_sous_plafond,
                      max(horiz) if horiz else None, max(verti) if verti else None, interieur)
