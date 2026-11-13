"""Le PROMENEUR d'Atelya : une BALADE continue dans tout le logement, une seule prise sans coupure (12/11/2026, NT : « une vraie
caméra qui se balade, qui pense, qui ose, qui passe par tous les recoins, qui va au bout de la pièce, qui se retourne »).

Comme un vidéaste avec une caméra stabilisée :
1. OÙ L'ON PEUT MARCHER : une grille fine (PAS_M) du logement ; murs, fenêtres, meubles et battants des portes OUVERTES sont des
   obstacles ; on marche à au moins MARGE_M de tout, et de préférence au milieu des passages (coût plus fort près des obstacles) ;
   les portes intérieures sont des passages (ouvertes pendant la balade ; la porte d'entrée palière reste fermée).
2. LE PARCOURS : on part de l'entrée (près de la porte palière) ; puis, dans l'ordre d'une visite (moteur/realisateur.ORDRE), pour
   chaque pièce qui a quelque chose à montrer : son meilleur POINT DE VUE (moteur/realisateur), puis le FOND de la pièce (le point
   libre le plus loin de l'endroit où l'on est entré), où la caméra SE RETOURNE lentement ; les étapes sont reliées par le plus
   court chemin (on passe par les portes), lissé pour une marche fluide à VITESSE m/s.
3. LE REGARD : devant soi en marchant (on regarde là où l'on va, un peu en avance), vers le cadrage choisi au point de vue (un
   temps d'arrêt), et un demi-tour lent au fond de la pièce ; la tête tourne doucement (au plus ROTATION_MAX °/s).
Sortie : un trajet au format de outils/unreal/cinematique_unreal.py (une clé toutes les CLE_IMAGES images) et ses étapes.

Depuis le 12/11/2026 (étape 0 du plan validé par NT), le VOL est découpé en briques dans moteur/cinema/ (navigation, parcours,
trajectoire, regard, caméra, réglages) ; ce fichier garde la balade à pied (option « marche ») et orchestre le vol. Les noms
d'avant restent disponibles ici.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from moteur import realisateur as rz
from moteur.cinema.camera import hauteurs_du_vol, trajet_du_vol
from moteur.cinema.navigation import Carte, _cotes, _hauteur_meuble, _rect, porte_palliere, portes_ouvertes  # noqa: F401
from moteur.cinema.controle import controler
from moteur.cinema.parcours import parcours_du_vol
from moteur.cinema.planificateur import planifier
from moteur.cinema.regard import angle as _angle, ecart as _ecart, profondeur as _profondeur, regard_du_vol, regard_profond
from moteur.cinema.reglages import *  # noqa: F401,F403  (les réglages, sous leurs noms d'avant)
from moteur.cinema.reglages import CIRCULATION, CLE_IMAGES, FOND_DISTANCE_M, IPS, MARGE_M, PAS_M
from moteur.cinema.trajectoire import allure_du_vol, courbe_du_vol

REGARD_AVANCE_VOL_M = 1.2  # planificateur : le regard anticipe là où l'on sera 1,2 m plus loin
OUVERTURE_CALME_M = 2.0  # planificateur : pas d'accélération « couloir » au tout début du film
PIVOT_PLANIFIE = 70.0  # planificateur : °/s à l'arrêt (60 avant ; NT : les demi-tours plus rapides)
ROTATION_PLANIFIEE = 35.0  # planificateur : °/s en vol (28 avant) : le regard suit mieux les virages des portes

# la balade À PIED (premier essai du 12/11/2026, remplacé par le vol ; gardé en option « marche »)
VITESSE = 0.45  # m/s : une marche lente, dans la pièce qu'on montre
VITESSE_PASSAGE = 0.8  # m/s : dans les couloirs et pour rejoindre la pièce suivante
ROTATION_MAX = 35.0  # °/s
ARRET_VUE_S = 1.8  # temps passé au point de vue (léger panoramique)
DEMI_TOUR_S = 3.2  # se retourner au fond de la pièce
DEMI_TOUR_DEG = 150.0
REGARD_AVANCE_M = 1.2  # on regarde là où l'on sera dans 1,2 m


def _lisser(points: np.ndarray, carte: Carte, fenetre_m: float = 0.8) -> np.ndarray:
    """Moyenne glissante le long du chemin (marche fluide), sans jamais sortir de la zone praticable."""
    n = max(1, int(fenetre_m / PAS_M / 2))
    lisse = points.copy()
    for k in range(len(points)):
        a, b = max(0, k - n), min(len(points), k + n + 1)
        candidat = points[a:b].mean(0)
        i, j = carte.case(candidat)
        if 0 <= i < carte.forme[0] and 0 <= j < carte.forme[1] and carte.distance[i, j] >= MARGE_M * 0.9:
            lisse[k] = candidat
    return lisse



def balade(logement: dict, savoir: dict | None = None, format_image=(1920, 1080), scene_eclairage: str | None = None) -> dict:
    """La balade : trajet (une clé toutes les CLE_IMAGES images), étapes, portes ouvertes, pièces sans fenêtre."""
    s = savoir or rz.savoir_faire()
    scene = rz.Scene2D(logement)
    pieces = [p for p in logement["pieces"] if rz._type(p) not in rz.SANS_INTERET and len(p.get("contour") or []) >= 3]
    pieces.sort(key=lambda p: (rz.ORDRE.index(rz._type(p)) if rz._type(p) in rz.ORDRE else len(rz.ORDRE), p["id"]))
    vues_par_piece = {}
    for piece in pieces:
        vues = rz.points_de_vue(scene, piece, 1, s)
        if vues and not rz.rien_a_montrer(vues[0]):
            vues_par_piece[piece["id"]] = vues[0]
    portes = portes_ouvertes(logement, set(vues_par_piece))
    carte = Carte(logement, portes)
    # ce que voit la caméra : portes ouvertes = on voit à travers ; portes fermées = mur
    ouvertes = {p["id"] for p in portes}
    voir = rz.Scene2D({**logement, "ouvertures": [o for o in logement.get("ouvertures", [])
                                                 if o["type"] != "porte" or o["id"] in ouvertes]}, portes_fermees=False)

    # départ : dans l'entrée, près de la porte palière
    palliere = porte_palliere(logement)
    entree = next((p for p in pieces if rz._type(p) == "entree"), pieces[0])
    if palliere:
        o = next(o for o in logement["ouvertures"] if o["id"] == palliere)
        m = next(m for m in logement["murs"] if m["id"] == o["mur"])
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        d = (b - a) / np.linalg.norm(b - a)
        repere = a + d * (o["position"] + o["largeur"] / 2)
    else:
        repere = np.asarray(entree["contour"], float).mean(0)
    position = carte.plus_proche_libre(repere, carte.masque_piece(entree))
    atteignable = carte.zones == carte.zones[position]  # tout ce qu'on peut rejoindre à pied depuis l'entrée
    etapes = [{"genre": "depart", "piece": entree["id"], "xy": carte.xy(position)}]
    chemin = [position]
    for piece in pieces:
        vue = vues_par_piece.get(piece["id"])
        if vue is None or rz._type(piece) in CIRCULATION:
            continue  # pièce sans rien à montrer, ou couloir : on la traverse sans s'y arrêter
        masque = carte.masque_piece(piece) & atteignable
        if not masque.any():
            continue
        cible_vue = carte.plus_proche_libre(vue["position"], masque)
        morceau = carte.chemin(chemin[-1], cible_vue)
        chemin += morceau[1:]
        etapes.append({"genre": "point_de_vue", "piece": piece["id"], "xy": carte.xy(cible_vue), "cap": vue["cap"],
                       "indice": len(chemin) - 1})
        # le fond de la pièce : la case la plus loin (à vol d'oiseau) de l'endroit où l'on est entré dans la pièce, à au moins
        # FOND_DISTANCE_M des murs et des meubles (pas le nez dans un angle)
        entree_piece = next((c for c in morceau if masque[c]), cible_vue)
        large = masque & (carte.distance >= min(FOND_DISTANCE_M, float(carte.distance[masque].max()) * 0.9))
        cases = np.argwhere(large if large.any() else masque)
        loin = cases[int(np.argmax((cases[:, 0] - entree_piece[0]) ** 2 + (cases[:, 1] - entree_piece[1]) ** 2))]
        fond = (int(loin[0]), int(loin[1]))
        if math.dist(carte.xy(fond), carte.xy(cible_vue)) > 1.2:
            chemin += carte.chemin(chemin[-1], fond)[1:]
            etapes.append({"genre": "fond", "piece": piece["id"], "xy": carte.xy(fond), "indice": len(chemin) - 1})

    # marche : lissage, puis une position par image à VITESSE m/s ; arrêts (point de vue, demi-tour) insérés
    xy = np.array([carte.xy(c) for c in chemin])
    xy = _lisser(_lisser(xy, carte), carte)
    pas_image = VITESSE / IPS
    images, regards, arrets = [], [], {}
    for e in etapes[1:]:
        arrets[e["indice"]] = e
    debut = 0
    indices = sorted(arrets) + [len(xy) - 1]
    cap_courant = None
    pieces_par_id = {p["id"]: p for p in logement["pieces"]}
    for fin in indices:
        cible = arrets.get(fin)
        piece_cible = pieces_par_id.get(cible["piece"]) if cible else None
        brut = xy[debut:fin + 1]
        if len(brut) > 1:
            # vitesse : lente quand on est dans la pièce que l'on vient montrer, plus vive dans les passages (moyenne glissante
            # pour des changements d'allure doux)
            vites = np.array([VITESSE if piece_cible and rz._dedans(tuple(q), piece_cible["contour"]) else VITESSE_PASSAGE
                              for q in brut])
            vites = np.convolve(np.pad(vites, 20, mode="edge"), np.ones(41) / 41, mode="valid")
            seg = np.linalg.norm(np.diff(brut, axis=0), axis=1)
            temps = np.concatenate([[0], np.cumsum(seg / ((vites[1:] + vites[:-1]) / 2))])
            t_img = np.arange(0, temps[-1], 1.0 / IPS)
            troncon = np.stack([np.interp(t_img, temps, brut[:, 0]), np.interp(t_img, temps, brut[:, 1])], 1)
        else:
            troncon = brut
        rayons = None
        for k, p in enumerate(troncon):
            avance = troncon[min(len(troncon) - 1, k + int(REGARD_AVANCE_M / (VITESSE_PASSAGE / IPS)))]
            direction = avance - p
            marche = _angle(direction) if np.linalg.norm(direction) > 0.05 else cap_courant
            if k % CLE_IMAGES == 0 or rayons is None:
                rayons = voir.rayons(tuple(p))
                cap = regard_profond(rayons, marche)
            images.append(p)
            regards.append(cap)
            cap_courant = cap
        debut = fin
        e = arrets.get(fin)
        if e is None:
            continue
        p = xy[fin]
        if e["genre"] == "point_de_vue":  # temps d'arrêt, regard vers le cadrage choisi, léger panoramique
            n = int(ARRET_VUE_S * IPS)
            for k in range(n):
                images.append(p)
                regards.append(e["cap"] + s["pano_deg"] * (2 * k / max(n - 1, 1) - 1))
        else:  # au fond de la pièce : on se retourne lentement vers la plus belle profondeur (on révèle la pièce)
            n = int(DEMI_TOUR_S * IPS)
            depart_cap = regards[-1]
            but = regard_profond(voir.rayons(tuple(p)), None)
            tour = _ecart(depart_cap, but)  # par le côté le plus court
            for k in range(n):
                t = k / max(n - 1, 1)
                images.append(p)
                regards.append(depart_cap + tour * (3 * t * t - 2 * t ** 3))
    # la tête tourne doucement : chaque cap rejoint le cap voulu à au plus ROTATION_MAX °/s
    # (dans les deux sens du temps : la tête ANTICIPE un virage au lieu de le suivre en retard)
    voulus = [regards[0]]
    for c in regards[1:]:
        voulus.append(voulus[-1] + _ecart(voulus[-1], c))  # caps déroulés (sans saut de 360°)
    pas_max = ROTATION_MAX / IPS
    caps = list(voulus)
    for i in range(1, len(caps)):
        caps[i] = caps[i - 1] + max(-pas_max, min(pas_max, voulus[i] - caps[i - 1]))
    arriere = list(voulus)
    for i in range(len(arriere) - 2, -1, -1):
        arriere[i] = arriere[i + 1] + max(-pas_max, min(pas_max, voulus[i] - arriere[i + 1]))
    caps = np.array([(a + b) / 2 for a, b in zip(caps, arriere)])
    # un léger lissage des caps (pas d'à-coups), puis les clés
    noyau = np.ones(9) / 9
    caps = np.convolve(np.pad(caps, 4, mode="edge"), noyau, mode="valid")
    points = [[round(float(images[k][0]), 3), round(float(images[k][1]), 3), round(s["hauteur_m"], 3),
               round(float(caps[k]), 2), round(s["tangage_deg"], 1)] for k in range(0, len(images), CLE_IMAGES)]
    if (len(images) - 1) % CLE_IMAGES:
        k = len(images) - 1
        points.append([round(float(images[k][0]), 3), round(float(images[k][1]), 3), round(s["hauteur_m"], 3),
                       round(float(caps[k]), 2), round(s["tangage_deg"], 1)])
    nb_images = (len(points) - 1) * CLE_IMAGES + 1
    trajet = {"points": points, "images": nb_images, "ips": IPS, "focale_mm": s["focale_mm"], "format": list(format_image),
              "balade": True}
    if scene_eclairage:
        trajet["scene"] = scene_eclairage
    sans_fenetre = [p["id"] for p in logement["pieces"] if not scene.a_une_fenetre(p)]
    return {"trajet": trajet, "etapes": etapes, "portes_ouvertes": [{k: v for k, v in p.items() if k != "battant"}
                                                                     for p in portes],
            "pieces_sans_fenetre": sans_fenetre, "duree_s": round(nb_images / IPS, 1),
            "longueur_m": round(float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1))), 1)}


def _en_passage(logement: dict, points: np.ndarray) -> np.ndarray:
    """Pour chaque point : est-on dans une circulation (couloir, dégagement, entrée) ou dans l'épaisseur d'une porte ?"""
    circulations = [p["contour"] for p in logement["pieces"]
                    if rz._type(p) in CIRCULATION and len(p.get("contour") or []) >= 3]
    autres = [p["contour"] for p in logement["pieces"] if rz._type(p) not in CIRCULATION and len(p.get("contour") or []) >= 3]
    sortie = np.zeros(len(points), bool)
    for k, q in enumerate(points):
        q = (float(q[0]), float(q[1]))
        sortie[k] = any(rz._dedans(q, c) for c in circulations) or not any(rz._dedans(q, c) for c in autres)
    # l'ouverture (les 2 premiers mètres) reste calme, même dans l'entrée
    parcouru = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    sortie[parcouru < OUVERTURE_CALME_M] = False
    return sortie


def _construire(logement: dict, parcours, s: dict, format_image, scene_eclairage, vide=None) -> dict:
    """Un plan de vol (parcours ou planificateur) → le vol complet : courbe et allure (trajectoire), regard, hauteur, clés."""
    pivots = getattr(parcours, "pivots", None)
    courbe, jonctions, durees = courbe_du_vol(parcours.chemin, parcours.carte, pivots)
    passages = _en_passage(logement, courbe) if pivots is not None else None
    positions, longueur, arrets = allure_du_vol(courbe, jonctions, parcours.etapes, durees,
                                                virages_suivis=ROTATION_PLANIFIEE if pivots is not None else None,
                                                passages=passages)
    panoramiques = None
    if pivots is not None:  # le regard de chaque arrêt voulu par le planificateur : le cadrage de sa pièce, puis la sortie
        panoramiques = []
        for (debut, fin), j in zip(arrets, sorted(jonctions)):
            pv = min(pivots, key=lambda q: float(np.linalg.norm(courbe[min(j, len(courbe) - 1)] - np.asarray(q["xy"]))))
            panoramiques.append((debut, fin, pv["cap"], pv.get("part", 0.55)))
    caps = regard_du_vol(positions, courbe, jonctions, parcours.etapes, parcours.voir, logement, panoramiques,
                         getattr(parcours, "fin_cap", None), REGARD_AVANCE_VOL_M if pivots is not None else None,
                         ROTATION_PLANIFIEE if pivots is not None else VOL_ROTATION_MAX,
                         PIVOT_PLANIFIE if pivots is not None else VOL_ROTATION_PIVOT,
                         _en_passage(logement, positions) if pivots is not None else None, ROTATION_PASSAGE, vide)
    hauteurs, tangages = hauteurs_du_vol(positions, parcours.voir, logement)
    trajet = trajet_du_vol(positions, hauteurs, caps, tangages, s["focale_mm"], format_image, scene_eclairage)
    sans_fenetre = [p["id"] for p in logement["pieces"] if not parcours.scene.a_une_fenetre(p)]
    return {"trajet": trajet, "etapes": parcours.etapes,
            "portes_ouvertes": [{k: v for k, v in p.items() if k != "battant"} for p in parcours.portes],
            "pieces_sans_fenetre": sans_fenetre, "duree_s": round(trajet["images"] / IPS, 1), "longueur_m": round(longueur, 1)}


def vol(logement: dict, savoir: dict | None = None, format_image=(1920, 1080), scene_eclairage: str | None = None,
        planificateur: bool = True, budget_s: float | None = None, decor: dict | None = None) -> dict:
    """LA CAMÉRA VOLANTE. Avec le PLANIFICATEUR (défaut depuis le 12/11/2026) : plusieurs plans de vol (ordres de visite,
    panoramiques au cœur des pièces en cul-de-sac, conclusion sur le plus beau cadrage), chacun construit en entier puis noté
    par le CONTRÔLEUR ; le meilleur est gardé (les autres notes sont dans « candidats »). Sans (`planificateur=False`) : le vol
    d'avant (survol du 12/11/2026), pour comparer. Résultat : trajet, étapes, portes ouvertes, pièces sans fenêtre, contrôle."""
    s = savoir or rz.savoir_faire()
    vide = None
    if decor:  # ce que la vraie vue couvre (vide_dehors.charger) : le regard évite de cadrer ce que les photos ne montrent pas
        from moteur.cinema import vide_dehors
        from moteur.cinema.reglages import VOL_HAUTEUR_M, VOL_TANGAGE_DEG
        vide = vide_dehors.regard_sans_vide(logement, decor, s["focale_mm"], format_image, VOL_HAUTEUR_M, VOL_TANGAGE_DEG)
    if not planificateur:
        return _construire(logement, parcours_du_vol(logement, s), s, format_image, scene_eclairage, vide)
    plans = planifier(logement, s)
    if not plans:
        return _construire(logement, parcours_du_vol(logement, s), s, format_image, scene_eclairage, vide)
    essais = []
    for plan in plans:
        r = _construire(logement, plan, s, format_image, scene_eclairage, vide)
        c = controler(logement, r, budget_s)
        essais.append((c["note"], r, c, plan))
    note, meilleur, c, plan = max(essais, key=lambda e: e[0])
    meilleur["controle"] = {"note": c["note"], "resume": c["resume"], "budget_s": c["budget_s"]}
    meilleur["candidats"] = [{"ordre": e[3].ordre, "note": e[0], "duree_s": e[1]["duree_s"],
                              "panoramiques": [pv["piece"] for pv in e[3].pivots], "retenu": e[1] is meilleur}
                             for e in essais]
    return meilleur


