r"""LES PHOTOS LUES, POSÉES DANS LE LOGEMENT (essai du 16/11/2026, accord de NT ; rien de ceci n'est en service).

    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\poser_photos_lues.py <fiche cameras-photos.json> <logement.json> ^
        <logement écrit> <dossier de la lecture> [--detecteur]

Pourquoi : dans la chaîne (outils/atelya/de_l_ecran_au_film.py --lecture-photos), cette commande remplace le repérage des meubles
(outils/habillage/reperer_meubles_photos.py). Le dossier de la lecture contient `lecture.json` (ce que Claude a compris de chaque
photo, moteur/lecture_photos.py) et `envoi\<photo>.json` (les rectangles numérotés qu'Atelya lui a montrés). Atelya pose ce qui
est lu (moteur/photos_lues.py) : meubles au sol, luminaires suspendus, objets au mur, et les ÉQUIPEMENTS du logement
(moteur/equipements.py : cheminée, radiateurs, cuisine, salle de bains, rideaux, passe-plat). Ce qui a été posé, et ce qui ne l'a
pas été (avec la raison), est écrit dans <logement écrit>.equipements.json.

--sans-equipements : comme avant le 16/11/2026, les équipements sont seulement comptés.

--detecteur : les MÊMES rectangles, avec la sorte que le détecteur leur donne (sans lecture) — la référence de l'essai.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur import lecture_photos as lp  # noqa: E402
from moteur import photos_lues  # noqa: E402


def objets_des_photos(fiche: dict, dossier: Path, detecteur: bool = False) -> dict[str, list[dict]]:
    """Pour chaque photo placée de la fiche : ses objets avec leur sorte (lue, ou celle du détecteur)."""
    lecture = None if detecteur else json.loads((dossier / "lecture.json").read_text(encoding="utf-8"))
    sortie = {}
    for nom in fiche["cameras"]:
        liste_f = dossier / "envoi" / f"{nom}.json"
        if not liste_f.is_file():
            continue
        liste = json.loads(liste_f.read_text(encoding="utf-8"))
        if detecteur:
            sortie[nom] = lp.objets_du_detecteur(liste)
        elif nom in lecture["photos"]:
            sortie[nom] = lp.objets_lus(lecture["photos"][nom], liste)
    return sortie


def baies_lues(logement: dict, fiche: dict, dossier: Path) -> dict[str, list[int]]:
    """Les votes de la lecture pour chaque baie du plan : {id: [fois lue « porte_fenetre », fois lue « fenetre »]}."""
    from moteur import caler_photos as cp
    from moteur.camera_photo import camera_depuis_dict

    plan = cp.plan_du_logement(logement)
    total: dict[str, list[int]] = {}
    for nom, objets in objets_des_photos(fiche, dossier).items():
        votes = photos_lues.baies_d_une_photo(objets, camera_depuis_dict(fiche["cameras"][nom]["camera"]), plan, logement)
        for ident, (pf, f) in votes.items():
            t = total.setdefault(ident, [0, 0])
            t[0] += pf
            t[1] += f
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="Poser dans le logement ce qu'une lecture des photos a compris")
    ap.add_argument("fiche", type=Path, help="cameras-photos.json (photos placées)")
    ap.add_argument("logement", type=Path)
    ap.add_argument("sortie", type=Path, help="logement.json écrit, avec les meubles posés")
    ap.add_argument("lecture", type=Path, help="dossier de la lecture (lecture.json et envoi)")
    ap.add_argument("--detecteur", action="store_true", help="référence : la sorte du détecteur au lieu de la sorte lue")
    ap.add_argument("--sans-equipements", action="store_true", help="ne pas poser les équipements (cheminée, radiateurs, cuisine…)")
    a = ap.parse_args()
    for f in (a.fiche, a.logement, a.lecture / "envoi"):
        if not f.exists():
            print(f"PLANTÉ : introuvable : {f}", flush=True)
            return 2
    from moteur.logement import Logement

    fiche = json.loads(a.fiche.read_text(encoding="utf-8"))
    logement = json.loads(a.logement.read_text(encoding="utf-8"))
    objets = objets_des_photos(fiche, a.lecture, a.detecteur)
    manquantes = [n for n in fiche["cameras"] if n not in objets]
    if manquantes:
        print(f"photos sans lecture (rien n'y est posé) : {', '.join(manquantes)}", flush=True)
    from moteur import equipements as eq

    r = photos_lues.poser(fiche, logement, RACINE, objets, par_sorte=not a.detecteur,
                          source="repérage photos" if a.detecteur else "repérage par lecture des photos", journal=print,
                          equiper=not (a.detecteur or a.sans_equipements))
    logement["meubles"] = list(logement.get("meubles", [])) + r["meubles"]
    logement = eq.appliquer(logement, r["equipements"])
    Logement.model_validate(logement)
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    a.sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    e = r["equipements"]
    a.sortie.with_suffix(".equipements.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in r["meubles"] + e["meubles"]:
        print(f"{str(m['piece']):14s} {m['categorie']:20s} {m['position']} face {m['face']}° ({m['source']})")
    for ident, rideau in e["rideaux"].items():
        print(f"{'':14s} {'rideaux':20s} fenêtre {ident} : {'voilage ' if rideau['voilage'] else ''}{'rideaux' if rideau['rideaux'] else ''}")
    for t in e["passe_plats"]:
        print(f"{'':14s} {'passe-plat':20s} mur {t['mur']} à {t['position']} m, {t['largeur']} × {t['hauteur']} m, bas à {t['allege']} m")
    for m in e.get("murs", []):
        print(f"{'':14s} {'muret ajouté':20s} {m['id']} de {m['debut']} à {m['fin']} (vide du plan refermé sous un passe-plat)")
    print(f"{len(r['meubles'])} meubles posés ; équipements : {len(e['meubles'])} posés, {len(e['rideaux'])} fenêtre(s) habillée(s), "
          f"{len(e['passe_plats'])} passe-plat(s), {len(e['non_poses'])} non posé(s) : {a.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
