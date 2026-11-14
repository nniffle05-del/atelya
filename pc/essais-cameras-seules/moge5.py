"""Pose des photos sur le plan, avec les portes et fenêtres vues par leur relief (moge4) pour départager les places.
MODE=murs (murs seuls), MODE=trou (ancien « on voit à travers » de moge2), MODE=creux (relief : défaut)."""
import json, os, sys, time
from pathlib import Path
import numpy as np
import etape_b as eb
import moge2 as m2
import moge4 as m4

MODE = os.environ.get("MODE", "creux")
P_MUR = float(os.environ.get("P_MUR", 0.6))    # creux vu là où le plan a un mur plein
P_FEN = float(os.environ.get("P_FEN", 0.3))    # fenêtre du plan là où la photo ne voit aucun creux (rideaux : possible)
A_FEN = float(os.environ.get("A_FEN", 0.6))    # MODE=fen : part de la note perdue si la fenêtre VUE ne tombe sur aucune fenêtre du plan
B_FEN = float(os.environ.get("B_FEN", 0.2))    # MODE=fen : part perdue si les fenêtres du plan en vue ne sont pas vues (rideaux fermés, reflets)
P_SOL = float(os.environ.get("P_SOL", 0.3))    # creux jusqu'au sol contre fenêtre à appui, ou l'inverse
ECH = tuple(float(v) for v in os.environ.get("ECH", "0.94,1.0,1.06").split(","))
LIM = tuple(float(v) for v in os.environ.get("LIM", "0.9,1.1").split(","))


def profil(z, hsp, aspect=None):
    R = m4.repere(z, hsp)
    if R is None:
        return None
    mur = m4.mur_par_direction(R, hsp)
    if len(mur) < 15:
        return None
    rel, _ = m4.relief(R, mur)
    ph = np.array(sorted(mur), float); rr = np.array([mur[int(d)] for d in ph])
    creux, sol = m4.ouvertures_vues(R, rel, hsp, ph)
    if aspect is not None:  # fenêtre reconnue à son aspect (même derrière des rideaux), sur le mur ou juste devant
        import cv2
        H, W = R["M"].shape
        fen = cv2.resize(aspect[..., 2].astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR) > 0.5
        mi = (~np.isnan(rel)) & (R["h"] > 1.0) & (R["h"] < 1.9) & (rel > -0.35)
        k = np.round(R["phi"]).astype(int); vu = np.zeros(len(ph), bool)
        for i, d in enumerate(ph):
            col = (k == int(d)) & mi
            if col.sum() >= 20 and (col & fen).sum() / col.sum() > 0.5:
                vu[i] = True
        if MODE == "fen":  # 1 = creux (relief), 2 = fenêtre (aspect), 3 = les deux
            creux = creux.astype(np.int8) + 2 * vu
        else:
            creux = creux | vu
    return ph, rr, creux, sol, {"z": R["z"], "ech": R["ech"]}


def tirs(mod, P, angles):
    """→ distances, sorte touchée (0 mur, 1 porte, 2 fenêtre ou baie), bas de l'ouverture touchée (m)."""
    D = np.stack([np.cos(np.radians(angles)), np.sin(np.radians(angles))], 1)[None].repeat(len(P), 0)
    t, s, b = [], [], []
    for i in range(0, len(P), 200):
        tt, j = eb.lancer(mod, P[i:i + 200], D[i:i + 200])
        t.append(tt); s.append(mod["sorte"][j]); b.append(mod["bas"][j] > 0.4)
    return np.concatenate(t), np.concatenate(s), np.concatenate(b)


def note(rm, rp, creux, sol, sorte, appui):
    rp = np.minimum(rp, 40.0)
    v = np.exp(-0.5 * ((rm - rp) / (0.10 + 0.04 * rp)) ** 2)
    if MODE == "fen":
        cr, fen, pf = (creux & 1) > 0, (creux & 2) > 0, sorte == 2
        v = v * np.where(cr & ~fen & (sorte == 0), 0.7, 1.0)
        v = v * np.where(cr & (sorte > 0) & (((sol == 1) & appui) | ((sol == -1) & ~appui)), 1 - P_SOL, 1.0)
        base, nf, npf, les2 = v.mean(-1), fen.sum(-1), pf.sum(-1), (fen & pf).sum(-1)
        if np.max(nf) >= 5:
            base = base * (1 - A_FEN + A_FEN * les2 / np.maximum(nf, 1))
        return base * np.where(npf >= 5, 1 - B_FEN + B_FEN * les2 / np.maximum(npf, 1), 1.0)
    if MODE != "murs":
        v = v * np.where(creux & (sorte == 0), 1 - P_MUR, 1.0) * np.where(~creux & (sorte == 2), 1 - P_FEN, 1.0)
        if MODE in ("creux", "aspect"):
            v = v * np.where(creux & (sorte > 0) & (((sol == 1) & appui) | ((sol == -1) & ~appui)), 1 - P_SOL, 1.0)
    return v.mean(-1)


