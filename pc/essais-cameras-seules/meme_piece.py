"""Deux photos montrent-elles la MÊME pièce ? Ressemblance des empreintes DINOv2 (image entière), contre le relevé à la main."""
import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image
from moteur import oeil_dinov2 as od
import etape_b as eb

S = Path(sys.argv[1]); oeil = od.charger("vitb14"); res = {}
for app in ("app-002", "app-001"):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
    noms = list(d["cameras"])
    ims = np.stack([cv2.cvtColor(cv2.resize(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=n)), (518, 350)), cv2.COLOR_BGR2RGB) for n in noms])
    e = od.empreintes(oeil, ims)
    sim = e @ e.T
    pieces = [mod["ids"][eb.piece_de(mod, np.array([[d["cameras"][n]["camera"]["x"], d["cameras"][n]["camera"]["y"]]]))[0]] for n in noms]
    m, a = [], []
    for i in range(len(noms)):
        for j in range(i + 1, len(noms)):
            (m if pieces[i] == pieces[j] else a).append(sim[i, j])
    print(app, f"même pièce : {np.mean(m):.2f} (min {np.min(m):.2f}, {len(m)} paires) | pièces différentes : {np.mean(a):.2f} (max {np.max(a):.2f}, {len(a)} paires)")
    np.set_printoptions(precision=2, linewidth=250, suppress=True)
    print([f"{n[-2:]}:{p[:4]}{p[-1]}" for n, p in zip(noms, pieces)]); print(sim)
    res[app] = {"noms": noms, "sim": sim.tolist()}
(S / "meme-piece.json").write_text(json.dumps(res), encoding="utf-8")
