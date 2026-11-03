"""Étape A3 : des murs en biais et des angles arrondis (option --biais du générateur).

Le générateur dessine des logements faits de rectangles : tous les murs sont horizontaux ou verticaux.
Or beaucoup de vrais plans ont des **pans coupés** (un angle du logement remplacé par un mur en biais,
à 45° ou entre 30° et 60°) et des **angles arrondis** (un quart de cercle). Ce module part d'un logement
déjà inventé et valide, et remplace quelques angles extérieurs « saillants » par l'un ou l'autre :

- le contour intérieur du niveau (coins) et celui de la pièce qui occupe l'angle sont recoupés ;
- les deux murs extérieurs qui formaient l'angle sont raccourcis jusqu'au nouveau mur ;
- le nouveau mur (MurLibre) porte la surface exacte qu'il occupe (raccords compris) et sa ligne d'axe
  (2 points en biais, une suite de points pour l'arrondi) ;
- rien n'est posé dans le coin coupé (meubles) et aucune ouverture n'est touchée : un angle n'est coupé
  que s'il n'y a ni porte ni fenêtre dans la partie supprimée des deux murs.

Un duplex garde le même contour aux deux niveaux : un angle n'est coupé que s'il peut l'être à tous les
niveaux. Tout dépend d'un tirage à part (« biais-<graine> ») : sans --biais, rien ne change.
"""
from __future__ import annotations

import math
import random

from moteur.generateur.logements import LogementGenere, Mur, MurLibre, Niveau, Piece, Rect, contour_piece

Point = tuple[float, float]

COTE_MIN, COTE_MAX = 700, 2200  # longueur coupée le long de chaque mur, en mm (pan coupé)
RAYON_MIN, RAYON_MAX = 800, 2500  # rayon intérieur d'un angle arrondi, en mm
RESTE_MIN = 700  # ce qui doit rester de mur droit dans la pièce, après la coupe
MARGE_OUVERTURE = 150  # distance minimale entre la coupe et une porte ou une fenêtre
PAS_ARC_DEG = 7.5  # un arrondi est dessiné par segments de 7,5° (12 segments par quart de cercle)


def _add(p: Point, q: Point, k: float = 1.0) -> Point:
    return (p[0] + k * q[0], p[1] + k * q[1])


def _inter(p: Point, d: Point, q: Point, e: Point) -> Point:
    """Intersection des droites p + t·d et q + s·e."""
    det = d[0] * (-e[1]) - d[1] * (-e[0])
    t = ((q[0] - p[0]) * (-e[1]) - (q[1] - p[1]) * (-e[0])) / det
    return (p[0] + t * d[0], p[1] + t * d[1])


def _unite(p: Point, q: Point) -> Point:
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n)


def angles_saillants(coins: list[Point]) -> list[int]:
    """Les indices des coins « saillants » (convexes) d'un contour parcouru dans le sens direct."""
    n = len(coins)
    res = []
    for i in range(n):
        a, c, b = coins[i - 1], coins[i], coins[(i + 1) % n]
        if (c[0] - a[0]) * (b[1] - c[1]) - (c[1] - a[1]) * (b[0] - c[0]) > 0:
            res.append(i)
    return res


def _mur_le_long(niveau: Niveau, c: Point, u: Point, n: Point, ep: int) -> Mur | None:
    """Le mur extérieur qui borde le côté du contour partant de c dans la direction u (dehors du côté n)."""
    vertical = abs(u[0]) < 0.5
    axe = (c[0] + n[0] * ep / 2) if vertical else (c[1] + n[1] * ep / 2)
    long_c = c[1] if vertical else c[0]
    for m in niveau.murs:
        if m.dehors and m.vertical == vertical and abs(m.axe - axe) < 1 and m.debut - ep <= long_c <= m.fin + ep:
            return m
    return None


def _piece_a_l_angle(niveau: Niveau, c: Point) -> Piece | None:
    for p in niveau.pieces:
        if any(abs(x - c[0]) < 1 and abs(y - c[1]) < 1 for x, y in contour_piece(p)):
            return p
    return None


def _ouvertures_libres(niveau: Niveau, m: Mur, lo: float, hi: float) -> bool:
    return all(o.u1 <= lo - MARGE_OUVERTURE or o.u0 >= hi + MARGE_OUVERTURE for o in niveau.ouvertures if o.mur is m)


