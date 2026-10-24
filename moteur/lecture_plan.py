"""Lecture automatique d'un plan : trouver les murs sur l'image (version 0.1).

Principe, en partant de l'image du plan :
1. Garder ce qui est foncé (les traits du dessin).
2. Effacer les traits fins (textes, cotes, portes, fenêtres) : il ne reste que
   les traits épais, c'est-à-dire les murs.
3. Redresser l'image si le plan a été scanné un peu de travers.
4. Séparer les morceaux de murs horizontaux et verticaux, et mesurer chacun :
   sa position, sa longueur et son épaisseur.
5. Recoller les morceaux d'un même mur coupés par une porte ou une fenêtre,
   et régler les bouts de chaque mur sur la convention du moteur (angles
   rejoints au milieu des murs ; une cloison s'arrête sur la face du mur
   qu'elle rencontre).

L'échelle (pixels par mètre) est lue toute seule sur les cotes du plan
(voir lecture_cotes.py), ou donnée à la main.

Avant tout, l'image est nettoyée (nettoyage.py) : feuille photographiée remise
à plat, papier rendu blanc, contraste d'une photocopie pâle rendu.

Limites de la version 0.1 : murs droits et perpendiculaires seulement.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from moteur.lecture_cotes import Echelle
    from moteur.lecture_ouvertures import OuvertureLue
    from moteur.lecture_pieces import PieceLue
    from moteur.nettoyage import Nettoyage

# Les tailles sont en mètres et converties en pixels avec l'échelle.
TRAIT_FIN_MAX = 0.045  # un trait plus fin que 4,5 cm sur le plan n'est pas un mur (une cloison fait 7 cm et plus)
MORCEAU_MIN = 0.32  # longueur minimale d'un morceau de mur
EPAISSEUR_MAX = 0.70  # épaisseur maximale d'un mur (un mur extérieur isolé fait couramment 40 à 55 cm)
OUVERTURE_MAX = 2.50  # au-delà, deux morceaux alignés sont deux murs distincts
BAIE_MAX = 4.50  # dans un mur épais (extérieur), une baie vitrée suivie d'une porte-fenêtre peut dépasser 2,50 m
BAIE_COUVERTE = 0.9  # part du trou où l'on voit le vitrage d'une grande baie
MUR_EPAIS_MIN = 0.15  # à partir de cette épaisseur, un mur est traité comme un mur extérieur ou porteur
BORD_ORIGINE = 0.05  # les murs du bord du logement dépassent tous à 5 cm près
TOLERANCE = 0.03  # écart admis entre deux morceaux « alignés »
INCLINAISON_MAX = 5.0  # degrés : inclinaison maximale corrigée
SAUT_DE_FACE = 0.02  # une face qui se décale de plus de 2 cm : le mur change d'épaisseur
MORCEAU_EPAISSEUR_MIN = 0.15  # en dessous, un changement d'épaisseur est une bavure

CALAGE_EPAISSEUR_MAX = 0.03  # une épaisseur lue à moins de 3 cm d'une épaisseur écrite prend celle-ci

CONFIANCE_LECTURE = 0.7


@dataclass
class Bande:
    """Un morceau de mur rectangulaire, en pixels de l'image redressée.

    `horizontal` : le mur court de gauche à droite (sinon de haut en bas).
    `debut`, `fin` : étendue le long du mur ; `bord1`, `bord2` : ses deux faces.
    """

    horizontal: bool
    debut: float
    fin: float
    bord1: float
    bord2: float

    @property
    def axe(self) -> float:
        return (self.bord1 + self.bord2) / 2

    @property
    def epaisseur(self) -> float:
        return self.bord2 - self.bord1


@dataclass
class MurLu:
    """Un mur lu sur le plan : son axe (en pixels de l'image redressée) et son épaisseur."""

    debut: tuple[float, float]
    fin: tuple[float, float]
    epaisseur_px: float


@dataclass
class Lecture:
    image_redressee: np.ndarray
    angle: float  # rotation appliquée pour redresser le plan, en degrés
    murs: list[MurLu]
    origine: tuple[float, float]  # coin intérieur sud-ouest, en pixels
    ouvertures_candidates: list[tuple[int, float, float]]  # (n° du mur, début, fin), en pixels


@dataclass
class PlanLu:
    """Tout ce que la lecture automatique a trouvé sur un plan."""

    lecture: Lecture  # les murs
    px_par_m: float
    echelle: Echelle | None  # le détail de l'échelle, si elle a été lue sur les cotes
    ouvertures: list[OuvertureLue]
    pieces: list[PieceLue]
    hauteur_sous_plafond: float | None  # si elle est écrite sur le plan
    nettoyage: Nettoyage | None = None  # ce qui a été fait à l'image avant de la lire


def lire_plan(image: np.ndarray, px_par_m: float | None = None) -> PlanLu:
    """Lit un plan entier : échelle (si elle n'est pas donnée), murs, portes, fenêtres et pièces."""
    # Chargés ici : le modèle de lecture de texte met une seconde à démarrer.
    from moteur.lecture_cotes import (
        egaliser_les_echelles, lire_epaisseurs, lire_hauteur_sous_plafond, lire_textes, lire_textes_et_echelle,
    )
    from moteur.lecture_ouvertures import lire_ouvertures
    from moteur.lecture_pieces import lire_pieces
    from moteur.nettoyage import nettoyer

    propre, nettoyage = nettoyer(en_gris(image))
    gris, angle = redresser(propre)
    echelle = None
    if px_par_m is None:
        textes, echelle = lire_textes_et_echelle(gris)
        gris, textes, echelle, nettoyage.etirement_hauteur = egaliser_les_echelles(
            gris, textes, echelle, photo=nettoyage.feuille_detouree
        )
        if echelle.px_par_m is None:
            raise ValueError("aucune cote lisible sur ce plan : donner l'échelle à la main")
        px_par_m = echelle.px_par_m
    else:
        textes = lire_textes(gris)
    lecture = lire_murs_sur_plan_droit(gris, angle, px_par_m)
    _caler_les_epaisseurs(lecture.murs, lire_epaisseurs(textes), px_par_m)

    bandes = []
    for m in lecture.murs:
        horizontal = m.debut[1] == m.fin[1]
        axe = m.debut[1] if horizontal else m.debut[0]
        bandes.append((horizontal, axe - m.epaisseur_px / 2, axe + m.epaisseur_px / 2))
    ouvertures = lire_ouvertures(
        gris, _traits_epais(gris, px_par_m), bandes, lecture.ouvertures_candidates, px_par_m
    )
    murs_m = [(m["debut"], m["fin"], m["epaisseur"]) for m in logement_depuis_lecture(lecture, px_par_m, "-")["murs"]]
    pieces = lire_pieces(gris.shape, murs_m, textes, px_par_m, lecture.origine)
    return PlanLu(lecture, px_par_m, echelle, ouvertures, pieces, lire_hauteur_sous_plafond(textes), nettoyage)


def logement_depuis_plan(plan: PlanLu, projet_id: str, hauteur_sous_plafond: float | None = None) -> dict:
    """Le contenu de logement.json (format logement/0.1) : murs, ouvertures et pièces lus."""
    from moteur.lecture_ouvertures import CONFIANCE, HAUTEURS
    from moteur.logement import TOLERANCE_SURFACE

    hsp = hauteur_sous_plafond or plan.hauteur_sous_plafond or 2.50
    s = plan.px_par_m
    logement = logement_depuis_lecture(plan.lecture, s, projet_id, hsp)

    prefixes = {"porte": "P", "porte_fenetre": "PF", "fenetre": "F"}
    compteurs: dict[str, int] = {}
    for o in plan.ouvertures:
        mur = plan.lecture.murs[o.mur]
        horizontal = mur.debut[1] == mur.fin[1]
        # Distance depuis le début du mur (à gauche pour un mur horizontal, en bas pour un vertical).
        position = (o.debut - mur.debut[0]) if horizontal else (mur.debut[1] - o.fin)
        hauteur, allege = HAUTEURS[o.type]
        compteurs[o.type] = compteurs.get(o.type, 0) + 1
        logement["ouvertures"].append({
            "id": f"{prefixes[o.type]}{compteurs[o.type]}",
            "type": o.type,
            "mur": logement["murs"][o.mur]["id"],
            "position": round(position / s, 3),
            "largeur": round((o.fin - o.debut) / s, 3),
            "hauteur": hauteur,
            "allege": allege,
            "statut": "estime",
            "source": "lecture_auto",
            "confiance": CONFIANCE[o.sure],
        })

    for n, p in enumerate(plan.pieces, start=1):
        d_accord = p.surface_ecrite is not None and abs(p.surface_ecrite - p.surface_calculee) <= TOLERANCE_SURFACE
        logement["pieces"].append({
            "id": f"piece_{n}",
            "nom": p.nom or f"Pièce {n}",
            "contour": [list(q) for q in p.contour],
            "surface": p.surface_ecrite if d_accord else None,
            "statut": "estime",
            "source": "lecture_auto",
            # Nom et surface écrits sur le plan, et surface d'accord : la lecture se confirme elle-même.
            "confiance": CONFIANCE_LECTURE if (p.nom and d_accord) else 0.5,
        })
    return logement


def proposition_a_verifier(plan: PlanLu, projet_id: str, nom_image: str, hauteur_sous_plafond: float | None = None) -> dict:
    """La lecture, au format de la page de saisie (outils/saisie-plan), pour qu'un humain la vérifie.

    Tout y est en pixels de l'image redressée, qui est jointe au fichier.
    Chaque élément douteux est signalé, pour que la page le mette en évidence.
    """
    import base64

    logement = logement_depuis_plan(plan, projet_id, hauteur_sous_plafond)
    s = float(plan.px_par_m)
    ox, oy = (float(v) for v in plan.lecture.origine)

    def en_pixels(p: list[float]) -> list[float]:
        return [round(ox + p[0] * s, 2), round(oy - p[1] * s, 2)]

    echelle, controle = {"pxParM": s, "longueur": None, "p1": None, "p2": None, "lue": False, "sure": True}, None
    if plan.echelle is not None:
        cotes = sorted(plan.echelle.retenues, key=lambda c: -c.longueur_px)
        principale = cotes[0]
        echelle.update(
            longueur=principale.valeur, p1=_liste(principale.bouts[0]), p2=_liste(principale.bouts[1]),
            lue=True, sure=plan.echelle.sure, cotes=[c.texte.texte for c in cotes],
        )
        # Le contrôle : de préférence une cote dans l'autre sens que la principale.
        autres = [c for c in cotes[1:] if c.verticale != principale.verticale] or cotes[1:]
        if autres:
            c = autres[0]
            controle = {
                "p1": _liste(c.bouts[0]), "p2": _liste(c.bouts[1]), "longueur": c.valeur,
                "ecart": round(float((c.longueur_px / s - c.valeur) / c.valeur * 100), 2),
            }

    hsp_lue = hauteur_sous_plafond is None and plan.hauteur_sous_plafond is not None
    _, png = cv2.imencode(".png", plan.lecture.image_redressee)
    murs = [
        {
            "id": m["id"], "debut": en_pixels(m["debut"]), "fin": en_pixels(m["fin"]),
            "epaisseur": m["epaisseur"], "longueurTapee": None, "source": "lecture_auto",
        }
        for m in logement["murs"]
    ]
    ouvertures = [
        {**o, "sure": lue.sure, "verifie": False}
        for o, lue in zip(logement["ouvertures"], plan.ouvertures)
    ]
    pieces = [
        {
            "id": p["id"], "nom": lue.nom or "", "contour": [en_pixels(q) for q in p["contour"]],
            "surfaceEcrite": lue.surface_ecrite, "accord": lue.surfaces_d_accord, "verifie": False,
        }
        for p, lue in zip(logement["pieces"], plan.pieces)
    ]
    return {
        "version": "saisie/0.2",
        "projet_id": projet_id,
        "hauteur_sous_plafond": logement["hauteur_sous_plafond"],
        "hsp_lue": hsp_lue or hauteur_sous_plafond is not None,
        "echelle": echelle,
        "controle": controle,
        "origine": [ox, oy],
        "murs": murs,
        "ouvertures": ouvertures,
        "pieces": pieces,
        "compteur": len(murs),
        "lecture_auto": True,
        "image": {"nom": nom_image, "dataUrl": "data:image/png;base64," + base64.b64encode(png.tobytes()).decode()},
    }


def _liste(point) -> list[float]:
    return [round(float(v), 2) for v in point]


def lire_murs(image: np.ndarray, px_par_m: float) -> Lecture:
    """Trouve les murs sur l'image d'un plan (niveaux de gris ou couleur)."""
    gris, angle = redresser(en_gris(image))
    return lire_murs_sur_plan_droit(gris, angle, px_par_m)


def en_gris(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def redresser(gris: np.ndarray) -> tuple[np.ndarray, float]:
    """Redresse un plan scanné de travers. Renvoie l'image droite et l'angle corrigé (degrés)."""
    _, noir = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    angle = _inclinaison(noir)
    if abs(angle) > 0.01:
        gris = _tourner(gris, angle, fond=255)
    return gris, angle


def lire_murs_sur_plan_droit(gris: np.ndarray, angle: float, px_par_m: float) -> Lecture:
    """Trouve les murs sur un plan déjà redressé."""
    noir = _traits_epais(gris, px_par_m)
    bandes = _bandes(noir, px_par_m, horizontal=True) + _bandes(noir, px_par_m, horizontal=False)
    _, traits = cv2.threshold(gris, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bandes, trous = _recoller(bandes, px_par_m, traits)
    bandes, trous = _sans_morceaux_englobes(bandes, trous, px_par_m)
    bandes, trous = _garder_le_logement(bandes, trous, px_par_m)
    trous += _prolonger_jusqu_aux_murs(bandes, noir, px_par_m)
    if not bandes:
        raise ValueError("aucun mur trouvé sur ce plan")
    murs = [_regler_les_bouts(b, bandes, px_par_m) for b in bandes]

    verticales = [b for b in bandes if not b.horizontal]
    horizontales = [b for b in bandes if b.horizontal]
    if not verticales or not horizontales:
        raise ValueError("impossible de trouver le contour du logement")
    # Un poteau ou une gaine collé au mur extérieur dépasse autant que lui, mais
    # sa face intérieure est plus loin : parmi les murs du bord, on prend la face
    # intérieure la plus proche de l'extérieur.
    bord = BORD_ORIGINE * px_par_m
    x_min = min(b.bord1 for b in verticales)
    y_max = max(b.bord2 for b in horizontales)
    gauche = min((b for b in verticales if b.bord1 <= x_min + bord), key=lambda b: b.bord2)
    bas = max((b for b in horizontales if b.bord2 >= y_max - bord), key=lambda b: b.bord1)
    origine = (gauche.bord2, bas.bord1)  # faces intérieures du mur de gauche et du mur du bas
    return Lecture(gris, angle, murs, origine, trous)


def logement_depuis_lecture(
    lecture: Lecture, px_par_m: float, projet_id: str, hauteur_sous_plafond: float = 2.50
) -> dict:
    """Le contenu de logement.json (format logement/0.1), toutes valeurs « estimées »."""
    ox, oy = lecture.origine

    def en_metres(p: tuple[float, float]) -> list[float]:
        return [round((p[0] - ox) / px_par_m, 3) + 0.0, round((oy - p[1]) / px_par_m, 3) + 0.0]

    return {
        "schema": "logement/0.1",
        "projet_id": projet_id,
        "unites": "m",
        "hauteur_sous_plafond": hauteur_sous_plafond,
        "murs": [
            {
                "id": f"M{i + 1}",
                "debut": en_metres(m.debut),
                "fin": en_metres(m.fin),
                "epaisseur": round(m.epaisseur_px / px_par_m, 2),
                "statut": "estime",
                "source": "lecture_auto",
                "confiance": CONFIANCE_LECTURE,
            }
            for i, m in enumerate(lecture.murs)
        ],
        "ouvertures": [],
        "pieces": [],
    }


# ---------- Étapes de la lecture ----------


def _traits_epais(gris: np.ndarray, px_par_m: float) -> np.ndarray:
    """Masque des traits épais : noir sur blanc → blanc sur noir, traits fins effacés."""
    _, noir = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k = max(3, math.ceil(TRAIT_FIN_MAX * px_par_m))  # un trait plus fin que k pixels est effacé
    return cv2.morphologyEx(noir, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))


def _caler_les_epaisseurs(murs: list[MurLu], ecrites: list[float], px_par_m: float) -> None:
    """Cale chaque mur sur l'épaisseur écrite sur le plan la plus proche, si elle l'est à 3 cm près.

    Sur une image floue ou très compressée, un mur paraît un ou deux pixels plus
    épais qu'il n'est (à 60 pixels par mètre, un pixel fait déjà 1,7 cm) ; le
    cartouche, lui, donne l'épaisseur exacte. Le milieu du mur ne bouge pas.
    """
    if not ecrites:
        return
    for m in murs:
        lue = m.epaisseur_px / px_par_m
        proche = min(ecrites, key=lambda e: abs(e - lue))
        if abs(proche - lue) <= CALAGE_EPAISSEUR_MAX:
            m.epaisseur_px = proche * px_par_m


def _inclinaison(masque: np.ndarray) -> float:
    """L'angle (en degrés) qui rend les murs les plus droits possible.

    On essaie plusieurs angles et on garde celui pour lequel les murs
    tombent sur le moins de lignes et de colonnes possible.
    """
    petit = cv2.resize(masque, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)

    def nettete(angle: float) -> float:
        m = _tourner(petit, angle, fond=0).astype(np.float64)
        return float(np.sum(m.sum(axis=1) ** 2) + np.sum(m.sum(axis=0) ** 2))

    meilleur = max(np.arange(-INCLINAISON_MAX, INCLINAISON_MAX + 1e-9, 0.25), key=nettete)
    fin = np.arange(meilleur - 0.25, meilleur + 0.25 + 1e-9, 0.02)
    return round(float(max(fin, key=nettete)), 2)


def _tourner(image: np.ndarray, angle: float, fond: int) -> np.ndarray:
    h, w = image.shape[:2]
    matrice = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(image, matrice, (w, h), flags=cv2.INTER_LINEAR, borderValue=fond)


def _bandes(masque: np.ndarray, px_par_m: float, horizontal: bool) -> list[Bande]:
    """Les morceaux de murs dans une direction, chacun mesuré par son rectangle.

    Un même trait épais peut changer d'épaisseur en chemin : dans un logement en L,
    un mur extérieur se prolonge souvent par une cloison plus fine, posée contre
    une de ses faces. On coupe alors le trait là où ses faces sautent, pour avoir
    un morceau par épaisseur (sinon la cloison serait lue comme un mur de 20 cm).
    """
    longueur = max(3, round(MORCEAU_MIN * px_par_m))
    taille = (longueur, 1) if horizontal else (1, longueur)
    sens = cv2.morphologyEx(masque, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, taille))
    sens = _sans_murs_epais_de_travers(sens, masque, taille, longueur, px_par_m, horizontal)
    if not horizontal:
        sens = sens.T  # on travaille toujours « de gauche à droite »
    n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(sens, connectivity=4)
    bandes = []
    for i, (x, y, w, h, surface) in enumerate(stats[1:], start=1):
        if surface < 0.5 * w * h:
            continue  # pas un rectangle plein
        for debut, fin, bord1, bord2 in _morceaux_d_epaisseur_constante(etiquettes[y:y + h, x:x + w] == i, px_par_m):
            bandes.append(Bande(horizontal, x + debut, x + fin, y + bord1, y + bord2))
    return bandes


def _sans_murs_epais_de_travers(
    sens: np.ndarray, masque: np.ndarray, taille: tuple[int, int], longueur: int, px_par_m: float, horizontal: bool
) -> np.ndarray:
    """Retire d'un passage les murs très épais qui vont dans l'autre sens.

    Un mur plus épais que MORCEAU_MIN (un mur extérieur isolé de 40 à 55 cm) passe aussi
    le filtre de l'autre sens : un mur vertical de 50 cm ressort comme un « mur horizontal »
    de 50 cm de long, souvent soudé aux vrais murs horizontaux. Seuls les morceaux qui ne
    ressemblent pas à un mur couché (plus hauts que larges, ou pas pleins) sont repris :
    on n'y garde que les pixels plus longs dans ce sens que dans l'autre.
    """
    n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(sens, connectivity=4)
    douteux = [i for i, (x, y, w, h, surface) in enumerate(stats[1:], start=1)
               if (h > w if horizontal else w > h) or surface < 0.5 * w * h]
    if not douteux:
        return sens
    zone = np.isin(etiquettes, douteux)
    le_long, en_travers = _longueurs_de_trait(masque, horizontal), _longueurs_de_trait(masque, not horizontal)
    epais_de_travers = (le_long >= longueur) & (le_long <= EPAISSEUR_MAX * px_par_m) & (en_travers > le_long)
    filtre = np.where(zone & epais_de_travers, 0, masque).astype(masque.dtype)
    repris = cv2.morphologyEx(filtre, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, taille))
    return np.where(zone, repris, sens).astype(sens.dtype)


