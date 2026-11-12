"""CE QU'ON VA MONTRER, et dans quel ordre : pour chaque pièce qui a quelque chose à montrer, son meilleur point de vue
(moteur/realisateur) ; dans les grandes pièces, aussi leur fond ; l'ordre de visite le plus court depuis l'entrée ; les
passages déjà empruntés coûtent plus cher (un circuit plutôt qu'un aller-retour). C'est ici que viendra le PLANIFICATEUR
(ouverture, révélations, valorisation, conclusion : étape 3 du plan validé par NT le 12/11/2026)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from moteur import realisateur as rz
from moteur.cinema.navigation import Carte, depart_dans_l_entree, distances_depuis, portes_ouvertes
from moteur.cinema.reglages import (CIRCULATION, FOND_DISTANCE_M, PAS_M, VOL_DEJA_VU_COUT, VOL_DEJA_VU_M, VOL_FOND_M2,
                                    VOL_HAUTEUR_M)


@dataclass
class Parcours:
    scene: rz.Scene2D  # le logement tel qu'il est (portes fermées)
    voir: rz.Scene2D  # ce que voit la caméra pendant le vol (portes ouvertes = on voit à travers)
    carte: Carte  # où la caméra peut passer
    portes: list  # les portes ouvertes pour la visite
    etapes: list  # départ, points de vue, fonds (genre, pièce, xy, cap)
    chemin: list  # les cases de la grille, de l'entrée à la fin


def parcours_du_vol(logement: dict, s: dict) -> Parcours:
    scene = rz.Scene2D(logement)
    pieces = [p for p in logement["pieces"] if rz._type(p) not in rz.SANS_INTERET and len(p.get("contour") or []) >= 3]
    vues_par_piece = {}
    for piece in pieces:
        vues = rz.points_de_vue(scene, piece, 1, s)
        if vues and not rz.rien_a_montrer(vues[0]):
            vues_par_piece[piece["id"]] = vues[0]
    portes = portes_ouvertes(logement, set(vues_par_piece))
    carte = Carte(logement, portes, hauteur_camera=VOL_HAUTEUR_M)  # les meubles bas se survolent
    ouvertes = {p["id"] for p in portes}
    voir = rz.Scene2D({**logement, "ouvertures": [o for o in logement.get("ouvertures", [])
                                                  if o["type"] != "porte" or o["id"] in ouvertes]}, portes_fermees=False)
    entree = next((p for p in pieces if rz._type(p) == "entree"), pieces[0])
    position = depart_dans_l_entree(logement, carte, entree)
    atteignable = carte.zones == carte.zones[position]
    a_voir = {}
    for piece in pieces:
        vue = vues_par_piece.get(piece["id"])
        masque = carte.masque_piece(piece) & atteignable
        if vue is None or rz._type(piece) in CIRCULATION or not masque.any():
            continue
        a_voir[piece["id"]] = (piece, vue, masque, carte.plus_proche_libre(vue["position"], masque))
    # l'ordre de visite le plus court : à chaque fois, la pièce la plus proche (par le chemin) de l'endroit où l'on est
    etapes = [{"genre": "depart", "piece": entree["id"], "xy": carte.xy(position)}]
    chemin = [position]

    def deja_vu():
        """Les passages déjà empruntés (à VOL_DEJA_VU_M près) coûtent plus cher : le vol cherche un autre chemin (un circuit,
        autour d'une table…) plutôt que de repasser au même endroit ; s'il n'y en a pas (une seule porte), il repasse."""
        m = np.zeros(carte.forme, np.uint8)
        for c in chemin:
            m[c] = 1
        r = int(VOL_DEJA_VU_M / PAS_M)
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        return VOL_DEJA_VU_COUT * m.astype(float)
    while a_voir:
        dist = distances_depuis(carte, chemin[-1])
        ident = min(a_voir, key=lambda k: dist.get(a_voir[k][3], math.inf))
        piece, vue, masque, cible = a_voir.pop(ident)
        morceau = carte.chemin(chemin[-1], cible, deja_vu())
        chemin += morceau[1:]
        etapes.append({"genre": "point_de_vue", "piece": ident, "xy": carte.xy(cible), "cap": vue["cap"]})
        if rz._aire(piece["contour"]) > VOL_FOND_M2:
            # le fond : le plus loin du POINT DE VUE (on traverse toute la pièce, ce que le point de vue ne montrait pas)
            large = masque & (carte.distance >= min(FOND_DISTANCE_M, float(carte.distance[masque].max()) * 0.9))
            cases = np.argwhere(large if large.any() else masque)
            loin = cases[int(np.argmax((cases[:, 0] - cible[0]) ** 2 + (cases[:, 1] - cible[1]) ** 2))]
            fond = (int(loin[0]), int(loin[1]))
            if math.dist(carte.xy(fond), carte.xy(cible)) > 1.5:
                chemin += carte.chemin(chemin[-1], fond, deja_vu())[1:]
                etapes.append({"genre": "fond", "piece": ident, "xy": carte.xy(fond)})
    return Parcours(scene=scene, voir=voir, carte=carte, portes=portes, etapes=etapes, chemin=chemin)
