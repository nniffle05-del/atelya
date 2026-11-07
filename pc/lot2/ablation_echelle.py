"""Contre-essai des corrections du lecteur d'échelle : on en retire UNE, on remesure, et on compte les erreurs qui reviennent.

Pourquoi : un correctif qui fait baisser les erreurs ne prouve pas la cause de chacune. Si, sans lui seul, des erreurs reviennent, ce
sont les siennes. Rien n'est modifié dans moteur/ : les fonctions sont remplacées en mémoire, le temps de la mesure. Les textes viennent
du cache de l'OCR (mesurer_echelle_lot2.py), donc tout est comparable à l'octet près.

Depuis le dépôt, avec OMP_NUM_THREADS=1 :
  python pc/lot2/ablation_echelle.py --sortie ..\\atelya\\echelle-cm\\ablation --processus 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesurer_echelle_lot2 as M  # noqa: E402

RETRAITS = ("croisements", "face_du_mur", "mur_au_bout_garde", "halo", "tableau", "dimensions", "petits_entiers", "garde_fou", "cote_ensemble")


def _retirer(nom: str) -> None:
    import numpy as np

    import moteur.echelle_plan as ep
    import moteur.lecture_cotes as lc

    if nom == "croisements":
        lc._croisements = lambda noir, y, debut, fin, cx, colonnes, *a: np.zeros(len(colonnes), bool)
    elif nom == "face_du_mur":
        vrai = lc._centres_des_groupes
        lc._centres_des_groupes = lambda c, p, d, cx=None, large=None: vrai(c, p, d)
    elif nom == "mur_au_bout_garde":
        lc._colonnes_d_un_mur_au_bout = lambda *a: set()
    elif nom == "halo":
        lc._mur_au_bout = lambda *a: None
    elif nom == "tableau":
        lc._nombres_d_un_tableau = lambda textes: []
    elif nom == "dimensions":
        ep._sans_les_dimensions_en_double = lambda dimensions, surfaces, dedans: dimensions
    elif nom == "petits_entiers":
        def admises(cotes, en_cm):
            if cotes or len(en_cm) < 2:
                return []
            ok = any(sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= lc.ECART_MAX for d in en_cm) >= 2 for c in en_cm)
            return en_cm if ok else []

        lc._cotes_en_cm_admises = admises
    elif nom == "garde_fou":
        ep.DESACCORD_COTES_SURES = 1e9
    elif nom == "cote_ensemble":
        # La plus grande cote reste connue même si les cotes se contredisent : on remet ce que lire_echelle_plan efface.
        vrai_lire = ep.lire_echelle_plan

        def lire(dessin, coloriage, redressement=None, angle=None, textes=None, px_par_pt=None):
            e = vrai_lire(dessin, coloriage, redressement, angle, textes, px_par_pt)
            if e.contredite and not e.cote_max_largeur and not e.cote_max_hauteur:
                nombres = [(c.valeur, c.verticale) for c in e.cotes]
                h = [v for v, vert in nombres if not vert]
                w = [v for v, vert in nombres if vert]
                e.cote_max_largeur, e.cote_max_hauteur = max(h) if h else None, max(w) if w else None
            return e

        ep.lire_echelle_plan = lire


def _prep(code: str, cache: str, nom: str) -> None:
    M._preparer(code, cache)
    _retirer(nom)


def _mesurer(nom: str, taches: dict, sortie: Path, processus: int, cache: str) -> dict:
    resultat = {}
    with Pool(processus, _prep, (".", cache, nom)) as pool:
        for cle, (fonction, liste) in taches.items():
            f = sortie / f"{nom}-{cle}.json"
            if f.exists():
                rs = json.loads(f.read_text(encoding="utf-8"))
            else:
                rs = list(pool.imap_unordered(fonction, liste))
                f.write_text(json.dumps(rs, ensure_ascii=False), encoding="utf-8")
            resultat[cle] = rs
    return resultat


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--processus", type=int, default=2)
    ap.add_argument("--cache-ocr", default=r"..\atelya\echelle-cm\cache-ocr")
    ap.add_argument("--reference", type=Path, default=Path(r"..\atelya\echelle-cm"))
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    jeu = Path(r"..\atelya\donnees\lot2-test")
    taches_jeu = [(str(ex), n.name, None, True, False) for ex in sorted((jeu / "exemples").iterdir()) if ex.is_dir()
                  and json.loads((ex / "manifeste.json").read_text(encoding="utf-8")).get("accepte", True)
                  for n in sorted(ex.iterdir()) if n.is_dir() and n.name.startswith("niveau_")]
    tirages = json.loads((a.reference / "apres-tirages.json").read_text(encoding="utf-8"))["plans"]
    taches_tirages = [(r"..\atelya\echelle-cm\tirages-cm", int(r["plan"])) for r in tirages]
    taches = {"lot2-test": (M._un_niveau_du_jeu, taches_jeu), "tirages": (M._un_tirage, taches_tirages)}
    ref = {c: {(r["plan"], r["niveau"]): r for r in json.loads((a.reference / f"apres-{c}.json").read_text(encoding="utf-8"))["plans"]} for c in taches}
    avant = {c: {(r["plan"], r["niveau"]): r for r in json.loads((a.reference / f"avant-{c}.json").read_text(encoding="utf-8"))["plans"]} for c in taches}
    bilan = {}
    for nom in RETRAITS:
        res = _mesurer(nom, taches, a.sortie, a.processus, a.cache_ocr)
        ligne = {}
        for c, rs in res.items():
            faux = sorted(r["plan"] for r in rs if r.get("lu") and (M.erreur_max(r) or 0) > M.SEUIL_ERREUR)
            faux_ref = {k[0] for k, r in ref[c].items() if r.get("lu") and (M.erreur_max(r) or 0) > M.SEUIL_ERREUR}
            faux_avant = {k[0] for k, r in avant[c].items() if r.get("lu") and (M.erreur_max(r) or 0) > M.SEUIL_ERREUR}
            reviennent = sorted(set(faux) - faux_ref)
            ligne[c] = {"faux": len(faux), "reviennent": reviennent, "dont_deja_faux_avant": sorted(set(reviennent) & faux_avant),
                        "lus": sum(bool(r.get("lu")) for r in rs)}
        bilan[nom] = ligne
        print(nom, json.dumps(ligne, ensure_ascii=False), flush=True)
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
