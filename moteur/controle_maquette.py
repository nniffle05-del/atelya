"""Contrôle automatique d'une maquette : y a-t-il un jour (un trou) dans le sol ou dans le plafond ? (étape B1, 08/11/2026)

Pourquoi : sur le premier vrai plan rendu (fr-031), un filet de ciel passait entre le sol et le mur, un filet de lumière sous
le plafond, et de petits carrés noirs aux jonctions des murs. Un client ne pardonne pas ça. Ce contrôle le voit sans lancer
Blender : vu de dessus, tout ce qui ferme le BAS de la maquette (murs posés au sol, sols, seuils) doit couvrir l'intérieur du
logement sans trou ; de même pour le HAUT (murs qui montent au plafond, linteaux, plafonds).

Méthode : les briques sont dessinées sur une grille fine (PAS = 4 mm) ; un trou est une zone vide qui ne touche pas le bord de
la grille (le dehors). Un jour plus fin que la grille peut échapper au contrôle (il se voit aussi beaucoup moins au rendu).
"""
from __future__ import annotations

import cv2
import numpy as np

from moteur.geometrie import Brique, _sens_direct

VERSION_CONTROLE = "0.1.0"
PAS = 0.004  # m : taille d'une case de la grille
MARGE = 0.10  # m : bord vide autour de la maquette (le dehors)
AIRE_MIN = 2  # cases : en dessous, ce n'est qu'un arrondi de dessin
SOUS_PIXEL = 8  # bits de précision sous la case pour dessiner les contours (cv2.fillPoly, shift)


def _grille(briques: list[Brique]) -> tuple[float, float, int, int]:
    xs = [p[0] for b in briques for p in b.contour]
    ys = [p[1] for b in briques for p in b.contour]
    x0, y0 = min(xs) - MARGE, min(ys) - MARGE
    return x0, y0, int((max(xs) + MARGE - x0) / PAS) + 1, int((max(ys) + MARGE - y0) / PAS) + 1


def _dessiner(briques: list[Brique], x0: float, y0: float, forme: tuple[int, int]) -> np.ndarray:
    m = np.zeros(forme, np.uint8)
    k = 1 << SOUS_PIXEL
    for b in briques:
        pts = np.array([[(x - x0) / PAS * k, (y - y0) / PAS * k] for x, y in b.contour], np.int64).astype(np.int32)
        cv2.fillPoly(m, [pts], 1, lineType=cv2.LINE_8, shift=SOUS_PIXEL)
    return m


def _trous(couvert: np.ndarray, x0: float, y0: float) -> list[dict]:
    n, etiq, stats, _ = cv2.connectedComponentsWithStats((couvert == 0).astype(np.uint8), connectivity=4)
    H, W = couvert.shape
    dehors = set(np.unique(np.concatenate([etiq[0], etiq[-1], etiq[:, 0], etiq[:, -1]])).tolist())
    sortie = []
    for i in range(1, n):
        if i in dehors or stats[i, cv2.CC_STAT_AREA] < AIRE_MIN:
            continue
        x, y, w, h, a = (int(v) for v in stats[i])
        sortie.append({"x": round(x0 + x * PAS, 3), "y": round(y0 + y * PAS, 3), "largeur": round(w * PAS, 3),
                       "hauteur": round(h * PAS, 3), "aire_m2": round(a * PAS * PAS, 5),
                       "epaisseur": round(_epaisseur((etiq[y:y + h, x:x + w] == i).astype(np.uint8)), 3)})
    return sorted(sortie, key=lambda t: -t["aire_m2"])


FENTE_MAX = 0.06  # m : un trou moins épais que ça (voir _epaisseur) est une fente (imprécision), bouchée ; au-delà : signalé
# Au-delà d'une fente, un trou est encore bouché s'il est petit (B1, mesuré sur les 20 vrais plans de Fable : 0,1 à 0,9 m²) :
VIDE_ENCLOS_MAX = 2.0  # m² : vide fermé par des murs, sans pièce (gaine, niche fermée, double mur) : rempli comme un mur
MORCEAU_DE_PIECE_MAX = 1.0  # m² : morceau de pièce sans sol, touchant la pièce : complété avec son sol et son plafond
ZONE_SIGNALEE_MIN = 0.25  # m² : un trou restant plus grand est signalé à l'écran de vérification (trous_a_signaler)
VIDE_SIGNALE_MIN = 0.5  # m² : un vide rempli comme une gaine plus grand que ça est signalé (WC, placard oublié ?)


