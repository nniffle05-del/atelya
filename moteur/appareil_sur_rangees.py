"""L'APPAREIL D'UNE PHOTO DE CUISINE REPRIS SUR LES ÉLÉMENTS RANGÉS : UN DERNIER RECOURS (28/11/2026, « l'appareil dans un meuble »).

Pourquoi : une photo de petite cuisine ne montre presque que des meubles (app-004, photo 05 : 35 points de plafond, aucun de
sol). Le calage (moteur/caler_photos.py), qui s'accroche aux murs, au sol et au plafond, n'a rien pour s'y repérer : l'appareil
sortait à 1 m de sa place, face au flanc d'une colonne. Les lignes lues de la fenêtre (moteur/affiner_appareils.py) fixent bien
le zoom et la distance, mais pas le glissement le long du mur (une fenêtre lointaine vue de face : glisser d'un mètre ou tourner
de 10° lui font le même effet). Or Atelya sait deux choses de plus sur ces photos : le RECTANGLE de chaque élément de cuisine
(la lecture les numérote) et sa PLACE sur le plan (moteur/rangees.py range la cuisine le long de ses murs). Ici l'appareil est
déplacé et tourné jusqu'à ce que les éléments du plan, vus par lui, tombent sur leurs rectangles — ENSEMBLE avec les lignes lues.

MESURÉ le 28/11/2026 sur les cinq photos de cuisine des trois logements (pc/essais-place-appareils/cuisine.py) :
  - ces éléments sont de MAUVAIS repères là où le calage avait des murs : rangés par modules de 60 cm, ils tombent à 200-350 px
    de leurs rectangles même avec un appareil relevé à la main (app-002) ; seuls, sur trois photos calées sur leurs murs, ils
    faisaient passer les repères marqués à la main de 19 à 84 px. D'où : DERNIER RECOURS SEULEMENT, pour une photo que l'affinage
    n'a pas pu caler sur ses murs (« depart », « lus »), jamais contre les lignes lues, et gardé seulement s'il colle nettement
    mieux (`affiner` → « garde ») ;
  - dans ce cadre : app-004 photo 05, appareil descendu de 0,75 m, la vue montre enfin la fenêtre, le meuble bas et la colonne
    comme la photo (jugé à l'œil dans Blender, pas de corrigé) ; app-002 photo 08 : neutre (repères à la main 15 → 14 px) ;
    app-002 photo 09 : non gardé. Un seul cas gagné : la vraie note viendra d'un logement jamais vu.
Seuls comptent les bords SÛRS : les côtés d'un élément haut (colonne, réfrigérateur : rien ne les cache) ou de son voisin, et
le dessus d'un meuble bas (le plan de travail) ; le rectangle d'un meuble bas n'en montre souvent que la partie visible.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
BORD_PX = 5  # un bord de rectangle à moins de 5 px du cadre est coupé par la photo : il dit seulement « au moins jusqu'ici »
PLAFOND_PX = 150.0  # un bord ne pèse jamais plus (un élément caché en partie par un autre ne doit pas tout emporter)
POIDS_HAUTEUR = 0.5  # les bords du haut et du bas pèsent moitié moins : la hauteur des éléments est celle de leur sorte, supposée
RAYON_M, PAS_M = 1.6, 0.08  # l'appareil est cherché à moins de 1,6 m de celui du calage, tous les 8 cm …
TOUR_DEG, PAS_DEG = 14.0, 1.0  # … tourné de ± 14° seulement (l'orientation du calage est sa mesure la plus sûre : 1 à 13°
#                                  d'écart aux relevés à la main sur les cuisines, pour 0,5 à 1,2 m de place), tous les degrés
RAPPEL_PX_PAR_DEG = 1.0  # à écart égal, l'orientation la plus proche de celle du calage
HAUTS = ("colonne_cuisine", "refrigerateur")  # éléments hauts : rien ne les cache, leurs deux côtés se voient en entier
DEPASSE_PX = 15.0  # un rectangle lu peut dépasser de 15 px de l'élément prévu sans rien dire
POIDS_CONTIENT = 0.5
ZOOMS = (0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1)  # le zoom du calage est souvent trop serré : essayé de − 20 % à + 10 %
RAPPEL_PX_PAR_M = 3.0  # à écart égal, l'appareil le plus proche de celui du calage
RAPPEL_ZOOM_PX = 20.0  # … et le zoom le plus proche (par 100 % d'écart)
CONTACT_MUR_M = 0.12  # l'appareil reste à 12 cm au moins d'un mur
CONTACT_MEUBLE_M = 0.05  # … et hors de tout élément rangé
CACHE_M = 0.7  # un élément n'est pas vu à travers un mur plein
PRES_M = 0.12  # un point plus près de l'appareil ne se projette pas
GARDE_PX = 45.0  # l'appareil repris n'est gardé que s'il colle à moins de 45 px en moyenne …
GARDE_GAIN = 0.7  # … et au moins 30 % mieux que celui du calage
BORDS_MIN = 3  # … sur au moins trois bords sûrs
GAIN_MIN_PX = 5.0  # … et d'au moins 5 px (un appareil déjà juste n'est pas « repris »)


def elements(rangees_de_la_photo: list[dict], boites: dict[int, list[float]], camera: dict, logement: dict, plan: dict) -> list[dict]:
    """Les éléments de cuisine que la lecture de CETTE photo range, avec leur rectangle sur la photo et leur boîte sur le plan :
    [{"sorte", "boite" (pixels), "centre", "n" (vers la pièce), "t" (le long du mur), "largeur", "profondeur", "haut", "mur"}]."""
    from moteur import rangees as rg
    from moteur.camera_photo import camera_depuis_dict

    cam = camera_depuis_dict(camera)
    toutes = rg.faces(logement)
    sortie = []
    for d in rangees_de_la_photo:
        f = rg.mur_designe(d["mur"], boites, cam, plan, logement, toutes)
        if f is None:
            continue
        L = float(np.linalg.norm(f["b"] - f["a"]))
        ranges = rg.ranger(d["suite"], L)
        if ranges is None:
            continue
        sens = rg.sens_de_l_image(f, cam)
        depart, e = (f["a"], (f["b"] - f["a"]) / L) if sens > 0 else (f["b"], (f["a"] - f["b"]) / L)
        n = np.asarray(f["normale"], float)
        for k, r in enumerate(ranges):
            vues = [boites[int(k)] for k in r["numeros"] if int(k) in boites]
            if not vues:
                continue
            profondeur, haut = rg.ELEMENTS[r["sorte"]]
            # un bord est SÛR (il se voit en entier) si l'élément est haut, ou s'il touche un élément haut de sa rangée ; le
            # bout d'un meuble bas, lui, est souvent caché (un îlot, des chaises devant) : son rectangle n'en montre qu'une part
            colle = lambda a, b: abs(a["fin"] - b["debut"]) < 1e-6  # noqa: E731
            surs = [r["sorte"] in HAUTS or (k > 0 and colle(ranges[k - 1], r) and ranges[k - 1]["sorte"] in HAUTS),
                    r["sorte"] in HAUTS or (k + 1 < len(ranges) and colle(r, ranges[k + 1]) and ranges[k + 1]["sorte"] in HAUTS)]
            sortie.append({"sorte": r["sorte"], "mur": (f["piece"], f["rang"]), "surs": surs,
                           "boite": [min(b[0] for b in vues), min(b[1] for b in vues), max(b[2] for b in vues), max(b[3] for b in vues)],
                           "centre": depart + e * (r["debut"] + r["fin"]) / 2 + n * (profondeur / 2 + rg.JEU_M), "n": n, "t": e,
                           "largeur": float(r["fin"] - r["debut"]), "profondeur": float(profondeur), "haut": float(haut)})
    return sortie


def _points(el: dict, par_arete: int = 7) -> np.ndarray:
    """Des points sur les douze arêtes de la boîte de l'élément (n, 3)."""
    c, n, t = el["centre"], el["n"], el["t"]
    coins = [np.array([*(c + a * el["largeur"] / 2 * t + b * el["profondeur"] / 2 * n), z])
             for a in (-1, 1) for b in (-1, 1) for z in (0.0, el["haut"])]
    s = np.linspace(0.0, 1.0, par_arete)[:, None]
    pts = [coins[i][None] * (1 - s) + coins[j][None] * s for i, j in _aretes_de_la_boite()]
    return np.concatenate(pts)


