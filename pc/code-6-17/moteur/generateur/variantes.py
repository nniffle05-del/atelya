"""Les variantes graphiques : comment un même logement peut être dessiné de façons différentes.

Un modèle qui doit lire de vrais plans rencontre des dessins d'architecte en noir et blanc,
des plans d'agence aux pièces colorées et meublées, des scans gris, des photos de travers…
Un `Style` décrit un de ces dessins ; `style_au_hasard` en tire un, avec plus ou moins de
fantaisie selon le niveau de diversité demandé (0 : plans propres et classiques, 3 : tout
est permis, dans les limites où un plan reste lisible).

Deux sortes de transformations :

- celles qui changent la géométrie visible (échelle, rotation, perspective, marges) : elles
  sont appliquées par une matrice unique dans rendu.py, à l'image ET aux masques ET aux
  annotations (voir `Repere`) ;
- celles qui ne touchent qu'aux pixels (flou, grain, papier gris, taches, compression JPEG,
  contraste) : `salir` les applique après coup, à l'image seule ; les masques restent exacts.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from moteur.generateur.photo import Realisme, capteur, composer, lumiere
from moteur.salissure import _photocopie, _taches

FAMILLES = ("architecte", "agence", "minimaliste", "scan", "photo", "colore", "croquis")
POLICES = ("Inter-Regular.otf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf")

# Couleurs des pièces (plans d'agence), par type de pièce : (R, G, B).
PALETTES = {
    "pastel": {
        "sejour": (255, 236, 200), "principale": (255, 236, 200), "cuisine": (255, 214, 170), "chambre": (214, 228, 255),
        "sdb": (200, 236, 240), "sde": (200, 236, 240), "wc": (210, 240, 230), "entree": (236, 236, 226),
        "degagement": (236, 236, 226), "placard": (226, 220, 210), "buanderie": (220, 236, 220), "bureau": (236, 220, 240),
        "escalier": (230, 230, 230),
    },
    "bois": {
        "sejour": (233, 204, 160), "principale": (233, 204, 160), "cuisine": (220, 220, 215), "chambre": (230, 206, 170),
        "sdb": (205, 220, 225), "sde": (205, 220, 225), "wc": (205, 220, 225), "entree": (222, 222, 218),
        "degagement": (222, 222, 218), "placard": (215, 210, 200), "buanderie": (220, 220, 215), "bureau": (233, 204, 160),
        "escalier": (210, 200, 185),
    },
    "gris": {s: (v, v, v) for s, v in {
        "sejour": 238, "principale": 238, "cuisine": 228, "chambre": 240, "sdb": 222, "sde": 222, "wc": 222,
        "entree": 232, "degagement": 232, "placard": 218, "buanderie": 226, "bureau": 236, "escalier": 215}.items()},
}


@dataclass
class Style:
    famille: str = "architecte"
    px_par_m: float = 100.0  # l'échelle de base du dessin
    fond: tuple[int, int, int] = (255, 255, 255)
    murs: tuple[int, int, int] = (40, 40, 40)  # couleur de l'aplat des murs
    murs_contour: bool = False  # murs cernés d'un trait (style agence : aplat clair, trait foncé)
    murs_contour_couleur: tuple[int, int, int] = (30, 30, 30)
    traits: tuple[int, int, int] = (40, 40, 40)  # portes, fenêtres, cotes
    textes: tuple[int, int, int] = (50, 50, 50)
    epaisseur_trait: float = 0.018  # en mètres (converti en pixels selon l'échelle)
    pieces_colorees: bool = False
    palette: str = "pastel"
    mobilier: bool = False
    cotes: bool = True  # chaînes de cotes autour du plan
    cotes_partielles: bool = True
    noms: bool = True  # nom des pièces
    surfaces: bool = True  # surface écrite sous le nom
    symboles: bool = True  # battants et arcs des portes, traits des fenêtres
    arcs: bool = True
    doubles_vantaux: bool = False
    cartouche: bool = True
    hsp_ecrite: bool = True
    titre: bool = True
    fleche_nord: bool = True
    echelle_graphique: bool = False
    police: str = POLICES[0]
    taille_texte: int = 20
    marges: tuple[int, int, int, int] = (170, 140, 140, 380)  # haut, bas, gauche, droite, en pixels
    rotation: float = 0.0  # degrés, appliqués à toute la page
    perspective: float = 0.0  # 0 : aucune ; 0,05 : les coins de la page bougent de 5 %
    # Vraie photo (option --vraie-camera) : la page vue par un appareil photo, selon les lois de l'optique,
    # au lieu de coins bougés au hasard. Focale en fraction du grand côté de la page, inclinaisons en degrés
    # (autour de l'axe horizontal, puis vertical), décalage du centre de la photo en fraction de la page.
    focale: float = 0.0  # 0 : pas de vraie caméra
    inclinaison: tuple[float, float] = (0.0, 0.0)
    centre_optique: tuple[float, float] = (0.0, 0.0)
    focale_photo: float = 0.0  # focale en fraction du grand côté de la photo entière (0 : photo recadrée sur la page)
    format_photo: float = 4 / 3  # grand côté / petit côté de la photo entière
    salissure: str = ""  # "", photocopie, taches, bruit, jpeg, telephone, grain
    contraste: float = 1.0  # < 1 : plus pâle ; > 1 : plus contrasté
    papier: int = 255  # le blanc du papier (230 : scanner un peu gris)
    realisme: Realisme | None = None  # photo réaliste (option --photo-realiste) : table, plis, ombres, reflets

    def en_dict(self) -> dict:
        return asdict(self)

    @property
    def niveaux_gris(self) -> bool:
        return self.fond == (255, 255, 255) and not self.pieces_colorees and self.murs[0] == self.murs[1] == self.murs[2]


def style_au_hasard(rng: random.Random, diversite: int = 2, famille: str | None = None) -> Style:
    """Un style tiré au hasard. `diversite` de 0 (sage) à 3 (tout est permis), `famille` pour l'imposer."""
    diversite = max(0, min(3, diversite))
    if famille is None:
        poids = {"architecte": 4, "agence": 3, "minimaliste": 1, "scan": 2, "photo": 1, "colore": 2, "croquis": 1}
        if diversite == 0:
            poids = {"architecte": 1}
        elif diversite == 1:
            poids = {"architecte": 4, "agence": 2, "colore": 1}
        famille = rng.choices(list(poids), weights=list(poids.values()))[0]
    px = rng.randint(60, 130) if diversite >= 1 else rng.randint(80, 110)
    s = Style(famille=famille, px_par_m=px, police=rng.choice(POLICES) if diversite >= 1 else POLICES[0])
    s.taille_texte = round(px * rng.uniform(0.17, 0.23))
    gris = rng.randint(0, 60)
    s.murs = (gris, gris, gris)
    t = min(gris + rng.randint(0, 30), 80)
    s.traits = (t, t, t)
    x = rng.randint(20, 80)
    s.textes = (x, x, x)
    s.cotes_partielles = rng.random() < 0.8
    s.doubles_vantaux = rng.random() < 0.3
    s.cartouche = rng.random() < 0.85
    s.hsp_ecrite = s.cartouche and rng.random() < 0.85
    s.titre = rng.random() < 0.8
    s.fleche_nord = rng.random() < 0.7

    if famille == "agence":
        s.pieces_colorees = rng.random() < 0.8
        s.palette = rng.choice(list(PALETTES))
        s.murs_contour = rng.random() < 0.7
        if s.murs_contour:
            g = rng.randint(120, 200)
            s.murs = (g, g, g)
        s.mobilier = rng.random() < 0.8
        s.cotes = rng.random() < 0.4
        s.cotes_partielles = s.cotes and rng.random() < 0.5
        s.cartouche = rng.random() < 0.3
        s.hsp_ecrite = s.cartouche and rng.random() < 0.5
        s.echelle_graphique = rng.random() < 0.4
    elif famille == "colore":
        s.pieces_colorees = True
        s.palette = rng.choice(list(PALETTES))
        s.mobilier = rng.random() < 0.4
        s.cotes = rng.random() < 0.7
    elif famille == "minimaliste":
        s.symboles = rng.random() < 0.3
        s.arcs = s.symboles
        s.cotes = rng.random() < 0.3
        s.cotes_partielles = False
        s.noms = rng.random() < 0.6
        s.surfaces = rng.random() < 0.3
        s.cartouche = False
        s.hsp_ecrite = False
        s.titre = rng.random() < 0.3
        s.fleche_nord = False
        s.epaisseur_trait = rng.uniform(0.01, 0.015)
    elif famille == "croquis":
        s.epaisseur_trait = rng.uniform(0.02, 0.035)
        s.murs_contour = True
        g = rng.randint(200, 245)
        s.murs = (g, g, g)
        s.arcs = rng.random() < 0.7
        s.surfaces = rng.random() < 0.5
    elif famille == "scan":
        s.salissure = rng.choice(["photocopie", "taches", "grain", "jpeg", "photocopie"])
        s.papier = rng.randint(225, 250)
        s.rotation = rng.choice((-1, 1)) * rng.uniform(0.3, 3.0) if diversite >= 1 else 0.0
        s.contraste = rng.uniform(0.75, 1.1)
    elif famille == "photo":
        s.salissure = "telephone"
        s.rotation = rng.choice((-1, 1)) * rng.uniform(0.5, 6.0)
        s.perspective = rng.uniform(0.02, 0.06) if diversite >= 2 else rng.uniform(0.01, 0.03)
        s.papier = rng.randint(215, 245)
    else:  # architecte
        s.mobilier = rng.random() < 0.15
        s.epaisseur_trait = rng.uniform(0.014, 0.022)
        if rng.random() < 0.25:  # murs épais : une épaisseur de trait plus forte et un noir franc
            s.murs = (0, 0, 0)

    if diversite >= 2:
        if rng.random() < 0.25 and not s.rotation:
            s.rotation = rng.choice((-1, 1)) * rng.uniform(0.2, 2.0)
        if rng.random() < 0.3:
            s.contraste = rng.uniform(0.7, 1.2)
        if rng.random() < 0.3 and not s.salissure:
            s.salissure = rng.choice(["bruit", "jpeg", "grain"])
        if rng.random() < 0.15:
            s.pieces_colorees = not s.pieces_colorees
            s.palette = rng.choice(list(PALETTES))
    if diversite >= 3:
        if rng.random() < 0.3:
            s.rotation = rng.choice((-1, 1)) * rng.uniform(1.0, 8.0)
        if rng.random() < 0.3:
            s.perspective = rng.uniform(0.01, 0.07)
        if rng.random() < 0.3:
            s.cotes, s.noms, s.surfaces = rng.random() < 0.5, rng.random() < 0.5, rng.random() < 0.5
    s.marges = (rng.randint(120, 220), rng.randint(90, 200), rng.randint(90, 200), rng.randint(220, 420))
    if not s.cotes and not s.cartouche:
        s.marges = tuple(round(v * 0.6) for v in s.marges)  # type: ignore[assignment]
    return s


