"""Remettre à plat un plan photographié de biais, avant de le traduire en mesures.

Quand on photographie un plan posé sur une table, le téléphone n'est jamais pile
au-dessus : la page apparaît en trapèze (la perspective). Sur l'image, les murs
qui sont parallèles en vrai ne le sont plus : les murs « horizontaux » se
rapprochent tous vers un même point au loin, les murs « verticaux » vers un autre.
Ces deux points s'appellent les points de fuite.

Le traducteur (moteur.coloriage) ne sait lire que des murs bien horizontaux et
verticaux. Ce module retrouve la déformation et la défait, sans rien apprendre,
par la géométrie seule (OpenCV et numpy) :

1. relever les bords droits des murs sur le coloriage d'Atelya ;
2. les ranger en deux familles (« horizontaux » et « verticaux ») ;
3. trouver le point de fuite de chaque famille (là où les bords se croisent) ;
4. calculer la transformation (une « homographie », matrice 3×3) qui renvoie ces
   deux points à l'infini : les murs redeviennent parallèles, horizontaux et verticaux ;
5. recommencer une fois sur l'image redressée pour gommer le petit reste.

Ce qu'un plan de biais ne dit pas seul : le rapport entre l'échelle en largeur et
celle en hauteur (une photo peut « écraser » un peu la page dans un sens). Ce rapport
vient des cotes, lues séparément en largeur et en hauteur. Sans cotes, on garde
l'échelle de la photo autour de son centre, qui est juste à quelques pour cent près.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

VERSION_REDRESSEMENT = "0.1.0"

MUR, PORTE_FENETRE = 1, 4
FOND = 0

LONGUEUR_MIN_BORD = 12  # pixels : un bord plus court ne dit pas grand-chose de sa direction
ECART_FAMILLE = 20.0  # degrés : un bord penché de plus que ça par rapport aux deux familles est ignoré
ECART_ABERRANT = 2.0  # degrés : après une première estimation, un bord qui s'en écarte plus est ignoré
AGRANDISSEMENT_MAX = 2.5  # au-delà, le redressement est jugé faux et on ne l'applique pas
# En dessous de cette déformation (fraction du grand côté), la page est vue de face : les petits défauts
# du coloriage d'Atelya feraient croire à une perspective qui n'existe pas, la simple rotation suffit.
SEUIL_DEFORMATION = 0.012


@dataclass
class Redressement:
    """La transformation trouvée : pixels de l'image d'origine → pixels de l'image redressée."""

    H: np.ndarray
    taille: tuple[int, int]  # (largeur, hauteur) de l'image redressée
    bords: int  # nombre de bords de murs utilisés
    perspective: float  # force de la perspective trouvée (0 : aucune)
    angle_deg: float  # inclinaison d'ensemble trouvée
    deformation: float = 0.0  # écart à une simple rotation, en fraction du grand côté (0 : page vue de face)

    @property
    def de_biais(self) -> bool:
        """Vrai si la page a été vue de biais (pas seulement penchée) : le redressement vaut la peine."""
        return self.deformation >= SEUIL_DEFORMATION

    def appliquer(self, image: np.ndarray, lineaire: bool = False) -> np.ndarray:
        """L'image redressée (plus proche voisin par défaut : les numéros de classe restent entiers)."""
        mode = cv2.INTER_LINEAR if lineaire else cv2.INTER_NEAREST
        return cv2.warpPerspective(image, self.H, self.taille, flags=mode,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=FOND)

    def point(self, u: float, v: float) -> tuple[float, float]:
        x, y, w = self.H @ (u, v, 1.0)
        return float(x / w), float(y / w)


# ---------------------------------------------------------------- 1. les bords droits

def _douglas_peucker(pts: np.ndarray, i0: int, i1: int, eps: float, sortie: list[int]) -> None:
    """Indices des sommets d'une ligne brisée qui suit pts[i0..i1] à eps pixels près."""
    pile = [(i0, i1)]
    while pile:
        a, b = pile.pop()
        if b - a < 2:
            continue
        p, q = pts[a], pts[b]
        d = q - p
        n = math.hypot(*d)
        seg = pts[a + 1:b]
        if n < 1e-9:
            dist = np.hypot(*(seg - p).T)
        else:
            dist = np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / n
        k = int(np.argmax(dist))
        if dist[k] > eps:
            m = a + 1 + k
            sortie.append(m)
            pile += [(a, m), (m, b)]


