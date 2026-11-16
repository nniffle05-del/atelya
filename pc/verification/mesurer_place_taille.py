r"""« PLACE ET TAILLE JUSTES » (16/11/2026) : la pose d'après la lecture des photos, refaite seule et notée — la boucle courte.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_place_taille.py <dossier de l'essai de départ> <sortie> [--cas …] [--ancien]

Pourquoi : la chaîne entière (essai_lecture_photos.py) prend 80 s par logement et par version ; seule l'étape « meubles » change
ici. Cette commande reprend le logement avec ses sols de l'essai de départ (<départ>/<logement>/c/logement-sols.json), refait
exactement l'étape « meubles » de la chaîne (moteur.photos_lues.poser, équipements, zéro collision : comme
outils/lecture_photos/poser_photos_lues.py), écrit <sortie>/<logement>/c/logement-meuble.json (+ trace.txt : d'où vient chaque
meuble) et note contre les relevés faits à la main avec la règle de l'essai (essai_lecture_photos.noter_meubles).
--ancien : la fusion d'avant (limite fixe), pour retrouver le point de départ.
Le juge officiel reste la chaîne entière (essai_lecture_photos.py … --versions a c) : à refaire avant de conclure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import essai_lecture_photos as essai  # noqa: E402
import poser_photos_lues as ppl  # noqa: E402
from banc_ressemblance import CAS, PC  # noqa: E402
from moteur import collisions, moge, photos_lues  # noqa: E402
from moteur import equipements as eq  # noqa: E402


def refaire(cas: str, depart: Path, sortie: Path, modele, options: dict) -> dict:
    fiche = essai.lire(CAS[cas]["fiche"])
    logement = essai.lire(depart / cas / "c" / "logement-sols.json")
    objets = ppl.objets_des_photos(fiche, PC / "lectures-photos" / cas)
    journal: list[str] = []
    r = photos_lues.poser(fiche, logement, RACINE, objets, modele_moge=modele, journal=lambda *a: journal.append(" ".join(str(x) for x in a)),
                          **options)
    logement["meubles"] = list(logement.get("meubles", [])) + r["meubles"]
    logement = eq.appliquer(logement, r["equipements"])
    logement, actions = collisions.reparer(logement, journal=lambda *a: journal.append(" ".join(str(x) for x in a)))
    d = sortie / cas / "c"
    d.mkdir(parents=True, exist_ok=True)
    (d / "logement-meuble.json").write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "logement-meuble.equipements.json").write_text(json.dumps(r["equipements"], ensure_ascii=False, indent=1), encoding="utf-8")
    photos, poses = r["trace"]["photos"], {m["id"]: m for m in logement["meubles"]}
    lignes = list(journal) + [""]
    for k, t in enumerate(r["trace"]["trouves"], start=1):
        m = poses.get(f"reperage_{k}")
        fin = f"→ posé {m['position']} {m['dimensions']} face {m['face']}" if m else "→ RETIRÉ ensuite"
        lignes.append(f"reperage_{k:<3d} {t['categorie']:18s} {t['position']} {t['vues']} vue(s) conf {t['confiance']} {fin}")
        for v in t.get("membres", []):
            lignes.append(f"      {photos[v['photo']]} n°{v['numero']} {v['categorie']} à {v['distance']:.1f} m  {[round(c, 2) for c in v['position']]}"
                          + ("  (rectangle approché)" if v["approche"] else ""))
    (d / "trace.txt").write_text("\n".join(lignes), encoding="utf-8")
    note = {"meubles_poses": len(logement["meubles"]), "collisions": collisions.resume(collisions.mesurer(logement)), "equipements": r["equipements"]}
    if cas in essai.VERITES:
        note["meubles"] = essai.noter_meubles(logement, essai.lire(essai.VERITES[cas]["meubles"])["meubles"], fiche)
    return note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("depart", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--ancien", action="store_true")
    a = ap.parse_args()
    modele = moge.charger()
    options = {"associer": False} if a.ancien else {}
    lignes, total = [], {"retrouves": 0, "bonne_sorte": 0, "en_trop": 0, "a_trouver": 0, "acc": 0, "acc_trop": 0, "acc_a_trouver": 0}
    for cas in a.cas:
        debut = time.time()
        n = refaire(cas, a.depart, a.sortie, modele, options)
        e, c = n["equipements"], n["collisions"]
        fin = (f" | équipements {len(e['meubles'])} posés, {len(e['non_poses'])} non posés | collisions {c['total']} | {n['meubles_poses']} objets "
               f"| {time.time() - debut:.0f} s")
        if "meubles" in n:
            m = n["meubles"]
            lignes.append(f"{cas} au sol : retrouvés {m['retrouves']}/{m['a_trouver']}, bonne sorte {m['bonne_sorte']}/{m['a_trouver']}, en trop {m['en_trop']}, "
                          f"écart {m['ecart_moyen_m']} m | accrochés {m['accroches_retrouves']}/{m['accroches_a_trouver']}, en trop {m['accroches_en_trop']}" + fin)
            lignes.append(f"      en trop : {', '.join(m['en_trop_detail'])}")
            for k, cle in (("retrouves", "retrouves"), ("bonne_sorte", "bonne_sorte"), ("en_trop", "en_trop"), ("a_trouver", "a_trouver"),
                           ("acc", "accroches_retrouves"), ("acc_trop", "accroches_en_trop"), ("acc_a_trouver", "accroches_a_trouver")):
                total[k] += m[cle]
        else:
            lignes.append(f"{cas} (pas de relevé)" + fin)
        print(lignes[-2] if "meubles" in n else lignes[-1], flush=True)
    lignes.append(f"TOTAL au sol : retrouvés {total['retrouves']}/{total['a_trouver']}, bonne sorte {total['bonne_sorte']}/{total['a_trouver']}, "
                  f"en trop {total['en_trop']} | accrochés {total['acc']}/{total['acc_a_trouver']}, en trop {total['acc_trop']}")
    a.sortie.mkdir(parents=True, exist_ok=True)
    (a.sortie / "bilan-court.txt").write_text("\n".join(lignes), encoding="utf-8")
    print("\n".join(lignes[-1:]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
