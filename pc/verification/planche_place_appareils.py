r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : la planche « photo | film avant | film après », en plein cadre, pour NT.

    ..\atelya\.venv\Scripts\python.exe pc\verification\planche_place_appareils.py <sortie> <logement> <fiche des photos> \
        "titre 1=<dossier des vues 1>" "titre 2=<dossier des vues 2>" … [--photos photo-09 photo-10]

Les dossiers des vues sont ceux d'outils/unreal/vues_photos_unreal.py (vue-<photo>.png, l'image du film AU CADRE de la photo).
Pour chaque photo présente dans au moins un dossier : la photo du client puis l'image du film de chaque dossier, à la même
taille ; une case reste grise quand la vue manque. Trois traits horizontaux fins, aux mêmes hauteurs sur toutes les cases,
aident l'œil à comparer la place des murs et des fenêtres. Titres sans accents (police d'OpenCV).
Écrit <sortie>/<logement>-<photo>.jpg et <sortie>/planche-<logement>.jpg.
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

from moteur.images import ecrire_image, lire_image  # noqa: E402

LARGEUR = 640


def case(image: np.ndarray | None, titre: str, hauteur: int) -> np.ndarray:
    c = np.full((hauteur, LARGEUR, 3), 90, np.uint8) if image is None else cv2.resize(image, (LARGEUR, hauteur), interpolation=cv2.INTER_AREA)
    for part in (0.25, 0.5, 0.75):  # repères pour l'œil : les mêmes hauteurs sur toutes les cases
        cv2.line(c, (0, int(hauteur * part)), (LARGEUR, int(hauteur * part)), (0, 220, 255), 1, cv2.LINE_AA)
    cv2.rectangle(c, (0, 0), (LARGEUR, 26), (0, 0, 0), -1)
    cv2.putText(c, titre, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return c


def main() -> int:
    args = [a for a in sys.argv[1:]]
    photos = args[args.index("--photos") + 1:] if "--photos" in args else None
    args = args[:args.index("--photos")] if "--photos" in args else args
    sortie, logement, fiche = Path(args[0]), args[1], json.loads(Path(args[2]).read_text(encoding="utf-8"))
    dossiers = [(a.split("=", 1)[0], Path(a.split("=", 1)[1])) for a in args[3:]]
    dossier_photos = RACINE / str(fiche["photos"])
    modele = fiche.get("fichier", "{nom}.png")
    noms = photos or sorted({p.stem[4:] for _, d in dossiers for p in d.glob("vue-photo-*.png")})
    sortie.mkdir(parents=True, exist_ok=True)
    lignes = []
    for nom in noms:
        photo = lire_image(dossier_photos / modele.format(nom=nom))
        if photo is None:
            print(f"PLANTÉ : photo introuvable : {dossier_photos / modele.format(nom=nom)}", flush=True)
            return 2
        hauteur = int(round(photo.shape[0] * LARGEUR / photo.shape[1]))
        cases = [case(photo, f"{logement} {nom} : la photo du client", hauteur)]
        for titre, d in dossiers:
            f = d / f"vue-{nom}.png"
            cases.append(case(lire_image(f) if f.is_file() else None, titre, hauteur))
        ligne = np.hstack(cases)
        ecrire_image(sortie / f"{logement}-{nom}.jpg", ligne)
        lignes.append(ligne)
    if not lignes:
        print("PLANTÉ : aucune vue trouvée", flush=True)
        return 2
    largeur = max(l.shape[1] for l in lignes)
    planche = np.vstack([np.pad(l, ((0, 6), (0, largeur - l.shape[1]), (0, 0)), constant_values=255) for l in lignes])
    ecrire_image(sortie / f"planche-{logement}.jpg", planche)
    print(f"{len(lignes)} photo(s) : {sortie / f'planche-{logement}.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