def bords_droits(masque: np.ndarray, longueur_min: float = LONGUEUR_MIN_BORD) -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Les bords droits d'un masque : [(point de départ, point d'arrivée, longueur)], en pixels."""
    m = masque.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    bords = []
    for c in contours:
        if len(c) < 2 * longueur_min:
            continue
        pts = c[:, 0, :].astype(np.float64)
        # Un contour est fermé : on le coupe au point le plus éloigné du premier pour le traiter en deux moitiés.
        loin = int(np.argmax(np.hypot(*(pts - pts[0]).T)))
        sommets = [0, loin, len(pts) - 1]
        _douglas_peucker(pts, 0, loin, 1.5, sommets)
        _douglas_peucker(pts, loin, len(pts) - 1, 1.5, sommets)
        sommets = sorted(set(sommets))
        for a, b in zip(sommets, sommets[1:]):
            if math.dist(pts[a], pts[b]) < longueur_min:
                continue
            # Les deux bouts sont des coins arrondis par les pixels : on les laisse de côté.
            garde = max(1, (b - a) // 10)
            morceau = pts[a + garde:b - garde + 1]
            if len(morceau) < 4:
                continue
            vx, vy, x0, y0 = cv2.fitLine(morceau.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()
            d = np.array([vx, vy], np.float64)
            o = np.array([x0, y0], np.float64)
            t = (morceau - o) @ d
            p, q = o + t.min() * d, o + t.max() * d
            bords.append((p, q, float(t.max() - t.min())))
    return bords


# ---------------------------------------------------------------- 2-3. familles et points de fuite

def _angle(p: np.ndarray, q: np.ndarray) -> float:
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))


def _ecart(a: float, b: float) -> float:
    """Écart entre deux directions (degrés), sans tenir compte du sens : entre 0 et 90."""
    d = (a - b) % 180.0
    return min(d, 180.0 - d)


def angle_dominant(bords) -> float:
    """L'inclinaison d'ensemble (degrés, entre -45 et 45) : la médiane pondérée des directions, modulo 90°."""
    if not bords:
        return 0.0
    a = np.array([((_angle(p, q) + 45.0) % 90.0) - 45.0 for p, q, _ in bords])
    w = np.array([n for _, _, n in bords])
    # Moyenne « circulaire » sur des angles modulo 90° (multipliés par 4 pour faire un tour complet).
    c = (w * np.cos(np.radians(4 * a))).sum()
    s = (w * np.sin(np.radians(4 * a))).sum()
    return float(math.degrees(math.atan2(s, c)) / 4)


def _point_de_fuite(lignes: np.ndarray, poids: np.ndarray) -> np.ndarray:
    """Le point (homogène) le plus proche de toutes les lignes : il annule au mieux l·v."""
    M = (lignes * poids[:, None]).T @ lignes
    _, vecteurs = np.linalg.eigh(M)
    return vecteurs[:, 0]


def _lignes(bords, T: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ls, ws = [], []
    for p, q, n in bords:
        a = T @ (p[0], p[1], 1.0)
        b = T @ (q[0], q[1], 1.0)
        l = np.cross(a, b)
        k = math.hypot(l[0], l[1])
        if k > 1e-12:
            ls.append(l / k)
            ws.append(n * n)
    return np.array(ls), np.array(ws)


def _ecart_au_point(bord, v: np.ndarray, T: np.ndarray) -> float:
    """Écart (degrés) entre un bord et la direction qui va de son milieu au point de fuite v."""
    p, q, _ = bord
    a = T @ (p[0], p[1], 1.0)
    b = T @ (q[0], q[1], 1.0)
    m = (a + b) / 2
    d_bord = b[:2] - a[:2]
    # direction vers v (en homogène : v_xy - m_xy * v_w)
    d_v = v[:2] * m[2] - m[:2] * v[2]
    if np.hypot(*d_v) < 1e-12:
        return 90.0
    c = abs(d_bord @ d_v) / (np.hypot(*d_bord) * np.hypot(*d_v))
    return math.degrees(math.acos(min(1.0, c)))


def points_de_fuite(bords, forme: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, int, float] | None:
    """(point de fuite des « horizontaux », des « verticaux », bords utilisés, angle dominant),
    dans le repère normalisé (centre de l'image en 0, demi-grand côté = 1)."""
    h, w = forme
    k = 2.0 / max(h, w)
    T = np.array([[k, 0, -k * w / 2], [0, k, -k * h / 2], [0, 0, 1]], np.float64)
    a0 = angle_dominant(bords)
    familles = [[b for b in bords if _ecart(_angle(b[0], b[1]), a0 + 90 * i) < ECART_FAMILLE] for i in (0, 1)]
    if any(sum(n for _, _, n in f) < 3 * LONGUEUR_MIN_BORD or len(f) < 2 for f in familles):
        return None
    vs = []
    for f in familles:
        l, wts = _lignes(f, T)
        v = _point_de_fuite(l, wts)
        # Une deuxième fois sans les bords aberrants (un coin mal coupé, une tache d'Atelya).
        bons = [b for b in f if _ecart_au_point(b, v, T) < ECART_ABERRANT]
        if len(bons) >= 2:
            l, wts = _lignes(bons, T)
            v = _point_de_fuite(l, wts)
        vs.append(v)
    return vs[0], vs[1], sum(len(f) for f in familles), a0


# ---------------------------------------------------------------- 4. l'homographie

def _homographie(v1: np.ndarray, v2: np.ndarray, forme: tuple[int, int]) -> np.ndarray | None:
    """Pixels → pixels redressés : v1 part à l'infini à l'horizontale, v2 à la verticale ;
    l'échelle est gardée au centre de l'image, dans chaque direction."""
    h, w = forme
    k = 2.0 / max(h, w)
    T = np.array([[k, 0, -k * w / 2], [0, k, -k * h / 2], [0, 0, 1]], np.float64)
    e3 = np.array([0.0, 0.0, 1.0])
    l_inf = np.cross(v1, v2)  # la « ligne d'horizon » de la page
    if abs(l_inf[2]) < 1e-12:
        return None
    l_inf = l_inf / l_inf[2]  # vaut 1 au centre de l'image
    r1 = np.cross(v2, e3)  # nul sur v2 : les « verticaux » gardent un x constant
    r2 = np.cross(v1, e3)  # nul sur v1 : les « horizontaux » gardent un y constant
    if np.hypot(*r1[:2]) < 1e-12 or np.hypot(*r2[:2]) < 1e-12:
        return None
    Hn = np.array([r1, r2, l_inf])
    # Au centre (0, 0, 1) : x' = r1[2], y' = r2[2]. On ramène le centre en 0 et la pente à 1, dans le bon sens.
    J = Hn[:2, :2] - np.outer(Hn[:2, 2], Hn[2, :2])  # dérivée de (x', y') au centre
    if abs(J[0, 0]) < abs(J[0, 1]):  # la famille « horizontale » est plus proche de la verticale : on échange
        Hn, J = Hn[[1, 0, 2]], J[[1, 0]]
    sx, sy = np.hypot(*J[0]), np.hypot(*J[1])
    if sx < 1e-12 or sy < 1e-12 or abs(np.linalg.det(J)) < 1e-6 * sx * sy:
        return None
    # Le sens : x' croît vers la droite, y' vers le bas, comme sur la photo.
    signe_x = 1.0 if J[0, 0] >= 0 else -1.0
    signe_y = 1.0 if J[1, 1] >= 0 else -1.0
    S = np.array([[signe_x / sx, 0, -signe_x * Hn[0, 2] / sx],
                  [0, signe_y / sy, -signe_y * Hn[1, 2] / sy],
                  [0, 0, 1]])
    # Le résultat est en unités normalisées : on revient aux pixels (1 pixel au centre = 1 pixel).
    return np.linalg.inv(T) @ S @ Hn @ T


def _cadrer(H: np.ndarray, forme: tuple[int, int], masque: np.ndarray | None = None,
            marge: int = 4) -> tuple[np.ndarray, tuple[int, int]] | None:
    """Décale H pour que tout le contenu redressé tombe dans l'image, avec une petite marge."""
    h, w = forme
    if masque is not None and masque.any():
        ys, xs = np.nonzero(masque)
        pts = np.array([[xs.min(), ys.min()], [xs.max() + 1, ys.min()], [xs.max() + 1, ys.max() + 1], [xs.min(), ys.max() + 1]],
                       np.float64)
    else:
        pts = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64)
    # Le contenu doit rester devant la « ligne d'horizon » (sinon la page se retournerait).
    hom = np.c_[pts, np.ones(len(pts))] @ H.T
    if (hom[:, 2] <= 0).any():
        return None
    xy = hom[:, :2] / hom[:, 2:]
    x0, y0 = xy.min(0) - marge
    x1, y1 = xy.max(0) + marge
    W, Hh = int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))
    if W * Hh > (AGRANDISSEMENT_MAX ** 2) * w * h or W <= 0 or Hh <= 0:
        return None
    D = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64)
    return D @ H, (W, Hh)


