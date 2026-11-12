"""OÙ la caméra peut passer : la grille du logement (murs, fenêtres, meubles hauts, battants des portes ouvertes = obstacles),
les portes ouvertes pour la visite, la porte palière, le plus court chemin (Dijkstra) et le point de départ dans l'entrée."""
from __future__ import annotations

import heapq
import math

import cv2
import numpy as np

from moteur import realisateur as rz
from moteur.cinema.reglages import BATTANT_EP, CIRCULATION, CONFORT_M, MARGE_M, PAS_M, SOUS_OBJET_M, SURVOL_MARGE_M


def _hauteur_meuble(m: dict) -> float:
    d = m.get("dimensions") or []
    return float(d[2]) if len(d) > 2 else 1.0


def etendue(m: dict) -> tuple[float, float]:
    """Le bas et le haut d'un meuble (m) : posé au sol, ou accroché en l'air (`altitude` = son bas : meuble haut de cuisine,
    étagère, suspension)."""
    bas = float(m.get("altitude") or 0.0)
    return bas, bas + _hauteur_meuble(m)


def au_dessus_du_vol(m: dict, hauteur_camera: float) -> bool:
    """L'objet est suspendu assez haut pour que la caméra passe DESSOUS (en descendant un peu si besoin)."""
    return etendue(m)[0] >= hauteur_camera + SOUS_OBJET_M


def bloque_le_vol(m: dict, hauteur_camera: float) -> bool:
    """Le meuble est un obstacle pour la caméra volante : trop haut pour être survolé, trop bas pour passer dessous (un meuble
    haut de cuisine de 1,40 à 2,10 m, une armoire). Avant le 12/11/2026, seule la hauteur comptait : un meuble haut accroché
    au mur passait pour un meuble bas, et la caméra l'aurait traversé."""
    return etendue(m)[1] > hauteur_camera - SURVOL_MARGE_M and not au_dessus_du_vol(m, hauteur_camera)


def _rect(centre_a, centre_b, ep):
    return rz._rectangle(centre_a, centre_b, ep)


def _cotes(logement: dict, o: dict):
    """Les deux pièces de part et d'autre d'une ouverture (None = dehors), et le repère du mur."""
    m = next(m for m in logement["murs"] if m["id"] == o["mur"])
    a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
    d = (b - a) / np.linalg.norm(b - a)
    milieu = a + d * (o["position"] + o["largeur"] / 2)
    n = np.array([-d[1], d[0]])
    cotes = [next((p for p in logement["pieces"] if rz._dedans(tuple(milieu + n * s * (m["epaisseur"] / 2 + 0.15)),
                                                                p["contour"])), None) for s in (1, -1)]
    return cotes, a, d, n, m


def portes_ouvertes(logement: dict, visitees: set | None = None) -> list[dict]:
    """Les portes OUVERTES pour la balade, comme un agent qui prépare une visite : seulement celles entre deux pièces visitées
    ou de circulation (entrée, dégagement) ; placards, WC, pièces non visitées et porte palière restent fermés. Le battant
    s'ouvre à 90° VERS L'INTÉRIEUR de la pièce (jamais dans le couloir ; entre deux pièces, dans la plus petite), sauf si le
    sens est donné (ouverture.sens). Renvoie gonds, angle de rotation (degrés, sens trigonométrique du plan) et le rectangle
    occupé par le battant ouvert."""
    sortie = []
    for o in logement.get("ouvertures", []):
        if o["type"] != "porte":
            continue
        (gauche_p, droite_p), a, d, n_gauche, m = _cotes(logement, o)
        if gauche_p is None or droite_p is None:
            continue  # porte palière ou porte vers dehors
        if visitees is not None and not all(p["id"] in visitees or rz._type(p) in CIRCULATION for p in (gauche_p, droite_p)):
            continue
        sens = o.get("sens") or {}
        au_debut = sens.get("charniere", "debut") == "debut"
        if "ouvre_vers" in sens:
            gauche = sens["ouvre_vers"] == "gauche"
        else:
            def rang(p):  # la pièce où s'ouvre la porte : pas une circulation, la plus petite
                return (rz._type(p) in CIRCULATION, rz._aire(p["contour"]))
            gauche = rang(gauche_p) < rang(droite_p)
        s = o["position"] if au_debut else o["position"] + o["largeur"]
        gond = a + d * s
        vers = n_gauche if gauche else -n_gauche
        ferme = d if au_debut else -d
        angle = math.degrees(math.atan2(ferme[0] * vers[1] - ferme[1] * vers[0], float(np.dot(ferme, vers))))
        bout = gond + vers * o["largeur"]
        sortie.append({"id": o["id"], "gond": [round(float(gond[0]), 4), round(float(gond[1]), 4)],
                       "angle_deg": round(angle, 1), "vers": (gauche_p if gauche else droite_p)["id"],
                       "battant": _rect(gond + vers * 0.03, bout, BATTANT_EP)})
    return sortie


