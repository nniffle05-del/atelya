"""Les meubles dessinés dans les pièces (variante « avec mobilier »).

Des symboles simples, comme sur les plans d'agence : lit, table de chevet, canapé, table,
plan de travail, évier, baignoire ou douche, lavabo, WC, machine à laver, bureau, étagère,
marches d'escalier. Tout est dessiné par notre code (aucun symbole importé), à partir du
rectangle de la pièce, en évitant la zone de battement des portes.

Chaque meuble a un type, un polygone (en mm, repère du logement) et une hauteur (pour la
carte de hauteur). Les meubles font partie de la vérité terrain « décor » : ils sont listés
dans les annotations mais n'entrent pas dans les masques des pièces (une pièce reste une pièce
sous son lit).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from moteur.generateur.logements import Niveau, Ouverture, Piece, Rect

Point = tuple[float, float]


@dataclass
class Meuble:
    type: str
    contour: list[Point]  # polygone en mm
    hauteur: int  # mm
    forme: str = "rect"  # rect, ellipse, marches (dessin des traits intérieurs)
    details: list[list[Point]] | None = None  # traits intérieurs (dossier du canapé, marches…)


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _zones_de_battement(piece: Piece, ouvertures: list[Ouverture]) -> list[Rect]:
    """Devant chaque porte de la pièce, un carré de la largeur de la porte reste libre."""
    r = piece.rect
    zones = []
    for o in ouvertures:
        if o.type == "fenetre":
            continue
        m = o.mur
        e = m.epaisseur / 2
        largeur = o.u1 - o.u0
        if m.vertical:
            if abs(m.axe + e - r.x0) < 1e-6 and r.y0 <= o.u0 and o.u1 <= r.y1:
                zones.append(Rect(r.x0, int(o.u0), int(r.x0 + largeur), int(o.u1)))
            elif abs(m.axe - e - r.x1) < 1e-6 and r.y0 <= o.u0 and o.u1 <= r.y1:
                zones.append(Rect(int(r.x1 - largeur), int(o.u0), r.x1, int(o.u1)))
        else:
            if abs(m.axe + e - r.y0) < 1e-6 and r.x0 <= o.u0 and o.u1 <= r.x1:
                zones.append(Rect(int(o.u0), r.y0, int(o.u1), int(r.y0 + largeur)))
            elif abs(m.axe - e - r.y1) < 1e-6 and r.x0 <= o.u0 and o.u1 <= r.x1:
                zones.append(Rect(int(o.u0), int(r.y1 - largeur), int(o.u1), r.y1))
    return zones


def _libre(rect: Rect, interdits: list[Rect], poses: list[Rect]) -> bool:
    for z in interdits + poses:
        if rect.x0 < z.x1 and z.x0 < rect.x1 and rect.y0 < z.y1 and z.y0 < rect.y1:
            return False
    return True


def _contre_un_mur(piece: Piece, lx: int, ly: int, interdits: list[Rect], poses: list[Rect],
                   rng: random.Random, marge: int = 50) -> Rect | None:
    """Un rectangle lx × ly posé contre un des murs de la pièce (le long duquel il tient), s'il y a la place."""
    r = piece.rect
    cotes = ["sud", "nord", "ouest", "est"]
    rng.shuffle(cotes)
    for cote in cotes:
        for _ in range(6):
            if cote in ("sud", "nord"):
                if r.largeur < lx + 2 * marge:
                    continue
                x0 = rng.randint(r.x0 + marge, r.x1 - marge - lx)
                y0 = r.y0 + marge if cote == "sud" else r.y1 - marge - ly
                cand = Rect(x0, y0, x0 + lx, y0 + ly)
            else:
                if r.hauteur < ly + 2 * marge:
                    continue
                y0 = rng.randint(r.y0 + marge, r.y1 - marge - ly)
                x0 = r.x0 + marge if cote == "ouest" else r.x1 - marge - lx
                cand = Rect(x0, y0, x0 + lx, y0 + ly)
            if cand.x0 >= r.x0 and cand.y0 >= r.y0 and cand.x1 <= r.x1 and cand.y1 <= r.y1 and _libre(cand, interdits, poses):
                poses.append(cand)
                return cand
    return None


