"""Toute la chaîne « blocs » : (1) groupes de photos de la même pièce (`main` = corrigé, `atelya` = ressemblance), (2) chaque
groupe recoupé par Depth Anything 3 et posé d'un bloc à plusieurs endroits possibles (moge15), (3) choix D'ENSEMBLE pour le
logement (comme moge9 : chaque pièce importante montrée, pas deux photos au même endroit), (4) réglage fin de chaque photo.
Comparer à moge9 (photos choisies une à une) : 3 bien placées, 9 à peu près, 16 bonne pièce, 7 collent aux repères.
RÉSULTATS (14/11/2026, 22 photos) : groupes `main` (plafond) 7 / 11 / 16 / 9 ; `pieces` (SEUL, groupes = pièces du premier
placement photo par photo) 5 / 12 / 17 / 8 ; `atelya` (ressemblance seule : groupes trop petits) 4 / 9 / 15 / 7 ;
`fusion` (réunir les groupes qui « tiennent » sur le plan) 6 / 10 / 15 / 8 mais réunit des pièces différentes : ÉCARTÉ.
Avec la sortie des intrus (SEUIL_INTRUS = 0,4, défaut) : `pieces` 7 / 12 / 16 / 8, et les 15 photos « sûres »
(marge > 0,4) sont toutes dans la bonne pièce (sans : 17 sûres dont 16)."""
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
import moge15 as m15

J, D = m15.JEU_M, m15.JEU_DEG
L_COUV, L_DOUBLE = m9.L_COUV, m9.L_DOUBLE


def vraie_place(R, ix, iy, k):
    """Dans le jeu laissé à la photo autour de sa place dans le bloc : la meilleure vraie case. → (ix, iy, cap, note)."""
    h, w, _ = R.shape
    y0, y1, x0, x1 = max(0, iy - J), min(h, iy + J + 1), max(0, ix - J), min(w, ix + J + 1)
    if y1 <= y0 or x1 <= x0:
        return ix, iy, k, 0.0
    caps = np.arange(k - D, k + D + 1) % 360
    s = R[y0:y1, x0:x1][:, :, caps]
    a, b, c = np.unravel_index(s.argmax(), s.shape)
    return x0 + b, y0 + a, int(caps[c]), float(s[a, b, c])


def choisir(unites, mod, graine=0):
    """unites : [[candidat]], candidat = {photos: {nom: {cam, note, piece}}}. → indices choisis, marges."""
    rng = np.random.default_rng(graine)
    seul = [[sum(np.log(max(p["note"], 1e-3)) for p in c["photos"].values()) for c in u] for u in unites]

    def total(ch):
        s = sum(seul[i][k] for i, k in enumerate(ch))
        vues = {p["piece"] for i, k in enumerate(ch) for p in unites[i][k]["photos"].values()}
        s += L_COUV * sum(m9.sorte(p) in m9.PRINCIPALES for p in vues)
        for i in range(len(ch)):
            for j in range(i + 1, len(ch)):
                for a in unites[i][ch[i]]["photos"].values():
                    for b in unites[j][ch[j]]["photos"].values():
                        if np.hypot(a["cam"][0] - b["cam"][0], a["cam"][1] - b["cam"][1]) < 1.0 and abs((a["cam"][2] - b["cam"][2] + 180) % 360 - 180) < 25:
                            s -= L_DOUBLE
        return s
    meilleur = (None, -1e9)
    for essai in range(30):
        ch = [int(np.argmax(seul[i])) if essai == 0 else int(rng.integers(len(u))) for i, u in enumerate(unites)]
        v = total(ch); bouge = True
        while bouge:
            bouge = False
            for i in rng.permutation(len(unites)):
                for k in range(len(unites[i])):
                    c2 = list(ch); c2[i] = k; v2 = total(c2)
                    if v2 > v + 1e-9:
                        ch, v, bouge = c2, v2, True
        if v > meilleur[1]:
            meilleur = (ch, v)
    ch, v = meilleur
    marges = []
    for i, u in enumerate(unites):
        ici = {p["piece"] for p in u[ch[i]]["photos"].values()}
        autres = [total([*ch[:i], k, *ch[i + 1:]]) for k in range(len(u)) if {p["piece"] for p in u[k]["photos"].values()} != ici]
        marges.append(v - max(autres) if autres else 9.0)
    return ch, marges