def porte_palliere(logement: dict) -> str | None:
    """La porte d'entrée du logement : une porte du pourtour de l'entrée qui ne donne sur aucune autre pièce."""
    entree = next((p for p in logement["pieces"] if rz._type(p) == "entree"), None)
    for o in logement.get("ouvertures", []):
        if o["type"] != "porte":
            continue
        cotes = [p["id"] if p else None for p in _cotes(logement, o)[0]]
        if entree and entree["id"] in cotes and None in cotes:
            return o["id"]
    return None


class Carte:
    """La grille où l'on peut passer, et le plus court chemin (Dijkstra, 8 voisins, coût plus fort près des obstacles)."""

    def __init__(self, logement: dict, portes: list[dict], hauteur_camera: float | None = None):
        scene = rz.Scene2D(logement, portes_fermees=False)  # le vide des portes ; celles qui restent fermées sont rebouchées plus bas
        murs = {m["id"]: m for m in logement["murs"]}
        pts = np.concatenate([np.asarray(p["contour"], float) for p in logement["pieces"]])
        self.mini = pts.min(0) - 0.5
        maxi = pts.max(0) + 0.5
        self.forme = (int((maxi[1] - self.mini[1]) / PAS_M) + 1, int((maxi[0] - self.mini[0]) / PAS_M) + 1)
        dedans = np.zeros(self.forme, np.uint8)
        for p in logement["pieces"]:
            cv2.fillPoly(dedans, [self._pixels(p["contour"])], 1)
        obstacles = np.zeros(self.forme, np.uint8)
        # les portes ouvertes : le passage (dans l'épaisseur du mur) est praticable, le battant ouvert est un obstacle
        ouvertes = {p["id"] for p in portes}
        for o in logement.get("ouvertures", []):
            if o["type"] == "porte" and o["id"] in ouvertes:
                m = murs[o["mur"]]
                a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
                d = (b - a) / np.linalg.norm(b - a)
                passage = _rect(a + d * o["position"], a + d * (o["position"] + o["largeur"]), m["epaisseur"] + 0.3)
                cv2.fillPoly(dedans, [self._pixels(passage)], 1)
        # un meuble assez bas pour être SURVOLÉ, ou suspendu assez haut pour passer dessous (caméra volante), n'est pas un
        # obstacle ; un meuble accroché à hauteur de caméra (meuble haut de cuisine) en est un
        meubles = [poly for m, poly in scene.meubles if hauteur_camera is None or bloque_le_vol(m, hauteur_camera)]
        for poly in scene.pleins + scene.fenetres + meubles + [p["battant"] for p in portes]:
            cv2.fillPoly(obstacles, [self._pixels(poly)], 1)
        # murs des portes fermées (porte palière) : obstacles
        for o in logement.get("ouvertures", []):
            if o["type"] == "porte" and o["id"] not in ouvertes:
                m = murs[o["mur"]]
                a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
                d = (b - a) / np.linalg.norm(b - a)
                cv2.fillPoly(obstacles, [self._pixels(_rect(a + d * o["position"], a + d * (o["position"] + o["largeur"]),
                                                             m["epaisseur"]))], 1)
        libre = (dedans == 1) & (obstacles == 0)
        self.distance = cv2.distanceTransform(libre.astype(np.uint8), cv2.DIST_L2, 5) * PAS_M
        self.libre = self.distance >= MARGE_M
        self.cout = 1.0 + 2.5 * np.clip((CONFORT_M - self.distance) / CONFORT_M, 0, 1)
        _, self.zones = cv2.connectedComponents(self.libre.astype(np.uint8), connectivity=8)

    def _pixels(self, poly) -> np.ndarray:
        p = np.asarray(poly, float)
        return np.stack([(p[:, 0] - self.mini[0]) / PAS_M, (p[:, 1] - self.mini[1]) / PAS_M], 1).round().astype(np.int32)

    def case(self, xy) -> tuple[int, int]:
        return int(round((xy[1] - self.mini[1]) / PAS_M)), int(round((xy[0] - self.mini[0]) / PAS_M))

    def xy(self, case) -> tuple[float, float]:
        return float(self.mini[0] + case[1] * PAS_M), float(self.mini[1] + case[0] * PAS_M)

    def plus_proche_libre(self, xy, dans=None) -> tuple[int, int]:
        i, j = self.case(xy)
        cases = np.argwhere(self.libre & (dans if dans is not None else True))
        if len(cases) == 0:
            raise ValueError("aucune case libre")
        k = int(np.argmin((cases[:, 0] - i) ** 2 + (cases[:, 1] - j) ** 2))
        return int(cases[k, 0]), int(cases[k, 1])

    def chemin(self, depart, arrivee, malus=None) -> list[tuple[int, int]]:
        h, w = self.forme
        cout = self.cout if malus is None else self.cout + malus
        dist = {depart: 0.0}
        venu = {}
        tas = [(0.0, depart)]
        voisins = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        while tas:
            c, u = heapq.heappop(tas)
            if u == arrivee:
                break
            if c > dist.get(u, math.inf):
                continue
            for di, dj in voisins:
                v = (u[0] + di, u[1] + dj)
                if not (0 <= v[0] < h and 0 <= v[1] < w) or not self.libre[v]:
                    continue
                nc = c + math.hypot(di, dj) * cout[v]
                if nc < dist.get(v, math.inf):
                    dist[v], venu[v] = nc, u
                    heapq.heappush(tas, (nc, v))
        if arrivee not in dist:
            raise ValueError(f"pas de chemin de {self.xy(depart)} à {self.xy(arrivee)}")
        chemin = [arrivee]
        while chemin[-1] != depart:
            chemin.append(venu[chemin[-1]])
        return chemin[::-1]

    def masque_piece(self, piece) -> np.ndarray:
        m = np.zeros(self.forme, np.uint8)
        cv2.fillPoly(m, [self._pixels(piece["contour"])], 1)
        return m.astype(bool)

    def degage(self, xy, marge: float) -> bool:
        """Le point est dans la grille et à au moins `marge` m de tout obstacle."""
        i, j = self.case(xy)
        return 0 <= i < self.forme[0] and 0 <= j < self.forme[1] and self.distance[i, j] >= marge


