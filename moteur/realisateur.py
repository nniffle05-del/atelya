"""Le RÉALISATEUR d'Atelya : il choisit SEUL les plans du film d'un logement (11/11/2026, demande NT : « il faut qu'Atelya sache
faire un plan cinéma tout seul », règle n° 21).

Entrée : le logement (logement.json : murs avec épaisseur, ouvertures, pièces, meubles). Sortie : une liste de PLANS, chacun un
trajet de caméra au format de moteur/blender/video_trajet.py et outils/unreal/cinematique_unreal.py ({"points": [[x, y, z, cap,
tangage], …], "images", "ips", "focale_mm", "format"}), plus la pièce filmée et pourquoi ce point de vue.

Comment, comme un vidéaste d'immobilier :
1. LES PIÈCES ET L'ORDRE : un parcours logique (entrée, séjour, cuisine, chambres, salles d'eau) ; pas les placards, WC,
   dégagements (rien à y montrer) ; une grande pièce (> GRANDE_PIECE_M2) a deux plans, pris de points de vue différents.
2. LE POINT DE VUE : des centaines de positions candidates dans la pièce (pas de 0,25 m), à au moins MARGE_MUR des murs et
   MARGE_MEUBLE des meubles (on tient debout là) ; de chaque position, 180 rayons dans le plan (un tous les 2°) mesurent ce que
   l'on voit : murs (une ouverture de porte laisse voir plus loin), fenêtres (la lumière), meubles. Pour chaque direction, la NOTE
   d'un cadrage (objectif FOCALE_MM, 90° de champ) : la part de la pièce vue (aire balayée par les rayons dans la pièce), une
   fenêtre dans le champ sans qu'elle le remplisse (la lumière qui fait l'image), les meubles vus, et une pénalité si l'on fait face
   à un mur proche.
3. LE MOUVEMENT : un travelling lent vers l'avant (AVANCEE_M en DUREE_S secondes) avec un léger panoramique (±PANO_DEG) ; si la
   caméra ne peut pas avancer sans toucher un mur ou un meuble, un travelling latéral ; sinon un panoramique sur place. Hauteur
   d'œil HAUTEUR_M, légère plongée TANGAGE_DEG (les verticales restent presque droites).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HAUTEUR_M = 1.5
TANGAGE_DEG = -5.0
FOCALE_MM = 18.0
CHAMP_DEG = 2 * math.degrees(math.atan(18.0 / FOCALE_MM))  # capteur de 36 mm
DUREE_S = 6.0
IPS = 24
FORMAT = (1920, 1080)
AVANCEE_M = 1.0
PANO_DEG = 6.0
MARGE_MUR = 0.45
MARGE_MUR_PETITE = 0.3  # pièces étroites (salles d'eau) : on se colle un peu plus
MARGE_MEUBLE = 0.3
PAS_M = 0.25
GRANDE_PIECE_M2 = 28.0
PORTEE_M = 12.0
ORDRE = ["entree", "sejour", "salon", "salle_a_manger", "cuisine", "bureau", "chambre", "salle_de_bain", "salle_d_eau"]
SANS_INTERET = {"placard", "wc", "degagement", "dressing", "cellier", "couloir", "buanderie", "local", "debarras"}
NB_RAYONS = 180
# Les portes intérieures sont FERMÉES dans la maquette 3D (vu le 11/11/2026 : le plan de l'entrée d'app-002 visait le séjour « à
# travers » deux portes fermées et ne filmait qu'un coin sombre) : elles cachent la vue comme un mur.
PORTES_FERMEES = True
CANDIDATS_MOUVEMENT = 120  # les meilleurs cadrages dont on essaie le mouvement
MALUS_PANORAMIQUE = 0.6


# ---------------------------------------------------------------------------------------------------------------------------
# LE SAVOIR-FAIRE APPRIS (11/11/2026, NT : « il doit l'apprendre tout seul » → il apprend des AVIS de NT, plan par plan).
# Chaque avis corrige un peu un ou plusieurs réglages (petits pas, bornés) ; les corrections sont gardées dans APPRIS (dans le
# dépôt) et deviennent le comportement par défaut de tous les films suivants (règle 21), avec l'historique des avis.
APPRIS = Path(__file__).resolve().parent / "realisateur_appris.json"
SAVOIR_DEFAUT = {
    "poids_part_vue": 2.0, "poids_fenetre": 0.8, "fenetre_min": 0.04, "fenetre_max": 0.35, "poids_meubles": 0.12,
    "poids_profondeur": 0.15, "poids_mur_proche": 0.8, "mur_proche_m": 2.2, "marge_mur": MARGE_MUR, "marge_meuble": MARGE_MEUBLE,
    "avancee_m": AVANCEE_M, "pano_deg": PANO_DEG, "duree_s": DUREE_S, "hauteur_m": HAUTEUR_M, "tangage_deg": TANGAGE_DEG,
    "focale_mm": FOCALE_MM,
}
BORNES = {
    "poids_part_vue": (0.5, 5.0), "poids_fenetre": (0.0, 3.0), "fenetre_min": (0.0, 0.3), "fenetre_max": (0.15, 0.8),
    "poids_meubles": (0.0, 0.5), "poids_profondeur": (0.0, 0.6), "poids_mur_proche": (0.0, 3.0), "mur_proche_m": (1.0, 4.0),
    "marge_mur": (0.3, 1.2), "marge_meuble": (0.2, 1.0), "avancee_m": (0.3, 2.5), "pano_deg": (0.0, 20.0), "duree_s": (3.0, 12.0),
    "hauteur_m": (1.1, 1.8), "tangage_deg": (-15.0, 3.0), "focale_mm": (14.0, 30.0),
}
# Les avis possibles (mots simples de NT) et ce qu'ils corrigent (un pas par avis).
AVIS = {
    "bien": {},
    "trop_pres": {"marge_mur": +0.1, "mur_proche_m": +0.3, "marge_meuble": +0.1},
    "trop_loin": {"marge_mur": -0.05, "poids_profondeur": -0.03},
    "ennuyeux": {"avancee_m": +0.3, "pano_deg": +2.0, "duree_s": -0.5},
    "trop_rapide": {"avancee_m": -0.2, "pano_deg": -1.5},
    "trop_lent": {"avancee_m": +0.2},
    "trop_long": {"duree_s": -0.5},
    "trop_court": {"duree_s": +0.5},
    "pas_assez_de_lumiere": {"poids_fenetre": +0.2, "fenetre_min": +0.03},
    "contre_jour": {"fenetre_max": -0.05, "poids_fenetre": -0.1},
    "piece_mal_montree": {"poids_part_vue": +0.3, "poids_mur_proche": +0.2},
    "pas_assez_de_meubles": {"poids_meubles": +0.04},
    "trop_haut": {"hauteur_m": -0.1},
    "trop_bas": {"hauteur_m": +0.1},
    "trop_plongeant": {"tangage_deg": +2.0},
    "pas_assez_plongeant": {"tangage_deg": -2.0},
    "deforme": {"focale_mm": +2.0},
    "pas_assez_large": {"focale_mm": -2.0},
}


def savoir_faire(chemin: Path | None = None) -> dict:
    """Le savoir-faire actuel : les réglages de départ, corrigés par tout ce qui a été appris des avis."""
    chemin = chemin or APPRIS
    s = dict(SAVOIR_DEFAUT)
    if chemin.is_file():
        s.update(json.loads(chemin.read_text(encoding="utf-8")).get("reglages", {}))
    return s


def apprendre(avis: list[dict], chemin: Path | None = None) -> dict:
    """Enregistre des avis ([{"plan": 3, "piece": "cuisine_1", "avis": ["trop_pres", …], "film": "…"}]) et corrige le
    savoir-faire en conséquence (un pas par avis, borné). Renvoie les réglages appris."""
    chemin = chemin or APPRIS
    donnees = json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else {"reglages": {}, "historique": []}
    s = {**SAVOIR_DEFAUT, **donnees.get("reglages", {})}
    for a in avis:
        for mot in a.get("avis", []):
            if mot not in AVIS:
                raise ValueError(f"avis inconnu « {mot} » (possibles : {', '.join(AVIS)})")
            for cle, pas in AVIS[mot].items():
                bas, haut = BORNES[cle]
                s[cle] = round(min(max(s[cle] + pas, bas), haut), 4)
        donnees["historique"].append(a)
    donnees["reglages"] = {k: v for k, v in s.items() if v != SAVOIR_DEFAUT[k]}
    chemin.write_text(json.dumps(donnees, indent=1, ensure_ascii=False), encoding="utf-8")
    return s


def _type(piece: dict) -> str:
    ident = piece["id"]
    return ident.rsplit("_", 1)[0] if ident.rsplit("_", 1)[-1].isdigit() else ident


def _aire(contour) -> float:
    c = np.asarray(contour, float)
    return 0.5 * abs(float(np.dot(c[:, 0], np.roll(c[:, 1], -1)) - np.dot(c[:, 1], np.roll(c[:, 0], -1))))


def _dedans(p, contour) -> bool:
    x, y = p
    c = contour
    dedans = False
    for i in range(len(c)):
        (x1, y1), (x2, y2) = c[i], c[(i + 1) % len(c)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def _rectangle(a, b, epaisseur) -> np.ndarray:
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = (b - a) / max(np.linalg.norm(b - a), 1e-9)
    n = np.array([-d[1], d[0]]) * epaisseur / 2
    return np.array([a + n, b + n, b - n, a - n])


def _rectangle_meuble(m: dict) -> np.ndarray:
    (cx, cy), (l, p) = m["position"], m["dimensions"][:2]
    a = math.radians(m.get("face") or 0.0)
    u, v = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    c = np.array([cx, cy])
    return np.array([c + u * l / 2 + v * p / 2, c - u * l / 2 + v * p / 2, c - u * l / 2 - v * p / 2, c + u * l / 2 - v * p / 2])


class Scene2D:
    """Le logement vu de dessus : murs pleins (rectangles), fenêtres (rectangles « lumière »), meubles."""

    def __init__(self, logement: dict, portes_fermees: bool | None = None):
        portes_fermees = PORTES_FERMEES if portes_fermees is None else portes_fermees
        self.pieces = logement["pieces"]
        murs = {m["id"]: m for m in logement["murs"]}
        par_mur: dict[str, list[dict]] = {}
        for o in logement.get("ouvertures", []):
            par_mur.setdefault(o["mur"], []).append(o)
        pleins, fenetres = [], []
        for ident, m in murs.items():
            a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
            longueur = float(np.linalg.norm(b - a))
            d = (b - a) / longueur
            debut = 0.0
            for o in sorted(par_mur.get(ident, []), key=lambda o: o["position"]):
                s, e = o["position"], o["position"] + o["largeur"]
                if s > debut:
                    pleins.append(_rectangle(a + d * debut, a + d * s, m["epaisseur"]))
                if o["type"] in ("fenetre", "porte_fenetre"):
                    fenetres.append(_rectangle(a + d * s, a + d * e, m["epaisseur"]))
                elif portes_fermees:
                    pleins.append(_rectangle(a + d * s, a + d * e, m["epaisseur"]))  # porte fermée : on ne voit pas à travers
                debut = max(debut, e)
            if debut < longueur:
                pleins.append(_rectangle(a + d * debut, b, m["epaisseur"]))
        self.pleins = pleins
        self.fenetres = fenetres
        self.meubles = [(m, _rectangle_meuble(m)) for m in logement.get("meubles", [])
                        if m.get("position") and m.get("dimensions")]
        # tous les côtés, avec leur genre : 0 mur, 1 fenêtre, 2 meuble haut (cache la vue), 3 meuble bas (vu, ne cache pas)
        cotes, genres, numeros = [], [], []
        for genre, polys in ((0, self.pleins), (1, self.fenetres)):
            for poly in polys:
                for i in range(4):
                    cotes.append([*poly[i], *poly[(i + 1) % 4]])
                    genres.append(genre)
                    numeros.append(-1)
        for k, (m, poly) in enumerate(self.meubles):
            genre = 2 if (m["dimensions"][2] if len(m["dimensions"]) > 2 else 1.0) > 1.4 else 3
            for i in range(4):
                cotes.append([*poly[i], *poly[(i + 1) % 4]])
                genres.append(genre)
                numeros.append(k)
        self.cotes = np.array(cotes, float)
        self.genres = np.array(genres)
        self.numeros = np.array(numeros)

    def a_une_fenetre(self, piece: dict, tolerance: float = 0.4) -> bool:
        """La pièce reçoit-elle le jour (une fenêtre ou porte-fenêtre sur son pourtour) ?"""
        contour = np.asarray(piece["contour"], float)
        for poly in self.fenetres:
            centre = poly.mean(0)
            for i in range(len(contour)):
                a, b = contour[i], contour[(i + 1) % len(contour)]
                t = np.clip(np.dot(centre - a, b - a) / max(np.dot(b - a, b - a), 1e-12), 0, 1)
                if np.linalg.norm(centre - (a + t * (b - a))) <= tolerance:
                    return True
        return False

    def distance_aux_obstacles(self, p) -> tuple[float, float]:
        """(distance aux murs pleins et fenêtres, distance aux meubles), en mètres (négative si dedans)."""
        p = np.asarray(p, float)

        def dist(polys):
            best = 1e9
            for poly in polys:
                if _dedans(p, poly):
                    return -1.0
                for i in range(4):
                    a, b = poly[i], poly[(i + 1) % 4]
                    t = np.clip(np.dot(p - a, b - a) / max(np.dot(b - a, b - a), 1e-12), 0, 1)
                    best = min(best, float(np.linalg.norm(p - (a + t * (b - a)))))
            return best
        return dist(self.pleins + self.fenetres), dist([poly for _, poly in self.meubles])

    def rayons(self, p) -> dict:
        """180 rayons depuis p : distance au premier obstacle qui cache (mur, fenêtre, meuble haut), genre touché, meubles vus."""
        angles = np.radians(np.arange(NB_RAYONS) * (360.0 / NB_RAYONS))
        d = np.stack([np.cos(angles), np.sin(angles)], 1)
        a, b = self.cotes[:, :2], self.cotes[:, 2:]
        e = b - a
        w = a - np.asarray(p, float)
        denom = d[:, None, 0] * e[None, :, 1] - d[:, None, 1] * e[None, :, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (w[None, :, 0] * e[None, :, 1] - w[None, :, 1] * e[None, :, 0]) / denom
            s = (w[None, :, 0] * d[:, None, 1] - w[None, :, 1] * d[:, None, 0]) / denom
        ok = (np.abs(denom) > 1e-12) & (t > 1e-6) & (s >= 0) & (s <= 1)
        t = np.where(ok, t, np.inf)
        cache = np.isin(self.genres, (0, 1, 2))
        tc = np.where(cache[None, :], t, np.inf)
        i = np.argmin(tc, 1)
        dist = np.minimum(tc[np.arange(len(i)), i], PORTEE_M)
        genre = np.where(np.isfinite(tc[np.arange(len(i)), i]), self.genres[i], -1)
        bas = (self.genres == 3)[None, :] & (t < dist[:, None])
        meubles_vus = [set(self.numeros[bas[k]]) | ({int(self.numeros[i[k]])} if genre[k] == 2 else set())
                       for k in range(len(i))]
        return {"angles": np.degrees(angles), "distance": dist, "genre": genre, "meubles": meubles_vus}


def _note_cadrage(r: dict, centre_deg: float, piece_aire: float, s: dict | None = None) -> tuple[float, dict]:
    s = s or savoir_faire()
    demi = math.degrees(math.atan(18.0 / s["focale_mm"]))
    ecart = (r["angles"] - centre_deg + 180) % 360 - 180
    champ = np.abs(ecart) <= demi
    dist = r["distance"][champ]
    if len(dist) == 0:
        return -1e9, {}
    pas = math.radians(360.0 / NB_RAYONS)
    aire_vue = float(np.sum(np.minimum(dist, 8.0) ** 2) * pas / 2)
    part_vue = min(aire_vue / max(piece_aire, 1.0), 1.5)
    fenetre = float(np.mean(r["genre"][champ] == 1))
    note_fenetre = 1.0 if s["fenetre_min"] <= fenetre <= s["fenetre_max"] else (0.4 if fenetre > s["fenetre_max"] else 0.0)
    meubles = set().union(*[r["meubles"][k] for k in np.nonzero(champ)[0]]) - {-1}
    centre = np.abs(ecart) <= 10
    face = float(np.min(r["distance"][centre])) if np.any(centre) else 0.0
    penalite_mur = max(0.0, s["mur_proche_m"] - face)
    profondeur = float(np.median(dist))
    note = (s["poids_part_vue"] * part_vue + s["poids_fenetre"] * note_fenetre + s["poids_meubles"] * min(len(meubles), 6)
            + s["poids_profondeur"] * min(profondeur, 6) - s["poids_mur_proche"] * penalite_mur)
    return note, {"part_vue": round(part_vue, 2), "fenetre": round(fenetre, 2), "meubles": len(meubles),
                  "face_m": round(face, 2), "profondeur_m": round(profondeur, 2)}


def _libre(scene: Scene2D, p, contour, marge_mur, marge_meuble=MARGE_MEUBLE) -> bool:
    if not _dedans(p, contour):
        return False
    dm, dmeuble = scene.distance_aux_obstacles(p)
    return dm >= marge_mur and dmeuble >= marge_meuble


def _chemin_libre(scene, a, b, contour, marge_mur, pas=0.1, marge_meuble=MARGE_MEUBLE) -> bool:
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = max(2, int(np.linalg.norm(b - a) / pas) + 1)
    return all(_libre(scene, a + (b - a) * k / (n - 1), contour, marge_mur, marge_meuble) for k in range(n))


def points_de_vue(scene: Scene2D, piece: dict, n: int = 1, s: dict | None = None) -> list[dict]:
    """Les n meilleurs points de vue d'une pièce (position, direction, note, détail), assez différents les uns des autres."""
    s = s or savoir_faire()
    contour = [tuple(p) for p in piece["contour"]]
    aire = _aire(contour)
    xs, ys = [p[0] for p in contour], [p[1] for p in contour]
    marge = s["marge_mur"] if min(max(xs) - min(xs), max(ys) - min(ys)) > 2.2 else MARGE_MUR_PETITE
    candidats = []
    for x in np.arange(min(xs) + marge, max(xs) - marge + 1e-9, PAS_M):
        for y in np.arange(min(ys) + marge, max(ys) - marge + 1e-9, PAS_M):
            p = (float(x), float(y))
            if not _libre(scene, p, contour, marge, s["marge_meuble"]):
                continue
            r = scene.rayons(p)
            for cap in range(0, 360, 10):
                note, detail = _note_cadrage(r, cap, aire, s)
                candidats.append({"position": p, "cap": float(cap), "note": note, "detail": detail, "marge": marge})
    candidats.sort(key=lambda c: -c["note"])
    # un plan qui BOUGE vaut mieux : parmi les meilleurs cadrages, ceux où la caméra peut avancer (ou glisser) passent devant
    for c in candidats[:CANDIDATS_MOUVEMENT]:
        c["trajet"], c["mouvement"] = mouvement(scene, piece, c, s)
        c["note_finale"] = c["note"] - (MALUS_PANORAMIQUE if c["mouvement"].startswith("panoramique") else 0.0)
    retenus = sorted(candidats[:CANDIDATS_MOUVEMENT], key=lambda c: -c["note_finale"])
    choisis = []
    for c in retenus:
        if all(math.dist(c["position"], o["position"]) > 2.5 or abs((c["cap"] - o["cap"] + 180) % 360 - 180) > 70
               for o in choisis):
            choisis.append(c)
        if len(choisis) == n:
            break
    return choisis


