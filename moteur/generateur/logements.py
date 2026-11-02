"""Inventer la géométrie d'un logement : pièces, murs, ouvertures, niveaux.

Ce module est dérivé de moteur/fabrique.py (étape 5b), qu'il ne modifie pas, et va plus loin :

- studios, chambres indépendantes, T1 à T5, duplex à deux niveaux reliés par un escalier ;
- rectangles, formes en L et formes irrégulières (deux encoches : U, T, Z…) ;
- couloirs, entrées, placards, buanderies, bureaux, cuisines ouvertes ou séparées ;
- murs extérieurs, murs porteurs intérieurs simulés (entre les zones) et cloisons ;
- toutes les distributions dans reglages.py.

La méthode reste celle de la fabrique :

1. un « programme » : la liste des pièces et la surface visée de chacune ;
2. une enveloppe (le contour intérieur) découpée en « zones » rectangulaires séparées par
   des murs ; pour un duplex, l'escalier est placé au niveau 0 et les cloisons qui l'isolent sont
   rejouées à l'étage, dont elles délimitent les zones (même escalier aux deux niveaux) ;
3. chaque zone est partagée entre ses pièces par des cloisons droites (découpage « en
   guillotine » : chaque cloison traverse tout le morceau qu'elle coupe) ;
4. on vérifie que c'est habitable (tailles courantes, chaque pièce desservie, une fenêtre
   par pièce de vie) ; sinon on retire (avec d'autres tirages) ;
5. on perce la porte d'entrée, les portes intérieures et les fenêtres ;
6. on tourne ou retourne le tout (8 possibilités), pour que l'entrée, l'encoche, l'escalier…
   se trouvent partout.

Tout est calculé en millimètres entiers et dépend d'une seule graine : la même graine
redonne exactement le même logement.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from moteur.generateur.reglages import Reglages
from moteur.habillage import sans_accents


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

    @property
    def surface(self) -> int:
        return self.largeur * self.hauteur


@dataclass
class Piece:
    nom: str
    sorte: str
    cible: float  # surface visée, en m²
    rect: Rect | None = None
    id: str = ""
    # Étape A3 (--biais) : contour réel quand un angle de la pièce est coupé (pan coupé, angle arrondi) ;
    # None = le rectangle. `interdits` : zones où rien ne se pose (le coin coupé).
    contour: list[tuple[float, float]] | None = None
    interdits: list[Rect] = field(default_factory=list)


@dataclass
class Mur:
    """Un mur droit, par son axe : `vertical` (de sud en nord) ou horizontal (d'ouest en est).

    `axe` : x (mur vertical) ou y (mur horizontal) de l'axe ; `debut` < `fin` : étendue le long du mur.
    `dehors` : pour un mur extérieur, le côté de l'extérieur (+1 ou -1) ; 0 pour un mur intérieur.
    `porteur` : mur porteur simulé (les murs extérieurs et les murs entre zones) ou simple cloison.
    """

    vertical: bool
    axe: float
    debut: float
    fin: float
    epaisseur: int
    dehors: int = 0
    porteur: bool = False
    id: str = ""
    coupe_debut: bool = False  # A3 : ce bout s'arrête sur un mur en biais (pas de rallonge d'angle)
    coupe_fin: bool = False


@dataclass
class MurLibre:
    """Étape A3 : un mur extérieur en biais (pan coupé) ou arrondi, à la place d'un angle du logement.

    `axe` : la ligne au milieu du mur (2 points pour un pan coupé, une suite de points pour un arrondi) ;
    `polygone` : la surface exacte occupée par le mur (raccords avec les deux murs voisins compris).
    """

    forme: str  # biais, arrondi
    axe: list[tuple[float, float]]
    polygone: list[tuple[float, float]]
    epaisseur: int
    dehors: int = 1
    porteur: bool = True
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
    sous_type: str = ""  # porte_entree, porte_interieure, baie, fenetre, porte_fenetre
    vers: int = 0  # côté où s'ouvre le battant (+1 ou -1 le long de x ou y) ; 0 pour une fenêtre
    charniere: int = 0  # 0 : charnière du côté de u0 ; 1 : du côté de u1
    id: str = ""


@dataclass
class Niveau:
    """Un niveau du logement : son contour intérieur, ses pièces, ses murs et ses ouvertures."""

    index: int
    coins: list[tuple[int, int]]  # contour intérieur, sens inverse des aiguilles d'une montre
    pieces: list[Piece]
    murs: list[Mur]
    ouvertures: list[Ouverture] = field(default_factory=list)
    z_sol: int = 0  # altitude du sol fini, en mm
    hsp: int = 2500
    murs_libres: list[MurLibre] = field(default_factory=list)  # A3 : murs en biais / arrondis

    @property
    def cadre(self) -> Rect:
        xs = [c[0] for c in self.coins]
        ys = [c[1] for c in self.coins]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    @property
    def surface(self) -> float:
        return round(sum(surface_piece(p) for p in self.pieces) / 1e6, 2)


def contour_piece(p: Piece) -> list[tuple[float, float]]:
    """Le contour de la pièce, en mm (sens direct) : son rectangle, ou son contour coupé (A3)."""
    if p.contour:
        return list(p.contour)
    r = p.rect
    return [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]


def aire(poly: list[tuple[float, float]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))) / 2


def surface_piece(p: Piece) -> float:
    """La surface de la pièce en mm² (celle du rectangle s'il n'y a pas d'angle coupé : rien ne change)."""
    return aire(p.contour) if p.contour else p.rect.surface


@dataclass
class LogementGenere:
    graine: int
    type: str
    forme: str
    niveaux: list[Niveau]
    ep_ext: int
    ep_cloison: int
    ep_porteur: int
    hsp: int
    plancher: int = 0  # épaisseur du plancher intermédiaire (duplex)
    essais: int = 1

    @property
    def duplex(self) -> bool:
        return len(self.niveaux) > 1

    @property
    def surface(self) -> float:
        return round(sum(n.surface for n in self.niveaux), 2)

    @property
    def pieces(self) -> list[Piece]:
        return [p for n in self.niveaux for p in n.pieces]

    @property
    def murs(self) -> list[Mur]:
        return [m for n in self.niveaux for m in n.murs]

    @property
    def ouvertures(self) -> list[Ouverture]:
        return [o for n in self.niveaux for o in n.ouvertures]

    @property
    def famille(self) -> str:
        """La famille géométrique : ce qui fait que deux logements se ressemblent dans les grandes lignes."""
        return f"{self.type}-{self.forme}-{'duplex' if self.duplex else 'plain-pied'}-{len(self.pieces)}p"


class Rate(Exception):
    """Ce tirage ne donne pas un logement habitable : on recommence."""


# ============================================================ 1. Le programme


NOMS = {
    "sejour": ["Séjour", "Séjour", "Salon", "Pièce de vie"],
    "sejour_cuisine": ["Séjour + cuisine", "Séjour / cuisine", "Pièce de vie", "Salon-cuisine"],
    "principale": ["Pièce principale", "Studio", "Séjour / chambre", "Pièce de vie"],
    "cuisine": ["Cuisine"],
    "chambre": ["Chambre"],
    "sdb": ["Salle de bains", "Salle de bain"],
    "sde": ["Salle d'eau", "Salle d'eau", "Douche"],
    "wc": ["WC", "WC", "Toilettes"],
    "entree": ["Entrée", "Entrée", "Hall"],
    "degagement": ["Dégagement", "Couloir", "Couloir", "Dgt"],
    "placard": ["Placard", "Placard", "Rangement", "Dressing", "Cellier"],
    "buanderie": ["Buanderie", "Cellier", "Lingerie"],
    "bureau": ["Bureau", "Bureau", "Chambre / bureau"],
    "escalier": ["Escalier", "Escalier", "Esc."],
}


class Fabricant:
    """Tout ce qu'il faut pour inventer un logement : la graine (le hasard) et les réglages."""

    def __init__(self, graine: int, reglages: Reglages | None = None):
        self.graine = graine
        self.r = reglages or Reglages()
        self.rng = random.Random(graine)

    # ---- tirages ----

    def choix(self, table: dict) -> object:
        cles = list(table)
        return self.rng.choices(cles, weights=[table[k] for k in cles])[0]

    def proba(self, table: dict, type_: str) -> bool:
        return self.rng.random() < table[type_]

    def surface(self, sorte: str, bonus: float = 0.0) -> float:
        mini, maxi = self.r.SURFACES[sorte]
        return round(self.rng.uniform(mini + bonus, maxi + bonus), 1)

    def nom(self, cle: str) -> str:
        return self.rng.choice(NOMS[cle])

    # ---- le programme ----

    def programme(self, type_: str) -> list[Piece]:
        """La liste des pièces d'un logement de ce type, avec une surface visée pour chacune."""
        r, rng = self.r, self.rng
        chambres = r.CHAMBRES[type_]
        pieces: list[Piece] = []

        def ajouter(cle: str, sorte: str, bonus: float = 0.0, nom: str | None = None) -> None:
            pieces.append(Piece(nom or self.nom(cle), sorte, self.surface(sorte, bonus)))

        if type_ == "studio":
            ajouter("principale", "principale")
        elif type_ == "chambre":
            pieces.append(Piece("Chambre", "chambre", round(rng.uniform(11, 17), 1)))
        elif self.proba(r.CUISINE_SEPAREE, type_):
            ajouter("sejour", "sejour", 1.5 * chambres)
            ajouter("cuisine", "cuisine", 0.5 * chambres)
        else:
            ajouter("sejour_cuisine", "sejour", 3.0 + 2.5 * chambres)
        for i in range(chambres):
            nom = "Chambre" if chambres == 1 else f"Chambre {i + 1}"
            ajouter("chambre", "chambre", -1.0 if i else 0.0, nom=nom)
        ajouter("sdb" if rng.random() < 0.55 else "sde", "sdb" if rng.random() < 0.55 else "sde", 0.3 * chambres)
        if self.proba(r.DEUXIEME_SDB, type_):
            ajouter("sde", "sde")
        if self.proba(r.WC_SEPARE, type_):
            ajouter("wc", "wc")
        if self.proba(r.ENTREE, type_):
            ajouter("entree", "entree", 0.4 * chambres)
        if self.proba(r.DEGAGEMENT, type_):
            ajouter("degagement", "degagement", 0.5 * chambres)
            if self.proba(r.DEUXIEME_DEGAGEMENT, type_):
                ajouter("degagement", "degagement")
        if self.proba(r.PLACARD, type_):
            n = 1 + (rng.random() < 0.3 and chambres >= 2)
            for i in range(n):
                ajouter("placard", "placard", nom=None if n == 1 else f"Placard {i + 1}")
        if self.proba(r.BUANDERIE, type_):
            ajouter("buanderie", "buanderie")
        if self.proba(r.BUREAU, type_):
            ajouter("bureau", "bureau")
        # Les noms doivent être uniques dans le logement (ex. deux « Placard », deux salles d'eau).
        vus: dict[str, int] = {}
        for p in pieces:
            vus[p.nom] = vus.get(p.nom, 0) + 1
        comptes: dict[str, int] = {}
        for p in pieces:
            if vus[p.nom] > 1:
                comptes[p.nom] = comptes.get(p.nom, 0) + 1
                p.nom = f"{p.nom} {comptes[p.nom]}"
        return pieces

    def programme_duplex(self, type_: str) -> tuple[list[Piece], list[Piece]]:
        """Le programme réparti sur deux niveaux : en bas la vie, en haut les chambres ; un escalier à chaque niveau."""
        pieces = self.programme(type_)
        bas_sortes = {"sejour", "cuisine", "entree", "wc", "buanderie"}
        bas = [p for p in pieces if p.sorte in bas_sortes]
        haut = [p for p in pieces if p.sorte not in bas_sortes]
        # Un placard peut aller en bas ; une chambre peut rester en bas s'il y en a plusieurs.
        for p in list(haut):
            if p.sorte == "placard" and self.rng.random() < 0.4:
                haut.remove(p)
                bas.append(p)
        chambres = [p for p in haut if p.sorte == "chambre"]
        if len(chambres) >= 3 and self.rng.random() < 0.4:
            haut.remove(chambres[-1])
            bas.append(chambres[-1])
        if not any(p.sorte in ("degagement",) for p in haut) and len(haut) >= 3 and self.rng.random() < 0.7:
            haut.append(Piece(self.nom("degagement"), "degagement", self.surface("degagement")))
        if len(haut) < 2:
            raise Rate("pas assez de pièces à l'étage")
        # Les deux niveaux ont le même contour : on déplace des pièces jusqu'à ce que leurs surfaces soient proches.
        deplacables = {"chambre", "bureau", "placard", "sde", "wc", "buanderie", "degagement"}
        for _ in range(4):
            s_bas, s_haut = sum(p.cible for p in bas), sum(p.cible for p in haut)
            if max(s_bas, s_haut) / min(s_bas, s_haut) <= 1.3:
                break
            grand, petit = (haut, bas) if s_haut > s_bas else (bas, haut)
            candidats = [p for p in grand if p.sorte in deplacables and len(grand) > 2]
            if not candidats:
                break
            ecart = (sum(p.cible for p in grand) - sum(p.cible for p in petit)) / 2
            p = min(candidats, key=lambda p: abs(p.cible - ecart))
            grand.remove(p)
            petit.append(p)
        # S'il manque encore de la surface à un niveau, on lui ajoute des pièces (un bureau, un couloir, un placard…).
        complements = ["bureau", "degagement", "placard", "sde", "buanderie"]
        for _ in range(3):
            s_bas, s_haut = sum(p.cible for p in bas), sum(p.cible for p in haut)
            if max(s_bas, s_haut) <= 1.3 * min(s_bas, s_haut):
                break
            petit = haut if s_haut < s_bas else bas
            sortes = {p.sorte for p in petit}
            choix = [c for c in complements if c not in sortes]
            if not choix:
                break
            sorte = choix[0]
            petit.append(Piece(self.nom(sorte), sorte, self.surface(sorte)))
        for niveau in (bas, haut):
            niveau.append(Piece(self.nom("escalier"), "escalier", self.surface("escalier")))
        return bas, haut

    # ============================================================ 2. L'enveloppe

    def contour(self, forme: str, w: int, h: int, encoches: dict[str, tuple[int, int]]) -> list[tuple[int, int]]:
        """Les coins intérieurs du logement, dans le sens inverse des aiguilles d'une montre.

        `encoches` : par coin (« SO », « SE », « NE », « NO »), le coin manquant (a de large, b de haut).
        """
        pts: list[tuple[int, int]] = []
        so, se, ne, no = (encoches.get(c) for c in ("SO", "SE", "NE", "NO"))
        pts += [(0, so[1]), (so[0], so[1]), (so[0], 0)] if so else [(0, 0)]
        pts += [(w - se[0], 0), (w - se[0], se[1]), (w, se[1])] if se else [(w, 0)]
        pts += [(w, h - ne[1]), (w - ne[0], h - ne[1]), (w - ne[0], h)] if ne else [(w, h)]
        pts += [(no[0], h), (no[0], h - no[1]), (0, h - no[1])] if no else [(0, h)]
        return pts

    def zones(self, w: int, h: int, encoches: dict[str, tuple[int, int]], ep: int) -> tuple[list[Rect], list[Mur]]:
        """Découpe l'enveloppe en bandes verticales rectangulaires, séparées par des murs d'épaisseur `ep`.

        Le mur entre deux bandes est pris sur la bande la moins haute (celle que l'encoche raccourcit) :
        il va ainsi de bout en bout de cette bande, sans laisser de morceau d'enveloppe sans affectation.
        """
        xs = {0, w}
        for coin, (a, b) in encoches.items():
            xs.add(a if coin in ("SO", "NO") else w - a)
        bornes = sorted(xs)
        bandes = []
        for i in range(len(bornes) - 1):
            xa, xb = bornes[i], bornes[i + 1]
            milieu = (xa + xb) / 2
            y0 = max([b for coin, (a, b) in encoches.items() if coin in ("SO", "SE")
                      and (milieu < a if coin == "SO" else milieu > w - a)], default=0)
            y1 = h - max([b for coin, (a, b) in encoches.items() if coin in ("NO", "NE")
                          and (milieu < a if coin == "NO" else milieu > w - a)], default=0)
            bandes.append(Rect(xa, y0, xb, y1))
        murs = []
        for i in range(1, len(bandes)):
            g, d = bandes[i - 1], bandes[i]
            y0, y1 = max(g.y0, d.y0), min(g.y1, d.y1)
            if y1 - y0 < 2 * self.r.PAS:
                raise Rate("zones mal reliées")
            if d.hauteur <= g.hauteur:  # le mur empiète sur la bande de droite
                murs.append(Mur(True, d.x0 + ep / 2, y0, y1, ep, porteur=True))
                d.x0 += ep
            else:
                murs.append(Mur(True, g.x1 - ep / 2, y0, y1, ep, porteur=True))
                g.x1 -= ep
        for z in bandes:
            if z.largeur <= 0 or z.hauteur <= 0:
                raise Rate("zone vide")
        return bandes, murs

    # ============================================================ 3. Le découpage

    def ordonner(self, pieces: list[Piece]) -> None:
        """Mélange les pièces, en gardant souvent des groupes qui vont ensemble.

        Sept fois sur dix, les petites pièces de service restent côte à côte (salle d'eau, WC,
        placards) ; pour les grands logements, la partie « jour » (séjour, cuisine, entrée) et la
        partie « nuit » (chambres, salles de bains, couloir) forment deux groupes, comme dans un vrai
        appartement. Le découpage en guillotine sépare alors d'abord les deux parties.
        """
        rng = self.rng
        rng.shuffle(pieces)
        if rng.random() < 0.3:
            return
        service = ("sdb", "sde", "wc", "placard", "buanderie")
        if len(pieces) >= 8 and rng.random() < 0.8:
            jour = [p for p in pieces if p.sorte in ("sejour", "principale", "cuisine", "entree", "wc", "buanderie")]
            nuit = [p for p in pieces if p not in jour]
            for groupe in (jour, nuit):  # dans chaque partie, les pièces de service groupées
                petites = [p for p in groupe if p.sorte in service]
                grandes = [p for p in groupe if p not in petites]
                k = rng.randint(0, len(grandes))
                groupe[:] = grandes[:k] + petites + grandes[k:]
            pieces[:] = jour + nuit if rng.random() < 0.5 else nuit + jour
            return
        petites = [p for p in pieces if p.sorte in service + ("entree", "degagement")]
        if len(petites) < 2:
            return
        reste = [p for p in pieces if p not in petites]
        k = rng.randint(0, len(reste))
        pieces[:] = reste[:k] + petites + reste[k:]

    def repartir(self, pieces: list[Piece], zones: list[Rect]) -> list[list[Piece]]:
        """Donne à chaque zone des pièces dont les surfaces visées remplissent à peu près sa surface.

        C'est un rangement « au mieux » : les grandes pièces d'abord, chacune dans la zone qui a le
        plus de place restante, puis on vérifie que chaque zone est remplie entre 70 et 140 %.
        On recommence avec un autre ordre jusqu'à y arriver (ou on abandonne ce tirage).
        """
        if len(pieces) < len(zones):
            raise Rate("zone sans pièce")
        aires = [z.surface / 1e6 for z in zones]
        total = sum(p.cible for p in pieces)
        echelle = sum(aires) / total  # les surfaces visées sont ramenées à la surface réelle disponible
        for _ in range(40):
            ordre = sorted(pieces, key=lambda p: -p.cible * self.rng.uniform(0.7, 1.3))
            restes = list(aires)
            parts: list[list[Piece]] = [[] for _ in zones]
            for p in ordre:
                vides = [i for i in range(len(zones)) if not parts[i]]
                # Tant qu'une zone est vide, on la sert avec une pièce qui lui convient.
                if vides and len(pieces) - sum(len(x) for x in parts) <= len(vides):
                    i = max(vides, key=lambda i: restes[i])
                else:
                    i = max(range(len(zones)), key=lambda i: restes[i])
                parts[i].append(p)
                restes[i] -= p.cible * echelle
            if all(parts) and all(0.7 <= sum(p.cible * echelle for p in part) / aire <= 1.4 for part, aire in zip(parts, aires)):
                return parts
        raise Rate("zone mal remplie")

    def couloir_central(self, pieces: list[Piece], zones: list[Rect], murs: list[Mur], ep: int
                        ) -> tuple[list[Rect], list[list[Piece]]]:
        """Répartit les pièces entre les zones ; pour un grand logement, un couloir sépare d'abord la partie
        jour (séjour, cuisine, entrée) de la partie nuit (chambres, salles de bains) dans la plus grande zone.

        Le couloir est le dégagement du programme, posé en bande sur toute la profondeur de la zone :
        les chambres s'ouvrent dessus, comme dans un vrai appartement. Renvoie (zones à découper,
        pièces de chaque zone) ; la pièce du couloir a déjà son rectangle.
        """
        r, rng = self.r, self.rng
        couloirs = [p for p in pieces if p.sorte == "degagement"]
        jour = [p for p in pieces if p.sorte in ("sejour", "principale", "cuisine", "entree", "wc", "buanderie")]
        nuit = [p for p in pieces if p not in jour and p.sorte != "degagement"]
        if len(pieces) < 7 or not couloirs or len(nuit) < 3 or len(jour) < 2 or rng.random() < 0.2:
            return zones, self.repartir(pieces, zones)
        couloir = couloirs[0]
        reste_couloirs = couloirs[1:]
        z = max(zones, key=lambda z: z.surface)
        autres = [x for x in zones if x is not z]
        largeur = _arrondi(rng.uniform(950, 1250), r.PAS)
        total = sum(p.cible for p in jour + nuit + reste_couloirs)
        part_jour = sum(p.cible for p in jour) / total
        long_ = max(z.largeur, z.hauteur) - largeur - 2 * ep
        l_jour = _arrondi(part_jour * long_ * rng.uniform(0.85, 1.15), r.PAS)
        if l_jour < r.COTE_MIN["sejour"] or long_ - l_jour < r.COTE_MIN["chambre"]:
            raise Rate("pas de place pour le couloir")
        if z.largeur >= z.hauteur:  # couloir vertical, jour à l'ouest, nuit à l'est (le tout est tourné ensuite)
            xa, xb = z.x0 + l_jour, z.x0 + l_jour + ep + largeur
            z_jour, z_couloir, z_nuit = Rect(z.x0, z.y0, xa, z.y1), Rect(xa + ep, z.y0, xb, z.y1), Rect(xb + ep, z.y0, z.x1, z.y1)
            murs += [Mur(True, xa + ep / 2, z.y0, z.y1, ep), Mur(True, xb + ep / 2, z.y0, z.y1, ep)]
        else:
            ya, yb = z.y0 + l_jour, z.y0 + l_jour + ep + largeur
            z_jour, z_couloir, z_nuit = Rect(z.x0, z.y0, z.x1, ya), Rect(z.x0, ya + ep, z.x1, yb), Rect(z.x0, yb + ep, z.x1, z.y1)
            murs += [Mur(False, ya + ep / 2, z.x0, z.x1, ep), Mur(False, yb + ep / 2, z.x0, z.x1, ep)]
        couloir.rect = z_couloir
        couloir.cible = round(z_couloir.surface / 1e6, 1)
        if min(z_couloir.largeur, z_couloir.hauteur) < r.COTE_MIN["degagement"]:
            raise Rate("couloir trop étroit")
        # Les autres zones de l'enveloppe (aile d'un L…) vont avec la partie jour ou la partie nuit, selon la place.
        zones_jour, zones_nuit = [z_jour], [z_nuit]
        for x in autres:
            (zones_jour if rng.random() < 0.5 else zones_nuit).append(x)
        parts = self.repartir(jour, zones_jour) + self.repartir(nuit + reste_couloirs, zones_nuit)
        return zones_jour + zones_nuit, parts

    def decouper(self, rect: Rect, pieces: list[Piece], ep: int, cloisons: list[Mur], budget: list[int],
                 journal: list[tuple[Rect, Mur, Rect, Rect]] | None = None) -> bool:
        """Découpe le rectangle entre les pièces, proportionnellement à leurs surfaces visées.

        On essaie les coupes possibles dans un ordre au hasard, et on revient en arrière quand
        une pièce sort trop petite ou trop allongée. `budget` limite le nombre de coupes essayées.
        Renvoie False si aucun découpage ne convient (les cloisons ajoutées sont alors retirées).
        `journal`, s'il est donné, garde chaque coupe retenue : (rectangle coupé, cloison, moitié a, moitié b).
        """
        r, rng = self.r, self.rng
        if len(pieces) == 1:
            pieces[0].rect = rect
            return self.habitable(pieces[0])
        if min(rect.largeur, rect.hauteur) < min(r.COTE_MIN[p.sorte] for p in pieces):
            return False
        ecarts = (1.0, 0.85, 1.15, 0.7, 1.3)
        coupes = [(k, vertical, ecart) for k in range(1, len(pieces)) for vertical in (True, False) for ecart in ecarts]
        rng.shuffle(coupes)
        coupes.sort(key=lambda c: (c[1] != (rect.largeur >= rect.hauteur), abs(c[2] - 1)))
        for k, vertical, ecart in coupes:
            if budget[0] <= 0:
                return False
            budget[0] -= 1
            a, b = pieces[:k], pieces[k:]
            part = min(0.95, ecart * sum(p.cible for p in a) / sum(p.cible for p in pieces))
            longueur = (rect.largeur if vertical else rect.hauteur) - ep
            l1 = _arrondi(part * longueur, r.PAS)
            if l1 < r.PAS or l1 > longueur - r.PAS:
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
            nj = len(journal) if journal is not None else 0
            if journal is not None:
                journal.append((rect, cloison, r1, r2))
            if self.decouper(r1, a, ep, cloisons, budget, journal) and self.decouper(r2, b, ep, cloisons, budget, journal):
                return True
            del cloisons[n:]
            if journal is not None:
                del journal[nj:]
        return False

    def habitable(self, p: Piece) -> bool:
        r = self.r
        rect = p.rect
        petit, grand = sorted((rect.largeur, rect.hauteur))
        if petit < r.COTE_MIN[p.sorte] or grand / petit > r.ALLONGEMENT_MAX[p.sorte]:
            return False
        if grand > r.COTE_MAX.get(p.sorte, 10 ** 9):
            return False
        surface = rect.surface / 1e6
        bas, haut = r.ECART_SURFACE
        # Les toutes petites pièces (placard, WC) ont droit à un peu plus de marge : 0,8 m² de plus que visé.
        return r.SURFACE_MIN.get(p.sorte, 0) <= surface and bas * p.cible <= surface <= max(haut * p.cible, p.cible + 0.8)

    # ============================================================ 4 et 5. Vérifier et percer

    def percer(self, niveau: Niveau, interieurs: list[Mur], depart: Piece, porte_entree: bool,
               distribution: set[str]) -> None:
        """Portes intérieures (un arbre de passages depuis `depart`), porte d'entrée, fenêtres."""
        r, rng = self.r, self.rng
        pieces = niveau.pieces
        occupe: dict[int, list[tuple[float, float]]] = {}
        voisins = {}
        for i, p in enumerate(pieces):
            for j, q in enumerate(pieces):
                if i != j and (passage := _passage(p, q, interieurs)) is not None:
                    voisins[(i, j)] = passage
        i0 = pieces.index(depart)
        atteintes = {i0}
        a_traiter = [i0]
        while a_traiter:  # d'abord les pièces de distribution, en partant de l'entrée
            i = a_traiter.pop(0)
            for j, q in enumerate(pieces):
                if j in atteintes or (i, j) not in voisins or q.sorte not in distribution:
                    continue
                if self.porte(niveau, pieces[i], q, voisins[(i, j)], occupe):
                    atteintes.add(j)
                    a_traiter.append(j)
        for j, q in enumerate(pieces):  # puis chaque autre pièce, depuis une pièce de distribution voisine
            if j in atteintes:
                continue
            if q.sorte in r.DEPUIS_N_IMPORTE_OU:
                hubs = [i for i in atteintes if (i, j) in voisins]
            else:
                hubs = [i for i in atteintes if (i, j) in voisins and pieces[i].sorte in distribution]
            # On préfère entrer dans une chambre ou une salle d'eau par l'entrée ou un couloir plutôt que par le séjour.
            hubs.sort(key=lambda i: (pieces[i].sorte in ("sejour", "principale")) != (q.sorte == "cuisine"))
            if not any(self.porte(niveau, pieces[i], q, voisins[(i, j)], occupe) for i in hubs):
                raise Rate(f"{q.nom} n'est pas desservie")
            atteintes.add(j)
        # Les placards et buanderies desservis par une pièce qui n'était pas encore atteinte : on les a
        # tous traités dans l'ordre des pièces, donc une pièce atteinte plus tard peut avoir été ignorée
        # comme hub ; la boucle ci-dessus garantit malgré tout que chaque pièce a une porte depuis une
        # pièce déjà atteinte, donc le logement est connexe.

        if porte_entree:
            faces = _faces_exterieures(depart, niveau.murs)
            rng.shuffle(faces)
            largeur = rng.choice(r.PORTE_ENTREE)
            for mur, a, b in faces:
                if (place := self.placer(occupe, mur, a, b, largeur, r.MARGE_PORTE)) is not None:
                    niveau.ouvertures.append(Ouverture("porte", mur, *place, 2040, 0, "porte_entree",
                                                       vers=-mur.dehors, charniere=rng.randint(0, 1)))
                    break
            else:
                raise Rate("pas de place pour la porte d'entrée")

        for p in pieces:
            faces = _faces_exterieures(p, niveau.murs)
            rng.shuffle(faces)
            posees = 0
            for type_, sous_type, largeur in self.fenetres_voulues(p, niveau.hsp):
                for mur, a, b in faces:
                    if (place := self.placer(occupe, mur, a, b, largeur, r.MARGE_OUVERTURE)) is not None:
                        niveau.ouvertures.append(self.fenetre(type_, sous_type, mur, place, niveau.hsp))
                        posees += 1
                        break
            if p.sorte in r.AVEC_FENETRE and posees == 0:
                raise Rate(f"{p.nom} n'a pas de fenêtre")

        for p in pieces:  # un couloir qui ne mène qu'à une seule pièce ne sert à rien
            if p.sorte == "degagement" and sum(_borde(o, p) for o in niveau.ouvertures if o.type == "porte") < 2:
                raise Rate(f"{p.nom} ne dessert rien")

    def placer(self, occupe: dict, mur: Mur, a: float, b: float, largeur: int, marge: int) -> tuple[float, float] | None:
        """Une place libre de cette largeur entre a et b sur le mur, loin des autres ouvertures (ou None)."""
        debut, fin = a + marge, b - marge - largeur
        if fin < debut:
            return None
        for _ in range(20):
            u0 = round(self.rng.uniform(debut, fin) / 10) * 10  # au centimètre
            u0 = min(max(u0, debut), fin)
            if all(u0 + largeur + self.r.ECART_OUVERTURES <= v0 or v1 + self.r.ECART_OUVERTURES <= u0
                   for v0, v1 in occupe.get(id(mur), [])):
                occupe.setdefault(id(mur), []).append((u0, u0 + largeur))
                return u0, u0 + largeur
        return None

    def porte(self, niveau: Niveau, p: Piece, q: Piece, passage: tuple[Mur, float, float, int], occupe: dict) -> bool:
        """Perce une porte entre p et q dans leur mur commun ; elle s'ouvre vers q si le battant y tient."""
        cloison, a, b, cote_q = passage
        sortes = {p.sorte, q.sorte}
        if sortes & {"wc", "sdb", "sde", "placard", "buanderie"}:
            largeur = self.rng.choice(self.r.LARGEURS_PORTES["petite"])
        elif sortes <= {"sejour", "principale", "entree", "degagement", "escalier"}:
            largeur = self.rng.choice(self.r.LARGEURS_PORTES["grande"])
        else:
            largeur = self.rng.choice(self.r.LARGEURS_PORTES["normale"])
        place = self.placer(occupe, cloison, a, b, largeur, self.r.MARGE_PORTE)
        if place is None:
            return False
        vers = cote_q if _battant_tient(q, cloison, largeur) else -cote_q
        if not _battant_tient(q if vers == cote_q else p, cloison, largeur):
            occupe[id(cloison)].pop()
            return False
        niveau.ouvertures.append(Ouverture("porte", cloison, *place, 2040, 0, "porte_interieure",
                                           vers=vers, charniere=self.rng.randint(0, 1)))
        return True

    def fenetres_voulues(self, p: Piece, hsp: int) -> list[tuple[str, str, int]]:
        rng = self.rng
        pf = hsp >= 2300  # une porte-fenêtre de 2,15 m demande assez de hauteur
        if p.sorte in ("sejour", "principale"):
            if pf and rng.random() < self.r.BAIE:
                premiere = ("porte_fenetre", "baie", rng.choice([2000, 2400, 2800, 3200]))
            elif pf and rng.random() < 0.5:
                premiere = ("porte_fenetre", "porte_fenetre", rng.choice([1400, 1600, 1800]))
            else:
                premiere = ("fenetre", "fenetre", rng.choice([1200, 1400, 1600, 1800]))
            return [premiere] + ([("fenetre", "fenetre", rng.choice([1000, 1200, 1400]))] if rng.random() < 0.5 else [])
        if p.sorte == "chambre":
            if pf and rng.random() < 0.2:
                return [("porte_fenetre", "porte_fenetre", rng.choice([1200, 1400]))]
            return [("fenetre", "fenetre", rng.choice([900, 1000, 1200, 1400]))]
        if p.sorte in ("cuisine", "bureau"):
            return [("fenetre", "fenetre", rng.choice([800, 1000, 1200]))]
        if p.sorte in {"sdb", "sde", "wc", "buanderie"} and rng.random() < 0.5:
            return [("fenetre", "fenetre", rng.choice([500, 600, 800]))]
        if p.sorte in {"escalier", "degagement"} and rng.random() < 0.3:
            return [("fenetre", "fenetre", rng.choice([500, 600]))]
        if p.sorte == "entree" and rng.random() < 0.1:
            return [("fenetre", "fenetre", 600)]
        return []

    def fenetre(self, type_: str, sous_type: str, mur: Mur, place: tuple[float, float], hsp: int) -> Ouverture:
        rng = self.rng
        if type_ == "porte_fenetre":
            return Ouverture(type_, mur, *place, 2150, 0, sous_type, vers=-mur.dehors, charniere=rng.randint(0, 1))
        largeur = place[1] - place[0]
        hauteur = 600 if largeur <= 600 else rng.choice([1150, 1250, 1350, 1450])
        haut = min(hsp - 150, rng.choice([2150, 2200, 2250]))
        return Ouverture(type_, mur, *place, hauteur, haut - hauteur, sous_type)

    # ============================================================ Le tout

    def generer(self) -> LogementGenere:
        """Invente un logement habitable (toujours le même pour la même graine)."""
        r, rng = self.r, self.rng
        type_ = str(self.choix(r.TYPES))
        duplex = self.proba(r.DUPLEX, type_)
        hsp = int(self.choix(r.HAUTEUR_SOUS_PLAFOND))
        ep_ext = int(self.choix(r.EPAISSEUR_EXTERIEURE))
        ep_cloison = int(self.choix(r.EPAISSEUR_CLOISON))
        ep_porteur = int(self.choix(r.EPAISSEUR_PORTEUR)) if rng.random() < r.PORTEUR_ENTRE_ZONES else ep_cloison
        forme = str(self.choix(r.FORMES))
        if type_ in ("studio", "chambre"):
            forme = "rectangle" if forme == "irregulier" or rng.random() < 0.7 else "L"
        if duplex and forme == "irregulier":
            forme = "L" if rng.random() < 0.5 else "rectangle"
        plancher = _arrondi(rng.uniform(*r.PLANCHER), r.PAS) if duplex else 0
        for essai in range(1, r.ESSAIS_MAX + 1):
            try:
                niveaux = self.essayer(type_, duplex, forme, hsp, ep_ext, ep_cloison, ep_porteur, plancher)
            except Rate:
                continue
            log = LogementGenere(self.graine, type_, forme, niveaux, ep_ext, ep_cloison, ep_porteur, hsp, plancher, essai)
            _nommer(log)
            return log
        raise RuntimeError(f"graine {self.graine} : aucun logement habitable en {r.ESSAIS_MAX} essais")

    def essayer(self, type_: str, duplex: bool, forme: str, hsp: int, ep_ext: int, ep_cloison: int,
                ep_porteur: int, plancher: int) -> list[Niveau]:
        r, rng = self.r, self.rng
        if duplex:
            programmes = list(self.programme_duplex(type_))
        else:
            programmes = [self.programme(type_)]
        for pieces in programmes:
            self.ordonner(pieces)
        # Tous les niveaux ont le même contour : la surface d'un niveau est celle du programme le plus grand,
        # et les pièces des autres niveaux grandissent un peu pour le remplir.
        sommes = [sum(p.cible for p in pieces) for pieces in programmes]
        total = max(sommes) * 1.03  # un peu de place pour les cloisons
        for pieces, somme in zip(programmes, sommes):
            manque = max(sommes) - somme
            if manque <= 0:
                continue
            if manque > 0.6 * somme:
                raise Rate("niveaux trop déséquilibrés")
            # Le niveau le moins chargé grandit par ses grandes pièces (un plus grand séjour, pas un plus grand WC).
            grandes = [p for p in pieces if p.sorte in ("sejour", "principale", "chambre", "cuisine", "bureau", "entree")]
            if not grandes:
                raise Rate("niveaux trop déséquilibrés")
            base = sum(p.cible for p in grandes)
            for p in grandes:
                p.cible = round(p.cible * (1 + manque / base), 1)

        allongement = rng.uniform(*r.ALLONGEMENT_CADRE)
        encoches: dict[str, tuple[int, int]] = {}
        coins_possibles = ["SO", "SE", "NE", "NO"]
        n_encoches = {"rectangle": 0, "L": 1, "irregulier": 2}[forme]
        for coin in rng.sample(coins_possibles, n_encoches):
            encoches[coin] = (rng.uniform(*r.ENCOCHE), rng.uniform(*r.ENCOCHE))  # en parts, converties plus bas
        aire_manquante = sum(a * b for a, b in encoches.values())
        if aire_manquante > 0.45:
            raise Rate("encoches trop grandes")
        aire_cadre = total * 1e6 / (1 - aire_manquante)
        w = _arrondi((aire_cadre * allongement) ** 0.5, r.PAS)
        h = _arrondi(aire_cadre / w, r.PAS)
        encoches_mm = {c: (_arrondi(fa * w, r.PAS), _arrondi(fb * h, r.PAS)) for c, (fa, fb) in encoches.items()}
        # Deux encoches d'un même côté ne doivent pas se toucher ni laisser une bande trop fine.
        for (c1, (a1, b1)), (c2, (a2, b2)) in [(x, y) for x in encoches_mm.items() for y in encoches_mm.items() if x[0] < y[0]]:
            meme_bord_vertical = (c1 in ("SO", "NO")) == (c2 in ("SO", "NO"))  # même côté ouest ou est
            meme_bord_horizontal = (c1 in ("SO", "SE")) == (c2 in ("SO", "SE"))  # même côté sud ou nord
            if meme_bord_horizontal and a1 + a2 > w - r.COTE_MIN["sejour"]:
                raise Rate("encoches qui se touchent")
            if meme_bord_vertical and b1 + b2 > h - r.COTE_MIN["sejour"]:
                raise Rate("encoches qui se touchent")
            if not meme_bord_vertical and not meme_bord_horizontal:  # coins opposés : il faut un passage entre les deux
                if a1 + a2 > w - r.COTE_MIN["degagement"] and b1 + b2 > h - r.COTE_MIN["degagement"]:
                    raise Rate("encoches qui se touchent")
        coins = self.contour(forme, w, h, encoches_mm)
        zones, murs_zones = self.zones(w, h, encoches_mm, ep_porteur)
        murs_ext = _murs_exterieurs(coins, ep_ext)

        # Niveau 0 : l'escalier (s'il y en a un) est une pièce comme les autres, placée par le découpage.
        # Niveau 1 : on rejoue les coupes qui isolent l'escalier au niveau 0 ; les autres morceaux
        # deviennent les zones de l'étage. L'escalier est ainsi au même endroit aux deux niveaux,
        # et les murs qui l'entourent montent d'un niveau à l'autre (murs porteurs).
        niveaux: list[Niveau] = []
        zones_niveau, murs_niveau = zones, murs_zones
        escalier: Piece | None = None
        for index, pieces in enumerate(programmes):
            interieurs = [Mur(m.vertical, m.axe, m.debut, m.fin, m.epaisseur, porteur=m.porteur) for m in murs_niveau]
            a_placer = list(pieces)
            if index > 0:
                esc = next(p for p in pieces if p.sorte == "escalier")
                esc.rect, esc.cible = escalier.rect, escalier.cible
                a_placer.remove(esc)
            journal: list[tuple[Rect, Mur, Rect, Rect]] = []
            zones_a_decouper, parts = self.couloir_central(a_placer, zones_niveau, interieurs, ep_cloison)
            budget = [r.BUDGET_COUPES + 150 * len(a_placer)]
            for zone, part in zip(zones_a_decouper, parts):
                if not self.decouper(zone, part, ep_cloison, interieurs, budget, journal):
                    raise Rate("pas de découpage habitable")
            if index == 0 and duplex:
                escalier = next(p for p in pieces if p.sorte == "escalier")
                zones_niveau, montants = _zones_autour(escalier.rect, zones, journal)
                for m in montants:
                    m.porteur = True
                murs_niveau = murs_zones + montants
            niveau = Niveau(index, list(coins), pieces, _murs_copies(murs_ext) + interieurs,
                            z_sol=index * (hsp + plancher), hsp=hsp)
            if index == 0:
                depart = _piece_de_depart(pieces)
                distribution = r.DISTRIBUTION - {"escalier"}
            else:
                depart = next(p for p in pieces if p.sorte == "escalier")
                distribution = set(r.DISTRIBUTION)
            self.percer(niveau, interieurs, depart, porte_entree=(index == 0), distribution=distribution)
            niveaux.append(niveau)
        n = rng.randrange(8)
        for niveau in niveaux:
            _transformer(niveau, w, h, n)
        return niveaux


# ============================================================ Géométrie (fonctions pures)


def _arrondi(v: float, pas: int) -> int:
    return int(round(v / pas)) * pas


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
        murs.append(Mur(vertical, axes[i], min(avant, apres), max(avant, apres), ep, dehors, porteur=True))
    return murs


def _zones_autour(escalier: Rect, zones: list[Rect], journal: list[tuple[Rect, Mur, Rect, Rect]]) -> tuple[list[Rect], list[Mur]]:
    """Les zones de l'étage d'un duplex : ce qui reste quand on rejoue les coupes du niveau 0 qui isolent l'escalier.

    Renvoie (zones restantes, cloisons rejouées). Les zones qui ne contiennent pas l'escalier sont gardées telles quelles.
    """
    restantes = [z for z in zones if not _contient(z, escalier)]
    courant = next(z for z in zones if _contient(z, escalier))
    montants: list[Mur] = []
    while courant != escalier:
        coupe = next((c for c in journal if c[0] == courant), None)
        if coupe is None:
            raise Rate("escalier introuvable dans les coupes")
        _, cloison, r1, r2 = coupe
        montants.append(Mur(cloison.vertical, cloison.axe, cloison.debut, cloison.fin, cloison.epaisseur))
        dedans, dehors = (r1, r2) if _contient(r1, escalier) else (r2, r1)
        restantes.append(dehors)
        courant = dedans
    return restantes, montants


def _contient(zone: Rect, r: Rect) -> bool:
    return zone.x0 <= r.x0 and zone.y0 <= r.y0 and r.x1 <= zone.x1 and r.y1 <= zone.y1


def _murs_copies(murs: list[Mur]) -> list[Mur]:
    return [Mur(m.vertical, m.axe, m.debut, m.fin, m.epaisseur, m.dehors, m.porteur) for m in murs]


def _faces_exterieures(piece: Piece, murs: list[Mur]) -> list[tuple[Mur, float, float]]:
    """Les morceaux des murs extérieurs qui bordent la pièce : (mur, début, fin) le long du mur."""
    r = piece.rect
    faces = []
    for m in murs:
        if not m.dehors:
            continue
        e = m.epaisseur / 2
        face = m.axe - m.dehors * e
        # Le mur va d'axe à axe de ses voisins ; sa face intérieure utile s'arrête une demi-épaisseur avant.
        if m.vertical and face == (r.x1 if m.dehors > 0 else r.x0):
            a, b = max(r.y0, m.debut + e), min(r.y1, m.fin - e)
        elif not m.vertical and face == (r.y1 if m.dehors > 0 else r.y0):
            a, b = max(r.x0, m.debut + e), min(r.x1, m.fin - e)
        else:
            continue
        if b > a:
            faces.append((m, a, b))
    return faces


def _passage(p: Piece, q: Piece, murs: list[Mur]) -> tuple[Mur, float, float, int] | None:
    """Le mur commun à deux pièces voisines : (mur, début, fin du morceau commun, côté de q)."""
    a, b = p.rect, q.rect
    for c in murs:
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


def _battant_tient(piece: Piece, mur: Mur, largeur: int) -> bool:
    """Le battant d'une porte de cette largeur, ouverte vers la pièce, y tient-il ?"""
    profondeur = piece.rect.largeur if mur.vertical else piece.rect.hauteur
    return profondeur >= largeur + 50


def _borde(o: Ouverture, p: Piece) -> bool:
    """L'ouverture est-elle dans un mur de la pièce ?"""
    r, m = p.rect, o.mur
    e = m.epaisseur / 2
    if m.vertical:
        return m.axe in (r.x0 - e, r.x1 + e) and r.y0 <= o.u0 and o.u1 <= r.y1
    return m.axe in (r.y0 - e, r.y1 + e) and r.x0 <= o.u0 and o.u1 <= r.x1


def _piece_de_depart(pieces: list[Piece]) -> Piece:
    """La pièce par laquelle on entre : l'entrée, sinon le séjour, sinon la plus grande."""
    for sorte in ("entree", "sejour", "principale"):
        for p in pieces:
            if p.sorte == sorte:
                return p
    return max(pieces, key=lambda p: p.rect.surface)


def _transformer(niveau: Niveau, w: int, h: int, n: int) -> None:
    """Tourne et/ou retourne le niveau (8 possibilités). Le repère reste : origine au coin sud-ouest du cadre.

    n : bit 1 = échange de x et y, bit 2 = miroir est-ouest, bit 4 = miroir nord-sud.
    """
    echange, mx, my = bool(n & 1), bool(n & 2), bool(n & 4)
    if echange:
        w, h = h, w

    def tx(x: float) -> float:
        return w - x if mx else x

    def ty(y: float) -> float:
        return h - y if my else y

    for p in niveau.pieces:
        r = p.rect
        if echange:
            r = Rect(r.y0, r.x0, r.y1, r.x1)
        xs, ys = sorted((tx(r.x0), tx(r.x1))), sorted((ty(r.y0), ty(r.y1)))
        p.rect = Rect(int(xs[0]), int(ys[0]), int(xs[1]), int(ys[1]))
    coins = []
    for x, y in niveau.coins:
        if echange:
            x, y = y, x
        coins.append((int(tx(x)), int(ty(y))))
    # L'échange ou un seul miroir inverse le sens de parcours : on le remet dans le sens direct.
    if echange != (mx != my):
        coins.reverse()
    niveau.coins = coins

    retourne: dict[int, bool] = {}
    axe_retourne: dict[int, bool] = {}
    for m in niveau.murs:
        if echange:
            m.vertical = not m.vertical
        miroir = mx if m.vertical else my
        miroir_long = my if m.vertical else mx
        f_axe = tx if m.vertical else ty
        f_long = ty if m.vertical else tx
        m.axe = f_axe(m.axe)
        if miroir:
            m.dehors = -m.dehors
        m.debut, m.fin = sorted((f_long(m.debut), f_long(m.fin)))
        retourne[id(m)], axe_retourne[id(m)] = miroir_long, miroir
    for o in niveau.ouvertures:
        m = o.mur
        f_long = ty if m.vertical else tx
        u0, u1 = sorted((f_long(o.u0), f_long(o.u1)))
        if retourne[id(m)]:
            o.charniere = 1 - o.charniere
        if axe_retourne[id(m)]:
            o.vers = -o.vers
        o.u0, o.u1 = u0, u1


def _nommer(log: LogementGenere) -> None:
    """Donne un identifiant unique et lisible à chaque pièce, mur et ouverture du logement."""
    noms = {(True, 1): "M_est", (True, -1): "M_ouest", (False, 1): "M_nord", (False, -1): "M_sud"}
    lettres = {"porte": "P", "porte_fenetre": "PF", "fenetre": "F"}
    for niveau in log.niveaux:
        suffixe = "" if niveau.index == 0 else f"_n{niveau.index}"
        compte: dict[str, int] = {}
        for m in niveau.murs:
            base = noms[(m.vertical, m.dehors)] if m.dehors else ("MP" if m.porteur else "C")
            compte[base] = compte.get(base, 0) + 1
        vus: dict[str, int] = {}
        for m in niveau.murs:
            base = noms[(m.vertical, m.dehors)] if m.dehors else ("MP" if m.porteur else "C")
            vus[base] = vus.get(base, 0) + 1
            m.id = (base if compte[base] == 1 and m.dehors else f"{base}{vus[base]}") + suffixe
        vus = {}
        for o in niveau.ouvertures:
            lettre = lettres[o.type]
            vus[lettre] = vus.get(lettre, 0) + 1
            o.id = f"{lettre}{vus[lettre]}{suffixe}"
        vus = {}
        for p in sorted(niveau.pieces, key=lambda p: (-p.rect.y1, p.rect.x0)):  # du nord-ouest au sud-est
            base = identifiant(p.nom)
            vus[base] = vus.get(base, 0) + 1
            p.id = (base if vus[base] == 1 else f"{base}_{vus[base]}") + suffixe


def identifiant(nom: str) -> str:
    """« Salle d'eau » → « salle_d_eau »."""
    return "_".join(sans_accents(nom).lower().replace("'", " ").replace("+", " ").replace("/", " ").replace("-", " ").split())


# ============================================================ Écriture au format logement/0.1


def _m(v: float) -> float:
    return round(v / 1000, 3) + 0.0


def en_logement(log: LogementGenere, niveau: Niveau) -> dict:
    """Le contenu d'un logement.json (format logement/0.1) pour un niveau : lisible par tout le moteur existant."""
    source = "generateur"

    def point(m: Mur, u: float) -> list[float]:
        return [_m(m.axe), _m(u)] if m.vertical else [_m(u), _m(m.axe)]

    pieces = []
    for p in sorted(niveau.pieces, key=lambda p: (-p.rect.y1, p.rect.x0)):
        pieces.append({
            "id": p.id,
            "nom": p.nom,
            "contour": [[_m(x), _m(y)] for x, y in contour_piece(p)],
            "surface": round(surface_piece(p) / 1e6, 2),
            "statut": "mesure",
            "source": source,
        })
    return {
        "schema": "logement/0.1",
        "projet_id": f"SYNTHESE-{log.graine:06d}" + (f"-N{niveau.index}" if log.duplex else ""),
        "unites": "m",
        "hauteur_sous_plafond": _m(niveau.hsp),
        "murs": [
            {"id": m.id, "debut": point(m, m.debut), "fin": point(m, m.fin), "epaisseur": _m(m.epaisseur),
             "statut": "mesure", "source": source}
            for m in niveau.murs
        ] + [
            # A3 : un mur en biais = 1 segment ; un mur arrondi = une suite de petits segments droits.
            {"id": f"{m.id}-{k}" if len(m.axe) > 2 else m.id, "debut": [_m(a[0]), _m(a[1])], "fin": [_m(b[0]), _m(b[1])],
             "epaisseur": _m(m.epaisseur), "statut": "mesure", "source": source}
            for m in niveau.murs_libres for k, (a, b) in enumerate(zip(m.axe, m.axe[1:]))
        ],
        "ouvertures": [
            {"id": o.id, "type": o.type, "mur": o.mur.id, "position": _m(o.u0 - o.mur.debut),
             "largeur": _m(o.u1 - o.u0), "hauteur": _m(o.hauteur), "allege": _m(o.allege),
             "statut": "mesure", "source": source}
            for o in niveau.ouvertures
        ],
        "pieces": pieces,
    }


def battants(niveau: Niveau) -> dict[str, tuple[int, int]]:
    """Pour le dessin : de quel côté s'ouvre chaque porte (vers) et où est sa charnière."""
    return {o.id: (o.vers, o.charniere) for o in niveau.ouvertures if o.type != "fenetre"}


def generer(graine: int, reglages: Reglages | None = None) -> LogementGenere:
    """Invente le logement de cette graine."""
    return Fabricant(graine, reglages).generer()