def distances_depuis(carte: Carte, depart) -> dict:
    """Coût du plus court chemin depuis `depart` vers toutes les cases (Dijkstra complet)."""
    h, w = carte.forme
    dist = {depart: 0.0}
    tas = [(0.0, depart)]
    voisins = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while tas:
        c, u = heapq.heappop(tas)
        if c > dist.get(u, math.inf):
            continue
        for di, dj in voisins:
            v = (u[0] + di, u[1] + dj)
            if not (0 <= v[0] < h and 0 <= v[1] < w) or not carte.libre[v]:
                continue
            nc = c + math.hypot(di, dj) * carte.cout[v]
            if nc < dist.get(v, math.inf):
                dist[v] = nc
                heapq.heappush(tas, (nc, v))
    return dist


def depart_dans_l_entree(logement: dict, carte: Carte, entree: dict) -> tuple[int, int]:
    """Le point de départ : dans l'entrée, au plus près de la porte palière (ou au centre de l'entrée s'il n'y en a pas)."""
    palliere = porte_palliere(logement)
    if palliere:
        o = next(o for o in logement["ouvertures"] if o["id"] == palliere)
        m = next(m for m in logement["murs"] if m["id"] == o["mur"])
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        d = (b - a) / np.linalg.norm(b - a)
        repere = a + d * (o["position"] + o["largeur"] / 2)
    else:
        repere = np.asarray(entree["contour"], float).mean(0)
    return carte.plus_proche_libre(repere, carte.masque_piece(entree))


