"""Tests de la lecture de la barre d'échelle dessinée sous un plan (moteur/barre_echelle.py)."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from moteur.lecture_cotes import TexteLu
from tests.test_coloriage import S, coloriage_t2

pytest.importorskip("rapidocr")

K = 1  # dessin à la taille du coloriage : sur une page plus grande, le petit « 2 m » échappe à la lecture


POLICE = Path(__file__).resolve().parent.parent / "moteur" / "polices" / "DejaVuSans.ttf"


def _texte(img: np.ndarray, texte: str, x: int, y: int) -> None:
    """Un texte comme ceux du générateur (police DejaVu, 22 px), coin haut gauche en (x, y)."""
    page = Image.fromarray(img)
    ImageDraw.Draw(page).text((x, y), texte, fill=60, font=ImageFont.truetype(str(POLICE), 22))
    img[:] = np.asarray(page)


def _barre(img: np.ndarray, x: int, y: int, px_par_m: float, metres: int) -> None:
    """Une barre comme celles du générateur : cases d'un mètre, pleines et vides tour à tour, cadre foncé,
    « 0 » sous le bout gauche et « N m » sous le bout droit."""
    for k in range(metres):
        u0, u1 = round(x + k * px_par_m), round(x + (k + 1) * px_par_m)
        if k % 2 == 0:
            cv2.rectangle(img, (u0, y), (u1, y + 8), 40, -1)
        cv2.rectangle(img, (u0, y), (u1, y + 8), 40, 1)
    _texte(img, "0", x - 6, y + 20)
    _texte(img, f"{metres} m", round(x + metres * px_par_m) - 10, y + 20)


def dessin_sans_cotes_avec_barre(metres: int = 2) -> np.ndarray:
    c = coloriage_t2()
    g = cv2.resize(np.where(c == 1, 30, 255).astype(np.uint8), None, fx=K, fy=K, interpolation=cv2.INTER_NEAREST)
    g = cv2.copyMakeBorder(g, 0, 160, 0, 0, cv2.BORDER_CONSTANT, value=255)
    _barre(g, 100 * K, 560 * K, S * K, metres)
    return g


def test_barre_lue_sur_un_plan_sans_cotes():
    from moteur.echelle_plan import lire_echelle_plan

    c = coloriage_t2()
    dessin = dessin_sans_cotes_avec_barre()
    col = np.pad(c, ((0, 160 // K), (0, 0)))  # le coloriage couvre aussi la marge du bas (vide)
    e = lire_echelle_plan(dessin, col)
    assert e.px_par_m is None  # aucune cote
    assert e.barre_sure and e.barre == pytest.approx(S, rel=0.01)
    largeur, hauteur, source = e.decision(de_biais=False)
    assert source == "barre" and largeur == hauteur == pytest.approx(S, rel=0.01)


def test_barre_mesuree_au_pixel_pres():
    from moteur.barre_echelle import lire_barre

    g = np.full((300, 700), 255, np.uint8)
    _barre(g, 100, 150, 123.0, 2)
    textes = [TexteLu("0", np.array([[92, 172], [110, 172], [110, 192], [92, 192]], float), 0.9),
              TexteLu("2 m", np.array([[336, 172], [380, 172], [380, 192], [336, 192]], float), 0.9)]
    b = lire_barre(g, textes)
    assert b is not None and b.sure and b.metres == 2
    assert b.px_par_m == pytest.approx(123.0, abs=0.6)


def test_barre_d_un_plan_un_peu_de_travers_mesuree_en_entier():
    """Un scan penché de 0,45° que rien n'a remis droit : la barre descend de 2 pixels d'un bout à
    l'autre, mais elle est mesurée en entier (et pas jusqu'à la première marche de la pente)."""
    from moteur.barre_echelle import lire_barre

    g = np.full((300, 700), 255, np.uint8)
    _barre(g, 100, 150, 123.0, 2)
    m = cv2.getRotationMatrix2D((350, 150), -0.45, 1.0)
    g = cv2.warpAffine(g, m, (700, 300), flags=cv2.INTER_LINEAR, borderValue=255)
    textes = [TexteLu("0", np.array([[92, 172], [110, 172], [110, 192], [92, 192]], float), 0.9),
              TexteLu("2 m", np.array([[336, 174], [380, 174], [380, 194], [336, 194]], float), 0.9)]
    b = lire_barre(g, textes)
    assert b is not None and b.sure
    assert b.px_par_m == pytest.approx(123.0, rel=0.01)


@pytest.mark.parametrize("metres, flou", [(2, "tourne"), (2, "grain"), (1, "tourne"), (3, "grain")])
def test_barre_floue_mesuree_sans_le_pixel_de_trop(metres, flou):
    """Un dessin flou (scan penché remis droit, ou grain lissé) étale les bouts de la barre d'un pixel :
    la barre ne doit pas s'en trouver allongée (+0,4 % avant la version 0.4). Bout droit plein (1 ou 3 m)
    ou simple trait (2 m)."""
    from moteur.barre_echelle import lire_barre

    g = np.full((300, 700), 255, np.uint8)
    _barre(g, 100, 150, 123.0, metres)
    if flou == "tourne":
        for angle in (1.3, -1.3):  # penché au scan, puis remis droit comme le coloriage
            m = cv2.getRotationMatrix2D((350.3, 150.6), angle, 1.0)
            g = cv2.warpAffine(g, m, (700, 300), flags=cv2.INTER_LINEAR, borderValue=255)
    else:
        bruit = np.random.default_rng(4).normal(0, 12, g.shape)
        g = np.clip(cv2.GaussianBlur(g.astype(float), (0, 0), 0.8) + bruit, 0, 255).astype(np.uint8)
    xd = round(100 + metres * 123.0)
    textes = [TexteLu("0", np.array([[92, 172], [110, 172], [110, 192], [92, 192]], float), 0.9),
              TexteLu(f"{metres} m", np.array([[xd - 10, 172], [xd + 34, 172], [xd + 34, 192], [xd - 10, 192]], float), 0.9)]
    b = lire_barre(g, textes)
    assert b is not None and b.metres == metres
    assert b.px_par_m == pytest.approx(123.0, rel=0.002)


def test_barre_sans_second_indice_pas_sure():
    """Une barre d'un mètre toute pleine, sans « 0 » : rien ne la confirme, elle n'est pas sûre."""
    from moteur.barre_echelle import lire_barre

    g = np.full((300, 600), 255, np.uint8)
    cv2.rectangle(g, (100, 150), (200, 158), 40, -1)
    _texte(g, "1 m", 190, 172)
    textes = [TexteLu("1 m", np.array([[190, 172], [234, 172], [234, 192], [190, 192]], float), 0.9)]
    b = lire_barre(g, textes)
    assert b is not None and not b.sure
    assert b.px_par_m == pytest.approx(100, abs=1.5)


def test_decider_avec_une_barre():
    """Logement de 600 × 400 px intérieur ; barre sûre de 100 px par m."""
    from moteur.echelle_plan import decider

    assert decider(None, None, False, None, None, (600, 400), False, 100.0) == (100.0, 100.0, "barre")
    assert decider(None, None, False, None, None, (600, 400), True, 100.0) == (100.0, None, "barre")  # photo : largeur seule
    # Les cotes passent avant la barre.
    assert decider(98.0, 98.0, True, None, None, (600, 400), False, 100.0)[2] == "cotes"
    # Logement de 60 cm de large d'après la barre : invraisemblable, à vérifier.
    assert decider(None, None, False, None, None, (600, 400), False, 1000.0)[2] == "à vérifier"
    # Des cotes mesurées mais rejetées, et une barre qui contredit la cote d'ensemble lue (6,00 m) :
    # le logement ne ferait que 4 m de large, à vérifier.
    assert decider(150.0, 150.0, True, 6.0, None, (600, 400), False, 150.0)[2] == "à vérifier"
    # Sans cote mesurée, « 12,33 » est sans doute une surface (« 12,33 m² ») : il ne contredit pas la barre.
    assert decider(None, None, False, 12.33, None, (600, 400), False, 100.0)[2] == "barre"
    # Des cotes rejetées par le garde-fou, mais une barre plausible : on garde la barre.
    assert decider(150.0, 150.0, True, 6.0, 4.0, (600, 400), False, 100.0) == (100.0, 100.0, "barre")
    # Des surfaces écrites qui contredisent la barre de plus de 3 % : à vérifier ; d'accord : la barre.
    assert decider(None, None, False, None, None, (600, 400), False, 80.0, 100.0)[2] == "à vérifier"
    assert decider(None, None, False, None, None, (600, 400), False, 100.0, 101.0) == (100.0, 100.0, "barre")
