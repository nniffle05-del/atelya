"""Repérer les meubles sur les photos du client, sans aide (09/11/2026, NT : « il faut le plus de possibilités possible »).

Pourquoi : jusqu'ici, Claude relevait les meubles à la main (verites/app-001/meubles.json) ; Atelya doit le faire seul.

Méthode :
1. L'œil DINOv2 regarde la photo par carrés de 14 × 14 pixels (photo réduite à 672 × 448 : 48 × 32 carrés) et donne
   l'empreinte de chaque carré. Un petit classificateur appris (comme pour les sols) dit, pour chaque carré, quel GROUPE de
   meuble il voit (canapé, fauteuil, chaise, table, lit, rangement, tapis, lampe, plante, déco) ou « rien ».
   Il est appris sur les photos d'essai meublées rendues par Blender, dont on connaît, pixel par pixel, le meuble vu
   (moteur/blender/masques_meubles.py, mode « catégories »).
2. Chaque tache d'un même groupe sur la photo = un meuble. Son PIED est le bas de la tache : la caméra calée dit où ce point
   touche le sol (en mètres). Le meuble est un peu plus loin que son bord avant : on recule de la moitié de sa profondeur.
3. Le même meuble vu sur plusieurs photos est fusionné (même groupe, à moins de FUSION_M).
4. Orientation : un meuble collé à un mur lui tourne le dos ; sinon, il regarde le milieu de la pièce.
Ce n'est qu'une première version : la place est approchée (≈ 0,5 m), la taille est celle d'un meuble courant du groupe.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
import torch

from moteur.meubles import NOMS_MEUBLES

TAILLE_ENTREE = (672, 448)  # largeur, hauteur données à l'œil (48 × 32 carrés de 14 px)
CARRE = 14
RIEN = "rien"
GROUPES = {
    "canape": ("canape",), "fauteuil": ("fauteuil",),
    "chaise": ("chaise", "tabouret_haut", "chaise_de_bureau"),
    "table": ("table", "table_basse", "table_d_appoint", "bureau"),
    "lit": ("lit", "lit_superpose"),
    "rangement": ("commode", "rangement", "etagere_cubes", "bibliotheque", "meuble_tv", "table_de_chevet", "banc", "placard",
                  "meuble_cuisine_bas", "colonne_cuisine", "ilot", "caisson"),
    "tapis": ("tapis",), "lampe": ("lampadaire", "lampe"), "plante": ("plante",),
}
CLASSES_MEUBLES = (RIEN, *GROUPES)
GROUPE_DE = {c: g for g, cs in GROUPES.items() for c in cs}
# un meuble courant de chaque groupe (largeur, profondeur, hauteur) et la catégorie qui le représente
TYPE_DE_GROUPE = {"canape": ("canape", (2.1, 0.9, 0.85)), "fauteuil": ("fauteuil", (0.75, 0.8, 0.85)),
                  "chaise": ("chaise", (0.5, 0.55, 0.85)), "table": ("table", (1.4, 0.8, 0.75)),
                  "lit": ("lit", (1.6, 2.05, 1.0)), "rangement": ("rangement", (1.2, 0.45, 0.9)),
                  "tapis": ("tapis", (1.8, 1.3, 0.02)), "lampe": ("lampadaire", (0.4, 0.4, 1.6)),
                  "plante": ("plante", (0.5, 0.5, 1.0))}
TACHE_MIN = {"tapis": 12, "chaise": 4, "lampe": 3}  # carrés minimum d'une tache pour compter comme un meuble
TACHE_MIN_DEFAUT = 16  # réglé sur le contrôle (fr-031, fr-038) le 09/11/2026 : moins de détections en trop
FUSION_M = {"chaise": 0.45, "fauteuil": 0.6}
FUSION_DEFAUT = 1.8  # réglé sur le contrôle : un grand meuble vu en morceaux ne compte qu une fois
CONTRE_MUR_M = 0.6


def groupe(categorie: str) -> str | None:
    return GROUPE_DE.get(categorie)


@torch.no_grad()
def empreintes_carres(oeil, photo_rgb: np.ndarray) -> np.ndarray:
    """(32, 48, d) : l'empreinte de chaque carré de la photo réduite à TAILLE_ENTREE."""
    from moteur.oeil_dinov2 import ECART, MOYENNE
    img = cv2.resize(photo_rgb, TAILLE_ENTREE, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    appareil = next(oeil.parameters()).device
    x = torch.from_numpy((img - MOYENNE) / ECART).permute(2, 0, 1)[None].to(appareil)
    with torch.autocast(device_type=appareil.type, enabled=appareil.type == "cuda"):
        _, carres = oeil(x)
    h, w = TAILLE_ENTREE[1] // CARRE, TAILLE_ENTREE[0] // CARRE
    e = torch.nn.functional.normalize(carres.float()[0], dim=-1)
    return e.reshape(h, w, -1).cpu().numpy()


def etiquettes_carres(masque_categories: np.ndarray, categories=NOMS_MEUBLES, part_min: float = 0.5) -> np.ndarray:
    """(32, 48) : l'indice dans CLASSES_MEUBLES du groupe vu dans chaque carré (masque de catégories : 0 = rien, k = n° k de
    `categories`), ou -1 si le carré est trop mélangé (aucun groupe ni « rien » à plus de part_min)."""
    h, w = TAILLE_ENTREE[1] // CARRE, TAILLE_ENTREE[0] // CARRE
    m = cv2.resize(masque_categories, TAILLE_ENTREE, interpolation=cv2.INTER_NEAREST)
    sortie = np.full((h, w), -1, int)
    vers_classe = np.zeros(256, int)  # valeur du pixel → classe
    for k, c in enumerate(categories, start=1):
        g = groupe(c)
        vers_classe[k] = CLASSES_MEUBLES.index(g) if g else 0
    classes = vers_classe[m]
    for i in range(h):
        for j in range(w):
            bloc = classes[i * CARRE:(i + 1) * CARRE, j * CARRE:(j + 1) * CARRE].ravel()
            compte = np.bincount(bloc, minlength=len(CLASSES_MEUBLES))
            k = int(compte.argmax())
            if compte[k] >= part_min * bloc.size:
                sortie[i, j] = k
    return sortie


def taches(probabilites: np.ndarray, seuil: float = 0.5) -> list[dict]:
    """Les taches de chaque groupe sur une photo (probabilités (32, 48, classes)) : carrés, et le pied (le carré le plus bas de
    chaque colonne de la tache)."""
    classe = probabilites.argmax(-1)
    sure = probabilites.max(-1) >= seuil
    sortie = []
    for k, g in enumerate(CLASSES_MEUBLES):
        if g == RIEN:
            continue
        masque = ((classe == k) & sure).astype(np.uint8)
        n, etiq, stats, _ = cv2.connectedComponentsWithStats(masque, connectivity=8)
        for e in range(1, n):
            if stats[e, cv2.CC_STAT_AREA] < TACHE_MIN.get(g, TACHE_MIN_DEFAUT):
                continue
            lignes, colonnes = np.nonzero(etiq == e)
            pied = [(int(c), int(lignes[colonnes == c].max())) for c in np.unique(colonnes)]
            sortie.append({"groupe": g, "carres": int(len(lignes)), "pied": pied,
                           "confiance": float(probabilites[lignes, colonnes, k].mean())})
    return sortie


def vers_le_sol(u: float, v: float, cam) -> tuple[float, float] | None:
    """Le point du sol vu au pixel (u, v) de la photo d'origine (None si le rayon ne descend pas)."""
    from moteur.camera_photo import axes
    x, y, z, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    d = vue + (u - u0) / f * droite - (v - v0) / f * haut
    if d[2] >= -1e-6:
        return None
    t = -z / d[2]
    return (x + t * d[0], y + t * d[1])


def meubles_d_une_photo(probabilites: np.ndarray, cam, largeur: int, hauteur: int, piece: dict | None) -> list[dict]:
    """Meubles vus sur une photo : groupe, place au sol (m), largeur vue, confiance."""
    from moteur.sol_a_plat import dans_polygone
    fu, fv = largeur / (TAILLE_ENTREE[0] // CARRE), hauteur / (TAILLE_ENTREE[1] // CARRE)
    sortie = []
    for t in taches(probabilites):
        points = []
        for c, l in t["pied"]:
            p = vers_le_sol((c + 0.5) * fu, (l + 1.0) * fv, cam)  # bas du carré le plus bas
            if p is not None and math.dist(p, cam[:2]) < 12:
                points.append(p)
        if len(points) < 2:
            continue
        pts = np.array(points)
        if piece is not None:
            dedans = dans_polygone(pts[:, 0], pts[:, 1], piece["contour"])
            if dedans.sum() < 2:
                continue
            pts = pts[dedans]
        _, (l, p, h) = TYPE_DE_GROUPE[t["groupe"]]
        # le pied vu est le bord AVANT du meuble (côté appareil) : le milieu est une demi-profondeur plus loin
        avant = pts.mean(0)
        direction = avant - np.asarray(cam[:2], float)
        direction /= max(np.linalg.norm(direction), 1e-9)
        recul = 0.0 if t["groupe"] == "tapis" else p / 2
        centre = avant + direction * recul
        etendue = float(np.linalg.norm(pts.max(0) - pts.min(0)))
        sortie.append({"groupe": t["groupe"], "position": [float(centre[0]), float(centre[1])], "largeur_vue": etendue,
                       "confiance": t["confiance"], "poids": t["carres"]})
    return sortie


def fusionner(vus: list[dict]) -> list[dict]:
    """Le même meuble vu sur plusieurs photos ne compte qu'une fois : regroupement par groupe et distance (moyenne pondérée)."""
    restants = sorted(vus, key=lambda m: -m["poids"])
    sortie = []
    while restants:
        tete = restants.pop(0)
        seuil = FUSION_M.get(tete["groupe"], FUSION_DEFAUT)
        paquet = [tete] + [m for m in restants if m["groupe"] == tete["groupe"] and math.dist(m["position"], tete["position"]) < seuil]
        restants = [m for m in restants if m not in paquet]
        poids = np.array([m["poids"] * m["confiance"] for m in paquet])
        pos = (np.array([m["position"] for m in paquet]) * poids[:, None]).sum(0) / poids.sum()
        sortie.append({"groupe": tete["groupe"], "position": [round(float(pos[0]), 3), round(float(pos[1]), 3)],
                       "vues": len(paquet), "confiance": round(float(np.mean([m["confiance"] for m in paquet])), 3),
                       "largeur_vue": round(float(max(m["largeur_vue"] for m in paquet)), 2)})
    return sortie


def orienter(meuble: dict, piece: dict) -> float:
    """Face du meuble (degrés) : dos au mur le plus proche s'il en est à moins de CONTRE_MUR_M, sinon vers le milieu de la pièce."""
    c = np.asarray(piece["contour"], float)
    p = np.asarray(meuble["position"], float)
    meilleur, normale = math.inf, None
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        ab = b - a
        t = float(np.clip((p - a) @ ab / max(ab @ ab, 1e-12), 0, 1))
        q = a + t * ab
        d = float(np.linalg.norm(p - q))
        if d < meilleur and d > 1e-6:
            meilleur, normale = d, (p - q) / d
    _, (l, pr, h) = TYPE_DE_GROUPE[meuble["groupe"]]
    if normale is not None and meilleur < CONTRE_MUR_M + pr / 2:
        return math.degrees(math.atan2(normale[1], normale[0]))
    centre = c.mean(0) - p
    return math.degrees(math.atan2(centre[1], centre[0]))


def vers_meubles_du_logement(trouves: list[dict], logement: dict) -> list[dict]:
    """Meubles trouvés → champ « meubles » du logement (statut « estime », source « repérage photos »)."""
    from moteur.sol_a_plat import piece_de
    sortie = []
    for k, m in enumerate(trouves, start=1):
        piece = piece_de(m["position"], logement["pieces"])
        if piece is None:
            continue
        categorie, dims = TYPE_DE_GROUPE[m["groupe"]]
        sortie.append({"id": f"reperage_{k}", "categorie": categorie, "piece": piece["id"], "position": m["position"],
                       "face": round(orienter(m, piece), 1), "dimensions": list(dims), "statut": "estime",
                       "source": f"repérage photos ({m['vues']} photo(s))", "confiance": min(1.0, m["confiance"])})
    return sortie


def vu_sur_une_photo(m: dict, cameras: list, logement: dict, largeur: int = 1206, hauteur: int = 804) -> bool:
    """Le milieu du meuble (à mi-hauteur) est-il dans le cadre d'une photo prise dans SA pièce, entre 0,5 et 12 m ? Sert à ne
    pas reprocher à Atelya un meuble qu'aucune photo ne montre."""
    from moteur.camera_photo import projeter
    from moteur.sol_a_plat import piece_de, piece_de_l_appareil
    piece = piece_de(m["position"], logement["pieces"])
    point = (m["position"][0], m["position"][1], m.get("altitude", 0) + m["dimensions"][2] / 2)
    for cam in cameras:
        p_cam, _ = piece_de_l_appareil(cam, logement["pieces"])
        if piece is None or p_cam is None or p_cam["id"] != piece["id"]:
            continue
        u, v, d = projeter(point, cam)
        if 0.5 < d < 12 and 0 <= u < largeur and 0 <= v < hauteur:
            return True
    return False


def noter_meubles(trouves: list[dict], verite: list[dict], distance_max: float = 0.8, cameras=None, logement=None) -> dict:
    """Comparaison avec les meubles relevés à la main (même groupe, à moins de distance_max) : retrouvés, en trop, écart de place.
    Avec les caméras et le logement, seuls les meubles vus sur au moins une photo sont à trouver."""
    a_trouver = [m for m in verite if groupe(m["categorie"]) and m.get("altitude", 0) < 0.3]
    if cameras is not None and logement is not None:
        a_trouver = [m for m in a_trouver if vu_sur_une_photo(m, cameras, logement)]
    libres = list(range(len(trouves)))
    ecarts, par_groupe = [], {}
    for m in a_trouver:
        g = groupe(m["categorie"])
        candidats = [(math.dist(trouves[i]["position"], m["position"]), i) for i in libres if trouves[i]["groupe"] == g]
        candidats = [c for c in candidats if c[0] <= distance_max]
        n = par_groupe.setdefault(g, [0, 0])
        n[1] += 1
        if candidats:
            d, i = min(candidats)
            libres.remove(i)
            ecarts.append(d)
            n[0] += 1
    return {"retrouves": f"{len(ecarts)}/{len(a_trouver)}", "en_trop": len(libres), "ecart_moyen_m": round(float(np.mean(ecarts)), 2)
            if ecarts else None, "par_groupe": {g: f"{a}/{b}" for g, (a, b) in sorted(par_groupe.items())}}


# ---------------------------------------------------------------- repérage par OWLv2 (10/11/2026)
# Repérage par OWLv2 (10/11/2026, NT : « prends ce qu'il y a de mieux ») : note minimale par groupe, réglée sur les tirages
# d'ENTRAÎNEMENT (meilleur F1, outils/habillage/reperer_meubles_owl.py), notée sur le CONTRÔLE fr-031/fr-038 :
# anciens tirages 45/84 retrouvés, 33 en trop (DINOv2 : 44/84, 44) ; tirages à vrais lits 56/99, 26 en trop (DINOv2 : 36/99,
# 57) ; lits 8/11 (2/11), tables 13/23 (8/23). Remplace le repérage DINOv2 (meubles-vits14-v1.pt, gardé pour comparaison).
SEUILS_OWL = {"canape": 0.5, "fauteuil": 0.5, "chaise": 0.3, "table": 0.3, "lit": 0.4, "rangement": 0.25, "tapis": 0.5,
              "lampe": 0.25, "plante": 0.5}  # plante : jamais retrouvée à l'entraînement (0/44) → seuil haut, presque éteinte
SEUIL_OWL_DEFAUT = 0.25
POIDS_COUPE = 0.1  # poids dans la fusion d'un meuble coupé par le bas de la photo


def meubles_owl_d_une_photo(objets: list[dict], groupe_de: dict, cam, largeur: int, hauteur: int, piece: dict | None,
                            seuils: dict | None = None, seuil_defaut: float = SEUIL_OWL_DEFAUT) -> list[dict]:
    """Meubles vus sur une photo d'après les rectangles d'OWLv2 (moteur/owlv2.py, objets()) : le BAS du rectangle est le pied
    du meuble (son bord avant, côté appareil) ; la caméra calée le reporte au sol ; le milieu est une demi-profondeur plus loin.
    Un tapis est à plat : son milieu est entre le haut et le bas du rectangle reportés au sol. Rend groupe, place, largeur vue."""
    from moteur.sol_a_plat import dans_polygone
    seuils = SEUILS_OWL if seuils is None else seuils
    sortie = []
    for o in objets:
        g = groupe_de.get(o["nom"])
        if g not in TYPE_DE_GROUPE or o["note"] < seuils.get(g, seuil_defaut):
            continue
        x0, y0, x1, y1 = o["boite"]
        um = (x0 + x1) / 2
        bas = min(y1, hauteur - 1)
        pied = vers_le_sol(um, bas, cam)
        gauche, droite = vers_le_sol(x0, bas, cam), vers_le_sol(x1, bas, cam)
        if pied is None or math.dist(pied, cam[:2]) > 12:
            continue
        _, (l, p, h) = TYPE_DE_GROUPE[g]
        if g == "tapis":
            haut = vers_le_sol(um, max(y0, 0), cam)
            centre = np.asarray(pied) if haut is None or math.dist(haut, cam[:2]) > 12 else (np.asarray(pied) + np.asarray(haut)) / 2
        else:
            direction = np.asarray(pied, float) - np.asarray(cam[:2], float)
            direction /= max(np.linalg.norm(direction), 1e-9)
            centre = np.asarray(pied, float) + direction * p / 2
        if piece is not None and not dans_polygone(np.array([centre[0]]), np.array([centre[1]]), piece["contour"])[0]:
            continue
        etendue = math.dist(gauche, droite) if gauche is not None and droite is not None else 0.0
        poids = float((x1 - x0) * (y1 - y0) / (largeur * hauteur) * 100)
        if y1 >= hauteur - 3 and g != "tapis":
            poids *= POIDS_COUPE  # coupé par le bas de la photo : son vrai pied est plus près, la place est peu sûre
        sortie.append({"groupe": g, "position": [float(centre[0]), float(centre[1])], "largeur_vue": etendue,
                       "confiance": float(o["note"]), "poids": poids})
    return sortie


CONTRE_LE_MUR = ("lit", "canape", "rangement")  # meubles presque toujours dos (tête) au mur
COLLER_MAX_M = 1.0  # le mur le plus proche à au plus une demi-profondeur + 1 m : on y colle le meuble


def coller_au_mur(meuble: dict, piece: dict) -> dict:
    """Un lit (tête), un canapé, un rangement (dos) : collé au mur le plus proche s'il en est assez près — son milieu est mis à
    une demi-profondeur (+ 3 cm) de ce mur, sans bouger le long du mur. La place lue sur la photo est sûre en travers de la vue,
    peu sûre en profondeur : le mur la corrige."""
    if meuble["groupe"] not in CONTRE_LE_MUR or piece is None:
        return meuble
    c = np.asarray(piece["contour"], float)
    p = np.asarray(meuble["position"], float)
    _, (l, pr, h) = TYPE_DE_GROUPE[meuble["groupe"]]
    meilleur, q_mur, normale = math.inf, None, None
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        ab = b - a
        t = float(np.clip((p - a) @ ab / max(ab @ ab, 1e-12), 0, 1))
        q = a + t * ab
        d = float(np.linalg.norm(p - q))
        if d < meilleur and d > 1e-6 and 0.0 < t < 1.0:
            meilleur, q_mur, normale = d, q, (p - q) / d
    if q_mur is None or meilleur > pr / 2 + COLLER_MAX_M:
        return meuble
    nouveau = q_mur + normale * (pr / 2 + 0.03)
    return {**meuble, "position": [round(float(nouveau[0]), 3), round(float(nouveau[1]), 3)]}


def reperer_owl(photos: list, logement: dict, objets_par_photo: list[list[dict]], groupe_de: dict,
                seuils: dict | None = None, coller: bool = True) -> list[dict]:
    """photos : [(largeur, hauteur, caméra 8 nombres)] ; objets_par_photo : rectangles d'OWLv2 de chaque photo → meubles
    trouvés (fusionnés entre photos ET entre phrases : « a bed » et « a bed with a duvet » sur le même lit ne font qu'un)."""
    from moteur.sol_a_plat import piece_de_l_appareil
    vus = []
    for (largeur, hauteur, cam), objets in zip(photos, objets_par_photo):
        piece, _ = piece_de_l_appareil(cam, logement["pieces"])
        vus += meubles_owl_d_une_photo(objets, groupe_de, cam, largeur, hauteur, piece, seuils)
    trouves = fusionner(vus)
    if coller:
        from moteur.sol_a_plat import piece_de
        trouves = [coller_au_mur(m, piece_de(m["position"], logement["pieces"])) for m in trouves]
    return trouves


def reperer_depuis_releve(releve: dict, logement: dict, racine, owl=None, journal=lambda *_: None) -> list[dict]:
    """Photos calées du client (cameras-photos.json) → meubles trouvés par OWLv2 (groupe, place, vues, confiance). Pour les
    poser dans le logement : vers_meubles_du_logement()."""
    from pathlib import Path

    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image
    from moteur.owlv2 import charger as charger_owl, objets
    from moteur.pas_du_sol import NOMS, REQUETES
    owl = owl or charger_owl()
    requetes = owl.textes(NOMS)
    groupe_de = {n: g for n, g in REQUETES.items() if g in TYPE_DE_GROUPE}
    dossier = Path(racine) / releve["photos"]
    modele = releve.get("fichier", "{nom}.png")
    photos, objs = [], []
    for nom, d in releve["cameras"].items():
        img = lire_image(dossier / modele.format(nom=nom))
        if img is None:
            raise FileNotFoundError(dossier / modele.format(nom=nom))
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        o = objets(owl.detecter(rgb, requetes), NOMS, seuil=0.1)
        photos.append((rgb.shape[1], rgb.shape[0], camera_depuis_dict(d["camera"])))
        objs.append(o)
        journal(f"  {nom} : {sum(1 for x in o if x['nom'] in groupe_de and x['note'] >= SEUILS_OWL.get(groupe_de[x['nom']], 1))} meuble(s) vu(s)")
    return reperer_owl(photos, logement, objs, groupe_de)
