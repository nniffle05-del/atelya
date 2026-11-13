r"""Dessine des carrelages que la bibliothèque CC0 n'a pas, d'après les photos d'un client (B2 temps 2, app-001, 09/11/2026) :
couleur, brillance et relief (normales), à la taille réelle, raccordables sans couture. Rien n'est téléchargé.

- « carreaux_cubes » : carreaux de ciment en LOSANGES posés en cubes (blanc cassé, gris clair, gris moyen, jaune moutarde),
  joint gris foncé autour de chaque losange (photos 05 et 06 d'app-001) ;
- « petits_carreaux_clairs » : carrés de 10 cm blanc cassé, quelques-uns un peu plus gris, joint gris de 2 mm (photo 12).

Les images vont dans la bibliothèque de matières (hors Git) avec leur fiche dans matieres.json :

    ..\atelya\.venv\Scripts\python.exe outils\bibliotheque\dessiner_carreaux.py ..\atelya\bibliotheque\matieres
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MM_PAR_PX = 1.0  # résolution des images : 1 pixel = 1 mm

# Couleurs (sRGB 0-255) relevées sur les photos du client, éclairage compris (à affiner ensuite par la teinte de la pièce).
CUBES = {"blanc": (226, 224, 217), "gris_clair": (199, 197, 191), "gris": (156, 154, 150), "moutarde": (204, 160, 74)}
CUBES_PART = {"blanc": 0.42, "gris_clair": 0.22, "gris": 0.20, "moutarde": 0.16}
CUBES_JOINT = (92, 90, 87)
CLAIRS = [((219, 215, 206), 0.75), ((205, 199, 189), 0.17), ((190, 184, 174), 0.08)]
CLAIRS_JOINT = (150, 147, 141)


def _normales(hauteur: np.ndarray, force: float) -> np.ndarray:
    """Carte de normales (convention OpenGL, celle des photos de la bibliothèque) d'une carte de hauteurs (0..1)."""
    gy, gx = np.gradient(hauteur * force)
    n = np.dstack([-gx, gy, np.ones_like(hauteur)])  # ligne d'image vers le bas = y vers le bas : le vert monte
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def _grain(forme, graine: int, force: float) -> np.ndarray:
    """Un léger grain irrégulier (le ciment et l'émail ne sont jamais parfaitement unis), raccordable."""
    r = np.random.default_rng(graine)
    bruit = r.normal(0, 1, forme).astype(np.float32)
    f = np.fft.fft2(bruit)
    ky, kx = np.meshgrid(np.fft.fftfreq(forme[0]), np.fft.fftfreq(forme[1]), indexing="ij")
    f *= np.exp(-(kx ** 2 + ky ** 2) / (2 * 0.02 ** 2))  # taches de quelques centimètres
    lisse = np.real(np.fft.ifft2(f))
    return 1.0 + force * lisse / (np.abs(lisse).max() + 1e-9)


def carreaux_cubes(cote_m: float = 0.115, colonnes: int = 8, rangs: int = 10, joint_mm: float = 3.0, graine: int = 1):
    """Losanges de `cote_m` posés en cubes (hexagones à pointe en haut, trois losanges chacun). Motif raccordable :
    `colonnes` hexagones en largeur, `rangs` rangées (nombre pair) en hauteur."""
    a = cote_m * 1000 / MM_PAR_PX  # côté en pixels
    w = math.sqrt(3) * a
    L, H = int(round(colonnes * w)), int(round(rangs * 1.5 * a))
    ys, xs = np.mgrid[0:H, 0:L].astype(np.float64) + 0.5
    # Le centre d'hexagone le plus proche (réseau à pointe en haut, rangées décalées d'une demi-largeur).
    meilleur = np.full((H, L), np.inf)
    ci = np.zeros((H, L), int)
    cj = np.zeros((H, L), int)
    cx = np.zeros((H, L))
    cy = np.zeros((H, L))
    for j in range(-1, rangs + 2):
        for i in range(-1, colonnes + 2):
            x0, y0 = i * w + (w / 2 if j % 2 else 0.0), j * 1.5 * a
            d = (xs - x0) ** 2 + (ys - y0) ** 2
            plus = d < meilleur
            meilleur[plus] = d[plus]
            ci[plus], cj[plus], cx[plus], cy[plus] = i % colonnes, j % rangs, x0, y0
    dx, dy = xs - cx, -(ys - cy)  # y vers le haut
    angle = (np.degrees(np.arctan2(dy, dx)) + 360.0) % 360.0
    face = np.where((angle >= 30) & (angle < 150), 0, np.where((angle >= 150) & (angle < 270), 1, 2))  # dessus, gauche, droite
    # Joint : bord de l'hexagone (distance aux six côtés) et trois rayons (vers 30°, 150° et 270°).
    r = math.sqrt(3) / 2 * a  # distance du centre au milieu d'un côté
    bord = np.full((H, L), np.inf)
    for k in range(6):
        t = math.radians(60 * k)  # normales des côtés d'un hexagone à pointe en haut : 0°, 60°… 300°
        bord = np.minimum(bord, r - (dx * math.cos(t) + dy * math.sin(t)))
    rayon = np.full((H, L), np.inf)
    for t in (30, 150, 270):
        ux, uy = math.cos(math.radians(t)), math.sin(math.radians(t))
        le_long = dx * ux + dy * uy
        rayon = np.minimum(rayon, np.where(le_long > 0, np.abs(dx * uy - dy * ux), np.inf))
    distance_joint = np.minimum(bord, rayon)
    joint = distance_joint < joint_mm / MM_PAR_PX / 2
    # Une couleur par losange, tirée au hasard selon les parts vues sur la photo (même tirage à chaque raccord).
    r_ = np.random.default_rng(graine)
    noms = list(CUBES)
    tirage = r_.choice(len(noms), size=(colonnes, rangs, 3), p=[CUBES_PART[n] for n in noms])
    nuance = r_.uniform(0.96, 1.04, size=(colonnes, rangs, 3))
    palette = np.array([CUBES[n] for n in noms], np.float64)
    couleur = palette[tirage[ci, cj, face]] * nuance[ci, cj, face][..., None]
    couleur *= _grain((H, L), graine + 7, 0.04)[..., None]
    couleur[joint] = CUBES_JOINT
    hauteur = np.clip(distance_joint / (joint_mm / MM_PAR_PX), 0, 1)  # le joint est en creux, bords adoucis
    brillance = np.where(joint, 235, 150).astype(np.uint8)  # ciment mat, joint plus mat encore
    return np.clip(couleur, 0, 255).astype(np.uint8), brillance, _normales(hauteur, 1.5), (L * MM_PAR_PX / 1000, H * MM_PAR_PX / 1000)


