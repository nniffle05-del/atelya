r"""Les photos du client CALÉES SEULES (moteur/caler_photos.py) : la fiche « d'où est prise chaque photo », sans relevé à la main.

    ..\atelya\.venv\Scripts\python.exe outils\habillage\caler_photos_seul.py logement.json ..\atelya\photos-clients\app-002\photos ^
        cameras-photos-seul.json [--corrige verites\app-002\cameras-photos.json]

La fiche écrite a le MÊME format que celle faite à la main (verites\<logement>\cameras-photos.json) : elle se donne telle
quelle aux sols (sols_photos.py) et aux meubles (reperer_meubles_photos.py). « cameras » ne contient que les photos dont
Atelya est SÛR ; les autres sont rangées dans « incertaines » (placées, mais à ne pas utiliser) et « non_calees ».
LA PIÈCE DONNÉE PAR LE CLIENT (15/11/2026) : --pieces <fichier.json>, ou un fichier « pieces-des-photos.json » rangé dans le
dossier des photos (alors pris tout seul, aussi par sols_photos.py et reperer_meubles_photos.py) :
    {"photo-01": "sejour_1", "photo-07": "chambre_2", "photo-09": "cuisine"}        (identifiant du plan, ou sorte de pièce)
ou  {"pieces": {…}, "confirmees": ["photo-07"], "endroits": {"photo-12": [11.4, 6.2]}}
    (confirmees : pièces confirmées à l'écran de vérification ; endroits : d'où la photo est prise, POINTÉ sur le plan à
     l'écran de vérification, en mètres du plan : Atelya cherche alors l'appareil à moins de 1,5 m de ce point ; un 3e
     nombre, facultatif, donne le sens du regard en degrés (0 = vers la droite du plan, 90 = vers le haut), à 45° près).
La fiche dit aussi quoi demander à la vérification : « a_pointer » = {photo: question en clair} pour chaque photo qu'Atelya
ne sait pas ranger (il hésite entre deux pièces, il doute de la pièce donnée, ou il n'a pas pu la placer).
Une photo dont la pièce est donnée est utilisée, sauf si Atelya la voit ailleurs : elle est alors rangée dans « a_verifier »
avec la raison (à confirmer à l'écran de vérification), et laissée de côté en attendant.
--corrige : compare à un relevé à la main (essais). --fenetres <dossier> : cartes des fenêtres toutes faites (essais sur les
deux logements qui ont servi à apprendre la couche des fenêtres : cartes apprises sans le logement noté).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import lire_image  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def lire_photos(dossier: Path) -> tuple[dict, str]:
    fichiers = sorted(p for p in dossier.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not fichiers:
        raise FileNotFoundError(f"aucune photo dans {dossier}")
    ext = {p.suffix for p in fichiers}
    if len(ext) > 1:
        raise ValueError(f"photos de plusieurs formats dans {dossier} : {sorted(ext)}")
    photos = {}
    for p in fichiers:
        im = lire_image(p)
        if im is None:
            raise FileNotFoundError(p)
        photos[p.stem] = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    return photos, "{nom}" + ext.pop()


def questions(resultat: dict) -> dict:
    """Ce que l'écran de vérification doit demander : pour chaque photo qu'Atelya ne sait pas ranger, la question en clair."""
    q = {}
    for n, d in resultat["cameras"].items():
        if d["sure"]:
            if d.get("endroit_douteux"):  # la pièce est sûre, pas la place dans la pièce : la photo reste utilisée, mais on demande
                q[n] = f"Atelya a rangé cette photo dans {d['piece']}, mais il n'est pas sûr de l'endroit : {d['endroit_douteux']}."
            continue
        if d.get("a_verifier"):
            q[n] = f"Pièce donnée : {d['piece']}, mais {d['a_verifier']}. Confirmez la pièce, ou pointez d'où la photo est prise."
        elif d.get("hesite_avec"):
            q[n] = f"Atelya hésite entre {d['piece']} et {', '.join(d['hesite_avec'])}. Pointez d'où la photo est prise."
        else:
            q[n] = "Atelya n'est pas sûr de la pièce. Pointez d'où la photo est prise."
    for n in resultat["non_calees"]:
        q[n] = "Atelya n'a pas pu placer cette photo. Pointez d'où elle est prise."
    return q


def fiche(resultat: dict, dossier: Path, modele: str) -> dict:
    try:
        rel = Path(os.path.relpath(dossier.resolve(), RACINE)).as_posix()
    except ValueError:  # autre disque
        rel = dossier.resolve().as_posix()
    garde = lambda d: {k: d[k] for k in ("camera", "largeur", "hauteur", "piece", "marge", "bloc", "hesite_avec", "donnee", "colle", "avis_seul", "a_verifier", "pointee", "endroit", "endroit_douteux", "affine")
                       if k in d and (k != "hesite_avec" or d[k])}
    return {"note": f"Caméras des photos retrouvées SEULES par Atelya (moteur/caler_photos.py {cp.VERSION}). « cameras » : photos "
                    "dont Atelya est sûr (seules à utiliser) ; « incertaines » : placées, mais pas sûres (« hesite_avec » : l'autre pièce possible).",
            "photos": rel, "fichier": modele,
            "cameras": {n: garde(d) for n, d in resultat["cameras"].items() if d["sure"]},
            "incertaines": {n: garde(d) for n, d in resultat["cameras"].items() if not d["sure"] and not d.get("a_verifier")},
            "a_verifier": {n: garde(d) for n, d in resultat["cameras"].items() if d.get("a_verifier")},
            "a_pointer": questions(resultat),
            "non_calees": resultat["non_calees"]}


PIECES_DES_PHOTOS = "pieces-des-photos.json"  # dans le dossier des photos : la pièce de chaque photo, dite par le client


def lire_pieces(chemin: Path | None, photos: dict) -> tuple[dict, set, dict]:
    """Le fichier des pièces données par le client → ({photo: pièce}, photos confirmées, {photo: (x, y) pointé à la
    vérification}). Les noms peuvent porter l'extension."""
    if chemin is None or not chemin.is_file():
        return {}, set(), {}
    d = json.loads(chemin.read_text(encoding="utf-8"))
    pieces, confirmees, endroits = (d["pieces"], d.get("confirmees", []), d.get("endroits", {})) if isinstance(d.get("pieces"), dict) else (d, [], {})
    nom = lambda n: n if n in photos else Path(n).stem
    inconnues = [n for n in pieces if nom(n) not in photos]
    if inconnues:
        print(f"  attention : {chemin.name} parle de photos absentes du dossier : {inconnues}", flush=True)
    return ({nom(n): p for n, p in pieces.items() if nom(n) in photos and p}, {nom(n) for n in confirmees},
            {nom(n): tuple(float(x) for x in v[:3]) for n, v in endroits.items() if nom(n) in photos})


