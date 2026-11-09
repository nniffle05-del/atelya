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
chevauchent, plus de deux murs qui se rejoignent au même point (sauf un « T » : voir B1).

B1, maquette sans fuite (08/11/2026). Une lecture (U-Net, Claude, vérité) n'est jamais exacte au millimètre ; la 3D, elle,
montre le moindre jour (fr-031 : filet de ciel entre le sol et le mur, filet de lumière sous le plafond, carrés noirs aux
jonctions). Donc :
- les sols et plafonds sont CALÉS sur les faces des murs : chaque côté d'une pièce qui longe la face d'un mur à moins de
  CALAGE_SOL (parallèle, en vis-à-vis) est posé exactement sur cette face (_caler_sur_les_murs) ;
- les bouts de murs à moins de TOLERANCE_NOEUD l'un de l'autre sont réunis en un même point (_reunir_les_bouts) ;
- trois murs ou plus au même point : si deux d'entre eux sont dans le prolongement l'un de l'autre, c'est un « T » (ou une
  croix) : les murs alignés passent, les autres viennent s'appuyer sur leur axe (rien à couper) ; sinon, toujours refusé ;
- un bout de mur qui s'arrête juste avant la face d'un autre mur (moins de TOLERANCE_NOEUD) est prolongé jusqu'à cette face.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from moteur.logement import Logement, Mur, Ouverture

VERSION_PLAN = "construction/0.1"
# Deux murs qui se rejoignent à moins de 1° sont dans le prolongement l'un de l'autre : pas de coupe d'onglet.
# Et quand l'onglet s'étirerait trop loin (angle de quelques degrés : à 2°, deux murs de 30 cm donnent 10 m d'onglet,
# qui avalait toutes les portes du mur sur fr-003), on les traite aussi comme alignés (voir _ajustements_aux_angles).
ANGLE_ONGLET_MIN_DEG = 1.0
PRESQUE_ALIGNES = math.cos(math.radians(ANGLE_ONGLET_MIN_DEG))
RECOUVREMENT_TOLERE = 0.01  # m : au-delà, deux ouvertures se chevauchent vraiment et le plan doit être corrigé
# Une ouverture lue un peu dans l'angle du mur (le coin est pris par le mur voisin) est raccourcie à ce qui reste du mur :
# c'est une imprécision de lecture, pas une erreur de plan. Au-delà de cette marge, le plan est faux et on refuse.
ANGLE_OUVERTURE_MAX = 0.30  # m
OUVERTURE_MIN = 0.25  # m : ce qui doit rester d'une ouverture raccourcie

