"""La COURBE lisse du vol et son ALLURE : le chemin de la grille devient une courbe sans angle qui ne touche jamais un obstacle ;
chaque demi-tour (cul-de-sac) devient une boucle en virage quand la place le permet, sinon un arrêt en vol stationnaire où la
caméra pivote ; la vitesse ralentit devant ce qu'on montre, dans les virages, au départ et à l'arrivée ; puis une position par
image."""
from __future__ import annotations

import math

import numpy as np

from moteur.cinema.navigation import Carte
from moteur.cinema.reglages import (IPS, MARGE_M, VOL_ACCEL_LATERALE, VOL_BOUCLE_RAYONS, VOL_BOUCLE_RECUL_M,
                                    VOL_DEPART_ARRIVEE_M, VOL_FINITION_S, VOL_LISSAGE_M, VOL_PIVOT_S, VOL_RAYON_VUE_M,
                                    VOL_ROTATION_MAX, VOL_VITESSE, VOL_VITESSE_VUE)


ARRET_PLANIFIE_M = 0.7  # planificateur : on freine sur 70 cm avant un panoramique, on réaccélère sur 70 cm après
VIRAGE_PART_ROTATION = 0.8  # dans un virage, la direction du mouvement tourne au plus à 80 % de la rotation permise au regard


def lissee(x, a, b):
    """Passage doux de 0 (x ≤ a) à 1 (x ≥ b), sans à-coup (courbe en S)."""
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def gauss(valeurs: np.ndarray, sigma: float) -> np.ndarray:
    """Lissage gaussien le long du temps / du chemin (écart type en nombre d'échantillons), bords prolongés."""
    if sigma <= 0 or len(valeurs) < 3:
        return valeurs.copy()
    r = int(3 * sigma) + 1
    noyau = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    noyau /= noyau.sum()
    if valeurs.ndim == 1:
        return np.convolve(np.pad(valeurs, r, mode="edge"), noyau, mode="valid")
    return np.stack([np.convolve(np.pad(valeurs[:, k], r, mode="edge"), noyau, mode="valid")
                     for k in range(valeurs.shape[1])], 1)


