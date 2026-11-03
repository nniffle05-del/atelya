"""La fabrique de plans : inventer des logements et les dessiner, avec leur corrigé (étape 5b).

Pour rendre la lecture des plans fiable, il faut beaucoup de plans dont on
connaît la bonne réponse. La fabrique en invente autant qu'on veut :

1. Elle choisit un type de logement (T1 à T4) et son programme : la liste
   des pièces et une surface visée pour chacune.
2. Elle choisit un contour : un rectangle, ou une forme en L (un rectangle
   auquel il manque un coin).
3. Elle découpe l'intérieur par des cloisons droites, une à une, en partageant
   la surface entre les pièces (découpage « en guillotine » : chaque cloison
   traverse tout le morceau qu'elle coupe).
4. Elle vérifie que le résultat est habitable : tailles de pièces courantes,
   chaque chambre ou salle d'eau accessible depuis l'entrée, le séjour ou un
   couloir, une fenêtre possible dans chaque pièce de vie. Sinon, elle
   recommence (avec d'autres tirages).
5. Elle place la porte d'entrée, les portes intérieures et les fenêtres.

Le résultat est un logement.json (le corrigé, vérifié par les règles de
logement.py), puis un plan.png dessiné par dessin_plan.py.

Tout dépend d'un seul numéro, la « graine » : la même graine redonne
exactement le même logement et le même dessin. On peut donc refabriquer un
plan à l'identique, sans l'avoir gardé.

Limites de la version 0.1 : angles droits seulement (comme le format
logement/0.1) ; un seul niveau ; pas de mobilier ni de cuisine dessinée.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from moteur.habillage import sans_accents
from moteur.logement import Logement

# Tout est calculé en millimètres entiers, pour éviter les erreurs d'arrondi ;
# le logement.json est écrit en mètres.
PAS = 50  # les pièces mesurent un nombre entier de fois 5 cm
MARGE_OUVERTURE = 150  # une fenêtre reste à 15 cm au moins des angles de sa pièce
MARGE_PORTE = 100  # une porte, à 10 cm au moins
ECART_OUVERTURES = 300  # deux ouvertures d'un même mur restent à 30 cm l'une de l'autre
ESSAIS_MAX = 2000  # tirages avant d'abandonner une graine
BUDGET_COUPES = 300  # coupes essayées par tirage
ECARTS = (1.0, 0.85, 1.15, 0.7, 1.3)  # une coupe peut s'écarter du partage exact des surfaces visées

TYPES = {"T1": 0.20, "T2": 0.35, "T3": 0.30, "T4": 0.15}

# Pour chaque sorte de pièce : plus petit côté (mm) et allongement maximal (grand côté / petit côté).
COTE_MIN = {"sejour": 3000, "cuisine": 1800, "chambre": 2600, "sdb": 1500, "wc": 850, "entree": 1100, "degagement": 900}
COTE_MAX_WC = 2200
ALLONGEMENT_MAX = {"sejour": 2.2, "cuisine": 2.6, "chambre": 1.8, "sdb": 2.4, "wc": 2.8, "entree": 4.0, "degagement": 7.0}
SURFACE_MIN = {"sejour": 15.0, "chambre": 8.5, "cuisine": 5.0}  # m²
DISTRIBUTION = {"entree", "degagement", "sejour"}  # les pièces par lesquelles on passe pour aller ailleurs
AVEC_FENETRE = {"sejour", "chambre", "cuisine"}  # pièces de vie : une fenêtre obligatoire


@dataclass
class Rect:
    """Un rectangle aux côtés horizontaux et verticaux, en mm : x vers l'est, y vers le nord."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def largeur(self) -> int:
        return self.x1 - self.x0

    @property
    def hauteur(self) -> int:
        return self.y1 - self.y0


@dataclass
class Piece:
    nom: str
    sorte: str  # sejour, cuisine, chambre, sdb, wc, entree, degagement
    cible: float  # surface visée, en m²
    rect: Rect | None = None


@dataclass
class Mur:
    """Un mur droit, par son axe : `vertical` (de sud en nord) ou horizontal (d'ouest en est).

    `axe` : x (mur vertical) ou y (mur horizontal) de l'axe ; `debut` < `fin` : étendue le long du mur.
    `dehors` : pour un mur extérieur, le côté de l'extérieur (+1 ou -1 le long de x ou y) ; 0 pour une cloison.
    """

    vertical: bool
    axe: float
    debut: float
    fin: float
    epaisseur: int
    dehors: int = 0
    id: str = ""


