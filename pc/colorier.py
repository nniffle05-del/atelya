"""Faire colorier par Atelya les plans d'une partie du jeu, et préparer le paquet à noter.

À lancer sur le PC, dans D:\\Modélisation immobilière\\atelya (là où se trouve entrainer.py) :

    uv run python colorier.py --jeu donnees/jeu-10000 --modele resultats-essai-2/atelya-essai-2.pt --sortie coloriages-test

Pour chaque plan de la partie « test » (983 plans jamais vus pendant l'apprentissage),
chaque niveau est colorié tel qu'Atelya l'a appris : dessin en gris, grand côté 768 px.
Le dossier de sortie reçoit, plan par plan :
- niveau_N.png : le coloriage d'Atelya (un numéro de classe 0 à 15 par pixel) ;
- la vérité utile à la note : geometrie.json, logement_niveauN.json,
  niveau_N/annotations.json et niveau_N/masque_semantique.png.
Puis tout est rangé dans un seul fichier zip, facile à copier.

Rien n'est installé : on réutilise le réseau et la fonction `predire` d'entrainer.py.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import zipfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from entrainer import UNet, dessins, lire_partitions, predire


def main() -> None:
    ap = argparse.ArgumentParser(description="Atelya colorie une partie du jeu")
    ap.add_argument("--jeu", type=Path, required=True)
    ap.add_argument("--modele", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--partie", default="test")
    ap.add_argument("--cote", type=int, default=768)
    ap.add_argument("--nombre", type=int, default=0, help="0 = tous les plans de la partie")
    a = ap.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sauve = torch.load(a.modele, map_location=dev)
    modele = UNet(base=sauve.get("base", 32), contexte=sauve.get("contexte", True)).to(dev)
    modele.load_state_dict(sauve["modele"])
    modele.eval()

    ids = lire_partitions(a.jeu)[a.partie]
    if a.nombre:
        ids = ids[:a.nombre]
    a.sortie.mkdir(parents=True, exist_ok=True)
    shutil.copy(a.jeu / "repartition.json", a.sortie / "repartition.json")
    t0, n = time.time(), 0
    for k, ident in enumerate(ids, 1):
        ex = a.jeu / "exemples" / ident
        dest = a.sortie / "exemples" / ident
        dest.mkdir(parents=True, exist_ok=True)
        for nom in ["geometrie.json", *[p.name for p in ex.glob("logement_niveau*.json")]]:
            shutil.copy(ex / nom, dest / nom)
        for dessin in dessins(a.jeu, ident, sans_mobilier=False):
            niv = dessin.parent
            (dest / niv.name).mkdir(exist_ok=True)
            for nom in ("annotations.json", "masque_semantique.png"):
                shutil.copy(niv / nom, dest / niv.name / nom)
            img = Image.open(dessin).convert("L")
            r = a.cote / max(img.size)
            img = img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BILINEAR)
            col = predire(modele, np.array(img, np.uint8), dev)
            Image.fromarray(col).save(dest / f"{niv.name}.png")
            (dest / niv.name / "dessin.txt").write_text(dessin.name, encoding="utf-8")
            n += 1
        if k % 100 == 0 or k == len(ids):
            print(f"{k}/{len(ids)} plans, {n} niveaux coloriés ({time.time() - t0:.0f} s)", flush=True)
    (a.sortie / "resume.json").write_text(json.dumps(
        {"modele": str(a.modele), "partie": a.partie, "plans": len(ids), "niveaux": n,
         "duree_s": round(time.time() - t0, 1), "appareil": str(dev)}, indent=1), encoding="utf-8")
    archive = a.sortie.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(a.sortie.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(a.sortie.parent))
    print(f"fini : {n} niveaux en {time.time() - t0:.0f} s ; paquet {archive} ({archive.stat().st_size / 1e6:.0f} Mo)")


if __name__ == "__main__":
    main()
