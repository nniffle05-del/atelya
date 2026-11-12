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
                  logement: dict) -> np.ndarray:
    """LE REGARD, choisi d'un seul coup sur tout le vol (programmation dynamique) : à chaque instant (une clé toutes les
    CLE_IMAGES images), une direction parmi 72 (tous les 5°) ; la suite retenue maximise ce qu'on voit (profondeur), regarde
    plutôt vers l'avant, se tourne vers le cadrage d'une pièce quand on y est, vers la plus belle profondeur aux demi-tours,
    et tourne doucement (au plus VOL_ROTATION_MAX °/s, chaque degré de rotation coûte un peu). Lisser après coup « moyenne »
    deux bonnes directions… à travers le mur qui les sépare : c'est ce que ce calcul évite. Renvoie un cap par image."""
    pieces_par_id = {p["id"]: p for p in logement["pieces"]}
    reveles = [(courbe[min(j, len(courbe) - 1)], regard_profond(voir.rayons(tuple(courbe[min(j, len(courbe) - 1)])), None))
               for j in jonctions]
    angles = np.arange(0, 360, 5.0)
    cles_idx = list(range(0, len(positions), CLE_IMAGES))
    if cles_idx[-1] != len(positions) - 1:
        cles_idx.append(len(positions) - 1)
    notes = np.zeros((len(cles_idx), len(angles)))
    for n, k in enumerate(cles_idx):
        p = positions[k]
        rayons = voir.rayons(tuple(p))
        profondeurs = np.array([min(profondeur(rayons, a), 6.0) for a in angles])
        devant = positions[min(len(positions) - 1, k + IPS)] - p
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
        vers_but = np.cos(np.radians(angles - but)) if but is not None else np.zeros(len(angles))
        notes[n] = profondeurs + 1.6 * avant * (1 - poids) + 2.5 * poids * vers_but - 3.0 * (profondeurs < VOL_MUR_MIN_M)
        if marche is not None:  # un travelling regarde là où il va : au-delà de VOL_REGARD_MAX_DEG, fortement pénalisé
            ecart_marche = np.abs((angles - marche + 180) % 360 - 180)
            notes[n] -= 6.0 * np.clip((ecart_marche - VOL_REGARD_MAX_DEG) / 30.0, 0, None)
    pas_cles = CLE_IMAGES / IPS
    # rotation permise : VOL_ROTATION_MAX en vol, VOL_ROTATION_PIVOT à l'arrêt (vitesse sous 0,15 m/s)
    vites_cles = [float(np.linalg.norm(positions[min(len(positions) - 1, k + 1)] - positions[k]) * IPS) for k in cles_idx]
    saut_max = max(1, int(round(VOL_ROTATION_PIVOT * pas_cles / 5.0)))  # en crans de 5°
    ecarts = np.arange(-saut_max, saut_max + 1)
    saut_vol = max(1, int(round(VOL_ROTATION_MAX * pas_cles / 5.0)))
    cout_rotation = 0.03 * np.abs(ecarts) * 5.0
    interdit = np.where(np.abs(ecarts) > saut_vol, 1e6, 0.0)
    total = notes[0].copy()
    venu = np.zeros((len(cles_idx), len(angles)), int)
    for n in range(1, len(cles_idx)):
        candidats = np.stack([np.roll(total, -e) for e in ecarts])  # candidats[i, a] = total[a + ecarts[i]]
        candidats = candidats - cout_rotation[:, None] - (interdit[:, None] if vites_cles[n] > 0.15 else 0.0)
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
