"""Atelya, essai n°1 : apprendre à colorier un plan pixel par pixel.

Atelya regarde l'image d'un plan (plan.jpg) et doit retrouver, pour chaque
pixel, ce qu'il représente : fond, mur, porte, fenêtre, type de pièce...
La « bonne réponse » est le masque sémantique dessiné par le générateur
(masque_semantique.png, 16 classes). Le réseau est un petit U-Net écrit ici
de zéro, sans poids appris par d'autres (aucune question de licence).

Utilisation (dans D:\\Modélisation immobilière\\atelya) :
    uv run python entrainer.py --jeu donnees/jeu-10000 --nb-train 1000 --minutes 25
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
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

NOMS = ["fond", "mur", "porte", "fenetre", "porte-fenetre", "sejour", "cuisine",
        "chambre", "salle d'eau", "wc", "entree", "degagement", "placard",
        "buanderie", "bureau", "escalier"]
NB_CLASSES = len(NOMS)
COULEURS = np.array([
    [255, 255, 255], [30, 30, 30], [220, 40, 40], [40, 120, 230], [140, 60, 200],
    [250, 200, 80], [250, 130, 50], [120, 200, 120], [80, 200, 220], [170, 230, 250],
    [230, 170, 200], [200, 200, 160], [150, 110, 80], [100, 160, 160], [190, 150, 230],
    [120, 120, 200]], dtype=np.uint8)


# ---------- lecture du jeu ----------

def lire_partitions(jeu: Path) -> dict[str, list[str]]:
    rep = json.loads((jeu / "repartition.json").read_text(encoding="utf-8"))
    parts = rep.get("partitions", rep)
    sortie: dict[str, list[str]] = {}
    for nom, ids in parts.items():
        cle = "train" if "train" in nom else "val" if nom.startswith("val") else "test" if "test" in nom else nom
        sortie[cle] = [str(i).zfill(6) if str(i).isdigit() else str(i) for i in ids]
    return sortie


def niveaux(jeu: Path, ident: str) -> list[Path]:
    return sorted(p for p in (jeu / "exemples" / ident).glob("niveau_*") if (p / "plan.jpg").exists())


def charger(dossier: Path, cote: int) -> tuple[np.ndarray, np.ndarray]:
    """Image (gris, uint8) et masque (uint8) réduits pour que le grand côté fasse `cote` px."""
    img = Image.open(dossier / "plan.jpg").convert("L")
    msq = Image.open(dossier / "masque_semantique.png")
    if msq.mode not in ("L", "P"):
        msq = msq.convert("L")
    r = cote / max(img.size)
    taille = (max(1, round(img.width * r)), max(1, round(img.height * r)))
    img = img.resize(taille, Image.BILINEAR)
    msq = msq.resize(taille, Image.NEAREST)
    m = np.array(msq, dtype=np.uint8)
    m[m >= NB_CLASSES] = 0
    return np.array(img, dtype=np.uint8), m


def charger_liste(jeu: Path, ids: list[str], cote: int, nom: str):
    paires, t0 = [], time.time()
    for k, ident in enumerate(ids, 1):
        for d in niveaux(jeu, ident):
            paires.append(charger(d, cote))
        if k % 200 == 0 or k == len(ids):
            print(f"  {nom} : {k}/{len(ids)} plans lus ({time.time() - t0:.0f} s)", flush=True)
    return paires


def morceau(img: np.ndarray, msq: np.ndarray, taille: int):
    """Découpe un carré au hasard (complété de blanc si le plan est plus petit), tourné/retourné au hasard."""
    h, w = img.shape
    H, W = max(h, taille), max(w, taille)
    if (H, W) != (h, w):
        i2 = np.full((H, W), 255, np.uint8); i2[:h, :w] = img
        m2 = np.zeros((H, W), np.uint8); m2[:h, :w] = msq
        img, msq = i2, m2
    y = random.randint(0, H - taille); x = random.randint(0, W - taille)
    img, msq = img[y:y + taille, x:x + taille], msq[y:y + taille, x:x + taille]
    k = random.randint(0, 3)
    img, msq = np.rot90(img, k), np.rot90(msq, k)
    if random.random() < 0.5:
        img, msq = img[:, ::-1], msq[:, ::-1]
    return np.ascontiguousarray(img), np.ascontiguousarray(msq)


def lot(paires, taille: int, n: int):
    choix = [morceau(*random.choice(paires), taille) for _ in range(n)]
    x = torch.from_numpy(np.stack([c[0] for c in choix]))[:, None].float() / 255.0
    y = torch.from_numpy(np.stack([c[1] for c in choix])).long()
    return x, y


# ---------- le réseau (U-Net) ----------

class Bloc(nn.Sequential):
    def __init__(self, a: int, b: int):
        super().__init__(nn.Conv2d(a, b, 3, padding=1, bias=False), nn.BatchNorm2d(b), nn.ReLU(inplace=True),
                         nn.Conv2d(b, b, 3, padding=1, bias=False), nn.BatchNorm2d(b), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, base: int = 32, classes: int = NB_CLASSES):
        super().__init__()
        c = [base, base * 2, base * 4, base * 8, base * 16]
        self.desc = nn.ModuleList([Bloc(1, c[0])] + [Bloc(c[i], c[i + 1]) for i in range(4)])
        self.mont = nn.ModuleList([nn.ConvTranspose2d(c[i + 1], c[i], 2, stride=2) for i in reversed(range(4))])
        self.fus = nn.ModuleList([Bloc(c[i] * 2, c[i]) for i in reversed(range(4))])
        self.tete = nn.Conv2d(c[0], classes, 1)

    def forward(self, x):
        gardes = []
        for i, b in enumerate(self.desc):
            x = b(x if i == 0 else F.max_pool2d(x, 2))
            gardes.append(x)
        gardes.pop()
        for m, f in zip(self.mont, self.fus):
            x = f(torch.cat([m(x), gardes.pop()], 1))
        return self.tete(x)


# ---------- évaluation ----------

@torch.no_grad()
def predire(modele, img: np.ndarray, dev) -> np.ndarray:
    h, w = img.shape
    H, W = math.ceil(h / 16) * 16, math.ceil(w / 16) * 16
    x = np.full((H, W), 255, np.uint8); x[:h, :w] = img
    t = torch.from_numpy(x)[None, None].float().to(dev) / 255.0
    with torch.autocast(dev.type, enabled=dev.type == "cuda"):
        s = modele(t)
    return s.argmax(1)[0, :h, :w].cpu().numpy().astype(np.uint8)


def evaluer(modele, paires, dev) -> dict:
    modele.eval()
    inter = np.zeros(NB_CLASSES); union = np.zeros(NB_CLASSES); vrais = np.zeros(NB_CLASSES); justes = total = 0
    for img, msq in paires:
        p = predire(modele, img, dev)
        justes += int((p == msq).sum()); total += msq.size
        for c in range(NB_CLASSES):
            a, b = p == c, msq == c
            inter[c] += (a & b).sum(); union[c] += (a | b).sum(); vrais[c] += b.sum()
    modele.train()
    # IoU = part commune entre la réponse d'Atelya et la vérité (100 % = parfait), pour les classes présentes.
    iou = {NOMS[c]: (round(float(inter[c] / union[c]) * 100, 1) if vrais[c] else None) for c in range(NB_CLASSES)}
    vals = [v for v in iou.values() if v is not None]
    return {"pixels_justes_pct": round(100 * justes / max(total, 1), 1),
            "iou_moyen_pct": round(sum(vals) / max(len(vals), 1), 1), "iou_par_classe_pct": iou}


def planche(modele, paires, dev, chemin: Path, n: int = 4):
    lignes = []
    for img, msq in paires[:n]:
        p = predire(modele, img, dev)
        lignes.append(np.concatenate([np.stack([img] * 3, -1), COULEURS[msq], COULEURS[p]], 1))
    w = max(l.shape[1] for l in lignes)
    lignes = [np.pad(l, ((0, 8), (0, w - l.shape[1]), (0, 0)), constant_values=255) for l in lignes]
    Image.fromarray(np.concatenate(lignes, 0)).save(chemin)


# ---------- programme principal ----------

def main():
    ap = argparse.ArgumentParser(description="Entraîner Atelya (essai)")
    ap.add_argument("--jeu", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, default=Path("sorties/essai-1"))
    ap.add_argument("--nb-train", type=int, default=1000)
    ap.add_argument("--nb-val", type=int, default=150)
    ap.add_argument("--cote", type=int, default=768, help="grand côté du plan réduit, en px")
    ap.add_argument("--morceau", type=int, default=384)
    ap.add_argument("--lot", type=int, default=8)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--minutes", type=float, default=25)
    ap.add_argument("--pas-par-tour", type=int, default=250)
    ap.add_argument("--graine", type=int, default=1)
    a = ap.parse_args()

    random.seed(a.graine); np.random.seed(a.graine); torch.manual_seed(a.graine)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Atelya, essai : calcul sur {torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'processeur'}", flush=True)
    a.sortie.mkdir(parents=True, exist_ok=True)

    parts = lire_partitions(a.jeu)
    print(f"Jeu : " + ", ".join(f"{k} {len(v)}" for k, v in parts.items()), flush=True)
    train = charger_liste(a.jeu, parts["train"][:a.nb_train], a.cote, "apprentissage")
    val = charger_liste(a.jeu, parts["val"][:a.nb_val], a.cote, "contrôle")

    # Poids des classes : les classes rares (portes, WC...) comptent plus, sinon Atelya les ignorerait.
    freq = np.bincount(np.concatenate([m.ravel() for _, m in train]), minlength=NB_CLASSES).astype(float)
    poids = torch.tensor(np.clip((freq.sum() / np.maximum(freq, 1) / NB_CLASSES) ** 0.5, 0.2, 10), dtype=torch.float32, device=dev)

    modele = UNet(a.base).to(dev)
    print(f"Réseau : {sum(p.numel() for p in modele.parameters()) / 1e6:.1f} millions de réglages", flush=True)
    opt = torch.optim.AdamW(modele.parameters(), lr=1e-3, weight_decay=1e-4)
    echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
    duree, t0, pas, historique, meilleur = a.minutes * 60, time.time(), 0, [], -1.0

    while time.time() - t0 < duree:
        perte_tour = 0.0
        for _ in range(a.pas_par_tour):
            frac = min((time.time() - t0) / duree, 1.0)
            for g in opt.param_groups:
                g["lr"] = 1e-3 * (0.5 * (1 + math.cos(math.pi * frac)) * 0.95 + 0.05)
            x, y = lot(train, a.morceau, a.lot)
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                perte = F.cross_entropy(modele(x), y, weight=poids)
            opt.zero_grad(set_to_none=True)
            echelle.scale(perte).backward(); echelle.step(opt); echelle.update()
            perte_tour += perte.item(); pas += 1
        note = evaluer(modele, val, dev)
        note.update(pas=pas, minutes=round((time.time() - t0) / 60, 1), perte=round(perte_tour / a.pas_par_tour, 4))
        historique.append(note)
        iou = note["iou_par_classe_pct"]
        print(f"[{note['minutes']:5.1f} min] pas {pas:6d}  perte {note['perte']:.3f}  pixels justes {note['pixels_justes_pct']}%  "
              f"IoU moyen {note['iou_moyen_pct']}%  murs {iou['mur']}%  portes {iou['porte']}%  fenêtres {iou['fenetre']}%", flush=True)
        if note["iou_moyen_pct"] > meilleur:
            meilleur = note["iou_moyen_pct"]
            torch.save({"modele": modele.state_dict(), "base": a.base, "classes": NOMS, "cote": a.cote, "note": note},
                       a.sortie / "atelya-essai.pt")
        (a.sortie / "historique.json").write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")

    modele.load_state_dict(torch.load(a.sortie / "atelya-essai.pt", map_location=dev)["modele"])
    final = evaluer(modele, val, dev)
    planche(modele, val, dev, a.sortie / "planche-plan-verite-atelya.png")
    bilan = {"meilleure_note": final, "pas": pas, "minutes": round((time.time() - t0) / 60, 1),
             "plans_appris": a.nb_train, "plans_controle": a.nb_val, "reglages": vars(a) | {"jeu": str(a.jeu), "sortie": str(a.sortie)},
             "machine": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
             "memoire_gpu_max_go": round(torch.cuda.max_memory_allocated() / 1e9, 2) if dev.type == "cuda" else None}
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BILAN " + json.dumps(final, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
