"""Les sols quand la lecture des photos est branchée (étape 4, 17/11/2026) : la lecture dit QUELS sols, Atelya dit OÙ.
Défaut corrigé : le sol que la brique prenait pour principal était effacé quand la lecture le dit second (lames de l'entrée
d'app-001 : sol juste 79 % → 92 %)."""
import numpy as np

from moteur import photos_lues as pl
from moteur import reconnaitre_sols as rs

CLASSES = (*rs.FAMILLES, rs.MEUBLE)
LAMES, HONGRIE, CARREAUX, MEUBLE = (CLASSES.index(c) for c in ("lames", "point_de_hongrie", "carreaux", rs.MEUBLE))
LOGEMENT = {"pieces": [{"id": "sejour_1", "contour": [[0, 0], [8, 0], [8, 4], [0, 4]]}]}


def _carte():
    """Un séjour de 8 × 4 m : 5 m de lames (l'entrée et le passage, le plus grand), 3 m de point de Hongrie (le salon), et un
    coin de carrelage dans les lames (la cuisine)."""
    votes = np.zeros((16, 32, len(CLASSES)))
    votes[:, :20, LAMES] = 1.0
    votes[:, 20:, HONGRIE] = 1.0
    votes[:6, :6] = 0.0
    votes[:6, :6, CARREAUX] = 1.0  # la cuisine
    vues = np.full(votes.shape[:2], 3, np.int32)
    return rs.CarteDesSols(votes, (0.0, 4.0), rs.CASE_M, CLASSES, votes_propres=votes.copy(), vues=vues, vues_propres=vues.copy())


def _surface(zones, famille):
    return sum(z["surface_m2"] for z in zones if z["famille"] == famille)


def test_sans_lecture_rien_ne_change():
    s = rs.sols_des_pieces(_carte(), LOGEMENT)["sejour_1"]
    assert s["famille"] == "lames" and "famille_brique" not in s
    assert sorted(z["famille"] for z in s["zones"]) == ["carreaux", "point_de_hongrie"]


def test_le_sol_principal_lu_ne_fait_plus_disparaitre_l_ancien():
    lus = {"sejour_1": {"famille": "point_de_hongrie", "autres": ["carreaux", "lames"]}}
    s = rs.sols_des_pieces(_carte(), LOGEMENT, lus=lus)["sejour_1"]
    assert s["famille"] == "point_de_hongrie" and s["famille_brique"] == "lames"
    # les lames (20 m² moins la cuisine) deviennent des zones, en morceaux convexes : rien n'est perdu
    assert abs(_surface(s["zones"], "lames") - (20.0 - 2.25)) < 1.0
    assert all(z["famille"] in ("lames", "carreaux") for z in s["zones"])
    # deux sols « autres » qui se touchent (carrelage de la cuisine, lames) ne sont pas fondus en une zone
    assert abs(_surface(s["zones"], "carreaux") - 2.25) < 0.3
    # les petites zones sont rangées après les grandes : là où deux enveloppes se recouvrent, la petite l'emporte
    assert [z["surface_m2"] for z in s["zones"]] == sorted((z["surface_m2"] for z in s["zones"]), reverse=True)


def test_une_piece_lue_d_un_seul_sol_n_a_pas_de_zone():
    s = rs.sols_des_pieces(_carte(), LOGEMENT, lus={"sejour_1": {"famille": "lames", "autres": []}})["sejour_1"]
    assert s["famille"] == "lames" and s["zones"] == []


def test_un_l_est_coupe_en_morceaux_convexes():
    tache = np.zeros((20, 20), bool)
    tache[:, :6] = True
    tache[14:, :] = True  # un L
    morceaux = rs.morceaux_convexes(tache)
    assert len(morceaux) == 2 and sum(int(m.sum()) for m in morceaux) == int(tache.sum())
    assert all(rs._plein(m) > 0.95 for m in morceaux)
    carre = np.ones((8, 8), bool)
    assert len(rs.morceaux_convexes(carre)) == 1


def test_une_photo_ne_vote_que_parmi_ses_sols():
    pr = np.zeros((3, len(CLASSES)))
    pr[0, [HONGRIE, CARREAUX, MEUBLE]] = 0.1, 0.7, 0.2  # un tapis pris pour du carrelage, sur une photo lue « point de Hongrie »
    pr[1, [LAMES, HONGRIE, CARREAUX]] = 0.2, 0.6, 0.2
    pr[2, [CARREAUX, MEUBLE]] = 0.9, 0.1  # aucun avis pour les sols lus : tout va au premier
    s = rs.avis_parmi(pr, CLASSES, ("point_de_hongrie",))
    assert np.allclose(s[0, [HONGRIE, CARREAUX, MEUBLE]], [0.8, 0.0, 0.2])  # la part de sol est gardée, « meuble » inchangé
    assert np.allclose(s[2, [HONGRIE, CARREAUX, MEUBLE]], [0.9, 0.0, 0.1])
    s = rs.avis_parmi(pr, CLASSES, ("point_de_hongrie", "lames"))
    assert np.allclose(s[1, [LAMES, HONGRIE, CARREAUX]], [0.25, 0.75, 0.0])
    assert rs.avis_parmi(pr, CLASSES, None) is pr and np.allclose(pr[0, CARREAUX], 0.7)  # sans lecture : inchangé


def test_les_sols_de_chaque_photo():
    lecture = {"photos": {"photo-01": {"sol": {"famille": "point_de_hongrie", "uniforme": True}},
                          "photo-02": {"sol": {"famille": "lames", "uniforme": False, "autre_famille": "carreaux"}},
                          "photo-03": {"sol": {"famille": None, "uniforme": True}}, "photo-04": {}}}
    assert pl.sols_des_photos(lecture) == {"photo-01": ("point_de_hongrie",), "photo-02": ("lames", "carreaux")}


def test_les_morceaux_d_un_meme_sol_ont_la_meme_couleur():
    pieces = {"sejour_1": {"famille": "point_de_hongrie", "zones": [
        {"famille": "lames", "surface_m2": 5.0, "couleur_photo": [0.5, 0.3, 0.2], "photos_couleur": 3, "empreinte": "a"},
        {"famille": "lames", "surface_m2": 9.0, "couleur_photo": [0.6, 0.4, 0.3], "photos_couleur": 1, "empreinte": "b"},
        {"famille": "lames", "surface_m2": 2.0},
        {"famille": "carreaux", "surface_m2": 7.0, "couleur_photo": [0.7, 0.7, 0.6], "photos_couleur": 2}]}}
    rs.zones_d_un_meme_sol(pieces)
    z = pieces["sejour_1"]["zones"]
    assert [x["couleur_photo"] for x in z[:3]] == [[0.5, 0.3, 0.2]] * 3 and [x["empreinte"] for x in z[:3]] == ["a"] * 3
    assert z[3]["couleur_photo"] == [0.7, 0.7, 0.6]  # un autre sol garde sa couleur


def test_mediane_ponderee():
    assert rs.mediane_ponderee([0.2, 0.9, 0.5], [1, 1, 1]) == 0.5
    assert rs.mediane_ponderee([0.2, 0.9, 0.5], [10, 1, 1]) == 0.2  # la photo qui voit le plus de sol l'emporte
    assert rs.mediane_ponderee([0.4], [3]) == 0.4
