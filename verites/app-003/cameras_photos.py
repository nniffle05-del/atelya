r"""app-003 : CORRIGÉ de la place des photos (15/11/2026), relevé à la main par Claude → verites/app-003/cameras-photos.json.

Pourquoi : noter en mètres la précision des photos calées seules (moteur/caler_photos.py) sur un logement jamais vu. Les corrigés
d'app-001 et app-002 sont douteux pour les photos « approchée » / « moyenne » ; celui-ci est fait avec plus de soin.

Méthode :
  - repères lus sur des agrandissements ×2 quadrillés de chaque photo (pixels de la photo, 1206 px de large) ;
  - ANCRES = éléments dessinés sur le plan et retrouvés sans doute sur la photo (angles de murs, montants de portes et de
    fenêtres), à leur place du plan ;
  - repères LIBRES = arêtes verticales bien nettes vues sur PLUSIEURS photos de la même pièce, mais absentes du plan ou mal
    dessinées (miroir, placards, embrasure de la fenêtre, porte du couloir) : leur place est une inconnue, calculée avec les
    caméras. Ils relient les photos entre elles (c'est le « calcul d'ensemble » des géomètres) ;
  - appareil de niveau, ligne d'horizon au milieu de la photo (vues tirées d'une visite virtuelle) ;
  - ZOOM et ORIENTATION mesurés SANS le plan, par les lignes de fuite des poutres, corniches et hauts de portes
    (pc/essais-cameras-seules/fuites.py) : orientation de chaque photo (CAPS ci-dessous) ; zoom net sur 8 photos (358 à 410 px,
    médiane 388), pris commun aux 10 photos (même visite virtuelle) : F = 388 px, soit un champ de 114° ;
  - il reste à trouver, par photo, la place (x, y) et la hauteur de l'appareil ;
  - l'incertitude de chaque caméra est chiffrée : calcul refait 150 fois en bougeant au hasard les pixels lus (± 3 px), les
    ancres du plan (± 12 cm), l'orientation (± 0,5°) et le zoom (± 12 px).
Constat : le plan de l'annonce est faux par endroits (embrasure de la fenêtre de la salle à manger, porte séjour / couloir) ;
ces éléments ne sont PAS des ancres.

    ..\atelya\.venv\Scripts\python.exe verites\app-003\cameras_photos.py [--images ..\atelya\b2\app-003\corrige]
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
PHOTOS = "../atelya/photos-clients/app-003/photos"
HSP = 2.90
LARGEUR = 1206
F = 388.0  # focale commune (pixels), médiane des lignes de fuite
CAPS = {  # orientation de chaque photo d'après ses lignes de fuite (degrés, 0 = vers +x)
    "photo-01": 1.3, "photo-06": 32.3, "photo-07": 145.0, "photo-08": -116.4, "photo-12": -89.0,
    "photo-02": 51.6, "photo-03": -136.7, "photo-04": -37.6, "photo-05": 137.5, "photo-14": 46.9,
}

GROUPES = {
    "salle à manger": {
        "piece": "sejour_2",
        "ancres": {
            "KW": (14.753, 10.98), "KE": (17.388, 10.98),  # montants de la grande ouverture vers la cuisine
            "NW": (13.32, 10.98), "NE1": (18.79, 10.98),  # angle nord-ouest ; bout du mur nord avant la fenêtre
            "PS": (13.32, 8.448), "PN": (13.32, 9.753),  # montants de la porte double vers l'entrée
        },
        "libres": {  # place de départ approximative ; la vraie est calculée
            "FS": (19.4, 7.93), "BS": (19.4, 7.6), "FL": (18.84, 7.59),  # fenêtre : montant sud, fond et bout de l'embrasure sud
            "FN": (19.4, 10.15), "NE2": (18.79, 10.6),  # fenêtre : montant nord ; bout du ressaut nord
            "C1W": (17.6, 7.5), "ME": (17.0, 7.3), "MW": (15.2, 7.3),  # placard est (arête ouest), miroir (bords est et ouest)
        },
        "photos": {
            "photo-01": {"depart": (13.4, 9.2, 0), "obs": [
                ("v", "KW", 40, 100, 600), ("v", "KE", 403, 230, 460), ("v", "NE1", 459, 220, 430), ("v", "NE2", 498, 220, 430),
                ("v", "FN", 521, 240, 390), ("v", "FS", 695, 240, 390), ("v", "BS", 724, 230, 430), ("v", "C1W", 778, 220, 450),
                ("v", "ME", 847, 160, 350), ("v", "MW", 1033, 20, 350),
                ("s", "KE", 403, 462), ("s", "NE1", 459, 434)]},
            "photo-06": {"depart": (13.6, 7.9, 30), "obs": [
                ("v", "KW", 250, 160, 540), ("v", "KE", 525, 250, 440), ("v", "NE2", 621, 240, 400),
                ("v", "FN", 648, 240, 400), ("v", "FS", 872, 220, 420), ("v", "BS", 899, 180, 450), ("v", "C1W", 950, 200, 540),
                ("v", "ME", 1068, 30, 350),
                ("s", "KW", 251, 549), ("s", "KE", 527, 443)]},
            "photo-07": {"depart": (19.0, 8.5, 150), "obs": [
                ("v", "PS", 365, 260, 430), ("v", "PN", 479, 260, 430), ("v", "NW", 570, 230, 430),
                ("v", "KW", 625, 260, 450), ("v", "KE", 820, 200, 510), ("v", "MW", 121, 80, 360),
                ("s", "KW", 627, 452), ("s", "KE", 822, 515),
                ("l", "KE", "NE1", (836, 522), (1083, 600), "pied du mur nord")]},
            "photo-08": {"depart": (18.6, 10.6, -120), "obs": [
                ("v", "FS", 91, 100, 480), ("v", "BS", 140, 100, 540), ("v", "FL", 292, 110, 530), ("v", "C1W", 501, 160, 480),
                ("v", "ME", 544, 180, 340), ("v", "MW", 668, 190, 340),
                ("v", "PS", 905, 230, 440), ("v", "PN", 1112, 200, 440),
                ("s", "PS", 905, 446), ("s", "PN", 1112, 522)]},
            "photo-12": {"depart": (16.3, 10.8, -85), "obs": [
                ("v", "FS", 167, 100, 480), ("v", "BS", 228, 150, 480), ("v", "FL", 291, 150, 490), ("v", "C1W", 474, 200, 480),
                ("v", "ME", 543, 180, 340), ("v", "MW", 703, 160, 340),
                ("v", "PS", 1100, 130, 570),
                ("s", "PS", 1098, 580)]},
        },
    },
    "séjour": {
        "piece": "sejour_1",
        "ancres": {
            "NW": (4.31, 14.09), "NE": (9.75, 14.09), "SE": (9.75, 9.04), "SW": (4.31, 9.04),
            "F1S": (4.31, 12.315), "F1N": (4.31, 13.596), "F2S": (4.31, 9.531), "F2N": (4.31, 10.960),  # deux portes-fenêtres
            "PN": (9.75, 10.640), "PS": (9.75, 9.384),  # porte double vers l'entrée
            "EPN": (13.13, 9.753),  # porte entrée / salle à manger vue à travers l'entrée (montant nord)
        },
        "libres": {
            "CE": (9.6, 9.04), "CW": (8.6, 9.04),  # porte vitrée du couloir (mur sud) : montants est et ouest
            "PLE": (5.3, 9.04), "PLW": (4.6, 9.04),  # porte vitrée du placard (mur sud, côté ouest)
            "M1": (6.6, 14.0), "M2": (7.6, 14.0),  # miroir doré de la cheminée (mur nord) : bords ouest et est
            "TVL": (9.7, 12.8), "TVR": (9.7, 11.8),  # téléviseur (mur est)
        },
        "photos": {
            "photo-02": {"depart": (4.9, 10.5, 45), "obs": [
                ("v", "M1", 434, 210, 350), ("v", "M2", 546, 220, 350), ("v", "NE", 640, 240, 380),
                ("v", "TVL", 693, 305, 355), ("v", "TVR", 772, 305, 358),
                ("v", "PN", 910, 230, 440), ("v", "EPN", 1071, 250, 430), ("v", "PS", 1158, 190, 500),
                ("s", "EPN", 1071, 440)]},
            "photo-03": {"depart": (9.0, 13.5, -135), "obs": [
                ("v", "CE", 88, 200, 480), ("v", "CW", 247, 200, 480), ("v", "PLE", 534, 230, 470), ("v", "PLW", 577, 230, 420),
                ("v", "SW", 585, 220, 410),
                ("v", "F2S", 608, 240, 420), ("v", "F2N", 691, 240, 420), ("v", "F1S", 806, 200, 440), ("v", "F1N", 1020, 150, 450),
                ("v", "NW", 1100, 80, 390),
                ("s", "CW", 247, 487), ("s", "SW", 585, 415)]},
            "photo-04": {"depart": (5.5, 13.3, -35), "obs": [
                ("v", "M2", 127, 20, 370), ("v", "TVL", 367, 300, 355), ("v", "TVR", 485, 305, 355),
                ("v", "PN", 575, 270, 400), ("v", "PS", 636, 270, 395), ("v", "SE", 650, 230, 390),
                ("v", "CE", 661, 260, 395), ("v", "CW", 706, 260, 395), ("v", "PLE", 993, 200, 490), ("v", "PLW", 1160, 180, 520),
                ("l", "SW", "SE", (1011, 492), (1158, 522), "pied du mur sud (sous la porte du placard)"),
                ("l", "SW", "SE", (665, 397), (703, 398), "pied du mur sud (sous la porte du couloir)")]},
            "photo-05": {"depart": (9.0, 9.4, 140), "obs": [
                ("v", "PLE", 85, 190, 500), ("v", "PLW", 125, 190, 500),
                ("v", "F2S", 225, 170, 470), ("v", "F2N", 415, 200, 450), ("v", "F1S", 530, 230, 420), ("v", "F1N", 615, 230, 410),
                ("v", "NW", 639, 230, 410), ("v", "M1", 719, 210, 350), ("v", "M2", 828, 200, 350),
                ("l", "SW", "NW", (230, 480), (410, 447), "pied du mur ouest (sous la porte-fenêtre sud)")]},
        },
    },
    "chambre d'angle": {
        "piece": "chambre_3",
        "ancres": {
            "FW": (1.355, 4.83), "FE": (2.833, 4.83),  # porte-fenêtre nord
            "PN": (4.06, 4.138), "PS": (4.06, 3.399),  # porte du couloir (est)
            "NE": (4.06, 4.83), "SEc": (4.06, 0.30),
        },
        "libres": {},
        "photos": {
            "photo-14": {"depart": (1.0, 1.5, 45), "obs": [
                ("v", "FW", 360, 200, 440), ("v", "FE", 489, 200, 440), ("v", "PN", 625, 240, 420), ("v", "PS", 670, 220, 420),
                ("l", "SEc", "NE", (966, 560), (1151, 620), "pied du mur est (à droite du lit)")]},
        },
    },
}
QUOI = {
    "KW": "ouverture cuisine, montant ouest", "KE": "ouverture cuisine, montant est", "NW": "angle nord-ouest", "NE": "angle nord-est",
    "SE": "angle sud-est", "SW": "angle sud-ouest", "NE1": "bout du mur nord", "NE2": "bout du ressaut nord", "PS": "porte, montant sud",
    "PN": "porte, montant nord", "FS": "fenêtre, montant sud", "FN": "fenêtre, montant nord", "BS": "embrasure sud, fond",
    "FL": "embrasure sud, bout", "C1W": "placard est, arête ouest", "ME": "miroir, bord est", "MW": "miroir, bord ouest",
    "F1S": "porte-fenêtre nord, montant sud", "F1N": "porte-fenêtre nord, montant nord", "F2S": "porte-fenêtre sud, montant sud",
    "F2N": "porte-fenêtre sud, montant nord", "EPN": "porte de la salle à manger vue à travers l'entrée", "CE": "porte du couloir, montant est",
    "CW": "porte du couloir, montant ouest", "PLE": "porte du placard, bord est", "PLW": "porte du placard, bord ouest",
    "M1": "miroir de la cheminée, bord ouest", "M2": "miroir de la cheminée, bord est", "TVL": "téléviseur, bord gauche",
    "TVR": "téléviseur, bord droit", "FW": "porte-fenêtre, montant ouest", "FE": "porte-fenêtre, montant est",
}


def _cam(p, hauteur, cap, f=F):
    """(x, y, z) + orientation et zoom mesurés → caméra complète : de niveau, centre optique au milieu."""
    return [p[0], p[1], p[2], cap, 0.0, f, LARGEUR / 2, hauteur / 2]


def _ecarts(vecteur, groupe, hauteurs, ancres, caps=CAPS, focales=None):
    """Tous les écarts (pixels) du groupe : vecteur = 3 nombres par photo (x, y, z), puis 2 par repère libre."""
    noms = list(groupe["photos"])
    libres = list(groupe["libres"])
    lieux = dict(ancres)
    for i, nom in enumerate(libres):
        lieux[nom] = vecteur[3 * len(noms) + 2 * i: 3 * len(noms) + 2 * i + 2]
    r = []
    for k, nom in enumerate(noms):
        p = vecteur[3 * k: 3 * k + 3]
        cam = _cam(p, hauteurs[nom], caps[nom], (focales or {}).get(nom, F))
        for o in groupe["photos"][nom]["obs"]:
            if o[0] == "v":
                u, _, prof = projeter((*lieux[o[1]], 1.0), cam)
                r.append(o[2] - u if prof > 0.05 else 500.0)
            elif o[0] == "s":
                u, v, prof = projeter((*lieux[o[1]], 0.0), cam)
                r += [o[2] - u, o[3] - v] if prof > 0.05 else [500.0, 500.0]
            else:
                ua, va, pa = projeter((*lieux[o[1]], 0.0), cam)
                ub, vb, pb = projeter((*lieux[o[2]], 0.0), cam)
                if pa < 0.05 or pb < 0.05:  # un bout derrière l'appareil : on le ramène devant, le long du mur
                    a, b = np.array([*lieux[o[1]], 0.0]), np.array([*lieux[o[2]], 0.0])
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
        bouge = False
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


def _depart(groupe, decalage=0.0, alea=None):
    v = []
    for d in groupe["photos"].values():
        x, y, _ = d["depart"]
        if alea is not None:
            x, y = x + alea.normal(0, decalage), y + alea.normal(0, decalage)
        v += [x, y, 1.3]
    for xy in groupe["libres"].values():
        v += list(xy)
    return np.array(v, float)


def caler_groupe(groupe, hauteurs, tirages=150, px=3.0, m=0.12, dcap=0.5, df=12.0):
    """Caméras du groupe + places des repères libres + incertitude de chaque caméra."""
    ancres = groupe["ancres"]
    v, r = _resoudre(_depart(groupe), lambda w: _ecarts(w, groupe, hauteurs, ancres))
    alea = np.random.default_rng(0)
    # 1. le résultat dépend-il du point de départ ? (8 départs bougés de 0,6 m)
    autres = []
    for _ in range(8):
        w, rw = _resoudre(_depart(groupe, 0.6, alea), lambda q: _ecarts(q, groupe, hauteurs, ancres))
        autres.append((float(rw @ rw), w))
        if float(rw @ rw) < float(r @ r) - 1e-6:
            v, r = w, rw
    stables = sum(1 for c, w in autres if abs(c - float(r @ r)) < 1e-3 * max(1.0, float(r @ r)))
    # 2. incertitude : lectures et plan bougés au hasard
    n = len(groupe["photos"])
    tires = []
    for _ in range(tirages):
        g2 = json.loads(json.dumps(groupe))
        for d in g2["photos"].values():
            for o in d["obs"]:
                if o[0] in "vs":
                    o[2] += alea.normal(0, px)
                if o[0] == "s":
                    o[3] += alea.normal(0, px)
                if o[0] == "l":
                    for q in (3, 4):
                        o[q] = [o[q][0] + alea.normal(0, px), o[q][1] + alea.normal(0, px)]
        a2 = {k: (xy[0] + alea.normal(0, m), xy[1] + alea.normal(0, m)) for k, xy in ancres.items()}
        c2 = {nom: CAPS[nom] + alea.normal(0, dcap) for nom in groupe["photos"]}
        f2 = dict.fromkeys(groupe["photos"], F + alea.normal(0, df))
        w, _ = _resoudre(v, lambda q: _ecarts(q, g2, hauteurs, a2, c2, f2), tours=40)
        tires.append(w)
    tires = np.array(tires)
    incert = {}
    for k, nom in enumerate(groupe["photos"]):
        d = np.hypot(tires[:, 3 * k] - v[3 * k], tires[:, 3 * k + 1] - v[3 * k + 1])
        incert[nom] = (float(np.percentile(d, 68)), dcap)
    lieux = dict(ancres)
    for i, nom in enumerate(groupe["libres"]):
        lieux[nom] = (float(v[3 * n + 2 * i]), float(v[3 * n + 2 * i + 1]))
    return v, lieux, incert, stables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", help="dossier où dessiner le contrôle (arêtes du plan et repères sur chaque photo)")
    parser.add_argument("--sans-ecrire", action="store_true")
    parser.add_argument("--tirages", type=int, default=150)
    args = parser.parse_args()
    from PIL import Image, ImageDraw

    logement = json.loads((ICI / "logement.json").read_text(encoding="utf-8"))
    dossier = RACINE / PHOTOS
    if not dossier.is_dir():
        sys.exit(f"PLANTÉ : dossier des photos introuvable ({PHOTOS})")
    cameras, libres_trouves = {}, {}
    for titre, groupe in GROUPES.items():
        tailles = {nom: Image.open(dossier / f"{nom}.jpg").size for nom in groupe["photos"]}
        hauteurs = {nom: t[1] for nom, t in tailles.items()}
        v, lieux, incert, stables = caler_groupe(groupe, hauteurs, args.tirages)
        print(f"\n== {titre} == (même résultat depuis {stables} départs sur 8)")
        for nom in groupe["libres"]:
            libres_trouves[f"{groupe['piece']}:{nom}"] = {"quoi": QUOI[nom], "x": round(lieux[nom][0], 2), "y": round(lieux[nom][1], 2)}
            print(f"   repère libre {nom:4s} {QUOI[nom]:45s} trouvé en ({lieux[nom][0]:6.2f}, {lieux[nom][1]:6.2f})"
                  f"   départ ({groupe['libres'][nom][0]:.2f}, {groupe['libres'][nom][1]:.2f})")
        for k, nom in enumerate(groupe["photos"]):
            p = [*v[3 * k: 3 * k + 3], CAPS[nom], F]
            cam = _cam(p, hauteurs[nom], CAPS[nom])
            reperes, ecarts = [], []
            for o in groupe["photos"][nom]["obs"]:
                libre = {"libre": True} if (o[0] != "l" and o[1] in groupe["libres"]) else {}
                if o[0] == "v":
                    x, y = lieux[o[1]]
                    e = [o[2] - projeter((x, y, 1.0), cam)[0]]
                    reperes.append({"type": "ligne", "a": [round(x, 3), round(y, 3), 0.0], "b": [round(x, 3), round(y, 3), HSP],
                                    "p1": [o[2], o[3]], "p2": [o[2], o[4]], "quoi": QUOI[o[1]], **libre})
                elif o[0] == "s":
                    x, y = lieux[o[1]]
                    u, w, _ = projeter((x, y, 0.0), cam)
                    e = [o[2] - u, o[3] - w]
                    reperes.append({"type": "point", "p": [round(x, 3), round(y, 3), 0.0], "uv": [o[2], o[3]],
                                    "quoi": "pied : " + QUOI[o[1]], **libre})
                else:
                    a, b = lieux[o[1]], lieux[o[2]]
                    reperes.append({"type": "ligne", "a": [a[0], a[1], 0.0], "b": [b[0], b[1], 0.0], "p1": list(o[3]),
                                    "p2": list(o[4]), "quoi": o[5]})
                    from moteur.camera_photo import residus
                    e = list(residus(cam, reperes[-1:]))
                reperes[-1]["ecart_px"] = round(float(np.abs(e).max()), 1)
                ecarts += [abs(float(q)) for q in e]
            dm, dcap = incert[nom]
            moyen, pire = float(np.mean(ecarts)), float(np.max(ecarts))
            qualite = "bonne" if dm <= 0.20 and moyen <= 5 else "moyenne" if dm <= 0.30 and moyen <= 8 else "approchée"
            cameras[nom] = {
                "camera": {"x": round(float(p[0]), 3), "y": round(float(p[1]), 3), "z": round(float(p[2]), 3),
                           "cap": round(float((p[3] + 180) % 360 - 180), 2), "tangage": 0.0, "f": round(float(p[4]), 1),
                           "u0": LARGEUR / 2, "v0": hauteurs[nom] / 2},
                "largeur": tailles[nom][0], "hauteur": tailles[nom][1], "piece": groupe["piece"], "qualite": qualite,
                "ecart_moyen_px": round(moyen, 1), "ecart_pire_px": round(pire, 1), "incertitude_m": round(dm, 2),
                "incertitude_cap_deg": round(dcap, 1), "reperes": reperes,
            }
            c = cameras[nom]["camera"]
            print(f"{nom} x={c['x']:6.2f} y={c['y']:6.2f} z={c['z']:4.2f} cap={c['cap']:7.1f} f={c['f']:5.0f}"
                  f" | écart {moyen:4.1f} px (pire {pire:4.1f}) | ± {dm:.2f} m, ± {dcap:.1f}° | {qualite}")
            print("      " + "  ".join(f"{r['quoi'][:22]}{'*' if r.get('libre') else ''}:{r['ecart_px']:.0f}" for r in reperes))
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
                image.save(sortie / f"controle-{nom}.png")
    if not args.sans_ecrire:
        fiche = {
            "note": "Corrigé de la place des photos d'app-003 (15/11/2026), relevé à la main par Claude avec soin : repères lus sur des "
                    "agrandissements quadrillés ; ancres = éléments sûrs du plan ; repères « libre » = arêtes vues sur plusieurs photos, "
                    "place calculée avec les caméras (calcul d'ensemble par pièce) ; « incertitude_m » = de combien la caméra bouge quand "
                    "on bouge les lectures de ± 3 px et les ancres de ± 12 cm, l'orientation de ± 0,5° et le zoom de ± 12 px ; zoom (388 px, commun) et orientation mesurés par les lignes de fuite, sans le plan. Produit par verites/app-003/cameras_photos.py.",
            "photos": PHOTOS, "fichier": "{nom}.jpg", "cameras": cameras, "reperes_libres": libres_trouves,
        }
        (ICI / "cameras-photos.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nÉcrit : verites/app-003/cameras-photos.json")


if __name__ == "__main__":
    main()
