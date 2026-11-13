"""Juger un FILM (et pas une photo) : scintillement, écart à des images de contrôle, temps de calcul (11/11/2026).

    python outils/unreal/juger_film.py <dossier_images> [<dossier_images> …] [--controle <dossier_cycles>] [--sortie <planche.jpg>]

Pour chaque dossier (image-0001.png… d'un même trajet, rendu-unreal.json à côté) :
- SCINTILLEMENT (/255) : ce qui change d'une image à l'autre sans s'expliquer par le mouvement. La caméra glisse doucement : une
  image doit être presque la moyenne de sa voisine d'avant et de celle d'après ; l'écart moyen restant est le grain qui « grouille »
  et la lumière qui « respire » (petit = film calme). Mesuré sur l'image réduite de moitié (le grain fin y compte encore) ;
- ÉCART À CYCLES (/255) sur les images communes avec le dossier de contrôle (images 1, 48, 96) : pour juger, jamais pour régler ;
- TEMPS par image (rendu-unreal.json) et temps pour 90 s de film à 24 images par seconde (2 160 images).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

CHARGEMENT_S = 25.0


def _lire(chemin: Path, echelle=0.5):
    im = cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR).astype(np.float32)
    return cv2.resize(im, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA) if echelle != 1 else im


def scintillement(images: list[Path]) -> float:
    if len(images) < 3:
        return float("nan")
    lues = [_lire(p) for p in images]
    ecarts = [float(np.abs(lues[k] - 0.5 * (lues[k - 1] + lues[k + 1])).mean()) for k in range(1, len(lues) - 1)]
    return float(np.mean(ecarts))


def juger(dossier: Path, controle: Path | None = None) -> dict:
    images = sorted(dossier.glob("image-*.png"))
    bilan = {"dossier": dossier.name, "images": len(images), "scintillement_255": round(scintillement(images), 2)}
    if controle:
        ecarts = []
        for c in sorted(controle.glob("image-*.png")):
            u = dossier / c.name
            if u.is_file():
                a, b = _lire(c, 1), _lire(u, 1)
                b = cv2.resize(b, (a.shape[1], a.shape[0]))
                ecarts.append(float(np.abs(a - b).mean()))
        bilan["ecart_cycles_255"] = round(float(np.mean(ecarts)), 1) if ecarts else None
    fiche = dossier / "rendu-unreal.json"
    if fiche.is_file():
        f = json.loads(fiche.read_text(encoding="utf-8"))
        # sans le chargement d'Unreal (~25 s par rendu, mesuré le 11/11/2026 : 3 images Lumen en 25 s), négligeable sur un vrai film
        par_image = max(f["rendu_s"] - CHARGEMENT_S, 0.0) / max(f["images"], 1)
        bilan["s_par_image"] = round(par_image, 2)
        bilan["film_90s_h"] = round(par_image * 2160 / 3600, 2)
    return bilan


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossiers", nargs="+")
    p.add_argument("--controle")
    a = p.parse_args()
    for d in a.dossiers:
        b = juger(Path(d), Path(a.controle) if a.controle else None)
        print(json.dumps(b, ensure_ascii=False))


if __name__ == "__main__":
    main()