def fiche_ou_photos(chemin: Path, logement: dict, a_cote: Path, journal=print, outils=None) -> dict:
    """Ce que les outils des sols et des meubles reçoivent : une fiche déjà faite (fichier .json, calée à la main ou par
    Atelya), ou directement le DOSSIER des photos du client : Atelya les cale alors seul et range la fiche `a_cote`.
    outils : les réseaux déjà chargés (caler_photos.Outils), pour ne pas les recharger à chaque appel (écran enchaîné)."""
    if not chemin.is_dir():
        return json.loads(chemin.read_text(encoding="utf-8"))
    import gc

    import torch
    photos, modele = lire_photos(chemin)
    pieces, confirmees, endroits = lire_pieces(chemin / PIECES_DES_PHOTOS, photos)
    journal(f"Photos calées seules ({len(photos)} photos, pièce donnée par le client pour {len(pieces)}, endroit pointé pour {len(endroits)}) :")
    f = fiche(cp.caler(logement, photos, outils=outils, journal=journal, pieces_donnees=pieces, confirmees=confirmees, endroits_donnes=endroits), chemin, modele)
    a_cote.parent.mkdir(parents=True, exist_ok=True)
    a_cote.write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    journal(f"  {len(f['cameras'])} photos sûres (utilisées), {len(f['a_pointer'])} à montrer à la vérification (« d'où est prise cette photo ? ») : {a_cote}")
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return f


