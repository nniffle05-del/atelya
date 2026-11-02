"""Une photo de téléphone réaliste (option --photo-realiste) : la feuille posée sur une vraie table.

Sans cette option, une « photo » est la page vue de biais sur un fond uni de la couleur du papier :
on ne voit ni le bord de la feuille ni la table. Un client, lui, photographie son plan posé sur une
table en bois, sous une lampe, souvent plié en quatre. Ce module ajoute :

- la table autour de la feuille (bois, stratifié, nappe, pierre) et l'ombre portée de la feuille ;
- les plis d'une feuille pliée ou froissée (lignes d'ombre et de lumière, sans déplacer le dessin) ;
- l'ombre douce du téléphone ou de la main, le reflet d'une lampe ou d'une fenêtre ;
- la mise au point ratée sur un bord, le bougé, le bruit du capteur, la couleur de la lumière.

Tout ne touche qu'aux pixels de l'image : les masques et les annotations restent exacts.
Les réglages sont tirés à part (voir `realisme_au_hasard`), les anciens jeux ne changent donc pas.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

import cv2
import numpy as np

TABLES = ("bois", "bois", "stratifie", "nappe", "pierre")


@dataclass
class Realisme:
    """Les tirages d'une photo réaliste, enregistrés avec le style (style.json)."""

    table: str = "bois"
    teinte_table: tuple[int, int, int] = (150, 105, 65)
    ombre_feuille: tuple[float, float, float] = (0.01, 0.015, 0.35)  # décalage x, y (fraction de la photo), force
    plis: str = ""  # "", quatre, deux, froisse
    ombre_main: float = 0.0  # 0 : aucune ; sinon la force de l'ombre du téléphone ou de la main
    reflet: float = 0.0  # 0 : aucun ; sinon la part de blanc au cœur du reflet
    flou_bord: float = 0.0  # flou (sigma, pixels) du côté où la mise au point est ratée
    bouge: int = 0  # longueur du bougé en pixels (0 : aucun)
    bruit: float = 3.0  # bruit du capteur (écart-type)
    lumiere: tuple[float, float, float] = (1.0, 1.0, 1.0)  # multiplicateurs R, G, B (ampoule, jour, néon)

    def en_dict(self) -> dict:
        return asdict(self)


def realisme_au_hasard(rng: random.Random) -> Realisme:
    r = Realisme()
    r.table = rng.choice(TABLES)
    r.teinte_table = {
        "bois": (rng.randint(110, 200), rng.randint(70, 140), rng.randint(35, 90)),
        "stratifie": rng.choice([(rng.randint(225, 245),) * 3, (rng.randint(30, 70),) * 3, (rng.randint(150, 190),) * 3]),
        "nappe": rng.choice([(rng.randint(170, 235), rng.randint(160, 225), rng.randint(140, 210)),  # tons doux
                             (rng.randint(60, 140), rng.randint(70, 140), rng.randint(80, 160)),
                             (rng.randint(120, 200), rng.randint(60, 110), rng.randint(50, 90))]),
        "pierre": (rng.randint(120, 200),) * 3,
    }[r.table]
    r.ombre_feuille = (rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), rng.uniform(0.2, 0.5))
    r.plis = rng.choices(["", "quatre", "deux", "froisse"], weights=[3, 3, 2, 2])[0]
    r.ombre_main = rng.uniform(0.2, 0.5) if rng.random() < 0.45 else 0.0
    r.reflet = rng.uniform(0.55, 0.95) if rng.random() < 0.4 else 0.0
    r.flou_bord = rng.uniform(1.0, 3.0) if rng.random() < 0.5 else 0.0
    r.bouge = rng.randint(3, 7) if rng.random() < 0.2 else 0
    r.bruit = rng.uniform(2.0, 8.0)
    r.lumiere = rng.choice([(1.0, 0.96, 0.82), (1.0, 0.98, 0.92), (0.93, 0.97, 1.0), (1.0, 1.0, 1.0), (0.96, 1.0, 0.95)])
    return r


