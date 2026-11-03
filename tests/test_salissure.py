"""Tests des plans salis et du nettoyage de l'image avant lecture (étape 5c)."""

import random
from pathlib import Path

import cv2
from moteur.images import ecrire_image, lire_image
import numpy as np
import pytest

from moteur.banc_essai import essayer, famille
from moteur.fabrique import fabriquer_dossier
from moteur.lecture_cotes import TexteLu, lire_epaisseurs
from moteur.nettoyage import nettoyer
from moteur.salissure import FAMILLES, salir, salir_dossier

PLAN = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "plan.png"


def _plan():
    return lire_image(str(PLAN), cv2.IMREAD_GRAYSCALE)


@pytest.mark.parametrize("nom", FAMILLES)
def test_salissure_reproductible(nom):
    a = salir(_plan(), nom, random.Random("graine"))
    b = salir(_plan(), nom, random.Random("graine"))
    c = salir(_plan(), nom, random.Random("autre graine"))
    assert np.array_equal(a, b)  # même graine, même salissure
    assert not np.array_equal(a, c)
    assert a.dtype == np.uint8


def test_salissure_inconnue():
    with pytest.raises(ValueError):
        salir(_plan(), "boue", random.Random(1))


def test_photo_de_telephone():
    photo = salir(_plan(), "telephone", random.Random(1))
    assert photo.ndim == 3  # une photo est en couleurs
    assert photo.shape[0] > _plan().shape[0] and photo.shape[1] > _plan().shape[1]  # la table autour


def test_salir_dossier(tmp_path):
    ecrire_image(str(tmp_path / "plan.png"), _plan())
    ecrits = salir_dossier(tmp_path)
    assert sorted(p.name for p in ecrits) == sorted(
        ["plan-travers.png", "plan-photocopie.png", "plan-taches.png", "plan-compression.jpg", "plan-telephone.jpg"]
    )
    assert all(lire_image(str(p)) is not None for p in ecrits)


def test_famille_d_apres_le_nom():
    assert famille(Path("plan.png")) == "propre"
    assert famille(Path("plan-telephone.jpg")) == "telephone"
    assert famille(Path("plan-douteux.png")) == "douteux"


def test_nettoyage_ne_touche_pas_un_plan_propre():
    propre, fait = nettoyer(_plan())
    assert not fait.feuille_detouree and not fait.fond_egalise
    # Le papier reste blanc ; seuls les traits gris (murs à 40 sur ce plan) sont foncés jusqu'au noir.
    papier = _plan() == 255
    assert (propre[papier] == 255).all()
    assert (propre <= _plan()).all()


def test_nettoyage_d_une_photocopie():
    copie = salir(_plan(), "photocopie", random.Random(1))
    assert np.percentile(copie, 0.5) > 30  # les traits sont devenus gris
    propre, fait = nettoyer(copie)
    assert fait.contraste_rendu
    assert np.percentile(propre, 0.5) < 10  # ils redeviennent noirs
    assert np.percentile(propre, 60) > 245  # et le papier blanc


def test_nettoyage_d_une_photo():
    photo = cv2.cvtColor(salir(_plan(), "telephone", random.Random(1)), cv2.COLOR_BGR2GRAY)
    propre, fait = nettoyer(photo)
    assert fait.feuille_detouree
    # La feuille remise à plat : plan et marge blanche, sans la table autour.
    assert np.median(propre[:20]) > 240 and np.median(propre[-20:]) > 240


def test_epaisseurs_du_cartouche():
    textes = [TexteLu(t, np.zeros((4, 2)), 1.0) for t in
              ["Murs exdérieurs 20 cm", "Cloisons .7 cm", "Hauteur sous plafond : 2,55 m", "Cotes intérieures, en mètres"]]
    assert lire_epaisseurs(textes) == [0.20, 0.07]


# Un plan témoin par famille, qui illustre une faiblesse corrigée :
# - travers 9 : trait de cote resté un peu penché ;
# - photocopie 28 : traînée de photocopieuse prise pour une marque de cote ;
# - taches 7 : deux cotes en désaccord faisaient planter la lecture (division par zéro) ;
# - compression 3 : battants de portes épaissis par le JPEG, pris pour des murs ;
# - telephone 5 : ombre sur la feuille, qui coupait son détourage.
@pytest.mark.parametrize("nom, graine", [("travers", 9), ("photocopie", 28), ("taches", 7), ("compression", 3), ("telephone", 5)])
def test_plans_salis_temoins_verts(nom, graine, tmp_path):
    pytest.importorskip("rapidocr")
    fabriquer_dossier(graine, tmp_path)
    (image,) = salir_dossier(tmp_path, (nom,))
    resultat = essayer(image, tmp_path / "logement.json")
    assert resultat.note is not None, resultat.echec
    assert resultat.note.vert, resultat.note.remarques
