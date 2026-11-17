r"""Les traits du sol retenus par moteur/sens_des_lames.py, dessinés SUR LA PHOTO (17/11/2026) : pour vérifier à l'œil que le
sens lu est bien celui des joints du parquet (verts : traits dans le sens retenu ; rouges : dans l'autre sens des murs ;
gris : les autres).

    ..\atelya\.venv\Scripts\python.exe pc\verification\voir_traits_photo.py <sortie> <logement> <photo> [<photo> …]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol, sens_des_lames as sl  # noqa: E402
from moteur.camera_photo import camera_depuis_dict, projeter  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402


def main() -> int:
    sortie, cas, photos = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    sortie.mkdir(parents=True, exist_ok=True)
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement = json.loads(Path(CAS[cas]["logement"]).read_text(encoding="utf-8"))
    logement = logement.get("logement", logement)
    axes = sl.axes_du_logement(logement)
    pds = pas_du_sol.charger(avec_dino=False)
    for nom in photos:
        cam = camera_depuis_dict(fiche["cameras"][nom]["camera"])
        photo = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
        rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
        traits = sl.traits_du_sol(rgb, cam, logement, pds.masque(f"{cas}/{nom}", rgb))
        choix = sl.sens_parmi(traits, axes)
        for t in traits:
            ecart = lambda axe: abs((t["angle"] - axe + 90) % 180 - 90)
            couleur = (0, 200, 0) if choix and ecart(choix["sens"]) <= sl.ECART_AXE else (0, 0, 255) if choix and ecart(choix["sens"] + 90) <= sl.ECART_AXE else (160, 160, 160)
            (ua, va, _), (ub, vb, _) = projeter((*t["a"], 0.0), cam), projeter((*t["b"], 0.0), cam)
            cv2.line(photo, (int(ua), int(va)), (int(ub), int(vb)), couleur, 2, cv2.LINE_AA)
        print(nom, "cap", round(cam[3]), "choix", choix, "traits", len(traits))
        ecrire_image(sortie / f"traits-{cas}-{nom}.jpg", photo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
