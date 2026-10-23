"""Tests du fichier « à vérifier » : la lecture automatique, préparée pour la page de saisie (étape 3e)."""

import base64
import json

import cv2
import numpy as np
import pytest

from moteur.lecture_plan import lire_plan, proposition_a_verifier
from test_lecture_plan import _plan

pytest.importorskip("rapidocr")


def _plan_douteux():
    """Le plan d'exercice, abîmé exprès à trois endroits."""
    image = _plan().copy()
    cv2.rectangle(image, (812, 196), (908, 224), 255, -1)  # les traits de la fenêtre de la chambre
    cv2.rectangle(image, (1130, 322), (1395, 356), 255, -1)  # la ligne « Hauteur sous plafond »
    cv2.rectangle(image, (800, 354), (910, 385), 255, -1)  # le nom « Chambre »
    return image


def test_proposition_complete():
    proposition = proposition_a_verifier(lire_plan(_plan()), "LU", "plan.png")
    texte = json.dumps(proposition)  # doit pouvoir s'écrire en JSON
    assert proposition["version"] == "saisie/0.2"
    assert (len(proposition["murs"]), len(proposition["ouvertures"]), len(proposition["pieces"])) == (7, 7, 4)
    assert proposition["echelle"]["sure"] and proposition["hsp_lue"]
    assert proposition["echelle"]["p1"] == [210.0, 145.0]  # la cote 8,00
    assert all(o["sure"] for o in proposition["ouvertures"])
    assert all(p["nom"] and p["accord"] for p in proposition["pieces"])
    # L'image jointe est le plan redressé : les pixels des murs y correspondent.
    png = base64.b64decode(proposition["image"]["dataUrl"].split(",", 1)[1])
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image.shape == _plan().shape
    assert len(texte) < 2_000_000


def test_les_doutes_sont_signales():
    proposition = proposition_a_verifier(lire_plan(_plan_douteux()), "LU", "plan.png")
    assert not proposition["hsp_lue"]
    douteuses = [o for o in proposition["ouvertures"] if not o["sure"]]
    assert len(douteuses) == 1  # la fenêtre effacée : un trou sans dessin
    assert [p["nom"] for p in proposition["pieces"]].count("") == 1  # la chambre sans nom
