r"""Le sens et la largeur des lames de parquet lus sur les photos, tous logements (17/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_sens_des_lames.py <sortie> [--cas app-001 …]

Pour chaque logement : photo par photo puis pièce par pièce, le sens des lames mesuré (moteur/sens_des_lames.py), à côté du
sens qu'Atelya posait jusqu'ici (celui des murs les plus longs du logement, le même partout). Écrit une image par logement : le
plan avec les traits retenus (verts : dans le sens trouvé ; gris : les autres) et une flèche par pièce.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol, sens_des_lames as sl  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402

lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    pds = pas_du_sol.charger(avec_dino=False)
    for cas in a.cas:
        fiche, logement = lire(CAS[cas]["fiche"]), lire(CAS[cas]["logement"])
        logement = logement.get("logement", logement)
        from moteur.habillage import orientation_sols
        from moteur.logement import Logement
        try:
            regle = math.degrees(orientation_sols(Logement.model_validate(logement))) % 180
        except Exception:  # un logement de vérification (autre enveloppe) : la règle n'est pas calculée
            regle = float("nan")
        axes = sl.axes_du_logement(logement)
        print(f"== {cas} (sens posé jusqu'ici, partout : {regle:.0f}° ; sens des murs : {axes})")
        dossier, modele = RACINE / fiche["photos"], fiche.get("fichier", "{nom}.png")
        tous: dict[str, list] = {}
        for nom, d in fiche["cameras"].items():
            photo = lire_image(dossier / modele.format(nom=nom))
            rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
            traits = sl.traits_du_sol(rgb, camera_depuis_dict(d["camera"]), logement, pds.masque(f"{cas}/{nom}", rgb))
            par_piece: dict[str, list] = {}
            for t in traits:
                par_piece.setdefault(t["piece"], []).append(t)
                tous.setdefault(t["piece"], []).append({**t, "photo": nom})
            for pid, ts in par_piece.items():
                s = sl.sens(ts)
                c = sl.sens_parmi(ts, axes)
                if c and c["note"] >= 1:
                    print(f"   {nom} {pid:14s} LE LONG DES MURS : {c['sens']:.0f}° note {c['note']} contre {c['autre']}" + (" SÛR" if c["sur"] else ""))
                if False and s and s["poids_m"] >= 3:
                    l = sl.largeur_des_lames(ts, s["sens"])
                    print(f"   {nom} {pid:14s} sens {s['sens']:5.1f}° part {s['part']:.2f} travers {s['travers']:.2f} ({s['poids_m']:.0f} m de traits)"
                          + (" SÛR" if s["sur"] else "") + (f" | lames de {100 * l['largeur_m']:.0f} cm ({l['ecarts']} écarts, part {l['part']})" if l else ""))
        # le plan
        pts = np.array([q for p in logement["pieces"] for q in p["contour"]], float)
        x0, y0, x1, y1 = pts[:, 0].min() - 0.5, pts[:, 1].min() - 0.5, pts[:, 0].max() + 0.5, pts[:, 1].max() + 0.5
        k = 1800 / (x1 - x0)
        px = lambda q: (int((q[0] - x0) * k), int((y1 - q[1]) * k))
        image = np.full((int((y1 - y0) * k), 1800, 3), 255, np.uint8)
        for p in logement["pieces"]:
            cv2.polylines(image, [np.array([px(q) for q in p["contour"]], np.int32)], True, (0, 0, 0), 2, cv2.LINE_AA)
        for pid, ts in tous.items():
            s = sl.sens(ts)
            if not s:
                continue
            c = sl.sens_parmi(ts, axes)
            l = sl.largeur_des_lames(ts, c["sens"]) if c else None
            print(f"  {pid:14s} TOUTES LES PHOTOS, LE LONG DES MURS : {c['sens']:.0f}° note {c['note']} contre {c['autre']}" + (" SÛR" if c["sur"] else " pas sûr")
                  + (f" | lames de {100 * l['largeur_m']:.0f} cm ({l['ecarts']} écarts, part {l['part']})" if l else ""))
            s = {**s, "sens": c["sens"], "sur": c["sur"]}
            print(f"  {pid:14s} (pic libre) : sens {s['sens']:5.1f}° part {s['part']:.2f} travers {s['travers']:.2f} ({s['poids_m']:.0f} m)"
                  + (" SÛR" if s["sur"] else " pas sûr") + (f" | lames de {100 * l['largeur_m']:.0f} cm ({l['ecarts']} écarts, part {l['part']})" if l else ""))
            for t in ts:
                dans = abs((t["angle"] - s["sens"] + 90) % 180 - 90) <= sl.LARGEUR_PIC
                cv2.line(image, px(t["a"]), px(t["b"]), (0, 150, 0) if dans else (190, 190, 190), 2 if dans else 1, cv2.LINE_AA)
            if s["sur"]:
                c = np.mean([t["milieu"] for t in ts], axis=0)
                u = np.array([math.cos(math.radians(s["sens"])), math.sin(math.radians(s["sens"]))])
                cv2.arrowedLine(image, px(c - u), px(c + u), (0, 0, 255), 5, cv2.LINE_AA, tipLength=0.15)
        ecrire_image(a.sortie / f"sens-{cas}.jpg", image)
    return 0


if __name__ == "__main__":
    sys.exit(main())
