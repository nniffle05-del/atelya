"""Le correcteur : noter une lecture automatique en la comparant à la bonne réponse (étape 5a).

On lui donne deux logement.json : celui proposé par la lecture du plan, et le
« corrigé » (le vrai logement). Il retrouve chaque élément du corrigé dans la
lecture, par sa position (les identifiants ne comptent pas : la lecture
numérote M1, M2… à sa façon), puis il compte :

- les murs trouvés, ceux qui sont justes (bouts et épaisseur à quelques
  centimètres près), ceux qui manquent et ceux qui sont inventés ;
- l'écart des dimensions générales du logement, hors tout, c'est-à-dire
  d'une face extérieure à l'autre (une erreur d'échelle se voit ici) ;
- les portes et fenêtres trouvées, de bon type et de bonne largeur ;
- les pièces trouvées, de bonne surface et de bon nom ;
- la hauteur sous plafond.

Il en déduit le nombre de corrections qu'un humain aurait à faire dans la
page de vérification, et si le plan est « vert » (vérifiable en moins de
2 minutes). Ce seuil est une hypothèse, à régler sur de vrais essais.

Les deux logements doivent utiliser le même repère (origine au coin
intérieur sud-ouest), ce que fait la lecture automatique.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Tolérances, en mètres sauf mention contraire.
ANGLE_MAX = 3.0  # degrés : deux murs plus inclinés l'un par rapport à l'autre ne se correspondent pas
DISTANCE_AXE_MAX = 0.10  # un mur lu à plus de 10 cm de l'axe du vrai mur n'est pas le même mur
RECOUVREMENT_MIN = 0.5  # le mur lu doit couvrir au moins la moitié du vrai mur
BOUTS_MAX = 0.05  # un mur est juste si ses deux bouts sont à moins de 5 cm des vrais
EPAISSEUR_MAX = 0.02  # et son épaisseur à moins de 2 cm
OUVERTURE_DISTANCE_MAX = 0.30  # écart maximal entre les milieux d'une vraie ouverture et d'une ouverture lue
OUVERTURE_LARGEUR_MAX = 0.05
SURFACE_MAX = 0.02  # 2 % : le critère de l'étape 3
DIMENSIONS_MAX = 0.01  # 1 % sur la largeur et la profondeur du logement
HSP_MAX = 0.01
ANGLE_COMMUN = 0.03  # deux bouts de mur à moins de 3 cm l'un de l'autre forment un angle
CORRECTIONS_VERT_MAX = 3  # hypothèse : au plus 3 corrections tiennent en 2 minutes

Point = tuple[float, float]


@dataclass
class Note:
    """La note d'une lecture. Chaque erreur est aussi décrite en une phrase, dans `remarques`."""

    murs_vrais: int = 0
    murs_trouves: int = 0
    murs_justes: int = 0
    murs_inventes: int = 0
    ecart_dimensions: float = 0.0  # en fraction : 0,01 = 1 %
    ouvertures_vraies: int = 0
    ouvertures_trouvees: int = 0
    ouvertures_justes: int = 0  # bon type et bonne largeur
    ouvertures_inventees: int = 0
    pieces_vraies: int = 0
    pieces_trouvees: int = 0
    pieces_justes: int = 0  # bonne surface et bon nom
    pieces_inventees: int = 0
    hsp_juste: bool = True
    remarques: list[str] = field(default_factory=list)

    @property
    def corrections(self) -> int:
        """Le nombre de gestes de correction dans la page de vérification (une hypothèse simple : un par erreur)."""
        return (
            (self.murs_vrais - self.murs_justes) + self.murs_inventes
            + (self.ouvertures_vraies - self.ouvertures_justes) + self.ouvertures_inventees
            + (self.pieces_vraies - self.pieces_justes) + self.pieces_inventees
            + (0 if self.hsp_juste else 1)
        )

    @property
    def vert(self) -> bool:
        """Le plan passerait la vérification humaine en moins de 2 minutes."""
        return self.ecart_dimensions <= DIMENSIONS_MAX and self.corrections <= CORRECTIONS_VERT_MAX

    def en_dict(self) -> dict:
        return {**asdict(self), "corrections": self.corrections, "vert": self.vert}

    def en_texte(self) -> str:
        def part(n: int, total: int) -> str:
            return f"{n}/{total}" + (f" ({100 * n / total:.0f} %)" if total else "")

        lignes = [
            f"Murs justes        : {part(self.murs_justes, self.murs_vrais)}"
            f", trouvés {self.murs_trouves}, inventés {self.murs_inventes}",
            f"Dimensions         : écart {100 * self.ecart_dimensions:.2f} %".replace(".", ","),
            f"Portes et fenêtres : {part(self.ouvertures_justes, self.ouvertures_vraies)} justes"
            f", trouvées {self.ouvertures_trouvees}, inventées {self.ouvertures_inventees}",
            f"Pièces             : {part(self.pieces_justes, self.pieces_vraies)} justes"
            f", trouvées {self.pieces_trouvees}, inventées {self.pieces_inventees}",
            f"Hauteur s. plafond : {'juste' if self.hsp_juste else 'fausse'}",
            f"Corrections à faire: {self.corrections} → "
            + ("VERT (moins de 2 min de vérification)" if self.vert else "ROUGE (trop de corrections)"),
        ]
        lignes += [f"  - {r}" for r in self.remarques]
        return "\n".join(lignes)


