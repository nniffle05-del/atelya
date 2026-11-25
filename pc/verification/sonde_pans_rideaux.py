r"""SONDE (19/11/2026, rideaux 2e temps) : ce que chaque photo dit des PANS de rideaux de chaque fenêtre.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_pans_rideaux.py [app-001 app-004 …]

Pour chaque rectangle « rideaux » lu sur une photo : la fenêtre du plan qu'il habille, et de quel côté de cette fenêtre il
pend, mesuré de deux façons (dans l'image, contre le rectangle de la fenêtre lu sur la même photo ; sur le mur du plan, par
les rayons des deux bords du rectangle). Puis ce qu'Atelya en conclut par fenêtre (moteur.equipements.pans_des_fenetres).
Rien n'est écrit : on lit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"

CHAINES = {"app-001": PC / "lectures-photos" / "voilages" / "chaine" / "app-001" / "c",
           "app-002": PC / "lectures-photos" / "parquet-sur-mesure" / "chaine-3" / "app-002" / "c",
           "app-004": PC / "lectures-photos" / "voilages" / "chaine" / "app-004" / "c"}


def sonder(cas: str) -> None:
    import cv2

    from banc_ressemblance import CAS
    from moteur import caler_photos as cp
    from moteur import equipements as eq
    from moteur import moge
    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image
    from poser_photos_lues import objets_des_photos

    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement = json.loads((CHAINES[cas] / "logement-sols.json").read_text(encoding="utf-8"))
    objets_par_photo = objets_des_photos(fiche, PC / "lectures-photos" / cas)
    plan = cp.plan_du_logement(logement)
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    modele = moge.charger()
    dossier, fichier = RACINE / fiche["photos"], fiche.get("fichier", "{nom}.png")
    vues = []
    for k, (nom, d) in enumerate(fiche["cameras"].items()):
        objets = objets_par_photo.get(nom) or []
        if not any(o["sorte"] == "rideaux" for o in objets):
            continue
        rgb = cv2.cvtColor(lire_image(dossier / fichier.format(nom=nom)), cv2.COLOR_BGR2RGB)
        hauteur, largeur = rgb.shape[:2]
        cam = camera_depuis_dict(d["camera"])
        repere = cp.repere(cp.mesurer(modele, rgb, float(d["camera"]["f"])), hsp)
        de_la_photo = eq.vues_d_une_photo(objets, cam, d["camera"], plan, repere, largeur, hauteur, logement, rgb, photo=k)
        for v in de_la_photo:
            if v["sorte"] in ("rideaux", "voilage"):
                v["nom_photo"] = nom
                vues.append(v)
    print(f"\n=== {cas} : {len(vues)} vue(s) de rideaux")
    sortie = eq.rideaux_des_fenetres([v for v in vues if v.get("point")], logement, lambda e, r: print("   refusé :", e.get("dit"), r))
    for v in vues:
        p = v.get("pan") or {}
        print(f"  {v['nom_photo']} {v['sorte']:8s} boîte {[int(b) for b in v['boite']]} point {None if v['point'] is None else [round(c, 2) for c in v['point']]}"
              f" | fenêtre {p.get('fenetre')} | côté {p.get('cote')} (par {p.get('par')}) | s {None if not p.get('s') else [round(x, 2) for x in p['s']]}"
              f" | autre côté visible : {p.get('autre_cote_visible')}")
    for ident, r in sortie.items():
        print(f"  → fenêtre {ident} : voilage {r['voilage']} rideaux {r['rideaux']} pans {r.get('pans')}")


if __name__ == "__main__":
    for cas in sys.argv[1:] or ["app-001", "app-004"]:
        sonder(cas)