# En dessous de cette distance (en mètres), deux points sont considérés égaux.
PRECISION = 1e-6
# B1 : imprécisions de lecture rattrapées pour que la maquette n'ait aucun jour (voir la tête du module).
TOLERANCE_NOEUD = 0.03  # m : deux bouts de murs plus proches sont le même point ; un bout aussi près d'une face la touche
ZONE_SOL_Z = 0.0005  # m : une zone de sol (autre revêtement dans la pièce) est posée un demi-millimètre au-dessus du sol de la
# pièce : à la même hauteur, les deux surfaces se disputeraient chaque point au rendu (taches noires)
CALAGE_SOL = 0.10  # m : un côté de pièce à moins de ça de la face d'un mur (parallèle) est posé dessus
DEPASSEMENT_MAX = 0.50  # m : un bout qui traverse un autre mur et dépasse de moins que ça est coupé (angle lu croisé)
ALIGNES_T = math.cos(math.radians(10.0))  # deux murs d'un même nœud à moins de 10° l'un de l'autre se prolongent (T)

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
    murs_lus, ouvertures = _reunir_les_bouts(logement.murs, logement.ouvertures)
    ajustements = _ajustements_aux_angles(murs_lus)
    _prolonger_jusqu_aux_faces(murs_lus, ajustements)
    ouvertures_par_mur: dict[str, list[Ouverture]] = {}
    for o in ouvertures:
        ouvertures_par_mur.setdefault(o.mur, []).append(o)

    for mur in murs_lus:
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
        contour = _sens_direct([_arrondi(pt) for pt in _caler_sur_les_murs(list(p.contour), murs_lus)])
        briques.append(Brique(f"sol__{p.id}", "sol", p.id, contour, 0.0, 0.0))
        briques.append(Brique(f"plafond__{p.id}", "plafond", p.id, contour, hsp, hsp))
        for k, zone in enumerate(p.zones_sol, start=1):
            morceau = _couper_par_convexe(contour, _sens_direct([_arrondi(pt) for pt in zone.contour]))
            if len(morceau) >= 3 and abs(_aire_signee(morceau)) > 1e-4:
                briques.append(Brique(f"zone_sol__{p.id}__{k}", "sol", p.id, _sens_direct(morceau), ZONE_SOL_Z, ZONE_SOL_Z))

    murs = {m.id: m for m in murs_lus}
    for o in ouvertures:
        if o.allege == 0:
            contour = _rectangle(murs[o.mur], o.position, o.position + o.largeur)
            briques.append(Brique(f"seuil__{o.id}", "sol", o.id, contour, 0.0, 0.0))

    from moteur.controle_maquette import jours_a_boucher  # importé ici : il importe Brique de ce module

    return briques + jours_a_boucher(briques, hsp)


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
            membres = [i, *groupe]
            if not _est_un_t(bouts, membres):
                noms = ", ".join(sorted({bouts[k][0].id for k in membres}))
                raise ValueError(f"plus de deux murs se rejoignent en {point} : {noms} (non géré)")
            # T ou croix : les murs alignés passent bout à bout ; les autres s'arrêtent sur leur FACE (B1). S'ils entraient
            # jusqu'à l'axe, deux murs se recouvriraient : leurs dessus, à la même hauteur, se font de l'ombre au rendu (carrés noirs).
            d = {k: _sortante(bouts[k][0], bouts[k][1]) for k in membres}
            a, b = min(((x, y) for x in membres for y in membres if x < y), key=lambda xy: _scalaire(d[xy[0]], d[xy[1]]))
            demi = max(bouts[a][0].epaisseur, bouts[b][0].epaisseur) / 2
            for k in membres:
                if k in (a, b):
                    continue
                sinus = max(abs(d[k][0] * d[a][1] - d[k][1] * d[a][0]), 0.3)  # en biais : un peu plus à reculer
                recul = demi / sinus
                mur_k, bout_k, _ = bouts[k]
                ajustements[mur_k.id][bout_k] = [-recul, -recul]
            deja_vus |= set(membres)
            continue
        j = groupe[0]
        deja_vus |= {i, j}
        mur_b, bout_b, _ = bouts[j]
        produit = abs(_scalaire(_direction(mur_a), _direction(mur_b)))
        if produit > PRESQUE_ALIGNES:
            continue  # murs dans le prolongement l'un de l'autre : rien à corriger (un onglet sur un angle minuscule exploserait)
        if produit > PRECISION:
            onglets = {m.id: (b, list(_onglet(m, b, n_, _)))
                       for (m, b), (n_, _) in (((mur_a, bout_a), (mur_b, bout_b)), ((mur_b, bout_b), (mur_a, bout_a)))}
            # Un onglet plus long que ça n'existe pas dans un logement : l'angle est trop aigu (moins de ~12° pour des murs
            # de 30 cm), c'est une lecture imprécise de deux murs alignés.
            limite = max(1.0, 2 * (mur_a.epaisseur + mur_b.epaisseur))
            if all(abs(v) <= limite for _, vals in onglets.values() for v in vals):  # sinon : comme des murs alignés
                for id_, (b, vals) in onglets.items():
                    ajustements[id_][b] = vals
            continue
        for k in (0, 1):
            ajustements[mur_a.id][bout_a][k] += mur_b.epaisseur / 2
            ajustements[mur_b.id][bout_b][k] -= mur_a.epaisseur / 2

    return {k: ((v[0][0], v[0][1]), (v[1][0], v[1][1])) for k, v in ajustements.items()}


def _sortante(mur: Mur, bout: int) -> Point:
    """La direction du mur en partant du bout `bout` vers l'intérieur du mur."""
    u = _direction(mur)
    return u if bout == 0 else (-u[0], -u[1])


def _est_un_t(bouts: list[tuple[Mur, int, Point]], membres: list[int]) -> bool:
    """Parmi les murs d'un même nœud, deux sont-ils dans le prolongement l'un de l'autre (T ou croix) ?"""
    d = [_sortante(bouts[k][0], bouts[k][1]) for k in membres]
    return any(_scalaire(d[a], d[b]) < -ALIGNES_T for a in range(len(d)) for b in range(a + 1, len(d)))


