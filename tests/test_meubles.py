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


def _glb_rouge(chemin):
    """Un modèle .glb minuscule : une matière dont la texture de couleur est une image rouge 4 × 4."""
    import json as _json
    import struct

    import cv2
    import numpy as np
    ok, png = cv2.imencode(".png", np.dstack([np.zeros((4, 4)), np.zeros((4, 4)), np.full((4, 4), 200)]).astype(np.uint8))
    binaire = png.tobytes() + b"\0" * (-len(png.tobytes()) % 4)
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binaire)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(png.tobytes())}],
           "images": [{"bufferView": 0, "mimeType": "image/png"}], "textures": [{"source": 0}],
           "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}]}
    j = _json.dumps(doc).encode()
    j += b" " * (-len(j) % 4)
    contenu = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(j) + 8 + len(binaire))
    contenu += struct.pack("<I4s", len(j), b"JSON") + j + struct.pack("<I4s", len(binaire), b"BIN\0") + binaire
    chemin.write_bytes(contenu)


def test_vraie_couleur_d_un_modele_et_choix_par_elle(tmp_path):
    from moteur.meubles import couleur_texture
    (tmp_path / "R").mkdir()
    _glb_rouge(tmp_path / "R" / "ROUGE.glb")
    assert couleur_texture(tmp_path / "R" / "ROUGE.glb") == (200, 0, 0)
    # le catalogue dit « White » mais la texture est rouge : avec la bibliothèque, la vraie couleur l'emporte
    liste = [{"id": "ROUGE", "product_type": "sofa", "name": "Sofa", "color": "White", "size_metres": [2.0, 0.85, 0.9]},
             {"id": "AUTRE", "product_type": "sofa", "name": "Sofa", "color": "Red", "size_metres": [2.0, 0.85, 0.9]}]
    memoire = {"AUTRE": [240, 240, 240]}
    assert choisir("canape", [2.0, 0.9, 0.85], (200, 0, 0), liste, bibliotheque=tmp_path, memoire=memoire)["id"] == "ROUGE"
    assert memoire["ROUGE"] == [200, 0, 0]


def test_meubler_ajoute_meubles_et_rideaux():
    from outils.habillage.meubler import meubler
    logement = {**LOGEMENT, "ouvertures": [{"id": "F1", "type": "fenetre", "mur": "M1", "position": 1.0, "largeur": 1.0,
                                            "hauteur": 1.2, "allege": 0.9, "statut": "mesure", "source": "t"}]}
    meubles = {"meubles": [{"id": "canape", "categorie": "canape", "position": [1, 1], "dimensions": [2, 0.9, 0.8],
                            "statut": "estime", "source": "t"}],
               "rideaux": {"F1": {"voilage": [245, 245, 245], "rideaux": None, "statut": "estime", "source": "t"}}}
    sortie = meubler(logement, meubles)
    assert sortie["ouvertures"][0]["rideaux"]["voilage"] == [245, 245, 245] and len(sortie["meubles"]) == 1
    with pytest.raises(KeyError):
        meubler(logement, {"rideaux": {"F9": meubles["rideaux"]["F1"]}})


def test_rideaux_poses_cote_interieur_sous_le_plafond():
    from moteur.habillage import rideaux_du_plan
    logement = Logement.model_validate({**LOGEMENT, "ouvertures": [
        {"id": "F1", "type": "porte_fenetre", "mur": "M1", "position": 1.0, "largeur": 1.2, "hauteur": 2.1, "allege": 0,
         "statut": "mesure", "source": "t", "rideaux": {"voilage": [245, 245, 245], "statut": "estime", "source": "t"}}]})
    (r,) = rideaux_du_plan(logement)
    assert r["centre"] == pytest.approx([1.6, 0.1]) and r["normale_deg"] == pytest.approx(90.0)  # mur sud, pièce au nord
    assert r["z_tringle"] == pytest.approx(2.4) and r["rideaux"] is None  # 30 cm au-dessus de la fenêtre (plafond bas)
