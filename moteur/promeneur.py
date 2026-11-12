"""Le PROMENEUR d'Atelya : une BALADE continue dans tout le logement, une seule prise sans coupure (12/11/2026, NT : « une vraie
caméra qui se balade, qui pense, qui ose, qui passe par tous les recoins, qui va au bout de la pièce, qui se retourne »).

Comme un vidéaste avec une caméra stabilisée :
1. OÙ L'ON PEUT MARCHER : une grille fine (PAS_M) du logement ; murs, fenêtres, meubles et battants des portes OUVERTES sont des
   obstacles ; on marche à au moins MARGE_M de tout, et de préférence au milieu des passages (coût plus fort près des obstacles) ;
   les portes intérieures sont des passages (ouvertes pendant la balade ; la porte d'entrée palière reste fermée).
2. LE PARCOURS : on part de l'entrée (près de la porte palière) ; puis, dans l'ordre d'une visite (moteur/realisateur.ORDRE), pour
   chaque pièce qui a quelque chose à montrer : son meilleur POINT DE VUE (moteur/realisateur), puis le FOND de la pièce (le point
   libre le plus loin de l'endroit où l'on est entré), où la caméra SE RETOURNE lentement ; les étapes sont reliées par le plus
   court chemin (on passe par les portes), lissé pour une marche fluide à VITESSE m/s.
3. LE REGARD : devant soi en marchant (on regarde là où l'on va, un peu en avance), vers le cadrage choisi au point de vue (un
   temps d'arrêt), et un demi-tour lent au fond de la pièce ; la tête tourne doucement (au plus ROTATION_MAX °/s).
Sortie : un trajet au format de outils/unreal/cinematique_unreal.py (une clé toutes les CLE_IMAGES images) et ses étapes.
"""
from __future__ import annotations

import heapq
import math

import cv2
import numpy as np

from moteur import realisateur as rz

PAS_M = 0.05
MARGE_M = 0.20  # on passe une porte de 60 cm (comme un opérateur) ; ailleurs, on préfère le milieu des passages (CONFORT_M)
CIRCULATION = {"entree", "degagement", "couloir", "hall"}
CONFORT_M = 0.6  # au-delà de cette distance des obstacles, plus de surcoût : on marche au milieu des passages
VITESSE = 0.45  # m/s : une marche lente, dans la pièce qu'on montre
VITESSE_PASSAGE = 0.8  # m/s : dans les couloirs et pour rejoindre la pièce suivante
ROTATION_MAX = 35.0  # °/s
ARRET_VUE_S = 1.8  # temps passé au point de vue (léger panoramique)
DEMI_TOUR_S = 3.2  # se retourner au fond de la pièce
DEMI_TOUR_DEG = 150.0
REGARD_AVANCE_M = 1.2  # on regarde là où l'on sera dans 1,2 m
# LE REGARD (12/11/2026, premier essai : la caméra fixait parfois un mur à quelques centimètres) : en marchant, on regarde vers
# là où l'on voit LOIN, à au plus REGARD_LIBERTE_DEG de la direction de marche ; au fond d'une pièce, le demi-tour va vers la
# plus belle profondeur (on révèle la pièce) ; le fond est pris à au moins FOND_DISTANCE_M des murs et des meubles.
REGARD_LIBERTE_DEG = 50.0
REGARD_LIBERTE_LARGE_DEG = 140.0  # quand tout est proche devant (on marche vers un angle ou une porte)
PROFONDEUR_MIN_M = 2.0
REGARD_CHAMP_DEG = 30.0  # demi-largeur du cône où l'on mesure la profondeur d'une direction
REGARD_RAPPEL = 0.025  # pénalité (m de profondeur par degré) pour s'écarter de la direction de marche
FOND_DISTANCE_M = 0.6
IPS = 24
CLE_IMAGES = 4
BATTANT_EP = 0.05


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
    """La grille où l'on peut marcher, et le plus court chemin (Dijkstra, 8 voisins, coût plus fort près des obstacles)."""

    def __init__(self, logement: dict, portes: list[dict]):
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
        for poly in scene.pleins + scene.fenetres + [poly for _, poly in scene.meubles] + [p["battant"] for p in portes]:
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

    def chemin(self, depart, arrivee) -> list[tuple[int, int]]:
        h, w = self.forme
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
                nc = c + math.hypot(di, dj) * self.cout[v]
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


