"""Rapprocher la couleur d'une matière de ce que montre une photo du client (B2-3, 08/11/2026).

Pourquoi : un parquet de la bibliothèque a le bon dessin (lames, chevrons) mais rarement la même couleur que celui du
client. On mesure donc la couleur du sol sur la photo, et on calcule une « teinte » : trois nombres (rouge, vert, bleu) par
lesquels Blender multiplie la couleur de la matière (champ `teinte` du sol de la pièce, voir moteur/logement.py).

Le piège : une photo d'annonce est éclaircie, assombrie ou réchauffée par le photographe. On ne prend donc pas la couleur
du sol telle quelle : on la compare à celle d'un MUR BLANC de la même photo, qui sert d'étalon (le mur blanc de la photo vaut
notre peinture blanche). Exemple : sol (0,24 ; 0,11 ; 0,05) et mur (0,37 ; 0,39 ; 0,40) → le sol renvoie 0,24 / 0,40 × 0,86 de
la lumière rouge, soit 0,52.

Pour l'instant, les zones (un morceau de sol, un morceau de mur blanc) sont choisies à la main ; plus tard, Atelya les
trouvera seul (brique photos, temps 2 de B2). Tout est calculé en lumière « linéaire » (les valeurs des pixels sont d'abord
décompressées, comme le fait Blender), sinon les multiplications seraient fausses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from moteur.matieres import CALCULEES

BLANC_PEINTURE = 0.86  # la peinture blanche des murs d'Atelya (moteur/blender/materiaux.py, COULEUR_PEINTURE)
GAIN_MIN, GAIN_MAX = 0.2, 4.0  # mêmes bornes que le format (moteur/logement.py, Sol.teinte)
ALBEDO_MAX = 0.85  # aucune couleur de sol ne renvoie plus de 85 % de la lumière


def lineaire(pixels: np.ndarray) -> np.ndarray:
    """Pixels 0-255 (sRGB, comme dans un fichier JPG ou PNG) → lumière linéaire de 0 à 1."""
    c = np.asarray(pixels, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def moyenne_zone(image: np.ndarray, zone: tuple[float, float, float, float]) -> np.ndarray:
    """La couleur moyenne (linéaire) d'une zone (x0, x1, y0, y1 en fractions de la largeur et de la hauteur)."""
    h, w = image.shape[:2]
    x0, x1, y0, y1 = zone
    morceau = image[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1), int(x0 * w):max(int(x1 * w), int(x0 * w) + 1), :3]
    return lineaire(morceau.reshape(-1, 3)).mean(axis=0)


def albedo_du_sol(image: np.ndarray, zone_sol, zone_mur_blanc) -> np.ndarray:
    """La part de lumière (rouge, vert, bleu) que renvoie le sol, étalonnée sur un mur blanc de la même photo."""
    sol = moyenne_zone(image, zone_sol)
    mur = moyenne_zone(image, zone_mur_blanc)
    return sol / max(float(mur.max()), 1e-6) * BLANC_PEINTURE


def albedo_de_la_matiere(bibliotheque: Path, matiere: str) -> np.ndarray:
    """La couleur moyenne (linéaire) de la photo d'une matière de la bibliothèque."""
    from PIL import Image

    source = CALCULEES.get(matiere) or matiere  # le point de Hongrie calculé prend la couleur du chêne clair
    image = Image.open(Path(bibliotheque) / source / "couleur.jpg").convert("RGB").resize((256, 256))
    return lineaire(np.asarray(image).reshape(-1, 3)).mean(axis=0)


def teinte_pour(albedo_matiere, albedo_cible) -> tuple[float, float, float]:
    """Les trois multiplicateurs qui donnent à la matière la couleur cible, bornés (pas de couleur plus claire que
    ALBEDO_MAX, pas de multiplicateur hors de GAIN_MIN..GAIN_MAX)."""
    matiere = np.maximum(np.asarray(albedo_matiere, dtype=float), 1e-4)
    cible = np.minimum(np.asarray(albedo_cible, dtype=float), ALBEDO_MAX)
    gains = np.clip(cible / matiere, GAIN_MIN, GAIN_MAX)
    return tuple(round(float(g), 2) for g in gains)


def ecart_de_couleur(albedo_matiere, albedo_cible) -> float:
    """À quel point les deux couleurs ont une teinte différente (0 = même teinte, quelle que soit la clarté)."""
    a = np.asarray(albedo_matiere, dtype=float)
    b = np.asarray(albedo_cible, dtype=float)
    return float(np.abs(a / a.sum() - b / b.sum()).sum())
