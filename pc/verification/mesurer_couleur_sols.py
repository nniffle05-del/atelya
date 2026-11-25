r"""ÉTAPE 4 b (17/11/2026) : la COULEUR des sols de la maquette contre celle des photos, sur tous les logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_couleur_sols.py <sortie> app-001=<dossier des rendus> [app-002=… …]
        [--titre "…"]

<dossier des rendus> : les vues de la maquette depuis la place des photos (vue-photo-NN.png, sorties de
outils/atelya/banc_ressemblance.py ou de planches_avant_apres.py : …/planches/<nom>/vues/rendus).

Pour chaque photo qui a son rendu : le sol que la photo montre PROPREMENT (pas derrière un lit, un canapé… : moteur/pas_du_sol)
est mis à plat ; les mêmes points du sol sont pris sur le rendu (même appareil). Sur chacune des deux images : la couleur
dominante de ces points (médiane, restes de meubles écartés) en CIELAB (L clarté, a rouge, b jaune), et la même couleur
rapportée au BLANC DES MURS de l'image (ce que le sol renvoie si le mur est blanc : ne dépend plus de l'exposition).
Écrit <sortie>/couleurs.json, couleurs.txt et une image de pastilles (photo | maquette) par logement.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol  # noqa: E402
from moteur.blanc_des_murs import blanc_des_murs  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from moteur.reconnaitre_sols import lab  # noqa: E402
from moteur.sol_a_plat import photos_a_plat  # noqa: E402
from moteur.teinte_photo import lineaire  # noqa: E402

lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
PIXELS_MIN = 3000  # 0,3 m² de sol propre au moins


def dominante(pixels: np.ndarray) -> np.ndarray | None:
    """Les pixels proches de la couleur dominante (restes de meubles, tapis, reflets écartés) ; None s'il y en a trop peu."""
    if len(pixels) < PIXELS_MIN:
        return None
    L = lab(pixels)
    ecart = np.linalg.norm(L - np.median(L, 0), axis=1)
    return pixels[ecart <= 2.0 * max(float(np.median(ecart)), 1.0)]


def decrire(pixels: np.ndarray, blanc: dict | None) -> dict:
    L = np.median(lab(pixels), 0)
    rgb = np.median(pixels, 0)
    d = {"L": round(float(L[0]), 1), "a": round(float(L[1]), 1), "b": round(float(L[2]), 1), "rgb": [int(round(v)) for v in rgb]}
    if blanc is not None:
        sol = np.median(lineaire(pixels), 0)
        d["contre_le_blanc"] = [round(float(v), 3) for v in sol / np.maximum(blanc["blanc"], 1e-6)]
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie", type=Path)
    ap.add_argument("rendus", nargs="+", help="app-001=<dossier des rendus>")
    ap.add_argument("--titre", default="")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    pds = pas_du_sol.charger(avec_dino=False)
    bilan, lignes = {}, [a.titre] if a.titre else []
    for demande in a.rendus:
        cas, dossier = demande.split("=", 1)
        dossier = Path(dossier)
        fiche, logement = lire(CAS[cas]["fiche"]), lire(CAS[cas]["logement"])
        logement = logement.get("logement", logement)
        fiche["cameras"] = {n: c for n, c in fiche["cameras"].items() if (dossier / f"vue-{n}.png").is_file()}
        if not fiche["cameras"]:
            print(f"PLANTÉ : aucun rendu vue-<photo>.png dans {dossier}", flush=True)
            return 1
        vues = photos_a_plat(fiche, logement, RACINE, journal=lambda *_: None, pas_du_sol=lambda n, rgb, cas=cas: pds.masque(f"{cas}/{n}", rgb))
        rendus = photos_a_plat({**fiche, "photos": str(dossier), "fichier": "vue-{nom}.png"}, logement, RACINE, journal=lambda *_: None)
        rendus = {n: v for n, _, v in rendus}
        bilan[cas], pastilles = {}, []
        for nom, piece, vue in vues:
            r = rendus.get(nom)
            if r is None:
                continue
            propre = (vue.finesse > 0) & (r.finesse > 0)
            if vue.douteux is not None:
                propre &= ~vue.douteux
            p_photo, p_rendu = dominante(vue.image[propre]), dominante(r.image[propre])
            if p_photo is None or p_rendu is None:
                continue
            L = lab(p_photo)
            bois = (L[:, 1] > 4) & (L[:, 2] > 12)  # un parquet : les sols de carrelage sont jugés à part (peu de points)
            sorte = "bois" if bois.mean() > 0.5 else "autre"
            d_photo = decrire(p_photo, blanc_des_murs(vue.photo, vue.camera, logement, vue.piece, vue.point_de_vue))
            d_rendu = decrire(p_rendu, blanc_des_murs(r.photo, r.camera, logement, r.piece, r.point_de_vue))
            ecart = float(np.linalg.norm([d_photo[k] - d_rendu[k] for k in "Lab"]))
            bilan[cas][nom] = {"piece": piece, "sorte": sorte, "photo": d_photo, "maquette": d_rendu, "ecart": round(ecart, 1)}
            lignes.append(f"{cas} {nom} ({piece}, {sorte}) : photo L {d_photo['L']:.0f} a {d_photo['a']:.0f} b {d_photo['b']:.0f} | maquette L {d_rendu['L']:.0f} "
                          f"a {d_rendu['a']:.0f} b {d_rendu['b']:.0f} | écart {ecart:.0f} (clarté {d_rendu['L'] - d_photo['L']:+.0f}, rouge {d_rendu['a'] - d_photo['a']:+.0f}, "
                          f"jaune {d_rendu['b'] - d_photo['b']:+.0f}) | contre le blanc : photo {d_photo.get('contre_le_blanc')} maquette {d_rendu.get('contre_le_blanc')}")
            pastille = np.zeros((90, 420, 3), np.uint8)
            pastille[:, :210] = d_photo["rgb"][::-1]
            pastille[:, 210:] = d_rendu["rgb"][::-1]
            cv2.putText(pastille, f"{nom} : photo", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(pastille, "maquette", (218, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            pastilles.append(pastille)
        if pastilles:
            ecrire_image(a.sortie / f"pastilles-{cas}.png", np.concatenate(pastilles, 0))
        bois = [v for v in bilan[cas].values() if v["sorte"] == "bois"]
        if bois:
            moy = lambda cle, k: float(np.mean([v[cle][k] for v in bois]))
            lignes.append(f"{cas} PARQUETS ({len(bois)} photos) : écart moyen {np.mean([v['ecart'] for v in bois]):.1f} ; clarté {moy('maquette', 'L') - moy('photo', 'L'):+.1f} ; "
                          f"rouge {moy('maquette', 'a') - moy('photo', 'a'):+.1f} ; jaune {moy('maquette', 'b') - moy('photo', 'b'):+.1f}")
    tous = [v for c in bilan.values() for v in c.values() if v["sorte"] == "bois"]
    if tous:
        lignes.append(f"TOUS LES LOGEMENTS, parquets ({len(tous)} photos) : écart moyen {np.mean([v['ecart'] for v in tous]):.1f} ; "
                      f"clarté {np.mean([v['maquette']['L'] - v['photo']['L'] for v in tous]):+.1f} ; rouge {np.mean([v['maquette']['a'] - v['photo']['a'] for v in tous]):+.1f} ; "
                      f"jaune {np.mean([v['maquette']['b'] - v['photo']['b'] for v in tous]):+.1f}")
    (a.sortie / "couleurs.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.sortie / "couleurs.txt").write_text("\n".join(lignes), encoding="utf-8")
    print("\n".join(lignes), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
