r"""Trier les parquets arrivés dans la bibliothèque sous un nom provisoire (parquet_acg_NNN, accord de NT du 17/11/2026) :
une planche de leurs images ENTIÈRES (pour les regarder) et, pour chacun, la mesure du sens de ses lames et de leur
écart, en part de la largeur de l'image.

    ..\atelya\.venv\Scripts\python.exe pc\verification\trier_parquets.py <dossier de sortie> [préfixe]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur.images import lire_image  # noqa: E402

BIB = RACINE.parent / "atelya" / "bibliotheque" / "matieres"
COTE, COLONNES, PAR_PLANCHE = 330, 6, 24
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def mesurer(image_bgr: np.ndarray) -> dict:
    """Le sens des lames dans l'image (0 = en travers, de gauche à droite ; 90 = de haut en bas), la netteté de ce sens
    (1 = aucun sens : motif en chevrons ou en damier) et la période des joints en part de la largeur de l'image."""
    g = cv2.cvtColor(cv2.resize(image_bgr, (1024, 1024), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    ix, iy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    ex, ey = float((ix ** 2).sum()), float((iy ** 2).sum())
    en_travers = ey > ex  # joints horizontaux : lames le long de x
    profil = np.abs(iy).mean(1) if en_travers else np.abs(ix).mean(0)
    profil = profil - profil.mean()
    ac = np.correlate(profil, profil, "full")[len(profil) - 1:]
    lo, hi = 20, 400
    k = lo + int(ac[lo:hi].argmax())
    return {"sens": 0 if en_travers else 90, "nettete": round(max(ex, ey) / max(min(ex, ey), 1e-9), 1), "periode": round(k / 1024, 3),
            "lames_par_image": round(1024 / k, 1)}


def main() -> int:
    sortie = Path(sys.argv[1])
    prefixe = sys.argv[2] if len(sys.argv) > 2 else "parquet_acg_"
    sortie.mkdir(parents=True, exist_ok=True)
    infos = json.loads((BIB / "matieres.json").read_text(encoding="utf-8"))
    try:
        police = ImageFont.truetype("arialbd.ttf", 19)
    except OSError:
        police = ImageFont.load_default()
    noms = sorted(d.name for d in BIB.iterdir() if d.is_dir() and d.name.startswith(prefixe))
    mesures, cases = {}, []
    for nom in noms:
        image = lire_image(BIB / nom / "couleur.jpg")
        m = mesurer(image)
        taille = (infos.get(nom) or {}).get("taille_image_m")
        m["taille_image_m"] = taille[0] if taille else None
        mesures[nom] = m
        case = Image.new("RGB", (COTE + 10, COTE + 56), (255, 255, 255))
        case.paste(Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).resize((COTE, COTE), Image.LANCZOS), (5, 5))
        d = ImageDraw.Draw(case)
        d.text((6, COTE + 7), nom.replace(prefixe, "n° ") + (f" : image de {taille[0]} m" if taille else " : taille inconnue"), fill=(0, 0, 0), font=police)
        d.text((6, COTE + 30), f"sens {m['sens']}° (netteté {m['nettete']}), {m['lames_par_image']} lames", fill=(110, 110, 110), font=police)
        cases.append(case)
        print(nom, m)
    for n in range(0, len(cases), PAR_PLANCHE):
        lot = cases[n:n + PAR_PLANCHE]
        w, h = lot[0].size
        lignes = (len(lot) + COLONNES - 1) // COLONNES
        planche = Image.new("RGB", (w * COLONNES, h * lignes), (255, 255, 255))
        for i, case in enumerate(lot):
            planche.paste(case, ((i % COLONNES) * w, (i // COLONNES) * h))
        planche.save(sortie / f"nouveaux-{n // PAR_PLANCHE + 1}.jpg", quality=88)
    (sortie / "mesures.json").write_text(json.dumps(mesures, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
