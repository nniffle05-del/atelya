r"""Ce que valent les photos CALÉES SEULES pour les sols et les meubles, sur les examens DÉJÀ VUS app-001 et app-002.

    ..\atelya\.venv\Scripts\python.exe outils\habillage\essai_calage_seul.py ..\atelya\b2\cameras-seules\service

Trois fiches comparées, mêmes briques (sols : moteur/reconnaitre_sols + « pas du sol » ; meubles : OWLv2), même notation que
non_recul_examens.py :
  « main »         : toutes les photos, calées à la main (les notes connues : sols 83,6 % / 87,9 %, meubles 25/34 et 22/30) ;
  « main, sûres »  : calées à la main, mais seulement les photos qu'Atelya juge sûres (ce que coûte d'avoir moins de photos) ;
  « seul »         : les photos sûres, calées par Atelya seul (moteur/caler_photos.py) : ce qui sera en service.
Les meubles sont toujours notés contre ce que TOUTES les photos montrent (caméras de la main).
La couche des fenêtres a été apprise sur ces deux logements : ici on donne à la chaîne les cartes apprises sans le logement
noté (..\atelya\b2\cameras-seules\aspect), pour ne pas se flatter.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from caler_photos_seul import fiche  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.oeil_dinov2 import charger as charger_oeil  # noqa: E402
from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre  # noqa: E402
from moteur.reperer_meubles import noter_meubles, reperer_depuis_releve  # noqa: E402
from non_recul_examens import EXAMENS, PC, RACINE, lire  # noqa: E402


def main() -> int:
    sortie = Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    outils = cp.Outils()
    clf_sols = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
    oeil = charger_oeil("vits14")
    pds = outils.pds
    bilan = {}
    for nom, f in EXAMENS.items():
        for k in ("releve", "logement", "verite_sols", "meubles"):
            if not f[k].is_file():
                print(f"PLANTÉ : fichier introuvable : {f[k]}", flush=True)
                return 2
        main_, logement = lire(f["releve"]), lire(f["logement"])
        dossier = RACINE / main_["photos"]; modele = main_.get("fichier", "{nom}.png")
        photos = {n: cv2.cvtColor(lire_image(dossier / modele.format(nom=n)), cv2.COLOR_BGR2RGB) for n in main_["cameras"]}
        cartes = {n: np.load(PC / "b2/cameras-seules/aspect" / f"{nom}-{n}.npy")[..., 2].astype(np.float32) for n in photos
                  if (PC / "b2/cameras-seules/aspect" / f"{nom}-{n}.npy").is_file()}
        print(f"{nom} : calage seul de {len(photos)} photos ({len(cartes)} cartes de fenêtres toutes faites)", flush=True)
        seul = fiche(cp.caler(logement, photos, outils, journal=lambda *a: None, fenetres_de=cartes), dossier, modele)
        (sortie / f"{nom}-cameras-seul.json").write_text(json.dumps(seul, ensure_ascii=False, indent=1), encoding="utf-8")
        sures = list(seul["cameras"])
        fiches = {"main": main_, "main, sûres": {**main_, "cameras": {n: main_["cameras"][n] for n in sures}}, "seul": seul}
        logement_sans_sols = json.loads(json.dumps(logement))
        for p in logement_sans_sols["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        verite_sols, verite_meubles = lire(f["verite_sols"]), lire(f["meubles"])["meubles"]
        cams = [camera_depuis_dict(d["camera"]) for d in main_["cameras"].values()]
        b = {"photos": len(photos), "sures": sures}
        for quoi, releve in fiches.items():
            note = noter(reconnaitre(releve, logement_sans_sols, RACINE, oeil, clf_sols, pas_du_sol=lambda n, rgb: pds.masque(f"{nom}/{n}", rgb)), verite_sols)
            trouves = reperer_depuis_releve(releve, logement, RACINE, owl=pds.owl)
            m = noter_meubles(trouves, verite_meubles, cameras=cams, logement=logement)
            b[quoi] = {"sols": {k: note.get(k) for k in ("surface_jugee_m2", "surface_juste", "pieces_justes")}, "meubles": m}
            print(f"{nom} [{quoi:11s}] {len(releve['cameras']):2d} photos | sols : {note.get('surface_juste')} justes sur {note.get('surface_jugee_m2')} m² jugés "
                  f"({note.get('pieces_justes')}) | meubles : {m}", flush=True)
        bilan[nom] = b
    (sortie / "bilan-calage-seul.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
