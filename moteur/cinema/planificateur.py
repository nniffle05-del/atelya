"""Le PLANIFICATEUR du vol (12/11/2026, étape 3 du plan validé par NT) : un seul vol continu, mais pensé comme un film.

Avant, la caméra allait CHERCHER des points (le point de vue d'une pièce, souvent dans un coin ; le fond d'une grande pièce) puis en
revenait : arrêts nets, demi-tours face aux murs (le contrôleur du survol de 50 s : 11 s le nez sur un mur, deux secousses).
Maintenant chaque pièce est MONTRÉE :

    ouverture     départ dans l'entrée, regard vers la plus belle profondeur
    révélation    on franchit la porte d'une pièce en regardant devant soi : la pièce s'ouvre
    valorisation  on passe par le CŒUR de la pièce (l'endroit le plus dégagé, loin de tous les murs) en regardant son plus beau
                  cadrage (moteur/realisateur) ; une grande pièce a deux cœurs
    panoramique   dans une pièce en cul-de-sac, on s'arrête en douceur au cœur, la caméra pivote lentement (le cadrage d'abord, puis
                  la sortie) et repart : au cœur, aucun mur n'est assez près pour boucher l'image
    conclusion    le film se termine au cœur de la dernière pièce, en ralentissant, sur son plus beau cadrage

Plusieurs ORDRES de visite sont essayés ; les plus prometteurs sont construits en entier et notés par le contrôleur
(moteur/cinema/controle.py) : le meilleur est tourné. Rien à régler à la main (règle n° 21 de NT).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from moteur import realisateur as rz
from moteur.cinema.navigation import (Carte, _cotes, depart_dans_l_entree, distances_depuis, portes_ouvertes,
                                      redresser_aux_portes)
from moteur.cinema.reglages import CIRCULATION, PAS_M, VOL_HAUTEUR_M, VOL_VITESSE

PORTES_DROITES = False  # portes franchies droit (navigation.redresser_aux_portes) : ESSAYÉ le 12/11/2026, sans gain (app-002 6,8 -> 7,0 s face aux murs, app-001 note 74 -> 65) : écarté
DEGAGE_PART = 0.9
DEGAGE_MAX_M = 1.4  # au-delà, assez dégagé pour tourner sans voir un mur de près (le contrôleur : mur « proche » < 1,2 m)
GRANDE_PIECE_M2 = 20.0  # au-delà, la pièce a un second cœur
COEUR_ECART_M = 3.0  # … à au moins ça du premier
PANORAMIQUE_DEG_S = 70.0  # vitesse de rotation du panoramique au cœur d'une pièce en cul-de-sac (45 avant l'avis de NT :
# « dès qu'il se retourne, il prend un peu de temps » ; pas plus de ~70 °/s : au-delà, à 24 images/s, le décor saute)
PANORAMIQUE_MIN_S = 1.2
PAUSE_CADRAGE_S = 0.4  # le temps de regarder le plus beau cadrage
SORTIE_DEG_S = 70.0  # puis on se tourne vers la sortie…
SORTIE_EN_VOL = 0.5  # … et on repart quand la moitié de ce dernier virage est faite : la fin du virage se fait en accélérant
DEMI_TOUR_DEG = 120.0  # au cœur d'une pièce, si le chemin repart à plus de ça de là où il arrivait : panoramique
DIRECTION_M = 0.6  # longueur de chemin pour mesurer d'où l'on arrive et où l'on repart
ORDRES_MAX = 5040  # 7 pièces montrées : on essaie tous les ordres ; au-delà, les plus proches d'abord
CANDIDATS = 4  # ordres construits en entier et notés par le contrôleur
CONCLUSION_POIDS_S = 6.0  # finir dans la pièce au plus beau cadrage vaut jusqu'à ça de film en plus


@dataclass
class Plan:
    """Un plan de vol : ce que le reste de la chaîne (trajectoire, regard, caméra) attend, plus ce qu'a décidé le planificateur."""
    scene: rz.Scene2D
    voir: rz.Scene2D
    carte: Carte
    portes: list
    etapes: list  # départ, cœurs (genre « point_de_vue », avec le cap du plus beau cadrage), conclusion
    chemin: list  # cases de la grille
    ordre: list = field(default_factory=list)  # les pièces, dans l'ordre de visite
    pivots: list = field(default_factory=list)  # panoramiques : {"xy", "duree_s", "cap", "piece"}
    fin_cap: float | None = None  # le cadrage de la dernière image
    estimation_s: float = 0.0