def _aretes_de_la_boite() -> list[tuple[int, int]]:
    """Les douze arêtes d'une boîte dont les coins sont numérotés a (2) × b (2) × z (2) : indice = 4a + 2b + z."""
    return [(i, i ^ bit) for i in range(8) for bit in (1, 2, 4) if i < i ^ bit]


def _ecarts(points: list[np.ndarray], els: list[dict], x: float, y: float, z: float, caps: np.ndarray, tangage: float, f: float,
            u0: float, v0: float, largeur: int, hauteur: int) -> tuple[np.ndarray, int]:
    """L'écart moyen (pixels, plafonné) entre les rectangles lus et les éléments vus par l'appareil, pour chaque cap de `caps`.
    Un bord SÛR (côté d'un élément haut ou de son voisin, dessus d'un meuble bas = le plan de travail) doit tomber sur le bord
    prévu ; les autres bords disent seulement « l'élément va au moins jusqu'ici » (le rectangle lu est sa partie visible).
    Rend aussi le nombre de bords sûrs qui ont servi."""
    import warnings

    c, s = np.cos(np.radians(caps))[:, None], np.sin(np.radians(caps))[:, None]
    ct, st = math.cos(math.radians(tangage)), math.sin(math.radians(tangage))
    total, poids, surs = np.zeros(len(caps)), 0.0, 0
    for P, el in zip(points, els):
        b = el["boite"]
        rx, ry, rz = (P[:, 0] - x)[None], (P[:, 1] - y)[None], (P[:, 2] - z)[None]
        avant = (rx * c + ry * s) * ct + rz * st
        droite = rx * s - ry * c
        haut = -(rx * c + ry * s) * st + rz * ct
        ok = avant > PRES_M
        with np.errstate(divide="ignore", invalid="ignore"):
            u = np.where(ok, u0 + f * droite / avant, np.nan)
            v = np.where(ok, v0 - f * haut / avant, np.nan)
        vu = ok.any(1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            g, dr, h, bas = np.nanmin(u, 1), np.nanmax(u, 1), np.nanmin(v, 1), np.nanmax(v, 1)
        dans = vu & (dr > 0) & (g < largeur) & (bas > 0) & (h < hauteur)
        g, dr, h, bas = np.clip(g, 0, largeur), np.clip(dr, 0, largeur), np.clip(h, 0, hauteur), np.clip(bas, 0, hauteur)
        grand = el["sorte"] in HAUTS
        #          prévu, lu, bord du cadre, sens (+1 : bord gauche ou haut), sûr ?, poids
        for prevu, lu, bord, sens, sur, w in ((g, b[0], 0.0, 1, el["surs"][0], 1.0), (dr, b[2], float(largeur), -1, el["surs"][1], 1.0),
                                              (h, b[1], 0.0, 1, not grand, POIDS_HAUTEUR), (bas, b[3], float(hauteur), -1, False, POIDS_HAUTEUR)):
            if abs(lu - bord) <= BORD_PX:  # coupé par le cadre : l'élément prévu doit sortir de la photo de ce côté
                e = np.maximum(0.0, sens * (prevu - bord) - BORD_PX)
            elif sur:
                e = np.abs(prevu - lu)
                surs += 1
            else:  # la partie visible : le rectangle lu ne doit pas dépasser de l'élément prévu
                e, w = np.maximum(0.0, sens * (prevu - lu) - DEPASSE_PX), w * POIDS_CONTIENT
            total += w * np.where(dans, np.minimum(e, PLAFOND_PX), PLAFOND_PX)
            poids += w
    return total / max(poids, 1e-9), surs


def _libre(x: float, y: float, logement: dict, pieces_permises: set, boites_au_sol: list) -> bool:
    """L'appareil peut-il se tenir ici : dans une pièce permise, à distance des murs, hors de tout élément rangé ?"""
    from moteur.sol_a_plat import piece_de

    p = piece_de((x, y), logement["pieces"])
    if p is None or p["id"] not in pieces_permises:
        return False
    q = np.array([x, y])
    for m in logement.get("murs", []):
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        ab = b - a
        s = float(np.clip((q - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0))
        if float(np.linalg.norm(q - (a + s * ab))) < float(m.get("epaisseur", 0.2)) / 2 + CONTACT_MUR_M:
            return False
    for c, n, t, demi_l, demi_p in boites_au_sol:
        r = q - c
        if abs(float(r @ t)) < demi_l + CONTACT_MEUBLE_M and abs(float(r @ n)) < demi_p + CONTACT_MEUBLE_M:
            return False
    return True


def _visibles(x: float, y: float, els: list[dict], plan: dict, logement: dict) -> bool:
    """Chaque élément se voit-il d'ici sans traverser un mur plein ?"""
    from moteur.photos_lues import premier_mur

    o = np.array([x, y])
    for el in els:
        cible = el["centre"] + el["n"] * (el["profondeur"] / 2)
        d = float(np.linalg.norm(cible - o))
        angle = math.degrees(math.atan2(cible[1] - o[1], cible[0] - o[0]))
        if premier_mur(plan, o, angle, pieces=logement["pieces"])[0] < d - CACHE_M:
            return False
    return True


def affiner(camera: dict, rangees_de_la_photo: list[dict], boites: dict[int, list[float]], largeur: int, hauteur: int, logement: dict,
            plan: dict | None = None, journal=lambda *_: None, lignes=None) -> dict | None:
    """L'appareil `camera` (x, y, z, cap, tangage, f, u0, v0) repris sur les éléments rangés de sa photo.
    Rend {"camera", "avant", "apres" (écart moyen aux rectangles, px), "elements", "bords", "garde", "raison", "vus"} ;
    None si la photo ne range aucun élément visible.
    lignes : fonction (appareil en 8 nombres) → écart en pixels aux LIGNES LUES des fenêtres de la photo (repères précis, qui
    fixent le zoom et la distance mais pas le glissement le long du mur) ; les deux écarts sont alors réduits ENSEMBLE."""
    from moteur import caler_photos as cp
    from moteur.sol_a_plat import piece_de

    if plan is None:
        plan = cp.plan_du_logement(logement)
        if len(plan["A"]):  # le regard passe les côtés sans mur, quel que soit l'interrupteur du calage
            plan = {**plan, "ouverte": (plan["voisine"] >= 0) & ~cp.faces_pleines(logement, plan)}
    cam = {k: float(camera[k]) for k in ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")}
    meilleur = None
    for tour in range(2):  # le mur que la lecture désigne dépend un peu de l'appareil : repris une fois avec l'appareil trouvé
        els = elements(rangees_de_la_photo, boites, cam if meilleur is None else meilleur["camera"], logement, plan)
        if not els:
            return meilleur
        if meilleur is not None and [e["mur"] for e in els] == meilleur["murs"]:
            break
        r = _chercher(cam, els, largeur, hauteur, logement, plan, lignes)
        r["murs"] = [e["mur"] for e in els]
        if meilleur is None or r["apres"] < meilleur["apres"]:
            meilleur = r
        else:
            break
    r = meilleur
    r["garde"], r["raison"] = True, ""
    if r["bords"] < BORDS_MIN:
        r["garde"], r["raison"] = False, f"{r['bords']} bord(s) sûr(s) seulement"
    elif r["apres"] > GARDE_PX:
        r["garde"], r["raison"] = False, f"colle encore mal ({r['apres']:.0f} px)"
    elif r["apres"] > GARDE_GAIN * r["avant"] or r["avant"] - r["apres"] < GAIN_MIN_PX:
        r["garde"], r["raison"] = False, "pas nettement mieux que le calage"
    journal(f"appareil sur les rangées : {r['elements']} élément(s), écart {r['avant']:.0f} → {r['apres']:.0f} px"
            + ("" if r["garde"] else f" (non gardé : {r['raison']})"))
    return r


POIDS_LIGNES = 3.0  # un pixel d'écart aux lignes lues (justes à quelques pixels) pèse comme trois pixels aux meubles (à ~30 px)


def _chercher(cam: dict, els: list[dict], largeur: int, hauteur: int, logement: dict, plan: dict, lignes=None) -> dict:
    from moteur import caler_photos as cp
    from moteur.sol_a_plat import piece_de

    points = [_points(e) for e in els]
    lus = els
    args = (cam["u0"], cam["v0"], largeur, hauteur)
    avant, bords = _ecarts(points, lus, cam["x"], cam["y"], cam["z"], np.array([cam["cap"]]), cam["tangage"], cam["f"], *args)
    ouverts = cp.espaces_ouverts(logement, plan)
    permises = set()
    for e in els:
        permises |= ouverts.get(e["mur"][0], {e["mur"][0]})
    ici = piece_de((cam["x"], cam["y"]), logement["pieces"])
    if ici is not None:
        permises.add(ici["id"])
    au_sol = [(e["centre"], e["n"], e["t"], e["largeur"] / 2, e["profondeur"] / 2) for e in els]
    caps = cam["cap"] + np.arange(-TOUR_DEG, TOUR_DEG + 1e-6, PAS_DEG)
    candidats = []
    for dx in np.arange(-RAYON_M, RAYON_M + 1e-6, PAS_M):
        for dy in np.arange(-RAYON_M, RAYON_M + 1e-6, PAS_M):
            if math.hypot(dx, dy) > RAYON_M or not _libre(cam["x"] + dx, cam["y"] + dy, logement, permises, au_sol):
                continue
            x, y = cam["x"] + dx, cam["y"] + dy
            e, _ = _ecarts(points, lus, x, y, cam["z"], caps, cam["tangage"], cam["f"], *args)
            e = e + RAPPEL_PX_PAR_DEG * np.abs(caps - cam["cap"])
            k = int(e.argmin())
            candidats.append((float(e[k]) + RAPPEL_PX_PAR_M * math.hypot(dx, dy), x, y, float(caps[k])))
    candidats.sort()
    def aux_lignes(x, y, cap, f):
        return 0.0 if lignes is None else POIDS_LIGNES * float(lignes([x, y, cam["z"], cap, cam["tangage"], f, cam["u0"], cam["v0"]]))

    meilleur = (float(avant[0]) + aux_lignes(cam["x"], cam["y"], cam["cap"], cam["f"]), cam["x"], cam["y"], cam["cap"], cam["f"])
    essayes = 0
    for _, x0, y0, c0 in candidats:
        if essayes >= 6:
            break
        if not _visibles(x0, y0, els, plan, logement):
            continue
        essayes += 1
        fins = c0 + np.arange(-2.0, 2.0 + 1e-6, 0.5)
        fins = fins[np.abs(fins - cam["cap"]) <= TOUR_DEG + 1e-6]
        for dx in np.arange(-0.12, 0.12 + 1e-6, 0.02):
            for dy in np.arange(-0.12, 0.12 + 1e-6, 0.02):
                x, y = x0 + dx, y0 + dy
                if not _libre(x, y, logement, permises, au_sol):
                    continue
                for zoom in ZOOMS:
                    e, _ = _ecarts(points, lus, x, y, cam["z"], fins, cam["tangage"], cam["f"] * zoom, *args)
                    e = e + RAPPEL_PX_PAR_DEG * np.abs(fins - cam["cap"])
                    if lignes is not None:
                        e = e + np.array([aux_lignes(x, y, c, cam["f"] * zoom) for c in fins])
                    k = int(e.argmin())
                    note = float(e[k]) + RAPPEL_PX_PAR_M * math.hypot(x - cam["x"], y - cam["y"]) + RAPPEL_ZOOM_PX * abs(zoom - 1.0)
                    if note < meilleur[0] and _visibles(x, y, els, plan, logement):
                        meilleur = (note, x, y, float(fins[k]), cam["f"] * zoom)
    _, x, y, cap, f = meilleur
    apres, _ = _ecarts(points, lus, x, y, cam["z"], np.array([cap]), cam["tangage"], f, *args)
    nouvelle = {**cam, "x": round(x, 3), "y": round(y, 3), "cap": round((cap + 180.0) % 360.0 - 180.0, 2), "f": round(f, 2)}
    return {"camera": nouvelle, "avant": float(avant[0]), "apres": float(apres[0]), "elements": len(els), "bords": bords,
            "lignes": None if lignes is None else [aux_lignes(cam["x"], cam["y"], cam["cap"], cam["f"]) / POIDS_LIGNES, aux_lignes(x, y, cap, f) / POIDS_LIGNES],
            "vus": [{"sorte": e["sorte"], "boite": [float(v) for v in e["boite"]], "points": p} for e, p in zip(els, points)]}


def prevu(points: np.ndarray, camera: dict, largeur: int, hauteur: int) -> list[float] | None:
    """Le rectangle où l'appareil voit ces points (pixels, coupé au cadre) ; None s'il ne les voit pas."""
    from moteur.camera_photo import camera_depuis_dict, projeter

    cam = camera_depuis_dict(camera)
    uv = [projeter(p, cam) for p in points]
    uv = [(u, v) for u, v, d in uv if d > PRES_M]
    if not uv:
        return None
    u, v = np.array(uv).T
    if u.max() < 0 or u.min() > largeur or v.max() < 0 or v.min() > hauteur:
        return None
    return [float(np.clip(u.min(), 0, largeur)), float(np.clip(v.min(), 0, hauteur)), float(np.clip(u.max(), 0, largeur)),
            float(np.clip(v.max(), 0, hauteur))]


def dessiner(image: np.ndarray, avant: dict, apres: dict, vus: list[dict], sortie) -> None:
    """Contrôle à l'œil : sur la photo, le rectangle LU de chaque élément (vert), celui que voit l'appareil du calage (rouge)
    et celui que voit l'appareil repris (bleu)."""
    import cv2

    from moteur.images import ecrire_image

    img = image.copy()
    hauteur, largeur = img.shape[:2]
    for v in vus:
        x0, y0, x1, y1 = (int(round(c)) for c in v["boite"])
        cv2.rectangle(img, (x0, y0), (x1, y1), (60, 200, 60), 3)
        for cam, couleur in ((avant, (40, 40, 230)), (apres, (230, 120, 30))):
            r = prevu(v["points"], cam, largeur, hauteur)
            if r is not None:
                cv2.rectangle(img, (int(r[0]), int(r[1])), (int(r[2]), int(r[3])), couleur, 2)
    ecrire_image(sortie, img)
