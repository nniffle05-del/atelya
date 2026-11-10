r"""Le TRADUCTEUR de la lecture de Claude : la fiche lecture-claude/0.1 (pixels) → le logement en mètres, ses doutes, et la
lecture que l'écran de vérification sait afficher (moteur.preparer_verification.verification_du_plan, inchangé).

Pourquoi (décision NT du 08/11/2026, docs/projet/memoire/plan-lancement-lecture-claude.md) : au lancement, Claude lit le plan
(en pixels) ; tout le reste est à Atelya. Ici, Atelya passe des pixels aux mètres, avec SES garde-fous :

1. Recalage : chaque mur de Claude glisse sur le trait du plan, à quelques pixels près (moteur.recalage_murs) : la
   documentation de l'API dit que les positions données par Claude sont approximatives ; le trait du plan est exact.
2. Le « coloriage de Claude » : la fiche est dessinée comme le coloriage du U-Net (murs, portes, fenêtres, pièces), à la même
   taille (768 px de grand côté), pour que le lecteur d'échelle d'Atelya (moteur.echelle_plan) s'y applique SANS réécriture,
   avec les textes lus par Claude comme ceux d'un PDF (les textes exacts du PDF passent avant, s'il y en a).
3. L'échelle à « deux clés » (accord NT du 08/11/2026) :
   - clé d'Atelya = l'échelle que notre lecteur retrouve sur le dessin (marques des cotes mesurées au pixel, surfaces, barre,
     « 1/50 »), avec toutes ses règles (deux cotes d'accord pour être « sûre », contradiction, ambiguïté…) ;
   - clé de Claude = l'échelle qu'il propose lui-même ;
   - les deux d'accord à ACCORD_DEUX_CLES près → échelle « lue » ; en désaccord → « à vérifier », doute fort en tête de l'écran.
   Sans clé d'Atelya, le brouillon prend la meilleure échelle disponible (les cotes de Claude, recalculées par nous depuis
   leurs bouts, si au moins deux s'accordent ; sinon l'échelle proposée par Claude si la taille du logement est vraisemblable ;
   sinon le secours habituel d'Atelya), toujours « à vérifier » : une échelle que seul Claude soutient ne construit rien.
4. Le logement : murs (axe + épaisseur), ouvertures posées sur leur mur, pièces = zones fermées par les murs autour du point
   donné par Claude (ou son contour si les murs ne la ferment pas). Repère d'Atelya : mètres, origine au coin sud-ouest de
   l'intérieur, y vers le nord (comme le générateur, le traducteur des coloriages et les vérités).
5. Les doutes : ceux de la fiche (nombre mal recopié…), ceux de Claude, ceux de l'échelle, les pièces mal fermées, plusieurs
   niveaux sur l'image, les contrôles propres à la lecture de Claude (moteur.doutes_claude : textes introuvables, cotes contre
   le dessin, surfaces contre les pièces), puis les contrôles de bon sens habituels (moteur.doutes.examiner).

Version 0.1.0 (08/11/2026) : première version (plans vus de face ; photo de biais : envoyer à Claude l'image déjà redressée).
Version 0.2.0 (08/11/2026) : doutes propres à la lecture de Claude (moteur.doutes_claude 0.1.0).
Version 0.2.1 (09/11/2026) : bouts de murs coupés droit sur la face du mur qu'ils touchent (fin du filet de lumière aux angles
   saillants, app-001), bouts libres non prolongés, contour à angles droits refusé s'il mord sur une pièce voisine. 21 vrais
   plans : bouche-trous 48,4 → 20,9 m², trous 11 → 10, sols superposés 0,072 → 0,027 m².
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image

from moteur.coloriage import FENETRE, MUR, PIECES, PORTE, PORTE_FENETRE, _contour_orthogonal
from moteur.doutes import doute_plusieurs_niveaux, examiner
from moteur.doutes_claude import doutes_des_cotes, doutes_des_surfaces, doutes_des_textes
from moteur.echelle_plan import decider, lire_echelle_plan
from moteur.lecture_claude import Cadre, FicheControlee, LectureClaude
from moteur.lecture_complete import COTE_ATELYA, Lecture, PlanLu, PlanSource, _echelle_de_secours, _taille_vraisemblable
from moteur.lecture_cotes import ECART_MAX, TexteLu
from moteur.logement import Logement
from moteur.recalage_murs import affiner_mur

VERSION_TRADUCTEUR_CLAUDE = "0.3.0"  # 10/11/2026 : dimensions de pièces mesurées entre les murs (2e clé)
MODELE = "claude"
ACCORD_DEUX_CLES = 0.03  # 3 % : écart maximal entre l'échelle retrouvée par Atelya et celle proposée par Claude
PORTEE_OUVERTURE_PX = 12.0  # une ouverture appartient à un mur dont l'axe passe à moins de ça (ou de son épaisseur)
DEBORD_OUVERTURE_M = 0.05  # une ouverture qui dépasse le bout de son mur de plus de 5 cm donne un doute
JONCTION_PX = 3.0  # px : un bout de mur à moins de 3 px d'un autre mur le touche (le recalage décale parfois un mur de si peu)
ECART_CONTOUR_PX = 1.5  # px : … et pas plus de 1,5 pixel d'écart en moyenne le long du bord de la zone
DEBORD_VOISINES_PX = 0.1  # px : … et il ne couvre pas plus de 0,1 pixel des pièces voisines par pixel de bord
ECART_CONTOUR = 0.03  # le contour à angles droits est gardé s'il épouse la zone à 3 % près (pixels en trop + en moins), sinon le contour libre
HAUTEUR_SOUS_PLAFOND = 2.50
HAUTEUR_PORTE, HAUTEUR_PORTE_FENETRE, HAUT_FENETRE = 2.04, 2.15, 2.20  # comme moteur.coloriage
CLASSE_OUVERTURE = {"porte": PORTE, "fenetre": FENETRE, "porte_fenetre": PORTE_FENETRE}
CLASSE_PIECE = {t: c for c, (t, _) in PIECES.items()}
NOM_PIECE = {t: n for _, (t, n) in PIECES.items()}


# ---------------------------------------------------------------- petits outils

def _xywh(c: Cadre, f: float = 1.0) -> list[float]:
    """Un cadre (x0, y0, x1, y1) en pixels envoyés → [x, y, largeur, hauteur] en pixels de l'image du plan."""
    x0, y0, x1, y1 = (v / f for v in c)
    return [round(min(x0, x1), 1), round(min(y0, y1), 1), round(abs(x1 - x0), 1), round(abs(y1 - y0), 1)]


