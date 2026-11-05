r"""Transformer une lecture d'Atelya en BROUILLON de saisie de vérité (pixels de l'image), à corriger à la main.

Pourquoi : tracer une vérité de zéro prend 20 à 40 minutes par plan ; partir de ce qu'Atelya a déjà lu (murs, ouvertures,
pièces, posés sur l'image par le calage de l'écran de vérification) va plus vite sur les plans propres. Le brouillon
garde les erreurs d'Atelya (faux murs, pièces coupées) : il faut le relire, pas le recopier.

    ..\atelya\.venv\Scripts\python.exe outils\verite\brouillon_saisie.py ..\atelya\lectures-lot-2026-11-05\fr-020 ..\atelya\vrais-plans\lot-2026-11-05\fr-020.jpg ..\atelya\verites\fr-020

Écrit <sortie>\brouillon-saisie.json (format de faire_verite.py) et copie l'image dans <sortie>.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.images import lire_image  # noqa: E402


def _projeter(M: np.ndarray, x: float, y: float) -> tuple[float, float]:
    u, v, w = M @ (x, y, 1.0)
    return float(u / w), float(v / w)


def _point_dedans(contour_px: list[tuple[float, float]], forme: tuple[int, int]) -> tuple[float, float]:
    """Un point bien à l'intérieur du contour (le plus loin des bords), pour que la saisie tombe dans la zone."""
    H, W = forme
    m = np.zeros((H, W), np.uint8)
    pts = np.array([[int(round(x)), int(round(y))] for x, y in contour_px], np.int32)
    cv2.fillPoly(m, [pts], 1)
    if m.sum() == 0:
        xs, ys = zip(*contour_px)
        return float(np.mean(xs)), float(np.mean(ys))
    d = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    y, x = np.unravel_index(int(np.argmax(d)), d.shape)
    return float(x), float(y)


def brouillon(lecture: Path, image: Path, sortie: Path) -> dict:
    v = json.loads((lecture / "verification.json").read_text(encoding="utf-8"))
    M = np.asarray(v["calage"]["matrice"], float)
    s = math.sqrt(abs(np.linalg.det(M[:2, :2])))  # px par m (moyenne des deux axes)
    img = lire_image(str(image))
    H, W = img.shape[:2]
    log = v["logement"]
    murs = []
    for m in log["murs"]:
        x0, y0 = _projeter(M, *m["debut"])
        x1, y1 = _projeter(M, *m["fin"])
        murs.append([round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), round(max(2.0, m["epaisseur"] * s), 1)])
    par_id = {m["id"]: m for m in log["murs"]}
    ouvertures = []
    for o in log["ouvertures"]:
        m = par_id[o["mur"]]
        (ax, ay), (bx, by) = m["debut"], m["fin"]
        L = math.hypot(bx - ax, by - ay) or 1e-9
        ux, uy = (bx - ax) / L, (by - ay) / L
        p0 = (ax + o["position"] * ux, ay + o["position"] * uy)
        p1 = (ax + (o["position"] + o["largeur"]) * ux, ay + (o["position"] + o["largeur"]) * uy)
        x0, y0 = _projeter(M, *p0)
        x1, y1 = _projeter(M, *p1)
        ouvertures.append([o["type"], round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)])
    pieces = []
    for p in log["pieces"]:
        contour_px = [_projeter(M, x, y) for x, y in p["contour"]]
        x, y = _point_dedans(contour_px, (H, W))
        type_ = p["id"].rsplit("_", 1)[0]
        pieces.append([p.get("nom") or type_, type_, round(x, 1), round(y, 1)])
    e = v.get("echelle", {})
    b = {"image": image.name,
         "_brouillon": "lecture d'Atelya (lecture_complete), posée sur l'image par le calage ; À RELIRE ET CORRIGER",
         "_echelle_atelya": {"px_par_m_image": round(s, 2), "etat": e.get("etat"), "source": e.get("source")},
         "px_par_m": round(s, 2), "echelle_source": f"brouillon Atelya ({e.get('etat')}, {e.get('source')}) : À VÉRIFIER",
         "hsp": 2.5, "affiner": True, "murs": murs, "ouvertures": ouvertures, "pieces": pieces, "incertain": []}
    sortie.mkdir(parents=True, exist_ok=True)
    if not (sortie / image.name).exists():
        shutil.copyfile(image, sortie / image.name)
    (sortie / "brouillon-saisie.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    return b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lecture", type=Path, help="dossier de lecture (contient verification.json)")
    ap.add_argument("image", type=Path, help="l'image du plan (celle qui a été lue)")
    ap.add_argument("sortie", type=Path, help="dossier de la vérité")
    a = ap.parse_args()
    b = brouillon(a.lecture, a.image, a.sortie)
    print(f"{a.sortie.name} : brouillon {len(b['murs'])} murs, {len(b['ouvertures'])} ouvertures, {len(b['pieces'])} pièces, "
          f"{b['px_par_m']} px/m ({b['_echelle_atelya']['etat']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
