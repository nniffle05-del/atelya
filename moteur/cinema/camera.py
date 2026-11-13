"""La caméra elle-même : sa HAUTEUR (1,6 m dans les passages, plus haut dans les grands espaces, toujours au-dessus des meubles
survolés et sous le plafond), sa plongée, et les CLÉS du trajet au format de outils/unreal/cinematique_unreal.py."""
from __future__ import annotations

import numpy as np

from moteur import realisateur as rz
from moteur.cinema.navigation import au_dessus_du_vol, etendue
from moteur.cinema.reglages import (CLE_IMAGES, IPS, SOUS_OBJET_M, SURVOL_MARGE_M, VOL_HAUTEUR_M, VOL_HAUTEUR_MAX_M,
                                    VOL_PLONGEE_PAR_M, VOL_SOUS_PLAFOND_M, VOL_TANGAGE_DEG)
from moteur.cinema.trajectoire import gauss, lissee


def hauteurs_du_vol(positions: np.ndarray, voir: rz.Scene2D, logement: dict) -> tuple[np.ndarray, np.ndarray]:
    """LA HAUTEUR : 1,6 m dans les passages, jusqu'à VOL_HAUTEUR_MAX_M dans les grands espaces ouverts (plan large, comme une
    grue), toujours au moins SURVOL_MARGE_M au-dessus d'un meuble survolé et sous le plafond ; regard plus plongeant en haut.
    Renvoie la hauteur (m) et la plongée (degrés) de chaque image."""
    hsp = float(logement.get("hauteur_sous_plafond") or 2.5)
    plafond_max = hsp - VOL_SOUS_PLAFOND_M
    meubles = [m for m in logement.get("meubles", []) if m.get("position") and m.get("dimensions")]
    # dessous : les meubles qu'on survole (posés au sol, ou trop bas pour passer dessous) ; dessus : les objets suspendus sous
    # lesquels on passe (suspension, étagère haute) : la caméra reste SOUS_OBJET_M plus bas (étape 2, 12/11/2026)
    dessous = [(rz._rectangle_meuble(m), etendue(m)[1]) for m in meubles if not au_dessus_du_vol(m, VOL_HAUTEUR_M)]
    dessus = [(rz._rectangle_meuble(m), etendue(m)[0]) for m in meubles if au_dessus_du_vol(m, VOL_HAUTEUR_M)]
    hauteurs = np.full(len(positions), VOL_HAUTEUR_M)
    plafonds = np.full(len(positions), plafond_max)
    for k in range(0, len(positions), CLE_IMAGES):
        r = voir.rayons(tuple(positions[k]))
        ouvert = float(np.mean(np.minimum(r["distance"], 8.0)))  # la taille de l'espace autour (moyenne des 180 rayons)
        h = VOL_HAUTEUR_M + (VOL_HAUTEUR_MAX_M - VOL_HAUTEUR_M) * float(lissee(ouvert, 1.5, 3.2))
        for poly, haut in dessous:
            if rz._dedans(tuple(positions[k]), [tuple(q) for q in poly]):
                h = max(h, haut + SURVOL_MARGE_M + 0.1)
        hauteurs[k:k + CLE_IMAGES] = min(h, plafond_max)
    for poly, bas in dessus:  # image par image (pas une sur CLE_IMAGES) : le bord de l'objet compte au centimètre
        contour = [tuple(q) for q in poly]
        for k in range(len(positions)):
            if rz._dedans(tuple(positions[k]), contour):
                plafonds[k] = min(plafonds[k], bas - SOUS_OBJET_M)
    hauteurs = gauss(gauss(hauteurs, 1.5 * IPS), 1.0 * IPS)
    if dessus:
        # le plafond local, élargi d'une seconde et demie de part et d'autre puis adouci : la caméra descend AVANT d'arriver
        # sous l'objet (sans jamais passer au-dessus de son plafond), et remonte après
        large = int(1.5 * IPS)
        bas_local = np.array([plafonds[max(0, k - large):k + large + 1].min() for k in range(len(plafonds))])
        hauteurs = np.minimum(hauteurs, np.minimum(gauss(bas_local, 0.5 * IPS), plafonds))
    return hauteurs, VOL_TANGAGE_DEG - VOL_PLONGEE_PAR_M * (hauteurs - VOL_HAUTEUR_M)


def trajet_du_vol(positions: np.ndarray, hauteurs: np.ndarray, caps: np.ndarray, tangages: np.ndarray, focale_mm: float,
                  format_image, scene_eclairage: str | None = None) -> dict:
    """Les clés de la caméra (une toutes les 2 images : elle suit exactement la courbe lisse), au format du trajet d'Unreal."""
    cle = 2
    points = [[round(float(positions[k][0]), 4), round(float(positions[k][1]), 4), round(float(hauteurs[k]), 3),
               round(float(caps[k]), 3), round(float(tangages[k]), 2)] for k in range(0, len(positions), cle)]
    nb_images = (len(points) - 1) * cle + 1
    trajet = {"points": points, "images": nb_images, "ips": IPS, "focale_mm": focale_mm, "format": list(format_image),
              "balade": True, "vol": True}
    if scene_eclairage:
        trajet["scene"] = scene_eclairage
    return trajet