def _deformation(H: np.ndarray, forme: tuple[int, int]) -> float:
    """De combien (fraction du grand côté) les coins de l'image s'écartent d'une simple rotation + échelle."""
    h, w = forme
    c = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = np.c_[c, np.ones(4)] @ H.T
    d = (d[:, :2] / d[:, 2:]).astype(np.float32)
    S, _ = cv2.estimateAffinePartial2D(c, d)
    if S is None:
        return 1.0
    e = np.hypot(*((np.c_[c, np.ones(4)] @ S.T) - d).T).max() / np.hypot(*S[:, 0])
    return float(e / max(h, w))


def _force_perspective(H: np.ndarray, forme: tuple[int, int]) -> float:
    """Combien l'échelle varie d'un bord à l'autre de l'image (0 : pas de perspective)."""
    h, w = forme
    g = H[2, :2] / H[2, 2] if abs(H[2, 2]) > 1e-12 else H[2, :2]
    return float(abs(g[0]) * w + abs(g[1]) * h)


# ---------------------------------------------------------------- 5. l'ensemble

def bati_du_coloriage(coloriage: np.ndarray) -> np.ndarray:
    """Murs, portes et fenêtres reliés au logement : ce qui dessine les lignes droites du plan.
    Les taches isolées (flèche du Nord, barre d'échelle, erreurs d'Atelya) sont jetées, et les bords
    sont lissés : un bord en dents de scie fausserait sa direction."""
    bati = ((coloriage >= MUR) & (coloriage <= PORTE_FENETRE)).astype(np.uint8)
    bati = cv2.medianBlur(bati * 255, 5) > 127
    n, etiq, stats, _ = cv2.connectedComponentsWithStats(bati.astype(np.uint8), connectivity=8)
    if n <= 1:
        return bati
    principal = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    garde = np.zeros(n, bool)
    garde[principal] = True
    # Les autres morceaux assez grands (un mur coupé en deux par Atelya) sont gardés aussi.
    garde[1:] |= stats[1:, cv2.CC_STAT_AREA] >= 0.05 * stats[principal, cv2.CC_STAT_AREA]
    return garde[etiq]


