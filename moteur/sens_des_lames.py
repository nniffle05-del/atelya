"""Le SENS des lames d'un parquet, et leur LARGEUR, lus sur les photos du client (17/11/2026).

Pourquoi : NT, en comparant les photos et la maquette : « je ne les trouve absolument pas ressemblants tant sur la couleur que
sur la direction du parquet ». Jusqu'ici le sens des lames n'était jamais lu : c'était celui des murs les plus longs du
logement, le même partout (moteur.habillage.orientation_sols).

Comment : sur une photo, les joints entre les lames sont de longs traits fins. On relève les traits droits de la photo
(détecteur de segments d'OpenCV), on ne garde que ceux qui sont posés sur le SOL d'une pièce (pas sur un meuble : masque
« pas du sol » ; pas au pied d'un mur : ce serait la plinthe), et on reporte chacun sur le plan grâce à la place de l'appareil.
Sur le plan, tous les joints d'un parquet à lames droites ont la même direction : c'est le pic de l'histogramme des directions.
La largeur des lames est l'écart le plus fréquent entre deux joints voisins.

Angles en degrés dans le repère du logement, de 0 à 180 : 0 = lames le long de l'axe x, 90 = le long de l'axe y.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
LONGUEUR_MIN_PX = 25.0  # un trait plus court sur la photo n'est pas un joint sûr
LONGUEUR_MIN_M = 0.25  # ni un trait de moins de 25 cm sur le sol
DISTANCE_MAX_M = 7.0  # au-delà, un pixel couvre trop de sol
PLINTHE_M = 0.10  # un trait à moins de 10 cm d'un mur est le pied du mur, pas un joint
LARGEUR_PIC = 8  # degrés de part et d'autre du pic comptés « dans le sens des lames »
PART_SURE = 0.45  # part du poids des traits dans le pic (et son vis-à-vis à 90°) pour que le sens soit sûr
POIDS_MIN_M = 6.0  # il faut au moins 6 m de traits en tout
RAYON_M = 0.25  # un trait dont le prolongement passe à moins de 25 cm du pied de l'appareil est écarté (voir traits_du_sol)
ECART_AXE = 12.0  # degrés : un trait à moins de ça d'un sens des murs compte pour ce sens
CASE_PEIGNE_M = 0.02  # les joints sont rangés en travers par cases de 2 cm
PLAFOND_CASE_M = 0.5  # une case ne compte pas plus de 50 cm de traits (un bord de table ne vaut pas dix joints)
NOTE_MIN_M = 3.0  # il faut au moins 3 m de joints ainsi comptés (six joints distincts au moins)
RAPPORT_MIN = 2.0  # et deux fois plus que dans l'autre sens des murs


def vers_le_sol(u, v, cam):
    """Le point du sol (z = 0) vu au pixel (u, v) par l'appareil `cam` (8 nombres, moteur.camera_photo) ; NaN au-dessus de
    l'horizon. Accepte des tableaux."""
    from moteur.camera_photo import axes

    x, y, z, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    a, b = (np.asarray(u, float) - u0) / f, (np.asarray(v, float) - v0) / f
    dx, dy, dz = (vue[k] + a * droite[k] - b * haut[k] for k in range(3))
    t = np.where(dz < -1e-6, -z / np.where(dz < -1e-6, dz, -1.0), np.nan)
    return x + t * dx, y + t * dy


