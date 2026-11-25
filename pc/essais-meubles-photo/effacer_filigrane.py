"""ESSAI : efface un filigrane clair (lettres blanches d'une agence) posé sur un meuble détouré, avant de le donner à un programme
« photo → 3D ». POURQUOI : sinon les lettres sont imprimées sur le tissu de l'objet fabriqué (canapé bleu d'app-004, 16/11/2026).

    python pc/essais-meubles-photo/effacer_filigrane.py <détouré .png (fond transparent)> <sortie .png>

Les points nettement plus clairs et plus gris que le meuble autour d'eux sont rebouchés avec les couleurs voisines (OpenCV, rien
d'installé). Ce qui est rebouché est INVENTÉ par le voisinage : à réserver aux filigranes, jamais à un vrai motif du meuble.
"""
import sys

import cv2
import numpy as np

sys.path.insert(0, ".")
from moteur.images import ecrire_image, lire_image  # noqa: E402


def main():
    entree, sortie = sys.argv[1:3]
    rgba = lire_image(entree, cv2.IMREAD_UNCHANGED)
    if rgba is None or rgba.shape[2] != 4:
        sys.exit("PLANTÉ : il faut une image détourée à fond transparent")
    bgr, alpha = rgba[:, :, :3].copy(), rgba[:, :, 3]
    dedans = cv2.erode((alpha > 127).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    flou = cv2.medianBlur(bgr, 31)
    hsv_flou = cv2.cvtColor(flou, cv2.COLOR_BGR2HSV).astype(np.float32)
    # un filigrane blanc : plus clair ET moins coloré que le tissu qui l'entoure
    lettres = dedans & (hsv[:, :, 2] - hsv_flou[:, :, 2] > 22) & (hsv_flou[:, :, 1] - hsv[:, :, 1] > 28)
    lettres = cv2.dilate(lettres.astype(np.uint8) * 255, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    propre = cv2.inpaint(bgr, lettres, 4, cv2.INPAINT_TELEA)
    assert ecrire_image(sortie, np.dstack([propre, alpha]))
    assert ecrire_image(sortie.replace(".png", "-ce-qui-est-rebouche.png"), lettres)
    print("rebouché :", round(100 * (lettres > 0).sum() / max(1, dedans.sum()), 1), "% du meuble")


if __name__ == "__main__":
    main()
