"""Nettoyer l'image d'un plan avant de la lire (étape 5c).

Les plans des clients ne sont pas propres : photocopie grise, tache, pli,
photo prise au téléphone avec une lumière inégale. La lecture (lecture_plan.py)
suppose un dessin foncé sur un papier blanc. Ce module remet l'image dans cet
état, en trois temps :

1. Détourer la feuille : sur une photo, la feuille est posée sur une table
   plus sombre et vue un peu en biais. On cherche ses quatre coins et on la
   remet à plat, comme un scanner (« redresser la perspective »).
2. Égaliser le fond : on estime la couleur du papier partout sur la feuille
   (en effaçant le dessin), puis on divise l'image par ce fond. Le papier
   redevient blanc partout, même sous une ombre, une tache ou un pli.
3. Rendre le contraste : le trait le plus foncé redevient noir, pour qu'une
   photocopie pâle ressemble à un dessin net.

Sur un plan déjà propre, l'image ne change presque pas.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

ECART_TABLE = 35  # le tour de l'image est plus sombre que le milieu d'au moins ce niveau de gris : c'est une photo
FEUILLE_MIN = 0.30  # la feuille occupe au moins 30 % de la photo
NOIR_PROPRE = 8
COIN_ECART = 8  # en pixels : les points de bord retenus pour ajuster un côté de la feuille  # un trait déjà aussi foncé n'a pas besoin qu'on renforce le contraste


@dataclass
class Nettoyage:
    """Ce qui a été fait à l'image (pour l'expliquer dans la page de vérification)."""

    feuille_detouree: bool = False
    fond_egalise: bool = False
    contraste_rendu: bool = False
    etirement_hauteur: float = 1.0  # image étirée en hauteur pour que l'échelle soit la même dans les deux sens


def nettoyer(gris: np.ndarray) -> tuple[np.ndarray, Nettoyage]:
    """L'image du plan, en niveaux de gris, remise à plat sur un papier blanc."""
    fait = Nettoyage()
    feuille = detourer_feuille(gris)
    if feuille is not None:
        gris, fait.feuille_detouree = feuille, True
    gris, fait.fond_egalise = egaliser_fond(gris)
    gris, fait.contraste_rendu = rendre_contraste(gris)
    return gris, fait