def _autour(x: float, y: float, r: float) -> list[float]:
    return [round(x - r, 1), round(y - r, 1), round(2 * r, 1), round(2 * r, 1)]


def _doute(code: str, raison: str, gravite: str = "fort", element: str | None = None, zone_px: list | None = None) -> dict:
    d = {"code": code, "raison": raison, "gravite": gravite, "element": element}
    if zone_px:
        d["zone_px"] = zone_px
    return d


def _textes(fiche: LectureClaude, f: float) -> list[TexteLu]:
    """Les textes lus par Claude, au format de moteur.lecture_cotes, en pixels de l'image du plan."""
    sortie = []
    for t in [*fiche.cotes, *fiche.surfaces, *fiche.textes]:
        x0, y0, x1, y1 = (v / f for v in t.cadre)
        boite = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64)
        sortie.append(TexteLu(t.texte, boite, 1.0))
    return sortie


def _echelle_des_cotes(fiche: LectureClaude, f: float) -> tuple[float | None, int]:
    """L'échelle (px de l'image du plan par m) que donnent les cotes de Claude, recalculée par NOUS depuis leurs bouts : le plus
    grand groupe de cotes d'accord entre elles à ECART_MAX près (même tolérance que moteur.echelle_plan ; à égalité, le groupe
    des plus longues cotes), longues cotes plus lourdes. Rend aussi la taille du groupe (il en faut deux pour s'y fier un peu).
    Pas la médiane : avec deux cotes en désaccord, la médiane tombe entre elles et n'en garde aucune."""
    valeurs = [(math.dist(*c.bouts) / f, c.valeur_m) for c in fiche.cotes if math.dist(*c.bouts) > 0]
    if not valeurs:
        return None, 0
    groupes = []
    for px0, v0 in valeurs:
        e0 = px0 / v0
        groupe = [(px, v) for px, v in valeurs if abs(px / v - e0) / e0 <= ECART_MAX]
        groupes.append((len(groupe), sum(v for _, v in groupe), groupe))
    _, _, gardees = max(groupes, key=lambda g: (g[0], g[1]))
    return sum(px for px, _ in gardees) / sum(v for _, v in gardees), len(gardees)


FACE_SOMBRE = 120  # niveau de gris sous lequel un pixel est « trait de mur »
FACE_EPAISSEUR_MIN = 3  # px : un trait plus fin est une hachure de sol ou un trait de meuble, pas la face d'un mur
ECART_MESURE_MAX = 0.08  # la distance mesurée entre les faces ne s'écarte pas de plus de 8 % des bouts donnés par Claude
COTES_ENTRE_MURS_MIN = 3  # au moins 3 dimensions d'accord pour confirmer l'échelle ainsi


def _face_rencontree(gris: np.ndarray, depart, direction, portee: float) -> float | None:
    """En partant de `depart` dans `direction` (unitaire), la distance (px) jusqu'au premier trait sombre ÉPAIS (au moins
    FACE_EPAISSEUR_MIN px de suite) : la face d'un mur. None si rien avant `portee`."""
    H, W = gris.shape
    suite, premier = 0, None
    t = 0.0
    while t <= portee:
        x, y = int(round(depart[0] + direction[0] * t)), int(round(depart[1] + direction[1] * t))
        if not (0 <= x < W and 0 <= y < H):
            return None
        if gris[y, x] < FACE_SOMBRE:
            if suite == 0:
                premier = t
            suite += 1
            if suite >= FACE_EPAISSEUR_MIN:
                return premier
        else:
            suite = 0
        t += 1.0
    return None


