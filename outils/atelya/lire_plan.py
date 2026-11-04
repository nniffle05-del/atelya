"""Lit un plan de bout en bout, comme pour un vrai client : plan (image ou PDF) → coloriage → aiguillage → échelle
→ logement → doutes. Sur le PC seulement (il faut PyTorch et les modèles).

Depuis le dossier du dépôt (atelya-code) :

    ..\\atelya\\.venv\\Scripts\\python.exe outils\\atelya\\lire_plan.py mon-plan.pdf --sortie ..\\atelya\\lectures

Pour chaque page, écrit dans <sortie>\\<nom>\\ : ecran.html (double-clic : l'écran de vérification avec ce plan) ;
plan.png (l'image lue) et verification.json, les deux fichiers qu'il contient ; logement.json, lecture.json (décision, doutes, échelle, modèle gardé, durées), coloriage.png
et coloriage-doute.png du modèle gardé.
Un plan refusé n'est pas un plantage : la commande le dit et finit normalement. Un plantage finit par un code ≠ 0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur.lecture_complete import VERSION_LECTURE_COMPLETE, FichierNonLisible, PlanLu, lire_plan, plans_du_fichier  # noqa: E402
from moteur.preparer_verification import verification_du_plan  # noqa: E402

sys.path.insert(0, str(RACINE / "outils" / "verification-plan" / "scripts"))
from page_unique import fabriquer as fabriquer_page_unique  # noqa: E402

MODELES = {"e5": "resultats-essai-5/atelya-essai-4.pt", "e7": "resultats-essai-7b/atelya-essai-7.pt"}


def colorieurs(atelya: Path, noms: list[str]) -> dict:
    """Les fonctions qui colorient, à partir des modèles du PC (entrainer.py et oeil.py sont dans l'ancien dossier)."""
    sys.path.insert(0, str(atelya.resolve()))
    import torch
    from colorier_angles import predire_avec_doute  # même lecture sous 4 angles que tous les bancs
    from oeil import charger_modele

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sortie = {}
    for nom in noms:
        chemin = atelya / MODELES[nom]
        if not chemin.is_file():
            raise FileNotFoundError(f"modèle introuvable : {chemin}")
        modele = charger_modele(chemin, dev)
        sortie[nom] = lambda img, m=modele: predire_avec_doute(m, img, dev)
    return sortie


def ecrire(plan: PlanLu, dossier: Path, duree_s: float) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    g = plan.gardee
    Image.fromarray(plan.source.image).save(dossier / "plan.png")
    if g.coloriage is not None:
        Image.fromarray(g.coloriage).save(dossier / "coloriage.png")
    if g.carte is not None:
        Image.fromarray(g.carte).save(dossier / "coloriage-doute.png")
    if g.logement is not None:
        (dossier / "logement.json").write_text(json.dumps(g.logement, ensure_ascii=False, indent=1), encoding="utf-8")
    verification = verification_du_plan(plan)
    if verification is not None:
        (dossier / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        fabriquer_page_unique(dossier)
    resume = {"version": VERSION_LECTURE_COMPLETE, "nom": plan.source.nom, "page": plan.source.page,
              "nature": plan.source.nature, "decision": plan.decision, "modele": g.modele, "aiguillage": plan.aiguillage,
              "echelle": g.echelle, "doutes": g.examen["doutes"], "infos": g.infos, "erreur": g.erreur,
              "details": g.details, "duree_s": round(duree_s, 1),
              "autres_lectures": {k: {"decision": v.examen["decision"], "echelle": v.echelle, "infos": v.infos}
                                  for k, v in plan.lectures.items() if k != g.modele}}
    (dossier / "lecture.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


def _compte(g) -> str:
    if g.logement is None:
        return g.erreur or "rien de lu"
    return f"{len(g.logement['murs'])} murs, {len(g.logement['ouvertures'])} ouvertures, {len(g.logement['pieces'])} pièces"


def main() -> int:
    ap = argparse.ArgumentParser(description="Lire un plan de bout en bout (image ou PDF)")
    ap.add_argument("plans", nargs="+", type=Path, help="fichiers image ou PDF")
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--atelya", type=Path, default=Path("../atelya"), help="ancien dossier (modèles, entrainer.py, oeil.py)")
    ap.add_argument("--seul", choices=sorted(MODELES), help="un seul modèle, sans aiguillage (comparaisons)")
    ap.add_argument("--sans-noms", action="store_true", help="ne pas lire les noms de pièces (comme les bancs)")
    a = ap.parse_args()

    if not a.atelya.is_dir():
        print(f"PLANTÉ : dossier introuvable : {a.atelya}", flush=True)
        return 2
    fonctions = colorieurs(a.atelya, [a.seul] if a.seul else list(MODELES))
    bilan = {"lu": 0, "a_verifier": 0, "refuse": 0}
    for fichier in a.plans:
        try:
            sources = plans_du_fichier(fichier)
        except FichierNonLisible as e:
            print(f"{fichier.name} : REFUSÉ, {e}", flush=True)
            bilan["refuse"] += 1
            continue
        for source in sources:
            t0 = time.time()
            plan = lire_plan(source, fonctions, avec_noms=not a.sans_noms)
            duree = time.time() - t0
            ecrire(plan, a.sortie / source.nom, duree)
            g = plan.gardee
            forts = sum(d["gravite"] == "fort" for d in g.examen["doutes"])
            print(f"{source.nom} : {plan.decision}, modèle {g.modele} ({plan.aiguillage}), échelle {g.echelle['etat']} "
                  f"({g.echelle['source']}), {_compte(g)}, {forts} doutes forts, {duree:.1f} s", flush=True)
            bilan[plan.decision] += 1
    print(f"FINI : {bilan['lu']} lus, {bilan['a_verifier']} à vérifier, {bilan['refuse']} refusés", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
