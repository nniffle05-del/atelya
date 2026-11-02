"""Le validateur : un exemple n'est accepté que s'il passe des contrôles explicites.

Deux moments :

1. `valider_geometrie` sur le logement en mémoire, avant tout dessin : pièces sans
   chevauchement et dans l'enveloppe, murs cohérents, ouvertures dans leur mur sans se chevaucher,
   chaque porte entre deux pièces (ou une pièce et l'extérieur), logement connexe, surfaces
   cohérentes, tailles plausibles ;
2. `valider_dossier` sur les fichiers écrits : tout est là et lisible, les masques relus
   correspondent aux polygones des annotations (à la tolérance près), le modèle 3D a la même
   emprise de murs que la 2D.

Chaque règle a un nom, un seuil réglable (voir `Regles`) et produit soit une erreur (l'exemple
est rejeté) soit un avertissement (accepté, mais noté). Les configurations atypiques mais
géométriquement valides passent : une pièce sans fenêtre n'est qu'un avertissement, un WC de
0,9 m de large est accepté.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from moteur.generateur.annotations import CLASSES, pieces_le_long, rect_de_l_ouverture, rect_du_mur, rasteriser
from moteur.generateur.logements import LogementGenere, Niveau, Rect, contour_piece, surface_piece


@dataclass
class Regles:
    """Les seuils des contrôles. Tout est en mètres ou en pourcentage."""

    cote_min_piece: float = 0.5  # m : en dessous, une pièce n'est pas une pièce
    surface_min_piece: float = 0.4  # m²
    surface_max_piece: float = 80.0  # m²
    largeur_porte_min: float = 0.6
    largeur_porte_max: float = 1.3
    largeur_fenetre_max: float = 4.0
    ecart_surface_pct: float = 0.5  # % d'écart toléré entre la surface annoncée et le contour
    ecart_masque_pct: float = 6.0  # % d'écart toléré entre l'aire d'un polygone et son masque relu
    ecart_3d_pct: float = 3.0  # % d'écart toléré entre l'emprise des murs 2D et 3D
    pieces_de_vie_avec_fenetre: bool = True  # avertissement seulement
    exiger_connexite: bool = True

    @classmethod
    def charger(cls, chemin: str | Path | None) -> Regles:
        if chemin is None:
            return cls()
        return cls(**json.loads(Path(chemin).read_text(encoding="utf-8")))


@dataclass
class Verdict:
    erreurs: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def accepte(self) -> bool:
        return not self.erreurs

    def en_dict(self) -> dict:
        return {"accepte": self.accepte, "erreurs": self.erreurs, "avertissements": self.avertissements}


def _chevauche(a: Rect, b: Rect) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def _dans_contour(r: Rect, coins: list[tuple[int, int]]) -> bool:
    """Le rectangle est-il dans le polygone rectiligne ? On teste son centre et ses quatre coins (un peu rentrés)."""
    pts = [((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2), (r.x0 + 1, r.y0 + 1), (r.x1 - 1, r.y0 + 1), (r.x1 - 1, r.y1 - 1), (r.x0 + 1, r.y1 - 1)]
    return all(_point_dans(p, coins) for p in pts)


def _point_dans(p: tuple[float, float], coins: list[tuple[int, int]]) -> bool:
    x, y = p
    dedans = False
    for (x1, y1), (x2, y2) in zip(coins, coins[1:] + coins[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def valider_niveau(log: LogementGenere, niveau: Niveau, regles: Regles, v: Verdict) -> None:
    n = f"niveau {niveau.index}"
    pieces = niveau.pieces
    # Pièces : tailles, chevauchements, dans l'enveloppe.
    for p in pieces:
        r = p.rect
        if r.largeur <= 0 or r.hauteur <= 0:
            v.erreurs.append(f"{n} : pièce {p.id} de taille nulle")
            continue
        if min(r.largeur, r.hauteur) / 1000 < regles.cote_min_piece:
            v.erreurs.append(f"{n} : pièce {p.id} trop étroite ({min(r.largeur, r.hauteur) / 1000:.2f} m)")
        s = surface_piece(p) / 1e6
        if not regles.surface_min_piece <= s <= regles.surface_max_piece:
            v.erreurs.append(f"{n} : pièce {p.id} de surface invraisemblable ({s:.2f} m²)")
        if p.contour:  # A3 : angle coupé : les sommets du contour, un peu rentrés vers le centre
            cx = sum(x for x, _ in p.contour) / len(p.contour)
            cy = sum(y for _, y in p.contour) / len(p.contour)
            pts = [(x + (cx - x) * 0.01, y + (cy - y) * 0.01) for x, y in contour_piece(p)]
            if not all(_point_dans(q, niveau.coins) for q in pts):
                v.erreurs.append(f"{n} : pièce {p.id} hors de l'enveloppe")
        elif not _dans_contour(r, niveau.coins):
            v.erreurs.append(f"{n} : pièce {p.id} hors de l'enveloppe")
    for i, a in enumerate(pieces):
        for b in pieces[i + 1:]:
            if _chevauche(a.rect, b.rect):
                v.erreurs.append(f"{n} : les pièces {a.id} et {b.id} se chevauchent")
    # Murs : longueur positive, pas de chevauchement entre murs intérieurs, pas de mur qui traverse une pièce.
    for m in niveau.murs:
        if m.fin - m.debut <= 0:
            v.erreurs.append(f"{n} : mur {m.id} de longueur nulle")
        if m.epaisseur <= 0:
            v.erreurs.append(f"{n} : mur {m.id} sans épaisseur")
        rm = rect_du_mur(m)
        for p in pieces:
            if _chevauche(rm, p.rect):
                v.erreurs.append(f"{n} : le mur {m.id} traverse la pièce {p.id}")
    interieurs = [m for m in niveau.murs if not m.dehors]
    for i, a in enumerate(interieurs):
        for b in interieurs[i + 1:]:
            if _chevauche(rect_du_mur(a), rect_du_mur(b)):
                v.erreurs.append(f"{n} : les murs {a.id} et {b.id} se chevauchent")
    # Ouvertures : dans le mur, sans chevauchement, tailles plausibles, entre deux espaces.
    par_mur: dict[str, list] = {}
    for o in niveau.ouvertures:
        m = o.mur
        if o.u0 < m.debut - 1e-6 or o.u1 > m.fin + 1e-6 or o.u1 <= o.u0:
            v.erreurs.append(f"{n} : l'ouverture {o.id} sort du mur {m.id}")
        largeur = (o.u1 - o.u0) / 1000
        if o.type == "porte" and not regles.largeur_porte_min <= largeur <= regles.largeur_porte_max:
            v.erreurs.append(f"{n} : porte {o.id} de largeur invraisemblable ({largeur:.2f} m)")
        if o.type != "porte" and largeur > regles.largeur_fenetre_max:
            v.erreurs.append(f"{n} : fenêtre {o.id} trop large ({largeur:.2f} m)")
        if o.allege + o.hauteur > niveau.hsp + 1e-6:
            v.erreurs.append(f"{n} : l'ouverture {o.id} dépasse le plafond")
        par_mur.setdefault(m.id, []).append(o)
        moins, plus = pieces_le_long(m, o.u0, o.u1, pieces)
        if o.type == "porte":
            if o.sous_type == "porte_entree":
                if (moins is None) == (plus is None):
                    v.erreurs.append(f"{n} : la porte d'entrée {o.id} ne relie pas une pièce à l'extérieur")
            elif moins is None or plus is None:
                v.erreurs.append(f"{n} : la porte {o.id} ne relie pas deux pièces")
        else:
            if (moins is None) == (plus is None):
                v.erreurs.append(f"{n} : la fenêtre {o.id} n'est pas entre une pièce et l'extérieur")
    for mid, lst in par_mur.items():
        lst.sort(key=lambda o: o.u0)
        for a, b in zip(lst, lst[1:]):
            if b.u0 < a.u1:
                v.erreurs.append(f"{n} : les ouvertures {a.id} et {b.id} se chevauchent sur le mur {mid}")
    # Surfaces : la somme des pièces + les murs intérieurs ≈ l'enveloppe.
    emprise = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(niveau.coins, niveau.coins[1:] + niveau.coins[:1]))) / 2
    habitable = sum(surface_piece(p) for p in pieces)
    murs_int = sum(rect_du_mur(m).surface for m in interieurs)
    if abs(emprise - habitable - murs_int) / emprise * 100 > regles.ecart_surface_pct:
        v.erreurs.append(f"{n} : surfaces incohérentes (enveloppe {emprise / 1e6:.2f}, pièces {habitable / 1e6:.2f}, "
                         f"murs {murs_int / 1e6:.2f} m²)")
    # Fenêtres des pièces de vie : avertissement.
    if regles.pieces_de_vie_avec_fenetre:
        for p in pieces:
            if p.sorte in ("sejour", "principale", "chambre", "cuisine", "bureau"):
                if not any(o.type != "porte" and p.id in pieces_le_long(o.mur, o.u0, o.u1, pieces) for o in niveau.ouvertures):
                    v.avertissements.append(f"{n} : {p.id} n'a pas de fenêtre")


def valider_geometrie(log: LogementGenere, geometrie: dict, regles: Regles | None = None) -> Verdict:
    """Tous les contrôles sur la géométrie (avant le dessin)."""
    regles = regles or Regles()
    v = Verdict()
    for niveau in log.niveaux:
        valider_niveau(log, niveau, regles, v)
    if regles.exiger_connexite and not geometrie["connectivite"]["connexe"]:
        v.erreurs.append("logement non connexe : " + ", ".join(geometrie["connectivite"]["non_atteintes"]))
    if log.duplex:
        escaliers = [p.rect for p in log.pieces if p.sorte == "escalier"]
        if len(escaliers) != 2 or escaliers[0] != escaliers[1]:
            v.erreurs.append("duplex : l'escalier n'est pas au même endroit aux deux niveaux")
    ids = [p.id for p in log.pieces] + [m.id for m in log.murs] + [o.id for o in log.ouvertures]
    if len(ids) != len(set(ids)):
        v.erreurs.append("identifiants en double")
    return v


# ---------------------------------------------------------------- les fichiers écrits


def _aire(poly: list[list[float]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))) / 2


def _centre_gravite(poly: list[list[float]]) -> tuple[float, float]:
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        k = x1 * y2 - x2 * y1
        a += k; cx += (x1 + x2) * k; cy += (y1 + y2) * k
    if abs(a) < 1e-9:
        return sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly)
    return cx / (3 * a), cy / (3 * a)


def chemin_du_plan(dn: Path) -> Path | None:
    """Le fichier du plan d'un niveau : plan.png, ou plan.jpg pour les plans abîmés."""
    for nom in ("plan.png", "plan.jpg"):
        if (dn / nom).exists():
            return dn / nom
    return None