def comparer(resultat: dict, corrige: dict, logement: dict) -> None:
    plan = cp.plan_du_logement(logement)
    lignes = []
    for n, d in resultat["cameras"].items():
        if n not in corrige["cameras"]:
            continue
        k, c = corrige["cameras"][n]["camera"], d["camera"]
        pv = "?"
        for t in np.arange(0, 1.6, 0.1):  # appareil relevé « dans le mur » : la pièce est celle qu'il regarde
            ip = cp.piece_de(plan, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
            if ip >= 0:
                pv = plan["ids"][ip]; break
        e, dc = float(np.hypot(c["x"] - k["x"], c["y"] - k["y"])), float(abs((c["cap"] - k["cap"] + 180) % 360 - 180))
        lignes.append((e, dc, d["piece"] == pv, d["sure"]))
        print(f"  {n} (main : {pv}) → {d['piece']} | {e:.2f} m, {dc:.0f}° | hauteur {c['z']:.2f} (main {k['z']:.2f}), zoom {c['f']:.0f} (main {k['f']:.0f})"
              f" | {'sûre' if d['sure'] else 'pas sûre'} (marge {d['marge']:.2f})")
    t = np.array(lignes, float)
    if not len(t):
        return
    for nom, sel in (("toutes les photos placées", t[:, 3] >= 0), ("photos sûres", t[:, 3] == 1)):
        u = t[sel]
        print(f"{nom} ({len(u)} sur {len(corrige['cameras'])} au corrigé) : bonne pièce {int(u[:, 2].sum())}, à peu près placées (< 1 m, < 15°) "
              f"{int(((u[:, 0] < 1) & (u[:, 1] < 15)).sum())}, bien placées (< 0,5 m, < 8°) {int(((u[:, 0] < 0.5) & (u[:, 1] < 8)).sum())}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Photos du client calées seules")
    ap.add_argument("logement", type=Path)
    ap.add_argument("photos", type=Path, help="dossier des photos du client")
    ap.add_argument("sortie", type=Path, help="fiche écrite (format cameras-photos.json)")
    ap.add_argument("--pieces", type=Path, help=f"la pièce de chaque photo, dite par le client (défaut : {PIECES_DES_PHOTOS} dans le dossier des photos)")
    ap.add_argument("--corrige", type=Path, help="relevé à la main, pour comparer (essais)")
    ap.add_argument("--fenetres", type=Path, help="dossier de cartes des fenêtres toutes faites, <prefixe><nom>.npy (essais)")
    ap.add_argument("--prefixe", default="", help="début du nom des cartes (--fenetres)")
    args = ap.parse_args()
    for f in (args.logement, args.photos):
        if not f.exists():
            print(f"PLANTÉ : introuvable : {f}", flush=True)
            return 2
    logement = json.loads(args.logement.read_text(encoding="utf-8"))
    photos, modele = lire_photos(args.photos)
    corrige = json.loads(args.corrige.read_text(encoding="utf-8")) if args.corrige else None
    if corrige:  # essais : seulement les photos du corrigé
        photos = {n: p for n, p in photos.items() if n in corrige["cameras"]}
    fen = None
    if args.fenetres:
        fen = {n: np.load(args.fenetres / f"{args.prefixe}{n}.npy")[..., 2].astype(np.float32) for n in photos if (args.fenetres / f"{args.prefixe}{n}.npy").is_file()}
    t0 = time.time()
    print(f"{len(photos)} photos, {len(logement['pieces'])} pièces", flush=True)
    pieces, confirmees, endroits = lire_pieces(args.pieces or args.photos / PIECES_DES_PHOTOS, photos)
    if pieces or endroits:
        print(f"pièce donnée par le client pour {len(pieces)} photos, endroit pointé pour {len(endroits)}", flush=True)
    resultat = cp.caler(logement, photos, journal=lambda *a: print(*a, flush=True), fenetres_de=fen, pieces_donnees=pieces, confirmees=confirmees,
                        endroits_donnes=endroits)
    f = fiche(resultat, args.photos, modele)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(f['cameras'])} photos sûres, {len(f['a_verifier'])} à vérifier, {len(f['incertaines'])} incertaines, {len(f['non_calees'])} non calées, "
          f"en {time.time() - t0:.0f} s → {args.sortie}", flush=True)
    for n, question in f["a_pointer"].items():
        print(f"  à demander à la vérification, {n} : {question}", flush=True)
    if corrige:
        comparer(resultat, corrige, logement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
