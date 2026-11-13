"""OWLv2 réécrit dans Atelya (moteur/owlv2.py, 10/11/2026). Les tests qui demandent les poids (620 Mo, sur le PC) sont sautés
ailleurs. Contrôle de référence fait le 10/11/2026 sur l'image d'exemple officielle (deux chats) : notes 0,614 et 0,665 comme
l'implémentation de référence, rectangles à 0,1 pixel près."""
import numpy as np
import pytest

from moteur.owlv2 import boites_iou, dossier_poids, objets, preparer

AVEC_POIDS = (dossier_poids() / "model.safetensors").is_file()


def test_preparer_remet_au_carre_avec_du_gris():
    photo = np.zeros((480, 960, 3), np.uint8)
    x = preparer(photo)
    assert tuple(x.shape) == (1, 3, 960, 960)
    gris = (0.5 - np.array([0.48145466, 0.4578275, 0.40821073])) / np.array([0.26862954, 0.26130258, 0.27577711])
    assert x[0, :, 900, 10].numpy() == pytest.approx(gris, abs=1e-4)  # bas : rempli de gris
    assert x[0, 0, 10, 10].item() == pytest.approx(-0.48145466 / 0.26862954, abs=1e-4)  # haut : la photo (noire)


def test_objets_garde_le_mieux_note_entre_deux_rectangles_qui_se_recouvrent():
    sortie = {"notes": np.array([[0.9, 0.1], [0.5, 0.6], [0.05, 0.1], [0.3, 0.2]]), "taille": (100, 200),
              "boites": np.array([[10, 10, 50, 50], [12, 12, 52, 52], [0, 0, 5, 5], [100, 10, 150, 90]], float)}
    o = objets(sortie, ["lit", "table"], seuil=0.2)
    assert [(x["nom"], x["carre"]) for x in o] == [("lit", 0), ("lit", 3)]
    assert boites_iou(sortie["boites"][:1], sortie["boites"][1:2])[0, 0] > 0.8


@pytest.mark.skipif(not AVEC_POIDS, reason="poids d'OWLv2 absents (sur le PC seulement)")
def test_mots_comme_clip():
    from moteur.owlv2 import Mots
    m = Mots(dossier_poids())
    assert m.numeros("a photo of a cat")[:7] == [49406, 320, 1125, 539, 320, 2368, 49407]
    assert len(m.numeros("a bed with a duvet")) == 16
