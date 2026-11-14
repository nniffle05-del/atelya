"""Deux photos montrent-elles LE MÊME LIEU ? Contrôle croisé par Depth Anything 3 lui-même : on lui donne les deux photos,
il rend la profondeur de chacune et la place des deux appareils ; les points de la photo A, revus depuis l'appareil B,
doivent tomber à la profondeur que B mesure au même endroit (et avoir à peu près la même couleur). Mesuré sur toutes les
paires de photos de chaque logement, contre le corrigé (même pièce ou non).
RÉSULTAT (14/11/2026) : au seuil de 40 % d'accord dans la partie commune, 23 vraies paires reconnues sur 34 pour 5 fausses
(dont deux chambres jumelles, 54 %, et un séjour avec une chambre, 67 %). Trop peu net pour FORMER les groupes ; sert à
sortir d'un groupe la photo qu'aucune autre ne revoit (moge16, SEUIL_INTRUS)."""
import json, sys
from itertools import combinations
from pathlib import Path
import cv2, numpy as np
from moteur import da3
import moge17 as m17


def revoir(r, i, j, ims):
    """Points de la photo i revus depuis l'appareil j → (part des points de i qui tombent dans j ET à la bonne profondeur,
    part d'accord parmi ceux qui tombent dans j, écart de couleur moyen des points d'accord /255)."""
    h, w = r["taille"]; d = r["profondeur"][i]
    fx, fy = r["focale_px"][i]; gx, gy = r["focale_px"][j]
    v, u = np.meshgrid(np.arange(h) + 0.5 - h / 2, np.arange(w) + 0.5 - w / 2, indexing="ij")
    Pw = np.stack([u / fx * d, v / fy * d, d], -1) @ r["appareils"][i][:, :3].T + r["appareils"][i][:, 3]
    Pj = (Pw - r["appareils"][j][:, 3]) @ r["appareils"][j][:, :3]
    z = Pj[..., 2]
    x = np.round(Pj[..., 0] / np.maximum(z, 1e-6) * gx + w / 2 - 0.5).astype(int); y = np.round(Pj[..., 1] / np.maximum(z, 1e-6) * gy + h / 2 - 0.5).astype(int)
    sur = r["confiance"][i] > np.percentile(r["confiance"][i], 30)
    dedans = sur & (z > 0) & (x >= 0) & (x < w) & (y >= 0) & (y < h)
    if dedans.sum() < 50:
        return 0.0, 0.0, 1.0
    dj = r["profondeur"][j][y[dedans], x[dedans]]
    ok = np.abs(z[dedans] - dj) / dj < 0.10
    coul = np.abs(ims[i][dedans][ok].astype(np.float32) - ims[j][y[dedans], x[dedans]][ok]).mean() / 255 if ok.sum() > 20 else 1.0
    return float(ok.sum() / sur.sum()), float(ok.mean()), float(coul)


def meme_lieu(modele, a, b):
    """→ (part en commun et d'accord, accord dans la partie commune, écart de couleur), les deux sens réunis."""
    r = da3.lire(modele, [a, b])
    ims = [da3.preparer(a)[:r["taille"][0], :r["taille"][1]], da3.preparer(b)[:r["taille"][0], :r["taille"][1]]]
    p1, p2 = revoir(r, 0, 1, ims), revoir(r, 1, 0, ims)
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2


if __name__ == "__main__":
    S = Path(sys.argv[1]); modele = da3.charger(); L = []; garde = {}
    for app in ("app-002", "app-001"):
        d, mod, ims, mes, pv = m17.charger(S, app)
        garde[app] = {}
        for a, b in combinations(list(ims), 2):
            commun, accord, coul = meme_lieu(modele, ims[a], ims[b])
            meme = pv[a] == pv[b]
            L.append((meme, commun, accord, coul)); garde[app][f"{a}|{b}"] = [commun, accord, coul]
            print(f"{app} {a[-2:]}-{b[-2:]} {'MÊME ' if meme else 'autre'} ({pv[a][:9]:9s}/{pv[b][:9]:9s}) | en commun et d'accord {100 * commun:3.0f} % | accord dans le commun {100 * accord:3.0f} % | couleur {coul:.2f}", flush=True)
    (S / "meme-lieu-da3.json").write_text(json.dumps(garde), encoding="utf-8")
    L = np.array(L, float); m = L[:, 0] == 1
    for k, nom in ((1, "en commun et d'accord"), (2, "accord dans le commun")):
        print(f"{nom} : même pièce médiane {100 * np.median(L[m, k]):.0f} % (de {100 * L[m, k].min():.0f} à {100 * L[m, k].max():.0f}) | pièces différentes médiane {100 * np.median(L[~m, k]):.0f} % (de {100 * L[~m, k].min():.0f} à {100 * L[~m, k].max():.0f})")
        for seuil in np.arange(0.05, 0.75, 0.05):
            oui = L[:, k] >= seuil
            print(f"    seuil {100 * seuil:.0f} % : dites « même lieu » {int(oui.sum())}, dont vraies {int((oui & m).sum())} sur {int(m.sum())}, fausses {int((oui & ~m).sum())}")