def _longueurs_de_trait(masque: np.ndarray, horizontal: bool) -> np.ndarray:
    """Pour chaque pixel noir, la longueur du trait plein qui le traverse, à l'horizontale ou à la verticale."""
    m = (masque > 0) if horizontal else (masque > 0).T
    longueurs = np.zeros(m.shape, dtype=np.int32)
    for i, ligne in enumerate(m):
        bords = np.diff(np.concatenate(([0], ligne.view(np.int8), [0])))
        for d, f in zip(np.flatnonzero(bords == 1), np.flatnonzero(bords == -1)):
            longueurs[i, d:f] = f - d
    return longueurs if horizontal else longueurs.T


def _morceaux_d_epaisseur_constante(trait: np.ndarray, px_par_m: float) -> list[tuple[int, int, int, int]]:
    """Coupe un trait (couché, de gauche à droite) là où ses faces sautent.

    Renvoie (début, fin, face du haut, face du bas) pour chaque morceau, en pixels
    dans le cadre du trait.
    """
    plein = trait.any(axis=0)
    haut = np.where(plein, trait.argmax(axis=0), 0)
    bas = np.where(plein, trait.shape[0] - trait[::-1].argmax(axis=0), 0)
    saut = max(2.0, SAUT_DE_FACE * px_par_m)
    court = max(3, round(MORCEAU_EPAISSEUR_MIN * px_par_m))

    # 1. Des morceaux où les deux faces restent à peu près à la même place.
    morceaux: list[list[int]] = []  # [début, fin]
    for c in range(trait.shape[1]):
        if morceaux:
            d = morceaux[-1][0]
            if abs(haut[c] - np.median(haut[d:c])) <= saut and abs(bas[c] - np.median(bas[d:c])) <= saut:
                morceaux[-1][1] = c + 1
                continue
        morceaux.append([c, c + 1])

    # 2. Un morceau trop court (bavure, angle) est rendu à son voisin le plus long.
    while len(morceaux) > 1:
        k = min(range(len(morceaux)), key=lambda j: morceaux[j][1] - morceaux[j][0])
        if morceaux[k][1] - morceaux[k][0] >= court:
            break
        voisin = k - 1 if k == len(morceaux) - 1 or (
            k > 0 and morceaux[k - 1][1] - morceaux[k - 1][0] >= morceaux[k + 1][1] - morceaux[k + 1][0]
        ) else k + 1
        morceaux[voisin] = [min(morceaux[k][0], morceaux[voisin][0]), max(morceaux[k][1], morceaux[voisin][1])]
        del morceaux[k]

    resultat = []
    for d, f in morceaux:
        # Les faces du morceau : celles de la majorité de ses colonnes (une bavure ne compte pas).
        resultat.append((d, f, int(np.median(haut[d:f])), int(np.median(bas[d:f]))))
    return resultat


