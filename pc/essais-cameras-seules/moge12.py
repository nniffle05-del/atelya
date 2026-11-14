"""Le ZOOM trouvé seul, sans outil nouveau : MoGe-2 donne à part l'INCLINAISON de chaque surface (ses « normales », lues sur
l'aspect, sans rapport avec le zoom) et les POINTS en mètres (qui s'étirent en profondeur quand le zoom est faux). Le bon
zoom est celui pour lequel l'inclinaison calculée d'après les points rejoint celle lue à part. Noté contre le zoom de la main.
RÉSULTAT (14/11/2026) : ÉCARTÉ. Le zoom « accordé » retombe sur celui de MoGe-2 (écart médian à la main 12 % contre 10 %) :
les inclinaisons s'étirent avec les points, elles n'apportent pas d'avis indépendant."""
import json, sys
from pathlib import Path
import cv2, numpy as np
from moteur import moge

RAPPORTS = np.arange(0.50, 1.251, 0.025)


def desaccord(z, f):
    """Écart médian (°) entre l'inclinaison des surfaces d'après les points remontés au zoom f, et celle lue à part."""
    P = moge._monter(z["brut"], z["masque_brut"], float(z["echelle"]), f)["points"][::4, ::4]
    N = z["normales"].astype(np.float32)[::4, ::4]; M = z["masque"][::4, ::4]
    P = cv2.blur(P, (5, 5))
    du, dv = (P[:, 4:] - P[:, :-4])[2:-2], (P[4:] - P[:-4])[:, 2:-2]
    n = np.cross(du, dv); L = np.linalg.norm(n, axis=-1)
    n = n / np.maximum(L, 1e-9)[..., None]
    c = np.abs((n * N[2:-2, 2:-2]).sum(-1)).clip(0, 1)
    zc = P[2:-2, 2:-2, 2]
    ok = cv2.erode(M.astype(np.uint8), np.ones((9, 9), np.uint8))[2:-2, 2:-2] > 0
    ok &= (np.linalg.norm(du, axis=-1) < 0.15 * zc) & (np.linalg.norm(dv, axis=-1) < 0.15 * zc) & (L > 0)  # pas à cheval sur un bord
    return float(np.degrees(np.arccos(np.median(c[ok])))) if ok.sum() > 500 else np.nan, float(np.degrees(np.arccos(c[ok])).mean()) if ok.sum() > 500 else np.nan


def zoom(z):
    """→ focale (px de la mesure) qui accorde le mieux points et inclinaisons, et la courbe."""
    f0 = float(z["focale"])
    e = np.array([desaccord(z, f0 * r)[1] for r in RAPPORTS])
    i = int(np.nanargmin(e))
    if 0 < i < len(e) - 1:  # creux affiné par une parabole
        a, b, c = e[i - 1], e[i], e[i + 1]; dec = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c > 1e-9 else 0.0
    else:
        dec = 0.0
    return f0 * (RAPPORTS[i] + dec * 0.025), e


if __name__ == "__main__":
    src = Path(sys.argv[1]); L = []; res = {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        for nom, c in d["cameras"].items():
            z = np.load(src / f"{app}-{nom}.npz"); z = {k: z[k] for k in z.files}
            fm = c["camera"]["f"] * z["masque"].shape[1] / c["largeur"]
            f, e = zoom(z)
            res[f"{app}-{nom}"] = f / z["masque"].shape[1]
            L.append((float(z["focale"]) / fm, f / fm))
            print(f"{app} {nom} [{c.get('qualite')}] zoom de MoGe-2 / main {L[-1][0]:.2f} | zoom accordé / main {L[-1][1]:.2f} | désaccord {np.nanmin(e):.1f}° (à MoGe-2 : {e[np.argmin(np.abs(RAPPORTS - 1))]:.1f}°)", flush=True)
    L = np.array(L)
    for nom, v in (("MoGe-2 seul", L[:, 0]), ("accordé aux inclinaisons", L[:, 1])):
        print(f"{nom:26s} : médiane {np.median(v):.2f}, écart médian à la main {100 * np.median(np.abs(v - 1)):.0f} %, pire {100 * np.max(np.abs(v - 1)):.0f} %, à moins de 10 % : {int((np.abs(v - 1) < 0.1).sum())} / {len(v)}")
    (src.parent / "zoom-accorde.json").write_text(json.dumps(res), encoding="utf-8")
