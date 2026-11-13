"""Plusieurs éclairages tout prêts dans la maquette Blender (B2 temps 2, demande NT du 09/11/2026).

Pourquoi : un même logement se montre sous plusieurs lumières (jour, ciel voilé, fin de journée, soirée, nuit). NT veut les
trouver DANS la maquette Blender et passer de l'une à l'autre lui-même : une SCÈNE Blender par éclairage (menu des scènes, en
haut à droite de Blender). Les scènes se partagent murs, sols, menuiseries, portails et caméras ; chacune a son ciel, ses
lampes allumées ou non, et son réglage « de photographe » (exposition et balance des blancs, voir moteur/blender/rendre.py).

Règle 20 (NT) : moment flatteur oui, soleil inventé non. Tant que l'orientation réelle du logement n'est pas connue (étape
B3), le soleil garde la direction PROVISOIRE du plan (habillage.SOLEIL_AZIMUT) ; seule sa hauteur change d'une ambiance à
l'autre. Les murs restent neutres (balance des blancs forte de jour), comme sur les photos d'annonce.

Les lampes : les plafonniers de chaque pièce (habillage.lumieres), éteints de jour, allumés en soirée et la nuit.
"""
from __future__ import annotations

import math
from pathlib import Path

# Le ciel : « physique » = ciel de Blender calculé comme l'atmosphère (soleil compris, à la hauteur donnée en degrés ; sous
# l'horizon c'est le crépuscule) ; « couvert » = ciel gris uniforme plus clair au zénith (ciel couvert de la CIE), sans soleil.
# clarte_murs : clarté visée des murs blancs (0,55 = pièce claire d'annonce) ; balance : part de la teinte des murs corrigée
# (1 = murs parfaitement neutres, 0 = la couleur de la lumière est gardée : soirée chaude).
AMBIANCES = [
    {"id": "jour_soleil", "nom": "1 Jour ensoleillé", "ciel": "physique", "hauteur_soleil": 50.0, "disque_soleil": True,
     "lampes": False, "clarte_murs": 0.55, "balance": 0.85},
    {"id": "jour_voile", "nom": "2 Jour voilé", "ciel": "couvert", "lampes": False, "clarte_murs": 0.47, "balance": 0.95},
    {"id": "fin_de_journee", "nom": "3 Fin de journée", "ciel": "physique", "hauteur_soleil": 7.0, "disque_soleil": True,
     "lampes": False, "clarte_murs": 0.50, "balance": 0.25},
    {"id": "soiree", "nom": "4 Soirée lampes allumées", "ciel": "physique", "hauteur_soleil": -3.0, "disque_soleil": False,
     "lampes": True, "clarte_murs": 0.45, "balance": 0.35},
    {"id": "nuit", "nom": "5 Nuit", "ciel": "nuit", "lampes": True, "clarte_murs": 0.35, "balance": 0.30},
]
AMBIANCE_DE_REFERENCE = "jour_soleil"  # la teinte des sols vus sur photo est réglée dans celle-ci (regler_teintes.py)

COULEUR_COUVERT = (0.92, 0.95, 1.0)  # ciel couvert : blanc à peine bleuté
FORCE_COUVERT = 1.2
COULEUR_NUIT = (0.010, 0.014, 0.030)  # nuit en ville : un fond bleu nuit très sombre
COULEUR_LAMPES = (1.0, 0.82, 0.62)  # blanc chaud (≈ 2 700 K) des ampoules d'habitation


def ambiances(soleil: dict | None) -> list[dict]:
    """Les ambiances avec la direction du soleil (rotation de Blender) tirée du soleil du plan de construction.

    soleil : la lumière « soleil » de construction.json ({"direction": [dx, dy, dz]}, direction de la lumière). Sans soleil,
    direction par défaut (lumière venant du sud-sud-ouest)."""
    if soleil:
        vers = [-c for c in soleil["direction"]]
        rotation = math.atan2(vers[0], vers[1])  # convention de Blender : 0 = soleil vers +y, 90° = vers +x
    else:
        rotation = math.radians(200.0)
    sortie = []
    for a in AMBIANCES:
        b = dict(a)
        if b["ciel"] == "physique":
            b["rotation_soleil"] = rotation
            b["elevation_soleil"] = math.radians(b["hauteur_soleil"])
        b["couleur_lampes"] = list(COULEUR_LAMPES)
        b["couleur_couvert"], b["force_couvert"] = list(COULEUR_COUVERT), FORCE_COUVERT
        b["couleur_nuit"] = list(COULEUR_NUIT)
        sortie.append(b)
    return sortie


def poser(construction: str | Path, maquette: str | Path, sortie: str | Path) -> Path:
    """Écrit les ambiances (eclairages.json à côté de la sortie) et fait poser les scènes par Blender."""
    import json

    from moteur.construire import DOSSIER_SCRIPTS, lancer_blender

    plan = json.loads(Path(construction).read_text(encoding="utf-8"))
    soleil = next((l for l in plan.get("lumieres", []) if l["type"] == "soleil"), None)
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    chemin = sortie.parent / "eclairages.json"
    chemin.write_text(json.dumps(ambiances(soleil), indent=1, ensure_ascii=False), encoding="utf-8")
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "poser_eclairages.py"), "--", str(chemin), str(sortie))
    return sortie


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pose une scène Blender par éclairage dans une maquette.")
    parser.add_argument("construction", help="construction.json de la maquette (pour la direction du soleil)")
    parser.add_argument("maquette", help="maquette.blend d'origine (non modifiée si la sortie est ailleurs)")
    parser.add_argument("sortie", help="maquette avec les éclairages (.blend)")
    args = parser.parse_args()
    print(f"Maquette avec éclairages : {poser(args.construction, args.maquette, args.sortie)}")


if __name__ == "__main__":
    main()
