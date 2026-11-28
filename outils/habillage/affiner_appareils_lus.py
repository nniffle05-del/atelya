r"""Les appareils des photos AFFINÉS AVEC LES LIGNES LUES DES FENÊTRES (« la place des appareils des photos », 24/11/2026).

    python outils/habillage/affiner_appareils_lus.py <fiche des photos placées> <logement.json> <vitrages.json> [--sortie <fiche>]

Pourquoi : le calage affine déjà l'appareil de chaque photo sur les lignes du plafond et du sol qu'il trouve seul
(moteur/affiner_appareils.py). Ces lignes fixent bien la distance et la hauteur, mal le glissement le long d'un mur. Quand la
lecture des fenêtres existe (moteur/vitrages.py : pied et haut du mur de la fenêtre, tour de la menuiserie), elle fixe ce qui
manque : la fenêtre du film tombe là où elle est sur la photo. Mesuré le 24/11/2026 sur trois logements : place des montants
des fenêtres 26 / 15 / 27 px → 9 / 4 / 16 px, hauteurs 16 / 21 / 27 px → 4 / 9 / 5 px (photos de 1206 px de large).

Le logement doit porter les fenêtres telles que les photos les montrent (largeur, bas et haut : étape « baies » de la chaîne).
Seules les photos calées par Atelya ET affinées par lui (champ « affine » de la fiche) sont reprises, depuis l'appareil du
calage (« avant ») : une fiche relevée à la main n'est jamais touchée. Une photo sans fenêtre lue garde son appareil.
La fiche est réécrite sur place (ou dans --sortie) ; chaque appareil repris dit comment (« affine » → « comment »).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import affiner_appareils as aa  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur import fuites, moge  # noqa: E402
from moteur.images import lire_image  # noqa: E402


def affiner_la_fiche(fiche: dict, logement: dict, lecture: dict, journal=print) -> dict[str, str]:
    """Reprend, dans `fiche` (modifiée sur place), l'appareil de chaque photo affinée par Atelya qui a des fenêtres lues.
    → {photo: comment}."""
    import torch

    from moteur.pas_du_sol import charger as charger_pds

    lus = {n: aa.reperes_lus(logement, f) for n, f in (lecture.get("photos") or {}).items()}
    a_reprendre = {n: d for n, d in fiche.get("cameras", {}).items() if d.get("affine", {}).get("avant") and lus.get(n)}
    if not a_reprendre:
        journal("  aucune photo à reprendre (pas de fenêtre lue sur une photo affinée par Atelya)")
        return {}
    dossier = RACINE / str(fiche.get("photos") or "")
    modele = fiche.get("fichier", "{nom}.png")
    photos = {}
    for n in fiche.get("cameras", {}):
        image = lire_image(dossier / modele.format(nom=n))
        if image is not None:
            photos[n] = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    appareil = "cuda" if torch.cuda.is_available() else "cpu"
    reseau = moge.charger(appareil)
    owl = charger_pds(appareil, avec_dino=False).owl
    zoom = fuites.zoom_du_lot({n: {**fuites.mesurer(rgb), "largeur": rgb.shape[1]} for n, rgb in photos.items()})
    cameras, avant = {}, {}
    for n, d in a_reprendre.items():
        if n not in photos:
            continue
        avant[n] = (dict(d["camera"]), dict(d["affine"]))
        d["camera"] = dict(d["affine"]["avant"])  # on repart de l'appareil du calage : le résultat ne dépend pas d'un affinage d'avant
        cameras[n] = d
    mesures = {n: cp.mesurer(reseau, photos[n]) for n in cameras}
    bilan = aa.affiner_les_appareils(logement, photos, cameras, mesures, owl=owl, zoom_du_lot=zoom, lus=lus, journal=journal)
    for n, comment in bilan.items():
        if comment == "depart":  # rien de mieux avec les lignes lues : la photo garde l'appareil que le calage lui avait donné
            cameras[n]["camera"], cameras[n]["affine"] = avant[n]
    del reseau, owl
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return bilan


DERNIER_RECOURS = ("depart", "lus")  # l'affinage n'a pas pu caler la photo sur ses murs


def reprendre_sur_les_rangees(fiche: dict, logement: dict, vitrages: dict, dossier_lecture: Path, journal=print) -> list[str]:
    """DERNIER RECOURS (28/11/2026, moteur/appareil_sur_rangees.py) : une photo de cuisine que l'affinage n'a pas pu caler sur
    ses murs (elle ne montre presque que des meubles) est reprise sur les éléments de cuisine que sa lecture range, ensemble
    avec les lignes lues de ses fenêtres. `fiche` est modifiée sur place. → les photos reprises."""
    import math

    import numpy as np

    from moteur import appareil_sur_rangees as ar

    import os

    if os.environ.get("ATELYA_RANGEES_DERNIER_RECOURS", "1") == "0":  # pour comparer : sans le dernier recours
        return []
    if not (dossier_lecture / "lecture.json").is_file() or not (dossier_lecture / "envoi").is_dir():
        return []
    sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
    from poser_photos_lues import objets_des_photos, rangees_des_photos

    objets, rangees = objets_des_photos(fiche, dossier_lecture), rangees_des_photos(fiche, dossier_lecture)
    scene, vide = aa.Scene(logement), {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
    reprises = []
    for nom in sorted(rangees):
        d = fiche["cameras"][nom]
        affine = d.get("affine")
        if not affine or affine.get("comment") not in DERNIER_RECOURS:  # calée sur ses murs, ou relevée à la main : pas touchée
            continue
        image = lire_image(RACINE / str(fiche.get("photos") or "") / fiche.get("fichier", "{nom}.png").format(nom=nom))
        if image is None:
            continue
        reps = aa.reperes_lus(logement, (vitrages.get("photos") or {}).get(nom) or [])
        lignes = (lambda c, reps=reps: aa.cout(np.array(c, float), scene, vide, reps)) if reps else None
        boites = {int(o["numero"]): o["boite"] for o in objets.get(nom) or []}
        r = ar.affiner(d["camera"], rangees[nom], boites, image.shape[1], image.shape[0], logement, lignes=lignes)
        if r is None:
            continue
        if not r["garde"] or (r.get("lignes") and r["lignes"][1] > aa.ACCEPTE_PX):
            journal(f"  {nom} : éléments de cuisine essayés en dernier recours, appareil laissé à sa place "
                    f"({r['raison'] or 'les lignes lues ne collent plus'})")
            continue
        c, n = d["camera"], r["camera"]
        journal(f"  {nom} : appareil repris sur les éléments de cuisine (dernier recours) : déplacé de "
                f"{math.hypot(n['x'] - c['x'], n['y'] - c['y']):.2f} m, cap {(n['cap'] - c['cap'] + 180) % 360 - 180:+.1f}°, écart aux éléments "
                f"{r['avant']:.0f} → {r['apres']:.0f} px" + (f", aux lignes lues {r['lignes'][0]:.0f} → {r['lignes'][1]:.0f} px" if r.get("lignes") else ""))
        affine["comment"] = "rangees" if affine["comment"] == "depart" else affine["comment"] + "+rangees"
        affine["rangees"] = {"avant": dict(c), "ecart": [round(r["avant"], 1), round(r["apres"], 1)],
                             "lignes": [round(v, 1) for v in r["lignes"]] if r.get("lignes") else None}
        c.update(x=round(float(n["x"]), 3), y=round(float(n["y"]), 3), cap=round(float(n["cap"]), 2), f=round(float(n["f"]), 2))
        reprises.append(nom)
    return reprises


def main() -> int:
    ap = argparse.ArgumentParser(description="Les appareils des photos affinés avec les lignes lues des fenêtres")
    ap.add_argument("fiche", type=Path)
    ap.add_argument("logement", type=Path)
    ap.add_argument("vitrages", type=Path)
    ap.add_argument("--sortie", type=Path)
    a = ap.parse_args()
    for p in (a.fiche, a.logement, a.vitrages):
        if not p.is_file():
            print(f"PLANTÉ : fichier introuvable : {p}", flush=True)
            return 2
    fiche = json.loads(a.fiche.read_text(encoding="utf-8"))
    logement = json.loads(a.logement.read_text(encoding="utf-8"))
    logement = logement.get("logement", logement)
    print("Appareils des photos repris avec les lignes lues des fenêtres :", flush=True)
    vitrages = json.loads(a.vitrages.read_text(encoding="utf-8"))
    bilan = affiner_la_fiche(fiche, logement, vitrages, journal=lambda *t: print(*t, flush=True))
    reprendre_sur_les_rangees(fiche, logement, vitrages, a.vitrages.parent, journal=lambda *t: print(*t, flush=True))
    sortie = a.sortie or a.fiche
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {sum(1 for c in bilan.values() if 'lus' in c)} photo(s) calée(s) sur leurs fenêtres lues, sur {len(bilan)} reprise(s) : {sortie}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
