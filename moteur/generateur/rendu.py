"""Dessiner le plan d'un niveau ET ses masques, dans le même repère pixel.

Le principe qui garantit des annotations exactes : tout ce qui est dessiné (murs, portes,
fenêtres, pièces, meubles) part des mêmes polygones en millimètres, convertis en pixels par
un seul `Repere`. L'image du plan et les masques sont d'abord dessinés « à plat » ; si le
style demande une rotation ou une perspective (scan de travers, photo), la même matrice est
appliquée à l'image (lissée) et aux polygones, et les masques sont dessinés directement
dans le repère final à partir des polygones transformés (aucun rééchantillonnage). Les salissures (grain, taches, JPEG) viennent en
dernier et ne déplacent aucun pixel.

Sorties pour un niveau (voir `Rendu`) :

- `plan`              : l'image RGB du plan, selon le style ;
- `plan_sans_mobilier`: la même sans les meubles mais avec l'escalier (seulement si le style dessine des meubles) ;
- `masque_semantique` : une classe par pixel (voir annotations.CLASSES) ;
- `masque_pieces`     : l'identifiant de pièce par pixel (0 = aucune) ;
- `masque_elements`   : l'identifiant de mur ou d'ouverture par pixel (0 = aucun) ;
- `contours`          : les bords des murs et ouvertures (255), le reste 0 ;
- `hauteur`           : la hauteur en millimètres des éléments pleins vus de dessus, sous un plan de
                        coupe à 1,50 m (murs : hauteur sous plafond ; fenêtre : allège ; porte : 0 ;
                        sol : 0 ; meubles : leur hauteur ; escalier : montée progressive) ;
- `annotations`       : la correspondance pixels ↔ mètres (matrice, échelle) et les polygones en pixels.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw

from moteur.dessin_plan import _police
from moteur.generateur.annotations import CLASSES, rect_de_l_ouverture, rect_du_mur, rasteriser
from moteur.generateur.logements import LogementGenere, MurLibre, Niveau, Ouverture, Piece, Rect, contour_piece, surface_piece
from moteur.generateur.mobilier import Meuble, meubler_niveau
from moteur.generateur.photo import plis_a_plat
from moteur.generateur import lot2 as L
from moteur.generateur import variete as V
from moteur.generateur.variantes import PALETTES, Style, salir

Point = tuple[float, float]
RECUL_COTE = 60  # pixels entre le mur et une ligne de cote
DOUBLE_VANTAIL_MIN = 1200  # mm : à partir de cette largeur, une porte peut avoir deux battants
PLAN_DE_COUPE = 1500  # mm : la hauteur à laquelle le plan « coupe » le logement
BLANC_SOUS_ECHELLE = 25  # pixels de papier laissés sous le texte de la barre d'échelle


def _place_echelle(style: Style) -> tuple[float, float]:
    """Où tombe la barre d'échelle, en pixels sous le bas du logement : (haut de la barre, bas de son texte).

    Sert au dessin de la barre ET à la marge du bas, pour que la barre et son « N m » restent
    entiers dans la page (avant 0.1.1, la moitié sortaient par le bas quand la marge était petite).
    """
    haut = RECUL_COTE + (style.taille_texte * 1.8 if style.cotes else 10)
    police = _police(style.police, round(style.taille_texte * 0.8))
    return haut, haut + 22 + max(police.getbbox(t, anchor="mm")[3] for t in ("0", "2 m"))


@dataclass
class Rendu:
    images: dict[str, np.ndarray]
    annotations: dict
    style: Style
    meubles: dict[str, list[Meuble]] = field(default_factory=dict)


def _vue_par_camera(points: np.ndarray, centre: tuple[float, float], cote: float, style) -> np.ndarray:
    """Où tombent des points de la page (pixels à plat) sur la photo d'un appareil incliné (sténopé).

    La page est posée à plat ; l'appareil, à une distance égale à sa focale, la regarde penché de
    `style.inclinaison` degrés (autour de l'axe horizontal de la page, puis du vertical). C'est ce que fait
    un vrai téléphone : les proportions perdues par la perspective se retrouvent par l'optique (moteur.redressement)."""
    f = style.focale * cote
    ax, ay = (math.radians(a) for a in style.inclinaison)
    rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    R = ry @ rx
    dx, dy = style.centre_optique[0] * cote, style.centre_optique[1] * cote
    sortie = []
    for x, y in points:
        X = R @ (x - centre[0] - dx, y - centre[1] - dy, 0.0) + (0.0, 0.0, f)
        sortie.append([centre[0] + dx + f * X[0] / X[2], centre[1] + dy + f * X[1] / X[2]])
    return np.array(sortie)


class Repere:
    """Millimètres du logement → pixels de l'image finale.

    Deux étapes : une affinité (échelle et marges) vers l'image « à plat », puis une homographie
    (rotation + perspective) vers l'image finale. `H` est la matrice 3×3 totale (mm → pixels).
    """

    def __init__(self, cadre: Rect, style: Style, rng: random.Random, nb_pieces: int = 12):
        self.s = style.px_par_m / 1000  # pixels par millimètre
        haut, bas, gauche, droite = style.marges
        if style.lot2 is not None:  # avant le reste : tableaux et légendes prennent leur place, l'image garde la taille des masques
            haut, bas, gauche, droite = L.marges_lot2(style, (haut, bas, gauche, droite), nb_pieces)
        if style.cartouche:  # la marge de droite s'élargit si le cartouche est écrit gros
            droite = max(droite, RECUL_COTE + 100 + round(style.taille_texte * 0.85 * 17))
        if style.echelle_graphique:  # la marge du bas s'élargit pour garder la barre d'échelle entière
            bas = max(bas, math.ceil(_place_echelle(style)[1]) + BLANC_SOUS_ECHELLE)
        self.xmin, self.ymin, self.xmax, self.ymax = cadre.x0, cadre.y0, cadre.x1, cadre.y1
        self.largeur0 = round((self.xmax - self.xmin) * self.s) + gauche + droite
        self.hauteur0 = round((self.ymax - self.ymin) * self.s) + haut + bas
        # mm → pixels à plat : u = gauche + (x - xmin) s ; v = haut + (ymax - y) s
        self.A = np.array([[self.s, 0, gauche - self.xmin * self.s],
                           [0, -self.s, haut + self.ymax * self.s],
                           [0, 0, 1]], dtype=np.float64)
        coins = np.float32([[0, 0], [self.largeur0, 0], [self.largeur0, self.hauteur0], [0, self.hauteur0]])
        cx, cy = self.largeur0 / 2, self.hauteur0 / 2
        a = math.radians(style.rotation)
        tournes = []
        for x, y in coins:
            dx, dy = x - cx, y - cy
            tournes.append([cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)])
        tournes = np.float32(tournes)
        if style.focale:
            # Une vraie photo n'est pas recadrée sur la page : son centre est l'axe de l'objectif. On garde donc
            # autant de place de chaque côté de ce centre (le reste de la table apparaît sur la photo).
            cote = max(self.largeur0, self.hauteur0)
            axe = np.float32([cx + style.centre_optique[0] * cote, cy + style.centre_optique[1] * cote])
            plats = tournes
            for _ in range(10):
                tournes = np.float32(_vue_par_camera(plats, (cx, cy), cote, style))
                demi = np.abs(tournes - axe).max(axis=0)
                if not style.focale_photo:
                    break
                # Une photo de téléphone est au format 4:3 (ou 16:9), et sa focale (objectif ~26 mm) vaut environ
                # 0,77 fois son grand côté. Si la page n'y tient pas, le photographe recule (la focale, en pages, grandit).
                cadre = style.focale * cote / style.focale_photo / 2
                besoin = max(demi.max(), demi.min() * style.format_photo)
                if besoin <= cadre:
                    break
                style.focale = float(style.focale * besoin / cadre * 1.01)
            if style.focale_photo:
                long_ = style.focale * cote / style.focale_photo / 2
                court = long_ / style.format_photo
                demi = np.float32([long_, court] if demi[0] >= demi[1] else [court, long_])
            decal = axe - demi
            tournes = np.vstack([tournes, axe + demi])  # le coin opposé fixe la taille de la photo
        else:
            if style.perspective:
                p = style.perspective
                tournes += np.float32([[rng.uniform(-p, p) * self.largeur0, rng.uniform(-p, p) * self.hauteur0] for _ in range(4)])
            decal = tournes.min(axis=0)
        tournes -= decal
        self.largeur, self.hauteur = int(math.ceil(tournes[:, 0].max())), int(math.ceil(tournes[:, 1].max()))
        self.W = cv2.getPerspectiveTransform(coins, tournes[:4]).astype(np.float64)
        self.identite = not style.rotation and not style.perspective and not style.focale
        self.H = self.W @ self.A

    def plat(self, x: float, y: float) -> Point:
        """mm → pixels de l'image à plat (celle où l'on dessine)."""
        u, v, _ = self.A @ (x, y, 1)
        return float(u), float(v)

    def final(self, x: float, y: float) -> Point:
        """mm → pixels de l'image finale."""
        u, v, w = self.H @ (x, y, 1)
        return float(u / w), float(v / w)

    def deformer(self, image: np.ndarray, lisse: bool, bord) -> np.ndarray:
        if self.identite:
            return image
        return cv2.warpPerspective(image, self.W, (self.largeur, self.hauteur),
                                   flags=cv2.INTER_LINEAR if lisse else cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=bord)