def _recoller(
    bandes: list[Bande], px_par_m: float, traits: np.ndarray | None = None
) -> tuple[list[Bande], list[tuple[int, float, float]]]:
    """Recolle les morceaux alignés d'un même mur ; les trous entre eux sont des ouvertures possibles.

    Un trou plus large que OUVERTURE_MAX n'est recollé que dans un mur épais,
    et seulement si un vitrage (trait fin le long du mur) le traverse presque
    entièrement : c'est alors une grande baie, pas deux murs distincts.
    """
    tol = TOLERANCE * px_par_m
    resultat: list[Bande] = []
    trous: list[tuple[int, float, float]] = []
    for horizontal in (True, False):
        restants = sorted((b for b in bandes if b.horizontal == horizontal), key=lambda b: (b.axe, b.debut))
        while restants:
            mur = restants.pop(0)
            alignes = [b for b in restants if abs(b.axe - mur.axe) <= tol and abs(b.epaisseur - mur.epaisseur) <= tol]
            for b in sorted(alignes, key=lambda b: b.debut):
                trou = b.debut - mur.fin
                if trou > OUVERTURE_MAX * px_par_m and not (
                    trou <= BAIE_MAX * px_par_m
                    and min(mur.epaisseur, b.epaisseur) >= MUR_EPAIS_MIN * px_par_m
                    and _vitrage_continu(traits, mur, b)
                ):
                    continue
                if trou > 0:
                    trous.append((len(resultat), mur.fin, b.debut))
                mur = Bande(horizontal, min(mur.debut, b.debut), max(mur.fin, b.fin),
                            min(mur.bord1, b.bord1), max(mur.bord2, b.bord2))
                restants.remove(b)
            resultat.append(mur)
    return resultat, trous


