"""Étape 6-19 : les styles du monde (--styles-monde) changent le dessin, jamais la vérité."""
import random

import numpy as np

from moteur.generateur.exportateur import Options, style_pour
from moteur.generateur.logements import generer
from moteur.generateur.reglages import Reglages
from moteur.generateur.rendu import rendre
from moteur.generateur.variete import SOLS, Variete, variete_au_hasard


def _rendus(graine: int):
    log = generer(graine, Reglages())
    sans = style_pour(graine, 0, Options(dossier=None))
    avec = style_pour(graine, 0, Options(dossier=None, styles_monde=True))
    return rendre(log, log.niveaux[0], sans), rendre(log, log.niveaux[0], avec), sans, avec


def test_sans_option_rien_ne_change():
    assert style_pour(60001, 0, Options(dossier=None)).variete is None


def test_la_verite_ne_bouge_pas():
    for graine in (60001, 60002, 60005, 60013):
        r1, r2, _, avec = _rendus(graine)
        assert avec.variete is not None
        for nom in ("masque_semantique", "masque_pieces", "masque_elements", "hauteur"):
            assert np.array_equal(r1.images[nom], r2.images[nom]), (graine, nom)
        assert r1.images["plan"].shape == r2.images["plan"].shape


def test_le_dessin_change():
    r1, r2, _, _ = _rendus(60003)
    assert not np.array_equal(r1.images["plan"], r2.images["plan"])


def test_tirages_varies():
    vs = [variete_au_hasard(random.Random(k)) for k in range(400)]
    assert {v.murs for v in vs} == {"plein", "trait", "double", "gris_clair", "hachure", "couleur"}
    assert {m for v in vs for m in v.sols.values()} == set(SOLS)
    for attribut in ("lettres", "capture", "absurde", "symboles_neuf", "arcs_pointilles"):
        assert 0 < sum(getattr(v, attribut) for v in vs) < 400, attribut
    assert isinstance(vs[0], Variete)
