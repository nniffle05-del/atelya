"""La version « FONDUS » d'un vol déjà tourné (moteur/cinema/montage.py) : mêmes images, sans les couloirs ni les murs en gros
plan, raccordées par des fondus enchaînés courts. Aucun nouveau rendu.

    python outils/unreal/monter_fondus.py <dossier du film> <logement.json> [--sortie fondus.mp4] [--apercu 960]

Le dossier du film est celui de outils/unreal/balade_unreal.py (images image-0001.png…, balade.json).
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur.cinema import controle, montage  # noqa: E402
from moteur.cinema.reglages import IPS  # noqa: E402


def lire(chemin: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier")
    p.add_argument("logement")
    p.add_argument("--sortie", help="la vidéo montée (défaut : fondus.mp4 dans le dossier du film)")
    p.add_argument("--apercu", type=int, help="largeur d'un aperçu (ex. 960) ; défaut : pleine taille")
    a = p.parse_args()
    dossier = Path(a.dossier)
    logement = json.loads(Path(a.logement).read_text(encoding="utf-8"))
    vol = json.loads((dossier / "balade.json").read_text(encoding="utf-8"))
    images = sorted(dossier.glob("image-*.png"))
    if not images:
        sys.exit(f"PLANTÉ : aucune image dans {dossier}")
    c = controle.controler(logement, vol)
    coupes = montage.passages_a_retirer(logement, c, len(images))
    suite = montage.suite_d_images(len(images), coupes)
    h, w = lire(images[0]).shape[:2]
    taille = (a.apercu, round(h * a.apercu / w)) if a.apercu else (w, h)
    sortie = Path(a.sortie) if a.sortie else dossier / "fondus.mp4"
    ecrivain = cv2.VideoWriter(str(sortie), cv2.VideoWriter_fourcc(*"mp4v"), IPS, taille)
    cache = {}

    def image(k):
        if k not in cache:
            cache.clear() if len(cache) > 64 else None
            im = lire(images[k])
            cache[k] = cv2.resize(im, taille, interpolation=cv2.INTER_AREA) if taille != (w, h) else im
        return cache[k]
    for ka, kb, t in suite:
        if t <= 0:
            ecrivain.write(image(ka))
        else:
            ecrivain.write(cv2.addWeighted(image(ka), 1.0 - t, image(kb), t, 0.0))
    ecrivain.release()
    retire = sum(b - a + 1 for a, b in coupes) / IPS
    print(f"Fondus : {len(coupes)} passages retirés ({retire:.1f} s) ; film {len(images) / IPS:.1f} s -> {len(suite) / IPS:.1f} s")
    for a_, b_ in coupes:
        print(f"   retiré {a_ / IPS:5.1f} - {(b_ + 1) / IPS:5.1f} s")
    print(f"   {sortie}")


if __name__ == "__main__":
    main()
