"""Le sol « mis à plat » : une photo du client redressée en vue de dessus (brique photos, 09/11/2026).

Pourquoi : sur une photo, le parquet est vu en biais et écrasé, de plus en plus petit au loin. Pour reconnaître un point de
Hongrie, des lames droites ou des carreaux, il vaut mieux le regarder comme sur un plan : vu de dessus, à une échelle connue
(1 cm par pixel par défaut). La caméra de la photo (moteur/camera_photo.py) dit où tombe chaque point du sol sur la photo :
on va donc chercher, pour chaque point d'une grille posée sur le sol, la couleur de la photo à cet endroit.

Ce que chaque photo ne peut pas montrer est écarté :
- ce qui est hors de la pièce de l'appareil ou caché par un de ses murs (le rayon de l'appareil au point du sol doit rester
  dans la pièce : un séjour en L cache une partie de lui-même) ;
- ce qui est derrière l'appareil, hors du cadre, ou trop loin (la « finesse » = pixels de la photo par cm de sol ; sous
  FINESSE_MIN, le motif n'est plus lisible : au loin, une lame de 7 cm fait moins de 2 pixels).
Les meubles, eux, ne sont pas connus : ils restent sur l'image à plat (étirés vers le fond). Les autres photos les compensent
(chaque endroit est vu par plusieurs photos, voir `assembler`).

Repère : celui du logement (mètres, x vers la droite, y vers le haut du plan). Ligne 0 de l'image à plat = y le plus grand
(comme un plan : le haut de l'image est le haut du plan).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from moteur.camera_photo import axes

RESOLUTION_M = 0.01  # 1 cm de sol par pixel de l'image à plat
FINESSE_MIN = 0.35  # pixels de la photo par cm de sol en dessous desquels le motif n'est plus lisible


@dataclass
class SolAPlat:
    """Une photo mise à plat. `image` (H, W, 3, uint8, RGB), `finesse` (H, W, float32 ; 0 = point non vu),
    `origine` = (x, y) du coin haut gauche (x mini, y maxi), `resolution` en m par pixel."""

    image: np.ndarray
    finesse: np.ndarray
    origine: tuple[float, float]
    resolution: float
    # d'où vient cette image (rempli par photos_a_plat) : la photo d'origine (RGB), sa caméra, la pièce et le point de vue
    photo: np.ndarray | None = None
    camera: list | None = None
    piece: dict | None = None
    point_de_vue: tuple | None = None

    def vers_sol(self, ligne, colonne):
        """(x, y) en mètres du centre d'un pixel de l'image à plat."""
        return (self.origine[0] + (np.asarray(colonne) + 0.5) * self.resolution,
                self.origine[1] - (np.asarray(ligne) + 0.5) * self.resolution)


def grille(emprise, resolution: float = RESOLUTION_M):
    """Centres des pixels d'une image à plat couvrant `emprise` = (x0, y0, x1, y1) : (X, Y) en mètres, et l'origine."""
    x0, y0, x1, y1 = emprise
    largeur, hauteur = int(np.ceil((x1 - x0) / resolution)), int(np.ceil((y1 - y0) / resolution))
    colonnes, lignes = np.meshgrid(np.arange(largeur), np.arange(hauteur))
    return x0 + (colonnes + 0.5) * resolution, y1 - (lignes + 0.5) * resolution, (x0, y1)


def projeter_sol(X, Y, cam):
    """Pour des points du sol (z = 0) : (u, v) sur la photo, profondeur, et finesse (pixels de la photo par cm de sol)."""
    x, y, z, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    rx, ry, rz = X - x, Y - y, -z
    p = rx * vue[0] + ry * vue[1] + rz * vue[2]
    sur = np.where(p > 1e-6, p, np.nan)
    u = u0 + f * (rx * droite[0] + ry * droite[1] + rz * droite[2]) / sur
    v = v0 - f * (rx * haut[0] + ry * haut[1] + rz * haut[2]) / sur
    # Un carré de sol de 1 cm vu à la distance d, sous l'angle de plongée a (sin a = z / d), fait f * 0,01 / p pixels de large
    # et f * 0,01 * sin(a) / p de haut : la finesse retenue est le plus petit des deux (le sens écrasé).
    d = np.sqrt(rx * rx + ry * ry + rz * rz)
    finesse = f * 0.01 / sur * np.minimum(1.0, z / np.maximum(d, 1e-6))
    return u, v, p, finesse


def dans_polygone(X, Y, contour) -> np.ndarray:
    """Points (X, Y) à l'intérieur du contour (règle pair-impair)."""
    c = np.asarray(contour, float)
    dedans = np.zeros(np.shape(X), bool)
    for (x1, y1), (x2, y2) in zip(c, np.roll(c, -1, axis=0)):
        if y1 == y2:
            continue
        croise = (y1 > Y) != (y2 > Y)
        dedans ^= croise & (X < (x2 - x1) * (Y - y1) / (y2 - y1) + x1)
    return dedans