# ---------------------------------------------------------------- salissures (pixels seulement)


def salir(image: np.ndarray, style: Style, rng: random.Random, page: np.ndarray | None = None,
          plis: np.ndarray | None = None) -> np.ndarray:
    """L'image RGB abîmée selon le style (contraste, papier, salissure). Ne déplace aucun pixel.

    Photo réaliste (`style.realisme`) : `page` dit quelle part de chaque pixel est couverte par la feuille,
    `plis` la lumière des plis ; la feuille est posée sur une table (voir moteur.generateur.photo)."""
    img = image.astype(np.float32)
    if style.papier < 255:
        img = img * (style.papier / 255)
    if style.contraste != 1.0:
        img = 128 + (img - 128) * style.contraste
    nrng = np.random.default_rng(rng.getrandbits(32))
    r = style.realisme
    if r is not None and page is not None:
        img = lumiere(composer(img, page, plis, r, rng, nrng), page, r, rng, nrng)
    s = style.salissure
    if s == "photocopie":
        gris = cv2.cvtColor(_octets(img), cv2.COLOR_RGB2GRAY)
        img = cv2.cvtColor(_photocopie(gris, rng, nrng), cv2.COLOR_GRAY2RGB).astype(np.float32)
    elif s == "taches":
        gris = cv2.cvtColor(_octets(img), cv2.COLOR_RGB2GRAY)
        img = cv2.cvtColor(_taches(gris, rng, nrng), cv2.COLOR_GRAY2RGB).astype(np.float32)
    elif s == "grain":
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.5, 1.0)) + nrng.normal(0, rng.uniform(4, 10), img.shape)
    elif s == "bruit":
        img = img + nrng.normal(0, rng.uniform(3, 8), img.shape)
    elif s == "telephone":
        img = _eclairage(img, rng, nrng)
        if r is not None and page is not None:
            img = capteur(img, r, rng, nrng)
    if s in ("jpeg", "telephone") or (s and rng.random() < 0.3):
        img = _jpeg(_octets(img), rng.randint(35, 80) if s == "jpeg" else rng.randint(60, 90)).astype(np.float32)
    return _octets(img)