def mouvement(scene: Scene2D, piece: dict, vue: dict, s: dict | None = None) -> tuple[list[list[float]], str]:
    """Le trajet du plan : travelling avant si possible, sinon latéral, sinon panoramique sur place."""
    s = s or savoir_faire()
    contour = [tuple(p) for p in piece["contour"]]
    p0 = np.asarray(vue["position"], float)
    cap = vue["cap"]
    marge = vue["marge"]
    pano = s["pano_deg"]
    avant = np.array([math.cos(math.radians(cap)), math.sin(math.radians(cap))])
    lateral = np.array([-avant[1], avant[0]])

    def trajet(a, b, cap_a, cap_b):
        m = (a + b) / 2
        return [[round(float(q[0]), 3), round(float(q[1]), 3), round(s["hauteur_m"], 3), round(c, 1), round(s["tangage_deg"], 1)]
                for q, c in ((a, cap_a), (m, (cap_a + cap_b) / 2), (b, cap_b))]

    longueurs = sorted({round(s["avancee_m"], 2), round(0.7 * s["avancee_m"], 2), round(0.5 * s["avancee_m"], 2)}, reverse=True)
    for longueur in longueurs:  # on recule d'abord si l'on peut, pour finir sur le point de vue choisi
        for a, b in ((p0 - avant * longueur, p0), (p0, p0 + avant * longueur)):
            if _chemin_libre(scene, a, b, contour, marge, marge_meuble=s["marge_meuble"]):
                return trajet(a, b, cap - pano, cap + pano), f"travelling avant {longueur:.1f} m"
    for longueur in (0.8, 0.5):
        for sens in (1, -1):
            a, b = p0 - lateral * sens * longueur / 2, p0 + lateral * sens * longueur / 2
            if _chemin_libre(scene, a, b, contour, marge, marge_meuble=s["marge_meuble"]):
                return trajet(a, b, cap + sens * pano, cap - sens * pano), f"travelling latéral {longueur:.1f} m"
    return trajet(p0, p0, cap - 2 * pano, cap + 2 * pano), "panoramique sur place"


