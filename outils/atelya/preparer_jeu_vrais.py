r"""Fabriquer un jeu d'entraînement à partir des VÉRITÉS des vrais plans (essai 8).

Pourquoi : Atelya n'a appris que sur des plans fabriqués par notre générateur ; chaque vrai style inconnu (sols
hachurés, dessin à la main, murs gris clair, photo floue) est colorié n'importe comment. Les vérités du lot 2
(outils/verite/faire_verite.py : image + masque_semantique.png aux classes du générateur) permettent enfin de lui
montrer du VRAI. 78 plans, c'est peu : chaque plan est donc MULTIPLIÉ en variantes (tourné d'un ou deux degrés,
agrandi ou réduit, un peu de perspective, photocopié, grain, JPEG, capture d'écran…), l'image ET son masque
transformés ensemble, comme le fait le générateur pour les plans fabriqués.

Garde-fou absolu : seuls les plans de la clé « entrainement » de verites/repartition-vrais-plans.json entrent
dans le jeu. Un dossier de vérité portant le nom d'un plan d'EXAMEN (clés examen_anciens / examen_nouveaux)
est REFUSÉ et signalé ; un plan inconnu de la répartition aussi.

Contrôle « vrais » : --controle N plans sont tirés au sort (graine fixe, ordre fixe sur la liste « entrainement »,
donc le même tirage d'une fois sur l'autre tant que leurs vérités existent) ; ils sont ÉCARTÉS de l'entraînement
et gardés en contrôle avec leur image ORIGINALE seule (partition « validation »), pour noter l'essai 8 sur du vrai
jamais vu.

Sortie = le format que lit entrainer.py (lire_partitions, dessins, charger) :
    <sortie>/exemples/<fr-0xx>-v<NN>/niveau_0/plan.png + masque_semantique.png + annotations.json
    <sortie>/repartition.json  {"schema": "repartition/1.0", "partitions": {"train": [...], "validation": [...], "test": []}}
    <sortie>/manifeste.json    (plans pris, refusés, contrôles, recettes)

Usage (depuis atelya-code, Python du PC) :
    ..\atelya\.venv\Scripts\python.exe outils\atelya\preparer_jeu_vrais.py --verites ..\atelya\verites-lot2
        --repartition verites\repartition-vrais-plans.json --sortie ..\atelya\donnees\vrais-2026-11-05 --variantes 12 --controle 8
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.generateur.variantes import Style, salir  # noqa: E402
from moteur.generateur.variete import FILIGRANES, Variete, capture  # noqa: E402

VERSION = "0.1.0"
NB_CLASSES = 16
SALISSURES = ("photocopie", "grain", "bruit", "jpeg", "telephone")
IMAGES = (".jpg", ".jpeg", ".png")


# ---------------------------------------------------------------- répartition et vérités

def lire_repartition(chemin: Path) -> dict:
    rep = json.loads(Path(chemin).read_text(encoding="utf-8"))
    for cle in ("entrainement",):
        if cle not in rep:
            raise ValueError(f"{chemin} : clé « {cle} » absente")
    return rep


def plans_d_examen(rep: dict) -> set[str]:
    return set(rep.get("examen_anciens", [])) | set(rep.get("examen_nouveaux", []))


def trier_verites(dossier_verites: Path, rep: dict) -> tuple[list[tuple[str, Path]], list[str], list[str], list[str]]:
    """(plans autorisés avec vérité finie, refusés car examen, inconnus de la répartition, autorisés sans vérité finie)."""
    examen, autorises = plans_d_examen(rep), set(rep["entrainement"])
    pris, refuses, inconnus, incomplets = [], [], [], []
    for d in sorted(p for p in Path(dossier_verites).iterdir() if p.is_dir()):
        nom = d.name
        if nom in examen:
            refuses.append(nom)
            continue
        if nom not in autorises:
            inconnus.append(nom)
            continue
        if (d / "masque_semantique.png").exists() and image_du_plan(d) is not None:
            pris.append((nom, d))
        else:
            incomplets.append(nom)
    return pris, refuses, inconnus, incomplets


def image_du_plan(dossier: Path) -> Path | None:
    """fr-0xx.jpg / .png posé dans le dossier de la vérité (le nom du plan, pas les aperçus ni la grille)."""
    for ext in IMAGES:
        f = dossier / f"{dossier.name}{ext}"
        if f.exists():
            return f
    verite = dossier / "verite.json"
    if verite.exists():
        nom = json.loads(verite.read_text(encoding="utf-8")).get("image")
        if nom and (dossier / nom).exists():
            return dossier / nom
    return None


def lire_verite(dossier: Path, cote_max: int = 0) -> tuple[np.ndarray, np.ndarray, dict]:
    """Image RGB (uint8), masque (uint8, classes 0-15) et verite.json (ou {}) ; réduits si le grand côté dépasse cote_max."""
    img = np.asarray(Image.open(image_du_plan(dossier)).convert("RGB"))
    msq = Image.open(dossier / "masque_semantique.png")
    if msq.mode not in ("L", "P"):
        msq = msq.convert("L")
    msq = np.asarray(msq, dtype=np.uint8).copy()
    if msq.shape[:2] != img.shape[:2]:
        raise ValueError(f"{dossier.name} : masque {msq.shape[:2]} et image {img.shape[:2]} de tailles différentes")
    msq[msq >= NB_CLASSES] = 0
    verite = {}
    if (dossier / "verite.json").exists():
        verite = json.loads((dossier / "verite.json").read_text(encoding="utf-8"))
    h, w = msq.shape
    if cote_max and max(h, w) > cote_max:
        r = cote_max / max(h, w)
        taille = (max(1, round(w * r)), max(1, round(h * r)))
        img = cv2.resize(img, taille, interpolation=cv2.INTER_AREA)
        msq = cv2.resize(msq, taille, interpolation=cv2.INTER_NEAREST)
    return np.ascontiguousarray(img), np.ascontiguousarray(msq), verite


# ---------------------------------------------------------------- variantes

@dataclass
class Recette:
    """Ce qui a été fait à une variante (écrit dans annotations.json, pour pouvoir le relire)."""

    rotation_deg: float = 0.0
    echelle: float = 1.0
    perspective: float = 0.0
    salissure: str = ""
    contraste: float = 1.0
    papier: int = 255
    capture: bool = False
    filigrane: str = ""
    agrandi: float = 1.0
    coins: list = field(default_factory=list)


def boite_logement(msq: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) des pixels non-fond : là où est le logement."""
    ys, xs = np.nonzero(msq)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def echelle_max(msq: np.ndarray, plafond: float = 1.4) -> float:
    """La plus grande échelle qui garde le logement entier dans le cadre (agrandi autour de son centre)."""
    boite = boite_logement(msq)
    if boite is None:
        return plafond
    h, w = msq.shape
    x0, y0, x1, y1 = boite
    bw, bh = max(x1 - x0, 1), max(y1 - y0, 1)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tient = min(2 * cx / bw, 2 * (w - cx) / bw, 2 * cy / bh, 2 * (h - cy) / bh) * 0.97
    return max(0.6, min(plafond, tient))