def _cotes_entre_murs(gris: np.ndarray, fiche: LectureClaude, f: float) -> tuple[float | None, int, list]:
    """2e clé pour les plans qui écrivent les DIMENSIONS DANS LES PIÈCES (« 450 X 525 », sans trait de cote, très courant en
    France ; test de bout en bout app-002, 10/11/2026) : pour chaque cote dont Claude a posé les bouts sur deux murs, Atelya
    part du milieu, avance des deux côtés jusqu'à la face du mur sur le DESSIN et mesure lui-même la distance. Gardées : les
    mesures à moins de ECART_MESURE_MAX des bouts de Claude ; puis le plus grand groupe d'accord (ECART_MAX, comme les cotes).
    Rend (px du plan par m, taille du groupe, détail)."""
    mesures, detail = [], []
    for c in fiche.cotes:
        (ax, ay), (bx, by) = ((x / f, y / f) for x, y in c.bouts)
        lc = math.hypot(bx - ax, by - ay)
        if lc < 10:
            continue
        u = ((bx - ax) / lc, (by - ay) / lc)
        m = ((ax + bx) / 2, (ay + by) / 2)
        da = _face_rencontree(gris, m, (-u[0], -u[1]), lc * 0.6)
        db = _face_rencontree(gris, m, u, lc * 0.6)
        if da is None or db is None:
            detail.append([c.texte, None])
            continue
        mesure = da + db
        if abs(mesure / lc - 1) > ECART_MESURE_MAX:
            detail.append([c.texte, round(mesure, 1), "trop loin des bouts de Claude"])
            continue
        mesures.append((mesure, c.valeur_m))
        detail.append([c.texte, round(mesure, 1), round(mesure / c.valeur_m, 2)])
    if not mesures:
        return None, 0, detail
    groupes = []
    for px0, v0 in mesures:
        e0 = px0 / v0
        g = [(px, v) for px, v in mesures if abs(px / v - e0) / e0 <= ECART_MAX]
        groupes.append((len(g), sum(v for _, v in g), g))
    _, _, gardees = max(groupes, key=lambda x: (x[0], x[1]))
    return sum(px for px, _ in gardees) / sum(v for _, v in gardees), len(gardees), detail


def _sur_le_mur(cx: float, cy: float, mur: list[float]) -> tuple[float, float]:
    """(distance du point à l'axe du mur, position relative le long du mur de 0 à 1)."""
    ax, ay, bx, by, _ = mur
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy or 1e-9
    t = ((cx - ax) * dx + (cy - ay) * dy) / l2
    return abs((cx - ax) * dy - (cy - ay) * dx) / math.sqrt(l2), t


def _mur_porteur(bords: list[float], murs: list[list[float]], indice_claude: int | None) -> int | None:
    """Le mur qui porte une ouverture : celui que Claude désigne s'il passe bien par elle, sinon le plus proche."""
    cx, cy = (bords[0] + bords[2]) / 2, (bords[1] + bords[3]) / 2

    def convient(k: int) -> float | None:
        d, t = _sur_le_mur(cx, cy, murs[k])
        return d if -0.02 <= t <= 1.02 and d <= max(PORTEE_OUVERTURE_PX, murs[k][4]) else None

    if indice_claude is not None and convient(indice_claude) is not None:
        return indice_claude
    proches = [(d, k) for k in range(len(murs)) if (d := convient(k)) is not None]
    return min(proches)[1] if proches else None