def visibles_depuis(X, Y, point, contour) -> np.ndarray:
    """Points du sol dont le segment depuis `point` (l'appareil, vu de dessus) ne traverse aucun bord du contour."""
    px, py = point
    c = np.asarray(contour, float)
    cache = np.zeros(np.shape(X), bool)
    dx, dy = X - px, Y - py
    for (ax, ay), (bx, by) in zip(c, np.roll(c, -1, axis=0)):
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        ok = np.abs(den) > 1e-12
        den = np.where(ok, den, 1.0)
        t = ((ax - px) * ey - (ay - py) * ex) / den  # le long du rayon (0 = appareil, 1 = point du sol)
        s = ((ax - px) * dy - (ay - py) * dx) / den  # le long du bord
        cache |= ok & (t > 1e-6) & (t < 1 - 1e-3) & (s >= 0) & (s <= 1)
    return ~cache


def mettre_a_plat(photo: np.ndarray, cam, contour_piece, emprise=None, resolution: float = RESOLUTION_M,
                  finesse_min: float = FINESSE_MIN, point_de_vue=None) -> SolAPlat:
    """Met à plat le sol de la pièce `contour_piece` vu sur `photo` (RGB) par la caméra `cam` (8 nombres, camera_photo).

    point_de_vue : d'où partent les rayons pour savoir ce que cachent les murs (par défaut l'appareil). Pour une photo prise
    depuis l'embrasure d'une porte, l'appareil est sur le bord de la pièce : on prend un point juste à l'intérieur."""
    c = np.asarray(contour_piece, float)
    if emprise is None:
        emprise = (c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max())
    X, Y, origine = grille(emprise, resolution)
    u, v, p, finesse = projeter_sol(X, Y, cam)
    h, w = photo.shape[:2]
    vu = (np.isfinite(u) & (p > 0.3) & (u >= 0) & (u <= w - 1) & (v >= 0) & (v <= h - 1) & (finesse >= finesse_min)
          & dans_polygone(X, Y, c) & visibles_depuis(X, Y, point_de_vue or (float(cam[0]), float(cam[1])), c))
    carte_u = np.where(vu, u, -1).astype(np.float32)
    carte_v = np.where(vu, v, -1).astype(np.float32)
    image = cv2.remap(photo, carte_u, carte_v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    image[~vu] = 0
    return SolAPlat(image, np.where(vu, finesse, 0.0).astype(np.float32), origine, resolution)


def assembler(vues: list[SolAPlat]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Une seule image du sol à partir de plusieurs photos à plat de MÊME emprise et résolution : chaque point prend la
    photo qui le voit le plus finement. Rend (image, finesse, n° de la photo retenue ou -1)."""
    finesses = np.stack([v.finesse for v in vues])
    meilleure = finesses.argmax(axis=0)
    finesse = finesses.max(axis=0)
    image = np.zeros_like(vues[0].image)
    for k, v in enumerate(vues):
        m = (meilleure == k) & (finesse > 0)
        image[m] = v.image[m]
    return image, finesse, np.where(finesse > 0, meilleure, -1)


MARGE_M = 0.3


def aire(contour) -> float:
    c = np.asarray(contour, float)
    return abs(float((c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1]).sum())) / 2


def piece_de(point, pieces: list[dict]) -> dict | None:
    x, y = point
    for p in pieces:
        if dans_polygone(np.array([x]), np.array([y]), p["contour"])[0]:
            return p
    return None


def piece_de_l_appareil(cam, pieces: list[dict]):
    """La pièce où se tient l'appareil et le point d'où il voit ; sur un seuil de porte (photo prise depuis l'embrasure),
    la pièce qu'il regarde et un point juste à l'intérieur."""
    a = np.radians(cam[3])
    for avance in (0.0, 0.2, 0.4, 0.6, 0.8):
        point = (float(cam[0] + avance * np.cos(a)), float(cam[1] + avance * np.sin(a)))
        piece = piece_de(point, pieces)
        if piece is not None:
            return piece, point
    return None, None


def emprise_du_logement(logement: dict, marge: float = MARGE_M):
    tous = np.array([pt for p in logement["pieces"] for pt in p["contour"]], float)
    return (tous[:, 0].min() - marge, tous[:, 1].min() - marge, tous[:, 0].max() + marge, tous[:, 1].max() + marge)


def photos_a_plat(releve: dict, logement: dict, racine, resolution: float = RESOLUTION_M, journal=print):
    """Toutes les photos calées d'un relevé (format cameras-photos.json ; clé « fichier » facultative, « {nom}.png » par
    défaut) mises à plat sur l'emprise du logement entier. Rend [(nom, id de la pièce, SolAPlat)]."""
    from pathlib import Path

    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image

    emprise = emprise_du_logement(logement)
    dossier = Path(racine) / releve["photos"]
    modele = releve.get("fichier", "{nom}.png")
    sorties = []
    for nom, d in releve["cameras"].items():
        cam = camera_depuis_dict(d["camera"])
        piece, point = piece_de_l_appareil(cam, logement["pieces"])
        if piece is None:
            journal(f"  {nom} : appareil hors des pièces, photo écartée")
            continue
        photo = lire_image(dossier / modele.format(nom=nom))
        if photo is None:
            raise FileNotFoundError(dossier / modele.format(nom=nom))
        rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
        vue = mettre_a_plat(rgb, cam, piece["contour"], emprise, resolution, point_de_vue=point)
        vue.photo, vue.camera, vue.piece, vue.point_de_vue = rgb, list(cam), piece, point
        journal(f"  {nom} : pièce {piece['id']}, {(vue.finesse > 0).sum() * resolution ** 2:.1f} m² de sol vus")
        sorties.append((nom, piece["id"], vue))
    return sorties
