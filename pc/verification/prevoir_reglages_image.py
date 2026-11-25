r"""POINT 2, MESURE (18/11/2026) : jusqu'où les seuls RÉGLAGES D'IMAGE du film peuvent rapprocher le film des photos ?

    ..\atelya\.venv\Scripts\python.exe pc\verification\prevoir_reglages_image.py <sortie du juge de la lumière> [--tirages 4000]

<sortie du juge> : un dossier écrit par outils/unreal/juger_lumiere.py (lumiere.json + cadres/<logement>/vue-<photo>.png).

Pourquoi : avant de toucher à la lumière ou aux réglages, savoir ce que chaque levier PEUT apporter. Ici, sans relancer Unreal
(moteur/juge_lumiere.scene_du_film : la pellicule à l'envers), on cherche LE MÊME réglage pour toutes les vues de tous les
logements (exposition en plus, les trois réglages de la courbe des tons, vivacité) qui rapproche le plus le film des photos
sur : la clarté des murs, la clarté et la vivacité du sol, les sombres, le milieu et les clairs de l'image entière, sa vivacité.
C'est une PRÉVISION (les pixels brûlés restent brûlés, Lumen n'est pas rejoué) et un plafond : ce qui reste après est à chercher
dans la lumière et dans les matières. Rien n'est changé dans Atelya.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import juge_lumiere as jl  # noqa: E402
from moteur import pellicule_unreal, photographe  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.reconnaitre_sols import lab  # noqa: E402

# ce que l'œil voit d'abord pèse plus : murs et sol ; puis l'image entière
GROS_ECART = 8.0
BORNES = {"crans": (-0.5, 2.5), "pente": (0.45, 1.0), "pied": (0.3, 0.8), "epaule": (0.2, 0.7), "vivacite": (1.0, 1.9)}
POIDS = {"murs_L": 2.0, "sol_L": 2.0, "sol_C": 1.5, "L5": 1.0, "L50": 1.0, "L95": 1.0, "C": 1.0}


def charger(dossier: Path) -> list[dict]:
    """Par vue : les valeurs de la photo (la cible) et, pour le film, la lumière dans la scène des murs, du sol et d'un
    échantillon de pixels de l'image entière."""
    bilan = json.loads((dossier / "lumiere.json").read_text(encoding="utf-8"))
    vues = []
    for cas, b in bilan.items():
        for nom, v in b.items():
            p, f = v["photo"], v["film"]
            if not (p["murs"] and p["sol"] and f["murs"] and f["sol"]):
                continue
            image = cv2.cvtColor(lire_image(dossier / "cadres" / cas / f"vue-{nom}.png"), cv2.COLOR_BGR2RGB).reshape(-1, 3)
            image = image[image.max(axis=1) > 0][::23]
            vues.append({"nom": f"{cas} {nom}",
                         "cible": {"murs_L": p["murs"]["L"], "sol_L": p["sol"]["L"], "sol_C": p["sol"]["C"], "L5": p["image"]["L5"],
                                   "L50": p["image"]["L50"], "L95": p["image"]["L95"], "C": p["image"]["C"]},
                         "murs": jl.scene_du_film(jl.affiche(f["murs"]["lineaire"])), "sol": jl.scene_du_film(jl.affiche(f["sol"]["lineaire"])),
                         "brules": image.min(axis=1) >= 254, "image": jl.scene_du_film(image)})
    return vues


def rejouer(scene: np.ndarray, r: dict) -> np.ndarray:
    pellicule = {"film_slope": r["pente"], "film_toe": r["pied"], "film_shoulder": r["epaule"], "film_black_clip": 0.0,
                 "film_white_clip": r.get("blanc", photographe.PELLICULE["film_white_clip"])}
    c = photographe.PELLICULE_COULEURS
    return 255.0 * pellicule_unreal.affiche(np.atleast_2d(scene) * 2.0 ** r["crans"], pellicule, r["vivacite"], c["expand_gamut"],
                                           c["blue_correction"])


def mesures(vue: dict, r: dict) -> dict:
    murs, sol = lab(rejouer(vue["murs"], r))[0], lab(rejouer(vue["sol"], r))[0]
    image = rejouer(vue["image"], r)
    image[vue["brules"]] = 255.0
    L = lab(image)
    l5, l50, l95 = np.percentile(L[:, 0], [5, 50, 95])
    return {"murs_L": float(murs[0]), "sol_L": float(sol[0]), "sol_C": float(np.hypot(sol[1], sol[2])), "L5": float(l5),
            "L50": float(l50), "L95": float(l95), "C": float(np.hypot(L[:, 1], L[:, 2]).mean())}