def precis(mod, ph, rm, creux, sol, cam):
    def f(c):
        if eb.piece_de(mod, c[None, :2])[0] < 0:
            return -1
        t, s, b = tirs(mod, c[None, :2], c[2] + ph)
        return float(note(rm * c[3], t, creux, sol, s, b)[0])
    best, pas = f(cam), np.array([0.1, 0.1, 2.0, 0.03])
    for _ in range(40):
        bouge = False
        for i in range(4):
            for sg in (-1, 1):
                c = cam.copy(); c[i] += sg * pas[i]
                if i == 3 and not LIM[0] <= c[3] <= LIM[1]:
                    continue
                v = f(c)
                if v > best + 1e-6:
                    best, cam, bouge = v, c, True
        if not bouge:
            pas = pas / 2
            if pas[0] < 0.005:
                break
    return cam, best


def candidats(mod, G, tour, tsorte, tappui, pr, nb=8):
    ph, rm, creux, sol, info = pr
    ip = ph.astype(int)
    notes = np.stack([np.stack([note(rm[None] * e, tour[:, (cap + ip) % 360], creux[None], sol[None], tsorte[:, (cap + ip) % 360],
                                     tappui[:, (cap + ip) % 360]) for cap in range(360)], 1) for e in ECH], 2)
    cands = []
    for o in np.argsort(notes.ravel())[::-1][:20000]:
        g, reste = divmod(int(o), 360 * len(ECH)); cap, ie = divmod(reste, len(ECH))
        if all(np.hypot(*(G[g] - q[:2])) > 0.6 or abs((cap - q[2] + 180) % 360 - 180) > 20 for q in cands):
            cands.append(np.array([G[g][0], G[g][1], float(cap), ECH[ie]]))
        if len(cands) == nb:
            break
    return sorted((precis(mod, ph, rm, creux, sol, q) for q in cands), key=lambda x: -x[1])


if __name__ == "__main__":
    src, sortie = Path(sys.argv[1]), Path(sys.argv[2]); sortie.mkdir(parents=True, exist_ok=True)
    bilan, garde = [], {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        mod = eb.modele(log); mod = dict(mod, sorte=mod["genre"].copy(), genre=np.zeros_like(mod["genre"]))
        G = m2.grille(mod)
        tour, tsorte, tappui = tirs(mod, G, np.arange(360.0))
        for nom, c in d["cameras"].items():
            k = c["camera"]; t0 = time.time()
            z = np.load(src / f"{app}-{nom}.npz")
            asp = np.load(src.parent / "aspect" / f"{app}-{nom}.npy") if MODE in ("aspect", "fen") else None
            pr = profil(z, mod["hsp"], asp)
            if pr is None:
                print(f"{app} {nom} : pas assez de murs vus"); bilan.append((np.nan, np.nan, 0, 0)); continue
            if MODE == "trou":  # l'ancien indice : seulement ce qui est à plus d'1 m derrière le mur
                p2 = m2.profil({k_: z[k_] for k_ in z.files}, mod["hsp"])
                tr = dict(zip(p2[0].astype(int), p2[2]))
                pr = (pr[0], pr[1], np.array([tr.get(int(a), False) for a in pr[0]]), pr[3] * 0, pr[4])
            fins = candidats(mod, G, tour, tsorte, tappui, pr)
            cam, n1 = fins[0]; n2 = fins[1][1] if len(fins) > 1 else 0
            ecart = float(np.hypot(cam[0] - k["x"], cam[1] - k["y"])); dcap = float(abs((cam[2] - k["cap"] + 180) % 360 - 180))
            rang = next((i + 1 for i, (q, _) in enumerate(fins) if np.hypot(q[0] - k["x"], q[1] - k["y"]) < 0.6 and abs((q[2] - k["cap"] + 180) % 360 - 180) < 10), 0)
            pm = mod["ids"][eb.piece_de(mod, cam[None, :2])[0]]
            pv = mod["ids"][eb.piece_de(mod, np.array([[k["x"], k["y"]]]))[0]]
            print(f"{app} {nom} [{c.get('qualite')}] écart {ecart:5.2f} m, cap {dcap:5.1f}°, dans {pm} (main : {pv}) | note {n1:.2f} (2e {n2:.2f}) | "
                  f"bonne place au rang {rang} | {len(pr[0])}° vus, {int(pr[2].sum())}° en creux dont {int((pr[2] & (pr[3] == 1)).sum())}° jusqu'au sol | {time.time() - t0:.0f} s", flush=True)
            bilan.append((ecart, dcap, rang, n1 - n2))
            garde[f"{app}-{nom}"] = [[*map(float, q), float(n)] for q, n in fins]
    (sortie / f"candidats-{MODE}{os.environ.get("SUFF", "")}.json").write_text(json.dumps(garde), encoding="utf-8")
    t = np.array(bilan)
    ok = (t[:, 0] < 0.5) & (t[:, 1] < 8); large = (t[:, 0] < 1.0) & (t[:, 1] < 15)
    print(f"MODE {MODE} | bien placées (< 0,5 m et < 8°) : {int(ok.sum())} / {len(t)} | à peu près (< 1 m et < 15°) : {int(large.sum())} | "
          f"bonne place dans les 8 premières : {int((t[:, 2] > 0).sum())}")