def _fr(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


class _Dessin:
    """Le dessin d'un niveau : l'image RGB et, en parallèle, les masques, tous à plat."""

    def __init__(self, log: LogementGenere, niveau: Niveau, style: Style, repere: Repere,
                 meubles: dict[str, list[Meuble]], avec_mobilier: bool):
        self.log, self.niv, self.style, self.rep = log, niveau, style, repere
        self.meubles = meubles if avec_mobilier else {}
        taille = (repere.largeur0, repere.hauteur0)
        self.image = Image.new("RGB", taille, style.fond)
        self.d = ImageDraw.Draw(self.image)
        # Les masques sont dessinés directement dans le repère final (après rotation/perspective), à partir
        # des polygones transformés : ils sont exacts, sans rééchantillonnage.
        self.semantique = np.zeros((repere.hauteur, repere.largeur), np.uint8)
        self.pieces_m = np.zeros_like(self.semantique)
        self.elements = np.zeros_like(self.semantique)
        self.hauteur = np.zeros((repere.hauteur, repere.largeur), np.uint16)
        self.fin = max(1, round(repere.s * 1000 * style.epaisseur_trait))
        self.moyen = max(2, round(repere.s * 1000 * 0.03))
        # Qui dessine les murs : la variété du style, ou celle que demande le lot 2.
        self.variete_murs = style.variete if style.lot2 is None else L.variete_des_murs(style)
        if style.lot2 is not None and style.lot2.vantail_fin:
            self.moyen = self.fin
        self.hasard_lot2: random.Random | None = None
        self.ids_pieces = {p.id: i + 1 for i, p in enumerate(niveau.pieces)}
        self.ids_elements = {m.id: i + 1 for i, m in enumerate(niveau.murs)}
        n = len(niveau.murs)
        self.ids_elements.update({o.id: n + i + 1 for i, o in enumerate(niveau.ouvertures)})
        n += len(niveau.ouvertures)  # A3 : les murs en biais / arrondis viennent après (les anciens numéros ne bougent pas)
        self.ids_elements.update({m.id: n + i + 1 for i, m in enumerate(niveau.murs_libres)})

    # ---- outils ----

    def px(self, x: float, y: float) -> Point:
        return self.rep.plat(x, y)

    def poly_px(self, contour: list[Point]) -> list[Point]:
        return [self.px(x, y) for x, y in contour]

    def rect_px(self, r: Rect) -> list[Point]:
        return self.poly_px([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])

    def remplir_masque(self, masque: np.ndarray, contour: list[Point], valeur: int) -> None:
        rasteriser(masque, [self.rep.final(x, y) for x, y in contour], valeur)

    def ligne(self, p: Point, q: Point, couleur, epaisseur: int) -> None:
        self.d.line((self.px(*p), self.px(*q)), fill=couleur, width=epaisseur)

    def texte(self, xy: Point, texte: str, taille: int, couleur, ancre: str = "mm", vertical: bool = False) -> None:
        police = _police(self.style.police, taille)
        if not vertical:
            self.d.text(xy, texte, fill=couleur, font=police, anchor=ancre)
            return
        g, h, dr, b = police.getbbox(texte)
        vignette = Image.new("L", (dr - g + 4, b - h + 4), 0)
        ImageDraw.Draw(vignette).text((2 - g, 2 - h), texte, fill=255, font=police)
        vignette = vignette.rotate(90, expand=True)
        x, y = round(xy[0] - vignette.width / 2), round(xy[1] - vignette.height / 2)
        self.image.paste(Image.new("RGB", vignette.size, couleur), (x, y), vignette)

    # ---- pièces ----

    def pieces(self) -> None:
        l2 = self.style.lot2
        palette = L.PALETTES_LOT2[l2.palette] if l2 is not None and l2.palette else PALETTES[self.style.palette]
        for p in self.niv.pieces:
            contour = contour_piece(p)
            if self.style.pieces_colorees:
                self.d.polygon(self.poly_px(contour), fill=palette.get(p.sorte, (240, 240, 240)))
            v = self.style.variete
            if v is not None and v.sols.get(p.sorte):
                V.sol(self, p, v.sols[p.sorte], v)
            if l2 is not None and l2.sols.get(p.sorte):  # V.sol est pure : une variété locale lui suffit
                V.sol(self, p, l2.sols[p.sorte], V.Variete(couleur_sol=l2.couleur_sol, pas_sol=l2.pas_sol))
            self.remplir_masque(self.semantique, contour, CLASSES[p.sorte])
            self.remplir_masque(self.pieces_m, contour, self.ids_pieces[p.id])
            if self.niv.index > 0 and p.sorte == "escalier":
                continue  # à l'étage, la trémie de l'escalier est un vide
        for p in self.niv.pieces:
            for m in self.meubles.get(p.id, []):
                self.meuble(m)

    def meuble(self, m: Meuble) -> None:
        couleur = self.style.traits
        pts = self.poly_px(m.contour)
        if self.style.lot2 is not None and self.style.lot2.mobilier_couleur:
            L.remplir_meuble(self, m, pts)
        if m.forme == "ellipse":
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            self.d.ellipse((min(xs), min(ys), max(xs), max(ys)), outline=couleur, width=self.fin)
            mx, my = [p[0] for p in m.contour], [p[1] for p in m.contour]
            cx, cy, rx, ry = (min(mx) + max(mx)) / 2, (min(my) + max(my)) / 2, (max(mx) - min(mx)) / 2, (max(my) - min(my)) / 2
            ovale = [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 32, endpoint=False)]
            self.remplir_masque(self.hauteur, ovale, min(m.hauteur, 65535))
        elif m.forme == "marches":
            r = m.contour
            xs, ys = [p[0] for p in r], [p[1] for p in r]
            self._marches(min(xs), min(ys), max(xs), max(ys), m)
        else:
            self.d.polygon(pts, outline=couleur, width=self.fin)
            self.remplir_masque(self.hauteur, m.contour, min(m.hauteur, 65535))
        details = m.details or []
        if m.forme == "marches" and self.style.lot2 is not None and self.style.lot2.escalier == "colimacon":
            details = []  # L.colimacon a déjà dessiné les marches : la flèche droite traverserait le cercle
        for trait in details:
            if len(trait) == 2:
                self.ligne(trait[0], trait[1], couleur, self.fin)
            else:
                self.d.polygon(self.poly_px(trait), outline=couleur, width=self.fin)

    def _marches(self, x0: float, y0: float, x1: float, y1: float, m: Meuble) -> None:
        """Les marches montent du bas de l'escalier jusqu'au plancher de l'étage : hauteur progressive."""
        couleur = self.style.traits
        l2 = self.style.lot2
        if l2 is not None and l2.escalier == "colimacon":
            L.colimacon(self, x0, y0, x1, y1)
        else:
            for trait in m.details or []:
                self.ligne(trait[0], trait[1], couleur, self.fin)
            if l2 is not None and l2.escalier == "fleche_acces":
                L.fleche_acces(self, x0, y0, x1, y1)
        le_long_de_x = (x1 - x0) >= (y1 - y0)
        n = 12
        haut = self.niv.hsp + self.log.plancher
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            if le_long_de_x:
                r = Rect(int(x0 + t0 * (x1 - x0)), int(y0), int(x0 + t1 * (x1 - x0)), int(y1))
            else:
                r = Rect(int(x0), int(y0 + t0 * (y1 - y0)), int(x1), int(y0 + t1 * (y1 - y0)))
            h = round(haut * (k + 1) / n)
            if h > PLAN_DE_COUPE:
                h = PLAN_DE_COUPE  # au-dessus du plan de coupe, on ne voit plus la marche : on garde la coupe
            self.remplir_masque(self.hauteur, [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)], h)

    # ---- murs et ouvertures ----

    def murs(self) -> None:
        st = self.style
        for m in self.niv.murs:
            r = rect_du_mur(m)
            contour = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            if self.variete_murs is not None:
                V.mur(self, m, contour, self.variete_murs)
            else:
                self.d.polygon(self.poly_px(contour), fill=st.murs)
            self.remplir_masque(self.semantique, contour, CLASSES["mur"])
            self.remplir_masque(self.elements, contour, self.ids_elements[m.id])
            self.remplir_masque(self.hauteur, contour, min(self.niv.hsp, 65535))
        for m in self.niv.murs_libres:
            self.mur_libre(m)
        for o in self.niv.ouvertures:
            r = rect_de_l_ouverture(o)
            contour = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            self.d.polygon(self.poly_px(contour), fill=st.fond if st.lot2 is None else L.couleur_ouverture(st, o))
            self.remplir_masque(self.semantique, contour, CLASSES[o.type])
            self.remplir_masque(self.elements, contour, self.ids_elements[o.id])
            self.remplir_masque(self.hauteur, contour, o.allege if o.type == "fenetre" else 0)
        if st.murs_contour:
            self.contour_des_murs()
        for o in self.niv.ouvertures:
            self.ouverture(o)

    def mur_libre(self, m: MurLibre) -> None:
        """A3 : un mur en biais ou arrondi, dessiné comme les autres murs du style (plein, trait, double, hachure)."""
        st, v = self.style, self.variete_murs
        pts = self.poly_px(m.polygone)
        genre = v.murs if v is not None else "plein"
        if genre == "trait":
            ep_px = max(1, m.epaisseur * self.rep.s)
            self.d.line(self.poly_px(m.axe), fill=st.murs, width=max(1, round(ep_px * v.epaisseur_trait_mur)))
        elif genre == "double":
            ep_px = max(1, m.epaisseur * self.rep.s)
            self.d.polygon(pts, outline=st.murs, width=max(1, round(min(3, ep_px * v.epaisseur_trait_mur))))
        elif genre == "hachure":
            V.mur(self, m, m.polygone, v)
        else:
            self.d.polygon(pts, fill=st.murs)
        self.remplir_masque(self.semantique, m.polygone, CLASSES["mur"])
        self.remplir_masque(self.elements, m.polygone, self.ids_elements[m.id])
        self.remplir_masque(self.hauteur, m.polygone, min(self.niv.hsp, 65535))

    def contour_des_murs(self) -> None:
        """Le trait qui cerne les murs (style agence) : le bord de l'union des murs, trous des ouvertures compris."""
        plein = (self.semantique == CLASSES["mur"]).astype(np.uint8)
        contours, _ = cv2.findContours(plein, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            pts = [tuple(map(float, p[0])) for p in c]
            if len(pts) >= 2:
                self.d.line(pts + [pts[0]], fill=self.style.murs_contour_couleur, width=self.fin)

    def ouverture(self, o: Ouverture) -> None:
        st = self.style
        if st.lot2 is not None and L.ouverture_en_boite(self, o):
            return
        m = o.mur
        e = m.epaisseur / 2
        t0, t1 = o.u0, o.u1
        couleur = st.traits

        def pt(t: float, n: float) -> Point:  # position le long du mur, décalage en travers
            return (m.axe + n, t) if m.vertical else (t, m.axe + n)

        if o.type == "fenetre":
            if st.symboles:
                for n in (-e, 0, e):
                    self.ligne(pt(t0, n), pt(t1, n), couleur, self.fin)
                for t in (t0, t1):
                    self.ligne(pt(t, -e), pt(t, e), couleur, self.fin)
            else:
                self.ligne(pt(t0, 0), pt(t1, 0), couleur, self.fin)
            return
        if o.type == "porte_fenetre":
            self.ligne(pt(t0, 0), pt(t1, 0), couleur, self.fin)
            if o.sous_type == "baie" and st.symboles:
                self.ligne(pt(t0, -e * 0.5), pt((t0 + t1) / 2, -e * 0.5), couleur, self.fin)
                self.ligne(pt((t0 + t1) / 2, e * 0.5), pt(t1, e * 0.5), couleur, self.fin)
                return
        if not st.symboles:
            for t in (t0, t1):
                self.ligne(pt(t, -e), pt(t, e), couleur, self.fin)
            return
        vers, charniere = o.vers or 1, o.charniere
        if st.doubles_vantaux and (t1 - t0) >= DOUBLE_VANTAIL_MIN:
            milieu = (t0 + t1) / 2
            vantaux = [(t0, milieu), (t1, milieu)]
        else:
            vantaux = [(t0, t1) if charniere == 0 else (t1, t0)]
        for pivot_t, autre_t in vantaux:
            largeur = abs(autre_t - pivot_t)
            pivot = pt(pivot_t, vers * e)
            bout = pt(pivot_t, vers * (e + largeur))
            self.ligne(pivot, bout, couleur, self.moyen)
            if st.arcs:
                self.arc(pivot, bout, pt(autre_t, vers * e), couleur)

    def arc(self, centre: Point, a: Point, b: Point, couleur) -> None:
        cx, cy = self.px(*centre)
        r = math.dist(self.px(*centre), self.px(*a))
        angles = []
        for p in (a, b):
            x, y = self.px(*p)
            angles.append(math.degrees(math.atan2(y - cy, x - cx)) % 360)
        debut, fin = angles
        if (fin - debut) % 360 > 180:
            debut, fin = fin, debut
        clair = tuple(min(c + 60, 170) for c in couleur)
        if (self.style.variete is not None and self.style.variete.arcs_pointilles) or (self.style.lot2 is not None and self.style.lot2.arcs_pointilles):
            V.arc_pointille(self, (cx - r, cy - r, cx + r, cy + r), debut, fin, clair, max(1, self.fin // 2))
            return
        self.d.arc((cx - r, cy - r, cx + r, cy + r), debut, fin, fill=clair, width=max(1, self.fin // 2))

    # ---- textes ----

    def noms(self) -> None:
        st = self.style
        if st.lot2 is not None:
            L.noms(self)
            return
        v = st.variete
        taille = st.taille_texte
        couleur = v.couleur_noms if v is not None and v.couleur_noms else st.textes
        for p in self.niv.pieces:
            r = p.rect
            cx, cy = self.px((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            place = r.largeur * self.rep.s * 0.9
            nom = p.nom.upper() if v is not None and v.majuscules else p.nom
            surface = f"{_fr(surface_piece(p) / 1e6)} m²"
            if v is not None and v.parentheses:
                surface = f"({surface})"
            t = taille
            while t > 9 and _police(st.police, t).getlength(nom) > place:
                t -= 1
            if st.noms and st.surfaces and r.hauteur * self.rep.s > 2.6 * taille:
                self.texte((cx, cy - taille * 0.6), nom, t, couleur)
                self.texte((cx, cy + taille * 0.6), surface, max(8, taille - 2),
                           tuple(min(c + 60, 150) for c in couleur))
            elif st.noms:
                self.texte((cx, cy), nom, t, couleur)
            elif st.surfaces:
                self.texte((cx, cy), surface, max(8, taille - 2), couleur)

    def cotes(self) -> None:
        rep, st = self.rep, self.style
        pieces = [p.rect for p in self.niv.pieces]
        x0, y0 = min(p.x0 for p in pieces), min(p.y0 for p in pieces)
        x1, y1 = max(p.x1 for p in pieces), max(p.y1 for p in pieces)
        haut = self.px(0, rep.ymax)[1] - RECUL_COTE
        gauche = self.px(rep.xmin, 0)[0] - RECUL_COTE
        bas = self.px(0, rep.ymin)[1] + RECUL_COTE
        droite = self.px(rep.xmax, 0)[0] + RECUL_COTE
        self.chaine([(x0, x1)], haut, True, -1)
        self.chaine([(y0, y1)], gauche, False, -1)
        if st.cotes_partielles:
            en_bas = sorted((p.x0, p.x1) for p in pieces if p.y0 == y0)
            a_droite = sorted((p.y0, p.y1) for p in pieces if p.x1 == x1)
            if len(en_bas) > 1:
                self.chaine(en_bas, bas, True, 1)
            if len(a_droite) > 1:
                self.chaine(a_droite, droite, False, 1)

    def chaine(self, intervalles: list[tuple[float, float]], position: float, horizontale: bool, cote_texte: int) -> None:
        st = self.style
        taille = round(st.taille_texte * 0.9)
        l2 = st.lot2
        coul_t, coul_x = st.traits, st.textes
        if l2 is not None and l2.couleur_cotes is not None:  # trait 16 : la chaîne entière est rouge (fr-031)
            coul_t = coul_x = l2.couleur_cotes
        for a, b in intervalles:
            if horizontale:
                p, q = (self.px(a, 0)[0], position), (self.px(b, 0)[0], position)
            else:
                p, q = (position, self.px(0, a)[1]), (position, self.px(0, b)[1])
            self.d.line((p, q), fill=coul_t, width=1)
            for x, y in (p, q):
                if horizontale:
                    self.d.line(((x, y - 9), (x, y + 9)), fill=coul_t, width=1)
                else:
                    self.d.line(((x - 9, y), (x + 9, y)), fill=coul_t, width=1)
                self.d.line(((x - 7, y + 7), (x + 7, y - 7)), fill=coul_t, width=2)
            milieu = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ecart = (taille * 0.75 + 8) * cote_texte
            valeur = _fr((b - a) / 1000) if l2 is None else L.texte_cote(b - a, l2)
            ecrire = self.texte if l2 is None else L.ecrivain_cotes(self)
            if horizontale:
                ecrire((milieu[0], milieu[1] + ecart), valeur, taille, coul_x)
            else:
                ecrire((milieu[0] + ecart, milieu[1]), valeur, taille, coul_x, vertical=True)

    def cartouche(self) -> None:
        rep, st = self.rep, self.style
        x = self.px(rep.xmax, 0)[0] + RECUL_COTE + 60
        y = self.px(0, rep.ymax)[1] + 30
        taille = round(st.taille_texte * 0.85)
        lignes = ["Cotes intérieures, en mètres", f"Murs extérieurs : {round(self.log.ep_ext / 10)} cm"]
        if self.log.ep_cloison < self.log.ep_ext:
            lignes.append(f"Cloisons : {round(self.log.ep_cloison / 10)} cm")
        if st.hsp_ecrite:
            lignes.append(f"Hauteur sous plafond : {_fr(self.niv.hsp / 1000)} m")
        if self.log.duplex:
            lignes.append("Rez-de-chaussée" if self.niv.index == 0 else "Étage")
        couleur = tuple(min(c + 50, 140) for c in st.textes)
        for i, ligne in enumerate(lignes):
            self.texte((x, y + i * taille * 1.5), ligne, taille, couleur, ancre="lm")
        if st.fleche_nord:
            fx, fy = x + 20, y + len(lignes) * taille * 1.5 + 30
            self.d.polygon([(fx, fy), (fx - 10, fy + 40), (fx + 10, fy + 40)], fill=st.murs if not st.murs_contour else st.traits)
            self.texte((fx, fy + 58), "N", taille, st.textes)

    def titre(self) -> None:
        texte = f"Plan n°{self.log.graine} — {self.log.type} de {self.log.surface:.0f} m²"
        if self.log.duplex:
            texte += " — " + ("rez-de-chaussée" if self.niv.index == 0 else "étage")
        self.texte((40, 40), texte.replace(".", ","), round(self.style.taille_texte * 1.2), self.style.textes, ancre="lm")

    def echelle_graphique(self) -> None:
        rep, st = self.rep, self.style
        metres = 1 if (rep.xmax - rep.xmin) < 5000 else 2
        x = self.px(rep.xmin, 0)[0]
        y = self.px(0, rep.ymin)[1] + _place_echelle(st)[0]
        for k in range(metres):
            u0, u1 = x + k * rep.s * 1000, x + (k + 1) * rep.s * 1000
            self.d.rectangle((u0, y, u1, y + 8), fill=st.traits if k % 2 == 0 else st.fond, outline=st.traits)
        self.texte((x, y + 22), "0", round(st.taille_texte * 0.8), st.textes)
        self.texte((x + metres * rep.s * 1000, y + 22), f"{metres} m", round(st.taille_texte * 0.8), st.textes)

    def tout(self, graine_style: str = "") -> None:
        st = self.style
        if st.lot2 is not None:
            # Hasard à part, même clé pour le plan et le plan sans mobilier : ils écrivent et cotent pareil.
            self.hasard_lot2 = random.Random(f"lot2-dessin-{self.log.graine}-{self.niv.index}-{graine_style}")
            L.avant_tout(self, self.hasard_lot2)
        self.pieces()
        self.murs()
        if st.noms or st.surfaces:
            self.noms()
        if st.variete is not None:
            if st.variete.lettres:
                V.lettres(self, st.variete)
            if st.variete.symboles_neuf:
                V.symboles_neuf(self, st.variete, random.Random(f"neuf-{self.log.graine}-{self.niv.index}"))
        if st.cotes and (st.lot2 is None or not st.lot2.sans_chaines):
            if st.lot2 is not None and st.lot2.blocs:
                L.cotes_des_blocs(self)  # une chaîne par bloc : autour de l'image entière, elle mesurerait aussi le vide
            else:
                self.cotes()
        if st.echelle_graphique:
            self.echelle_graphique()
        if st.cartouche:
            self.cartouche()
        if st.titre:
            self.titre()
        if st.lot2 is not None:
            L.apres_tout(self, self.hasard_lot2)


def rendre(log: LogementGenere, niveau: Niveau, style: Style, graine_style: str = "") -> Rendu:
    """Dessine le niveau selon le style : images, masques et annotations pixels, tous alignés."""
    rng = random.Random(f"rendu-{log.graine}-{niveau.index}-{graine_style}")
    cadre = _cadre_des_murs(niveau)
    rep = Repere(cadre, style, rng, nb_pieces=len(niveau.pieces))
    tous = meubler_niveau(niveau, log.graine)
    # Les marches d'un escalier ne sont pas du mobilier : un plan les montre toujours, et la carte de
    # hauteur doit toujours les porter. Un style « sans mobilier » garde donc l'escalier.
    escaliers = {pid: [m for m in lst if m.forme == "marches"] for pid, lst in tous.items()}
    escaliers = {pid: lst for pid, lst in escaliers.items() if lst}
    meubles = tous if style.mobilier else escaliers
    if style.lot2 is not None:
        meubles = L.plans_de_travail_au_mur(meubles, niveau)
        if style.lot2.mobilier_fixes:
            meubles = L.garder_fixes(meubles)
    d = _Dessin(log, niveau, style, rep, meubles, avec_mobilier=True)
    d.tout(graine_style)
    images: dict[str, np.ndarray] = {}
    page, plis = _feuille(rep, style, f"photo-{log.graine}-{niveau.index}-{graine_style}")
    plan = rep.deformer(np.asarray(d.image), True, style.fond)
    images["plan"] = salir(plan, style, random.Random(f"salissure-{log.graine}-{niveau.index}-{graine_style}"), page, plis)
    if style.mobilier:
        d2 = _Dessin(log, niveau, style, rep, escaliers, avec_mobilier=True)
        d2.tout(graine_style)
        nu = rep.deformer(np.asarray(d2.image), True, style.fond)
        images["plan_sans_mobilier"] = salir(nu, style, random.Random(f"salissure-{log.graine}-{niveau.index}-{graine_style}"),
                                             page, plis)
    # Le bord d'une pièce et le bord de son mur tombent sur la même rangée de pixels (les polygones
    # se touchent) : le mur l'emporte, pour qu'un pixel d'une pièce porte toujours la classe de la pièce.
    v = style.variete
    if v is not None and (v.capture or v.filigrane or v.agrandi > 1.0):
        for nom in [n for n in images if n.startswith("plan")]:
            images[nom] = V.capture(images[nom], d.semantique, v, random.Random(f"capture-{log.graine}-{niveau.index}-{graine_style}"))
    if style.lot2 is not None and style.lot2.teinte:
        for nom in [n for n in images if n.startswith("plan")]:
            images[nom] = L.teinter(images[nom], style.lot2.teinte)
    if style.lot2 is not None and style.lot2.ecran and style.realisme is None:
        # En dernier : le bord de l'écran reste noir. Même clé pour les deux images : plan et plan sans mobilier, même écran.
        for nom in [n for n in images if n.startswith("plan")]:
            images[nom] = L.ecran_pixels(images[nom], d.semantique, style.lot2, random.Random(f"lot2-pixels-{log.graine}-{niveau.index}-{graine_style}"))
    d.pieces_m[d.elements > 0] = 0
    images["masque_semantique"] = d.semantique
    images["masque_pieces"] = d.pieces_m
    images["masque_elements"] = d.elements
    images["hauteur"] = d.hauteur
    plein = ((images["masque_semantique"] >= 1) & (images["masque_semantique"] <= 4)).astype(np.uint8)
    bord = cv2.morphologyEx(plein, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    images["contours"] = (bord * 255).astype(np.uint8)
    return Rendu(images, _annotations_pixels(log, niveau, rep, d, style, meubles), style, meubles)


def _feuille(rep: Repere, style: Style, graine: str) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Photo réaliste : la part de chaque pixel couverte par la feuille et la lumière des plis, dans le
    repère final (None, None sans photo réaliste). Dessinées à plat puis vues par la même matrice que le plan."""
    if style.realisme is None or rep.identite:
        return None, None
    rng = random.Random(graine)
    nrng = np.random.default_rng(rng.getrandbits(32))
    page = rep.deformer(np.ones((rep.hauteur0, rep.largeur0), np.float32), True, 0.0)
    plis = plis_a_plat(rep.hauteur0, rep.largeur0, style.realisme, rng, nrng)
    if plis is not None:
        plis = rep.deformer(plis, True, 1.0)
    return page, plis


def _cadre_des_murs(niveau: Niveau) -> Rect:
    rects = [rect_du_mur(m) for m in niveau.murs]
    return Rect(min(r.x0 for r in rects), min(r.y0 for r in rects), max(r.x1 for r in rects), max(r.y1 for r in rects))


def _annotations_pixels(log: LogementGenere, niveau: Niveau, rep: Repere, d: _Dessin, style: Style,
                        meubles: dict[str, list[Meuble]]) -> dict:
    """Ce qu'il faut pour relier les images à la géométrie : la matrice, et chaque élément en pixels."""

    def poly(r: Rect) -> list[list[float]]:
        return [[round(u, 2), round(v, 2)] for u, v in (rep.final(x, y) for x, y in
                                                        ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)))]

    def boite(pts: list[list[float]]) -> list[float]:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]

    # La matrice mètres → pixels : H travaille en mm, on absorbe le facteur 1000 dans ses deux premières colonnes.
    H_m = rep.H.copy()
    H_m[:, 0] *= 1000
    H_m[:, 1] *= 1000
    pieces = []
    def poly_pts(contour) -> list[list[float]]:
        return [[round(u, 2), round(v, 2)] for u, v in (rep.final(x, y) for x, y in contour)]

    for p in niveau.pieces:
        pts = poly_pts(p.contour) if p.contour else poly(p.rect)
        pieces.append({"id": p.id, "valeur_masque": d.ids_pieces[p.id], "classe": CLASSES[p.sorte],
                       "polygone_px": pts, "boite_px": boite(pts)})
    murs = []
    for m in niveau.murs:
        pts = poly(rect_du_mur(m))
        murs.append({"id": m.id, "valeur_masque": d.ids_elements[m.id], "classe": CLASSES["mur"],
                     "polygone_px": pts, "boite_px": boite(pts)})
    for m in niveau.murs_libres:
        pts = poly_pts(m.polygone)
        murs.append({"id": m.id, "valeur_masque": d.ids_elements[m.id], "classe": CLASSES["mur"],
                     "polygone_px": pts, "boite_px": boite(pts)})
    ouvertures = []
    for o in niveau.ouvertures:
        pts = poly(rect_de_l_ouverture(o))
        ouvertures.append({"id": o.id, "valeur_masque": d.ids_elements[o.id], "classe": CLASSES[o.type],
                           "polygone_px": pts, "boite_px": boite(pts)})
    mob = []
    for pid, lst in meubles.items():
        for m in lst:
            pts = [[round(u, 2), round(v, 2)] for u, v in (rep.final(x, y) for x, y in m.contour)]
            mob.append({"piece": pid, "type": m.type, "forme": m.forme, "hauteur": m.hauteur / 1000,
                        "contour": [[round(x / 1000, 3), round(y / 1000, 3)] for x, y in m.contour],
                        "polygone_px": pts, "boite_px": boite(pts)})
    return {
        "niveau": niveau.index,
        "image": {"largeur": rep.largeur, "hauteur": rep.hauteur, "px_par_m": style.px_par_m,
                  "rotation_deg": style.rotation, "perspective": style.perspective,
                  "matrice_m_vers_px": [[round(v, 6) for v in ligne] for ligne in H_m.tolist()],
                  "a_plat": rep.identite},
        "style": style.en_dict(),
        "classes_masque_semantique": {str(k): v for k, v in sorted(set(CLASSES.items()), key=lambda kv: kv[1])},
        "plan_de_coupe_hauteur_m": PLAN_DE_COUPE / 1000,
        "pieces": pieces, "murs": murs, "ouvertures": ouvertures, "mobilier": mob,
    }