def ecarts(vues: list[dict], r: dict) -> tuple[float, dict]:
    """La note d'un réglage (plus petit = plus près des photos) et l'écart moyen film − photo de chaque mesure."""
    par_mesure = {k: [] for k in POIDS}
    for vue in vues:
        m = mesures(vue, r)
        for k in POIDS:
            par_mesure[k].append(m[k] - vue["cible"][k])
    # écarts « bornés » : au-delà de GROS_ECART points, un écart ne compte plus au carré (un sol dont la MATIÈRE est fausse,
    # ex. la chambre d'app-004 à -40, ne doit pas tirer le réglage d'image de tous les logements)
    def borne(v):
        v = np.abs(np.asarray(v, float))
        return np.where(v <= GROS_ECART, v ** 2, GROS_ECART * (2 * v - GROS_ECART))

    note = sum(POIDS[k] * float(np.mean(borne(v))) for k, v in par_mesure.items()) / sum(POIDS.values())
    return float(np.sqrt(note)), {k: round(float(np.mean(v)), 1) for k, v in par_mesure.items()}


def chercher(vues: list[dict], depart: dict, tirages: int) -> dict:
    """Le meilleur réglage commun pour ces vues : exposition seule, puis vivacité, puis tout ensemble (tirages au hasard)."""
    seule = min(({**depart, "crans": c} for c in np.arange(0.0, 2.55, 0.05)), key=lambda r: ecarts(vues, r)[0])
    deux = min(({**seule, "vivacite": s} for s in np.arange(1.0, 1.85, 0.05)), key=lambda r: ecarts(vues, r)[0])
    rng = np.random.default_rng(0)
    meilleur, note = dict(deux), ecarts(vues, deux)[0]
    for k in range(tirages):
        largeur = 1.0 if k < tirages // 2 else 0.15
        essai = {c: float(np.clip(meilleur[c] + largeur * rng.normal(0, 0.25) * (b - a_), a_, b)) for c, (a_, b) in BORNES.items()}
        if essai["pied"] + 0.18 >= 1.0:
            continue
        n = ecarts(vues, essai)[0]
        if n < note:
            meilleur, note = essai, n
    return {"seule": seule, "deux": deux, "tout": {k: round(v, 3) for k, v in meilleur.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier", type=Path)
    ap.add_argument("--tirages", type=int, default=4000)
    a = ap.parse_args()
    vues = charger(a.dossier)
    if not vues:
        print(f"PLANTÉ : aucune vue complète dans {a.dossier}", flush=True)
        return 1
    p = photographe.PELLICULE
    depart = {"crans": 0.0, "pente": p["film_slope"], "pied": p["film_toe"], "epaule": p["film_shoulder"],
              "vivacite": photographe.PELLICULE_COULEURS["saturation"]}
    lignes = [f"{len(vues)} vues ; écarts moyens film − photo (clarté L et vivacité C, en points CIELAB)"]

    def dire(titre, r):
        note, e = ecarts(vues, r)
        lignes.append(f"{titre:<34} note {note:5.1f} | murs {e['murs_L']:+5.1f} | sol clarté {e['sol_L']:+5.1f} vivacité {e['sol_C']:+5.1f} | image "
                      f"sombres {e['L5']:+5.1f} milieu {e['L50']:+5.1f} clairs {e['L95']:+5.1f} vivacité {e['C']:+5.1f} | "
                      + " ".join(f"{k} {v:.3g}" for k, v in r.items()))
        return note

    dire("le film d'aujourd'hui", depart)
    r = chercher(vues, depart, a.tirages)
    dire("exposition seule", r["seule"])
    dire("exposition + vivacité", r["deux"])
    dire("exposition + courbe + vivacité", r["tout"])
    meilleur = r["tout"]
    # le réglage tient-il sur un logement qu'il n'a PAS vu ? cherché sur deux logements, noté sur le troisième
    logements = sorted({v["nom"].split()[0] for v in vues})
    if len(logements) >= 3:
        lignes.append("")
        lignes.append("réglage cherché sans un logement, puis noté sur ce logement (avant -> avec ce réglage | avec le réglage de tous) :")
        for cas in logements:
            dehors = [v for v in vues if v["nom"].split()[0] == cas]
            autres = [v for v in vues if v["nom"].split()[0] != cas]
            sans = chercher(autres, depart, a.tirages // 2)["tout"]
            lignes.append(f"  sans {cas} : note sur {cas} {ecarts(dehors, depart)[0]:.1f} -> {ecarts(dehors, sans)[0]:.1f} | "
                          f"{ecarts(dehors, meilleur)[0]:.1f} ; " + " ".join(f"{k} {v:.3g}" for k, v in sans.items()))
    lignes.append("")
    lignes.append("par vue, avec ce dernier réglage (film − photo) :")
    for vue in vues:
        m = mesures(vue, meilleur)
        lignes.append(f"  {vue['nom']:<18} murs {m['murs_L'] - vue['cible']['murs_L']:+5.1f} | sol clarté {m['sol_L'] - vue['cible']['sol_L']:+5.1f} "
                      f"vivacité {m['sol_C'] - vue['cible']['sol_C']:+5.1f} | image milieu {m['L50'] - vue['cible']['L50']:+5.1f}")
    (a.dossier / "prevision-reglages-image.txt").write_text("\n".join(lignes), encoding="utf-8")
    (a.dossier / "prevision-reglages-image.json").write_text(json.dumps(meilleur, indent=1), encoding="utf-8")
    print("\n".join(lignes), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
