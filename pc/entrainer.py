"""Atelya, essai n°2 : apprendre à colorier un plan pixel par pixel, sans rien inventer dans les marges.

Atelya regarde l'image d'un plan (plan.jpg) et doit retrouver, pour chaque
pixel, ce qu'il représente : fond, mur, porte, fenêtre, type de pièce...
La « bonne réponse » est le masque sémantique dessiné par le générateur
(masque_semantique.png, 16 classes). Le réseau est un petit U-Net écrit ici
de zéro, sans poids appris par d'autres (aucune question de licence).

Ce qui change par rapport à l'essai n°1 :
- Atelya voit plus loin : un « bloc de contexte » au fond du réseau (convolutions
  espacées) lui fait voir environ 1 000 px autour de chaque point au lieu de ~200 ;
  un texte de la marge n'est plus confondu avec le nom d'une pièce, car Atelya voit
  qu'il n'y a pas de murs autour.
- Morceaux plus grands (512 px) et tirés aussi à cheval sur les bords du plan
  (complétés de blanc), pour que les marges et les bords soient autant vus que le centre.
- Tous les dessins : l'essai 1 ne lisait que les plans abîmés (plan.jpg) et sautait les
  dessins propres (plan.png), soit plus de la moitié du jeu. La version « sans meubles »
  d'un plan meublé sert aussi d'exemple d'apprentissage.
- Tout le jeu d'apprentissage (8 219 plans) : les plans sont gardés en mémoire en PNG
  compressé (~1 Go au lieu de ~8 Go) et décompressés à la volée par 4 fils de calcul.
  Ils sont lus une seule fois puis rangés dans un fichier « cache » pour les fois suivantes.
- Nouvelle note : « taches dans les marges » = pixels colorié hors du logement.
- Pause automatique si la carte graphique dépasse --temp-max °C.

Utilisation (dans D:\\Modélisation immobilière\\atelya) :
    uv run python entrainer.py --jeu donnees/jeu-10000 --sortie resultats-essai-2 --minutes 120
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pickle
import queue
import random
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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


def dessins(jeu: Path, ident: str, sans_mobilier: bool) -> list[Path]:
    """Les dessins d'un plan, niveau par niveau : plan.png (dessin propre) ou plan.jpg (plan abîmé).
    L'essai 1 ne prenait que plan.jpg et ratait ainsi plus de la moitié des plans.
    Avec `sans_mobilier`, la version sans meubles compte comme un dessin de plus (même vérité)."""
    sortie = []
    for niv in sorted((jeu / "exemples" / ident).glob("niveau_*")):
        noms = ["plan"] + (["plan_sans_mobilier"] if sans_mobilier else [])
        for nom in noms:
            sortie += [f for f in (niv / f"{nom}.png", niv / f"{nom}.jpg") if f.exists()][:1]
    return sortie


def charger(fichier: Path, cote: int) -> tuple[np.ndarray, np.ndarray]:
    """Image (gris, uint8) et masque (uint8) réduits pour que le grand côté fasse `cote` px."""
    img = Image.open(fichier).convert("L")
    msq = Image.open(fichier.parent / "masque_semantique.png")
    if msq.mode not in ("L", "P"):
        msq = msq.convert("L")
    r = cote / max(img.size)
    taille = (max(1, round(img.width * r)), max(1, round(img.height * r)))
    img = img.resize(taille, Image.BILINEAR)
    msq = msq.resize(taille, Image.NEAREST)
    m = np.array(msq, dtype=np.uint8)
    m[m >= NB_CLASSES] = 0
    return np.array(img, dtype=np.uint8), m


def en_png(a: np.ndarray) -> bytes:
    f = io.BytesIO()
    Image.fromarray(a).save(f, format="PNG", compress_level=1)
    return f.getvalue()


def de_png(b: bytes) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(b)), dtype=np.uint8)


def _lire_un(args) -> list[tuple[bytes, bytes]]:
    jeu, ident, cote, sans_mobilier = args
    return [tuple(en_png(a) for a in charger(f, cote)) for f in dessins(Path(jeu), ident, sans_mobilier)]


def charger_liste(jeu: Path, ids: list[str], cote: int, nom: str, processus: int,
                  sans_mobilier: bool = False) -> list[tuple[bytes, bytes]]:
    """Plans réduits, gardés en PNG compressé. Lus une fois, puis repris du fichier cache."""
    cache = jeu / f"cache-atelya-{cote}px" / f"{nom}-{len(ids)}{'-sm' if sans_mobilier else ''}.pkl"
    if cache.exists():
        print(f"  {nom} : repris du cache {cache.name}", flush=True)
        return pickle.loads(cache.read_bytes())
    paires, t0 = [], time.time()
    with ProcessPoolExecutor(processus) as ex:
        for k, liste in enumerate(ex.map(_lire_un, [(str(jeu), i, cote, sans_mobilier) for i in ids], chunksize=16), 1):
            paires.extend(liste)
            if k % 500 == 0 or k == len(ids):
                print(f"  {nom} : {k}/{len(ids)} plans lus ({time.time() - t0:.0f} s)", flush=True)
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(pickle.dumps(paires, protocol=pickle.HIGHEST_PROTOCOL))
    return paires


def morceau(img: np.ndarray, msq: np.ndarray, taille: int, debord: float):
    """Découpe un carré au hasard, qui peut déborder du plan (complété de blanc), tourné/retourné au hasard.

    Avec `debord` = 0.5, le carré peut dépasser d'une demi-taille de chaque côté : les bords
    et les marges du plan sont alors tirés aussi souvent que le centre.
    """
    h, w = img.shape
    d = int(taille * debord)
    H, W = max(h + 2 * d, taille), max(w + 2 * d, taille)
    i2 = np.full((H, W), 255, np.uint8); m2 = np.zeros((H, W), np.uint8)
    i2[d:d + h, d:d + w] = img; m2[d:d + h, d:d + w] = msq
    y = random.randint(0, H - taille); x = random.randint(0, W - taille)
    img, msq = i2[y:y + taille, x:x + taille], m2[y:y + taille, x:x + taille]
    k = random.randint(0, 3)
    img, msq = np.rot90(img, k), np.rot90(msq, k)
    if random.random() < 0.5:
        img, msq = img[:, ::-1], msq[:, ::-1]
    return np.ascontiguousarray(img), np.ascontiguousarray(msq)


class Distributeur:
    """Prépare les lots à l'avance, avec plusieurs fils, pendant que la carte graphique calcule."""

    def __init__(self, paires, taille: int, n: int, debord: float, fils: int = 4, avance: int = 6):
        self.paires, self.taille, self.n, self.debord = paires, taille, n, debord
        self.pool = ThreadPoolExecutor(fils)
        self.file: queue.Queue = queue.Queue(avance)
        threading.Thread(target=self._remplir, daemon=True).start()

    def _un(self, _):
        a, b = random.choice(self.paires)
        return morceau(de_png(a), de_png(b), self.taille, self.debord)

    def _remplir(self):
        while True:
            choix = list(self.pool.map(self._un, range(self.n)))
            x = torch.from_numpy(np.stack([c[0] for c in choix]))[:, None].float() / 255.0
            y = torch.from_numpy(np.stack([c[1] for c in choix])).long()
            self.file.put((x.pin_memory() if torch.cuda.is_available() else x, y))

    def lot(self):
        return self.file.get()


