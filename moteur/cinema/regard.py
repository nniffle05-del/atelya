"""OÙ REGARDE la caméra : la profondeur vue dans une direction (rayons du plan), le regard « vers le loin » de la marche, et le
regard du VOL choisi d'un seul calcul sur tout le trajet (programmation dynamique)."""
from __future__ import annotations

import math

import numpy as np

from moteur import realisateur as rz
from moteur.cinema.reglages import (CLE_IMAGES, IPS, PROFONDEUR_MIN_M, REGARD_CHAMP_DEG, REGARD_LIBERTE_DEG,
                                    REGARD_LIBERTE_LARGE_DEG, REGARD_RAPPEL, VOL_MUR_MIN_M, VOL_RAYON_VUE_M,
                                    VOL_REGARD_MAX_DEG, VOL_ROTATION_MAX, VOL_ROTATION_PIVOT)
from moteur.cinema.trajectoire import gauss, lissee

CENTRE_DEMI_DEG = 15.0  # le centre de l'image (comme le contrôleur)
CENTRE_MUR_M = 1.0  # un obstacle plus près que ça au centre de l'image coûte jusqu'à CENTRE_POIDS
CENTRE_POIDS = 4.0
FIN_S = 2.5  # la conclusion : les dernières secondes regardent le plus beau cadrage de la dernière pièce
# PRÈS D'UNE PORTE et dans les couloirs (12/11/2026) : en passant une porte qui donne sur un couloir étroit, la caméra arrivait
# face au mur d'en face (app-002 : 25-27 s, 38-40 s) car le regard restait à moins de VOL_REGARD_MAX_DEG de la marche ; là, il
# peut déjà se tourner vers où l'on va (comme quelqu'un qui regarde dans le couloir en franchissant la porte).
PORTE_LIBERTE_M = 1.2
# ESSAYÉ à 75° le 12/11/2026 (contrôleur) : app-001 note 74,2 -> 76,6, nez au mur 6,2 -> 5,6 s ; mais app-002 6,8 -> 7,0 s.
# Gain mitigé : laissé ÉGAL à VOL_REGARD_MAX_DEG (sans effet) ; à reprendre avec d'autres logements.
REGARD_MAX_PORTE_DEG = VOL_REGARD_MAX_DEG


def profondeur(rayons: dict, cap: float) -> float:
    """La profondeur vue dans une direction : médiane des distances des rayons à ±REGARD_CHAMP_DEG (plafonnée à 8 m)."""
    ecart = np.abs((rayons["angles"] - cap + 180) % 360 - 180)
    d = rayons["distance"][ecart <= REGARD_CHAMP_DEG]
    return float(np.median(np.minimum(d, 8.0))) if len(d) else 0.0


def regard_profond(rayons: dict, cap_marche: float | None) -> float:
    """La direction où regarder : vers la profondeur, sans trop s'écarter de la marche (ou n'importe où si cap_marche None)."""
    if cap_marche is None:
        caps = np.arange(0, 360, 10.0)
        return float(caps[int(np.argmax([profondeur(rayons, c) for c in caps]))])
    for liberte in (REGARD_LIBERTE_DEG, REGARD_LIBERTE_LARGE_DEG):
        caps = cap_marche + np.arange(-liberte, liberte + 1e-6, 10.0)
        profondeurs = [profondeur(rayons, c) for c in caps]
        notes = [pr - REGARD_RAPPEL * abs(c - cap_marche) for pr, c in zip(profondeurs, caps)]
        meilleur = int(np.argmax(notes))
        if profondeurs[meilleur] >= PROFONDEUR_MIN_M:
            break  # devant soi, on voit assez loin ; sinon on tourne la tête plus franchement (comme on le ferait)
    return float(caps[meilleur])


def angle(v) -> float:
    return math.degrees(math.atan2(v[1], v[0]))


def ecart(a, b) -> float:
    return (b - a + 180) % 360 - 180