def _vitrage_continu(traits: np.ndarray | None, mur: Bande, b: Bande) -> bool:
    """Le trou entre deux morceaux d'un mur est-il traversé par un dessin presque sans coupure ?"""
    if traits is None:
        return False
    t = traits if mur.horizontal else traits.T
    r0, r1 = round(max(mur.bord1, b.bord1)), round(min(mur.bord2, b.bord2)) + 1
    zone = t[r0:r1, round(mur.fin) + 2:round(b.debut) - 1]
    return zone.size > 0 and zone.max(axis=0).mean() >= BAIE_COUVERTE


def _rectangle(b: Bande) -> tuple[float, float, float, float]:
    return (b.debut, b.bord1, b.fin, b.bord2) if b.horizontal else (b.bord1, b.debut, b.bord2, b.fin)


def _sans_morceaux_englobes(
    bandes: list[Bande], trous: list[tuple[int, float, float]], px_par_m: float
) -> tuple[list[Bande], list[tuple[int, float, float]]]:
    """Enlève les petits morceaux tout entiers contenus dans un autre mur.

    Le bout d'un mur épais, au bord d'une baie, se lit aussi comme un petit
    mur en travers ; une fois la baie recollée, il est à l'intérieur du mur.
    """
    tol = TOLERANCE * px_par_m

    def dedans(b: Bande, a: Bande) -> bool:
        bx0, by0, bx1, by1 = _rectangle(b)
        ax0, ay0, ax1, ay1 = _rectangle(a)
        return ax0 - tol <= bx0 and bx1 <= ax1 + tol and ay0 - tol <= by0 and by1 <= ay1 + tol

    garde = [i for i, b in enumerate(bandes)
             if not any(j != i and a.fin - a.debut > b.fin - b.debut and dedans(b, a) for j, a in enumerate(bandes))]
    nouveaux = {i: n for n, i in enumerate(garde)}
    return [bandes[i] for i in garde], [(nouveaux[i], a, b) for i, a, b in trous if i in nouveaux]