@dataclass
class Ouverture:
    """Une ouverture dans un mur, par son étendue le long du mur (mêmes coordonnées que debut/fin du mur)."""

    type: str  # porte, porte_fenetre, fenetre
    mur: Mur
    u0: float
    u1: float
    hauteur: int
    allege: int
    vers: int = 0  # côté où s'ouvre le battant (+1 ou -1 le long de x ou y) ; 0 pour une fenêtre
    charniere: int = 0  # 0 : charnière du côté de u0 ; 1 : du côté de u1
    id: str = ""


@dataclass
class Fabrication:
    """Un logement inventé, avant son écriture en logement.json."""

    graine: int
    type: str
    forme: str  # rectangle ou L
    hsp: int
    ep_ext: int
    ep_cloison: int
    pieces: list[Piece]
    murs: list[Mur]
    ouvertures: list[Ouverture] = field(default_factory=list)
    essais: int = 1

    @property
    def surface(self) -> float:
        return round(sum(p.rect.largeur * p.rect.hauteur for p in self.pieces) / 1e6, 2)


# ---------- 1. Le programme ----------


def programme(type_: str, rng: random.Random) -> list[Piece]:
    """La liste des pièces d'un logement de ce type, avec une surface visée pour chacune."""

    def p(nom: str, sorte: str, mini: float, maxi: float) -> Piece:
        return Piece(nom, sorte, round(rng.uniform(mini, maxi), 1))

    pieces: list[Piece] = []
    chambres = {"T1": 0, "T2": 1, "T3": 2, "T4": 3}[type_]
    cuisine_a_part = rng.random() < {"T1": 0.0, "T2": 0.3, "T3": 0.5, "T4": 0.6}[type_]
    if cuisine_a_part:
        pieces += [p("Séjour", "sejour", 17, 26 + 2 * chambres), p("Cuisine", "cuisine", 6, 10)]
    else:
        pieces.append(p(rng.choice(["Séjour + cuisine", "Séjour"]), "sejour", 19 + 2 * chambres, 27 + 3 * chambres))
    for i in range(chambres):
        nom = "Chambre" if chambres == 1 else f"Chambre {i + 1}"
        pieces.append(p(nom, "chambre", 9.5, 13.5 if i == 0 else 12))
    if type_ == "T4" and rng.random() < 0.5:
        pieces += [p("Salle de bains", "sdb", 4, 6), p("Salle d'eau", "sdb", 3, 4)]
    else:
        pieces.append(p(rng.choice(["Salle de bains", "Salle d'eau"]), "sdb", 3.2, 4.5 + 0.5 * chambres))
    if rng.random() < {"T1": 0.0, "T2": 0.5, "T3": 0.85, "T4": 1.0}[type_]:
        pieces.append(p("WC", "wc", 1.2, 1.8))
    if rng.random() < {"T1": 1.0, "T2": 0.85, "T3": 1.0, "T4": 1.0}[type_]:
        pieces.append(p("Entrée", "entree", 2.2, 3.5 + chambres * 0.6))
    if rng.random() < {"T1": 0.0, "T2": 0.1, "T3": 0.6, "T4": 0.85}[type_]:
        pieces.append(p("Dégagement", "degagement", 2.0, 4.5))
    return pieces


# ---------- 2 et 3. Le contour et le découpage ----------


def _arrondi(v: float) -> int:
    return int(round(v / PAS)) * PAS


