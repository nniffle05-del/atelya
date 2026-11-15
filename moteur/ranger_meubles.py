r"""RANGER LES MEUBLES trouvés sur les photos : jamais deux meubles au même endroit, jamais un meuble dans un mur.

Pourquoi (NT, 15/11/2026, premier film d'app-004 : « des meubles en trop, des chaises qui traversent des meubles ») : chaque
meuble est posé d'après les photos, à 30-50 cm près ; le même meuble vu de deux endroits peut être posé deux fois, un meuble
pris pour deux sortes (meuble télé = « rangement » ET « table ») est posé deux fois, et rien n'empêchait deux meubles d'occuper
la même place (deux chaises plantées dans la table). Ici, des règles de bon sens, appliquées par défaut après le repérage :

1. les meubles sont repris du plus sûr au moins sûr (les gros d'abord : lit, canapé, rangement, table, fauteuil, chaise ; à
   sorte égale, celui que le plus de photos ont vu) ;
2. un meuble doit tenir dans SA pièce : s'il dépasse dans un mur, il est ramené vers l'intérieur (au plus GLISSE_MAX), sinon retiré ;
3. deux meubles de la MÊME sorte qui se recouvrent : c'est le même meuble vu deux fois, le moins sûr est retiré (deux chaises
   ou deux fauteuils qui ne se recouvrent qu'un peu sont deux vrais voisins : le moins sûr est seulement écarté) ;
4. deux meubles de sortes différentes : si ces sortes se confondent (SE_CONFONDENT) et qu'ils se recouvrent beaucoup (plus de
   MEME_OBJET du plus petit), c'est un seul objet pris pour deux sortes, le moins sûr est retiré ; sinon le moins sûr est écarté
   jusqu'à ne plus toucher (au plus
   GLISSE_MAX) ; sans place libre, une table ou un rangement est rétréci (table d'appoint, chevet) ; sinon retiré ;
5. une chaise peut être glissée sous une table (jusqu'à SOUS_LA_TABLE de sa surface) ; au-delà elle est reculée et tournée vers
   la table.
Un tapis est à plat : il ne gêne personne et n'est gêné par personne. Les meubles déjà dans le logement (relevés, placés à
l'écran : statut autre que « estime » ou source sans « repérage ») ne sont jamais déplacés ni retirés ; les autres s'y adaptent.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
RANG = {"lit": 0, "canape": 1, "rangement": 2, "table": 3, "fauteuil": 4, "chaise": 5, "lampadaire": 6, "plante": 7}
A_PLAT = ("tapis",)
PLUSIEURS_COTE_A_COTE = ("chaise", "fauteuil")  # sortes dont deux voisins qui se touchent un peu sont deux vrais meubles
RETRECIT = ("table", "rangement")  # sortes qui existent en petit (table d'appoint, chevet) : rétrécies plutôt que retirées
PROFONDEUR_MIN = 0.4  # m
# sortes qu'un même objet peut recevoir à la fois (un meuble télé est vu « rangement » et « table », une méridienne « canapé » et
# « lit ») ; entre deux autres sortes, un fort recouvrement vient d'une place mal lue : le meuble est écarté, pas retiré
SE_CONFONDENT = {frozenset(p) for p in (("table", "rangement"), ("canape", "fauteuil"), ("canape", "lit"), ("chaise", "fauteuil"))}
TOUCHE = 0.04  # part de la surface du plus petit en dessous de laquelle deux meubles ne « se recouvrent » pas (place à 30 cm près)
MEME_OBJET = 0.5  # au-delà de cette part du plus petit : un seul objet pris pour deux
SOUS_LA_TABLE = 0.35  # part d'une chaise qui peut être sous une table
DANS_LA_PIECE = 0.9  # part d'un meuble qui doit être dans sa pièce (le reste : quelques centimètres dans l'épaisseur du mur)
GLISSE_MAX = 0.8  # m : déplacement maximal d'un meuble pour le dégager
PAS = 0.05  # m
GRILLE = 9  # points par côté pour mesurer un recouvrement


def _points(m: dict) -> np.ndarray:
    """Une grille de points couvrant l'emprise au sol du meuble (largeur en travers de sa face, profondeur le long)."""
    l, p = float(m["dimensions"][0]), float(m["dimensions"][1])
    a = math.radians(float(m.get("face", 0.0)))
    f, t = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    u = (np.arange(GRILLE) + 0.5) / GRILLE - 0.5
    g = np.stack(np.meshgrid(u, u), -1).reshape(-1, 2)
    return np.asarray(m["position"], float) + g[:, :1] * l * t + g[:, 1:] * p * f