# ---------- le réseau (U-Net + bloc de contexte) ----------

class Bloc(nn.Sequential):
    def __init__(self, a: int, b: int):
        super().__init__(nn.Conv2d(a, b, 3, padding=1, bias=False), nn.BatchNorm2d(b), nn.ReLU(inplace=True),
                         nn.Conv2d(b, b, 3, padding=1, bias=False), nn.BatchNorm2d(b), nn.ReLU(inplace=True))


class Contexte(nn.Module):
    """Au fond du réseau (image 16 fois plus petite), des convolutions espacées de 2, 4, 8 puis 16 cases :
    chaque point « voit » presque tout le plan. Le résultat s'ajoute à l'entrée (rien n'est perdu)."""

    def __init__(self, c: int):
        super().__init__()
        self.couches = nn.ModuleList(nn.Sequential(nn.Conv2d(c, c, 3, padding=d, dilation=d, bias=False),
                                                   nn.BatchNorm2d(c), nn.ReLU(inplace=True)) for d in (2, 4, 8, 16))

    def forward(self, x):
        for c in self.couches:
            x = x + c(x)
        return x


class UNet(nn.Module):
    def __init__(self, base: int = 32, classes: int = NB_CLASSES, contexte: bool = True):
        super().__init__()
        c = [base, base * 2, base * 4, base * 8, base * 16]
        self.desc = nn.ModuleList([Bloc(1, c[0])] + [Bloc(c[i], c[i + 1]) for i in range(4)])
        self.contexte = Contexte(c[4]) if contexte else nn.Identity()
        self.mont = nn.ModuleList([nn.ConvTranspose2d(c[i + 1], c[i], 2, stride=2) for i in reversed(range(4))])
        self.fus = nn.ModuleList([Bloc(c[i] * 2, c[i]) for i in reversed(range(4))])
        self.tete = nn.Conv2d(c[0], classes, 1)

    def forward(self, x):
        gardes = []
        for i, b in enumerate(self.desc):
            x = b(x if i == 0 else F.max_pool2d(x, 2))
            gardes.append(x)
        gardes.pop()
        x = self.contexte(x)
        for m, f in zip(self.mont, self.fus):
            x = f(torch.cat([m(x), gardes.pop()], 1))
        return self.tete(x)


