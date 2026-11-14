r"""Les meubles d'un logement trouvés SEULS sur les photos calées du client (OWLv2, en service depuis le 10/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\reperer_meubles_photos.py verites\app-002\cameras-photos.json ^
        logement.json logement-meuble.json
    ..\atelya\.venv\Scripts\python.exe outils\habillage\reperer_meubles_photos.py ..\atelya\photos-clients\app-002\photos ^
        logement.json logement-meuble.json          (dossier de photos : Atelya les cale SEUL, 14/11/2026)

Le 1er argument est une fiche de photos calées (à la main ou par Atelya) OU le dossier des photos du client : dans ce cas
Atelya cale les photos seul (moteur/caler_photos.py), n'utilise que celles dont il est sûr et range sa fiche à côté de la
sortie (<sortie>.cameras-seul.json). Mesuré le 14/11/2026 (examens déjà vus) : app-002 19/30 meubles retrouvés (22 avec la
fiche à la main), app-001 10/34 (25 à la main : le grand séjour est placé à 1 m près, les meubles tombent à côté).

Chaque meuble trouvé (moteur/reperer_meubles.reperer_depuis_releve) est ajouté au logement avec le statut « estime » et la
taille d'un meuble courant de son groupe ; ceux déjà présents (relevés, placés à l'écran) sont gardés. Le client vérifie et
corrige à l'écran de vérification.
Non-recul (examens déjà vus, 10/11/2026) : app-001 16/34 → 25/34 retrouvés (en trop 24 → 18), app-002 10/30 → 22/30 (en trop 9).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.logement import Logement  # noqa: E402
from moteur.reperer_meubles import reperer_depuis_releve, vers_meubles_du_logement  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caler_photos_seul import fiche_ou_photos  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description="Meubles trouvés seuls sur les photos du client (OWLv2)")
    ap.add_argument("releve", type=Path, help="cameras-photos.json (photos calées), ou le dossier des photos (calées seules)")
    ap.add_argument("logement", type=Path)
    ap.add_argument("sortie", type=Path, help="logement.json écrit, avec les meubles trouvés")
    args = ap.parse_args()
    for f in (args.releve, args.logement):
        if not f.exists():
            print(f"PLANTÉ : introuvable : {f}", flush=True)
            return 2
    logement = json.loads(args.logement.read_text(encoding="utf-8"))
    releve = fiche_ou_photos(args.releve, logement, args.sortie.with_suffix(".cameras-seul.json"))
    trouves = reperer_depuis_releve(releve, logement, RACINE, journal=print)
    nouveaux = vers_meubles_du_logement(trouves, logement)
    pris = {m["id"] for m in logement.get("meubles", [])} | {p["id"] for p in logement["pieces"]}
    for m in nouveaux:
        while m["id"] in pris:
            m["id"] += "b"
        pris.add(m["id"])
    logement["meubles"] = list(logement.get("meubles", [])) + nouveaux
    Logement.model_validate(logement)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in nouveaux:
        print(f"{m['piece']:14s} {m['categorie']:12s} {m['position']} face {m['face']}° ({m['source']})")
    print(f"{len(nouveaux)} meubles trouvés : {args.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
