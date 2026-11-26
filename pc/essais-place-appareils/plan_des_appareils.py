r"""Deux variantes du calage à REGARDER : la photo du client à gauche, le plan à droite avec l'appareil de chaque variante
(rouge = la première, bleu = la seconde, vert = le relevé à la main quand il existe) et son champ de vision.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\plan_des_appareils.py <avant> <après> <sortie> app-002:photo-12 app-004:photo-06 …

Sur le plan : murs en noir, portes en orange, fenêtres en bleu clair, nom des pièces.
"""
import math
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from caler import cas  # noqa: E402
from juger import CORRIGES, SORTIE, lire  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import ecrire_image  # noqa: E402

COTE = 900


def dessin_du_plan(logement: dict, cams: list[tuple[dict, tuple]], piece: str | None) -> np.ndarray:
    plan = cp.plan_du_logement(logement)
    tout = np.concatenate(plan["pieces"])
    if piece in plan["ids"]:  # cadré sur la pièce de la photo et ses voisines
        c = plan["pieces"][plan["ids"].index(piece)]
        x0, y0 = c.min(0) - 2.0; x1, y1 = c.max(0) + 2.0
    else:
        x0, y0 = tout.min(0) - 0.5; x1, y1 = tout.max(0) + 0.5
    for d, _ in cams:
        x0, y0, x1, y1 = min(x0, d["x"] - 0.5), min(y0, d["y"] - 0.5), max(x1, d["x"] + 0.5), max(y1, d["y"] + 0.5)
    k = COTE / max(x1 - x0, y1 - y0)
    px = lambda p: (int(round((p[0] - x0) * k)), int(round((y1 - p[1]) * k)))  # noqa: E731  (le nord du plan en haut)
    im = np.full((int((y1 - y0) * k) + 1, int((x1 - x0) * k) + 1, 3), 255, np.uint8)
    for a, b, s in zip(plan["A"], plan["B"], plan["sorte"]):
        cv2.line(im, px(a), px(b), [(0, 0, 0), (0, 140, 255), (255, 190, 80)][int(s)], 3 if s == 0 else 5, cv2.LINE_AA)
    for i, c in zip(plan["ids"], plan["pieces"]):
        cv2.putText(im, i, px(c.mean(0) - np.array([0.6, 0.0])), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1, cv2.LINE_AA)
    for d, coul in cams:
        o = np.array([d["x"], d["y"]])
        demi = math.degrees(math.atan(d["u0"] / d["f"]))
        for a in (d["cap"] - demi, d["cap"] + demi, d["cap"]):
            r = 3.0 if a != d["cap"] else 1.0
            cv2.line(im, px(o), px(o + r * np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])), coul, 2 if a == d["cap"] else 1, cv2.LINE_AA)
        cv2.circle(im, px(o), 7, coul, -1, cv2.LINE_AA)
    return im


def main():
    a, b, sortie = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    sortie.mkdir(parents=True, exist_ok=True)
    par_logement = {}
    for x in sys.argv[4:]:
        l, n = x.split(":")
        par_logement.setdefault(l, []).append(n)
    for l, noms in par_logement.items():
        c = cas(l)
        fa, fb = lire(SORTIE / a / f"{l}.json")["cameras"], lire(SORTIE / b / f"{l}.json")["cameras"]
        main_ = lire(CORRIGES[l])["cameras"] if l in CORRIGES else {}
        for n in noms:
            cams = [(fa[n]["camera"], (0, 0, 230)), (fb[n]["camera"], (230, 80, 0))]
            if n in main_:
                cams.append((main_[n]["camera"], (0, 170, 0)))
            p = dessin_du_plan(c["logement"], cams, fb[n].get("piece"))
            photo = cv2.cvtColor(c["photos"][n], cv2.COLOR_RGB2BGR)
            h = 700
            photo = cv2.resize(photo, (int(photo.shape[1] * h / photo.shape[0]), h))
            p = cv2.resize(p, (int(p.shape[1] * h / p.shape[0]), h))
            planche = np.concatenate([photo, np.full((h, 12, 3), 255, np.uint8), p], 1)
            cv2.putText(planche, f"{l} {n} ({fb[n].get('piece')}) : rouge = {a}, bleu = {b}" + (", vert = main" if n in main_ else ""), (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(planche, f"{l} {n} ({fb[n].get('piece')}) : rouge = {a}, bleu = {b}" + (", vert = main" if n in main_ else ""), (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            ecrire_image(sortie / f"{l}-{n}.jpg", planche)
            print(sortie / f"{l}-{n}.jpg", flush=True)


if __name__ == "__main__":
    main()
