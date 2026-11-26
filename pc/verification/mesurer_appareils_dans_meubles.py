"""L'APPAREIL DANS UN MEUBLE (26/11/2026) : depuis la place de chaque photo, l'appareil du film tombe-t-il dans un meuble ?

Pour chaque photo d'une fiche d'appareils (`cameras-photos*.json`) et la maquette meublée du logement (`logement-meuble.json`) :
  - DEDANS : l'appareil (x, y, z) est-il à l'intérieur de la boîte d'un objet (meuble, équipement) ou d'un mur ?
  - PROCHE : la boîte la plus proche de l'appareil (distance en m) ;
  - BOUCHÉ : part de l'image dont le premier objet touché par le regard est à moins de BOUCHE m (rayons lancés sur une grille
    de l'image ; les trous des portes et des fenêtres ne bouchent pas) — c'est ce qui rend une vue noire ou faite de
    l'intérieur d'un caisson.
Boîtes = celles du contrôle des collisions (`moteur/collisions.py`) : rectangle tourné vu de dessus, du bas au haut de l'objet.
Les objets plats (tapis) et les rideaux ne comptent pas.

    python pc/verification/mesurer_appareils_dans_meubles.py <sortie.json> <logement>=<logement-meuble.json>:<fiche>[,<fiche>…] …
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import collisions  # noqa: E402
from moteur.camera_photo import axes  # noqa: E402

BOUCHE = 0.35  # m : un objet plus près que cela du regard bouche l'image
GRILLE = (32, 20)  # rayons lancés sur la largeur et la hauteur de l'image


def boites(logement: dict) -> list[dict]:
    """Toutes les boîtes solides : meubles et équipements, murs (avec leurs trous)."""
    hsp = float(logement.get("hauteur_sous_plafond") or 2.5)
    sortie = []
    for m in logement.get("meubles", []):
        if collisions.famille(m) == "plat":
            continue
        z0, z1 = collisions.hauteurs(m)
        sortie.append({"quoi": f"{m['categorie']} {m.get('id', '')}".strip(), "sorte": "objet", "rect": collisions.rect_du_meuble(m),
                       "z": (z0, z1), "objet": m})
    ouv = {}
    for o in logement.get("ouvertures", []):
        ouv.setdefault(o["mur"], []).append(o)
    for w in logement.get("murs", []):
        r = collisions.rect_du_mur(w)
        if r is None:
            continue
        sortie.append({"quoi": f"mur {w['id']}", "sorte": "mur", "rect": r, "z": (0.0, float(w.get("hauteur") or hsp)),
                       "trous": ouv.get(w["id"], []), "debut": np.asarray(w["debut"], float), "L": r.h1 * 2})
    return sortie


def dedans(p: np.ndarray, b: dict, marge: float = 0.0) -> bool:
    r = b["rect"]
    d = p[:2] - r.c
    return (abs(float(d @ r.e1)) <= r.h1 + marge and abs(float(d @ r.e2)) <= r.h2 + marge
            and b["z"][0] - marge <= p[2] <= b["z"][1] + marge)


def distance(p: np.ndarray, b: dict) -> float:
    r = b["rect"]
    d = p[:2] - r.c
    dx = max(0.0, abs(float(d @ r.e1)) - r.h1)
    dy = max(0.0, abs(float(d @ r.e2)) - r.h2)
    dz = max(0.0, b["z"][0] - p[2], p[2] - b["z"][1])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def dans_un_trou(b: dict, q: np.ndarray) -> bool:
    """Le point q (sur ou dans un mur) tombe-t-il dans une porte ou une fenêtre de ce mur ?"""
    if b["sorte"] != "mur":
        return False
    s = float((q[:2] - b["debut"]) @ b["rect"].e1)
    for o in b["trous"]:
        a0, a1 = float(o.get("allege") or 0.0), float(o.get("allege") or 0.0) + float(o["hauteur"])
        if o["position"] - 0.02 <= s <= o["position"] + o["largeur"] + 0.02 and a0 - 0.02 <= q[2] <= a1 + 0.02:
            return True
    return False


def premier_choc(p: np.ndarray, v: np.ndarray, b: dict) -> float | None:
    """Distance le long du rayon p + t v (v unitaire) jusqu'à l'entrée dans la boîte (0 si p est dedans) ; None sinon."""
    r = b["rect"]
    o = np.array([float((p[:2] - r.c) @ r.e1), float((p[:2] - r.c) @ r.e2), p[2]])
    w = np.array([float(v[:2] @ r.e1), float(v[:2] @ r.e2), v[2]])
    lo, hi = np.array([-r.h1, -r.h2, b["z"][0]]), np.array([r.h1, r.h2, b["z"][1]])
    t0, t1 = 0.0, math.inf
    for k in range(3):
        if abs(w[k]) < 1e-12:
            if o[k] < lo[k] or o[k] > hi[k]:
                return None
            continue
        a, c = (lo[k] - o[k]) / w[k], (hi[k] - o[k]) / w[k]
        a, c = min(a, c), max(a, c)
        t0, t1 = max(t0, a), min(t1, c)
        if t0 > t1:
            return None
    return t0


def mesurer_photo(cam: dict, larg: int, haut: int, bs: list[dict]) -> dict:
    p = np.array([cam["x"], cam["y"], cam["z"]], float)
    vue, droite, hautv = axes(float(cam["cap"]), float(cam.get("tangage", 0.0)))
    f, u0, v0 = float(cam["f"]), float(cam.get("u0", larg / 2)), float(cam.get("v0", haut / 2))
    dans = [b["quoi"] for b in bs if dedans(p, b)]
    proches = sorted(((distance(p, b), b["quoi"]) for b in bs if b["sorte"] == "objet"), key=lambda t: t[0])[:2]
    mur = min((distance(p, b) for b in bs if b["sorte"] == "mur"), default=math.inf)
    bouche, par_objet, n = 0, {}, 0
    for i in range(GRILLE[0]):
        for j in range(GRILLE[1]):
            u, w = (i + 0.5) * larg / GRILLE[0], (j + 0.5) * haut / GRILLE[1]
            v = vue + (u - u0) / f * droite - (w - v0) / f * hautv
            v = v / np.linalg.norm(v)
            n += 1
            mieux = None
            for b in bs:
                t = premier_choc(p, v, b)
                if t is None or t > BOUCHE:
                    continue
                if b["sorte"] == "mur" and dans_un_trou(b, p + v * max(t, 0.0) + v * 0.01):
                    continue
                if mieux is None or t < mieux[0]:
                    mieux = (t, b["quoi"])
            if mieux is not None:
                bouche += 1
                par_objet[mieux[1]] = par_objet.get(mieux[1], 0) + 1
    return {"dedans": dans, "proche": [[round(d, 3), q] for d, q in proches], "mur_m": round(mur, 3),
            "bouche": round(bouche / n, 3), "bouche_par": {k: round(c / n, 3) for k, c in sorted(par_objet.items(), key=lambda t: -t[1])}}


def main(argv: list[str]) -> None:
    sortie, cas = Path(argv[0]), argv[1:]
    tout = {}
    for c in cas:
        nom, reste = c.split("=", 1)
        logf, fiches = reste.split(":", 1)
        logement = json.loads(Path(logf).read_text(encoding="utf-8"))
        bs = boites(logement)
        pieces = {p["id"]: p for p in logement.get("pieces", [])}
        for fiche in fiches.split(","):
            fd = json.loads(Path(fiche).read_text(encoding="utf-8"))
            cle = f"{nom} | {Path(fiche).parent.name}/{Path(fiche).name}"
            tout[cle] = {}
            for photo, e in sorted(fd.get("cameras", {}).items()):
                cam = e.get("camera") or e
                if "x" not in cam:
                    continue
                r = mesurer_photo(cam, int(e.get("largeur", 1206)), int(e.get("hauteur", 800)), bs)
                r["piece"] = e.get("piece")
                r["z"] = round(float(cam["z"]), 2)
                tout[cle][photo] = r
                drapeau = "DEDANS " + ",".join(r["dedans"]) if r["dedans"] else ""
                if r["bouche"] >= 0.05 or drapeau:
                    print(f"{cle:70s} {photo}  piece={r['piece']}  z={r['z']}  bouché {r['bouche']:.0%}  {drapeau}  "
                          f"proche={r['proche'][:1]}  par={list(r['bouche_par'].items())[:3]}")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(tout, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for v in tout.values())
    k = sum(1 for v in tout.values() for r in v.values() if r["dedans"] or r["bouche"] >= 0.05)
    print(f"{k} vues touchées sur {n} (dedans, ou ≥ 5 % de l'image bouchée à moins de {BOUCHE} m)")


if __name__ == "__main__":
    main(sys.argv[1:])
