r"""BANC « FENÊTRES RÉTRÉCIES EXPRÈS » (20/11/2026, étape F1) : Atelya retrouve-t-il la largeur d'une fenêtre que le plan dessine
trop étroite ?

    ..\atelya\.venv\Scripts\python.exe pc\verification\banc_baies_retrecies.py [--part 0.5] [app-001 app-002 app-004]

Pourquoi : sur les trois logements, UNE seule fenêtre est nettement contredite par les photos (le coin repas d'app-001) : un
cas ne dit pas si la règle marche ailleurs. Ici, chaque baie du relevé que les photos montrent « comme le plan » est rétrécie
exprès (à `part` fois sa largeur, autour de son milieu ; statut « estime », comme un plan sans cotes), une à la fois ; Atelya
doit la voir trop étroite et l'élargir. On compte : retrouvées, et l'écart entre la largeur rendue et celle du plan d'origine.
Les baies que les photos ne voient qu'en partie (bord coupé, meuble devant) ne peuvent pas toutes être retrouvées : c'est dit.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cas", nargs="*", default=["app-001", "app-002", "app-004"])
    ap.add_argument("--part", type=float, default=0.5, help="la baie est rétrécie à cette part de sa largeur (défaut 0,5)")
    a = ap.parse_args()
    from banc_ressemblance import CAS
    from moteur import largeur_baies as lb
    from poser_photos_lues import objets_des_photos
    from sonde_largeur_fenetres import CHAINES, PC

    retrouvees, essayees, ecarts, touchees_a_tort = 0, 0, [], 0
    for cas in a.cas:
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        logement = json.loads((CHAINES[cas] / "logement-depart.json").read_text(encoding="utf-8"))
        objets = objets_des_photos(fiche, PC / "lectures-photos" / cas)
        releve = json.loads((RACINE / "verites" / cas / "baies.json").read_text(encoding="utf-8"))["baies"]
        print(f"  {cas}")
        for ident, r in releve.items():
            if r["verdict"] != "comme_le_plan":
                continue
            lg = copy.deepcopy(logement)
            o = next(o for o in lg["ouvertures"] if o["id"] == ident)
            vraie = float(o["largeur"])
            o.update(position=float(o["position"]) + vraie * (1 - a.part) / 2, largeur=vraie * a.part, statut="estime", source="banc")
            mesures = lb.lire(lg, fiche, objets)
            apres, changes, doutes = lb.elargir(lg, mesures)
            vues = sorted(round(m["s"][1] - m["s"][0], 2) for m in mesures if m["baie"] == ident)
            essayees += 1
            c = next((c for c in changes if c["id"] == ident), None)
            touchees_a_tort += sum(1 for c in changes if c["id"] != ident and releve.get(c["id"], {}).get("verdict") != "plus_large")
            if c is not None:
                retrouvees += 1
                ecarts.append(c["apres"]["largeur"] - vraie)
            print(f"    {ident} : plan {vraie:.2f} m, rétrécie à {vraie * a.part:.2f} m, vue {vues or 'par aucune photo'} → "
                  + (f"élargie à {c['apres']['largeur']:.2f} m (écart {c['apres']['largeur'] - vraie:+.2f} m)" if c
                     else "PAS retrouvée" + (" (doute : photos pas d'accord)" if any(d["id"] == ident for d in doutes) else "")))
    moyen = sum(abs(e) for e in ecarts) / len(ecarts) if ecarts else float("nan")
    print(f"BANC DES FENÊTRES RÉTRÉCIES (à {a.part:.0%}) : retrouvées {retrouvees} sur {essayees} ; écart moyen à la largeur du plan "
          f"{moyen:.2f} m, au pire {max((abs(e) for e in ecarts), default=float('nan')):.2f} m ; autres baies touchées à tort : {touchees_a_tort}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