def corriger(lu: dict, vrai: dict) -> Note:
    """Compare une lecture (contenu d'un logement.json) au corrigé, et renvoie la note."""
    note = Note()
    correspondance_murs = _noter_murs(lu["murs"], vrai["murs"], note)
    note.ecart_dimensions = _ecart_dimensions(lu["murs"], vrai["murs"])
    if note.ecart_dimensions > DIMENSIONS_MAX:
        note.remarques.append(f"dimensions générales fausses de {100 * note.ecart_dimensions:.1f} % : échelle à revoir")
    _noter_ouvertures(lu, vrai, correspondance_murs, note)
    _noter_pieces(lu.get("pieces", []), vrai.get("pieces", []), note)
    note.hsp_juste = abs(lu["hauteur_sous_plafond"] - vrai["hauteur_sous_plafond"]) <= HSP_MAX
    if not note.hsp_juste:
        note.remarques.append(
            f"hauteur sous plafond lue {lu['hauteur_sous_plafond']} m au lieu de {vrai['hauteur_sous_plafond']} m"
        )
    return note


# --- Murs ---------------------------------------------------------------


def _noter_murs(murs_lus: list[dict], murs_vrais: list[dict], note: Note) -> dict[str, str]:
    """Associe chaque vrai mur au mur lu qui lui ressemble le plus. Renvoie {id vrai: id lu}."""
    note.murs_vrais = len(murs_vrais)
    libres = list(murs_lus)
    correspondance: dict[str, str] = {}
    for v in murs_vrais:
        candidats = [m for m in libres if _meme_mur(m, v)]
        if not candidats:
            note.remarques.append(f"mur {v['id']} manquant")
            continue
        m = min(candidats, key=lambda c: _ecart_bouts(c, v))
        libres.remove(m)
        correspondance[v["id"]] = m["id"]
        note.murs_trouves += 1
        ecart, epaisseur = _ecart_bouts(m, v), abs(m["epaisseur"] - v["epaisseur"])
        if ecart <= BOUTS_MAX and epaisseur <= EPAISSEUR_MAX:
            note.murs_justes += 1
        else:
            note.remarques.append(
                f"mur {v['id']} trouvé mais imprécis (bouts à {100 * ecart:.0f} cm, "
                f"épaisseur à {100 * epaisseur:.0f} cm)"
            )
    note.murs_inventes = len(libres)
    for m in libres:
        note.remarques.append(f"mur {m['id']} inventé (de {_texte_point(m['debut'])} à {_texte_point(m['fin'])})")
    return correspondance


def _meme_mur(lu: dict, vrai: dict) -> bool:
    """Le mur lu est-il le même que le vrai : même direction, sur le même axe, et le couvrant assez ?"""
    (ax, ay), (bx, by) = vrai["debut"], vrai["fin"]
    longueur = math.dist((ax, ay), (bx, by))
    ux, uy = (bx - ax) / longueur, (by - ay) / longueur
    (cx, cy), (dx, dy) = lu["debut"], lu["fin"]
    longueur_lue = math.dist((cx, cy), (dx, dy))
    if longueur_lue == 0:
        return False
    cosinus = abs(((dx - cx) * ux + (dy - cy) * uy) / longueur_lue)
    if math.degrees(math.acos(min(1.0, cosinus))) > ANGLE_MAX:
        return False
    # Distance des deux bouts lus à l'axe du vrai mur (produit vectoriel).
    for px, py in ((cx, cy), (dx, dy)):
        if abs((px - ax) * uy - (py - ay) * ux) > DISTANCE_AXE_MAX:
            return False
    # Recouvrement le long du mur.
    t1 = (cx - ax) * ux + (cy - ay) * uy
    t2 = (dx - ax) * ux + (dy - ay) * uy
    commun = min(max(t1, t2), longueur) - max(min(t1, t2), 0.0)
    return commun >= RECOUVREMENT_MIN * longueur