def _contour(zone: np.ndarray, voisines: np.ndarray | None = None) -> list[tuple[float, float]] | None:
    """Le contour d'une zone : à angles droits s'il ÉPOUSE la zone (murs droits), sinon le contour libre (murs en biais, plan
    un peu penché). Épouser = pixels de l'un et pas de l'autre ≤ ECART_CONTOUR de la zone (B1, 08/11/2026 : comparer les seules
    surfaces laissait passer un rectangle droit sur une pièce penchée de 2°, fr-024, avec des pointes vides le long des murs),
    et presque rien sur les pièces `voisines` (DEBORD_VOISINES_PX par pixel de bord ; fr-022, 09/11/2026 : le rectangle d'un
    séjour partagé en deux mordait de 0,18 m² sur l'autre moitié, deux sols au même endroit, rendus noirs)."""
    ortho = _contour_orthogonal(zone)
    aire = float(zone.sum())
    if ortho is not None and aire > 0:
        dessin = np.zeros(zone.shape, np.uint8)
        k = 1 << 4
        pts = np.round((np.asarray(ortho, np.float64) - 0.5) * k).astype(np.int32)  # bords des pixels → centres (fillPoly)
        cv2.fillPoly(dessin, [pts], 1, shift=4)
        bords, _ = cv2.findContours(zone.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        perimetre = sum(cv2.arcLength(c, True) for c in bords)
        ecart = float(np.logical_xor(dessin > 0, zone).sum())
        # Les deux : une petite pièce tolère 3 % (un rang de pixels), une grande pas plus de 1,5 px en moyenne le long du bord
        # (fr-038 : 3 % d'un séjour de 85 m² laissaient le rectangle droit déborder de 0,7 m² sur la cuisine).
        debord = float((dessin.astype(bool) & voisines).sum()) if voisines is not None else 0.0
        if ecart / aire <= ECART_CONTOUR and ecart <= ECART_CONTOUR_PX * max(perimetre, 1.0) \
                and debord <= DEBORD_VOISINES_PX * max(perimetre, 1.0):
            return ortho
    contours, _ = cv2.findContours(zone.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return ortho
    c = max(contours, key=cv2.contourArea)
    pts = cv2.approxPolyDP(c, 1.5, True)[:, 0, :].astype(float)
    return [(float(x), float(y)) for x, y in pts] if len(pts) >= 3 else ortho


def _partager(zones: list, membres: list[int], zone: np.ndarray, contours: dict[int, list]) -> None:
    """Découpe `zone` entre les pièces `membres` (indices dans `zones`) : chaque pixel va à la pièce dont le contour lu le
    contient (la première lue en cas de recouvrement), sinon à la plus proche ; une pièce sans contour prend le reste."""
    ys, xs = np.nonzero(zone)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    z = zone[y0:y1, x0:x1]
    graines = []
    for i in membres:
        if i in contours:
            g = _polygone([(u - x0, v - y0) for u, v in contours[i]], z.shape) & z
        else:
            g = None
        graines.append(g)
    reste = z.copy()
    for g in graines:
        if g is not None:
            reste &= ~g
    graines = [g if g is not None else reste for g in graines]
    distances = np.stack([cv2.distanceTransform((~g).astype(np.uint8), cv2.DIST_L2, 3) if g.any()
                          else np.full(z.shape, np.inf, np.float32) for g in graines])
    proprietaire = np.argmin(distances, axis=0)
    for rang, i in enumerate(membres):
        pid, ptype, _, c = zones[i]
        masque = np.zeros(zone.shape, bool)
        masque[y0:y1, x0:x1] = z & (proprietaire == rang)
        zones[i] = (pid, ptype, masque, c)


def _coupe_du_bout(murs: list, k: int, debut: bool) -> tuple[tuple[float, float], tuple[float, float]]:
    """La ligne (un point, une direction) où s'arrête un bout du mur k.

    Le bout touche un autre mur (angle, té, même décalé de quelques pixels par le recalage) : il s'arrête sur la FACE LOINTAINE
    de cet autre mur, celle qu'il atteint après l'avoir traversé ; l'angle est rempli, rien ne dépasse dans la pièce. Bout près
    d'un autre mur sans le croiser (courbe faite de morceaux décalés d'un pixel, mur continué avec un petit écart : fr-026) :
    prolongé d'une demi-épaisseur + JONCTION_PX, l'écart se ferme. Bout libre (mur qui s'arrête dans la pièce, aucun mur à
    moins de cette distance) : coupé net, comme en 3D (fr-022 : un mur de 98 cm prolongé de 50 cm laissait un vide au sol)."""
    x0, y0, x1, y1, ep = murs[k]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    (ex, ey), (dx, dy) = ((x0, y0), (-ux, -uy)) if debut else ((x1, y1), (ux, uy))  # le bout, et la direction vers le dehors
    r = ep / 2 + JONCTION_PX
    meilleur = None
    voisin = False  # un autre mur passe tout près du bout (courbe faite de morceaux, mur continué avec un petit écart…)
    for j, (a0, b0, a1, b1, epj) in enumerate(murs):
        Lj = math.hypot(a1 - a0, b1 - b0)
        if j == k or Lj == 0:
            continue
        vx, vy = (a1 - a0) / Lj, (b1 - b0) / Lj
        s = min(max((ex - a0) * vx + (ey - b0) * vy, 0.0), Lj)
        if math.hypot(ex - a0 - s * vx, ey - b0 - s * vy) - epj / 2 <= r:
            voisin = True
        nx, ny = -vy, vx
        cos = nx * dx + ny * dy
        if abs(cos) < 0.5:  # moins de 30° entre les deux murs : un prolongement, pas une jonction
            continue
        t = (nx * (a0 - ex) + ny * (b0 - ey)) / cos  # distance du bout à l'axe de l'autre mur, le long du mur k
        demi = epj / 2 / abs(cos)  # demi-épaisseur de l'autre mur, le long du mur k
        if not -demi - JONCTION_PX <= t <= demi + r:
            continue
        s = (ex + t * dx - a0) * vx + (ey + t * dy - b0) * vy  # où le mur k rencontre l'autre mur, le long de celui-ci
        if not -ep / 2 - epj / 2 - JONCTION_PX <= s <= Lj + ep / 2 + epj / 2 + JONCTION_PX:
            continue
        if meilleur is None or abs(t) < meilleur[0]:
            signe = 1.0 if cos > 0 else -1.0
            meilleur = (abs(t), (a0 + signe * epj / 2 * nx, b0 + signe * epj / 2 * ny), (vx, vy))
    if meilleur is not None:
        return meilleur[1], meilleur[2]
    if voisin:
        return (ex + r * dx, ey + r * dy), (-dy, dx)
    return (ex, ey), (-dy, dx)


def _croisement(p, u, q, v) -> tuple[float, float]:
    """Le point commun des droites (p, direction u) et (q, direction v), supposées non parallèles."""
    det = u[0] * -v[1] - u[1] * -v[0]
    lam = ((q[0] - p[0]) * -v[1] - (q[1] - p[1]) * -v[0]) / det
    return p[0] + lam * u[0], p[1] + lam * u[1]


def _bati(murs: list, forme: tuple[int, int]) -> np.ndarray:
    """Les murs dessinés en pixels (1 = mur), chacun en bande à bouts COUPÉS DROIT sur la face du mur qu'il touche.

    App-001 (09/11/2026) : avant, chaque mur était prolongé d'une demi-épaisseur + 3 px avec des bouts ARRONDIS ; à un angle
    saillant (un angle de mur qui avance dans la pièce), ce bout dépassait d'environ 25 cm dans la pièce : le contour de la pièce
    gardait une bosse, son sol et son plafond s'arrêtaient avant le mur, et le bouche-trou laissait un filet de lumière en 3D."""
    bati = np.zeros(forme, np.uint8)
    k16 = 1 << 4
    # Côtés des murs dessinés comme avant (axe arrondi au pixel, trait de t = max(1, round(ep)) px de cv2.line : de l'axe moins
    # (t + 1) // 2 à l'axe plus (t + 1) // 2, bords compris, 0 pour t = 1) : seuls les bouts changent, le reste de la lecture
    # (origine, surfaces) ne bouge pas.
    def _largeur_dessinee(ep: float) -> int:
        t = max(1, int(round(ep)))
        return 0 if t == 1 else 2 * ((t + 1) // 2)

    murs = [[int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)), _largeur_dessinee(ep)] for x0, y0, x1, y1, ep in murs]
    for k, (x0, y0, x1, y1, ep) in enumerate(murs):
        L = math.hypot(x1 - x0, y1 - y0)
        if L == 0:
            continue
        u = ((x1 - x0) / L, (y1 - y0) / L)
        m = (-u[1], u[0])
        demi = ep / 2
        (p0, d0), (p1, d1) = _coupe_du_bout(murs, k, True), _coupe_du_bout(murs, k, False)
        coins = []
        for cote, (p, d) in ((demi, (p0, d0)), (demi, (p1, d1)), (-demi, (p1, d1)), (-demi, (p0, d0))):
            coins.append(_croisement((x0 + cote * m[0], y0 + cote * m[1]), u, p, d))
        cv2.fillPoly(bati, [np.round(np.asarray(coins) * k16).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=4)
        # L'axe en trait de 1 px par-dessus : un mur fin et penché reste étanche (les zones libres sont prises en 4-connexité).
        a, b = _croisement((x0, y0), u, p0, d0), _croisement((x0, y0), u, p1, d1)
        cv2.line(bati, (int(round(a[0])), int(round(a[1]))), (int(round(b[0])), int(round(b[1]))), 1, 1)
    return bati


def _polygone(points, forme: tuple[int, int]) -> np.ndarray:
    m = np.zeros(forme, np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(points, np.float64)).astype(np.int32)], 1)
    return m.astype(bool)


