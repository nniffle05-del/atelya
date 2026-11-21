"""Voir le MOTIF de ferronnerie qu'Atelya tire des photos d'un logement (moteur/ferronnerie.py), avant de le construire.

    python pc/verification/voir_ferronnerie.py <vitrages.json> <dossier des photos> <sortie.jpg>

Écrit une planche : chaque bande de garde-corps mise à plat (photo | fer), puis le module (médiane des répétitions), puis le
motif répété tel qu'il sera construit. Affiche le pas mesuré dans chaque bande : le même garde-corps doit donner le même pas
d'une photo à l'autre (contrôle des proportions redressées).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur import ferronnerie as fe  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402


def main() -> None:
    lecture = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    photos, sortie = Path(sys.argv[2]), Path(sys.argv[3])
    lignes, bandes, noms = [], [], []
    for photo, fenetres in sorted(lecture["photos"].items()):
        chemin = photos / f"{photo}.jpg"
        if not chemin.exists():
            continue
        image = lire_image(chemin)
        for n, f in enumerate(fenetres):
            b = fe.bande(image, f)
            if b is None:
                continue
            bandes.append(b)
            noms.append(f"{photo} vantail {n} ({f['baie']})")
            m = None
            if False:
                print(f"{photo} vantail {n} ({f['baie']}) : {b['face']:.0f} px de haut sur la photo, proportions {b['aspect']:.2f}, "
                  + (f"pas {m[0] / fe.HAUT_PX:.3f} de la hauteur (netteté {m[1]:.2f})" if m else "pas illisible"))
            gris = np.clip(255 - b["fer"] * 400, 0, 255).astype(np.uint8)
            gris[~b["vu"]] = 200
            lignes.append(gris)
    commun = fe.pas_commun(bandes)
    print("pas commun :", None if commun is None else round(commun / fe.HAUT_PX, 3), "de la hauteur")
    for nom, b in zip(noms, bandes):
        m = fe.pas_d_une_bande(b, commun)
        print(f"{nom} : {b['face']:.0f} px de haut sur la photo, proportions {b['aspect']:.2f}, "
              + (f"pas {m[0] / fe.HAUT_PX:.3f} de la hauteur (netteté {m[1]:.2f})" if m else "pas illisible"))
    mod = fe.module(bandes, print)
    if mod is None:
        print("PAS DE MOTIF lisible")
        return
    print(f"module : pas {mod["pas"]:.3f}, {mod["repetitions"]} répétitions, accord {mod["accord"]:.2f}, symétrie {mod["symetrie"]:.2f}, de haut en bas {mod["symetrie_debout"]:.2f} autour de {mod["axe"]:.2f}")
    c = fe.contours(mod["fer"])
    motif = {"pas": mod["pas"], "contours": c}
    print(f"{len(c)} contours, {sum(len(x) for x in c)} points")
    brut = np.clip(255 - mod["fer"] * 255, 0, 255).astype(np.uint8)
    redessine = (1 - fe.dessiner(motif, brut.shape[1], brut.shape[0])) * 255
    morceaux = fe.panneau(motif, 1.20, 0.60)
    print(f"panneau de 1,20 × 0,60 m : {len(morceaux)} morceaux, {sum(len(m['contour']) + sum(len(t) for t in m['trous']) for m in morceaux)} points")
    echelle = 500
    toile = np.full((int(0.60 * echelle) + 20, int(1.20 * echelle) + 20), 255, np.uint8)
    for m in morceaux:
        pts = [np.round(np.array([[10 + x * echelle, 10 + (0.60 - z) * echelle] for x, z in poly]) * 16).astype(np.int32)
               for poly in [m["contour"], *m["trous"]]]
        cv2.fillPoly(toile, pts, 0, lineType=cv2.LINE_AA, shift=4)
    largeur = max(toile.shape[1], max(x.shape[1] for x in lignes) * 2 + 10)

    def poser(images):
        ligne = np.full((max(i.shape[0] for i in images), largeur), 128, np.uint8)
        x = 0
        for i in images:
            if x + i.shape[1] > largeur:
                break
            ligne[:i.shape[0], x:x + i.shape[1]] = i
            x += i.shape[1] + 10
        return ligne

    rangees = [poser(lignes[i:i + 3]) for i in range(0, len(lignes), 3)]
    rangees.append(poser([brut, redessine.astype(np.uint8), np.tile(redessine.astype(np.uint8), (1, 4))]))
    rangees.append(poser([toile]))
    grand = cv2.resize(np.hstack([brut, redessine.astype(np.uint8)]), None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    ecrire_image(sortie.with_name(sortie.stem + "-module.jpg"), grand)
    ecrire_image(sortie, np.vstack([np.vstack([r, np.full((10, largeur), 128, np.uint8)]) for r in rangees]))
    print("écrit", sortie)


if __name__ == "__main__":
    main()