def estimer_redressement(coloriage: np.ndarray, passes: int = 2) -> Redressement | None:
    """La transformation qui remet le plan à plat (murs horizontaux et verticaux), ou None
    si le coloriage n'a pas assez de murs droits pour la trouver."""
    bati = bati_du_coloriage(coloriage)
    forme = bati.shape
    H = np.eye(3)
    masque = bati.astype(np.uint8)
    taille = (forme[1], forme[0])
    nb, angle0 = 0, None
    for _ in range(passes):
        bords = bords_droits(masque)
        r = points_de_fuite(bords, masque.shape)
        if r is None:
            break
        v1, v2, nb, a0 = r
        if angle0 is None:
            angle0 = a0
        Hk = _homographie(v1, v2, masque.shape)
        if Hk is None:
            break
        cadre = _cadrer(Hk @ H, forme, bati)
        if cadre is None:
            break
        H, taille = cadre
        masque = cv2.warpPerspective(bati.astype(np.uint8), H, taille, flags=cv2.INTER_NEAREST)
    if nb == 0:
        return None
    return Redressement(H=H, taille=taille, bords=nb, perspective=_force_perspective(H, forme),
                        angle_deg=float(angle0 or 0.0), deformation=_deformation(H, forme))


def corriger_proportions(r: Redressement, rapport: float) -> Redressement:
    """Étire la hauteur de l'image redressée par `rapport` (= échelle en largeur / échelle en hauteur,
    donnée par les cotes) : un mètre fait alors le même nombre de pixels dans les deux sens."""
    S = np.diag([1.0, rapport, 1.0])
    w, h = r.taille
    return Redressement(H=S @ r.H, taille=(w, int(math.ceil(h * rapport))), bords=r.bords,
                        perspective=r.perspective, angle_deg=r.angle_deg, deformation=r.deformation)