def _reunir_les_bouts(murs: list[Mur], ouvertures: list[Ouverture]) -> tuple[list[Mur], list[Ouverture]]:
    """Les bouts de murs à moins de TOLERANCE_NOEUD (ou de la moitié de l'épaisseur du plus mince) les uns des autres,
    réunis en leur point moyen (B1).

    Une lecture pose rarement deux bouts EXACTEMENT au même point (fr-031 : 113 et 108 px) ; sans cela, l'angle n'est pas
    fermé et il reste un jour dans la maquette. Les ouvertures restent à leur place dans la pièce : leur position, comptée
    depuis le début du mur, suit le déplacement de ce début. Un mur dont les deux bouts tomberaient au même point n'est pas
    touché."""
    bouts = [(k, b, m.debut if b == 0 else m.fin) for k, m in enumerate(murs) for b in (0, 1)]
    parent = list(range(len(bouts)))

    def racine(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(bouts)):
        for j in range(i + 1, len(bouts)):
            ki, kj = bouts[i][0], bouts[j][0]
            # Plus proches que la moitié de l'épaisseur du plus mince des deux murs : c'est forcément le même coin (fr-031 :
            # deux morceaux d'un mur extérieur de 22-25 cm s'arrêtaient à 3,5 cm l'un de l'autre → carré noir au rendu).
            tol = max(TOLERANCE_NOEUD, 0.5 * min(murs[ki].epaisseur, murs[kj].epaisseur))
            if ki != kj and math.dist(bouts[i][2], bouts[j][2]) < tol:
                parent[racine(i)] = racine(j)
    groupes: dict[int, list[int]] = {}
    for i in range(len(bouts)):
        groupes.setdefault(racine(i), []).append(i)
    nouveaux = [[m.debut, m.fin] for m in murs]
    for membres in groupes.values():
        if len(membres) < 2:
            continue
        if len(membres) > 2 and not _est_un_t([(murs[k], b, p) for k, b, p in bouts], membres):
            continue  # trois murs ou plus sans prolongement : les réunir créerait un nœud que la 3D ne sait pas faire
        cx = sum(bouts[i][2][0] for i in membres) / len(membres)
        cy = sum(bouts[i][2][1] for i in membres) / len(membres)
        for i in membres:
            k, b, _ = bouts[i]
            nouveaux[k][b] = (cx, cy)
    sortie, decalage = [], {}
    for m, (debut, fin) in zip(murs, nouveaux):
        if (debut, fin) == (m.debut, m.fin) or math.dist(debut, fin) < 10 * TOLERANCE_NOEUD:
            sortie.append(m)
            continue
        u = _direction(m)
        decalage[m.id] = (debut[0] - m.debut[0]) * u[0] + (debut[1] - m.debut[1]) * u[1]
        sortie.append(m.model_copy(update={"debut": debut, "fin": fin}))
    if not decalage:
        return murs, ouvertures
    longueurs = {m.id: m.longueur for m in sortie}
    ouv = []
    for o in ouvertures:
        if o.mur in decalage:
            pos = min(max(0.0, o.position - decalage[o.mur]), max(0.0, longueurs[o.mur] - o.largeur))
            o = o.model_copy(update={"position": pos})
        ouv.append(o)
    return sortie, ouv


