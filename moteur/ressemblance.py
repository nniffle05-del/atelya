r"""LA RESSEMBLANCE entre une photo du client et la maquette vue du même endroit : une note automatique (16/11/2026).

Pourquoi (NT, 16/11/2026 : « j'ai l'impression qu'on travaille que sur ce logement […] le but c'est qu'Atelya soit le plus
performant possible ») : pour savoir si une maquette ressemble aux photos, il fallait tourner un film et le regarder : lent, un
seul logement à la fois, et jugé à l'œil. Ici, chaque photo de chaque logement est comparée à la maquette rendue depuis la même
place par un œil automatique (DINOv2 ViT-B/14, déjà dans Atelya : il décrit chaque petit carré d'une image par ce qu'il montre —
une fenêtre, un lit, un parquet — bien plus que par sa couleur exacte). Deux notes :

- `locale` : les deux images se ressemblent-elles AU MÊME ENDROIT (carré par carré) ? De 0 à 1. Elle monte quand la fenêtre, le
  lit, le sol de la maquette sont là où ils sont sur la photo.
- `reconnue` : parmi toutes les vues de la maquette du logement, celle prise depuis la place de la photo est-elle celle qui
  ressemble le plus à la photo ? (rang 1 = oui.) Une maquette fidèle se reconnaît pièce par pièce ; une maquette aux murs blancs
  partout pareils ne se reconnaît pas.

Ce n'est PAS l'avis d'un client : c'est un thermomètre, le même pour tous les logements, qui dit si une correction d'Atelya
rapproche les maquettes des photos en général. Il se contrôle contre l'œil de NT (planches côte à côte du banc).
"""
from __future__ import annotations

import cv2
import numpy as np

VERSION = "0.1.0"
LARGEUR, HAUTEUR = 1204, 798  # 86 × 57 carrés de 14 px : toutes les images sont ramenées à cette taille
MARQUE = (0.22, 0.10)  # coins écartés (logos de l'annonce) : part de la largeur, part de la hauteur


def carres(oeil, rgb: np.ndarray) -> np.ndarray:
    """Ce que l'œil voit dans chaque carré de l'image : (57, 86, dimension), chaque carré ramené à la longueur 1."""
    import torch

    from moteur.oeil_dinov2 import ECART, MOYENNE

    x = (cv2.resize(rgb, (LARGEUR, HAUTEUR), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0 - MOYENNE) / ECART
    x = torch.from_numpy(x).permute(2, 0, 1)[None].to(next(oeil.parameters()).device)
    with torch.no_grad(), torch.autocast(device_type=x.device.type, enabled=x.device.type == "cuda"):
        _, c = oeil(x)
    c = c[0].float().cpu().numpy().reshape(HAUTEUR // 14, LARGEUR // 14, -1)
    return c / np.maximum(np.linalg.norm(c, axis=-1, keepdims=True), 1e-9)


def masque_utile() -> np.ndarray:
    """Les carrés comparés : tout, sauf les quatre coins (logos de l'annonce)."""
    h, w = HAUTEUR // 14, LARGEUR // 14
    m = np.ones((h, w), bool)
    lx, ly = int(round(MARQUE[0] * w)), int(round(MARQUE[1] * h))
    for y0 in (0, h - ly):
        for x0 in (0, w - lx):
            m[y0:y0 + ly, x0:x0 + lx] = False
    return m


def locale(a: np.ndarray, b: np.ndarray, masque: np.ndarray | None = None) -> float:
    """La ressemblance carré par carré de deux images décrites par `carres` (moyenne des accords, de −1 à 1)."""
    masque = masque_utile() if masque is None else masque
    return float((a * b).sum(-1)[masque].mean())


def carte(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """L'accord de chaque carré (pour dessiner OÙ la maquette ne ressemble pas à la photo)."""
    return (a * b).sum(-1)


def tableau(photos: dict[str, np.ndarray], rendus: dict[str, np.ndarray]) -> dict:
    """Pour un logement : la note locale de chaque photo contre SA vue de la maquette, et le rang de cette vue parmi toutes
    les vues de la maquette (1 = c'est elle qui ressemble le plus à la photo)."""
    noms = [n for n in photos if n in rendus]
    m = masque_utile()
    notes = {a: {b: locale(photos[a], rendus[b], m) for b in noms} for a in noms}
    sortie = {}
    for a in noms:
        rang = 1 + sum(1 for b in noms if b != a and notes[a][b] > notes[a][a])
        sortie[a] = {"locale": round(notes[a][a], 4), "rang": rang,
                     "meilleure_autre": round(max((notes[a][b] for b in noms if b != a), default=0.0), 4)}
    return sortie


def resume(par_photo: dict) -> dict:
    """La note d'un logement : moyenne des notes locales, et part des photos « reconnues » (rang 1)."""
    if not par_photo:
        return {"photos": 0}
    return {"photos": len(par_photo), "locale": round(float(np.mean([v["locale"] for v in par_photo.values()])), 4),
            "reconnues": sum(v["rang"] == 1 for v in par_photo.values()),
            "marge": round(float(np.mean([v["locale"] - v["meilleure_autre"] for v in par_photo.values()])), 4)}
