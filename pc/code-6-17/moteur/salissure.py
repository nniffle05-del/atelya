"""Salir les plans fabriqués, pour voir si la lecture tient sur des plans réalistes (étape 5c).

Un vrai client n'envoie pas un plan aussi propre que ceux de la fabrique : il
envoie un scan un peu de travers, une photocopie grise, une feuille tachée ou
pliée, une image réduite pour l'e-mail, ou une photo prise au téléphone. Ce
module abîme exprès un plan propre, de cinq façons (les « familles ») :

- travers     : scan de travers (la feuille a tourné de 0,5 à 4 degrés), papier un peu gris ;
- photocopie  : flou, traits gris pâle, papier grisé, grain et petits points ;
- taches      : tache de café, pli de la feuille, traits de stylo griffonnés ;
- compression : image réduite et enregistrée en JPEG très compressé (le format
                des photos, qui perd des détails pour prendre moins de place) ;
- telephone   : photo de la feuille posée sur une table : vue un peu en biais,
                lumière inégale, ombre, léger flou, couleurs, JPEG.

Le plan sali garde le même corrigé (logement.json) : seul le dessin change.
Une même graine (ici le nom du dossier du plan) redonne toujours la même salissure.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

FAMILLES = ("travers", "photocopie", "taches", "compression", "telephone")
EXTENSION = {"travers": ".png", "photocopie": ".png", "taches": ".png", "compression": ".jpg", "telephone": ".jpg"}


def salir(image: np.ndarray, famille: str, rng: random.Random) -> np.ndarray:
    """Le plan abîmé selon une famille (image en niveaux de gris ou couleur, 255 = blanc)."""
    gris = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    nrng = np.random.default_rng(rng.getrandbits(32))
    if famille == "travers":
        return _travers(gris, rng, nrng)
    if famille == "photocopie":
        return _photocopie(gris, rng, nrng)
    if famille == "taches":
        return _taches(gris, rng, nrng)
    if famille == "compression":
        return _compression(gris, rng)
    if famille == "telephone":
        return _telephone(gris, rng, nrng)
    raise ValueError(f"famille de salissure inconnue : {famille}")


# ---------- Les cinq familles ----------


def _travers(gris: np.ndarray, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    page = _sur_une_feuille(gris, rng)
    angle = rng.choice((-1, 1)) * rng.uniform(0.5, 4.0)
    h, w = page.shape
    matrice = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    page = cv2.warpAffine(page, matrice, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    papier = rng.randint(230, 250)  # le blanc du scanner n'est jamais tout à fait blanc
    page = page.astype(np.float32) * papier / 255 + nrng.normal(0, 3, page.shape)
    return _octets(page)


def _photocopie(gris: np.ndarray, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    page = cv2.GaussianBlur(gris, (0, 0), rng.uniform(0.7, 1.4)).astype(np.float32)
    noir, blanc = rng.uniform(40, 90), rng.uniform(205, 235)  # le noir devient gris, le blanc grisé
    page = noir + page * (blanc - noir) / 255
    page += nrng.normal(0, rng.uniform(4, 9), page.shape)  # le grain
    # Petits points de toner semés sur la feuille.
    h, w = page.shape
    for _ in range(rng.randint(80, 300)):
        cv2.circle(page, (rng.randrange(w), rng.randrange(h)), rng.choice((1, 1, 1, 2)), rng.uniform(40, 120), -1)
    # Une traînée verticale pâle, comme une vitre de photocopieuse sale.
    if rng.random() < 0.5:
        x = rng.randrange(w)
        page[:, max(0, x - 2):x + 2] -= rng.uniform(10, 30)
    return _octets(page)


def _taches(gris: np.ndarray, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    page = gris.astype(np.float32)
    h, w = page.shape
    # Une ou deux taches de café : un disque pâle aux bords irréguliers, plus foncé sur son pourtour.
    for _ in range(rng.randint(1, 2)):
        rayon = rng.uniform(0.06, 0.14) * min(h, w)
        cx, cy = rng.uniform(0.15, 0.85) * w, rng.uniform(0.15, 0.85) * h
        tache = np.zeros((h, w), np.float32)
        angles = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        bosses = 1 + 0.15 * np.sin(angles * rng.randint(2, 5) + rng.uniform(0, 6)) + nrng.normal(0, 0.04, 48)
        contour = np.stack([cx + rayon * bosses * np.cos(angles), cy + rayon * bosses * np.sin(angles)], 1)
        cv2.fillPoly(tache, [contour.astype(np.int32)], 1.0)
        tache = cv2.GaussianBlur(tache, (0, 0), 3)
        anneau = np.clip(tache * (1 - tache) * 4, 0, 1)
        page *= 1 - (rng.uniform(0.06, 0.15) * tache + rng.uniform(0.10, 0.20) * anneau)
    # Un pli : une ligne qui traverse la feuille, un côté un peu plus sombre.
    if rng.random() < 0.8:
        horizontal = rng.random() < 0.5
        pos = rng.uniform(0.3, 0.7) * (h if horizontal else w)
        coord = np.arange(h if horizontal else w, dtype=np.float32) - pos
        ombre = 1 - 0.06 * np.exp(-np.abs(coord) / rng.uniform(8, 25)) - 0.12 * np.exp(-(coord / 1.5) ** 2)
        page *= ombre[:, None] if horizontal else ombre[None, :]
    # Quelques traits de stylo griffonnés (annotations à la main), fins.
    for _ in range(rng.randint(1, 3)):
        x, y = rng.uniform(0.1, 0.9) * w, rng.uniform(0.1, 0.9) * h
        points = [(x, y)]
        for _ in range(rng.randint(4, 10)):
            x += rng.uniform(-40, 40)
            y += rng.uniform(-25, 25)
            points.append((x, y))
        cv2.polylines(page, [np.array(points, np.int32)], False, rng.uniform(30, 90), rng.choice((1, 2)), cv2.LINE_AA)
    page += nrng.normal(0, 2, page.shape)
    return _octets(page)


def _compression(gris: np.ndarray, rng: random.Random) -> np.ndarray:
    facteur = rng.uniform(0.6, 0.85)  # une image réduite pour être envoyée par e-mail
    petit = cv2.resize(gris, None, fx=facteur, fy=facteur, interpolation=cv2.INTER_AREA)
    return _jpeg(petit, rng.randint(20, 45))


def _telephone(gris: np.ndarray, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    page = _sur_une_feuille(gris, rng).astype(np.float32)
    h, w = page.shape
    # La table autour de la feuille : un fond plus sombre, un peu texturé.
    marge = round(0.08 * max(h, w))
    H, W = h + 2 * marge, w + 2 * marge
    table = rng.uniform(60, 150) + cv2.GaussianBlur(nrng.normal(0, 25, (H, W)).astype(np.float32), (0, 0), 6)
    # La feuille vue un peu en biais : ses quatre coins bougent un peu (perspective).
    biais = rng.uniform(0.02, 0.06)
    coins = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    bouges = coins + np.float32([[marge, marge]]) + np.float32(
        [[rng.uniform(-1, 1) * biais * w, rng.uniform(-1, 1) * biais * h] for _ in range(4)]
    )
    matrice = cv2.getPerspectiveTransform(coins, bouges)
    feuille = cv2.warpPerspective(page, matrice, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    masque = cv2.warpPerspective(np.ones((h, w), np.float32), matrice, (W, H), flags=cv2.INTER_LINEAR)
    photo = feuille * masque + table * (1 - masque)
    # La lumière inégale : plus claire d'un côté, et l'ombre douce du téléphone ou de la main.
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a = rng.uniform(0, 2 * np.pi)
    pente = ((xx - W / 2) * np.cos(a) + (yy - H / 2) * np.sin(a)) / max(H, W)
    lumiere = 1 + rng.uniform(0.15, 0.35) * pente
    ox, oy, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.25, 0.5) * max(H, W)
    lumiere *= 1 - rng.uniform(0.10, 0.25) * np.exp(-((xx - ox) ** 2 + (yy - oy) ** 2) / (2 * r * r))
    photo = photo * lumiere * rng.uniform(0.85, 1.0)
    photo = cv2.GaussianBlur(photo, (0, 0), rng.uniform(0.6, 1.2)) + nrng.normal(0, 4, photo.shape)
    # Les couleurs d'une photo : un blanc un peu jaune ou bleu.
    teinte = np.array([rng.uniform(0.88, 1.0), rng.uniform(0.95, 1.0), rng.uniform(0.95, 1.05)], np.float32)
    couleur = _octets(photo[:, :, None] * teinte[None, None, :])
    return _jpeg(couleur, rng.randint(70, 88))


# ---------- Outils ----------


def _sur_une_feuille(gris: np.ndarray, rng: random.Random) -> np.ndarray:
    """Le plan avec une marge blanche autour, comme sur une feuille de papier."""
    marge = round(rng.uniform(0.03, 0.08) * max(gris.shape))
    return cv2.copyMakeBorder(gris, marge, marge, marge, marge, cv2.BORDER_CONSTANT, value=255)


def _octets(image: np.ndarray) -> np.ndarray:
    return np.clip(image, 0, 255).astype(np.uint8)


def _jpeg(image: np.ndarray, qualite: int) -> np.ndarray:
    """L'image telle qu'elle revient après un enregistrement en JPEG (avec ses défauts)."""
    ok, octets = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, qualite])
    assert ok
    return cv2.imdecode(octets, cv2.IMREAD_UNCHANGED)


def salir_dossier(dossier: Path, familles: tuple[str, ...] = FAMILLES) -> list[Path]:
    """Écrit à côté du plan.png d'un dossier un plan sali par famille (plan-travers.png…)."""
    image = cv2.imread(str(dossier / "plan.png"), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"pas de plan.png dans {dossier}")
    ecrits = []
    for famille in familles:
        sali = salir(image, famille, random.Random(f"salissure-{famille}-{dossier.name}"))
        chemin = dossier / f"plan-{famille}{EXTENSION[famille]}"
        if EXTENSION[famille] == ".jpg":
            # Déjà passé par le JPEG dans salir() : on l'enregistre sans le dégrader une seconde fois.
            cv2.imwrite(str(chemin), sali, [cv2.IMWRITE_JPEG_QUALITY, 100])
        else:
            cv2.imwrite(str(chemin), sali)
        ecrits.append(chemin)
    return ecrits


def main() -> None:
    parser = argparse.ArgumentParser(description="Salit les plans fabriqués (scan de travers, photocopie, taches…).")
    parser.add_argument("dossier", nargs="?", default="sorties/fabrique", help="dossier de la fabrique (par défaut : sorties/fabrique)")
    parser.add_argument("--familles", default=",".join(FAMILLES), help=f"familles à produire, séparées par des virgules ({', '.join(FAMILLES)})")
    args = parser.parse_args()

    familles = tuple(f.strip() for f in args.familles.split(",") if f.strip())
    inconnues = [f for f in familles if f not in FAMILLES]
    if inconnues:
        sys.exit(f"Famille inconnue : {', '.join(inconnues)} (au choix : {', '.join(FAMILLES)})")
    dossiers = sorted(p.parent for p in Path(args.dossier).glob("*/plan.png"))
    if not dossiers:
        sys.exit(f"Échec : aucun plan.png dans les sous-dossiers de {args.dossier}")
    debut = time.perf_counter()
    for d in dossiers:
        salir_dossier(d, familles)
    print(f"{len(dossiers) * len(familles)} plans salis ({', '.join(familles)}) en {time.perf_counter() - debut:.0f} s → {args.dossier}")


if __name__ == "__main__":
    main()
