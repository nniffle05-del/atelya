"""Murs raccordés (examen app-004, 15/11/2026) : recalage des murs gris cernés d'un trait, fentes vers le dehors, raccord."""
import numpy as np

from moteur.controle_maquette import fentes_vers_dehors
from moteur.geometrie import calculer_briques
from moteur.logement import Logement
from moteur.raccorder_murs import fermer_les_fentes, raccorder
from moteur.recalage_murs import affiner_mur

GRIS, TRAIT = 203, 135  # le gris de remplissage et le trait de bord d'un plan d'annonce


def _page(h=200, w=300):
    return np.full((h, w), 255, np.uint8)


def _mur_cerne(page, x0, y0, x1, y1):
    """Un rectangle gris cerné d'un trait de 1 px (bornes comprises)."""
    page[y0:y1 + 1, x0:x1 + 1] = GRIS
    page[y0, x0:x1 + 1] = page[y1, x0:x1 + 1] = TRAIT
    page[y0:y1 + 1, x0] = page[y0:y1 + 1, x1] = TRAIT


def test_mur_gris_cerne_recale_sur_toute_la_bande():
    page = _page()
    _mur_cerne(page, 20, 90, 280, 107)  # mur horizontal de 18 px (rangées 90 à 107) : son milieu est à 98,5
    x0, y0, x1, y1, ep = affiner_mur(page, [20.0, 96.0, 280.0, 96.0, 15.0])  # saisi 2,5 px trop haut, 3 px trop fin
    assert abs(y0 - 98.5) < 0.6 and abs(y1 - 98.5) < 0.6
    assert abs(ep - 18.0) < 1.0


def test_cloison_grise_cernee_garde_son_epaisseur():
    page = _page()
    _mur_cerne(page, 20, 96, 280, 102)  # cloison de 7 px
    _, y0, _, _, ep = affiner_mur(page, [20.0, 100.0, 280.0, 100.0, 6.0])
    assert abs(y0 - 99.5) < 0.6
    assert 6.0 <= ep <= 8.0  # avant : elle glissait sur un trait de bord, ou devenait épaisse de 3 px


def test_plein_colle_a_un_mur_ne_glisse_pas_sur_son_trait():
    page = _page()
    _mur_cerne(page, 10, 40, 290, 57)  # le mur porteur (y de 40 à 57)
    page[57:70, 100:201] = GRIS  # un plein collé dessous (y jusqu'à 69), sans trait entre les deux
    page[69, 100:201] = TRAIT
    page[57:70, 100] = page[57:70, 200] = TRAIT
    page[57, 101:200] = GRIS
    _, y0, _, _, ep = affiner_mur(page, [100.0, 63.5, 200.0, 63.5, 12.0])  # axe vrai du plein : 63,5
    assert abs(y0 - 63.5) < 1.0  # avant : + 4,5 px (le plein se décollait du mur de 6 cm en 3D)
    assert ep == 12.0


def test_la_porte_d_une_cloison_n_est_pas_mesuree():
    page = _page()
    _mur_cerne(page, 150, 20, 156, 180)  # cloison verticale de 7 px
    page[70:150, 150:157] = 255  # sa porte : la moitié de sa longueur est vide…
    page[70:150, 150] = TRAIT  # … avec le trait fin du battant sur un bord
    exclure = [((70 - 20) / 160, (150 - 20) / 160)]
    x0, _, _, _, ep = affiner_mur(page, [153.0, 20.0, 153.0, 180.0, 6.0], exclure=exclure)
    assert abs(x0 - 153.0) < 0.6 and 6.0 <= ep <= 8.0


def test_mur_noir_plein_inchange_par_le_second_regard():
    page = _page()
    page[90:105, 20:281] = 0  # mur noir de 15 px, axe 97
    assert affiner_mur(page, [20.0, 96.0, 280.0, 96.0, 15.0])[1::2][:1] == [97.0]


def _logement(murs, contour, ouvertures=()):
    return {"schema": "logement/0.1", "projet_id": "essai", "unites": "m", "hauteur_sous_plafond": 2.5,
            "murs": [{"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2, "statut": "estime", "source": "essai"} for i, a, b in murs],
            "ouvertures": list(ouvertures),
            "pieces": [{"id": "sejour_1", "nom": "Séjour", "contour": [list(p) for p in contour], "statut": "estime", "source": "essai"}]}


CARRE = [(0, 0), (4, 0), (4, 3), (0, 3)]


def _murs_du_carre(fente=0.0):
    """Une pièce de 4 × 3 m ; le mur du bas est en deux morceaux, séparés par une fente."""
    return [("M1", (-0.1, -0.1), (2.0 - fente / 2, -0.1)), ("M1b", (2.0 + fente / 2, -0.1), (4.1, -0.1)),
            ("M2", (4.1, -0.1), (4.1, 3.1)), ("M3", (4.1, 3.1), (-0.1, 3.1)), ("M4", (-0.1, 3.1), (-0.1, -0.1))]


def _fentes(lg):
    return fentes_vers_dehors(calculer_briques(Logement.model_validate(lg)))


def test_fente_entre_deux_bouts_de_murs_trouvee_puis_refermee():
    lg = _logement(_murs_du_carre(fente=0.17), CARRE)
    avant = _fentes(lg)
    assert len(avant) == 1 and 0.1 < avant[0]["longueur_m"] < 0.3
    apres, bilan = fermer_les_fentes(lg)
    assert len(bilan["raccords"]) == 2 and bilan["fentes_apres"] == []
    assert _fentes(apres) == []
    assert lg["murs"][0]["fin"] == [2.0 - 0.085, -0.1]  # le logement d'entrée n'est pas modifié


def test_logement_sans_fente_inchange():
    lg = _logement(_murs_du_carre(), CARRE)
    apres, bilan = fermer_les_fentes(lg)
    assert apres == lg and bilan["raccords"] == [] and bilan["fentes_avant"] == []


def test_un_vrai_passage_n_est_pas_referme():
    lg = _logement(_murs_du_carre(fente=0.9), CARRE)  # 90 cm : une porte oubliée, pas un défaut de saisie
    apres, bilan = fermer_les_fentes(lg)
    assert apres == lg and len(bilan["fentes_apres"]) == 1  # laissé tel quel, et signalé


def test_raccord_de_deux_pans_en_angle_au_croisement_des_axes():
    murs = [("A", (0.0, 0.0), (1.0, 0.0)), ("B", (1.25, 0.1), (2.05, 0.5))]  # B fait un angle avec A, 25 cm plus loin
    lg, raccords = raccorder(_logement(murs, CARRE))
    a, b = lg["murs"]
    assert a["fin"] == b["debut"]  # les deux bouts se rejoignent au même point
    assert abs(a["fin"][1]) < 1e-6 and abs(a["fin"][0] - 1.05) < 0.002
    assert {(r["mur"], r["bout"]) for r in raccords} == {("A", "fin"), ("B", "debut")}


def test_raccord_par_le_debut_decale_les_ouvertures():
    murs = [("A", (0.0, 0.0), (1.0, 0.0)), ("B", (1.15, 0.0), (4.0, 0.0))]
    porte = {"id": "O1", "type": "porte", "mur": "B", "position": 1.0, "largeur": 0.8, "hauteur": 2.04, "allege": 0.0,
             "statut": "estime", "source": "essai"}
    lg, _ = raccorder(_logement(murs, CARRE, [porte]))
    assert lg["murs"][1]["debut"] == [1.0, 0.0]
    assert lg["ouvertures"][0]["position"] == 1.15  # la porte reste au même endroit du logement
