"""Poser les photos d'une même pièce D'UN BLOC sur le plan : Depth Anything 3 dit où sont les appareils les uns par rapport
aux autres (moge14) ; on cherche la place et l'orientation du bloc entier pour lesquelles CHAQUE photo colle aux murs du
plan (notes de moge5). Un morceau de pièce vu par plusieurs photos se confond bien moins qu'une photo seule.
Groupes : `main` = photos de la même pièce d'après le relevé à la main (plafond de la méthode) ; `atelya` = photos
qu'Atelya juge de la même pièce (ressemblance, meme_piece.py)."""
import json, os, sys, time
os.environ.setdefault("MODE", "fen"); os.environ.setdefault("ECH", "0.72,0.8,0.88,0.96,1.04"); os.environ.setdefault("LIM", "0.68,1.08")
from pathlib import Path
import cv2, numpy as np
from moteur.images import lire_image, ecrire_image
from moteur import da3
import etape_b as eb
import moge2 as m2
import moge5 as m5
import moge9 as m9
import moge14 as m14

ECHELLES = (0.85, 0.92, 1.0, 1.08, 1.16)   # l'échelle du bloc (mise en mètres par MoGe-2) est incertaine
JEU_M, JEU_DEG = int(os.environ.get("JEU_M", 2)), int(os.environ.get("JEU_DEG", 4))  # jeu laissé à chaque photo : cases de 20 cm, degrés


def notes_photo(mod, G, tirs, z, asp, cache):
    if cache.is_file():
        c = np.load(cache); return c["N"].astype(np.float32), c["E"]
    pr = m5.profil(z, mod["hsp"], asp)
    if pr is None:
        return None, None
    ph, rm, creux, sol, _ = pr; ip = ph.astype(int); tour, tsorte, tappui = tirs
    n = np.stack([np.stack([m5.note(rm[None] * e, tour[:, (cap + ip) % 360], creux[None], sol[None], tsorte[:, (cap + ip) % 360],
                                    tappui[:, (cap + ip) % 360]) for cap in range(360)], 1) for e in m5.ECH], 2)
    N, E = n.max(2).astype(np.float16), n.argmax(2).astype(np.uint8)
    np.savez_compressed(cache, N=N, E=E)
    return N.astype(np.float32), E


def trame(G, o, forme, N):
    """Notes rangées sur le quadrillage du plan (ligne, colonne, cap), avec le jeu laissé à chaque photo."""
    T = np.zeros((*forme, 360), np.float32)
    ij = np.round((G - o) / m2.PAS).astype(int)
    T[ij[:, 1], ij[:, 0]] = N
    if JEU_M:
        import torch
        T = torch.nn.functional.max_pool2d(torch.from_numpy(T).permute(2, 0, 1)[None], 2 * JEU_M + 1, 1, JEU_M)[0].permute(1, 2, 0).numpy()
    if JEU_DEG:
        T = np.max([np.roll(T, d, 2) for d in range(-JEU_DEG, JEU_DEG + 1)], 0)
    return T


