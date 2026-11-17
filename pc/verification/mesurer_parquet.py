r"""LE PARQUET MESURÉ SUR LES PHOTOS, photo par photo (18/11/2026) : largeur et longueur des lames, nuances, joints.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_parquet.py <sortie> [app-001 app-002 …]

Pour chaque photo où le sens des lames se lit : le sol mis à plat dans le sens des lames (moteur/parquet_photo.py), les mesures,
et une IMAGE DE CONTRÔLE (<sortie>/<logement>-<photo>.jpg) : le sol à plat, le parquet retenu comme « propre » éclairci, et les
longs joints trouvés tracés en vert dans chaque bande : on voit d'un coup d'œil si les traits verts tombent sur les joints.
Puis les mesures réunies par logement (toutes les photos de lames droites ensemble).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402
from moteur import parquet_photo as pp, pas_du_sol, sens_des_lames as sl  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from moteur.sol_a_plat import piece_de_l_appareil  # noqa: E402


def main() -> int:
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    pds = pas_du_sol.charger(avec_dino=False)
    bilan = {}
    for cas in sys.argv[2:] or list(CAS):
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        logement = json.loads(Path(CAS[cas]["logement"]).read_text(encoding="utf-8"))
        logement = logement.get("logement", logement)
        axes = sl.axes_du_logement(logement)
        par_piece: dict[str, list] = {}
        bilan[cas] = {}
        for nom, d in fiche["cameras"].items():
            cam = camera_depuis_dict(d["camera"])
            piece, point = piece_de_l_appareil(cam, logement["pieces"])
            if piece is None:
                continue
            photo = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
            rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
            masque = pds.masque(f"{cas}/{nom}", rgb)
            traits = [t for t in sl.traits_du_sol(rgb, cam, logement, masque) if t["piece"] == piece["id"]]
            choix = sl.sens_parmi(traits, axes)
            if not choix or choix["note"] < 1.5 or choix["note"] < 2 * choix["autre"]:
                print(f"{cas} {nom} ({piece['id']}) : sens des lames pas lu sur cette photo", flush=True)
                continue
            image, vu = pp.sol_dans_le_sens(rgb, cam, piece["contour"], choix["sens"], masque, point)
            propre = pp.bois_propre(image, vu)
            large = pp.bois_vu(image, vu)
            m = pp.mesurer_parquet([(image, propre, large)])
            print(f"{cas} {nom} ({piece['id']}, sens {choix['sens']:.0f}°) : {json.dumps(m, ensure_ascii=False)}", flush=True)
            bilan[cas][nom] = {"piece": piece["id"], "sens": choix["sens"], **m}
            par_piece.setdefault(f"{piece['id']} sens {choix['sens']:.0f}", []).append((image, propre, large))
            # image de contrôle
            dessin = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            dessin[~large] = (dessin[~large] * 0.35).astype(np.uint8)
            dessin[large & ~propre] = (dessin[large & ~propre] * 0.7).astype(np.uint8)
            if "largeur_m" in m:
                for b in pp.rangs_par_bande(image, propre, m["largeur_m"]):
                    k = np.tan(np.radians(b["penche"]))
                    fl = b["rangs"].shape[1]
                    for j in b["joints"]:
                        # la bande a été redressée d'un penché : le joint, dans l'image d'origine, est penché d'autant
                        y0, y1 = b["ligne"] + j + k * fl / 2, b["ligne"] + j - k * fl / 2
                        cv2.line(dessin, (b["colonne"], int(round(y0))), (b["colonne"] + fl, int(round(y1))), (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(dessin, f"lames {100 * m['largeur_m']:.1f} cm", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
            ys, xs = np.nonzero(vu)
            if len(ys):
                dessin = dessin[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            ecrire_image(sortie / f"{cas}-{nom}.jpg", dessin)
        for cle, vues in par_piece.items():
            m = pp.mesurer_parquet(vues)
            print(f"{cas} ENSEMBLE {cle} ({len(vues)} photos) : {json.dumps(m, ensure_ascii=False)}", flush=True)
            bilan[cas][f"ensemble {cle}"] = m
    (sortie / "mesures.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
