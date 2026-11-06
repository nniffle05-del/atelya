r"""Atelya, essai n°8 : l'essai 5 + l'œil DINOv2, entraîné AUSSI sur de VRAIS plans.

POURQUOI. Jusqu'ici Atelya n'a vu que des plans fabriqués par notre générateur. Sur les vrais plans français
(note ~55/100), chaque style inconnu (sols hachurés, dessin à la main, murs gris clair, photo floue) est colorié
n'importe comment, et les chantiers « échelle », « traducteur » ou « 3D » corrigent l'aval, pas le coloriage.
L'essai 8 lui montre enfin du vrai : les vérités des 78 plans d'entraînement du lot 2 (jamais les 40 plans
d'examen), multipliées en variantes par outils/atelya/preparer_jeu_vrais.py, mélangées aux plans fabriqués
(anciens + photos + styles du monde + murs en biais, et plus tard le lot 2 du générateur) pour ne rien oublier.

COMMENT. Même recette que l'essai 7b (entrainer_essai7b.py, étape A3) : U-Net de l'essai 5 + œil DINOv2 ViT-S/14
figé (oeil.py), maître = essai 5 figé qui rappelle ses bonnes réponses, déguisements, retour en arrière si la
perte dérive, échauffement du pas, plafond des corrections (--clip), lots qui débordent sautés. En plus :
- --jeu-vrais : jeu(x) au format de preparer_jeu_vrais.py ; partition « train » = apprentissage, partition
  « validation » = contrôle « vrais » (8 plans jamais vus, image originale seule) ;
- --part-vrais : part des morceaux tirés dans les vrais plans (0,3 par défaut). Les parts se lisent EN CASCADE :
  d'abord vrais, puis biais sur le reste, puis monde et photos sur le reste du reste, puis les anciens plans ;
- une note « vrais » à chaque tour (IoU moyen sur le contrôle vrais), écrite dans historique.json ;
- RÈGLE DU MODÈLE GARDÉ : la meilleure note « vrais » SANS recul de plus de --recul-max (0,5 point d'IoU) sur
  les anciens plans, sur les photos ET sur les murs en biais, par rapport au modèle de DÉPART noté sur les mêmes
  contrôles ;
- --reprendre = l'essai 5 (sans œil : la fusion de l'œil part de zéro, Atelya répond d'abord exactement comme
  l'essai 5) ou le 7b (avec œil : la fusion déjà apprise est reprise aussi) ; --maitre choisit le maître (par
  défaut le modèle de départ ; donner l'essai 5 pour garder le même maître d'un essai à l'autre) ;
- --nb-val-final : nombre de plans de chaque contrôle complet noté à la fin (0 = tout) ;
- --minutes reste la SEULE durée : un tour en cours s'arrête quand le temps est écoulé.
Sorties dans --sortie : atelya-essai-8.pt (gardé selon la règle), atelya-essai-8-dernier.pt (fin de chaque tour),
historique.json, bilan.json, planche-vrais-verite-atelya.png.

USAGE (dans D:\Modélisation immobilière\atelya, à côté d'entrainer.py et oeil.py) :
    .venv\Scripts\python.exe entrainer_essai8.py --jeu donnees\jeu-10000
        --jeu-photos donnees\photos-app-cotes donnees\photos-app-sans-cotes donnees\photos-reel-cotes donnees\photos-reel-sans-cotes
        --jeu-monde donnees\monde-6-19 --jeu-biais donnees\biais-a3 donnees\biais-monde-a3 donnees\biais-photos-a3 --part-biais 0.2
        --jeu-vrais donnees\vrais-2026-11-05 --part-vrais 0.3
        --reprendre resultats-essai-5\atelya-essai-4.pt --maitre resultats-essai-5\atelya-essai-4.pt --oeil vits14
        --processus 1 --figer-bn --poids-maitre 3.0 --poids-escalier 3.0 --part-monde 0.2 --part-photos 0.45
        --lr 5e-5 --lr-oeil 1e-4 --minutes 25 --sortie resultats-essai-8-T0
(--processus 1 obligatoire sur le PC pour charger un nouveau jeu : WinError 1455 sinon ; les jeux déjà lus sont repris
de leur cache-atelya-768px.) Voir pc/essai8/petits-essais-8.ps1 pour les phases eclair / T0 / T1 / T2 / long.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import entrainer as e2
from entrainer import NB_CLASSES, NOMS, charger_liste, de_png, evaluer, lire_partitions, planche, temperature_gpu
from oeil import charger_modele, construire, etat

GRAINES_TEST_PHOTOS = range(20001, 20331)
CONTROLES = ("anciens", "photos", "monde", "biais", "vrais")
PROTEGES = ("anciens", "photos", "biais")  # aucun recul de plus de --recul-max sur ces trois contrôles


class DistributeurMelange(e2.Distributeur):
    """Parts en cascade : `part_vrais` des morceaux dans les vrais plans ; sur le reste, `part_biais` dans les murs en biais ;
    sur le reste, `part_monde` dans les styles du monde et `part` dans les photos ; le reste dans les anciens plans."""

    def __init__(self, paires, photos, monde, taille, n, debord, part: float, part_monde: float,
                 biais=None, part_biais: float = 0.0, vrais=None, part_vrais: float = 0.0):
        self.photos, self.part, self.monde, self.part_monde = photos, part, monde, part_monde
        self.biais, self.part_biais = biais or [], part_biais if biais else 0.0
        self.vrais, self.part_vrais = vrais or [], part_vrais if vrais else 0.0
        super().__init__(paires, taille, n, debord)

    def _un(self, _):
        t = random.random()
        if t < self.part_vrais:
            a, b = random.choice(self.vrais)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        t = (t - self.part_vrais) / max(1e-9, 1 - self.part_vrais) if self.part_vrais else t
        if t < self.part_biais:
            a, b = random.choice(self.biais)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        t = (t - self.part_biais) / max(1e-9, 1 - self.part_biais) if self.part_biais else t
        if t < self.part_monde:
            a, b = random.choice(self.monde)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        if t < self.part_monde + self.part:
            a, b = random.choice(self.photos)
            return e2.morceau(de_png(a), de_png(b), self.taille, self.debord)
        return super()._un(_)


def parts_effectives(part_vrais: float, part_biais: float, part_monde: float, part_photos: float) -> dict:
    """Ce que donne la cascade, en part réelle des morceaux (pour le journal et le bilan)."""
    reste = 1.0
    sortie = {"vrais": round(part_vrais, 3)}
    reste -= part_vrais
    sortie["biais"] = round(reste * part_biais, 3)
    reste *= 1 - part_biais
    sortie["monde"] = round(reste * part_monde, 3)
    sortie["photos"] = round(reste * part_photos, 3)
    sortie["anciens"] = round(max(0.0, reste * (1 - part_monde - part_photos)), 3)
    return sortie


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


def charger_depart(chemin: Path, dev, oeil_voulu: str, degeler: int):
    """Le modèle de départ : essai 5 (U-Net seul : l'œil est ajouté, fusion à zéro) ou 7b (U-Net + œil : fusion reprise)."""
    sauve = torch.load(chemin, map_location=dev)
    base, contexte = sauve.get("base", 32), sauve.get("contexte", True)
    oeil_sauve = sauve.get("oeil") or "aucun"
    if oeil_sauve != "aucun" and oeil_sauve != oeil_voulu:
        raise SystemExit(f"ARRÊT : {chemin} a été appris avec l'œil {oeil_sauve}, mais --oeil {oeil_voulu} est demandé")
    modele = construire(base, contexte, oeil_voulu, degeler).to(dev)
    manque, inattendus = modele.load_state_dict(sauve["modele"], strict=False)
    fusion_reprise = oeil_voulu != "aucun" and not any(k.startswith("fusion.") for k in manque)
    manque = [k for k in manque if not k.startswith(("oeil.", "fusion."))]
    if manque or inattendus:
        raise SystemExit(f"ARRÊT : le modèle de départ ne correspond pas (manque {manque[:3]}, en trop {list(inattendus)[:3]})")
    return modele, sauve, fusion_reprise


def noter(modele, controles: dict, dev) -> dict:
    return {k: evaluer(modele, v, dev) for k, v in controles.items() if v}


def main():
    ap = argparse.ArgumentParser(description="Entraîner Atelya, essai 8 : essai 5 + œil DINOv2 + vrais plans")
    ap.add_argument("--jeu", type=Path, required=True, help="jeu habituel (jeu-10000)")
    ap.add_argument("--jeu-photos", type=Path, nargs="+", required=True, help="jeu(x) de photos vraie caméra")
    ap.add_argument("--jeu-monde", type=Path, nargs="+", required=True, help="jeu(x) --styles-monde (générateur 0.1.4)")
    ap.add_argument("--jeu-biais", type=Path, nargs="*", default=[], help="jeux murs en biais / arrondis (A3-2)")
    ap.add_argument("--jeu-vrais", type=Path, nargs="+", required=True,
                    help="jeu(x) de vrais plans (preparer_jeu_vrais.py : train = apprentissage, validation = contrôle vrais)")
    ap.add_argument("--reprendre", type=Path, required=True, help="modèle de départ : essai 5 (sans œil) ou 7b (avec œil)")
    ap.add_argument("--maitre", type=Path, default=None, help="modèle maître figé (défaut : le modèle de départ)")
    ap.add_argument("--sortie", type=Path, default=Path("resultats-essai-8"))
    ap.add_argument("--oeil", choices=["aucun", "vits14", "vitb14"], default="vits14", help="œil DINOv2 ajouté")
    ap.add_argument("--part-vrais", type=float, default=0.3, help="part des morceaux tirés dans les vrais plans")
    ap.add_argument("--part-biais", type=float, default=0.0, help="part (du reste) tirée dans les jeux biais")
    ap.add_argument("--part-photos", type=float, default=0.25, help="part (du reste) tirée dans les photos")
    ap.add_argument("--part-monde", type=float, default=0.4, help="part (du reste) tirée dans les styles du monde")
    ap.add_argument("--retour-arriere", type=float, default=1.6,
                    help="si la perte d'un tour dépasse ce multiple de la meilleure perte (ou si des lots débordent), "
                         "on revient au dernier bon état et on divise le pas d'apprentissage par 2 (essai 7b)")
    ap.add_argument("--clip", type=float, default=1.0, help="plafond de la norme des corrections (évite les « nan »)")
    ap.add_argument("--pas-chauffe", type=int, default=400, help="échauffement : le pas monte de 0 au maximum sur ces premiers pas")
    ap.add_argument("--lr-oeil", type=float, default=3e-4, help="pas d'apprentissage de la fusion (et des blocs dégelés ÷10)")
    ap.add_argument("--degeler", type=int, default=0, help="nombre de derniers blocs DINOv2 qui apprennent")
    ap.add_argument("--part-coherence", type=float, default=0.5, help="part des lots montrés aussi « déguisés »")
    ap.add_argument("--poids-coherence", type=float, default=1.0, help="poids de l'accord entre les deux réponses")
    ap.add_argument("--poids-escalier", type=float, default=1.0, help="multiplie le poids de la classe escalier")
    ap.add_argument("--figer-bn", action="store_true", help="les moyennes BatchNorm restent celles du départ")
    ap.add_argument("--poids-maitre", type=float, default=0.0, help="poids du rappel du maître figé, sur les pixels où il a juste")
    ap.add_argument("--nb-val", type=int, default=150, help="plans de chaque contrôle notés à chaque tour")
    ap.add_argument("--nb-val-final", type=int, default=0, help="plans de chaque contrôle notés à la fin (0 = tout)")
    ap.add_argument("--recul-max", type=float, default=0.5, help="recul permis (points d'IoU) sur anciens, photos et biais")
    ap.add_argument("--cote", type=int, default=768)
    ap.add_argument("--morceau", type=int, default=512)
    ap.add_argument("--debord", type=float, default=0.5)
    ap.add_argument("--lot", type=int, default=4)
    ap.add_argument("--lr", type=float, default=5e-5, help="pas d'apprentissage de départ (essai 7b : 5e-5)")
    ap.add_argument("--minutes", type=float, default=120, help="la seule durée : l'apprentissage s'arrête au bout de ces minutes")
    ap.add_argument("--pas-par-tour", type=int, default=500)
    ap.add_argument("--processus", type=int, default=1)
    ap.add_argument("--temp-max", type=int, default=88)
    ap.add_argument("--graine", type=int, default=8)
    a = ap.parse_args()
    if a.maitre is None:
        a.maitre = a.reprendre

    random.seed(a.graine); np.random.seed(a.graine); torch.manual_seed(a.graine)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Atelya, essai 8 (œil {a.oeil}, vrais plans) : calcul sur "
          f"{torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'processeur'}", flush=True)
    a.sortie.mkdir(parents=True, exist_ok=True)

    # ---- lecture des jeux (mêmes noms de cache que les essais 7/7b : les jeux déjà lus sont repris tels quels)
    parts = lire_partitions(a.jeu)
    train = charger_liste(a.jeu, parts["train"], a.cote, "apprentissage", a.processus, sans_mobilier=True)
    val_final = charger_liste(a.jeu, parts["val"], a.cote, "controle", a.processus)
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
    random.Random(0).shuffle(val_photos_final)
    monde, val_monde_final = [], []
    for jm in a.jeu_monde:
        pm = lire_partitions(jm)
        monde += charger_liste(jm, sorted(set(pm.get("train", []) + pm.get("test", []))), a.cote, "monde-apprentissage",
                               a.processus, sans_mobilier=True)
        val_monde_final += charger_liste(jm, pm.get("val", []), a.cote, "monde-controle", a.processus)
    random.Random(1).shuffle(val_monde_final)
    biais, val_biais_final = [], []
    for jb in a.jeu_biais:
        pb = lire_partitions(jb)
        biais += charger_liste(jb, sorted(set(pb.get("train", []) + pb.get("test", []))), a.cote, "biais-apprentissage",
                               a.processus, sans_mobilier=True)
        val_biais_final += charger_liste(jb, pb.get("val", []), a.cote, "biais-controle", a.processus)
    random.Random(2).shuffle(val_biais_final)
    # Vrais plans : « train » = les variantes des plans appris ; « validation » = les plans de contrôle, image originale seule.
    vrais, val_vrais_final, plans_vrais = [], [], set()
    for jv in a.jeu_vrais:
        pv = lire_partitions(jv)
        if not pv.get("train"):
            raise SystemExit(f"ARRÊT : {jv} n'a aucun dessin d'apprentissage (partition train vide)")
        vrais += charger_liste(jv, pv["train"], a.cote, "vrais-apprentissage", a.processus)
        val_vrais_final += charger_liste(jv, pv.get("val", []), a.cote, "vrais-controle", a.processus)
        plans_vrais |= {i.split("-v")[0] for i in pv["train"]}
    if not val_vrais_final:
        print("ATTENTION : aucun plan de contrôle « vrais » (partition validation vide) : la règle du modèle gardé "
              "retombe sur la moyenne monde + biais, comme en 7b", flush=True)
    print(f"Lecture : {len(train)} dessins anciens, {len(photos)} photos, {len(monde)} monde, {len(biais)} biais, "
          f"{len(vrais)} vrais ({len(plans_vrais)} plans) ; contrôles {len(val_final)} anciens, {len(val_photos_final)} photos, "
          f"{len(val_monde_final)} monde, {len(val_biais_final)} biais, {len(val_vrais_final)} vrais", flush=True)
    finals = {"anciens": val_final, "photos": val_photos_final, "monde": val_monde_final, "biais": val_biais_final,
              "vrais": val_vrais_final}
    if a.nb_val_final:
        finals = {k: v[:a.nb_val_final] for k, v in finals.items()}
    controles = {k: v[:a.nb_val] for k, v in finals.items()}
    print("Parts effectives des morceaux : " + ", ".join(f"{k} {v:.1%}" for k, v in
                                                          parts_effectives(a.part_vrais if vrais else 0, a.part_biais if biais else 0,
                                                                           a.part_monde, a.part_photos).items()), flush=True)

    # Mêmes poids que l'essai 2 (calculés sur les anciens plans).
    freq = np.zeros(NB_CLASSES)
    for _, b in random.sample(train, min(1500, len(train))):
        freq += np.bincount(de_png(b).ravel(), minlength=NB_CLASSES)
    poids = torch.tensor(np.clip((freq.sum() / np.maximum(freq, 1) / NB_CLASSES) ** 0.5, 0.2, 10),
                         dtype=torch.float32, device=dev)
    poids[NOMS.index("escalier")] *= a.poids_escalier

    # ---- modèle de départ, maître
    modele, ancien, fusion_reprise = charger_depart(a.reprendre, dev, a.oeil, a.degeler)
    base, contexte = ancien.get("base", 32), ancien.get("contexte", True)
    n_app = sum(p.numel() for p in modele.parameters() if p.requires_grad)
    print(f"Départ {a.reprendre} : œil {a.oeil}, fusion {'reprise du modèle de départ' if fusion_reprise else 'à zéro (répond comme le départ)'}, "
          f"{n_app / 1e6:.1f} millions de réglages qui apprennent (dégelés {a.degeler})", flush=True)
    maitre = None
    if a.poids_maitre > 0:
        maitre = charger_modele(a.maitre, dev)
        for prm in maitre.parameters():
            prm.requires_grad_(False)
        print(f"Maître figé : {a.maitre} (poids {a.poids_maitre})", flush=True)
    dep = noter(modele, controles, dev)
    for k in CONTROLES:
        if k in dep:
            print(f"Départ {k:8s}: {resume(dep[k])}", flush=True)
    seuils = {k: dep[k]["iou_moyen_pct"] - a.recul_max for k in PROTEGES if k in dep}
    print("Règle : meilleure note vrais sans recul > " + f"{a.recul_max} sur " +
          ", ".join(f"{k} (min {s:.1f})" for k, s in seuils.items()), flush=True)

    groupes = [{"params": [p for n, p in modele.named_parameters() if p.requires_grad and not n.startswith(("oeil.", "fusion."))],
                "lr": a.lr, "base_lr": a.lr}]
    fus = [p for n, p in modele.named_parameters() if p.requires_grad and n.startswith("fusion.")]
    if fus:
        groupes.append({"params": fus, "lr": a.lr_oeil, "base_lr": a.lr_oeil})
    oe = [p for n, p in modele.named_parameters() if p.requires_grad and n.startswith("oeil.")]
    if oe:
        groupes.append({"params": oe, "lr": a.lr_oeil / 10, "base_lr": a.lr_oeil / 10})
    opt = torch.optim.AdamW(groupes, weight_decay=1e-4)
    echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
    distrib = DistributeurMelange(train, photos, monde, a.morceau, a.lot, a.debord, a.part_photos, a.part_monde,
                                  biais, a.part_biais, vrais, a.part_vrais)
    duree, t0, pas, pauses, sautes = a.minutes * 60, time.time(), 0, 0.0, 0
    historique = [{"pas": 0, "minutes": 0.0, **dep}]
    meilleur, garde = -1.0, False

    def ecoule() -> float:
        return time.time() - t0 - pauses

    def sauver(chemin: Path, notes: dict) -> None:
        torch.save({"modele": etat(modele), "base": base, "contexte": contexte, "oeil": a.oeil, "degeler": a.degeler,
                    "classes": NOMS, "cote": a.cote, "note": notes, "pas": pas, "essai": 8, "depart": str(a.reprendre)}, chemin)

    # Garde-fou « retour en arrière » (essai 7b) : on garde en mémoire le dernier bon état.
    def photo_etat():
        return ({k: v.detach().to("cpu", copy=True) for k, v in modele.state_dict().items()},
                copy.deepcopy(opt.state_dict()))
    bon_etat, meilleure_perte, sautes_avant, retours, facteur = photo_etat(), float("inf"), 0, 0, 1.0

    while ecoule() < duree:
        perte_tour, faits = 0.0, 0
        for _ in range(a.pas_par_tour):
            if ecoule() >= duree:  # --minutes est la seule durée : le tour en cours s'arrête aussi
                break
            frac = min(ecoule() / duree, 1.0)
            for g in opt.param_groups:
                g["lr"] = (g["base_lr"] * facteur * (0.5 * (1 + math.cos(math.pi * frac)) * 0.95 + 0.05)
                           * min(1.0, (pas + 1) / max(a.pas_chauffe, 1)))
            if a.figer_bn:
                for mod in modele.modules():
                    if isinstance(mod, torch.nn.modules.batchnorm._BatchNorm):
                        mod.eval()
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
            if not torch.isfinite(perte):  # un lot qui déborde est sauté (et compté)
                sautes += 1
                continue
            echelle.scale(perte).backward()
            echelle.unscale_(opt)
            torch.nn.utils.clip_grad_norm_([q for g in opt.param_groups for q in g["params"]], a.clip)
            echelle.step(opt); echelle.update()
            perte_tour += perte.item(); pas += 1; faits += 1
        if faits == 0:
            break
        perte_moy = perte_tour / faits
        fini = all(torch.isfinite(v).all() for v in modele.state_dict().values() if v.is_floating_point())
        if not fini or sautes - sautes_avant > 5 or perte_moy > a.retour_arriere * meilleure_perte:
            retours += 1; facteur /= 2
            etat_m, etat_o = bon_etat
            modele.load_state_dict(etat_m); opt.load_state_dict(etat_o)
            echelle = torch.amp.GradScaler(enabled=dev.type == "cuda")
            print(f"    RETOUR EN ARRIÈRE n° {retours} (perte {perte_moy:.3f}, meilleure {meilleure_perte:.3f}, "
                  f"lots sautés ce tour {sautes - sautes_avant}) : pas d'apprentissage × {facteur:g}", flush=True)
            sautes_avant = sautes
            if retours > 6:
                print("    trop de retours en arrière : on arrête l'apprentissage ici", flush=True)
                break
            continue
        sautes_avant = sautes
        meilleure_perte = min(meilleure_perte, perte_moy)
        bon_etat = photo_etat()
        notes = noter(modele, controles, dev)
        temp = temperature_gpu()
        minutes = round(ecoule() / 60, 1)
        historique.append({"pas": pas, "minutes": minutes, "perte": round(perte_moy, 4), "temperature_gpu": temp, **notes})
        print(f"[{minutes:5.1f} min] pas {pas:6d}  perte {perte_moy:.3f}  GPU {temp} °C  lots sautés {sautes}", flush=True)
        for k in CONTROLES:
            if k in notes:
                print(f"    {k:8s}: {resume(notes[k])}", flush=True)
        ok = all(notes[k]["iou_moyen_pct"] >= s for k, s in seuils.items())
        if "vrais" in notes:
            note = notes["vrais"]["iou_moyen_pct"]
        else:
            note = (notes["monde"]["iou_moyen_pct"] + notes["biais"]["iou_moyen_pct"]) / 2 if "biais" in notes else notes["monde"]["iou_moyen_pct"]
        if ok and note > meilleur:
            meilleur, garde = note, True
            sauver(a.sortie / "atelya-essai-8.pt", notes)
            print(f"    -> gardé (note vrais {note})", flush=True)
        elif not ok:
            print("    (recul : " + ", ".join(f"{k} {notes[k]['iou_moyen_pct']} (min {s:.1f})" for k, s in seuils.items()
                                             if notes[k]["iou_moyen_pct"] < s) + " ; pas gardé)", flush=True)
        sauver(a.sortie / "atelya-essai-8-dernier.pt", notes)
        (a.sortie / "historique.json").write_text(json.dumps(historique, ensure_ascii=False, indent=1), encoding="utf-8")
        while temp is not None and temp > a.temp_max:
            print(f"  carte graphique à {temp} °C : pause d'une minute pour la laisser refroidir", flush=True)
            time.sleep(60); pauses += 60; temp = temperature_gpu()

    # ---- bilan : le dernier état, le modèle gardé et le modèle de départ, notés sur les contrôles complets
    bilan = {"essai": 8, "retours_en_arriere": retours, "pas": pas, "lots_sautes": sautes,
             "minutes": round((time.time() - t0) / 60, 1), "minutes_de_pause_chaleur": round(pauses / 60, 1),
             "dessins_anciens": len(train), "photos_apprises": len(photos), "plans_photos": len(ids_p),
             "dessins_monde": len(monde), "dessins_biais": len(biais), "dessins_vrais": len(vrais),
             "plans_vrais_appris": sorted(plans_vrais), "controle_vrais": len(val_vrais_final),
             "parts_effectives": parts_effectives(a.part_vrais if vrais else 0, a.part_biais if biais else 0, a.part_monde, a.part_photos),
             "regle": {"note": "vrais (IoU moyen)", "recul_max": a.recul_max, "proteges": list(seuils), "seuils": seuils},
             "fusion_reprise": fusion_reprise,
             "reglages": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
             "machine": torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
             "memoire_gpu_max_go": round(torch.cuda.max_memory_allocated() / 1e9, 2) if dev.type == "cuda" else None}
    bilan["dernier"] = noter(modele, finals, dev)
    for k, v in bilan["dernier"].items():
        print(f"BILAN dernier {k} : {resume(v)}", flush=True)
    if not garde:
        print("AUCUN MODÈLE GARDÉ : chaque tour reculait sur les anciens plans, les photos ou les biais. On garde le départ.", flush=True)
        bilan["garde"] = False
    else:
        modele.load_state_dict(torch.load(a.sortie / "atelya-essai-8.pt", map_location=dev)["modele"], strict=False)
        bilan["garde"] = True
        bilan["essai8"] = noter(modele, finals, dev)
        if finals["vrais"]:
            planche(modele, finals["vrais"], dev, a.sortie / "planche-vrais-verite-atelya.png", n=8)
    depart, _, _ = charger_depart(a.reprendre, dev, a.oeil, a.degeler)
    bilan["depart_meme_controle"] = noter(depart, finals, dev)
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for nom in ("depart_meme_controle", "essai8"):
        if nom in bilan:
            for k in bilan[nom]:
                print(f"BILAN {nom} {k} : {resume(bilan[nom][k])}", flush=True)


if __name__ == "__main__":
    main()