def _garder_le_logement(
    bandes: list[Bande], trous: list[tuple[int, float, float]], px_par_m: float
) -> tuple[list[Bande], list[tuple[int, float, float]]]:
    """Garde le plus grand groupe de murs qui se touchent : c'est le logement.

    Les murs d'un logement se tiennent tous entre eux. Un élément isolé
    (flèche du nord, cartouche, légende) n'en fait pas partie.
    """
    tol = TOLERANCE * px_par_m

    def rectangle(b: Bande) -> tuple[float, float, float, float]:
        return (b.debut, b.bord1, b.fin, b.bord2) if b.horizontal else (b.bord1, b.debut, b.bord2, b.fin)

    def se_touchent(a: Bande, b: Bande) -> bool:
        ax0, ay0, ax1, ay1 = rectangle(a)
        bx0, by0, bx1, by1 = rectangle(b)
        return ax0 <= bx1 + tol and bx0 <= ax1 + tol and ay0 <= by1 + tol and by0 <= ay1 + tol

    groupe_de = list(range(len(bandes)))

    def chef(i: int) -> int:
        while groupe_de[i] != i:
            i = groupe_de[i]
        return i

    for i in range(len(bandes)):
        for j in range(i + 1, len(bandes)):
            if se_touchent(bandes[i], bandes[j]):
                groupe_de[chef(j)] = chef(i)
    if not bandes:
        return [], []
    tailles: dict[int, float] = {}
    for i, b in enumerate(bandes):
        tailles[chef(i)] = tailles.get(chef(i), 0) + (b.fin - b.debut)
    garde = max(tailles, key=tailles.get)
    nouveaux = {i: n for n, i in enumerate(i for i in range(len(bandes)) if chef(i) == garde)}
    return (
        [bandes[i] for i in nouveaux],
        [(nouveaux[i], a, b) for i, a, b in trous if i in nouveaux],
    )


