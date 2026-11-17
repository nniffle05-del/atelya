r"""LA LECTURE DES PHOTOS PAR CLAUDE, sans appeler l'API : préparer ce qu'on lui enverrait (essai du 16/11/2026, accord de NT).

    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\preparer_photos.py <fiche cameras-photos.json> <dossier de sortie>

Pourquoi : les détecteurs d'Atelya encadrent des objets sans les comprendre (« un rangement »). Dans cet essai, Claude ne
dessine RIEN : Atelya lui montre chaque photo avec ses rectangles NUMÉROTÉS, et Claude dit, numéro par numéro, ce que c'est
vraiment (moteur/lecture_photos.py : le format de sa réponse). La géométrie reste à Atelya.

Écrit dans <sortie> : pour chaque photo, <photo>.jpg (la photo avec les rectangles numérotés) et <photo>.json (la liste :
numéro, ce que le détecteur croit voir, note, rectangle) ; consigne.txt (ce qu'on demande à Claude).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))

from banc_fidelite import NOMS, Detecteur  # noqa: E402
from banc_ressemblance import lire_photo  # noqa: E402

from moteur import fidelite_photos as fp  # noqa: E402
from moteur.lecture_photos import consigne  # noqa: E402

COULEURS = [(230, 25, 75), (0, 130, 200), (60, 180, 75), (245, 130, 48), (145, 30, 180), (0, 150, 150), (240, 50, 230), (128, 128, 0),
            (170, 110, 40), (0, 0, 128), (128, 0, 0), (0, 128, 128)]


def _police(taille: int):
    try:
        return ImageFont.truetype("arialbd.ttf", taille)
    except OSError:
        return ImageFont.load_default()


def objets_numerotes(detecteur: Detecteur, fiche: dict, nom: str) -> tuple[Image.Image, list[dict]]:
    """La photo et ses objets distincts (du plus grand au plus petit), numérotés à partir de 1."""
    rgb = lire_photo(fiche, nom)
    h, w = rgb.shape[:2]
    objets = fp.objets_de_la_photo(detecteur.brut(fiche, nom, rgb), w, h)
    objets.sort(key=lambda o: -(o["boite"][2] - o["boite"][0]) * (o["boite"][3] - o["boite"][1]))
    liste = [{"numero": k, "detecteur": o["sorte"], "phrase": o["phrase"], "note": round(o["note"], 2), "boite": [round(v) for v in o["boite"]]}
             for k, o in enumerate(objets, start=1)]
    return Image.fromarray(rgb), liste


def dessiner(image: Image.Image, liste: list[dict]) -> Image.Image:
    image = image.copy()
    d = ImageDraw.Draw(image)
    police = _police(20)
    for o in liste:
        c = COULEURS[(o["numero"] - 1) % len(COULEURS)]
        x0, y0, x1, y1 = o["boite"]
        d.rectangle([x0, y0, x1, y1], outline=c, width=3)
        texte = str(o["numero"])
        l = d.textlength(texte, font=police)
        d.rectangle([x0, y0, x0 + l + 10, y0 + 24], fill=c)
        d.text((x0 + 5, y0 + 1), texte, fill="white", font=police)
    return image


def main() -> int:
    fiche = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sortie = Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    detecteur = Detecteur()
    for nom in fiche["cameras"]:
        image, liste = objets_numerotes(detecteur, fiche, nom)
        dessiner(image, liste).save(sortie / f"{nom}.jpg", quality=92)
        (sortie / f"{nom}.json").write_text(json.dumps(liste, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nom} : " + ", ".join(f"{o['numero']} {NOMS.get(o['detecteur'], o['detecteur'])}" for o in liste), flush=True)
    (sortie / "consigne.txt").write_text(consigne(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
