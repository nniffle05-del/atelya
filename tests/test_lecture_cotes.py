"""Tests de la lecture automatique de l'échelle (cotes du plan) et de la hauteur sous plafond."""

import math

import numpy as np
import pytest

from moteur.lecture_cotes import TexteLu, lire_echelle, lire_hauteur_sous_plafond, lire_textes
from moteur.lecture_plan import en_gris, lire_plan, logement_depuis_plan, redresser
from moteur.logement import Logement, charger_logement
from test_lecture_plan import COPIES, DOSSIER, TOLERANCE_LONGUEUR, _milieu, _plan

pytest.importorskip("rapidocr")

TOLERANCE_ECHELLE = 0.01  # ±1 % : le critère de l'étape 3c


@pytest.mark.parametrize("nom", COPIES)
def test_echelle_lue_sur_les_cotes(nom):
    image, attendue = COPIES[nom]()
    gris, _ = redresser(en_gris(image))
    echelle = lire_echelle(gris)
    assert echelle.sure
    assert abs(echelle.px_par_m - attendue) / attendue <= TOLERANCE_ECHELLE
    assert len(echelle.retenues) >= 5  # le plan porte 7 cotes
    assert echelle.hauteur_sous_plafond == 2.50


def test_une_cote_mal_lue_est_ecartee():
    """Si le texte « 3,20 » était lu « 3,80 », cette cote ne doit pas fausser l'échelle."""
    gris = _plan()
    textes = lire_textes(gris)
    for t in textes:
        if t.texte == "3,20":
            t.texte = "3,80"
    echelle = lire_echelle(gris, textes)
    assert [c.texte.texte for c in echelle.ecartees] == ["3,80"]
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)


def test_une_seule_cote_ne_suffit_pas():
    gris = _plan()
    textes = [t for t in lire_textes(gris) if t.texte == "8,00"]
    echelle = lire_echelle(gris, textes)
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)
    assert not echelle.sure  # à faire vérifier par un humain


def test_un_plan_sans_cote_est_signale():
    vide = np.full((400, 600), 255, np.uint8)
    assert lire_echelle(vide).px_par_m is None


@pytest.mark.parametrize(
    "texte, attendu",
    [
        ("Hauteur sous plafond : 2,50 m", 2.50),
        ("HSP 2.70", 2.70),
        ("H.S.P. = 2,45 m", 2.45),
        ("Séjour 25,92 m²", None),
    ],
)
def test_hauteur_sous_plafond(texte, attendu):
    assert lire_hauteur_sous_plafond([TexteLu(texte, np.zeros((4, 2)), 1.0)]) == attendu


@pytest.mark.parametrize("nom", ["plan d'origine", "de travers de -3,5° et compressé", "résolution réduite (60 px/m)"])
def test_plan_lu_sans_rien_donner(nom):
    """Le chemin complet : une image, et rien d'autre, donne les bons murs en mètres."""
    image, _ = COPIES[nom]()
    plan = lire_plan(image)
    logement = Logement.model_validate(logement_depuis_plan(plan, "LU"))
    reference = charger_logement(DOSSIER / "logement.json")
    assert logement.hauteur_sous_plafond == reference.hauteur_sous_plafond
    assert len(logement.murs) == len(reference.murs)
    for ref in reference.murs:
        lu = min(logement.murs, key=lambda m: math.dist(_milieu(m), _milieu(ref)))
        assert abs(lu.longueur - ref.longueur) / ref.longueur <= TOLERANCE_LONGUEUR, ref.id


def _plan_chiffre_sur_le_trait(blanc_autour_du_chiffre=0):
    """Une cote « 3,00 » de 300 px avec le chiffre au milieu du trait, juste au-dessus d'un mur épais."""
    gris = np.full((300, 600), 255, np.uint8)
    gris[100:102, 100:401] = 90  # le trait de cote
    gris[97:105, 100] = gris[97:105, 400] = 90  # des marques minuscules
    gris[120:140, 40:560] = 0  # le mur, plus long que la cote
    gris[90:112, 230 - blanc_autour_du_chiffre:271 + blanc_autour_du_chiffre] = 255
    gris[92:110, 232:269:3] = 40  # le chiffre
    boite = np.array([[230.0, 90], [270, 90], [270, 111], [230, 111]])
    return gris, TexteLu("3,00", boite, 1.0)


@pytest.mark.parametrize("blanc", [0, 8])
def test_chiffre_au_milieu_du_trait(blanc):
    gris, texte = _plan_chiffre_sur_le_trait(blanc)
    echelle = lire_echelle(gris, [texte])
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)


def test_le_bord_d_un_mur_n_est_pas_un_trait_de_cote():
    gris = np.full((300, 600), 255, np.uint8)
    gris[120:140, 40:560] = 0
    boite = np.array([[230.0, 96], [270, 96], [270, 111], [230, 111]])
    assert lire_echelle(gris, [TexteLu("5,00", boite, 1.0)]).px_par_m is None


