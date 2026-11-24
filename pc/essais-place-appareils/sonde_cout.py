r"""Sonde : ce que valent, devant les lignes du plafond et du sol trouvées seules, l'appareil du corrigé, celui du service et
l'appareil affiné (une ligne par photo). Avec --images <dossier> : la photo avec les points trouvés (plafond jaune, sol cyan)
et les murs du plan vus par l'appareil du corrigé (vert), du service (rouge) et affiné (bleu)."""
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE)); sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from moteur.affiner_appareils import CACHE_MUR, Scene, cache_mur, cout, jonctions, tirer  # noqa: E402
from caler import cas  # noqa: E402
from juger import CORRIGES, SORTIE, lire  # noqa: E402
from moteur import caler_photos as cp, moge  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import ecrire_image  # noqa: E402


def lignes_du_plan(cam, A, B, hsp, W, portes=None):
    x, y, z, cap, _, f, u0, v0 = cam
    u = np.arange(0, W, 4.0)
    th = np.arctan((u - u0) / f)
    rho = tirer(A, B, np.array([x, y]), cap - np.degrees(th), portes)
    p = np.maximum(rho * np.cos(th), 1e-3)
    return u, v0 - f * (hsp - z) / p, v0 + f * z / p


def main():
    noms = [a for a in sys.argv[1:] if a.startswith("app-")]
    variantes = [a for a in sys.argv[1:] if not a.startswith("app-") and not a.startswith("--") and (SORTIE / a).is_dir()]
    images = Path(sys.argv[sys.argv.index("--images") + 1]) if "--images" in sys.argv else None
    toutes = "--toutes-les-faces" in sys.argv
    modele = moge.charger("cuda" if torch.cuda.is_available() else "cpu")
    from moteur.pas_du_sol import charger as charger_pds
    owl = charger_pds("cuda" if torch.cuda.is_available() else "cpu", avec_dino=False).owl
    requetes = owl.textes(list(CACHE_MUR))
    for nom in noms:
        c = cas(nom)
        sc = Scene(c["logement"])
        A, B, hsp, portes = sc.A, sc.B, sc.hsp, sc.portes
        corr = lire(CORRIGES[nom])["cameras"] if nom in CORRIGES else {}
        fiches = {v: lire(SORTIE / v / f"{nom}.json")["cameras"] for v in variantes}
        for n in sorted(c["photos"]):
            if "--photos" in sys.argv and n not in sys.argv:
                continue
            rgb = c["photos"][n]
            caches = cache_mur(owl, requetes, rgb)
            jon = jonctions(cp.mesurer(modele, rgb), hsp, caches)
            cams = {"corrigé": corr.get(n), **{v: fiches[v].get(n) for v in variantes}}
            txt = []
            for k, d in cams.items():
                if d is None:
                    continue
                r = cout(np.array(camera_depuis_dict(d["camera"])), sc, jon, None, detail=True)
                txt.append(f"{k} " + "/".join(f"{r.get(q, float('nan')):.0f}" for q in ("plafond", "sol")))
            print(f"{nom} {n} plafond {len(jon['plafond'])} sol {len(jon['sol'])} | " + " | ".join(txt), flush=True)
            if images is not None:
                im = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR).copy()
                im[caches] = (im[caches] * 0.75 + np.array([40, 0, 40])).astype(np.uint8)
                for (u, v) in jon["plafond"]:
                    cv2.circle(im, (int(u), int(v)), 2, (0, 255, 255), -1)
                for (u, v) in jon["sol"]:
                    cv2.circle(im, (int(u), int(v)), 2, (255, 255, 0), -1)
                for (k, d), coul in zip(cams.items(), [(0, 200, 0), (0, 0, 255), (255, 80, 0), (255, 0, 255)]):
                    if d is None:
                        continue
                    u, vp, vs = lignes_du_plan(np.array(camera_depuis_dict(d["camera"])), A, B, hsp, rgb.shape[1], portes)
                    for vv in (vp, vs):
                        pts = np.stack([u, np.clip(vv, -50, rgb.shape[0] + 50)], 1).astype(np.int32)
                        cv2.polylines(im, [pts], False, coul, 1, cv2.LINE_AA)
                    cv2.putText(im, k, (10, 20 + 18 * list(cams).index(k)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, coul, 1, cv2.LINE_AA)
                images.mkdir(parents=True, exist_ok=True)
                ecrire_image(images / f"{nom}-{n}.jpg", im)


main()