def _ecart_bouts(lu: dict, vrai: dict) -> float:
    """Le plus grand écart entre les bouts lus et les vrais bouts (dans un sens ou dans l'autre)."""
    a, b = vrai["debut"], vrai["fin"]
    c, d = lu["debut"], lu["fin"]
    return min(max(math.dist(a, c), math.dist(b, d)), max(math.dist(a, d), math.dist(b, c)))


def _ecart_dimensions(murs_lus: list[dict], murs_vrais: list[dict]) -> float:
    """Écart relatif de la largeur et de la profondeur hors tout du logement (le plus grand des deux).

    Hors tout : d'une face extérieure à l'autre, et non d'un axe de mur à l'autre.
    Un même angle peut se dessiner de deux façons (le mur continue jusqu'au coin,
    ou un petit bout de mur vient le fermer) : leurs axes ne s'arrêtent pas au même
    endroit, mais leurs faces extérieures, si. C'est elles qu'on mesure sur place.
    """
    def cadre(murs: list[dict]) -> tuple[float, float]:
        rectangles = [_rectangle_du_mur(m, murs) for m in murs]
        return (max(r[2] for r in rectangles) - min(r[0] for r in rectangles),
                max(r[3] for r in rectangles) - min(r[1] for r in rectangles))

    (lx, ly), (vx, vy) = cadre(murs_lus), cadre(murs_vrais)
    return float(max(abs(lx - vx) / vx, abs(ly - vy) / vy))  # float : les coordonnées lues peuvent venir de numpy


def _rectangle_du_mur(mur: dict, murs: list[dict]) -> tuple[float, float, float, float]:
    """Le rectangle (x0, y0, x1, y1) occupé par le mur, rallongé dans les angles qu'il partage avec un autre mur.

    Dans un angle, les deux axes s'arrêtent au même point : chaque mur est rallongé
    de la demi-épaisseur de l'autre, pour aller jusqu'au coin extérieur.
    """
    (ax, ay), (bx, by) = mur["debut"], mur["fin"]
    longueur = math.dist((ax, ay), (bx, by))
    if longueur == 0:
        return ax, ay, ax, ay
    ux, uy = (bx - ax) / longueur, (by - ay) / longueur
    rallonges = [
        max((autre["epaisseur"] / 2 for autre in murs if autre is not mur
             and any(math.dist(bout, p) <= ANGLE_COMMUN for p in (autre["debut"], autre["fin"]))), default=0.0)
        for bout in (mur["debut"], mur["fin"])
    ]
    ax, ay = ax - ux * rallonges[0], ay - uy * rallonges[0]
    bx, by = bx + ux * rallonges[1], by + uy * rallonges[1]
    nx, ny = -uy * mur["epaisseur"] / 2, ux * mur["epaisseur"] / 2
    xs, ys = (ax + nx, ax - nx, bx + nx, bx - nx), (ay + ny, ay - ny, by + ny, by - ny)
    return min(xs), min(ys), max(xs), max(ys)


# --- Ouvertures ---------------------------------------------------------


def _milieu_ouverture(ouverture: dict, murs: dict[str, dict]) -> Point | None:
    mur = murs.get(ouverture["mur"])
    if mur is None:
        return None
    (ax, ay), (bx, by) = mur["debut"], mur["fin"]
    longueur = math.dist((ax, ay), (bx, by))
    t = (ouverture["position"] + ouverture["largeur"] / 2) / longueur
    return ax + t * (bx - ax), ay + t * (by - ay)


