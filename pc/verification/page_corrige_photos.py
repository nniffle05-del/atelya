r"""Une page de l'écran de vérification pour faire POINTER PAR NT la vraie place de photos dont on n'a pas de relevé : ses
réponses servent de CORRIGÉ (examen du signal « endroit douteux », 15/11/2026). Aucun calcul d'Atelya, et AUCUNE place
proposée à l'écran : il ne faut pas influencer la personne qui pointe.

    ..\atelya\.venv\Scripts\python.exe pc\verification\page_corrige_photos.py <logement.json> <image du plan> <px par m> <x0> <y0> ^
        <dossier des photos> <dossier de sortie> photo-09 photo-10 …

<px par m>, <x0>, <y0> : comment poser les mètres du logement sur l'image du plan (origine en pixels, y de l'image vers le bas).
Écrit <sortie>\ecran.html (double-clic). « Terminer » télécharge <projet>-photos.json : le corrigé pointé.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "verification-plan" / "scripts"))
from moteur import photos_verification as pv  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from page_unique import fabriquer  # noqa: E402

QUESTION = ("Pour le corrigé : pointez le plus précisément possible l'endroit d'où cette photo est prise, puis tirez vers ce qu'elle "
            "regarde. Si vous ne pouvez vraiment pas le dire : « Je ne sais pas ».")


def main() -> int:
    logement, image, px_par_m, x0, y0, photos, sortie, *noms = sys.argv[1:]
    logement = json.loads(Path(logement).read_text(encoding="utf-8"))
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    plan = lire_image(Path(image))
    if plan is None:
        print(f"PLANTÉ : image du plan illisible : {image}", flush=True)
        return 2
    ecrire_image(sortie / "plan.png", plan)
    questions = []
    for nom in noms:
        fichier = next((p for p in sorted(Path(photos).glob(nom + ".*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")), None)
        if fichier is None:
            print(f"PLANTÉ : photo introuvable : {nom} dans {photos}", flush=True)
            return 2
        donnee, w, h = pv._photo_reduite(fichier)
        questions.append({"nom": nom, "image": donnee, "largeur": w, "hauteur": h, "question": QUESTION, "piece": None, "hesite_avec": [], "proposition": None})
    v = {"schema": "verification/0.1", "plan": "plan.png", "calage": {"px_par_m": float(px_par_m), "origine_px": [float(x0), float(y0)]},
         "echelle": {"etat": "lue", "source": "relevé"}, "logement": logement, "doutes": [], "photos": {"seules": True, "questions": questions}}
    (sortie / "verification.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    print(f"{len(questions)} photos à pointer : {fabriquer(sortie)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