def _lisser(points: np.ndarray, carte: Carte, fenetre_m: float = 0.8) -> np.ndarray:
    """Moyenne glissante le long du chemin (marche fluide), sans jamais sortir de la zone praticable."""
    n = max(1, int(fenetre_m / PAS_M / 2))
    lisse = points.copy()
    for k in range(len(points)):
        a, b = max(0, k - n), min(len(points), k + n + 1)
        candidat = points[a:b].mean(0)
        i, j = carte.case(candidat)
        if 0 <= i < carte.forme[0] and 0 <= j < carte.forme[1] and carte.distance[i, j] >= MARGE_M * 0.9:
            lisse[k] = candidat
    return lisse


def _reechantillonner(points: np.ndarray, pas_m: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-6:
        return points[:1]
    t = np.arange(0, s[-1], pas_m)
    return np.stack([np.interp(t, s, points[:, 0]), np.interp(t, s, points[:, 1])], 1)


def _profondeur(rayons: dict, cap: float) -> float:
    """La profondeur vue dans une direction : médiane des distances des rayons à ±REGARD_CHAMP_DEG (plafonnée à 8 m)."""
    ecart = np.abs((rayons["angles"] - cap + 180) % 360 - 180)
    d = rayons["distance"][ecart <= REGARD_CHAMP_DEG]
    return float(np.median(np.minimum(d, 8.0))) if len(d) else 0.0


def regard_profond(rayons: dict, cap_marche: float | None) -> float:
    """La direction où regarder : vers la profondeur, sans trop s'écarter de la marche (ou n'importe où si cap_marche None)."""
    if cap_marche is None:
        caps = np.arange(0, 360, 10.0)
        return float(caps[int(np.argmax([_profondeur(rayons, c) for c in caps]))])
    for liberte in (REGARD_LIBERTE_DEG, REGARD_LIBERTE_LARGE_DEG):
        caps = cap_marche + np.arange(-liberte, liberte + 1e-6, 10.0)
        profondeurs = [_profondeur(rayons, c) for c in caps]
        notes = [pr - REGARD_RAPPEL * abs(c - cap_marche) for pr, c in zip(profondeurs, caps)]
        meilleur = int(np.argmax(notes))
        if profondeurs[meilleur] >= PROFONDEUR_MIN_M:
            break  # devant soi, on voit assez loin ; sinon on tourne la tête plus franchement (comme on le ferait)
    return float(caps[meilleur])


def _angle(v) -> float:
    return math.degrees(math.atan2(v[1], v[0]))


def _ecart(a, b) -> float:
    return (b - a + 180) % 360 - 180


def balade(logement: dict, savoir: dict | None = None, format_image=(1920, 1080), scene_eclairage: str | None = None) -> dict:
    """La balade : trajet (une clé toutes les CLE_IMAGES images), étapes, portes ouvertes, pièces sans fenêtre."""
    s = savoir or rz.savoir_faire()
    scene = rz.Scene2D(logement)
    pieces = [p for p in logement["pieces"] if rz._type(p) not in rz.SANS_INTERET and len(p.get("contour") or []) >= 3]
    pieces.sort(key=lambda p: (rz.ORDRE.index(rz._type(p)) if rz._type(p) in rz.ORDRE else len(rz.ORDRE), p["id"]))
    vues_par_piece = {}
    for piece in pieces:
        vues = rz.points_de_vue(scene, piece, 1, s)
        if vues and not rz.rien_a_montrer(vues[0]):
            vues_par_piece[piece["id"]] = vues[0]
    portes = portes_ouvertes(logement, set(vues_par_piece))
    carte = Carte(logement, portes)
    # ce que voit la caméra : portes ouvertes = on voit à travers ; portes fermées = mur
    ouvertes = {p["id"] for p in portes}
    voir = rz.Scene2D({**logement, "ouvertures": [o for o in logement.get("ouvertures", [])
                                                 if o["type"] != "porte" or o["id"] in ouvertes]}, portes_fermees=False)

    # départ : dans l'entrée, près de la porte palière
    palliere = porte_palliere(logement)
    entree = next((p for p in pieces if rz._type(p) == "entree"), pieces[0])
    if palliere:
        o = next(o for o in logement["ouvertures"] if o["id"] == palliere)
        m = next(m for m in logement["murs"] if m["id"] == o["mur"])
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        d = (b - a) / np.linalg.norm(b - a)
        repere = a + d * (o["position"] + o["largeur"] / 2)
    else:
        repere = np.asarray(entree["contour"], float).mean(0)
    position = carte.plus_proche_libre(repere, carte.masque_piece(entree))
    atteignable = carte.zones == carte.zones[position]  # tout ce qu'on peut rejoindre à pied depuis l'entrée
    etapes = [{"genre": "depart", "piece": entree["id"], "xy": carte.xy(position)}]
    chemin = [position]
    for piece in pieces:
        vue = vues_par_piece.get(piece["id"])
        if vue is None or rz._type(piece) in CIRCULATION:
            continue  # pièce sans rien à montrer, ou couloir : on la traverse sans s'y arrêter
        masque = carte.masque_piece(piece) & atteignable
        if not masque.any():
            continue
        cible_vue = carte.plus_proche_libre(vue["position"], masque)
        morceau = carte.chemin(chemin[-1], cible_vue)
        chemin += morceau[1:]
        etapes.append({"genre": "point_de_vue", "piece": piece["id"], "xy": carte.xy(cible_vue), "cap": vue["cap"],
                       "indice": len(chemin) - 1})
        # le fond de la pièce : la case la plus loin (à vol d'oiseau) de l'endroit où l'on est entré dans la pièce, à au moins
        # FOND_DISTANCE_M des murs et des meubles (pas le nez dans un angle)
        entree_piece = next((c for c in morceau if masque[c]), cible_vue)
        large = masque & (carte.distance >= min(FOND_DISTANCE_M, float(carte.distance[masque].max()) * 0.9))
        cases = np.argwhere(large if large.any() else masque)
        loin = cases[int(np.argmax((cases[:, 0] - entree_piece[0]) ** 2 + (cases[:, 1] - entree_piece[1]) ** 2))]
        fond = (int(loin[0]), int(loin[1]))
        if math.dist(carte.xy(fond), carte.xy(cible_vue)) > 1.2:
            chemin += carte.chemin(chemin[-1], fond)[1:]
            etapes.append({"genre": "fond", "piece": piece["id"], "xy": carte.xy(fond), "indice": len(chemin) - 1})

    # marche : lissage, puis une position par image à VITESSE m/s ; arrêts (point de vue, demi-tour) insérés
    xy = np.array([carte.xy(c) for c in chemin])
    xy = _lisser(_lisser(xy, carte), carte)
    pas_image = VITESSE / IPS
    images, regards, arrets = [], [], {}
    for e in etapes[1:]:
        arrets[e["indice"]] = e
    debut = 0
    indices = sorted(arrets) + [len(xy) - 1]
    cap_courant = None
    pieces_par_id = {p["id"]: p for p in logement["pieces"]}
    for fin in indices:
        cible = arrets.get(fin)
        piece_cible = pieces_par_id.get(cible["piece"]) if cible else None
        brut = xy[debut:fin + 1]
        if len(brut) > 1:
            # vitesse : lente quand on est dans la pièce que l'on vient montrer, plus vive dans les passages (moyenne glissante
            # pour des changements d'allure doux)
            vites = np.array([VITESSE if piece_cible and rz._dedans(tuple(q), piece_cible["contour"]) else VITESSE_PASSAGE
                              for q in brut])
            vites = np.convolve(np.pad(vites, 20, mode="edge"), np.ones(41) / 41, mode="valid")
            seg = np.linalg.norm(np.diff(brut, axis=0), axis=1)
            temps = np.concatenate([[0], np.cumsum(seg / ((vites[1:] + vites[:-1]) / 2))])
            t_img = np.arange(0, temps[-1], 1.0 / IPS)
            troncon = np.stack([np.interp(t_img, temps, brut[:, 0]), np.interp(t_img, temps, brut[:, 1])], 1)
        else:
            troncon = brut
        rayons = None
        for k, p in enumerate(troncon):
            avance = troncon[min(len(troncon) - 1, k + int(REGARD_AVANCE_M / (VITESSE_PASSAGE / IPS)))]
            direction = avance - p
            marche = _angle(direction) if np.linalg.norm(direction) > 0.05 else cap_courant
            if k % CLE_IMAGES == 0 or rayons is None:
                rayons = voir.rayons(tuple(p))
                cap = regard_profond(rayons, marche)
            images.append(p)
            regards.append(cap)
            cap_courant = cap
        debut = fin
        e = arrets.get(fin)
        if e is None:
            continue
        p = xy[fin]
        if e["genre"] == "point_de_vue":  # temps d'arrêt, regard vers le cadrage choisi, léger panoramique
            n = int(ARRET_VUE_S * IPS)
            for k in range(n):
                images.append(p)
                regards.append(e["cap"] + s["pano_deg"] * (2 * k / max(n - 1, 1) - 1))
        else:  # au fond de la pièce : on se retourne lentement vers la plus belle profondeur (on révèle la pièce)
            n = int(DEMI_TOUR_S * IPS)
            depart_cap = regards[-1]
            but = regard_profond(voir.rayons(tuple(p)), None)
            tour = _ecart(depart_cap, but)  # par le côté le plus court
            for k in range(n):
                t = k / max(n - 1, 1)
                images.append(p)
                regards.append(depart_cap + tour * (3 * t * t - 2 * t ** 3))
    # la tête tourne doucement : chaque cap rejoint le cap voulu à au plus ROTATION_MAX °/s
    # (dans les deux sens du temps : la tête ANTICIPE un virage au lieu de le suivre en retard)
    voulus = [regards[0]]
    for c in regards[1:]:
        voulus.append(voulus[-1] + _ecart(voulus[-1], c))  # caps déroulés (sans saut de 360°)
    pas_max = ROTATION_MAX / IPS
    caps = list(voulus)
    for i in range(1, len(caps)):
        caps[i] = caps[i - 1] + max(-pas_max, min(pas_max, voulus[i] - caps[i - 1]))
    arriere = list(voulus)
    for i in range(len(arriere) - 2, -1, -1):
        arriere[i] = arriere[i + 1] + max(-pas_max, min(pas_max, voulus[i] - arriere[i + 1]))
    caps = np.array([(a + b) / 2 for a, b in zip(caps, arriere)])
    # un léger lissage des caps (pas d'à-coups), puis les clés
    noyau = np.ones(9) / 9
    caps = np.convolve(np.pad(caps, 4, mode="edge"), noyau, mode="valid")
    points = [[round(float(images[k][0]), 3), round(float(images[k][1]), 3), round(s["hauteur_m"], 3),
               round(float(caps[k]), 2), round(s["tangage_deg"], 1)] for k in range(0, len(images), CLE_IMAGES)]
    if (len(images) - 1) % CLE_IMAGES:
        k = len(images) - 1
        points.append([round(float(images[k][0]), 3), round(float(images[k][1]), 3), round(s["hauteur_m"], 3),
                       round(float(caps[k]), 2), round(s["tangage_deg"], 1)])
    nb_images = (len(points) - 1) * CLE_IMAGES + 1
    trajet = {"points": points, "images": nb_images, "ips": IPS, "focale_mm": s["focale_mm"], "format": list(format_image),
              "balade": True}
    if scene_eclairage:
        trajet["scene"] = scene_eclairage
    sans_fenetre = [p["id"] for p in logement["pieces"] if not scene.a_une_fenetre(p)]
    return {"trajet": trajet, "etapes": etapes, "portes_ouvertes": [{k: v for k, v in p.items() if k != "battant"}
                                                                     for p in portes],
            "pieces_sans_fenetre": sans_fenetre, "duree_s": round(nb_images / IPS, 1),
            "longueur_m": round(float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1))), 1)}


