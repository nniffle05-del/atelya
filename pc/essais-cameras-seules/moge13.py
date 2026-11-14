"""Le ZOOM trouvé seul, 2e idée : un zoom faux étire la profondeur, donc les murs ne sont plus d'ÉQUERRE entre eux.
On cherche l'étirement qui remet les murs à angle droit. Noté contre le zoom de la main.
RÉSULTAT (14/11/2026) : ÉCARTÉ. Les murs sont déjà d'équerre dans la mesure de MoGe-2 ; l'étirement trouvé est pire que rien
(écart médian 18 % contre 10 %, à moins de 10 % : 11 → 6 photos sur 22)."""
import json, sys
from pathlib import Path
import numpy as np
import etape_b as eb
import moge4 as m4

ETIREMENTS = np.arange(0.60, 1.451, 0.01)


def equerre(R, hsp):
    """→ (étirement s : profondeur vraie = mesurée / s ; netteté de l'équerre à s ; netteté sans correction ; part du 2e mur)."""
    m = R["M"] & R["vert"] & R["devant"] & (R["h"] > 1.2) & (R["h"] < hsp - 0.04)
    na, nb = R["n_a"][m][::7], R["n_b"][m][::7]
    if len(na) < 2000:
        return None
    net = []
    for s in ETIREMENTS:
        t = np.arctan2(s * nb, na)
        net.append(np.hypot(np.cos(4 * t).mean(), np.sin(4 * t).mean()))
    net = np.array(net); i = int(net.argmax())
    t = np.arctan2(ETIREMENTS[i] * nb, na); t0 = 0.25 * np.arctan2(np.sin(4 * t).mean(), np.cos(4 * t).mean())
    fam = np.cos(2 * (t - t0)) > 0  # les deux familles de murs
    return float(ETIREMENTS[i]), float(net[i]), float(net[np.argmin(np.abs(ETIREMENTS - 1))]), float(min(fam.mean(), 1 - fam.mean()))


if __name__ == "__main__":
    src = Path(sys.argv[1]); L = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        hsp = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))["hsp"]
        for nom, c in d["cameras"].items():
            z = np.load(src / f"{app}-{nom}.npz")
            vrai = float(z["focale"]) / (c["camera"]["f"] * z["masque"].shape[1] / c["largeur"])
            r = equerre(m4.repere(z, hsp), hsp)
            if r is None:
                print(app, nom, "pas assez de murs"); continue
            s, n1, n0, part = r
            L.append((vrai, s, part))
            print(f"{app} {nom} [{c.get('qualite')}] étirement vrai (main) {vrai:.2f} | trouvé par l'équerre {s:.2f} | netteté {n0:.2f} → {n1:.2f} | 2e mur : {100 * part:.0f} % des points", flush=True)
    L = np.array(L)
    for nom, sel in (("toutes", L[:, 2] >= 0), ("2e mur ≥ 15 %", L[:, 2] >= 0.15), ("2e mur ≥ 25 %", L[:, 2] >= 0.25)):
        v = L[sel]
        print(f"{nom:14s} ({len(v):2d} photos) : écart médian sans correction {100 * np.median(np.abs(v[:, 0] - 1)):.0f} % | après équerre {100 * np.median(np.abs(v[:, 0] / v[:, 1] - 1)):.0f} % | "
              f"à moins de 10 % : {int((np.abs(v[:, 0] - 1) < 0.1).sum())} → {int((np.abs(v[:, 0] / v[:, 1] - 1) < 0.1).sum())}")
