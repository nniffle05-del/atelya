"""Recouper les photos d'une même pièce avec Depth Anything 3 « base » (moteur/da3.py) : d'un lot de photos, la place et la
direction de chaque appareil par rapport aux autres. Mise en mètres : profondeurs de MoGe-2 (déjà mesurées). Le « haut » :
celui de MoGe-2 sur chaque photo. Noté contre le déplacement relevé à la main, comme moge10 (5 paires justes sur 34).
Lots essayés : PIECE (les photos d'une même pièce d'après la main), TOUT (toutes les photos du logement), PAIRE (2 à 2).
RÉSULTAT (14/11/2026), 34 paires de la même pièce : PIECE 14 déplacements justes (< 1 m, < 15°), rotation juste 22 ;
PAIRE 12 ; TOUT (pièces mélangées) 3 seulement. Séjour d'app-002 : 10 paires sur 10 à moins de 6°. Zoom de DA3 moins
bon que celui de MoGe-2 (écart médian à la main 18 % contre 10 %) : ne pas s'en servir."""
import json, sys, time
from itertools import combinations
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image
from moteur import da3
import etape_b as eb


RAYONS = __import__("os").environ.get("RAYONS", "0") == "1"  # mêmes places que le décodeur (mesuré) : inutile par défaut


def verticale(n, ok):
    n = n[::4, ::4].reshape(-1, 3)[ok[::4, ::4].ravel()]
    haut = np.array([0.0, -1.0, 0.0])
    for seuil in (0.8, 0.9, 0.96, 0.98):
        s = n[np.abs(n @ haut) > seuil]
        if len(s) < 50:
            break
        s = s * np.sign(s @ haut)[:, None]
        haut = s.mean(0); haut /= np.linalg.norm(haut)
    return haut


