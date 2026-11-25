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
    import argparse

    ap = argparse.ArgumentParser(description="Planche à trois colonnes : la photo, la maquette avant, la maquette après")
    ap.add_argument("planches", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("demandes", nargs="+", help="<logement>:<photo>[,<photo>…]")
    ap.add_argument("--avant", type=Path, help="le dossier des planches de la colonne du milieu, s'il n'est pas le même")
    ap.add_argument("--suffixes", nargs=2, default=("a", "c"), help="les deux versions comparées (dossiers <logement>-<suffixe>)")
    ap.add_argument("--titres", nargs=2, default=TITRES[1:], help="les titres des deux colonnes de droite")
    a = ap.parse_args()
    planches, sortie = a.planches, a.sortie
    titres = (TITRES[0], *a.titres)
    lignes = []
    for demande in a.demandes:
        cas, photos = demande.split(":")
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        for photo in photos.split(","):
            images = [Image.fromarray(lire_photo(fiche, photo))]
            for dossier, version in ((a.avant or planches, a.suffixes[0]), (planches, a.suffixes[1])):
                vue = dossier / f"{cas}-{version}" / "vues" / "rendus" / f"vue-{photo}.png"
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
    for k, titre in enumerate(titres):
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