# ---------- évaluation ----------

@torch.no_grad()
def predire(modele, img: np.ndarray, dev) -> np.ndarray:
    """Plan entier d'un coup (complété de blanc jusqu'à un multiple de 16)."""
    h, w = img.shape
    H, W = math.ceil(h / 16) * 16, math.ceil(w / 16) * 16
    x = np.full((H, W), 255, np.uint8); x[:h, :w] = img
    t = torch.from_numpy(x)[None, None].float().to(dev) / 255.0
    with torch.autocast(dev.type, enabled=dev.type == "cuda"):
        s = modele(t)
    return s.argmax(1)[0, :h, :w].cpu().numpy().astype(np.uint8)


def hors_logement(msq: np.ndarray, marge: int = 6) -> np.ndarray:
    """Vrai pour les pixels loin du logement (hors de son cadre élargi de `marge` px) : la marge du dessin."""
    dehors = np.ones(msq.shape, bool)
    ys, xs = np.nonzero(msq)
    if len(ys):
        dehors[max(ys.min() - marge, 0):ys.max() + marge + 1, max(xs.min() - marge, 0):xs.max() + marge + 1] = False
    return dehors


def evaluer(modele, paires, dev) -> dict:
    modele.eval()
    inter = np.zeros(NB_CLASSES); union = np.zeros(NB_CLASSES); vrais = np.zeros(NB_CLASSES)
    justes = total = taches = marge_tot = plans_taches = 0
    for a, b in paires:
        img, msq = de_png(a), de_png(b)
        p = predire(modele, img, dev)
        justes += int((p == msq).sum()); total += msq.size
        for c in range(NB_CLASSES):
            u, v = p == c, msq == c
            inter[c] += (u & v).sum(); union[c] += (u | v).sum(); vrais[c] += v.sum()
        dehors = hors_logement(msq)
        t = int(((p != 0) & dehors).sum())
        taches += t; marge_tot += int(dehors.sum()); plans_taches += t >= 50
    modele.train()
    # IoU = part commune entre la réponse d'Atelya et la vérité (100 % = parfait), pour les classes présentes.
    iou = {NOMS[c]: (round(float(inter[c] / union[c]) * 100, 1) if vrais[c] else None) for c in range(NB_CLASSES)}
    vals = [v for v in iou.values() if v is not None]
    return {"pixels_justes_pct": round(100 * justes / max(total, 1), 1),
            "iou_moyen_pct": round(sum(vals) / max(len(vals), 1), 1), "iou_par_classe_pct": iou,
            # Taches inventées dans les marges : part des pixels de marge coloriés, et plans touchés (≥ 50 px).
            "taches_marges_pct": round(100 * taches / max(marge_tot, 1), 2),
            "plans_avec_taches_pct": round(100 * plans_taches / max(len(paires), 1), 1)}