def _pixels(poly: list[list[float]], taille: tuple[int, int], sauf: np.ndarray | None = None) -> int:
    """Le nombre de pixels que remplit ce polygone, tramé comme le fait le rendu, hors ceux de `sauf`."""
    m = np.zeros(taille, np.uint8)
    rasteriser(m, poly, 1)
    if sauf is not None:
        m[sauf > 0] = 0
    return int(m.sum())


def valider_dossier(dossier: Path, regles: Regles | None = None, v: Verdict | None = None) -> Verdict:
    """Relit les fichiers d'un exemple et vérifie qu'ils se correspondent."""
    regles = regles or Regles()
    v = v or Verdict()
    dossier = Path(dossier)
    geo_chemin = dossier / "geometrie.json"
    if not geo_chemin.exists():
        v.erreurs.append("geometrie.json manquant")
        return v
    try:
        geo = json.loads(geo_chemin.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        v.erreurs.append(f"geometrie.json illisible : {e}")
        return v
    for niveau in geo["niveaux"]:
        dn = dossier / f"niveau_{niveau['index']}"
        ann_chemin = dn / "annotations.json"
        if not ann_chemin.exists():
            v.erreurs.append(f"{dn.name}/annotations.json manquant")
            continue
        ann = json.loads(ann_chemin.read_text(encoding="utf-8"))
        for nom in ("masque_semantique.png", "masque_pieces.png", "masque_elements.png", "contours.png", "hauteur.png"):
            if not (dn / nom).exists():
                v.erreurs.append(f"{dn.name}/{nom} manquant")
        plan_chemin = chemin_du_plan(dn)
        if plan_chemin is None:
            v.erreurs.append(f"{dn.name}/plan.png (ou .jpg) manquant")
        if v.erreurs:
            continue
        plan = cv2.imread(str(plan_chemin), cv2.IMREAD_UNCHANGED)
        sem = cv2.imread(str(dn / "masque_semantique.png"), cv2.IMREAD_UNCHANGED)
        pieces_m = cv2.imread(str(dn / "masque_pieces.png"), cv2.IMREAD_UNCHANGED)
        elements = cv2.imread(str(dn / "masque_elements.png"), cv2.IMREAD_UNCHANGED)
        hauteur = cv2.imread(str(dn / "hauteur.png"), cv2.IMREAD_UNCHANGED)
        if any(x is None for x in (plan, sem, pieces_m, elements, hauteur)):
            v.erreurs.append(f"{dn.name} : une image est corrompue")
            continue
        taille = (ann["image"]["hauteur"], ann["image"]["largeur"])
        for nom, img in (("plan", plan), ("masque_semantique", sem), ("masque_pieces", pieces_m), ("masque_elements", elements), ("hauteur", hauteur)):
            if img.shape[:2] != taille:
                v.erreurs.append(f"{dn.name}/{nom}.png : taille {img.shape[:2]} au lieu de {taille}")
        if hauteur.dtype != np.uint16:
            v.erreurs.append(f"{dn.name}/hauteur.png n'est pas en 16 bits")
        # Les murs et ouvertures, retramés : ils l'emportent sur le bord des pièces qu'ils touchent.
        occupe = np.zeros(taille, np.uint8)
        for e in ann["murs"] + ann["ouvertures"]:
            rasteriser(occupe, e["polygone_px"], 1)
        # Chaque pièce : son polygone en pixels, retramé (sans les murs), ≈ le nombre de pixels de son identifiant.
        for p in ann["pieces"]:
            attendu = _pixels(p["polygone_px"], taille, occupe)
            compte = int(np.count_nonzero(pieces_m == p["valeur_masque"]))
            if attendu > 0 and abs(compte - attendu) / attendu * 100 > regles.ecart_masque_pct:
                v.erreurs.append(f"{dn.name} : masque de la pièce {p['id']} ({compte} px) ≠ annotation ({attendu:.0f} px)")
            # Le masque sémantique dit la même classe au centre de la pièce.
            if len(p["polygone_px"]) == 4:
                cx = int(sum(q[0] for q in p["polygone_px"]) / 4)
                cy = int(sum(q[1] for q in p["polygone_px"]) / 4)
            else:  # A3 : pièce à angle coupé : le centre de gravité de la surface
                cx, cy = (int(v) for v in _centre_gravite(p["polygone_px"]))
            if 0 <= cy < sem.shape[0] and 0 <= cx < sem.shape[1] and sem[cy, cx] != p["classe"]:
                if not (niveau["index"] > 0 and p["classe"] == CLASSES["escalier"]):
                    v.erreurs.append(f"{dn.name} : classe {sem[cy, cx]} au centre de {p['id']} (attendu {p['classe']})")
        for o in ann["ouvertures"]:
            attendu = _pixels(o["polygone_px"], taille)
            compte = int(np.count_nonzero(elements == o["valeur_masque"]))
            # Une ouverture est mince (quelques pixels) : la tolérance est plus large, en pixels et en pour cent.
            if attendu > 0 and abs(compte - attendu) > max(12, attendu * max(regles.ecart_masque_pct, 15) / 100):
                v.erreurs.append(f"{dn.name} : masque de l'ouverture {o['id']} ({compte} px) ≠ annotation ({attendu:.0f} px)")
        # L'aire totale des murs (sémantique) ≈ l'union des polygones de murs (redessinée ici, sans les ouvertures).
        if True:
            union = np.zeros(taille, np.uint8)
            for m in ann["murs"]:
                rasteriser(union, m["polygone_px"], 1)
            for o in ann["ouvertures"]:
                rasteriser(union, o["polygone_px"], 0)
            attendu = int(union.sum())
            compte = int(np.count_nonzero(sem == CLASSES["mur"]))
            if abs(compte - attendu) / max(attendu, 1) * 100 > regles.ecart_masque_pct:
                v.erreurs.append(f"{dn.name} : masque des murs ({compte} px) ≠ polygones ({attendu} px)")
    # 3D, si elle a été produite : même emprise de murs que la 2D.
    glb = dossier / "modele.glb"
    if glb.exists():
        from moteur.generateur.modele3d import lire_glb
        try:
            gltf = lire_glb(glb)
        except Exception as e:  # noqa: BLE001
            v.erreurs.append(f"modele.glb corrompu : {e}")
        else:
            noms = {n["name"] for n in gltf["nodes"]}
            murs_attendus = {m["id"] for n in geo["niveaux"] for m in n["murs"]}
            if not murs_attendus <= noms:
                v.erreurs.append(f"modele.glb : murs absents de la 3D : {sorted(murs_attendus - noms)[:5]}")
        constr = dossier / "construction.json"
        if constr.exists():
            from moteur.generateur.modele3d import emprise_des_murs
            briques = json.loads(constr.read_text(encoding="utf-8"))["briques"]
            n0 = geo["niveaux"][0]
            attendu = sum(_aire(m["polygone"]) for m in n0["murs"]) - sum(_aire(o["polygone"]) for o in n0["ouvertures"]
                                                                        if o["type"] != "fenetre" or o["allege"] == 0)
            # Les murs extérieurs se recouvrent aux angles dans la 2D (chaque mur couvre l'angle) : on retire ces carrés.
            ext = [m for m in n0["murs"] if m["exterieur"]]
            attendu -= len(ext) * (ext[0]["epaisseur"] ** 2) if ext else 0
            obtenu = emprise_des_murs(briques)
            if attendu > 0 and abs(obtenu - attendu) / attendu * 100 > regles.ecart_3d_pct:
                v.avertissements.append(f"emprise des murs 2D ({attendu:.2f} m²) et 3D ({obtenu:.2f} m²) différentes")
    return v
