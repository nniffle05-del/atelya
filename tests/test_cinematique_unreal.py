"""Outils de la cinématique Unreal (outils/unreal/) : calage de l'exposition sur une référence, comparatif des moteurs."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils" / "unreal"))

import cinematique_unreal as cu  # noqa: E402
import comparer_moteurs as cm  # noqa: E402


def _ecrire(chemin: Path, valeur: int, taille=(36, 64)):
    image = np.full((*taille, 3), valeur, dtype=np.uint8)
    cv2.imencode(".png", image)[1].tofile(str(chemin))


def test_ecart_d_exposition(tmp_path):
    """Une image deux fois moins claire (en lumière physique) que la référence demande +1 cran."""
    rendu, reference = tmp_path / "rendu", tmp_path / "ref"
    rendu.mkdir()
    reference.mkdir()
    clair = 188  # ≈ 0,5 en clarté linéaire
    sombre = round(255 * (1.055 * 0.25 ** (1 / 2.4) - 0.055))  # 0,25 en clarté linéaire
    for f in (1, 48, 96):
        _ecrire(rendu / f"image-{f:04d}.png", sombre)
        _ecrire(reference / f"image-{f:04d}.png", clair)
    assert abs(cu.ecart_d_exposition(rendu, reference) - 1.0) < 0.05
    assert abs(cu.ecart_d_exposition(reference, reference)) < 1e-9


def test_comparer_moteurs(tmp_path):
    dossiers = []
    for k in range(3):
        d = tmp_path / f"m{k}"
        d.mkdir()
        for f in range(1, 5):
            _ecrire(d / f"image-{f:04d}.png", 60 * k + 20, taille=(72, 128))
        dossiers.append(d)
    sortie = tmp_path / "comparatif"
    cm.comparer(sortie, [("A", dossiers[0], 29.0), ("B", dossiers[1], 2.0), ("C", dossiers[2], 0.3)], largeur=64)
    assert sortie.with_suffix(".mp4").is_file()
    planche = cv2.imdecode(np.fromfile(str(sortie.with_suffix(".jpg")), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert planche.shape[:2] == (72 * 3, 128)  # l'image du milieu de chaque moteur, l'une sous l'autre


def test_repere_atelya_vers_unreal():
    """Le passage vérifié à l'import d'app-002 : X = 100 x, Y = -100 y, Z = 100 z (texte du script Unreal)."""
    texte = (Path(__file__).resolve().parents[1] / "moteur" / "unreal" / "preparer_cinematique.py").read_text(encoding="utf-8")
    assert "unreal.Vector(100.0 * x, -100.0 * y, 100.0 * z)" in texte
    assert "-float(cap)" in texte


def test_images_d_essai_appariees(tmp_path):
    """Movie Render Queue nomme la passe du masque « FinalImage » + nom du matériau : chaque image a son masque."""
    for f in (1, 9, 17):
        (tmp_path / f"FinalImage.{f:04d}.png").write_bytes(b"")
        (tmp_path / f"FinalImageM_MasqueBlancs.{f:04d}.png").write_bytes(b"")
    images, masques = cu.images_d_essai(tmp_path)
    assert [p.name for p in images] == ["FinalImage.0001.png", "FinalImage.0009.png", "FinalImage.0017.png"]
    assert [p.name for p in masques] == [f"FinalImageM_MasqueBlancs.{f:04d}.png" for f in (1, 9, 17)]