def test_plus_de_cotes_ecartees_que_gardees_est_une_contradiction():
    gris = _plan()
    textes = lire_textes(gris)
    assert not lire_echelle(gris, textes).contredite
    cotes = [t for t in textes if "," in t.texte and len(t.texte) == 4]
    for i, t in enumerate(cotes[:-2]):
        t.texte = f"{9 - i * 0.7:.2f}".replace(".", ",")  # chacune fausse, et toutes différentes
    echelle = lire_echelle(gris, textes)
    assert len(echelle.ecartees) > len(echelle.retenues) and echelle.contredite


def test_cote_en_centimetres_entiers():
    """« 300 » au milieu de son trait (plans de géomètre, fr-010) : 3,00 m."""
    gris, texte = _plan_chiffre_sur_le_trait()
    texte.texte = "300"
    assert lire_echelle(gris, [texte]).px_par_m is None  # une seule cote en centimètres ne suffit pas : numéro de pièce ?
    echelle = lire_echelle(gris, [texte, texte])  # deux cotes d'accord (ici la même, lue deux fois) : le plan est en cm
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)
    decimale = TexteLu("3,00", texte.boite, 1.0)
    assert lire_echelle(gris, [decimale, texte, texte]).retenues[0].texte.texte == "3,00"  # avec une cote « d,dd », les entiers sont ignorés
    assert len(lire_echelle(gris, [decimale, texte, texte]).retenues) == 1


def test_un_numero_sans_trait_n_est_pas_une_cote():
    vide = np.full((300, 600), 255, np.uint8)
    boite = np.array([[230.0, 90], [270, 90], [270, 111], [230, 111]])
    assert lire_echelle(vide, [TexteLu("2024", boite, 1.0), TexteLu("405", boite, 1.0)]).px_par_m is None


def test_hachures_de_sol_gris_clair_ne_sont_pas_des_marques():
    """PDF d'architecte (fr-019) : des lattes de parquet gris clair traversent la cote ; ses vraies marques sont de petits
    traits noirs de 4 à 8 pixels. Avant : la cote mesurait l'écart entre deux lattes."""
    gris = np.full((300, 600), 255, np.uint8)
    gris[:, 115::30] = 200  # les lattes, sur toute la hauteur
    gris[150:152, 100:401] = 80  # le trait de cote
    gris[147:155, 100:102] = 40  # ses marques
    gris[147:155, 399:401] = 40
    gris[118:143, 226:275] = 255  # le chiffre, au-dessus du trait
    gris[122:139, 232:269:3] = 40
    boite = np.array([[230.0, 120], [270, 120], [270, 141], [230, 141]])
    echelle = lire_echelle(gris, [TexteLu("3,00", boite, 1.0)])
    assert echelle.px_par_m == pytest.approx(100, rel=TOLERANCE_ECHELLE)


def test_des_cotes_imprecises_ne_sont_pas_une_contradiction():
    """Dessin à la main (fr-010) : des cotes à ±10 % de l'échelle gardée sont imprécises, pas contradictoires."""
    from moteur.lecture_cotes import CoteLue, Echelle

    boite = np.zeros((4, 2))

    def cote(valeur, px):
        return CoteLue(valeur, px, False, TexteLu(str(valeur), boite, 1.0), ((0.0, 0.0), (px, 0.0)))

    gardees = [cote(4.0, 400), cote(3.0, 300)]
    imprecises = [cote(2.0, 215), cote(1.0, 92), cote(1.5, 162)]
    fausses = [cote(2.0, 400), cote(1.0, 300), cote(1.5, 50)]
    assert not Echelle(100.0, True, gardees, imprecises).contredite
    assert Echelle(100.0, True, gardees, fausses).contredite


def test_sure_quand_deux_cotes_s_accordent_entre_elles():
    """Trois cotes à 58,5, 58,5 et 56 px/m : les deux premières s'accordent, l'échelle est sûre (avant, la moyenne
    pondérée tombait entre les deux et personne n'était « concordant »)."""
    from moteur.lecture_cotes import CoteLue, Echelle, lire_echelle

    gris, texte = _plan_chiffre_sur_le_trait()
    # On ne peut pas dessiner trois cotes facilement : on vérifie le critère sur les objets eux-mêmes via lire_echelle
    # d'une image sans cote (aucune), puis sur un faux jeu de cotes retenues recomposé.
    boite = np.zeros((4, 2))

    def cote(valeur, px):
        return CoteLue(valeur, px, False, TexteLu(str(valeur), boite, 1.0), ((0.0, 0.0), (px, 0.0)))

    retenues = [cote(3.28, 3.28 * 58.54), cote(1.65, 1.65 * 56.01), cote(1.48, 1.48 * 58.52)]
    from moteur import lecture_cotes as L
    px = sum(c.longueur_px for c in retenues) / sum(c.valeur for c in retenues)
    concordantes = max(sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= L.ACCORD for d in retenues) for c in retenues)
    assert concordantes == 2 and all(abs(c.px_par_m - px) / px > L.ACCORD for c in retenues)
    assert lire_echelle(gris, [texte]).sure is False  # une seule cote : toujours pas sûre
