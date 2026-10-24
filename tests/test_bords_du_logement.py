"""Ce qui dépasse du logement : petits blocs de mur et fenêtres d'angle (étape 5d, vrais plans suisses)."""

from moteur.correcteur import corriger
from tests.test_murs_courts import _lire, _logement, _mur, _ouverture


def test_ressaut_colle_dehors_contre_un_mur_epais():
    """Un bloc de mur (34 cm) dépasse de 26 cm sous la façade, là où elle change d'épaisseur (plan suisse sd-f87bf0bb).

    Trop court pour être lu comme un mur, il était perdu : la profondeur hors tout était lue 4 % trop courte.
    """
    vrai = {
        "schema": "logement/0.1", "projet_id": "RESSAUT", "unites": "m", "hauteur_sous_plafond": 2.5,
        "murs": [
            _mur("Sud1", [-0.17, -0.17], [3.0, -0.17], 0.34),
            _mur("Sud2", [3.0, -0.10], [8.1, -0.10], 0.20),
            _mur("Bloc", [3.0, -0.60], [3.0, -0.10], 0.34),
            _mur("Est", [8.1, -0.10], [8.1, 5.5], 0.20),
            _mur("Nord", [-0.17, 5.5], [8.1, 5.5], 0.20),
            _mur("Ouest", [-0.17, -0.17], [-0.17, 5.5], 0.34),
        ],
        "ouvertures": [], "pieces": [],
    }
    note = corriger(_lire(vrai), vrai)
    assert note.ecart_dimensions <= 0.01, note.remarques
    assert note.murs_trouves == note.murs_vrais and note.murs_inventes == 0, note.remarques


def test_fenetre_d_angle_au_bout_d_un_mur():
    """Le mur nord se prolonge dehors de 1,50 m, dont 1,10 m de fenêtre jusqu'à son bout : il est lu en entier."""
    vrai = _logement()
    d = 0.27 / 2
    vrai["murs"].append(_mur("Avancee", [8 + d, 5.4 + d], [8 + d + 1.5, 5.4 + d], 0.27))
    vrai["ouvertures"].append(_ouverture("F1", "fenetre", "Avancee", 0.4, 1.1))
    note = corriger(_lire(vrai), vrai)
    assert note.ecart_dimensions <= 0.01, note.remarques
    assert note.ouvertures_justes == 2, note.remarques  # la porte de la cloison, et la fenêtre d'angle
