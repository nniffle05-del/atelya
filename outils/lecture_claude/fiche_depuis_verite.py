r"""Une VÉRITÉ de vrai plan (tracée par Fable, outils/verite/faire_verite.py) → une fiche lecture-claude/0.1, comme si Claude
avait lu ce plan presque parfaitement.

Pourquoi (décision NT du 08/11/2026) : l'API ne sera testée qu'à la fin ; en attendant, une vérité de Fable tient lieu de
lecture de Claude pour faire travailler tout ce qui suit (traducteur, écran de vérification, 3D Blender) sur un VRAI plan.
Plans d'ENTRAÎNEMENT seulement (vérités Fable relues : fr-021 à fr-027, fr-029 à fr-041) : jamais les 13 plans d'examen pour
régler quoi que ce soit.

Ce que la vérité ne contient pas, la fiche ne l'invente pas : aucun texte (ni cote, ni surface) ; l'échelle proposée est celle
de la vérité (la « clé de Claude »). Les textes peuvent être fournis par la lecture de textes d'Atelya (traduire_fiche.py
--textes-atelya) pour que la clé d'Atelya joue aussi.

    ..\atelya\.venv\Scripts\python.exe outils\lecture_claude\fiche_depuis_verite.py verites\fr-031 ..\atelya\vrais-plans\lot-2026-11-05\fr-031.jpg --sortie ..\atelya\lectures-claude\fr-031-fiche.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.lecture_claude import SCHEMA, TYPES_PIECES, controler_fiche, taille_pour_claude  # noqa: E402

TYPES = {"sdb": "salle_d_eau", "sde": "salle_d_eau", "sejour_cuisine": "sejour", "principale": "sejour"}


def fiche_depuis_verite(dossier: Path, image: Path) -> dict:
    saisie = json.loads((dossier / "verite-saisie.json").read_text(encoding="utf-8"))
    verite = json.loads((dossier / "verite.json").read_text(encoding="utf-8"))
    with Image.open(image) as im:
        W, H = im.size
    if (W, H) != (verite["largeur"], verite["hauteur"]):
        raise ValueError(f"l'image fait {W} × {H} px, la vérité a été tracée sur {verite['largeur']} × {verite['hauteur']} px")
    l2, h2 = taille_pour_claude(W, H)
    k = l2 / W  # pixels de l'image envoyée / pixels du plan

    def p(v: float) -> float:
        return round(v * k, 2)

    murs = [{"id": f"M{i + 1}", "axe": [p(x0), p(y0), p(x1), p(y1)], "epaisseur_px": max(p(ep), 0.5)}
            for i, (x0, y0, x1, y1, ep) in enumerate(verite["murs_px"])]  # les murs FINAUX de la vérité (affinés)
    ouvertures = [{"id": f"O{i + 1}", "type": t, "bords": [p(x0), p(y0), p(x1), p(y1)]}
                  for i, (t, x0, y0, x1, y1) in enumerate(saisie["ouvertures"])]
    pieces = []
    for i, (nom, type_, x, y) in enumerate(saisie["pieces"]):
        type_ = TYPES.get(type_, type_)
        if type_ not in TYPES_PIECES:
            raise ValueError(f"type de pièce inconnu dans la vérité : {type_}")
        pieces.append({"id": f"P{i + 1}", "nom": nom, "type": type_, "point": [p(x), p(y)]})
    inconnue = bool(verite.get("echelle_inconnue"))
    return {"schema": SCHEMA, "image": {"nom": image.name, "largeur": l2, "hauteur": h2},
            "murs": murs, "ouvertures": ouvertures, "pieces": pieces,
            "echelle_proposee": {"px_par_m": round(verite["px_par_m"] * k, 4), "source": "portes" if inconnue else "cotes",
                                 "explication": f"échelle de la vérité ({verite.get('echelle_source', '')})"[:300]},
            "doutes": [{"raison": str(t)[:300], "gravite": "faible"} for t in verite.get("incertain", [])]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Vérité de vrai plan → fiche lecture-claude/0.1")
    ap.add_argument("verite", type=Path, help="dossier de la vérité (verite-saisie.json + verite.json)")
    ap.add_argument("image", type=Path, help="l'image du plan sur laquelle la vérité a été tracée")
    ap.add_argument("--sortie", type=Path, required=True)
    a = ap.parse_args()
    for f in (a.verite / "verite-saisie.json", a.verite / "verite.json", a.image):
        if not f.is_file():
            print(f"PLANTÉ : fichier introuvable : {f}", flush=True)
            return 2
    fiche = fiche_depuis_verite(a.verite, a.image)
    controle = controler_fiche(fiche, (fiche["image"]["largeur"], fiche["image"]["hauteur"]))
    if controle.refusee:
        print("PLANTÉ : fiche refusée : " + "; ".join(p.raison for p in controle.problemes), flush=True)
        return 1
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    a.sortie.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.verite.name} : {len(fiche['murs'])} murs, {len(fiche['ouvertures'])} ouvertures, {len(fiche['pieces'])} pièces, "
          f"image envoyée {fiche['image']['largeur']} × {fiche['image']['hauteur']} px : {a.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