def detourer_feuille(gris: np.ndarray) -> np.ndarray | None:
    """Sur une photo, la feuille remise à plat ; None si l'image n'est pas une photo de feuille."""
    h, w = gris.shape
    bord = max(4, round(0.02 * min(h, w)))
    tour = np.concatenate([gris[:bord].ravel(), gris[-bord:].ravel(), gris[:, :bord].ravel(), gris[:, -bord:].ravel()])
    milieu = gris[h // 4:3 * h // 4, w // 4:3 * w // 4]
    if np.median(milieu) - np.median(tour) < ECART_TABLE:
        return None  # pas de table autour : c'est un scan ou un dessin

    # Le bord de la feuille : le plus grand contour net de l'image. On suit les bords
    # (passage brusque du clair au sombre) plutôt que la clarté : une ombre douce
    # assombrit la feuille sans créer de bord, et ne la coupe donc pas.
    flou = cv2.GaussianBlur(gris, (0, 0), 2)
    fins = cv2.Canny(flou, 20, 60)
    bords = cv2.dilate(fins, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(bords, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max((cv2.convexHull(c) for c in contours), key=cv2.contourArea)
    if cv2.contourArea(contour) < FEUILLE_MIN * h * w:
        return None
    coins = _quatre_coins(contour)
    if coins is None:
        return None
    coins = _affiner_coins(coins, fins)

    # Les coins dans l'ordre : haut-gauche, haut-droite, bas-droite, bas-gauche.
    somme, diff = coins.sum(axis=1), np.diff(coins, axis=1).ravel()
    hg, bd, hd, bg = coins[np.argmin(somme)], coins[np.argmax(somme)], coins[np.argmin(diff)], coins[np.argmax(diff)]
    largeur = round((np.linalg.norm(hd - hg) + np.linalg.norm(bd - bg)) / 2)
    hauteur = round((np.linalg.norm(bg - hg) + np.linalg.norm(bd - hd)) / 2)
    # On rogne 1 % autour pour ne pas garder un liseré de table.
    rogne = round(0.01 * min(largeur, hauteur))
    source = np.float32([hg, hd, bd, bg])
    cible = np.float32([[-rogne, -rogne], [largeur + rogne, -rogne], [largeur + rogne, hauteur + rogne], [-rogne, hauteur + rogne]])
    matrice = cv2.getPerspectiveTransform(source, cible)
    return cv2.warpPerspective(gris, matrice, (largeur, hauteur), flags=cv2.INTER_CUBIC, borderValue=255)


def egaliser_fond(gris: np.ndarray) -> tuple[np.ndarray, bool]:
    """Divise l'image par la couleur du papier, estimée partout en effaçant le dessin."""
    petit = cv2.resize(gris, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    # Une « fermeture » efface tout ce qui est foncé et plus petit que le gabarit : les murs, les textes.
    # Le gabarit (31 pixels ici, environ 120 sur l'image entière) doit couvrir l'angle de deux murs
    # extérieurs épais de 55 cm ; plus petit, l'angle serait pris pour du papier sale et blanchi.
    gabarit = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    fond = cv2.medianBlur(cv2.morphologyEx(petit, cv2.MORPH_CLOSE, gabarit), 5)
    fond = cv2.resize(fond, (gris.shape[1], gris.shape[0]), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    if np.percentile(fond, 1) >= 250:
        return gris, False  # le papier est déjà blanc partout
    egal = gris.astype(np.float32) * 255 / np.maximum(fond, 1)
    return np.clip(egal, 0, 255).astype(np.uint8), True


def rendre_contraste(gris: np.ndarray) -> tuple[np.ndarray, bool]:
    """Étire les gris pour que le trait le plus foncé redevienne noir et le papier blanc."""
    noir = float(np.percentile(gris, 0.5))
    blanc = float(np.percentile(gris, 60))  # le papier occupe bien plus de la moitié de la feuille
    if noir <= NOIR_PROPRE or blanc - noir < 40:
        return gris, False
    etire = (gris.astype(np.float32) - noir) * 255 / (blanc - noir)
    return np.clip(etire, 0, 255).astype(np.uint8), True


def _affiner_coins(coins: np.ndarray, bords: np.ndarray) -> np.ndarray:
    """Place les coins au pixel près : chaque côté de la feuille est une droite ajustée sur ses points de bord.

    Les coins trouvés d'abord sont approximatifs (à quelques pixels) ; or une erreur
    de 3 pixels sur un coin suffit à décaler les murs d'un bout à l'autre du plan.
    """
    ys, xs = np.nonzero(bords)
    points = np.stack([xs, ys], axis=1).astype(np.float32)
    # Les coins dans l'ordre du tour de la feuille.
    centre = coins.mean(axis=0)
    ordre = np.argsort(np.arctan2(coins[:, 1] - centre[1], coins[:, 0] - centre[0]))
    coins = coins[ordre]
    droites = []
    for a, b in zip(coins, np.roll(coins, -1, axis=0)):
        cote = b - a
        longueur = float(np.linalg.norm(cote))
        u = cote / longueur
        n = np.array([-u[1], u[0]])
        rel = points - a
        le_long = rel @ u
        ecart = np.abs(rel @ n)
        # Les points de bord près de ce côté, sans ses deux bouts (où les côtés se mélangent).
        proches = points[(ecart <= COIN_ECART) & (le_long > 0.1 * longueur) & (le_long < 0.9 * longueur)]
        if len(proches) < 20:
            return coins
        vx, vy, x0, y0 = cv2.fitLine(proches, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        droites.append((np.array([x0, y0]), np.array([vx, vy])))
    affines = []
    for (p1, d1), (p2, d2) in zip(np.roll(droites, 1, axis=0), droites):
        # Intersection de deux côtés voisins : p1 + t·d1 = p2 + s·d2.
        matrice = np.array([d1, -d2]).T
        if abs(np.linalg.det(matrice)) < 1e-6:
            return coins
        t = np.linalg.solve(matrice, p2 - p1)[0]
        affines.append(p1 + t * d1)
    affines = np.float32(affines)
    if np.abs(affines - coins).max() > 3 * COIN_ECART:
        return coins  # l'ajustement s'est égaré : on garde les coins approximatifs
    return affines


def _quatre_coins(contour: np.ndarray) -> np.ndarray | None:
    """Simplifie le contour de la feuille en un quadrilatère (ses quatre coins)."""
    perimetre = cv2.arcLength(contour, True)
    for precision in (0.01, 0.02, 0.03, 0.05):
        approche = cv2.approxPolyDP(contour, precision * perimetre, True)
        if len(approche) == 4:
            return approche.reshape(4, 2).astype(np.float32)
    return None
