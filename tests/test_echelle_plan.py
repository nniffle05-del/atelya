"""Tests de la lecture de l'échelle d'un plan colorié, sur les cotes de son dessin (moteur/echelle_plan.py)."""

import cv2
import numpy as np
import pytest

from moteur.redressement import estimer_redressement
from tests.test_coloriage import S, coloriage_t2
from tests.test_redressement import COINS, VUS, echelles

pytest.importorskip("rapidocr")

K = 2  # le dessin est deux fois plus grand que le coloriage (comme un plan vu par Atelya en 768 px)


def _cote(img: np.ndarray, p: tuple[int, int], q: tuple[int, int], texte: str) -> None:
    """Une cote comme sur les plans du générateur : trait fin, marques en bout, nombre à côté."""
    cv2.line(img, p, q, 40, 1)
    horizontale = p[1] == q[1]
    for x, y in (p, q):
        if horizontale:
            cv2.line(img, (x, y - 9), (x, y + 9), 40, 1)
        else:
            cv2.line(img, (x - 9, y), (x + 9, y), 40, 1)
        cv2.line(img, (x - 7, y + 7), (x + 7, y - 7), 40, 2)
    (w, h), _ = cv2.getTextSize(texte, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    case = np.full((h + 12, w + 8), 255, np.uint8)
    cv2.putText(case, texte, (4, h + 4), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 40, 2, cv2.LINE_AA)
    if horizontale:
        x0, y0 = (p[0] + q[0]) // 2 - case.shape[1] // 2, p[1] - 14 - case.shape[0]
    else:
        case = cv2.rotate(case, cv2.ROTATE_90_COUNTERCLOCKWISE)
        x0, y0 = p[0] - 14 - case.shape[1], (p[1] + q[1]) // 2 - case.shape[0] // 2
    img[y0:y0 + case.shape[0], x0:x0 + case.shape[1]] = np.minimum(img[y0:y0 + case.shape[0], x0:x0 + case.shape[1]], case)


def dessin_t2() -> np.ndarray:
    """Le dessin du T2 de coloriage_t2 (murs noirs), deux fois plus grand, avec ses cotes intérieures
    6,00 m (en haut) et 4,00 m (à gauche) dessinées dans la marge."""
    c = coloriage_t2()
    g = np.where(c == 1, 30, 255).astype(np.uint8)
    g = cv2.resize(g, None, fx=K, fy=K, interpolation=cv2.INTER_NEAREST)
    x0, x1, y0, y1 = 120 * K, 720 * K, 120 * K, 520 * K  # intérieur du logement, en pixels du dessin
    _cote(g, (x0, 70 * K), (x1, 70 * K), "6,00")
    _cote(g, (70 * K, y0), (70 * K, y1), "4,00")
    return g


def test_plan_a_plat():
    from moteur.echelle_plan import lire_echelle_plan

    e = lire_echelle_plan(dessin_t2(), coloriage_t2())
    assert e.px_par_m == pytest.approx(S, rel=0.01)
    assert e.largeur == e.hauteur
    assert len(e.cotes) == 2


def test_plan_penche():
    """Un scan penché de 3° : on lit les cotes sur le dessin tourné comme le coloriage."""
    from moteur.echelle_plan import lire_echelle_plan

    def tourner(img, fond):
        h, w = img.shape
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 3.0, 1.0)
        return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=fond)

    e = lire_echelle_plan(tourner(dessin_t2(), 255), tourner(coloriage_t2(), 0))
    assert e.px_par_m == pytest.approx(S, rel=0.01)


def test_photo_de_biais_largeur_et_hauteur():
    """Une photo de biais : les cotes, lues après redressement, donnent l'échelle dans chaque sens,
    et donc les vraies proportions du plan (que la photo a écrasées)."""
    from moteur.echelle_plan import lire_echelle_plan

    W = cv2.getPerspectiveTransform(COINS, VUS).astype(np.float64)
    col = cv2.warpPerspective(coloriage_t2(), W, (820, 660), flags=cv2.INTER_NEAREST)
    D = np.diag([K, K, 1.0])
    dessin = cv2.warpPerspective(dessin_t2(), D @ W @ np.linalg.inv(D), (820 * K, 660 * K),
                                 flags=cv2.INTER_LINEAR, borderValue=255)
    r = estimer_redressement(col)
    assert r is not None and r.de_biais
    sx, sy = echelles(r.H @ W, 420, 320)  # pixels redressés par pixel du plan d'origine (S px par m)
    e = lire_echelle_plan(dessin, col, r)
    assert e.largeur == pytest.approx(S * sx, rel=0.02)
    assert e.hauteur == pytest.approx(S * sy, rel=0.02)


