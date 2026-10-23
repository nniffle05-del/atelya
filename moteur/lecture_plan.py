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

Limites de la version 0.1 : murs droits et perpendiculaires seulement ;
plan propre (dessin d'architecte, export PDF, scan net) ; l'échelle est
donnée (sa lecture automatique viendra à l'étape 3c).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Les tailles sont en mètres et converties en pixels avec l'échelle.
TRAIT_FIN_MAX = 0.06  # un trait plus fin que 6 cm sur le plan n'est pas un mur
MORCEAU_MIN = 0.32  # longueur minimale d'un morceau de mur
OUVERTURE_MAX = 2.50  # au-delà, deux morceaux alignés sont deux murs distincts
TOLERANCE = 0.03  # écart admis entre deux morceaux « alignés »
INCLINAISON_MAX = 5.0  # degrés : inclinaison maximale corrigée

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


def lire_murs(image: np.ndarray, px_par_m: float) -> Lecture:
    """Trouve les murs sur l'image d'un plan (niveaux de gris ou couleur)."""
    gris = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    noir = _traits_epais(gris, px_par_m)
    angle = _inclinaison(noir)
    if abs(angle) > 0.01:
        gris = _tourner(gris, angle, fond=255)
        noir = _traits_epais(gris, px_par_m)

    bandes = _bandes(noir, px_par_m, horizontal=True) + _bandes(noir, px_par_m, horizontal=False)
    bandes, trous = _recoller(bandes, px_par_m)
    bandes, trous = _garder_le_logement(bandes, trous, px_par_m)
    if not bandes:
        raise ValueError("aucun mur trouvé sur ce plan")
    murs = [_regler_les_bouts(b, bandes, px_par_m) for b in bandes]

    verticales = [b for b in bandes if not b.horizontal]
    horizontales = [b for b in bandes if b.horizontal]
    if not verticales or not horizontales:
        raise ValueError("impossible de trouver le contour du logement")
    gauche = min(verticales, key=lambda b: b.bord1)
    bas = max(horizontales, key=lambda b: b.bord2)
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
    k = max(3, round(TRAIT_FIN_MAX * px_par_m)) | 1  # taille impaire
    return cv2.morphologyEx(noir, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))


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
    """Les morceaux de murs dans une direction, chacun mesuré par son rectangle."""
    longueur = max(3, round(MORCEAU_MIN * px_par_m))
    taille = (longueur, 1) if horizontal else (1, longueur)
    sens = cv2.morphologyEx(masque, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, taille))
    n, _, stats, _ = cv2.connectedComponentsWithStats(sens, connectivity=4)
    bandes = []
    for x, y, w, h, surface in stats[1:]:
        if surface < 0.5 * w * h:
            continue  # pas un rectangle plein
        if horizontal:
            bandes.append(Bande(True, x, x + w, y, y + h))
        else:
            bandes.append(Bande(False, y, y + h, x, x + w))
    return bandes


def _recoller(bandes: list[Bande], px_par_m: float) -> tuple[list[Bande], list[tuple[int, float, float]]]:
    """Recolle les morceaux alignés d'un même mur ; les trous entre eux sont des ouvertures possibles."""
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
                if trou > OUVERTURE_MAX * px_par_m:
                    continue
                if trou > 0:
                    trous.append((len(resultat), mur.fin, b.debut))
                mur = Bande(horizontal, min(mur.debut, b.debut), max(mur.fin, b.fin),
                            min(mur.bord1, b.bord1), max(mur.bord2, b.bord2))
                restants.remove(b)
            resultat.append(mur)
    return resultat, trous


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
            if au_bout:
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
    parser = argparse.ArgumentParser(description="Lit les murs d'un plan et écrit un logement.json proposé.")
    parser.add_argument("plan", help="image du plan (PNG ou JPG)")
    parser.add_argument("sortie", help="fichier logement.json à écrire")
    parser.add_argument("--echelle", type=float, required=True, help="pixels par mètre (ex. 100)")
    parser.add_argument("--projet", default="PLAN-LU", help="nom du projet")
    args = parser.parse_args()
    image = cv2.imread(args.plan, cv2.IMREAD_GRAYSCALE)
    if image is None:
        sys.exit(f"Échec : image illisible ({args.plan})")
    try:
        lecture = lire_murs(image, args.echelle)
    except ValueError as erreur:
        sys.exit(f"Échec : {erreur}")
    logement = logement_depuis_lecture(lecture, args.echelle, args.projet)
    Path(args.sortie).write_text(json.dumps(logement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(lecture.murs)} murs trouvés (plan redressé de {lecture.angle}°) → {args.sortie}")


if __name__ == "__main__":
    main()
