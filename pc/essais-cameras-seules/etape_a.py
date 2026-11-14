"""Étape A : lignes de la photo → horizon, focale, angle entre le regard et les murs."""
import json, sys, time
from pathlib import Path
import cv2
import numpy as np
from moteur.images import lire_image


def segments(gris, long_min=30):
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    clair = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gris)  # blanc sur blanc : plafond contre mur
    s = np.concatenate([x.reshape(-1, 4) for x in (lsd.detect(gris)[0], lsd.detect(clair)[0]) if x is not None]).astype(float)
    L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
    s, L = s[L >= long_min], L[L >= long_min]
    h, w = gris.shape
    logo = (np.maximum(s[:, 0], s[:, 2]) < 0.22 * w) & (np.maximum(s[:, 1], s[:, 3]) < 0.08 * h)
    return s[~logo], L[~logo]


def direction_murs(logement):
    """Direction principale des murs (degrés, modulo 90)."""
    a, p = [], []
    for m in logement["murs"]:
        d = np.array(m["fin"], float) - np.array(m["debut"], float)
        a.append(np.degrees(np.arctan2(d[1], d[0])) % 90); p.append(np.hypot(*d))
    a, p = np.array(a), np.array(p)
    z = (p * np.exp(1j * np.radians(a * 4))).sum()
    return float(np.degrees(np.angle(z)) / 4 % 90)


def fuite(seg, L, w, h, tol_deg=1.5):
    """(v_h, f, alpha, score) : alpha = angle (degrés, sens trigo) de la direction de murs 1 par rapport au regard."""
    u0 = w / 2
    d = seg[:, 2:] - seg[:, :2]
    ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180
    vert = np.abs(ang - 90) < 3.0
    s, Ls, dd = seg[~vert], L[~vert], d[~vert]
    dd = dd / np.linalg.norm(dd, axis=1)[:, None]
    mil = (s[:, :2] + s[:, 2:]) / 2
    poids = np.minimum(Ls, 200.0)

    def note(vh, f, al):  # tableaux de même forme (K,) → (K,)
        ca, sa = np.cos(np.radians(al)), np.sin(np.radians(al))
        tot = np.zeros(len(vh)); parts = []
        for X, Y, W in ((u0 * ca - f * sa, vh * ca, ca), (u0 * sa + f * ca, vh * sa, sa)):
            ex = X[:, None] - mil[None, :, 0] * W[:, None]
            ey = Y[:, None] - mil[None, :, 1] * W[:, None]
            n = np.hypot(ex, ey) + 1e-9
            sinus = np.abs(ex * dd[None, :, 1] - ey * dd[None, :, 0]) / n
            ok = sinus < np.sin(np.radians(tol_deg))
            parts.append((ok * poids[None, :]).sum(1))
        return parts[0] + parts[1], parts[0], parts[1]

    def grille(vhs, fs, als):
        V, F, A = np.meshgrid(vhs, fs, als, indexing="ij")
        V, F, A = V.ravel(), F.ravel(), A.ravel()
        sc = np.concatenate([note(V[i:i + 4000], F[i:i + 4000], A[i:i + 4000])[0] for i in range(0, len(V), 4000)])
        return V, F, A, sc
    V, F, A, sc = grille(np.arange(0.2 * h, 0.7 * h, 8.0), np.geomspace(330, 800, 24), np.arange(-45, 45, 2.0))
    i = int(np.argmax(sc))
    V, F, A, sc = grille(np.arange(V[i] - 10, V[i] + 10.1, 2.0), np.geomspace(F[i] / 1.06, F[i] * 1.06, 9), np.arange(A[i] - 2.5, A[i] + 2.6, 0.5))
    i = int(np.argmax(sc))
    t, p1, p2 = note(V[i:i + 1], F[i:i + 1], A[i:i + 1])
    return float(V[i]), float(F[i]), float(A[i]), float(t[0]), float(p1[0]), float(p2[0]), float(poids.sum())


if __name__ == "__main__":
    for app in ("app-001", "app-002"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        log = json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8"))
        base = direction_murs(log)
        print(app, "direction des murs", round(base, 1))
        for nom, c in d["cameras"].items():
            ch = Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)
            im = lire_image(ch)
            gris = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            t0 = time.time()
            seg, L = segments(gris)
            vh, f, al, sc, p1, p2, tot = fuite(seg, L, gris.shape[1], gris.shape[0])
            k = c["camera"]
            al_vrai = ((base - k["cap"]) + 45) % 90 - 45
            print(f"  {nom} seg {len(seg):4d} | horizon {vh:5.0f} (main {k['v0']:5.0f}) | focale {f:4.0f} (main {k['f']:4.0f}) | angle {al:6.1f} (main {al_vrai:6.1f}) | appui {p1 / tot:.2f} {p2 / tot:.2f} | {time.time() - t0:.1f} s")
