"""Monter un film à partir de plusieurs plans rendus (11/11/2026) : les plans bout à bout, avec un fondu enchaîné entre deux.

    python outils/unreal/monter_film.py <sortie.mp4> <dossier_plan> [<dossier_plan> …] [--fondu 0.5] [--ips 24]

Chaque dossier contient image-0001.png… (outils/unreal/cinematique_unreal.py). Le fondu mêle la fin d'un plan au début du
suivant (0,5 s par défaut) : le film dure la somme des plans moins les fondus.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def _lire(chemin: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)


def monter(sortie: Path, plans: list[Path], fondu_s: float = 0.5, ips: int = 24) -> dict:
    listes = [sorted(p.glob("image-*.png")) for p in plans]
    if not all(listes):
        sys.exit("PLANTÉ : un plan n'a pas d'images (" + ", ".join(str(p) for p, l in zip(plans, listes) if not l) + ")")
    h, w = _lire(listes[0][0]).shape[:2]
    n_fondu = int(round(fondu_s * ips))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    ecrivain = cv2.VideoWriter(str(sortie), cv2.VideoWriter_fourcc(*"mp4v"), ips, (w, h))
    total = 0
    for k, images in enumerate(listes):
        debut = n_fondu if k > 0 else 0
        fin = len(images) - (n_fondu if k < len(listes) - 1 else 0)
        for i in range(debut, fin):
            ecrivain.write(cv2.resize(_lire(images[i]), (w, h)))
            total += 1
        if k < len(listes) - 1:
            suivant = listes[k + 1]
            for j in range(n_fondu):
                a = cv2.resize(_lire(images[fin + j]), (w, h)).astype(np.float32)
                b = cv2.resize(_lire(suivant[j]), (w, h)).astype(np.float32)
                t = (j + 1) / (n_fondu + 1)
                ecrivain.write(np.clip(a * (1 - t) + b * t, 0, 255).astype(np.uint8))
                total += 1
    ecrivain.release()
    return {"sortie": str(sortie), "images": total, "duree_s": round(total / ips, 2), "format": [w, h]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sortie")
    p.add_argument("plans", nargs="+")
    p.add_argument("--fondu", type=float, default=0.5)
    p.add_argument("--ips", type=int, default=24)
    a = p.parse_args()
    print(monter(Path(a.sortie), [Path(x) for x in a.plans], a.fondu, a.ips))


if __name__ == "__main__":
    main()
