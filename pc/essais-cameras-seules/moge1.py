"""MoGe-2 sur les 22 photos calées à la main : zoom, hauteur de l'appareil, hauteur sous plafond, contre la main."""
import json, sys, time
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
from moteur import moge
import etape_b as eb

sortie = Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
m = moge.charger()


def verticale(r):
    """Le « haut » dans le repère de l'appareil, d'après les surfaces horizontales (sol, plafond, tables)."""
    n, ok = r["normales"][::4, ::4].reshape(-1, 3), r["masque"][::4, ::4].ravel()
    n = n[ok]
    haut = np.array([0.0, -1.0, 0.0])
    for seuil in (0.8, 0.9, 0.96, 0.98):
        c = n @ haut
        s = n[np.abs(c) > seuil]
        if len(s) < 50:
            break
        s = s * np.sign(s @ haut)[:, None]
        haut = s.mean(0); haut /= np.linalg.norm(haut)
    return haut


def pic(v, pas=0.02):
    if len(v) < 30:
        return None
    h, b = np.histogram(v, bins=np.arange(v.min(), v.max() + pas, pas))
    h = np.convolve(h, np.ones(3), "same")
    return float(b[h.argmax()] + pas / 2)


if __name__ == "__main__":
    lignes = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        hsp = eb.modele(log)["hsp"]
        for nom, c in d["cameras"].items():
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
            t = time.time(); r = moge.lire(m, rgb); dt = time.time() - t
            np.savez_compressed(sortie / f"{app}-{nom}.npz", points=r["points"].astype(np.float16), masque=r["masque"],
                                normales=r["normales"].astype(np.float16), focale=r["focale_px"],
                                brut=r["brut"].astype(np.float32), masque_brut=r["masque_brut"], echelle=r["echelle"])
            k = c["camera"]
            haut = verticale(r)
            p, n, ok = r["points"][::4, ::4].reshape(-1, 3), r["normales"][::4, ::4].reshape(-1, 3), r["masque"][::4, ::4].ravel()
            hh = p[ok] @ haut; horiz = np.abs(n[ok] @ haut) > 0.95
            sol, plaf = pic(hh[horiz & (hh < -0.4)]), pic(hh[horiz & (hh > 0.3)])
            tang = np.degrees(np.arcsin(-haut[2]))  # regard vers le haut = positif ?
            print(f"{app} {nom} [{c.get('qualite')}] focale {r['focale_px']:.0f} / main {k['f']:.0f} | appareil à {(-sol if sol else np.nan):.2f} m / main {k['z']:.2f}"
                  f" | plafond {((plaf - sol) if sol and plaf else np.nan):.2f} / plan {hsp:.2f} | tangage {tang:+.1f}° | {dt:.1f} s", flush=True)
            lignes.append((r["focale_px"] / k["f"], (-sol if sol else np.nan) - k["z"], ((plaf - sol) if sol and plaf else np.nan) / hsp))
            pr = r["profondeur"].copy(); pr[~r["masque"]] = 0
            vis = cv2.applyColorMap(np.clip(pr / 8 * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
            ecrire_image(sortie / f"{app}-{nom}.jpg", cv2.resize(np.hstack([im, vis]), None, fx=0.5, fy=0.5))
    t = np.array(lignes)
    print("focale / main : médiane %.2f, écart |%%| médian %.0f %%" % (np.nanmedian(t[:, 0]), 100 * np.nanmedian(np.abs(t[:, 0] - 1))))
    print("hauteur appareil - main : médiane %+.2f m, |écart| médian %.2f m" % (np.nanmedian(t[:, 1]), np.nanmedian(np.abs(t[:, 1]))))
    print("plafond / plan : médiane %.2f, |écart| médian %.0f %%" % (np.nanmedian(t[:, 2]), 100 * np.nanmedian(np.abs(t[:, 2] - 1))))
