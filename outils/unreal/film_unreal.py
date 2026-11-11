"""Le FILM d'un logement, de bout en bout et sans aucun choix à la main (11/11/2026, règle n° 21).

    python outils/unreal/film_unreal.py <paquet> <nom> <logement.json> [--eclairage jour_soleil] [--moteur lumen_max]
                                        [--duree-plan 6] [--sortie film.mp4] [--sans-import]

1. le RÉALISATEUR (moteur/realisateur.py) choisit les plans d'après le plan du logement : pièces, ordre, points de vue, mouvements ;
   il écrit plans.json et plans.png (vue de dessus) à côté du film ;
2. chaque plan est rendu par outils/unreal/cinematique_unreal.py (le photographe règle l'exposition PIÈCE PAR PIÈCE) ;
3. les plans sont montés bout à bout avec des fondus (outils/unreal/monter_film.py) ; bilan film.json (temps, réglages, plans).
"""
import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cinematique_unreal as cu  # noqa: E402
import monter_film  # noqa: E402

from moteur import realisateur  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paquet")
    p.add_argument("nom")
    p.add_argument("logement")
    p.add_argument("--eclairage", default="jour_soleil")
    p.add_argument("--moteur", default="lumen_max", choices=["lumen", "lumen_max", "path_tracer"])
    p.add_argument("--duree-plan", type=float, help="secondes par plan (défaut : le savoir-faire appris)")
    p.add_argument("--sortie", help="la vidéo du film (défaut : rendus/<nom>/film-<éclairage>/film.mp4)")
    p.add_argument("--sans-import", action="store_true")
    a = p.parse_args()
    debut = time.time()
    paquet = Path(a.paquet)
    fiche = json.loads((paquet / "scene-atelya.json").read_text(encoding="utf-8"))
    ambiance = next((x for x in fiche.get("eclairages", []) if a.eclairage in (x.get("id"), x.get("nom"))), None)
    if ambiance is None:
        sys.exit(f"PLANTÉ : éclairage « {a.eclairage} » absent de la fiche")
    dossier = cu.STUDIO / "Paquets" / "rendus" / a.nom / f"film-{ambiance['id']}"
    dossier.mkdir(parents=True, exist_ok=True)
    logement = json.loads(Path(a.logement).read_text(encoding="utf-8"))
    print("1. Le réalisateur choisit les plans")
    plans = realisateur.realiser(logement, a.duree_plan, scene_eclairage=ambiance.get("nom"))
    if not plans:
        sys.exit("PLANTÉ : le réalisateur n'a trouvé aucun plan")
    (dossier / "plans.json").write_text(json.dumps(plans, indent=1, ensure_ascii=False), encoding="utf-8")
    realisateur.dessiner(logement, plans, dossier / "plans.png")
    for plan in plans:
        print(f"   plan {plan['numero']} : {plan['nom_piece']} ({plan['mouvement']})")
    if not a.sans_import:
        print("2. Import de la maquette dans Unreal")
        cu._python_unreal(cu.SCRIPTS_UE / "importer_maquette.py", paquet.as_posix(), a.nom)
    rendus = []
    for plan in plans:
        trajet = dossier / f"trajet-plan{plan['numero']}.json"
        trajet.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"3. Plan {plan['numero']}/{len(plans)} : {plan['nom_piece']}")
        # pièce sans fenêtre filmée de jour : son plafonnier est allumé (comme un photographe d'immobilier)
        lampes = [plan["piece"]] if not plan.get("lumiere_du_jour", True) and not ambiance.get("lampes") else None
        bilan = cu.un_eclairage(paquet, a.nom, trajet, ambiance, a.moteur, suffixe=f"-film-plan{plan['numero']}",
                                lampes_pieces=lampes)
        rendus.append(bilan)
    sortie = Path(a.sortie) if a.sortie else dossier / "film.mp4"
    print("4. Montage")
    montage = monter_film.monter(sortie, [Path(b["video"]).parent for b in rendus])
    bilan = {"logement": logement.get("projet_id"), "eclairage": ambiance["id"], "moteur": a.moteur, "plans": len(plans),
             "duree_film_s": montage["duree_s"], "images": montage["images"], "format": montage["format"],
             "calcul_total_min": round((time.time() - debut) / 60, 1),
             "rendu_seul_min": round(sum(b["rendu_s"] for b in rendus) / 60, 1), "film": str(sortie),
             "detail": [{"plan": pl["numero"], "piece": pl["piece"], "mouvement": pl["mouvement"],
                         "exposition_unreal": b["controles"][-1]["exposition_unreal"],
                         "murs_ecart_crans": b["controles"][-1]["correction"]} for pl, b in zip(plans, rendus)]}
    (dossier / "film.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Film : {sortie} ({bilan['duree_film_s']} s, {bilan['plans']} plans) ; calcul {bilan['calcul_total_min']} min")


if __name__ == "__main__":
    main()
