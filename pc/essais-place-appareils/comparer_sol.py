r"""LE SOL PRIS POUR UN LIT, 2e TEMPS (25/11/2026) : deux variantes du calage comparées photo par photo.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\comparer_sol.py <avant> <après> [--tout]

Pour chaque photo des quatre logements : la pièce, « sûre » ou non, de combien l'appareil a bougé (mètres, cap), sa HAUTEUR
(avant → après, et celle du relevé à la main quand il existe), son zoom, ce que l'affinage a fait. Sans --tout : seulement les
photos qui changent (pièce, sûre, plus de 5 cm, plus de 0,5°). Puis le bilan : photos placées, sûres, hauteur de l'appareil
contre les relevés à la main (écart moyen, toutes les photos puis les seules photos non affinées), place contre les corrigés.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from juger import CORRIGES, SORTIE, lire  # noqa: E402

LOGEMENTS = ("app-001", "app-002", "app-003", "app-004")


def main():
    a, b = [x for x in sys.argv[1:] if not x.startswith("--")][:2]
    tout = "--tout" in sys.argv
    bilan = {v: {"placees": 0, "sures": 0, "dz": [], "dz_depart": [], "m": [], "affinees": 0} for v in (a, b)}
    change = 0
    for l in LOGEMENTS:
        fa, fb = lire(SORTIE / a / f"{l}.json"), lire(SORTIE / b / f"{l}.json")
        ca, cb = fa["cameras"], fb["cameras"]
        main_ = lire(CORRIGES[l])["cameras"] if l in CORRIGES else {}
        for v, c in ((a, ca), (b, cb)):
            t = bilan[v]
            t["placees"] += len(c); t["sures"] += sum(d["sure"] for d in c.values())
            t["affinees"] += sum(d.get("affine", {}).get("comment", "depart") != "depart" for d in c.values())
            for n, d in c.items():
                if n in main_:
                    k = main_[n]["camera"]
                    t["dz"].append(abs(d["camera"]["z"] - k["z"]))
                    t["m"].append(math.hypot(d["camera"]["x"] - k["x"], d["camera"]["y"] - k["y"]))
                    if d.get("affine", {}).get("comment", "depart") == "depart":
                        t["dz_depart"].append(abs(d["camera"]["z"] - k["z"]))
        for n in sorted(set(ca) | set(cb)):
            da, db = ca.get(n), cb.get(n)
            if da is None or db is None:
                print(f"{l} {n} : placée seulement dans « {a if db is None else b} » ({(fa if da is None else fb)['non_calees'].get(n)})")
                change += 1
                continue
            xa, xb = da["camera"], db["camera"]
            bouge = math.hypot(xa["x"] - xb["x"], xa["y"] - xb["y"])
            cap = abs((xa["cap"] - xb["cap"] + 180) % 360 - 180)
            diff = da["piece"] != db["piece"] or da["sure"] != db["sure"] or bouge > 0.05 or cap > 0.5 or abs(xa["z"] - xb["z"]) > 0.05
            change += diff
            if not (diff or tout):
                continue
            k = main_.get(n, {}).get("camera")
            vrai = f" (main {k['z']:.2f})" if k else ""
            metres = (f" | au corrigé {math.hypot(xa['x'] - k['x'], xa['y'] - k['y']):.2f} → {math.hypot(xb['x'] - k['x'], xb['y'] - k['y']):.2f} m" if k else "")
            af = lambda d: d.get("affine", {}).get("comment", "-")
            zc = lambda d: d.get("affine", {}).get("avant", {}).get("z", d["camera"]["z"])
            print(f"{l} {n} : {da['piece']}{' sûre' if da['sure'] else ''} → {db['piece']}{' sûre' if db['sure'] else ''} | bouge {bouge:.2f} m, cap {cap:.1f}°"
                  f" | hauteur {xa['z']:.2f} → {xb['z']:.2f}{vrai} [au calage {zc(da):.2f} → {zc(db):.2f}] | zoom {xa['f']:.0f} → {xb['f']:.0f} | affinage {af(da)} → {af(db)}{metres}")
    print(f"\n{change} photos changent")
    for v, t in bilan.items():
        m = np.array(t["m"]) if t["m"] else np.array([np.nan])
        print(f"{v:14s} : {t['placees']} placées, {t['sures']} sûres, {t['affinees']} affinées | hauteur de l'appareil contre la main : écart moyen "
              f"{np.mean(t['dz']):.2f} m ({len(t['dz'])} photos), non affinées {np.mean(t['dz_depart']) if t['dz_depart'] else float('nan'):.2f} m ({len(t['dz_depart'])})"
              f" | place contre la main : médiane {np.median(m):.2f}, moyenne {m.mean():.2f}, pire {m.max():.2f} m")


if __name__ == "__main__":
    main()