def _epaisseur(trou: np.ndarray) -> float:
    """L'épaisseur d'un trou en mètres : le diamètre du plus grand cercle qui y tient (une fente penchée de 2 m de long
    reste une fente de quelques centimètres ; sa boîte englobante, elle, serait grande)."""
    d = cv2.distanceTransform(np.pad(trou, 1), cv2.DIST_L2, 3)
    return float(2 * d.max() * PAS)


def jours_a_boucher(briques: list[Brique], hauteur_sous_plafond: float) -> list[Brique]:
    """Les petites briques qui bouchent les FENTES restantes (dernier filet de sécurité de B1, après le calage des sols et
    le raccord des murs). Fente touchant une pièce : un morceau de sol (et de plafond) de cette pièce, même matériau.
    Vide enclos par des murs (fente, gaine, niche fermée : moins de VIDE_ENCLOS_MAX) : plein, comme un mur, du sol au plafond.
    Morceau de pièce sans sol (moins de MORCEAU_DE_PIECE_MAX) : complété avec le sol et le plafond de la pièce. Plus grand
    (pièce oubliée, terrasse, partie commune…) : jamais bouché en silence, trous_a_signaler() le dit à l'écran de vérification."""
    if not briques:
        return []
    x0, y0, W, H = _grille(briques)
    hsp = hauteur_sous_plafond
    murs = [b for b in briques if b.categorie == "mur"]
    pieces = [b for b in briques if b.categorie == "sol" and b.id.startswith("sol__")]
    etiquettes = np.zeros((H, W), np.int32)
    k = 1 << SOUS_PIXEL
    for i, b in enumerate(pieces, start=1):
        pts = np.array([[(x - x0) / PAS * k, (y - y0) / PAS * k] for x, y in b.contour], np.int64).astype(np.int32)
        cv2.fillPoly(etiquettes, [pts], i, lineType=cv2.LINE_8, shift=SOUS_PIXEL)
    sortie: list[Brique] = []
    vus: set[tuple] = set()
    for nom, groupe, z in (("sol", [b for b in briques if b.categorie == "sol"] + [b for b in murs if b.z_bas <= 1e-6], 0.0),
                           ("plafond", [b for b in briques if b.categorie == "plafond"]
                            + [b for b in murs if b.z_haut >= hsp - 1e-6], hsp)):
        couvert = _dessiner(groupe, x0, y0, (H, W))
        n, etiq, stats, _ = cv2.connectedComponentsWithStats((couvert == 0).astype(np.uint8), connectivity=4)
        dehors = set(np.unique(np.concatenate([etiq[0], etiq[-1], etiq[:, 0], etiq[:, -1]])).tolist())
        for i in range(1, n):
            x, y, w, h, a = (int(v) for v in stats[i])
            if i in dehors or a < 1:
                continue
            # La petite zone autour du trou seulement (2 cases de marge), pas toute la grille : il peut y avoir des dizaines de trous.
            u0, v0, u1, v1 = max(0, x - 2), max(0, y - 2), min(W, x + w + 2), min(H, y + h + 2)
            trou = (etiq[v0:v1, u0:u1] == i).astype(np.uint8)
            gros = cv2.dilate(trou, np.ones((3, 3), np.uint8))  # une case de plus : la pièce bouche sous le bord des voisins
            voisins = etiquettes[v0:v1, u0:u1][gros > 0]
            voisins = voisins[voisins > 0]
            aire = a * PAS * PAS
            if _epaisseur(trou) > FENTE_MAX and aire > (MORCEAU_DE_PIECE_MAX if len(voisins) else VIDE_ENCLOS_MAX):
                continue  # un vrai trou (pièce oubliée, terrasse…) : signalé par trous_a_signaler(), jamais bouché en silence
            contours, _ = cv2.findContours(gros, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                pts = cv2.approxPolyDP(c, 0.5, True)[:, 0, :]
                if len(pts) < 3:
                    continue
                contour = _sens_direct([(round(x0 + (u0 + u + 0.5) * PAS, 6), round(y0 + (v0 + v + 0.5) * PAS, 6)) for u, v in pts])  # sens direct comme toutes les briques (sinon Blender voit la face de dos : noire)
                cle = (tuple(contour), bool(len(voisins)))
                if len(voisins):
                    piece = pieces[int(np.bincount(voisins).argmax()) - 1]
                    sortie.append(Brique(f"joint_{nom}__{piece.element}_{len(sortie) + 1}", nom, piece.element, contour, z, z))
                elif cle not in vus:  # enclos par des murs (fente, gaine, niche fermée) : plein du sol au plafond, une seule fois
                    mur = min(murs, key=lambda m: min(abs(px - contour[0][0]) + abs(py - contour[0][1]) for px, py in m.contour))
                    sortie.append(Brique(f"joint_mur__{mur.element}_{len(sortie) + 1}", "mur", mur.element, contour, 0.0, hsp))
                vus.add(cle)
    return sortie


def controler(briques: list[Brique], hauteur_sous_plafond: float) -> dict:
    """Les trous du bas (sol) et du haut (plafond) de la maquette, du plus grand au plus petit."""
    x0, y0, W, H = _grille(briques)
    murs = [b for b in briques if b.categorie == "mur"]
    bas = [b for b in briques if b.categorie == "sol"] + [b for b in murs if b.z_bas <= 1e-6]
    haut = [b for b in briques if b.categorie == "plafond"] + [b for b in murs if b.z_haut >= hauteur_sous_plafond - 1e-6]
    sortie = {"version": VERSION_CONTROLE, "pas_m": PAS}
    # Deux sols (ou deux plafonds) de pièces au même endroit : la 3D ne sait lequel montrer (fr-031 : cuisine rendue noire).
    compte = np.zeros((H, W), np.uint8)
    for b in briques:
        if b.categorie == "sol" and b.id.startswith("sol__"):
            compte += _dessiner([b], x0, y0, (H, W))
    sortie["sols_superposes_m2"] = round(float((compte > 1).sum()) * PAS * PAS, 4)
    # Deux murs l'un dans l'autre : leurs dessus, à la même hauteur, se font de l'ombre au rendu (carrés noirs aux jonctions).
    compte[:] = 0
    for b in murs:
        if b.z_haut >= hauteur_sous_plafond - 1e-6 and not b.id.startswith("joint_"):
            compte += _dessiner([b], x0, y0, (H, W))
    sortie["murs_superposes_m2"] = round(float((compte > 1).sum()) * PAS * PAS, 4)
    for nom, groupe in (("sol", bas), ("plafond", haut)):
        trous = _trous(_dessiner(groupe, x0, y0, (H, W)), x0, y0)
        sortie[nom] = {"trous": len(trous), "aire_m2": round(sum(t["aire_m2"] for t in trous), 4), "detail": trous[:20]}
    return sortie


def trous_a_signaler(briques: list[Brique], hauteur_sous_plafond: float) -> list[dict]:
    """Les trous qui restent au SOL de la maquette (après les bouche-trous de jours_a_boucher, déjà dans les briques) et plus
    grands que ZONE_SIGNALEE_MIN : une zone fermée par les murs où aucune pièce n'a été lue. Rendus comme doutes pour l'écran
    de vérification (moteur.preparer_verification), avec leur boîte en mètres."""
    r = controler(briques, hauteur_sous_plafond)
    return [t for t in r["sol"]["detail"] if t["aire_m2"] >= ZONE_SIGNALEE_MIN]


def vides_remplis(briques: list[Brique]) -> list[dict]:
    """Les vides enclos remplis comme une gaine par jours_a_boucher et plus grands que VIDE_SIGNALE_MIN : un WC ou un placard
    oublié par la lecture serait rempli de la même façon ; la personne qui vérifie doit le savoir (jamais rien en silence)."""
    sortie = []
    for b in briques:
        if b.id.startswith("joint_mur__"):
            aire = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(b.contour, b.contour[1:] + b.contour[:1]))) / 2
            if aire >= VIDE_SIGNALE_MIN:
                xs, ys = [p[0] for p in b.contour], [p[1] for p in b.contour]
                sortie.append({"aire_m2": round(aire, 2), "zone_m": [min(xs), min(ys), max(xs), max(ys)]})
    return sortie
