r"""Étape B1 (maquette sans jour) : mesure des trous au sol et au plafond sur les vrais plans dont Fable a fait la vérité,
AVANT (géométrie d'avant B1, fichier donné) et APRÈS (géométrie du dépôt).

Chaîne pour chaque plan : vérité de Fable → fiche lecture-claude (outils/lecture_claude/fiche_depuis_verite.py) → traducteur
(moteur.traduire_claude, sans OCR) → logement → briques → moteur.controle_maquette.

    ..\atelya\.venv\Scripts\python.exe pc\b1\mesurer_jours.py --avant <geometrie_avant.py> --sortie ..\atelya\b1\jours.json fr-021 fr-022 ...
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_claude"))

from fiche_depuis_verite import fiche_depuis_verite  # noqa: E402

from moteur import geometrie as apres  # noqa: E402
from moteur.controle_maquette import controler  # noqa: E402
from moteur.lecture_claude import controler_fiche  # noqa: E402
from moteur.lecture_complete import plans_du_fichier  # noqa: E402
from moteur.logement import Logement  # noqa: E402
from moteur.traduire_claude import traduire  # noqa: E402

DOSSIERS_IMAGES = [Path("../atelya/verites-lot2"), Path("../atelya/vrais-plans/lot-2026-11-05"),
                   Path("../atelya/vrais-plans/lot-2026-10-31"), Path("../atelya/vrais-plans/travail-2026-11-04")]


def _image(nom: str, fichier: str) -> Path | None:
    for d in DOSSIERS_IMAGES:
        for c in (d / nom / fichier, d / fichier):
            if c.is_file():
                return c
    return None


def _mesure(geo, log: Logement) -> dict:
    try:
        briques = [apres.Brique(**b.__dict__) for b in geo.calculer_briques(log)]
    except ValueError as e:
        return {"refus": str(e)[:150]}
    r = controler(briques, log.hauteur_sous_plafond)
    return {"sol": r["sol"]["trous"], "sol_m2": r["sol"]["aire_m2"], "plafond": r["plafond"]["trous"],
            "plafond_m2": r["plafond"]["aire_m2"], "plus_grands": r["sol"]["detail"][:3], "superposes_m2": r["sols_superposes_m2"], "murs_superposes_m2": r["murs_superposes_m2"],
            "bouche_trous": sum(1 for b in briques if b.id.startswith("joint_"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--avant", type=Path, required=True, help="geometrie.py d'avant B1 (git show <commit>:moteur/geometrie.py)")
    ap.add_argument("--verites", type=Path, default=RACINE / "verites")
    ap.add_argument("--sortie", type=Path, required=True)
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("geometrie_avant", a.avant)
    avant = importlib.util.module_from_spec(spec)
    sys.modules["geometrie_avant"] = avant
    spec.loader.exec_module(avant)
    lignes = []
    for nom in a.plans:
        t0 = time.time()
        dossier = a.verites / nom
        verite = json.loads((dossier / "verite.json").read_text(encoding="utf-8"))
        image = _image(nom, verite["image"])
        if image is None:
            print(f"{nom} : image introuvable ({verite['image']})", flush=True)
            lignes.append({"plan": nom, "erreur": "image introuvable"})
            continue
        try:
            fiche = fiche_depuis_verite(dossier, image)
        except ValueError as e:
            print(f"{nom} : {e}", flush=True)
            lignes.append({"plan": nom, "erreur": str(e)})
            continue
        source = plans_du_fichier(image)[0]
        k = fiche["image"]["largeur"] / source.image.shape[1]
        lu = traduire(source, controler_fiche(fiche, (fiche["image"]["largeur"], fiche["image"]["hauteur"])), k, ocr=False)
        if lu.gardee.logement is None:
            print(f"{nom} : traduction refusée ({lu.gardee.erreur})", flush=True)
            lignes.append({"plan": nom, "erreur": lu.gardee.erreur})
            continue
        log = Logement.model_validate(lu.gardee.logement)
        ligne = {"plan": nom, "pieces": len(log.pieces), "avant": _mesure(avant, log), "apres": _mesure(apres, log),
                 "secondes": round(time.time() - t0, 1)}
        lignes.append(ligne)
        av, ap_ = ligne["avant"], ligne["apres"]
        print(f"{nom} : avant {av.get('refus') or (av['sol'], av['sol_m2'], av['plafond'])} | après "
              f"{ap_.get('refus') or (ap_['sol'], ap_['sol_m2'], ap_['plafond'], 'bouche-trous', ap_['bouche_trous'], 'sols superposés', ap_['superposes_m2'], 'murs superposés', ap_['murs_superposes_m2'])}", flush=True)
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    a.sortie.write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
