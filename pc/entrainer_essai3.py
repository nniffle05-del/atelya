"""Atelya, essai n°3 : mieux reconnaître les petites pièces (WC, placard, buanderie, bureau).

Repart d'Atelya essai 2 (même réseau, mêmes 16 classes) et le perfectionne :
- Morceaux ciblés : environ la moitié des morceaux de plan sont centrés sur une petite pièce
  (classe tirée au hasard parmi les 4, pour que le bureau, très rare, soit vu autant que le WC).
  L'autre moitié reste tirée au hasard, pour ne rien oublier du reste.
- Erreurs comptées plus fort sur ces 4 classes (--renfort, ×2,5 par défaut en plus du poids de l'essai 2).
- Reprise des réglages appris par l'essai 2 (--reprendre), avec un pas d'apprentissage plus petit.

Utilise les fonctions d'entrainer.py (essai 2), à poser dans le même dossier.

Utilisation (dans D:\\Modélisation immobilière\\atelya) :
    uv run python entrainer_essai3.py --jeu donnees/jeu-10000 --reprendre resultats-essai-2/atelya-essai-2.pt
        --sortie resultats-essai-3 --minutes 90 --comparer resultats-essai-2/atelya-essai-2.pt
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import entrainer as e2
from entrainer import NB_CLASSES, NOMS, UNet, charger_liste, de_png, evaluer, lire_partitions, planche, temperature_gpu

PETITES = [NOMS.index(n) for n in ("wc", "placard", "buanderie", "bureau")]


def morceau_centre(img: np.ndarray, msq: np.ndarray, taille: int, classe: int):
    """Carré de `taille` px centré (à ±1/4 de taille près) sur un pixel de `classe`, tourné/retourné au hasard."""
    ys, xs = np.nonzero(msq == classe)
    k = random.randrange(len(ys))
    j = taille // 4
    cy, cx = ys[k] + random.randint(-j, j), xs[k] + random.randint(-j, j)
    h, w = img.shape
    d = taille  # marge blanche autour du plan, pour pouvoir centrer près des bords
    i2 = np.full((h + 2 * d, w + 2 * d), 255, np.uint8); m2 = np.zeros((h + 2 * d, w + 2 * d), np.uint8)
    i2[d:d + h, d:d + w] = img; m2[d:d + h, d:d + w] = msq
    y, x = cy + d - taille // 2, cx + d - taille // 2
    img, msq = i2[y:y + taille, x:x + taille], m2[y:y + taille, x:x + taille]
    r = random.randint(0, 3)
    img, msq = np.rot90(img, r), np.rot90(msq, r)
    if random.random() < 0.5:
        img, msq = img[:, ::-1], msq[:, ::-1]
    return np.ascontiguousarray(img), np.ascontiguousarray(msq)


class DistributeurCible(e2.Distributeur):
    """Comme l'essai 2, mais une part `cible` des morceaux est centrée sur une petite pièce."""

    def __init__(self, paires, taille, n, debord, avec: dict[int, list[int]], cible: float):
        self.avec, self.cible = {c: l for c, l in avec.items() if l}, cible
        super().__init__(paires, taille, n, debord)

    def _un(self, _):
        if self.avec and random.random() < self.cible:
            c = random.choice(list(self.avec))
            a, b = self.paires[random.choice(self.avec[c])]
            return morceau_centre(de_png(a), de_png(b), self.taille, c)
        return super()._un(_)


def recenser(paires) -> dict[int, list[int]]:
    """Pour chaque petite classe, les dessins qui en contiennent (au moins 30 px)."""
    avec = {c: [] for c in PETITES}
    for i, (_, b) in enumerate(paires):
        n = np.bincount(de_png(b).ravel(), minlength=NB_CLASSES)
        for c in PETITES:
            if n[c] >= 30:
                avec[c].append(i)
    return avec


