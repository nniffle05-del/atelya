r"""MEUBLES PRÉCIS : la SORTE exacte, la TAILLE et la COULEUR de chaque meuble, tirées des photos (16/11/2026).

Pourquoi (NT, 16/11/2026 : « je veux qu'Atelya soit le plus performant possible », après le film d'app-004 où une table ronde de
90 cm était posée en table de 1,40 m, une armoire blanche de 2 m en buffet de bois de 90 cm, un canapé bleu en gris) : le
repérage (moteur/reperer_meubles.py) ne gardait de chaque meuble vu qu'un GROUPE (« rangement », « table ») et lui donnait la
taille d'un meuble courant, sans couleur. Or :
- le détecteur dit plus que le groupe : « a nightstand », « a wardrobe », « a tv stand », « a coffee table », « a desk »… ;
- (la taille, elle, ne se mesure pas bien sur le rectangle : voir `dimensions`) ;
- les pixels du rectangle donnent sa couleur ;
- et la maquette sait déjà choisir un modèle par sorte, taille et couleur (moteur/meubles.py : c'est ainsi qu'app-001 et
  app-002 ont été meublés à la main).
Banc de fidélité (outils/atelya/banc_fidelite.py), défaut trouvé au passage : deux meubles différents de la même photo (la
table ronde et le meuble télé, vus « table » tous les deux) étaient FONDUS en un seul meuble posé entre les deux (fusion à
1,8 m). Règle ajoutée : deux objets distincts d'une même photo ne sont jamais le même meuble.

Ce module ne pose rien lui-même : il prépare, pour moteur/reperer_meubles.py, ce que chaque photo voit (un objet par meuble,
avec ses mesures), la fusion entre photos, puis la sorte, la taille et la couleur de chaque meuble trouvé.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"

# phrase du détecteur → catégorie de la maquette (moteur/meubles.py). Une phrase absente garde le meuble courant de son groupe.
CATEGORIE_DE = {
    "a bed": "lit", "a bed with a duvet": "lit", "a bunk bed": "lit_superpose", "a loft bed": "lit_superpose",
    "a sofa": "canape", "a couch": "canape", "an armchair": "fauteuil",
    "a chair": "chaise", "a stool": "chaise", "an office chair": "chaise_de_bureau",
    "a dining table": "table", "a table": "table", "a coffee table": "table_basse", "a desk": "bureau",
    "a side table": "table_d_appoint",
    "a chest of drawers": "commode", "a cabinet": "rangement", "a bookshelf": "bibliotheque", "a shelf": "rangement",
    "a tv stand": "meuble_tv", "a nightstand": "table_de_chevet", "a bench": "banc", "a wardrobe": "placard",
    "a sideboard": "rangement", "kitchen cabinets": "meuble_cuisine_bas",
    "a rug": "tapis", "a carpet": "tapis", "a floor lamp": "lampadaire", "a lamp": "lampadaire", "a potted plant": "plante",
}
# catégorie → taille courante (largeur, profondeur, hauteur), largeur possible (min, max), hauteur possible (min, max)
TAILLES = {
    "canape": ((2.0, 0.9, 0.85), (1.3, 3.2), (0.7, 1.0)),
    "fauteuil": ((0.8, 0.8, 0.85), (0.6, 1.1), (0.7, 1.1)),
    "chaise": ((0.5, 0.55, 0.85), (0.4, 0.6), (0.75, 1.0)),
    "chaise_de_bureau": ((0.6, 0.6, 1.0), (0.5, 0.7), (0.85, 1.2)),
    "table": ((1.4, 0.8, 0.75), (0.7, 2.6), (0.7, 0.8)),
    "table_basse": ((1.0, 0.6, 0.42), (0.5, 1.6), (0.3, 0.5)),
    "table_d_appoint": ((0.5, 0.5, 0.55), (0.35, 0.8), (0.4, 0.7)),
    "bureau": ((1.3, 0.65, 0.75), (0.8, 2.0), (0.7, 0.8)),
    "lit": ((1.6, 2.05, 1.0), (0.9, 2.0), (0.9, 1.1)),
    "lit_superpose": ((1.0, 2.0, 1.7), (0.9, 1.6), (1.4, 2.0)),
    "commode": ((0.9, 0.45, 0.85), (0.6, 1.6), (0.6, 1.3)),
    "rangement": ((1.2, 0.45, 0.9), (0.5, 2.4), (0.5, 2.3)),
    "bibliotheque": ((0.8, 0.3, 1.8), (0.5, 2.5), (1.0, 2.5)),
    "meuble_tv": ((1.4, 0.4, 0.5), (0.8, 2.4), (0.3, 0.7)),
    "table_de_chevet": ((0.45, 0.4, 0.55), (0.35, 0.65), (0.4, 0.7)),
    "banc": ((1.1, 0.4, 0.45), (0.7, 1.8), (0.35, 0.6)),
    "placard": ((1.5, 0.6, 2.2), (0.8, 3.5), (1.7, 2.6)),
    "meuble_cuisine_bas": ((1.8, 0.6, 0.9), (0.6, 4.0), (0.85, 0.95)),
    "tapis": ((1.8, 1.3, 0.02), (0.6, 3.5), (0.02, 0.02)),
    "lampadaire": ((0.4, 0.4, 1.6), (0.3, 0.6), (1.2, 1.9)),
    "plante": ((0.5, 0.5, 1.0), (0.3, 0.9), (0.4, 2.0)),
    # sortes que la phrase du détecteur ne donne jamais, mais qu'une LECTURE des photos nomme (moteur/photos_lues.py)
    "tabouret_haut": ((0.45, 0.45, 1.0), (0.35, 0.55), (0.9, 1.15)),
    "etagere_cubes": ((1.5, 0.4, 0.8), (0.4, 2.0), (0.4, 2.0)),
    "lampe": ((0.3, 0.3, 0.5), (0.2, 0.5), (0.3, 0.8)),
    "colonne_cuisine": ((0.6, 0.6, 2.2), (0.6, 2.4), (1.9, 2.5)),
    "meuble_cuisine_haut": ((1.8, 0.35, 0.7), (0.6, 4.0), (0.6, 0.9)),
    "ilot": ((2.0, 0.9, 0.9), (1.0, 3.0), (0.85, 1.1)),
    "caisson": ((1.2, 0.3, 1.2), (0.5, 3.0), (0.8, 2.6)),
}
BORD_PX = 4  # un rectangle à moins de 4 px du bord de la photo est coupé par le cadre : il ne mesure rien de ce côté
FUSION_M = {"chaise": 0.45, "fauteuil": 0.6}  # distance en dessous de laquelle deux vues sont le même meuble (comme avant)
FUSION_DEFAUT = 1.8
# Fusion par SORTE exacte (photos lues : la même sorte revient d'une photo à l'autre) : les petits meubles qui vont par deux
# (chevets de part et d'autre d'un lit, lampes) ne se fondent qu'à moins de 90 cm ; le reste comme avant.
# Les GRANDS meubles adossés (un buffet de 2 m, un linéaire de cuisine, une armoire) : chaque photo en voit un bout différent, leurs
# vues s'étalent sur leur longueur ; elles se fondent jusqu'à 2,5 m (deux de la même photo restent toujours deux meubles).
FUSION_SORTE_M = {"chaise": 0.45, "tabouret_haut": 0.45, "chaise_de_bureau": 0.6, "fauteuil": 0.6, "table_de_chevet": 0.9,
                  "table_d_appoint": 0.9, "lampe": 0.9, "lampadaire": 0.9, "plante": 0.9,
                  "rangement": 2.5, "meuble_cuisine_bas": 2.5, "placard": 2.5, "canape": 2.5, "meuble_tv": 2.5, "ilot": 2.5}
# côté d'un meuble ROND de chaque sorte (une lecture des photos dit la forme : « table ronde »)
COTE_ROND = {"table": 1.0, "table_basse": 0.8, "table_d_appoint": 0.5, "tapis": 1.6}


def taille_courante(categorie: str) -> tuple[float, float, float]:
    return TAILLES.get(categorie, TAILLES["rangement"])[0]


def mesurer(boite, cam, largeur: int, hauteur: int, rgb: np.ndarray | None) -> dict:
    """Ce que le rectangle d'un meuble dit de lui sur UNE photo : son pied au sol, sa largeur vue (en travers du regard), la
    pente du regard vers son haut, sa couleur, et les côtés où le cadre de la photo le coupe."""
    from moteur.camera_photo import axes
    from moteur.reperer_meubles import vers_le_sol

    x0, y0, x1, y1 = (float(v) for v in boite)
    um, bas = (x0 + x1) / 2, min(y1, hauteur - 1)
    pied = vers_le_sol(um, bas, cam)
    gauche, droite_ = vers_le_sol(x0, bas, cam), vers_le_sol(x1, bas, cam)
    cx, cy, cz, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    d = vue + (um - u0) / f * droite - (y0 - v0) / f * haut  # le rayon vers le milieu du haut du rectangle
    plat = float(np.hypot(d[0], d[1]))
    m = {"pied": pied, "largeur_vue": math.dist(gauche, droite_) if gauche is not None and droite_ is not None else None,
         "pente_du_haut": float(d[2] / plat) if plat > 1e-6 else None,
         "coupe_cotes": x0 <= BORD_PX or x1 >= largeur - BORD_PX, "coupe_haut": y0 <= BORD_PX, "coupe_bas": y1 >= hauteur - 3,
         "couleur": None}
    if pied is not None:
        fond = vers_le_sol(um, max(y0, 0.0), cam)  # un tapis est à plat : le haut de son rectangle touche aussi le sol
        m["profondeur_vue"] = math.dist(pied, fond) if fond is not None and math.dist(fond, cam[:2]) < 12 else None
    if rgb is not None:
        ix0, ix1 = int(x0 + 0.25 * (x1 - x0)), int(x0 + 0.75 * (x1 - x0))
        iy0, iy1 = int(y0 + 0.25 * (y1 - y0)), int(y0 + 0.75 * (y1 - y0))
        coeur = rgb[max(0, iy0):max(iy0 + 1, iy1), max(0, ix0):max(ix0 + 1, ix1)].reshape(-1, 3)
        if len(coeur):
            m["couleur"] = [int(v) for v in np.median(coeur, axis=0)]
    return m


def fusionner(vus: list[dict], par_sorte: bool = False) -> list[dict]:
    """Le même meuble vu sur plusieurs photos ne compte qu'une fois : vues du même GROUPE à moins de FUSION_M du meuble le
    plus net… SAUF deux objets distincts d'une MÊME photo, qui restent deux meubles. La sorte du meuble est celle que ses vues
    donnent le plus souvent (pondérée par leur poids et leur note) ; sa place est la moyenne pondérée, comme avant.
    `par_sorte` (photos lues) : seules les vues de la même SORTE exacte se fondent (un bureau et une table voisins restent deux)."""
    restants = sorted(vus, key=lambda m: -m["poids"])
    sortie = []
    cle = "categorie" if par_sorte else "groupe"
    while restants:
        tete = restants.pop(0)
        seuil = FUSION_M.get(tete["groupe"], FUSION_DEFAUT)
        if par_sorte:
            seuil = FUSION_SORTE_M.get(tete["categorie"], seuil)
        paquet, photos = [tete], {tete.get("photo")}
        for m in sorted(restants, key=lambda m: math.dist(m["position"], tete["position"])):
            if m[cle] != tete[cle] or math.dist(m["position"], tete["position"]) >= seuil:
                continue
            if m.get("photo") is not None and m.get("photo") in photos:
                continue  # un autre objet de la même photo : un autre meuble
            paquet.append(m)
            photos.add(m.get("photo"))
        restants = [m for m in restants if not any(m is p for p in paquet)]
        poids = np.array([m["poids"] * m["confiance"] for m in paquet])
        pos = (np.array([m["position"] for m in paquet]) * poids[:, None]).sum(0) / poids.sum()
        voix: dict[str, float] = {}
        for m, w in zip(paquet, poids):
            if m.get("categorie"):
                voix[m["categorie"]] = voix.get(m["categorie"], 0.0) + float(w)
        fusionne = {"groupe": tete["groupe"], "categorie": max(voix, key=voix.get) if voix else None,
                    "position": [round(float(pos[0]), 3), round(float(pos[1]), 3)], "vues": len(paquet),
                    "confiance": round(float(np.mean([m["confiance"] for m in paquet])), 3),
                    "largeur_vue": round(float(max(m["largeur_vue"] for m in paquet)), 2),
                    "mesures": [m["mesure"] for m in paquet if m.get("mesure")]}
        formes: dict[str, float] = {}
        for m, w in zip(paquet, poids):
            if m.get("forme"):
                formes[m["forme"]] = formes.get(m["forme"], 0.0) + float(w)
        if formes:
            fusionne["forme"] = max(formes, key=formes.get)
        sortie.append(fusionne)
    return sortie


def selon_la_forme(categorie: str, dims, forme: str | None) -> tuple[float, float, float]:
    """La taille corrigée par ce qu'une lecture des photos dit de la forme : un meuble ROND a la même largeur et profondeur (la
    table ronde d'app-004 était posée en table de 1,40 × 0,80 m) ; un lit « une place » fait 90 cm de large."""
    l, p, h = dims
    if not forme:
        return l, p, h
    if forme in ("ronde", "rond"):
        c = COTE_ROND.get(categorie, min(l, p))
        return c, c, h
    if categorie == "lit" and forme == "une place":
        return 0.9, p, h
    return l, p, h


