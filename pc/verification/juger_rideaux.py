r"""LE JUGE DES RIDEAUX, 1re pièce (19/11/2026) : les rideaux d'un logement fait par Atelya contre le relevé fait à la main.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_rideaux.py app-004=<logement-meuble.json> [app-001=<…>]

Le relevé (verites/<logement>/rideaux.json) dit, pour chaque fenêtre dont une photo montre l'habillage : voilage ou non, rideaux
épais ou non, combien de pans et de quel côté (« gauche » / « droite », vu de la pièce, face à la fenêtre). Ce juge compare :
la SORTE (voilage, rideaux épais), le NOMBRE de pans et leur CÔTÉ. Il ne regarde pas le film : il dit si le LOGEMENT est juste ;
le film se regarde à côté de la photo (pc/verification/vues_rideaux.sh). Code de sortie 0 même s'il y a des fautes : on lit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import equipements as eq  # noqa: E402


def pans_vus_de_la_piece(ouverture: dict, logement: dict) -> list[str]:
    """Les pans de rideaux épais de l'ouverture, dits « gauche » / « droite » vu de la pièce (sans mesure : les deux)."""
    r = ouverture.get("rideaux") or {}
    if not r.get("rideaux"):
        return []
    if not r.get("pans"):
        return ["droite", "gauche"]
    baie = eq.repere_de_la_baie(ouverture, logement)
    # vu de la pièce, la fin du mur est à gauche quand la normale (vers la pièce) est à gauche du mur
    fin_a_gauche = float(baie["t"][0] * baie["n"][1] - baie["t"][1] * baie["n"][0]) > 0
    cote = {"fin": "gauche" if fin_a_gauche else "droite", "debut": "droite" if fin_a_gauche else "gauche"}
    return sorted(cote[p["cote"]] for p in r["pans"])


def juger(cas: str, logement: dict) -> dict:
    verite = json.loads((RACINE / "verites" / cas / "rideaux.json").read_text(encoding="utf-8"))
    ouvertures = {o["id"]: o for o in logement.get("ouvertures", [])}
    bilan = {"fenetres": 0, "sorte": 0, "nombre": 0, "cote": 0, "lignes": []}
    for ident, v in verite["fenetres"].items():
        o = ouvertures.get(ident)
        r = (o or {}).get("rideaux") or {}
        pans = pans_vus_de_la_piece(o, logement) if o else []
        sorte = bool(r.get("voilage")) == v["voilage"] and bool(r.get("rideaux")) == v["rideaux"]
        nombre = sorte and len(pans) == len(v["pans"])
        cote = nombre and pans == sorted(v["pans"])
        bilan["fenetres"] += 1
        bilan["sorte"] += sorte
        bilan["nombre"] += bool(nombre)
        bilan["cote"] += bool(cote)
        dire = lambda voilage, epais, p: " + ".join(x for x in ("voilage" if voilage else "", f"rideaux ({', '.join(p) or '—'})" if epais else "") if x) or "rien"
        bilan["lignes"].append(f"  {'juste' if cote else 'FAUX '}  {ident:4s} {v['piece']:32s} photos : {dire(v['voilage'], v['rideaux'], sorted(v['pans'])):38s} "
                               f"Atelya : {dire(r.get('voilage'), r.get('rideaux'), pans)}")
    return bilan


def main() -> int:
    total = {"fenetres": 0, "sorte": 0, "nombre": 0, "cote": 0}
    for arg in sys.argv[1:]:
        cas, _, chemin = arg.partition("=")
        bilan = juger(cas, json.loads(Path(chemin).read_text(encoding="utf-8")))
        print(f"{cas} ({chemin})")
        print("\n".join(bilan["lignes"]))
        for k in total:
            total[k] += bilan[k]
    n = total["fenetres"]
    print(f"\nRIDEAUX, {n} fenêtres relevées : bonne sorte {total['sorte']}/{n} ; bon nombre de pans {total['nombre']}/{n} ; "
          f"pans du bon côté {total['cote']}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
