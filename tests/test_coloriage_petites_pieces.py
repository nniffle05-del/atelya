"""Tests des corrections 0.3 du traducteur : ouvertures trop épaisses, cloisons oubliées."""

import numpy as np
import pytest

from moteur.coloriage import MUR, PORTE_FENETRE, fusionner_coloriages, lire_coloriage

S = 100  # pixels par mètre


def px(m: float) -> int:
    return int(round(m * S))


def coloriage_t1(pieces: list[tuple[float, float, float, float, int]]) -> np.ndarray:
    """Un logement de 5,00 × 4,00 m (murs de 20 cm), puis des pièces en mètres (x0, y0, x1, y1, classe)."""
    c = np.zeros((px(6.4), px(7.4)), np.uint8)
    o = (px(1), px(1))

    def rect(x0, y0, x1, y1, v):
        c[o[1] + px(4.2 - y1):o[1] + px(4.2 - y0), o[0] + px(x0 + 0.2):o[0] + px(x1 + 0.2)] = v

    rect(-0.2, -0.2, 5.2, 4.2, MUR)
    for x0, y0, x1, y1, v in pieces:
        rect(x0, y0, x1, y1, v)
    return c, rect


def test_porte_fenetre_plus_epaisse_que_le_mur():
    c, rect = coloriage_t1([(0, 0, 5, 4, 5)])
    # Porte-fenêtre de 2,40 m dans le mur ouest, coloriée débordante et ondulée comme le fait Atelya.
    rect(-0.26, 0.5, -0.2, 2.9, PORTE_FENETRE)
    rect(-0.2, 0.5, 0, 2.9, PORTE_FENETRE)
    rect(0, 0.5, 0.05, 1.7, PORTE_FENETRE)
    log, _ = lire_coloriage(c, S)
    pf = [o for o in log["ouvertures"] if o["type"] == "porte_fenetre"]
    assert len(pf) == 1
    assert pf[0]["largeur"] == pytest.approx(2.4, abs=0.03)
    assert pf[0]["position"] == pytest.approx(0.5 + 0.1, abs=0.03)  # mesuré depuis l'axe du mur sud
    ouest = next(m for m in log["murs"] if m["id"] == pf[0]["mur"])
    assert ouest["epaisseur"] == pytest.approx(0.2, abs=0.01)
    assert abs(ouest["fin"][1] - ouest["debut"][1]) == pytest.approx(4.2, abs=0.03)  # un seul mur, d'un coin à l'autre


def test_cloison_oubliee_entre_wc_et_placard():
    # WC (1,0 × 1,4 m) et placard (1,0 × 1,0 m) l'un au-dessus de l'autre : la cloison qui les sépare
    # n'a pas été coloriée. Les deux couleurs suffisent à les séparer.
    c, rect = coloriage_t1([(0, 0, 3.9, 4, 5), (4, 0, 5, 1.4, 9), (4, 1.4, 5, 2.4, 12), (4, 2.5, 5, 4, 7)])
    rect(3.9, 0, 4, 4, MUR)
    rect(4, 2.4, 5, 2.5, MUR)
    log, details = lire_coloriage(c, S)
    types = sorted(details["types_pieces"].values())
    assert types == ["chambre", "placard", "sejour", "wc"]
    wc = next(p for p in log["pieces"] if details["types_pieces"][p["id"]] == "wc")
    ys = [p[1] for p in wc["contour"]]
    assert max(ys) - min(ys) == pytest.approx(1.4, abs=0.08)


def test_petite_tache_ne_coupe_pas_une_grande_piece():
    c, rect = coloriage_t1([(0, 0, 5, 4, 5), (1, 1, 1.5, 1.5, 6)])  # 0,25 m² de « cuisine » dans le séjour
    _, details = lire_coloriage(c, S)
    assert list(details["types_pieces"].values()) == ["sejour"]


def test_duo_garde_le_bati_et_prend_le_type_des_pieces():
    murs = np.array([[0, 1, 5, 5], [2, 1, 12, 12]], np.uint8)  # essai 2 : fond, mur, porte, séjour, placard
    pieces = np.array([[7, 5, 6, 0], [9, 9, 9, 1]], np.uint8)  # essai 3 : voit d'autres choses
    duo = fusionner_coloriages(murs, pieces)
    # Fond, murs et porte restent ceux de l'essai 2 ; une pièce vue par les deux prend le type de l'essai 3 ;
    # une pièce que l'essai 3 prend pour du fond ou un mur garde le type de l'essai 2.
    assert duo.tolist() == [[0, 1, 6, 5], [2, 1, 9, 12]]
    with pytest.raises(ValueError):
        fusionner_coloriages(murs, pieces[:, :3])
