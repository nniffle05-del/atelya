r"""Essayer « pas du sol » (moteur/pas_du_sol.py) sur le CONTRÔLE fabriqué (fr-031, fr-038, jamais appris) (10/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\essayer_pas_du_sol.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\b2\pas-du-sol\essai-1.json

Jamais app-001 ni app-002 (examens déjà vus : seulement le non-recul, une fois, à la fin).
Trois jeux : « lits » (fr-031-m3/m4, fr-038-m3/m4 : vrais lits garnis), « meubles » (m1/m2 : anciens tirages meublés),
« vides » (t1/t2 : pièces vides, rien à écarter : ne doit pas reculer).
Pour chaque réglage : surface juste (part du sol vu dont la famille décidée est la bonne), pièces justes, m² jugés ; et, avec
le masque des meubles mis à plat (vérité) : justesse sous les meubles et ailleurs. TOUT est compté sur la surface et les
pièces jugées SANS écartement : ce qui n'est plus jugé compte comme raté.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.pas_du_sol import charger  # noqa: E402
from moteur.reconnaitre_sols import Classifieur, famille_decidee, familles_verite, noter, reconnaitre  # noqa: E402
from moteur.sol_a_plat import emprise_du_logement, mettre_a_plat, piece_de_l_appareil  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
JEUX = {"lits": ("fr-031-m3", "fr-031-m4", "fr-038-m3", "fr-038-m4"),
        "meubles": ("fr-031-m1", "fr-031-m2", "fr-038-m1", "fr-038-m2"),
        "vides": ("fr-031-t1", "fr-031-t2", "fr-038-t1", "fr-038-t2")}
REGLAGES = {
    "sans": None,
    "owl": {"p_dans": -1.0},
    "owl-sans-tables-chaises": {"p_dans": -1.0, "groupes": ("lit", "canape", "fauteuil", "rangement")},
    "owl-lits-canapes": {"p_dans": -1.0, "groupes": ("lit", "canape")},
    "owl-lits-canapes-rangements": {"p_dans": -1.0, "groupes": ("lit", "canape", "rangement")},
    "owl-lits-canapes-fauteuils": {"p_dans": -1.0, "groupes": ("lit", "canape", "fauteuil")},
    "owl+dino-0.3": {"p_dans": 0.3},
    "dino-seul-0.7": {"avec_owl": False, "p_seul": 0.7},
}


def meubles_a_plat(t: Path, releve: dict, lg: dict, resolution: float, forme) -> np.ndarray | None:
    """Vérité : la part de chaque case couverte par un meuble (masque des meubles, tapis compris) sur au moins une photo."""
    if not (t / "masques").is_dir():
        return None
    emprise = emprise_du_logement(lg)
    couvert = None
    for nom, info in releve["cameras"].items():
        brut = lire_image(t / "masques" / f"masque-{nom}.png", cv2.IMREAD_GRAYSCALE)
        if brut is None:
            continue
        cam = camera_depuis_dict(info["camera"])
        piece, point = piece_de_l_appareil(cam, lg["pieces"])
        if piece is None:
            continue
        v = mettre_a_plat(np.repeat(brut[..., None], 3, axis=2), cam, piece["contour"], emprise, resolution, point_de_vue=point)
        m = cv2.resize(v.image[..., 0].astype(np.float32) / 255.0, (forme[1], forme[0]), interpolation=cv2.INTER_AREA)
        couvert = m if couvert is None else np.maximum(couvert, m)
    return couvert


def mesurer(res: dict, lg: dict, couvert, base: dict | None) -> dict:
    """Tout se compte sur la surface et les pièces jugées SANS écartement (`base`) : une case ou une pièce qui n'est plus
    jugée compte comme ratée (pour un film du logement, une pièce sans sol décidé est un échec)."""
    carte = res["carte"]
    X, Y = carte.centres()
    c2 = carte.case ** 2
    ver = familles_verite(lg, X, Y, carte.classes)
    dec = famille_decidee(res["pieces"], lg, X, Y, carte.classes)
    jug = carte.vue() & (ver >= 0) & (dec >= 0)
    if base is None:
        base = {"jug": jug, "pieces": [pid for pid in res["pieces"] if any(p["id"] == pid and p.get("sol") for p in lg["pieces"])]}
    B = base["jug"]
    juste = B & (dec == ver) & (dec >= 0)
    sous = couvert > 0.5
    from moteur.reconnaitre_sols import famille
    attendu = {p["id"]: famille(p["sol"]["matiere"]) for p in lg["pieces"] if p.get("sol")}
    pj = sum(1 for pid in base["pieces"] if pid in res["pieces"] and res["pieces"][pid]["famille"] == attendu[pid])
    return {"base": base, "m2": float(B.sum() * c2), "m2_justes": float(juste.sum() * c2),
            "m2_sous": float((B & sous).sum() * c2), "m2_sous_justes": float((juste & sous).sum() * c2),
            "m2_libre": float((B & ~sous).sum() * c2), "m2_libre_justes": float((juste & ~sous).sum() * c2),
            "m2_plus_juges": float((B & ~jug).sum() * c2), "pieces_justes": f"{pj}/{len(base['pieces'])}"}


def resumer(lignes: list[dict]) -> dict:
    s = lambda k: sum(l[k] for l in lignes)  # noqa: E731
    pj = [l["pieces_justes"].split("/") for l in lignes]
    return {"surface_juste": round(s("m2_justes") / max(s("m2"), 1e-9), 3), "m2": round(s("m2"), 1),
            "juste_sous_meubles": round(s("m2_sous_justes") / max(s("m2_sous"), 1e-9), 3), "m2_sous": round(s("m2_sous"), 1),
            "juste_ailleurs": round(s("m2_libre_justes") / max(s("m2_libre"), 1e-9), 3),
            "m2_plus_juges": round(s("m2_plus_juges"), 1),
            "pieces_justes": f"{sum(int(a) for a, _ in pj)}/{sum(int(b) for _, b in pj)}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Essayer « pas du sol » sur le contrôle fabriqué")
    ap.add_argument("essais", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--modele-sols", type=Path, default=RACINE / "moteur" / "modeles" / "sols-vits14-v2.pt")
    ap.add_argument("--modele-meubles", type=Path, default=None)
    ap.add_argument("--reglages", nargs="*", default=None)
    args = ap.parse_args()
    debut = time.time()
    clf = Classifieur.depuis(torch.load(args.modele_sols, weights_only=False))
    pds = charger(modele_meubles=args.modele_meubles)
    oeil = pds.oeil  # même œil DINOv2 (ViT-S/14) pour les sols et les meubles
    reglages = {k: v for k, v in REGLAGES.items() if args.reglages is None or k in args.reglages or k == "sans"}
    bilan = {}
    for jeu, tirages in JEUX.items():
        par_reglage = {k: [] for k in reglages}
        for nom_t in tirages:
            t = args.essais / nom_t
            if not (t / "cameras-photos.json").is_file():
                print(f"  {nom_t} absent, sauté", flush=True)
                continue
            releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
            lg = json.loads((t / "logement.json").read_text(encoding="utf-8"))
            base, couvert = None, None
            for k, r in reglages.items():
                fonction = None if r is None else (lambda nom, rgb, r=r, t=t: pds.masque(f"{t.name}/{nom}", rgb, **r))
                res = reconnaitre(releve, lg, RACINE, oeil, clf, pas_du_sol=fonction)
                if couvert is None:
                    couvert = meubles_a_plat(t, releve, lg, res["resolution"], res["carte"].votes.shape[:2])
                    couvert = couvert if couvert is not None else np.zeros(res["carte"].votes.shape[:2])
                m = mesurer(res, lg, couvert, base)
                base = m.pop("base")
                par_reglage[k].append(m)
            print(f"  {jeu} {nom_t} fait ({time.time() - debut:.0f} s)", flush=True)
        bilan[jeu] = {k: resumer(v) for k, v in par_reglage.items() if v}
        for k, v in bilan[jeu].items():
            print(f"[{jeu}] {k:26s} {v}", flush=True)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