def _bruit_doux(h: int, w: int, nrng: np.random.Generator, cellule: int) -> np.ndarray:
    """Un bruit à grosses taches (entre -1 et 1), lissé : veines, nuages de la pierre, éclairage."""
    petit = nrng.normal(0, 1, (max(2, h // cellule + 2), max(2, w // cellule + 2))).astype(np.float32)
    grand = cv2.resize(petit, (w, h), interpolation=cv2.INTER_CUBIC)
    return grand / (np.abs(grand).max() + 1e-6)


def table(h: int, w: int, r: Realisme, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    """L'image RGB (float) de la table sous la feuille."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.array(r.teinte_table, np.float32)
    if r.table == "bois":
        a = rng.uniform(0, np.pi)
        v = -xx * np.sin(a) + yy * np.cos(a)  # en travers des lattes
        largeur = rng.uniform(0.12, 0.3) * max(h, w)  # largeur d'une latte
        latte = np.floor(v / largeur)
        # veines presque droites le long des lattes, qui ondulent à peine (nœuds rares)
        veines = np.sin(v * rng.uniform(0.04, 0.1) + _bruit_doux(h, w, nrng, 150) * rng.uniform(1.0, 2.5) + latte * 1.7)
        fines = np.sin(v * rng.uniform(0.5, 1.0) + _bruit_doux(h, w, nrng, 120) * 2)  # le fil du bois
        teinte = 1 + 0.08 * veines + 0.04 * fines + 0.06 * np.sin(latte * 2.3)
        joint = np.abs(v - (latte + 0.5) * largeur) > largeur / 2 - 1.5
        teinte = np.where(joint, teinte * 0.7, teinte)
        img = base[None, None, :] * teinte[:, :, None]
    elif r.table == "nappe":
        pas = rng.uniform(3, 7)
        trame = 1 + 0.06 * np.sin(xx * 2 * np.pi / pas) * np.sin(yy * 2 * np.pi / pas)
        if rng.random() < 0.4:  # nappe à carreaux
            carreau = rng.uniform(0.04, 0.1) * max(h, w)
            damier = ((np.floor(xx / carreau) + np.floor(yy / carreau)) % 2).astype(np.float32)
            trame = trame * (1 - 0.25 * damier)
        img = base[None, None, :] * trame[:, :, None]
    elif r.table == "pierre":
        nuages = 0.5 * _bruit_doux(h, w, nrng, 40) + 0.3 * _bruit_doux(h, w, nrng, 12)
        img = base[None, None, :] * (1 + 0.15 * nuages)[:, :, None]
    else:  # stratifié : presque uni
        img = base[None, None, :] * (1 + 0.03 * _bruit_doux(h, w, nrng, 80))[:, :, None]
    return img + nrng.normal(0, 2.5, img.shape).astype(np.float32)


def plis_a_plat(h: int, w: int, r: Realisme, rng: random.Random, nrng: np.random.Generator) -> np.ndarray | None:
    """La lumière (autour de 1) des plis du papier, dessinée sur la page à plat. None : feuille lisse."""
    if not r.plis:
        return None
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    lum = np.ones((h, w), np.float32)
    plis: list[tuple[float, float, float, float, float]] = []  # point, direction en travers, force, longueur (0 : tout)
    if r.plis in ("quatre", "deux"):
        plis.append((w / 2 + rng.uniform(-0.02, 0.02) * w, h / 2, 0.0, rng.uniform(0.04, 0.1), 0.0))  # pli vertical
        if r.plis == "quatre":
            plis.append((w / 2, h / 2 + rng.uniform(-0.02, 0.02) * h, np.pi / 2, rng.uniform(0.03, 0.08), 0.0))
    else:  # froissé : beaucoup de petits plis dans tous les sens
        for _ in range(rng.randint(8, 18)):  # des plis courts, qui s'effacent vers leurs bouts
            plis.append((rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, np.pi), rng.uniform(0.02, 0.05),
                         rng.uniform(0.1, 0.4) * max(h, w)))
    for px, py, a, force, longueur in plis:
        # distance signée au pli : un côté s'assombrit, l'autre accroche la lumière ; une fine arête au milieu
        d = (xx - px) * np.cos(a) + (yy - py) * np.sin(a)
        cote = rng.choice((-1, 1))
        large = rng.uniform(0.01, 0.04) * max(h, w)
        effet = cote * force * np.sign(d) * np.exp(-np.abs(d) / large) - force * 0.8 * np.exp(-(d / 1.5) ** 2)
        if longueur:
            le_long = -(xx - px) * np.sin(a) + (yy - py) * np.cos(a)
            effet = effet * np.exp(-(le_long / longueur) ** 2)
        lum += effet
    if r.plis == "froisse":
        lum += 0.05 * _bruit_doux(h, w, nrng, 50)
    return lum


def composer(image: np.ndarray, page: np.ndarray, plis: np.ndarray | None, r: Realisme,
             rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    """La photo (float RGB) : la page (image, déjà vue de biais) posée sur la table, avec ombres et plis.

    `page` : la part de chaque pixel couverte par la feuille (0 à 1, bords adoucis), dans le repère final.
    `plis` : la lumière des plis dans le même repère (ou None)."""
    h, w = page.shape
    img = image.astype(np.float32)
    if plis is not None:
        img = img * plis[:, :, None]
    fond = table(h, w, r, rng, nrng)
    dx, dy, force = r.ombre_feuille
    decale = cv2.warpAffine(page, np.float32([[1, 0, dx * w], [0, 1, dy * h]]), (w, h))
    ombre = cv2.GaussianBlur(decale, (0, 0), max(2.0, 0.008 * max(h, w)))
    fond = fond * (1 - force * ombre)[:, :, None]
    p = page[:, :, None]
    return img * p + fond * (1 - p)


def lumiere(img: np.ndarray, page: np.ndarray, r: Realisme, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    """Ombre de la main, reflet, couleur de la lumière, vignettage (sur toute la photo)."""
    h, w = page.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ys, xs = np.nonzero(page > 0.5)
    if r.ombre_main:
        # une forme allongée (téléphone, avant-bras) qui entre par un bord, très floue
        masque = np.zeros((h, w), np.float32)
        bord = rng.randrange(4)
        cx = rng.uniform(0.1, 0.9) * w if bord in (0, 2) else (0 if bord == 3 else w)
        cy = rng.uniform(0.1, 0.9) * h if bord in (1, 3) else (0 if bord == 0 else h)
        axes = (int(rng.uniform(0.12, 0.3) * max(h, w)), int(rng.uniform(0.25, 0.5) * max(h, w)))
        cv2.ellipse(masque, (int(cx), int(cy)), axes, rng.uniform(0, 180), 0, 360, 1.0, -1)
        masque = cv2.GaussianBlur(masque, (0, 0), rng.uniform(0.03, 0.08) * max(h, w))
        img = img * (1 - r.ombre_main * masque)[:, :, None]
    if r.reflet and len(xs):
        k = rng.randrange(len(xs))
        cx, cy = xs[k], ys[k]
        rx, ry = rng.uniform(0.06, 0.2) * w, rng.uniform(0.04, 0.14) * h
        a = rng.uniform(0, np.pi)
        u = ((xx - cx) * np.cos(a) + (yy - cy) * np.sin(a)) / rx
        v = (-(xx - cx) * np.sin(a) + (yy - cy) * np.cos(a)) / ry
        g = r.reflet * np.exp(-(u * u + v * v) ** rng.uniform(1.0, 2.0))  # cœur plus ou moins franc
        g = g * (0.35 + 0.65 * page)  # sur la table, le reflet est plus faible (surface mate)
        img = img * rng.uniform(0.72, 0.88)  # le téléphone baisse l'exposition à cause du reflet : le papier grisaille
        img = img * (1 - g[:, :, None]) + 255 * g[:, :, None]
    img = img * np.array(r.lumiere, np.float32)[None, None, :]
    rayon = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    return img * (1 - rng.uniform(0.05, 0.25) * np.clip(rayon - 0.4, 0, None) ** 2)[:, :, None]


def capteur(img: np.ndarray, r: Realisme, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    """Mise au point ratée sur un côté, bougé, bruit du capteur (plus fort dans les ombres)."""
    h, w = img.shape[:2]
    if r.flou_bord:
        flou = cv2.GaussianBlur(img, (0, 0), r.flou_bord)
        a = rng.uniform(0, 2 * np.pi)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        t = ((xx - w / 2) * np.cos(a) + (yy - h / 2) * np.sin(a)) / (max(h, w) / 2)
        poids = np.clip(t * rng.uniform(0.8, 1.5), 0, 1)[:, :, None]  # net d'un côté, flou de l'autre
        img = img * (1 - poids) + flou * poids
    if r.bouge:
        noyau = np.zeros((r.bouge, r.bouge), np.float32)
        noyau[r.bouge // 2, :] = 1
        rot = cv2.getRotationMatrix2D((r.bouge / 2 - 0.5, r.bouge / 2 - 0.5), rng.uniform(0, 180), 1)
        noyau = cv2.warpAffine(noyau, rot, (r.bouge, r.bouge))
        img = cv2.filter2D(img, -1, noyau / max(noyau.sum(), 1e-6))
    sombre = 1.5 - np.clip(img.mean(axis=2, keepdims=True) / 255, 0, 1)
    gris = nrng.normal(0, r.bruit, (h, w, 1)).astype(np.float32)
    couleur = nrng.normal(0, r.bruit * 0.4, img.shape).astype(np.float32)
    return img + (gris + couleur) * sombre
