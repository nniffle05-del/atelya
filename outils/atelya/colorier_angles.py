"""Étape A1 : Atelya colorie chaque plan sous plusieurs angles et dit où il hésite.

À lancer là où se trouve entrainer.py (PC : D:\\Modélisation immobilière\\atelya) :

    uv run python colorier_angles.py --jeu donnees/jeu-10000 --modele resultats-essai-5/atelya-essai-4.pt \
        --sortie coloriages-a1-test

Même chose que colorier.py, plus une « carte des doutes » par niveau :
- niveau_N.png : le coloriage d'Atelya, IDENTIQUE à colorier.py (lecture normale, rien ne change) ;
- niveau_N-doute.png : pour chaque pixel, 0 (sûr) à 255 (Atelya ne sait pas).

Comment : le plan est colorié 4 fois (normal, retourné gauche-droite, haut-bas, les deux), chaque
résultat est remis à l'endroit, et l'on fait la moyenne des probabilités. Le doute d'un pixel vaut
1 − (probabilité moyenne de la couleur choisie par la lecture normale) : il monte quand Atelya hésite
entre deux couleurs ou quand ses 4 lectures ne sont pas d'accord.

--images : dossier de vrais plans (*.jpg, *.png) au lieu d'un jeu ; écrit <nom>.png et <nom>-doute.png.
Rien n'est installé : on réutilise le réseau d'entrainer.py.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from entrainer import UNet, dessins, lire_partitions, predire

RETOURNEMENTS = ((), (3,), (2,), (2, 3))  # normal, gauche-droite, haut-bas, les deux


def charger_modele(chemin: Path, dev) -> UNet:
    sauve = torch.load(chemin, map_location=dev)
    modele = UNet(base=sauve.get("base", 32), contexte=sauve.get("contexte", True)).to(dev)
    modele.load_state_dict(sauve["modele"])
    return modele.eval()


@torch.no_grad()
def predire_avec_doute(modele, img: np.ndarray, dev) -> tuple[np.ndarray, np.ndarray]:
    """(coloriage de la lecture normale, carte des doutes 0-255)."""
    col = predire(modele, img, dev)  # exactement la lecture habituelle
    h, w = img.shape
    H, W = math.ceil(h / 16) * 16, math.ceil(w / 16) * 16
    x = np.full((H, W), 255, np.uint8)
    x[:h, :w] = img
    t = torch.from_numpy(x)[None, None].float().to(dev) / 255.0
    somme = None
    for axes in RETOURNEMENTS:
        e = torch.flip(t, axes) if axes else t
        with torch.autocast(dev.type, enabled=dev.type == "cuda"):
            s = modele(e)
        p = torch.softmax(s.float(), 1)
        p = torch.flip(p, axes) if axes else p
        somme = p if somme is None else somme + p
    moy = (somme / len(RETOURNEMENTS))[0, :, :h, :w]
    choisie = torch.from_numpy(col.astype(np.int64)).to(dev)[None]
    sure = moy.gather(0, choisie)[0].cpu().numpy()
    doute = np.clip(np.round((1.0 - sure) * 255), 0, 255).astype(np.uint8)
    return col, doute


def reduire(chemin: Path, cote: int) -> np.ndarray:
    img = Image.open(chemin).convert("L")
    r = cote / max(img.size)
    img = img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BILINEAR)
    return np.array(img, np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser(description="Atelya colorie sous 4 angles et écrit la carte des doutes")
    ap.add_argument("--jeu", type=Path)
    ap.add_argument("--images", type=Path, help="dossier de vrais plans (au lieu de --jeu)")
    ap.add_argument("--modele", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--partie", default="test")
    ap.add_argument("--cote", type=int, default=768)
    ap.add_argument("--nombre", type=int, default=0, help="0 = tous les plans de la partie")
    ap.add_argument("--fils", type=int, default=0, help="fils de calcul du processeur (0 = au choix de torch)")
    a = ap.parse_args()
    if a.fils:
        torch.set_num_threads(a.fils)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    modele = charger_modele(a.modele, dev)
    a.sortie.mkdir(parents=True, exist_ok=True)
    t0, n = time.time(), 0

    if a.images:
        for f in sorted(p for p in a.images.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")):
            col, doute = predire_avec_doute(modele, reduire(f, a.cote), dev)
            Image.fromarray(col).save(a.sortie / f"{f.stem}.png")
            Image.fromarray(doute).save(a.sortie / f"{f.stem}-doute.png")
            n += 1
            print(f"{f.name} : {100 * (doute > 127).mean():.1f} % de pixels douteux", flush=True)
    else:
        ids = lire_partitions(a.jeu)[a.partie]
        if a.nombre:
            ids = ids[:a.nombre]
        shutil.copy(a.jeu / "repartition.json", a.sortie / "repartition.json")
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
                col, doute = predire_avec_doute(modele, reduire(dessin, a.cote), dev)
                Image.fromarray(col).save(dest / f"{niv.name}.png")
                Image.fromarray(doute).save(dest / f"{niv.name}-doute.png")
                (dest / niv.name / "dessin.txt").write_text(dessin.name, encoding="utf-8")
                n += 1
            if k % 50 == 0 or k == len(ids):
                print(f"{k}/{len(ids)} plans, {n} niveaux ({time.time() - t0:.0f} s)", flush=True)
    (a.sortie / "resume-angles.json").write_text(json.dumps(
        {"modele": str(a.modele), "niveaux": n, "angles": len(RETOURNEMENTS), "duree_s": round(time.time() - t0, 1),
         "appareil": str(dev)}, indent=1), encoding="utf-8")
    print(f"fini : {n} niveaux en {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
