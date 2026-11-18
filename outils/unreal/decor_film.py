"""Le DÉCOR du film d'un logement dans Unreal : ce qu'on voit par les fenêtres et autour (18/11/2026).

Un seul endroit décide de ce décor, pour le film entier (outils/unreal/balade_unreal.py) ET pour les vues de mesure prises depuis
la place des photos du client (outils/unreal/vues_photos_unreal.py, pc/verification/panoramique_lumiere.py). Pourquoi : jusqu'au
18/11/2026 les vues de mesure étaient tournées SANS la vue par les fenêtres, sans les balcons, avec la vitre d'origine : on jugeait
la lumière sur des images qui n'étaient pas celles du film livré (remarque de NT : « il n'y a plus de vue »).

Le décor :
- la VRAIE VUE par les fenêtres, tirée des photos du client (outils/unreal/vue_dehors_photos.py), aux moments de jour seulement,
  et la vitre claire qui va avec ;
- les BALCONS du plan ;
- à défaut de vraie vue : le ciel photographié de l'éclairage, posé sur l'image (moteur/cinema/ciels.py).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from moteur.cinema import ciels  # noqa: E402

STUDIO = Path("D:/Atelya-Unreal")
# La VRAIE VUE (étape 5, 13/11/2026) n'est posée qu'aux moments de JOUR : les photos d'annonce sont prises de jour.
MOMENTS_VUE = ("jour_soleil", "jour_voile")
BIBLIOTHEQUE_CIELS = RACINE.parent / "atelya" / "bibliotheque" / "ciels"


def ciel_photo(ambiance_id: str) -> dict | None:
    """Le ciel photographié de cet éclairage (moteur/cinema/ciels.py), copié au besoin dans un dossier SANS ACCENT pour Unreal."""
    reglage = ciels.ciel_photo(ambiance_id, (STUDIO / "Paquets" / "ciels").as_posix())
    if reglage is None:
        return None
    cible = Path(reglage["image"])
    if not cible.is_file():
        source = BIBLIOTHEQUE_CIELS / cible.name
        if not source.is_file():
            print(f"   (pas de ciel photographié : {source} absent)", flush=True)
            return None
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, cible)
    return reglage


def vues_par_les_fenetres(logement_json: Path, photos_json: Path | None, ambiance_id: str, dossier_vues: Path) -> list[dict]:
    """Les toiles de la vraie vue ([] hors des moments de jour, sans photos, ou si aucune photo ne voit dehors). <dossier_vues>
    doit être SANS ACCENT (Unreal y lit les images) et ne pas être effacé avant le rendu."""
    if not photos_json or ambiance_id not in MOMENTS_VUE:
        return []
    import vue_dehors_photos

    return vue_dehors_photos.preparer(Path(logement_json), Path(photos_json), Path(dossier_vues))


def reglage_du_decor(logement: dict, vues: list[dict], ambiance_id: str) -> dict:
    """Les réglages de la préparation Unreal (moteur/unreal/preparer_cinematique.py) qui posent ce décor."""
    return {"vues_dehors": vues, "verre_clair": bool(vues),
            # les BALCONS du plan (logement.json : balcons), construits dans la scène (13/11/2026)
            "balcons": logement.get("balcons", []), "hauteur_etage": logement.get("hauteur_sous_plafond", 2.5),
            # le ciel photographié est posé SUR L'IMAGE à la place de tout ce qui est « ciel » : il passait par-dessus la vraie vue
            # (translucide) et lui retirait ses couleurs (arbres gris, 13/11/2026) ; avec la vraie vue, pas de ciel photographié
            "ciel_photo": None if vues else ciel_photo(ambiance_id)}


def decor_du_film(logement_json: Path, photos_json: Path | None, ambiance_id: str, dossier_vues: Path) -> dict:
    """Tout le décor d'un coup, pour les vues de mesure : les mêmes réglages que le film entier."""
    logement = json.loads(Path(logement_json).read_text(encoding="utf-8"))
    vues = vues_par_les_fenetres(logement_json, photos_json, ambiance_id, dossier_vues)
    return reglage_du_decor(logement, vues, ambiance_id)
