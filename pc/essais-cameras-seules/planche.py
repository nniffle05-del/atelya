"""Planche d'images : ce qu'Atelya reconnaît comme ouvertures (orange = par le relief, vert = fenêtre par l'aspect)."""
import json, sys, cv2, numpy as np
from pathlib import Path
from moteur.images import lire_image, ecrire_image
import moge4 as m4
S = Path(sys.argv[1]); lignes = []
for app, noms in (("app-002", ["photo-04", "photo-14", "photo-10"]), ("app-001", ["photo-08", "photo-10", "photo-05"])):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    hsp = float(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))["hauteur_sous_plafond"])
    for nom in noms:
        im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
        z = np.load(S / "moge" / f"{app}-{nom}.npz"); R = m4.repere(z, hsp); mur = m4.mur_par_direction(R, hsp); rel, _ = m4.relief(R, mur)
        cr = m4.creux_propres(R, rel, hsp) & (R["h"] > 0.1)
        a = np.load(S / "aspect" / f"{app}-{nom}.npy").astype(np.float32); H, W = im.shape[:2]
        fen = (cv2.resize(a[..., 2], (W, H)) > 0.5) & ~np.isnan(rel) & (rel > -0.35) & (R["h"] > 0.3) & (R["h"] < hsp - 0.1)
        vis = (im * 0.5).astype(np.float32)
        vis[fen] = 0.45 * vis[fen] + 0.55 * np.array((0, 220, 0)); vis[cr] = 0.45 * vis[cr] + 0.55 * np.array((0, 150, 255))
        l = np.hstack([im, vis.astype(np.uint8)]); lignes.append(cv2.resize(l, (1600, int(l.shape[0] * 1600 / l.shape[1]))))
ecrire_image(S / "planche-portes-fenetres.jpg", np.vstack(lignes))