def reechantillonner(points: np.ndarray, pas_m: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-6:
        return points[:1]
    t = np.arange(0, s[-1], pas_m)
    return np.stack([np.interp(t, s, points[:, 0]), np.interp(t, s, points[:, 1])], 1)


def lisser_vol(points: np.ndarray, carte: Carte, sigma_m: float = VOL_LISSAGE_M, passes: int = 6) -> np.ndarray:
    """Une courbe très lisse qui ne touche jamais un obstacle. À chaque passe : lissage gaussien, puis DOSAGE progressif entre
    le chemin sûr et la courbe lissée (dosage lui-même lissé) : près d'un obstacle, la courbe reste plus près du chemin sûr,
    sans jamais sauter de l'un à l'autre (garder le point d'origine dès qu'un point lissé frôlait un obstacle faisait des
    crochets, donc des secousses de côté : vu sur le vol d'app-002 le 12/11/2026)."""
    pts = reechantillonner(points, 0.1)

    def degagement(q):
        d = np.empty(len(q))
        for k, x in enumerate(q):
            i, j = carte.case(x)
            d[k] = carte.distance[i, j] if 0 <= i < carte.forme[0] and 0 <= j < carte.forme[1] else 0.0
        return d
    for _ in range(passes):
        lisse = gauss(pts, sigma_m / 0.1)
        dose = np.clip((degagement(lisse) - MARGE_M) / 0.15, 0, 1)
        dose = np.clip(gauss(dose, sigma_m / 0.2), 0, 1)
        for _essai in range(12):
            neuf = pts + dose[:, None] * (lisse - pts)
            trop_pres = degagement(neuf) < MARGE_M * 0.9
            if not trop_pres.any():
                break
            # autour des points trop près, on réduit le dosage en douceur (une cloche, pas une marche)
            cloche = np.clip(gauss(trop_pres.astype(float), 3) * 4, 0, 1)
            dose = dose * (1 - 0.5 * cloche)
        pts = neuf
    return pts


def boucle_demi_tour(brut: np.ndarray, i: int, carte: Carte) -> np.ndarray | None:
    """Au bout d'une impasse, au lieu de rebrousser chemin (la caméra reculait), une BOUCLE en virage : on arrive, on décrit un
    demi-cercle de rayon r (le plus grand qui tient, d'un côté ou de l'autre) et on repart en avant, puis on rejoint le chemin
    du retour en douceur. Renvoie le chemin modifié, ou None si aucune boucle ne tient (on garde alors le pivot lent)."""
    # la boucle s'amorce plus tôt si la pointe est serrée : on remonte l'approche jusqu'à VOL_BOUCLE_RECUL_M pour trouver la place
    for recul in range(0, int(VOL_BOUCLE_RECUL_M / 0.1) + 1, 3):
        sortie = _boucle_a(brut, i, carte, recul)
        if sortie is not None:
            return sortie
    return None


def _boucle_a(brut: np.ndarray, i: int, carte: Carte, recul: int) -> np.ndarray | None:
    for r in VOL_BOUCLE_RAYONS:
        m = int(round(r / 0.1)) + recul
        retour = m + 15
        if i - m - 5 < 0 or i + retour >= len(brut):
            continue
        a = brut[i - m]
        d = brut[i - recul] - brut[i - m - 5]
        if np.linalg.norm(d) < 1e-6:
            continue
        d = d / np.linalg.norm(d)
        n = np.array([-d[1], d[0]])
        for cote in (1.0, -1.0):
            c = a + cote * n * r
            phis = np.linspace(0, math.pi, max(8, int(math.pi * r / 0.1)))
            arc = np.array([c + r * (-cote * n * math.cos(f) + d * math.sin(f)) for f in phis])
            b, rejoint = arc[-1], brut[i + retour]
            pas = max(2, int(np.linalg.norm(rejoint - b) / 0.1))
            liaison = np.array([b + (rejoint - b) * k / pas for k in range(1, pas)])
            neuf = np.concatenate([arc, liaison]) if len(liaison) else arc
            if all(carte.degage(q, MARGE_M * 1.1) for q in neuf):
                return np.concatenate([brut[:i - m], neuf, brut[i + retour:]])
    return None


def courbe_du_vol(chemin: list, carte: Carte, pivots: list | None = None) -> tuple[np.ndarray, list[int], list[float]]:
    """Le chemin de la grille → la courbe lisse (un point tous les 10 cm), les JONCTIONS (indices des demi-tours restés sans
    boucle, où la caméra s'arrête et pivote) et la durée de chaque arrêt. `pivots` (planificateur) : les panoramiques voulus
    ({"xy", "duree_s"}) : là, jamais de boucle, un arrêt de la durée demandée."""
    # les DEMI-TOURS (cul-de-sac : fond d'une pièce, cuisine en impasse) : la trajectoire y est coupée ; chaque morceau est lissé à
    # part, et la caméra ralentit jusqu'à presque s'arrêter à la jonction, où elle pivote (un drone ne rebrousse pas chemin d'un coup)
    brut = reechantillonner(np.array([carte.xy(c) for c in chemin], float), 0.1)
    coupes, groupe = [], []  # par groupe de détections voisines, le point où le retournement est le plus franc (la pointe)
    for i in range(5, len(brut) - 5):
        u, w = brut[i] - brut[i - 5], brut[i + 5] - brut[i]
        nu, nw = np.linalg.norm(u), np.linalg.norm(w)
        cosinus = float(np.dot(u, w) / (nu * nw)) if nu > 1e-6 and nw > 1e-6 else 1.0
        if cosinus < -0.5:
            if groupe and i - groupe[-1][0] > 10:
                coupes.append(min(groupe, key=lambda g: g[1])[0])
                groupe = []
            groupe.append((i, cosinus))
    if groupe:
        coupes.append(min(groupe, key=lambda g: g[1])[0])
    # les panoramiques voulus par le planificateur : un arrêt à l'endroit exact (le demi-tour détecté le plus proche est remplacé)
    voulus = {}
    for pv in pivots or []:
        ecarts = np.linalg.norm(brut - np.asarray(pv["xy"]), axis=1)
        i = int(np.argmin(ecarts))
        if ecarts[i] > 0.3:
            continue
        coupes = [c for c in coupes if abs(c - i) > 10]
        voulus[i] = float(pv["duree_s"])
    coupes = sorted(set(coupes) | set(voulus))
    # chaque autre demi-tour devient une boucle quand la place le permet (en partant de la fin : les indices restent justes)
    restent, durees = [], {}
    for i in sorted(coupes, reverse=True):
        boucle = None if i in voulus else boucle_demi_tour(brut, i, carte)
        if boucle is None:
            restent.append(i)
            durees[i] = voulus.get(i, VOL_PIVOT_S)
        else:
            decalage = len(boucle) - len(brut)
            restent = [j + decalage for j in restent]
            durees = {j + decalage: d for j, d in durees.items()}
            brut = boucle
    coupes = sorted(restent)
    morceaux = np.split(np.arange(len(brut)), coupes)
    courbe, jonctions = [], []
    for k, idx in enumerate(morceaux):
        morceau = brut[idx[0]:idx[-1] + 2] if k < len(morceaux) - 1 else brut[idx[0]:]
        lisse = lisser_vol(morceau, carte) if len(morceau) > 3 else morceau
        base = reechantillonner(morceau, 0.1)
        if len(lisse) > 3 and len(base) == len(lisse):  # bouts ramenés exactement sur le chemin (pas de saut entre morceaux)
            d_bout = np.minimum(np.arange(len(lisse)), np.arange(len(lisse))[::-1]) * 0.1
            w = lissee(d_bout, 0.0, 0.8)[:, None]
            lisse = base * (1 - w) + lisse * w
        if courbe:
            jonctions.append(len(np.concatenate(courbe)))
        courbe.append(lisse)
    return np.concatenate(courbe), jonctions, [durees[c] for c in coupes[:len(jonctions)]]


def allure_du_vol(courbe: np.ndarray, jonctions: list[int], etapes: list[dict], durees: list[float] | None = None,
                  virages_suivis: float | None = None) -> tuple[np.ndarray, float, list[tuple[int, int]]]:
    """La vitesse le long de la courbe (croisière, ralentie devant ce qu'on montre, dans les virages, au départ et à l'arrivée,
    arrêt et pivot aux demi-tours), puis UNE POSITION PAR IMAGE. Renvoie les positions, la longueur de la courbe (m) et les
    arrêts (première et dernière image de chaque arrêt, dans l'ordre)."""
    seg = np.linalg.norm(np.diff(courbe, axis=0), axis=1)
    abscisse = np.concatenate([[0], np.cumsum(seg)])
    longueur = float(abscisse[-1])
    reperes = [np.asarray(e["xy"]) for e in etapes[1:]]

    proche = np.min(np.stack([np.linalg.norm(courbe - r, axis=1) for r in reperes]), 0) if reperes else np.full(len(courbe), 9.0)
    vitesse = VOL_VITESSE_VUE + (VOL_VITESSE - VOL_VITESSE_VUE) * lissee(proche, 0.4, VOL_RAYON_VUE_M)
    # la courbure (changement de direction par mètre, sur ±0,5 m) borne la vitesse : v² · courbure ≤ accélération latérale
    direction = np.unwrap(np.arctan2(np.gradient(courbe[:, 1]), np.gradient(courbe[:, 0])))
    n5 = max(1, int(0.5 / 0.1))
    virage = np.abs(np.concatenate([direction[n5:], np.repeat(direction[-1], n5)])
                    - np.concatenate([np.repeat(direction[0], n5), direction[:-n5]])) / (2 * n5 * 0.1)
    vitesse = np.minimum(vitesse, np.sqrt(VOL_ACCEL_LATERALE / np.maximum(gauss(virage, 3), 1e-3)))
    # … et à petite échelle (±0,2 m) : un virage sec se prend lentement
    n2 = 2
    virage_fin = np.abs(np.concatenate([direction[n2:], np.repeat(direction[-1], n2)])
                        - np.concatenate([np.repeat(direction[0], n2), direction[:-n2]])) / (2 * n2 * 0.1)
    vitesse = np.minimum(vitesse, np.sqrt(VOL_ACCEL_LATERALE / np.maximum(gauss(virage_fin, 4), 1e-3)))
    if virages_suivis:
        # le REGARD doit pouvoir suivre le virage : la direction du mouvement ne tourne jamais plus vite que la caméra ne peut
        # tourner (sinon, au passage d'une porte, le regard reste en retard… sur le mur d'en face) ; planificateur, 12/11/2026
        omega = math.radians(virages_suivis * VIRAGE_PART_ROTATION)
        limite = omega / np.maximum(gauss(virage, 3), 1e-3)
        # sauf autour des arrêts (panoramiques) : la caméra y ralentit déjà jusqu'à s'arrêter, et le demi-tour y est voulu
        for j in jonctions:
            limite[np.abs(abscisse - abscisse[min(j, len(abscisse) - 1)]) < 1.2] = np.inf
        vitesse = np.minimum(vitesse, limite)
    vitesse *= 0.15 + 0.85 * lissee(abscisse, 0, VOL_DEPART_ARRIVEE_M) * lissee(longueur - abscisse, 0, VOL_DEPART_ARRIVEE_M)
    vitesse = gauss(gauss(vitesse, 0.6 / 0.1), 0.6 / 0.1)
    for j in jonctions:  # ralentir jusqu'au demi-tour (presque à l'arrêt, la caméra pivote), puis repartir — après le lissage
        d_arret = np.abs(abscisse - abscisse[min(j, len(abscisse) - 1)])
        r = ARRET_PLANIFIE_M if virages_suivis else 1.0  # planificateur : freinage et départ plus courts (avis de NT)
        vitesse = np.where(d_arret < r, 0.04 + (vitesse - 0.04) * np.sqrt(np.clip(d_arret / r, 0, 1.0)), vitesse)
    vitesse = np.maximum(vitesse, 0.04)
    # au bout d'une impasse : arrêt complet en vol stationnaire VOL_PIVOT_S secondes (la caméra pivote vers la sortie), puis on repart
    durees = list(durees) if durees is not None else [VOL_PIVOT_S] * len(jonctions)
    arrets = sorted((float(abscisse[min(j, len(abscisse) - 1)]), d) for j, d in zip(jonctions, durees))
    immobiles = []
    positions, s_courant = [], 0.0
    while s_courant < longueur:
        v = float(np.interp(s_courant, abscisse, vitesse))
        q = np.array([np.interp(s_courant, abscisse, courbe[:, 0]), np.interp(s_courant, abscisse, courbe[:, 1])])
        positions.append(q)
        suivant = s_courant + max(v, 0.04) / IPS
        if arrets and s_courant < arrets[0][0] <= suivant:
            immobiles.append((len(positions), len(positions) + int(arrets[0][1] * IPS) - 1))
            positions += [q] * int(arrets[0][1] * IPS)
            arrets.pop(0)
        s_courant = suivant
    # finition dans le temps (0,2 s) : gomme les petits crochets restants, la caméra ne bouge que de quelques centimètres
    return gauss(np.array(positions), VOL_FINITION_S * IPS), longueur, immobiles
