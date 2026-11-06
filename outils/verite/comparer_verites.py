r"""Comparer deux vérités du même plan, pixel par pixel (masques sémantiques), classe par classe.

Pourquoi : pour juger une méthode de tracé moins coûteuse, on retrace à l'aveugle un plan déjà fait, puis on mesure l'écart.
L'IoU (part commune entre les deux masques, 100 % = identiques) dit si la méthode perd vraiment en qualité. Les deux vérités ont
leurs propres erreurs : un écart dit qu'elles divergent, pas laquelle a raison.

    ..\atelya\.venv\Scripts\python.exe outils\verite\comparer_verites.py ..\atelya\verites-lot2 ..\atelya\verites-test-methode fr-023 fr-030
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

NOMS = {0: "fond", 1: "mur", 2: "porte", 3: "fenetre", 4: "porte_fenetre", 5: "sejour", 6: "cuisine", 7: "chambre", 8: "salle_d_eau",
        9: "wc", 10: "entree", 11: "degagement", 12: "placard", 13: "buanderie", 14: "bureau", 15: "escalier"}
TOUTES_PIECES = list(range(5, 16))


def iou(a: np.ndarray, b: np.ndarray) -> float | None:
    u = (a | b).sum()
    return round(100 * float((a & b).sum()) / float(u), 1) if u else None


def comparer(ref: np.ndarray, autre: np.ndarray) -> dict:
    sortie = {"pixels_identiques": round(100 * float((ref == autre).mean()), 1),
              "bati_mur_ouv": iou(np.isin(ref, [1, 2, 3, 4]), np.isin(autre, [1, 2, 3, 4])),
              "interieur": iou(np.isin(ref, TOUTES_PIECES), np.isin(autre, TOUTES_PIECES))}
    par_classe = {NOMS[c]: iou(ref == c, autre == c) for c in sorted(set(np.unique(ref)) | set(np.unique(autre))) if c != 0}
    vals = [v for v in par_classe.values() if v is not None]
    sortie["iou_moyen"] = round(sum(vals) / max(1, len(vals)), 1)
    sortie["par_classe"] = par_classe
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reference", type=Path)
    ap.add_argument("autre", type=Path)
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--carte", action="store_true", help="écrit desaccord.png dans le dossier de référence (différences en rouge)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for p in a.plans:
        ref = np.array(Image.open(a.reference / p / "masque_semantique.png"))
        aut = np.array(Image.open(a.autre / p / "masque_semantique.png"))
        if ref.shape != aut.shape:
            print(f"{p} : tailles différentes {ref.shape} {aut.shape}")
            return 2
        r = comparer(ref, aut)
        e = [json.loads((d / p / "verite.json").read_text(encoding="utf-8"))["px_par_m"] for d in (a.reference, a.autre)]
        print(f"{p} : {json.dumps(r, ensure_ascii=False)} ; échelles {e[0]} / {e[1]} px/m ({100 * (e[1] / e[0] - 1):+.1f} %)")
        if a.carte:  # le plan en gris, en rouge là où les deux tracés ne disent pas la même chose : ce que le relecteur doit trancher
            image = next(f for f in (a.reference / p).glob(f"{p}.*") if f.suffix.lower() in (".jpg", ".jpeg", ".png"))
            fond = np.array(Image.open(image).convert("RGB"))
            fond[ref != aut] = (255, 0, 0)
            Image.fromarray(fond).save(a.reference / p / "desaccord.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
