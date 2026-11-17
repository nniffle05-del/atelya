r"""Les SOLS NUS : la maquette SANS MEUBLES rendue depuis la place des photos, pour juger les sols (18/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\sols_nus.py <dossier de la chaîne> <sortie> [--version c] [--cas app-001 …]
        [--photos app-001:photo-05,photo-07 …]

Pourquoi : les juges du sol (le sens des lames : comparer_sens_photo_rendu.py ; la couleur : mesurer_couleur_sols.py ; le
parquet : comparer_parquet_photo_rendu.py) mesurent le sol sur le rendu. Avec les meubles, leurs arêtes et leurs ombres
faussent la mesure : on rend donc la même maquette, meubles retirés.
<dossier de la chaîne> : une sortie de pc\verification\essai_lecture_photos.py (<dossier>/<logement>/<version>/logement-meuble.json).
Écrit <sortie>/<logement>-3d/maquette.blend et <sortie>/planches/<logement>/vues/rendus/vue-<photo>.png. S'arrête au premier plantage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402


def lancer(commande: list, journal: Path) -> None:
    r = subprocess.run([str(c) for c in commande], cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with journal.open("a", encoding="utf-8") as f:
        f.write(r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"PLANTÉ (code {r.returncode}) : {' '.join(str(c) for c in commande[:4])} … voir {journal}", flush=True)
        sys.exit(r.returncode or 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chaine", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--version", default="c")
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--photos", nargs="*", default=[], help="app-001:photo-05,photo-07 : seulement ces photos (toutes par défaut)")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    journal = a.sortie / "journal.txt"
    choisies = dict(d.split(":") for d in a.photos)
    maquettes = []
    for cas in a.cas:
        debut = time.time()
        logement = json.loads((a.chaine / cas / a.version / "logement-meuble.json").read_text(encoding="utf-8"))
        logement["meubles"] = []
        for o in logement.get("ouvertures", []):  # ni rideaux ni voilages : ils changent la lumière sur le sol
            o.pop("rideaux", None)
        nu = a.sortie / f"{cas}-logement-nu.json"
        nu.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        if cas in choisies:
            fiche["cameras"] = {n: c for n, c in fiche["cameras"].items() if n in choisies[cas].split(",")}
        fiche_f = a.sortie / f"{cas}-fiche.json"
        fiche_f.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
        d3 = a.sortie / f"{cas}-3d"
        lancer([sys.executable, "-m", "moteur.construire", nu, d3, "--sans-images"], journal)
        maquettes += ["--maquette", cas, d3 / "maquette.blend", fiche_f]
        print(f"{cas} : maquette sans meubles construite en {time.time() - debut:.0f} s", flush=True)
    debut = time.time()
    lancer([sys.executable, "outils/atelya/banc_ressemblance.py", a.sortie / "planches", *maquettes], journal)
    print(f"vues rendues en {time.time() - debut:.0f} s : {a.sortie / 'planches'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
