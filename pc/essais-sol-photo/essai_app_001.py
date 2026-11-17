r"""ESSAI « LE SOL PRÉLEVÉ SUR LA PHOTO », sur app-001 (18/11/2026) : le logement de la chaîne, où le point de Hongrie du séjour
et les lames de l'entrée et des chambres prennent l'image prélevée sur les photos (pc\essais-sol-photo\sol_de_la_photo.py).

    ..\atelya\.venv\Scripts\python.exe pc\essais-sol-photo\essai_app_001.py <logement-meuble.json de la chaîne> <sortie>

Écrit <sortie>/logement-essai.json et prélève les deux sols dans <sortie>/app-001-3d/matieres-sur-mesure/ (la construction les
y trouve déjà dessinés et les pose tels quels). ESSAI : rien de branché dans la chaîne.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import parquet_sur_mesure as psm  # noqa: E402

FICHE_CAMERAS = RACINE / "verites/app-001/cameras-photos.json"


def main() -> int:
    depart, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    logement = json.loads(depart.read_text(encoding="utf-8"))
    hongrie = psm.fiche({"largeur_m": 0.09, "longueur_m": 0.5, "nuance": 0.0, "chaleur": 0.0, "creux_mm": 0.0})  # une étiquette : l'image vient de la photo
    lames = None
    for p in logement["pieces"]:
        for sol in ([p["sol"]] if p.get("sol") else []) + [z["sol"] for z in p.get("zones_sol", [])]:
            if sol.get("parquet"):
                lames = sol["parquet"]
                sol.pop("teinte", None)  # la couleur est déjà celle de la photo
            # (le point de Hongrie n'est pas encore prélevé : essai du 18/11/2026 non concluant, morceau propre trop petit)
    essai = sortie / "logement-essai.json"
    essai.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    matieres = sortie / "app-001-3d" / "matieres-sur-mesure"
    travaux = [("sejour_1", 0.0, matieres / psm.nom(lames), ["--zones", "lames", "--photos", "photo-07", "photo-05", "--lames", str(lames["largeur"])])]
    for piece, sens, dossier, options in travaux:
        r = subprocess.run([sys.executable, str(RACINE / "pc/essais-sol-photo/sol_de_la_photo.py"), str(essai), str(FICHE_CAMERAS), str(sortie),
                            piece, str(sens), str(dossier), *options], cwd=RACINE)
        if r.returncode != 0:
            print(f"PLANTÉ : prélèvement du sol de {piece} (sens {sens:.0f}°), code {r.returncode}", flush=True)
            return r.returncode
    print(f"Logement d'essai : {essai}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
