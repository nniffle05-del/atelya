r"""ESSAI « CLAUDE LIT LES PHOTOS » : la planche à trois colonnes, pour juger à l'œil (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\planche_lecture_photos.py <dossier des planches> <sortie.jpg> ^
        <logement>:<photo>[,<photo>…] [<logement>:<photo>…]

Pour chaque photo demandée : la photo du client | la maquette d'Atelya aujourd'hui (version a) | la maquette avec la lecture des
photos (version c), rendues de la même place (outils/atelya/banc_ressemblance.py --maquette <logement>-a … <logement>-c …).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))

from banc_ressemblance import CAS, lire_photo  # noqa: E402

LARGEUR = 620
TITRES = ("la photo du client", "Atelya aujourd'hui", "Atelya avec la lecture des photos")


def _police(taille: int):
    try:
        return ImageFont.truetype("arialbd.ttf", taille)
    except OSError:
        return ImageFont.load_default()


def main() -> int:
    planches, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    lignes = []
    for demande in sys.argv[3:]:
        cas, photos = demande.split(":")
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        for photo in photos.split(","):
            images = [Image.fromarray(lire_photo(fiche, photo))]
            for version in ("a", "c"):
                vue = planches / f"{cas}-{version}" / "vues" / "rendus" / f"vue-{photo}.png"
                if not vue.is_file():
                    print(f"PLANTÉ : vue absente : {vue}", flush=True)
                    return 2
                images.append(Image.open(vue).convert("RGB"))
            h = int(images[0].height * LARGEUR / images[0].width)
            lignes.append((f"{cas}  {photo}", [im.resize((LARGEUR, h), Image.LANCZOS) for im in images]))
    if not lignes:
        return 2
    police, petite = _police(22), _police(16)
    haut = 44
    total = haut + sum(l[1][0].height + 30 for l in lignes)
    feuille = Image.new("RGB", (3 * LARGEUR + 4 * 10, total), "white")
    d = ImageDraw.Draw(feuille)
    for k, titre in enumerate(TITRES):
        d.text((10 + k * (LARGEUR + 10) + 6, 8), titre, fill="black", font=police)
    y = haut
    for nom, images in lignes:
        d.text((16, y + 5), nom, fill=(90, 90, 90), font=petite)
        for k, im in enumerate(images):
            feuille.paste(im, (10 + k * (LARGEUR + 10), y + 28))
        y += images[0].height + 30
    sortie.parent.mkdir(parents=True, exist_ok=True)
    feuille.save(sortie, quality=88)
    print(f"{sortie} : {feuille.size}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
