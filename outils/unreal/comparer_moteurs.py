"""Vidéo et planche comparatives d'un même plan rendu par plusieurs moteurs (11/11/2026 : Cycles, EEVEE, Unreal Engine 5).

    python outils/unreal/comparer_moteurs.py <sortie_sans_extension> "Titre|dossier|secondes par image" [...]

Chaque dossier contient image-0001.png… (même trajet, même nombre d'images). Écrit <sortie>.mp4 (les moteurs côte à côte, avec
leur nom et leur temps de calcul par image) et <sortie>.jpg (l'image du milieu, en grand, l'une sous l'autre).
"""
import sys
from pathlib import Path

import cv2
import numpy as np


def _lire(chemin):
    return cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)


def _etiquette(image, texte):
    cv2.rectangle(image, (0, 0), (image.shape[1], 30), (255, 255, 255), -1)
    cv2.putText(image, texte, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    return image


def comparer(sortie: Path, moteurs: list[tuple[str, Path, float]], largeur=640, ips=24) -> None:
    listes = [sorted(d.glob("image-*.png")) for _, d, _ in moteurs]
    n = min(len(l) for l in listes)
    if n == 0:
        sys.exit("PLANTÉ : un des dossiers n'a pas d'images")
    premiere = _lire(listes[0][0])
    hauteur = round(premiere.shape[0] * largeur / premiere.shape[1])
    video = cv2.VideoWriter(str(sortie.with_suffix(".mp4")), cv2.VideoWriter_fourcc(*"mp4v"), ips,
                            (largeur * len(moteurs), hauteur))
    for i in range(n):
        cases = [_etiquette(cv2.resize(_lire(l[i]), (largeur, hauteur), interpolation=cv2.INTER_AREA),
                            f"{titre} : {s:.1f} s / image") for (titre, _, s), l in zip(moteurs, listes)]
        video.write(np.hstack(cases))
    video.release()
    milieu = n // 2
    grandes = [_etiquette(_lire(l[milieu]).copy(), f"{titre} : {s:.1f} s / image") for (titre, _, s), l in zip(moteurs, listes)]
    cv2.imencode(".jpg", np.vstack(grandes), [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(str(sortie.with_suffix(".jpg")))


if __name__ == "__main__":
    sortie = Path(sys.argv[1])
    moteurs = []
    for a in sys.argv[2:]:
        titre, dossier, secondes = a.split("|")
        moteurs.append((titre, Path(dossier), float(secondes)))
    comparer(sortie, moteurs)
    print(f"{sortie.with_suffix('.mp4')} et {sortie.with_suffix('.jpg')}")