def glisse(A, dy, dx):
    """B[y, x] = A[y + dy, x + dx] (0 hors du plan)."""
    B = np.zeros_like(A); h, w = A.shape
    y0, y1, x0, x1 = max(0, -dy), min(h, h - dy), max(0, -dx), min(w, w - dx)
    if y1 > y0 and x1 > x0:
        B[y0:y1, x0:x1] = A[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    return B


def poser_bloc(T, rel, noms, combien=5):
    """T : {nom: trame}, rel : {nom: (centre 2D m, cap rad)} du bloc. → meilleures places du bloc :
    [(note, {nom: (colonne, ligne, cap °)})], la 1re photo sert d'ancre."""
    a = noms[0]; c0, t0 = rel[a]; trouves = []
    for s in ECHELLES:
        for cap in range(0, 360):
            rot = np.radians(cap) - t0; cr, sr = np.cos(rot), np.sin(rot)
            tot = T[a][:, :, cap].copy(); ou = {a: (0, 0, cap)}
            for n in noms[1:]:
                d = (rel[n][0] - c0) * s
                dx, dy = int(round((cr * d[0] - sr * d[1]) / m2.PAS)), int(round((sr * d[0] + cr * d[1]) / m2.PAS))
                k = int(round(cap + np.degrees(rel[n][1] - t0))) % 360
                tot += glisse(T[n][:, :, k], dy, dx); ou[n] = (dx, dy, k)
            for _ in range(3):
                iy, ix = np.unravel_index(tot.argmax(), tot.shape)
                trouves.append((float(tot[iy, ix]), ix, iy, cap, s, ou))
                tot[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] = 0
    trouves.sort(key=lambda x: -x[0]); garde = []
    for v, ix, iy, cap, s, ou in trouves:
        if all(np.hypot(ix - g[1], iy - g[2]) > 4 or abs((cap - g[3] + 180) % 360 - 180) > 20 for g in garde):
            garde.append((v, ix, iy, cap, s, ou))
        if len(garde) == combien:
            break
    return [(v, {n: (ix + dx, iy + dy, k) for n, (dx, dy, k) in ou.items()}, s) for v, ix, iy, cap, s, ou in garde]


def groupes_atelya(noms, sim):
    """Photos jugées de la même pièce par leur ressemblance (mêmes règles que moge9), en groupes."""
    lie = lambda a, b: sim[a][b] >= m9.SEUIL_MEME or (max(noms, key=lambda x: sim[a][x] if x != a else -1) == b
                                                       and max(noms, key=lambda x: sim[b][x] if x != b else -1) == a and sim[a][b] >= 0.5)
    g = {n: i for i, n in enumerate(noms)}
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            if lie(a, b):
                ga, gb = g[a], g[b]
                g = {n: (ga if v == gb else v) for n, v in g.items()}
    return [[n for n in noms if g[n] == v] for v in dict.fromkeys(g.values())]


if __name__ == "__main__":
    S = Path(sys.argv[1]); quoi = sys.argv[2] if len(sys.argv) > 2 else "main"
    modele = da3.charger(); objets = json.loads((S / "objets.json").read_text(encoding="utf-8")); bilan = []; sortie = {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod0 = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        mod = dict(mod0, sorte=mod0["genre"].copy(), genre=np.zeros_like(mod0["genre"]))
        G = m2.grille(mod); pg = eb.piece_de(mod, G); tirs = m5.tirs(mod, G, np.arange(360.0))
        o = np.concatenate(mod["pieces"]).min(0); forme = tuple((np.round((G - o) / m2.PAS).astype(int).max(0) + 1)[::-1])
        mp = json.loads((S / "meme-piece.json").read_text(encoding="utf-8"))[app]
        sim = {a: {b: mp["sim"][i][j] for j, b in enumerate(mp["noms"])} for i, a in enumerate(mp["noms"])}
        ims, mes, pv, T, Z = {}, {}, {}, {}, {}
        for nom, c in d["cameras"].items():
            t0 = time.time()
            ims[nom] = cv2.cvtColor(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
            z = np.load(S / "moge" / f"{app}-{nom}.npz"); Z[nom] = z
            mes[nom] = {"points": z["points"], "masque": z["masque"], "haut": m14.verticale(z["normales"].astype(np.float32), z["masque"])}
            N, E = notes_photo(mod, G, tirs, z, np.load(S / "aspect" / f"{app}-{nom}.npy"), S / "pose" / f"notes-{app}-{nom}.npz")
            if N is None:
                continue
            fac = np.array([m9.facteur(m9.indices(objets[f"{app}/{nom}"]), mod["ids"][p]) for p in pg], np.float32)
            T[nom] = trame(G, o, forme, N * fac[:, None])
            k = c["camera"]; pv[nom] = "?"
            for t in np.arange(0, 1.6, 0.1):
                ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
                if ip >= 0:
                    pv[nom] = mod["ids"][ip]; break
            print(app, nom, f"notes prêtes ({time.time() - t0:.0f} s)", flush=True)
        noms = list(T)
        if quoi == "main":
            groupes = [[n for n in noms if pv[n] == p] for p in dict.fromkeys(pv[n] for n in noms)]
        else:
            groupes = groupes_atelya(noms, sim)
        sortie[app] = {}
        for g in groupes:
            if len(g) >= 2:
                rel, e, ecart, _, _ = m14.poser(modele, g, ims, mes)
            else:
                rel = {g[0]: (np.zeros(2), 0.0)}
            places = poser_bloc(T, rel, g)
            v, ou, s = places[0]; v2 = places[1][0] if len(places) > 1 else 0.0
            print(f"{app} bloc {'+'.join(n[-2:] for n in g)} : note {v:.2f} (2e place {v2:.2f}), échelle du bloc {s:.2f}", flush=True)
            for n in g:
                ix, iy, cap = ou[n]; cam = np.array([o[0] + ix * m2.PAS, o[1] + iy * m2.PAS, float(cap)])
                k = d["cameras"][n]["camera"]
                e, dc = float(np.hypot(cam[0] - k["x"], cam[1] - k["y"])), float(abs((cam[2] - k["cap"] + 180) % 360 - 180))
                ip = eb.piece_de(mod, cam[None, :2])[0]; piece = mod["ids"][ip] if ip >= 0 else "hors du plan"
                ec = m9.colle(cam, d["cameras"][n])
                bilan.append((e, dc, piece == pv[n], ec, len(g)))
                sortie[app][n] = {"cam": cam.tolist(), "piece": piece, "bloc": g, "note_bloc": v, "note_2e": v2}
                print(f"    {n} (main : {pv[n]}) → {piece} | {e:.2f} m, {dc:.0f}° ({ec:.0f} px)", flush=True)
        # image : le plan, la main en vert, Atelya en rouge
        Ei = 60; cc = np.concatenate(mod["pieces"]); o0 = cc.min(0) - 0.5; taille = ((cc.max(0) - o0 + 0.5) * Ei).astype(int)
        vis = np.full((taille[1], taille[0], 3), 255, np.uint8)
        px = lambda p: (int((p[0] - o0[0]) * Ei), int(taille[1] - (p[1] - o0[1]) * Ei))
        for a, b, gn in zip(mod0["A"], mod0["B"], mod0["genre"]):
            cv2.line(vis, px(a), px(b), ((0, 0, 0), (0, 160, 255), (255, 160, 0))[gn], 2)
        for n in sortie[app]:
            k = d["cameras"][n]["camera"]
            for q, coul in (((k["x"], k["y"], k["cap"]), (0, 150, 0)), (sortie[app][n]["cam"], (0, 0, 255))):
                t = np.radians(q[2]); p0 = np.array(q[:2])
                cv2.circle(vis, px(p0), 7, coul, -1); cv2.line(vis, px(p0), px(p0 + 0.7 * np.array([np.cos(t), np.sin(t)])), coul, 2)
                cv2.putText(vis, n[-2:], (px(p0)[0] + 8, px(p0)[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, coul, 2)
            cv2.line(vis, px((k["x"], k["y"])), px(sortie[app][n]["cam"][:2]), (190, 190, 190), 1)
        ecrire_image(S / f"plan-blocs-{quoi}-{app}.png", vis)
    (S / "pose" / f"blocs-{quoi}.json").write_text(json.dumps(sortie), encoding="utf-8")
    t = np.array(bilan, float)
    for nom, sel in (("toutes", t[:, 4] > 0), ("photos en bloc (≥ 2)", t[:, 4] >= 2), ("photos seules", t[:, 4] == 1)):
        u = t[sel]
        print(f"{nom:22s} ({len(u):2d}) | bien placées (< 0,5 m, < 8°) : {int(((u[:, 0] < 0.5) & (u[:, 1] < 8)).sum())} | à peu près (< 1 m, < 15°) : "
              f"{int(((u[:, 0] < 1.0) & (u[:, 1] < 15)).sum())} | bonne pièce : {int(u[:, 2].sum())} | colle aux repères (< 12 px) : {int((u[:, 3] < 12).sum())}")
