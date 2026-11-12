"""La caméra elle-même : sa HAUTEUR (1,6 m dans les passages, plus haut dans les grands espaces, toujours au-dessus des meubles
survolés et sous le plafond), sa plongée, et les CLÉS du trajet au format de outils/unreal/cinematique_unreal.py."""
from __future__ import annotations

import numpy as np

from moteur import realisateur as rz
from moteur.cinema.navigation import _hauteur_meuble
from moteur.cinema.reglages import (CLE_IMAGES, IPS, SURVOL_MARGE_M, VOL_HAUTEUR_M, VOL_HAUTEUR_MAX_M, VOL_PLONGEE_PAR_M,
                                    VOL_SOUS_PLAFOND_M, VOL_TANGAGE_DEG)
from moteur.cinema.trajectoire import gauss, lissee


def hauteurs_du_vol(positions: np.ndarray, voir: rz.Scene2D, logement: dict) -> tuple[np.ndarray, np.ndarray]:
    """LA HAUTEUR : 1,6 m dans les passages, jusqu'à VOL_HAUTEUR_MAX_M dans les grands espaces ouverts (plan large, comme une
    grue), toujours au moins SURVOL_MARGE_M au-dessus d'un meuble survolé et sous le plafond ; regard plus plongeant en haut.
    Renvoie la hauteur (m) et la plongée (degrés) de chaque image."""
    hsp = float(logement.get("hauteur_sous_plafond") or 2.5)
    plafond_max = hsp - VOL_SOUS_PLAFOND_M
    meubles_bas = [(rz._rectangle_meuble(m), _hauteur_meuble(m)) for m in logement.get("meubles", [])
                   if m.get("position") and m.get("dimensions")]
    hauteurs = np.full(len(positions), VOL_HAUTEUR_M)
    for k in range(0, len(positions), CLE_IMAGES):
        r = voir.rayons(tuple(positions[k]))
        ouvert = float(np.mean(np.minimum(r["distance"], 8.0)))  # la taille de l'espace autour (moyenne des 180 rayons)
        h = VOL_HAUTEUR_M + (VOL_HAUTEUR_MAX_M - VOL_HAUTEUR_M) * float(lissee(ouvert, 1.5, 3.2))
        for poly, hm in meubles_bas:
            if rz._dedans(tuple(positions[k]), [tuple(q) for q in poly]):
                h = max(h, hm + SURVOL_MARGE_M + 0.1)
        hauteurs[k:k + CLE_IMAGES] = min(h, plafond_max)
    hauteurs = gauss(gauss(hauteurs, 1.5 * IPS), 1.0 * IPS)
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