def _decouper(rect: Rect, pieces: list[Piece], ep: int, rng: random.Random, cloisons: list[Mur],
              budget: list[int]) -> bool:
    """Découpe le rectangle entre les pièces, proportionnellement à leurs surfaces visées.

    On essaie les coupes possibles dans un ordre au hasard, et on revient en arrière quand
    une pièce sort trop petite ou trop allongée. `budget` limite le nombre de coupes essayées.
    Renvoie False si aucun découpage ne convient (les cloisons ajoutées sont alors retirées).
    """
    if len(pieces) == 1:
        pieces[0].rect = rect
        return _habitable(pieces[0])
    if not _assez_grand(rect, pieces):
        return False
    coupes = [(k, vertical, ecart) for k in range(1, len(pieces)) for vertical in (True, False) for ecart in ECARTS]
    rng.shuffle(coupes)
    # D'abord les coupes dans la longueur du rectangle, puis les surfaces les plus proches des surfaces visées.
    coupes.sort(key=lambda c: (c[1] != (rect.largeur >= rect.hauteur), abs(c[2] - 1)))
    for k, vertical, ecart in coupes:
        if budget[0] <= 0:
            return False
        budget[0] -= 1
        a, b = pieces[:k], pieces[k:]
        part = min(0.95, ecart * sum(p.cible for p in a) / sum(p.cible for p in pieces))
        longueur = (rect.largeur if vertical else rect.hauteur) - ep
        l1 = _arrondi(part * longueur)
        if l1 < PAS or l1 > longueur - PAS:
            continue
        if vertical:  # cloison verticale : a à l'ouest, b à l'est
            f = rect.x0 + l1
            cloison = Mur(True, f + ep / 2, rect.y0, rect.y1, ep)
            r1, r2 = Rect(rect.x0, rect.y0, f, rect.y1), Rect(f + ep, rect.y0, rect.x1, rect.y1)
        else:  # cloison horizontale : a au sud, b au nord
            f = rect.y0 + l1
            cloison = Mur(False, f + ep / 2, rect.x0, rect.x1, ep)
            r1, r2 = Rect(rect.x0, rect.y0, rect.x1, f), Rect(rect.x0, f + ep, rect.x1, rect.y1)
        n = len(cloisons)
        cloisons.append(cloison)
        if _decouper(r1, a, ep, rng, cloisons, budget) and _decouper(r2, b, ep, rng, cloisons, budget):
            return True
        del cloisons[n:]
    return False


def _assez_grand(rect: Rect, pieces: list[Piece]) -> bool:
    """Un rectangle trop étroit pour la plus petite de ses pièces ne peut pas convenir."""
    besoin = min(COTE_MIN[p.sorte] for p in pieces)
    return min(rect.largeur, rect.hauteur) >= besoin


def _contour(largeur: int, profondeur: int, encoche: tuple[int, int] | None) -> list[tuple[int, int]]:
    """Les coins intérieurs du logement, dans le sens inverse des aiguilles d'une montre.

    Avec une encoche (a, b), il manque le coin sud-est : a de large, b de haut (forme en L).
    """
    w, h = largeur, profondeur
    if encoche is None:
        return [(0, 0), (w, 0), (w, h), (0, h)]
    a, b = encoche
    return [(0, 0), (w - a, 0), (w - a, b), (w, b), (w, h), (0, h)]


def _murs_exterieurs(coins: list[tuple[int, int]], ep: int) -> list[Mur]:
    """Un mur par côté du contour, d'axe décalé d'une demi-épaisseur vers l'extérieur, rejoint aux angles."""
    n = len(coins)
    cotes = []  # (vertical, face, côté du dehors)
    for i in range(n):
        (x1, y1), (x2, y2) = coins[i], coins[(i + 1) % n]
        if x1 == x2:  # sens inverse des aiguilles d'une montre : le dehors est à droite du trajet
            cotes.append((True, x1, 1 if y2 > y1 else -1))
        else:
            cotes.append((False, y1, -1 if x2 > x1 else 1))
    axes = [face + dehors * ep / 2 for _, face, dehors in cotes]
    murs = []
    for i, (vertical, _, dehors) in enumerate(cotes):
        avant, apres = axes[i - 1], axes[(i + 1) % n]
        murs.append(Mur(vertical, axes[i], min(avant, apres), max(avant, apres), ep, dehors))
    return murs


def _faces_exterieures(piece: Piece, murs: list[Mur]) -> list[tuple[Mur, float, float]]:
    """Les morceaux des murs extérieurs qui bordent la pièce : (mur, début, fin) le long du mur."""
    r = piece.rect
    faces = []
    for m in murs:
        if not m.dehors:
            continue
        face = m.axe - m.dehors * m.epaisseur / 2
        if m.vertical and face == (r.x1 if m.dehors > 0 else r.x0):
            a, b = max(r.y0, m.debut), min(r.y1, m.fin)
        elif not m.vertical and face == (r.y1 if m.dehors > 0 else r.y0):
            a, b = max(r.x0, m.debut), min(r.x1, m.fin)
        else:
            continue
        if b > a:
            faces.append((m, a, b))
    return faces