def _prolonger_jusqu_aux_murs(bandes: list[Bande], noir: np.ndarray, px_par_m: float) -> list[tuple[int, float, float]]:
    """Prolonge jusqu'au mur voisin un mur qui s'arrête dans le vide.

    Quand une porte est percée tout près du bout d'une cloison, le petit bout
    de cloison qui reste (10 à 30 cm) est trop court pour être lu comme un mur :
    la cloison semble s'arrêter dans le vide, la pièce n'est plus fermée et se
    fond avec sa voisine. Dans un logement, une cloison va toujours d'un mur à
    un autre : on la prolonge donc jusqu'au premier mur perpendiculaire qu'elle
    rencontre (à moins de OUVERTURE_MAX), et l'espace vide devient une
    ouverture possible (la porte). Modifie les bandes ; renvoie les nouveaux trous.
    """
    tol = TOLERANCE * px_par_m
    nouveaux: list[tuple[int, float, float]] = []
    for n, mur in enumerate(bandes):
        perpendiculaires = [
            b for b in bandes
            if b.horizontal != mur.horizontal and b.debut - tol <= mur.bord1 and mur.bord2 <= b.fin + tol
        ]
        trait = noir if mur.horizontal else noir.T
        rangees = trait[max(0, round(mur.bord1)):round(mur.bord2)]
        if rangees.shape[0] == 0:
            continue
        plein = (rangees > 0).mean(axis=0) >= 0.8  # colonnes où le mur (ou un bout de mur) est dessiné
        for cote in (-1, 1):
            bout = mur.debut if cote < 0 else mur.fin
            if any(b.bord1 - tol <= bout <= b.bord2 + tol for b in perpendiculaires):
                continue  # le mur s'arrête déjà sur un autre mur
            devant = [b for b in perpendiculaires if (b.bord1 - bout) * cote > 0 or (b.bord2 - bout) * cote > 0]
            if not devant:
                continue
            cible = min(devant, key=lambda b: abs((b.bord1 if cote > 0 else b.bord2) - bout))
            face = cible.bord1 if cote > 0 else cible.bord2
            if abs(face - bout) > OUVERTURE_MAX * px_par_m or abs(face - bout) < 2 * tol:
                continue
            # Le vide va du bout du mur au premier pixel de mur dessiné (petit bout de cloison, ou mur cible).
            colonnes = [c for c in range(round(bout), round(face), cote) if 0 <= c < plein.size]
            depart = next((k for k, c in enumerate(colonnes) if not plein[c]), len(colonnes))  # sortir du mur flou
            arret = next((c for c in colonnes[depart:] if plein[c]), round(face))
            bout = colonnes[depart] if depart < len(colonnes) else bout
            debut_trou, fin_trou = sorted((bout, float(arret)))
            if fin_trou - debut_trou < MORCEAU_MIN * px_par_m:
                continue  # trop étroit pour une porte
            if cote > 0:
                mur.fin = face
            else:
                mur.debut = face
            nouveaux.append((n, debut_trou, fin_trou))
    return nouveaux