def traits_du_sol(photo_rgb: np.ndarray, cam, logement: dict, pas_du_sol: np.ndarray | None = None) -> list[dict]:
    """Les traits droits de la photo posés sur le sol d'une pièce, reportés sur le plan :
    [{"piece", "a": (x, y), "b": (x, y), "angle" (0-180), "longueur" (m), "milieu": (x, y)}]."""
    import cv2

    from moteur.sol_a_plat import dans_polygone, visibles_depuis

    gris = cv2.cvtColor(photo_rgb, cv2.COLOR_RGB2GRAY)
    lignes = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gris)[0]
    if lignes is None:
        return []
    s = np.asarray(lignes, float).reshape(-1, 4)  # (N, 1, 4) ou (N, 4) selon la version d'OpenCV
    s = s[np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]) >= LONGUEUR_MIN_PX]
    if not len(s):
        return []
    h, w = gris.shape
    if pas_du_sol is not None:  # ni un bout ni le milieu sur un meuble
        garde = np.ones(len(s), bool)
        for uu, vv in ((s[:, 0], s[:, 1]), (s[:, 2], s[:, 3]), ((s[:, 0] + s[:, 2]) / 2, (s[:, 1] + s[:, 3]) / 2)):
            garde &= ~pas_du_sol[np.clip(vv.round().astype(int), 0, h - 1), np.clip(uu.round().astype(int), 0, w - 1)]
        s = s[garde]
    ax, ay = vers_le_sol(s[:, 0], s[:, 1], cam)
    bx, by = vers_le_sol(s[:, 2], s[:, 3], cam)
    ok = np.isfinite(ax) & np.isfinite(bx)
    ax, ay, bx, by = ax[ok], ay[ok], bx[ok], by[ok]
    mx, my = (ax + bx) / 2, (ay + by) / 2
    longueur = np.hypot(bx - ax, by - ay)
    cx, cy = float(cam[0]), float(cam[1])
    ok = (longueur >= LONGUEUR_MIN_M) & (np.hypot(mx - cx, my - cy) <= DISTANCE_MAX_M) & (np.hypot(ax - cx, ay - cy) <= DISTANCE_MAX_M + 2) \
        & (np.hypot(bx - cx, by - cy) <= DISTANCE_MAX_M + 2)
    sortie = []
    for p in logement["pieces"]:
        c = np.asarray(p["contour"], float)
        dans = ok & dans_polygone(ax, ay, c) & dans_polygone(bx, by, c) & dans_polygone(mx, my, c)
        if not dans.any():
            continue
        # vus sans mur entre l'appareil et le trait (une autre pièce aperçue par une porte : le milieu doit être visible)
        visible = np.zeros(len(mx), bool)
        dedans_piece = bool(dans_polygone(np.array([cx]), np.array([cy]), c)[0])
        if dedans_piece:
            visible[dans] = visibles_depuis(mx[dans], my[dans], (cx, cy), c)
        else:
            visible[dans] = True
        for i in np.nonzero(dans & visible)[0]:
            if _distance_au_contour((mx[i], my[i]), c) < PLINTHE_M:
                continue
            # Un trait qui VISE le pied de l'appareil n'est presque jamais un joint : c'est l'arête verticale d'un meuble, d'un
            # pied de table ou d'une porte (toute verticale tombe sur le sol en rayon partant de l'appareil), ou le reflet d'une
            # fenêtre. Les joints d'un parquet posé dans le sens du regard sont parallèles entre eux : seuls ceux du milieu
            # visent l'appareil, les autres restent.
            ux, uy = (bx[i] - ax[i]) / longueur[i], (by[i] - ay[i]) / longueur[i]
            if abs((cx - ax[i]) * uy - (cy - ay[i]) * ux) < RAYON_M:
                continue
            angle = math.degrees(math.atan2(by[i] - ay[i], bx[i] - ax[i])) % 180.0
            sortie.append({"piece": p["id"], "a": (float(ax[i]), float(ay[i])), "b": (float(bx[i]), float(by[i])), "angle": angle,
                           "longueur": float(longueur[i]), "milieu": (float(mx[i]), float(my[i]))})
    return sortie


def _distance_au_contour(point, contour: np.ndarray) -> float:
    d = math.inf
    for a, b in zip(contour, np.roll(contour, -1, axis=0)):
        u = b - a
        n = float(u @ u)
        t = 0.0 if n == 0 else max(0.0, min(1.0, float((np.asarray(point) - a) @ u) / n))
        d = min(d, float(np.hypot(*(np.asarray(point) - (a + t * u)))))
    return d


def sens(traits: list[dict]) -> dict | None:
    """Le sens des lames d'après des traits du sol : {"sens" (degrés, 0-180), "part" (part du poids des traits dans le pic),
    "travers" (part dans le sens perpendiculaire : les bouts de lames), "poids_m", "sur" (bool)} ; None sans trait.
    Chaque trait pèse sa longueur sur le sol (au plus 2 m : un grand reflet ne décide pas seul)."""
    if not traits:
        return None
    angles = np.array([t["angle"] for t in traits])
    poids = np.minimum(np.array([t["longueur"] for t in traits]), 2.0)
    histo = np.zeros(180)
    np.add.at(histo, np.floor(angles).astype(int) % 180, poids)
    noyau = np.exp(-0.5 * (np.arange(-12, 13) / 3.0) ** 2)
    lisse = np.convolve(np.concatenate([histo[-12:], histo, histo[:12]]), noyau / noyau.sum(), mode="valid")
    pic = int(lisse.argmax())
    ecart = lambda a, b: np.abs((a - b + 90.0) % 180.0 - 90.0)
    pres = ecart(angles, pic + 0.5) <= LARGEUR_PIC
    # le sens précis : moyenne des angles du pic (sur le cercle de 180°)
    doubles = np.radians(2 * angles[pres])
    precis = (math.degrees(math.atan2(float((poids[pres] * np.sin(doubles)).sum()), float((poids[pres] * np.cos(doubles)).sum()))) / 2) % 180.0
    part = float(poids[pres].sum() / poids.sum())
    travers = float(poids[ecart(angles, pic + 90.5) <= LARGEUR_PIC].sum() / poids.sum())
    return {"sens": round(precis, 1), "part": round(part, 3), "travers": round(travers, 3), "poids_m": round(float(poids.sum()), 1),
            "traits": int(len(traits)), "sur": bool(part + travers >= PART_SURE and part >= 1.5 * travers and poids.sum() >= POIDS_MIN_M)}


