r"""Non-recul sur les examens DÉJÀ VUS app-001 et app-002 (10/11/2026) : une seule fois, AUCUN réglage.

    ..\atelya\.venv\Scripts\python.exe outils\habillage\non_recul_examens.py ..\atelya\b2\non-recul-2026-11-10

Sols (sols-vits14-v2) : sans / avec « pas du sol » (moteur/pas_du_sol.py). Meubles : DINOv2 (meubles-vits14-v1) / OWLv2
(moteur/reperer_meubles.reperer_depuis_releve). Même notation que les examens (noter, noter_meubles).
Le passage « sans » / DINOv2 doit redonner les notes déjà connues (app-001 sols 81,5 %, meubles 16/34 ; app-002 sols 79,2 %,
meubles 10/30) : sinon, quelque chose a changé sans le vouloir.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.oeil_dinov2 import charger as charger_oeil  # noqa: E402
from moteur.pas_du_sol import charger as charger_pds  # noqa: E402
from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre  # noqa: E402
from moteur.reperer_meubles import (empreintes_carres, fusionner, meubles_d_une_photo, noter_meubles,  # noqa: E402
                                    reperer_depuis_releve)
from moteur.sol_a_plat import piece_de_l_appareil  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
PC = RACINE.parent / "atelya"
EXAMENS = {
    "app-001": {"releve": RACINE / "verites/app-001/cameras-photos.json", "logement": PC / "lectures-claude/app-001/logement.json",
                "verite_sols": PC / "b2/app-001/brique-photos/verite-logement-sols.json",
                "meubles": RACINE / "verites/app-001/meubles.json"},
    "app-002": {"releve": RACINE / "verites/app-002/cameras-photos.json", "logement": RACINE / "verites/app-002/logement.json",
                "verite_sols": PC / "b2/app-002/examen/logement-verite-sols.json",
                "meubles": RACINE / "verites/app-002/meubles.json"},
}


def lire(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    clf_sols = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
    clf_meubles = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/meubles-vits14-v1.pt", weights_only=False))
    oeil = charger_oeil("vits14")
    pds = charger_pds(avec_dino=False)
    bilan = {}
    for nom, f in EXAMENS.items():
        for k in ("releve", "logement", "verite_sols", "meubles"):
            if not f[k].is_file():
                print(f"PLANTÉ : fichier introuvable : {f[k]}", flush=True)
                return 2
        releve, logement = lire(f["releve"]), lire(f["logement"])
        logement_sans_sols = json.loads(json.dumps(logement))
        for p in logement_sans_sols["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        verite_sols, verite_meubles = lire(f["verite_sols"]), lire(f["meubles"])["meubles"]
        b = {}
        for mode, fonction in (("sols_sans", None), ("sols_pas_du_sol", lambda n, rgb: pds.masque(f"{nom}/{n}", rgb))):
            note = noter(reconnaitre(releve, logement_sans_sols, RACINE, oeil, clf_sols, pas_du_sol=fonction), verite_sols)
            b[mode] = {k: note.get(k) for k in ("surface_jugee_m2", "surface_juste", "pieces_justes", "pieces")}
            print(f"{nom} {mode} : {note.get('surface_juste')} ({note.get('pieces_justes')}) {note.get('pieces')}", flush=True)
        dossier = RACINE / releve["photos"]
        modele = releve.get("fichier", "{nom}.png")
        photos = []
        for n, d in releve["cameras"].items():
            img = lire_image(dossier / modele.format(nom=n))
            photos.append((cv2.cvtColor(img, cv2.COLOR_BGR2RGB), camera_depuis_dict(d["camera"])))
        cams = [c for _, c in photos]
        vus = []
        for rgb, cam in photos:
            e = empreintes_carres(oeil, rgb)
            p = clf_meubles.probabilites(e.reshape(-1, e.shape[-1])).reshape(*e.shape[:2], -1)
            piece, _ = piece_de_l_appareil(cam, logement["pieces"])
            vus += meubles_d_une_photo(p, cam, rgb.shape[1], rgb.shape[0], piece)
        b["meubles_dino"] = noter_meubles(fusionner(vus), verite_meubles, cameras=cams, logement=logement)
        trouves = reperer_depuis_releve(releve, logement, RACINE, owl=pds.owl)
        b["meubles_owl"] = noter_meubles(trouves, verite_meubles, cameras=cams, logement=logement)
        (sortie / f"meubles-owl-{nom}.json").write_text(json.dumps(trouves, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nom} meubles DINOv2 : {b['meubles_dino']}", flush=True)
        print(f"{nom} meubles OWLv2  : {b['meubles_owl']}", flush=True)
        bilan[nom] = b
    (sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
