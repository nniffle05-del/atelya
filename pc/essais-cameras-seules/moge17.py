"""La TAILLE d'un bloc de photos mesurée par la hauteur sous plafond : dans le nuage de points commun que Depth Anything 3
rend pour les photos d'une pièce, la distance sol-plafond doit valoir la hauteur écrite sur le plan. Comparée à la mise en
mètres par les profondeurs de MoGe-2 (moge14), et à la vraie taille (écarts entre appareils relevés à la main).
RÉSULTAT (14/11/2026) : ÉCARTÉ. La taille par le plafond dépend du zoom, que DA3 estime mal (jusqu'à 30 % trop serré sur
app-001) : écart moyen à la vraie taille 61 % contre 29 % par MoGe-2 (séjours : 0,93 / 1,27 contre 0,92 / 1,06)."""
import json, sys
from itertools import combinations
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image
from moteur import da3
import etape_b as eb
import moge14 as m14


def pic(v, lo, hi, n=240):
    h, b = np.histogram(v, bins=np.linspace(lo, hi, n + 1))
    h = np.convolve(h, np.ones(5), "same")
    return float(b[h.argmax()] + (hi - lo) / n / 2), float(h.max())


def bloc(modele, noms, ims, mes, hsp, focales=None):
    """→ dict : pour chaque photo `centre` (2D, à plat), `cap`, `hauteur` (au-dessus du sol), le tout en MÈTRES d'après la
    hauteur sous plafond (`echelle`, None si sol ou plafond introuvable) ; `echelle_moge` = l'ancienne mise en mètres."""
    r = da3.lire(modele, [ims[n] for n in noms])
    h, w = r["taille"]
    hauts = np.array([r["appareils"][i][:, :3] @ mes[n]["haut"] for i, n in enumerate(noms)])
    haut = hauts.mean(0); haut /= np.linalg.norm(haut)
    v, u = np.meshgrid(np.arange(h) + 0.5 - h / 2, np.arange(w) + 0.5 - w / 2, indexing="ij")
    hh, hz, em = [], [], []
    for i, n in enumerate(noms):
        z = mes[n]; d = r["profondeur"][i]
        fx, fy = (r["focale_px"][i] if focales is None else (focales[n] * w, focales[n] * w))
        Pc = np.stack([u / fx * d, v / fy * d, d], -1)
        Pw = Pc @ r["appareils"][i][:, :3].T + r["appareils"][i][:, 3]
        nm = cv2.resize(z["normales"], (w, h), interpolation=cv2.INTER_NEAREST)
        ok = cv2.resize(z["masque"].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        sur = ok & (r["confiance"][i] > np.median(r["confiance"][i]))
        zm = cv2.resize(z["points"][..., 2].astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
        em.append(np.median(zm[sur] / d[sur]))
        horiz = ok & (np.abs(nm @ z["haut"]) > 0.95)
        hh.append((Pw @ haut)[horiz]); hz.append(float(r["appareils"][i][:, 3] @ haut))
    hh = np.concatenate(hh); hz = np.array(hz)
    e = None; sol = None
    if len(hh) > 2000:
        lo, hi = np.percentile(hh, [0.5, 99.5]); marge = 0.08 * (hi - lo)
        bas, haut_ = hh[hh < hz.min() - marge], hh[hh > hz.max() + marge]
        if len(bas) > 500 and len(haut_) > 500:
            sol, ns = pic(bas, lo, hz.min() - marge); plaf, npl = pic(haut_, hz.max() + marge, hi)
            e = hsp / (plaf - sol)
    em = float(np.median(em)); ech = e if e is not None else em
    ax = np.cross(haut, [0.0, 0.0, 1.0]); ax /= np.linalg.norm(ax); ay = np.cross(haut, ax)
    photos = {}
    for i, n in enumerate(noms):
        R, t = r["appareils"][i][:, :3], r["appareils"][i][:, 3]
        f = R[:, 2] - haut * (R[:, 2] @ haut)
        photos[n] = {"centre": np.array([t @ ax, t @ ay]) * ech, "cap": float(np.arctan2(f @ ay, f @ ax)),
                     "hauteur": float((t @ haut - sol) * e) if e is not None else None}
    return {"photos": photos, "echelle": e, "echelle_moge": em, "brut": {n: np.array([r["appareils"][i][:, 3] @ ax, r["appareils"][i][:, 3] @ ay]) for i, n in enumerate(noms)},
            "focales": {n: float(r["focale_px"][i][0] / w) for i, n in enumerate(noms)}}


def charger(S, app):
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
    ims, mes, pv = {}, {}, {}
    for nom, c in d["cameras"].items():
        ims[nom] = cv2.cvtColor(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
        z = np.load(S / "moge" / f"{app}-{nom}.npz"); nm = z["normales"].astype(np.float32)
        mes[nom] = {"points": z["points"], "masque": z["masque"], "normales": nm, "haut": m14.verticale(nm, z["masque"]),
                    "focale": float(z["focale"]) / z["masque"].shape[1]}
        k = c["camera"]; pv[nom] = "?"
        for t in np.arange(0, 1.6, 0.1):
            ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
            if ip >= 0:
                pv[nom] = mod["ids"][ip]; break
    return d, mod, ims, mes, pv


if __name__ == "__main__":
    S = Path(sys.argv[1]); modele = da3.charger(); L = []
    for app in ("app-002", "app-001"):
        d, mod, ims, mes, pv = charger(S, app)
        for piece in dict.fromkeys(pv.values()):
            g = [n for n in pv if pv[n] == piece]
            if len(g) < 2:
                continue
            for quoi, foc in (("zoom de DA3", None), ("zoom de MoGe-2", {n: mes[n]["focale"] for n in g})):
                b = bloc(modele, g, ims, mes, mod["hsp"], foc)
                # vraie échelle : écarts entre appareils (main) / écarts bruts de DA3, paires assez écartées
                rap = [np.hypot(d["cameras"][a]["camera"]["x"] - d["cameras"][c]["camera"]["x"], d["cameras"][a]["camera"]["y"] - d["cameras"][c]["camera"]["y"])
                       / max(np.hypot(*(b["brut"][a] - b["brut"][c])), 1e-6) for a, c in combinations(g, 2)
                       if np.hypot(d["cameras"][a]["camera"]["x"] - d["cameras"][c]["camera"]["x"], d["cameras"][a]["camera"]["y"] - d["cameras"][c]["camera"]["y"]) > 1.5]
                vraie = float(np.median(rap)) if rap else np.nan
                e = b["echelle"]
                dz = [b["photos"][n]["hauteur"] - d["cameras"][n]["camera"]["z"] for n in g] if e else [np.nan]
                print(f"{app} {piece:10s} {len(g)} photos [{quoi:14s}] | taille par le plafond / vraie : {(e / vraie if e else np.nan):.2f} | par MoGe-2 / vraie : {b['echelle_moge'] / vraie:.2f} | "
                      f"hauteur des appareils - main : {np.median(dz):+.2f} m (de {np.min(dz):+.2f} à {np.max(dz):+.2f})", flush=True)
                if quoi == "zoom de DA3":
                    L.append(((e / vraie) if e else np.nan, b["echelle_moge"] / vraie, len(g)))
                    fz = [b["focales"][n] * d["cameras"][n]["largeur"] / d["cameras"][n]["camera"]["f"] for n in g]
                    print(f"      zoom de DA3 / main dans ce bloc : {np.round(fz, 2).tolist()}")
    L = np.array(L)
    print(f"écart moyen à la vraie taille : par le plafond {100 * np.nanmean(np.abs(L[:, 0] - 1)):.0f} % | par MoGe-2 {100 * np.nanmean(np.abs(L[:, 1] - 1)):.0f} %")