def _passages(p: Piece, q: Piece, cloisons: list[Mur]) -> tuple[Mur, float, float, int] | None:
    """La cloison commune à deux pièces voisines : (cloison, début, fin du morceau commun, côté de q)."""
    a, b = p.rect, q.rect
    for c in cloisons:
        e = c.epaisseur / 2
        if c.vertical and a.x1 == c.axe - e and b.x0 == c.axe + e:
            u0, u1, cote = max(a.y0, b.y0), min(a.y1, b.y1), 1
        elif c.vertical and a.x0 == c.axe + e and b.x1 == c.axe - e:
            u0, u1, cote = max(a.y0, b.y0), min(a.y1, b.y1), -1
        elif not c.vertical and a.y1 == c.axe - e and b.y0 == c.axe + e:
            u0, u1, cote = max(a.x0, b.x0), min(a.x1, b.x1), 1
        elif not c.vertical and a.y0 == c.axe + e and b.y1 == c.axe - e:
            u0, u1, cote = max(a.x0, b.x0), min(a.x1, b.x1), -1
        else:
            continue
        if u1 > u0 and c.debut <= u0 and u1 <= c.fin:
            return c, u0, u1, cote
    return None


def _habitable(p: Piece) -> bool:
    r = p.rect
    petit, grand = sorted((r.largeur, r.hauteur))
    if petit < COTE_MIN[p.sorte] or grand / petit > ALLONGEMENT_MAX[p.sorte]:
        return False
    if p.sorte == "wc" and grand > COTE_MAX_WC:
        return False
    surface = r.largeur * r.hauteur / 1e6
    # Une pièce peut s'écarter de sa surface visée, mais pas du simple au double.
    return SURFACE_MIN.get(p.sorte, 0) <= surface and 0.6 * p.cible <= surface <= 1.5 * p.cible


# ---------- 4 et 5. Vérifier et percer ----------


class Rate(Exception):
    """Ce tirage ne donne pas un logement habitable : on recommence."""


def _largeur_porte(p: Piece, q: Piece, rng: random.Random) -> int:
    sortes = {p.sorte, q.sorte}
    if "wc" in sortes or "sdb" in sortes:
        return rng.choice([700, 800])
    if sortes <= {"sejour", "entree", "degagement"}:
        return rng.choice([800, 900, 900])
    return rng.choice([800, 800, 900])


def _placer(occupe: dict[int, list[tuple[float, float]]], mur: Mur, a: float, b: float, largeur: int,
            marge: int, rng: random.Random) -> tuple[float, float] | None:
    """Une place libre de cette largeur entre a et b sur le mur, loin des autres ouvertures (ou None)."""
    debut, fin = a + marge, b - marge - largeur
    if fin < debut:
        return None
    for _ in range(20):
        u0 = round(rng.uniform(debut, fin) / 10) * 10  # au centimètre
        u0 = min(max(u0, debut), fin)
        if all(u0 + largeur + ECART_OUVERTURES <= v0 or v1 + ECART_OUVERTURES <= u0 for v0, v1 in occupe.get(id(mur), [])):
            occupe.setdefault(id(mur), []).append((u0, u0 + largeur))
            return u0, u0 + largeur
    return None


def _battant(piece: Piece, mur: Mur, largeur: int) -> bool:
    """Le battant d'une porte de cette largeur, ouverte vers la pièce, y tient-il ?"""
    profondeur = piece.rect.largeur if mur.vertical else piece.rect.hauteur
    return profondeur >= largeur + 50


