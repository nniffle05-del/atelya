r"""Dessine le parquet « à l'anglaise » que la bibliothèque n'a pas (17/11/2026, NT : « il manque quand même le parquet le plus
courant des appartements français : des lames de chêne de 8 à 12 cm, longues, propres, claires ou miel »).

Comment : comme le point de Hongrie d'Atelya, le bois vient d'une VRAIE photo de chêne déjà dans la bibliothèque (« chene_clair »,
plaquage de chêne de Poly Haven, CC0). Chaque lame est un morceau différent de cette photo, pris dans le fil du bois, avec sa
propre nuance ; les lames ont des longueurs inégales et leurs bouts sont décalés d'un rang à l'autre (pose « à l'anglaise ») ;
un joint fin et sombre les sépare. Trois images, comme toute matière : couleur, relief (les joints en creux), brillance.
L'image se raccorde sans couture sur ses quatre bords. Rien n'est téléchargé.

    ..\atelya\.venv\Scripts\python.exe outils\bibliotheque\dessiner_parquet.py ..\atelya\bibliotheque\matieres

Les lames vont de gauche à droite de l'image (sens 0 du catalogue). La largeur des lames du dessin est de 10 cm : Atelya
l'agrandit ou la réduit (champ « echelle » du sol) pour obtenir la largeur mesurée sur les photos du client (6 à 16 cm).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dessiner_carreaux import _normales  # noqa: E402

NOM = "lames_chene_anglaise"
SOURCE = "chene_clair"  # la photo de chêne dont les lames sont tirées (fil du bois de haut en bas de l'image)
LARGEUR_LAME_M = 0.10
RANGS = 24  # 24 lames de 10 cm : une image de 2,40 m
LONGUEURS_M = (0.55, 1.45)  # les lames d'un parquet à l'anglaise n'ont pas toutes la même longueur
JOINT_MM = 1.4
SORTIE_PX = 2048


def dessiner(bibliotheque: Path, graine: int = 7) -> tuple[Image.Image, Image.Image, Image.Image, float]:
    fiches = json.loads((bibliotheque / "matieres.json").read_text(encoding="utf-8"))
    photo = Image.open(bibliotheque / SOURCE / "couleur.jpg").convert("RGB")
    px_par_m = photo.width / fiches[SOURCE]["taille_image_m"][0]
    # la photo ramenée à 1 mm par pixel et couchée : le fil du bois va de gauche à droite, comme les lames
    bois = np.asarray(photo.resize((int(round(photo.width / px_par_m * 1000)),) * 2, Image.LANCZOS).rotate(90, expand=True), np.float32)
    alea = np.random.default_rng(graine)
    cote = int(round(RANGS * LARGEUR_LAME_M * 1000))  # 1 pixel = 1 mm
    h_lame = cote // RANGS
    couleur = np.zeros((cote, cote, 3), np.float32)
    creux = np.ones((cote, cote), np.float32)  # 1 = surface, 0 = fond d'un joint
    demi = max(1, int(round(JOINT_MM / 2)))
    for rang in range(RANGS):
        y0 = rang * h_lame
        # les lames du rang : longueurs tirées au hasard, ajustées pour remplir exactement la largeur (raccord sans couture)
        longueurs = []
        while sum(longueurs) < cote:
            longueurs.append(alea.uniform(*LONGUEURS_M) * 1000)
        longueurs = np.array(longueurs) * cote / sum(longueurs)
        x = float(alea.uniform(0, cote))  # le premier bout de lame, décalé d'un rang à l'autre
        for longueur in longueurs:
            n = int(round(longueur))
            # un morceau de la photo, dans le fil, à un endroit et dans un sens différents pour chaque lame
            by = int(alea.integers(0, bois.shape[0] - h_lame))
            bx = int(alea.integers(0, max(1, bois.shape[1] - n)))
            morceau = bois[by:by + h_lame, bx:bx + n]
            if morceau.shape[1] < n:  # lame plus longue que la photo : on prolonge en miroir
                morceau = np.concatenate([morceau, morceau[:, ::-1]], 1)[:, :n]
            if alea.random() < 0.5:
                morceau = morceau[:, ::-1]
            if alea.random() < 0.5:
                morceau = morceau[::-1]
            # la nuance de la lame : un peu plus claire ou plus foncée, un peu plus chaude ou plus froide
            clarte = float(np.clip(alea.normal(1.0, 0.055), 0.86, 1.14))
            chaleur = float(np.clip(alea.normal(0.0, 0.015), -0.035, 0.035))
            morceau = morceau * clarte * np.array([1 + chaleur, 1.0, 1 - chaleur], np.float32)
            colonnes = (int(round(x)) + np.arange(n)) % cote
            couleur[y0:y0 + h_lame, colonnes] = morceau
            creux[y0:y0 + h_lame, colonnes[:demi]] = 0.0  # le bout de la lame
            creux[y0:y0 + h_lame, colonnes[-demi:]] = 0.0
            x += longueur
        creux[y0:y0 + demi] = 0.0  # le long joint entre deux rangs
        creux[y0 + h_lame - demi:y0 + h_lame] = 0.0
    # le joint : une ligne fine et sombre, aux bords adoucis (un léger chanfrein)
    doux = np.asarray(Image.fromarray((creux * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9)), np.float32) / 255
    couleur = np.clip(couleur * (0.50 + 0.50 * doux)[..., None], 0, 255)
    image = Image.fromarray(couleur.astype(np.uint8)).resize((SORTIE_PX, SORTIE_PX), Image.LANCZOS)
    hauteur = np.asarray(Image.fromarray((doux * 255).astype(np.uint8)).resize((SORTIE_PX, SORTIE_PX), Image.LANCZOS), np.float32) / 255
    relief = Image.fromarray(_normales(hauteur, 3.0))
    # la brillance : un vernis régulier (gris moyen), plus mat dans les joints ; un rien de variation d'une lame à l'autre
    gris = np.asarray(image.convert("L"), np.float32) / 255
    mat = np.clip(0.45 + 0.35 * (1 - hauteur) + 0.10 * (gris - gris.mean()), 0, 1)
    brillance = Image.fromarray((mat * 255).astype(np.uint8))
    return image, relief, brillance, cote / 1000


def main() -> int:
    ap = argparse.ArgumentParser(description="Dessine le parquet de chêne à l'anglaise d'Atelya")
    ap.add_argument("bibliotheque", type=Path)
    a = ap.parse_args()
    if not (a.bibliotheque / SOURCE / "couleur.jpg").is_file():
        print(f"PLANTÉ : la photo de chêne « {SOURCE} » manque dans {a.bibliotheque}")
        return 1
    image, relief, brillance, taille = dessiner(a.bibliotheque)
    dossier = a.bibliotheque / NOM
    dossier.mkdir(exist_ok=True)
    image.save(dossier / "couleur.jpg", quality=92)
    relief.save(dossier / "relief.jpg", quality=92)
    brillance.save(dossier / "brillance.jpg", quality=92)
    chemin = a.bibliotheque / "matieres.json"
    fiches = json.loads(chemin.read_text(encoding="utf-8"))
    fiches[NOM] = {"description": "parquet de chêne à l'anglaise, lames de 10 cm (dessiné par Atelya)",
                   "source": "dessiné par Atelya (outils/bibliotheque/dessiner_parquet.py) d'après la photo de chêne « chene_clair »",
                   "identifiant": NOM, "licence": "CC0 1.0 (photo d'origine : Poly Haven, oak_veneer_01)", "auteurs": ["Atelya"],
                   "taille_image_m": [taille, taille], "octets": sum(f.stat().st_size for f in dossier.glob("*.jpg"))}
    chemin.write_text(json.dumps(fiches, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{NOM} : image de {taille} m, lames de {100 * LARGEUR_LAME_M:.0f} cm, dans {dossier}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
