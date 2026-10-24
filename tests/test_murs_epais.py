"""Murs extérieurs très épais (40 à 55 cm, courants avec l'isolation) : la lecture doit les garder (étape 5d)."""

import pytest

from moteur.correcteur import corriger
from moteur.dessin_plan import Style, dessiner_plan


def _logement(ep: float) -> dict:
    """Un T2 de 8,00 × 5,40 m intérieur, murs extérieurs d'épaisseur ep, une cloison de 10 cm."""
    d = ep / 2

    def mur(id_, a, b, e):
        return {"id": id_, "debut": a, "fin": b, "epaisseur": e, "statut": "mesure", "source": "test"}

    return {
        "schema": "logement/0.1", "projet_id": "MURS-EPAIS", "unites": "m", "hauteur_sous_plafond": 2.5,
        "murs": [
            mur("M_sud", [-d, -d], [8 + d, -d], ep),
            mur("M_est", [8 + d, -d], [8 + d, 5.4 + d], ep),
            mur("M_nord", [-d, 5.4 + d], [8 + d, 5.4 + d], ep),
            mur("M_ouest", [-d, -d], [-d, 5.4 + d], ep),
            mur("C1", [4.85, 0.0], [4.85, 5.4], 0.10),
        ],
        "ouvertures": [
            {"id": "P1", "type": "porte", "mur": "C1", "position": 2.0, "largeur": 0.8, "hauteur": 2.04,
             "allege": 0, "statut": "mesure", "source": "test"},
        ],
        "pieces": [
            {"id": "s", "nom": "Séjour", "contour": [[0, 0], [4.8, 0], [4.8, 5.4], [0, 5.4]], "surface": 25.92,
             "statut": "mesure", "source": "test"},
            {"id": "c", "nom": "Chambre", "contour": [[4.9, 0], [8, 0], [8, 5.4], [4.9, 5.4]], "surface": 16.74,
             "statut": "mesure", "source": "test"},
        ],
    }


@pytest.mark.parametrize("epaisseur", [0.20, 0.45, 0.55])
def test_murs_exterieurs_epais_lus(epaisseur):
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    vrai = _logement(epaisseur)
    image = dessiner_plan(vrai, Style(px_par_m=100))
    lu = logement_depuis_plan(lire_plan(image, px_par_m=100), "TEST")
    note = corriger(lu, vrai)
    assert note.murs_trouves == note.murs_vrais, note.remarques
    assert note.ecart_dimensions <= 0.01, note.remarques
    assert note.pieces_trouvees == 2, note.remarques


def test_grande_baie_dans_un_mur_epais():
    """Une baie de 3,20 m dans un mur de 45 cm : le mur reste entier, la baie est une fenêtre."""
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    vrai = _logement(0.45)
    vrai["ouvertures"].append(
        {"id": "F1", "type": "fenetre", "mur": "M_sud", "position": 0.8, "largeur": 3.2, "hauteur": 1.35,
         "allege": 0.95, "statut": "mesure", "source": "test"})
    image = dessiner_plan(vrai, Style(px_par_m=100))
    lu = logement_depuis_plan(lire_plan(image, px_par_m=100), "TEST")
    note = corriger(lu, vrai)
    assert note.murs_trouves == note.murs_vrais and note.murs_inventes == 0, note.remarques
    assert note.ouvertures_justes == 2, note.remarques
    assert note.ecart_dimensions <= 0.01, note.remarques


def test_poteau_contre_le_mur_du_bas_ne_decale_pas_le_logement():
    """Un poteau plus épais que le mur extérieur, collé dessous : l'origine reste le coin intérieur."""
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    vrai = _logement(0.30)
    vrai["murs"].append({"id": "Poteau", "debut": [2.0, -0.05], "fin": [2.6, -0.05], "epaisseur": 0.50,
                         "statut": "mesure", "source": "test"})
    image = dessiner_plan(vrai, Style(px_par_m=100))
    lu = logement_depuis_plan(lire_plan(image, px_par_m=100), "TEST")
    note = corriger(lu, vrai)
    assert note.murs_justes >= note.murs_vrais - 1, note.remarques  # le poteau lui-même peut être imprécis


def test_placard_relie_par_une_porte_garde():
    """Un placard dont les cloisons ne touchent aucun mur (relié au reste par le passage) est gardé."""
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    vrai = _logement(0.20)

    def cloison(id_, a, b):
        return {"id": id_, "debut": a, "fin": b, "epaisseur": 0.10, "statut": "mesure", "source": "test"}

    vrai["murs"] += [
        cloison("K_sud", [1.0, 3.0], [2.6, 3.0]),
        cloison("K_nord", [1.0, 4.4], [2.6, 4.4]),
        cloison("K_ouest", [1.0, 3.0], [1.0, 4.4]),
        cloison("K_est", [2.6, 3.0], [2.6, 4.4]),
    ]
    vrai["ouvertures"].append({"id": "P2", "type": "porte", "mur": "K_sud", "position": 0.4, "largeur": 0.8,
                               "hauteur": 2.04, "allege": 0, "statut": "mesure", "source": "test"})
    image = dessiner_plan(vrai, Style(px_par_m=100))
    lu = logement_depuis_plan(lire_plan(image, px_par_m=100), "TEST")
    note = corriger(lu, vrai)
    assert note.murs_justes == note.murs_vrais, note.remarques
