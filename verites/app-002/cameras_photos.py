r"""app-002 : CORRIGÉ SOIGNÉ de la place des photos (15/11/2026), relevé à la main par Claude
→ verites/app-002/cameras-photos-soigne.json. L'ancien relevé (cameras-photos.json, 10/11/2026, zoom ajusté à la main photo
par photo) reste en place : les vérités des sols et des meubles et les notes connues s'appuient dessus.

Pourquoi : savoir si la variante « fin » du calage (zoom par les lignes de fuite) place mieux ou moins bien les photos que la
chaîne en service ; l'ancien relevé ne pouvait pas le dire (son zoom, libre, allait de 554 à 669 px selon la photo).

Méthode (celle de verites/app-003/cameras_photos.py, avec deux ajouts) :
  - repères lus sur des agrandissements ×2 quadrillés (pixels de la photo, 1206 px de large) ;
  - ANCRES = éléments du plan retrouvés sans doute sur la photo (angles de murs, montants de portes et de baies) ;
  - repères LIBRES = objets fixés au mur vus sur plusieurs photos (appliques, tableau, radiateur, interrupteur) : ils glissent
    le long de leur mur, leur place est calculée avec les caméras (calcul d'ensemble) ;
  - ZOOM commun : 545 px (médiane des 5 photos au zoom net par les lignes de fuite : 533 à 555) ;
  - ajout 1 : l'ORIENTATION n'est pas reprise telle quelle des lignes de fuite automatiques (fausses de 9 à 17° sur les
    chambres 10 et 14, où une seule famille de lignes est vue) ; elle est calculée, à partir des ancres et de FUYANTES
    (corniches, plinthes, hauts de baies : arêtes horizontales parallèles à un mur) désignées à la main, puis mesurées au
    dixième de pixel par le détecteur de segments (`affiner_fuyantes`) ;
  - ajout 2 : la ligne d'horizon (v0) est libre (photos recadrées en hauteur), rappelée mollement vers le milieu ;
  - incertitude de chaque caméra : calcul refait 150 fois en bougeant au hasard les pixels lus (± 3 px), les ancres du plan
    (± 12 cm) et le zoom (± 12 px) ; pour le séjour, le plan est en plus étiré au hasard de 0 à 5 % du nord au sud (le plan
    relevé fait 4,28 m, ses cotes écrites disent 4,50 m, et les photos préfèrent ~5 % de plus).

    ..\atelya\.venv\Scripts\python.exe verites\app-002\cameras_photos.py [--images ..\atelya\b2\app-002\corrige] [--zoom-libre]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur.camera_photo import projeter  # noqa: E402

ICI = Path(__file__).resolve().parent
PHOTOS = "../atelya/photos-clients/app-002/photos"
HSP = 2.50
LARGEUR = 1206
F = 545.0  # focale commune (pixels), médiane des lignes de fuite nettes

# Observations : ("v", repère, u, v haut, v bas) arête verticale ; ("s", repère, u, v) pied au sol ;
# ("d", "x" ou "y", (u, v), (u, v), quoi) fuyante = arête horizontale parallèle à l'axe ; ("l", A, B, (u, v), (u, v), quoi) pied
# de mur entre deux repères. Libres : (x, y, axe fixé) ; "y" = l'objet est sur un mur à y constant, il ne glisse qu'en x.
GROUPES = {
    "séjour": {
        "piece": "sejour_1",
        "etirement": (6.95, 1.05),  # le plan relevé fait 4,28 m du nord au sud, ses cotes écrites disent 4,50 : doute compté dans l'incertitude
        "ancres": {
            "NW": (1.23, 6.95), "NE": (6.40, 6.95), "TE": (6.40, 4.69), "SW": (1.23, 2.67), "SEc": (6.45, 2.67),
            "PEW": (5.14, 6.95), "PEE": (6.28, 6.95),  # porte vers l'entrée
            "BSW": (2.25, 2.67), "BSE": (5.81, 2.67),  # baie sud
            "BWS": (1.23, 4.20), "BWN": (1.23, 6.58),  # baie ouest
            "C1NE": (9.75, 4.69), "C1SE": (9.75, 0.0), "B1E": (9.25, 0.0), "B1W": (6.89, 0.0),  # coin salon (ancienne chambre 1)
        },
        "libres": {
            "L1": (2.6, 6.85, "y"), "L2": (4.2, 6.85, "y"), "INT": (4.9, 6.95, "y"),
            "RL": (1.5, 6.85, "y"), "RR": (2.0, 6.85, "y"),
            "TN": (6.40, 6.1, "x"), "TS": (6.40, 5.5, "x"),
        },
        "photos": {
            "photo-01": {"depart": (2.0, 2.8, 50), "obs": [
                ("v", "PEW", 580, 262, 400), ("v", "PEE", 663, 262, 400), ("v", "NE", 681, 215, 495), ("v", "TE", 886, 190, 495),
                ("v", "C1NE", 1014, 215, 235), ("v", "L1", 282, 215, 255), ("v", "L2", 503, 240, 275), ("v", "INT", 566, 335, 350),
                ("v", "TN", 740, 240, 315), ("v", "TS", 792, 240, 315), ("v", "RL", 28, 395, 545), ("v", "RR", 137, 395, 545),
                ("s", "TE", 886, 501),
                ("d", "x", (50, 117), (625, 200), "corniche du mur du buffet"), ("d", "x", (20, 552), (225, 540), "pied du mur du buffet"),
                ("d", "y", (681, 197), (886, 167), "corniche du mur du tableau"), ("d", "x", (886, 170), (1013, 220), "corniche du fond du coin salon"),
                ("d", "y", (1013, 220), (1206, 197), "corniche du mur est")]},
            "photo-03": {"depart": (1.8, 6.6, -40), "obs": [
                ("v", "TE", 404, 215, 515), ("v", "SEc", 606, 240, 435), ("v", "BSE", 658, 265, 440), ("v", "BSW", 1165, 180, 553),
                ("v", "TN", 194, 225, 335), ("v", "TS", 291, 225, 335),
                ("s", "TE", 404, 519),
                ("d", "y", (20, 117), (415, 205), "corniche du mur du tableau"), ("d", "y", (85, 567), (400, 520), "pied du mur du tableau"),
                ("d", "x", (611, 265), (1206, 115), "corniche du mur de la baie sud"), ("d", "x", (666, 280), (1156, 180), "haut de la baie sud")]},
            "photo-04": {"depart": (3.0, 2.5, 91), "obs": [
                ("v", "BWN", 350, 240, 520), ("v", "NW", 372, 240, 520), ("v", "PEW", 826, 290, 480), ("v", "PEE", 968, 290, 480),
                ("v", "NE", 987, 230, 525), ("v", "L1", 542, 290, 320), ("v", "L2", 731, 290, 320), ("v", "INT", 812.5, 380, 390),
                ("v", "TN", 1073.5, 240, 350), ("v", "TS", 1156, 230, 345), ("v", "RL", 376, 420, 515), ("v", "RR", 440, 420, 515),
                ("s", "NE", 987, 531), ("s", "NW", 372, 524),
                ("d", "x", (380, 232), (980, 232), "corniche du mur du buffet"), ("d", "y", (50, 50), (360, 225), "corniche du mur de la baie ouest"),
                ("d", "y", (0, 697), (350, 527), "pied de la baie ouest"), ("d", "y", (986, 227), (1206, 122), "corniche du mur du tableau")]},
            "photo-05": {"depart": (7.0, 2.8, 150), "obs": [
                ("v", "SW", 259, 220, 495), ("v", "BWS", 443, 275, 470), ("v", "BWN", 630, 280, 450), ("v", "NW", 671.5, 270, 480),
                ("v", "PEW", 1016, 230, 520), ("v", "L1", 753.5, 285, 310), ("v", "L2", 898.5, 255, 285), ("v", "INT", 996, 345, 360),
                ("s", "SW", 259, 497),
                ("d", "x", (731, 250), (1206, 102), "corniche du mur du buffet"), ("d", "x", (951, 505), (1031, 522), "pied du mur du buffet"),
                ("d", "y", (265, 495), (435, 477), "pied du mur ouest")]},
            "photo-07": {"depart": (7.8, 0.5, 90), "obs": [
                ("v", "SEc", 200, 20, 290), ("v", "PEW", 380, 285, 400), ("v", "TE", 415, 180, 495), ("v", "C1NE", 845, 165, 180),
                ("v", "L2", 312, 290, 305), ("v", "INT", 367.5, 340, 350),
                ("s", "TE", 415, 500),
                ("d", "x", (410, 172), (840, 172), "corniche du fond du coin salon"), ("d", "y", (846, 165), (991, 15), "corniche du mur est"),
                ("d", "x", (202, 245), (412, 245), "corniche du mur du buffet (au loin)")]},
            "photo-06": {"depart": (7.5, 3.5, -40), "obs": [
                ("v", "C1NE", 47, 60, 400), ("v", "C1SE", 751, 250, 505), ("v", "B1E", 801, 285, 500),  # bord ouest de la baie caché par l'armoire blanche
                ("s", "C1SE", 751, 505),
                ("d", "y", (55, 30), (751, 245), "corniche du mur est"), ("d", "x", (761, 247), (1116, 197), "corniche du mur de la baie"),
                ("d", "x", (751, 505), (1016, 542), "pied du mur de la baie"), ("d", "x", (801, 282), (1111, 242), "haut de la baie")]},
        },
    },
    "chambre du milieu": {
        "piece": "chambre_1",
        "ancres": {"SE": (12.47, 0.0), "SW": (9.89, 0.0), "BE": (11.98, 0.0), "BW": (10.03, 0.0), "NWc": (9.89, 4.75)},
        "libres": {},
        "photos": {
            "photo-10": {"depart": (12.0, 4.0, -122), "obs": [
                ("v", "SE", 186, 150, 540), ("v", "BE", 267.5, 225, 520), ("v", "BW", 550, 240, 420), ("v", "SW", 570, 225, 420),
                ("d", "y", (601, 215), (996, 10), "corniche du mur ouest"), ("d", "y", (981, 660), (1206, 750), "plinthe du mur ouest"),
                ("d", "y", (186, 150), (155, 50), "corniche du mur est"), ("d", "x", (240, 165), (565, 220), "corniche du mur de la baie"),
                ("d", "x", (291, 247), (537, 262), "haut de la baie"),
                ("l", "SW", "NWc", (981, 692), (1156, 770), "pied du mur ouest")]},
        },
    },
    "chambre du fond": {
        "piece": "chambre_2",
        "ancres": {"SE": (15.20, 0.0), "SW": (12.64, 0.0), "BE": (14.72, 0.0), "BW": (12.77, 0.0), "NWc": (12.64, 4.75)},
        "libres": {},
        "photos": {
            "photo-14": {"depart": (13.1, 4.0, -57), "obs": [
                ("v", "SE", 651, 215, 480), ("v", "BE", 716, 245, 490), ("v", "BW", 1009, 215, 515), ("v", "SW", 1047, 150, 540),
                ("d", "y", (350, 45), (640, 200), "corniche du mur est"), ("d", "y", (0, 710), (165, 652), "plinthe du mur est"),
                ("d", "x", (651, 217), (1041, 155), "corniche du mur de la baie"), ("d", "x", (716, 247), (976, 227), "haut de la baie"),
                ("l", "SW", "NWc", (1071, 607), (1166, 780), "pied du mur ouest")]},
            "photo-15": {"depart": (14.9, 4.0, -122), "obs": [
                ("v", "SE", 150, 100, 500), ("v", "BE", 258, 190, 500), ("v", "BW", 542.5, 205, 485), ("v", "SW", 570, 195, 470),
                ("d", "y", (566, 197), (916, 10), "corniche du mur ouest"), ("d", "y", (971, 609), (1206, 700), "plinthe du mur ouest"),
                ("d", "x", (150, 100), (570, 195), "corniche du mur de la baie"), ("d", "x", (265, 200), (527, 232), "haut de la baie"),
                ("l", "SW", "NWc", (976, 645), (1206, 750), "pied du mur ouest")]},
        },
    },
}
QUOI = {
    "NW": "angle nord-ouest", "NE": "angle nord-est", "TE": "bout du mur du tableau", "SW": "angle sud-ouest", "SE": "angle sud-est",
    "SEc": "angle saillant baie sud / coin salon", "PEW": "porte de l'entrée, bord ouest", "PEE": "porte de l'entrée, bord est",
    "BSW": "baie sud, bord ouest", "BSE": "baie sud, bord est", "BWS": "baie ouest, bord sud", "BWN": "baie ouest, bord nord",
    "C1NE": "coin salon, angle nord-est", "C1SE": "coin salon, angle sud-est", "B1E": "baie du coin salon, bord est",
    "B1W": "baie du coin salon, bord ouest", "L1": "applique ouest", "L2": "applique est", "INT": "interrupteur près de la porte",
    "RL": "radiateur, bord ouest", "RR": "radiateur, bord est", "TN": "tableau, bord nord", "TS": "tableau, bord sud",
    "BE": "baie, bord est", "BW": "baie, bord ouest", "NWc": "angle nord-ouest",
}
def affiner_fuyantes(groupe, dossier):
    """Chaque fuyante relevée à la main est remplacée par les segments que l'ordinateur trouve au même endroit de la photo
    (détecteur de segments d'OpenCV : au dixième de pixel, bien mieux que l'œil sur un agrandissement). La main dit seulement
    QUELLE arête c'est (parallèle à quel mur) ; sans segment trouvé, la lecture à la main reste."""
    import cv2

    from moteur.fuites import segments
    from moteur.images import lire_image

    for nom, d in groupe["photos"].items():
        seg = segments(cv2.cvtColor(lire_image(dossier / f"{nom}.jpg"), cv2.COLOR_BGR2RGB), mini=40.0)
        obs = []
        for o in d["obs"]:
            if o[0] != "d":
                obs.append(o)
                continue
            p1, p2 = np.array(o[2], float), np.array(o[3], float)
            t = (p2 - p1) / (np.linalg.norm(p2 - p1) + 1e-12)
            trouves = []
            for x0, y0, x1, y1 in seg:
                a, b = np.array([x0, y0], float), np.array([x1, y1], float)
                u = (b - a) / (np.linalg.norm(b - a) + 1e-12)
                m = (a + b) / 2
                le_long = float((m - p1) @ t)
                if abs(u[0] * t[1] - u[1] * t[0]) < math.sin(math.radians(4.0)) and abs(float((m - p1) @ np.array([-t[1], t[0]]))) < 9.0                         and -10.0 < le_long < np.linalg.norm(p2 - p1) + 10.0:
                    trouves.append(("d", o[1], (float(x0), float(y0)), (float(x1), float(y1)), o[4], "auto"))
            obs += trouves or [o]
        d["obs"] = obs


