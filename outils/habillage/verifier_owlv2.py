r"""Vérifier OWLv2 (moteur/owlv2.py) sur les photos d'essai meublées (Blender), où l'on sait où est chaque meuble (10/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\verifier_owlv2.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\b2\owlv2-verification [--planches 12]

OWLv2 n'a JAMAIS vu ces photos (rien n'est appris ici) : toutes les photos meublées servent de banc. Jamais app-001 ni app-002.
Vérité d'une photo : son masque de catégories (categories\categories-<photo>.png, pixel = n° de la catégorie + 1). Un « vrai
meuble » = une tache d'un même groupe (lit, table…) d'au moins 0,5 % de la photo. Un rectangle d'OWLv2 le RETROUVE s'il est du
même groupe et le recouvre assez (intersection / union ≥ 0,3, ou rectangle contenant ≥ 60 % de la tache et tache ≥ 40 % du
rectangle). Les rectangles qui ne retrouvent rien sont « en trop ».
Écrit : bilan.json (par groupe et par seuil de note), detections.json (tout, pour les étapes suivantes) et des planches
(photo + rectangles vrais en vert, trouvés en orange).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.images import ecrire_image, lire_image  # noqa: E402
from moteur.meubles import NOMS_MEUBLES  # noqa: E402
from moteur.owlv2 import boites_iou, charger, objets  # noqa: E402
from moteur.reperer_meubles import GROUPES, groupe  # noqa: E402

# Ce qu'on demande à OWLv2, et le groupe d'Atelya de chaque phrase (« autre » = objets qui ne sont pas des meubles à
# repérer : on les demande quand même, pour qu'une fenêtre ou une porte ne soit pas prise pour une armoire).
REQUETES = {
    "a bed": "lit", "a bed with a duvet": "lit", "a bunk bed": "lit", "a loft bed": "lit",
    "a sofa": "canape", "a couch": "canape",
    "an armchair": "fauteuil",
    "a chair": "chaise", "a stool": "chaise", "an office chair": "chaise",
    "a dining table": "table", "a table": "table", "a coffee table": "table", "a desk": "table", "a side table": "table",
    "a chest of drawers": "rangement", "a cabinet": "rangement", "a bookshelf": "rangement", "a shelf": "rangement",
    "a tv stand": "rangement", "a nightstand": "rangement", "a bench": "rangement", "a wardrobe": "rangement",
    "a sideboard": "rangement", "kitchen cabinets": "rangement",
    "a rug": "tapis", "a carpet": "tapis",
    "a floor lamp": "lampe", "a lamp": "lampe",
    "a potted plant": "plante",
    "a window": "autre", "a door": "autre", "a radiator": "autre", "a painting": "autre", "a mirror": "autre",
    "a television": "autre", "a pillow": "autre", "a ceiling light": "autre",
}
NOMS = list(REQUETES)
SEUILS = (0.1, 0.15, 0.2, 0.25, 0.3, 0.4)
PART_MIN = 0.005  # une tache plus petite que 0,5 % de la photo n'est pas un meuble « à retrouver »


def vrais_meubles(masque: np.ndarray) -> list[dict]:
    """Les taches de chaque groupe (pixel = n° de catégorie + 1) : rectangle et masque de la tache."""
    vers_groupe = np.zeros(256, np.int16)
    groupes = list(GROUPES)
    for k, c in enumerate(NOMS_MEUBLES, start=1):
        g = groupe(c)
        vers_groupe[k] = groupes.index(g) + 1 if g else 0
    gm = vers_groupe[masque]
    sortie = []
    n_min = PART_MIN * masque.size
    for gi, g in enumerate(groupes, start=1):
        m = cv2.morphologyEx((gm == gi).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        for k in range(1, n):
            x, y, w, h, a = stats[k]
            if a >= n_min:
                sortie.append({"groupe": g, "boite": [float(x), float(y), float(x + w), float(y + h)], "aire": int(a),
                               "masque": etiquettes == k})
    return sortie


def retrouve(d_boite, v: dict) -> bool:
    b = np.array([d_boite], float)
    if boites_iou(b, np.array([v["boite"]], float))[0, 0] >= 0.3:
        return True
    x0, y0, x1, y1 = (int(round(c)) for c in d_boite)
    dedans = int(v["masque"][max(0, y0):max(0, y1), max(0, x0):max(0, x1)].sum())
    aire_boite = max((x1 - x0) * (y1 - y0), 1)
    return dedans >= 0.6 * v["aire"] and dedans >= 0.4 * aire_boite


def noter_photo(sortie: dict, vrais: list[dict], seuil: float) -> dict:
    """Par groupe : vrais, retrouvés, en trop (pour les rectangles d'un groupe de meubles, pas « autre »)."""
    res = {g: {"vrais": 0, "retrouves": 0, "en_trop": 0} for g in GROUPES}
    trouves = [o for o in objets(sortie, NOMS, seuil=seuil) if REQUETES[o["nom"]] != "autre"]
    utilise = [False] * len(trouves)
    for v in vrais:
        res[v["groupe"]]["vrais"] += 1
        for i, o in enumerate(trouves):
            if REQUETES[o["nom"]] == v["groupe"] and retrouve(o["boite"], v):
                res[v["groupe"]]["retrouves"] += 1
                utilise[i] = True
                break
    for i, o in enumerate(trouves):
        if not utilise[i] and not any(REQUETES[o["nom"]] == v["groupe"] and retrouve(o["boite"], v) for v in vrais):
            res[REQUETES[o["nom"]]]["en_trop"] += 1
    return res


def planche(photo: np.ndarray, vrais: list[dict], trouves: list[dict]) -> np.ndarray:
    img = cv2.cvtColor(photo, cv2.COLOR_RGB2BGR).copy()
    for v in vrais:
        x0, y0, x1, y1 = (int(c) for c in v["boite"])
        cv2.rectangle(img, (x0, y0), (x1, y1), (60, 200, 60), 3)
        cv2.putText(img, v["groupe"], (x0 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 200, 60), 2)
    for o in trouves:
        x0, y0, x1, y1 = (int(c) for c in o["boite"])
        couleur = (0, 140, 255) if REQUETES[o["nom"]] != "autre" else (180, 180, 180)
        cv2.rectangle(img, (x0, y0), (x1, y1), couleur, 2)
        cv2.putText(img, f"{o['nom'][2:] if o['nom'].startswith('a ') else o['nom']} {o['note']:.2f}", (x0 + 4, y0 + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Vérifier OWLv2 sur les photos d'essai meublées")
    ap.add_argument("essais", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--planches", type=int, default=12)
    ap.add_argument("--seuil-planche", type=float, default=0.2)
    args = ap.parse_args()
    args.sortie.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    owl = charger()
    requetes = owl.textes(NOMS)
    photos = [(t, p) for t in sorted(args.essais.iterdir()) if (t / "categories").is_dir()
              for p in sorted((t / "rendus").glob("vue-*.png"))]
    print(f"{len(photos)} photos meublées", flush=True)
    total = {s: {g: {"vrais": 0, "retrouves": 0, "en_trop": 0} for g in GROUPES} for s in SEUILS}
    detections, n_planches = {}, 0
    for i, (t, p) in enumerate(photos):
        nom = p.stem[len("vue-"):]
        photo = lire_image(p)
        masque = lire_image(t / "categories" / f"categories-{nom}.png", cv2.IMREAD_GRAYSCALE)
        if photo is None or masque is None:
            raise FileNotFoundError(f"{p} ou son masque de catégories")
        photo = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
        sortie = owl.detecter(photo, requetes)
        vrais = vrais_meubles(masque)
        for s in SEUILS:
            for g, r in noter_photo(sortie, vrais, s).items():
                for k in r:
                    total[s][g][k] += r[k]
        detections[f"{t.name}/{nom}"] = {"objets": objets(sortie, NOMS, seuil=0.1),
                                         "vrais": [{k: v[k] for k in ("groupe", "boite", "aire")} for v in vrais]}
        a_un_lit = any(v["groupe"] == "lit" for v in vrais)
        if n_planches < args.planches and (a_un_lit or i % 37 == 0):
            ecrire_image(args.sortie / f"planche-{t.name}-{nom}.jpg",
                         planche(photo, vrais, objets(sortie, NOMS, seuil=args.seuil_planche)))
            n_planches += 1
        if i % 50 == 0:
            print(f"  {i + 1}/{len(photos)} ({time.time() - debut:.0f} s)", flush=True)
    bilan = {}
    for s in SEUILS:
        lignes = {}
        for g, r in total[s].items():
            lignes[g] = {**r, "rappel": round(r["retrouves"] / r["vrais"], 3) if r["vrais"] else None}
        tv = sum(r["vrais"] for r in total[s].values())
        tr = sum(r["retrouves"] for r in total[s].values())
        te = sum(r["en_trop"] for r in total[s].values())
        bilan[str(s)] = {"tous": {"vrais": tv, "retrouves": tr, "en_trop": te, "rappel": round(tr / max(tv, 1), 3)},
                         "groupes": lignes}
        print(f"seuil {s} : {bilan[str(s)]['tous']}", flush=True)
    (args.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.sortie / "detections.json").write_text(json.dumps(detections, ensure_ascii=False), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
