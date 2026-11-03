"""Lire et écrire des images dans un dossier dont le nom a des accents (piège de cv2 sous Windows)."""
import numpy as np
import pytest

from moteur.images import ecrire_image, lire_image

cv2 = pytest.importorskip("cv2")


@pytest.mark.parametrize("extension", [".png", ".jpg"])
def test_aller_retour_dans_un_dossier_accentue(tmp_path, extension):
    dossier = tmp_path / "Modélisation immobilière à côté"
    dossier.mkdir()
    image = np.full((40, 60), 255, np.uint8)
    image[10:30, 5:55] = 0  # un mur noir
    chemin = dossier / f"plan{extension}"
    assert ecrire_image(chemin, image)
    assert chemin.stat().st_size > 0
    relue = lire_image(chemin, cv2.IMREAD_GRAYSCALE)
    assert relue is not None and relue.shape == image.shape
    if extension == ".png":
        assert np.array_equal(relue, image)


def test_fichier_absent_donne_none(tmp_path):
    assert lire_image(tmp_path / "été" / "absent.png") is None
