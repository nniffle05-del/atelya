r"""La TAILLE des meubles posés contre celle du relevé fait à la main (17/11/2026, « place et taille justes »).

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_tailles.py <dossier> [<dossier> …] [--version c] [--detail]

Pour chaque dossier (sortie de essai_lecture_photos.py ou mesurer_place_taille.py) : les meubles appariés au relevé complété
(même règle que la note : à moins de 80 cm, même groupe), et pour eux l'écart de LARGEUR (le grand côté au sol), en % de la
vraie ; séparé entre les meubles adossés (armoires, buffets, bibliothèques, cuisines : moteur.photos_lues.ADOSSES) et les autres
(chaises et tapis exclus : leur taille ne se relève pas). Dit aussi l'écart de place moyen des adossés.
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
from moteur.photos_lues import ADOSSES  # noqa: E402

SANS_TAILLE = ("chaise", "chaise_de_bureau", "tabouret_haut", "tapis", "lampadaire", "lampe", "plante")
grand = lambda m: max(m["dimensions"][0], m["dimensions"][1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossiers", nargs="+", type=Path)
    ap.add_argument("--version", default="c")
    ap.add_argument("--cas", nargs="*", default=["app-001", "app-002"])
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    for dossier in a.dossiers:
        adosses, autres, places = [], [], []
        for cas in a.cas:
            logement = essai.lire(dossier / cas / a.version / "logement-meuble.json")
            d = diag.detail(logement, essai.charger_releve(cas), essai.lire(CAS[cas]["fiche"]))
            for v, m in d["exacts"] + d["proches"] + d["hors"]:
                if v["categorie"] in SANS_TAILLE:
                    continue
                ecart = abs(grand(m) - grand(v)) / grand(v)
                (adosses if v["categorie"] in ADOSSES else autres).append(ecart)
                if v["categorie"] in ADOSSES:
                    places.append(math.dist(v["position"], m["position"]))
                    if a.detail:
                        print(f"   {cas} {v['id']:22s} vrai {grand(v):.2f} m, posé {grand(m):.2f} m ({100 * ecart:3.0f} %), à {places[-1]:.2f} m")
        moy = lambda l: f"{100 * sum(l) / len(l):.0f} %" if l else "-"
        print(f"{dossier.name:14s} adossés : {len(adosses)} appariés, écart de largeur moyen {moy(adosses)}, écart de place moyen "
              f"{sum(places) / max(len(places), 1):.2f} m | autres meubles : {len(autres)}, écart de largeur {moy(autres)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