def _noter_ouvertures(lu: dict, vrai: dict, correspondance_murs: dict[str, str], note: Note) -> None:
    murs_lus = {m["id"]: m for m in lu["murs"]}
    murs_vrais = {m["id"]: m for m in vrai["murs"]}
    libres = [(o, _milieu_ouverture(o, murs_lus)) for o in lu.get("ouvertures", [])]
    vraies = vrai.get("ouvertures", [])
    note.ouvertures_vraies = len(vraies)
    for v in vraies:
        milieu = _milieu_ouverture(v, murs_vrais)
        candidats = [
            (o, p) for o, p in libres
            if p is not None and milieu is not None and math.dist(p, milieu) <= OUVERTURE_DISTANCE_MAX
            # Si le mur porteur a été retrouvé, l'ouverture lue doit être sur ce mur-là.
            and correspondance_murs.get(v["mur"], o["mur"]) == o["mur"]
        ]
        if not candidats:
            note.remarques.append(f"{_nom_ouverture(v['type'])} {v['id']} manquante")
            continue
        o, p = min(candidats, key=lambda c: math.dist(c[1], milieu))
        libres.remove((o, p))
        note.ouvertures_trouvees += 1
        fautes = []
        if o["type"] != v["type"]:
            fautes.append(f"lue comme {_nom_ouverture(o['type'])}")
        if abs(o["largeur"] - v["largeur"]) > OUVERTURE_LARGEUR_MAX:
            fautes.append(f"largeur {o['largeur']:.2f} m au lieu de {v['largeur']:.2f} m")
        if fautes:
            note.remarques.append(f"{_nom_ouverture(v['type'])} {v['id']} : " + ", ".join(fautes))
        else:
            note.ouvertures_justes += 1
    note.ouvertures_inventees = len(libres)
    for o, _ in libres:
        note.remarques.append(f"{_nom_ouverture(o['type'])} {o['id']} inventée (sur le mur lu {o['mur']})")


def _nom_ouverture(type_: str) -> str:
    return {"porte": "porte", "porte_fenetre": "porte-fenêtre", "fenetre": "fenêtre"}[type_]


# --- Pièces -------------------------------------------------------------


def _noter_pieces(pieces_lues: list[dict], pieces_vraies: list[dict], note: Note) -> None:
    note.pieces_vraies = len(pieces_vraies)
    libres = list(pieces_lues)
    for v in pieces_vraies:
        cv = _centre(v["contour"])
        # Même pièce : chacune contient le centre de l'autre.
        candidats = [p for p in libres if _dedans(_centre(p["contour"]), v["contour"]) and _dedans(cv, p["contour"])]
        if not candidats:
            note.remarques.append(f"pièce « {v['nom']} » manquante")
            continue
        p = min(candidats, key=lambda c: math.dist(_centre(c["contour"]), cv))
        libres.remove(p)
        note.pieces_trouvees += 1
        s_lue, s_vraie = _surface(p["contour"]), _surface(v["contour"])
        fautes = []
        if abs(s_lue - s_vraie) > SURFACE_MAX * s_vraie:
            fautes.append(f"{s_lue:.2f} m² au lieu de {s_vraie:.2f} m²".replace(".", ","))
        if _simplifier(p["nom"]) != _simplifier(v["nom"]):
            fautes.append(f"nommée « {p['nom']} »")
        if fautes:
            note.remarques.append(f"pièce « {v['nom']} » : " + ", ".join(fautes))
        else:
            note.pieces_justes += 1
    note.pieces_inventees = len(libres)
    for p in libres:
        note.remarques.append(f"pièce « {p['nom']} » inventée")


def _surface(contour: list[Point]) -> float:
    """Formule du lacet, comme dans logement.py."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def _centre(contour: list[Point]) -> Point:
    """Le centre de gravité de la surface (juste aussi pour une pièce en L)."""
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        k = x1 * y2 - x2 * y1
        a += k
        cx += (x1 + x2) * k
        cy += (y1 + y2) * k
    if a == 0:
        return sum(p[0] for p in contour) / len(contour), sum(p[1] for p in contour) / len(contour)
    return cx / (3 * a), cy / (3 * a)


def _dedans(point: Point, contour: list[Point]) -> bool:
    """Le point est-il dans le contour ? (on compte les bords traversés par une demi-droite)"""
    x, y = point
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def _simplifier(nom: str) -> str:
    """« Séjour + Cuisine » et « sejour + cuisine » sont le même nom."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("'", " ").split())


def _texte_point(p: Point) -> str:
    return f"({p[0]:.2f} ; {p[1]:.2f})".replace(".", ",")


def main() -> None:
    parser = argparse.ArgumentParser(description="Note une lecture automatique en la comparant au vrai logement.json.")
    parser.add_argument("lu", help="logement.json proposé par la lecture du plan")
    parser.add_argument("vrai", help="logement.json corrigé (la bonne réponse)")
    args = parser.parse_args()
    try:
        lu, vrai = (json.loads(Path(c).read_text(encoding="utf-8")) for c in (args.lu, args.vrai))
    except (OSError, json.JSONDecodeError) as erreur:
        sys.exit(f"Échec : {erreur}")
    print(corriger(lu, vrai).en_texte())


if __name__ == "__main__":
    main()
