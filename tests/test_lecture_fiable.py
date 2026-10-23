"""Tests des corrections de la lecture des plans (fil « Lecture des plans fiable »).

Chaque plan témoin est fabriqué (étape 5b) puis lu et noté (étape 5a) ; il
illustre une faiblesse corrigée :
- graine 3 : la lecture plantait (« truth value of an array ») ;
- graine 9 : logement en L, dont un mur extérieur se prolonge par une cloison de 7 cm ;
- graine 24 : portes percées tout près du bout d'une cloison ;
- graine 199 : porte-fenêtre à deux battants.
"""

import numpy as np
import pytest

from moteur.banc_essai import essayer
from moteur.fabrique import fabriquer_dossier
from moteur.lecture_pieces import nom_propre
from moteur.lecture_plan import _morceaux_d_epaisseur_constante

pytest.importorskip("rapidocr")


@pytest.mark.parametrize("graine", [3, 9, 24, 199])
def test_plans_temoins_verts(graine, tmp_path):
    fabriquer_dossier(graine, tmp_path)
    resultat = essayer(tmp_path / "plan.png", tmp_path / "logement.json")
    assert resultat.note is not None, resultat.echec
    note = resultat.note
    assert note.murs_justes == note.murs_vrais, note.remarques
    assert note.ouvertures_justes == note.ouvertures_vraies, note.remarques
    assert note.pieces_justes == note.pieces_vraies, note.remarques
    assert note.vert


def test_mur_qui_change_d_epaisseur_coupe_en_deux():
    # Un mur de 20 px d'épaisseur sur 100 px, prolongé par une cloison de 7 px
    # posée contre sa face du haut (comme dans un logement en L).
    trait = np.zeros((20, 200), bool)
    trait[:, :100] = True
    trait[:7, 100:] = True
    morceaux = _morceaux_d_epaisseur_constante(trait, px_par_m=100)
    assert morceaux == [(0, 100, 0, 20), (100, 200, 0, 7)]


def test_petite_bavure_ignoree():
    trait = np.zeros((20, 200), bool)
    trait[:, :] = True
    trait[18:, 50:53] = False  # un défaut de 3 px : pas un changement d'épaisseur
    assert _morceaux_d_epaisseur_constante(trait, px_par_m=100) == [(0, 200, 0, 20)]


@pytest.mark.parametrize(
    "lu, attendu",
    [
        ("Saile d'eau", "Salle d'eau"),
        ("Salle d’eau", "Salle d'eau"),
        ("Salle/de bains", "Salle de bains"),
        ("Séjour7 cuisine", "Séjour + cuisine"),
        ("\\Entrée", "Entrée"),
        ("Chambre 2", "Chambre 2"),
        ("Chambre parentale", "Chambre parentale"),  # un nom inhabituel est gardé tel quel
    ],
)
def test_nom_de_piece_nettoye(lu, attendu):
    assert nom_propre(lu) == attendu
