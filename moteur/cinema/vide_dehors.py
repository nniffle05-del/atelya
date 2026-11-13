"""Combien de VIDE la caméra du film cadre par les fenêtres (13/11/2026) : un outil de MESURE.

Pourquoi : la vraie vue par les fenêtres ne montre que ce que les photos du client montrent (règle NT : rien de recopié ni de
fabriqué). Les photos, prises du fond des pièces et plus bas que la caméra du film (0,8 à 1,4 m contre 1,6 à 1,9 m), ne voient
jamais le pied des immeubles d'en face ni la rue : sous la vue, le décor est une surface unie. Quand la caméra s'avance vers une
fenêtre, « on voit qu'en dessous il n'y a rien » (NT).

Comment : la fabrique du décor (outils/unreal/vue_dehors_photos.py) garde pour chaque toile le masque de ce qui est SOUS la
vue (vue_dehors.sous_la_vue). Pour chaque image clé du vol, on lance les rayons de la caméra qui sortent par les fenêtres
(vue_dehors.masque_fenetres : murs, balcons pleins) et on regarde où ils tombent : sur la rue, ou sur une toile sous la vue =
du VIDE. `mesurer` donne la part de l'image sur du vide, clé par clé.

Essais du 13/11/2026 sur app-002 (vol de 46 s) : 21,5 s avec du vide (> VIDE_MAX), jusqu'à 6,3 % de l'image. RELEVER LE REGARD
n'y change rien (essayé jusqu'à +15°, retiré du code) : ce qu'on voit par une fenêtre dépend de la PLACE de la caméra par
rapport à l'appui ou au garde-corps, pas de son inclinaison ; la fenêtre reste dans l'image. BAISSER la caméra à la hauteur des
photos n'en retire qu'une partie (1,2 m : 17,6 s, 3,6 % au plus ; 1,0 m : 15,2 s, 2,9 %) et frôle les meubles : non retenu.
Retenu (idée de NT) : le REGARD du vol évite les directions qui cadrent du vide (`regard_sans_vide`), sauf aux moments
où la caméra montre une pièce (regard.VIDE_CADRAGE).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from moteur import vue_dehors

VIDE_MAX = 0.004  # part de l'image admise sur du vide (0,4 % : une frange au bas d'une fenêtre)
LARGEUR_PX = 192  # les rayons : une image de 192 px de large


def charger(dossier: Path) -> dict | None:
    """Ce que le décor couvre (vues-dehors.json de la fabrique du décor) : toiles et masques « sous la vue »."""
    f = Path(dossier) / "vues-dehors.json"
    if not f.is_file():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    toiles = []
    for t in d.get("couverture", []):
        m = cv2.imdecode(np.fromfile(t["sous_la_vue"], np.uint8), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        toiles.append({**t, "n": np.array(t["n"], float), "origine": np.array(t["origine"], float),
                       "axe_u": np.array(t["axe_u"], float), "masque": m > 127})
    return {"toiles": toiles, "niveau_rue": float(d.get("niveau_rue_m", vue_dehors.Z_BAS_M))} if toiles else None


def part_de_vide(cam, taille, ouvertures, murs, balcons, decor: dict) -> float:
    """Part de l'image (0 à 1) où la caméra `cam` ([x, y, z, cap, tangage, f, u0, v0]) voit, par une fenêtre, la rue ou une
    toile SOUS la vue des photos."""
    largeur, hauteur = taille
    vue, _ = vue_dehors.masque_fenetres(cam, taille, ouvertures, murs, balcons=balcons)
    if not vue.any():
        return 0.0
    vs, us = np.nonzero(vue)
    d = vue_dehors._rayons(cam, us.astype(float), vs.astype(float))
    c = np.array(cam[:3], float)
    t_min = np.full(len(d), np.inf)
    vide = np.zeros(len(d), bool)
    for t in decor["toiles"]:
        dn = d[:, 0] * t["n"][0] + d[:, 1] * t["n"][1]
        ok = dn > 1e-6
        tt = (t["decalage"] - float(c[:2] @ t["n"])) / np.where(ok, dn, 1.0)
        p = c[None, :] + tt[:, None] * d
        a = (p - t["origine"][None, :]) @ t["axe_u"]
        b = t["origine"][2] - p[:, 2]
        ok &= (tt > 0) & (a >= 0) & (a < t["longueur_u"]) & (b >= 0) & (b < t["longueur_v"]) & (tt < t_min)
        m = t["masque"]
        col = np.clip((a / t["longueur_u"] * m.shape[1]).astype(int), 0, m.shape[1] - 1)
        lig = np.clip((b / t["longueur_v"] * m.shape[0]).astype(int), 0, m.shape[0] - 1)
        vide = np.where(ok, m[lig, col], vide)
        t_min = np.where(ok, tt, t_min)
    descend = d[:, 2] < -1e-6
    t_rue = np.where(descend, (decor["niveau_rue"] - c[2]) / np.where(descend, d[:, 2], -1.0), np.inf)
    vide |= t_rue < t_min  # la rue avant toute toile (ou aucune toile dans cette direction, en regardant vers le bas)
    return float(vide.sum()) / (largeur * hauteur)


def mesurer(trajet: dict, logement: dict, decor: dict, tangages: np.ndarray | None = None) -> np.ndarray:
    """Part de vide de chaque clé du trajet (points [x, y, z, cap, tangage]) ; `tangages` remplace ceux du trajet."""
    pts = np.array(trajet["points"], float)
    largeur = LARGEUR_PX
    hauteur = int(round(largeur * trajet["format"][1] / trajet["format"][0]))
    f = largeur * float(trajet["focale_mm"]) / 36.0
    ouv = vue_dehors.ouvertures_vitrees(logement)
    murs = vue_dehors.murs_et_trous(logement)
    tg = pts[:, 4] if tangages is None else tangages
    return np.array([part_de_vide([p[0], p[1], p[2], p[3], tg[i], f, largeur / 2, hauteur / 2], (largeur, hauteur), ouv, murs,
                                  logement.get("balcons"), decor) for i, p in enumerate(pts)])


VIDE_TOLERE = 0.02  # part de l'image sur du vide qui ne coûte rien au regard (essayé à 0,4 % : les chambres ne montraient plus leur fenêtre)
VIDE_PLEIN = 0.05  # à partir de cette part de l'image sur du vide, une direction de regard coûte le maximum
_GARDE: dict = {}  # parts de vide déjà calculées (par décor)


def regard_sans_vide(logement: dict, decor: dict, focale_mm: float, format_image, hauteur_m: float, tangage_deg: float):
    """Pour le choix du REGARD du vol (moteur/cinema/regard.py) : une fonction (xy, cap) → coût de 0 à 1 de regarder dans
    cette direction depuis cet endroit, d'après la part de l'image qui tomberait sur du vide (1 dès VIDE_PLEIN). NT,
    13/11/2026 : « quand il sait que sur certains angles on voit le bas où il n'y a rien, pourquoi ne les évite-t-il pas ? »
    La caméra peut toujours regarder une fenêtre de là où la vue des photos la couvre ; ailleurs, elle regarde autre chose.
    Hauteur et plongée : celles du vol courant. Rayons sur une image de 96 px ; résultats gardés (les plans de vol candidats
    repassent aux mêmes endroits)."""
    largeur = 96
    hauteur = int(round(largeur * format_image[1] / format_image[0]))
    f = largeur * float(focale_mm) / 36.0
    demi_champ = float(np.degrees(np.arctan(largeur / 2 / f))) + 3.0
    ouv = vue_dehors.ouvertures_vitrees(logement)
    murs = vue_dehors.murs_et_trous(logement)
    balcons = logement.get("balcons")
    bouts = np.array([q for o in ouv for q in (o["a"], o["b"], (o["a"] + o["b"]) / 2)], float).reshape(-1, 2)
    garde = _GARDE.setdefault((id(decor), largeur, round(hauteur_m, 2), round(tangage_deg, 1)), {})

    def cout(xy, cap: float) -> float:
        cle = (round(float(xy[0]), 2), round(float(xy[1]), 2), round(float(cap)) % 360)
        if cle not in garde:
            v = 0.0
            if len(bouts):
                vers = np.degrees(np.arctan2(bouts[:, 1] - xy[1], bouts[:, 0] - xy[0]))
                if (np.abs((vers - cap + 180) % 360 - 180) < demi_champ).any():  # une fenêtre peut être dans l'image
                    v = part_de_vide([float(xy[0]), float(xy[1]), hauteur_m, float(cap), tangage_deg, f, largeur / 2,
                                      hauteur / 2], (largeur, hauteur), ouv, murs, balcons, decor)
            garde[cle] = v
        return float(np.clip((garde[cle] - VIDE_TOLERE) / (VIDE_PLEIN - VIDE_TOLERE), 0.0, 1.0))
    return cout
