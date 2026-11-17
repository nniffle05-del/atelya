r"""La HAUTEUR SOUS PLAFOND estimée d'après les photos du client, quand le plan ne l'écrit pas.

Pourquoi (examen app-004, 15/11/2026) : beaucoup de plans d'annonce n'écrivent pas la hauteur sous plafond et le client ne la
connaît pas ; sans elle Atelya prenait 2,50 m partout. Or les photos la montrent : MoGe-2 (moteur.moge) donne chaque point
d'une photo en mètres ; sur une photo où l'on voit le sol ET le plafond, l'écart entre les deux est la hauteur de la pièce.
C'est la mesure déjà faite à la main pour app-003 (médiane des photos, 2,90 m) ; ici elle devient une étape de la chaîne
(jointure « photos → hauteur », appelée par outils/lecture_claude/traduire_fiche.py --photos).

Méthode (fixée AVANT de regarder app-004, contrôlée sur app-001 dont le plan écrit « HSP 3m ») : par photo, le sol et le
plafond sont les deux grandes surfaces horizontales (mêmes règles que moteur.caler_photos.repere) ; on garde les photos où
les deux se voient et dont la hauteur est vraisemblable ; la hauteur du logement est la MÉDIANE, arrondie à 5 cm. Moins de
PHOTOS_MIN photos utilisables : pas d'estimation (None), la hauteur par défaut reste.

Précision connue : MoGe-2 retrouve la hauteur à environ 4 % près en médiane (22 photos d'app-001 et app-002, 13/11/2026).

Version 0.1.0 (15/11/2026).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

VERSION = "0.1.0"
PHOTOS_MIN = 3  # en dessous, la médiane ne veut rien dire
VRAISEMBLABLE = (2.1, 4.5)  # m : une hauteur de pièce hors de là est une erreur de mesure (mezzanine, photo de détail…)
ARRONDI = 0.05  # m


def hauteur_d_une_photo(mesure: dict) -> float | None:
    """L'écart sol → plafond (m) d'une photo mesurée par moteur.caler_photos.mesurer ; None si l'un des deux ne se voit pas."""
    from moteur.caler_photos import _pic

    h = mesure["points"] @ mesure["haut"]
    horiz = mesure["masque"] & (np.abs(mesure["normales"] @ mesure["haut"]) > 0.95)
    sol, plaf = _pic(h[horiz & (h < -0.4)]), _pic(h[horiz & (h > 0.3)])
    if sol is None or plaf is None:
        return None
    return float(plaf - sol)


def estimer(photos: dict[str, np.ndarray], modele_moge=None, journal=None) -> dict:
    """La hauteur sous plafond d'après les photos ({nom: image RGB}).

    Rend {"hauteur": mètres ou None, "photos": {nom: hauteur ou None}, "gardees": nombre de photos utilisées}."""
    from moteur import moge
    from moteur.caler_photos import mesurer

    modele = modele_moge or moge.charger()
    par_photo = {}
    for nom, rgb in photos.items():
        v = hauteur_d_une_photo(mesurer(modele, rgb))
        par_photo[nom] = round(v, 3) if v is not None else None
    bonnes = [v for v in par_photo.values() if v is not None and VRAISEMBLABLE[0] <= v <= VRAISEMBLABLE[1]]
    hauteur = round(round(float(np.median(bonnes)) / ARRONDI) * ARRONDI, 2) if len(bonnes) >= PHOTOS_MIN else None
    if journal:
        journal(f"Hauteur sous plafond d'après les photos : {hauteur if hauteur else 'non estimée'} "
                f"({len(bonnes)} photos utilisables sur {len(photos)})")
    return {"hauteur": hauteur, "photos": par_photo, "gardees": len(bonnes), "version": VERSION}


def estimer_dossier(dossier: Path, journal=None) -> dict:
    """Comme `estimer`, sur le dossier des photos du client (mêmes fichiers que le calage des photos)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils" / "habillage"))
    from caler_photos_seul import lire_photos

    photos, _ = lire_photos(Path(dossier))
    return estimer(photos, journal=journal)


if __name__ == "__main__":
    import json
    import sys

    r = estimer_dossier(Path(sys.argv[1]), journal=lambda *a: print(*a, flush=True))
    if "--detail" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
