"""La LUMIÈRE du film, mesurée sur ses images (cinématique, étape 4, 12/11/2026).

Pourquoi : pour rendre la lumière du film réaliste EN MOUVEMENT, il faut d'abord savoir ce qui ne va pas, chiffres à l'appui, et
pouvoir comparer avant / après sur les mêmes images. Trois défauts possibles, mesurés image par image :
- FENÊTRES BRÛLÉES : la vue du dehors (ciel, sol du dehors) sort en blanc pur, ou « laiteuse » (presque blanche, sans couleur ni
  détail). Repérée par le canal VERT du masque des essais (moteur/unreal/preparer_cinematique._materiau_masque) ;
- ZONES TROP SOMBRES : part de l'intérieur « bouchée » (presque noire) ou sombre ;
- SAUTS D'EXPOSITION : la clarté des murs et plafonds (canal ROUGE du masque, comme le photographe) qui bouge vite d'un moment à
  l'autre, ou qui diffère d'une pièce à l'autre.
Tout se mesure sur ce que verra le client (les images affichées), ramené en lumière « physique » par la courbe de la pellicule à
l'envers (moteur/photographe.lineaire_affiche), en CRANS (1 cran = lumière × 2).
"""
from __future__ import annotations

import math

import numpy as np

from moteur import photographe

SEUIL_BRULE = 250 / 255  # blanc pur : les trois couleurs au plafond
SEUIL_BLANC = 235 / 255  # « laiteux » : presque blanc, plus de couleur ni de détail
SEUIL_BOUCHE = 20 / 255  # presque noir : plus de détail
SEUIL_SOMBRE = 50 / 255
PIXELS_MIN = 30  # en dessous, une zone (murs, dehors) est jugée absente de l'image
SAUT_FENETRE_S = 1.0  # un saut = variation de la clarté des murs en 1 s
SAUT_SEUIL_CRANS = 0.5  # au-delà : visible (un œil remarque un demi-cran qui change en une seconde)
# Un moment BREF (< 1 s) ne compte pas comme un saut : une embrasure à l'ombre qui remplit l'image le temps de passer une porte est
# VRAIMENT plus sombre (vu le 12/11/2026, film v3 à 30,5 s) ; ce qu'on cherche, c'est l'exposition qui reste fausse.
SAUT_MEDIANE_S = 1.0
ECART_VISIBLE_CRANS = 0.5  # murs trop clairs ou trop sombres de plus d'un demi-cran


def _log2(x) -> float:
    return float(math.log2(max(float(x), 1e-9)))


def mesurer_image(rvb: np.ndarray, murs: np.ndarray | None = None, dehors: np.ndarray | None = None,
                  clarte_visee: float = photographe.CLARTE_MURS) -> dict:
    """Mesures d'une image affichée (H × W × 3, valeurs 0..1, rouge-vert-bleu) avec les masques (booléens, même taille) des murs
    et plafonds et du dehors vu par les fenêtres (None = inconnu)."""
    rvb = np.asarray(rvb, float)
    h, w = rvb.shape[:2]
    murs = np.zeros((h, w), bool) if murs is None else np.asarray(murs, bool)
    dehors = np.zeros((h, w), bool) if dehors is None else np.asarray(dehors, bool)
    affiche = rvb @ photographe.POIDS
    mini = rvb.min(axis=2)
    lin = photographe.lineaire_affiche(rvb) @ photographe.POIDS
    m = {"dehors_part": round(float(dehors.mean()), 4)}
    if dehors.sum() >= PIXELS_MIN:
        r, v, b = (rvb[dehors][:, i] for i in range(3))
        maxi = np.maximum(np.maximum(r, v), b)
        saturation = np.where(maxi > 0, (maxi - np.minimum(np.minimum(r, v), b)) / np.maximum(maxi, 1e-6), 0)
        m.update({"dehors_brule": round(float((mini[dehors] >= SEUIL_BRULE).mean()), 4),
                  "dehors_blanc": round(float((mini[dehors] >= SEUIL_BLANC).mean()), 4),
                  "dehors_affiche": round(float(np.median(affiche[dehors])) * 255, 1),
                  "dehors_couleur": round(float(np.median(saturation)), 3),
                  # détail restant dans la vue : écart entre clairs et sombres du dehors, en crans
                  "dehors_detail_crans": round(float(np.subtract(*np.percentile(np.log2(np.maximum(lin[dehors], 1e-6)),
                                                                                  [95, 5]))), 2)})
    if murs.sum() >= PIXELS_MIN:
        mur_lin = float(np.median(lin[murs]))
        m.update({"murs_lineaire": round(mur_lin, 4), "murs_affiche": round(float(np.median(affiche[murs])) * 255, 1),
                  # + : murs plus sombres que visé ; - : plus clairs (même règle que le photographe)
                  "murs_ecart_crans": round(_log2(clarte_visee) - _log2(mur_lin), 3)})
        if dehors.sum() >= PIXELS_MIN:
            m["dehors_sur_murs_crans"] = round(_log2(np.median(lin[dehors])) - _log2(mur_lin), 2)
    dedans = ~dehors
    if dedans.sum() >= PIXELS_MIN:
        ld = np.log2(np.maximum(lin[dedans], 1e-6))
        m.update({"bouche": round(float((affiche[dedans] < SEUIL_BOUCHE).mean()), 4),
                  "sombre": round(float((affiche[dedans] < SEUIL_SOMBRE).mean()), 4),
                  "dedans_brule": round(float((mini[dedans] >= SEUIL_BRULE).mean()), 4),
                  "dedans_affiche": round(float(np.median(affiche[dedans])) * 255, 1),
                  "etendue_crans": round(float(np.subtract(*np.percentile(ld, [95, 5]))), 2)})
    return m


