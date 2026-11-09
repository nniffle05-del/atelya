"""Le décor proposé par Atelya : coussins, vases, lampes de chevet, plantes, tableaux (B4, 09/11/2026).

Pourquoi : une pièce meublée sans aucun objet « fait maquette » ; sur une photo d'annonce, il y a toujours des coussins sur le
canapé, un vase sur la table, une plante dans un coin. Atelya ajoute donc un décor PLAUSIBLE autour des grands meubles déjà posés.
Chaque objet est marqué statut « ajoute » et source « décor proposé par Atelya » : rien n'est présenté comme vu sur une photo, et
tout se retire ou se change à l'écran de vérification (règle NT n° 19 : le type de pièce n'impose rien ; ici, ce sont les meubles
présents qui appellent leur décor).

Règles (hasard fixé par une graine : le même logement donne toujours le même décor) :
- canapé : 2 à 4 coussins posés sur l'assise, contre le dossier ; lit : 2 coussins contre la tête de lit ;
- table basse, table de repas : un vase au milieu ; table de chevet : une lampe à poser ;
- tableau au-dessus d'un canapé ou d'un lit s'il n'y en a pas déjà un à moins d'un mètre ;
- une plante dans un coin libre des pièces de plus de 9 m², une fois sur deux.
"""
from __future__ import annotations

import math
import random

ASSISE_CANAPE = 0.42  # hauteur de l'assise (m)
SURFACE_PLANTE_M2 = 9.0


def _local(m: dict, dx: float, dy: float) -> list[float]:
    """Point du sol à (dx le long de la largeur, dy vers l'AVANT du meuble) depuis son milieu."""
    a = math.radians(m.get("face", 0.0))
    av = (math.cos(a), math.sin(a))
    cote = (-math.sin(a), math.cos(a))
    x, y = m["position"]
    return [round(x + dx * cote[0] + dy * av[0], 3), round(y + dx * cote[1] + dy * av[1], 3)]


def _objet(ident, categorie, piece, position, face, dimensions, altitude, couleur=None):
    o = {"id": ident, "categorie": categorie, "piece": piece, "position": position, "face": round(face, 1),
         "dimensions": [round(d, 3) for d in dimensions], "altitude": round(altitude, 3), "statut": "ajoute",
         "source": "décor proposé par Atelya", "confiance": 0.5}
    if couleur:
        o["couleur"] = list(couleur)
    return o


def _aire(contour) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]))) / 2


def decorer(logement: dict, graine: int = 1) -> list[dict]:
    """Les objets de décor à ajouter au logement (les meubles déjà présents ne sont pas changés)."""
    alea = random.Random(graine)
    meubles = logement.get("meubles", [])
    hsp = logement["hauteur_sous_plafond"]
    deja = {m["id"] for m in meubles}
    sortie = []

    def ident(base):
        k = 1
        while f"{base}_{k}" in deja:
            k += 1
        deja.add(f"{base}_{k}")
        return f"{base}_{k}"

    tableaux = [m for m in meubles if m["categorie"] == "tableau"]
    palette = [(200, 190, 175), (120, 140, 160), (180, 120, 90), (90, 110, 90), (230, 225, 215), (60, 70, 90)]
    for m in meubles:
        l, p, h = m["dimensions"]
        face = m.get("face", 0.0)
        piece = m.get("piece")
        if m["categorie"] == "canape":
            n = alea.choice([2, 3, 4])
            couleur = alea.choice(palette)
            for i in range(n):
                dx = (i - (n - 1) / 2) * min(0.5, (l - 0.5) / max(n, 1))
                sortie.append(_objet(ident("coussin"), "coussin", piece, _local(m, dx, -p / 2 + 0.22), face,
                                     (0.45, 0.15, 0.45), ASSISE_CANAPE, couleur if i % 2 == 0 else alea.choice(palette)))
        elif m["categorie"] == "lit":
            for dx in (-l / 4, l / 4):
                sortie.append(_objet(ident("coussin"), "coussin", piece, _local(m, dx, -p / 2 + 0.25), face,
                                     (0.6, 0.15, 0.4), min(0.5, h * 0.5), (235, 232, 225)))
        elif m["categorie"] in ("table_basse", "table"):
            sortie.append(_objet(ident("vase"), "vase", piece, _local(m, 0, 0), face, (0.16, 0.16, 0.28), h,
                                 alea.choice(palette)))
        elif m["categorie"] == "table_de_chevet":
            sortie.append(_objet(ident("lampe"), "lampe", piece, _local(m, 0, 0), face, (0.3, 0.3, 0.5), h))
        if m["categorie"] in ("canape", "lit") and m.get("altitude", 0) < 0.1:
            dos = _local(m, 0, -p / 2 - 0.02)  # contre le mur, derrière le meuble
            if not any(math.dist(t["position"], dos) < 1.0 for t in tableaux):
                largeur = min(1.4, l * 0.6)
                bas = max(h + 0.25, 1.2)
                if bas + 0.7 < hsp - 0.2:
                    t = _objet(ident("tableau"), "tableau", piece, dos, face, (largeur, 0.04, 0.7), bas, alea.choice(palette))
                    sortie.append(t)
                    tableaux.append(t)
    # une plante dans un coin libre (à plus de 70 cm de tout meuble) des pièces assez grandes
    for piece in logement.get("pieces", []):
        if _aire(piece["contour"]) < SURFACE_PLANTE_M2 or alea.random() < 0.5:
            continue
        coins = list(piece["contour"])
        alea.shuffle(coins)
        cx = sum(x for x, _ in piece["contour"]) / len(piece["contour"])
        cy = sum(y for _, y in piece["contour"]) / len(piece["contour"])
        for x, y in coins:
            d = math.hypot(cx - x, cy - y)
            if d < 1e-6:
                continue
            q = [round(x + (cx - x) / d * 0.45, 3), round(y + (cy - y) / d * 0.45, 3)]  # 45 cm vers l'intérieur
            if all(math.dist(q, m["position"]) > 0.7 + max(m["dimensions"][:2]) / 2 for m in meubles + sortie):
                sortie.append(_objet(ident("plante"), "plante", piece["id"], q, 0.0, (0.5, 0.5, 1.1), 0.0, (70, 110, 60)))
                break
    return sortie