# ---------------------------------------------------------------- la traduction

def _refus(source: PlanSource, raison: str, echelle: dict | None = None, coloriage=None) -> PlanLu:
    lecture = Lecture(MODELE, None, None, examiner(None, erreur=raison), echelle or {"etat": "a_verifier", "source": None},
                      coloriage=coloriage, erreur=raison)
    return PlanLu(source, lecture, {MODELE: lecture}, "lecture de Claude")


def traduire(source: PlanSource, controlee: FicheControlee, facteur: float = 1.0, *, projet_id: str | None = None,
             recaler: bool = True, ocr: bool = True) -> PlanLu:
    """La lecture complète d'un plan à partir de la fiche de Claude.

    `source` : le plan tel que l'écran l'affichera (image pleine taille, textes exacts du PDF s'il y en a) ;
    `controlee` : la fiche passée par moteur.lecture_claude.controler_fiche ;
    `facteur` : pixels de l'image ENVOYÉE à Claude / pixels de l'image du plan (moteur.lecture_claude.image_pour_claude)."""
    if controlee.refusee:
        raisons = "; ".join(p.raison for p in controlee.problemes if p.gravite == "refus") or "fiche refusée"
        return _refus(source, f"fiche de Claude refusée : {raisons}")
    fiche = controlee.lecture
    f = float(facteur)
    projet_id = projet_id or source.nom
    H, W = source.image.shape[:2]
    gris = np.asarray(Image.fromarray(source.image).convert("L"))
    autres: list[dict] = []
    infos: dict = {"version": VERSION_TRADUCTEUR_CLAUDE}

    # 1. Les murs en pixels du plan, recalés sur le trait.
    murs = [[m.axe[0] / f, m.axe[1] / f, m.axe[2] / f, m.axe[3] / f, m.epaisseur_px / f] for m in fiche.murs]
    if recaler:
        avant = [list(m) for m in murs]
        murs = [affiner_mur(gris, m) for m in murs]
        decalages = [abs(_sur_le_mur((a[0] + a[2]) / 2, (a[1] + a[3]) / 2, b)[0]) for a, b in zip(avant, murs)]
        infos["recalage_px_moyen"] = round(float(np.mean(decalages)), 2) if decalages else 0.0
    indice_mur = {m.id: k for k, m in enumerate(fiche.murs)}

    # 2. Le bâti, puis les zones libres : une pièce = la zone fermée par les murs autour du point donné par Claude.
    bati = _bati(murs, (H, W))
    n, etiq = cv2.connectedComponents((bati == 0).astype(np.uint8), connectivity=4)
    au_bord = set(np.unique(np.concatenate([etiq[0], etiq[-1], etiq[:, 0], etiq[:, -1]])).tolist())
    zones: list[tuple[str, str, np.ndarray, bool]] = []  # (id Claude, type, masque, contour donné par Claude)
    prises: dict[int, int] = {}
    partages: dict[int, list[int]] = {}  # zone → pièces (indices dans zones) qui se la partagent
    contours_lus: dict[int, list] = {}  # indice dans zones → contour donné par la lecture (pixels du plan)
    for p in fiche.pieces:
        x, y = p.point[0] / f, p.point[1] / f
        u, v = min(max(int(round(x)), 0), W - 1), min(max(int(round(y)), 0), H - 1)
        z = int(etiq[v, u])
        contour_claude = [(a / f, b / f) for a, b in p.contour] if p.contour else None
        ici = _autour(x, y, 15)
        if z == 0 or z in au_bord:
            if contour_claude:
                zones.append((p.id, p.type, _polygone(contour_claude, (H, W)) & (bati == 0), True))
                autres.append(_doute("piece_ouverte", f"{p.nom or NOM_PIECE[p.type]} : les murs lus ne la ferment pas, "
                                     "contour donné par la lecture", "faible", p.id, ici))
            else:
                pourquoi = "son point tombe sur un mur" if z == 0 else "les murs lus ne la ferment pas (mur ou porte manquant ?)"
                autres.append(_doute("piece_ouverte", f"{p.nom or NOM_PIECE[p.type]} non construite : {pourquoi}", "fort",
                                     None, ici))
            continue
        if z in prises:
            k = prises[z]
            if contour_claude:  # même zone, mais la lecture sépare les pièces : la zone sera partagée entre elles (plus bas)
                zones.append((p.id, p.type, etiq == z, True))
                contours_lus[len(zones) - 1] = contour_claude
                partages.setdefault(z, [k]).append(len(zones) - 1)
            else:  # même zone, sans cloison entre elles (cuisine ouverte…) : une seule pièce
                premiere = next(q for q in fiche.pieces if q.id == zones[k][0])
                autres.append(_doute("pieces_reunies", f"{p.nom or NOM_PIECE[p.type]} et {premiere.nom or NOM_PIECE[premiere.type]} "
                                     "sans mur entre elles : réunies en une seule pièce", "faible", zones[k][0], ici))
            continue
        prises[z] = len(zones)
        zones.append((p.id, p.type, etiq == z, bool(contour_claude)))
        if contour_claude:
            contours_lus[len(zones) - 1] = contour_claude

    # Une zone fermée que la lecture partage entre plusieurs pièces (cuisine ouverte sur le séjour…) est découpée entre elles,
    # sans trou ni recouvrement : chaque point va à la pièce dont le contour lu le contient, sinon à la plus proche (B1 ; avant,
    # la première pièce gardait toute la zone : fr-031, le séjour recouvrait la cuisine, deux sols au même endroit, rendus noirs).
    for z, membres in partages.items():
        _partager(zones, membres, etiq == z, contours_lus)

    # Jamais deux pièces au même endroit (deux sols superposés : la 3D les rend noirs) : une pièce perd ce qu'une pièce lue
    # avant elle occupe déjà (un contour donné par la lecture peut déborder sur la pièce voisine).
    deja = np.zeros((H, W), bool)
    for i, (pid, ptype, masque_i, c_i) in enumerate(zones):
        zones[i] = (pid, ptype, masque_i & ~deja, c_i)
        deja |= zones[i][2]

    # 3. Le « coloriage de Claude » (classes du U-Net), réduit comme l'image que colorie Atelya.
    masque = bati.copy() * MUR
    for _, type_, zone, _ in zones:
        masque[zone] = CLASSE_PIECE[type_]
    porteurs = []
    for o in fiche.ouvertures:
        bords = [v / f for v in o.bords]
        k = _mur_porteur(bords, murs, indice_mur.get(o.mur) if o.mur else None)
        porteurs.append(k)
        if k is not None:
            cv2.line(masque, (int(round(bords[0])), int(round(bords[1]))), (int(round(bords[2])), int(round(bords[3]))),
                     CLASSE_OUVERTURE[o.type], max(1, int(round(murs[k][4]))))
    r = COTE_ATELYA / max(W, H)
    taille_col = (max(1, round(W * r)), max(1, round(H * r)))
    col = cv2.resize(masque, taille_col, interpolation=cv2.INTER_NEAREST)
    rc = col.shape[1] / W  # pixels du plan → pixels du coloriage

    # 4. L'échelle à deux clés.
    textes = source.textes if source.textes is not None else _textes(fiche, f)
    e = lire_echelle_plan(gris, col, None, angle=0.0, textes=textes, px_par_pt=source.px_par_pt, blocs=False)
    lx, ly, origine = decider(e.largeur, e.hauteur, e.sure, e.cote_max_largeur, e.cote_max_hauteur, e.interieur_px, False,
                              e.barre if e.barre_sure else None, e.surfaces if e.surfaces_sure else None, False,
                              e.approchee, False, e.surfaces, ecrite=e.ecrite, ambigue=e.ambigue, plusieurs_blocs=False)
    cle_atelya = lx or ly  # px du coloriage par m
    if not cle_atelya:  # pas de trait de cote, de barre ni de surface : les dimensions écrites dans les pièces, mesurées entre les murs
        entre_murs, n_entre, detail_entre = _cotes_entre_murs(gris, fiche, f)
        infos["cotes_entre_murs"] = detail_entre
        if entre_murs and n_entre >= COTES_ENTRE_MURS_MIN and _taille_vraisemblable(entre_murs * rc, e.interieur_px):
            cle_atelya, origine = entre_murs * rc, f"{n_entre} dimensions de pièces mesurées entre les murs du dessin"
    prop = fiche.echelle_proposee.px_par_m
    cle_claude = prop / f * rc if prop else None
    cotes_claude, cotes_accord = _echelle_des_cotes(fiche, f)
    cotes_claude = cotes_claude * rc if cotes_claude else None
    detail = {"atelya": cle_atelya, "atelya_source": origine, "atelya_sure": bool(e.sure), "contredite": e.contredite,
              "ambigue": e.ambigue, "cotes_atelya": [[c.valeur, round(c.px_par_m, 2)] for c in e.cotes],
              "surfaces_px_par_m": e.surfaces, "ecrite": e.ecrite_detail or None,
              "claude": cle_claude, "claude_source": fiche.echelle_proposee.source,
              "claude_explication": fiche.echelle_proposee.explication,
              "cotes_claude": cotes_claude, "cotes_claude_accord": cotes_accord, "unite": "px du coloriage par m"}
    if cle_atelya and cle_claude:
        detail["ecart_deux_cles"] = round(cle_claude / cle_atelya - 1, 4)
    if cle_atelya and cle_claude and abs(cle_claude / cle_atelya - 1) <= ACCORD_DEUX_CLES:
        s_col, etat, source_ech = cle_atelya, "lue", f"{origine} ; confirmée par l'échelle de la lecture de Claude"
    elif cle_atelya and cle_claude:
        s_col, etat = cle_atelya, "a_verifier"
        source_ech = f"{origine} ; en désaccord avec l'échelle de la lecture de Claude"
        autres.append(_doute("echelle_desaccord", f"Échelle à vérifier : celle retrouvée sur le dessin ({origine}) et celle de la "
                             f"lecture de Claude diffèrent de {100 * abs(cle_claude / cle_atelya - 1):.0f} %. "
                             "Vérifie une cote pour tout recaler.", "fort"))
    elif cle_atelya:
        s_col, etat, source_ech = cle_atelya, "lue", f"{origine} (la lecture de Claude n'a pas proposé d'échelle)"
    else:
        if cotes_claude and cotes_accord >= 2 and _taille_vraisemblable(cotes_claude, e.interieur_px):
            s_col, comment = cotes_claude, f"tirée de {cotes_accord} cotes lues par Claude, non retrouvées sur le dessin"
        elif cle_claude and _taille_vraisemblable(cle_claude, e.interieur_px):
            s_col, comment = cle_claude, f"proposée par la lecture de Claude ({fiche.echelle_proposee.source})"
        else:
            s_col, comment = _echelle_de_secours(e, col.shape)
        etat, source_ech = "a_verifier", None
        autres.append(_doute("echelle", f"Échelle non retrouvée sur le dessin : les mesures sont provisoires ({comment}). "
                             "Corrige une cote pour tout recaler.", "fort"))
    echelle = {"etat": etat, "source": source_ech, "px_par_m_largeur": s_col, "px_par_m_hauteur": s_col,
               "cotes": len(e.cotes), "detail": detail}
    if etat != "lue":
        echelle["provisoire"] = s_col
        echelle["raison"] = autres[-1]["raison"] if autres and autres[-1]["code"].startswith("echelle") else ""
    s = s_col / rc  # px du plan par m

    # 5. Le logement, en mètres (origine : coin sud-ouest de l'intérieur).
    if not zones:
        return _refus(source, "aucune pièce fermée dans la lecture de Claude", echelle, masque)
    interieur = np.zeros((H, W), bool)
    for _, _, zone, _ in zones:
        interieur |= zone
    ys, xs = np.nonzero(interieur)
    ox, oy = float(xs.min()), float(ys.max() + 1)

    def m_(u: float, v: float) -> list[float]:
        return [round((u - ox) / s, 3), round((oy - v) / s, 3)]

    ids_murs: dict[str, str] = {}
    sortie_murs = []
    for k, (x0, y0, x1, y1, ep) in enumerate(murs):
        if abs(x1 - x0) >= abs(y1 - y0):  # d'ouest en est
            (x0, y0), (x1, y1) = sorted([(x0, y0), (x1, y1)])
        else:  # du sud (bas de l'image) au nord
            (x0, y0), (x1, y1) = sorted([(x0, y0), (x1, y1)], key=lambda p: -p[1])
        murs[k] = [x0, y0, x1, y1, ep]
        ident = f"M{k + 1}"
        ids_murs[fiche.murs[k].id] = ident
        sortie_murs.append({"id": ident, "debut": m_(x0, y0), "fin": m_(x1, y1), "epaisseur": round(ep / s, 3),
                            "statut": "estime", "source": "lecture_claude"})
    hsp = float(e.hauteur_sous_plafond or HAUTEUR_SOUS_PLAFOND)
    ids_ouv: dict[str, str] = {}
    sortie_ouv = []
    for o, k in zip(fiche.ouvertures, porteurs):
        bords = [v / f for v in o.bords]
        if k is None:
            autres.append(_doute("ouverture_hors_mur", f"{o.type.replace('_', '-')} lue hors de tout mur : non construite", "fort",
                                 None, _autour((bords[0] + bords[2]) / 2, (bords[1] + bords[3]) / 2, 15)))
            continue
        x0, y0, x1, y1, _ = murs[k]
        Lm = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / Lm, (y1 - y0) / Lm
        t0 = (bords[0] - x0) * ux + (bords[1] - y0) * uy
        t1 = (bords[2] - x0) * ux + (bords[3] - y0) * uy
        a, b = sorted((t0, t1))
        debord = (max(0.0, -a) + max(0.0, b - Lm)) / s
        a, b = max(0.0, a), min(Lm, b)
        ident = f"O{len(sortie_ouv) + 1}"
        if b - a <= 0:
            autres.append(_doute("ouverture_hors_mur", f"{o.type.replace('_', '-')} au-delà du bout de son mur : non construite",
                                 "fort", fiche.murs[k].id, _autour((bords[0] + bords[2]) / 2, (bords[1] + bords[3]) / 2, 15)))
            continue
        if debord > DEBORD_OUVERTURE_M:
            autres.append(_doute("ouverture_debord", f"{o.type.replace('_', '-')} lue au-delà du bout de son mur "
                                 f"({100 * debord:.0f} cm) : raccourcie", "faible", o.id))
        largeur = (b - a) / s
        if o.type == "porte":
            hauteur, allege = HAUTEUR_PORTE, 0.0
        elif o.type == "porte_fenetre":
            hauteur, allege = HAUTEUR_PORTE_FENETRE, 0.0
        else:
            haut = min(hsp - 0.15, HAUT_FENETRE)
            hauteur = 0.60 if largeur <= 0.65 else 1.25
            allege = haut - hauteur
        ids_ouv[o.id] = ident
        sortie_ouv.append({"id": ident, "type": o.type, "mur": ids_murs[fiche.murs[k].id], "position": round(a / s, 3),
                           "largeur": round(largeur - 1e-6, 3), "hauteur": round(min(hauteur, hsp), 3), "allege": round(allege, 3),
                           "statut": "estime", "source": "lecture_claude"})
    noms_claude = {p.id: p.nom for p in fiche.pieces}
    ids_pieces: dict[str, str] = {}
    sortie_pieces, types, noms_lus = [], {}, []
    occupees = np.zeros((H, W), bool)
    for _, _, zone, _ in zones:
        occupees |= zone
    for pid, type_, zone, _ in zones:
        contour = _contour(zone, occupees & ~zone)
        if contour is None:
            autres.append(_doute("piece_ouverte", f"{noms_claude[pid] or NOM_PIECE[type_]} : contour introuvable", "fort"))
            continue
        ident = f"{type_}_{sum(1 for t in types.values() if t == type_) + 1}"
        ids_pieces[pid] = ident
        sortie_pieces.append({"id": ident, "nom": noms_claude[pid] or NOM_PIECE[type_], "contour": [m_(u, v) for u, v in contour],
                              "statut": "estime", "source": "lecture_claude"})
        types[ident] = type_
        if noms_claude[pid]:
            noms_lus.append(ident)
    logement = {"schema": "logement/0.1", "projet_id": projet_id, "unites": "m", "hauteur_sous_plafond": hsp,
                "murs": sortie_murs, "ouvertures": sortie_ouv, "pieces": sortie_pieces}
    try:
        Logement.model_validate(logement)
    except Exception as err:  # noqa: BLE001 — un logement incohérent est un résultat (refusé), pas un plantage
        return _refus(source, f"logement incohérent : {str(err)[:200]}", echelle, masque)

    # 6. Les doutes venus de la fiche et de Claude, avec les noms du logement, puis ce que Claude affirme contrôlé contre le dessin.
    ids = {**ids_murs, **ids_ouv, **ids_pieces}
    for d in autres:  # les doutes écrits jusqu'ici désignent les éléments par leur id dans la fiche de Claude
        d["element"] = ids.get(d["element"]) if d.get("element") else None
    autres += doutes_des_textes(fiche, f, gris, source.textes, ocr=ocr)
    if etat == "lue":  # sans échelle lue, chaque cote et chaque surface seraient accusées à tort
        autres += doutes_des_cotes(fiche, f, s, e.cotes, ids)
        autres += doutes_des_surfaces(fiche, f, logement, ids, lambda u, v: m_(u, v))
    for p in controlee.problemes:  # seuls les « doute » arrivent ici (un « refus » a déjà arrêté la traduction)
        autres.append(_doute(p.code, p.raison, "fort", ids.get(p.element), _xywh(p.cadre, f) if p.cadre else None))
    for d in fiche.doutes:
        autres.append(_doute("claude", f"Lecture de Claude : {d.raison}", d.gravite, ids.get(d.element),
                             _xywh(d.cadre, f) if d.cadre else None))
    if fiche.autres_niveaux:
        autres.append(doute_plusieurs_niveaux([_xywh(n.cadre, f) for n in fiche.autres_niveaux]))
    details = {"px_par_m": s, "origine_px": [ox, oy], "angle_deg": 0.0, "types_pieces": types, "pieces_nom_lu": noms_lus,
               "ids_claude": ids}
    examen = examiner(logement, details, autres=autres)
    lecture = Lecture(MODELE, logement, details, examen, echelle, None, masque, None, infos)
    return PlanLu(source, lecture, {MODELE: lecture}, "lecture de Claude")
