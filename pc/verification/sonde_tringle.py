r"""SONDE (23/11/2026, rideaux 2e temps, étape c) : la HAUTEUR et la COULEUR de la tringle d'après les photos.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_tringle.py [app-001 app-004 …] [--images <dossier>]

Pour chaque rectangle « rideaux » ou « voilage » lu sur une photo : la hauteur de son haut dans le relief de la photo (remis
entre le sol et le plafond de la pièce), la tringle cherchée dans l'image à côté de lui (un trait fin qui passe par le haut du
tissu), sa couleur et celle du mur autour. Puis ce que moteur.equipements.tringle_d_une_fenetre retient par fenêtre.
Avec --images : chaque photo avec le trait trouvé dessiné dessus (à REGARDER). Rien d'autre n'est écrit.
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


def vues_des_tringles(cas: str, logement: dict | None = None):
    """(logement, vues « rideaux » et « voilage » de toutes les photos, {nom de photo : image RGB}), comme la chaîne."""
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
    vues, images = [], {}
    for k, (nom, d) in enumerate(fiche["cameras"].items()):
        objets = objets_par_photo.get(nom) or []
        if not any(o["sorte"] == "rideaux" for o in objets):
            continue
        rgb = cv2.cvtColor(lire_image(dossier / fichier.format(nom=nom)), cv2.COLOR_BGR2RGB)
        hauteur, largeur = rgb.shape[:2]
        cam = camera_depuis_dict(d["camera"])
        repere = cp.repere(cp.mesurer(modele, rgb, float(d["camera"]["f"])), hsp)
        images[nom] = rgb
        for v in eq.vues_d_une_photo(objets, cam, d["camera"], plan, repere, largeur, hauteur, logement, rgb, photo=k):
            if v["sorte"] in ("rideaux", "voilage"):
                v["nom_photo"] = nom
                vues.append(v)
    return logement, vues, images


def sonder(cas: str, images_vers: Path | None) -> None:
    import cv2

    from moteur import equipements as eq
    from moteur.images import ecrire_image

    logement, vues, images = vues_des_tringles(cas)
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    sortie = eq.rideaux_des_fenetres([v for v in vues if v.get("point")], logement)
    print(f"\n=== {cas} (hauteur sous plafond {hsp:.2f} m)")
    dessins = {nom: cv2.cvtColor(img, cv2.COLOR_RGB2BGR) for nom, img in images.items()}
    for v in vues:
        t = v.get("tringle")
        if t is None:
            continue
        x0, y0, x1, y1 = v["boite"]
        arrondi = lambda x: None if x is None else round(float(x), 2)
        trait = t.get("trait")
        print(f"  {v['nom_photo']} {v['sorte']:8s} boîte x {int(x0)}-{int(x1)} y {int(y0)}-{int(y1)} | haut du tissu {arrondi(t.get('haut'))} m"
              f" | trait {None if not trait else [int(c) for c in trait['a'] + trait['b']]} force {arrondi(trait and trait['force'])}"
              f" | hauteur {arrondi(t.get('hauteur'))} m | couleur {t.get('couleur')} mur {t.get('mur')} clarté {arrondi(t.get('clarte'))}")
        if trait:
            a, b = trait["a"], trait["b"]
            cv2.line(dessins[v["nom_photo"]], (int(a[0]), int(a[1]) - 6), (int(b[0]), int(b[1]) - 6), (0, 0, 255), 1)
            cv2.line(dessins[v["nom_photo"]], (int(a[0]), int(a[1]) + 6), (int(b[0]), int(b[1]) + 6), (0, 0, 255), 1)
        cv2.rectangle(dessins[v["nom_photo"]], (int(x0), int(y0)), (int(x1), int(y1)), (0, 200, 0), 1)
    for ident, r in sortie.items():
        print(f"  → fenêtre {ident} : tringle {r.get('tringle')}")
    if images_vers:
        images_vers.mkdir(parents=True, exist_ok=True)
        for nom, img in dessins.items():
            ecrire_image(images_vers / f"{cas}-{nom}.jpg", img)


if __name__ == "__main__":
    args = sys.argv[1:]
    vers = None
    if "--images" in args:
        k = args.index("--images")
        vers = Path(args[k + 1])
        del args[k:k + 2]
    for cas in args or ["app-001", "app-004"]:
        sonder(cas, vers)
