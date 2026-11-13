"""Inscrire le VRAI soleil dans la fiche de scène d'un logement (scene-atelya.json, paquet Unreal) (11/11/2026).

    python outils/atelya/soleil_reel.py <scene-atelya.json> --nord 0 [--source "…"] [--latitude 46.6 --longitude 2.4 --date 2026-04-21]

--nord : direction du nord sur le plan, en degrés depuis le haut du plan, sens des aiguilles d'une montre (0 = le haut du plan est
au nord ; « la façade du bas est au sud » donne 0). Les éclairages avec soleil (jour, fin de journée, soirée) reçoivent la
direction et la hauteur calculées (moteur/soleil.py) ; la fiche garde d'où viennent ces données et leur statut (« mesure » si le
client les a données à l'écran, « estime » si dites oralement, « ajoute » si supposées par Atelya).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import soleil  # noqa: E402


def inscrire(fiche_json: Path, nord_deg: float, source: str, lieu: dict | None = None, jour: date | None = None,
             statut_orientation: str = "estime") -> dict:
    fiche = json.loads(fiche_json.read_text(encoding="utf-8"))
    lieu_donne = lieu is not None
    lieu = lieu or soleil.LIEU_DEFAUT
    jour_donne = jour is not None
    jour = jour or soleil.DATE_DEFAUT
    soleils = soleil.soleils_des_eclairages(nord_deg, lieu, jour)
    for a in fiche.get("eclairages", []):
        s = soleils.get(a.get("id"))
        if s:
            a["rotation_soleil"], a["elevation_soleil"] = s["rotation_soleil"], s["elevation_soleil"]
            a["hauteur_soleil"] = s["hauteur_deg"]
            a["heure_legale"] = s["heure_legale"]
    fiche["soleil"] = {
        "orientation": {"nord_deg": nord_deg, "statut": statut_orientation, "source": source},
        "lieu": {**lieu, "statut": "mesure" if lieu_donne else "ajoute"},
        "date": {"jour": jour.isoformat(), "statut": "mesure" if jour_donne else "ajoute"},
        "eclairages": {k: {c: v for c, v in s.items() if c not in ("rotation_soleil", "elevation_soleil")}
                       for k, s in soleils.items()},
        "calcul": "moteur/soleil.py (formules NOAA)",
    }
    soleil_plan = next((l for l in fiche.get("lumieres", []) if l.get("genre") == "soleil"), None)
    if soleil_plan is not None and "jour_soleil" in soleils:
        soleil_plan["direction"] = [-c for c in soleils["jour_soleil"]["vers_le_soleil"]]
        soleil_plan["note"] = "direction vers laquelle va la lumière (soleil réel du « Jour ensoleillé »)"
    fiche_json.write_text(json.dumps(fiche, indent=1, ensure_ascii=False), encoding="utf-8")
    return fiche["soleil"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fiche")
    p.add_argument("--nord", type=float, required=True)
    p.add_argument("--source", default="non précisée")
    p.add_argument("--statut", default="estime", choices=["mesure", "estime", "ajoute"])
    p.add_argument("--latitude", type=float)
    p.add_argument("--longitude", type=float)
    p.add_argument("--date")
    a = p.parse_args()
    lieu = {"latitude": a.latitude, "longitude": a.longitude, "nom": "donné"} if a.latitude is not None else None
    print(json.dumps(inscrire(Path(a.fiche), a.nord, a.source, lieu, date.fromisoformat(a.date) if a.date else None, a.statut),
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
