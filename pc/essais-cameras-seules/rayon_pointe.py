r"""JUSQU'OÙ ATELYA S'ÉCARTE-T-IL D'UN ENDROIT POINTÉ PAR NT ? (16/11/2026, étape « endroit douteux »)

Quand NT pointe d'où une photo est prise, Atelya cherche l'appareil à moins de RAYON_POINTE du point (1,5 m depuis le
15/11/2026). Constat sur la cuisine d'app-002 : pointée au bon endroit, la photo glisse quand même à 1,7 m. Faut-il rester
plus près de la réponse de NT ?

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\rayon_pointe.py [app-001 app-002 app-003]

Chaque photo qui a un relevé est POINTÉE comme le ferait NT : à 0,5 m de la vraie place (il ne pointe pas au centimètre ;
décalage tiré au sort, graine fixe), le sens du regard à 20° près. Le calage est rejoué avec plusieurs rayons ; on compare
l'écart final à la vraie place. Conditions du service (fenêtres vues par la couche en service).
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from jumelles import LOGEMENTS, memoire  # noqa: E402
from pieces_donnees import CLIENT, RELEVES  # noqa: E402

RAYONS = (1.5, 1.0, 0.75, 0.5)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(noms):
    o = cp.Outils()
    memoire(o)
    gardees, tout = [], {r: [] for r in RAYONS}
    for nom in noms:
        f = LOGEMENTS[nom]
        logement = json.loads(f["logement"].read_text(encoding="utf-8"))
        photos = {n: cv2.cvtColor(lire_image(f["photos"] / f"{n}.{f['ext']}"), cv2.COLOR_BGR2RGB) for n in f["vrai"]}
        gardees.append(photos)
        client = {n: CLIENT.get(nom, {}).get(n, v[0]) for n, v in f["vrai"].items()}
        sorte = {n: cp.sorte_de_piece(p) for n, p in client.items() if p}
        releves = [json.loads(r.read_text(encoding="utf-8")) for r in RELEVES[nom]]
        vraies = {n: next((x["cameras"][n]["camera"] for x in releves if n in x["cameras"]), None) for n in photos}
        rng = np.random.default_rng(2026)
        endroits = {}
        for n, v in vraies.items():
            if v is None:
                continue
            a = rng.uniform(0, 2 * math.pi)
            endroits[n] = (v["x"] + 0.5 * math.cos(a), v["y"] + 0.5 * math.sin(a), v["cap"] + float(rng.choice([-20.0, 20.0])))
        print(f"\n{nom} : {len(endroits)} photos pointées à 0,5 m de leur vraie place")
        lignes = {}
        for rayon in RAYONS:
            cp.RAYON_POINTE = rayon
            r = cp.caler(logement, photos, outils=o, journal=lambda *a: None, pieces_donnees=sorte, endroits_donnes=endroits)
            for n, v in vraies.items():
                if v is None:
                    continue
                d = r["cameras"].get(n)
                e = None if d is None else (math.hypot(d["camera"]["x"] - v["x"], d["camera"]["y"] - v["y"]), abs((d["camera"]["cap"] - v["cap"] + 180) % 360 - 180),
                                            d["piece"] in f["vrai"][n])
                lignes.setdefault(n, {})[rayon] = e
                tout[rayon].append((nom, n, e))
        for n, parr in sorted(lignes.items()):
            print(f"  {n} " + " | ".join(f"{r} m : " + ("PERDUE     " if e is None else f"{e[0]:.2f} m {e[1]:3.0f}°{'' if e[2] else ' PIÈCE FAUSSE'}") for r, e in parr.items()))
    cp.RAYON_POINTE = 1.5
    print("\nBILAN (toutes les photos pointées)")
    for rayon, v in tout.items():
        ok = np.array([e[:2] for _, _, e in v if e is not None])
        petites = np.array([e[0] for lg, n, e in v if e is not None and cp.sorte_de_piece((CLIENT.get(lg, {}).get(n) or LOGEMENTS[lg]["vrai"][n][0])) in cp.PETITES_PIECES])
        print(f"  rayon {rayon} m : {len(ok)} placées sur {len(v)}, perdues {sum(e is None for _, _, e in v)}, pièce fausse {sum(e is not None and not e[2] for _, _, e in v)} ; "
              f"écart médian {np.median(ok[:, 0]):.2f} m, moyen {ok[:, 0].mean():.2f} m, pire {ok[:, 0].max():.2f} m ; à plus de 1 m : {int((ok[:, 0] > 1).sum())} ; "
              f"cap médian {np.median(ok[:, 1]):.0f}°, à plus de 45° : {int((ok[:, 1] > 45).sum())} ; petites pièces : {np.round(petites, 2).tolist()}")


if __name__ == "__main__":
    try:
        main([a for a in sys.argv[1:] if not a.startswith("--")] or list(LOGEMENTS))
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
