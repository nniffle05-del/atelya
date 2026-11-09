r"""Pose les sols vus sur les photos du client dans un logement (B2 temps 2, app-001, 09/11/2026) : la matière de chaque pièce,
ses zones de sol (un autre revêtement dans la même pièce, sans mur ni trait), l'échelle du motif, et la teinte mesurée sur la
photo de la pièce (mur blanc = étalon, moteur/teinte_photo.py).

Le fichier de choix (JSON) :
    {"photos": "<dossier des photos>", "bibliotheque": "<..\atelya\bibliotheque\matieres>",
     "pieces": {"<id de la pièce>": {"matiere": "...", "echelle": 1.13, "source": "photo 03",
                                     "photo": "photo-03.png", "zone_sol": [x0, x1, y0, y1], "zone_mur_blanc": [x0, x1, y0, y1],
                                     "zones": [{"contour": [[x, y], ...], "matiere": "...", "source": "photos 05, 06", ...}]}}}
Les zones de photo sont en fractions de la largeur et de la hauteur ; sans photo, pas de teinte. Les contours des zones de sol
sont en mètres, dans le repère du logement. Statut des sols posés : « estime » (vu sur photo).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\poser_sols.py logement.json verites\app-001\sols.json --sortie logement-sols.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.logement import Logement  # noqa: E402
from moteur.teinte_photo import albedo_de_la_matiere, albedo_du_sol, teinte_pour  # noqa: E402


def sol_vu(choix: dict, photos: Path, bibliotheque: Path) -> dict:
    """Le champ `sol` (ou le `sol` d'une zone) d'après un choix : matière, échelle, teinte mesurée sur la photo."""
    sol = {"matiere": choix["matiere"], "statut": "estime", "source": choix.get("source") or "photo du client",
           "confiance": 0.8}
    if choix.get("echelle"):
        sol["echelle"] = choix["echelle"]
    if choix.get("photo"):
        chemin = photos / choix["photo"]
        if not chemin.is_file():
            raise FileNotFoundError(f"photo introuvable : {chemin}")
        image = np.asarray(Image.open(chemin).convert("RGB"))
        cible = albedo_du_sol(image, choix["zone_sol"], choix["zone_mur_blanc"])
        sol["teinte"] = list(teinte_pour(albedo_de_la_matiere(bibliotheque, choix["matiere"]), cible))
        sol["couleur_photo"] = [round(float(min(max(c, 0.0), 1.0)), 4) for c in cible]  # la cible du réglage au rendu
    return sol


def poser_sols(logement: dict, choix: dict, racine: Path) -> dict:
    photos, bibliotheque = racine / choix["photos"], racine / choix["bibliotheque"]
    pieces = {p["id"]: p for p in logement["pieces"]}
    for pid, c in choix["pieces"].items():
        if pid not in pieces:
            raise KeyError(f"pièce inconnue dans le logement : {pid}")
        piece = pieces[pid]
        piece["sol"] = sol_vu(c, photos, bibliotheque)
        piece["zones_sol"] = [{"contour": z["contour"], "sol": sol_vu(z, photos, bibliotheque)} for z in c.get("zones", [])]
    Logement.model_validate(logement)  # zones convexes, matières du catalogue…
    return logement


def main() -> int:
    ap = argparse.ArgumentParser(description="Pose les sols vus sur les photos du client")
    ap.add_argument("logement", type=Path)
    ap.add_argument("choix", type=Path)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--racine", type=Path, default=Path("."), help="dossier d'où partent les chemins du fichier de choix")
    a = ap.parse_args()
    for f in (a.logement, a.choix):
        if not f.is_file():
            print(f"PLANTÉ : fichier introuvable : {f}", flush=True)
            return 2
    logement = poser_sols(json.loads(a.logement.read_text(encoding="utf-8")),
                          json.loads(a.choix.read_text(encoding="utf-8")), a.racine)
    a.sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in logement["pieces"]:
        if p.get("sol", {}).get("statut") == "estime":
            zones = ", ".join(z["sol"]["matiere"] for z in p.get("zones_sol", []))
            print(f"{p['id']} : {p['sol']['matiere']} teinte {p['sol'].get('teinte')}" + (f" ; zones : {zones}" if zones else ""))
    print(f"Logement avec les sols : {a.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