NP = 5  # inconnues par photo : x, y, z, cap, v0 (+ f en dernier si --zoom-libre)


def _cam(p, f=F):
    return [p[0], p[1], p[2], p[3], 0.0, f, LARGEUR / 2, p[4]]


def _fuyante(cam, axe, p1, p2):
    """Écart (pixels, au bout du segment) entre un segment de la photo et la direction du point de fuite de l'axe."""
    _, _, _, cap, _, f, u0, v0 = cam
    c, s = math.cos(math.radians(cap)), math.sin(math.radians(cap))
    dx, dy = (1.0, 0.0) if axe == "x" else (0.0, 1.0)
    a, b = dx * c + dy * s, dx * s - dy * c  # parts de l'axe le long de la visée et vers la droite
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    w = np.array([f * b + (u0 - mx) * a, (v0 - my) * a])
    w = w / (np.linalg.norm(w) + 1e-12)
    t = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    demi = np.linalg.norm(t) / 2
    t = t / (2 * demi + 1e-12)
    return float(t[0] * w[1] - t[1] * w[0]) * demi


def _lieux(vecteur, groupe, ancres, np_):
    lieux = dict(ancres)
    base = np_ * len(groupe["photos"])
    for i, (nom, (x, y, axe)) in enumerate(groupe["libres"].items()):
        lieux[nom] = (vecteur[base + i], y) if axe == "y" else (x, vecteur[base + i])
    return lieux


