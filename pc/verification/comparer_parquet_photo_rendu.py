r"""LE JUGE DU PARQUET (18/11/2026, NT : « je veux que le sens soit le même, et aussi le parquet ») : le parquet MESURÉ sur
chaque photo et sur le rendu de la maquette fait du même endroit (même mesure : moteur/parquet_photo.py).

    ..\atelya\.venv\Scripts\python.exe pc\verification\comparer_parquet_photo_rendu.py <sortie> app-001=<dossier des rendus> […]

<dossier des rendus> : vue-<photo>.png, maquette SANS meubles (pc\verification\sols_nus.py : …/planches/<logement>/vues/rendus).
Pour chaque photo où le sens des lames se lit : largeur des lames, nuances, longueur, joints, sur la photo et sur la maquette ;
et une image <sortie>/<logement>-<photo>.jpg : le même morceau de sol VU DE DESSUS, la photo à gauche, la maquette à droite, à
la même échelle (les lames à l'horizontale) : on voit d'un coup d'œil si c'est le même parquet.
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

CLES = (("largeur_m", "largeur des lames", 100, "cm"), ("nuance", "nuances", 100, "%"), ("longueur_m", "longueur", 1, "m"), ("creux_mm", "joint", 1, "mm"))


def main() -> int:
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    pds = pas_du_sol.charger(avec_dino=False)
    bilan, lignes = {}, []
    ecarts = {c[0]: [] for c in CLES}
    for demande in sys.argv[2:]:
        cas, dossier = demande.split("=", 1)
        fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
        logement = json.loads(Path(CAS[cas]["logement"]).read_text(encoding="utf-8"))
        logement = logement.get("logement", logement)
        axes = sl.axes_du_logement(logement)
        bilan[cas] = {}
        for nom, d in fiche["cameras"].items():
            rendu = Path(dossier) / f"vue-{nom}.png"
            if not rendu.is_file():
                continue
            cam = camera_depuis_dict(d["camera"])
            piece, point = piece_de_l_appareil(cam, logement["pieces"])
            if piece is None:
                continue
            photo = cv2.cvtColor(lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
            image = cv2.cvtColor(lire_image(rendu), cv2.COLOR_BGR2RGB)
            if image.shape[:2] != photo.shape[:2]:
                image = cv2.resize(image, (photo.shape[1], photo.shape[0]), interpolation=cv2.INTER_AREA)
            masque = pds.masque(f"{cas}/{nom}", photo)
            traits = [t for t in sl.traits_du_sol(photo, cam, logement, masque) if t["piece"] == piece["id"]]
            choix = sl.sens_parmi(traits, axes)
            if not choix or choix["note"] < 1.5 or choix["note"] < 2 * choix["autre"]:
                continue
            a_plat, vu = pp.sol_dans_le_sens(photo, cam, piece["contour"], choix["sens"], masque, point)
            propre, large = pp.bois_propre(a_plat, vu), pp.bois_vu(a_plat, vu)
            m_photo = pp.mesurer_parquet([(a_plat, propre, large)])
            # la maquette au même endroit : les mêmes points du sol (ceux que la photo montre proprement)
            r_plat, r_vu = pp.sol_dans_le_sens(image, cam, piece["contour"], choix["sens"], None, point)
            m_rendu = pp.mesurer_parquet([(r_plat, r_vu & large, r_vu & large)])
            bilan[cas][nom] = {"piece": piece["id"], "sens": choix["sens"], "photo": m_photo, "maquette": m_rendu}
            morceaux = []
            for cle, titre, k, unite in CLES:
                p, r = m_photo.get(cle), m_rendu.get(cle)
                if p is not None and r is not None:
                    ecarts[cle].append(abs(r / p - 1.0) if p else 0.0)
                dire = lambda v: "non mesuré" if v is None else f"{k * v:.1f} {unite}" if k != 1 else f"{v:.2f} {unite}"
                morceaux.append(f"{titre} : photo {dire(p)}, maquette {dire(r)}")
            lignes.append(f"{cas} {nom} ({piece['id']}) | " + " | ".join(morceaux))
            print(lignes[-1], flush=True)
            # l'image côte à côte : le sol vu de dessus, photo | maquette
            ys, xs = np.nonzero(large)
            if len(ys) < 2000:
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            gauche, droite = a_plat[y0:y1, x0:x1].copy(), r_plat[y0:y1, x0:x1].copy()
            gauche[~large[y0:y1, x0:x1]] = 255
            droite[~(large & r_vu)[y0:y1, x0:x1]] = 255
            paire = np.concatenate([gauche, np.full((gauche.shape[0], 12, 3), 255, np.uint8), droite], 1)
            bandeau = np.full((34, paire.shape[1], 3), 255, np.uint8)
            cv2.putText(bandeau, f"{cas} {nom} : la photo, sol vu de dessus", (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(bandeau, "la maquette, au meme endroit", (gauche.shape[1] + 18, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
            ecrire_image(sortie / f"{cas}-{nom}.jpg", cv2.cvtColor(np.concatenate([bandeau, paire], 0), cv2.COLOR_RGB2BGR))
    resume = "BILAN (écart moyen maquette / photo) : " + " ; ".join(
        f"{titre} {100 * np.mean(ecarts[cle]):.0f} % sur {len(ecarts[cle])} vues" for cle, titre, _, _ in CLES if ecarts[cle])
    print(resume, flush=True)
    (sortie / "parquets.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    (sortie / "parquets.txt").write_text("\n".join(lignes + [resume]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