def matrice(h: int, w: int, centre: tuple[float, float], rec: Recette) -> np.ndarray:
    """Homographie 3×3 : échelle et rotation autour du centre du logement, puis coins de la page bougés."""
    cx, cy = centre
    s = rec.echelle
    S = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy], [0, 0, 1]], np.float64)
    R = np.vstack([cv2.getRotationMatrix2D((cx, cy), rec.rotation_deg, 1.0), [0, 0, 1]])
    M = R @ S
    if rec.coins:
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32(rec.coins)
        M = cv2.getPerspectiveTransform(src, dst) @ M
    return M


def transformer(img: np.ndarray, msq: np.ndarray, M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Image et masque déformés ensemble ; hors-champ = papier blanc (255) et fond (0) ; masque sans mélange (NEAREST)."""
    h, w = msq.shape
    img2 = cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=(255, 255, 255))
    msq2 = cv2.warpPerspective(msq, M, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return img2, msq2


def tirer_recette(rng: random.Random, msq: np.ndarray) -> Recette:
    """Une variante au hasard : géométrie (tour, échelle, perspective) et salissures de pixels ; au moins un changement."""
    h, w = msq.shape
    rec = Recette()
    if rng.random() < 0.5:
        rec.rotation_deg = round(rng.choice((-1, 1)) * rng.uniform(1.0, 5.0), 2)
    if rng.random() < 0.5:
        rec.echelle = round(rng.uniform(0.6, echelle_max(msq)), 3)
    if rng.random() < 0.3:
        rec.perspective = round(rng.uniform(0.02, 0.06), 3)
        rec.coins = [[round(x + rng.uniform(-rec.perspective, rec.perspective) * w, 1),
                      round(y + rng.uniform(-rec.perspective, rec.perspective) * h, 1)]
                     for x, y in ((0, 0), (w, 0), (w, h), (0, h))]
    if rng.random() < 0.7:
        rec.salissure = rng.choice(SALISSURES)
    if rng.random() < 0.5:
        rec.contraste = round(rng.uniform(0.7, 1.2), 3)
    if rng.random() < 0.5:
        rec.papier = rng.randint(215, 255)
    if rng.random() < 0.2:
        rec.capture = True
        rec.filigrane = rng.choice(FILIGRANES) if rng.random() < 0.5 else ""
        rec.agrandi = round(rng.uniform(1.5, 2.5), 2) if rng.random() < 0.3 else 1.0
    elif rng.random() < 0.08:
        rec.filigrane = rng.choice(FILIGRANES)
    if rec == Recette():
        rec.salissure = rng.choice(SALISSURES)
    return rec


def appliquer(img: np.ndarray, msq: np.ndarray, rec: Recette, rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    """La variante : géométrie (image + masque), puis capture d'écran et salissures (pixels de l'image seuls)."""
    h, w = msq.shape
    if rec.rotation_deg or rec.echelle != 1.0 or rec.coins:
        boite = boite_logement(msq)
        centre = ((boite[0] + boite[2]) / 2, (boite[1] + boite[3]) / 2) if boite else (w / 2, h / 2)
        img, msq = transformer(img, msq, matrice(h, w, centre, rec))
    if rec.capture or rec.filigrane or rec.agrandi > 1.0:
        img = capture(img, msq, Variete(capture=rec.capture, filigrane=rec.filigrane, agrandi=rec.agrandi), rng)
    if rec.salissure or rec.contraste != 1.0 or rec.papier != 255:
        img = salir(img, Style(salissure=rec.salissure, contraste=rec.contraste, papier=rec.papier), rng)
    return np.ascontiguousarray(img), np.ascontiguousarray(msq)


def variante(img: np.ndarray, msq: np.ndarray, plan: str, k: int) -> tuple[np.ndarray, np.ndarray, Recette]:
    """Variante n° k du plan (k = 0 : l'original tel quel). Hasard déterministe : même recette d'une fois sur l'autre."""
    if k == 0:
        return img, msq, Recette()
    rng = random.Random(f"vrais-{plan}-{k}")
    rec = tirer_recette(rng, msq)
    img2, msq2 = appliquer(img, msq, rec, rng)
    return img2, msq2, rec


# ---------------------------------------------------------------- le jeu

def choisir_controles(rep: dict, disponibles: list[str], nombre: int, graine: int, imposes: list[str] | None = None) -> list[str]:
    """Les plans de contrôle : ordre fixe (graine) sur TOUTE la liste « entrainement », les premiers qui ont une vérité."""
    if imposes:
        manquants = [p for p in imposes if p not in disponibles]
        if manquants:
            raise ValueError(f"contrôles imposés sans vérité finie : {manquants}")
        return list(imposes)
    ordre = list(rep["entrainement"])
    random.Random(graine).shuffle(ordre)
    dispo = set(disponibles)
    return [p for p in ordre if p in dispo][:max(0, nombre)]


def ecrire_exemple(sortie: Path, ident: str, img: np.ndarray, msq: np.ndarray, annotations: dict) -> None:
    d = sortie / "exemples" / ident / "niveau_0"
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(d / "plan.png", compress_level=3)
    Image.fromarray(msq, mode="L").save(d / "masque_semantique.png")
    (d / "annotations.json").write_text(json.dumps(annotations, ensure_ascii=False, indent=1), encoding="utf-8")


def fabriquer_jeu(verites: Path, repartition: Path, sortie: Path, variantes: int = 12, controle: int = 8,
                  graine: int = 20261105, controles_imposes: list[str] | None = None, cote_max: int = 2000,
                  silencieux: bool = False) -> dict:
    def dire(t: str) -> None:
        if not silencieux:
            print(t, flush=True)

    rep = lire_repartition(repartition)
    pris, refuses, inconnus, incomplets = trier_verites(Path(verites), rep)
    for nom in refuses:
        dire(f"REFUSÉ : {nom} est un plan d'EXAMEN, il n'entre jamais dans un jeu d'entraînement")
    for nom in inconnus:
        dire(f"ignoré : {nom} n'est pas dans la répartition ({repartition})")
    if incomplets:
        dire(f"pas encore de vérité finie (masque_semantique.png) : {', '.join(incomplets)}")
    if not pris:
        raise SystemExit("ARRÊT : aucune vérité d'entraînement finie dans " + str(verites))
    noms = [n for n, _ in pris]
    controles = choisir_controles(rep, noms, controle, graine, controles_imposes)
    sortie = Path(sortie)
    (sortie / "exemples").mkdir(parents=True, exist_ok=True)
    train, val, recettes, t0 = [], [], {}, time.time()
    for nom, dossier in pris:
        img, msq, verite = lire_verite(dossier, cote_max)
        nb = 1 if nom in controles else max(1, variantes)
        for k in range(nb):
            img2, msq2, rec = variante(img, msq, nom, k)
            ident = f"{nom}-v{k:02d}"
            h, w = msq2.shape
            ecrire_exemple(sortie, ident, img2, msq2, {
                "niveau": 0, "image": {"largeur": w, "hauteur": h}, "source": "vrai plan", "plan": nom, "variante": k,
                "controle": nom in controles, "px_par_m_origine": verite.get("px_par_m"), "recette": asdict(rec)})
            (val if nom in controles else train).append(ident)
            recettes[ident] = asdict(rec)
        dire(f"  {nom} : {nb} dessin(s){' (contrôle, original seul)' if nom in controles else ''}")
    partitions = {"schema": "repartition/1.0", "version_preparer": VERSION, "date": str(date.today()), "graine": graine,
                  "partitions": {"train": train, "validation": val, "test": []}}
    (sortie / "repartition.json").write_text(json.dumps(partitions, ensure_ascii=False, indent=1), encoding="utf-8")
    manifeste = {"schema": "jeu-vrais/0.1", "version": VERSION, "date": str(date.today()), "verites": str(verites),
                 "repartition_source": str(repartition), "variantes": variantes, "cote_max": cote_max, "graine": graine,
                 "plans_appris": [n for n in noms if n not in controles], "plans_controle": controles,
                 "refuses_examen": refuses, "inconnus": inconnus, "sans_verite_finie": incomplets,
                 "dessins_train": len(train), "dessins_validation": len(val), "recettes": recettes}
    (sortie / "manifeste.json").write_text(json.dumps(manifeste, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"Jeu {sortie} : {len(noms)} plans ({len(controles)} en contrôle : {', '.join(controles) or 'aucun'}), "
         f"{len(train)} dessins d'apprentissage, {len(val)} de contrôle, {time.time() - t0:.0f} s")
    return manifeste


def main() -> None:
    ap = argparse.ArgumentParser(description="Jeu d'entraînement Atelya à partir des vérités des vrais plans (essai 8)")
    ap.add_argument("--verites", type=Path, required=True, help="dossier des vérités (un sous-dossier par plan)")
    ap.add_argument("--repartition", type=Path, default=Path(__file__).resolve().parents[2] / "verites" / "repartition-vrais-plans.json")
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--variantes", type=int, default=12, help="dessins par plan appris (v00 = l'original)")
    ap.add_argument("--controle", type=int, default=8, help="plans gardés en contrôle « vrais » (original seul)")
    ap.add_argument("--controle-liste", type=str, default="", help="plans de contrôle imposés, séparés par des virgules")
    ap.add_argument("--graine", type=int, default=20261105, help="graine du tirage des contrôles")
    ap.add_argument("--cote-max", type=int, default=2000, help="grand côté maximal des images écrites (0 = tel quel)")
    a = ap.parse_args()
    imposes = [p.strip() for p in a.controle_liste.split(",") if p.strip()] or None
    fabriquer_jeu(a.verites, a.repartition, a.sortie, a.variantes, a.controle, a.graine, imposes, a.cote_max)


if __name__ == "__main__":
    main()