def main():
    ap = argparse.ArgumentParser(description="Entraîner Atelya (essai 3 : petites pièces)")
    ap.add_argument("--jeu", type=Path, required=True)
    ap.add_argument("--reprendre", type=Path, required=True, help="modèle de l'essai 2 (.pt)")
    ap.add_argument("--sortie", type=Path, default=Path("resultats-essai-3"))
    ap.add_argument("--nb-train", type=int, default=0, help="0 = tous les plans d'apprentissage")
    ap.add_argument("--nb-val", type=int, default=150)
    ap.add_argument("--nb-val-final", type=int, default=0)
    ap.add_argument("--cote", type=int, default=768)
    ap.add_argument("--morceau", type=int, default=512)
    ap.add_argument("--debord", type=float, default=0.5)
    ap.add_argument("--lot", type=int, default=4)
    ap.add_argument("--cible", type=float, default=0.5, help="part des morceaux centrés sur une petite pièce")
    ap.add_argument("--renfort", type=float, default=2.5, help="poids en plus des erreurs sur les petites pièces")
    ap.add_argument("--lr", type=float, default=3e-4, help="pas d'apprentissage de départ (essai 2 : 1e-3)")
    ap.add_argument("--minutes", type=float, default=90)
    ap.add_argument("--pas-par-tour", type=int, default=500)
    ap.add_argument("--processus", type=int, default=6)
    ap.add_argument("--temp-max", type=int, default=88)
    ap.add_argument("--comparer", type=Path, help="modèle précédent (.pt), noté à la fin sur les mêmes plans")
    ap.add_argument("--graine", type=int, default=3)
    a = ap.parse_args()

    random.seed(a.graine); np.random.seed(a.graine); torch.manual_seed(a.graine)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Atelya, essai 3 : calcul sur {torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'processeur'}", flush=True)
    a.sortie.mkdir(parents=True, exist_ok=True)

    parts = lire_partitions(a.jeu)
    ids_train = parts["train"][:a.nb_train] if a.nb_train else parts["train"]
    ids_val = parts["val"][:a.nb_val_final] if a.nb_val_final else parts["val"]
    train = charger_liste(a.jeu, ids_train, a.cote, "apprentissage", a.processus, sans_mobilier=True)
    val_final = charger_liste(a.jeu, ids_val, a.cote, "controle", a.processus)
    val = val_final[:a.nb_val]
    t = time.time()
    avec = recenser(train)
    print(f"Lecture : {len(train)} dessins ; petites pièces ({time.time() - t:.0f} s) : "
          + ", ".join(f"{NOMS[c]} {len(l)}" for c, l in avec.items()), flush=True)

    # Mêmes poids que l'essai 2, puis renfort sur les 4 petites pièces.
    freq = np.zeros(NB_CLASSES)
    for _, b in random.sample(train, min(1500, len(train))):
        freq += np.bincount(de_png(b).ravel(), minlength=NB_CLASSES)
    w = np.clip((freq.sum() / np.maximum(freq, 1) / NB_CLASSES) ** 0.5, 0.2, 10)
    w[PETITES] *= a.renfort
    poids = torch.tensor(w, dtype=torch.float32, device=dev)
    print("Poids : " + ", ".join(f"{NOMS[c]} {w[c]:.2f}" for c in range(NB_CLASSES)), flush=True)

    ancien = torch.load(a.reprendre, map_location=dev)
    modele = UNet(ancien.get("base", 32), contexte=ancien.get("contexte", True)).to(dev)
    modele.load_state_dict(ancien["modele"])
    depart = evaluer(modele, val, dev)
    print(f"Départ (essai 2) : IoU moyen {depart['iou_moyen_pct']}%  "
          + "  ".join(f"{NOMS[c]} {depart['iou_par_classe_pct'][NOMS[c]]}%" for c in PETITES), flush=True)

    opt = torch.optim.AdamW(modele.parameters(), lr=a.lr, weight_decay=1e-4)
    echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
    distrib = DistributeurCible(train, a.morceau, a.lot, a.debord, avec, a.cible)
    duree, t0, pas, historique, meilleur, pauses = a.minutes * 60, time.time(), 0, [depart], -1.0, 0.0

    while time.time() - t0 - pauses < duree:
        perte_tour = 0.0
        for _ in range(a.pas_par_tour):
            frac = min((time.time() - t0 - pauses) / duree, 1.0)
            for g in opt.param_groups:
                g["lr"] = a.lr * (0.5 * (1 + math.cos(math.pi * frac)) * 0.95 + 0.05)
            x, y = distrib.lot()
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                perte = F.cross_entropy(modele(x), y, weight=poids)
            opt.zero_grad(set_to_none=True)
            echelle.scale(perte).backward(); echelle.step(opt); echelle.update()
            perte_tour += perte.item(); pas += 1
        note = evaluer(modele, val, dev)
        temp = temperature_gpu()
        note.update(pas=pas, minutes=round((time.time() - t0 - pauses) / 60, 1), perte=round(perte_tour / a.pas_par_tour, 4),
                    temperature_gpu=temp)
        historique.append(note)
        iou = note["iou_par_classe_pct"]
        print(f"[{note['minutes']:5.1f} min] pas {pas:6d}  perte {note['perte']:.3f}  IoU moyen {note['iou_moyen_pct']}%  "
              f"murs {iou['mur']}%  " + "  ".join(f"{NOMS[c]} {iou[NOMS[c]]}%" for c in PETITES) + f"  GPU {temp} °C", flush=True)
        if note["iou_moyen_pct"] > meilleur:
            meilleur = note["iou_moyen_pct"]
            torch.save({"modele": modele.state_dict(), "base": ancien.get("base", 32), "contexte": ancien.get("contexte", True),
                        "classes": NOMS, "cote": a.cote, "note": note}, a.sortie / "atelya-essai-3.pt")
        (a.sortie / "historique.json").write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
        while temp is not None and temp > a.temp_max:
            print(f"  carte graphique à {temp} °C : pause d'une minute pour la laisser refroidir", flush=True)
            time.sleep(60); pauses += 60; temp = temperature_gpu()

    modele.load_state_dict(torch.load(a.sortie / "atelya-essai-3.pt", map_location=dev)["modele"])
    final = evaluer(modele, val_final, dev)
    planche(modele, val_final, dev, a.sortie / "planche-plan-verite-atelya.png")
    bilan = {"meilleure_note": final, "pas": pas, "minutes": round((time.time() - t0) / 60, 1),
             "minutes_de_pause_chaleur": round(pauses / 60, 1), "plans_appris": len(ids_train),
             "dessins_avec_petites_pieces": {NOMS[c]: len(l) for c, l in avec.items()},
             "reglages": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
             "machine": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu"}
    if a.comparer and a.comparer.exists():
        m = torch.load(a.comparer, map_location=dev)
        m1 = UNet(m.get("base", 32), contexte=m.get("contexte", True)).to(dev)
        m1.load_state_dict(m["modele"])
        bilan["essai_precedent_meme_controle"] = evaluer(m1, val_final, dev)
        print("ESSAI PRECEDENT " + json.dumps(bilan["essai_precedent_meme_controle"], ensure_ascii=False), flush=True)
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BILAN " + json.dumps(final, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
