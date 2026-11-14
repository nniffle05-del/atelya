"""Recouper les photos d'une même pièce avec MapAnything « apache » (moteur/mapanything.py) : d'un lot de photos, la place
et la direction de chaque appareil par rapport aux autres, DIRECTEMENT EN MÈTRES (échelle rendue par le réseau, sans
MoGe-2). Le « haut » reste celui de MoGe-2 sur chaque photo. Même banc que moge14 (Depth Anything 3) : mêmes 22 photos,
mêmes groupes PIECE (les photos d'une même pièce d'après la main), mêmes critères, noté contre le déplacement relevé à
la main. En plus : le rapport entre l'échelle du réseau et celle qu'aurait donnée MoGe-2, et, pour les paires écartées
de plus de 1,5 m, « distance entre appareils trouvée / distance vraie ». PAIRE=1 : aussi les photos deux à deux ;
TOUT=1 : aussi toutes les photos du logement en un seul lot.
Repères (moge14, DA3 « base » + MoGe-2), 34 paires : déplacement juste 14, rotation juste 22 ; séjour d'app-002 : 10
paires sur 10 à moins de 6°.
RÉSULTAT (14/11/2026), 34 paires de la même pièce : PIECE déplacement juste (< 1 m, < 15°) 10, très juste 1, rotation
juste (< 15°) 25, écart médian 1,39 m et 8,3° ; avec les mêmes places remises à l'échelle de MoGe-2 : 10 justes, 1,31 m.
Séjour d'app-002 : rotations au pire 9,0°, médiane 4,0° (DA3 : au pire 5,2°). TOUT (pièces mélangées) 7 justes, rotation
23 (DA3 : 3 et 12) ; PAIRE 7 et 22. Distance trouvée / vraie : médiane 0,92 (0,37 à 1,81), 14 paires sur 30 à moins de
20 %. Échelle du réseau / MoGe-2 : 0,82. Zoom / main : 0,82 (MoGe-2 1,09) : ne pas s'en servir. Temps : 0,4 s pour 2
photos, 1,1 s pour 5, 2,8 s pour 11 ; carte 3,4 Go au plus.
Lancement : python moge20.py ../atelya/b2/cameras-seules"""
import json, os, sys, time
from itertools import combinations
from pathlib import Path
import cv2, numpy as np, torch
from moteur.images import lire_image
from moteur import mapanything
from moge14 import eb, relatif, verticale  # moge14 ne charge aucun réseau à l'import (ni moge1, ni moge4, ni moge6)

PAIRES = os.environ.get("PAIRE", "0") == "1"  # aussi les photos deux à deux
TOUT = os.environ.get("TOUT", "0") == "1"      # aussi toutes les photos du logement en un seul lot