def _percer(fab: Fabrication, cloisons: list[Mur], rng: random.Random) -> None:
    """Porte d'entrée, portes intérieures et fenêtres. Lève Rate si le logement n'est pas desservi."""
    pieces = fab.pieces
    occupe: dict[int, list[tuple[float, float]]] = {}

    # Portes intérieures : un arbre de passages depuis la pièce d'entrée.
    entree = next((p for p in pieces if p.sorte == "entree"), next(p for p in pieces if p.sorte == "sejour"))
    voisins = {}
    for i, p in enumerate(pieces):
        for j, q in enumerate(pieces):
            if i != j and (passage := _passages(p, q, cloisons)) is not None:
                voisins[(i, j)] = passage
    atteintes = {pieces.index(entree)}
    a_traiter = [pieces.index(entree)]
    while a_traiter:  # d'abord les pièces de distribution, en partant de l'entrée
        i = a_traiter.pop(0)
        for j, q in enumerate(pieces):
            if j in atteintes or (i, j) not in voisins or q.sorte not in DISTRIBUTION:
                continue
            if _porte(fab, pieces[i], q, voisins[(i, j)], occupe, rng):
                atteintes.add(j)
                a_traiter.append(j)
    for j, q in enumerate(pieces):  # puis chaque autre pièce, depuis une pièce de distribution voisine
        if j in atteintes:
            continue
        hubs = [i for i in atteintes if (i, j) in voisins and pieces[i].sorte in DISTRIBUTION]
        # On préfère entrer dans une chambre ou une salle d'eau par l'entrée ou un couloir plutôt que par le séjour.
        hubs.sort(key=lambda i: (pieces[i].sorte == "sejour") != (q.sorte == "cuisine"))
        if not any(_porte(fab, pieces[i], q, voisins[(i, j)], occupe, rng) for i in hubs):
            raise Rate(f"{q.nom} n'est pas desservie")
        atteintes.add(j)

    # Porte d'entrée, sur un mur extérieur de la pièce d'entrée.
    faces = _faces_exterieures(entree, fab.murs)
    rng.shuffle(faces)
    largeur = rng.choice([900, 900, 800])
    for mur, a, b in faces:
        if (place := _placer(occupe, mur, a, b, largeur, MARGE_PORTE, rng)) is not None:
            fab.ouvertures.append(Ouverture("porte", mur, *place, 2040, 0, vers=-mur.dehors, charniere=rng.randint(0, 1)))
            break
    else:
        raise Rate("pas de place pour la porte d'entrée")

    # Fenêtres.
    for p in pieces:
        faces = _faces_exterieures(p, fab.murs)
        rng.shuffle(faces)
        voulues = _fenetres_voulues(p, fab.hsp, rng)
        posees = 0
        for type_, largeur in voulues:
            for mur, a, b in faces:
                if (place := _placer(occupe, mur, a, b, largeur, MARGE_OUVERTURE, rng)) is not None:
                    fab.ouvertures.append(_fenetre(type_, mur, place, fab.hsp, rng))
                    posees += 1
                    break
        if p.sorte in AVEC_FENETRE and posees == 0:
            raise Rate(f"{p.nom} n'a pas de fenêtre")

    # Un dégagement (couloir) qui ne mène qu'à une seule pièce ne sert à rien.
    for p in pieces:
        if p.sorte == "degagement" and sum(_borde(o, p) for o in fab.ouvertures if o.type == "porte") < 2:
            raise Rate(f"{p.nom} ne dessert rien")


def _borde(o: Ouverture, p: Piece) -> bool:
    """L'ouverture est-elle dans un mur de la pièce ?"""
    r, m = p.rect, o.mur
    e = m.epaisseur / 2
    if m.vertical:
        return m.axe in (r.x0 - e, r.x1 + e) and r.y0 <= o.u0 and o.u1 <= r.y1
    return m.axe in (r.y0 - e, r.y1 + e) and r.x0 <= o.u0 and o.u1 <= r.x1


def _porte(fab: Fabrication, p: Piece, q: Piece, passage: tuple[Mur, float, float, int],
           occupe: dict, rng: random.Random) -> bool:
    """Perce une porte entre p et q dans leur cloison commune ; elle s'ouvre vers q si le battant y tient."""
    cloison, a, b, cote_q = passage
    largeur = _largeur_porte(p, q, rng)
    place = _placer(occupe, cloison, a, b, largeur, MARGE_PORTE, rng)
    if place is None:
        return False
    vers = cote_q if _battant(q, cloison, largeur) else -cote_q
    if not _battant(q if vers == cote_q else p, cloison, largeur):
        occupe[id(cloison)].pop()
        return False
    fab.ouvertures.append(Ouverture("porte", cloison, *place, 2040, 0, vers=vers, charniere=rng.randint(0, 1)))
    return True


def _fenetres_voulues(p: Piece, hsp: int, rng: random.Random) -> list[tuple[str, int]]:
    pf = hsp >= 2300  # une porte-fenêtre de 2,15 m demande assez de hauteur
    if p.sorte == "sejour":
        premiere = ("porte_fenetre", rng.choice([1400, 1600, 1800, 2000, 2400])) if pf and rng.random() < 0.6 \
            else ("fenetre", rng.choice([1200, 1400, 1600, 1800]))
        return [premiere] + ([("fenetre", rng.choice([1000, 1200, 1400]))] if rng.random() < 0.5 else [])
    if p.sorte == "chambre":
        if pf and rng.random() < 0.2:
            return [("porte_fenetre", rng.choice([1200, 1400]))]
        return [("fenetre", rng.choice([900, 1000, 1200, 1400]))]
    if p.sorte == "cuisine":
        return [("fenetre", rng.choice([800, 1000, 1200]))]
    if p.sorte in {"sdb", "wc"} and rng.random() < 0.5:
        return [("fenetre", rng.choice([500, 600, 800]))]
    return []