def _mediane_glissante(t: np.ndarray, c: np.ndarray, largeur_s: float) -> np.ndarray:
    return np.array([np.median(c[(t >= x - largeur_s / 2) & (t <= x + largeur_s / 2)]) for x in t])


def sauts(temps: list[float], crans: list[float], fenetre_s: float = SAUT_FENETRE_S,
          seuil: float = SAUT_SEUIL_CRANS, mediane_s: float = SAUT_MEDIANE_S) -> dict:
    """Variations rapides d'une clarté (en crans) au fil du film : la plus forte variation sur `fenetre_s` secondes, et les
    moments où elle dépasse `seuil` (regroupés : un moment par saut). Les moments plus brefs que `mediane_s` sont ignorés
    (médiane glissante d'abord ; 0 = tout compte)."""
    t = np.asarray(temps, float)
    c = np.asarray(crans, float)
    ok = np.isfinite(c)
    t, c = t[ok], c[ok]
    if mediane_s and len(t):
        c = _mediane_glissante(t, c, mediane_s)
    if len(t) < 2:
        return {"max_crans": 0.0, "moments": []}
    variations = []
    for i in range(len(t)):
        j = np.searchsorted(t, t[i] + fenetre_s, side="right") - 1
        if j > i:
            variations.append((float(t[i]), float(c[j] - c[i])))
    if not variations:
        return {"max_crans": 0.0, "moments": []}
    moments = []
    for debut, dv in variations:
        if abs(dv) < seuil:
            continue
        if moments and debut - moments[-1]["fin_s"] <= fenetre_s:
            dernier = moments[-1]
            dernier["fin_s"] = round(debut, 2)
            if abs(dv) > abs(dernier["crans"]):
                dernier["crans"] = round(dv, 2)
        else:
            moments.append({"debut_s": round(debut, 2), "fin_s": round(debut, 2), "crans": round(dv, 2)})
    return {"max_crans": round(max(abs(v) for _, v in variations), 2), "moments": moments}


def _mediane(valeurs) -> float | None:
    v = [x for x in valeurs if x is not None]
    return round(float(np.median(v)), 3) if v else None


def _moyenne(valeurs) -> float | None:
    v = [x for x in valeurs if x is not None]
    return round(float(np.mean(v)), 4) if v else None