def rien_a_montrer(vue: dict) -> bool:
    """Un vidéaste ne filme pas une pièce vide et sans fenêtre (12/11/2026, premier film d'app-002 : l'entrée, la salle d'eau
    et la salle de bains ne montraient que des murs, les sanitaires n'étant pas encore modélisés)."""
    d = vue.get("detail") or {}
    return d.get("meubles", 0) == 0 and d.get("fenetre", 0.0) == 0.0


def realiser(logement: dict, duree_s: float | None = None, format_image=FORMAT, scene_eclairage: str | None = None,
             s: dict | None = None) -> list[dict]:
    """Les plans du film, dans l'ordre du parcours, avec le savoir-faire appris (savoir_faire())."""
    s = s or savoir_faire()
    duree_s = duree_s or s["duree_s"]
    scene = Scene2D(logement)
    pieces = [p for p in logement["pieces"] if _type(p) not in SANS_INTERET and len(p.get("contour") or []) >= 3]

    def rang(p):
        t = _type(p)
        return (ORDRE.index(t) if t in ORDRE else len(ORDRE), p["id"])
    plans = []
    for piece in sorted(pieces, key=rang):
        n = 2 if _aire(piece["contour"]) > GRANDE_PIECE_M2 else 1
        for k, vue in enumerate(points_de_vue(scene, piece, n, s)):
            if rien_a_montrer(vue):
                continue
            points, maniere = vue["trajet"], vue["mouvement"]
            plan = {"piece": piece["id"], "nom_piece": piece.get("nom", piece["id"]), "numero": len(plans) + 1,
                    "lumiere_du_jour": scene.a_une_fenetre(piece),
                    "points": points, "images": int(round(duree_s * IPS)), "ips": IPS, "focale_mm": s["focale_mm"],
                    "format": list(format_image), "mouvement": maniere, "note": round(vue["note"], 2),
                    "pourquoi": vue["detail"]}
            if scene_eclairage:
                plan["scene"] = scene_eclairage
            plans.append(plan)
    return plans


