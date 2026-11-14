"""Deux réseaux indépendants (Depth Anything 3 « base », MapAnything « apache ») contre le relevé à la main : quand les deux
réseaux sont d'accord ENTRE EUX mais pas avec la main, c'est le relevé à la main qui est douteux (ou la photo trop dure pour
les deux). Lit les places écrites par moge14 (da3-poses.json) et moge20 (mapanything-poses.json), lots PIECE."""
import json, sys
from itertools import combinations
from pathlib import Path
import numpy as np


def rot(p, a, b):
    return float(np.degrees(p[b][2] - p[a][2]))


def ecart(x, y):
    return abs((x - y + 180) % 360 - 180)


if __name__ == "__main__":
    S = Path(sys.argv[1])
    A = json.loads((S / "pose" / "da3-poses.json").read_text(encoding="utf-8"))
    B = json.loads((S / "pose" / "mapanything-poses.json").read_text(encoding="utf-8"))
    L = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))["cameras"]
        for piece in A[app]:
            if piece == "tout" or piece not in B[app]:
                continue
            pa, pb = A[app][piece], B[app][piece]
            par_photo = {n: [] for n in pa}
            for a, b in combinations(list(pa), 2):
                vrai = d[b]["camera"]["cap"] - d[a]["camera"]["cap"]
                e_ab, e_am, e_bm = ecart(rot(pa, a, b), rot(pb, a, b)), ecart(rot(pa, a, b), vrai), ecart(rot(pb, a, b), vrai)
                L.append((e_ab, e_am, e_bm))
                for n in (a, b):
                    par_photo[n].append((e_ab, e_am, e_bm))
            for n, v in par_photo.items():
                v = np.array(v)
                print(f"{app} {piece:10s} {n} [{d[n].get('qualite')}] | rotation, médiane sur ses paires : les deux réseaux entre eux {np.median(v[:, 0]):5.1f}° | "
                      f"DA3 contre la main {np.median(v[:, 1]):5.1f}° | MapAnything contre la main {np.median(v[:, 2]):5.1f}°")
    L = np.array(L)
    print(f"{len(L)} paires | réseaux d'accord entre eux à moins de 8° : {int((L[:, 0] < 8).sum())} | dont en désaccord avec la main de plus de 12° (les deux) : "
          f"{int(((L[:, 0] < 8) & (L[:, 1] > 12) & (L[:, 2] > 12)).sum())} | dont d'accord avec la main à moins de 8° (les deux) : {int(((L[:, 0] < 8) & (L[:, 1] < 8) & (L[:, 2] < 8)).sum())}")
    print(f"écart médian : entre réseaux {np.median(L[:, 0]):.1f}° | DA3 / main {np.median(L[:, 1]):.1f}° | MapAnything / main {np.median(L[:, 2]):.1f}°")
