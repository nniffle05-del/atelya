r"""SONDE (20/11/2026, fenêtres F1) : ce que chaque photo dit de la LARGEUR de chaque fenêtre du plan.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_largeur_fenetres.py [app-001 app-002 app-004]

Pour chaque rectangle « fenêtre », « porte-fenêtre », « rideaux » ou « voilage » lu sur une photo : la fenêtre du plan qu'il
montre, et son étendue le long du mur (rayons de ses deux bords, depuis la place de l'appareil), à côté de la largeur du plan.
Rien n'est écrit : on lit.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"

CHAINES = {"app-001": PC / "lectures-photos" / "rideaux-pans" / "chaine" / "app-001" / "c",
           "app-002": PC / "lectures-photos" / "parquet-sur-mesure" / "chaine-3" / "app-002" / "c",
           "app-004": PC / "lectures-photos" / "rideaux-pans" / "chaine" / "app-004" / "c"}
SORTES = ("fenetre", "porte_fenetre", "rideaux", "voilage")


def sonder(cas: str) -> None:
    from banc_ressemblance import CAS
    from moteur import equipements as eq
    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image
    from poser_photos_lues import objets_des_photos

    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement = json.loads((CHAINES[cas] / "logement-depart.json").read_text(encoding="utf-8"))
    objets_par_photo = objets_des_photos(fiche, PC / "lectures-photos" / cas)
    murs = {m["id"]: m for m in logement["murs"]}
    baies = []
    for o in logement["ouvertures"]:
        if o["type"] == "porte":
            continue
        r = eq.repere_de_la_baie(o, logement)
        if r is None:
            continue
        m = murs[o["mur"]]
        L = float(np.linalg.norm(np.asarray(m["fin"], float) - np.asarray(m["debut"], float)))
        r.update(type=o["type"], largeur=float(o["largeur"]), mur=o["mur"], long_mur=L, position=float(o["position"]))
        baies.append(r)
    print(f"\n=== {cas} : {len(baies)} baie(s) du plan")
    for b in baies:
        print(f"  {b['id']:5s} {b['type']:14s} largeur {b['largeur']:.2f} m, mur {b['mur']} de {b['long_mur']:.2f} m (de {b['position']:.2f} à {b['position'] + b['largeur']:.2f})")
    dossier, fichier = RACINE / fiche["photos"], fiche.get("fichier", "{nom}.png")
    for nom, d in fiche["cameras"].items():
        objets = [o for o in objets_par_photo.get(nom) or [] if o["sorte"] in SORTES]
        if not objets:
            continue
        image = lire_image(dossier / fichier.format(nom=nom))
        hauteur, largeur = image.shape[:2]
        cam = [float(c) for c in camera_depuis_dict(d["camera"])]
        for o in objets:
            x0, y0, x1, y1 = (float(v) for v in o["boite"])
            lignes = []
            for b in baies:
                if float((np.array(cam[:2]) - b["centre"]) @ b["n"]) < 0.05:
                    continue
                s = [eq._sur_le_mur(cam, u, (y0 + y1) / 2, b) for u in (x0, x1)]
                if None in s:
                    continue
                s0, s1 = sorted(s)
                if s1 < -b["demi"] - 1.0 or s0 > b["demi"] + 1.0:
                    continue
                # le mur de la baie est-il bien le premier que le rayon du milieu rencontre ? (distance au centre)
                dist = float(np.linalg.norm(np.array(cam[:2]) - b["centre"]))
                lignes.append(f"{b['id']} s [{s0:+.2f} … {s1:+.2f}] = {s1 - s0:.2f} m pour ±{b['demi']:.2f} (plan {b['largeur']:.2f}), à {dist:.1f} m")
            coupe = ("G" if x0 < 0.04 * largeur else "") + ("D" if x1 > 0.96 * largeur else "")
            print(f"  {nom} {o['sorte']:13s} « {(o.get('dit') or '')[:40]} » boîte {[int(v) for v in o['boite']]} coupée {coupe or '-'} "
                  f"{'MANQUANT' if o.get('manquant') else ''} | " + (" ; ".join(lignes) or "aucune baie"))


if __name__ == "__main__":
    for cas in sys.argv[1:] or ["app-001", "app-002", "app-004"]:
        sonder(cas)