def dessiner(logement: dict, plans: list[dict], chemin, px_par_m: int = 60) -> None:
    """Les plans vus de dessus (pour vérifier d'un coup d'œil) : murs en noir, fenêtres en bleu, meubles en gris, chaque plan
    avec son numéro, son trajet (rouge) et son champ de vision au départ (orange)."""
    import cv2

    from moteur.images import ecrire_image

    scene = Scene2D(logement)
    pts = np.concatenate([np.asarray(p["contour"], float) for p in logement["pieces"]])
    mini, maxi = pts.min(0) - 1.0, pts.max(0) + 1.0
    w, h = (maxi - mini) * px_par_m
    image = np.full((int(h), int(w), 3), 255, np.uint8)

    def ecran(p):
        return int((p[0] - mini[0]) * px_par_m), int((maxi[1] - p[1]) * px_par_m)
    for piece in logement["pieces"]:
        cv2.polylines(image, [np.array([ecran(p) for p in piece["contour"]], np.int32)], True, (225, 225, 225), 1)
    for _, poly in scene.meubles:
        cv2.fillPoly(image, [np.array([ecran(p) for p in poly], np.int32)], (200, 200, 200))
    for poly in scene.pleins:
        cv2.fillPoly(image, [np.array([ecran(p) for p in poly], np.int32)], (40, 40, 40))
    for poly in scene.fenetres:
        cv2.fillPoly(image, [np.array([ecran(p) for p in poly], np.int32)], (230, 160, 60))
    for plan in plans:
        p0, p1 = plan["points"][0], plan["points"][-1]
        cap = math.radians(p0[3])
        for s in (-1, 1):
            a = cap + s * math.radians(CHAMP_DEG / 2)
            cv2.line(image, ecran(p0[:2]), ecran((p0[0] + 2.0 * math.cos(a), p0[1] + 2.0 * math.sin(a))), (0, 150, 255), 1,
                     cv2.LINE_AA)
        cv2.arrowedLine(image, ecran(p0[:2]), ecran(p1[:2]) if p0[:2] != p1[:2] else
                        ecran((p0[0] + 0.4 * math.cos(cap), p0[1] + 0.4 * math.sin(cap))), (0, 0, 220), 2, cv2.LINE_AA,
                        tipLength=0.3)
        cv2.putText(image, str(plan["numero"]), (ecran(p0[:2])[0] + 6, ecran(p0[:2])[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 200), 2, cv2.LINE_AA)
    ecrire_image(chemin, image)
