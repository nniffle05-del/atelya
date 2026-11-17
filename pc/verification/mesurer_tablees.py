r"""Les CHAISES ET TABOURETS posés contre ceux du relevé fait à la main : place et ORIENTATION (étape 3, 17/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_tablees.py <dossier> [<dossier> …] [--version c] [--detail]

Pour chaque dossier (sortie de essai_lecture_photos.py ou mesurer_place_taille.py) : les sièges appariés au relevé (même règle
que la note : à moins de 80 cm, même groupe), leur écart de place moyen, et combien regardent dans le bon sens (à 30° près de
l'orientation relevée : vers leur table). Les tables, îlots et bureaux : écart de place moyen.
Réserve : le relevé place les chaises à ± 30 cm et, autour de la table d'app-001, par symétrie (2 et 2) alors que la photo 04
en montre une en bout de table ; les images restent le juge.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import diag_en_trop as diag  # noqa: E402
import essai_lecture_photos as essai  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402
from moteur.tablees import PORTEUSES, SIEGES  # noqa: E402

BON_SENS_DEG = 30.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossiers", nargs="+", type=Path)
    ap.add_argument("--version", default="c")
    ap.add_argument("--cas", nargs="*", default=["app-001", "app-002"])
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    for dossier in a.dossiers:
        places, sens, tables, a_trouver = [], 0, [], 0
        for cas in a.cas:
            logement = essai.lire(dossier / cas / a.version / "logement-meuble.json")
            releve = essai.charger_releve(cas)
            a_trouver += sum(1 for v in releve if v["categorie"] in SIEGES)
            d = diag.detail(logement, releve, essai.lire(CAS[cas]["fiche"]))
            for v, m in d["exacts"] + d["proches"] + d["hors"]:
                ecart = math.dist(v["position"], m["position"])
                if v["categorie"] in PORTEUSES:
                    tables.append(ecart)
                if v["categorie"] not in SIEGES:
                    continue
                tourne = abs((float(m.get("face", 0.0)) - float(v.get("face", 0.0) or 0.0) + 180.0) % 360.0 - 180.0)
                places.append(ecart)
                sens += tourne <= BON_SENS_DEG
                if a.detail:
                    print(f"   {cas} {v['id']:18s} à {ecart:.2f} m, tourné de {tourne:3.0f}° par rapport au relevé")
        moy = lambda l: f"{sum(l) / len(l):.2f} m" if l else "-"
        print(f"{dossier.name:14s} sièges : {len(places)} retrouvés sur {a_trouver} du relevé, écart de place moyen {moy(places)}, "
              f"{sens} dans le bon sens | tables, îlots, bureaux : {len(tables)}, écart de place moyen {moy(tables)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
