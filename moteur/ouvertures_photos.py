r"""CE QUE LE PLAN NE DIT PAS, LU SUR LES PHOTOS : une baie descend-elle jusqu'au sol ? (15/11/2026, examen app-004)

Pourquoi (NT : « le plan ne veut pas tout dire […] il faudrait comprendre via les photos ») : un plan d'annonce dessine toutes
les baies de la même façon ; la lecture en fait des fenêtres sur allège (1,25 m de haut, à 95 cm du sol). Sur les photos
d'app-004, trois baies sur quatre sont de hautes fenêtres qui descendent jusqu'au sol, avec garde-corps : le film montrait de
petites fenêtres carrées, moins de lumière, et la vue par les fenêtres tombait à côté.

Comment : pour placer les photos, Atelya mesure déjà, direction par direction, si le creux vu dans un mur descend jusqu'au sol
(moteur.caler_photos.profil : MoGe-2 donne chaque point de la photo en mètres ; « creux » = plus loin que le mur ; « jusqu'au
sol » = la bande de 15 à 80 cm au-dessus du sol est elle aussi en creux ; un meuble devant = caché, on ne dit rien). Ici, chaque
direction de chaque photo placée est suivie jusqu'à la baie du plan qu'elle touche en premier, et vote pour elle : « jusqu'au
sol » ou « sur allège ». Une baie qui reçoit assez de votes prend la sorte que les photos montrent.

Rien n'est inventé : une baie qu'aucune photo ne montre, ou dont le bas est caché, reste comme le plan l'a lue. Le statut passe à
« estime », la source dit « photos ». Les portes intérieures ne sont pas concernées.
"""
from __future__ import annotations

import copy
import math

import numpy as np

VERSION = "0.1.0"
VOTES_MIN = 8  # directions (degrés) qui doivent avoir vu le bas de la baie, toutes photos confondues
PART_MIN = 0.6  # part des votes qu'il faut pour changer la sorte lue sur le plan
ECART_MUR_M = 0.6  # la baie touchée doit être là où la photo voit son mur, à 60 cm près
HAUT_PORTE_FENETRE = 2.15  # m (comme moteur.traduire_claude)
ALLEGE_FENETRE, HAUTEUR_FENETRE = 0.95, 1.25  # m


def _baies(logement: dict) -> list[dict]:
    """Les fenêtres et portes-fenêtres du logement, avec leurs deux bouts sur l'axe de leur mur."""
    murs = {m["id"]: m for m in logement.get("murs", [])}
    sortie = []
    for o in logement.get("ouvertures", []):
        m = murs.get(o.get("mur"))
        if m is None or o["type"] == "porte":
            continue
        a, b = np.array(m["debut"], float), np.array(m["fin"], float)
        L = float(np.linalg.norm(b - a))
        if L < 1e-6:
            continue
        t = (b - a) / L
        sortie.append({"id": o["id"], "a": a + t * float(o["position"]), "b": a + t * (float(o["position"]) + float(o["largeur"]))})
    return sortie


def _touche(origine: np.ndarray, angle_deg: float, a: np.ndarray, b: np.ndarray) -> float | None:
    """La distance à laquelle le rayon parti de `origine` dans la direction `angle_deg` coupe le segment [a, b] (None sinon)."""
    d = np.array([math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))])
    e = b - a
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - origine[0]) * e[1] - (a[1] - origine[1]) * e[0]) / den
    s = ((a[0] - origine[0]) * d[1] - (a[1] - origine[1]) * d[0]) / den
    return float(t) if t > 0.2 and 0.0 <= s <= 1.0 else None