def _prolonger_jusqu_aux_faces(murs: list[Mur], ajustements: dict[str, Ajustement]) -> None:
    """Chaque bout de mur LIBRE (qui ne rejoint aucun autre bout) et qui touche un autre mur est coupé sur la bonne face (B1).

    Une lecture pose les bouts à peu près : un mur s'arrête 1 ou 2 cm avant la face d'un autre (une fente laisse passer le
    jour), entre dedans jusqu'à son axe (un « T » lu ainsi), ou le traverse et dépasse (un angle en L dont les deux traits se
    croisent, fr-030). Deux murs l'un dans l'autre ont leurs dessus à la même hauteur, qui se font de l'ombre au rendu : des
    carrés noirs à chaque jonction. Règle : le mur s'arrête sur la face de l'autre par laquelle il arrive ; dans un angle en L
    croisé, l'un des deux va jusqu'à la face extérieure de l'autre (l'angle reste plein) et l'autre s'arrête sur sa face.
    Hors de ces cas (bout loin de tout mur, mur parallèle), rien ne change."""
    libres = []
    for m in murs:
        for b in (0, 1):
            p = m.debut if b == 0 else m.fin
            if not any(math.dist(p, q) < PRECISION for n in murs if n is not m for q in (n.debut, n.fin)):
                libres.append((m, b, p))
    sin_min = math.sin(math.radians(10.0))
    for m, b, p in libres:
        dedans = _sortante(m, b)  # du bout vers le corps du mur
        dehors = (-dedans[0], -dedans[1])  # au-delà du bout
        recul = min(1.0, m.longueur / 2)
        corps = (p[0] + dedans[0] * recul, p[1] + dedans[1] * recul)  # un point du corps du mur, en retrait du bout
        for autre in murs:
            if autre is m:
                continue
            v = _direction(autre)
            n = (-v[1], v[0])
            rel = (p[0] - autre.debut[0], p[1] - autre.debut[1])
            s = _scalaire(rel, v)
            face = autre.epaisseur / 2
            if not -face <= s <= autre.longueur + face:
                continue
            k = _scalaire(dehors, n)  # de combien la distance (signée) à l'axe de l'autre change quand le mur avance
            if abs(k) <= sin_min:
                continue  # parallèles
            d = _scalaire(rel, n)
            d_corps = _scalaire((corps[0] - autre.debut[0], corps[1] - autre.debut[1]), n)
            if abs(d_corps) <= face:
                continue  # le corps du mur est dans l'autre : ce n'est pas un bout qui arrive sur lui
            cote = 1.0 if d_corps > 0 else -1.0
            if k * cote >= 0:
                continue  # en avançant, le mur s'éloigne de l'autre
            t_proche = (cote * face - d) / k  # avancer de ça amène le bout sur la face par laquelle il arrive
            t_loin = (-cote * face - d) / k  # … sur la face opposée
            if 0 < t_proche <= TOLERANCE_NOEUD:
                rallonge = t_proche  # fente : prolongé jusqu'à la face
            elif t_proche <= 0 and t_loin >= -DEPASSEMENT_MAX:
                croise = any(math.dist(p, q) < m.epaisseur + autre.epaisseur for q in (autre.debut, autre.fin))
                rallonge = t_loin if croise and m.id < autre.id else t_proche
            else:
                continue
            if abs(rallonge) <= PRECISION:
                break
            av = ajustements[m.id]
            av_bout = (av[b][0] + rallonge, av[b][1] + rallonge)
            ajustements[m.id] = (av_bout, av[1]) if b == 0 else (av[0], av_bout)
            break


