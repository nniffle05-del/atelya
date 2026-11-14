r"""Zoom et orientation d'une photo par les LIGNES DE FUITE (essai du 15/11/2026, pour le corrigé d'app-003).

Pourquoi : dans une pièce, les arêtes horizontales (corniches, poutres, hauts de portes, plinthes) suivent deux directions à
l'équerre. Sur la photo, chaque famille converge vers un point de l'horizon. La place de ces deux points donne, sans le plan,
le ZOOM de l'appareil (focale f) et son ORIENTATION par rapport aux murs (à 90° près) : (u1 - u0)(u2 - u0) = -f².
Appareil supposé de niveau (verticales droites), centre optique au milieu en largeur.

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\fuites.py <dossier photos> <sortie> photo-01 photo-02 ...
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur.images import ecrire_image, lire_image  # noqa: E402


def segments(image, mini=30):
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    s = lsd.detect(gris)[0]
    s = s.reshape(-1, 4) if s is not None else np.zeros((0, 4))
    return s[np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]) >= mini]


def fuites(image, tolerance=1.2, haut_seulement=True):
    """(alpha°, f, v0, note, segments, famille de chaque segment) ; alpha = angle entre l'axe de visée et la 1re direction des murs."""
    h, w = image.shape[:2]
    u0 = w / 2
    s = segments(image)
    dx, dy = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    long = np.hypot(dx, dy)
    garde = np.abs(np.degrees(np.arctan2(dx, dy)) % 180 - 90) < 84  # ni vertical (à 6° près)
    garde &= ~((np.abs(np.degrees(np.arctan2(dx, dy))) < 6) | (np.abs(np.degrees(np.arctan2(dx, dy))) > 174))
    mx, my = (s[:, 0] + s[:, 2]) / 2, (s[:, 1] + s[:, 3]) / 2
    if haut_seulement:
        garde &= my < h / 2 - 15  # le parquet en chevrons a ses propres fuites : on ne garde que le haut de la photo
    s, dx, dy, long, mx, my = s[garde], dx[garde], dy[garde], long[garde], mx[garde], my[garde]
    direction = np.arctan2(dy, dx)
    poids = np.minimum(long, 150.0)

    def note(alpha, f, v0, detail=False):
        t = np.tan(np.radians(alpha))
        points = [u0 + f * t, u0 - f / t if abs(t) > 1e-6 else 1e9]
        ecart = []
        for pu in points:
            vers = np.arctan2(v0 - my, pu - mx)
            d = np.abs((direction - vers + np.pi / 2) % np.pi - np.pi / 2)
            ecart.append(np.degrees(d))
        ecart = np.array(ecart)
        bon = ecart.min(0) < tolerance
        if detail:
            return np.where(bon, ecart.argmin(0), -1)
        n1 = (poids * (ecart[0] < tolerance)).sum()
        n2 = (poids * (ecart[1] < tolerance)).sum()
        return n1 + n2, min(n1, n2)

    meilleur = None
    for v0 in (h / 2,):
        for alpha in np.arange(-44.5, 45.01, 0.5):
            for f in np.arange(260, 720, 10):
                n, petit = note(alpha, f, v0)
                if meilleur is None or n > meilleur[0]:
                    meilleur = (n, alpha, f, v0, petit)
    _, a0, f0, v0, _ = meilleur
    for alpha in np.arange(a0 - 0.6, a0 + 0.61, 0.1):
        for f in np.arange(f0 - 12, f0 + 12.1, 2):
            for v in np.arange(h / 2 - 12, h / 2 + 12.1, 3):
                n, petit = note(alpha, f, v)
                if n > meilleur[0]:
                    meilleur = (n, alpha, f, v, petit)
    n, alpha, f, v0, petit = meilleur
    courbe = {int(ff): round(float(max(note(a, ff, v0)[0] for a in np.arange(alpha - 1, alpha + 1.01, 0.25))), 0) for ff in range(260, 720, 20)}
    return float(alpha), float(f), float(v0), float(n), float(petit), s, note(alpha, f, v0, True), courbe


def main():
    dossier, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    resultats = {}
    for nom in sys.argv[3:]:
        image = lire_image(dossier / f"{nom}.jpg")
        alpha, f, v0, n, petit, s, famille, courbe = fuites(image)
        resultats[nom] = {"alpha": round(alpha, 2), "f": round(f, 1), "v0": round(v0, 1), "note": round(n), "petite_famille": round(petit), "courbe": courbe}
        print(nom, resultats[nom])
        for (x0, y0, x1, y1), fam in zip(s, famille):
            couleur = [(0, 0, 255), (0, 200, 0), (160, 160, 160)][fam] if fam >= 0 else (160, 160, 160)
            cv2.line(image, (int(x0), int(y0)), (int(x1), int(y1)), couleur, 2 if fam >= 0 else 1)
        cv2.line(image, (0, int(v0)), (image.shape[1], int(v0)), (255, 0, 255), 1)
        ecrire_image(sortie / f"fuites-{nom}.png", image)
    (sortie / "fuites.json").write_text(json.dumps(resultats, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