def _remplacer(contour: list[Point], c: Point, nouveaux: list[Point]) -> list[Point] | None:
    for i, (x, y) in enumerate(contour):
        if abs(x - c[0]) < 1 and abs(y - c[1]) < 1:
            return contour[:i] + nouveaux + contour[i + 1:]
    return None


def _aire(poly: list[Point]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))) / 2


def _geometrie(c: Point, u_in: Point, u_out: Point, a: float, b: float, ep: int, forme: str):
    """Les points de la coupe, le polygone du nouveau mur, son axe et les nouveaux bouts des deux murs voisins.

    c : l'angle intérieur ; u_in : direction de c vers le coin précédent (le long du 1er mur) ;
    u_out : direction de c vers le coin suivant (le long du 2e mur). Le dehors du 1er mur est du côté
    −u_out, celui du 2e du côté −u_in.
    """
    n_in, n_out = (-u_out[0], -u_out[1]), (-u_in[0], -u_in[1])
    p1, p2 = _add(c, u_in, a), _add(c, u_out, b)
    b1, b2 = _add(p1, n_in, ep), _add(p2, n_out, ep)
    if forme == "biais":
        k = math.hypot(1 / a, 1 / b)
        nc = (-(u_in[0] / a + u_out[0] / b) / k, -(u_in[1] / a + u_out[1] / b) / k)  # normale vers le dehors
        d = (p2[0] - p1[0], p2[1] - p1[1])
        x1 = _inter(_add(p1, nc, ep), d, _add(c, n_in, ep), u_in)
        x2 = _inter(_add(p1, nc, ep), d, _add(c, n_out, ep), u_out)
        m1 = _inter(_add(p1, nc, ep / 2), d, _add(c, n_in, ep / 2), u_in)
        m2 = _inter(_add(p1, nc, ep / 2), d, _add(c, n_out, ep / 2), u_out)
        interieur = [p1, p2]
        polygone = [p1, b1, x1, x2, b2, p2]
        axe = [m1, m2]
        bout_in, bout_out = m1, m2  # les murs voisins s'arrêtent sur l'axe du mur en biais
    else:
        o = _add(_add(c, u_in, a), u_out, a)  # centre du quart de cercle (a = b = rayon)
        n = max(2, round(90 / PAS_ARC_DEG))

        def arc(r: float, de_p1: bool) -> list[Point]:
            pts = []
            for k in range(n + 1):
                t = math.radians(90 * k / n)
                t = math.radians(90) - t if de_p1 else t
                pts.append((o[0] - r * (math.cos(t) * u_out[0] + math.sin(t) * u_in[0]),
                            o[1] - r * (math.cos(t) * u_out[1] + math.sin(t) * u_in[1])))
            return pts  # t = 0 : o − r·u_out (du côté de p1) ; t = 90° : o − r·u_in (du côté de p2)

        interieur = arc(a, False)  # de p1 à p2
        interieur[0], interieur[-1] = p1, p2
        polygone = interieur + arc(a + ep, True)
        axe = arc(a + ep / 2, False)
        bout_in, bout_out = p1, p2  # l'arrondi se raccorde bout à bout aux murs droits
    return interieur, polygone, axe, bout_in, bout_out


def _raccourcir(m: Mur, c: Point, bout: Point, coupe: bool = True) -> None:
    """Le bout du mur m le plus proche de l'angle c s'arrête sur `bout` (sans rallonge d'angle)."""
    long_c = c[1] if m.vertical else c[0]
    long_b = bout[1] if m.vertical else bout[0]
    if abs(m.debut - long_c) < abs(m.fin - long_c):
        m.debut, m.coupe_debut = long_b, coupe
    else:
        m.fin, m.coupe_fin = long_b, coupe


