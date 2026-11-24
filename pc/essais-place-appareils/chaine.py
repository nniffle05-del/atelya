r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : NON-RECUL de la CHAÎNE (sols, meubles, équipements, baies, collisions, avec
la lecture des photos) quand les appareils sont ceux d'ATELYA, avant et après l'affinage.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\chaine.py <variante> [<variante>…] [--cas app-001 app-002 app-004]

Pour chaque variante du banc (caler.py, affiner.py : « service », « defaut », « service+AB »…), la fiche des appareils est
écrite au format de service (..\atelya\b2\place-appareils\fiches\<logement>-<variante>.json), puis le banc de la chaîne
(pc\verification\essai_lecture_photos.py, version « c ») refait chaque logement avec CETTE fiche à la place de sa fiche
habituelle (appareils relevés à la main pour app-001 et app-002). Sorties : ..\atelya\b2\place-appareils\chaine\<variante>\.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
for d in ("outils/habillage", "outils/atelya", "pc/verification", "pc/essais-place-appareils"):
    sys.path.insert(0, str(RACINE / d))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import caler_photos_seul as outil  # noqa: E402
from juger import SORTIE, lire  # noqa: E402


def fiche_de_service(variante: str, logement: str) -> Path:
    f = lire(SORTIE / variante / f"{logement}.json")
    fiche = outil.fiche({"cameras": f["cameras"], "non_calees": f.get("non_calees", {})}, Path(f["photos"]), f["fichier"])
    chemin = SORTIE / "fiches" / f"{logement}-{variante}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    return chemin


def main() -> int:
    args = sys.argv[1:]
    cas = args[args.index("--cas") + 1:] if "--cas" in args else ["app-001", "app-002", "app-004"]
    variantes = args[:args.index("--cas")] if "--cas" in args else args
    import essai_lecture_photos as essai
    from banc_ressemblance import CAS

    for v in variantes:
        for c in cas:
            CAS[c]["fiche"] = fiche_de_service(v, c)
        sys.argv = ["essai_lecture_photos.py", str(SORTIE / "chaine" / v), "--cas", *cas, "--versions", "c"]
        code = essai.main()
        if code:
            print(f"PLANTÉ : chaîne de la variante {v} (code {code})", flush=True)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
