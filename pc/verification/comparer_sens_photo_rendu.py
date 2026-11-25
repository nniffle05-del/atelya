r"""LE JUGE DU SENS DES LAMES (17/11/2026, NT : « je veux que le sens soit le même ») : le sens des lames mesuré sur chaque
PHOTO et sur le RENDU de la maquette fait du même endroit (même mesure : moteur/sens_des_lames.py), pièce par pièce.

    ..\atelya\.venv\Scripts\python.exe pc\verification\comparer_sens_photo_rendu.py app-001=<dossier des rendus> [app-002=… …]

Pour chaque photo et chaque pièce où les deux se mesurent : « même sens » ou « SENS DIFFÉRENT ».
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol, sens_des_lames as sl  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402

NOTE_MIN = 1.5  # m de joints comptés, sur une seule image, pour qu'un sens soit dit


def par_piece(image_bgr, cam, logement, masque, axes) -> dict:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    traits: dict[str, list] = {}
    for t in sl.traits_du_sol(rgb, cam, logement, masque(rgb) if masque else None):
        traits.setdefault(t["piece"], []).append(t)
    sortie = {}
    for pid, ts in traits.items():
        c = sl.sens_parmi(ts, axes)
        if c and c["note"] >= NOTE_MIN and c["note"] >= 2 * c["autre"]:
            sortie[pid] = c
    return sortie


def main() -> int:
    pds = pas_du_sol.charger(avec_dino=False)
    memes = differents = 0
    for demande in sys.argv[1:]:
        cas, dossier = demande.split("=", 1)
        fiche, logement = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8")), json.loads(Path(CAS[cas]["logement"]).read_text(encoding="utf-8"))
        logement = logement.get("logement", logement)
        axes = sl.axes_du_logement(logement)
        for nom, d in fiche["cameras"].items():
            rendu = Path(dossier) / f"vue-{nom}.png"
            if not rendu.is_file():
                continue
            cam = camera_depuis_dict(d["camera"])
            photo = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
            image = lire_image(rendu)
            if image.shape[:2] != photo.shape[:2]:
                image = cv2.resize(image, (photo.shape[1], photo.shape[0]))
            sur_photo = par_piece(photo, cam, logement, lambda rgb, cle=f"{cas}/{nom}": pds.masque(cle, rgb), axes)
            sur_rendu = par_piece(image, cam, logement, None, axes)
            for pid in sorted(set(sur_photo) | set(sur_rendu)):
                p, r = sur_photo.get(pid), sur_rendu.get(pid)
                if p and r:
                    meme = p["sens"] == r["sens"]
                    memes += meme
                    differents += not meme
                    print(f"{cas} {nom} {pid:12s} photo {p['sens']:.0f}° ({p['note']} contre {p['autre']}) | maquette {r['sens']:.0f}° ({r['note']} contre {r['autre']}) | "
                          + ("même sens" if meme else "SENS DIFFÉRENT"))
                elif p:
                    print(f"{cas} {nom} {pid:12s} photo {p['sens']:.0f}° ({p['note']} contre {p['autre']}) | maquette : sens non mesurable sur le rendu")
    print(f"BILAN : même sens {memes}, sens différent {differents}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
