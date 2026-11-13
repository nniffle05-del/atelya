"""Caméra d'une photo du client : retrouver d'où et dans quelle direction la photo a été prise (B2 temps 2, étape 4, 09/11/2026).

Pourquoi : pour comparer la maquette à une photo, il faut la regarder depuis le MÊME endroit, dans la MÊME direction, avec le
même objectif ; sinon on compare deux vues différentes (défaut relevé par NT à l'étape 3). Plus tard, la brique photos s'en
servira pour savoir quelle partie du sol ou des murs chaque photo montre.

Méthode (celle des outils de « camera matching ») : sur la photo, on relève des arêtes dont on connaît la place dans le
logement (angle vertical de deux murs, pied d'un mur, haut d'un mur, montant de fenêtre ou de porte). Le calcul cherche la
caméra qui fait tomber ces arêtes à leur place sur la photo (moindres carrés, méthode de Levenberg-Marquardt).

La caméra est celle d'un photographe d'immobilier : tenue de NIVEAU (les verticales restent droites sur la photo), avec un
éventuel décentrement vertical (le centre optique n'est pas au milieu de l'image). Paramètres, dans cet ordre :
    x, y, z (m, repère du logement), cap (degrés, 0 = vers +x, sens inverse des aiguilles d'une montre), tangage (degrés,
    0 = de niveau), f (focale en pixels de la photo), u0, v0 (centre optique en pixels).
Repères (« reperes ») :
    {"type": "ligne", "a": [x, y, z], "b": [x, y, z], "p1": [u, v], "p2": [u, v]} : deux points de la photo posés sur la
        droite qui passe par a et b (il suffit qu'ils soient SUR l'arête, pas à ses bouts) ;
    {"type": "point", "p": [x, y, z], "uv": [u, v]} : un point précis.
"""
from __future__ import annotations

import math

import numpy as np

CAPTEUR_MM = 36.0  # largeur du capteur « plein format » utilisée pour traduire la focale en millimètres dans Blender
NOMS = ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")


def axes(cap: float, tangage: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Direction de visée, droite et haut de l'image (vecteurs unitaires)."""
    c, s = math.cos(math.radians(cap)), math.sin(math.radians(cap))
    ct, st = math.cos(math.radians(tangage)), math.sin(math.radians(tangage))
    vue = np.array([c * ct, s * ct, st])
    droite = np.array([s, -c, 0.0])
    return vue, droite, np.cross(droite, vue)


def projeter(point, cam) -> tuple[float, float, float]:
    """(u, v, profondeur) d'un point 3D sur la photo. Profondeur ≤ 0 : derrière l'appareil."""
    x, y, z, cap, tangage, f, u0, v0 = cam
    vue, droite, haut = axes(cap, tangage)
    r = np.asarray(point, float) - np.array([x, y, z])
    p = float(r @ vue)
    return u0 + f * float(r @ droite) / p, v0 - f * float(r @ haut) / p, p


def residus(cam, reperes: list[dict]) -> np.ndarray:
    """Écarts en pixels entre la photo et la maquette vue par cette caméra (2 nombres par repère)."""
    r = []
    for rep in reperes:
        if rep["type"] == "ligne":
            ua, va, _ = projeter(rep["a"], cam)
            ub, vb, _ = projeter(rep["b"], cam)
            n = np.array([vb - va, -(ub - ua)])
            n = n / (np.linalg.norm(n) + 1e-12)
            for uo, vo in (rep["p1"], rep["p2"]):
                r.append(float(n @ np.array([uo - ua, vo - va])))  # distance du point relevé à l'arête projetée
        else:
            u, v, _ = projeter(rep["p"], cam)
            r += [u - rep["uv"][0], v - rep["uv"][1]]
    return np.array(r)


def ajuster(cam, reperes: list[dict], libres=(0, 1, 2, 3, 5, 7), rappels: dict | None = None,
            tours: int = 300) -> tuple[np.ndarray, np.ndarray]:
    """Caméra qui colle le mieux aux repères, en partant de `cam`.

    libres : indices des paramètres ajustés (par défaut : tangage nul, centre optique au milieu en largeur).
    rappels : {indice: (valeur, poids)} ; un paramètre mal fixé par les repères (souvent la focale, ou la hauteur) est tiré
    doucement vers une valeur plausible ; poids = pixels d'écart comptés par unité d'écart au rappel.
    Rend (caméra, écarts en pixels)."""
    cam = np.array(cam, float)
    libres = list(libres)
    rappels = rappels or {}

    def ecarts(c):
        r = list(residus(c, reperes))
        r += [(c[i] - val) * poids for i, (val, poids) in rappels.items()]
        return np.array(r)

    lam = 1e-2
    r = ecarts(cam)
    cout = float(r @ r)
    for _ in range(tours):
        J = np.zeros((len(r), len(libres)))
        for j, i in enumerate(libres):
            h = 1e-4 * max(1.0, abs(cam[i]))
            c2 = cam.copy()
            c2[i] += h
            J[:, j] = (ecarts(c2) - r) / h
        A, g = J.T @ J, J.T @ r
        pas = None
        while lam < 1e8:
            pas = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            c2 = cam.copy()
            c2[libres] += pas
            r2 = ecarts(c2)
            if float(r2 @ r2) < cout:
                cam, r, cout = c2, r2, float(r2 @ r2)
                lam = max(lam / 3, 1e-7)
                break
            lam *= 4
        if lam >= 1e8 or pas is None or np.abs(pas).max() < 1e-7:
            break
    return cam, residus(cam, reperes)


def pour_blender(cam, largeur: int, hauteur: int) -> dict:
    """Réglages de la caméra Blender équivalente : focale (mm, capteur 36 mm en largeur), décentrement, rotation (degrés)."""
    x, y, z, cap, tangage, f, u0, v0 = (float(v) for v in cam)
    return {
        "position": [x, y, z],
        "rotation_deg": [90.0 + tangage, 0.0, cap - 90.0],  # Blender : la caméra regarde le long de son -Z local
        "focale_mm": f * CAPTEUR_MM / largeur,
        "capteur_mm": CAPTEUR_MM,
        "decentrement": [(largeur / 2 - u0) / largeur, (v0 - hauteur / 2) / largeur],
        "format": [largeur, hauteur],
    }


def camera_depuis_dict(d: dict) -> list[float]:
    return [float(d.get(n, 0.0)) for n in NOMS]
