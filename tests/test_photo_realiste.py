"""Option --photo-realiste du générateur : la feuille posée sur une vraie table (étape 6-16)."""

import dataclasses
from pathlib import Path

import numpy as np

from moteur.generateur.exportateur import Options, style_pour
from moteur.generateur.logements import generer
from moteur.generateur.rendu import rendre

GRAINE = 40002  # un plan de la famille « photo » (vraie caméra)
MASQUES = ("masque_semantique", "masque_pieces", "masque_elements", "contours", "hauteur")


def _styles():
    camera = Options(dossier=Path("."), familles=["photo"], vraie_camera=True)
    realiste = dataclasses.replace(camera, photo_realiste=True)
    return style_pour(GRAINE, 0, camera), style_pour(GRAINE, 0, realiste)


def test_les_anciens_styles_ne_changent_pas():
    camera, realiste = _styles()
    assert camera.realisme is None and realiste.realisme is not None
    assert dataclasses.replace(realiste, realisme=None) == camera


def test_les_masques_restent_exacts():
    log = generer(GRAINE)
    camera, realiste = _styles()
    a = rendre(log, log.niveaux[0], camera)
    b = rendre(log, log.niveaux[0], realiste)
    for nom in MASQUES:
        assert np.array_equal(a.images[nom], b.images[nom]), nom
    sans_style = lambda ann: {k: v for k, v in ann.items() if k != "style"}  # noqa: E731
    assert sans_style(a.annotations) == sans_style(b.annotations)
    assert a.images["plan"].shape == b.images["plan"].shape


def test_la_table_entoure_la_feuille():
    log = generer(GRAINE)
    camera, realiste = _styles()
    a = rendre(log, log.niveaux[0], camera).images["plan"].astype(np.float32)
    b = rendre(log, log.niveaux[0], realiste).images["plan"].astype(np.float32)
    # Un coin de la photo est hors de la feuille : sans l'option, c'est la couleur du papier ; avec, la table.
    coin_a, coin_b = a[:8, :8].mean(axis=(0, 1)), b[:8, :8].mean(axis=(0, 1))
    assert np.abs(coin_a - coin_b).max() > 10


def test_meme_graine_meme_photo():
    log = generer(GRAINE)
    _, realiste = _styles()
    a = rendre(log, log.niveaux[0], realiste).images["plan"]
    b = rendre(log, log.niveaux[0], realiste).images["plan"]
    assert np.array_equal(a, b)
