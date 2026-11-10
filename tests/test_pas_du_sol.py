"""« Pas du sol » (10/11/2026) : masque des lits / canapés / rangements repérés par OWLv2, points douteux à la mise à plat,
vignettes douteuses qui votent peu, pièce décidée par ses cases propres (moteur/pas_du_sol.py, sol_a_plat.py, reconnaitre_sols.py)."""
import numpy as np

from moteur.pas_du_sol import PasDuSol
from moteur.reconnaitre_sols import POIDS_DOUTEUX, CarteDesSols, sols_des_pieces, vignettes


def test_masque_rectangles_des_groupes_ecartes_seulement():
    pds = PasDuSol()
    pds.cache["p"] = {"taille": (100, 200), "objets": [
        {"nom": "a bed", "note": 0.6, "boite": [10, 20, 60, 80]},
        {"nom": "a rug", "note": 0.9, "boite": [100, 50, 190, 95]},       # un tapis : jamais écarté
        {"nom": "a dining table", "note": 0.8, "boite": [120, 0, 150, 30]},  # une table : pas dans le réglage retenu
        {"nom": "a cabinet", "note": 0.1, "boite": [0, 0, 5, 5]}]}           # note trop faible
    m = pds.masque("p", np.zeros((100, 200, 3), np.uint8))
    assert m.shape == (100, 200) and m[50, 30] and not m[70, 150] and not m[10, 130] and not m[2, 2]
    assert m.sum() == 50 * 60


def test_vignette_un_peu_douteuse_remplie_tres_douteuse_vote_peu():
    image = np.full((300, 300, 3), 100, np.uint8)
    finesse = np.ones((300, 300), np.float32)
    douteux = np.zeros((300, 300), bool)
    douteux[:, 250:] = True  # la vignette de droite (colonnes 200-300) est douteuse à 50 %
    v, centres, f, facteurs = vignettes(image, finesse, 0.01, pas_m=1.0, douteux=douteux)
    assert len(v) == 9
    assert sorted(set(np.round(facteurs, 3))) == [POIDS_DOUTEUX, 1.0]
    douteux[:, 290:] = True
    douteux[:, :290] = False  # 10 % douteux : remplacé par le sol propre, poids 0,9
    *_, facteurs = vignettes(image, finesse, 0.01, pas_m=1.0, douteux=douteux)
    assert np.isclose(facteurs.min(), 0.9)


def test_piece_decidee_par_ses_cases_propres():
    # pièce de 4 × 2 m, cases de 25 cm : 16 × 8 ; votes : à gauche (propre) lames, à droite (derrière un lit) carreaux,
    # plus fort ; les carreaux ne viennent que de vignettes douteuses
    classes = ("lames", "point_de_hongrie", "batons_rompus", "carreaux")
    votes = np.zeros((8, 16, 4))
    votes[:, :8, 0] = 1.0
    votes[:, 8:, 3] = 3.0
    propres = np.zeros_like(votes)
    propres[:, :8, 0] = 1.0
    logement = {"pieces": [{"id": "ch", "contour": [[0, 0], [4, 0], [4, 2], [0, 2]]}]}
    sans = sols_des_pieces(CarteDesSols(votes, (0.0, 2.0), 0.25, classes), logement)
    avec = sols_des_pieces(CarteDesSols(votes, (0.0, 2.0), 0.25, classes, votes_propres=propres), logement)
    # sans les cases propres, le lit (carreaux) l'emporte : pièce décidée en carreaux, les lames réduites à une zone
    assert sans["ch"]["famille"] == "carreaux" and [z["famille"] for z in sans["ch"]["zones"]] == ["lames"]
    assert avec["ch"]["famille"] == "lames" and avec["ch"]["zones"] == []
