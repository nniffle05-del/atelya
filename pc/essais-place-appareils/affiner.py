r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : l'appareil de chaque photo AFFINÉ DANS L'IMAGE (moteur/affiner_appareils.py),
essai des deux voies sur les quatre logements.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\affiner.py <variante de départ> <voie> [<voie>…] [--logements …]

Départ : les appareils d'une variante déjà calée (caler.py ; « service » = le calage sans affinage). Voies :
  A   Atelya SEUL : les lignes du plafond et du sol trouvées dans le relief de la photo ;
  B   seulement les lignes LUES des fenêtres (vitrages.json : pied et haut du mur de la fenêtre, tour de la menuiserie) ;
  AB  les deux ensemble.
Sorties : ..\atelya\b2\place-appareils\<départ>+<voie>\<logement>.json, au même format que caler.py (le juge : juger.py).
Les mesures des photos (lignes trouvées, zoom des lignes de fuite) sont gardées dans ..\atelya\b2\place-appareils\memoire\.
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import affiner_appareils as aa  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur import fuites, moge  # noqa: E402

JONCTIONS = "j7"       # version de la mémoire des mesures (à changer quand `jonctions` change)


def mesures_du_logement(nom: str, c: dict, noms_photos, hsp: float) -> dict:
    """{photo: (jonctions, {"f", "net", "largeur"} des lignes de fuite)}, gardé sur le disque."""
    from juger import SORTIE
    memoire = SORTIE / "memoire" / f"{nom}-{JONCTIONS}.pkl"
    if memoire.is_file():
        return pickle.loads(memoire.read_bytes())
    import torch
    from moteur.pas_du_sol import charger as charger_pds
    appareil = "cuda" if torch.cuda.is_available() else "cpu"
    modele = moge.charger(appareil)
    owl = charger_pds(appareil, avec_dino=False).owl
    requetes = owl.textes(list(aa.CACHE_MUR))
    mesures = {}
    for n in noms_photos:
        rgb = c["photos"][n]
        fu = fuites.mesurer(rgb)
        mesures[n] = aa.jonctions(cp.mesurer(modele, rgb), hsp, aa.cache_mur(owl, requetes, rgb)), {"f": fu["f"], "net": fu["net"], "largeur": rgb.shape[1]}
    memoire.parent.mkdir(parents=True, exist_ok=True)
    memoire.write_bytes(pickle.dumps(mesures))
    del modele, owl
    torch.cuda.empty_cache()
    return mesures


def main():
    from caler import cas
    from juger import MAQUETTES, SORTIE, lire

    args = sys.argv[1:]
    noms = args[args.index("--logements") + 1:] if "--logements" in args else ["app-001", "app-002", "app-003", "app-004"]
    args = args[:args.index("--logements")] if "--logements" in args else args
    depart, voies = args[0], args[1:]
    for nom in noms:
        c = cas(nom)
        logement = c["logement"]
        scene = aa.Scene(logement)
        fiche = lire(SORTIE / depart / f"{nom}.json")
        lus = {}
        if nom in MAQUETTES:
            maquette = lire(MAQUETTES[nom] / "logement-meuble.json")
            maquette = maquette.get("logement", maquette)
            lus = {n: aa.reperes_lus(maquette, f) for n, f in lire(MAQUETTES[nom] / "vitrages.json")["photos"].items()}
        mesures = mesures_du_logement(nom, c, list(fiche["cameras"]), scene.hsp)
        zoom_lot = fuites.zoom_du_lot({n: fu for n, (_, fu) in mesures.items()})
        print(f"{nom} : hsp {scene.hsp:.2f} m, {len(scene.A)} faces pleines, {len(scene.limites[0])} limites sans mur ; zoom du lot : {zoom_lot}", flush=True)
        vide = {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
        for voie in voies:
            t0 = time.time()
            cameras = json.loads(json.dumps(fiche["cameras"]))
            jon = {n: (j if "A" in voie else {**vide, "z": j.get("z", 1.3)}) for n, (j, _) in mesures.items()}
            bilan = aa.affiner_les_appareils(logement, c["photos"], cameras, {}, zoom_du_lot=zoom_lot, lus=lus if "B" in voie else None,
                                            journal=lambda *a: None, jonctions_de=jon)
            (SORTIE / f"{depart}+{voie}").mkdir(parents=True, exist_ok=True)
            (SORTIE / f"{depart}+{voie}" / f"{nom}.json").write_text(json.dumps({"photos": fiche["photos"], "fichier": fiche["fichier"], "cameras": cameras,
                                                                                "non_calees": fiche.get("non_calees", {})}, ensure_ascii=False, indent=1), encoding="utf-8")
            compte = {k: sum(1 for v in bilan.values() if v == k) for k in ("lignes+lus", "lignes", "lus", "depart")}
            print(f"  {nom} [{voie}] {compte} ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
