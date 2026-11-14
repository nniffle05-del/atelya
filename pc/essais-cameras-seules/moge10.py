"""Recouper deux photos d'une même pièce SANS outil nouveau : les mêmes endroits retrouvés d'une photo à l'autre par l'œil
DINOv2 (petits carrés qui se ressemblent, à la même hauteur), placés en mètres par MoGe-2 ; on cherche le déplacement
(tourner + glisser) qui met le plus de carrés d'accord. Noté contre le déplacement relevé à la main.
RÉSULTAT (14/11/2026) : ÉCARTÉ. 34 paires de la même pièce : 5 déplacements justes (< 1 m, < 15°), 1 très juste ; la confiance
ne sépare pas les bonnes paires des fausses (l'œil confond les endroits qui se ressemblent, murs opposés compris)."""
import json, sys
from pathlib import Path
import numpy as np, torch
from moteur.images import lire_image
from moteur import oeil_dinov2 as od
import etape_b as eb
import moge4 as m4
import moge6 as m6

DH = 0.25       # deux carrés ne peuvent être le même endroit que s'ils sont à la même hauteur (m)
CASE = 0.25     # finesse du vote sur le glissement (m)


def carres_3d(oeil, im, z, hsp):
    """Par carré de la photo : empreinte, place (x devant, y à gauche, m), hauteur, validité."""
    f = m6.carres(oeil, im)
    R = m4.repere(z, hsp)
    if R is None:
        return None
    H, W = R["M"].shape; hp, wp = f.shape[:2]
    yy = np.clip(((np.arange(hp) + 0.5) * H / hp).astype(int), 0, H - 1); xx = np.clip(((np.arange(wp) + 0.5) * W / wp).astype(int), 0, W - 1)
    g = lambda a: a[yy][:, xx].reshape(-1)
    r, phi, h = g(R["r"]), np.radians(g(R["phi"])), g(R["h"])
    ok = g(R["M"]) & g(R["devant"]) & (h > 0.08) & (h < hsp - 0.08) & (r < 12)
    f = f.reshape(-1, f.shape[-1]); f = f / np.linalg.norm(f, axis=1, keepdims=True)
    return {"f": f[ok].astype(np.float32), "X": np.stack([r * np.cos(phi), r * np.sin(phi)], 1)[ok].astype(np.float32), "h": h[ok].astype(np.float32),
            "vert": g(R["vert"])[ok]}


def paires(a, b, seuil=0.45):
    """Carrés qui se choisissent l'un l'autre (ressemblance, même hauteur)."""
    fa, fb = torch.from_numpy(a["f"]).cuda(), torch.from_numpy(b["f"]).cuda()
    s = fa @ fb.T
    s[(torch.from_numpy(a["h"]).cuda()[:, None] - torch.from_numpy(b["h"]).cuda()[None]).abs() > DH] = -1
    ja = s.argmax(1); ib = s.argmax(0)
    i = torch.arange(len(fa), device=s.device)
    bon = (ib[ja] == i) & (s[i, ja] > seuil)
    return i[bon].cpu().numpy(), ja[bon].cpu().numpy(), s[i, ja][bon].cpu().numpy()


def deplacement(XA, XB, w):
    """Vote : pour chaque rotation, où tombent les glissements ? → (rotation °, glissement, voix du gagnant, voix du 2e)."""
    if len(XA) < 8:
        return None
    best = []
    for th in range(0, 360, 2):
        c, s = np.cos(np.radians(th)), np.sin(np.radians(th))
        t = XA - XB @ np.array([[c, s], [-s, c]])
        k = np.floor(t / CASE).astype(int); k -= k.min(0)
        idx = k[:, 0] * (k[:, 1].max() + 1) + k[:, 1]
        v = np.bincount(idx, weights=w)
        o = int(v.argmax())
        best.append((v[o], th, np.median(t[idx == o], 0)))
    best.sort(key=lambda x: -x[0])
    v1, th, t = best[0]
    v2 = max([b[0] for b in best if abs((b[1] - th + 180) % 360 - 180) > 20 or np.hypot(*(b[2] - t)) > 1.0] or [0.0])
    for _ in range(4):  # réglage fin sur les carrés d'accord
        c, s = np.cos(np.radians(th)), np.sin(np.radians(th))
        P = XB @ np.array([[c, s], [-s, c]]) + t
        d = np.hypot(*(XA - P).T); acc = d < 0.3 + 0.06 * np.hypot(*XA.T)
        if acc.sum() < 6:
            break
        a0, b0 = XA[acc].mean(0), XB[acc].mean(0)
        Hm = (XB[acc] - b0).T @ (XA[acc] - a0)
        th = float(np.degrees(np.arctan2(Hm[0, 1] - Hm[1, 0], Hm[0, 0] + Hm[1, 1])))
        c, s = np.cos(np.radians(th)), np.sin(np.radians(th))
        t = a0 - b0 @ np.array([[c, s], [-s, c]])
    return float(th % 360), t.astype(float), float(v1), float(v2), int(acc.sum())