def dimensions(categorie: str, face: float, position, mesures: list[dict]) -> tuple[float, float, float]:
    """La taille du meuble : celle d'un meuble COURANT DE SA SORTE (une table de chevet de 45 cm, une armoire de 2,20 m de
    haut), et non plus du groupe (tout « rangement » = un buffet de 1,20 × 0,90 m).

    La taille n'est PAS mesurée sur les rectangles des photos : essayé le 16/11/2026 (largeur vue au pied du meuble, hauteur par
    la pente du regard vers son haut, vues de face seulement, la plus grande retenue) et comparé aux 30 meubles relevés à la
    main d'app-001 et app-002 (hors chaises et tapis). Écart moyen de largeur : taille courante du groupe 33 %, taille courante
    de la sorte 23 %, taille mesurée 28 % ; de hauteur : 34 %, 23 %, 24 %. La mesure ne fait pas mieux que la sorte : le
    rectangle ne couvre souvent qu'un morceau du meuble et la place de l'appareil n'est connue qu'à 40 cm près. À reprendre
    avec les points en mètres de MoGe-2 pris DANS le rectangle (pas fait)."""
    return taille_courante(categorie)


def couleur(mesures: list[dict]) -> list[int] | None:
    """La couleur du meuble : la médiane, canal par canal, de ce que ses vues montrent en son cœur."""
    c = [m["couleur"] for m in mesures if m.get("couleur")]
    return [int(v) for v in np.median(np.array(c), axis=0)] if c else None
