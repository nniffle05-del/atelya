"""Tests du dessin des plans : le cas test n°0 redessiné doit être relu aussi bien que le plan d'exercice."""

import json
import random
from pathlib import Path

import cv2
from moteur.images import ecrire_image

from moteur.banc_essai import essayer
from moteur.dessin_plan import Style, dessiner_plan, style_au_hasard

EXEMPLE = Path(__file__).parent.parent / "exemples" / "cas-test-00"
LOGEMENT = json.loads((EXEMPLE / "logement.json").read_text(encoding="utf-8"))


def _pixel(image, style: Style, x: float, y: float) -> int:
    """La couleur du plan au point (x, y) en mètres du logement (repère du cas test n°0)."""
    from moteur.dessin_plan import MARGE_GAUCHE, MARGE_HAUT

    xmin, ymax = -0.20, 5.60  # bords extérieurs des murs du cas test n°0
    return int(image[round(MARGE_HAUT + (ymax - y) * style.px_par_m), round(MARGE_GAUCHE + (x - xmin) * style.px_par_m)])


def test_murs_et_ouvertures_au_bon_endroit():
    style = Style()
    image = dessiner_plan(LOGEMENT, style)
    assert _pixel(image, style, 2.0, -0.10) < 100  # dans le mur sud
    assert _pixel(image, style, 4.85, 3.0) < 100  # dans la cloison du séjour
    assert _pixel(image, style, 5.55, -0.10) > 200  # dans le trou de la porte d'entrée (5,10 à 6,00)
    assert _pixel(image, style, 2.4, 2.7) > 200  # au milieu du séjour


def test_meme_style_meme_dessin():
    a = dessiner_plan(LOGEMENT, style_au_hasard(random.Random(1)))
    b = dessiner_plan(LOGEMENT, style_au_hasard(random.Random(1)))
    assert (a == b).all()


def test_cas_test_redessine_relu_sans_faute(tmp_path):
    dossier = tmp_path / "cas-test-00"
    dossier.mkdir()
    (dossier / "logement.json").write_text(json.dumps(LOGEMENT), encoding="utf-8")
    ecrire_image(str(dossier / "plan.png"), dessiner_plan(LOGEMENT, titre="Cas test n°0 redessiné"))
    resultat = essayer(dossier / "plan.png", dossier / "logement.json")
    assert resultat.note is not None, resultat.echec
    assert resultat.note.corrections == 0, resultat.note.remarques