SEUIL_FUSION = float(os.environ.get("SEUIL_FUSION", 0.85))  # deux groupes fusionnent si le bloc réuni garde cette part des notes
SEUIL_INTRUS = float(os.environ.get("SEUIL_INTRUS", 0.4))    # part d'accord en dessous de laquelle deux photos ne montrent pas le même lieu
SIM_MIN = float(os.environ.get("SIM_MIN", 0.35))            # et si au moins deux de leurs photos se ressemblent un peu


def fusionner(groupes, T, sim, poser):
    """Réunir les groupes qui tiennent ENSEMBLE sur le plan : on recoupe les deux groupes par Depth Anything 3, on pose le
    bloc réuni ; si chaque photo y colle presque aussi bien que dans son groupe d'origine, c'est la même pièce."""
    note = lambda g: poser(g)[0][0]
    groupes = [list(g) for g in groupes]
    while True:
        essais = []
        for i in range(len(groupes)):
            for j in range(i + 1, len(groupes)):
                if max(sim[a][b] for a in groupes[i] for b in groupes[j]) < SIM_MIN:
                    continue
                r = note(groupes[i] + groupes[j]) / (note(groupes[i]) + note(groupes[j]))
                essais.append((r, i, j))
                print(f"    réunir {'+'.join(n[-2:] for n in groupes[i])} et {'+'.join(n[-2:] for n in groupes[j])} : garde {100 * r:.0f} % des notes", flush=True)
        if not essais or max(essais)[0] < SEUIL_FUSION:
            return groupes
        r, i, j = max(essais)
        print(f"    → réunis : {'+'.join(n[-2:] for n in groupes[i] + groupes[j])}", flush=True)
        groupes = [g for k, g in enumerate(groupes) if k not in (i, j)] + [groupes[i] + groupes[j]]


