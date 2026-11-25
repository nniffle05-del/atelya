r"""F2 (20/11/2026) : la planche « photo | film avant | film après », RECADRÉE SUR LES FENÊTRES, pour juger la vue dans le film.

    ..\atelya\.venv\Scripts\python.exe pc\verification\planche_vue_propre.py <sortie> <logement> <logement.json> <cameras.json> \
        <dossier des vues avant> <dossier des vues après> [photo-09 photo-10 …]

Les dossiers des vues sont ceux d'outils/unreal/vues_photos_unreal.py (vue-<photo>.png, au cadre de la photo) ou les « cadres »
du juge de la lumière. Pour chaque photo présente des deux côtés (ou seulement « après », la colonne « avant » reste vide) :
la photo du client, l'image du film d'avant, celle d'après, recadrées autour des fenêtres que la photo montre. Une image par
photo (<sortie>/<logement>-<photo>.jpg) et une planche d'ensemble (<sortie>/planche-<logement>.jpg). Titres sans accents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import camera_photo, vue_dehors  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from preparer_vitrages import photo_de  # noqa: E402

HAUT = 620
MARGE = 0.35  # part de la taille des fenêtres gardée autour d'elles


def main() -> int:
    if len(sys.argv) < 7:
        print(__doc__)
        return 1
    sortie, cas = Path(sys.argv[1]), sys.argv[2]
    logement = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    fiche = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    avant, apres = Path(sys.argv[5]), Path(sys.argv[6])
    voulues = sys.argv[7:]
    sortie.mkdir(parents=True, exist_ok=True)
    ouvertures, murs = vue_dehors.ouvertures_vitrees(logement), vue_dehors.murs_et_trous(logement)
    lignes = []
    for nom, d in fiche["cameras"].items():
        if (voulues and nom not in voulues) or not (apres / f"vue-{nom}.png").is_file():
            continue
        photo = lire_image(photo_de(fiche, Path(sys.argv[4]).parent, nom))
        h, w = photo.shape[:2]
        _, trou = vue_dehors.masque_fenetres(camera_photo.camera_depuis_dict(d["camera"]), (w, h), ouvertures, murs)
        if trou.sum() < 1500:
            continue
        vs, us = np.nonzero(trou)
        mx, my = int((us.max() - us.min()) * MARGE) + 30, int((vs.max() - vs.min()) * MARGE) + 30
        x0, x1, y0, y1 = max(0, us.min() - mx), min(w, us.max() + mx), max(0, vs.min() - my), min(h, vs.max() + my)
        k = HAUT / (y1 - y0)
        cellules = []
        for titre, image in (("la photo du client", photo),
                             ("le film, avant", lire_image(avant / f"vue-{nom}.png") if (avant / f"vue-{nom}.png").is_file() else None),
                             ("le film, apres", lire_image(apres / f"vue-{nom}.png"))):
            if image is None:
                c = np.full((HAUT, int((x1 - x0) * k), 3), 235, np.uint8)
                cv2.putText(c, "(pas filme avant)", (10, HAUT // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1, cv2.LINE_AA)
            else:
                if image.shape[:2] != (h, w):
                    image = cv2.resize(image, (w, h), interpolation=cv2.INTER_AREA)
                c = cv2.resize(image[y0:y1, x0:x1], (int((x1 - x0) * k), HAUT), interpolation=cv2.INTER_CUBIC)
            bande = np.full((34, c.shape[1], 3), 255, np.uint8)
            cv2.putText(bande, titre, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 2, cv2.LINE_AA)
            cellules += [np.concatenate([bande, c], 0), np.full((HAUT + 34, 8, 3), 255, np.uint8)]
        ligne = np.concatenate(cellules[:-1], 1)
        nomme = np.full((26, ligne.shape[1], 3), 255, np.uint8)
        cv2.putText(nomme, f"{cas}  {nom}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA)
        ligne = np.concatenate([nomme, ligne], 0)
        ecrire_image(sortie / f"{cas}-{nom}.jpg", ligne)
        lignes.append(ligne)
        print(f"{cas} {nom} : {sortie / f'{cas}-{nom}.jpg'}", flush=True)
    if lignes:
        large = max(l.shape[1] for l in lignes)
        lignes = [np.pad(l, ((0, 0), (0, large - l.shape[1]), (0, 0)), constant_values=255) for l in lignes]
        ecrire_image(sortie / f"planche-{cas}.jpg", np.concatenate(lignes, 0))
        print(f"planche : {sortie / f'planche-{cas}.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
