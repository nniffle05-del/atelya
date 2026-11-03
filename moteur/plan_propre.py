"""Le plan 2D propre, à livrer au client (étape P7).

À partir d'un logement.json (de préférence celui validé à l'écran de vérification),
ce module dessine une page prête à imprimer ou à envoyer :
- en haut à gauche, la marque « Atelya » et la mention « Plan réalisé par Atelya » ;
- en haut à droite, le titre, l'adresse (si on la connaît) et la date ;
- au centre, le plan à une échelle d'architecte (1/50, 1/100…) : murs en noir,
  y compris en biais, portes avec leur arc d'ouverture, fenêtres, nom, surface et
  dimensions de chaque pièce, dimensions hors tout ;
- sur le côté, le tableau des surfaces, la surface totale, la barre d'échelle,
  la flèche du nord seulement si quelqu'un l'a indiquée, et la mention
  « surfaces indicatives, pas un mesurage Carrez ».

La page sort en PDF (image à 300 points par pouce, faite avec Pillow, déjà installé)
et en PNG pour un aperçu. Rien de ce module ne sert à l'entraînement : le dessin
d'entraînement reste dans dessin_plan.py, inchangé.

Garde-fou : un fichier qui n'est pas passé par l'écran de vérification est dessiné
avec la mention « BROUILLON, NON VÉRIFIÉ » en travers de la page.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from moteur.logement import Logement

VERSION = "0.1.0"
POLICE = Path(__file__).parent / "polices" / "Inter-Regular.otf"
DPI = 300
SUR = 2  # le dessin est fait 2 fois plus grand puis réduit : traits lisses
FORMATS_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0)}  # paysage
ECHELLES = (50, 75, 100, 125, 150, 200, 250, 300, 400, 500)
MOTS_EXTERIEURS = ("balcon", "terrasse", "loggia", "jardin", "cour", "patio")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")
MENTION = ("Surfaces indicatives, calculées d'après le plan fourni. Ce document n'est pas "
           "un mesurage loi Carrez ou loi Boutin et n'a pas de valeur contractuelle.")

# Couleurs (rouge, vert, bleu).
NOIR = (28, 28, 30)
TEXTE = (40, 40, 44)
GRIS = (110, 110, 116)
GRIS_CLAIR = (170, 170, 176)
SOL = (244, 240, 233)  # le sol des pièces, beige très clair
MARQUE = (30, 91, 90)  # vert-bleu de la marque
BLANC = (255, 255, 255)


@dataclass
class Infos:
    """Ce qui est écrit autour du plan. Tout est facultatif sauf ce qui a une valeur par défaut."""

    titre: str = "Plan du logement"
    adresse: str = ""  # Atelya ne peut pas la deviner : elle vient du client ou du site
    reference: str = ""
    date_plan: date = field(default_factory=date.today)
    nord_deg: float | None = None  # angle du nord, en degrés, compté depuis le haut de la page, sens horaire
    brouillon: bool = False


@dataclass
class Page:
    """La page dessinée et ce qu'on a choisi pour elle."""

    image: Image.Image  # en couleur, à 300 points par pouce
    format: str
    echelle: int  # 100 pour 1/100
    surface_habitable: float
    surface_exterieurs: float

    def enregistrer_pdf(self, chemin: str | Path) -> None:
        self.image.save(str(chemin), "PDF", resolution=DPI, title="Plan réalisé par Atelya")

    def enregistrer_png(self, chemin: str | Path, reduction: int = 1) -> None:
        image = self.image
        if reduction > 1:
            image = image.resize((image.width // reduction, image.height // reduction), Image.LANCZOS)
        image.save(str(chemin))


# ---------- Lecture du fichier ----------


def lire_entree(donnees: dict) -> tuple[dict, bool, dict]:
    """Accepte un logement.json, un résultat de l'écran de vérification ou un fichier à vérifier.

    Renvoie (logement, vérifié par un humain ?, infos trouvées dans le fichier).
    """
    schema = donnees.get("schema", "")
    if schema.startswith("resultat-verification/"):
        return donnees["logement"], donnees.get("statut", "").startswith("valide"), donnees.get("infos", {})
    if schema.startswith("verification/"):
        return donnees["logement"], False, donnees.get("infos", {})
    if schema.startswith("logement/"):
        # Un logement seul est vérifié s'il sort de l'écran (ses éléments touchés portent « +verification »)
        # ou si celui qui lance la commande l'affirme (option --verifie).
        sources = [e.get("source", "") for cle in ("murs", "ouvertures", "pieces") for e in donnees.get(cle, [])]
        return donnees, any(s.endswith("+verification") for s in sources), {}
    raise ValueError(f"fichier non reconnu (schéma « {schema} »)")


# ---------- Calculs ----------


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


def _distance_segment(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def est_exterieur(nom: str) -> bool:
    nom = nom.lower()
    return any(m in nom for m in MOTS_EXTERIEURS)


def surface_piece(piece: dict) -> float:
    return piece.get("surface") or _surface(piece["contour"])


def dimensions_rectangle(contour: list) -> tuple[float, float] | None:
    """Largeur et profondeur d'une pièce rectangulaire (même tournée), sinon None."""
    pts = [tuple(p) for p in contour]
    if len(pts) == 5 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:4]
    if len(pts) != 4:
        return None
    cotes = [math.dist(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % 4]
        u = (a[0] - b[0], a[1] - b[1])
        v = (c[0] - b[0], c[1] - b[1])
        if abs(u[0] * v[0] + u[1] * v[1]) > 0.02 * math.hypot(*u) * math.hypot(*v):
            return None
    largeur, profondeur = cotes[0], cotes[1]
    # « largeur » = la plus proche de l'horizontale de la page.
    dx = abs(pts[1][0] - pts[0][0])
    if dx < cotes[0] * 0.5:
        largeur, profondeur = profondeur, largeur
    return largeur, profondeur


def point_etiquette(contour: list, obstacles: list[tuple[tuple[float, float], float]] = ()) -> tuple[float, float]:
    """Le point de la pièce le plus loin de ses bords et des débattements de portes (cercles centre, rayon)."""
    xs = [p[0] for p in contour]
    ys = [p[1] for p in contour]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    aretes = list(zip(contour, contour[1:] + contour[:1]))
    meilleur, score = ((x0 + x1) / 2, (y0 + y1) / 2), -1.0
    n = 24
    for i in range(1, n):
        for j in range(1, n):
            p = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n)
            if not _dedans(p, contour):
                continue
            d = min(_distance_segment(p, a, b) for a, b in aretes)
            for centre, rayon in obstacles:
                d = min(d, max(math.dist(p, centre) - rayon, -1.0) + 0.0)
            # On préfère un peu le centre du cadre, pour un placement régulier.
            d -= 0.05 * math.dist(p, ((x0 + x1) / 2, (y0 + y1) / 2))
            if d > score:
                meilleur, score = p, d
    return meilleur


def _hauteur_libre(contour: list, x: float, y: float) -> float:
    """Comme _largeur_libre, mais sur la ligne verticale (place pour les lignes de texte)."""
    tourne = [(b, a) for a, b in contour]
    return _largeur_libre(tourne, y, x)


def _largeur_libre(contour: list, x: float, y: float) -> float:
    """La largeur dont dispose un texte centré en (x, y) : deux fois la distance au bord le plus proche
    sur la ligne horizontale qui passe par ce point."""
    gauche, droite = -math.inf, math.inf
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi <= x:
                gauche = max(gauche, xi)
            else:
                droite = min(droite, xi)
    if not (math.isfinite(gauche) and math.isfinite(droite)):
        xs = [c[0] for c in contour]
        return max(xs) - min(xs)
    return 2 * min(x - gauche, droite - x)


def _enveloppe(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """L'enveloppe convexe d'un nuage de points (méthode de la « chaîne monotone »)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def tour(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    bas, haut = [], []
    for p in pts:
        while len(bas) >= 2 and tour(bas[-2], bas[-1], p) <= 0:
            bas.pop()
        bas.append(p)
    for p in reversed(pts):
        while len(haut) >= 2 and tour(haut[-2], haut[-1], p) <= 0:
            haut.pop()
        haut.append(p)
    return bas[:-1] + haut[:-1]


def _angle_de_murs(p, mur_a, mur_b) -> list[tuple[float, float]] | None:
    """Le morceau qui bouche l'angle entre deux murs qui se terminent au même point p (coupe d'onglet).

    Chaque mur s'arrête sur son axe ; on ajoute le coin extérieur (là où les faces extérieures
    des deux murs se rejoignent) et les bouts des deux murs, et on remplit leur enveloppe.
    """
    def depart(m):  # direction qui part du point p vers l'intérieur du mur
        a, b = m["debut"], m["fin"]
        loin = b if math.dist(a, p) < math.dist(b, p) else a
        l = math.dist(p, loin)
        return ((loin[0] - p[0]) / l, (loin[1] - p[1]) / l) if l else None

    ua, ub = depart(mur_a), depart(mur_b)
    if ua is None or ub is None:
        return None
    la, lb = (-ua[1], ua[0]), (-ub[1], ub[0])
    ea, eb = mur_a["epaisseur"] / 2, mur_b["epaisseur"] / 2
    points = [tuple(p)]
    points += [(p[0] + s * ea * la[0], p[1] + s * ea * la[1]) for s in (1, -1)]
    points += [(p[0] + s * eb * lb[0], p[1] + s * eb * lb[1]) for s in (1, -1)]
    det = ua[0] * ub[1] - ua[1] * ub[0]
    if abs(det) > 1e-6:
        for s in (1, -1):  # la face gauche de l'un continue la face droite de l'autre
            qa = (p[0] + s * ea * la[0], p[1] + s * ea * la[1])
            qb = (p[0] - s * eb * lb[0], p[1] - s * eb * lb[1])
            # qa + t·ua = qb + r·ub
            dx, dy = qb[0] - qa[0], qb[1] - qa[1]
            t = (dx * ub[1] - dy * ub[0]) / det
            r = (dx * ua[1] - dy * ua[0]) / det
            coin = (qa[0] + t * ua[0], qa[1] + t * ua[1])
            if t <= 1e-9 and r <= 1e-9 and math.dist(coin, p) <= 4 * max(ea, eb):
                points.append(coin)
    return _enveloppe(points)


def _rectangle_mur(m: dict) -> list[tuple[float, float]]:
    (ax, ay), (bx, by) = m["debut"], m["fin"]
    l = math.dist((ax, ay), (bx, by))
    e = m["epaisseur"] / 2
    nx, ny = -(by - ay) / l * e, (bx - ax) / l * e
    return [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]


def _cadre_murs(murs: list[dict]) -> tuple[float, float, float, float]:
    pts = [c for m in murs for c in _rectangle_mur(m)]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


# ---------- Dessin ----------


@lru_cache(maxsize=64)
def _police(taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(POLICE), max(6, taille))


def _fr(v: float, decimales: int = 2) -> str:
    return f"{v:.{decimales}f}".replace(".", ",")


def _date_fr(d: date) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


class _Feuille:
    def __init__(self, largeur_mm: float, hauteur_mm: float):
        self.k = DPI / 25.4 * SUR  # pixels par millimètre (dessin agrandi)
        self.image = Image.new("RGB", (round(largeur_mm * self.k), round(hauteur_mm * self.k)), BLANC)
        self.d = ImageDraw.Draw(self.image)

    def mm(self, v: float) -> float:
        return v * self.k

    def texte(self, xy_mm, texte: str, taille_mm: float, couleur=TEXTE, ancre: str = "la", gras: bool = False,
              halo: float = 0.0):
        police = _police(round(self.mm(taille_mm) * 1.38))  # taille de police ≈ hauteur des capitales × 1,38
        x, y = self.mm(xy_mm[0]), self.mm(xy_mm[1])
        epaisseur = round(self.mm(halo)) if halo else (max(1, round(self.mm(taille_mm) * 0.06)) if gras else 0)
        self.d.text((x, y), texte, fill=couleur, font=police, anchor=ancre,
                    stroke_width=epaisseur, stroke_fill=couleur)

    def largeur_texte_mm(self, texte: str, taille_mm: float) -> float:
        return _police(round(self.mm(taille_mm) * 1.38)).getlength(texte) / self.k

    def paragraphe(self, xy_mm, texte: str, taille_mm: float, largeur_mm: float, couleur=GRIS,
                   interligne: float = 1.5) -> float:
        """Écrit un texte sur plusieurs lignes ; renvoie la hauteur utilisée (mm)."""
        mots, lignes, ligne = texte.split(), [], ""
        for mot in mots:
            essai = f"{ligne} {mot}".strip()
            if self.largeur_texte_mm(essai, taille_mm) > largeur_mm and ligne:
                lignes.append(ligne)
                ligne = mot
            else:
                ligne = essai
        if ligne:
            lignes.append(ligne)
        for i, l in enumerate(lignes):
            self.texte((xy_mm[0], xy_mm[1] + i * taille_mm * interligne), l, taille_mm, couleur)
        return len(lignes) * taille_mm * interligne


class _Plan:
    """Le dessin du logement dans un cadre de la feuille, à une échelle donnée."""

    def __init__(self, f: _Feuille, log: dict, echelle: int, centre_mm: tuple[float, float]):
        self.f = f
        self.log = log
        self.s = 1000.0 / echelle * f.k  # pixels par mètre
        x0, y0, x1, y1 = _cadre_murs(log["murs"])
        self.cadre = (x0, y0, x1, y1)
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.px_centre = (f.mm(centre_mm[0]), f.mm(centre_mm[1]))
        self.murs = {m["id"]: m for m in log["murs"]}
        self.debattements: list[tuple[tuple[float, float], float]] = []  # (pivot, rayon) de chaque battant

    def px(self, x: float, y: float) -> tuple[float, float]:
        return self.px_centre[0] + (x - self.cx) * self.s, self.px_centre[1] - (y - self.cy) * self.s

    def poly(self, pts, couleur) -> None:
        self.f.d.polygon([self.px(*p) for p in pts], fill=couleur)

    def ligne(self, pts, couleur, epaisseur_mm: float) -> None:
        self.f.d.line([self.px(*p) for p in pts], fill=couleur,
                      width=max(1, round(self.f.mm(epaisseur_mm))), joint="curve")

    # --- Pièces (le sol) ---

    def sols(self) -> None:
        for p in self.log.get("pieces", []):
            self.poly(p["contour"], SOL)

    # --- Murs ---

    def dessiner_murs(self) -> None:
        murs = self.log["murs"]
        for m in murs:
            self.poly(_rectangle_mur(m), NOIR)
        # Les angles : à chaque bout de mur, on bouche le coin avec les murs qui le touchent.
        for m in murs:
            for bout in (m["debut"], m["fin"]):
                voisins = [v for v in murs if v is not m
                           and min(math.dist(bout, v["debut"]), math.dist(bout, v["fin"])) < 1e-3]
                for v in voisins:
                    coins = _angle_de_murs(bout, m, v)
                    if coins:
                        self.poly(coins, NOIR)

    # --- Ouvertures ---

    def ouvertures(self) -> None:
        trait = 0.25  # mm
        for o in self.log.get("ouvertures", []):
            mur = self.murs.get(o["mur"])
            if mur is None:
                continue
            (ax, ay), (bx, by) = mur["debut"], mur["fin"]
            l = math.dist((ax, ay), (bx, by))
            ux, uy = (bx - ax) / l, (by - ay) / l
            nx, ny = -uy, ux
            e = mur["epaisseur"] / 2
            t0, t1 = o["position"], o["position"] + o["largeur"]

            def pt(t: float, n: float) -> tuple[float, float]:
                return ax + t * ux + n * nx, ay + t * uy + n * ny

            marge = 0.004
            self.poly([pt(t0, -e - marge), pt(t1, -e - marge), pt(t1, e + marge), pt(t0, e + marge)], BLANC)
            # Les tableaux (bords du trou) : un trait fin pour finir proprement le mur.
            for t in (t0, t1):
                self.ligne([pt(t, -e), pt(t, e)], NOIR, trait)
            if o["type"] == "fenetre":
                self.poly([pt(t0, -e * 0.25), pt(t1, -e * 0.25), pt(t1, e * 0.25), pt(t0, e * 0.25)], (215, 228, 235))
                for n in (-e, -e * 0.25, e * 0.25, e):
                    self.ligne([pt(t0, n), pt(t1, n)], NOIR, trait)
                continue
            if o["type"] == "porte_fenetre":
                self.poly([pt(t0, -e * 0.2), pt(t1, -e * 0.2), pt(t1, e * 0.2), pt(t0, e * 0.2)], (215, 228, 235))
                for n in (-e * 0.2, e * 0.2):
                    self.ligne([pt(t0, n), pt(t1, n)], NOIR, trait)
            sens = self._cote_ouverture(pt, t0, t1, e)
            largeur = t1 - t0
            if largeur >= 1.2:  # deux battants
                milieu = (t0 + t1) / 2
                vantaux = [(t0, milieu), (t1, milieu)]
            else:
                vantaux = [(t0, t1)]
            for pivot_t, autre_t in vantaux:
                r = abs(autre_t - pivot_t)
                pivot = pt(pivot_t, sens * e)
                bout = (pivot[0] + sens * r * nx, pivot[1] + sens * r * ny)
                ferme = pt(autre_t, sens * e)
                self.debattements.append((pivot, r))
                self.ligne([pivot, bout], NOIR, 0.35)
                a0 = math.atan2(bout[1] - pivot[1], bout[0] - pivot[0])
                a1 = math.atan2(ferme[1] - pivot[1], ferme[0] - pivot[0])
                ecart = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                arc = [(pivot[0] + r * math.cos(a0 + ecart * i / 32), pivot[1] + r * math.sin(a0 + ecart * i / 32))
                       for i in range(33)]
                self.ligne(arc, GRIS, 0.18)

    def _cote_ouverture(self, pt, t0: float, t1: float, e: float) -> int:
        """La porte s'ouvre vers la plus petite des pièces qui la bordent (vers l'intérieur pour l'entrée)."""
        tm = (t0 + t1) / 2
        choix = []
        for sens in (1, -1):
            p = pt(tm, sens * (e + 0.08))
            for piece in self.log.get("pieces", []):
                if _dedans(p, piece["contour"]):
                    choix.append((_surface(piece["contour"]), sens))
        return min(choix)[1] if choix else 1

    # --- Noms, surfaces et dimensions ---

    def etiquettes(self) -> None:
        f = self.f
        for p in self.log.get("pieces", []):
            x, y = point_etiquette(p["contour"], self.debattements)
            X, Y = self.px(x, y)
            largeur_dispo_mm = _largeur_libre(p["contour"], x, y) * self.s / f.k * 0.8
            hauteur_dispo_mm = _hauteur_libre(p["contour"], x, y) * self.s / f.k * 0.85
            nom = p["nom"]
            taille = 2.6
            while taille > 1.8 and (f.largeur_texte_mm(nom, taille) > largeur_dispo_mm
                                    or taille * 1.75 * 1.85 > hauteur_dispo_mm):
                taille -= 0.1
            surface = f"{_fr(surface_piece(p))} m²"
            dims = dimensions_rectangle(p["contour"])
            lignes = [(nom, taille, TEXTE, True), (surface, taille * 0.85, GRIS, False)]
            if dims and hauteur_dispo_mm > taille * 5.2:
                texte_dims = f"{_fr(dims[0])} × {_fr(dims[1])}"
                if f.largeur_texte_mm(texte_dims, taille * 0.72) <= largeur_dispo_mm:
                    lignes.append((texte_dims, taille * 0.72, GRIS_CLAIR, False))
            pas = [t * 1.75 for _, t, _, _ in lignes]
            haut = Y / f.k - sum(pas) / 2 + pas[0] / 2
            for (texte, t, couleur, gras), h in zip(lignes, pas):
                f.texte((X / f.k, haut), texte, t, SOL, ancre="mm", halo=0.5)  # un liseré couleur du sol
                f.texte((X / f.k, haut), texte, t, couleur, ancre="mm", gras=gras)
                haut += h

    # --- Dimensions hors tout ---

    def cotes_hors_tout(self) -> None:
        x0, y0, x1, y1 = self.cadre
        recul = self.f.mm(7)
        gx, hy = self.px(x0, y1)
        dx, by = self.px(x1, y0)
        self._cote((gx, hy - recul), (dx, hy - recul), _fr(x1 - x0), horizontale=True)
        self._cote((gx - recul, by), (gx - recul, hy), _fr(y1 - y0), horizontale=False)

    def _cote(self, p, q, texte: str, horizontale: bool) -> None:
        f, d = self.f, self.f.d
        w = max(1, round(f.mm(0.18)))
        d.line((p, q), fill=GRIS, width=w)
        tick = f.mm(1.2)
        for x, y in (p, q):
            d.line(((x - tick, y + tick), (x + tick, y - tick)), fill=GRIS, width=w * 2)
            if horizontale:
                d.line(((x, y - tick * 1.6), (x, y + f.mm(5))), fill=GRIS_CLAIR, width=w)
            else:
                d.line(((x - tick * 1.6, y), (x + f.mm(5), y)), fill=GRIS_CLAIR, width=w)
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        taille = 2.3
        if horizontale:
            f.texte((mx / f.k, my / f.k - 1.2), texte, taille, TEXTE, ancre="md")
        else:
            police = _police(round(f.mm(taille) * 1.38))
            g, h, dr, b = police.getbbox(texte)
            vignette = Image.new("L", (dr - g + 6, b - h + 6), 0)
            ImageDraw.Draw(vignette).text((3 - g, 3 - h), texte, fill=255, font=police)
            vignette = vignette.rotate(90, expand=True)
            x = round(mx - f.mm(1.2) - vignette.width)
            y = round(my - vignette.height / 2)
            f.image.paste(Image.new("RGB", vignette.size, TEXTE), (x, y), vignette)


def _choisir_mise_en_page(log: dict, format_voulu: str | None) -> tuple[str, bool, int]:
    """(format, paysage ?, échelle) : la plus grande échelle d'architecte où le plan tient."""
    x0, y0, x1, y1 = _cadre_murs(log["murs"])
    lm, hm = x1 - x0, y1 - y0
    paysage = lm >= hm
    formats = [format_voulu] if format_voulu else ["A4", "A3"]
    for fmt in formats:
        lp, hp = FORMATS_MM[fmt]
        if not paysage:
            lp, hp = hp, lp
        zl, zh = _zone_plan_mm(lp, hp, paysage)
        for e in ECHELLES:
            if e < 50:
                continue
            if lm * 1000 / e <= zl and hm * 1000 / e <= zh:
                if fmt == "A4" and not format_voulu and e > 100:
                    break  # trop petit sur A4 : on essaie l'A3 avant de réduire davantage
                return fmt, paysage, e
    fmt = formats[-1]
    lp, hp = FORMATS_MM[fmt]
    if not paysage:
        lp, hp = hp, lp
    zl, zh = _zone_plan_mm(lp, hp, paysage)
    e = max(50, math.ceil(max(lm * 1000 / zl, hm * 1000 / zh) / 50) * 50)
    return fmt, paysage, e


MARGE = 12.0
ENTETE = 26.0
PANNEAU_PAYSAGE = 74.0  # largeur du panneau de droite en paysage
PANNEAU_PORTRAIT = 62.0  # hauteur du panneau du bas en portrait
PLACE_COTES = 12.0


def _zone_plan_mm(lp: float, hp: float, paysage: bool) -> tuple[float, float]:
    if paysage:
        return lp - 2 * MARGE - PANNEAU_PAYSAGE - 2 * PLACE_COTES, hp - 2 * MARGE - ENTETE - 2 * PLACE_COTES
    return lp - 2 * MARGE - 2 * PLACE_COTES, hp - 2 * MARGE - ENTETE - PANNEAU_PORTRAIT - 2 * PLACE_COTES


def dessiner_page(logement: dict, infos: Infos | None = None, format_page: str | None = None) -> Page:
    """La page complète du plan propre."""
    infos = infos or Infos()
    Logement.model_validate(logement)  # refuse un logement incohérent, comme le moteur
    fmt, paysage, echelle = _choisir_mise_en_page(logement, format_page)
    lp, hp = FORMATS_MM[fmt]
    if not paysage:
        lp, hp = hp, lp
    f = _Feuille(lp, hp)

    # --- Le plan ---
    zl, zh = _zone_plan_mm(lp, hp, paysage)
    gauche = MARGE + PLACE_COTES
    haut = MARGE + ENTETE + PLACE_COTES
    plan = _Plan(f, logement, echelle, (gauche + zl / 2 + 3, haut + zh / 2))
    plan.sols()
    plan.dessiner_murs()
    plan.ouvertures()
    plan.etiquettes()
    plan.cotes_hors_tout()

    # --- L'en-tête ---
    _entete(f, infos, lp)

    # --- Le panneau : surfaces, échelle, nord, mention ---
    pieces = logement.get("pieces", [])
    interieures = [p for p in pieces if not est_exterieur(p["nom"])]
    exterieures = [p for p in pieces if est_exterieur(p["nom"])]
    s_hab = round(sum(surface_piece(p) for p in interieures), 2)
    s_ext = round(sum(surface_piece(p) for p in exterieures), 2)
    if paysage:
        cadre = (lp - MARGE - PANNEAU_PAYSAGE + 6, MARGE + ENTETE + 2, PANNEAU_PAYSAGE - 6, hp - 2 * MARGE - ENTETE - 2)
    else:
        cadre = (MARGE, hp - MARGE - PANNEAU_PORTRAIT + 4, lp - 2 * MARGE, PANNEAU_PORTRAIT - 4)
    _panneau(f, cadre, interieures, exterieures, s_hab, s_ext, echelle, fmt, infos, paysage)

    if infos.brouillon:
        _filigrane(f, "BROUILLON, NON VÉRIFIÉ")

    image = f.image.resize((f.image.width // SUR, f.image.height // SUR), Image.LANCZOS)
    return Page(image=image, format=fmt, echelle=echelle, surface_habitable=s_hab, surface_exterieurs=s_ext)


def _entete(f: _Feuille, infos: Infos, lp: float) -> None:
    x, y = MARGE, MARGE
    # Le logo : une petite maison dans un carré arrondi, puis le nom.
    c = 11.0
    f.d.rounded_rectangle((f.mm(x), f.mm(y), f.mm(x + c), f.mm(y + c)), radius=f.mm(2.2), fill=MARQUE)
    toit = [(x + c * 0.2, y + c * 0.52), (x + c * 0.5, y + c * 0.24), (x + c * 0.8, y + c * 0.52)]
    f.d.line([(f.mm(a), f.mm(b)) for a, b in toit], fill=BLANC, width=round(f.mm(0.9)), joint="curve")
    f.d.rectangle((f.mm(x + c * 0.3), f.mm(y + c * 0.5), f.mm(x + c * 0.7), f.mm(y + c * 0.78)),
                  outline=BLANC, width=round(f.mm(0.8)))
    f.texte((x + c + 3.5, y + 0.4), "Atelya", 5.2, MARQUE, ancre="la", gras=True)
    f.texte((x + c + 3.5, y + 8.2), "Plan réalisé par Atelya", 2.2, GRIS, ancre="la")
    # À droite : titre, adresse, date.
    xd = lp - MARGE
    f.texte((xd, y + 0.6), infos.titre, 4.0, TEXTE, ancre="ra", gras=True)
    ligne = y + 7.6
    if infos.adresse:
        for morceau in infos.adresse.replace("|", "\n").split("\n"):
            f.texte((xd, ligne), morceau.strip(), 2.4, TEXTE, ancre="ra")
            ligne += 3.8
    bas = f"Plan établi le {_date_fr(infos.date_plan)}"
    if infos.reference:
        bas += f"  ·  Réf. {infos.reference}"
    f.texte((xd, ligne), bas, 2.1, GRIS, ancre="ra")
    # Un filet sous l'en-tête.
    yl = f.mm(MARGE + ENTETE - 6)
    f.d.line(((f.mm(MARGE), yl), (f.mm(lp - MARGE), yl)), fill=(220, 218, 212), width=round(f.mm(0.3)))


def _panneau(f: _Feuille, cadre, interieures, exterieures, s_hab, s_ext, echelle, fmt, infos, paysage) -> None:
    x, y, l, h = cadre
    if not paysage:
        # En portrait : deux colonnes (surfaces à gauche, échelle et mention à droite).
        _tableau(f, x, y, l * 0.55 - 4, interieures, exterieures, s_hab, s_ext)
        _legende(f, x + l * 0.58, y + (16 if infos.nord_deg is not None else 0), l * 0.42, echelle, fmt, infos)
        return
    hauteur = _tableau(f, x, y, l, interieures, exterieures, s_hab, s_ext)
    _legende(f, x, max(y + hauteur + (22 if infos.nord_deg is not None else 8), y + h - 62), l, echelle, fmt, infos)


def _tableau(f: _Feuille, x, y, l, interieures, exterieures, s_hab, s_ext) -> float:
    depart = y
    f.texte((x, y), "SURFACES", 2.2, GRIS, gras=True)
    y += 6
    lignes = sorted(interieures, key=lambda p: -surface_piece(p)) + exterieures
    pas = 4.6 if len(lignes) <= 12 else max(3.2, 55 / len(lignes))
    taille = min(2.3, pas * 0.5)
    for p in lignes:
        if p in exterieures and p is exterieures[0]:
            y += 1.5
        couleur = GRIS if p in exterieures else TEXTE
        f.texte((x, y), p["nom"], taille, couleur)
        f.texte((x + l, y), f"{_fr(surface_piece(p))} m²", taille, couleur, ancre="ra")
        y += pas
    y += 1
    f.d.line(((f.mm(x), f.mm(y)), (f.mm(x + l), f.mm(y))), fill=TEXTE, width=round(f.mm(0.3)))
    y += 2.5
    f.texte((x, y), "Surface habitable", 2.5, TEXTE, gras=True)
    f.texte((x, y + 3.6), "indicative", 2.0, GRIS)
    f.texte((x + l, y), f"{_fr(s_hab)} m²", 3.6, MARQUE, ancre="ra", gras=True)
    y += 8.5
    if exterieures:
        f.texte((x, y), "Extérieurs (non compris)", 2.1, GRIS)
        f.texte((x + l, y), f"{_fr(s_ext)} m²", 2.3, GRIS, ancre="ra")
        y += 5
    return y - depart


def _legende(f: _Feuille, x, y, l, echelle, fmt, infos: Infos) -> None:
    # La barre d'échelle : des carreaux d'un mètre (ou de 2 m à petite échelle).
    pas_m = 1 if echelle <= 100 else 2 if echelle <= 250 else 5
    n = 5 if echelle <= 100 else 4
    pas_mm = pas_m * 1000 / echelle
    while n > 2 and n * pas_mm > l - 6:
        n -= 1
    hb = 1.6
    for i in range(n):
        x0 = x + i * pas_mm
        f.d.rectangle((f.mm(x0), f.mm(y), f.mm(x0 + pas_mm), f.mm(y + hb)),
                      fill=NOIR if i % 2 == 0 else BLANC, outline=NOIR, width=max(1, round(f.mm(0.15))))
    for i in range(n + 1):
        f.texte((x + i * pas_mm, y + hb + 1.2), f"{i * pas_m}", 1.9, GRIS, ancre="ma")
    f.texte((x + n * pas_mm + 2, y + hb / 2), "m", 1.9, GRIS, ancre="lm")
    if infos.nord_deg is not None:
        _fleche_nord(f, x + l - 6, y - 10, infos.nord_deg)
    y += 9
    f.texte((x, y), f"Échelle 1/{echelle} (impression {fmt}, sans ajustement)", 2.0, TEXTE)
    y += 3.8
    f.texte((x, y), "Cotes en mètres, dimensions intérieures des pièces", 2.0, GRIS)
    y += 3.8
    y += 2.5
    f.paragraphe((x, y), MENTION, 1.9, l, GRIS, interligne=1.55)


def _fleche_nord(f: _Feuille, cx_mm: float, cy_mm: float, angle_deg: float) -> None:
    a = math.radians(angle_deg)
    def tourne(dx, dy):  # dx, dy en mm, y vers le bas
        return f.mm(cx_mm + dx * math.cos(a) - dy * math.sin(a)), f.mm(cy_mm + dx * math.sin(a) + dy * math.cos(a))
    f.d.ellipse((f.mm(cx_mm - 5), f.mm(cy_mm - 5), f.mm(cx_mm + 5), f.mm(cy_mm + 5)),
                outline=GRIS_CLAIR, width=round(f.mm(0.2)))
    f.d.polygon([tourne(0, -4.2), tourne(-1.8, 2.8), tourne(0, 1.6)], fill=NOIR)
    f.d.polygon([tourne(0, -4.2), tourne(1.8, 2.8), tourne(0, 1.6)], fill=GRIS_CLAIR)
    nx, ny = tourne(0, -7.3)
    f.texte((nx / f.k, ny / f.k), "N", 2.2, TEXTE, ancre="mm", gras=True)


def _filigrane(f: _Feuille, texte: str) -> None:
    police = _police(round(f.mm(14)))
    g, h, d, b = police.getbbox(texte)
    calque = Image.new("L", (d - g + 20, b - h + 20), 0)
    ImageDraw.Draw(calque).text((10 - g, 10 - h), texte, fill=255, font=police)
    calque = calque.rotate(28, expand=True, resample=Image.BICUBIC)
    calque = calque.point(lambda v: v * 0.28)
    x = (f.image.width - calque.width) // 2
    y = (f.image.height - calque.height) // 2
    f.image.paste(Image.new("RGB", calque.size, (200, 40, 40)), (x, y), calque)


# ---------- Commande ----------


def faire_plan(entree: str | Path, sortie: str | Path, infos: Infos | None = None, format_page: str | None = None,
               verifie: bool = False, png: bool = True) -> Page:
    """Lit un fichier, dessine la page, écrit le PDF (et un PNG d'aperçu à côté)."""
    donnees = json.loads(Path(entree).read_text(encoding="utf-8"))
    logement, deja_verifie, infos_fichier = lire_entree(donnees)
    infos = infos or Infos()
    if not infos.adresse and infos_fichier.get("adresse"):
        infos.adresse = infos_fichier["adresse"]
    if infos.titre == Infos.titre and infos_fichier.get("titre"):
        infos.titre = infos_fichier["titre"]
    if infos.nord_deg is None and infos_fichier.get("nord_deg") is not None:
        infos.nord_deg = float(infos_fichier["nord_deg"])
    if not infos.reference:
        infos.reference = infos_fichier.get("reference") or logement.get("projet_id", "")
    infos.brouillon = not (deja_verifie or verifie)
    page = dessiner_page(logement, infos, format_page)
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    page.enregistrer_pdf(sortie)
    if png:
        page.enregistrer_png(sortie.with_suffix(".png"), reduction=2)
    return page


def main(arguments: list[str] | None = None) -> None:
    a = argparse.ArgumentParser(description="Dessine le plan 2D propre (PDF) d'un logement lu par Atelya.")
    a.add_argument("entree", help="logement.json, ou résultat de l'écran de vérification")
    a.add_argument("--sortie", default=None, help="fichier PDF (par défaut : à côté de l'entrée)")
    a.add_argument("--titre", default=Infos.titre)
    a.add_argument("--adresse", default="", help="sur plusieurs lignes : séparer par « | »")
    a.add_argument("--reference", default="")
    a.add_argument("--nord", type=float, default=None, help="angle du nord en degrés depuis le haut, sens horaire")
    a.add_argument("--format", choices=sorted(FORMATS_MM), default=None)
    a.add_argument("--verifie", action="store_true", help="le logement a été contrôlé par un humain")
    o = a.parse_args(arguments)
    sortie = o.sortie or str(Path(o.entree).with_suffix("")) + "-plan.pdf"
    infos = Infos(titre=o.titre, adresse=o.adresse.replace("|", "\n"), reference=o.reference, nord_deg=o.nord)
    page = faire_plan(o.entree, sortie, infos, o.format, o.verifie)
    etat = "BROUILLON (non vérifié)" if infos.brouillon else "vérifié"
    print(f"{sortie} : {page.format}, échelle 1/{page.echelle}, "
          f"surface habitable indicative {_fr(page.surface_habitable)} m², {etat}")


if __name__ == "__main__":
    main()