# PASSAGE DES PORTES (cinématique, étape 4, 12/11/2026) : le plus court chemin longe le mur puis tourne au dernier moment dans la
# porte ; la caméra, qui regarde là où elle va, avait le nez sur le mur en sortant des pièces (app-002 : 25-27 s et 38-40 s, mur
# à 0,2-0,3 m au centre de l'image, 6,8 s du film « nez au mur »). Comme un cadreur : on s'aligne FACE à la porte un peu avant, on
# la franchit droit, on en ressort droit, en regardant à travers.
PORTE_APPROCHE_M = (0.9, 0.7, 0.5)  # distance du point d'alignement, de part et d'autre (la plus grande qui tient)
PORTE_ZONE_M = 0.6  # on raccorde le chemin d'origine à ça au-delà du point d'alignement
PORTE_GARDE_M = 1.2  # un arrêt de la visite (cœur, point de vue) plus près que ça de la porte : on n'y touche pas


def _libre(carte: Carte, q) -> bool:
    i, j = carte.case(tuple(q))
    return 0 <= i < carte.forme[0] and 0 <= j < carte.forme[1] and bool(carte.libre[i, j])


def redresser_aux_portes(chemin: list, carte: Carte, logement: dict, portes: list[dict], gardes_xy: list) -> list:
    """Le chemin (cases) où chaque porte ouverte franchie l'est DROIT : point d'alignement en face de la porte de chaque côté
    (sur la normale du mur, à PORTE_APPROCHE_M), ligne droite entre les deux par le milieu de la porte. Sans place pour
    s'aligner, ou près d'un arrêt de la visite (`gardes_xy`), la porte garde le chemin d'origine."""
    par_id = {o["id"]: o for o in logement.get("ouvertures", [])}
    xy = np.array([carte.xy(c) for c in chemin], float)
    travaux = []
    for p in portes:
        o = par_id.get(p["id"])
        if o is None:
            continue
        _, a, d, n, m = _cotes(logement, o)
        centre = a + d * (o["position"] + o["largeur"] / 2)
        ecarts = np.linalg.norm(xy - centre, axis=1)
        i = int(np.argmin(ecarts))
        if ecarts[i] > max(0.35, o["largeur"] / 2) or any(np.linalg.norm(np.asarray(g) - centre) < PORTE_GARDE_M for g in gardes_xy):
            continue
        avant = xy[max(0, i - 6)] - centre
        cote = 1.0 if float(np.dot(avant, n)) >= 0 else -1.0
        for approche in PORTE_APPROCHE_M:
            A, B = centre + n * cote * approche, centre - n * cote * approche
            ligne = [A + (B - A) * t for t in np.linspace(0, 1, max(2, int(2 * approche / PAS_M) + 1))]
            if all(carte.degage(tuple(q), MARGE_M) for q in (A, B)) and all(_libre(carte, q) for q in ligne):
                break
        else:
            continue
        rayon = approche + PORTE_ZONE_M
        e = i
        while e > 0 and ecarts[e - 1] <= rayon:
            e -= 1
        x = i
        while x < len(chemin) - 1 and ecarts[x + 1] <= rayon:
            x += 1
        if e == 0 or x == len(chemin) - 1:
            continue  # la porte est au tout début ou à la toute fin du vol : on n'y touche pas
        travaux.append((e, x, A, B, ligne))
    for e, x, A, B, ligne in sorted(travaux, key=lambda t: -t[0]):
        if any(e2 <= x and e <= x2 for e2, x2, *_ in travaux if (e2, x2) != (e, x) and e2 > e):
            continue  # deux portes trop proches : on garde la plus en aval
        try:
            cases_ligne = []
            for q in ligne:
                c = carte.case(tuple(q))
                if not cases_ligne or cases_ligne[-1] != c:
                    cases_ligne.append(c)
            nouveau = carte.chemin(chemin[e], cases_ligne[0])[:-1] + cases_ligne + carte.chemin(cases_ligne[-1], chemin[x])[1:]
        except Exception:  # noqa: BLE001 : pas de chemin : on garde l'ancien
            continue
        if len(nouveau) < 2:
            continue
        chemin = chemin[:e] + nouveau + chemin[x + 1:]
    return chemin
