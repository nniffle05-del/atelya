r"""SONDE (F2, 20/11/2026) : ce que chaque photo voit « par une fenêtre », en grand.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_profondeur_dehors.py <sortie> [app-004 [photo-09 …]]

Pour chaque fenêtre NON voilée de chaque photo : la photo recadrée sur le trou de la fenêtre (trait blanc = le trou d'après le
plan et la place de l'appareil), agrandie. Sert à regarder ce qui, dans ce trou, n'est PAS le dehors (rideaux, montants, battant
ouvert, garde-corps, marque de l'agence).

ESSAI ÉCARTÉ, MESURÉ LE 20/11/2026 : séparer le dehors par le RELIEF de la photo (MoGe-2). Le relief voit la vitre comme une
surface PLATE, à la distance du mur (27 photos des trois logements : 0 % du trou vu « loin » ; app-004 photo-10 : tout le trou
entre 3,5 et 4,1 m). Il ne distingue donc pas un immeuble d'en face d'un montant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import camera_photo, vue_dehors  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402

F1 = "../atelya/lectures-photos/fenetres-f1/chaine/{cas}/c/logement-meuble.json"
CAS = {
    "app-001": (F1, "verites/app-001/cameras-photos.json"),
    "app-002": (F1, "verites/app-002/cameras-photos.json"),
    "app-004": (F1, "../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json"),
}


def photo_de(fiche: dict, nom: str) -> Path | None:
    dossier = RACINE / fiche["photos"]
    modeles = [fiche["fichier"]] if fiche.get("fichier") else ["{nom}.png", "{nom}.jpg"]
    return next((dossier / m.format(nom=nom) for m in modeles if (dossier / m.format(nom=nom)).is_file()), None)


def main() -> int:
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    cas_voulus = [a for a in sys.argv[2:] if a.startswith("app-")] or list(CAS)
    photos_voulues = [a for a in sys.argv[2:] if a.startswith("photo-")]
    for cas in cas_voulus:
        logement = json.loads((RACINE / CAS[cas][0].format(cas=cas)).read_text(encoding="utf-8"))
        fiche = json.loads((RACINE / CAS[cas][1]).read_text(encoding="utf-8"))
        ouvertures = vue_dehors.ouvertures_vitrees(logement)
        murs = vue_dehors.murs_et_trous(logement)
        for nom, d in fiche["cameras"].items():
            chemin = photo_de(fiche, nom)
            if chemin is None or (photos_voulues and nom not in photos_voulues):
                continue
            bgr = lire_image(chemin)
            cam = camera_photo.camera_depuis_dict(d["camera"])
            h, w = bgr.shape[:2]
            for o in ouvertures:
                if o.get("voilee"):
                    continue
                _, trou = vue_dehors.masque_fenetres(cam, (w, h), [o], murs)
                if trou.sum() < 3000:
                    continue
                vs, us = np.nonzero(trou)
                m = 40
                x0, x1, y0, y1 = max(0, us.min() - m), min(w, us.max() + m), max(0, vs.min() - m), min(h, vs.max() + m)
                image = bgr.copy()
                contours, _ = cv2.findContours(trou, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(image, contours, -1, (255, 255, 255), 1)
                k = min(4.0, 900.0 / max(x1 - x0, y1 - y0))
                deux = [cv2.resize(i[y0:y1, x0:x1], None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC) for i in (bgr, image)]
                ecrire_image(sortie / f"{cas}-{nom}-{o['id']}.jpg", np.concatenate(deux, 1))
                print(f"{cas} {nom} {o['id']} : trou {int(trou.sum())} px, cadre [{x0}, {y0}, {x1}, {y1}], agrandi {k:.1f} fois", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