def resumer(mesures: list[dict], ips: int = 24) -> dict:
    """Bilan du film d'après les mesures image par image (chacune : « image » (0 = la première), « piece », et les mesures de
    mesurer_image). Fenêtres : moyennes sur les images où l'on voit dehors (≥ 1 % de l'image)."""
    avec_dehors = [m for m in mesures if m.get("dehors_part", 0) >= 0.01 and "dehors_blanc" in m]
    murs = [m for m in mesures if "murs_ecart_crans" in m]
    temps = [m["image"] / ips for m in murs]
    s = sauts(temps, [-m["murs_ecart_crans"] for m in murs])  # clarté des murs (en crans) : + = plus clair
    par_piece = {}
    for m in mesures:
        par_piece.setdefault(m.get("piece") or "?", []).append(m)
    pieces = {}
    for nom, liste in par_piece.items():
        pieces[nom] = {"images": len(liste), "murs_ecart_crans": _mediane(m.get("murs_ecart_crans") for m in liste),
                       "dehors_blanc": _moyenne(m.get("dehors_blanc") for m in liste if m.get("dehors_part", 0) >= 0.01),
                       "sombre": _moyenne(m.get("sombre") for m in liste)}
    ecarts_pieces = [p["murs_ecart_crans"] for p in pieces.values() if p["murs_ecart_crans"] is not None]
    return {
        "images_mesurees": len(mesures),
        "fenetres": {
            "images_avec_dehors": len(avec_dehors),
            "part_du_dehors_brule": _moyenne(m["dehors_brule"] for m in avec_dehors),
            "part_du_dehors_blanc": _moyenne(m["dehors_blanc"] for m in avec_dehors),
            "images_fenetre_laiteuse": sum(1 for m in avec_dehors if m["dehors_blanc"] >= 0.5),
            "couleur_du_dehors": _mediane(m["dehors_couleur"] for m in avec_dehors),
            "detail_du_dehors_crans": _mediane(m["dehors_detail_crans"] for m in avec_dehors),
            "dehors_sur_murs_crans": _mediane(m.get("dehors_sur_murs_crans") for m in avec_dehors),
        },
        "sombre": {"part_bouchee": _moyenne(m.get("bouche") for m in mesures),
                   "part_sombre": _moyenne(m.get("sombre") for m in mesures),
                   "images_sombres_10pc": sum(1 for m in mesures if m.get("sombre", 0) >= 0.10),
                   "etendue_crans": _mediane(m.get("etendue_crans") for m in mesures)},
        "exposition": {"murs_ecart_median_crans": _mediane(m["murs_ecart_crans"] for m in murs),
                       "murs_trop_clairs": round(float(np.mean([m["murs_ecart_crans"] < -ECART_VISIBLE_CRANS for m in murs])), 3)
                       if murs else None,
                       "murs_trop_sombres": round(float(np.mean([m["murs_ecart_crans"] > ECART_VISIBLE_CRANS for m in murs])), 3)
                       if murs else None,
                       "murs_ecart_max_crans": round(max((abs(m["murs_ecart_crans"]) for m in murs), default=0.0), 2),
                       "saut_max_crans_par_s": s["max_crans"], "sauts": s["moments"],
                       "ecart_entre_pieces_crans": round(max(ecarts_pieces) - min(ecarts_pieces), 2) if ecarts_pieces else None},
        "pieces": pieces,
    }


# Les chiffres comparés avant / après (sur les mêmes images du même vol), avec le sens du mieux.
COMPARES = [
    ("Fenêtres : part du dehors en blanc pur", ("fenetres", "part_du_dehors_brule"), "bas"),
    ("Fenêtres : part du dehors presque blanc (laiteux)", ("fenetres", "part_du_dehors_blanc"), "bas"),
    ("Fenêtres : images où la vue est laiteuse (> 50 %)", ("fenetres", "images_fenetre_laiteuse"), "bas"),
    ("Fenêtres : couleur gardée dans la vue (0..1)", ("fenetres", "couleur_du_dehors"), "haut"),
    ("Fenêtres : détail dans la vue (crans)", ("fenetres", "detail_du_dehors_crans"), "haut"),
    ("Intérieur : part bouchée (< 20/255)", ("sombre", "part_bouchee"), "bas"),
    ("Intérieur : part sombre (< 50/255)", ("sombre", "part_sombre"), "bas"),
    ("Intérieur : étendue des clartés (crans)", ("sombre", "etendue_crans"), None),
    ("Murs : écart médian à la visée (crans)", ("exposition", "murs_ecart_median_crans"), "zero"),
    ("Murs : pire écart à la visée (crans)", ("exposition", "murs_ecart_max_crans"), "bas"),
    ("Murs : part du film trop clairs (> 0,5 cran)", ("exposition", "murs_trop_clairs"), "bas"),
    ("Murs : part du film trop sombres (> 0,5 cran)", ("exposition", "murs_trop_sombres"), "bas"),
    ("Murs : plus forte variation durable en 1 s (crans)", ("exposition", "saut_max_crans_par_s"), "bas"),
    ("Murs : écart entre pièces (crans)", ("exposition", "ecart_entre_pieces_crans"), "bas"),
]


def comparer(avant: dict, apres: dict) -> list[dict]:
    """Les chiffres de deux bilans (resumer) côte à côte, avec « mieux » / « moins bien » / « = »."""
    lignes = []
    for nom, (bloc, cle), sens in COMPARES:
        a, b = avant.get(bloc, {}).get(cle), apres.get(bloc, {}).get(cle)
        verdict = ""
        if a is not None and b is not None and sens:
            gain = {"bas": a - b, "haut": b - a, "zero": abs(a) - abs(b)}[sens]
            verdict = "=" if abs(gain) < 1e-3 + 0.02 * max(abs(a), abs(b)) else ("mieux" if gain > 0 else "moins bien")
        lignes.append({"chiffre": nom, "avant": a, "apres": b, "verdict": verdict})
    return lignes