def test_plan_sans_cote():
    from moteur.echelle_plan import lire_echelle_plan

    c = coloriage_t2()
    g = cv2.resize(np.where(c == 1, 30, 255).astype(np.uint8), None, fx=K, fy=K, interpolation=cv2.INTER_NEAREST)
    e = lire_echelle_plan(g, c)
    assert e.px_par_m is None and not e.sure


def test_une_echelle_impossible_est_envoyee_a_verifier():
    """Logement de 600 px de large intérieur et cote d'ensemble 6,00 m : 100 px par m."""
    from moteur.echelle_plan import decider

    assert decider(100.0, 100.0, True, 6.0, 4.0, (600, 400), False)[2] == "cotes"
    # « 6,00 » lu, mais une échelle de 150 px par m : le logement ne ferait que 4 m de large.
    assert decider(150.0, 150.0, True, 6.0, 4.0, (600, 400), False) == (None, None, "à vérifier")
    # Échelle trop petite (logement de 12 m) tirée d'une seule cote : à vérifier ; tirée de deux
    # cotes concordantes, on la garde (la cote d'ensemble peut simplement ne pas avoir été lue).
    assert decider(50.0, 50.0, False, 6.0, 4.0, (600, 400), False)[2] == "à vérifier"
    assert decider(50.0, 50.0, True, 6.0, 4.0, (600, 400), False)[2] == "cotes"


def test_secours_par_la_cote_d_ensemble():
    from moteur.echelle_plan import decider

    largeur, hauteur, source = decider(None, None, False, 6.0, 4.0, (601, 399), False)
    assert source == "cote d'ensemble" and largeur == pytest.approx(100, rel=0.01)
    assert decider(None, None, False, 6.0, 3.1, (600, 400), False)[2] == "à vérifier"  # largeur et hauteur en désaccord
    assert decider(None, None, False, 6.0, 4.0, (600, 400), True)[2] == "à vérifier"  # photo : pas de secours


def test_echelle_approchee_par_les_portes():
    """Trois portes de 83 cm et une de 73 cm à 100 px par m, plus un petit morceau de porte (coloriage
    hésitant) : l'échelle approchée est 100 px par m ; sans au moins deux portes, pas d'échelle approchée."""
    from moteur.coloriage import MUR, PORTE
    from moteur.echelle_plan import echelle_par_portes

    col = np.zeros((400, 600), np.uint8)
    col[50:60, 50:550] = MUR
    for x, larg in ((80, 83), (220, 83), (360, 73), (480, 83)):
        col[50:60, x:x + larg] = PORTE
    col[200:210, 100:120] = PORTE  # un bout de porte de 20 px
    assert echelle_par_portes(col) == pytest.approx(100.0, rel=0.01)
    seule = np.zeros((400, 600), np.uint8)
    seule[50:60, 80:163] = PORTE
    assert echelle_par_portes(seule) is None


def test_photocopie_pale_relue_aux_gris_etires():
    """Une photocopie : papier gris (212), encre pâle (180) et un peu floue. Le modèle de lecture n'y voit
    aucun nombre ; relue aux gris étirés (papier blanc, encre noire), elle redonne l'échelle."""
    from moteur.echelle_plan import lire_echelle_plan

    d = dessin_t2().astype(np.float32)
    pale = 180 + (d / 255) * (212 - 180)
    pale = cv2.GaussianBlur(pale, (0, 0), 0.8) + np.random.default_rng(3).normal(0, 3, pale.shape)
    dessin = np.clip(pale, 0, 255).astype(np.uint8)
    e = lire_echelle_plan(dessin, coloriage_t2())
    assert e.sure and e.px_par_m == pytest.approx(S, rel=0.01)