def poser(modele, noms, ims, mesures):
    """→ {nom: (centre 2D en m, cap en rad)} dans un repère commun à plat, et les mesures du lot."""
    if torch.cuda.is_available():
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    r = mapanything.lire(modele, [ims[n] for n in noms])
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    duree = time.time() - t0
    h, w = r["taille"]
    ech, hauts, foc = [], [], {}
    for i, n in enumerate(noms):
        z = mesures[n]
        H, W = z["masque"].shape  # la mesure de MoGe-2 couvre TOUTE la photo ; le réseau n'en voit que le cadre
        x0, y0, x1, y1 = np.round(r["cadre"][i] * np.array([W / ims[n].shape[1], H / ims[n].shape[0]] * 2)).astype(int)
        zm = cv2.resize(z["points"][y0:y1, x0:x1, 2].astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
        ok = cv2.resize(z["masque"][y0:y1, x0:x1].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        ok &= r["masque"][i] & (r["confiance"][i] > np.median(r["confiance"][i]))
        ech.append(np.median(zm[ok] / (r["profondeur"][i][ok] / r["echelle"])))  # l'échelle qu'aurait donnée MoGe-2
        hauts.append(r["appareils"][i][:, :3] @ z["haut"])
        foc[n] = float(r["focale_px"][i][0] / w * (r["cadre"][i][2] - r["cadre"][i][0]) / ims[n].shape[1])  # en parts de la largeur d'origine
    hauts = np.array(hauts)
    haut = hauts.mean(0); haut /= np.linalg.norm(haut)
    ecart = float(np.degrees(np.arccos(np.clip(hauts @ haut, -1, 1))).max())
    ax = np.cross(haut, [0.0, 0.0, 1.0]); ax /= np.linalg.norm(ax); ay = np.cross(haut, ax)
    sortie = {}
    for i, n in enumerate(noms):
        R, t = r["appareils"][i][:, :3], r["appareils"][i][:, 3]  # déjà en mètres
        f = R[:, 2] - haut * (R[:, 2] @ haut)
        sortie[n] = (np.array([t @ ax, t @ ay]), float(np.arctan2(f @ ay, f @ ax)))
    R0 = r["appareils"][0][:, :3]  # l'appareil de la 1re photo doit sortir (presque) à l'origine, sans rotation
    repere = (float(np.degrees(np.arccos(np.clip((np.trace(R0) - 1) / 2, -1, 1)))), float(np.linalg.norm(r["appareils"][0][:, 3])))
    return sortie, {"echelle": r["echelle"], "moge": np.array(ech), "hauts": ecart, "focales": foc, "duree": duree, "repere": repere,
                    "memoire": torch.cuda.max_memory_allocated() / 2 ** 30 if torch.cuda.is_available() else 0.0, "taille": (h, w)}


if __name__ == "__main__":
    S = Path(sys.argv[1])
    t0 = time.time(); modele = mapanything.charger()
    print(f"MapAnything chargé en {time.time() - t0:.0f} s | sur la carte : {torch.cuda.memory_allocated() / 2 ** 30:.2f} Go", flush=True)
    bilan = {"PIECE": [], "PIECE, échelle de MoGe-2": [], "TOUT": [], "PAIRE": []}; focales = []; garde = {}; lots = []; rapports = []; distances = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        ims, mes, pv = {}, {}, {}
        for nom, c in d["cameras"].items():
            ims[nom] = cv2.cvtColor(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
            z = np.load(S / "moge" / f"{app}-{nom}.npz")
            mes[nom] = {"points": z["points"], "masque": z["masque"], "haut": verticale(z["normales"].astype(np.float32), z["masque"]),
                        "focale": float(z["focale"])}
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

        def noter(quoi, poses, a, b, texte="", muet=False):
            t, r = relatif(poses[a], poses[b]); tv, rv = vrai(a, b)
            e, da, dv = float(np.hypot(*(t - tv))), float(abs((r - rv + 180) % 360 - 180)), float(np.hypot(*tv))
            bilan[quoi].append((e, da, dv, app == "app-002" and pv[a] == "sejour_1"))
            if muet:
                return
            if dv > 1.5:
                texte = f"| distance trouvée / vraie {np.hypot(*t) / dv:.2f} " + texte
                if quoi == "PIECE":
                    distances.append(float(np.hypot(*t) / dv))
            print(f"{app} {quoi:5s} {a[-2:]}-{b[-2:]} ({pv[a][:9]}) | écart au corrigé {e:5.2f} m, {da:5.1f}° | vraie distance {dv:.2f} m {texte}", flush=True)

        garde[app] = {}
        if TOUT:
            poses, m = poser(modele, noms, ims, mes)
            lots.append((len(noms), m["duree"], m["memoire"]))
            print(f"{app} TOUT : {len(noms)} photos en {m['duree']:.1f} s, carte {m['memoire']:.2f} Go | échelle du réseau {m['echelle']:.2f} | réseau / MoGe-2 "
                  f"{m['echelle'] / float(np.median(m['moge'])):.2f} | désaccord des « hauts » {m['hauts']:.1f}°", flush=True)
            garde[app]["tout"] = {n: [*map(float, p[0]), p[1]] for n, p in poses.items()}
            for a, b in combinations(noms, 2):
                if pv[a] == pv[b]:
                    noter("TOUT", poses, a, b)
        for piece in sorted(set(pv.values())):
            g = [n for n in noms if pv[n] == piece]
            if len(g) < 2:
                continue
            poses, m = poser(modele, g, ims, mes)
            rapport = m["echelle"] / float(np.median(m["moge"]))
            lots.append((len(g), m["duree"], m["memoire"])); rapports.append(rapport)
            print(f"{app} PIECE {piece} : {len(g)} photos de {m['taille'][1]} × {m['taille'][0]} en {m['duree']:.1f} s, carte {m['memoire']:.2f} Go | échelle du réseau "
                  f"{m['echelle']:.2f} | réseau / MoGe-2 {rapport:.2f} (par photo {(m['echelle'] / m['moge']).min():.2f} à {(m['echelle'] / m['moge']).max():.2f}) | "
                  f"désaccord des « hauts » {m['hauts']:.1f}° | 1re photo à {m['repere'][0]:.2f}° et {m['repere'][1]:.3f} m de l'origine", flush=True)
            garde[app][piece] = {n: [*map(float, p[0]), p[1]] for n, p in poses.items()}
            for n in g:
                k = d["cameras"][n]
                focales.append((m["focales"][n] * k["largeur"] / k["camera"]["f"], mes[n]["focale"] / mes[n]["masque"].shape[1] * k["largeur"] / k["camera"]["f"]))
            for a, b in combinations(g, 2):
                noter("PIECE", poses, a, b)
            remis = {n: (p[0] / rapport, p[1]) for n, p in poses.items()}  # les mêmes places, remises à l'échelle de MoGe-2
            for a, b in combinations(g, 2):
                noter("PIECE, échelle de MoGe-2", remis, a, b, muet=True)
            if PAIRES:
                for a, b in combinations(g, 2):
                    poses2, m2 = poser(modele, [a, b], ims, mes)
                    noter("PAIRE", poses2, a, b, f"| « hauts » {m2['hauts']:.1f}° | réseau / MoGe-2 {m2['echelle'] / float(np.median(m2['moge'])):.2f}")
    (S / "pose").mkdir(exist_ok=True)
    (S / "pose" / "mapanything-poses.json").write_text(json.dumps(garde), encoding="utf-8")
    for quoi, L in bilan.items():
        if not L:
            continue
        L = np.array(L, float)
        print(f"{quoi} : {len(L)} paires de la même pièce | déplacement juste (< 1 m, < 15°) : {int(((L[:, 0] < 1) & (L[:, 1] < 15)).sum())} | très juste (< 0,5 m, < 8°) : "
              f"{int(((L[:, 0] < 0.5) & (L[:, 1] < 8)).sum())} | rotation seule juste (< 15°) : {int((L[:, 1] < 15).sum())} | écart médian {np.median(L[:, 0]):.2f} m, {np.median(L[:, 1]):.1f}°")
        s = L[L[:, 3] > 0]
        print(f"{quoi} : séjour d'app-002, {len(s)} paires | rotation : au pire {s[:, 1].max():.1f}°, médiane {np.median(s[:, 1]):.1f}° | déplacement : au pire {s[:, 0].max():.2f} m, médiane {np.median(s[:, 0]):.2f} m")
    D = np.array(distances)
    print(f"distance trouvée / vraie (PIECE, {len(D)} paires écartées de plus de 1,5 m) : médiane {np.median(D):.2f}, de {D.min():.2f} à {D.max():.2f}, à moins de 20 % : {int((np.abs(D - 1) < 0.2).sum())}")
    print(f"échelle du réseau / échelle de MoGe-2 ({len(rapports)} lots) : médiane {np.median(rapports):.2f}, de {min(rapports):.2f} à {max(rapports):.2f}")
    F = np.array(focales)
    print(f"zoom / main : MapAnything médiane {np.median(F[:, 0]):.2f}, écart médian {100 * np.median(np.abs(F[:, 0] - 1)):.0f} %, à moins de 10 % : {int((np.abs(F[:, 0] - 1) < 0.1).sum())} / {len(F)} | "
          f"MoGe-2 médiane {np.median(F[:, 1]):.2f}, écart médian {100 * np.median(np.abs(F[:, 1] - 1)):.0f} %, à moins de 10 % : {int((np.abs(F[:, 1] - 1) < 0.1).sum())}")
    print("temps par lot : " + ", ".join(f"{n} photos {t:.1f} s" for n, t, _ in lots) + f" | mémoire de la carte au plus : {max(m for _, _, m in lots):.2f} Go")
