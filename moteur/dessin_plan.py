"""Dessiner le plan coté d'un logement, à partir de son logement.json (étape 5b).

Le dessin suit les conventions des plans d'architecte, comme le plan du cas
test n°0 :
- les murs en aplat foncé, interrompus aux portes et fenêtres ;
- une porte : un battant (trait droit) et un quart de cercle (son ouverture) ;
- une fenêtre : deux traits le long des faces du mur et un au milieu (le vitrage) ;
- une porte-fenêtre : un trait de vitrage, un battant et son quart de cercle ;
- des cotes intérieures en mètres (« 4,80 »), avec une marque à chaque bout ;
- dans chaque pièce, son nom et sa surface (« 9,92 m² ») ;
- un cartouche : épaisseurs des murs, hauteur sous plafond, flèche du nord.

Un « style » fait varier le dessin d'un plan à l'autre (échelle, gris, taille
des textes, présence des cotes partielles…), pour que la lecture apprenne à
reconnaître des plans qui ne se ressemblent pas tous. Les salissures (scan,
photo de travers) viendront à l'étape 5c.

Le dessin utilise Pillow (déjà installé avec RapidOCR) et trois polices libres
jointes au dépôt (moteur/polices), pour que le même plan soit dessiné pareil
sur le Mac et sur le PC.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Place autour du logement, en pixels : titre et cotes en haut, cotes en bas et à gauche,
# cotes et cartouche à droite.
MARGE_HAUT, MARGE_BAS, MARGE_GAUCHE, MARGE_DROITE = 170, 140, 140, 380
RECUL_COTE = 60  # distance entre le mur et une ligne de cote
DOUBLE_VANTAIL_MIN = 1.20  # en mètres : à partir de cette largeur, une ouverture peut avoir deux battants
POLICES = Path(__file__).parent / "polices"
NOMS_POLICES = ("Inter-Regular.otf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf")


@dataclass
class Style:
    px_par_m: int = 100  # l'échelle du dessin
    gris_murs: int = 40  # 0 = noir, 255 = blanc
    gris_traits: int = 40  # portes, fenêtres, cotes
    gris_textes: int = 50
    taille_texte: int = 20
    cotes_partielles: bool = True  # la chaîne de cotes pièce par pièce, en bas et à droite
    doubles_vantaux: bool = False  # les portes et portes-fenêtres larges dessinées à deux battants
    arcs: bool = True  # les quarts de cercle des portes
    cartouche: bool = True  # le texte « Murs extérieurs : 20 cm… » et la flèche du nord
    hsp_ecrite: bool = True  # la hauteur sous plafond, dans le cartouche
    police: str = NOMS_POLICES[0]

    def en_dict(self) -> dict:
        return asdict(self)


def style_au_hasard(rng: random.Random) -> Style:
    """Un style de dessin tiré au hasard, dans des limites où un plan reste lisible."""
    px = rng.randint(70, 130)
    gris = rng.randint(0, 60)
    return Style(
        px_par_m=px,
        gris_murs=gris,
        gris_traits=min(gris + rng.randint(0, 30), 70),
        gris_textes=rng.randint(20, 80),
        taille_texte=round(px * rng.uniform(0.17, 0.22)),
        cotes_partielles=rng.random() < 0.8,
        doubles_vantaux=rng.random() < 0.3,
        arcs=rng.random() < 0.95,
        cartouche=(cartouche := rng.random() < 0.9),
        hsp_ecrite=rng.random() < 0.85 and cartouche,  # sans cartouche, la hauteur n'est écrite nulle part
        police=rng.choice(NOMS_POLICES),
    )


def dessiner_plan(logement: dict, style: Style | None = None, titre: str | None = None,
                  battants: dict[str, tuple[int, int]] | None = None) -> np.ndarray:
    """Le plan du logement, en image en niveaux de gris (tableau numpy, 255 = blanc).

    `battants` : pour chaque porte, (côté où elle s'ouvre : +1 ou -1 le long de x ou y,
    charnière : 0 du côté du début de l'ouverture, 1 du côté de sa fin). Sans indication,
    la porte s'ouvre vers une pièce (de préférence la plus petite), charnière au début.
    """
    style = style or Style()
    d = _Dessin(logement, style, battants or {})
    d.murs()
    d.ouvertures()
    d.pieces()
    d.cotes()
    if style.cartouche:
        d.cartouche()
    if titre:
        d.texte((40, 40), titre, round(style.taille_texte * 1.2), style.gris_textes, ancre="lm")
    return np.asarray(d.image)


@lru_cache(maxsize=64)
def _police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(POLICES / nom), max(8, taille))


def _fr(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


class _Dessin:
    def __init__(self, logement: dict, style: Style, battants: dict[str, tuple[int, int]]):
        self.log = logement
        self.style = style
        self.s = style.px_par_m
        self.battants = battants
        self.murs_par_id = {m["id"]: m for m in logement["murs"]}
        bords = [_rectangle_du_mur(m) for m in logement["murs"]]
        self.xmin = min(b[0] for b in bords)
        self.ymin = min(b[1] for b in bords)
        self.xmax = max(b[2] for b in bords)
        self.ymax = max(b[3] for b in bords)
        # La marge de droite s'élargit si le cartouche est écrit gros.
        droite = max(MARGE_DROITE, RECUL_COTE + 100 + round(style.taille_texte * 0.85 * 16))
        largeur = round((self.xmax - self.xmin) * self.s) + MARGE_GAUCHE + droite
        hauteur = round((self.ymax - self.ymin) * self.s) + MARGE_HAUT + MARGE_BAS
        self.image = Image.new("L", (largeur, hauteur), 255)
        self.dessin = ImageDraw.Draw(self.image)
        self.fin = max(2, round(self.s * 0.018))  # épaisseur d'un trait fin, en pixels
        self.moyen = max(2, round(self.s * 0.03))  # battant de porte

    # --- Conversions ---

    def px(self, x: float, y: float) -> tuple[float, float]:
        """Mètres (y vers le nord) → pixels (y vers le bas)."""
        return MARGE_GAUCHE + (x - self.xmin) * self.s, MARGE_HAUT + (self.ymax - y) * self.s

    def rect(self, x0: float, y0: float, x1: float, y1: float, gris: int) -> None:
        (a, b), (c, d) = self.px(x0, y1), self.px(x1, y0)
        self.dessin.rectangle((round(a), round(b), round(c) - 1, round(d) - 1), fill=gris)

    def ligne(self, p: tuple[float, float], q: tuple[float, float], gris: int, epaisseur: int) -> None:
        self.dessin.line((self.px(*p), self.px(*q)), fill=gris, width=epaisseur)

    def texte(self, xy: tuple[float, float], texte: str, taille: int, gris: int, ancre: str = "mm",
              vertical: bool = False) -> None:
        police = _police(self.style.police, taille)
        if not vertical:
            self.dessin.text(xy, texte, fill=gris, font=police, anchor=ancre)
            return
        # Texte vertical (cotes des murs verticaux) : écrit à plat, puis tourné d'un quart de tour.
        g, h, d, b = police.getbbox(texte)
        vignette = Image.new("L", (d - g + 4, b - h + 4), 0)
        ImageDraw.Draw(vignette).text((2 - g, 2 - h), texte, fill=255, font=police)
        vignette = vignette.rotate(90, expand=True)
        x, y = round(xy[0] - vignette.width / 2), round(xy[1] - vignette.height / 2)
        self.image.paste(Image.new("L", vignette.size, gris), (x, y), vignette)

    # --- Murs et ouvertures ---

    def murs(self) -> None:
        for m in self.log["murs"]:
            self.rect(*_rectangle_du_mur(m, self.log["murs"]), self.style.gris_murs)

    def ouvertures(self) -> None:
        for o in self.log["ouvertures"]:
            mur = self.murs_par_id[o["mur"]]
            (ax, ay), (bx, by) = mur["debut"], mur["fin"]
            longueur = math.dist((ax, ay), (bx, by))
            ux, uy = (bx - ax) / longueur, (by - ay) / longueur  # le long du mur
            nx, ny = -uy, ux  # en travers du mur
            e = mur["epaisseur"] / 2
            t0, t1 = o["position"], o["position"] + o["largeur"]

            def point(t: float, n: float) -> tuple[float, float]:
                return ax + t * ux + n * nx, ay + t * uy + n * ny

            # Le trou dans le mur.
            coins = [point(t0, -e), point(t1, -e), point(t1, e), point(t0, e)]
            xs, ys = [c[0] for c in coins], [c[1] for c in coins]
            self.rect(min(xs), min(ys), max(xs), max(ys), 255)
            gris = self.style.gris_traits
            if o["type"] == "fenetre":
                for n in (-e, 0, e):
                    self.ligne(point(t0, n), point(t1, n), gris, self.fin)
                for t in (t0, t1):
                    self.ligne(point(t, -e), point(t, e), gris, self.fin)
                continue
            if o["type"] == "porte_fenetre":
                self.ligne(point(t0, 0), point(t1, 0), gris, self.fin)
            vers, charniere = self.battants.get(o["id"]) or self._battant_par_defaut(o, mur)
            sens = vers * (nx + ny)  # nx + ny vaut ±1 : le côté choisi, dans le repère du mur
            if self.style.doubles_vantaux and o["largeur"] >= DOUBLE_VANTAIL_MIN:
                milieu = (t0 + t1) / 2  # deux battants, chacun de la moitié de la largeur
                vantaux = [(t0, milieu), (t1, milieu)]
            else:
                vantaux = [(t0, t1) if charniere == 0 else (t1, t0)]
            for pivot_t, autre_t in vantaux:
                largeur = abs(autre_t - pivot_t)
                pivot = point(pivot_t, sens * e)
                bout = (pivot[0] + sens * largeur * nx, pivot[1] + sens * largeur * ny)
                self.ligne(pivot, bout, gris, self.moyen)
                if self.style.arcs:
                    self._arc(pivot, bout, point(autre_t, sens * e), gris)

    def _arc(self, centre: tuple[float, float], a: tuple[float, float], b: tuple[float, float], gris: int) -> None:
        cx, cy = self.px(*centre)
        r = math.dist(centre, a) * self.s
        angles = []
        for p in (a, b):
            x, y = self.px(*p)
            angles.append(math.degrees(math.atan2(y - cy, x - cx)) % 360)
        debut, fin = angles
        if (fin - debut) % 360 > 180:  # Pillow tourne dans le sens des aiguilles d'une montre
            debut, fin = fin, debut
        self.dessin.arc((cx - r, cy - r, cx + r, cy + r), debut, fin, fill=min(gris + 60, 160), width=1)

    def _battant_par_defaut(self, o: dict, mur: dict) -> tuple[int, int]:
        """Sans indication : la porte s'ouvre vers la plus petite des pièces qui la bordent."""
        (ax, ay), (bx, by) = mur["debut"], mur["fin"]
        longueur = math.dist((ax, ay), (bx, by))
        t = o["position"] + o["largeur"] / 2
        mx, my = ax + t * (bx - ax) / longueur, ay + t * (by - ay) / longueur
        vertical = abs(bx - ax) < abs(by - ay)
        choix = []
        for vers in (1, -1):
            d = mur["epaisseur"] / 2 + 0.05
            p = (mx + vers * d, my) if vertical else (mx, my + vers * d)
            for piece in self.log.get("pieces", []):
                if _dedans(p, piece["contour"]):
                    choix.append((_surface(piece["contour"]), vers))
        return (min(choix)[1] if choix else 1), 0

    # --- Pièces ---

    def pieces(self) -> None:
        taille = self.style.taille_texte
        for p in self.log.get("pieces", []):
            xs = [c[0] for c in p["contour"]]
            ys = [c[1] for c in p["contour"]]
            cx, cy = self.px((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            # Un nom trop long pour la pièce est écrit plus petit, comme le ferait un dessinateur.
            place = (max(xs) - min(xs)) * self.s * 0.9
            t = taille
            while t > 10 and _police(self.style.police, t).getlength(p["nom"]) > place:
                t -= 1
            self.texte((cx, cy - taille * 0.6), p["nom"], t, self.style.gris_textes)
            surface = p.get("surface") or _surface(p["contour"])
            self.texte((cx, cy + taille * 0.6), f"{_fr(surface)} m²", taille - 2, min(self.style.gris_textes + 60, 150))

    # --- Cotes ---

    def cotes(self) -> None:
        """Cotes intérieures : largeur et profondeur totales, et pièce par pièce en bas et à droite."""
        pieces = [_cadre(p["contour"]) for p in self.log.get("pieces", [])]
        if pieces:
            x0, y0 = min(p[0] for p in pieces), min(p[1] for p in pieces)
            x1, y1 = max(p[2] for p in pieces), max(p[3] for p in pieces)
        else:
            x0, y0, x1, y1 = self.xmin, self.ymin, self.xmax, self.ymax
        haut = self.px(0, self.ymax)[1] - RECUL_COTE
        gauche = self.px(self.xmin, 0)[0] - RECUL_COTE
        bas = self.px(0, self.ymin)[1] + RECUL_COTE
        droite = self.px(self.xmax, 0)[0] + RECUL_COTE
        self._chaine([(x0, x1)], haut, horizontale=True, cote_texte=-1)
        self._chaine([(y0, y1)], gauche, horizontale=False, cote_texte=-1)
        if self.style.cotes_partielles:
            en_bas = sorted((p[0], p[2]) for p in pieces if abs(p[1] - y0) < 1e-6)
            a_droite = sorted((p[1], p[3]) for p in pieces if abs(p[2] - x1) < 1e-6)
            if len(en_bas) > 1:
                self._chaine(en_bas, bas, horizontale=True, cote_texte=1)
            if len(a_droite) > 1:
                self._chaine(a_droite, droite, horizontale=False, cote_texte=1)

    def _chaine(self, intervalles: list[tuple[float, float]], position: float, horizontale: bool,
                cote_texte: int) -> None:
        """Une ligne de cotes : un trait par intervalle, une marque à chaque bout, la valeur à côté."""
        gris = self.style.gris_traits
        taille = round(self.style.taille_texte * 0.9)
        for a, b in intervalles:
            if horizontale:
                p, q = (self.px(a, 0)[0], position), (self.px(b, 0)[0], position)
            else:
                p, q = (position, self.px(0, a)[1]), (position, self.px(0, b)[1])
            self.dessin.line((p, q), fill=gris, width=1)
            for x, y in (p, q):
                if horizontale:
                    self.dessin.line(((x, y - 9), (x, y + 9)), fill=gris, width=1)
                else:
                    self.dessin.line(((x - 9, y), (x + 9, y)), fill=gris, width=1)
                self.dessin.line(((x - 7, y + 7), (x + 7, y - 7)), fill=gris, width=2)
            milieu = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ecart = (taille * 0.75 + 8) * cote_texte  # assez loin du trait pour que la lecture ne les confonde pas
            if horizontale:
                self.texte((milieu[0], milieu[1] + ecart), _fr(b - a), taille, self.style.gris_textes)
            else:
                self.texte((milieu[0] + ecart, milieu[1]), _fr(b - a), taille, self.style.gris_textes, vertical=True)

    # --- Cartouche ---

    def cartouche(self) -> None:
        x = self.px(self.xmax, 0)[0] + RECUL_COTE + 60
        y = self.px(0, self.ymax)[1] + 30
        taille = round(self.style.taille_texte * 0.85)
        ext = max((m["epaisseur"] for m in self.log["murs"]), default=0)
        cloisons = min((m["epaisseur"] for m in self.log["murs"]), default=0)
        lignes = ["Cotes intérieures, en mètres", f"Murs extérieurs : {round(ext * 100)} cm"]
        if cloisons < ext:
            lignes.append(f"Cloisons : {round(cloisons * 100)} cm")
        if self.style.hsp_ecrite:
            lignes.append(f"Hauteur sous plafond : {_fr(self.log['hauteur_sous_plafond'])} m")
        gris = min(self.style.gris_textes + 50, 140)
        for i, ligne in enumerate(lignes):
            self.texte((x, y + i * taille * 1.5), ligne, taille, gris, ancre="lm")
        # La flèche du nord.
        fx, fy = x + 20, y + len(lignes) * taille * 1.5 + 30
        self.dessin.polygon([(fx, fy), (fx - 10, fy + 40), (fx + 10, fy + 40)], fill=self.style.gris_murs)
        self.texte((fx, fy + 58), "N", taille, self.style.gris_textes)


# ---------- Géométrie ----------


def _rectangle_du_mur(mur: dict, murs: list[dict] | None = None) -> tuple[float, float, float, float]:
    """Le rectangle occupé par le mur (x0, y0, x1, y1), rallongé aux angles qu'il partage avec un autre mur."""
    (ax, ay), (bx, by) = mur["debut"], mur["fin"]
    e = mur["epaisseur"] / 2
    longueur = math.dist((ax, ay), (bx, by))
    ux, uy = (bx - ax) / longueur, (by - ay) / longueur
    rallonges = []
    for bout in (mur["debut"], mur["fin"]):
        autres = [m["epaisseur"] / 2 for m in murs or [] if m is not mur
                  and any(math.dist(bout, q) < 1e-6 for q in (m["debut"], m["fin"]))]
        rallonges.append(max(autres, default=0.0))
    ax, ay = ax - ux * rallonges[0], ay - uy * rallonges[0]
    bx, by = bx + ux * rallonges[1], by + uy * rallonges[1]
    nx, ny = -uy * e, ux * e
    xs = [ax + nx, ax - nx, bx + nx, bx - nx]
    ys = [ay + ny, ay - ny, by + ny, by - ny]
    return min(xs), min(ys), max(xs), max(ys)


def _cadre(contour: list) -> tuple[float, float, float, float]:
    xs = [c[0] for c in contour]
    ys = [c[1] for c in contour]
    return min(xs), min(ys), max(xs), max(ys)


def _surface(contour: list) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def _dedans(point: tuple[float, float], contour: list) -> bool:
    x, y = point
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans
