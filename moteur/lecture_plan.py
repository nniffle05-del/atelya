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
from moteur.images import lire_image
import numpy as np

if TYPE_CHECKING:
    from moteur.lecture_cotes import Echelle
    from moteur.lecture_ouvertures import OuvertureLue
    from moteur.lecture_pieces import PieceLue
    from moteur.nettoyage import Nettoyage

# Les tailles sont en mètres et converties en pixels avec l'échelle.
TRAIT_FIN_MAX = 0.045  # un trait plus fin que 4,5 cm sur le plan n'est pas un mur (une cloison fait 7 cm et plus)
MORCEAU_MIN = 0.32  # longueur minimale d'un morceau de mur
CLOISON_MIN = 0.06  # épaisseur minimale du mur voisin (une cloison fait 7 cm et plus)
EPAISSEUR_MAX = 0.70  # épaisseur maximale d'un mur (un mur extérieur isolé fait couramment 40 à 55 cm)
OUVERTURE_MAX = 2.50  # au-delà, deux morceaux alignés sont deux murs distincts
BAIE_MAX = 4.50  # dans un mur épais (extérieur), une baie vitrée suivie d'une porte-fenêtre peut dépasser 2,50 m
MARGE_BATTANT = 0.04  # bande collée à la face du mur qu'on ne regarde pas (bord flou du mur)
PROFONDEUR_ARC_MAX = 1.20  # on cherche l'arc d'une porte jusqu'à 1,20 m du mur
ARC_COUVERT = 0.8  # l'arc passe devant au moins 80 % du vide
BAIE_COUVERTE = 0.9  # part du trou où l'on voit le vitrage d'une grande baie
MUR_EPAIS_MIN = 0.15  # à partir de cette épaisseur, un mur est traité comme un mur extérieur ou porteur
PASSAGE_MAX = 1.20  # deux groupes de murs séparés de moins qu'une porte font partie du même logement
GROUPE_MIN = 1.50  # longueur totale de murs d'un groupe qu'on rattache à travers un passage
VITRAGE_BOUT_MIN = 0.40  # un vitrage qui prolonge le bout libre d'un mur fait au moins 40 cm
RESSAUT_MIN = 0.08  # un ressaut (petit bout de mur collé dehors contre un mur épais) dépasse d'au moins 8 cm
RESSAUT_MAX = 0.80  # et ne dépasse pas 80 cm, ni en saillie ni en largeur (au-delà, ce serait un mur lu à part)
RESSAUT_PLEIN = 0.90  # part de son rectangle qu'il remplit (une tache ronde en remplit moins)
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
    fins = _traits_fins(traits, noir)
    bandes += _bouts_alignes(noir, traits, bandes, px_par_m)
    bandes, trous = _recoller(bandes, px_par_m, traits)
    bandes, trous = _sans_morceaux_englobes(bandes, trous, px_par_m)
    bandes, trous = _garder_le_logement(bandes, trous, px_par_m)
    bandes += _ressauts(noir, bandes, px_par_m)
    trous += _vitrages_au_bout(bandes, traits, noir, px_par_m)
    trous += _prolonger_jusqu_aux_murs(bandes, noir, traits, fins, px_par_m)
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
        trait = etiquettes[y:y + h, x:x + w] == i
        if surface < 0.5 * w * h and not _plein_par_colonnes(trait):
            continue  # pas un rectangle plein, ni des rectangles bout à bout
        for debut, fin, bord1, bord2 in _morceaux_d_epaisseur_constante(trait, px_par_m):
            bandes.append(Bande(horizontal, x + debut, x + fin, y + bord1, y + bord2))
    return bandes


def _plein_par_colonnes(trait: np.ndarray) -> bool:
    """Le trait (couché) est-il fait de rectangles pleins mis bout à bout ?

    Une cloison fine de 5 m qui se termine par un bout de mur épais de 70 cm
    n'occupe qu'une petite part de son cadre : ce n'est pas un rectangle, mais
    chaque colonne y est pleine d'une face à l'autre. Un dessin troué (texte,
    hachures, arc) ne l'est pas.
    """
    plein = trait.any(axis=0)
    haut = trait.argmax(axis=0)
    bas = trait.shape[0] - trait[::-1].argmax(axis=0)
    return bool(plein.all()) and trait.sum() >= 0.95 * (bas - haut).sum()


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


