r"""Les photos du client à l'ÉCRAN DE VÉRIFICATION : « d'où est prise cette photo ? » (15/11/2026, parcours « en deux temps »).

1. Préparer l'écran (Atelya cale les photos, puis fabrique la page avec une question par photo qu'il ne sait pas ranger) :
    ..\atelya\.venv\Scripts\python.exe outils\habillage\questions_photos.py preparer <dossier de lecture> <dossier des photos>
   <dossier de lecture> : celui du plan déjà lu et vérifié (logement.json, verification.json, plan.png : sorties de
   outils\atelya\lire_plan.py ou outils\lecture_claude\traduire_fiche.py). La page est écrite dans
   <dossier de lecture>\photos\ecran.html (double-clic) : la photo, la question, et le plan sur lequel on clique là où se
   tenait le photographe en tirant vers ce qu'il regardait. Sans question à poser, aucune page n'est faite.
   --logement <fichier> : un autre logement.json que celui du dossier (logement corrigé).

2. Ranger les réponses (le fichier téléchargé par le bouton « Valider » de l'écran) :
    ..\atelya\.venv\Scripts\python.exe outils\habillage\questions_photos.py ranger <fichier rendu par l'écran> <dossier des photos>
   Les endroits pointés sont ajoutés à <dossier des photos>\pieces-des-photos.json ; les outils des sols et des meubles
   (sols_photos.py, reperer_meubles_photos.py) le relisent tout seuls. Relancer « preparer » montre ce qui reste à demander.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RACINE / "outils" / "verification-plan" / "scripts"))
from caler_photos_seul import PIECES_DES_PHOTOS, fiche_ou_photos  # noqa: E402
from moteur import photos_verification as pv  # noqa: E402


def preparer(lecture: Path, photos: Path, logement_: Path | None) -> int:
    from page_unique import fabriquer
    for f in (lecture / "verification.json", lecture / "plan.png", photos):
        if not f.exists():
            print(f"PLANTÉ : introuvable : {f}", flush=True)
            return 2
    verification = json.loads((lecture / "verification.json").read_text(encoding="utf-8"))
    logement = json.loads((logement_ or lecture / "logement.json").read_text(encoding="utf-8"))
    sortie = lecture / "questions-photos"
    sortie.mkdir(parents=True, exist_ok=True)
    fiche = fiche_ou_photos(photos, logement, sortie / "cameras-photos-seul.json", journal=lambda *a: print(*a, flush=True))
    bloc = pv.questions_pour_l_ecran(fiche, photos, logement=logement)
    bloc["seules"] = True  # page des photos seules : le plan a déjà été vérifié, l'écran ne repose pas ses questions sur le plan
    if not bloc["questions"]:
        (sortie / "ecran.html").unlink(missing_ok=True)  # la page d'un passage précédent n'a plus rien à demander
        print(f"Aucune question à poser : les {len(fiche['cameras'])} photos sont rangées.", flush=True)
        return 0
    # l'écran des photos : le logement tel qu'il est (plus de doutes sur le plan : il est déjà vérifié), et les questions
    verification.update(logement=logement, doutes=[], photos=bloc)
    (sortie / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, default=float), encoding="utf-8")
    shutil.copyfile(lecture / "plan.png", sortie / "plan.png")
    page = fabriquer(sortie)
    print(f"{len(fiche['cameras'])} photos rangées, {len(bloc['questions'])} questions à poser → {page}", flush=True)
    for q in bloc["questions"]:
        print(f"  {q['nom']} : {q['question']}", flush=True)
    return 0


def ranger(rendu: Path, photos: Path) -> int:
    for f in (rendu, photos):
        if not f.exists():
            print(f"PLANTÉ : introuvable : {f}", flush=True)
            return 2
    resultat = json.loads(rendu.read_text(encoding="utf-8"))
    reponses = resultat.get("photos")
    if not reponses or not reponses.get("endroits"):
        print("Aucun endroit pointé dans ce fichier : rien à ranger.", flush=True)
        return 0
    chemin = photos / PIECES_DES_PHOTOS
    avant = json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None
    chemin.write_text(json.dumps(pv.ranger_les_reponses(avant, reponses), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(reponses['endroits'])} endroits pointés rangés dans {chemin}" + (f" ; {len(reponses.get('passees', []))} photos passées" if reponses.get("passees") else ""),
          flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Photos du client à l'écran de vérification")
    sous = ap.add_subparsers(dest="quoi", required=True)
    a = sous.add_parser("preparer"); a.add_argument("lecture", type=Path); a.add_argument("photos", type=Path); a.add_argument("--logement", type=Path)
    b = sous.add_parser("ranger"); b.add_argument("rendu", type=Path); b.add_argument("photos", type=Path)
    args = ap.parse_args()
    return preparer(args.lecture, args.photos, args.logement) if args.quoi == "preparer" else ranger(args.rendu, args.photos)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