def _coeurs(carte: Carte, masque: np.ndarray, grande: bool, portes_xy: list) -> list[tuple[int, int]]:
    """Le cœur d'une pièce : un endroit bien dégagé (à au moins DEGAGE_PART du dégagement le plus grand de la pièce, plafonné à
    DEGAGE_MAX_M) et, parmi ceux-là, le plus proche d'une porte : on montre la pièce sans aller au bout (une cuisine en
    longueur se voit en entier depuis son entrée) ; une grande pièce a un second cœur, loin du premier."""
    d = np.where(masque & carte.libre, carte.distance, 0.0)
    if d.max() <= 0:
        return []
    assez = d >= DEGAGE_PART * min(float(d.max()), DEGAGE_MAX_M)
    cases = np.argwhere(assez)
    if portes_xy:
        portes = np.array([carte.case(q) for q in portes_xy], float)
        proches = np.min(np.linalg.norm(cases[:, None, :] - portes[None, :, :], axis=2), 1)
        i = cases[int(np.argmin(proches))]
    else:
        i = np.unravel_index(int(np.argmax(d)), d.shape)
    coeurs = [(int(i[0]), int(i[1]))]
    if grande:
        ii, jj = np.indices(d.shape)
        loin = ((ii - i[0]) ** 2 + (jj - i[1]) ** 2) * PAS_M ** 2 >= COEUR_ECART_M ** 2
        d2 = np.where(loin, d, 0.0)
        if d2.max() >= max(0.6, 0.6 * d.max()):
            j = np.unravel_index(int(np.argmax(d2)), d2.shape)
            coeurs.append((int(j[0]), int(j[1])))
    return coeurs


def _portes_de(logement: dict, piece_id: str, ouvertes: set) -> list:
    """Le milieu des portes ouvertes (et des portes-fenêtres intérieures) qui donnent dans la pièce."""
    sortie = []
    for o in logement.get("ouvertures", []):
        if o["type"] != "porte" or o["id"] not in ouvertes:
            continue
        cotes, a, d, _, _ = _cotes(logement, o)
        if any(c is not None and c["id"] == piece_id for c in cotes):
            m = a + d * (o["position"] + o["largeur"] / 2)
            sortie.append((float(m[0]), float(m[1])))
    return sortie


def _meilleur_cap(scene: rz.Scene2D, xy, aire: float, s: dict) -> float:
    """Le plus beau cadrage DEPUIS cet endroit (la note du réalisateur : part de la pièce vue, fenêtre, meubles, profondeur)."""
    r = scene.rayons(tuple(xy))
    return float(max(range(0, 360, 10), key=lambda c: rz._note_cadrage(r, float(c), aire, s)[0]))


def _cap(a, b) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def _ecart(a, b) -> float:
    return (b - a + 180) % 360 - 180


def _direction(carte: Carte, chemin: list, i: int, sens: int) -> float | None:
    """D'où l'on arrive (sens -1) ou vers où l'on repart (sens +1) à la case i du chemin, sur DIRECTION_M de chemin."""
    pas = max(1, int(DIRECTION_M / PAS_M))
    j = i + sens * pas
    if j < 0 or j >= len(chemin):
        return None
    a, b = carte.xy(chemin[min(i, j)]), carte.xy(chemin[max(i, j)])
    return _cap(a, b) if math.dist(a, b) > 0.05 else None


