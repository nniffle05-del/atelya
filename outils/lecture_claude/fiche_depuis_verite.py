r"""Une VÉRITÉ de vrai plan (tracée par Fable, outils/verite/faire_verite.py) → une fiche lecture-claude/0.1, comme si Claude
avait lu ce plan presque parfaitement.

Pourquoi (décision NT du 08/11/2026) : l'API ne sera testée qu'à la fin ; en attendant, une vérité de Fable tient lieu de
lecture de Claude pour faire travailler tout ce qui suit (traducteur, écran de vérification, 3D Blender) sur un VRAI plan.
Plans d'ENTRAÎNEMENT seulement (vérités Fable relues : fr-021 à fr-027, fr-029 à fr-041) : jamais les 13 plans d'examen pour
régler quoi que ce soit.

Ce que la vérité ne contient pas, la fiche ne l'invente pas : aucun texte (ni cote, ni surface) ; l'échelle proposée est celle
de la vérité (la « clé de Claude »).

Une convention des vérités est retirée (étape B1, 08/11/2026) : pour fermer une pièce sans cloison (cuisine ouverte, front de
placard), Fable trace un FAUX MUR très fin presque entièrement occupé par une « porte » de toute la largeur. En 3D, cela donnait
un mur de 2 cm, un linteau suspendu et un battant de porte de 2 à 3 m. Un tel mur (moins de FAUX_MUR_EPAISSEUR, couvert à plus de
FAUX_MUR_COUVERT par ses ouvertures) est retiré avec ses ouvertures, et chaque pièce reçoit son contour (comme Claude le donne) :
les deux pièces restent deux pièces, sans mur entre elles. Les textes peuvent être fournis par la lecture de textes d'Atelya (traduire_fiche.py
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
FAUX_MUR_EPAISSEUR = 0.05  # m
FAUX_MUR_COUVERT = 0.85  # part de la longueur du mur occupée par ses ouvertures


def _faux_murs(logement: dict) -> set[str]:
    """Les ids des faux murs de la vérité (voir la tête du module)."""
    import math

    faux = set()
    for m in logement["murs"]:
        longueur = math.dist(m["debut"], m["fin"])
        ouvert = sum(o["largeur"] for o in logement["ouvertures"] if o["mur"] == m["id"])
        if m["epaisseur"] < FAUX_MUR_EPAISSEUR and longueur > 0 and ouvert >= FAUX_MUR_COUVERT * longueur:
            faux.add(m["id"])
    return faux


def _dans(x: float, y: float, contour) -> bool:
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


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

    logement = json.loads((dossier / "logement.json").read_text(encoding="utf-8"))  # mêmes ordres que la saisie (M1…, O1…)
    faux = _faux_murs(logement)
    murs = [{"id": f"M{i + 1}", "axe": [p(x0), p(y0), p(x1), p(y1)], "epaisseur_px": max(p(ep), 0.5)}
            for i, (x0, y0, x1, y1, ep) in enumerate(verite["murs_px"])  # les murs FINAUX de la vérité (affinés)
            if f"M{i + 1}" not in faux]
    sur_un_faux_mur = {o["id"] for o in logement["ouvertures"] if o["mur"] in faux}
    ouvertures = [{"id": f"O{i + 1}", "type": t, "bords": [p(x0), p(y0), p(x1), p(y1)]}
                  for i, (t, x0, y0, x1, y1) in enumerate(saisie["ouvertures"]) if f"O{i + 1}" not in sur_un_faux_mur]
    s, (ox, oy) = verite["px_par_m"], verite["origine_px"]
    contours = [[(ox + x * s, oy - y * s) for x, y in q["contour"]] for q in logement["pieces"]]  # mètres → pixels du plan
    pieces = []
    for i, (nom, type_, x, y) in enumerate(saisie["pieces"]):
        type_ = TYPES.get(type_, type_)
        if type_ not in TYPES_PIECES:
            raise ValueError(f"type de pièce inconnu dans la vérité : {type_}")
        piece = {"id": f"P{i + 1}", "nom": nom, "type": type_, "point": [p(x), p(y)]}
        contour = next((c for c in contours if _dans(x, y, c)), None)
        if contour is not None:
            piece["contour"] = [[p(u), p(v)] for u, v in contour]
        pieces.append(piece)
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