if __name__ == "__main__":
    src, sortie = Path(sys.argv[1]), Path(sys.argv[2]); sortie.mkdir(parents=True, exist_ok=True)
    oeil = od.charger("vitb14"); res = {}; lignes = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        C, pv = {}, {}
        for nom, c in d["cameras"].items():
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            z = np.load(src / f"{app}-{nom}.npz")
            C[nom] = carres_3d(oeil, im, z, mod["hsp"])
            k = c["camera"]; pv[nom] = "?"
            for t in np.arange(0, 1.6, 0.1):
                ip = eb.piece_de(mod, np.array([[k["x"] + t * np.cos(np.radians(k["cap"])), k["y"] + t * np.sin(np.radians(k["cap"]))]]))[0]
                if ip >= 0:
                    pv[nom] = mod["ids"][ip]; break
        noms = [n for n in C if C[n] is not None]; res[app] = {}
        for i, a in enumerate(noms):
            for b in noms[i + 1:]:
                ia, ib, s = paires(C[a], C[b])
                r = deplacement(C[a]["X"][ia], C[b]["X"][ib], s)
                if r is None:
                    continue
                th, t, v1, v2, nacc = r
                ka, kb = d["cameras"][a]["camera"], d["cameras"][b]["camera"]
                ca, sa = np.cos(np.radians(ka["cap"])), np.sin(np.radians(ka["cap"]))
                tv = np.array([[ca, sa], [-sa, ca]]) @ np.array([kb["x"] - ka["x"], kb["y"] - ka["y"]])
                e, da = float(np.hypot(*(t - tv))), float(abs((th - (kb["cap"] - ka["cap"]) + 180) % 360 - 180))
                meme = pv[a] == pv[b]
                lignes.append((meme, e, da, v1, v2, nacc, len(ia)))
                res[app][f"{a}|{b}"] = {"rot": th, "t": t.tolist(), "voix": v1, "voix2": v2, "accord": nacc, "paires": int(len(ia))}
                print(f"{app} {a[-2:]}-{b[-2:]} {'MÊME ' if meme else 'autre'} ({pv[a][:8]:8s}/{pv[b][:8]:8s}) | {len(ia):4d} carrés appariés, {nacc:3d} d'accord, voix {v1:5.1f} (2e {v2:5.1f}) | "
                      + (f"écart au corrigé {e:5.2f} m, {da:5.1f}°" if meme else ""), flush=True)
    (sortie / "recoupement.json").write_text(json.dumps(res), encoding="utf-8")
    L = np.array(lignes, float); m = L[:, 0] == 1
    print(f"paires de la même pièce : {int(m.sum())} | déplacement juste (< 1 m, < 15°) : {int(((L[m, 1] < 1) & (L[m, 2] < 15)).sum())} | très juste (< 0,5 m, < 8°) : {int(((L[m, 1] < 0.5) & (L[m, 2] < 8)).sum())}")
    for seuil in (20, 30, 40, 60):
        for rap in (1.0, 1.5):
            sur = (L[:, 5] >= seuil) & (L[:, 3] >= rap * L[:, 4])
            print(f"  accord ≥ {seuil} carrés, gagnant ≥ {rap} × le 2e : {int(sur.sum())} paires, dont même pièce {int((sur & m).sum())}, dont justes {int((sur & m & (L[:, 1] < 1) & (L[:, 2] < 15)).sum())}")