def _dans_le_meuble(P: np.ndarray, m: dict) -> np.ndarray:
    l, p = float(m["dimensions"][0]), float(m["dimensions"][1])
    a = math.radians(float(m.get("face", 0.0)))
    d = P - np.asarray(m["position"], float)
    return (np.abs(d @ np.array([-math.sin(a), math.cos(a)])) <= l / 2) & (np.abs(d @ np.array([math.cos(a), math.sin(a)])) <= p / 2)


def recouvrement(a: dict, b: dict) -> float:
    """La part du PLUS PETIT des deux meubles couverte par l'autre (0 = ils ne se touchent pas, 1 = l'un est dans l'autre)."""
    aire = lambda m: float(m["dimensions"][0]) * float(m["dimensions"][1])
    petit, grand = (a, b) if aire(a) <= aire(b) else (b, a)
    return float(_dans_le_meuble(_points(petit), grand).mean())


def _dans_le_polygone(P: np.ndarray, contour) -> np.ndarray:
    c = np.asarray(contour, float)
    x, y = P[:, 0], P[:, 1]
    r = np.zeros(len(P), bool)
    for (x1, y1), (x2, y2) in zip(c, np.roll(c, -1, axis=0)):
        cond = (y1 > y) != (y2 > y)
        r ^= cond & (x < x1 + (y - y1) * (x2 - x1) / np.where(y2 != y1, y2 - y1, 1.0))
    return r


def part_dans_la_piece(m: dict, piece: dict | None) -> float:
    return 1.0 if piece is None else float(_dans_le_polygone(_points(m), piece["contour"]).mean())


def _score(m: dict) -> float:
    vues = 1
    s = str(m.get("source", ""))
    if "(" in s:
        try:
            vues = int(s.split("(")[1].split()[0])
        except ValueError:
            pass
    return vues * float(m.get("confiance", 0.5))


def _fixe(m: dict) -> bool:
    """Un meuble relevé ou placé par quelqu'un : on n'y touche pas."""
    return m.get("statut") != "estime" or "repérage" not in str(m.get("source", ""))


def _glisser(m: dict, direction: np.ndarray, accepte) -> dict | None:
    """Le meuble déplacé LE MOINS POSSIBLE jusqu'à ce que `accepte(meuble)` soit vrai : de proche en proche, d'abord dans
    `direction`, puis dans les directions voisines (8 en tout) ; None si rien ne convient à moins de GLISSE_MAX."""
    n = float(np.linalg.norm(direction))
    a0 = math.atan2(direction[1], direction[0]) if n > 1e-9 else 0.0
    angles = [a0 + math.radians(d) for d in (0, 45, -45, 90, -90, 135, -135, 180)]
    for k in range(1, int(GLISSE_MAX / PAS) + 1):
        for a in angles:
            essai = {**m, "position": [round(float(m["position"][0] + math.cos(a) * PAS * k), 3),
                                       round(float(m["position"][1] + math.sin(a) * PAS * k), 3)]}
            if accepte(essai):
                return essai
    return None


