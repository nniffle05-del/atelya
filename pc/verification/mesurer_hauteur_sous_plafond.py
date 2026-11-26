r"""LE SOL PRIS POUR UN LIT, 2e TEMPS (25/11/2026) : la HAUTEUR SOUS PLAFOND d'après les photos, avec la règle d'aujourd'hui
(moteur.hauteur_photos : les deux plus GRANDES surfaces à plat) et avec la règle partagée (moteur.caler_photos.sol_et_plafond :
le sol = la plus basse, le plafond = la plus haute). MESURE seulement : rien n'est changé.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_hauteur_sous_plafond.py

Sur les quatre logements, photo par photo (relief de MoGe-2 au zoom libre, comme en service), puis la médiane arrondie à 5 cm.
Ce qu'on sait de la vraie hauteur : app-001 « HSP 3m » écrit sur le plan ; app-002 2,50 m (relevé) ; app-003 2,90 m (estimée à
la main d'après les photos) ; app-004 inconnue (2,70 m estimés par Atelya à l'examen).
Sortie : ..\atelya\b2\sol-des-photos\hauteur-sous-plafond\mesure.json
"""
import json
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pc" / "essais-place-appareils"))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
sys.path.insert(0, str(RACINE / "pc" / "essais-cameras-seules"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import caler_photos as cp, moge  # noqa: E402
from moteur.hauteur_photos import ARRONDI, PHOTOS_MIN, VRAISEMBLABLE, hauteur_d_une_photo  # noqa: E402
from caler import cas  # noqa: E402

SORTIE = RACINE.parent / "atelya" / "b2/sol-des-photos/hauteur-sous-plafond"
CONNUE = {"app-001": (3.0, "écrite sur le plan"), "app-002": (2.5, "relevé"), "app-003": (2.9, "estimée à la main"), "app-004": (None, "inconnue")}


def partagee(mes: dict) -> float | None:
    h = mes["points"] @ mes["haut"]
    horiz = mes["masque"] & (np.abs(mes["normales"] @ mes["haut"]) > 0.95)
    sol, plaf = cp.sol_et_plafond(h, horiz)
    return None if sol is None or plaf is None else float(plaf - sol)


def mediane(v: list) -> tuple[float | None, float | None, int]:
    bonnes = [x for x in v if x is not None and VRAISEMBLABLE[0] <= x <= VRAISEMBLABLE[1]]
    if len(bonnes) < PHOTOS_MIN:
        return None, None, len(bonnes)
    m = float(np.median(bonnes))
    return round(round(m / ARRONDI) * ARRONDI, 2), m, len(bonnes)


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    modele = moge.charger()
    bilan = {}
    for nom in ("app-001", "app-002", "app-003", "app-004"):
        c = cas(nom)
        b = bilan[nom] = {"connue": CONNUE[nom][0], "photos": {}}
        for n in sorted(c["photos"]):
            mes = cp.mesurer(modele, c["photos"][n])
            a, p = hauteur_d_une_photo(mes), partagee(mes)
            b["photos"][n] = {"aujourd_hui": a, "partagee": p, "piece": c["pieces"].get(n)}
            if a is None or p is None or abs(a - p) > 0.03:
                f = lambda x: "  -  " if x is None else f"{x:5.2f}"  # noqa: E731
                print(f"  {nom} {n} ({c['pieces'].get(n)}) : {f(a)} → {f(p)} m", flush=True)
        for cle in ("aujourd_hui", "partagee"):
            b[cle] = mediane([p[cle] for p in b["photos"].values()])
        v = CONNUE[nom]
        print(f"{nom} : aujourd'hui {b['aujourd_hui'][0]} m (médiane {b['aujourd_hui'][1]:.3f}, {b['aujourd_hui'][2]} photos) ; règle partagée "
              f"{b['partagee'][0]} m (médiane {b['partagee'][1]:.3f}, {b['partagee'][2]} photos) ; vraie : {v[0] if v[0] else '?'} ({v[1]})", flush=True)
        # la médiane tient-elle à une photo près ? (chaque photo retirée à son tour)
        for cle in ("aujourd_hui", "partagee"):
            noms = list(b["photos"])
            vues = sorted({mediane([b["photos"][m][cle] for m in noms if m != n])[0] for n in noms}, key=lambda x: (x is None, x))
            b[f"{cle}_sans_une"] = vues
            print(f"     {cle} : en retirant une photo, la hauteur vaut {vues}")
    (SORTIE / "mesure.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
