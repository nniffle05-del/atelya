"""Sols fidèles aux photos (NT, 16/11/2026, app-004 : « le parquet n'est pas le même ») : pas de zone de sol là où les photos
voient un meuble, même bois = même couleur, un espace ouvert garde le sol de la pièce voisine."""
import numpy as np

from moteur import reconnaitre_sols as rs

CLASSES = (*rs.FAMILLES, rs.MEUBLE)
LAMES, CARREAUX = CLASSES.index("lames"), CLASSES.index("carreaux")


def _carte(vues_propres_dans_la_zone: int):
    """Une pièce de 4 × 4 m (16 × 16 cases) en lames, avec une tache de carreaux de 1,5 × 1,5 m vue par 4 photos."""
    votes = np.zeros((16, 16, len(CLASSES)))
    votes[..., LAMES] = 1.0
    votes[4:10, 4:10, LAMES], votes[4:10, 4:10, CARREAUX] = 0.0, 1.0
    vues = np.full((16, 16), 4, np.int32)
    propres = vues.copy()
    propres[4:10, 4:10] = vues_propres_dans_la_zone
    return rs.CarteDesSols(votes, (0.0, 4.0), rs.CASE_M, CLASSES, votes_propres=votes.copy(), vues=vues, vues_propres=propres)


LOGEMENT = {"pieces": [{"id": "sejour_1", "contour": [[0, 0], [4, 0], [4, 4], [0, 4]]}]}


def test_zone_vue_proprement_gardee():
    s = rs.sols_des_pieces(_carte(4), LOGEMENT)["sejour_1"]
    assert s["famille"] == "lames" and [z["famille"] for z in s["zones"]] == ["carreaux"]


def test_zone_la_ou_les_photos_voient_un_meuble_retiree():
    s = rs.sols_des_pieces(_carte(1), LOGEMENT)["sejour_1"]  # 3 photos sur 4 y voient un lit : pas un autre sol
    assert s["famille"] == "lames" and s["zones"] == []


def test_meme_bois_vu_sur_une_seule_photo_prend_la_couleur_sure():
    pieces = {"sejour_1": {"famille": "lames", "couleur_photo": [0.27, 0.14, 0.05], "photos_couleur": 5},
              "chambre_1": {"famille": "batons_rompus", "couleur_photo": [0.70, 0.47, 0.26], "photos_couleur": 1},
              "cuisine_1": {"famille": "carreaux", "couleur_photo": [0.8, 0.8, 0.8], "photos_couleur": 1}}
    rs.couleur_sure_du_bois(pieces)
    assert pieces["chambre_1"]["couleur_photo"] == [0.27, 0.14, 0.05] and pieces["chambre_1"]["couleur_photo_seule"] == [0.70, 0.47, 0.26]
    assert pieces["sejour_1"]["couleur_photo"] == [0.27, 0.14, 0.05]
    assert pieces["cuisine_1"]["couleur_photo"] == [0.8, 0.8, 0.8]  # un carrelage n'est pas un bois : inchangé


def test_sans_parquet_sur_rien_ne_change():
    pieces = {"chambre_1": {"famille": "lames", "couleur_photo": [0.70, 0.47, 0.26], "photos_couleur": 1}}
    rs.couleur_sure_du_bois(pieces)
    assert pieces["chambre_1"]["couleur_photo"] == [0.70, 0.47, 0.26]


def _deux_pieces(cloison: bool, id_voisine: str = "entree_1"):
    """Un séjour (sol reconnu) et une pièce voisine sans sol, avec ou sans cloison entre les deux (x = 4)."""
    mur = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
    murs = [mur("M1", (0, -0.1), (6, -0.1)), mur("M2", (0, 3.1), (6, 3.1)), mur("M3", (-0.1, 0), (-0.1, 3)), mur("M4", (6.1, 0), (6.1, 3))]
    if cloison:
        murs.append(mur("M5", (4, 0), (4, 3)))
    x = 4.1 if cloison else 4.0
    sol = {"matiere": "chene_noeuds", "teinte": [0.59, 0.58, 0.56], "couleur_photo": [0.27, 0.14, 0.05], "statut": "estime",
           "confiance": 0.8, "source": "brique photos (5 photos pour la couleur)"}
    return {"murs": murs, "pieces": [{"id": "sejour_1", "contour": [[0, 0], [3.9 if cloison else 4.0, 0], [3.9 if cloison else 4.0, 3], [0, 3]], "sol": sol},
                                     {"id": id_voisine, "contour": [[x, 0], [6, 0], [6, 3], [x, 3]]}]}


def test_espace_ouvert_garde_le_sol_de_la_piece_voisine():
    lg = rs.sols_des_espaces_ouverts(_deux_pieces(cloison=False))
    sol = lg["pieces"][1]["sol"]
    assert sol["matiere"] == "chene_noeuds" and sol["teinte"] == [0.59, 0.58, 0.56] and sol["statut"] == "ajoute"
    assert "sejour_1" in sol["source"] and "espace ouvert" in sol["source"]


def test_une_cloison_ou_une_piece_d_eau_ne_reprend_pas_le_sol():
    assert "sol" not in rs.sols_des_espaces_ouverts(_deux_pieces(cloison=True))["pieces"][1]
    assert "sol" not in rs.sols_des_espaces_ouverts(_deux_pieces(cloison=False, id_voisine="cuisine_1"))["pieces"][1]