def largeur_des_lames(traits: list[dict], sens_deg: float, mini: float = 0.04, maxi: float = 0.35) -> dict | None:
    """La largeur des lames : l'écart le plus fréquent entre deux joints voisins (traits dans le sens des lames, rangés en
    travers). {"largeur_m", "ecarts"} ; None s'il y a trop peu de joints voisins."""
    a = math.radians(sens_deg)
    le_long, en_travers = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    ecart = lambda x: abs((x - sens_deg + 90.0) % 180.0 - 90.0)
    joints = [t for t in traits if ecart(t["angle"]) <= LARGEUR_PIC]
    ecarts = []
    for i, t in enumerate(joints):
        m = np.asarray(t["milieu"])
        proche = None
        for j, autre in enumerate(joints):
            if i == j:
                continue
            d = np.asarray(autre["milieu"]) - m
            long_, travers_ = float(d @ le_long), float(d @ en_travers)
            # un joint VOISIN : en face (les deux traits se recouvrent le long des lames) et du côté positif
            if abs(long_) <= (t["longueur"] + autre["longueur"]) / 2 and 0.02 < travers_ <= maxi * 1.5:
                proche = travers_ if proche is None else min(proche, travers_)
        if proche is not None:
            ecarts.append(proche)
    ecarts = [e for e in ecarts if mini <= e <= maxi]
    if len(ecarts) < 12:
        return None
    histo, bords = np.histogram(ecarts, bins=np.arange(mini, maxi + 0.01, 0.01))
    lisse = np.convolve(histo, [0.25, 0.5, 0.25], mode="same")
    k = int(lisse.argmax())
    autour = [e for e in ecarts if abs(e - (bords[k] + 0.005)) <= 0.015]
    return {"largeur_m": round(float(np.median(autour)), 3), "ecarts": len(ecarts), "part": round(len(autour) / len(ecarts), 2)}


def axes_du_logement(logement: dict) -> tuple[float, float]:
    """Les deux sens des murs du logement (degrés) : celui des murs les plus longs, et son travers (même règle que
    moteur.habillage.orientation_sols, sur le logement écrit en dictionnaire)."""
    poids: dict[int, float] = {}
    for m in logement.get("murs", []):
        (x0, y0), (x1, y1) = m["debut"], m["fin"]
        angle = round(math.degrees(math.atan2(y1 - y0, x1 - x0))) % 180
        poids[angle] = poids.get(angle, 0.0) + math.hypot(x1 - x0, y1 - y0)
    premier = float(max(poids, key=poids.get)) if poids else 0.0
    return premier, (premier + 90.0) % 180.0


def sens_parmi(traits: list[dict], axes: tuple[float, float]) -> dict | None:
    """Le sens des lames CHOISI ENTRE LES DEUX SENS DES MURS (un parquet est presque toujours posé le long d'un mur) :
    {"sens" (l'axe retenu), "note" (m de joints comptés dans ce sens), "autre" (dans l'autre sens), "sur"}.
    Les traits proches d'un axe sont rangés EN PEIGNE : par cases de 2 cm en travers, chaque case plafonnée. Un parquet donne
    beaucoup de joints parallèles (beaucoup de cases) ; un bord de table ou un reflet, une ou deux."""
    if not traits:
        return None
    notes = []
    for axe in axes:
        a = math.radians(axe)
        cases: dict[int, float] = {}
        for t in traits:
            if abs((t["angle"] - axe + 90.0) % 180.0 - 90.0) > ECART_AXE:
                continue
            travers = -t["milieu"][0] * math.sin(a) + t["milieu"][1] * math.cos(a)
            k = int(round(travers / CASE_PEIGNE_M))
            cases[k] = min(cases.get(k, 0.0) + t["longueur"], PLAFOND_CASE_M)
        notes.append(sum(cases.values()))
    k = int(np.argmax(notes))
    note, autre = notes[k], notes[1 - k]
    return {"sens": float(axes[k]), "note": round(note, 1), "autre": round(autre, 1),
            "sur": bool(note >= NOTE_MIN_M and note >= RAPPORT_MIN * autre)}