def meubler(piece: Piece, niveau: Niveau, rng: random.Random) -> list[Meuble]:
    """Les meubles d'une pièce, selon sa sorte (liste vide pour un placard ou un dégagement)."""
    r = piece.rect
    interdits = _zones_de_battement(piece, niveau.ouvertures) + list(piece.interdits)
    poses: list[Rect] = []
    meubles: list[Meuble] = []

    def pose(type_: str, lx: int, ly: int, hauteur: int, forme: str = "rect", tourner: bool = True) -> Rect | None:
        if tourner and r.largeur < r.hauteur:
            lx, ly = ly, lx
        rect = _contre_un_mur(piece, lx, ly, interdits, poses, rng)
        if rect is None and tourner:
            rect = _contre_un_mur(piece, ly, lx, interdits, poses, rng)
        if rect is not None:
            meubles.append(Meuble(type_, _rect(rect.x0, rect.y0, rect.x1, rect.y1), hauteur, forme))
        return rect

    sorte = piece.sorte
    if sorte == "chambre":
        lit = pose("lit", rng.choice([1400, 1600, 1800]), 2000, 500)
        if lit is not None:
            # Deux oreillers côté mur (le petit côté collé au mur) et une table de chevet.
            meubles[-1].details = _oreillers(lit, r)
            pose("chevet", 450, 450, 550, tourner=False)
        pose("armoire", 1200, 600, 2100)
    elif sorte in ("sejour", "principale"):
        canape = pose("canape", rng.choice([1800, 2000, 2200]), 900, 850)
        if canape is not None:
            meubles[-1].details = [_dossier(canape, r)]
        pose("table", rng.choice([1200, 1400, 1600]), 800, 750, forme=rng.choice(["rect", "ellipse"]))
        if sorte == "principale":
            pose("lit", 1400, 2000, 500)
        if "cuisine" in piece.nom.lower() or (sorte == "principale"):
            pose("plan_de_travail", rng.choice([1800, 2400, 3000]), 600, 900)
    elif sorte == "cuisine":
        pose("plan_de_travail", rng.choice([1800, 2400, 3000]), 600, 900)
        if rng.random() < 0.6:
            pose("plan_de_travail", rng.choice([1200, 1800]), 600, 900)
        if rng.random() < 0.5:
            pose("table", 800, 800, 750)
    elif sorte in ("sdb", "sde"):
        if sorte == "sdb" and rng.random() < 0.7:
            pose("baignoire", 1700, 750, 550)
        else:
            pose("douche", rng.choice([800, 900]), rng.choice([800, 900, 1200]), 50, tourner=False)
        pose("lavabo", 600, 450, 850, forme="ellipse")
        if rng.random() < 0.4:
            pose("wc", 400, 650, 400, forme="ellipse")
    elif sorte == "wc":
        pose("wc", 400, 650, 400, forme="ellipse")
    elif sorte == "buanderie":
        pose("lave_linge", 600, 600, 850)
        if rng.random() < 0.5:
            pose("etagere", 800, 400, 1800)
    elif sorte == "bureau":
        pose("bureau", 1400, 700, 750)
        pose("etagere", 800, 350, 1800)
    elif sorte == "escalier":
        meubles.append(_escalier(piece, niveau))
    return meubles


def _oreillers(lit: Rect, piece: Rect) -> list[list[Point]]:
    """Deux oreillers au bout du lit qui touche le mur ; un trait les sépare du reste."""
    long_en_x = lit.largeur > lit.hauteur
    details = []
    if long_en_x:
        au_mur_ouest = lit.x0 - piece.x0 <= piece.x1 - lit.x1
        xo = lit.x0 + 80 if au_mur_ouest else lit.x1 - 80 - 450
        for k in range(2):
            y = lit.y0 + 80 + k * (lit.hauteur - 160) / 2
            details.append(_rect(xo, y, xo + 450, y + (lit.hauteur - 160) / 2 - 60))
        x_sep = lit.x0 + 600 if au_mur_ouest else lit.x1 - 600
        details.append([(x_sep, lit.y0), (x_sep, lit.y1)])
    else:
        au_mur_sud = lit.y0 - piece.y0 <= piece.y1 - lit.y1
        yo = lit.y0 + 80 if au_mur_sud else lit.y1 - 80 - 450
        for k in range(2):
            x = lit.x0 + 80 + k * (lit.largeur - 160) / 2
            details.append(_rect(x, yo, x + (lit.largeur - 160) / 2 - 60, yo + 450))
        y_sep = lit.y0 + 600 if au_mur_sud else lit.y1 - 600
        details.append([(lit.x0, y_sep), (lit.x1, y_sep)])
    return details


def _dossier(canape: Rect, piece: Rect) -> list[Point]:
    """Le dossier du canapé : un trait le long du côté collé au mur."""
    if canape.largeur > canape.hauteur:
        y = canape.y0 + 250 if canape.y0 - piece.y0 <= piece.y1 - canape.y1 else canape.y1 - 250
        return [(canape.x0, y), (canape.x1, y)]
    x = canape.x0 + 250 if canape.x0 - piece.x0 <= piece.x1 - canape.x1 else canape.x1 - 250
    return [(x, canape.y0), (x, canape.y1)]


def _escalier(piece: Piece, niveau: Niveau) -> Meuble:
    """Les marches d'un escalier droit : des traits en travers de la pièce, tous les 25 cm environ."""
    r = piece.rect
    le_long_de_x = r.largeur >= r.hauteur
    longueur = r.largeur if le_long_de_x else r.hauteur
    n = max(2, round(longueur / 260))
    pas = longueur / n
    traits = []
    for k in range(1, n):
        if le_long_de_x:
            x = r.x0 + k * pas
            traits.append([(x, r.y0), (x, r.y1)])
        else:
            y = r.y0 + k * pas
            traits.append([(r.x0, y), (r.x1, y)])
    # La flèche du sens de montée, au milieu.
    if le_long_de_x:
        traits.append([(r.x0 + 150, (r.y0 + r.y1) / 2), (r.x1 - 150, (r.y0 + r.y1) / 2)])
    else:
        traits.append([((r.x0 + r.x1) / 2, r.y0 + 150), ((r.x0 + r.x1) / 2, r.y1 - 150)])
    hauteur = niveau.hsp  # la hauteur « vue de dessus » de la montée (les marches montent jusqu'au plancher)
    return Meuble("escalier", _rect(r.x0, r.y0, r.x1, r.y1), hauteur, "marches", traits)


def meubler_niveau(niveau: Niveau, graine: int) -> dict[str, list[Meuble]]:
    """Les meubles de chaque pièce du niveau ; même graine, mêmes meubles."""
    rng = random.Random(f"mobilier-{graine}-{niveau.index}")
    return {p.id: meubler(p, niveau, rng) for p in niveau.pieces}