def poser(modele, noms, ims, mesures, reference=None):
    """→ {nom: (centre 2D en m, cap en rad)} dans un repère commun à plat, échelle, accord des « hauts » (°), focales."""
    r = da3.lire(modele, [ims[n] for n in noms], reference=reference)
    if RAYONS:  # appareils calculés par les rayons (plus précis d'après l'éditeur) au lieu du petit décodeur
        r = dict(r, appareils=r["appareils_rayons"], focale_px=r["focale_rayons_px"])
    h, w = r["taille"]
    ech, hauts = [], []
    for i, n in enumerate(noms):
        z = mesures[n]
        zm = cv2.resize(z["points"][..., 2].astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
        ok = cv2.resize(z["masque"].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        ok &= r["confiance"][i] > np.median(r["confiance"][i])
        ech.append(np.median(zm[ok] / r["profondeur"][i][ok]))
        hauts.append(r["appareils"][i][:, :3] @ z["haut"])
    e = float(np.median(ech)); hauts = np.array(hauts)
    haut = hauts.mean(0); haut /= np.linalg.norm(haut)
    ecart = float(np.degrees(np.arccos(np.clip(hauts @ haut, -1, 1))).max())
    # repère à plat : deux axes horizontaux quelconques
    ax = np.cross(haut, [0.0, 0.0, 1.0]); ax /= np.linalg.norm(ax); ay = np.cross(haut, ax)
    sortie = {}
    for i, n in enumerate(noms):
        R, t = r["appareils"][i][:, :3], r["appareils"][i][:, 3] * e
        f = R[:, 2] - haut * (R[:, 2] @ haut)
        sortie[n] = (np.array([t @ ax, t @ ay]), float(np.arctan2(f @ ay, f @ ax)))
    return sortie, e, ecart, {n: float(r["focale_px"][i][0] / w) for i, n in enumerate(noms)}, np.array(ech)


def relatif(pa, pb):
    """Place et cap de b vus de a : (devant, à gauche) en m, rotation en °."""
    (ca, ta), (cb, tb) = pa, pb
    d = cb - ca
    return np.array([d[0] * np.cos(ta) + d[1] * np.sin(ta), -d[0] * np.sin(ta) + d[1] * np.cos(ta)]), float(np.degrees(tb - ta))


if __name__ == "__main__":
    S = Path(sys.argv[1]); modele = da3.charger(); bilan = {"PIECE": [], "TOUT": [], "PAIRE": []}; focales = []; garde = {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        ims, mes, pv = {}, {}, {}
        for nom, c in d["cameras"].items():
            ims[nom] = cv2.cvtColor(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
            z = np.load(S / "moge" / f"{app}-{nom}.npz")
            mes[nom] = {"points": z["points"], "masque": z["masque"], "haut": verticale(z["normales"].astype(np.float32), z["masque"])}
            k = c["camera"]; pv[nom] = "?"
            for t in np.arange(0, 1.6, 0.1):
                ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
                if ip >= 0:
                    pv[nom] = mod["ids"][ip]; break
        noms = list(ims)

        def vrai(a, b):
            ka, kb = d["cameras"][a]["camera"], d["cameras"][b]["camera"]
            ca, sa = np.cos(np.radians(ka["cap"])), np.sin(np.radians(ka["cap"]))
            return np.array([[ca, sa], [-sa, ca]]) @ np.array([kb["x"] - ka["x"], kb["y"] - ka["y"]]), kb["cap"] - ka["cap"]

        def noter(quoi, poses, a, b, texte=""):
            t, r = relatif(poses[a], poses[b]); tv, rv = vrai(a, b)
            e, da = float(np.hypot(*(t - tv))), float(abs((r - rv + 180) % 360 - 180))
            bilan[quoi].append((e, da, float(np.hypot(*tv))))
            print(f"{app} {quoi:5s} {a[-2:]}-{b[-2:]} ({pv[a][:9]}) | écart au corrigé {e:5.2f} m, {da:5.1f}° | vraie distance {np.hypot(*tv):.2f} m {texte}", flush=True)

        t0 = time.time()
        poses, e, ecart, foc, ech = poser(modele, noms, ims, mes)
        print(f"{app} TOUT : {len(noms)} photos en {time.time() - t0:.1f} s | échelle {e:.2f} (par photo {ech.min():.2f} à {ech.max():.2f}) | désaccord des « hauts » jusqu'à {ecart:.1f}°")
        garde[app] = {"tout": {n: [*map(float, p[0]), p[1]] for n, p in poses.items()}}
        for n in noms:
            focales.append((foc[n] * d["cameras"][n]["largeur"] / d["cameras"][n]["camera"]["f"], float(np.load(S / "moge" / f"{app}-{n}.npz")["focale"]) / np.load(S / "moge" / f"{app}-{n}.npz")["masque"].shape[1] * d["cameras"][n]["largeur"] / d["cameras"][n]["camera"]["f"]))
        for a, b in combinations(noms, 2):
            if pv[a] == pv[b]:
                noter("TOUT", poses, a, b)
        for piece in sorted(set(pv.values())):
            g = [n for n in noms if pv[n] == piece]
            if len(g) < 2:
                continue
            poses, e, ecart, _, ech = poser(modele, g, ims, mes)
            print(f"{app} PIECE {piece} : {len(g)} photos | échelle {e:.2f} ({ech.min():.2f} à {ech.max():.2f}) | désaccord des « hauts » {ecart:.1f}°")
            garde[app][piece] = {n: [*map(float, p[0]), p[1]] for n, p in poses.items()}
            for a, b in combinations(g, 2):
                noter("PIECE", poses, a, b)
            for a, b in combinations(g, 2):
                poses2, e, ecart, _, _ = poser(modele, [a, b], ims, mes)
                noter("PAIRE", poses2, a, b, f"| « hauts » {ecart:.1f}°")
    (S / "pose" / "da3-poses.json").write_text(json.dumps(garde), encoding="utf-8")
    for quoi, L in bilan.items():
        L = np.array(L)
        print(f"{quoi:5s} : {len(L)} paires de la même pièce | déplacement juste (< 1 m, < 15°) : {int(((L[:, 0] < 1) & (L[:, 1] < 15)).sum())} | très juste (< 0,5 m, < 8°) : "
              f"{int(((L[:, 0] < 0.5) & (L[:, 1] < 8)).sum())} | rotation seule juste (< 15°) : {int((L[:, 1] < 15).sum())} | écart médian {np.median(L[:, 0]):.2f} m, {np.median(L[:, 1]):.1f}°")
    F = np.array(focales)
    print(f"zoom / main : DA3 médiane {np.median(F[:, 0]):.2f}, écart médian {100 * np.median(np.abs(F[:, 0] - 1)):.0f} %, à moins de 10 % : {int((np.abs(F[:, 0] - 1) < 0.1).sum())} / {len(F)} | "
          f"MoGe-2 médiane {np.median(F[:, 1]):.2f}, écart médian {100 * np.median(np.abs(F[:, 1] - 1)):.0f} %, à moins de 10 % : {int((np.abs(F[:, 1] - 1) < 0.1).sum())}")