def _regler_les_bouts(mur: Bande, bandes: list[Bande], px_par_m: float) -> MurLu:
    """Place chaque bout du mur selon ce qu'il rencontre.

    - Angle (le mur rencontre le BOUT d'un mur perpendiculaire) : on s'arrête
      sur l'axe de l'autre mur ; les deux murs partagent alors le même point.
    - Té (le mur bute sur le MILIEU d'un autre mur) : on s'arrête sur la face
      de l'autre mur, côté intérieur.
    - Rien : on garde le bout tel qu'il est dessiné.
    """
    tol = TOLERANCE * px_par_m
    bouts = [mur.debut, mur.fin]
    for i, bout in enumerate(bouts):
        for autre in bandes:
            if autre.horizontal == mur.horizontal:
                continue
            touche = autre.bord1 - tol <= bout <= autre.bord2 + tol
            croise = autre.debut - tol <= mur.bord1 and mur.bord2 <= autre.fin + tol
            if not (touche and croise):
                continue
            au_bout = abs(mur.bord1 - autre.debut) <= tol or abs(mur.bord2 - autre.fin) <= tol
            # Une cloison qui arrive au bout d'un mur plus épais ne fait pas un angle avec lui :
            # elle prolonge un autre mur (logement en L) et s'arrête sur sa face, comme en té.
            plus_fin = mur.epaisseur < autre.epaisseur - tol
            if au_bout and not plus_fin:
                bouts[i] = autre.axe
            else:
                bouts[i] = autre.bord2 if i == 0 else autre.bord1
            break
    a, b = bouts
    if mur.horizontal:
        return MurLu((a, mur.axe), (b, mur.axe), mur.epaisseur)
    # Image : y vers le bas. On décrit le mur de bas en haut, comme dans le logement.
    return MurLu((mur.axe, b), (mur.axe, a), mur.epaisseur)


