"""Le CADRE de la photo pour la caméra du film (sorti de moteur/juge_lumiere.py le 25/11/2026).

Module LÉGER exprès (math seulement) : outils/unreal/vues_photos_unreal.py en a besoin pendant tout un tournage, et l'importer
depuis juge_lumiere chargeait PyTorch (plus d'1 Go de mémoire gardé pendant le rendu d'Unreal, sur un PC de 16 Go : le 25/11 un
tournage a planté, mémoire pleine). Ne rien importer de lourd ici.
"""
from __future__ import annotations

import math

CAPTEUR_MM = 36.0


def cadre_du_film(d: dict) -> dict:
    """Le cadrage EXACT de la photo par la caméra du film. L'appareil de la photo regarde à l'horizontale avec l'horizon
    décalé dans l'image (les verticales restent verticales, comme le font les photographes d'annonces) ; une caméra de film
    regarde au centre de son image. Le film est donc tourné sur une image plus grande, centrée sur le point de fuite de la
    photo, puis ROGNÉ au cadre de la photo : mêmes points aux mêmes pixels, sans pencher la caméra.
    Rend {tangage, focale_mm, format [largeur, hauteur], rognage [colonne, ligne, largeur, hauteur]}."""
    c = d["camera"]
    largeur, hauteur = int(d.get("largeur", 1206)), int(d.get("hauteur", 804))
    f, u0, v0 = float(c["f"]), float(c.get("u0", largeur / 2)), float(c["v0"])
    demi_l = int(math.ceil(max(u0, largeur - u0)))
    demi_h = int(math.ceil(max(v0, hauteur - v0)))
    grand = [2 * demi_l, 2 * demi_h]
    return {"tangage": float(c.get("tangage", 0.0)), "focale_mm": round(f * CAPTEUR_MM / grand[0], 4), "format": grand,
            "rognage": [int(round(demi_l - u0)), int(round(demi_h - v0)), largeur, hauteur]}
