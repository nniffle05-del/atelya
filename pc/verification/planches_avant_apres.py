r"""Planches à trois colonnes « la photo | la maquette AVANT | la maquette APRÈS », depuis deux logements meublés (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\planches_avant_apres.py <dossier avant> <dossier après> <sortie> ^
        <logement>:<photo>[,<photo>…] [<logement>:…] [--titres "avant" "après"] [--version c]

Pourquoi : juger à l'œil un changement de la POSE des meubles (NT : « résultats en images »). Les deux dossiers sont des sorties
de pc\verification\essai_lecture_photos.py (ou mesurer_place_taille.py) : <dossier>/<logement>/<version>/logement-meuble.json.
Pour chaque logement demandé : les deux maquettes sont construites (moteur.construire, sans images), rendues depuis la place
des photos demandées (outils/atelya/banc_ressemblance.py --maquette), puis assemblées (planche_lecture_photos.py) dans
<sortie>/comparaison-<logement>.jpg. S'arrête au premier plantage.
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
    ap.add_argument("avant", type=Path)
    ap.add_argument("apres", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("demandes", nargs="+")
    ap.add_argument("--titres", nargs=2, default=("avec la lecture, avant", "avec la lecture, après"))
    ap.add_argument("--version", default="c")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    journal = a.sortie / "journal.txt"
    py = sys.executable
    for demande in a.demandes:
        cas, photos = demande.split(":")
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        fiche["cameras"] = {n: c for n, c in fiche["cameras"].items() if n in photos.split(",")}
        fiche_f = a.sortie / f"{cas}-fiche.json"
        fiche_f.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
        maquettes = []
        for nom, dossier in (("avant", a.avant), ("apres", a.apres)):
            debut = time.time()
            d3 = a.sortie / f"{cas}-{nom}-3d"
            lancer([py, "-m", "moteur.construire", dossier / cas / a.version / "logement-meuble.json", d3, "--sans-images"], journal)
            maquettes += ["--maquette", f"{cas}-{nom}", d3 / "maquette.blend", fiche_f]
            print(f"{cas} {nom} : maquette construite en {time.time() - debut:.0f} s", flush=True)
        debut = time.time()
        lancer([py, "outils/atelya/banc_ressemblance.py", a.sortie / "planches", *maquettes], journal)
        print(f"{cas} : vues rendues en {time.time() - debut:.0f} s", flush=True)
        lancer([py, "pc/verification/planche_lecture_photos.py", a.sortie / "planches", a.sortie / f"comparaison-{cas}.jpg", demande,
                "--suffixes", "avant", "apres", "--titres", *a.titres], journal)
        print(f"{cas} : {a.sortie / f'comparaison-{cas}.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