def _ecarts(vecteur, groupe, hauteurs, ancres, f=F, zoom_libre=False):
    np_ = NP + (1 if zoom_libre else 0)
    lieux = _lieux(vecteur, groupe, ancres, np_)
    r = []
    for k, nom in enumerate(groupe["photos"]):
        p = vecteur[np_ * k: np_ * (k + 1)]
        cam = _cam(p, p[5] if zoom_libre else f)
        r.append((p[4] - hauteurs[nom] / 2) * 0.15)  # horizon rappelé vers le milieu de la photo
        r.append((p[2] - 1.2) * 4.0)                 # hauteur de l'appareil rappelée vers 1,2 m
        for o in groupe["photos"][nom]["obs"]:
            if o[0] == "v":
                u, _, prof = projeter((*lieux[o[1]], 1.0), cam)
                r.append(o[2] - u if prof > 0.05 else 500.0)
            elif o[0] == "s":
                u, v, prof = projeter((*lieux[o[1]], 0.0), cam)
                r += [o[2] - u, o[3] - v] if prof > 0.05 else [500.0, 500.0]
            elif o[0] == "d":
                r.append(_fuyante(cam, o[1], o[2], o[3]))
            else:
                a, b = np.array([*lieux[o[1]], 0.0]), np.array([*lieux[o[2]], 0.0])
                (ua, va, pa), (ub, vb, pb) = projeter(a, cam), projeter(b, cam)
                if pa < 0.05 or pb < 0.05:  # un bout derrière l'appareil : on le ramène devant, le long du mur
                    if pa < 0.05 and pb < 0.05:
                        r += [500.0, 500.0]
                        continue
                    if pa < 0.05:
                        a = a + (b - a) * (0.3 - pa) / (pb - pa)
                    else:
                        b = b + (a - b) * (0.3 - pb) / (pa - pb)
                    (ua, va, _), (ub, vb, _) = projeter(a, cam), projeter(b, cam)
                n = np.array([vb - va, -(ub - ua)])
                n = n / (np.linalg.norm(n) + 1e-12)
                r += [float(n @ np.array([q[0] - ua, q[1] - va])) for q in (o[3], o[4])]
    return np.array(r)


