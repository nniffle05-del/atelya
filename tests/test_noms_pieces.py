"""Tests de la lecture des noms de pièces (moteur/noms_pieces.py) et de leur effet sur le traducteur."""

import numpy as np
import pytest

from moteur.coloriage import MUR, lire_coloriage
from moteur.noms_pieces import NomLu, noms_depuis_textes, type_depuis_nom


@pytest.mark.parametrize("texte, attendu", [
    ("WC", "wc"), ("W.C.", "wc"), ("Toilettes", "wc"),
    ("Placard", "placard"), ("Rangement", "placard"), ("Dressing", "placard"), ("Rgt", "placard"),
    ("Buanderie", "buanderie"), ("Lingerie", "buanderie"),
    ("Chambre 2", "chambre"), ("Ch. 1", "chambre"), ("Chambre / bureau", "bureau"), ("Bureau", "bureau"),
    ("Séjour / cuisine", "sejour"), ("Salon-cuisine", "sejour"), ("Pièce de vie", "sejour"),
    ("Cuisine", "cuisine"), ("Salle de bains", "salle_d_eau"), ("Salle d'eau 1", "salle_d_eau"),
    ("SdB", "salle_d_eau"), ("Entrée", "entree"), ("Hall", "entree"),
    ("Dégagement", "degagement"), ("Dgt", "degagement"), ("Couloir", "degagement"),
    ("Escalier", "escalier"), ("Esc.", "escalier"),
])
def test_noms_reconnus(texte, attendu):
    assert type_depuis_nom(texte) == attendu


@pytest.mark.parametrize("texte", ["Cellier", "12,40 m²", "3,20", "N", "Cotes intérieures, en mètres",
                                   "Plan n°407 — T3 de 90 m²", "Hauteur sous plafond : 2,50 m", "X", ""])
def test_textes_qui_ne_sont_pas_des_noms(texte):
    assert type_depuis_nom(texte) is None


def test_texte_mal_lu_ignore():
    noms = noms_depuis_textes([("WC", 10, 10, 0.95), ("Placard", 50, 50, 0.3)])
    assert [n.type for n in noms] == ["wc"]


def test_le_nom_l_emporte_sur_la_couleur():
    S = 100
    c = np.zeros((520, 620), np.uint8)
    c[50:470, 50:570] = MUR
    c[70:450, 70:300] = 5  # séjour
    c[70:450, 310:550] = 12  # colorié « placard » par erreur…
    c[70:450, 300:310] = MUR
    _, details = lire_coloriage(c, S, noms=[NomLu("wc", 430, 260, "WC")])  # … mais le plan écrit « WC »
    assert sorted(details["types_pieces"].values()) == ["sejour", "wc"]
    assert len(details["pieces_nom_lu"]) == 1