def _fenetre(type_: str, mur: Mur, place: tuple[float, float], hsp: int, rng: random.Random) -> Ouverture:
    if type_ == "porte_fenetre":
        return Ouverture(type_, mur, *place, 2150, 0, vers=-mur.dehors, charniere=rng.randint(0, 1))
    largeur = place[1] - place[0]
    hauteur = 600 if largeur <= 600 else rng.choice([1150, 1250, 1350, 1450])
    haut = min(hsp - 150, rng.choice([2150, 2200, 2250]))
    return Ouverture(type_, mur, *place, hauteur, haut - hauteur)


# ---------- Le tout ----------


def fabriquer(graine: int) -> Fabrication:
    """Invente un logement habitable à partir de la graine (toujours le même pour la même graine)."""
    rng = random.Random(graine)
    type_ = rng.choices(list(TYPES), weights=list(TYPES.values()))[0]
    hsp = rng.choice([2400, 2500, 2500, 2500, 2550, 2600, 2700])
    ep_ext = rng.choices([150, 200, 250, 300], weights=[2, 5, 2, 1])[0]
    ep_cloison = rng.choices([70, 100], weights=[1, 4])[0]
    for essai in range(1, ESSAIS_MAX + 1):
        try:
            fab = _essayer(graine, type_, hsp, ep_ext, ep_cloison, rng)
        except Rate:
            continue
        fab.essais = essai
        return fab
    raise RuntimeError(f"graine {graine} : aucun logement habitable en {ESSAIS_MAX} essais")


def _essayer(graine: int, type_: str, hsp: int, ep_ext: int, ep_cloison: int, rng: random.Random) -> Fabrication:
    pieces = programme(type_, rng)
    rng.shuffle(pieces)
    total = sum(p.cible for p in pieces) * 1.03  # un peu de place pour les cloisons
    forme = "L" if type_ != "T1" and rng.random() < 0.35 else "rectangle"
    allongement = rng.uniform(1.0, 1.8)
    cloisons: list[Mur] = []
    if forme == "rectangle":
        w = _arrondi((total * 1e6 * allongement) ** 0.5)
        h = _arrondi(total * 1e6 / w)
        encoche = None
        if not _decouper(Rect(0, 0, w, h), pieces, ep_cloison, rng, cloisons, [BUDGET_COUPES]):
            raise Rate("pas de découpage habitable")
    else:
        # L = un grand rectangle (ouest, toute la profondeur) + une aile (est, au-dessus de l'encoche).
        fa, fb = rng.uniform(0.25, 0.5), rng.uniform(0.25, 0.55)  # taille de l'encoche, en part des côtés
        aire_cadre = total * 1e6 / (1 - fa * fb)
        w = _arrondi((aire_cadre * allongement) ** 0.5)
        h = _arrondi(aire_cadre / w)
        a, b = _arrondi(fa * w), _arrondi(fb * h)
        encoche = (a, b)
        ouest = Rect(0, 0, w - a, h)
        aile = Rect(w - a + ep_cloison, b, w, h)
        part_aile = aile.largeur * aile.hauteur / (ouest.largeur * ouest.hauteur + aile.largeur * aile.hauteur)
        # On donne à l'aile les dernières pièces de la liste, jusqu'à atteindre à peu près sa part de surface.
        k, cumul = len(pieces), 0.0
        while k > 1 and cumul + pieces[k - 1].cible / 2 < part_aile * sum(p.cible for p in pieces):
            k -= 1
            cumul += pieces[k].cible
        if k == len(pieces):
            raise Rate("aile vide")
        cloisons.append(Mur(True, w - a + ep_cloison / 2, b, h, ep_cloison))
        budget = [BUDGET_COUPES]
        if not (_decouper(ouest, pieces[:k], ep_cloison, rng, cloisons, budget)
                and _decouper(aile, pieces[k:], ep_cloison, rng, cloisons, budget)):
            raise Rate("pas de découpage habitable")
    murs = _murs_exterieurs(_contour(w, h, encoche), ep_ext)
    fab = Fabrication(graine, type_, forme, hsp, ep_ext, ep_cloison, pieces, murs + cloisons)
    _percer(fab, cloisons, rng)
    _transformer(fab, w, h, rng.randrange(8))
    return fab