def _caler_sur_les_murs(contour: list[Point], murs: list[Mur]) -> list[Point]:
    """Le contour d'une pièce, chaque côté posé sur la face du mur qu'il longe (B1).

    Un côté est calé sur une face si elle lui est parallèle (à 2° près), tournée vers la pièce, à moins de CALAGE_SOL, et si
    elle le longe sur au moins 90 % de sa longueur (un côté qui ne longe qu'un bout de mur
    déborderait, au-delà du bout, sur la pièce voisine : fr-038). Les sommets deviennent les croisements des côtés calés. Si le
    calage déforme trop la pièce (surface changée de plus de 20 %), le contour d'origine est gardé."""
    pts = _sens_direct(contour)
    n = len(pts)
    if n < 3:
        return contour
    faces = []
    for m in murs:
        u = _direction(m)
        g = (-u[1], u[0])
        for cote in (-1.0, 1.0):
            off = cote * m.epaisseur / 2
            origine = (m.debut[0] + g[0] * off, m.debut[1] + g[1] * off)
            faces.append((origine, u, (g[0] * cote, g[1] * cote), -m.epaisseur / 2, m.longueur + m.epaisseur / 2))
    sin_max = math.sin(math.radians(2.0))
    lignes: list[tuple[Point, Point] | None] = []
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        L = math.dist(a, b)
        if L < 1e-3:
            lignes.append(None)
            continue
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        dedans = (-d[1], d[0])  # contour dans le sens direct : la pièce est à gauche du côté
        milieu = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        meilleure, ecart_min = None, CALAGE_SOL
        for origine, u, normale, t0, t1 in faces:
            if abs(d[0] * u[1] - d[1] * u[0]) > sin_max or _scalaire(normale, dedans) < 0.99:
                continue
            ecart = abs(_scalaire((milieu[0] - origine[0], milieu[1] - origine[1]), normale))
            ta = _scalaire((a[0] - origine[0], a[1] - origine[1]), u)
            tb = _scalaire((b[0] - origine[0], b[1] - origine[1]), u)
            commun = min(max(ta, tb), t1) - max(min(ta, tb), t0)
            if ecart <= ecart_min and commun >= 0.9 * L:
                meilleure, ecart_min = (origine, u), ecart
        lignes.append(meilleure if meilleure is not None else (a, d))
    sortie = []
    for k in range(n):
        avant, apres = lignes[k - 1], lignes[k]
        if avant is None or apres is None:
            sortie.append(pts[k])
            continue
        (p, u), (q, v) = avant, apres
        det = u[0] * v[1] - u[1] * v[0]
        if abs(det) < 1e-6:  # côtés dans le prolongement l'un de l'autre : on garde le sommet, ramené sur la ligne
            t = _scalaire((pts[k][0] - q[0], pts[k][1] - q[1]), v)
            sortie.append((q[0] + v[0] * t, q[1] + v[1] * t))
            continue
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / det
        x = (p[0] + u[0] * t, p[1] + u[1] * t)
        sortie.append(x if math.dist(x, pts[k]) <= 2 * CALAGE_SOL else pts[k])
    a0, a1 = abs(_aire_signee(pts)), abs(_aire_signee(sortie))
    if a0 <= 0 or abs(a1 / a0 - 1) > 0.20:
        return contour
    return sortie


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
    debut_libre, fin_libre = max(t_debut), min(t_fin)  # entre les deux, le mur est à lui ; au-delà, c'est l'angle
    for o in sorted(ouvertures, key=lambda o: o.position):
        gauche, droite = o.position, o.position + o.largeur
        if debut_libre - ANGLE_OUVERTURE_MAX <= gauche < debut_libre:
            gauche = debut_libre
        if fin_libre < droite <= fin_libre + ANGLE_OUVERTURE_MAX:
            droite = fin_libre
        if (gauche, droite) != (o.position, o.position + o.largeur) and droite - gauche < OUVERTURE_MIN:
            raise ValueError(f"l'ouverture {o.id} est presque entièrement dans l'angle du mur {mur.id}")
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
        derniere = max(ouvertures, key=lambda o: o.position)
        raise ValueError(f"l'ouverture {derniere.id} du mur {mur.id} empiète sur son angle")
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


def _couper_par_convexe(sujet: list[Point], coupe: list[Point]) -> list[Point]:
    """La partie de `sujet` (un polygone, creux permis) qui tombe dans `coupe` (convexe, sens direct) : découpe de
    Sutherland-Hodgman, un côté de `coupe` après l'autre. Une pièce en L coupée peut garder un côté aller-retour de largeur
    nulle, sans surface : invisible."""
    sortie = list(sujet)
    for (ax, ay), (bx, by) in zip(coupe, coupe[1:] + coupe[:1]):
        if not sortie:
            break

        def dedans(p: Point) -> bool:
            return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= -PRECISION

        def croisement(p: Point, q: Point) -> Point:
            dx, dy = q[0] - p[0], q[1] - p[1]
            den = (bx - ax) * dy - (by - ay) * dx
            t = ((p[0] - ax) * dy - (p[1] - ay) * dx) / den if abs(den) > 1e-15 else 0.0
            return _arrondi((ax + t * (bx - ax), ay + t * (by - ay)))

        entree, sortie = sortie, []
        for i, q in enumerate(entree):
            p = entree[i - 1]
            if dedans(q):
                if not dedans(p):
                    sortie.append(croisement(p, q))
                sortie.append(q)
            elif dedans(p):
                sortie.append(croisement(p, q))
    return [pt for i, pt in enumerate(sortie) if pt != sortie[i - 1]] if sortie else []


def _sens_direct(contour: list[Point]) -> list[Point]:
    """Remet le contour dans le sens inverse des aiguilles d'une montre."""
    return contour if _aire_signee(contour) > 0 else contour[::-1]


def _arrondi(point: Point) -> Point:
    # Au micromètre : efface les minuscules erreurs de calcul (ex. 5.1000000000000005).
    return (round(point[0], 6) + 0.0, round(point[1], 6) + 0.0)