def votes_d_une_photo(profil: dict, camera: dict, logement: dict, plan: dict | None = None) -> dict[str, list[int]]:
    """Ce qu'UNE photo placée dit de chaque baie : {id de la baie: [directions « jusqu'au sol », directions « sur allège »]}."""
    from moteur import caler_photos as cp

    plan = plan or cp.plan_du_logement(logement)
    origine = np.array([float(camera["x"]), float(camera["y"])])
    baies = _baies(logement)
    votes: dict[str, list[int]] = {}
    angles = float(camera["cap"]) + np.asarray(profil["phi"], float)
    T, S, _ = cp.tirs(plan, origine[None], angles)
    for i, angle in enumerate(angles):
        if profil["sol"][i] == 0 or profil["creux"][i] == 0 or S[0, i] != 2:
            continue  # bas caché, pas de creux vu, ou la première chose que le plan met dans cette direction n'est pas une baie
        if abs(float(T[0, i]) - float(profil["r"][i])) > ECART_MUR_M:
            continue  # la photo ne voit pas son mur là où le plan met la baie : place de la photo trop incertaine ici
        touchees = [(t, b["id"]) for b in baies if (t := _touche(origine, float(angle), b["a"], b["b"])) is not None]
        if not touchees:
            continue
        t, ident = min(touchees)
        if abs(t - float(T[0, i])) > 0.5:
            continue  # une autre baie, derrière un mur
        votes.setdefault(ident, [0, 0])[0 if profil["sol"][i] == 1 else 1] += 1
    return votes


def lire(logement: dict, releve: dict, racine, outils=None, journal=None) -> dict[str, list[int]]:
    """Les votes de toutes les photos placées d'une fiche (cameras-photos.json) pour chaque baie du logement."""
    from pathlib import Path

    import cv2

    from moteur import caler_photos as cp
    from moteur import moge
    from moteur.images import lire_image

    modele_moge = outils.moge if outils is not None else moge.charger()
    plan = cp.plan_du_logement(logement)
    dossier = Path(racine) / releve["photos"]
    fichier = releve.get("fichier", "{nom}.png")
    total: dict[str, list[int]] = {}
    for nom, d in releve.get("cameras", {}).items():
        image = lire_image(dossier / fichier.format(nom=nom))
        if image is None:
            raise FileNotFoundError(dossier / fichier.format(nom=nom))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pr = cp.profil(cp.mesurer(modele_moge, rgb, float(d["camera"]["f"])), plan["hsp"])
        if pr is None:
            continue
        v = votes_d_une_photo(pr, d["camera"], logement, plan)
        for ident, (sol, allege) in v.items():
            t = total.setdefault(ident, [0, 0])
            t[0] += sol
            t[1] += allege
        if journal and v:
            journal(f"  {nom} : " + ", ".join(f"{i} jusqu'au sol {s} / sur allège {a}" for i, (s, a) in sorted(v.items())))
    return total


def corriger(logement: dict, votes: dict[str, list[int]], journal=None) -> tuple[dict, list[dict]]:
    """Le logement dont les baies ont la sorte que les photos montrent, et ce qui a changé ({id, avant, apres, votes})."""
    lg = copy.deepcopy(logement)
    hsp = float(lg.get("hauteur_sous_plafond", 2.5))
    changes = []
    for o in lg.get("ouvertures", []):
        sol, allege = votes.get(o["id"], (0, 0))
        if o["type"] == "porte" or sol + allege < VOTES_MIN:
            continue
        if o["type"] == "fenetre" and sol / (sol + allege) >= PART_MIN:
            haut = min(max(float(o.get("allege", 0.0)) + float(o["hauteur"]), HAUT_PORTE_FENETRE), hsp - 0.15)
            apres = {"type": "porte_fenetre", "allege": 0.0, "hauteur": round(haut, 3)}
        elif o["type"] == "porte_fenetre" and allege / (sol + allege) >= PART_MIN:
            haut = min(float(o["hauteur"]), hsp - 0.15)
            apres = {"type": "fenetre", "allege": ALLEGE_FENETRE, "hauteur": round(max(haut - ALLEGE_FENETRE, 0.6), 3)}
        else:
            continue
        changes.append({"id": o["id"], "avant": o["type"], "apres": apres["type"], "votes": [sol, allege]})
        o.update(apres, statut="estime", source="photos (bas de la baie vu sur les photos du client)")
        if journal:
            journal(f"  baie {o['id']} : {changes[-1]['avant']} → {apres['type']} (jusqu'au sol {sol}, sur allège {allege})")
    return lg, changes