def ranger(meubles: list[dict], logement: dict, journal=None) -> tuple[list[dict], list[dict]]:
    """Les meubles rangés (ordre d'origine gardé) et la liste de ce qui a été fait : {"id", "action", "raison"}."""
    pieces = {p["id"]: p for p in logement.get("pieces", [])}
    actions: list[dict] = []
    ordre = sorted(range(len(meubles)), key=lambda i: (not _fixe(meubles[i]), RANG.get(meubles[i]["categorie"], 9), -_score(meubles[i])))
    gardes: dict[int, dict] = {}

    def gene(m: dict, sauf: int | None = None) -> tuple[int, float] | None:
        """Le meuble gardé que `m` recouvre le plus (au-delà de ce qui est permis), et de combien."""
        pire = None
        for j, k in gardes.items():
            if j == sauf or k["categorie"] in A_PLAT:
                continue
            r = recouvrement(m, k)
            permis = SOUS_LA_TABLE if {m["categorie"], k["categorie"]} == {"chaise", "table"} else TOUCHE
            if r > permis and (pire is None or r > pire[1]):
                pire = (j, r)
        return pire

    def note(m: dict, action: str, raison: str) -> None:
        actions.append({"id": m["id"], "categorie": m["categorie"], "action": action, "raison": raison})
        if journal:
            journal(f"  meubles : {m['categorie']} {m['id']} {action} ({raison})")

    for i in ordre:
        m = dict(meubles[i])
        if _fixe(m) or m["categorie"] in A_PLAT:
            gardes[i] = m
            continue
        piece = pieces.get(m.get("piece"))
        bien_place = lambda e: part_dans_la_piece(e, piece) >= DANS_LA_PIECE and gene(e) is None
        if piece is not None and part_dans_la_piece(m, piece) < DANS_LA_PIECE:  # règle 2 : il dépasse dans un mur
            milieu = np.asarray(piece["contour"], float).mean(0) - np.asarray(m["position"], float)
            dedans = _glisser(m, milieu, lambda e: part_dans_la_piece(e, piece) >= DANS_LA_PIECE)
            if dedans is None:
                note(m, "retiré", "il ne tient pas dans sa pièce")
                continue
            note(m, "déplacé", "il dépassait dans un mur")
            m = dedans
        g = gene(m)
        if g is not None:
            autre = gardes[g[0]]
            petits = m["categorie"] in PLUSIEURS_COTE_A_COTE  # des chaises voisines sont de VRAIES chaises voisines
            if autre["categorie"] == m["categorie"] and (g[1] > MEME_OBJET or not petits):  # règle 3
                note(m, "retiré", f"le même meuble que {autre['id']}, vu deux fois")
                continue
            chaise_et_table = {m["categorie"], autre["categorie"]} == {"chaise", "table"}
            if g[1] > MEME_OBJET and frozenset((m["categorie"], autre["categorie"])) in SE_CONFONDENT:  # règle 4
                note(m, "retiré", f"au même endroit que {autre['categorie']} {autre['id']}")
                continue
            ecart = np.asarray(m["position"], float) - np.asarray(autre["position"], float)
            if float(np.linalg.norm(ecart)) < 1e-6:
                a = math.radians(float(m.get("face", 0.0)))
                ecart = -np.array([math.cos(a), math.sin(a)])
            degage = _glisser(m, ecart, bien_place)
            if degage is None and m["categorie"] in RETRECIT:
                # pas de place pour un meuble de taille courante : c'en est un petit (table d'appoint, table de chevet)
                for part in (0.7, 0.5, 0.4):
                    l, pr = float(m["dimensions"][0]) * part, max(float(m["dimensions"][1]) * part, PROFONDEUR_MIN)
                    petit = {**m, "dimensions": [round(max(l, PROFONDEUR_MIN), 2), round(pr, 2), m["dimensions"][2]]}
                    degage = petit if bien_place(petit) else _glisser(petit, ecart, bien_place)
                    if degage is not None:
                        break
            if degage is None:
                note(m, "retiré", f"il traversait {autre['categorie']} {autre['id']}, sans place libre à côté")
                continue
            if m["categorie"] == "chaise" and autre["categorie"] == "table":  # règle 5 : la chaise regarde sa table
                vers = np.asarray(autre["position"], float) - np.asarray(degage["position"], float)
                degage["face"] = round(math.degrees(math.atan2(vers[1], vers[0])), 1)
                if not bien_place(degage):
                    degage["face"] = m.get("face", 0.0)
            note(m, "déplacé", f"il traversait {autre['categorie']} {autre['id']}")
            m = degage
        gardes[i] = m
    return [gardes[i] for i in range(len(meubles)) if i in gardes], actions


def chevauchements(meubles: list[dict]) -> list[tuple[str, str, float]]:
    """Les paires de meubles qui se recouvrent au-delà du permis (contrôle : doit être vide après `ranger`)."""
    solides = [m for m in meubles if m["categorie"] not in A_PLAT]
    sortie = []
    for i, a in enumerate(solides):
        for b in solides[i + 1:]:
            r = recouvrement(a, b)
            if r > (SOUS_LA_TABLE if {a["categorie"], b["categorie"]} == {"chaise", "table"} else TOUCHE):
                sortie.append((a["id"], b["id"], round(r, 2)))
    return sortie
