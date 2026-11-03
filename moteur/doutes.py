"""Les doutes d'Atelya (étape A1) : signaler ce qui est peut-être faux au lieu de se tromper en silence.

Ce module ne change rien à la lecture : il la relit et pose des drapeaux. Trois sources :

1. La carte des doutes d'Atelya (facultative) : le plan colorié plusieurs fois (normal, retourné
   gauche-droite, haut-bas, les deux ; outils/atelya/colorier_angles.py, sur le PC). Pour chaque pixel,
   1 − la probabilité moyenne de la couleur choisie : 0 = sûr, 1 = Atelya ne sait pas. On en tire un doute
   par élément lu (mur, ouverture, pièce) et les « zones douteuses orphelines » (là où Atelya hésite
   sans avoir rien lu : une porte peut-être oubliée).
2. Des contrôles de bon sens sur le logement lu, sans image : pièce sans accès, fenêtre entre deux
   pièces, épaisseur de mur improbable, surface improbable pour le type, pièces qui se chevauchent,
   type de pièce hésitant.
3. Des refus : ce qui ne ressemble pas à un logement (aucun mur, aucune pièce…).

Décision par plan (`examiner`) : « lu » (rien à signaler), « a_verifier » (au moins un doute fort, liste
pour l'écran de vérification) ou « refuse ». Un doute fort envoie le plan à la vérification ; un doute
faible est seulement montré.

Format d'un doute : {"code", "element" (id ou None), "raison" (phrase pour l'humain), "gravite"
("fort" ou "faible"), "zone_m" [x0, y0, x1, y1] dans le repère du logement}. L'écran de vérification
(outils/verification-plan) attend `zone_px` : on la calcule avec le calage du plan quand il est connu.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from moteur.coloriage import redresser

VERSION_DOUTES = "0.1.0"

# --- Seuils (réglés sur les bancs ; voir /mnt/project-files/atelya-doutes/plan.md) ---
EPAISSEUR_MIN, EPAISSEUR_MAX = 0.025, 0.70  # m
LARGEUR_PORTE_MIN, LARGEUR_PORTE_MAX = 0.50, 1.80  # m
LARGEUR_FENETRE_MAX = 6.0  # m (baie vitrée)
SURFACE_MIN = {"placard": 0.15, "wc": 0.7, "degagement": 0.6, "escalier": 1.0}  # m²
SURFACE_MIN_DEFAUT = 1.5
SURFACE_MAX = {"wc": 5.0, "placard": 6.0, "salle_d_eau": 20.0, "entree": 25.0}
CONTACT_PIECES = 0.06  # m : deux pièces plus proches se touchent (pas de mur entre elles)
PORTEE_OUVERTURE = 0.15  # m : une porte à moins de (épaisseur / 2 + ça) d'une pièce y donne accès
CONFIANCE_TYPE_MIN = 0.6  # part de la couleur majoritaire dans la pièce
DOUTE_PIXEL = 0.5  # un pixel est « douteux » au-delà
DOUTE_ELEMENT = 0.25  # part de pixels douteux qui rend un élément douteux (fort) ; réglé sur les bancs A1
DOUTE_ELEMENT_FAIBLE = 0.15
ORPHELINE_MIN = 0.35  # m² : plus petite zone douteuse orpheline signalée ; réglé sur les bancs A1
PAS = 0.02  # m : finesse des calculs de surfaces


def _doute(code: str, raison: str, gravite: str = "fort", element: str | None = None,
           zone: tuple[float, float, float, float] | None = None) -> dict:
    d = {"code": code, "element": element, "raison": raison, "gravite": gravite}
    if zone is not None:
        d["zone_m"] = [round(float(v), 3) for v in zone]
    return d


def _type(piece: dict) -> str:
    return piece["id"].rsplit("_", 1)[0]


def _surface(contour) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def _boite(points) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _centre_ouverture(o: dict, murs: dict) -> tuple[float, float]:
    m = murs[o["mur"]]
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    L = math.dist(m["debut"], m["fin"]) or 1.0
    t = (o["position"] + o["largeur"] / 2) / L
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def _zone_ouverture(o: dict, murs: dict) -> tuple[float, float, float, float]:
    m = murs[o["mur"]]
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    L = math.dist(m["debut"], m["fin"]) or 1.0
    a, b = o["position"] / L, (o["position"] + o["largeur"]) / L
    p, q = (x1 + a * (x2 - x1), y1 + a * (y2 - y1)), (x1 + b * (x2 - x1), y1 + b * (y2 - y1))
    e = m["epaisseur"] / 2
    return min(p[0], q[0]) - e, min(p[1], q[1]) - e, max(p[0], q[0]) + e, max(p[1], q[1]) + e


def _zone_mur(m: dict) -> tuple[float, float, float, float]:
    e = m["epaisseur"] / 2
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    return min(x1, x2) - e, min(y1, y2) - e, max(x1, x2) + e, max(y1, y2) + e


class _Grille:
    """Une grille en mètres (pas PAS) qui couvre le logement, pour dessiner pièces et murs."""

    def __init__(self, logement: dict, marge: float = 0.5):
        pts = [p for m in logement["murs"] for p in (m["debut"], m["fin"])]
        pts += [p for piece in logement["pieces"] for p in piece["contour"]]
        x0, y0, x1, y1 = _boite(pts)
        self.x0, self.y0 = x0 - marge, y0 - marge
        self.forme = (int((y1 - y0 + 2 * marge) / PAS) + 2, int((x1 - x0 + 2 * marge) / PAS) + 2)

    def px(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.x0) / PAS, (y - self.y0) / PAS

    def polygone(self, contour) -> np.ndarray:
        m = np.zeros(self.forme, np.uint8)
        pts = np.array([self.px(x, y) for x, y in contour], np.float32)
        cv2.fillPoly(m, [np.round(pts * 4).astype(np.int32)], 1, shift=2)
        return m.astype(bool)

    def valeur(self, masque: np.ndarray, x: float, y: float) -> bool:
        u, v = self.px(x, y)
        i, j = int(round(v)), int(round(u))
        return 0 <= i < masque.shape[0] and 0 <= j < masque.shape[1] and bool(masque[i, j])


# ---------------------------------------------------------------- contrôles de bon sens

def controles_bon_sens(logement: dict, types: dict[str, str] | None = None,
                       noms_lus: list[str] | None = None) -> list[dict]:
    """Les incohérences d'un logement lu, sans regarder l'image.

    `types` : type de chaque pièce (details["types_pieces"] de moteur.coloriage) ; à défaut, tiré de l'id.
    `noms_lus` : pièces dont le nom a été lu sur le plan (leur type est sûr)."""
    doutes: list[dict] = []
    murs = {m["id"]: m for m in logement["murs"]}
    pieces = logement["pieces"]
    types = types or {p["id"]: _type(p) for p in pieces}
    noms_lus = set(noms_lus or [])

    for m in logement["murs"]:
        if not EPAISSEUR_MIN <= m["epaisseur"] <= EPAISSEUR_MAX:
            doutes.append(_doute("epaisseur", f"mur de {100 * m['epaisseur']:.0f} cm d'épaisseur : improbable",
                                 "fort", m["id"], _zone_mur(m)))

    for o in logement["ouvertures"]:
        if o["mur"] not in murs:
            continue
        L = o["largeur"]
        if o["type"] == "porte" and not LARGEUR_PORTE_MIN <= L <= LARGEUR_PORTE_MAX:
            doutes.append(_doute("largeur_porte", f"porte de {100 * L:.0f} cm de large : improbable", "fort",
                                 o["id"], _zone_ouverture(o, murs)))
        elif o["type"] != "porte" and L > LARGEUR_FENETRE_MAX:
            doutes.append(_doute("largeur_fenetre", f"fenêtre de {L:.1f} m de large : improbable", "fort",
                                 o["id"], _zone_ouverture(o, murs)))

    if not pieces:
        return doutes
    g = _Grille(logement)
    rasters = {p["id"]: g.polygone(p["contour"]) for p in pieces}
    interieur = np.zeros(g.forme, bool)
    for r in rasters.values():
        interieur |= r

    # Surfaces improbables pour le type.
    for p in pieces:
        t, s = types.get(p["id"], _type(p)), _surface(p["contour"])
        bas, haut = SURFACE_MIN.get(t, SURFACE_MIN_DEFAUT), SURFACE_MAX.get(t)
        if s < bas or (haut is not None and s > haut):
            doutes.append(_doute("surface", f"{p['nom']} de {s:.1f} m² : surface improbable", "fort",
                                 p["id"], _boite(p["contour"])))

    # Type de pièce hésitant (Atelya a colorié la pièce de plusieurs couleurs, aucun nom lu).
    for p in pieces:
        if p["id"] not in noms_lus and p.get("confiance", 1.0) < CONFIANCE_TYPE_MIN:
            doutes.append(_doute("type_hesitant", f"{p['nom']} : type hésitant ({100 * p.get('confiance', 0):.0f} % "
                                 "de la pièce coloriée ainsi)", "faible", p["id"], _boite(p["contour"])))

    # Pièces qui se chevauchent.
    ids = list(rasters)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            inter = (rasters[a] & rasters[b]).sum()
            if inter * PAS * PAS >= 0.10:
                doutes.append(_doute("chevauchement", f"les pièces {a} et {b} se chevauchent", "fort", a,
                                     _boite([q for p in pieces if p["id"] in (a, b) for q in p["contour"]])))

    # Accès : chaque pièce touche une porte (ou porte-fenêtre), ou une autre pièce sans mur entre elles.
    noyau = np.ones((2 * int(round(CONTACT_PIECES / PAS)) + 1,) * 2, np.uint8)
    elargies = {k: cv2.dilate(r.astype(np.uint8), noyau).astype(bool) for k, r in rasters.items()}
    acces = {k: False for k in rasters}
    for o in logement["ouvertures"]:
        if o["type"] == "fenetre" or o["mur"] not in murs:
            continue
        cx, cy = _centre_ouverture(o, murs)
        portee = murs[o["mur"]]["epaisseur"] / 2 + PORTEE_OUVERTURE
        for k, r in rasters.items():
            if acces[k]:
                continue
            for dx, dy in ((portee, 0), (-portee, 0), (0, portee), (0, -portee)):
                if g.valeur(r, cx + dx, cy + dy):
                    acces[k] = True
                    break
    for a in ids:
        if not acces[a] and any((elargies[a] & rasters[b]).any() for b in ids if b != a):
            acces[a] = True
    for p in pieces:
        if not acces[p["id"]] and len(pieces) > 1:
            doutes.append(_doute("sans_acces", f"{p['nom']} : aucune porte ni passage trouvés", "fort",
                                 p["id"], _boite(p["contour"])))

    # Fenêtre entre deux pièces (les deux côtés du mur sont à l'intérieur).
    for o in logement["ouvertures"]:
        if o["type"] == "porte" or o["mur"] not in murs:
            continue
        m = murs[o["mur"]]
        cx, cy = _centre_ouverture(o, murs)
        (x1, y1), (x2, y2) = m["debut"], m["fin"]
        L = math.dist(m["debut"], m["fin"]) or 1.0
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        d = m["epaisseur"] / 2 + 0.10
        if g.valeur(interieur, cx + nx * d, cy + ny * d) and g.valeur(interieur, cx - nx * d, cy - ny * d):
            doutes.append(_doute("fenetre_interieure", "fenêtre sur un mur entre deux pièces", "fort",
                                 o["id"], _zone_ouverture(o, murs)))
    return doutes


# ---------------------------------------------------------------- la carte des doutes

def carte_au_repere(carte: np.ndarray, details: dict, redressement=None) -> np.ndarray:
    """La carte des doutes (0-255, même taille que le coloriage) dans le repère où le logement a été lu
    (remise à plat, puis rotation), en valeurs de 0 à 1."""
    c = carte.astype(np.float32) / 255.0 if carte.dtype == np.uint8 else carte.astype(np.float32)
    if redressement is not None:
        c = redressement.appliquer(c, lineaire=True)
    return redresser(c, details.get("angle_deg", 0.0) if redressement is None else 0.0, lineaire=True)


def _vers_px(details: dict):
    ox, oy = details["origine_px"]
    s = details["px_par_m"]
    return lambda x, y: (ox + x * s, oy - y * s)


def doutes_de_la_carte(logement: dict, details: dict, carte: np.ndarray) -> tuple[list[dict], dict]:
    """Doutes par élément lu et zones douteuses orphelines, d'après la carte (déjà au repère, 0-1).
    Renvoie (doutes, mesures) ; mesures = part de pixels douteux sur le bâti, dans les pièces, partout."""
    h, w = carte.shape
    vers = _vers_px(details)
    s = details["px_par_m"]
    douteux = carte > DOUTE_PIXEL
    lus = np.zeros((h, w), np.uint8)
    doutes: list[dict] = []
    parts: dict[str, float] = {}  # part de pixels douteux de chaque élément (pour régler les seuils)

    def noter(masque: np.ndarray, element: str, quoi: str, zone) -> None:
        n = int(masque.sum())
        if not n:
            return
        part = float(douteux[masque].mean())
        parts[element] = round(part, 3)
        if part >= DOUTE_ELEMENT_FAIBLE:
            fort = part >= DOUTE_ELEMENT
            doutes.append(_doute("carte", f"{quoi} : Atelya hésite sur {100 * part:.0f} % de sa surface",
                                 "fort" if fort else "faible", element, zone))

    murs = {m["id"]: m for m in logement["murs"]}
    for m in logement["murs"]:
        msq = np.zeros((h, w), np.uint8)
        a, b = vers(*m["debut"]), vers(*m["fin"])
        e = max(1, int(round(m["epaisseur"] * s)))
        cv2.line(msq, tuple(int(round(v)) for v in a), tuple(int(round(v)) for v in b), 1, e)
        lus |= msq
        noter(msq.astype(bool), m["id"], f"mur {m['id']}", _zone_mur(m))
    for o in logement["ouvertures"]:
        if o["mur"] not in murs:
            continue
        x0, y0, x1, y1 = _zone_ouverture(o, murs)
        (u0, v0), (u1, v1) = vers(x0, y1), vers(x1, y0)
        msq = np.zeros((h, w), np.uint8)
        cv2.rectangle(msq, (int(round(u0)), int(round(v0))), (int(round(u1)), int(round(v1))), 1, -1)
        lus |= msq
        nom = {"porte": "porte", "fenetre": "fenêtre", "porte_fenetre": "porte-fenêtre"}[o["type"]]
        noter(msq.astype(bool), o["id"], f"{nom} {o['id']}", (x0, y0, x1, y1))
    dans_pieces = np.zeros((h, w), np.uint8)
    for p in logement["pieces"]:
        msq = np.zeros((h, w), np.uint8)
        pts = np.array([vers(x, y) for x, y in p["contour"]], np.float32)
        cv2.fillPoly(msq, [np.round(pts * 4).astype(np.int32)], 1, shift=2)
        dans_pieces |= msq
        noter(msq.astype(bool), p["id"], p["nom"], _boite(p["contour"]))

    # Zones orphelines : du doute hors de tout mur et de toute ouverture lus, collé au logement
    # (par exemple une porte qu'Atelya a hésité à colorier et que la lecture a laissée de côté).
    pres = cv2.dilate((lus | dans_pieces), np.ones((5, 5), np.uint8)).astype(bool)
    orphelin = (douteux & pres & ~lus.astype(bool)).astype(np.uint8)
    # Les bords des pièces (une ligne de pixels contre les murs) sont toujours un peu douteux : on les retire.
    orphelin = cv2.morphologyEx(orphelin, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(orphelin, connectivity=8)
    ox, oy = details["origine_px"]
    orphelines = []
    for i in range(1, n):
        x, y, ww, hh, aire = stats[i]
        zone = ((x - ox) / s, (oy - y - hh) / s, (x + ww - ox) / s, (oy - y) / s)
        if aire >= 0.02 * s * s:
            orphelines.append([round(aire / s / s, 3), [round(v, 2) for v in zone]])
        if aire < ORPHELINE_MIN * s * s:
            continue
        doutes.append(_doute("zone_douteuse", f"Atelya hésite ici sans rien avoir lu ({aire / s / s:.2f} m²)",
                             "fort", None, zone))
    bati = lus.astype(bool)
    mesures = {"bati": round(float(douteux[bati].mean()), 4) if bati.any() else None,
               "pieces": round(float(douteux[dans_pieces.astype(bool)].mean()), 4) if dans_pieces.any() else None,
               "tout": round(float(douteux.mean()), 4), "elements": parts, "orphelines": orphelines}
    return doutes, mesures


# ---------------------------------------------------------------- refus et décision

def refus(logement: dict | None, erreur: str | None = None) -> list[dict]:
    """Ce qui ne ressemble pas à un logement : rien de lisible, ou presque rien."""
    if logement is None:
        return [_doute("pas_un_plan", f"aucun logement lisible ({erreur or 'lecture impossible'})", "fort")]
    sortie = []
    if len(logement["murs"]) < 4:
        sortie.append(_doute("pas_un_plan", f"seulement {len(logement['murs'])} mur(s) lu(s)", "fort"))
    if not logement["pieces"]:
        sortie.append(_doute("pas_un_plan", "aucune pièce fermée", "fort"))
    elif sum(_surface(p["contour"]) for p in logement["pieces"]) < 8.0:
        sortie.append(_doute("pas_un_plan", "moins de 8 m² de pièces lues", "fort"))
    return sortie


def examiner(logement: dict | None, details: dict | None = None, *, carte: np.ndarray | None = None,
             redressement=None, erreur: str | None = None, autres: list[dict] | None = None) -> dict:
    """Tous les doutes d'une lecture et la décision : « lu », « a_verifier » ou « refuse ».

    `carte` : la carte des doutes d'Atelya, à la taille du coloriage lu (0-255) ; `redressement` celui
    donné à lire_coloriage. `autres` : doutes venus d'ailleurs (échelle à vérifier, coloriage douteux…)."""
    r = refus(logement, erreur)
    if r:
        return {"version": VERSION_DOUTES, "decision": "refuse", "doutes": r, "mesures": {}}
    details = details or {}
    doutes = controles_bon_sens(logement, details.get("types_pieces"), details.get("pieces_nom_lu"))
    mesures: dict = {}
    if carte is not None and "origine_px" in details:
        d, mesures = doutes_de_la_carte(logement, details, carte_au_repere(carte, details, redressement))
        doutes += d
    doutes += autres or []
    fort = any(d["gravite"] == "fort" for d in doutes)
    return {"version": VERSION_DOUTES, "decision": "a_verifier" if fort else "lu", "doutes": doutes,
            "mesures": mesures}
