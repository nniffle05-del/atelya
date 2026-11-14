"""Point 2, temps B : choisir ENSEMBLE la place de toutes les photos d'un logement : bonnes notes, type de pièce d'après les
meubles vus (OWLv2), pas deux photos au même endroit, chaque pièce importante montrée. Image : le plan avec les appareils."""
import json, os, sys
from pathlib import Path
import cv2, numpy as np
from moteur.images import ecrire_image
import etape_b as eb
from moteur import camera_photo as cp


def colle(cam, c):
    """Second juge (la main est incertaine de ~0,5 m) : place et cap GARDÉS, hauteur / zoom / centre réglés, de combien
    les repères relevés à la main s'écartent-ils (px, moyenne) ? Zoom déraisonnable = ne colle pas."""
    k = c["camera"]
    c0 = [cam[0], cam[1], k["z"], cam[2], 0.0, k["f"], k["u0"], k["v0"]]
    c1, r = cp.ajuster(c0, c["reperes"], libres=(2, 5, 7), rappels={5: (k["f"], 0.02), 2: (k["z"], 5.0)})
    return float(np.abs(r).mean()) if 250 < c1[5] < 1100 and 0.3 < c1[2] < 2.2 else 99.0

L_TYPE = float(os.environ.get("L_TYPE", 1.0))      # poids du type de pièce d'après les meubles
L_COUV = float(os.environ.get("L_COUV", 0.15))     # prime par pièce importante montrée
L_DOUBLE = float(os.environ.get("L_DOUBLE", 0.5))  # amende : deux photos au même endroit, même regard
L_MEME = float(os.environ.get("L_MEME", 0.4))      # prime : deux photos qui se ressemblent beaucoup, dans la même pièce
SEUIL_MEME = 0.6
PRINCIPALES = ("sejour", "chambre", "cuisine")


def sorte(piece):
    return piece.rsplit("_", 1)[0]


def indices(objs):
    """Ce que les meubles disent : {type de pièce: facteur} (1 = compatible)."""
    m = lambda *noms: max([o["note"] for o in objs if o["nom"] in noms] or [0.0])
    nb = lambda nom, s: sum(o["nom"] == nom and o["note"] >= s for o in objs)
    lit = m("a bed", "a bed with a duvet", "a bunk bed", "a loft bed")
    salon = max(m("a sofa", "a couch"), m("a coffee table"), m("a dining table"))
    cuisine = nb("a cabinet", 0.4) + nb("kitchen cabinets", 0.3) >= 3
    repas = m("a dining table") >= 0.35 or nb("a chair", 0.4) + nb("a stool", 0.4) >= 3
    f = {}
    if lit >= 0.45:
        f = {"chambre": 1.0, "sejour": 0.6}
    elif salon >= 0.45:
        f = {"sejour": 1.0, "chambre": 0.5}
    elif repas:
        f = {"sejour": 1.0, "cuisine": 0.9, "chambre": 0.3}
    elif cuisine:
        f = {"cuisine": 1.0, "sejour": 0.8, "entree": 0.6, "degagement": 0.5}
    return f


def facteur(f, piece):
    return 1.0 if not f else f.get(sorte(piece), 0.25)


def choisir(cands, types, sim=None, graine=0):
    noms = list(cands); rng = np.random.default_rng(graine)
    seul = {n: [np.log(max(c["note"], 1e-3)) + L_TYPE * np.log(facteur(types[n], c["piece"])) for c in cands[n]] for n in noms}

    def lies(a, b):
        """Même pièce ? très ressemblantes, ou chacune la plus ressemblante de l'autre (et assez)."""
        if sim[a][b] >= SEUIL_MEME:
            return True
        ma = max(noms, key=lambda x: sim[a][x] if x != a else -1); mb = max(noms, key=lambda x: sim[b][x] if x != b else -1)
        return ma == b and mb == a and sim[a][b] >= 0.5

    def total(ch):
        s = sum(seul[n][ch[n]] for n in noms)
        vues = {cands[n][ch[n]]["piece"] for n in noms}
        s += L_COUV * sum(sorte(p) in PRINCIPALES for p in vues)
        for i, a in enumerate(noms):
            ca = cands[a][ch[a]]["cam"]
            for b in noms[i + 1:]:
                cb = cands[b][ch[b]]["cam"]
                if np.hypot(ca[0] - cb[0], ca[1] - cb[1]) < 1.0 and abs((ca[2] - cb[2] + 180) % 360 - 180) < 25:
                    s -= L_DOUBLE
                if sim is not None and lies(a, b) and cands[a][ch[a]]["piece"] == cands[b][ch[b]]["piece"]:
                    s += L_MEME
        return s
    meilleur = (None, -1e9)
    for essai in range(30):
        ch = {n: (int(np.argmax(seul[n])) if essai == 0 else int(rng.integers(len(cands[n])))) for n in noms}
        v = total(ch); bouge = True
        while bouge:
            bouge = False
            for n in rng.permutation(noms):
                for k in range(len(cands[n])):
                    c2 = dict(ch); c2[n] = k; v2 = total(c2)
                    if v2 > v + 1e-9:
                        ch, v, bouge = c2, v2, True
        if v > meilleur[1]:
            meilleur = (ch, v)
    ch, v = meilleur
    marges = {}  # de combien l'ensemble perd si cette photo change de PIÈCE (petit = Atelya n'est pas sûr)
    for n in noms:
        autres = [total({**ch, n: k}) for k in range(len(cands[n])) if cands[n][k]["piece"] != cands[n][ch[n]]["piece"]]
        marges[n] = v - max(autres) if autres else 9.0
    return ch, marges


