"""Atelya, essai n°6 : apprendre les styles des vrais plans, et qu'« un mur reste un mur ».

Étape 6-19. Repart d'Atelya essai 5 et lui montre, en plus de tout ce qu'il connaît (anciens plans
et photos), les plans « styles du monde » du générateur 0.1.4 (--styles-monde) : sols dessinés,
murs en trait fin, double trait ou gris très clair, lettres A-D, captures d'écran, styles absurdes.
Deux nouveautés d'apprentissage :
- --part-monde : une part des morceaux vient des plans « styles du monde » ;
- --part-coherence : sur une part des lots, le même morceau est montré une 2e fois « déguisé »
  (inversé clair/foncé, réduit à ses contours, contraste écrasé, gris remappés au hasard). Atelya
  doit donner la même réponse aux deux (la bonne) : il apprend la forme, pas l'apparence.
Le modèle gardé : meilleure note « monde » sans reculer de plus de --recul-max points ni sur les
anciens plans, ni sur les photos.

--- Texte de l'essai 4, gardé pour mémoire :
Atelya, essai n°4 : apprendre à lire les photos de plans prises au téléphone.

Repart d'Atelya essai 2 (même réseau, mêmes 16 classes) et lui montre, en plus des plans
qu'il connaît déjà, des photos « vraie caméra » fabriquées par le générateur
(--familles photo --vraie-camera) : feuille penchée avec une vraie perspective,
format 4:3 ou 16:9, table autour de la feuille.
- Mélange : une part --part-photos des morceaux vient des photos, le reste des anciens plans
  (pour ne rien oublier de ce qu'il sait déjà).
- Reprise des réglages appris par l'essai 2 (--reprendre), avec un pas d'apprentissage plus petit.
- Note à chaque tour sur deux contrôles : anciens plans ET photos. Le modèle gardé est celui qui
  a la meilleure note photos SANS reculer de plus de --recul-max points sur les anciens plans.

Les photos de test de l'étape 6-14 (graines 20001 à 20330) ne doivent PAS être dans --jeu-photos.

Utilise les fonctions d'entrainer.py (essai 2), à poser dans le même dossier.

Utilisation (dans D:\\Modélisation immobilière\\atelya) :
    uv run python entrainer_essai4.py --jeu donnees/jeu-10000 --jeu-photos donnees/photos-app-cotes donnees/photos-app-sans-cotes
        --reprendre resultats-essai-2/atelya-essai-2.pt --sortie resultats-essai-4 --minutes 120
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

GRAINES_TEST_PHOTOS = range(20001, 20331)


class DistributeurMelange(e2.Distributeur):
    """Une part `part_monde` des morceaux vient des styles du monde, une part `part` des photos, le reste des anciens plans."""

    def __init__(self, paires, photos, monde, taille, n, debord, part: float, part_monde: float):
        self.photos, self.part, self.monde, self.part_monde = photos, part, monde, part_monde
        super().__init__(paires, taille, n, debord)

    def _un(self, _):
        t = random.random()
        if t < self.part_monde:
            a, b = random.choice(self.monde)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        if t < self.part_monde + self.part:
            a, b = random.choice(self.photos)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        return super()._un(_)


def deguiser(x: torch.Tensor) -> torch.Tensor:
    """Le même morceau, autrement dessiné (gris de 0 à 1, forme (lot, 1, h, w)). Chaque morceau tire un déguisement."""
    sortie = []
    for i in range(x.shape[0]):
        v = x[i:i + 1]
        t = random.random()
        if t < 0.25:  # clair sur foncé
            v = 1 - v
        elif t < 0.5:  # seulement les contours : un mur plein devient un double trait
            k = random.choice((3, 5))
            dilate = F.max_pool2d(1 - v, k, 1, k // 2)
            erode = -F.max_pool2d(-(1 - v), k, 1, k // 2)
            v = 1 - (dilate - erode).clamp(0, 1)
        elif t < 0.75:  # gris remappés au hasard (table de 8 paliers, pas forcément croissante)
            paliers = torch.rand(9, device=v.device)
            paliers[-1] = max(float(paliers[-1]), 0.85)  # le papier reste plutôt clair
            pos = v * 8
            i0 = pos.floor().clamp(0, 7).long()
            f = pos - i0
            v = paliers[i0] * (1 - f) + paliers[i0 + 1] * f
        else:  # contraste écrasé, papier gris, un peu de bruit
            a = random.uniform(0.25, 0.6)
            v = (1 - a) * random.uniform(0.3, 1.0) + a * v + torch.randn_like(v) * 0.03
        sortie.append(v.clamp(0, 1))
    return torch.cat(sortie)


def resume(n: dict) -> str:
    iou = n["iou_par_classe_pct"]
    return (f"IoU moyen {n['iou_moyen_pct']}%  murs {iou['mur']}%  portes {iou['porte']}%  "
            f"fenêtres {iou['fenetre']}%  taches marges {n['plans_avec_taches_pct']}%")


def main():
    ap = argparse.ArgumentParser(description="Entraîner Atelya (essai 6 : styles du monde, un mur reste un mur)")
    ap.add_argument("--jeu", type=Path, required=True, help="jeu habituel (jeu-10000)")
    ap.add_argument("--jeu-photos", type=Path, nargs="+", required=True,
                    help="jeu(x) de photos vraie caméra fabriqués pour l'apprentissage")
    ap.add_argument("--jeu-monde", type=Path, nargs="+", required=True, help="jeu(x) --styles-monde (générateur 0.1.4)")
    ap.add_argument("--reprendre", type=Path, required=True, help="modèle de départ (essai 5, .pt)")
    ap.add_argument("--sortie", type=Path, default=Path("resultats-essai-6"))
    ap.add_argument("--part-photos", type=float, default=0.25, help="part des morceaux tirés dans les photos")
    ap.add_argument("--part-monde", type=float, default=0.4, help="part des morceaux tirés dans les styles du monde")
    ap.add_argument("--part-coherence", type=float, default=0.5, help="part des lots montrés aussi « déguisés »")
    ap.add_argument("--poids-coherence", type=float, default=1.0, help="poids de l'accord entre les deux réponses")
    ap.add_argument("--poids-maitre", type=float, default=0.0,
                    help="poids du rappel de l'essai 5 (maître figé), sur les pixels où il a juste (essai 6b : 1.0)")
    ap.add_argument("--nb-val", type=int, default=150, help="plans de contrôle notés à chaque tour (anciens et photos)")
    ap.add_argument("--recul-max", type=float, default=0.5, help="recul permis sur les anciens plans (points d'IoU)")
    ap.add_argument("--cote", type=int, default=768)
    ap.add_argument("--morceau", type=int, default=512)
    ap.add_argument("--debord", type=float, default=0.5)
    ap.add_argument("--lot", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-4, help="pas d'apprentissage de départ (essai 2 : 1e-3)")
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--pas-par-tour", type=int, default=500)
    ap.add_argument("--processus", type=int, default=6)
    ap.add_argument("--temp-max", type=int, default=88)
    ap.add_argument("--graine", type=int, default=6)
    a = ap.parse_args()

    random.seed(a.graine); np.random.seed(a.graine); torch.manual_seed(a.graine)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Atelya, essai 6 : calcul sur {torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'processeur'}", flush=True)
    a.sortie.mkdir(parents=True, exist_ok=True)

    parts = lire_partitions(a.jeu)
    train = charger_liste(a.jeu, parts["train"], a.cote, "apprentissage", a.processus, sans_mobilier=True)
    val_final = charger_liste(a.jeu, parts["val"], a.cote, "controle", a.processus)
    val = val_final[:a.nb_val]

    # Photos : tout sert à apprendre sauf la partie « validation », qui sert de contrôle photos.
    photos, val_photos_final, ids_p = [], [], []
    for jp in a.jeu_photos:
        pp = lire_partitions(jp)
        ids = sorted(set(pp.get("train", []) + pp.get("test", [])))
        ids_v = pp.get("val", [])
        interdits = [i for i in ids + ids_v if i.isdigit() and int(i) in GRAINES_TEST_PHOTOS]
        if interdits:
            raise SystemExit(f"ARRÊT : {len(interdits)} photos de test (graines 20001-20330) dans {jp}")
        photos += charger_liste(jp, ids, a.cote, "photos-apprentissage", a.processus, sans_mobilier=True)
        val_photos_final += charger_liste(jp, ids_v, a.cote, "photos-controle", a.processus)
        ids_p += ids
    random.Random(0).shuffle(val_photos_final)  # contrôle à chaque tour = un peu de chaque jeu
    val_photos = val_photos_final[:a.nb_val]
    monde, val_monde_final = [], []
    for jm in a.jeu_monde:
        pm = lire_partitions(jm)
        monde += charger_liste(jm, sorted(set(pm.get("train", []) + pm.get("test", []))), a.cote, "monde-apprentissage",
                               a.processus, sans_mobilier=True)
        val_monde_final += charger_liste(jm, pm.get("val", []), a.cote, "monde-controle", a.processus)
    random.Random(1).shuffle(val_monde_final)
    val_monde = val_monde_final[:a.nb_val]
    print(f"Styles du monde : {len(monde)} dessins, contrôle {len(val_monde_final)}", flush=True)
    print(f"Lecture : {len(train)} dessins anciens, {len(photos)} photos ; contrôle {len(val_final)} anciens, "
          f"{len(val_photos_final)} photos", flush=True)

    # Mêmes poids que l'essai 2 (calculés sur les anciens plans).
    freq = np.zeros(NB_CLASSES)
    for _, b in random.sample(train, min(1500, len(train))):
        freq += np.bincount(de_png(b).ravel(), minlength=NB_CLASSES)
    poids = torch.tensor(np.clip((freq.sum() / np.maximum(freq, 1) / NB_CLASSES) ** 0.5, 0.2, 10),
                         dtype=torch.float32, device=dev)

    ancien = torch.load(a.reprendre, map_location=dev)
    base, contexte = ancien.get("base", 32), ancien.get("contexte", True)
    modele = UNet(base, contexte=contexte).to(dev)
    modele.load_state_dict(ancien["modele"])
    maitre = None
    if a.poids_maitre > 0:
        maitre = UNet(base, contexte=contexte).to(dev)
        maitre.load_state_dict(ancien["modele"])
        maitre.eval()
        for prm in maitre.parameters():
            prm.requires_grad_(False)
    dep_a, dep_p, dep_m = evaluer(modele, val, dev), evaluer(modele, val_photos, dev), evaluer(modele, val_monde, dev)
    print(f"Départ (essai 5) anciens : {resume(dep_a)}", flush=True)
    print(f"Départ (essai 5) photos  : {resume(dep_p)}", flush=True)
    print(f"Départ (essai 5) monde   : {resume(dep_m)}", flush=True)
    seuil = dep_a["iou_moyen_pct"] - a.recul_max
    seuil_p = dep_p["iou_moyen_pct"] - a.recul_max

    opt = torch.optim.AdamW(modele.parameters(), lr=a.lr, weight_decay=1e-4)
    echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
    distrib = DistributeurMelange(train, photos, monde, a.morceau, a.lot, a.debord, a.part_photos, a.part_monde)
    duree, t0, pas, pauses = a.minutes * 60, time.time(), 0, 0.0
    historique = [{"pas": 0, "anciens": dep_a, "photos": dep_p, "monde": dep_m}]
    meilleur, garde = -1.0, False

    while time.time() - t0 - pauses < duree:
        perte_tour = 0.0
        for _ in range(a.pas_par_tour):
            frac = min((time.time() - t0 - pauses) / duree, 1.0)
            for g in opt.param_groups:
                g["lr"] = a.lr * (0.5 * (1 + math.cos(math.pi * frac)) * 0.95 + 0.05)
            x, y = distrib.lot()
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            deux = random.random() < a.part_coherence
            if deux:
                x = torch.cat([x, deguiser(x)])
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                sorties = modele(x)
            sorties = sorties.float()
            if deux:
                n = y.shape[0]
                s1, s2 = sorties[:n], sorties[n:]
                perte = (F.cross_entropy(s1, y, weight=poids) + F.cross_entropy(s2, y, weight=poids)) / 2
                # Accord : la réponse au morceau déguisé doit ressembler à celle du morceau normal.
                accord = F.kl_div(F.log_softmax(s2, 1), F.softmax(s1, 1).detach(), reduction="batchmean") / (s1.shape[2] * s1.shape[3])
                perte = perte + a.poids_coherence * accord
            else:
                perte = F.cross_entropy(sorties, y, weight=poids)
            if maitre is not None:
                n = y.shape[0]
                with torch.no_grad(), torch.autocast(dev.type, enabled=dev.type == "cuda"):
                    sm = maitre(x[:n]).float()
                juste = (sm.argmax(1) == y).float()
                kl = (F.softmax(sm, 1) * (F.log_softmax(sm, 1) - F.log_softmax(sorties[:n], 1))).sum(1)
                perte = perte + a.poids_maitre * (kl * juste).sum() / juste.sum().clamp(min=1.0)
            opt.zero_grad(set_to_none=True)
            echelle.scale(perte).backward(); echelle.step(opt); echelle.update()
            perte_tour += perte.item(); pas += 1
        na, np_, nm = evaluer(modele, val, dev), evaluer(modele, val_photos, dev), evaluer(modele, val_monde, dev)
        temp = temperature_gpu()
        minutes = round((time.time() - t0 - pauses) / 60, 1)
        historique.append({"pas": pas, "minutes": minutes, "perte": round(perte_tour / a.pas_par_tour, 4),
                           "temperature_gpu": temp, "anciens": na, "photos": np_, "monde": nm})
        print(f"[{minutes:5.1f} min] pas {pas:6d}  perte {perte_tour / a.pas_par_tour:.3f}  GPU {temp} °C", flush=True)
        print(f"    anciens : {resume(na)}", flush=True)
        print(f"    photos  : {resume(np_)}", flush=True)
        print(f"    monde   : {resume(nm)}", flush=True)
        # Le modèle gardé : meilleure note monde, sans recul de plus de --recul-max sur les anciens plans ni sur les photos.
        ok = na["iou_moyen_pct"] >= seuil and np_["iou_moyen_pct"] >= seuil_p
        if ok and nm["iou_moyen_pct"] > meilleur:
            meilleur, garde = nm["iou_moyen_pct"], True
            torch.save({"modele": modele.state_dict(), "base": base, "contexte": contexte, "classes": NOMS,
                        "cote": a.cote, "note": {"anciens": na, "photos": np_, "monde": nm}, "pas": pas},
                       a.sortie / "atelya-essai-6.pt")
            print("    -> gardé", flush=True)
        elif not ok:
            print(f"    (recul : anciens {na['iou_moyen_pct']} (min {seuil:.1f}), photos {np_['iou_moyen_pct']} "
                  f"(min {seuil_p:.1f}) ; pas gardé)", flush=True)
        torch.save({"modele": modele.state_dict(), "base": base, "contexte": contexte, "classes": NOMS,
                    "cote": a.cote, "note": {"anciens": na, "photos": np_, "monde": nm}, "pas": pas},
                   a.sortie / "atelya-essai-6-dernier.pt")
        (a.sortie / "historique.json").write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
        while temp is not None and temp > a.temp_max:
            print(f"  carte graphique à {temp} °C : pause d'une minute pour la laisser refroidir", flush=True)
            time.sleep(60); pauses += 60; temp = temperature_gpu()

    bilan = {"pas": pas, "minutes": round((time.time() - t0) / 60, 1), "minutes_de_pause_chaleur": round(pauses / 60, 1),
             "dessins_anciens": len(train), "photos_apprises": len(photos), "plans_photos": len(ids_p),
             "dessins_monde": len(monde),
             "reglages": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
             "machine": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
             "memoire_gpu_max_go": round(torch.cuda.max_memory_allocated() / 1e9, 2) if dev.type == "cuda" else None}
    if not garde:
        print("AUCUN MODÈLE GARDÉ : chaque tour reculait sur les anciens plans ou les photos. On garde l'essai 5.", flush=True)
        bilan["garde"] = False
    else:
        modele.load_state_dict(torch.load(a.sortie / "atelya-essai-6.pt", map_location=dev)["modele"])
        bilan["garde"] = True
        bilan["essai6"] = {"anciens": evaluer(modele, val_final, dev), "photos": evaluer(modele, val_photos_final, dev),
                           "monde": evaluer(modele, val_monde_final, dev)}
        planche(modele, val_monde_final, dev, a.sortie / "planche-monde-verite-atelya.png")
    m2 = UNet(base, contexte=contexte).to(dev)
    m2.load_state_dict(ancien["modele"])
    bilan["essai5_meme_controle"] = {"anciens": evaluer(m2, val_final, dev), "photos": evaluer(m2, val_photos_final, dev),
                                     "monde": evaluer(m2, val_monde_final, dev)}
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for nom in ("essai5_meme_controle", "essai6"):
        if nom in bilan:
            for k in ("anciens", "photos", "monde"):
                print(f"BILAN {nom} {k} : {resume(bilan[nom][k])}", flush=True)


if __name__ == "__main__":
    main()