if __name__ == "__main__":
    S = Path(sys.argv[1]); quoi = sys.argv[2] if len(sys.argv) > 2 else "atelya"
    modele = da3.charger(); objets = json.loads((S / "objets.json").read_text(encoding="utf-8")); bilan = []; sortie = {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod0 = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        mod = dict(mod0, sorte=mod0["genre"].copy(), genre=np.zeros_like(mod0["genre"]))
        G = m2.grille(mod); pg = eb.piece_de(mod, G); tirs = m5.tirs(mod, G, np.arange(360.0))
        o = np.concatenate(mod["pieces"]).min(0); ij = np.round((G - o) / m2.PAS).astype(int); forme = tuple((ij.max(0) + 1)[::-1])
        P = np.full(forme, -1); P[ij[:, 1], ij[:, 0]] = pg  # pièce de chaque case
        mp = json.loads((S / "meme-piece.json").read_text(encoding="utf-8"))[app]
        sim = {a: {b: mp["sim"][i][j] for j, b in enumerate(mp["noms"])} for i, a in enumerate(mp["noms"])}
        ims, mes, pv, T, R, Er, prof = {}, {}, {}, {}, {}, {}, {}
        for nom, c in d["cameras"].items():
            ims[nom] = cv2.cvtColor(lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
            z = np.load(S / "moge" / f"{app}-{nom}.npz"); asp = np.load(S / "aspect" / f"{app}-{nom}.npy")
            mes[nom] = {"points": z["points"], "masque": z["masque"], "haut": m14.verticale(z["normales"].astype(np.float32), z["masque"])}
            N, E = m15.notes_photo(mod, G, tirs, z, asp, S / "pose" / f"notes-{app}-{nom}.npz")
            if N is None:
                continue
            fac = np.array([m9.facteur(m9.indices(objets[f"{app}/{nom}"]), mod["ids"][p]) for p in pg], np.float32)
            R[nom] = np.zeros((*forme, 360), np.float32); R[nom][ij[:, 1], ij[:, 0]] = N * fac[:, None]
            Er[nom] = np.zeros((*forme, 360), np.uint8); Er[nom][ij[:, 1], ij[:, 0]] = E
            T[nom] = m15.trame(G, o, forme, N * fac[:, None])
            prof[nom] = m5.profil(z, mod["hsp"], asp)
            k = c["camera"]; pv[nom] = "?"
            for t in np.arange(0, 1.6, 0.1):
                ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
                if ip >= 0:
                    pv[nom] = mod["ids"][ip]; break
        noms = list(T); deja = {}

        def poser(g):
            cle = tuple(g)
            if cle not in deja:
                rel = m14.poser(modele, g, ims, mes)[0] if len(g) >= 2 else {g[0]: (np.zeros(2), 0.0)}
                deja[cle] = m15.poser_bloc(T, rel, g, combien=40)
            return deja[cle]
        groupes = [[n for n in noms if pv[n] == p] for p in dict.fromkeys(pv[n] for n in noms)] if quoi == "main" else m15.groupes_atelya(noms, sim)
        if quoi == "fusion":
            groupes = fusionner(groupes, T, sim, poser)
        if quoi == "pieces":  # groupes = photos qu'un premier placement photo par photo (moge9) met dans la même pièce
            cands = {n: c for n, c in json.loads((S / "pose" / f"par-piece-{app}.json").read_text(encoding="utf-8")).items() if c and n in T}
            ens, _ = m9.choisir(cands, {n: m9.indices(objets[f"{app}/{n}"]) for n in cands}, sim)
            ou = {n: cands[n][ens[n]]["piece"] if n in cands else n for n in noms}
            groupes = [[n for n in noms if ou[n] == q] for q in dict.fromkeys(ou.values())]
        if SEUIL_INTRUS > 0:  # une photo qu'AUCUNE autre du groupe ne « revoit » (contrôle croisé de moge18) sort du groupe
            ml = json.loads((S / "meme-lieu-da3.json").read_text(encoding="utf-8"))[app]
            acc = lambda x, y: (ml.get(f"{x}|{y}") or ml.get(f"{y}|{x}") or [0, 0, 1])[1]
            nouveaux = []
            for g in groupes:
                reste = [n for n in g if len(g) == 1 or max(acc(n, m) for m in g if m != n) >= SEUIL_INTRUS]
                nouveaux += ([reste] if reste else []) + [[n] for n in g if n not in reste]
            groupes = nouveaux
        print(app, "groupes :", " | ".join("+".join(n[-2:] for n in g) for g in groupes), flush=True)

        def candidat(ou):
            c = {"photos": {}}
            for n, (ix, iy, k) in ou.items():
                x, y, k2, v = vraie_place(R[n], ix, iy, k)
                e = m5.ECH[int(Er[n][y, x, k2])] if v > 0 else 1.0
                c["photos"][n] = {"cam": [float(o[0] + x * m2.PAS), float(o[1] + y * m2.PAS), float(k2), float(e)], "note": v,
                                  "piece": mod["ids"][P[y, x]] if v > 0 and P[y, x] >= 0 else "hors du plan"}
            return c
        unites = []
        for g in groupes:
            if len(g) >= 2:
                places = poser(g)
                cs = [candidat(ou) for _, ou, _ in places]
                garde, vues = cs[:6], set()
                for c in cs:  # + la meilleure place du bloc pour chaque pièce où il peut tomber
                    cle = tuple(sorted({p["piece"] for p in c["photos"].values()}))
                    if cle not in vues:
                        vues.add(cle)
                        if c not in garde:
                            garde.append(c)
                unites.append(garde)
            else:  # photo seule : ses meilleures places dans chaque pièce
                n = g[0]; cs = []
                for p in range(len(mod["pieces"])):
                    Rp = R[n] * (P == p)[:, :, None]
                    for _ in range(2):
                        iy, ix, k = np.unravel_index(Rp.argmax(), Rp.shape)
                        if Rp[iy, ix, k] <= 0:
                            break
                        cs.append(candidat({n: (ix, iy, k)}))
                        Rp[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] = 0
                unites.append(cs)
        ch, marges = choisir(unites, mod)
        sortie[app] = {}
        for u, k, g, marge in zip(unites, ch, groupes, marges):
            for n, p in u[k]["photos"].items():
                cam = np.array(p["cam"])
                if prof[n] is not None and p["note"] > 0:  # réglage fin, gardé s'il reste près de la place du bloc
                    ph, rm, creux, sol, _ = prof[n]
                    c2, _ = m5.precis(mod, ph, rm, creux, sol, cam.copy())
                    if np.hypot(*(c2[:2] - cam[:2])) < 0.6 and abs((c2[2] - cam[2] + 180) % 360 - 180) < 10:
                        cam = c2
                kk = d["cameras"][n]["camera"]
                e, dc = float(np.hypot(cam[0] - kk["x"], cam[1] - kk["y"])), float(abs((cam[2] - kk["cap"] + 180) % 360 - 180))
                ip = eb.piece_de(mod, cam[None, :2])[0]; piece = mod["ids"][ip] if ip >= 0 else "hors du plan"
                ec = m9.colle(cam, d["cameras"][n])
                bilan.append((e, dc, piece == pv[n], ec, len(g), marge))
                sortie[app][n] = {"cam": cam.tolist(), "piece": piece, "bloc": g, "marge": marge}
                print(f"{app} {n} [bloc {'+'.join(x[-2:] for x in g)}] (main : {pv[n]}) → {piece} | {e:.2f} m, {dc:.0f}° ({ec:.0f} px) | marge {marge:.2f}", flush=True)
        Ei = 60; cc = np.concatenate(mod["pieces"]); o0 = cc.min(0) - 0.5; taille = ((cc.max(0) - o0 + 0.5) * Ei).astype(int)
        vis = np.full((taille[1], taille[0], 3), 255, np.uint8)
        px = lambda p: (int((p[0] - o0[0]) * Ei), int(taille[1] - (p[1] - o0[1]) * Ei))
        for a, b, gn in zip(mod0["A"], mod0["B"], mod0["genre"]):
            cv2.line(vis, px(a), px(b), ((0, 0, 0), (0, 160, 255), (255, 160, 0))[gn], 2)
        for n in sortie[app]:
            kk = d["cameras"][n]["camera"]
            for q, coul in (((kk["x"], kk["y"], kk["cap"]), (0, 150, 0)), (sortie[app][n]["cam"], (0, 0, 255))):
                t = np.radians(q[2]); p0 = np.array(q[:2])
                cv2.circle(vis, px(p0), 7, coul, -1); cv2.line(vis, px(p0), px(p0 + 0.7 * np.array([np.cos(t), np.sin(t)])), coul, 2)
                cv2.putText(vis, n[-2:], (px(p0)[0] + 8, px(p0)[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, coul, 2)
            cv2.line(vis, px((kk["x"], kk["y"])), px(sortie[app][n]["cam"][:2]), (190, 190, 190), 1)
        ecrire_image(S / f"plan-blocs-{quoi}-{app}.png", vis)
    (S / "pose" / f"blocs-{quoi}.json").write_text(json.dumps(sortie), encoding="utf-8")
    t = np.array(bilan, float)
    for nom, sel in (("toutes", t[:, 4] > 0), ("photos en bloc (≥ 2)", t[:, 4] >= 2), ("photos seules", t[:, 4] == 1)):
        u = t[sel]
        print(f"{nom:22s} ({len(u):2d}) | bien placées (< 0,5 m, < 8°) : {int(((u[:, 0] < 0.5) & (u[:, 1] < 8)).sum())} | à peu près (< 1 m, < 15°) : "
              f"{int(((u[:, 0] < 1.0) & (u[:, 1] < 15)).sum())} | bonne pièce : {int(u[:, 2].sum())} | colle aux repères (< 12 px) : {int((u[:, 3] < 12).sum())}")
    for seuil in (0.2, 0.4):
        sur = t[:, 5] > seuil
        print(f"Atelya se dit sûr (marge > {seuil}) : {int(sur.sum())} photos, dont bonne pièce {int(t[sur, 2].sum())}, à peu près placées {int(((t[sur, 0] < 1.0) & (t[sur, 1] < 15)).sum())}")