def _transformer(fab: Fabrication, w: int, h: int, n: int) -> None:
    """Tourne et/ou retourne le logement (8 possibilités), pour que l'encoche, l'entrée… soient partout.

    n : bit 1 = échange de x et y (quart de tour combiné à un retournement), bit 2 = miroir est-ouest,
    bit 4 = miroir nord-sud. Le repère reste : origine au coin sud-ouest du cadre intérieur.
    """
    echange, mx, my = bool(n & 1), bool(n & 2), bool(n & 4)
    if echange:
        w, h = h, w

    def tx(x: float) -> float:
        return w - x if mx else x

    def ty(y: float) -> float:
        return h - y if my else y

    for p in fab.pieces:
        r = p.rect
        if echange:
            r = Rect(r.y0, r.x0, r.y1, r.x1)
        xs, ys = sorted((tx(r.x0), tx(r.x1))), sorted((ty(r.y0), ty(r.y1)))
        p.rect = Rect(xs[0], ys[0], xs[1], ys[1])

    retourne: dict[int, bool] = {}  # le mur a été retourné dans sa longueur
    axe_retourne: dict[int, bool] = {}  # ses deux côtés ont été échangés
    for m in fab.murs:
        if echange:
            m.vertical = not m.vertical
        miroir = mx if m.vertical else my  # retourne l'axe du mur
        miroir_long = my if m.vertical else mx  # retourne le mur dans sa longueur
        f_axe = tx if m.vertical else ty
        f_long = ty if m.vertical else tx
        m.axe = f_axe(m.axe)
        if miroir:
            m.dehors = -m.dehors
        m.debut, m.fin = sorted((f_long(m.debut), f_long(m.fin)))
        retourne[id(m)], axe_retourne[id(m)] = miroir_long, miroir
    for o in fab.ouvertures:
        m = o.mur
        f_long = ty if m.vertical else tx
        u0, u1 = sorted((f_long(o.u0), f_long(o.u1)))
        if retourne[id(m)]:
            o.charniere = 1 - o.charniere
        if axe_retourne[id(m)]:
            o.vers = -o.vers
        o.u0, o.u1 = u0, u1


# ---------- Écriture du logement.json ----------


def _m(v: float) -> float:
    return round(v / 1000, 3) + 0.0


def _nommer(fab: Fabrication) -> None:
    """Donne un identifiant lisible à chaque mur et à chaque ouverture."""
    noms = {(True, 1): "M_est", (True, -1): "M_ouest", (False, 1): "M_nord", (False, -1): "M_sud"}
    compte: dict[str, int] = {}
    for m in fab.murs:
        base = noms[(m.vertical, m.dehors)] if m.dehors else "C"
        compte[base] = compte.get(base, 0) + 1
    vus: dict[str, int] = {}
    for m in fab.murs:
        base = noms[(m.vertical, m.dehors)] if m.dehors else "C"
        vus[base] = vus.get(base, 0) + 1
        m.id = base if compte[base] == 1 and base != "C" else f"{base}{vus[base]}"
    lettres = {"porte": "P", "porte_fenetre": "PF", "fenetre": "F"}
    vus = {}
    for o in fab.ouvertures:
        lettre = lettres[o.type]
        vus[lettre] = vus.get(lettre, 0) + 1
        o.id = f"{lettre}{vus[lettre]}"


def en_logement(fab: Fabrication) -> dict:
    """Le contenu du logement.json (format logement/0.1) : le corrigé du plan."""
    _nommer(fab)
    source = "fabrique"

    def point(m: Mur, u: float) -> list[float]:
        return [_m(m.axe), _m(u)] if m.vertical else [_m(u), _m(m.axe)]

    ids_pieces: dict[str, int] = {}
    pieces = []
    for p in sorted(fab.pieces, key=lambda p: (-p.rect.y1, p.rect.x0)):  # du nord-ouest au sud-est
        base = _identifiant(p.nom)
        ids_pieces[base] = ids_pieces.get(base, 0) + 1
        r = p.rect
        pieces.append({
            "id": base if ids_pieces[base] == 1 else f"{base}_{ids_pieces[base]}",
            "nom": p.nom,
            "contour": [[_m(r.x0), _m(r.y0)], [_m(r.x1), _m(r.y0)], [_m(r.x1), _m(r.y1)], [_m(r.x0), _m(r.y1)]],
            "surface": round(r.largeur * r.hauteur / 1e6, 2),
            "statut": "mesure",
            "source": source,
        })
    return {
        "schema": "logement/0.1",
        "projet_id": f"FABRIQUE-{fab.graine:05d}",
        "unites": "m",
        "hauteur_sous_plafond": _m(fab.hsp),
        "murs": [
            {"id": m.id, "debut": point(m, m.debut), "fin": point(m, m.fin), "epaisseur": _m(m.epaisseur),
             "statut": "mesure", "source": source}
            for m in fab.murs
        ],
        "ouvertures": [
            {"id": o.id, "type": o.type, "mur": o.mur.id, "position": _m(o.u0 - o.mur.debut),
             "largeur": _m(o.u1 - o.u0), "hauteur": _m(o.hauteur), "allege": _m(o.allege),
             "statut": "mesure", "source": source}
            for o in fab.ouvertures
        ],
        "pieces": pieces,
    }


