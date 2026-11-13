"""Les AVIS de NT sur un film : le réalisateur d'Atelya apprend d'eux (11/11/2026).

    python outils/atelya/noter_film.py <dossier_du_film> "1:bien" "3:trop_pres,ennuyeux" "tous:trop_rapide"

<dossier_du_film> : celui de outils/unreal/film_unreal.py (plans.json). Chaque argument : un numéro de plan (ou « tous ») puis ses
avis, séparés par des virgules. Avis possibles : voir moteur/realisateur.AVIS (bien, trop_pres, trop_loin, ennuyeux, trop_rapide,
trop_lent, trop_long, trop_court, pas_assez_de_lumiere, contre_jour, piece_mal_montree, pas_assez_de_meubles, trop_haut, trop_bas,
trop_plongeant, pas_assez_plongeant, deforme, pas_assez_large). Les réglages corrigés sont gardés dans
moteur/realisateur_appris.json et servent à TOUS les films suivants.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import realisateur  # noqa: E402


def avis_depuis_arguments(plans: list[dict], arguments: list[str], film: str) -> list[dict]:
    sortie = []
    for arg in arguments:
        cible, _, mots = arg.partition(":")
        mots = [m.strip().lower().replace(" ", "_").replace("é", "e").replace("è", "e") for m in mots.split(",") if m.strip()]
        visés = plans if cible.strip() == "tous" else [p for p in plans if str(p["numero"]) == cible.strip()]
        if not visés:
            raise ValueError(f"plan « {cible} » inconnu (plans 1 à {len(plans)}, ou « tous »)")
        for p in visés:
            sortie.append({"film": film, "date": date.today().isoformat(), "plan": p["numero"], "piece": p["piece"],
                           "avis": mots})
    return sortie


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    dossier = Path(sys.argv[1])
    plans = json.loads((dossier / "plans.json").read_text(encoding="utf-8"))
    avis = avis_depuis_arguments(plans, sys.argv[2:], dossier.name)
    avant = realisateur.savoir_faire()
    apres = realisateur.apprendre(avis)
    for cle in apres:
        if apres[cle] != avant[cle]:
            print(f"  {cle} : {avant[cle]} -> {apres[cle]}")
    print(f"{len(avis)} avis enregistrés ; savoir-faire gardé dans {realisateur.APPRIS}")


if __name__ == "__main__":
    main()
