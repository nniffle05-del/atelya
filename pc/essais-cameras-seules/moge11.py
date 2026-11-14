"""Deux photos placées sur le plan montrent-elles LES MÊMES CHOSES AU MÊME ENDROIT ? Pour un couple de places proposées,
chaque petit carré d'une photo (placé en mètres par MoGe-2) est comparé aux carrés de l'autre photo qui tombent au même
endroit du logement : même aspect (œil DINOv2) = accord, aspect différent = désaccord. Sert à départager les places
(vérification) au lieu de chercher l'assemblage à l'aveugle (moge10 : 5 paires justes sur 34).
RÉSULTAT (14/11/2026) : ÉCARTÉ. 14 paires où le bon couple de places est proposé : il arrive 1er à l'accord 1 fois
(aux notes seules : 7 fois). Profondeurs trop incertaines + aspect trop peu précis."""
import json, os, sys
from pathlib import Path
import numpy as np, torch
from moteur.images import lire_image
from moteur import oeil_dinov2 as od
import etape_b as eb
import moge10 as m10

RAYON = float(os.environ.get("RAYON", 0.45))   # « au même endroit » : à moins de tant de mètres (les profondeurs sont incertaines)
NEUTRE = float(os.environ.get("NEUTRE", 0.45))  # ressemblance de deux carrés pris au hasard dans un même logement


def monde(c, cam):
    t = np.radians(cam[2]); R = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]], np.float32)
    return torch.from_numpy((c["X"] * cam[3]) @ R.T + np.array(cam[:2], np.float32)).cuda()


def accord(ca, cama, cb, camb, T):
    """→ note d'accord (positive = mêmes choses au même endroit), nombre de carrés qui se recouvrent."""
    A, B = monde(ca, cama), monde(cb, camb)
    pres = (torch.cdist(A, B) < RAYON) & ((T["h"][id(ca)][:, None] - T["h"][id(cb)][None]).abs() < 0.2)
    s = T["f"][id(ca)] @ T["f"][id(cb)].T
    s = torch.where(pres, s, torch.full_like(s, -1))
    m1, m2 = s.max(1).values, s.max(0).values
    v = torch.cat([m1[m1 > -1], m2[m2 > -1]])
    return (float((v - NEUTRE).sum()) / 200, int(len(v))) if len(v) else (0.0, 0)


def preparer(app, src, oeil, hsp, d):
    C = {}
    for nom in d["cameras"]:
        im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
        c = m10.carres_3d(oeil, im, np.load(src / f"{app}-{nom}.npz"), hsp)
        if c is not None:
            garde = (c["h"] > 0.15) & (c["h"] < min(hsp - 0.15, 2.3))  # ni sol, ni plafond, ni haut des murs (partout pareils)
            C[nom] = {k: v[garde] for k, v in c.items()}
    T = {"f": {id(c): torch.from_numpy(c["f"]).cuda() for c in C.values()}, "h": {id(c): torch.from_numpy(c["h"]).cuda() for c in C.values()}}
    return C, T


if __name__ == "__main__":
    S = Path(sys.argv[1]); src = S / "moge"; oeil = od.charger("vitb14"); bilan = []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        cands = {n: c for n, c in json.loads((S / "pose" / f"par-piece-{app}.json").read_text(encoding="utf-8")).items() if c}
        C, T = preparer(app, src, oeil, mod["hsp"], d)
        juste = lambda n, c: (np.hypot(c["cam"][0] - d["cameras"][n]["camera"]["x"], c["cam"][1] - d["cameras"][n]["camera"]["y"]) < 1.0
                              and abs((c["cam"][2] - d["cameras"][n]["camera"]["cap"] + 180) % 360 - 180) < 15)
        noms = [n for n in cands if n in C]
        for i, a in enumerate(noms):
            for b in noms[i + 1:]:
                L = []
                for x in cands[a]:
                    for y in cands[b]:
                        if x["piece"] != y["piece"]:
                            continue
                        v, n = accord(C[a], x["cam"], C[b], y["cam"], T)
                        L.append((v, n, juste(a, x), juste(b, y), x["note"] * y["note"]))
                if not L:
                    continue
                L = np.array(L, float)
                if not (L[:, 2] * L[:, 3]).any():
                    continue  # la bonne paire de places n'est pas dans les propositions
                o = np.argsort(-L[:, 0]); rang = int(np.where((L[o, 2] * L[o, 3]) > 0)[0][0]) + 1
                on = np.argsort(-L[:, 4]); rang_notes = int(np.where((L[on, 2] * L[on, 3]) > 0)[0][0]) + 1
                bon = L[(L[:, 2] * L[:, 3]) > 0, 0].max(); faux = L[(L[:, 2] * L[:, 3]) == 0, 0]
                bilan.append((rang, rang_notes, len(L)))
                print(f"{app} {a[-2:]}-{b[-2:]} | {len(L):3d} couples de places | le bon couple : accord {bon:6.2f}, rang {rang} (par les notes seules : rang {rang_notes}) | "
                      f"meilleur faux couple {faux.max() if len(faux) else 0:6.2f}, faux moyens {faux.mean() if len(faux) else 0:6.2f}", flush=True)
    b = np.array(bilan)
    print(f"{len(b)} paires de photos où le bon couple est proposé | bon couple 1er à l'accord : {int((b[:, 0] == 1).sum())} (aux notes seules : {int((b[:, 1] == 1).sum())}) | "
          f"dans les 3 premiers : {int((b[:, 0] <= 3).sum())} (notes : {int((b[:, 1] <= 3).sum())}) | couples par paire : {b[:, 2].mean():.0f} en moyenne")