def planifier(logement: dict, s: dict) -> list[Plan]:
    """Les plans de vol candidats, du plus prometteur au moins prometteur (au plus CANDIDATS)."""
    scene = rz.Scene2D(logement)
    pieces = [p for p in logement["pieces"] if rz._type(p) not in rz.SANS_INTERET and len(p.get("contour") or []) >= 3]
    vues = {}
    for piece in pieces:
        v = rz.points_de_vue(scene, piece, 1, s)
        if v and not rz.rien_a_montrer(v[0]):
            vues[piece["id"]] = v[0]
    portes = portes_ouvertes(logement, set(vues))
    carte = Carte(logement, portes, hauteur_camera=VOL_HAUTEUR_M)
    ouvertes = {p["id"] for p in portes}
    voir = rz.Scene2D({**logement, "ouvertures": [o for o in logement.get("ouvertures", [])
                                                  if o["type"] != "porte" or o["id"] in ouvertes]}, portes_fermees=False)
    entree = next((p for p in pieces if rz._type(p) == "entree"), pieces[0])
    depart = depart_dans_l_entree(logement, carte, entree)
    atteignable = carte.zones == carte.zones[depart]
    a_montrer = {}
    for piece in pieces:
        vue = vues.get(piece["id"])
        masque = carte.masque_piece(piece) & atteignable
        if vue is None or rz._type(piece) in CIRCULATION or not masque.any():
            continue
        coeurs = _coeurs(carte, masque, rz._aire(piece["contour"]) > GRANDE_PIECE_M2, _portes_de(logement, piece["id"], ouvertes))
        if coeurs:
            a_montrer[piece["id"]] = (piece, vue, coeurs)
    if not a_montrer:
        return []

    # le plus beau cadrage depuis chaque cœur
    caps = {c: _meilleur_cap(scene, carte.xy(c), rz._aire(piece["contour"]), s)
            for piece, _, cs in a_montrer.values() for c in cs}
    # les distances (par le chemin) entre le départ et tous les cœurs : une fois pour toutes
    points = [depart] + [c for _, _, cs in a_montrer.values() for c in cs]
    distances = {p: distances_depuis(carte, p) for p in points}

    def longueur_piece(ident, arrivee):
        """Visiter une pièce en arrivant de `arrivee` : les cœurs dans le meilleur ordre ; renvoie (longueur, cœurs, sortie)."""
        cs = a_montrer[ident][2]
        meilleur = None
        for ordre in itertools.permutations(cs):
            total, ici = 0.0, arrivee
            for c in ordre:
                total += distances[ici].get(c, math.inf) * PAS_M
                ici = c
            if meilleur is None or total < meilleur[0]:
                meilleur = (total, list(ordre), ici)
        return meilleur

    notes_vue = {k: v[1]["note"] for k, v in a_montrer.items()}
    meilleure_vue = max(notes_vue.values())
    ecart_notes = max(1e-6, meilleure_vue - min(notes_vue.values()))
    ordres = []
    ids = list(a_montrer)
    tous = itertools.permutations(ids) if math.factorial(len(ids)) <= ORDRES_MAX else [tuple(ids)]
    for ordre in tous:
        total, ici = 0.0, depart
        for ident in ordre:
            longueur, _, ici = longueur_piece(ident, ici)
            total += longueur
        # une estimation du film : le chemin à la vitesse de croisière (un peu moins), plus un panoramique par pièce en
        # cul-de-sac (on ne le sait vraiment qu'une fois le chemin tracé : on compte toutes les pièces sauf la dernière, au pire)
        estimation = total / (0.8 * VOL_VITESSE) + PANORAMIQUE_MIN_S * (len(ordre) - 1)
        fin = CONCLUSION_POIDS_S * (meilleure_vue - notes_vue[ordre[-1]]) / ecart_notes
        ordres.append((estimation + fin, estimation, ordre))
    ordres.sort(key=lambda o: o[0])

    plans = []
    for _, estimation, ordre in ordres[:CANDIDATS]:
        chemin = [depart]
        etapes = [{"genre": "depart", "piece": entree["id"], "xy": carte.xy(depart)}]
        arrivees = []  # (indice dans le chemin, pièce, cap) des cœurs
        ici = depart
        for ident in ordre:
            _, vue, _ = a_montrer[ident]
            _, cs, _ = longueur_piece(ident, ici)
            for n, c in enumerate(cs):
                chemin += carte.chemin(chemin[-1], c)[1:]
                ici = c
                cap = caps[c]
                etapes.append({"genre": "point_de_vue" if n == 0 else "coeur", "piece": ident, "xy": carte.xy(c), "cap": cap})
                arrivees.append((len(chemin) - 1, ident, cap))
        etapes[-1]["genre"] = "conclusion"
        pivots = []
        for i, ident, cap in arrivees[:-1]:
            arrive, repart = _direction(carte, chemin, i, -1), _direction(carte, chemin, i, +1)
            if arrive is None or repart is None or abs(_ecart(arrive, repart)) < DEMI_TOUR_DEG:
                continue
            # le panoramique : de là où l'on arrive vers le plus beau cadrage, puis vers la sortie
            # le temps se partage selon les angles : tourner jusqu'au cadrage, s'y poser, puis tourner vers la sortie et repartir
            # aussitôt (avant : moitié-moitié, et la caméra attendait parfois 2 s face à la porte)
            vers_cadrage = abs(_ecart(arrive, cap)) / PANORAMIQUE_DEG_S + PAUSE_CADRAGE_S
            vers_sortie = abs(_ecart(cap, repart)) / SORTIE_DEG_S
            duree = max(PANORAMIQUE_MIN_S, vers_cadrage + SORTIE_EN_VOL * vers_sortie)
            pivots.append({"xy": carte.xy(chemin[i]), "piece": ident, "cap": cap, "duree_s": round(duree, 2),
                           "part": round(vers_cadrage / duree, 3)})
        if PORTES_DROITES:
            chemin = redresser_aux_portes(chemin, carte, logement, portes, [e["xy"] for e in etapes])
        plans.append(Plan(scene=scene, voir=voir, carte=carte, portes=portes, etapes=etapes, chemin=chemin, ordre=list(ordre),
                          pivots=pivots, fin_cap=etapes[-1]["cap"], estimation_s=round(estimation, 1)))
    return plans
