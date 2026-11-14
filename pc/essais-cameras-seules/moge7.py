"""Diagnostic : la note de la BONNE place (celle de la main, réglée finement) contre celle de la place gagnante."""
import json, os, sys
from pathlib import Path
import numpy as np
import etape_b as eb
import moge5 as m5

src = Path(sys.argv[1])
gagnants = json.loads((Path(sys.argv[2]) / f"candidats-{m5.MODE}.json").read_text(encoding="utf-8"))
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
    mod = dict(mod, sorte=mod["genre"].copy(), genre=np.zeros_like(mod["genre"]))
    for nom, c in d["cameras"].items():
        k = c["camera"]; z = np.load(src / f"{app}-{nom}.npz")
        asp = np.load(src.parent / "aspect" / f"{app}-{nom}.npy") if m5.MODE == "aspect" else None
        ph, rm, creux, sol, info = m5.profil(z, mod["hsp"], asp)
        meill = (None, -1)
        for dx in (-0.8, -0.4, 0, 0.4, 0.8):
            for dy in (-0.8, -0.4, 0, 0.4, 0.8):
                for e in (0.8, 0.9, 1.0):
                    q = np.array([k["x"] + dx, k["y"] + dy, k["cap"], e])
                    if eb.piece_de(mod, q[None, :2])[0] < 0:
                        continue
                    r = m5.precis(mod, ph, rm, creux, sol, q)
                    if r[1] > meill[1]:
                        meill = r
        if meill[0] is None:
            print(app, nom, ": la place de la main est hors du logement"); continue
        cam, n = meill
        g = gagnants[f"{app}-{nom}"][0]
        print(f"{app} {nom} : bonne place réglée → note {n:.2f} (à {np.hypot(cam[0]-k['x'], cam[1]-k['y']):.2f} m de la main, cap {abs((cam[2]-k['cap']+180)%360-180):.0f}°, échelle {cam[3]:.2f}) | gagnante {g[4]:.2f}", flush=True)