def regard_du_vol(positions: np.ndarray, courbe: np.ndarray, jonctions: list[int], etapes: list[dict], voir: rz.Scene2D,
                  logement: dict, panoramiques: list | None = None, fin_cap: float | None = None,
                  avance_m: float | None = None, rotation_max: float = VOL_ROTATION_MAX,
                  rotation_pivot: float = VOL_ROTATION_PIVOT, passages: np.ndarray | None = None,
                  rotation_passage: float | None = None) -> np.ndarray:
    """LE REGARD, choisi d'un seul coup sur tout le vol (programmation dynamique) : à chaque instant (une clé toutes les
    CLE_IMAGES images), une direction parmi 72 (tous les 5°) ; la suite retenue maximise ce qu'on voit (profondeur), regarde
    plutôt vers l'avant, se tourne vers le cadrage d'une pièce quand on y est, vers la plus belle profondeur aux demi-tours,
    et tourne doucement (au plus VOL_ROTATION_MAX °/s, chaque degré de rotation coûte un peu). Lisser après coup « moyenne »
    deux bonnes directions… à travers le mur qui les sépare : c'est ce que ce calcul évite. Renvoie un cap par image.

    Planificateur (12/11/2026) : `panoramiques` = [(première image, dernière image, cap, part)] des arrêts au cœur d'une pièce
    en cul-de-sac : la part `part` de l'arrêt regarde le plus beau cadrage, la suite se tourne vers la sortie ;
    `fin_cap` : les dernières secondes regardent ce cadrage (la conclusion) ; `avance_m` : le regard anticipe là où la caméra
    sera dans `avance_m` mètres de chemin (et non dans une seconde : à vitesse lente, une seconde, c'est 20 cm, et le regard ne
    voyait pas venir le virage d'une porte)."""
    pieces_par_id = {p["id"]: p for p in logement["pieces"]}
    panoramiques = panoramiques or []
    from moteur.cinema.navigation import _cotes  # (import tardif : navigation dépend de ce module par trajectoire)
    centres_portes = []
    if REGARD_MAX_PORTE_DEG > VOL_REGARD_MAX_DEG:
        for o in logement.get("ouvertures", []):
            if o["type"] == "porte":
                try:
                    _, a, d, _, _ = _cotes(logement, o)
                except StopIteration:
                    continue
                centres_portes.append(a + d * (o["position"] + o["largeur"] / 2))
    centres_portes = np.array(centres_portes, float).reshape(-1, 2)
    jonctions_libres = [] if panoramiques else jonctions  # avec le planificateur, les arrêts ont leur propre regard
    reveles = [(courbe[min(j, len(courbe) - 1)], regard_profond(voir.rayons(tuple(courbe[min(j, len(courbe) - 1)])), None))
               for j in jonctions_libres]
    angles = np.arange(0, 360, 5.0)
    parcouru = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(positions, axis=0), axis=1))])
    cles_idx = list(range(0, len(positions), CLE_IMAGES))
    if cles_idx[-1] != len(positions) - 1:
        cles_idx.append(len(positions) - 1)
    notes = np.zeros((len(cles_idx), len(angles)))
    for n, k in enumerate(cles_idx):
        p = positions[k]
        rayons = voir.rayons(tuple(p))
        profondeurs = np.array([min(profondeur(rayons, a), 6.0) for a in angles])
        if avance_m is None:
            devant = positions[min(len(positions) - 1, k + IPS)] - p
        else:
            j = min(len(positions) - 1, int(np.searchsorted(parcouru, parcouru[k] + avance_m)))
            # jamais au-delà du prochain arrêt : derrière un demi-tour, « plus loin sur le chemin » est… derrière soi
            j = min([j] + [p[0] for p in panoramiques if p[0] >= k])
            devant = positions[j] - p
        if np.linalg.norm(devant) < 0.05:
            devant = p - positions[max(0, k - IPS)]
        marche = angle(devant) if np.linalg.norm(devant) > 0.05 else None
        avant = np.cos(np.radians(angles - marche)) if marche is not None else np.zeros(len(angles))
        but, poids = None, 0.0
        for xy_j, but_j in reveles:
            w = 1.0 - float(lissee(float(np.linalg.norm(p - xy_j)), 0.3, 1.5))
            if w > poids:
                but, poids = but_j, w
        for e in etapes[1:]:
            if e["genre"] != "point_de_vue" or not rz._dedans(tuple(p), pieces_par_id[e["piece"]]["contour"]):
                continue
            w = 1.0 - float(lissee(float(np.linalg.norm(p - np.asarray(e["xy"]))), 0.5, VOL_RAYON_VUE_M))
            if w > poids:
                but, poids = e["cap"], w
        for debut, fin, cap_pano, part in panoramiques:
            if debut <= k <= debut + part * (fin - debut):  # seulement une fois arrêté (sinon elle recule)
                but, poids = cap_pano, 1.0  # d'abord le plus beau cadrage…
            elif debut + part * (fin - debut) < k <= fin:
                but, poids = None, 0.0  # … puis on se tourne vers là où l'on va repartir
        if fin_cap is not None and k >= len(positions) - FIN_S * IPS:
            w = float(lissee(k - (len(positions) - FIN_S * IPS), 0, IPS))
            if w >= poids:
                but, poids = fin_cap, w
        vers_but = np.cos(np.radians(angles - but)) if but is not None else np.zeros(len(angles))
        notes[n] = profondeurs + 1.6 * avant * (1 - poids) + 2.5 * poids * vers_but - 3.0 * (profondeurs < VOL_MUR_MIN_M)
        if avance_m is not None:  # planificateur : la même règle que le contrôleur, un obstacle proche AU CENTRE de l'image
            ecarts_rayons = np.abs((rayons["angles"][None, :] - angles[:, None] + 180) % 360 - 180)
            centre = np.where(ecarts_rayons <= CENTRE_DEMI_DEG, rayons["distance"][None, :], np.inf).min(1)
            notes[n] -= CENTRE_POIDS * np.clip((CENTRE_MUR_M - centre) / 0.5, 0, 1)
        if marche is not None:  # un travelling regarde là où il va : au-delà de VOL_REGARD_MAX_DEG, fortement pénalisé
            ecart_marche = np.abs((angles - marche + 180) % 360 - 180)
            pres_porte = len(centres_portes) and float(np.linalg.norm(centres_portes - p, axis=1).min()) < PORTE_LIBERTE_M
            dans_passage = passages is not None and bool(passages[k])
            limite = max(VOL_REGARD_MAX_DEG, REGARD_MAX_PORTE_DEG) if (pres_porte or dans_passage) else VOL_REGARD_MAX_DEG
            notes[n] -= 6.0 * np.clip((ecart_marche - limite) / 30.0, 0, None)
    pas_cles = CLE_IMAGES / IPS
    # rotation permise : VOL_ROTATION_MAX en vol, VOL_ROTATION_PIVOT à l'arrêt (vitesse sous 0,15 m/s)
    vites_cles = [float(np.linalg.norm(positions[min(len(positions) - 1, k + 1)] - positions[k]) * IPS) for k in cles_idx]
    saut_max = max(1, int(round(rotation_pivot * pas_cles / 5.0)))  # en crans de 5°
    ecarts = np.arange(-saut_max, saut_max + 1)
    saut_vol = max(1, int(round(rotation_max * pas_cles / 5.0)))
    cout_rotation = 0.03 * np.abs(ecarts) * 5.0
    interdit = np.where(np.abs(ecarts) > saut_vol, 1e6, 0.0)
    if passages is not None and rotation_passage is not None:  # dans les couloirs, le regard peut tourner un peu plus vite
        saut_passage = max(1, int(round(rotation_passage * pas_cles / 5.0)))
        interdit_passage = np.where(np.abs(ecarts) > saut_passage, 1e6, 0.0)
    total = notes[0].copy()
    venu = np.zeros((len(cles_idx), len(angles)), int)
    for n in range(1, len(cles_idx)):
        candidats = np.stack([np.roll(total, -e) for e in ecarts])  # candidats[i, a] = total[a + ecarts[i]]
        borne = interdit_passage if passages is not None and rotation_passage is not None and passages[cles_idx[n]] else interdit
        candidats = candidats - cout_rotation[:, None] - (borne[:, None] if vites_cles[n] > 0.15 else 0.0)
        meilleur = np.argmax(candidats, 0)
        venu[n] = (np.arange(len(angles)) + ecarts[meilleur]) % len(angles)
        total = candidats[meilleur, np.arange(len(angles))] + notes[n]
    suite = [int(np.argmax(total))]
    for n in range(len(cles_idx) - 1, 0, -1):
        suite.append(int(venu[n][suite[-1]]))
    suite = suite[::-1]
    caps_cles = [float(angles[suite[0]])]
    for a in suite[1:]:
        caps_cles.append(caps_cles[-1] + ecart(caps_cles[-1], float(angles[a])))  # déroulé, sans saut de 360°
    caps = np.interp(np.arange(len(positions)), cles_idx, caps_cles)
    return gauss(caps, 0.5 * IPS)  # finition : la rotation démarre et s'arrête en douceur
