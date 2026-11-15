"""Les photos du client à l'écran de vérification (moteur/photos_verification.py) : questions à poser, réponses à ranger."""
import numpy as np
import pytest

from moteur import photos_verification as pv
from moteur.images import ecrire_image


def _fiche():
    cam = lambda x, y, cap: {"x": x, "y": y, "z": 1.3, "cap": cap, "tangage": 0.0, "f": 500.0, "u0": 300.0, "v0": 200.0}
    return {"photos": "photos", "fichier": "{nom}.jpg", "cameras": {"photo-01": {"camera": cam(2, 2, 0), "piece": "sejour_1"}},
            "incertaines": {"photo-02": {"camera": cam(7, 2, 90), "piece": "chambre_1", "hesite_avec": ["chambre_2"]},
                            "photo-04": {"camera": cam(3, 3, 10), "piece": "sejour_1"}},
            "a_verifier": {"photo-03": {"camera": cam(1, 5, 180), "piece": "cuisine_1", "a_verifier": "les meubles vus ne vont pas"}},
            "non_calees": {"photo-05": "trop peu de murs visibles"},
            "a_pointer": {"photo-04": "Atelya n'est pas sûr de la pièce.", "photo-03": "Pièce donnée : cuisine_1, mais…",
                          "photo-02": "Atelya hésite entre chambre_1 et chambre_2.", "photo-05": "Atelya n'a pas pu placer cette photo."}}


def test_questions_pour_l_ecran(tmp_path):
    for i in range(1, 6):
        ecrire_image(tmp_path / f"photo-0{i}.jpg", np.full((400, 2000, 3), 40 * i, np.uint8))
    q = pv.questions_pour_l_ecran(_fiche(), tmp_path, largeur=500)["questions"]
    assert [x["nom"] for x in q] == ["photo-02", "photo-03", "photo-04", "photo-05"]  # hésitations, puis doutes, puis le reste
    assert all(x["image"].startswith("data:image/jpeg;base64,") and x["largeur"] == 500 and x["hauteur"] == 100 for x in q)
    assert q[0]["hesite_avec"] == ["chambre_2"] and q[0]["proposition"] == {"x": 7, "y": 2, "cap": 90}
    assert q[3]["proposition"] is None and q[3]["piece"] is None                      # photo non placée : rien à proposer
    assert "photo-01" not in [x["nom"] for x in q]                                    # une photo sûre n'est pas redemandée


def test_questions_avec_les_noms_affiches_a_l_ecran():
    logement = {"pieces": [{"id": "chambre_1", "nom": "Chambre 2"}, {"id": "chambre_10", "nom": "Bureau"}, {"id": "sejour_1", "nom": "Séjour"}, {"id": "wc_1"}]}
    t = pv.avec_les_noms("Atelya hésite entre chambre_1 et chambre_10 (pas sejour_1, ni wc_1).", logement)
    assert t == "Atelya hésite entre « Chambre 2 » et « Bureau » (pas « Séjour », ni wc_1)."
    assert pv.avec_les_noms("chambre_1", None) == "chambre_1"


def test_photo_absente_arrete_tout(tmp_path):
    with pytest.raises(FileNotFoundError):
        pv.questions_pour_l_ecran(_fiche(), tmp_path)


def test_ranger_les_reponses():
    client = {"photo-02": "chambre", "photo-03": "cuisine"}
    d = pv.ranger_les_reponses(client, {"endroits": {"photo-02": [7.123456, 2.0, 91.26], "photo-05": [1, 1]}, "passees": ["photo-03"]})
    assert d["pieces"] == client and d["endroits"] == {"photo-02": [7.123, 2.0, 91.26], "photo-05": [1.0, 1.0]}
    d2 = pv.ranger_les_reponses(d, {"endroits": {"photo-02": [6.0, 2.5, 80]}})         # un nouvel endroit remplace l'ancien
    assert d2["endroits"]["photo-02"] == [6.0, 2.5, 80.0] and d2["endroits"]["photo-05"] == [1.0, 1.0] and d2["pieces"] == client
    assert pv.ranger_les_reponses(None, None) == {"pieces": {}}
    with pytest.raises(ValueError):
        pv.ranger_les_reponses(client, {"endroits": {"photo-02": [7.0]}})
