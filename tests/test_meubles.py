"""B4 : catalogue des meubles, choix du modèle ABO, format du logement (moteur/meubles.py, moteur/logement.py)."""
import pytest

from moteur.logement import Logement
from moteur.meubles import CATEGORIES, SUR_MESURE, candidats, choisir, couleur_abo

LISTE = [
    {"id": "S1", "product_type": "sofa", "name": "Modern Sofa, grey", "color": "Grey", "size_metres": [2.2, 0.85, 0.95]},
    {"id": "S2", "product_type": "sofa", "name": "Small Sofa", "color": "Yellow", "size_metres": [1.5, 0.8, 0.85]},
    {"id": "S3", "product_type": "sofa", "name": "Sleeper Sofa bed", "color": "Grey", "size_metres": [2.2, 0.85, 0.95]},
    {"id": "C1", "product_type": "chair", "name": "Dining Chair", "color": "Silver", "size_metres": [0.5, 0.85, 0.55]},
    {"id": "C2", "product_type": "chair", "name": "Office Desk Chair", "color": "Black", "size_metres": [0.6, 1.0, 0.6]},
    {"id": "A1", "product_type": "chair", "name": "Accent Chair", "color": "Mustard", "size_metres": [0.7, 0.85, 0.8]},
]


def test_categories_coherentes():
    assert {"cuisine", "ilot", "caisson"} & set(CATEGORIES) == {"ilot", "caisson"}
    assert SUR_MESURE >= {"ilot", "meuble_cuisine_bas", "placard", "television"}
    assert all(CATEGORIES[c][1] is None for c in SUR_MESURE)


def test_candidats_par_type_mots_et_exclusions():
    assert [e["id"] for e in candidats("canape", LISTE)] == ["S1", "S2"]  # le canapé-lit est écarté
    assert [e["id"] for e in candidats("chaise", LISTE)] == ["C1"]
    assert [e["id"] for e in candidats("fauteuil", LISTE)] == ["A1"]
    assert candidats("ilot", LISTE) == []


def test_choisir_par_dimensions_puis_couleur():
    assert choisir("canape", [2.3, 0.95, 0.85], (180, 180, 180), LISTE)["id"] == "S1"
    assert choisir("canape", [1.5, 0.85, 0.8], (220, 180, 50), LISTE)["id"] == "S2"
    assert choisir("canape", [2.3, 0.95, 0.85], None, LISTE, exclure={"S1"})["id"] == "S2"
    assert couleur_abo("Pastel Yellow") == couleur_abo("yellow")
    assert couleur_abo("Sonoma Oak/White")[0] > 150


LOGEMENT = {
    "schema": "logement/0.1", "projet_id": "t", "hauteur_sous_plafond": 2.5,
    "murs": [{"id": "M1", "debut": [0, 0], "fin": [4, 0], "epaisseur": 0.2, "statut": "mesure", "source": "t"}],
    "pieces": [{"id": "sejour", "nom": "Séjour", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]], "statut": "mesure", "source": "t"}],
}


def test_un_meuble_dans_le_logement():
    meuble = {"id": "canape", "categorie": "canape", "piece": "sejour", "position": [1, 1], "face": 90,
              "dimensions": [2.2, 0.9, 0.85], "couleur": [180, 180, 180], "statut": "estime", "source": "photo 01"}
    log = Logement.model_validate({**LOGEMENT, "meubles": [meuble]})
    assert log.meubles[0].dimensions == (2.2, 0.9, 0.85)
    with pytest.raises(ValueError, match="pièce inconnue"):
        Logement.model_validate({**LOGEMENT, "meubles": [{**meuble, "piece": "cuisine"}]})
    with pytest.raises(ValueError, match="dépasse le plafond"):
        Logement.model_validate({**LOGEMENT, "meubles": [{**meuble, "altitude": 2.0}]})
    with pytest.raises(ValueError, match="en double"):
        Logement.model_validate({**LOGEMENT, "meubles": [{**meuble, "id": "sejour"}]})
