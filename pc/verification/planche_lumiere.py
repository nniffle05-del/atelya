r"""POINT 2 (18/11/2026) : la planche AVANT / APRÈS de la lumière du film, pour NT.

    ..\atelya\.venv\Scripts\python.exe pc\verification\planche_lumiere.py <sortie> "titre 1=<sortie du juge 1>" ["titre 2=<…>" …]

Chaque <sortie du juge> est un dossier écrit par outils/unreal/juger_lumiere.py (cadres/<logement>/vue-<photo>.png = l'image du
film au cadre de la photo, lumiere.json = les mesures). Pour chaque logement : une ligne par photo, la photo du client puis
l'image du film de chaque essai, avec sous chaque image la couleur mesurée des murs et du sol. Les titres sont écrits sans
accents (police d'OpenCV). Écrit <sortie>/planche-<logement>.jpg.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))

from banc_ressemblance import CAS  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402

LARGEUR = 620


def pastilles(d: dict | None, largeur: int) -> np.ndarray:
    bande = np.full((46, largeur, 3), 255, np.uint8)
    x = 4
    for nom in ("murs", "sol"):
        c = (d or {}).get(nom)
        if not c:
            continue
        bande[6:40, x:x + 54] = c["rgb"][::-1]
        cv2.rectangle(bande, (x, 6), (x + 54, 40), (150, 150, 150), 1)
        cv2.putText(bande, f"{nom} : clarte {c['L']:.0f}", (x + 60, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(bande, f"vivacite {c['C']:.0f}", (x + 60, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (90, 90, 90), 1, cv2.LINE_AA)
        x += 210
    return bande


def main() -> int:
    sortie = Path(sys.argv[1])
    essais = [(a.split("=", 1)[0], Path(a.split("=", 1)[1])) for a in sys.argv[2:]]
    if not essais:
        print(__doc__)
        return 1
    sortie.mkdir(parents=True, exist_ok=True)
    bilans = [json.loads((d / "lumiere.json").read_text(encoding="utf-8")) for _, d in essais]
    for cas in CAS:
        noms = [n for n in bilans[0].get(cas, {}) if all(n in b.get(cas, {}) for b in bilans)]
        if not noms:
            continue
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        colonnes = ["la photo du client (le modele)"] + [t for t, _ in essais]
        titre = np.full((40, (LARGEUR + 8) * len(colonnes), 3), 255, np.uint8)
        for k, t in enumerate(colonnes):
            cv2.putText(titre, t, (k * (LARGEUR + 8) + 4, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 2, cv2.LINE_AA)
        lignes = [titre]
        for nom in noms:
            photo = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
            h = int(round(photo.shape[0] * LARGEUR / photo.shape[1]))
            images = [photo] + [lire_image(d / "cadres" / cas / f"vue-{nom}.png") for _, d in essais]
            mesures = [bilans[0][cas][nom]["photo"]] + [b[cas][nom]["film"] for b in bilans]
            blocs = []
            for image, m in zip(images, mesures):
                bloc = np.concatenate([cv2.resize(image, (LARGEUR, h), interpolation=cv2.INTER_AREA), pastilles(m, LARGEUR)], 0)
                blocs += [bloc, np.full((bloc.shape[0], 8, 3), 255, np.uint8)]
            bandeau = np.full((24, (LARGEUR + 8) * len(colonnes), 3), 255, np.uint8)
            cv2.putText(bandeau, f"{cas}  {nom}  ({bilans[0][cas][nom]['piece']})", (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA)
            lignes += [bandeau, np.concatenate(blocs, 1)]
        ecrire_image(sortie / f"planche-{cas}.jpg", np.concatenate(lignes, 0))
        print(f"planche : {sortie / f'planche-{cas}.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