def _resoudre(vecteur, fonction, tours=200):
    """Moindres carrés (Levenberg-Marquardt, dérivées numériques)."""
    v = np.array(vecteur, float)
    r = fonction(v)
    cout, lam = float(r @ r), 1e-2
    for _ in range(tours):
        J = np.zeros((len(r), len(v)))
        for j in range(len(v)):
            h = 1e-4 * max(1.0, abs(v[j]))
            w = v.copy()
            w[j] += h
            J[:, j] = (fonction(w) - r) / h
        A, g = J.T @ J, J.T @ r
        bouge, gain = False, 0.0
        while lam < 1e9:
            pas = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            r2 = fonction(v + pas)
            if float(r2 @ r2) < cout:
                gain = cout - float(r2 @ r2)
                v, r, cout, lam, bouge = v + pas, r2, float(r2 @ r2), max(lam / 3, 1e-8), True
                break
            lam *= 4
        if not bouge or gain < 1e-9:
            break
    return v, r


def _depart(groupe, hauteurs, decalage=0.0, alea=None, zoom_libre=False):
    v = []
    for nom, d in groupe["photos"].items():
        x, y, cap = d["depart"]
        if alea is not None:
            x, y, cap = x + alea.normal(0, decalage), y + alea.normal(0, decalage), cap + alea.normal(0, 4.0)
        v += [x, y, 1.2, cap, hauteurs[nom] / 2] + ([F] if zoom_libre else [])
    for x, y, axe in groupe["libres"].values():
        v.append(x if axe == "y" else y)
    return np.array(v, float)