def dessiner(logement: dict, resultat: dict, chemin, px_par_m: int = 60) -> None:
    """La balade vue de dessus : le chemin (rouge, une flèche par seconde dans le sens du regard), les étapes."""
    from moteur.images import ecrire_image

    rz.dessiner(logement, [], chemin, px_par_m)
    from moteur.images import lire_image
    image = lire_image(chemin)
    pts = np.concatenate([np.asarray(p["contour"], float) for p in logement["pieces"]])
    mini, maxi = pts.min(0) - 1.0, pts.max(0) + 1.0

    def ecran(p):
        return int((p[0] - mini[0]) * px_par_m), int((maxi[1] - p[1]) * px_par_m)
    pts_t = resultat["trajet"]["points"]
    for a, b in zip(pts_t, pts_t[1:]):
        cv2.line(image, ecran(a), ecran(b), (0, 0, 220), 2, cv2.LINE_AA)
    pas = max(1, IPS // CLE_IMAGES)
    for p in pts_t[::pas]:
        c = math.radians(p[3])
        cv2.arrowedLine(image, ecran(p), ecran((p[0] + 0.35 * math.cos(c), p[1] + 0.35 * math.sin(c))), (0, 140, 255), 1,
                        cv2.LINE_AA, tipLength=0.4)
    for k, e in enumerate(resultat["etapes"]):
        couleur = {"depart": (0, 160, 0), "point_de_vue": (200, 0, 200), "fond": (200, 120, 0)}[e["genre"]]
        cv2.circle(image, ecran(e["xy"]), 7, couleur, -1)
        cv2.putText(image, str(k), (ecran(e["xy"])[0] + 8, ecran(e["xy"])[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
    ecrire_image(chemin, image)
