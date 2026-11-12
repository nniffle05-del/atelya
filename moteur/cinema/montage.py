"""Le MONTEUR : la version « fondus » d'un vol (12/11/2026, NT : « je compare d'abord » une seule prise et des fondus).

La caméra reste continue DANS chaque pièce ; les passages sans intérêt (couloirs, entrée traversée, moments où le contrôleur voit
le nez de la caméra sur un mur) sont retirés et les morceaux gardés se raccordent par un FONDU ENCHAÎNÉ court. Le montage se fait
sur les images déjà tournées : aucun nouveau rendu.
"""
from __future__ import annotations

from moteur import realisateur as rz
from moteur.cinema.reglages import CIRCULATION, IPS

FONDU_S = 0.6  # durée d'un fondu enchaîné
OUVERTURE_S = 2.5  # le début du film (l'entrée, le premier regard) n'est jamais coupé
GARDE_MIN_S = 1.5  # un morceau gardé plus court que ça entre deux coupes est coupé aussi (pas de flash d'une demi-seconde)
COUPE_MIN_S = 0.5  # un passage à retirer plus court que ça est gardé (un fondu coûte plus qu'il ne rapporte)


def _type_piece(logement: dict, ident: str | None) -> str | None:
    piece = next((p for p in logement["pieces"] if p["id"] == ident), None)
    return rz._type(piece) if piece else None


def passages_a_retirer(logement: dict, controle: dict, images: int) -> list[tuple[int, int]]:
    """Les passages à retirer (première et dernière image) : les moments dans une circulation, et ceux où le contrôleur voit le
    nez de la caméra sur un mur ; jamais l'ouverture ni la fin."""
    retirer = [False] * images
    for d in controle["defauts"]:
        if d["genre"] == "nez_au_mur" and d["debut_s"] is not None:
            for k in range(int(d["debut_s"] * IPS), min(images, int(d["fin_s"] * IPS) + 1)):
                retirer[k] = True
    # les pièces image par image (contrôleur)
    for k, piece in enumerate(controle.get("pieces_par_image") or []):
        if _type_piece(logement, piece) in CIRCULATION:
            retirer[k] = True
    debut_garde = int(OUVERTURE_S * IPS)
    for k in range(min(images, debut_garde)):
        retirer[k] = False
    fin_garde = images - int(controle.get("fin_garde_s", 2.5) * IPS)
    for k in range(max(0, fin_garde), images):
        retirer[k] = False
    # en morceaux ; les morceaux gardés trop courts entre deux coupes sont coupés ; les coupes trop courtes sont gardées
    morceaux = []
    k = 0
    while k < images:
        j = k
        while j + 1 < images and retirer[j + 1] == retirer[k]:
            j += 1
        morceaux.append([retirer[k], k, j])
        k = j + 1
    for i, m in enumerate(morceaux):
        if not m[0] and 0 < i < len(morceaux) - 1 and (m[2] - m[1] + 1) < GARDE_MIN_S * IPS:
            m[0] = True
    coupes, courant = [], None
    for retire, a, b in morceaux:
        if retire:
            courant = [courant[0], b] if courant else [a, b]
        elif courant:
            coupes.append(tuple(courant))
            courant = None
    if courant:
        coupes.append(tuple(courant))
    return [(a, b) for a, b in coupes if b - a + 1 >= COUPE_MIN_S * IPS]


def suite_d_images(images: int, coupes: list[tuple[int, int]]) -> list[tuple[int, int, float]]:
    """Le film monté, image par image : (image A, image B, mélange) — mélange 0 = A seule. À chaque coupe, un fondu enchaîné de
    FONDU_S : la fin du morceau d'avant se fond dans le début du morceau d'après."""
    n_fondu = max(1, int(FONDU_S * IPS))
    gardes, debut = [], 0
    for a, b in coupes:
        if a > debut:
            gardes.append((debut, a - 1))
        debut = b + 1
    if debut < images:
        gardes.append((debut, images - 1))
    sortie = []
    for i, (a, b) in enumerate(gardes):
        fin = b - n_fondu if i < len(gardes) - 1 else b
        sortie += [(k, k, 0.0) for k in range(a if i == 0 else a + n_fondu, fin + 1)]
        if i < len(gardes) - 1:
            a2 = gardes[i + 1][0]
            for j in range(n_fondu):
                t = (j + 1) / (n_fondu + 1)
                sortie.append((min(b, b - n_fondu + 1 + j), a2 + j, t * t * (3 - 2 * t)))
    return sortie
