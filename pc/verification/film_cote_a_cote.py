r"""Deux films du même vol, CÔTE À CÔTE, pour juger un changement en mouvement (point 2, 18/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\film_cote_a_cote.py <sortie.mp4> "avant=<dossier d'images>" "apres=<dossier d'images>"
        [--ips 24] [--largeur 960]

Chaque dossier contient les images d'un film (image-0001.png…, sorties de outils/unreal/balade_unreal.py), tournées sur le MÊME
trajet. Pourquoi : le produit est le film (CLAUDE.md § 0) ; un changement de lumière se juge quand la caméra bouge, pas
seulement sur des images à l'arrêt. Les titres sont écrits sans accents (police d'OpenCV). S'arrête si les deux films n'ont
pas le même nombre d'images.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def lire(chemin: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        sys.exit(f"PLANTÉ : image illisible {chemin}")
    return image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie", type=Path)
    ap.add_argument("films", nargs=2, help="titre=<dossier d'images>")
    ap.add_argument("--ips", type=int, default=24)
    ap.add_argument("--largeur", type=int, default=960)
    a = ap.parse_args()
    titres, listes = [], []
    for f in a.films:
        titre, dossier = f.split("=", 1)
        images = sorted(Path(dossier).glob("image-*.png"))
        if not images:
            sys.exit(f"PLANTÉ : aucune image dans {dossier}")
        titres.append(titre)
        listes.append(images)
    if len(listes[0]) != len(listes[1]):
        sys.exit(f"PLANTÉ : les deux films n'ont pas le même nombre d'images ({len(listes[0])} et {len(listes[1])})")
    h0, w0 = lire(listes[0][0]).shape[:2]
    h = int(round(h0 * a.largeur / w0)) // 2 * 2
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    provisoire = a.sortie.with_name("cote-a-cote-provisoire.mp4")  # OpenCV n'écrit pas dans un chemin à accents
    ecrivain = cv2.VideoWriter(str(provisoire) if str(a.sortie).isascii() else "cote-a-cote-provisoire.mp4",
                               cv2.VideoWriter_fourcc(*"mp4v"), a.ips, (2 * a.largeur + 8, h + 40))
    ecrit = Path(str(provisoire) if str(a.sortie).isascii() else "cote-a-cote-provisoire.mp4")
    for gauche, droite in zip(*listes):
        cadre = np.full((h + 40, 2 * a.largeur + 8, 3), 255, np.uint8)
        for k, (chemin, titre) in enumerate(((gauche, titres[0]), (droite, titres[1]))):
            x = k * (a.largeur + 8)
            cadre[40:, x:x + a.largeur] = cv2.resize(lire(chemin), (a.largeur, h), interpolation=cv2.INTER_AREA)
            cv2.putText(cadre, titre, (x + 8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
        ecrivain.write(cadre)
    ecrivain.release()
    if not ecrit.is_file() or ecrit.stat().st_size == 0:
        sys.exit("PLANTÉ : la vidéo n'a pas été écrite")
    a.sortie.write_bytes(ecrit.read_bytes())
    ecrit.unlink()
    print(f"film côte à côte : {a.sortie} ({len(listes[0])} images, {len(listes[0]) / a.ips:.1f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