def dessiner(logement: dict, resultat: dict, chemin, px_par_m: int = 60) -> None:
    """La balade vue de dessus : le chemin (rouge, une flèche par seconde dans le sens du regard), les étapes."""
    from moteur.images import ecrire_image

    rz.dessiner(logement, [], chemin, px_par_m)
    from moteur.images import lire_image
    image = lire_image(chemin)
    pts = np.concatenate([np.asarray(p["contour"], float) for p in logement["pieces"]])
    mini, maxi = pts.min(0) - 1.0, pts.max(0) + 1.0

    def ecran(p):
        return int((p[0] - mini[0]) * px_par_m), int((maxi[1] - p[1]) * px_par_m)
    pts_t = resultat["trajet"]["points"]
    for a, b in zip(pts_t, pts_t[1:]):
        cv2.line(image, ecran(a), ecran(b), (0, 0, 220), 2, cv2.LINE_AA)
    pas = max(1, IPS // CLE_IMAGES)
    for p in pts_t[::pas]:
        c = math.radians(p[3])
        cv2.arrowedLine(image, ecran(p), ecran((p[0] + 0.35 * math.cos(c), p[1] + 0.35 * math.sin(c))), (0, 140, 255), 1,
                        cv2.LINE_AA, tipLength=0.4)
    for k, e in enumerate(resultat["etapes"]):
        couleur = {"depart": (0, 160, 0), "point_de_vue": (200, 0, 200), "fond": (200, 120, 0), "coeur": (200, 120, 0),
                   "conclusion": (0, 0, 200)}.get(e["genre"], (90, 90, 90))
        cv2.circle(image, ecran(e["xy"]), 7, couleur, -1)
        cv2.putText(image, str(k), (ecran(e["xy"])[0] + 8, ecran(e["xy"])[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
    ecrire_image(chemin, image)
