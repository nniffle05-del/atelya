"""Le « photographe » d'Unreal (moteur/photographe.py) : même règle que Blender, pellicule qui imite AgX, mesure des murs sur
les images du film (courbe des tons à l'envers), exposition suivante avec la pente apprise."""
import ast
import math
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from moteur import photographe as ph

RACINE = Path(__file__).resolve().parents[1]


def test_memes_chiffres_que_blender():
    texte = (RACINE / "moteur" / "blender" / "rendre.py").read_text(encoding="utf-8")
    for nom in ("CLARTE_MURS", "FORCE_BALANCE"):
        assert float(re.search(rf"^{nom} = ([\d.]+)", texte, re.M).group(1)) == getattr(ph, nom)
    assert "EXPOSITION_MIN, EXPOSITION_MAX = -12.0, 6.0" in texte
    assert "np.percentile(luminance, [20, 90])" in texte  # les murs « ordinaires »


def test_meme_pellicule_dans_unreal():
    texte = (RACINE / "moteur" / "unreal" / "preparer_cinematique.py").read_text(encoding="utf-8")
    ligne = next(l for l in texte.splitlines() if l.startswith("PELLICULE = "))
    assert ast.literal_eval(ligne.split("=", 1)[1].strip()) == ph.PELLICULE
    assert '"render_warm_up_frames", True' in texte  # préchauffe calculée : plus de 1re image sombre


def test_reglage_exposition_et_balance():
    gris = np.full((100, 3), 0.1)
    expo, blanc = ph.reglage(gris, clarte=0.55, force_balance=0.7)
    assert expo == pytest.approx(math.log2(5.5))
    assert blanc == pytest.approx((1.0, 1.0, 1.0))
    roses = np.tile([0.12, 0.1, 0.09], (100, 1))  # murs rosis par un parquet orangé
    expo, blanc = ph.reglage(roses, clarte=0.55, force_balance=1.0)
    corrige = np.array([0.12, 0.1, 0.09]) * np.array(ph.gain_unreal(blanc))
    assert corrige[0] == pytest.approx(corrige[1]) == pytest.approx(corrige[2])  # balance complète : murs neutres
    assert float(np.array(blanc) @ ph.POIDS) == pytest.approx(1.0)  # la balance ne change pas la clarté
    assert ph.reglage(np.zeros((5, 3))) is None  # trop peu de murs : pas de réglage


def test_pellicule_imite_agx():
    for x, agx in ph.AGX_MESURES.items():
        assert abs(float(ph.courbe_unreal(x, **ph.PELLICULE)) * 255 - agx) < 3.0, x
    ecarts_usine = [abs(float(ph.courbe_unreal(x, **ph.PELLICULE_USINE)) * 255 - agx) for x, agx in ph.AGX_MESURES.items()]
    assert max(ecarts_usine) > 15  # la courbe d'usine écrase les sombres (sol trop foncé du comparatif)
    assert float(ph.courbe_unreal(0.18, **ph.PELLICULE_USINE)) * 255 == pytest.approx(117.6, abs=0.5)  # formule d'Unreal


def test_pellicule_a_l_envers():
    for x in (0.01, 0.1, 0.47, 2.0):
        assert ph.lineaire_affiche(ph.courbe_unreal(x, **ph.PELLICULE)) == pytest.approx(x, rel=0.02)


def _png(chemin: Path, image: np.ndarray):
    cv2.imencode(".png", image[..., ::-1].astype(np.uint8))[1].tofile(str(chemin))


def test_mesurer_sur_les_images_du_film(tmp_path):
    """Murs (moitié gauche) rosés, affichés par la pellicule ; masque plus petit (comme l'essai), mis à la taille de l'image."""
    murs = np.array([0.26, 0.23, 0.21])
    affiche = [float(ph.courbe_unreal(v, **ph.PELLICULE)) * 255 for v in murs]
    images, masques = [], []
    for k in range(3):
        film = np.full((40, 60, 3), 30.0)
        film[:, :30] = affiche
        masque = np.zeros((10, 15, 3))
        masque[:, :7] = 255
        _png(tmp_path / f"image-{k:04d}.png", np.round(film))
        _png(tmp_path / f"masque.{k:04d}.png", masque)
        images.append(tmp_path / f"image-{k:04d}.png")
        masques.append(tmp_path / f"masque.{k:04d}.png")
    m = ph.mesurer(images, masques, clarte=0.47, force_balance=1.0)
    assert m["correction"] == pytest.approx(math.log2(0.47 / float(murs @ ph.POIDS)), abs=0.05)
    assert m["gain"][0] < 1 < m["gain"][2]  # moins de rouge, plus de bleu
    assert all(i["murs_pixels"] > 0 for i in m["images"])
    # rendu avec un gain déjà appliqué (rouge × 2) : la mesure le retire, les murs « avant balance » sont deux fois moins rouges
    deux = ph.mesurer(images, masques, 0.47, 1.0, gain=(2.0, 1.0, 1.0))
    assert deux["gain"][0] > m["gain"][0]
    with pytest.raises(ValueError):
        ph.mesurer([], [], 0.47, 0.7)  # aucun mur vu : arrêt net, pas d'exposition inventée


def test_prochaine_exposition():
    assert ph.prochaine_exposition([(-6.7, -1.5)]) == pytest.approx(-8.2)  # un essai : 1 cran pour 1 cran
    # au soleil (11/11/2026) : -1,52 cran d'exposition n'avait rattrapé que 0,83 cran de clarté → pente 0,55
    b = ph.prochaine_exposition([(-6.69, -1.52), (-8.21, -0.69)])
    assert b == pytest.approx(-8.21 - 0.69 / (0.83 / 1.52), abs=0.01)
    assert ph.prochaine_exposition([(-7.0, -1.0), (-8.0, -1.0)]) == pytest.approx(-8.0 - 1.0 / 0.3)  # pente bornée