def _identifiant(nom: str) -> str:
    """« Salle d'eau » → « salle_d_eau »."""
    return "_".join(sans_accents(nom).lower().replace("'", " ").replace("+", " ").split())


def battants(fab: Fabrication) -> dict[str, tuple[int, int]]:
    """Pour le dessin : de quel côté s'ouvre chaque porte (vers) et où est sa charnière."""
    return {o.id: (o.vers, o.charniere) for o in fab.ouvertures if o.type != "fenetre"}


def fiche(fab: Fabrication, style: dict) -> dict:
    """Ce qu'il faut savoir d'un plan fabriqué pour analyser les résultats du banc (pas lu par le banc)."""
    return {
        "graine": fab.graine,
        "type": fab.type,
        "forme": fab.forme,
        "surface_m2": fab.surface,
        "pieces": len(fab.pieces),
        "ouvertures": len(fab.ouvertures),
        "epaisseur_murs_exterieurs_m": _m(fab.ep_ext),
        "epaisseur_cloisons_m": _m(fab.ep_cloison),
        "hauteur_sous_plafond_m": _m(fab.hsp),
        "essais": fab.essais,
        "dessin": style,
    }


def fabriquer_dossier(graine: int, dossier: Path) -> dict:
    """Fabrique un logement et écrit logement.json, plan.png et fiche.json dans le dossier."""
    import cv2
    from moteur.images import ecrire_image

    from moteur.dessin_plan import dessiner_plan, style_au_hasard

    fab = fabriquer(graine)
    logement = en_logement(fab)
    Logement.model_validate(logement)  # le corrigé respecte les règles du format
    style = style_au_hasard(random.Random(f"style-{graine}"))
    titre = f"Plan de synthèse n°{graine} — {fab.type} de {fab.surface:.0f} m²".replace(".", ",")
    image = dessiner_plan(logement, style, titre=titre, battants=battants(fab))
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "logement.json").write_text(json.dumps(logement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ecrire_image(str(dossier / "plan.png"), image)
    f = fiche(fab, style.en_dict())
    (dossier / "fiche.json").write_text(json.dumps(f, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f


def main() -> None:
    parser = argparse.ArgumentParser(description="Invente des logements et dessine leurs plans, avec leur corrigé.")
    parser.add_argument("nombre", type=int, help="combien de plans fabriquer")
    parser.add_argument("dossier", nargs="?", default="sorties/fabrique", help="où les écrire (par défaut : sorties/fabrique)")
    parser.add_argument("--depart", type=int, default=1, help="première graine (par défaut : 1)")
    args = parser.parse_args()

    dossier = Path(args.dossier)
    debut = time.perf_counter()
    types: dict[str, int] = {}
    for graine in range(args.depart, args.depart + args.nombre):
        try:
            f = fabriquer_dossier(graine, dossier / f"plan-{graine:05d}")
        except RuntimeError as erreur:
            print(f"✗ {erreur}")
            continue
        types[f["type"]] = types.get(f["type"], 0) + 1
        print(f"✓ plan-{graine:05d} : {f['type']} {f['forme']}, {f['surface_m2']:.2f} m², "
              f"{f['pieces']} pièces, {f['ouvertures']} ouvertures".replace(".", ","))
    if not types:
        sys.exit("Échec : aucun plan fabriqué")
    resume = ", ".join(f"{n} {t}" for t, n in sorted(types.items()))
    print(f"\n{sum(types.values())} plans fabriqués ({resume}) en {time.perf_counter() - debut:.0f} s → {dossier}")
    print(f"Pour les noter : uv run python -m moteur.banc_essai {dossier} --rapport {dossier}/rapport.json")


if __name__ == "__main__":
    main()