# ---------- Commande ----------


def main() -> None:
    parser = argparse.ArgumentParser(description="Lit un plan (murs, portes, fenêtres, pièces) et écrit un logement.json proposé.")
    parser.add_argument("plan", help="image du plan (PNG ou JPG)")
    parser.add_argument("sortie", help="fichier logement.json à écrire")
    parser.add_argument("--echelle", type=float, help="pixels par mètre (ex. 100) ; sinon lue sur les cotes")
    parser.add_argument("--hsp", type=float, help="hauteur sous plafond en mètres ; sinon lue sur le plan, ou 2,50")
    parser.add_argument("--projet", default="PLAN-LU", help="nom du projet")
    args = parser.parse_args()
    image = cv2.imread(args.plan, cv2.IMREAD_GRAYSCALE)
    if image is None:
        sys.exit(f"Échec : image illisible ({args.plan})")
    try:
        plan = lire_plan(image, args.echelle)
    except ValueError as erreur:
        sys.exit(f"Échec : {erreur}")

    def fr(x: float) -> str:
        return f"{x:.2f}".replace(".", ",")

    echelle = plan.echelle
    if echelle is not None:
        cotes = ", ".join(c.texte.texte for c in echelle.retenues)
        print(f"Échelle lue : {plan.px_par_m} pixels par mètre, d'après les cotes {cotes}")
        for c in echelle.ecartees:
            print(f"  cote écartée (pas d'accord avec les autres) : {c.texte.texte}")
        if not echelle.sure:
            print("  ATTENTION : moins de deux cotes concordantes, échelle à vérifier")
    if args.hsp is None:
        if plan.hauteur_sous_plafond is not None:
            print(f"Hauteur sous plafond lue sur le plan : {fr(plan.hauteur_sous_plafond)} m")
        else:
            print("Hauteur sous plafond non trouvée : 2,50 m par défaut, à vérifier")

    lecture = plan.lecture
    print(f"{len(lecture.murs)} murs trouvés (plan redressé de {lecture.angle}°)")
    noms = {"porte": "porte(s)", "porte_fenetre": "porte(s)-fenêtre(s)", "fenetre": "fenêtre(s)"}
    compte = ", ".join(
        f"{sum(o.type == t for o in plan.ouvertures)} {nom}"
        for t, nom in noms.items()
        if any(o.type == t for o in plan.ouvertures)
    )
    print(f"{len(plan.ouvertures)} ouvertures trouvées : {compte or 'aucune'}")
    if any(not o.sure for o in plan.ouvertures):
        print(f"  ATTENTION : {sum(not o.sure for o in plan.ouvertures)} ouverture(s) au dessin peu clair, à vérifier")
    print(f"{len(plan.pieces)} pièces trouvées :")
    for p in plan.pieces:
        ligne = f"  {p.nom or 'sans nom (à nommer)'} : {fr(p.surface_calculee)} m² calculés"
        if p.surface_ecrite is None:
            ligne += ", pas de surface écrite sur le plan"
        elif p.surfaces_d_accord:
            ligne += f", {fr(p.surface_ecrite)} m² écrits : d'accord"
        else:
            ligne += f", mais {fr(p.surface_ecrite)} m² écrits : À VÉRIFIER"
        print(ligne)

    logement = logement_depuis_plan(plan, args.projet, args.hsp)
    sortie = Path(args.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)  # crée le dossier (par exemple sorties/) s'il manque
    sortie.write_text(json.dumps(logement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {args.sortie}")

    # Le même résultat, pour la vérification humaine dans la page de saisie.
    a_verifier = sortie.with_name(sortie.stem + "-a-verifier.json")
    proposition = proposition_a_verifier(plan, args.projet, Path(args.plan).name, args.hsp)
    a_verifier.write_text(json.dumps(proposition, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {a_verifier} (à ouvrir dans la page de saisie pour vérifier)")

if __name__ == "__main__":
    main()