def _eclairage(img: np.ndarray, rng: random.Random, nrng: np.random.Generator) -> np.ndarray:
    """La lumière inégale d'une photo : un côté plus clair, une ombre douce, un blanc un peu teinté, du flou."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = rng.uniform(0, 2 * np.pi)
    pente = ((xx - w / 2) * np.cos(a) + (yy - h / 2) * np.sin(a)) / max(h, w)
    lumiere = 1 + rng.uniform(0.1, 0.3) * pente
    ox, oy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.25, 0.5) * max(h, w)
    lumiere *= 1 - rng.uniform(0.08, 0.22) * np.exp(-((xx - ox) ** 2 + (yy - oy) ** 2) / (2 * r * r))
    img = img * lumiere[:, :, None] * rng.uniform(0.85, 1.0)
    teinte = np.array([rng.uniform(0.9, 1.0), rng.uniform(0.95, 1.0), rng.uniform(0.9, 1.05)], np.float32)
    img = img * teinte[None, None, :]
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.5, 1.1)) + nrng.normal(0, 3, img.shape)
    return img


def _octets(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def _jpeg(image: np.ndarray, qualite: int) -> np.ndarray:
    ok, octets = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, qualite])
    assert ok
    return cv2.cvtColor(cv2.imdecode(octets, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
