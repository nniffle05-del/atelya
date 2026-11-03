"""La vérité terrain vectorielle d'un logement inventé : le fichier `geometrie.json`.

C'est la référence dont tout le reste découle (le dessin, les masques, le modèle 3D) :
elle est écrite en mètres, dans le repère du logement (x vers l'est, y vers le nord,
origine au coin sud-ouest du cadre intérieur du niveau 0), sans rien savoir des images.

Schéma `plan-synthetique/1.0` :

- `niveaux[]` : pour chaque niveau, son contour intérieur, ses murs (axe, épaisseur, polygone,
  porteur ou cloison, extérieur ou intérieur, pièces qu'il borde), ses ouvertures (type,
  sous-type, mur, position le long du mur, largeur, hauteur, allège, polygone, centre,
  orientation, côté d'ouverture, pièces reliées), ses pièces (type, nom, contour, surface,
  centre), les adjacences (deux pièces séparées par un mur) et les connexions (deux pièces
  reliées par une porte) ;
- `connectivite` : si toutes les pièces sont atteignables depuis l'entrée, et par où ;
- `surfaces` et `dimensions` globales, `parametres` de génération (graine, type, forme…).

Les identifiants sont ceux du logement.json de chaque niveau (format logement/0.1), ce qui
permet de passer de l'un à l'autre.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from moteur.generateur import VERSION_GENERATEUR
from moteur.generateur.logements import LogementGenere, Mur, Niveau, Ouverture, Piece, Rect, contour_piece, surface_piece

SCHEMA = "plan-synthetique/1.0"

# Les classes des masques sémantiques : une valeur par sorte d'élément. 0 = fond (hors logement).
CLASSES = {
    "fond": 0, "mur": 1, "porte": 2, "fenetre": 3, "porte_fenetre": 4,
    "sejour": 5, "principale": 5, "cuisine": 6, "chambre": 7, "sdb": 8, "sde": 8, "wc": 9, "entree": 10,
    "degagement": 11, "placard": 12, "buanderie": 13, "bureau": 14, "escalier": 15,
}
NOMS_CLASSES = {
    0: "fond", 1: "mur", 2: "porte", 3: "fenetre", 4: "porte_fenetre", 5: "sejour", 6: "cuisine", 7: "chambre",
    8: "salle_d_eau", 9: "wc", 10: "entree", 11: "degagement", 12: "placard", 13: "buanderie", 14: "bureau",
    15: "escalier",
}


def _m(v: float) -> float:
    return round(v / 1000, 3) + 0.0


def _pt(x: float, y: float) -> list[float]:
    return [_m(x), _m(y)]


def rect_du_mur(m: Mur) -> Rect:
    """Le rectangle occupé par le mur, en mm.

    Un mur extérieur va d'axe à axe de ses voisins ; on le rallonge d'une demi-épaisseur à chaque
    bout pour qu'il couvre tout l'angle (les murs extérieurs ont tous la même épaisseur). Un mur
    intérieur s'arrête sur la face des murs qu'il rejoint : rien à rallonger.
    """
    e = m.epaisseur / 2
    rallonge = e if m.dehors else 0
    r0 = 0 if m.coupe_debut else rallonge  # A3 : un bout qui s'arrête sur un mur en biais n'est pas rallongé
    r1 = 0 if m.coupe_fin else rallonge
    if m.vertical:
        return Rect(int(m.axe - e), int(m.debut - r0), int(m.axe + e), int(m.fin + r1))
    return Rect(int(m.debut - r0), int(m.axe - e), int(m.fin + r1), int(m.axe + e))


def rect_de_l_ouverture(o: Ouverture) -> Rect:
    e = o.mur.epaisseur / 2
    if o.mur.vertical:
        return Rect(int(o.mur.axe - e), int(o.u0), int(o.mur.axe + e), int(o.u1))
    return Rect(int(o.u0), int(o.mur.axe - e), int(o.u1), int(o.mur.axe + e))


def _polygone(r: Rect) -> list[list[float]]:
    return [_pt(r.x0, r.y0), _pt(r.x1, r.y0), _pt(r.x1, r.y1), _pt(r.x0, r.y1)]


def pieces_le_long(m: Mur, u0: float, u1: float, pieces: list[Piece]) -> tuple[str | None, str | None]:
    """Les pièces de chaque côté du mur entre u0 et u1 : (côté -, côté +) ; None = extérieur ou rien."""
    e = m.epaisseur / 2
    moins = plus = None
    for p in pieces:
        r = p.rect
        if m.vertical:
            le_long = r.y0 <= u0 + 1e-6 and u1 - 1e-6 <= r.y1
            if le_long and abs(r.x1 - (m.axe - e)) < 1e-6:
                moins = p.id
            if le_long and abs(r.x0 - (m.axe + e)) < 1e-6:
                plus = p.id
        else:
            le_long = r.x0 <= u0 + 1e-6 and u1 - 1e-6 <= r.x1
            if le_long and abs(r.y1 - (m.axe - e)) < 1e-6:
                moins = p.id
            if le_long and abs(r.y0 - (m.axe + e)) < 1e-6:
                plus = p.id
    return moins, plus


def pieces_bordees(m: Mur, pieces: list[Piece]) -> list[str]:
    """Toutes les pièces qui touchent une face du mur (sur une longueur non nulle)."""
    e = m.epaisseur / 2
    ids = []
    for p in pieces:
        r = p.rect
        if m.vertical:
            touche = abs(r.x1 - (m.axe - e)) < 1e-6 or abs(r.x0 - (m.axe + e)) < 1e-6
            recouvre = min(r.y1, m.fin) - max(r.y0, m.debut) > 0
        else:
            touche = abs(r.y1 - (m.axe - e)) < 1e-6 or abs(r.y0 - (m.axe + e)) < 1e-6
            recouvre = min(r.x1, m.fin) - max(r.x0, m.debut) > 0
        if touche and recouvre:
            ids.append(p.id)
    return ids


def adjacences(niveau: Niveau) -> list[dict]:
    """Les couples de pièces séparées par un mur, avec le mur et la longueur du contact."""
    resultat = []
    vus = set()
    for m in niveau.murs:
        if m.dehors:
            continue
        e = m.epaisseur / 2
        moins = [p for p in niveau.pieces if abs((p.rect.x1 if m.vertical else p.rect.y1) - (m.axe - e)) < 1e-6]
        plus = [p for p in niveau.pieces if abs((p.rect.x0 if m.vertical else p.rect.y0) - (m.axe + e)) < 1e-6]
        for a in moins:
            for b in plus:
                if m.vertical:
                    lo, hi = max(a.rect.y0, b.rect.y0, m.debut), min(a.rect.y1, b.rect.y1, m.fin)
                else:
                    lo, hi = max(a.rect.x0, b.rect.x0, m.debut), min(a.rect.x1, b.rect.x1, m.fin)
                if hi - lo > 0 and (a.id, b.id, m.id) not in vus:
                    vus.add((a.id, b.id, m.id))
                    resultat.append({"pieces": [a.id, b.id], "mur": m.id, "longueur": _m(hi - lo)})
    return resultat


def connexions(niveau: Niveau) -> list[dict]:
    """Les couples de pièces reliées par une porte (ou une porte-fenêtre vers l'extérieur)."""
    resultat = []
    for o in niveau.ouvertures:
        if o.type == "fenetre":
            continue
        moins, plus = pieces_le_long(o.mur, o.u0, o.u1, niveau.pieces)
        resultat.append({"ouverture": o.id, "pieces": [moins or "exterieur", plus or "exterieur"]})
    return resultat


def connectivite(log: LogementGenere, liens: dict[int, list[dict]]) -> dict:
    """Depuis la pièce où l'on entre, atteint-on toutes les pièces (en passant par l'escalier entre niveaux) ?"""
    voisins: dict[str, set[str]] = {p.id: set() for p in log.pieces}
    for lst in liens.values():
        for c in lst:
            a, b = c["pieces"]
            if a in voisins and b in voisins:
                voisins[a].add(b)
                voisins[b].add(a)
    # Les escaliers des deux niveaux sont un seul passage.
    escaliers = [p.id for p in log.pieces if p.sorte == "escalier"]
    for a in escaliers:
        for b in escaliers:
            if a != b:
                voisins[a].add(b)
    porte = next((o for o in log.niveaux[0].ouvertures if o.sous_type == "porte_entree"), None)
    if porte is None:
        return {"connexe": False, "entree": None, "atteintes": [], "non_atteintes": [p.id for p in log.pieces]}
    moins, plus = pieces_le_long(porte.mur, porte.u0, porte.u1, log.niveaux[0].pieces)
    depart = moins or plus
    vues = {depart}
    pile = [depart]
    while pile:
        x = pile.pop()
        for y in voisins[x]:
            if y not in vues:
                vues.add(y)
                pile.append(y)
    non = [p.id for p in log.pieces if p.id not in vues]
    return {"connexe": not non, "entree": depart, "atteintes": sorted(vues), "non_atteintes": non}


def decrire_niveau(log: LogementGenere, niveau: Niveau) -> dict:
    pieces = []
    for p in niveau.pieces:
        r = p.rect
        pieces.append({
            "id": p.id, "nom": p.nom, "type": p.sorte, "classe": CLASSES[p.sorte], "niveau": niveau.index,
            "contour": [_pt(x, y) for x, y in contour_piece(p)] if p.contour else _polygone(r),
            "cadre": [_m(r.x0), _m(r.y0), _m(r.x1), _m(r.y1)],
            "centre": _pt((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2),
            "surface": round(surface_piece(p) / 1e6, 2), "largeur": _m(r.largeur), "profondeur": _m(r.hauteur),
        })
    murs = []
    for m in niveau.murs:
        r = rect_du_mur(m)
        murs.append({
            "id": m.id, "niveau": niveau.index, "exterieur": bool(m.dehors), "porteur": bool(m.porteur),
            "orientation": "verticale" if m.vertical else "horizontale",
            "axe": {"debut": _pt(m.axe, m.debut) if m.vertical else _pt(m.debut, m.axe),
                    "fin": _pt(m.axe, m.fin) if m.vertical else _pt(m.fin, m.axe)},
            "epaisseur": _m(m.epaisseur), "longueur": _m(m.fin - m.debut), "hauteur": _m(niveau.hsp),
            "polygone": _polygone(r), "cote_exterieur": m.dehors,
            "pieces": pieces_bordees(m, niveau.pieces),
            "ouvertures": [o.id for o in niveau.ouvertures if o.mur is m],
        })
    for m in niveau.murs_libres:  # A3 : murs en biais / arrondis
        murs.append({
            "id": m.id, "niveau": niveau.index, "exterieur": True, "porteur": m.porteur,
            "orientation": "oblique" if m.forme == "biais" else "arrondi",
            "axe": {"debut": _pt(*m.axe[0]), "fin": _pt(*m.axe[-1])},
            "axe_points": [_pt(x, y) for x, y in m.axe],
            "epaisseur": _m(m.epaisseur),
            "longueur": _m(sum(math.dist(a, b) for a, b in zip(m.axe, m.axe[1:]))), "hauteur": _m(niveau.hsp),
            "polygone": [_pt(x, y) for x, y in m.polygone], "cote_exterieur": m.dehors,
            "pieces": [], "ouvertures": [],
        })
    ouvertures = []
    for o in niveau.ouvertures:
        r = rect_de_l_ouverture(o)
        moins, plus = pieces_le_long(o.mur, o.u0, o.u1, niveau.pieces)
        ouvertures.append({
            "id": o.id, "niveau": niveau.index, "type": o.type, "sous_type": o.sous_type, "classe": CLASSES[o.type],
            "mur": o.mur.id, "position": _m(o.u0 - o.mur.debut), "largeur": _m(o.u1 - o.u0),
            "hauteur": _m(o.hauteur), "allege": _m(o.allege), "epaisseur": _m(o.mur.epaisseur),
            "orientation": "verticale" if o.mur.vertical else "horizontale",
            "polygone": _polygone(r), "centre": _pt((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2),
            "ouvre_vers": o.vers, "charniere": o.charniere,
            "pieces": [moins or "exterieur", plus or "exterieur"],
        })
    cadre = niveau.cadre
    emprise = _surface_contour(niveau.coins)
    habitable = sum(surface_piece(p) for p in niveau.pieces)
    return {
        "index": niveau.index, "id": f"niveau_{niveau.index}", "z_sol": _m(niveau.z_sol),
        "hauteur_sous_plafond": _m(niveau.hsp),
        "contour_interieur": [_pt(x, y) for x, y in niveau.coins],
        "cadre": [_m(cadre.x0), _m(cadre.y0), _m(cadre.x1), _m(cadre.y1)],
        "dimensions": {"largeur": _m(cadre.largeur), "profondeur": _m(cadre.hauteur)},
        "surfaces": {"habitable": round(habitable / 1e6, 2), "emprise_interieure": round(emprise / 1e6, 2),
                     "cloisons": round((emprise - habitable) / 1e6, 2)},
        "pieces": pieces, "murs": murs, "ouvertures": ouvertures,
        "adjacences": adjacences(niveau), "connexions": connexions(niveau),
    }


def _surface_contour(coins: list[tuple[int, int]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(coins, coins[1:] + coins[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def decrire(log: LogementGenere) -> dict:
    """Le contenu de geometrie.json : toute la vérité terrain du logement, en mètres."""
    niveaux = [decrire_niveau(log, n) for n in log.niveaux]
    liens = {n["index"]: n["connexions"] for n in niveaux}
    return {
        "schema": SCHEMA,
        "version_generateur": VERSION_GENERATEUR,
        "unites": "m",
        "repere": "x vers l'est, y vers le nord, origine au coin sud-ouest du cadre intérieur ; z vers le haut",
        "identifiant": f"SYNTHESE-{log.graine:06d}",
        "parametres": {
            "graine": log.graine, "type": log.type, "forme": log.forme, "duplex": log.duplex,
            "famille": log.famille, "essais": log.essais,
            "epaisseur_murs_exterieurs": _m(log.ep_ext), "epaisseur_cloisons": _m(log.ep_cloison),
            "epaisseur_murs_porteurs": _m(log.ep_porteur), "hauteur_sous_plafond": _m(log.hsp),
            "plancher_intermediaire": _m(log.plancher),
        },
        "resume": {
            "surface_habitable": log.surface, "nombre_pieces": len(log.pieces), "nombre_niveaux": len(log.niveaux),
            "nombre_murs": len(log.murs), "nombre_ouvertures": len(log.ouvertures),
            "nombre_portes": sum(o.type == "porte" for o in log.ouvertures),
            "nombre_fenetres": sum(o.type != "porte" for o in log.ouvertures),
            "pieces_par_type": _compter(p.sorte for p in log.pieces),
        },
        "classes": NOMS_CLASSES,
        "niveaux": niveaux,
        "connectivite": connectivite(log, liens),
    }


def _compter(valeurs) -> dict[str, int]:
    c: dict[str, int] = {}
    for v in valeurs:
        c[v] = c.get(v, 0) + 1
    return dict(sorted(c.items()))


# ---------------------------------------------------------------- tramage des masques


def _retrait(poly: list[tuple[float, float]], d: float) -> list[tuple[float, float]] | None:
    """Le polygone convexe dont les côtés sont rentrés de `d` pixels ; None s'il est trop petit pour ça."""
    n = len(poly)
    aire2 = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))
    if abs(aire2) < 1e-9:
        return None
    sens = 1.0 if aire2 > 0 else -1.0
    lignes = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        longueur = math.hypot(dx, dy)
        if longueur < 1e-9:
            continue
        nx, ny = -dy / longueur * sens, dx / longueur * sens  # la normale vers l'intérieur
        lignes.append((x1 + nx * d, y1 + ny * d, dx, dy))
    if len(lignes) < 3:
        return None
    sommets = []
    for i in range(len(lignes)):
        ax, ay, adx, ady = lignes[i - 1]
        bx, by, bdx, bdy = lignes[i]
        det = adx * bdy - ady * bdx
        if abs(det) < 1e-9:
            return None
        t = ((bx - ax) * bdy - (by - ay) * bdx) / det
        sommets.append((ax + t * adx, ay + t * ady))
    aire2_apres = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(sommets, sommets[1:] + sommets[:1]))
    if aire2_apres * aire2 <= 0:  # retourné : le polygone faisait moins d'un pixel de large
        return None
    return sommets


def rasteriser(masque: np.ndarray, polygone_px: list, valeur: int) -> None:
    """Remplit dans `masque` les pixels dont le centre est dans le polygone (coordonnées en pixels, un pixel
    couvrant [i, i+1[ ). Le rendu et le validateur passent tous deux par ici, donc comptent pareil.

    cv2.fillPoly colorie aussi les pixels de la frontière (un rectangle de w × h pixels en remplit
    (w+1) × (h+1)) : on rentre d'abord les côtés d'un demi-pixel, puis on décale d'un demi-pixel.
    """
    # Arrondi au centième, comme les polygones écrits dans annotations.json : le rendu et la relecture
    # partent ainsi des mêmes nombres (339.5 et 339.4999999 ne donnent pas la même rangée).
    poly = [(round(float(u), 2), round(float(v), 2)) for u, v in polygone_px]
    rentre = _retrait(poly, 0.5)
    if rentre is None:  # trop mince : au moins une rangée de pixels, comme fillPoly le fait
        pts = [[math.floor(u + 0.5 + 1e-6), math.floor(v + 0.5 + 1e-6)] for u, v in poly]
    else:  # (u - 0.5) + 0.5 : la partie entière, avec une marge contre les erreurs d'arrondi
        pts = [[math.floor(u + 1e-6), math.floor(v + 1e-6)] for u, v in rentre]
    cv2.fillPoly(masque, [np.array(pts, np.int32)], int(valeur))
