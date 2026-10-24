"""Doublons et plans trop semblables.

Deux contrôles :

- le doublon exact : deux logements dont la géométrie est identique à une symétrie près
  (les 8 rotations/retournements) ont la même « empreinte » (un condensé SHA-256 de leurs
  pièces, murs et ouvertures normalisés) ;
- la ressemblance : une « signature » résume chaque logement (type, forme, nombre de pièces,
  surfaces triées, dimensions du cadre, graphe des voisinages) ; une distance entre signatures
  dit si deux plans se ressemblent trop (même programme, mêmes proportions à quelques pour cent).

Les variantes graphiques d'un même logement partagent sa graine : elles ne sont jamais comparées
entre elles, elles restent ensemble (voir exportateur.repartir).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from moteur.generateur.logements import LogementGenere, Niveau, Rect

SEUIL_RESSEMBLANCE = 0.06  # distance en dessous de laquelle deux plans sont « trop semblables »


def _normaliser(niveau: Niveau, n: int) -> list:
    """Les rectangles du niveau après la symétrie n (8 possibilités), ramenés au coin (0, 0), triés."""
    cadre = niveau.cadre
    w, h = cadre.largeur, cadre.hauteur
    echange, mx, my = bool(n & 1), bool(n & 2), bool(n & 4)

    def f(r: Rect) -> tuple:
        x0, y0, x1, y1 = r.x0 - cadre.x0, r.y0 - cadre.y0, r.x1 - cadre.x0, r.y1 - cadre.y0
        if echange:
            x0, y0, x1, y1 = y0, x0, y1, x1
        ww, hh = (h, w) if echange else (w, h)
        if mx:
            x0, x1 = ww - x1, ww - x0
        if my:
            y0, y1 = hh - y1, hh - y0
        return (x0, y0, x1, y1)

    from moteur.generateur.annotations import rect_de_l_ouverture, rect_du_mur
    pieces = sorted((f(p.rect), p.sorte) for p in niveau.pieces)
    murs = sorted(f(rect_du_mur(m)) for m in niveau.murs)
    ouv = sorted((f(rect_de_l_ouverture(o)), o.type) for o in niveau.ouvertures)
    return [pieces, murs, ouv]


def empreinte(log: LogementGenere) -> str:
    """Le condensé de la géométrie, identique pour deux logements égaux à une symétrie près."""
    candidats = []
    for n in range(8):
        candidats.append(json.dumps([_normaliser(niv, n) for niv in log.niveaux], separators=(",", ":")))
    canonique = min(candidats)  # la même pour toutes les orientations du même logement
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()[:16]


@dataclass
class Signature:
    type: str
    forme: str
    duplex: bool
    nb_pieces: int
    surface: float
    allongement: float  # grand côté / petit côté du cadre
    surfaces: list[float]  # surfaces des pièces, triées, en part de la surface totale
    degres: list[int]  # nombre de voisins (par une porte) de chaque pièce, trié
    types: list[str]  # sortes de pièces, triées

    def en_dict(self) -> dict:
        return self.__dict__


def signature(log: LogementGenere, geometrie: dict) -> Signature:
    cadre = log.niveaux[0].cadre
    petit, grand = sorted((cadre.largeur, cadre.hauteur))
    total = sum(p.rect.surface for p in log.pieces)
    degres: dict[str, int] = {p.id: 0 for p in log.pieces}
    for n in geometrie["niveaux"]:
        for c in n["connexions"]:
            for pid in c["pieces"]:
                if pid in degres:
                    degres[pid] += 1
    return Signature(
        type=log.type, forme=log.forme, duplex=log.duplex, nb_pieces=len(log.pieces), surface=log.surface,
        allongement=round(grand / petit, 3),
        surfaces=sorted(round(p.rect.surface / total, 4) for p in log.pieces),
        degres=sorted(degres.values()),
        types=sorted(p.sorte for p in log.pieces),
    )


def distance(a: dict, b: dict) -> float:
    """0 = même programme et mêmes proportions ; grand = très différents. Infini si les familles diffèrent."""
    if (a["type"], a["forme"], a["duplex"], a["nb_pieces"]) != (b["type"], b["forme"], b["duplex"], b["nb_pieces"]):
        return float("inf")
    if a["types"] != b["types"]:
        return float("inf")
    d_surf = sum(abs(x - y) for x, y in zip(a["surfaces"], b["surfaces"]))  # somme des écarts de parts (≤ 2)
    d_taille = abs(a["surface"] - b["surface"]) / max(a["surface"], b["surface"])
    d_forme = abs(a["allongement"] - b["allongement"]) / max(a["allongement"], b["allongement"])
    d_degres = sum(abs(x - y) for x, y in zip(a["degres"], b["degres"])) / (2 * max(1, a["nb_pieces"]))
    return round(d_surf + d_taille + d_forme + d_degres, 4)


def chercher(entrees: list[dict], seuil: float = SEUIL_RESSEMBLANCE) -> dict:
    """Parmi des entrées {id, empreinte, signature}, les doublons exacts et les paires trop semblables.

    Les paires ne sont cherchées que dans une même famille (type, forme, duplex, nombre de pièces),
    donc le coût reste raisonnable pour des dizaines de milliers de plans.
    """
    par_empreinte: dict[str, list[str]] = {}
    for e in entrees:
        par_empreinte.setdefault(e["empreinte"], []).append(e["id"])
    doublons = [ids for ids in par_empreinte.values() if len(ids) > 1]
    familles: dict[tuple, list[dict]] = {}
    for e in entrees:
        s = e["signature"]
        familles.setdefault((s["type"], s["forme"], s["duplex"], s["nb_pieces"], tuple(s["types"])), []).append(e)
    semblables = []
    for groupe in familles.values():
        for i, a in enumerate(groupe):
            for b in groupe[i + 1:]:
                d = distance(a["signature"], b["signature"])
                if d < seuil:
                    semblables.append({"ids": [a["id"], b["id"]], "distance": d})
    return {
        "nombre": len(entrees), "doublons_exacts": doublons, "trop_semblables": semblables,
        "seuil": seuil, "familles": {" ".join(map(str, k[:4])): len(v) for k, v in familles.items()},
    }
