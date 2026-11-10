r"""Repérage des meubles par OWLv2 contre l'ancien repérage DINOv2 (10/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\reperer_meubles_owl.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\b2\meubles-owl

OWLv2 n'apprend RIEN sur nos photos fabriquées : ses seuils (note minimale par groupe) sont réglés sur les tirages
d'ENTRAÎNEMENT (tous sauf fr-031 et fr-038), puis la note est donnée sur le CONTRÔLE (fr-031, fr-038 : anciens tirages m1/m2
et tirages à vrais lits m3/m4). L'ancien repérage (meubles-vits14-v1.pt, réglé SUR le contrôle le 09/11/2026) est noté sur le
même contrôle, de la même façon (moteur/reperer_meubles.noter_meubles : même groupe, à moins de 0,8 m, meubles vus sur au
moins une photo). Jamais app-001 ni app-002.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.owlv2 import charger as charger_owl, objets  # noqa: E402
from moteur.pas_du_sol import NOMS, REQUETES  # noqa: E402
from moteur.reperer_meubles import GROUPES, TYPE_DE_GROUPE, groupe, noter_meubles, reperer_owl  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
CONTROLE = ("fr-031", "fr-038")
SEUILS = (0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)
GROUPE_DE = {n: g for n, g in REQUETES.items() if g in TYPE_DE_GROUPE}


def tirages_meubles(essais: Path):
    for t in sorted(essais.iterdir()):
        if re.search(r"-m\d+$", t.name) and (t / "categories").is_dir() and (t / "logement.json").is_file():
            yield t


def compter(trouves, verite, cameras, logement, g) -> tuple[int, int, int]:
    """(retrouvés, à trouver, en trop) pour le groupe g."""
    n = noter_meubles([m for m in trouves if m["groupe"] == g], [m for m in verite if groupe(m["categorie"]) == g],
                      cameras=cameras, logement=logement)
    a, b = (int(x) for x in n["retrouves"].split("/"))
    return a, b, n["en_trop"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Repérage des meubles : OWLv2 contre DINOv2")
    ap.add_argument("essais", type=Path)
    ap.add_argument("sortie", type=Path)
    args = ap.parse_args()
    args.sortie.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    cache = args.sortie / "objets-owl.json"
    memoire = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
    owl, requetes = None, None
    donnees = {}
    for t in tirages_meubles(args.essais):
        releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
        logement = json.loads((t / "logement.json").read_text(encoding="utf-8"))
        photos, objs = [], []
        for nom, d in releve["cameras"].items():
            cle = f"{t.name}/{nom}"
            img = None
            if cle not in memoire:
                if owl is None:
                    owl = charger_owl()
                    requetes = owl.textes(NOMS)
                img = cv2.cvtColor(lire_image(t / "rendus" / f"vue-{nom}.png"), cv2.COLOR_BGR2RGB)
                memoire[cle] = {"taille": list(img.shape[:2]), "objets": objets(owl.detecter(img, requetes), NOMS, seuil=0.1)}
            h, w = memoire[cle]["taille"]
            photos.append((w, h, camera_depuis_dict(d["camera"])))
            objs.append(memoire[cle]["objets"])
        donnees[t.name] = (t, logement, photos, objs)
    cache.write_text(json.dumps(memoire), encoding="utf-8")
    print(f"{len(donnees)} tirages meublés, rectangles prêts ({time.time() - debut:.0f} s)", flush=True)

    def bilan(noms, seuils):
        par_g = {g: [0, 0, 0] for g in GROUPES}
        for n in noms:
            t, logement, photos, objs = donnees[n]
            trouves = reperer_owl(photos, logement, objs, GROUPE_DE, seuils)
            cams = [c for _, _, c in photos]
            for g in GROUPES:
                a, b, e = compter(trouves, logement["meubles"], cams, logement, g)
                par_g[g][0] += a
                par_g[g][1] += b
                par_g[g][2] += e
        return par_g

    entrainement = [n for n in donnees if n.rsplit("-", 1)[0] not in CONTROLE]
    # 1. un seuil par groupe, réglé sur l'entraînement : meilleur F1 = 2 TP / (2 TP + oubliés + en trop)
    choix = {}
    grilles = {s: bilan(entrainement, {g: s for g in GROUPES}) for s in SEUILS}
    for g in GROUPES:
        def f1(s):
            a, b, e = grilles[s][g]
            return 2 * a / max(2 * a + (b - a) + e, 1)
        choix[g] = max(SEUILS, key=f1)
        a, b, e = grilles[choix[g]][g]
        print(f"  {g:10s} seuil {choix[g]} : entraînement {a}/{b} retrouvés, {e} en trop", flush=True)
    resultats = {"seuils": choix}
    # 2. note sur le contrôle : OWLv2 (seuils choisis) et DINOv2 v1
    from moteur.oeil_dinov2 import charger as charger_oeil
    from moteur.reconnaitre_sols import Classifieur
    from moteur.reperer_meubles import empreintes_carres, fusionner, meubles_d_une_photo
    from moteur.sol_a_plat import piece_de_l_appareil
    clf = Classifieur.depuis(torch.load(RACINE / "moteur" / "modeles" / "meubles-vits14-v1.pt", weights_only=False))
    oeil = charger_oeil(clf.oeil)
    for jeu, motif in (("controle-anciens (m1, m2)", r"-m[12]$"), ("controle-vrais-lits (m3, m4)", r"-m[34]$")):
        noms = [n for n in donnees if n.rsplit("-", 1)[0] in CONTROLE and re.search(motif, n)]
        owl_g = bilan(noms, choix)
        dino_g = {g: [0, 0, 0] for g in GROUPES}
        for n in noms:
            t, logement, photos, _ = donnees[n]
            releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
            vus = []
            for (w, h, cam), nom in zip(photos, releve["cameras"]):
                rgb = cv2.cvtColor(lire_image(t / "rendus" / f"vue-{nom}.png"), cv2.COLOR_BGR2RGB)
                e = empreintes_carres(oeil, rgb)
                p = clf.probabilites(e.reshape(-1, e.shape[-1])).reshape(*e.shape[:2], -1)
                piece, _ = piece_de_l_appareil(cam, logement["pieces"])
                vus += meubles_d_une_photo(p, cam, w, h, piece)
            trouves = fusionner(vus)
            for g in GROUPES:
                a, b, e = compter(trouves, logement["meubles"], [c for _, _, c in photos], logement, g)
                dino_g[g][0] += a
                dino_g[g][1] += b
                dino_g[g][2] += e
        def total(d):
            return [sum(v[i] for v in d.values()) for i in range(3)]
        resultats[jeu] = {"owl": {g: f"{a}/{b} (+{e})" for g, (a, b, e) in owl_g.items()},
                          "dino": {g: f"{a}/{b} (+{e})" for g, (a, b, e) in dino_g.items()},
                          "owl_total": total(owl_g), "dino_total": total(dino_g)}
        print(f"[{jeu}] OWLv2 : {resultats[jeu]['owl_total']} | DINOv2 : {resultats[jeu]['dino_total']}  (retrouvés, à trouver, en trop)", flush=True)
        for g in GROUPES:
            print(f"   {g:10s} OWLv2 {resultats[jeu]['owl'][g]:14s} DINOv2 {resultats[jeu]['dino'][g]}", flush=True)
    (args.sortie / "bilan.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