if __name__ == "__main__":
    S = Path(sys.argv[1]); objets = json.loads((S / "objets.json").read_text(encoding="utf-8"))
    bilan = {"seule": [], "ensemble": []}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        cands = {n: c for n, c in json.loads((S / "pose" / f"par-piece-{app}.json").read_text(encoding="utf-8")).items() if c}
        types = {n: indices(objets[f"{app}/{n}"]) for n in cands}
        mp = json.loads((S / "meme-piece.json").read_text(encoding="utf-8"))[app]
        sim = {a: {b: mp["sim"][i][j] for j, b in enumerate(mp["noms"])} for i, a in enumerate(mp["noms"])}
        ens, marges = choisir(cands, types, sim)
        E = 60; cc = np.concatenate(mod["pieces"]); o0 = cc.min(0) - 0.5; taille = ((cc.max(0) - o0 + 0.5) * E).astype(int)
        vis = np.full((taille[1], taille[0], 3), 255, np.uint8)
        px = lambda p: (int((p[0] - o0[0]) * E), int(taille[1] - (p[1] - o0[1]) * E))
        for a, b, g in zip(mod["A"], mod["B"], mod["genre"]):
            cv2.line(vis, px(a), px(b), ((0, 0, 0), (0, 160, 255), (255, 160, 0))[g], 2)
        for n in cands:
            k = d["cameras"][n]["camera"]; pv = "?"
            for t in np.arange(0, 1.6, 0.1):  # appareil relevé « dans le mur » : la pièce est celle qu'il regarde
                ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
                if ip >= 0:
                    pv = mod["ids"][ip]; break
            ligne = f"{app} {n} (meubles : {'/'.join(types[n]) or '?'} ; main : {pv})"
            for quoi, i in (("seule", int(np.argmax([c["note"] for c in cands[n]]))), ("ensemble", ens[n])):
                c = cands[n][i]; cam = c["cam"]
                e, dc = float(np.hypot(cam[0] - k["x"], cam[1] - k["y"])), float(abs((cam[2] - k["cap"] + 180) % 360 - 180))
                ec = colle(cam, d["cameras"][n])
                bilan[quoi].append((e, dc, c["piece"] == pv, ec, marges[n] if quoi == "ensemble" else 0))
                ligne += f" | {quoi} : {c['piece']} {e:.2f} m {dc:.0f}° ({ec:.0f} px)"
            print(ligne + f" | marge {marges[n]:.2f}")
            for q, coul in (((k["x"], k["y"], k["cap"]), (0, 150, 0)), (cands[n][ens[n]]["cam"], (0, 0, 255))):
                t = np.radians(q[2]); p0 = np.array(q[:2])
                cv2.circle(vis, px(p0), 7, coul, -1); cv2.line(vis, px(p0), px(p0 + 0.7 * np.array([np.cos(t), np.sin(t)])), coul, 2)
                cv2.putText(vis, n[-2:], (px(p0)[0] + 8, px(p0)[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, coul, 2)
            cv2.line(vis, px((k["x"], k["y"])), px(cands[n][ens[n]]["cam"][:2]), (190, 190, 190), 1)
        ecrire_image(S / f"plan-ensemble-{app}.png", vis)
    for quoi, t in bilan.items():
        t = np.array(t, float)
        print(f"{quoi:9s} | bien placées (< 0,5 m, < 8°) : {int(((t[:, 0] < 0.5) & (t[:, 1] < 8)).sum())} / {len(t)} | à peu près (< 1 m, < 15°) : "
              f"{int(((t[:, 0] < 1.0) & (t[:, 1] < 15)).sum())} | dans la bonne pièce : {int(t[:, 2].sum())} | colle aux repères (< 12 px) : {int((t[:, 3] < 12).sum())}")
    t = np.array(bilan["ensemble"], float)
    for seuil in (0.1, 0.2, 0.4):
        sur = t[:, 4] > seuil
        print(f"Atelya se dit sûr de la pièce (marge > {seuil}) : {int(sur.sum())} photos, dont bonne pièce {int(t[sur, 2].sum())}, à peu près placées {int(((t[sur, 0] < 1.0) & (t[sur, 1] < 15)).sum())}")