def caler_groupe(groupe, hauteurs, tirages=150, px=3.0, m=0.12, df=12.0, zoom_libre=False):
    """Caméras du groupe + places des repères libres + incertitude de chaque caméra."""
    ancres = groupe["ancres"]
    f = lambda w: _ecarts(w, groupe, hauteurs, ancres, zoom_libre=zoom_libre)  # noqa: E731
    v, r = _resoudre(_depart(groupe, hauteurs, zoom_libre=zoom_libre), f)
    alea = np.random.default_rng(0)
    autres = []
    for _ in range(8):  # le résultat dépend-il du point de départ ? (départs bougés de 0,6 m et 4°)
        w, rw = _resoudre(_depart(groupe, hauteurs, 0.6, alea, zoom_libre), f)
        autres.append(float(rw @ rw))
        if float(rw @ rw) < float(r @ r) - 1e-6:
            v, r = w, rw
    stables = sum(1 for c in autres if abs(c - float(r @ r)) < 1e-3 * max(1.0, float(r @ r)))
    np_ = NP + (1 if zoom_libre else 0)
    tires = []
    for _ in range(tirages if not zoom_libre else 0):
        g2 = json.loads(json.dumps(groupe))
        for d in g2["photos"].values():
            for o in d["obs"]:
                if o[0] in "vs":
                    o[2] += alea.normal(0, px)
                if o[0] == "s":
                    o[3] += alea.normal(0, px)
                if o[0] == "d":
                    bruit = 1.0 if len(o) > 5 else px  # segment trouvé par l'ordinateur : ± 1 px
                    for q in (2, 3):
                        o[q] = [o[q][0] + alea.normal(0, bruit), o[q][1] + alea.normal(0, bruit)]
                if o[0] == "l":
                    for q in (3, 4):
                        o[q] = [o[q][0] + alea.normal(0, px), o[q][1] + alea.normal(0, px)]
        y_ref, s_max = groupe.get("etirement", (0.0, 1.0))
        s = alea.uniform(1.0, s_max)
        a2 = {k: (xy[0] + alea.normal(0, m), y_ref + (xy[1] - y_ref) * s + alea.normal(0, m)) for k, xy in ancres.items()}
        f2 = F + alea.normal(0, df)
        w, _ = _resoudre(v, lambda q: _ecarts(q, g2, hauteurs, a2, f2), tours=40)
        tires.append(w)
    tires = np.array(tires) if tires else np.zeros((0, len(v)))
    incert = {}
    for k, nom in enumerate(groupe["photos"]):
        if len(tires):
            d = np.hypot(tires[:, np_ * k] - v[np_ * k], tires[:, np_ * k + 1] - v[np_ * k + 1])
            dc = np.abs(tires[:, np_ * k + 3] - v[np_ * k + 3])
            incert[nom] = (float(np.percentile(d, 68)), float(np.percentile(dc, 68)))
        else:
            incert[nom] = (0.0, 0.0)
    return v, _lieux(v, groupe, ancres, np_), incert, stables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", help="dossier où dessiner le contrôle (arêtes du plan et repères sur chaque photo)")
    parser.add_argument("--sans-ecrire", action="store_true")
    parser.add_argument("--tirages", type=int, default=150)
    parser.add_argument("--zoom-libre", action="store_true", help="contrôle : le zoom de chaque photo est calculé aussi (rien n'est écrit)")
    args = parser.parse_args()
    from PIL import Image, ImageDraw

    logement = json.loads((ICI / "logement.json").read_text(encoding="utf-8"))
    dossier = RACINE / PHOTOS
    if not dossier.is_dir():
        sys.exit(f"PLANTÉ : dossier des photos introuvable ({PHOTOS})")
    np_ = NP + (1 if args.zoom_libre else 0)
    cameras, libres_trouves = {}, {}
    for titre, groupe in GROUPES.items():
        tailles = {nom: Image.open(dossier / f"{nom}.jpg").size for nom in groupe["photos"]}
        hauteurs = {nom: t[1] for nom, t in tailles.items()}
        affiner_fuyantes(groupe, dossier)
        v, lieux, incert, stables = caler_groupe(groupe, hauteurs, args.tirages, zoom_libre=args.zoom_libre)
        print(f"\n== {titre} == (même résultat depuis {stables} départs sur 8)")
        for nom, (x0, y0, _) in groupe["libres"].items():
            libres_trouves[f"{groupe['piece']}:{nom}"] = {"quoi": QUOI[nom], "x": round(float(lieux[nom][0]), 2), "y": round(float(lieux[nom][1]), 2)}
            print(f"   repère libre {nom:4s} {QUOI[nom]:32s} trouvé en ({lieux[nom][0]:6.2f}, {lieux[nom][1]:6.2f})   départ ({x0:.2f}, {y0:.2f})")
        for k, nom in enumerate(groupe["photos"]):
            p = v[np_ * k: np_ * (k + 1)]
            f = float(p[5]) if args.zoom_libre else F
            cam = _cam(p, f)
            reperes, fuyantes, ecarts = [], [], []
            for o in groupe["photos"][nom]["obs"]:
                libre = {"libre": True} if (o[0] in "vs" and o[1] in groupe["libres"]) else {}
                if o[0] == "v":
                    x, y = (float(q) for q in lieux[o[1]])
                    e = [o[2] - projeter((x, y, 1.0), cam)[0]]
                    reperes.append({"type": "ligne", "a": [round(x, 3), round(y, 3), 0.0], "b": [round(x, 3), round(y, 3), HSP],
                                    "p1": [o[2], o[3]], "p2": [o[2], o[4]], "quoi": QUOI[o[1]], **libre})
                elif o[0] == "s":
                    x, y = (float(q) for q in lieux[o[1]])
                    u, w, _ = projeter((x, y, 0.0), cam)
                    e = [o[2] - u, o[3] - w]
                    reperes.append({"type": "point", "p": [round(x, 3), round(y, 3), 0.0], "uv": [o[2], o[3]], "quoi": "pied : " + QUOI[o[1]], **libre})
                elif o[0] == "d":
                    e = [_fuyante(cam, o[1], o[2], o[3])]
                    fuyantes.append({"axe": o[1], "p1": [round(q, 1) for q in o[2]], "p2": [round(q, 1) for q in o[3]], "quoi": o[4],
                                     "source": "ordinateur" if len(o) > 5 else "main", "ecart_px": round(abs(e[0]), 1)})
                    ecarts += [abs(float(q)) for q in e]
                    continue
                else:
                    from moteur.camera_photo import residus

                    a, b = lieux[o[1]], lieux[o[2]]
                    reperes.append({"type": "ligne", "a": [a[0], a[1], 0.0], "b": [b[0], b[1], 0.0], "p1": list(o[3]), "p2": list(o[4]), "quoi": o[5]})
                    e = list(residus(cam, reperes[-1:]))
                reperes[-1]["ecart_px"] = round(float(np.abs(e).max()), 1)
                ecarts += [abs(float(q)) for q in e]
            dm, dcap = incert[nom]
            moyen, pire = float(np.mean(ecarts)), float(np.max(ecarts))
            qualite = "bonne" if dm <= 0.20 and moyen <= 5 else "moyenne" if dm <= 0.30 and moyen <= 8 else "approchée"
            cameras[nom] = {
                "camera": {"x": round(float(p[0]), 3), "y": round(float(p[1]), 3), "z": round(float(p[2]), 3),
                           "cap": round(float((p[3] + 180) % 360 - 180), 2), "tangage": 0.0, "f": round(f, 1),
                           "u0": LARGEUR / 2, "v0": round(float(p[4]), 1)},
                "largeur": tailles[nom][0], "hauteur": tailles[nom][1], "piece": groupe["piece"], "qualite": qualite,
                "ecart_moyen_px": round(moyen, 1), "ecart_pire_px": round(pire, 1), "incertitude_m": round(dm, 2),
                "incertitude_cap_deg": round(dcap, 1), "reperes": reperes, "fuyantes": fuyantes,
            }
            c = cameras[nom]["camera"]
            print(f"{nom} x={c['x']:6.2f} y={c['y']:6.2f} z={c['z']:4.2f} cap={c['cap']:7.1f} f={c['f']:5.0f} horizon={c['v0']:5.0f} (milieu {hauteurs[nom] / 2:.0f})"
                  f" | écart {moyen:4.1f} px (pire {pire:4.1f}) | ± {dm:.2f} m, ± {dcap:.1f}° | {qualite}")
            print("      " + "  ".join(f"{r['quoi'][:20]}{'*' if r.get('libre') else ''}:{r['ecart_px']:.0f}" for r in reperes))
            print("      fuyantes " + "  ".join(f"{r['quoi'][:24]}{'' if r['source'] == 'main' else '°'}:{r['ecart_px']:.1f}" for r in fuyantes))
            if args.images:
                from outils.habillage.caler_photos import dessiner

                sortie = Path(args.images)
                sortie.mkdir(parents=True, exist_ok=True)
                dessiner(dossier / f"{nom}.jpg", cam, logement, sortie / f"controle-{nom}.png", [], {groupe["piece"]})
                image = Image.open(sortie / f"controle-{nom}.png")
                trait = ImageDraw.Draw(image)
                for r in reperes:  # rouge = lu sur la photo ; vert (ancre) ou orange (libre) = où le calcul le met
                    if r["type"] == "ligne" and r["a"][:2] == r["b"][:2]:
                        u = projeter((r["a"][0], r["a"][1], 1.0), cam)[0]
                        trait.line([(r["p1"][0], r["p1"][1]), (r["p2"][0], r["p2"][1])], fill=(255, 0, 0), width=3)
                        trait.line([(u, r["p1"][1] - 12), (u, r["p2"][1] + 12)], fill=(255, 150, 0) if r.get("libre") else (0, 220, 0), width=1)
                for r in fuyantes:
                    trait.line([tuple(r["p1"]), tuple(r["p2"])], fill=(255, 0, 255), width=2)
                image.save(sortie / f"controle-{nom}.png")
    if not args.sans_ecrire and not args.zoom_libre:
        fiche = {
            "note": "Corrigé SOIGNÉ de la place des photos d'app-002 (15/11/2026), relevé à la main par Claude : repères lus sur des "
                    "agrandissements quadrillés ; ancres = éléments sûrs du plan ; repères « libre » = objets fixés au mur vus sur plusieurs "
                    "photos, place calculée avec les caméras (calcul d'ensemble par pièce) ; zoom commun 545 px (lignes de fuite nettes de 5 "
                    "photos) ; orientation calculée d'après les ancres et des fuyantes relevées à la main ; « incertitude_m » = de combien la "
                    "caméra bouge quand on bouge les lectures de ± 3 px, les ancres de ± 12 cm et le zoom de ± 12 px. L'ancien relevé "
                    "(cameras-photos.json) reste la référence des vérités sols / meubles. Produit par verites/app-002/cameras_photos.py.",
            "photos": PHOTOS, "fichier": "{nom}.jpg", "cameras": cameras, "reperes_libres": libres_trouves,
        }
        (ICI / "cameras-photos-soigne.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nÉcrit : verites/app-002/cameras-photos-soigne.json")


if __name__ == "__main__":
    main()
