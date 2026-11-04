"""Transforme un logement en « plan de construction » : une liste de briques.

Une brique est un volume simple : un contour vu de dessus (un polygone),
monté entre une altitude basse et une altitude haute. Si les deux altitudes
sont égales, la brique est une simple surface (un sol ou un plafond).

Ce module ne dépend pas de Blender : tous les calculs se testent seuls.
Blender n'a ensuite qu'à poser les briques (voir moteur/blender/poser_briques.py).

Ce que la version 0.1 sait faire :
- les murs, découpés autour des ouvertures (morceaux pleins, allèges sous les
  fenêtres, linteaux au-dessus des portes et fenêtres) ;
- les angles entre deux murs perpendiculaires, fermés proprement ;
- (A3) les angles quelconques (pans coupés, arrondis en segments) : coupe d'onglet,
  chaque mur s'arrête sur la ligne qui joint les croisements de leurs faces ;
- un sol et un plafond par pièce, plus un seuil au sol sous chaque porte.

Ce qu'elle refuse (avec un message clair) : deux ouvertures qui se
chevauchent, plus de deux murs qui se rejoignent au même point.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from moteur.logement import Logement, Mur, Ouverture

VERSION_PLAN = "construction/0.1"
PRESQUE_ALIGNES = 0.9995  # deux murs à moins de ~1,8° l'un de l'autre sont considérés comme alignés
RECOUVREMENT_TOLERE = 0.01  # m : au-delà, deux ouvertures se chevauchent vraiment et le plan doit être corrigé

# En dessous de cette distance (en mètres), deux points sont considérés égaux.
PRECISION = 1e-6

Point = tuple[float, float]


@dataclass(frozen=True)
class Brique:
    id: str
    categorie: Literal["mur", "sol", "plafond", "menuiserie"]
    element: str  # identifiant de l'élément du logement d'où vient la brique
    contour: list[Point]  # sens inverse des aiguilles d'une montre, vu de dessus
    z_bas: float
    z_haut: float
    materiau: str = ""  # choisi à l'habillage (voir moteur/habillage.py)


def plan_de_construction(logement: Logement) -> dict:
    """Le plan complet, prêt à être écrit en JSON et lu par Blender."""
    return {
        "schema": VERSION_PLAN,
        "projet_id": logement.projet_id,
        "briques": [asdict(b) for b in calculer_briques(logement)],
    }


def calculer_briques(logement: Logement) -> list[Brique]:
    briques: list[Brique] = []
    ajustements = _ajustements_aux_angles(logement.murs)
    ouvertures_par_mur: dict[str, list[Ouverture]] = {}
    for o in logement.ouvertures:
        ouvertures_par_mur.setdefault(o.mur, []).append(o)

    for mur in logement.murs:
        debut, fin = ajustements[mur.id]
        briques += _briques_du_mur(
            mur,
            hauteur=mur.hauteur or logement.hauteur_sous_plafond,
            t_debut=(-debut[0], -debut[1]),
            t_fin=(mur.longueur + fin[0], mur.longueur + fin[1]),
            ouvertures=ouvertures_par_mur.get(mur.id, []),
        )

    hsp = logement.hauteur_sous_plafond
    for p in logement.pieces:
        contour = _sens_direct([_arrondi(pt) for pt in p.contour])
        briques.append(Brique(f"sol__{p.id}", "sol", p.id, contour, 0.0, 0.0))
        briques.append(Brique(f"plafond__{p.id}", "plafond", p.id, contour, hsp, hsp))

    murs = {m.id: m for m in logement.murs}
    for o in logement.ouvertures:
        if o.allege == 0:
            contour = _rectangle(murs[o.mur], o.position, o.position + o.largeur)
            briques.append(Brique(f"seuil__{o.id}", "sol", o.id, contour, 0.0, 0.0))

    return briques


Ajustement = tuple[tuple[float, float], tuple[float, float]]


def _ajustements_aux_angles(murs: list[Mur]) -> dict[str, Ajustement]:
    """De combien rallonger (positif) ou raccourcir (négatif) chaque bout de mur.

    Pour chaque mur : (début, fin), et pour chaque bout deux valeurs, une par face
    (face droite n = -e/2, face gauche n = +e/2 ; « gauche » en allant du début à la fin).

    Angle droit : deux murs dessinés par leur axe se rejoignent au milieu de leur
    épaisseur ; sans correction, il manquerait un petit carré dans l'angle. On rallonge
    donc le premier mur de la demi-épaisseur du second, et on raccourcit le second de
    la demi-épaisseur du premier (mêmes valeurs pour les deux faces).

    Autre angle (A3 : pans coupés, arrondis) : coupe d'onglet. Les faces intérieures des
    deux murs se croisent en un point, les faces extérieures en un autre ; chaque mur
    s'arrête sur la ligne qui joint ces deux points. Ils se touchent sans se chevaucher.
    """
    ajustements = {m.id: [[0.0, 0.0], [0.0, 0.0]] for m in murs}
    bouts: list[tuple[Mur, int, Point]] = []
    for m in murs:
        bouts += [(m, 0, m.debut), (m, 1, m.fin)]

    deja_vus: set[int] = set()
    for i, (mur_a, bout_a, point) in enumerate(bouts):
        if i in deja_vus:
            continue
        groupe = [
            j for j, (_, _, autre) in enumerate(bouts)
            if j != i and math.dist(point, autre) < PRECISION
        ]
        if not groupe:
            continue
        if len(groupe) > 1:
            noms = ", ".join(sorted({bouts[k][0].id for k in [i, *groupe]}))
            raise ValueError(f"plus de deux murs se rejoignent en {point} : {noms} (non géré)")
        j = groupe[0]
        deja_vus |= {i, j}
        mur_b, bout_b, _ = bouts[j]
        produit = abs(_scalaire(_direction(mur_a), _direction(mur_b)))
        if produit > PRESQUE_ALIGNES:
            continue  # murs dans le prolongement l'un de l'autre : rien à corriger (un onglet sur un angle minuscule exploserait)
        if produit > PRECISION:
            for (m, b), (n_, _) in (((mur_a, bout_a), (mur_b, bout_b)), ((mur_b, bout_b), (mur_a, bout_a))):
                ajustements[m.id][b] = list(_onglet(m, b, n_, _))
            continue
        for k in (0, 1):
            ajustements[mur_a.id][bout_a][k] += mur_b.epaisseur / 2
            ajustements[mur_b.id][bout_b][k] -= mur_a.epaisseur / 2

    return {k: ((v[0][0], v[0][1]), (v[1][0], v[1][1])) for k, v in ajustements.items()}


def _onglet(mur: Mur, bout: int, autre: Mur, bout_autre: int) -> tuple[float, float]:
    """Coupe d'onglet du bout `bout` de `mur` contre `autre` : l'ajustement de chaque face."""
    u, v = _direction(mur), _direction(autre)
    g, h = (-u[1], u[0]), (-v[1], v[0])
    # directions qui partent du point de rencontre, le long de chaque mur
    d_mur = (u[0], u[1]) if bout == 0 else (-u[0], -u[1])
    d_autre = (v[0], v[1]) if bout_autre == 0 else (-v[0], -v[1])
    # face intérieure = celle tournée vers l'autre mur
    signe_mur = 1.0 if _scalaire(g, d_autre) > 0 else -1.0
    signe_autre = 1.0 if _scalaire(h, d_mur) > 0 else -1.0
    sortie = []
    for n in (-mur.epaisseur / 2, mur.epaisseur / 2):
        interieure = (n > 0) == (signe_mur > 0)
        m = autre.epaisseur / 2 * (signe_autre if interieure else -signe_autre)
        # mur.debut + g*n + u*t = autre.debut + h*m + v*s  →  t
        px = autre.debut[0] + h[0] * m - mur.debut[0] - g[0] * n
        py = autre.debut[1] + h[1] * m - mur.debut[1] - g[1] * n
        det = u[0] * (-v[1]) - u[1] * (-v[0])
        t = (px * (-v[1]) - py * (-v[0])) / det
        sortie.append(-t if bout == 0 else t - mur.longueur)
    return sortie[0], sortie[1]


def _briques_du_mur(
    mur: Mur, hauteur: float, t_debut: tuple[float, float], t_fin: tuple[float, float],
    ouvertures: list[Ouverture],
) -> list[Brique]:
    """Découpe un mur autour de ses ouvertures.

    `t` est la distance le long de l'axe du mur, mesurée depuis son début ; les bouts
    t_debut et t_fin donnent une valeur par face (droite, gauche) : coupe d'onglet.
    """
    briques: list[Brique] = []
    if not ouvertures:
        # Mur sans ouverture : une seule brique. Un tout petit mur entre deux onglets ne doit pas
        # avoir de faces qui se croisent.
        t_fin = (max(t_fin[0], t_debut[0]), max(t_fin[1], t_debut[1]))
        if max(t_fin[0] - t_debut[0], t_fin[1] - t_debut[1]) <= PRECISION:
            return []
        return [Brique(f"{mur.id}__plein_1", "mur", mur.id, _rectangle(mur, t_debut, t_fin), 0.0, hauteur)]
    curseur = t_debut
    numero = 0
    for o in sorted(ouvertures, key=lambda o: o.position):
        gauche, droite = o.position, o.position + o.largeur
        if gauche < max(curseur) - RECOUVREMENT_TOLERE:
            raise ValueError(
                f"l'ouverture {o.id} chevauche une autre ouverture ou l'angle du mur {mur.id}"
            )
        gauche = max(gauche, max(curseur))  # arrondi d'une lecture : deux ouvertures qui se touchent à quelques mm près
        if gauche - min(curseur) > PRECISION:
            numero += 1
            briques.append(
                Brique(f"{mur.id}__plein_{numero}", "mur", mur.id,
                       _rectangle(mur, curseur, gauche), 0.0, hauteur)
            )
        if o.allege > PRECISION:
            briques.append(
                Brique(f"{mur.id}__allege_{o.id}", "mur", mur.id,
                       _rectangle(mur, gauche, droite), 0.0, o.allege)
            )
        haut = o.allege + o.hauteur
        if hauteur - haut > PRECISION:
            briques.append(
                Brique(f"{mur.id}__linteau_{o.id}", "mur", mur.id,
                       _rectangle(mur, gauche, droite), haut, hauteur)
            )
        curseur = (droite, droite)

    reste = min(t_fin) - max(curseur)
    if reste < -PRECISION:
        raise ValueError(f"une ouverture du mur {mur.id} empiète sur son angle")
    if max(t_fin) - min(curseur) > PRECISION:
        numero += 1
        briques.append(
            Brique(f"{mur.id}__plein_{numero}", "mur", mur.id,
                   _rectangle(mur, curseur, t_fin), 0.0, hauteur)
        )
    return briques


def _rectangle(
    mur: Mur, t1: float | tuple[float, float], t2: float | tuple[float, float],
    n1: float | None = None, n2: float | None = None
) -> list[Point]:
    """Le rectangle occupé par le mur entre les distances t1 et t2 de son axe.

    Dans l'épaisseur, il va de n1 à n2 (distances à l'axe, comptées vers la
    gauche du mur) ; par défaut, toute l'épaisseur. Les menuiseries s'en
    servent pour se loger au milieu du mur. t1 et t2 peuvent donner une valeur
    par face (n1, n2) : le contour est alors un trapèze (coupe d'onglet).
    """
    t1a, t1b = t1 if isinstance(t1, tuple) else (t1, t1)
    t2a, t2b = t2 if isinstance(t2, tuple) else (t2, t2)
    if n1 is None or n2 is None:
        n1, n2 = -mur.epaisseur / 2, mur.epaisseur / 2
    ux, uy = _direction(mur)
    gx, gy = -uy, ux  # vers la gauche du mur
    x0, y0 = mur.debut
    coins = [
        (x0 + ux * t + gx * n, y0 + uy * t + gy * n)
        for t, n in ((t1a, n1), (t2a, n1), (t2b, n2), (t1b, n2))
    ]
    return _sens_direct([_arrondi(c) for c in coins])


def _direction(mur: Mur) -> Point:
    (x1, y1), (x2, y2) = mur.debut, mur.fin
    return ((x2 - x1) / mur.longueur, (y2 - y1) / mur.longueur)


def _scalaire(u: Point, v: Point) -> float:
    return u[0] * v[0] + u[1] * v[1]


def _aire_signee(contour: list[Point]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        total += x1 * y2 - x2 * y1
    return total / 2


def _sens_direct(contour: list[Point]) -> list[Point]:
    """Remet le contour dans le sens inverse des aiguilles d'une montre."""
    return contour if _aire_signee(contour) > 0 else contour[::-1]


def _arrondi(point: Point) -> Point:
    # Au micromètre : efface les minuscules erreurs de calcul (ex. 5.1000000000000005).
    return (round(point[0], 6) + 0.0, round(point[1], 6) + 0.0)