def planche(modele, paires, dev, chemin: Path, n: int = 6):
    lignes = []
    for a, b in paires[:n]:
        img, msq = de_png(a), de_png(b)
        p = predire(modele, img, dev)
        lignes.append(np.concatenate([np.stack([img] * 3, -1), COULEURS[msq], COULEURS[p]], 1))
    w = max(l.shape[1] for l in lignes)
    lignes = [np.pad(l, ((0, 8), (0, w - l.shape[1]), (0, 0)), constant_values=255) for l in lignes]
    Image.fromarray(np.concatenate(lignes, 0)).save(chemin)


def temperature_gpu() -> int | None:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return None


# ---------- programme principal ----------

def main():
    ap = argparse.ArgumentParser(description="Entraîner Atelya (essai 2)")
    ap.add_argument("--jeu", type=Path, required=True)
    ap.add_argument("--sortie", type=Path, default=Path("resultats-essai-2"))
    ap.add_argument("--nb-train", type=int, default=0, help="0 = tous les plans d'apprentissage")
    ap.add_argument("--nb-val", type=int, default=150, help="plans de contrôle notés pendant l'apprentissage")
    ap.add_argument("--nb-val-final", type=int, default=0, help="plans de contrôle notés à la fin (0 = tous)")
    ap.add_argument("--cote", type=int, default=768, help="grand côté du plan réduit, en px")
    ap.add_argument("--morceau", type=int, default=512)
    ap.add_argument("--debord", type=float, default=0.5, help="part du morceau qui peut dépasser du plan")
    ap.add_argument("--lot", type=int, default=4)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--sans-contexte", action="store_true", help="réseau de l'essai 1 (pour comparer)")
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--pas-par-tour", type=int, default=500)
    ap.add_argument("--processus", type=int, default=6, help="processus pour la première lecture du jeu")
    ap.add_argument("--temp-max", type=int, default=88, help="pause si la carte graphique dépasse (°C)")
    ap.add_argument("--comparer", type=Path, help="modèle d'un essai précédent (.pt), noté à la fin sur les mêmes plans")
    ap.add_argument("--graine", type=int, default=1)
    a = ap.parse_args()

    random.seed(a.graine); np.random.seed(a.graine); torch.manual_seed(a.graine)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Atelya, essai 2 : calcul sur {torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'processeur'}", flush=True)
    a.sortie.mkdir(parents=True, exist_ok=True)

    parts = lire_partitions(a.jeu)
    print("Jeu : " + ", ".join(f"{k} {len(v)}" for k, v in parts.items()), flush=True)
    ids_train = parts["train"][:a.nb_train] if a.nb_train else parts["train"]
    ids_val = parts["val"][:a.nb_val_final] if a.nb_val_final else parts["val"]
    t_lecture = time.time()
    train = charger_liste(a.jeu, ids_train, a.cote, "apprentissage", a.processus, sans_mobilier=True)
    val_final = charger_liste(a.jeu, ids_val, a.cote, "controle", a.processus)
    val = val_final[:a.nb_val]
    print(f"Lecture : {len(train)} dessins d'apprentissage, {len(val_final)} de contrôle, "
          f"{sum(len(x) + len(y) for x, y in train) / 1e9:.2f} Go en mémoire, {time.time() - t_lecture:.0f} s", flush=True)

    # Poids des classes : les classes rares (portes, WC...) comptent plus, sinon Atelya les ignorerait.
    freq = np.zeros(NB_CLASSES)
    for _, b in random.sample(train, min(1500, len(train))):
        freq += np.bincount(de_png(b).ravel(), minlength=NB_CLASSES)
    poids = torch.tensor(np.clip((freq.sum() / np.maximum(freq, 1) / NB_CLASSES) ** 0.5, 0.2, 10), dtype=torch.float32, device=dev)

    modele = UNet(a.base, contexte=not a.sans_contexte).to(dev)
    print(f"Réseau : {sum(p.numel() for p in modele.parameters()) / 1e6:.1f} millions de réglages", flush=True)
    opt = torch.optim.AdamW(modele.parameters(), lr=1e-3, weight_decay=1e-4)
    echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
    distrib = Distributeur(train, a.morceau, a.lot, a.debord)
    duree, t0, pas, historique, meilleur, pauses = a.minutes * 60, time.time(), 0, [], -1.0, 0.0

    while time.time() - t0 - pauses < duree:
        perte_tour = 0.0
        for _ in range(a.pas_par_tour):
            frac = min((time.time() - t0 - pauses) / duree, 1.0)
            for g in opt.param_groups:
                g["lr"] = 1e-3 * (0.5 * (1 + math.cos(math.pi * frac)) * 0.95 + 0.05)
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
        print(f"[{note['minutes']:5.1f} min] pas {pas:6d}  perte {note['perte']:.3f}  pixels justes {note['pixels_justes_pct']}%  "
              f"IoU moyen {note['iou_moyen_pct']}%  murs {iou['mur']}%  portes {iou['porte']}%  fenêtres {iou['fenetre']}%  "
              f"taches marges {note['plans_avec_taches_pct']}% des plans  GPU {temp} °C", flush=True)
        if note["iou_moyen_pct"] > meilleur:
            meilleur = note["iou_moyen_pct"]
            torch.save({"modele": modele.state_dict(), "base": a.base, "contexte": not a.sans_contexte,
                        "classes": NOMS, "cote": a.cote, "note": note}, a.sortie / "atelya-essai-2.pt")
        (a.sortie / "historique.json").write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
        while temp is not None and temp > a.temp_max:
            print(f"  carte graphique à {temp} °C : pause d'une minute pour la laisser refroidir", flush=True)
            time.sleep(60); pauses += 60; temp = temperature_gpu()

    modele.load_state_dict(torch.load(a.sortie / "atelya-essai-2.pt", map_location=dev)["modele"])
    final = evaluer(modele, val_final, dev)
    planche(modele, val_final, dev, a.sortie / "planche-plan-verite-atelya.png")
    bilan = {"meilleure_note": final, "pas": pas, "minutes": round((time.time() - t0) / 60, 1),
             "minutes_de_pause_chaleur": round(pauses / 60, 1),
             "plans_appris": len(ids_train), "dessins_appris": len(train), "plans_controle": len(ids_val),
             "reglages": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
             "machine": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
             "memoire_gpu_max_go": round(torch.cuda.max_memory_allocated() / 1e9, 2) if dev.type == "cuda" else None}
    if a.comparer and a.comparer.exists():
        # L'essai 1 n'avait été noté que sur des plans abîmés : on le renote ici sur les mêmes plans que l'essai 2.
        ancien = torch.load(a.comparer, map_location=dev)
        m1 = UNet(ancien.get("base", 32), contexte=ancien.get("contexte", False)).to(dev)
        m1.load_state_dict(ancien["modele"])
        bilan["essai_precedent_meme_controle"] = evaluer(m1, val_final, dev)
        print("ESSAI PRECEDENT " + json.dumps(bilan["essai_precedent_meme_controle"], ensure_ascii=False), flush=True)
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BILAN " + json.dumps(final, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