def _essayer(log: LogementGenere, rng: random.Random, c: Point) -> dict | None:
    """Coupe (ou arrondit) l'angle c à tous les niveaux, si c'est possible partout ; sinon ne touche à rien."""
    coins0 = [tuple(map(float, q)) for q in log.niveaux[0].coins]
    i = next(k for k, q in enumerate(coins0) if q == c)
    nb = len(coins0)
    u_in, u_out = _unite(c, coins0[i - 1]), _unite(c, coins0[(i + 1) % nb])
    forme = "arrondi" if rng.random() < 0.4 else "biais"
    if forme == "arrondi":
        a = b = round(rng.uniform(RAYON_MIN, RAYON_MAX) / 10) * 10
    else:
        a = round(rng.uniform(COTE_MIN, COTE_MAX) / 10) * 10
        angle = 45.0 if rng.random() < 0.5 else rng.uniform(30.0, 60.0)
        b = max(COTE_MIN // 2, round(a * math.tan(math.radians(angle)) / 10) * 10)
    if a + RESTE_MIN > math.dist(c, coins0[i - 1]) or b + RESTE_MIN > math.dist(c, coins0[(i + 1) % nb]):
        return None
    ep = log.ep_ext
    interieur, polygone, axe, bout_in, bout_out = _geometrie(c, u_in, u_out, a, b, ep, forme)
    plan = []
    for niv in log.niveaux:  # tout vérifier avant de toucher à quoi que ce soit
        p = _piece_a_l_angle(niv, c)
        m_in = _mur_le_long(niv, c, u_in, (-u_out[0], -u_out[1]), ep)
        m_out = _mur_le_long(niv, c, u_out, (-u_in[0], -u_in[1]), ep)
        if p is None or m_in is None or m_out is None or p.sorte == "escalier":
            return None
        r = p.rect
        if a + RESTE_MIN > (r.largeur if abs(u_in[0]) > 0.5 else r.hauteur):
            return None
        if b + RESTE_MIN > (r.largeur if abs(u_out[0]) > 0.5 else r.hauteur):
            return None
        nouveau = _remplacer(contour_piece(p), c, interieur)
        if nouveau is None or _aire(nouveau) < 0.7 * _aire(contour_piece(p)):
            return None
        for m, u, d in ((m_in, u_in, a), (m_out, u_out, b)):
            lc = c[1] if m.vertical else c[0]
            ld = lc + d * (u[1] if m.vertical else u[0])
            if not _ouvertures_libres(niv, m, min(lc, ld), max(lc, ld)):
                return None
        plan.append((niv, p, m_in, m_out, nouveau))
    for niv, p, m_in, m_out, nouveau in plan:
        p.contour = nouveau
        xs, ys = [q[0] for q in (c, *interieur)], [q[1] for q in (c, *interieur)]
        p.interdits.append(Rect(int(min(xs)) - 100, int(min(ys)) - 100, int(max(xs)) + 100, int(max(ys)) + 100))
        _raccourcir(m_in, c, bout_in, coupe=forme == "biais")
        _raccourcir(m_out, c, bout_out, coupe=forme == "biais")
        suffixe = "" if niv.index == 0 else f"_n{niv.index}"
        ident = f"M_{forme}{len(niv.murs_libres) + 1}{suffixe}"
        niv.murs_libres.append(MurLibre(forme, list(axe), list(polygone), ep, id=ident))
        niv.coins = _remplacer([tuple(map(float, q)) for q in niv.coins], c, interieur)
    return {"forme": forme, "angle": [round(c[0]), round(c[1])], "a_mm": a, "b_mm": b,
            "angle_deg": round(math.degrees(math.atan2(b, a)), 1) if forme == "biais" else None,
            "bouts": [interieur[0], interieur[-1]]}


def couper_angles(log: LogementGenere, rng: random.Random) -> list[dict]:
    """Coupe ou arrondit 1 à 4 angles saillants du logement (tous niveaux pareils). Renvoie ce qui a été fait."""
    if any([tuple(map(float, c)) for c in n.coins] != [tuple(map(float, c)) for c in log.niveaux[0].coins]
           for n in log.niveaux[1:]):
        return []
    voulu = rng.choices((1, 2, 3, 4), weights=(55, 30, 10, 5))[0]
    faits: list[dict] = []
    bouts: set[tuple[int, int]] = set()
    while len(faits) < voulu:
        coins0 = [tuple(map(float, q)) for q in log.niveaux[0].coins]
        nb = len(coins0)
        candidats = []
        for i in angles_saillants(coins0):
            c, avant, apres = coins0[i], coins0[i - 1], coins0[(i + 1) % nb]
            droit = (avant[0] == c[0]) != (avant[1] == c[1]) and (apres[0] == c[0]) != (apres[1] == c[1])
            pres = {(round(q[0]), round(q[1])) for q in (c, avant, apres)} & bouts
            if droit and not pres:  # un angle droit d'origine, qui ne partage aucun mur avec une coupe
                candidats.append(c)
        rng.shuffle(candidats)
        for c in candidats:
            r = _essayer(log, rng, c)
            if r:
                bouts.update((round(q[0]), round(q[1])) for q in r.pop("bouts"))
                faits.append(r)
                break
        else:
            break
    return faits