def petits_carreaux_clairs(cote_m: float = 0.10, n: int = 10, joint_mm: float = 2.0, graine: int = 2):
    """Carrés de `cote_m`, n × n carreaux par image (raccordable), quelques-uns un peu plus gris."""
    c = int(round(cote_m * 1000 / MM_PAR_PX))
    T = c * n
    ys, xs = np.mgrid[0:T, 0:T] + 0.5
    u, v = (xs % c), (ys % c)
    distance_joint = np.minimum(np.minimum(u, c - u), np.minimum(v, c - v))
    joint = distance_joint < joint_mm / MM_PAR_PX / 2
    r = np.random.default_rng(graine)
    couleurs = np.array([col for col, _ in CLAIRS], np.float64)
    tirage = r.choice(len(CLAIRS), size=(n, n), p=[p for _, p in CLAIRS])
    nuance = r.uniform(0.98, 1.02, size=(n, n))
    i, j = (xs // c).astype(int), (ys // c).astype(int)
    couleur = couleurs[tirage[j, i]] * nuance[j, i][..., None] * _grain((T, T), graine + 7, 0.02)[..., None]
    couleur[joint] = CLAIRS_JOINT
    hauteur = np.clip(distance_joint / (joint_mm / MM_PAR_PX), 0, 1)
    brillance = np.where(joint, 230, 70).astype(np.uint8)  # émail brillant, joint mat
    return np.clip(couleur, 0, 255).astype(np.uint8), brillance, _normales(hauteur, 1.0), (T * MM_PAR_PX / 1000,) * 2


DESSINS = {
    "carreaux_cubes": (carreaux_cubes, "carreaux de ciment en losanges posés en cubes (blanc, gris clair, gris, moutarde)"),
    "petits_carreaux_clairs": (petits_carreaux_clairs, "petits carreaux carrés de 10 cm blanc cassé, joint gris"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Dessine les carrelages d'Atelya dans la bibliothèque de matières")
    ap.add_argument("bibliotheque", type=Path, help="..\\atelya\\bibliotheque\\matieres")
    a = ap.parse_args()
    fiches_chemin = a.bibliotheque / "matieres.json"
    if not fiches_chemin.is_file():
        print(f"PLANTÉ : bibliothèque introuvable : {fiches_chemin}", flush=True)
        return 2
    fiches = json.loads(fiches_chemin.read_text(encoding="utf-8"))
    for nom, (dessin, description) in DESSINS.items():
        couleur, brillance, relief, taille = dessin()
        dossier = a.bibliotheque / nom
        dossier.mkdir(exist_ok=True)
        Image.fromarray(couleur).save(dossier / "couleur.jpg", quality=92)
        Image.fromarray(brillance).save(dossier / "brillance.jpg", quality=92)
        Image.fromarray(relief).save(dossier / "relief.jpg", quality=95)
        fiches[nom] = {"description": description, "source": "dessiné par Atelya (outils/bibliotheque/dessiner_carreaux.py)",
                       "identifiant": nom, "licence": "Atelya (aucune image extérieure)", "page": "",
                       "auteurs": ["Atelya"], "taille_image_m": [round(taille[0], 4), round(taille[1], 4)],
                       "octets": sum((dossier / f).stat().st_size for f in ("couleur.jpg", "brillance.jpg", "relief.jpg"))}
        print(f"{nom} : {couleur.shape[1]} × {couleur.shape[0]} px = {taille[0]:.3f} × {taille[1]:.3f} m", flush=True)
    fiches_chemin.write_text(json.dumps(fiches, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
