r"""Repérage des meubles : apprendre à l'œil à reconnaître, carré par carré, le meuble vu sur une photo (09/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\apprendre_meubles.py ..\atelya\b2\brique-photos-essais ^
        moteur\modeles\meubles-vits14-v1.pt [--app001]

Exemples : les photos d'essai MEUBLÉES rendues par Blender (tirages « -m1 », « -m2 ») et leurs masques de catégories
(categories\categories-<photo>.png, moteur/blender/masques_meubles.py). fr-031 et fr-038 = CONTRÔLE (jamais appris) : on y
lance tout le repérage (photos → meubles au sol) et on le compare aux meubles posés. --app001 : le même repérage sur les vraies
photos d'app-001, comparé aux 47 meubles relevés à la main (verites/app-001/meubles.json).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.oeil_dinov2 import charger  # noqa: E402
from moteur.reconnaitre_sols import Classifieur  # noqa: E402
from moteur.reperer_meubles import (CLASSES_MEUBLES, empreintes_carres, etiquettes_carres, fusionner,  # noqa: E402
                                    meubles_d_une_photo, noter_meubles)
from moteur.sol_a_plat import piece_de_l_appareil  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
CONTROLE = ("fr-031", "fr-038")
RIEN_PAR_PHOTO = 250  # carrés « rien » gardés par photo (ils sont très nombreux)


def photos_meublees(essais: Path):
    for t in sorted(essais.iterdir()):
        if t.name[-2:] not in ("m1", "m2") or not (t / "categories").is_dir():
            continue
        releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
        logement = json.loads((t / "logement.json").read_text(encoding="utf-8"))
        for nom, d in releve["cameras"].items():
            rendu = lire_image(t / "rendus" / f"vue-{nom}.png")
            masque = lire_image(t / "categories" / f"categories-{nom}.png", cv2.IMREAD_GRAYSCALE)
            if rendu is None or masque is None:
                continue
            yield t, logement, nom, d, cv2.cvtColor(rendu, cv2.COLOR_BGR2RGB), masque


def reperer(photos, logement: dict, oeil, clf: Classifieur) -> list[dict]:
    """photos : [(rgb, caméra 8 nombres)] → meubles trouvés (fusionnés)."""
    vus = []
    for rgb, cam in photos:
        e = empreintes_carres(oeil, rgb)
        p = clf.probabilites(e.reshape(-1, e.shape[-1])).reshape(*e.shape[:2], -1)
        piece, _ = piece_de_l_appareil(cam, logement["pieces"])
        vus += meubles_d_une_photo(p, cam, rgb.shape[1], rgb.shape[0], piece)
    return fusionner(vus)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apprendre le repérage des meubles")
    ap.add_argument("essais", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--app001", action="store_true")
    ap.add_argument("--graine", type=int, default=5)
    args = ap.parse_args()
    alea = np.random.default_rng(args.graine)
    debut = time.time()
    oeil = charger("vits14")
    X, y, controle_tirages = [], [], {}
    for t, logement, nom, d, rgb, masque in photos_meublees(args.essais):
        logement_nom = t.name.rsplit("-", 1)[0]
        if logement_nom in CONTROLE:
            controle_tirages.setdefault(t, (logement, []))[1].append((rgb, camera_depuis_dict(d["camera"])))
            continue
        e = empreintes_carres(oeil, rgb)
        etiq = etiquettes_carres(masque)
        ok = etiq >= 0
        rien = np.argwhere(ok & (etiq == 0))
        garde = ok & (etiq > 0)
        if len(rien) > RIEN_PAR_PHOTO:
            rien = rien[alea.choice(len(rien), RIEN_PAR_PHOTO, replace=False)]
        garde[rien[:, 0], rien[:, 1]] = True
        X.append(e[garde])
        y.append(etiq[garde])
    X, y = np.concatenate(X), np.concatenate(y)
    print(f"{len(X)} carrés appris ({time.time() - debut:.0f} s) :",
          {c: int((y == i).sum()) for i, c in enumerate(CLASSES_MEUBLES)}, flush=True)
    clf = Classifieur(X.shape[1], CLASSES_MEUBLES, "vits14")
    print(f"justesse apprise {clf.apprendre(X, y):.3f}", flush=True)
    notes = {}
    for t, (logement, photos) in sorted(controle_tirages.items()):
        trouves = reperer(photos, logement, oeil, clf)
        notes[t.name] = noter_meubles(trouves, logement["meubles"])
        print(f"contrôle {t.name} : {notes[t.name]}", flush=True)
    if args.app001:
        releve = json.loads((RACINE / "verites/app-001/cameras-photos.json").read_text(encoding="utf-8"))
        logement = json.loads((RACINE.parent / "atelya/lectures-claude/app-001/logement.json").read_text(encoding="utf-8"))
        verite = json.loads((RACINE / "verites/app-001/meubles.json").read_text(encoding="utf-8"))["meubles"]
        photos = []
        for nom, d in releve["cameras"].items():
            img = lire_image(RACINE / releve["photos"] / f"{nom}.png")
            photos.append((cv2.cvtColor(img, cv2.COLOR_BGR2RGB), camera_depuis_dict(d["camera"])))
        trouves = reperer(photos, logement, oeil, clf)
        notes["app-001"] = noter_meubles(trouves, verite)
        print(f"app-001 : {notes['app-001']}", flush=True)
        (args.sortie.parent / "meubles-trouves-app001.json").write_text(json.dumps(trouves, ensure_ascii=False, indent=1),
                                                                        encoding="utf-8")
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    torch.save({**clf.etat(), "notes": notes}, args.sortie)
    print(f"FINI en {time.time() - debut:.0f} s : {args.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
