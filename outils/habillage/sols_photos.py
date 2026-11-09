r"""Brique photos : le sol de l'appartement vu de dessus, reconstitué depuis les photos du client (09/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\sols_photos.py a_plat verites\app-001\cameras-photos.json ^
        ..\atelya\lectures-claude\app-001\logement.json ..\atelya\b2\app-001\brique-photos [--verite verites\app-001\sols.json]

Chaque photo calée (cameras-photos.json) est mise à plat sur le sol de la pièce où se tient l'appareil (moteur/sol_a_plat.py),
puis toutes sont assemblées : chaque endroit du sol prend la photo qui le voit le plus finement. Écrit dans le dossier de sortie :
    sol-a-plat.png      le sol de tout l'appartement vu de dessus (1 cm par pixel), contours des pièces en rouge,
                        et, avec --verite, les zones de sol de la vérité (jaune cubes, bleu lames, sinon blanc) ;
    sol-a-plat.npz      l'image brute, la finesse et le n° de photo de chaque point (pour la reconnaissance) ;
    a-plat\photo-XX.png chaque photo à plat seule.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.images import ecrire_image  # noqa: E402
from moteur.sol_a_plat import RESOLUTION_M, aire, assembler, photos_a_plat  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def dessiner_contours(image, origine, resolution, contours, couleur, epaisseur=2):
    for c in contours:
        pts = np.array([[(x - origine[0]) / resolution, (origine[1] - y) / resolution] for x, y in c], np.int32)
        cv2.polylines(image, [pts], True, couleur, epaisseur, cv2.LINE_AA)


COULEURS_FAMILLES = {"lames": (255, 150, 0), "point_de_hongrie": (180, 60, 255), "batons_rompus": (0, 200, 0),
                     "carreaux": (0, 220, 255)}  # BGR : bleu, rose, vert, jaune


def dessiner_reconnaissance(resultat: dict, logement: dict, sortie: Path) -> None:
    """Le sol à plat avec, par-dessus, la famille décidée (couleur pleine et légère) et les zones trouvées (traits épais)."""
    from moteur.reconnaitre_sols import FAMILLES, famille_decidee
    image, finesse, origine, res = resultat["image"], resultat["finesse"], resultat["origine"], resultat["resolution"]
    dessin = cv2.cvtColor(image, cv2.COLOR_RGB2BGR).astype(np.float32)
    lignes, colonnes = np.nonzero(finesse > 0)
    X, Y = origine[0] + (colonnes + 0.5) * res, origine[1] - (lignes + 0.5) * res
    decide = famille_decidee(resultat["pieces"], logement, X, Y)
    for i, f in enumerate(FAMILLES):
        m = decide == i
        dessin[lignes[m], colonnes[m]] = 0.6 * dessin[lignes[m], colonnes[m]] + 0.4 * np.array(COULEURS_FAMILLES[f])
    dessin = dessin.astype(np.uint8)
    dessin[finesse == 0] = (60, 60, 60)
    dessiner_contours(dessin, origine, res, [p["contour"] for p in logement["pieces"]], (0, 0, 255), 3)
    for s in resultat["pieces"].values():
        for z in s["zones"]:
            dessiner_contours(dessin, origine, res, [z["contour"]], COULEURS_FAMILLES[z["famille"]], 5)
    for k, f in enumerate(FAMILLES):  # légende
        cv2.rectangle(dessin, (20, 20 + 40 * k), (55, 50 + 40 * k), COULEURS_FAMILLES[f], -1)
        cv2.putText(dessin, f.replace("_", " "), (65, 45 + 40 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    ecrire_image(sortie, dessin)


def commande_reconnaitre(args) -> int:
    import torch

    from moteur.oeil_dinov2 import charger
    from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre
    releve = json.loads(args.releve.read_text(encoding="utf-8"))
    logement = json.loads(args.logement.read_text(encoding="utf-8"))
    clf = Classifieur.depuis(torch.load(args.modele, weights_only=False))
    resultat = reconnaitre(releve, logement, RACINE, charger(clf.oeil), clf, journal=print)
    args.sortie.mkdir(parents=True, exist_ok=True)
    (args.sortie / "sols-reconnus.json").write_text(json.dumps(resultat["pieces"], ensure_ascii=False, indent=1), encoding="utf-8")
    dessiner_reconnaissance(resultat, logement, args.sortie / "sols-reconnus.png")
    for pid, s in resultat["pieces"].items():
        zones = ", ".join(f"{z['famille']} {z['surface_m2']} m²" for z in s["zones"])
        print(f"{pid} : {s['famille']} ({s['part']:.0%} des votes, {s['surface_vue_m2']} m² vus), couleur {s['couleur']}"
              + (f" ; zones : {zones}" if zones else ""))
    if args.verite:
        verite = json.loads(args.verite.read_text(encoding="utf-8"))
        visees = None
        if args.couleurs:
            choix = json.loads(args.couleurs.read_text(encoding="utf-8"))
            visees = {pid: c["couleur_visee"] for pid, c in choix["pieces"].items() if c.get("couleur_visee")}
        note = noter(resultat, verite, visees)
        (args.sortie / "note.json").write_text(json.dumps(note, ensure_ascii=False, indent=1), encoding="utf-8")
        print("NOTE :", json.dumps(note, ensure_ascii=False))
    print(f"Écrit : {args.sortie / 'sols-reconnus.png'}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Brique photos : sol vu de dessus depuis les photos du client")
    sous = ap.add_subparsers(dest="commande", required=True)
    a = sous.add_parser("a_plat")
    a.add_argument("releve", type=Path)
    a.add_argument("logement", type=Path)
    a.add_argument("sortie", type=Path)
    a.add_argument("--verite", type=Path)
    r = sous.add_parser("reconnaitre", help="reconnaître les sols et, avec --verite, noter")
    r.add_argument("releve", type=Path)
    r.add_argument("logement", type=Path)
    r.add_argument("modele", type=Path, help="classificateur appris (outils/habillage/apprendre_sols.py)")
    r.add_argument("sortie", type=Path)
    r.add_argument("--verite", type=Path, help="logement dont les pièces ont leur sol et leurs zones (la bonne réponse)")
    r.add_argument("--couleurs", type=Path, help="fichier de choix des sols avec « couleur_visee » (verites/app-001/sols.json)")
    args = ap.parse_args()
    for f in (args.releve, args.logement):
        if not f.is_file():
            print(f"PLANTÉ : fichier introuvable : {f}", flush=True)
            return 2
    if args.commande == "reconnaitre":
        return commande_reconnaitre(args)
    releve = json.loads(args.releve.read_text(encoding="utf-8"))
    logement = json.loads(args.logement.read_text(encoding="utf-8"))
    trio = photos_a_plat(releve, logement, RACINE)
    noms, vues = [n for n, _, _ in trio], [v for _, _, v in trio]
    image, finesse, choix = assembler(vues)
    origine = vues[0].origine
    (args.sortie / "a-plat").mkdir(parents=True, exist_ok=True)
    for v, nom in zip(vues, noms):
        ecrire_image(args.sortie / "a-plat" / f"{nom}.png", cv2.cvtColor(v.image, cv2.COLOR_RGB2BGR))
    np.savez_compressed(args.sortie / "sol-a-plat.npz", image=image, finesse=finesse, choix=choix,
                        origine=np.array(origine), resolution=RESOLUTION_M, noms=np.array(noms))
    dessin = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    dessin[finesse == 0] = (60, 60, 60)
    dessiner_contours(dessin, origine, RESOLUTION_M, [p["contour"] for p in logement["pieces"]], (0, 0, 255), 3)
    if args.verite:
        verite = json.loads(args.verite.read_text(encoding="utf-8"))
        for p in verite["pieces"].values():
            for z in p.get("zones", []):
                coul = (0, 220, 255) if "cubes" in z["matiere"] else (255, 150, 0)
                dessiner_contours(dessin, origine, RESOLUTION_M, [z["contour"]], coul, 2)
    ecrire_image(args.sortie / "sol-a-plat.png", dessin)
    vu = (finesse > 0).sum() * RESOLUTION_M ** 2
    total = sum(aire(p["contour"]) for p in logement["pieces"])
    print(f"Sol vu par au moins une photo : {vu:.1f} m² sur {total:.1f} m² ({100 * vu / total:.0f} %)")
    print(f"Écrit : {args.sortie / 'sol-a-plat.png'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
