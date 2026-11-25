r"""SONDE (22/11/2026, rideaux 2e temps, étape b) : la LARGEUR de chaque pan de rideau, et où il pend par rapport à sa fenêtre.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_largeur_pans.py [app-001 app-004 …]

Pour chaque rectangle « rideaux » lu sur une photo : ses deux bords reportés sur le mur (m, depuis le milieu de la fenêtre du
plan), les deux bords de la fenêtre lue sur la MÊME photo reportés de même, et ce que moteur.equipements.pan_d_une_vue en
tire (largeur, recouvrement de la baie, bords coupés ou cachés). Puis les pans retenus par fenêtre. Rien n'est écrit : on lit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "pc" / "verification"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def vues_des_rideaux(cas: str, logement: dict | None = None):
    """(logement, vues « rideaux » et « voilage » de toutes les photos du logement), comme la chaîne les calcule."""
    import cv2

    from banc_ressemblance import CAS
    from moteur import caler_photos as cp
    from moteur import equipements as eq
    from moteur import moge
    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image
    from poser_photos_lues import objets_des_photos
    from sonde_pans_rideaux import CHAINES, PC

    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    if logement is None:
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
        for v in eq.vues_d_une_photo(objets, cam, d["camera"], plan, repere, largeur, hauteur, logement, rgb, photo=k):
            if v["sorte"] in ("rideaux", "voilage"):
                v["nom_photo"] = nom
                vues.append(v)
    return logement, vues


def sonder(cas: str) -> None:
    from moteur import equipements as eq

    logement, vues = vues_des_rideaux(cas)
    sortie = eq.rideaux_des_fenetres([v for v in vues if v.get("point")], logement)
    ouvertures = {o["id"]: o for o in logement["ouvertures"]}
    print(f"\n=== {cas}")
    for v in vues:
        p = v.get("pan")
        if not p:
            continue
        baie = eq.repere_de_la_baie(ouvertures[p["fenetre"]], logement)
        x0, y0, x1, y1 = v["boite"]
        fen = []
        for fx0, fy0, fx1, fy1 in v.get("baies_vues") or []:
            s = [eq._sur_le_mur(v["appareil"], u, (fy0 + fy1) / 2, baie, 0.0) for u in (fx0, fx1)]
            fen.append(([int(fx0), int(fx1)], None if None in s else [round(x, 2) for x in sorted(s)]))
        arrondi = lambda x: None if x is None else round(x, 2)
        print(f"  {v['nom_photo']} → {p['fenetre']} (demi {baie['demi']:.2f}) boîte x {int(x0)}-{int(x1)} y {int(y0)}-{int(y1)} | côté {p.get('cote')} par {p.get('par')}"
              f" | s {None if not p.get('s') else [round(x, 2) for x in p['s']]} | fenêtres vues {fen}"
              f" | largeur {arrondi(p.get('largeur'))} sûre {p.get('largeur_sure')} | recouvre {arrondi(p.get('recouvre'))} | dit {v.get('dit')!r}")
    for ident, r in sortie.items():
        print(f"  → fenêtre {ident} : pans {r.get('pans')}")


if __name__ == "__main__":
    for cas in sys.argv[1:] or ["app-001", "app-004"]:
        sonder(cas)
