r"""Mesure du REPÉRAGE PRÉCIS des meubles (moteur/meubles_photos.py) contre les meubles relevés à la main (app-001, app-002,
caméras relevées à la main) : retrouvés / en trop comme avant, et, pour les meubles retrouvés, la SORTE exacte, l'écart de
LARGEUR et de HAUTEUR, et l'écart de COULEUR. Avant (groupe seul, taille courante) contre après (précis).

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_meubles_precis.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.owlv2 import charger  # noqa: E402
from moteur.ranger_meubles import chevauchements, ranger  # noqa: E402
from moteur.reconnaitre_sols import lab  # noqa: E402
from moteur.reperer_meubles import groupe, noter_meubles, reperer_depuis_releve, vers_meubles_du_logement  # noqa: E402

CAS = {"app-001": (RACINE / "verites/app-001/cameras-photos.json", PC / "lectures-claude/app-001/logement.json", RACINE / "verites/app-001/meubles.json"),
       "app-002": (RACINE / "verites/app-002/cameras-photos.json", RACINE / "verites/app-002/logement.json", RACINE / "verites/app-002/meubles.json")}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def attributs(trouves: list[dict], verite: list[dict]) -> dict:
    """Pour chaque meuble de la vérité retrouvé (même groupe, à moins de 0,8 m) : sorte exacte ? écarts de taille et de couleur."""
    libres = list(range(len(trouves)))
    sortes, largeurs, hauteurs, couleurs = [], [], [], []
    for v in verite:
        g = groupe(v["categorie"])
        if not g or (v.get("altitude") or 0) >= 0.3:
            continue
        cands = [(math.dist(trouves[i]["position"], v["position"]), i) for i in libres if groupe(trouves[i]["categorie"]) == g]
        cands = [c for c in cands if c[0] <= 0.8]
        if not cands:
            continue
        _, i = min(cands)
        libres.remove(i)
        t = trouves[i]
        sortes.append(t["categorie"] == v["categorie"])
        largeurs.append(abs(t["dimensions"][0] - v["dimensions"][0]) / v["dimensions"][0])
        hauteurs.append(abs(t["dimensions"][2] - v["dimensions"][2]) / v["dimensions"][2])
        if v.get("couleur") and t.get("couleur"):
            a, b = lab(np.array([v["couleur"]], float))[0], lab(np.array([t["couleur"]], float))[0]
            couleurs.append(float(np.linalg.norm(a - b)))
    pct = lambda x: f"{100 * float(np.mean(x)):.0f} %" if x else "?"
    med = lambda x: f"{100 * float(np.median(x)):.0f} %" if x else "?"
    return {"sorte exacte": pct(sortes), "écart de largeur (médian)": med(largeurs), "écart de hauteur (médian)": med(hauteurs),
            "couleurs données": f"{len(couleurs)}/{len(sortes)}", "écart de couleur (médian)": round(float(np.median(couleurs)), 1) if couleurs else None}


owl = charger()
for nom, (releve, logement, verite) in CAS.items():
    releve, logement, verite = lire(releve), lire(logement), lire(verite)["meubles"]
    logement["meubles"] = []
    cams = [camera_depuis_dict(d["camera"]) for d in releve["cameras"].values()]
    for titre, precis in (("avant (groupe, taille courante)", False), ("après (précis)", True)):
        ms, _ = ranger(vers_meubles_du_logement(reperer_depuis_releve(releve, logement, RACINE, owl=owl, precis=precis), logement), logement)
        n = noter_meubles([{"groupe": groupe(m["categorie"]), "position": m["position"]} for m in ms], verite, cameras=cams, logement=logement)
        print(f"{nom} | {titre:32s} | {len(ms)} meubles, se traversent {len(chevauchements(ms))} ; retrouvés {n['retrouves']}, en trop {n['en_trop']}, "
              f"écart de place {n['ecart_moyen_m']} m ; {n['par_groupe']}", flush=True)
        print(f"{nom} | {'':32s} | {attributs(ms, verite)}", flush=True)
        if precis:
            compte = {}
            for m in ms:
                compte[m["categorie"]] = compte.get(m["categorie"], 0) + 1
            print(f"{nom} | {'':32s} | sortes posées : {dict(sorted(compte.items()))}", flush=True)
