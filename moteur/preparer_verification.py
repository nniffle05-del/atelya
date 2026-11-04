"""Prépare le fichier de l'écran de vérification (format verification/0.1) à partir d'une lecture complète.

Le calage dit où poser les mètres lus sur l'image que l'écran affiche. La lecture passe par plusieurs repères :
image pleine taille → réduite à 768 px (le coloriage) → tournée, ou remise à plat pour une photo de biais → mètres.
La matrice du calage fait tout ce chemin à l'envers, des mètres vers les pixels de l'image pleine taille.

Convention : à l'écran comme dans le traducteur, le pixel n° i couvre l'intervalle [i, i + 1] ; pour OpenCV (rotation,
redressement), le pixel n° i est centré sur i. D'où le décalage d'un demi-pixel de part et d'autre de ces deux étapes.
Sans lui, le dessin glisserait d'un demi-pixel de coloriage, soit plus d'un pixel sur une grande image.
"""
from __future__ import annotations

import numpy as np

from moteur.coloriage import _rotation
from moteur.lecture_complete import PlanLu

VERSION_PREPARATEUR = "0.1.0"
SCHEMA = "verification/0.1"
ANGLE_NUL = 0.01  # degrés : en dessous, le traducteur ne tourne pas le coloriage


def _decalage(d: float) -> np.ndarray:
    return np.array([[1.0, 0.0, d], [0.0, 1.0, d], [0.0, 0.0, 1.0]])


def matrice_calage(details: dict, forme_coloriage: tuple[int, int], forme_image: tuple[int, int], redressement=None) -> np.ndarray:
    """La matrice 3 × 3 : point en mètres → pixel de l'image pleine taille (pixel n° i = intervalle [i, i + 1])."""
    s = details["px_par_m"]
    ox, oy = details["origine_px"]
    vers_repere = np.array([[s, 0.0, ox], [0.0, -s, oy], [0.0, 0.0, 1.0]])  # mètres → repère lu (y vers le bas)
    if redressement is not None:
        coloriage_vers_repere = np.asarray(redressement.H, float)
    elif abs(details.get("angle_deg", 0.0)) >= ANGLE_NUL:
        m, _, _ = _rotation(forme_coloriage, details["angle_deg"])
        coloriage_vers_repere = np.vstack([m, [0.0, 0.0, 1.0]])
    else:
        coloriage_vers_repere = np.eye(3)
    h_c, l_c = forme_coloriage[:2]
    h_i, l_i = forme_image[:2]
    vers_image = np.diag([l_i / l_c, h_i / h_c, 1.0])  # réduction un peu différente en largeur et en hauteur (arrondis)
    M = vers_image @ _decalage(0.5) @ np.linalg.inv(coloriage_vers_repere) @ _decalage(-0.5) @ vers_repere
    return M / M[2, 2]


def projeter(M: np.ndarray, x: float, y: float) -> tuple[float, float]:
    """Le pixel d'un point en mètres (même calcul que pointVersPixel de l'écran)."""
    u, v, w = M @ (x, y, 1.0)
    return float(u / w), float(v / w)


def zone_en_pixels(M: np.ndarray, zone_m) -> list[float]:
    """Une zone en mètres (x0, y0, x1, y1) → le rectangle [x, y, largeur, hauteur] qui l'englobe sur l'image."""
    x0, y0, x1, y1 = zone_m
    pts = np.array([projeter(M, a, b) for a in (x0, x1) for b in (y0, y1)])
    (u0, v0), (u1, v1) = pts.min(0), pts.max(0)
    return [round(float(u0), 1), round(float(v0), 1), round(float(u1 - u0), 1), round(float(v1 - v0), 1)]


def _echelle(echelle: dict) -> dict:
    sortie = {"etat": echelle["etat"], "source": echelle.get("source")}
    if echelle.get("raison"):
        sortie["raison"] = echelle["raison"]
    return sortie


def verification_du_plan(plan: PlanLu, nom_image: str = "plan.png") -> dict | None:
    """Le contenu de verification.json ; None pour un plan refusé (rien à montrer : pas d'écran)."""
    g = plan.gardee
    if plan.decision == "refuse" or g.logement is None or g.details is None:
        return None
    M = matrice_calage(g.details, g.coloriage.shape, plan.source.image.shape, g.redressement)
    doutes = []
    for d in g.examen["doutes"]:
        sortie = {"element": d.get("element"), "raison": d["raison"], "code": d["code"], "gravite": d["gravite"]}
        if d.get("zone_m"):
            sortie["zone_px"] = zone_en_pixels(M, d["zone_m"])
        doutes.append(sortie)
    return {"schema": SCHEMA, "plan": nom_image, "calage": {"matrice": [[round(float(v), 10) for v in ligne] for ligne in M]},
            "echelle": _echelle(g.echelle), "logement": g.logement, "doutes": doutes,
            "lecture": {"decision": plan.decision, "modele": g.modele, "aiguillage": plan.aiguillage, "preparateur": VERSION_PREPARATEUR}}
