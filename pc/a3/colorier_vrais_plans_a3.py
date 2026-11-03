"""Atelya colorie de vrais plans (images seules, sans vérité) et fabrique des planches à regarder.

À lancer sur le PC, dans D:\\Modélisation immobilière\\atelya :
    .venv\\Scripts\\python.exe colorier_vrais_plans.py --dossier vrais-plans\\lot-2026-10-31 ^
        --modele resultats-essai-5\\atelya-essai-4.pt --sortie vrais-plans\\coloriages-lot-2026-10-31
Rien n'est installé : on réutilise le réseau et `predire` d'entrainer.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from oeil import charger_modele  # A3 : lit aussi les modèles avec œil DINOv2
from entrainer import COULEURS, NOMS, UNet, predire




def legende(hauteur: int) -> np.ndarray:
    im = Image.new("RGB", (190, hauteur), "white")
    d = ImageDraw.Draw(im)
    for c, nom in enumerate(NOMS):
        y = 10 + c * 22
        d.rectangle([8, y, 26, y + 16], fill=tuple(int(v) for v in COULEURS[c]), outline="black")
        d.text((34, y + 2), nom, fill="black")
    return np.array(im)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", type=Path, required=True)
    ap.add_argument("--modele", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--cote", type=int, default=768)
    a = ap.parse_args()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    modele = charger_modele(a.modele, dev)
    a.sortie.mkdir(parents=True, exist_ok=True)
    resume = {"modele": str(a.modele), "appareil": str(dev), "plans": {}}
    for f in sorted(a.dossier.glob("*.jpg")):
        img = Image.open(f).convert("L")
        r = a.cote / max(img.size)
        img = img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BILINEAR)
        gris = np.array(img, np.uint8)
        col = predire(modele, gris, dev)
        Image.fromarray(col).save(a.sortie / f"{f.stem}-classes.png")
        couleur = COULEURS[col].astype(np.uint8)
        melange = (0.45 * np.stack([gris] * 3, -1) + 0.55 * couleur).astype(np.uint8)
        h = gris.shape[0]
        leg = legende(h) if h >= 370 else np.full((h, 190, 3), 255, np.uint8)
        planche = np.concatenate([np.stack([gris] * 3, -1), np.full((h, 8, 3), 255, np.uint8), melange,
                                  np.full((h, 8, 3), 255, np.uint8), leg], 1)
        Image.fromarray(planche).save(a.sortie / f"{f.stem}-planche.jpg", quality=90)
        part = np.bincount(col.ravel(), minlength=len(NOMS)) / col.size * 100
        resume["plans"][f.stem] = {NOMS[c]: round(float(part[c]), 2) for c in range(len(NOMS)) if part[c] >= 0.05}
        print(f"{f.name} : colorié ({gris.shape[1]}x{gris.shape[0]})", flush=True)
    (a.sortie / "resume.json").write_text(json.dumps(resume, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"FINI : {len(resume['plans'])} plans", flush=True)


if __name__ == "__main__":
    main()