def _bouts_alignes(noir: np.ndarray, traits: np.ndarray, bandes: list[Bande], px_par_m: float) -> list[Bande]:
    """Les bouts de mur trop courts pour être lus seuls, mais alignés sur un mur déjà lu.

    Entre deux fenêtres, ou entre une porte et un angle, il ne reste souvent
    qu'un bout de mur de 15 à 30 cm (un « trumeau »), plus court que
    MORCEAU_MIN : ni le passage horizontal ni le passage vertical ne le
    gardent. Mais il a exactement les deux faces d'un mur voisin lu sur la
    même ligne, à moins d'une ouverture de distance : c'est un morceau de ce
    mur. On l'ajoute ; le recollage le réunit ensuite au reste du mur, et les
    vides entre eux deviennent des ouvertures possibles.

    Une tache isolée (photocopie, photo) peut par hasard avoir les faces d'une
    cloison : un vrai bout de mur, lui, touche toujours un autre trait du
    dessin (cadre de fenêtre, battant de porte, mur voisin).
    """
    tol = TOLERANCE * px_par_m
    fin = max(2, math.ceil(TRAIT_FIN_MAX * px_par_m))
    _, dessin, taille_dessin, _ = cv2.connectedComponentsWithStats(traits.astype(np.uint8), connectivity=8)
    logement, _ = _garder_le_logement(bandes, [], px_par_m)
    if not logement:
        return []
    rectangles = [_rectangle(b) for b in logement]
    cadre = (min(r[0] for r in rectangles), min(r[1] for r in rectangles),
             max(r[2] for r in rectangles), max(r[3] for r in rectangles))
    deja = np.zeros(noir.shape, dtype=np.uint8)
    for b in bandes:
        x0, y0, x1, y1 = (round(v) for v in _rectangle(b))
        deja[max(0, y0 - 1):y1 + 1, max(0, x0 - 1):x1 + 1] = 1
    reste = np.where(deja > 0, 0, noir).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(reste, connectivity=4)
    nouveaux: list[Bande] = []
    for x, y, w, h, surface in stats[1:]:
        if min(w, h) < fin or surface < 0.8 * w * h:
            continue  # trait fin, ou forme qui n'est pas un rectangle plein
        if taille_dessin[dessin[y + h // 2, x + w // 2], cv2.CC_STAT_AREA] < 1.5 * surface:
            continue  # tache isolée
        if x < cadre[0] - tol or x + w > cadre[2] + tol or y < cadre[1] - tol or y + h > cadre[3] + tol:
            continue  # hors des murs déjà lus : un trait des cotes ou du cartouche
        candidats = []
        for b in bandes:
            if b.horizontal:
                bord1, bord2, debut, fin_ = y, y + h, x, x + w
            else:
                bord1, bord2, debut, fin_ = x, x + w, y, y + h
            if abs(b.bord1 - bord1) > tol or abs(b.bord2 - bord2) > tol:
                continue  # pas les mêmes faces
            if b.epaisseur < CLOISON_MIN * px_par_m:
                continue  # un « mur » si fin qu'il est sans doute un reste de trait
            ecart = max(b.debut - fin_, debut - b.fin)
            if ecart > OUVERTURE_MAX * px_par_m:
                continue
            candidats.append((ecart, b, debut, fin_))
        if candidats:
            _, b, debut, fin_ = min(candidats, key=lambda c: c[0])
            nouveaux.append(Bande(b.horizontal, float(debut), float(fin_), b.bord1, b.bord2))
    return nouveaux


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


def _traits_fins(traits: np.ndarray, noir: np.ndarray) -> np.ndarray:
    """Les traits fins seulement (battants de porte, cadres de fenêtre) : les traits sans les murs."""
    fins = traits.copy()
    fins[cv2.dilate(noir, np.ones((5, 5), np.uint8)) > 0] = 0  # murs un peu élargis, pour leurs bords flous
    return fins


def _ouverture_dessinee(
    traits: np.ndarray, fins: np.ndarray, horizontal: bool, debut: float, fin: float,
    bord1: float, bord2: float, px_par_m: float, vitrages_min: int = 1,
) -> bool:
    """Une porte (son battant) ou une fenêtre (son cadre, le long du mur) est-elle dessinée dans ce vide ?"""
    from moteur.lecture_ouvertures import _a_un_battant, _traits_le_long

    t, f = (traits, fins) if horizontal else (traits.T, fins.T)
    return (_a_un_battant(f, debut, fin, bord1, bord2, px_par_m)
            or _traits_le_long(t, debut, fin, bord1, bord2) >= vitrages_min
            or _battant_dans_le_vide(f, debut, fin, bord1, bord2, px_par_m))


def _battant_dans_le_vide(
    fins: np.ndarray, debut: float, fin: float, bord1: float, bord2: float, px_par_m: float
) -> bool:
    """Le battant d'une porte balaie-t-il le vide, d'un côté du mur ou de l'autre ?

    Le battant ne part pas toujours d'un bord du vide (un petit bout de mur non
    lu l'élargit), et il est souvent dessiné ouvert à plat contre le mur voisin,
    où il se confond avec lui. Mais l'arc qu'il décrit, lui, passe devant tout le
    vide. Dans un passage ouvert, il n'y a rien devant. On regarde donc, de
    chaque côté du mur, une bande aussi profonde que le vide est large : si des
    traits fins passent devant presque tout le vide (ARC_COUVERT), c'est une porte.
    Les traits droits parallèles au mur (ligne de cote) n'y comptent pas.
    """
    h, w = fins.shape
    c0, c1 = max(0, round(debut) + 2), min(w, round(fin) - 1)
    if c1 - c0 < 3:
        return False
    marge = max(2, round(MARGE_BATTANT * px_par_m))
    profondeur = min(fin - debut, PROFONDEUR_ARC_MAX * px_par_m)
    for r0, r1 in ((bord1 - marge - profondeur, bord1 - marge), (bord2 + marge, bord2 + marge + profondeur)):
        r0, r1 = max(0, round(r0)), min(h, round(r1))
        if r1 - r0 < 3:
            continue
        zone = fins[r0:r1, c0:c1] > 0
        zone[zone.mean(axis=1) >= 0.5] = False  # un trait droit le long du mur (ligne de cote, vitrage) n'est pas un arc
        if zone.any(axis=0).mean() >= ARC_COUVERT:
            return True
    return False


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

    Les murs d'un logement se tiennent tous entre eux, à une porte près : un
    groupe de pièces peut n'être relié au reste que par des portes dont le
    bout de mur est trop court pour être lu. Un élément isolé (flèche du
    nord, cartouche, légende) est plus loin et n'en fait pas partie. Un trait
    seul (battant de porte, meuble) ne passe pas une porte : seul un vrai
    groupe de murs (GROUPE_MIN de long) est rattaché à travers un passage.
    """
    contact, passage = TOLERANCE * px_par_m, PASSAGE_MAX * px_par_m

    def rectangle(b: Bande) -> tuple[float, float, float, float]:
        return (b.debut, b.bord1, b.fin, b.bord2) if b.horizontal else (b.bord1, b.debut, b.bord2, b.fin)

    def proches(a: Bande, b: Bande, tol: float) -> bool:
        ax0, ay0, ax1, ay1 = rectangle(a)
        bx0, by0, bx1, by1 = rectangle(b)
        return ax0 <= bx1 + tol and bx0 <= ax1 + tol and ay0 <= by1 + tol and by0 <= ay1 + tol

    groupe_de = list(range(len(bandes)))

    def chef(i: int) -> int:
        while groupe_de[i] != i:
            i = groupe_de[i]
        return i

    def longueurs() -> dict[int, float]:
        tailles: dict[int, float] = {}
        for i, b in enumerate(bandes):
            tailles[chef(i)] = tailles.get(chef(i), 0) + (b.fin - b.debut)
        return tailles

    for i in range(len(bandes)):
        for j in range(i + 1, len(bandes)):
            if proches(bandes[i], bandes[j], contact):
                groupe_de[chef(j)] = chef(i)
    vrais_groupes = {g for g, n in longueurs().items() if n >= GROUPE_MIN * px_par_m}
    for i in range(len(bandes)):
        for j in range(i + 1, len(bandes)):
            if chef(i) in vrais_groupes and chef(j) in vrais_groupes and proches(bandes[i], bandes[j], passage):
                groupe_de[chef(j)] = chef(i)
                vrais_groupes.add(chef(i))
    if not bandes:
        return [], []
    tailles = longueurs()
    garde = max(tailles, key=tailles.get)
    nouveaux = {i: n for n, i in enumerate(i for i in range(len(bandes)) if chef(i) == garde)}
    return (
        [bandes[i] for i in nouveaux],
        [(nouveaux[i], a, b) for i, a, b in trous if i in nouveaux],
    )


def _ressauts(noir: np.ndarray, bandes: list[Bande], px_par_m: float) -> list[Bande]:
    """Les petits bouts de mur collés à l'extérieur d'un mur épais, qui dépassent du logement.

    Au coin d'un logement, ou au bout d'un mur mitoyen, le mur extérieur porte
    souvent un ressaut : un bloc de mur plein de 10 à 50 cm qui dépasse vers
    l'extérieur (bout du mur du voisin, poteau, about de balcon). Il est trop
    court pour être lu comme un mur, mais il fait partie des dimensions hors
    tout du logement : sans lui, la façade est lue 20 à 40 cm trop courte.
    On le lit comme un petit mur perpendiculaire, de l'axe du mur épais
    jusqu'au bout du ressaut. Seul ce qui dépasse du cadre des murs déjà lus
    compte : un bloc à l'intérieur (gaine, placard) ne change pas les
    dimensions et serait plus souvent un meuble ou une tache.
    """
    if not bandes:
        return []
    tol = TOLERANCE * px_par_m
    rectangles = [_rectangle(b) for b in bandes]
    cadre = (min(r[0] for r in rectangles), min(r[1] for r in rectangles),
             max(r[2] for r in rectangles), max(r[3] for r in rectangles))
    deja = np.zeros(noir.shape, dtype=np.uint8)
    for x0, y0, x1, y1 in rectangles:
        deja[max(0, round(y0)):round(y1) + 1, max(0, round(x0)):round(x1) + 1] = 1
    mini, maxi = RESSAUT_MIN * px_par_m, RESSAUT_MAX * px_par_m
    # L'ouverture efface les liserés de mur laissés hors des rectangles (face qui ondule d'un pixel).
    k = max(3, round(mini))
    reste = cv2.morphologyEx(np.where(deja > 0, 0, noir).astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(reste, connectivity=4)
    nouveaux: list[Bande] = []
    for x, y, w, h, surface in stats[1:]:
        if min(w, h) < mini or max(w, h) > maxi or surface < RESSAUT_PLEIN * w * h:
            continue  # trop petit, trop grand, ou pas un bloc plein
        x1, y1 = x + w, y + h
        if not (x < cadre[0] - tol or x1 > cadre[2] + tol or y < cadre[1] - tol or y1 > cadre[3] + tol):
            continue  # ne dépasse pas du logement
        for b in bandes:
            if b.epaisseur < MUR_EPAIS_MIN * px_par_m:
                continue  # seulement contre un mur épais (extérieur ou porteur)
            debut, fin_, bord1, bord2 = (x, x1, y, y1) if b.horizontal else (y, y1, x, x1)
            if debut < b.debut - tol or fin_ > b.fin + tol:
                continue  # pas tout entier le long de ce mur
            if abs(bord1 - b.bord2) <= tol:  # collé à sa face « 2 » (dessous ou droite)
                bout = bord2
            elif abs(bord2 - b.bord1) <= tol:  # collé à sa face « 1 » (dessus ou gauche)
                bout = bord1
            else:
                continue
            a, z = sorted((b.axe, float(bout)))
            nouveaux.append(Bande(not b.horizontal, a, z, float(debut), float(fin_)))
            break
    return nouveaux


def _vitrages_au_bout(bandes: list[Bande], traits: np.ndarray, noir: np.ndarray, px_par_m: float) -> list[tuple[int, float, float]]:
    """Prolonge un mur épais dont le bout libre se continue par une fenêtre (fenêtre d'angle, bow-window).

    D'habitude, une fenêtre est posée entre deux morceaux de mur, et le recollage
    la retrouve. Mais une fenêtre d'angle part du bout du mur et va jusqu'au coin
    sans morceau de mur après elle : le mur semble s'arrêter net, et le logement
    est lu trop court de toute la largeur de la fenêtre. On reconnaît la fenêtre
    à son cadre dessiné dans le prolongement du mur : un trait fin le long de
    chacune des deux faces, sans coupure. Le mur est prolongé jusqu'au bout du
    cadre, et la fenêtre devient une ouverture possible. Si un mur reprend juste
    après le cadre, c'est une fenêtre ordinaire entre deux murs : on n'y touche
    pas. Modifie les bandes ; renvoie les nouveaux trous.
    """
    tol = TOLERANCE * px_par_m
    nouveaux: list[tuple[int, float, float]] = []
    for n, mur in enumerate(bandes):
        if mur.epaisseur < MUR_EPAIS_MIN * px_par_m:
            continue
        t = traits if mur.horizontal else traits.T
        plein = noir if mur.horizontal else noir.T
        r0, r1 = round(mur.bord1), round(mur.bord2)
        if r0 < 0 or r1 >= t.shape[0]:
            continue
        # Le cadre de la fenêtre : un trait fin sur chaque face (à 2 pixels près), et du blanc entre les deux
        # (sinon, c'est un autre mur, plein, dans le prolongement).
        face1 = t[max(0, r0 - 2):r0 + 3].max(axis=0)
        face2 = t[r1 - 2:r1 + 3].max(axis=0)
        traits_des_faces = (face1 > 0) & (face2 > 0)
        cadre = traits_des_faces & (t[r0 + 3:r1 - 2].mean(axis=0) < 0.5)
        for cote in (-1, 1):
            bout = mur.debut if cote < 0 else mur.fin
            if any(_touche_le_bout(mur, b, bout, cote, tol) for b in bandes if b is not mur):
                continue  # le mur s'arrête sur un autre mur : ce n'est pas un bout libre
            c = round(bout) + cote * 2
            longueur = 0
            while 0 <= c < cadre.size and cadre[c] and longueur <= BAIE_MAX * px_par_m:
                c += cote
                longueur += 1
            if not VITRAGE_BOUT_MIN * px_par_m <= longueur <= BAIE_MAX * px_par_m:
                continue
            for _ in range(round(tol)):  # le trait qui ferme le cadre, en travers
                if not (0 <= c < cadre.size and traits_des_faces[c]):
                    break
                c += cote
            apres = plein[r0:r1 + 1, max(0, min(c, c + cote * round(3 * tol))):max(c, c + cote * round(3 * tol)) + 1]
            if apres.size and (apres > 0).mean() >= 0.5:
                continue  # un mur reprend après la fenêtre : le bout n'était pas libre
            nouveau_bout = float(c - cote)
            if cote > 0:
                nouveaux.append((n, mur.fin, nouveau_bout))
                mur.fin = nouveau_bout
            else:
                nouveaux.append((n, nouveau_bout, mur.debut))
                mur.debut = nouveau_bout
    return nouveaux


def _touche_le_bout(mur: Bande, autre: Bande, bout: float, cote: int, tol: float) -> bool:
    """Un autre mur commence-t-il au bout du mur (en travers, ou dans son prolongement) ?"""
    if autre.horizontal != mur.horizontal:
        return autre.debut - tol <= mur.axe <= autre.fin + tol and autre.bord1 - tol <= bout + cote * tol <= autre.bord2 + tol
    return abs(autre.axe - mur.axe) <= tol and autre.debut - tol <= bout + cote * 2 * tol <= autre.fin + tol


def _prolonger_jusqu_aux_murs(
    bandes: list[Bande], noir: np.ndarray, traits: np.ndarray, fins: np.ndarray, px_par_m: float
) -> list[tuple[int, float, float]]:
    """Prolonge jusqu'au mur voisin un mur qui s'arrête dans le vide.

    Quand une porte est percée tout près du bout d'une cloison, le petit bout
    de cloison qui reste (10 à 30 cm) est trop court pour être lu comme un mur :
    la cloison semble s'arrêter dans le vide, la pièce n'est plus fermée et se
    fond avec sa voisine. Dans un logement, une cloison va toujours d'un mur à
    un autre : on la prolonge donc jusqu'au premier mur perpendiculaire qu'elle
    rencontre (à moins de OUVERTURE_MAX), et l'espace vide devient une
    ouverture possible (la porte). Modifie les bandes ; renvoie les nouveaux trous.

    Mais un vrai logement a aussi des passages ouverts : une cloison peut
    s'arrêter net au milieu d'une pièce (entrée ouverte sur le séjour, coin
    cuisine). On ne prolonge donc que si une porte (son battant) ou une
    fenêtre (son cadre) est dessinée dans le vide ; sinon, le vide reste ouvert.
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
            if not _ouverture_dessinee(traits, fins, mur.horizontal, debut_trou, fin_trou, mur.bord1, mur.bord2, px_par_m, 2):
                continue  # ni porte ni fenêtre dessinée : un passage ouvert
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
    image = lire_image(args.plan, cv2.IMREAD_GRAYSCALE)
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
