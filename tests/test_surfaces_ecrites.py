"""Tests de l'échelle lue sur les surfaces écrites dans les pièces (moteur/surfaces_ecrites.py)."""

import numpy as np
import pytest

from moteur.coloriage import bati_du_logement, dehors_du_logement
from moteur.echelle_plan import decider
from moteur.lecture_cotes import TexteLu
from moteur.surfaces_ecrites import SurfaceLue, echelle_par_surfaces, surfaces_dans_textes
from tests.test_coloriage import S, coloriage_t2


def _texte(t: str, x: float = 10, y: float = 10) -> TexteLu:
    return TexteLu(t, np.array([[x - 5, y - 5], [x + 5, y - 5], [x + 5, y + 5], [x - 5, y + 5]], float), 0.9)


def _dedans() -> np.ndarray:
    c = coloriage_t2()
    bati = bati_du_logement(c, S)
    return ~bati & ~dehors_du_logement(bati)


def test_formes_de_surface_reconnues():
    lues = [v for v, _, _ in surfaces_dans_textes([_texte(t) for t in (
        "21,06 m²", "2,10m2", "3,61Lm²", "Plan nº4 — T2 de 45 m²", "2 m", "Hauteur sous plafond : 3,20 m", "4,80", "Chambre")])]
    assert lues == [21.06, 2.10, 3.61]


def test_echelle_donnee_par_deux_pieces_d_accord():
    # Le séjour et la chambre du T2 de test font chacun 2,95 × 4,00 = 11,80 m² (intérieur).
    e = echelle_par_surfaces(_dedans(), [SurfaceLue(11.80, 250, 300), SurfaceLue(11.80, 550, 300)])
    assert e.sure and e.px_par_m == pytest.approx(S, rel=0.01)


def test_une_seule_piece_ou_des_pieces_en_desaccord_ne_suffisent_pas():
    seule = echelle_par_surfaces(_dedans(), [SurfaceLue(11.80, 250, 300)])
    assert seule is not None and not seule.sure  # une seule pièce peut tromper
    desaccord = echelle_par_surfaces(_dedans(), [SurfaceLue(11.80, 250, 300), SurfaceLue(17.80, 550, 300)])
    assert not desaccord.sure  # « 11,80 » lu « 17,80 » : les deux avis s'écartent de 23 %
    dehors = echelle_par_surfaces(_dedans(), [SurfaceLue(11.80, 5, 5)])
    assert dehors is None  # un texte hors du logement (titre, cartouche) ne compte pas


def test_les_cotes_puis_la_barre_passent_avant_les_surfaces():
    interieur = (6.0 * S, 4.0 * S)
    assert decider(S, S, True, 6.0, 4.0, interieur, False, None, 1.05 * S)[2] == "cotes"
    assert decider(None, None, False, None, None, interieur, False, S, 1.02 * S)[2] == "barre"  # d'accord à 3 % près
    assert decider(None, None, False, None, None, interieur, False, None, S) == (S, S, "surfaces")
    # Un logement de 600 m de côté n'est pas vraisemblable : à vérifier.
    assert decider(None, None, False, None, None, interieur, False, None, S / 100)[2] == "à vérifier"


def test_surfaces_lues_sur_un_plan_sans_cotes():
    pytest.importorskip("rapidocr")
    from moteur.echelle_plan import lire_echelle_plan
    from tests.test_barre_echelle import _texte as ecrire

    c = coloriage_t2()
    dessin = np.where(c == 1, 30, 255).astype(np.uint8)
    ecrire(dessin, "11,80 m²", 200, 290)
    ecrire(dessin, "11,80 m²", 500, 290)
    e = lire_echelle_plan(dessin, c)
    assert e.px_par_m is None and e.barre is None  # ni cotes ni barre
    assert e.surfaces_sure and e.surfaces == pytest.approx(S, rel=0.01)
    largeur, hauteur, source = e.decision(de_biais=False)
    assert source == "surfaces" and largeur == hauteur == pytest.approx(S, rel=0.01)


def test_surfaces_controlent_les_cotes_peu_sures_et_pas_sur_une_photo():
    interieur = (6.0 * S, 4.0 * S)
    # Une seule cote lue (peu sûre), contredite de 4 % par les surfaces : un humain tranche.
    assert decider(S, S, False, None, None, interieur, False, None, 1.04 * S)[2] == "à vérifier"
    assert decider(S, S, False, None, None, interieur, False, None, 1.01 * S)[2] == "cotes"
    # Sur une photo de biais, les surfaces ne donnent pas l'échelle.
    assert decider(None, None, False, None, None, interieur, True, None, S)[2] == "à vérifier"


def test_formes_de_surfaces_des_vrais_plans():
    """« (14,13 m2) » (fr-009), « 1,9m2 » (fr-004), « 4,32m × 5,17m » (fr-012 : le produit vaut une surface)."""
    import numpy as np

    from moteur.lecture_cotes import TexteLu
    from moteur.surfaces_ecrites import surfaces_dans_textes

    boite = np.array([[0.0, 0], [10, 0], [10, 5], [0, 5]])
    textes = [TexteLu(t, boite, 1.0) for t in ["(14,13 m2)", "1,9m2", "4,32m × 5,17m", "T2 de 45 m²", "4,80", "2 m"]]
    valeurs = [round(v, 2) for v, _, _ in surfaces_dans_textes(textes)]
    assert valeurs == [14.13, 1.9, 22.33]


def test_surfaces_d_une_legende_ramenees_dans_les_pieces_du_meme_nom():
    """Plan de diagnostiqueur : les surfaces sont listées sous le plan, pas écrites dans les pièces (fr-003, fr-004, fr-017)."""
    import numpy as np

    from moteur.lecture_cotes import TexteLu
    from moteur.surfaces_ecrites import echelle_par_surfaces, surfaces_de_legende

    dedans = np.zeros((600, 800), bool)
    dedans[100:400, 100:500] = True  # 300 × 400 px = 12 m² à 100 px/m
    dedans[100:400, 520:720] = True  # 300 × 200 px = 6 m²
    dedans[420:520, 100:700] = True  # 100 × 600 px = 6 m²

    def texte(t, x, y):
        return TexteLu(t, np.array([[x - 30.0, y - 8], [x + 30, y - 8], [x + 30, y + 8], [x - 30, y + 8]]), 1.0)

    textes = [texte("Séjour", 300, 250), texte("Chambre 1", 620, 250), texte("Chambre 2", 400, 470),
              texte("Superficie loi Carrez totale : 24,00 m²", 300, 560),
              texte("Séjour 12,00 m²", 200, 580), texte("Chambre 2", 180, 595), texte("6,00 m²", 320, 595),
              texte("Chambre 1 : 6,00 m²", 500, 580), texte("Cuisine 9,00 m²", 650, 580)]  # pas de cuisine sur le plan
    lues = surfaces_de_legende(textes, lambda x, y: (x, y), dedans)
    assert sorted(round(s.valeur, 2) for s in lues) == [6.0, 6.0, 12.0]
    e = echelle_par_surfaces(dedans, lues)
    assert e.sure and abs(e.px_par_m - 100) / 100 < 0.01
