"""Meubles précis (moteur/meubles_photos.py, 16/11/2026) : la sorte exacte, la taille de la sorte et la couleur vues sur les photos ;
deux objets distincts d'une même photo ne sont jamais fondus en un seul meuble."""
import numpy as np

from moteur import meubles_photos as mp
from moteur import reperer_meubles as rm

PIECE = {"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]]}
LOGEMENT = {"pieces": [PIECE]}


def _vu(groupe, categorie, x, y, photo, poids=1.0, confiance=0.6, couleur=None):
    return {"groupe": groupe, "categorie": categorie, "position": [x, y], "poids": poids, "confiance": confiance, "photo": photo,
            "largeur_vue": 1.0, "mesure": {"couleur": couleur, "pied": (x, y), "appareil": [0.0, 0.0, 1.3]}}


def test_deux_objets_de_la_meme_photo_restent_deux_meubles():
    # la table ronde et le meuble télé, vus « table » tous les deux sur la photo 0, à 1,5 m l'un de l'autre (moins que 1,8 m)
    vus = [_vu("table", "table", 1.0, 1.0, photo=0, poids=3), _vu("table", "table_d_appoint", 2.5, 1.0, photo=0, poids=2),
           _vu("table", "table", 1.2, 1.1, photo=1, poids=1)]
    trouves = mp.fusionner(vus)
    assert len(trouves) == 2
    table = next(t for t in trouves if t["categorie"] == "table")
    assert table["vues"] == 2 and table["position"][0] < 1.3  # la vue de la photo 1 rejoint la table la plus proche
    # l'ancienne fusion (par groupe et distance seulement) en faisait UN meuble posé entre les deux
    assert len(rm.fusionner(vus)) == 1 and 1.3 < rm.fusionner(vus)[0]["position"][0] < 2.0


def test_la_sorte_est_celle_que_les_vues_donnent_le_plus():
    vus = [_vu("rangement", "table_de_chevet", 1.0, 1.0, photo=0, poids=2), _vu("rangement", "table_de_chevet", 1.1, 1.0, photo=1, poids=2),
           _vu("rangement", "rangement", 1.0, 1.1, photo=2, poids=1)]
    trouve, = mp.fusionner(vus)
    assert trouve["categorie"] == "table_de_chevet" and trouve["vues"] == 3 and len(trouve["mesures"]) == 3


def test_sorte_taille_et_couleur_arrivent_dans_le_logement():
    bleu = [41, 88, 124]
    trouves = mp.fusionner([_vu("canape", "canape", 3.0, 0.5, photo=0, couleur=bleu), _vu("canape", "canape", 3.1, 0.5, photo=1, couleur=[45, 90, 130]),
                            _vu("rangement", "placard", 5.6, 2.0, photo=0, couleur=[230, 230, 228]),
                            _vu("rangement", "table_de_chevet", 0.4, 3.6, photo=1, couleur=[160, 150, 140])])
    meubles = {m["categorie"]: m for m in rm.vers_meubles_du_logement(trouves, LOGEMENT)}
    assert set(meubles) == {"canape", "placard", "table_de_chevet"}
    assert meubles["placard"]["dimensions"] == [1.5, 0.6, 2.2]  # une armoire est haute : plus un buffet de 90 cm
    assert meubles["table_de_chevet"]["dimensions"] == [0.45, 0.4, 0.55]
    assert meubles["canape"]["couleur"] == [43, 89, 127]  # la médiane de ses deux vues
    assert meubles["canape"]["statut"] == "estime"


def test_un_lit_garde_sa_literie_par_defaut_et_pas_de_couleur():
    trouves = mp.fusionner([_vu("lit", "lit", 3.0, 1.2, photo=0, couleur=[200, 200, 200])])
    lit, = rm.vers_meubles_du_logement(trouves, LOGEMENT)
    assert "couleur" not in lit and lit["literie"] == rm.LITERIE_PAR_DEFAUT


def test_une_table_au_milieu_de_la_piece_est_posee_droite():
    trouves = mp.fusionner([_vu("table", "table", 2.2, 2.3, photo=0)])
    table, = rm.vers_meubles_du_logement(trouves, LOGEMENT)
    assert table["face"] % 90.0 == 0.0  # le long des murs, plus « vers le centre de la pièce »


def test_couleur_au_coeur_du_rectangle():
    photo = np.full((400, 600, 3), 250, np.uint8)
    photo[150:250, 200:400] = (40, 90, 125)  # le canapé bleu, au cœur de son rectangle ; le mur blanc autour
    m = mp.mesurer((150, 100, 450, 300), [0.0, 0.0, 1.3, 0.0, 0.0, 300.0, 300.0, 150.0], 600, 400, photo)
    assert m["couleur"] == [40, 90, 125] and m["coupe_cotes"] is False and m["pied"] is not None


def test_toutes_les_sortes_ont_une_taille_et_existent_dans_la_maquette():
    from moteur.meubles import NOMS_MEUBLES

    for phrase, categorie in mp.CATEGORIE_DE.items():
        assert categorie in NOMS_MEUBLES, phrase
        assert categorie in mp.TAILLES, categorie
        l, p, h = mp.taille_courante(categorie)
        (_, _, _), (lmin, lmax), (hmin, hmax) = mp.TAILLES[categorie]
        assert lmin <= l <= lmax and hmin <= h <= hmax
