import json, sys
from pathlib import Path
import cv2
from moteur.images import lire_image
from moteur import pas_du_sol as pds
p = pds.charger(avec_dino=False)
res = {}
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    for nom in d["cameras"]:
        im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
        b = p.brut(f"{app}/{nom}", cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        res[f"{app}/{nom}"] = [{"nom": o["nom"], "note": float(o["note"]), "boite": [float(x) for x in o["boite"]]} for o in b["objets"]]
        print(app, nom, sorted({(o["nom"], round(float(o["note"]), 2)) for o in b["objets"] if o["note"] >= 0.2}, key=lambda x: -x[1])[:9], flush=True)
(Path(sys.argv[1]) / "objets.json").write_text(json.dumps(res), encoding="utf-8")
