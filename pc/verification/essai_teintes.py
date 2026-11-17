r"""ÉTAPE 4 b (17/11/2026) : essayer une façon de régler la teinte des sols sur des maquettes DÉJÀ construites, tous logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\essai_teintes.py <maquettes> <sortie> [--borne 2] [--titre "…"]
        [--sans-reglage] [--cas app-001 …]

<maquettes> : un dossier qui contient <logement>-apres-3d\maquette.blend et construction.json (une sortie de
planches_avant_apres.py), ou <logement>\3d\… (banc de ressemblance).
Pour chaque logement : la maquette est copiée, ses teintes sont réglées de nouveau (moteur/blender/regler_teintes.py, --borne :
de combien le réglage peut s'écarter de la teinte calculée sur la photo ; 1 = aucun réglage au rendu), elle est rendue depuis
la place de quelques photos (PHOTOS : séjours, chambres, cuisines) et la couleur des sols est mesurée contre les photos
(mesurer_couleur_sols.py). --sans-reglage : la maquette telle quelle (point de départ). S'arrête au premier plantage.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402

PHOTOS = {"app-001": ["photo-03", "photo-04", "photo-05", "photo-07", "photo-08", "photo-11"],
          "app-002": ["photo-01", "photo-03", "photo-07", "photo-10", "photo-14", "photo-08"],
          "app-004": ["photo-02", "photo-07", "photo-08", "photo-09", "photo-12", "photo-05"]}


def lancer(commande: list, journal: Path) -> str:
    r = subprocess.run([str(c) for c in commande], cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with journal.open("a", encoding="utf-8") as f:
        f.write(r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"PLANTÉ (code {r.returncode}) : {' '.join(str(c) for c in commande[:4])} … voir {journal}", flush=True)
        sys.exit(r.returncode or 1)
    return r.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("maquettes", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--borne", type=float, default=None)
    ap.add_argument("--sans-reglage", action="store_true")
    ap.add_argument("--titre", default="")
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    journal = a.sortie / "journal.txt"
    py, blender = sys.executable, os.environ.get("BLENDER")
    rendus = []
    for cas in a.cas:
        source = next((d for d in (a.maquettes / f"{cas}-apres-3d", a.maquettes / cas / "3d", a.maquettes / f"{cas}-3d") if (d / "maquette.blend").is_file()), None)
        if source is None:
            print(f"PLANTÉ : pas de maquette pour {cas} dans {a.maquettes}", flush=True)
            return 1
        d3 = a.sortie / f"{cas}-3d"
        d3.mkdir(exist_ok=True)
        for f in ("maquette.blend", "construction.json"):
            shutil.copyfile(source / f, d3 / f)
        if not a.sans_reglage:
            debut = time.time()
            sortie = lancer([blender, "-b", "--factory-startup", "--python-exit-code", "1", d3 / "maquette.blend", "--python",
                             RACINE / "moteur/blender/regler_teintes.py", "--", d3 / "construction.json", d3 / "reglages_teinte.json", "jour_voile",
                             a.borne if a.borne is not None else 1e9], journal)
            print("\n".join(l for l in sortie.splitlines() if l.startswith("Teinte réglée")), flush=True)
            print(f"{cas} : teintes réglées en {time.time() - debut:.0f} s", flush=True)
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        fiche["cameras"] = {n: c for n, c in fiche["cameras"].items() if n in PHOTOS[cas]}
        fiche_f = a.sortie / f"{cas}-fiche.json"
        fiche_f.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
        debut = time.time()
        lancer([py, "outils/atelya/banc_ressemblance.py", a.sortie / "planches", "--maquette", cas, d3 / "maquette.blend", fiche_f], journal)
        print(f"{cas} : {len(fiche['cameras'])} vues rendues en {time.time() - debut:.0f} s", flush=True)
        rendus.append(f"{cas}={a.sortie / 'planches' / cas / 'vues' / 'rendus'}")
    print(lancer([py, "pc/verification/mesurer_couleur_sols.py", a.sortie / "couleur", *rendus, "--titre", a.titre], journal), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
