r"""Photos d'essai pour la brique photos : des intérieurs rendus par Blender dont on connaît les sols (09/11/2026).

Pourquoi : pour mettre au point la reconnaissance des sols sans regarder les photos d'app-001 (elles restent l'EXAMEN), il
faut des photos dont on connaît la bonne réponse. On prend les maquettes d'autres logements, on donne à chaque pièce un sol
tiré au hasard dans le catalogue (parfois un second sol sur une partie de la pièce, comme une cuisine ouverte), et on pose des
caméras « de photographe » (de niveau, à hauteur d'homme, grand angle). Blender rend les photos ; la caméra de chacune est
connue exactement.

    ..\atelya\.venv\Scripts\python.exe outils\habillage\photos_d_essai.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\lectures-claude\fr-021\logement.json ... [--tirages 2] [--graine 1]

Chaque tirage écrit dans <sortie>\<logement>-t<n>\ : logement.json (la vérité : sol de chaque pièce et zones), construction\
(maquette), cameras-photos.json (même format que verites\app-001\cameras-photos.json) et rendus\vue-<photo>.png.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.matieres import NOMS_SOLS  # noqa: E402
from moteur.sol_a_plat import dans_polygone, mettre_a_plat  # noqa: E402

LARGEUR, HAUTEUR = 1206, 804  # comme les photos d'annonce d'app-001
ECLAIRAGES = ("1 Jour ensoleillé", "2 Jour voilé", "3 Fin de journée")
ECHANTILLONS = 96


def aire(contour) -> float:
    c = np.asarray(contour, float)
    return abs(float((c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1]).sum())) / 2


def sol_au_hasard(alea: random.Random, eviter: str | None = None) -> dict:
    from moteur.reconnaitre_sols import famille
    choix = [m for m in NOMS_SOLS if eviter is None or famille(m) != famille(eviter)]
    matiere = alea.choice(choix)
    commun = alea.gauss(0, 0.18)
    teinte = [round(min(1.8, max(0.4, math.exp(commun + alea.gauss(0, 0.06)))), 3) for _ in range(3)]
    return {"matiere": matiere, "teinte": teinte, "echelle": round(alea.uniform(0.8, 1.25), 2), "statut": "mesure",
            "source": "photos d'essai (tirage au hasard)"}


def zone_au_hasard(alea: random.Random, contour, sol_piece: dict) -> dict:
    """Un rectangle d'un autre sol sur 30 à 60 % de la pièce, du côté d'un de ses bords (le reste est coupé à la construction)."""
    c = np.asarray(contour, float)
    x0, y0, x1, y1 = c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()
    part = alea.uniform(0.3, 0.6)
    if x1 - x0 >= y1 - y0:
        coupe = x0 + part * (x1 - x0)
        r = [[x0, y0], [coupe, y0], [coupe, y1], [x0, y1]] if alea.random() < 0.5 else [[coupe, y0], [x1, y0], [x1, y1], [coupe, y1]]
    else:
        coupe = y0 + part * (y1 - y0)
        r = [[x0, y0], [x1, y0], [x1, coupe], [x0, coupe]] if alea.random() < 0.5 else [[x0, coupe], [x1, coupe], [x1, y1], [x0, y1]]
    return {"contour": [[round(x, 3), round(y, 3)] for x, y in r], "sol": sol_au_hasard(alea, eviter=sol_piece["matiere"])}


def distance_aux_bords(point, contour) -> float:
    p = np.asarray(point, float)
    c = np.asarray(contour, float)
    d = math.inf
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        ab = b - a
        t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = min(d, float(np.linalg.norm(p - (a + t * ab))))
    return d


def cameras_au_hasard(alea: random.Random, piece: dict, combien: int) -> list[list[float]]:
    """Caméras de photographe dans la pièce, chacune voyant au moins 3 m² de son sol."""
    c = np.asarray(piece["contour"], float)
    sorties, essais = [], 0
    while len(sorties) < combien and essais < 200:
        essais += 1
        x, y = alea.uniform(c[:, 0].min(), c[:, 0].max()), alea.uniform(c[:, 1].min(), c[:, 1].max())
        if not dans_polygone(np.array([x]), np.array([y]), c)[0] or distance_aux_bords((x, y), c) < 0.4:
            continue
        champ = math.radians(alea.uniform(70, 100))
        f = LARGEUR / 2 / math.tan(champ / 2)
        cam = [x, y, alea.uniform(0.95, 1.45), alea.uniform(-180, 180), alea.uniform(-8, 0) if alea.random() < 0.3 else 0.0,
               f, LARGEUR / 2, HAUTEUR / 2 + alea.uniform(-60, 20)]
        vu = mettre_a_plat(np.zeros((HAUTEUR, LARGEUR, 3), np.uint8), cam, c, resolution=0.05)
        if (vu.finesse > 0).sum() * 0.0025 >= 3.0:
            sorties.append([round(float(v), 4) for v in cam])
    return sorties


def tirage(logement: dict, alea: random.Random) -> tuple[dict, dict]:
    """Le logement avec des sols tirés au hasard, et les caméras (format cameras-photos.json)."""
    from moteur.camera_photo import NOMS
    logement = json.loads(json.dumps(logement))
    cameras = {}
    for p in logement["pieces"]:
        p["sol"] = sol_au_hasard(alea)
        p["zones_sol"] = [zone_au_hasard(alea, p["contour"], p["sol"])] if aire(p["contour"]) >= 10 and alea.random() < 0.4 else []
        a = aire(p["contour"])
        combien = 0 if a < 4 else (1 if a < 12 else 2)
        for k, cam in enumerate(cameras_au_hasard(alea, p, combien), start=1):
            cameras[f"{p['id']}-{k}"] = {"camera": dict(zip(NOMS, cam)), "largeur": LARGEUR, "hauteur": HAUTEUR}
    return logement, cameras


def main() -> int:
    ap = argparse.ArgumentParser(description="Photos d'essai rendues par Blender, sols connus")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("logements", type=Path, nargs="+")
    ap.add_argument("--tirages", type=int, default=2)
    ap.add_argument("--graine", type=int, default=1)
    args = ap.parse_args()
    from moteur.construire import construire
    from outils.habillage.caler_photos import rendre
    alea = random.Random(args.graine)
    for chemin in args.logements:
        if not chemin.is_file():
            print(f"PLANTÉ : logement introuvable : {chemin}", flush=True)
            return 2
        base = json.loads(chemin.read_text(encoding="utf-8"))
        for t in range(1, args.tirages + 1):
            debut = time.time()
            dossier = args.sortie / f"{chemin.parent.name}-t{t}"
            dossier.mkdir(parents=True, exist_ok=True)
            logement, cameras = tirage(base, alea)
            (dossier / "logement.json").write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
            maquette = construire(dossier / "logement.json", dossier / "construction")
            scene = alea.choice(ECLAIRAGES)
            releve = {"photos": str((dossier / "rendus").resolve()), "fichier": "vue-{nom}.png", "eclairage": scene,
                      "cameras": cameras}
            (dossier / "cameras-photos.json").write_text(json.dumps(releve, ensure_ascii=False, indent=1), encoding="utf-8")
            rendre(releve, maquette, dossier, ECHANTILLONS, scene)
            print(f"{dossier.name} : {len(cameras)} photos ({scene}) en {time.time() - debut:.0f} s", flush=True)
    print("FINI", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # règle 6 : une ligne claire en cas de plantage
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
