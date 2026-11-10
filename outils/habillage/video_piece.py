r"""Un plan vidéo dans une maquette d'Atelya (moteur/blender/video_trajet.py), puis la vidéo .mp4 (10/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\video_piece.py maquette.blend trajet.json dossier ^
        [--echantillons 128] [--chrono]

--chrono : ne rend que l'image du milieu, pour annoncer la durée totale avant de lancer le plan entier.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.construire import DOSSIER_SCRIPTS, lancer_blender  # noqa: E402
from moteur.images import lire_image  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Plan vidéo dans une maquette d'Atelya")
    ap.add_argument("maquette", type=Path)
    ap.add_argument("trajet", type=Path)
    ap.add_argument("dossier", type=Path)
    ap.add_argument("--echantillons", type=int, default=128)
    ap.add_argument("--chrono", action="store_true")
    args = ap.parse_args()
    for f in (args.maquette, args.trajet):
        if not f.is_file():
            print(f"PLANTÉ : fichier introuvable : {f}", flush=True)
            return 2
    trajet = json.loads(args.trajet.read_text(encoding="utf-8"))
    n = int(trajet.get("images", 96))
    images = args.dossier / "images"
    seulement = str(n // 2) if args.chrono else ""
    debut = time.time()
    lancer_blender(str(args.maquette), "--python", str(DOSSIER_SCRIPTS / "video_trajet.py"), "--", str(args.trajet),
                   str(images), str(args.echantillons), seulement)
    duree = time.time() - debut
    if args.chrono:
        print(f"Une image (avec le chargement de la maquette) : {duree:.0f} s", flush=True)
        return 0
    fichiers = sorted(images.glob("image-*.png"))
    if len(fichiers) != n:
        print(f"PLANTÉ : {len(fichiers)} images rendues sur {n}", flush=True)
        return 1
    premiere = lire_image(fichiers[0])
    h, w = premiere.shape[:2]
    video = args.dossier / "plan.mp4"
    ecrivain = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), int(trajet.get("ips", 24)), (w, h))
    for f in fichiers:
        ecrivain.write(lire_image(f))
    ecrivain.release()
    print(f"Vidéo : {video} ({n} images, {duree / 60:.0f} min)", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {str(e)[-800:]}", flush=True)
        raise
