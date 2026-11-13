"""Brique photos : familles de sols, vignettes, classificateur, votes et vérité (moteur/reconnaitre_sols.py)."""
import numpy as np

from moteur.matieres import NOMS_SOLS
from moteur.reconnaitre_sols import (FAMILLES, Classifieur, famille, familles_verite, matieres_verite, vignettes, voter)


def test_chaque_matiere_a_sa_famille():
    assert famille("point_de_hongrie") == famille("hongrie_naturel") == "point_de_hongrie"
    assert famille("parquet_batons_rompus") == "batons_rompus"
    assert famille("chene_clair_photo") == famille("stratifie") == "lames"
    assert famille("carreaux_cubes") == famille("tomettes") == "carreaux"
    assert {famille(m) for m in NOMS_SOLS} == set(FAMILLES)


def test_vignettes_seulement_la_ou_le_sol_est_vu():
    image = np.full((300, 300, 3), 100, np.uint8)
    finesse = np.zeros((300, 300), np.float32)
    finesse[:, :150] = 1.0  # moitié gauche vue
    v, centres, f = vignettes(image, finesse, resolution=0.01, taille_m=1.0, pas_m=0.25, sortie_px=56)
    assert len(v) > 0 and v.shape[1:] == (56, 56, 3)
    assert (centres[:, 1] <= 100).all()  # aucune vignette au-delà de la partie vue
    assert np.allclose(f, 1.0)


def test_le_classificateur_apprend_deux_nuages():
    alea = np.random.default_rng(0)
    a = alea.normal(0, 1, (50, 8)) + np.r_[3, 0, 0, 0, 0, 0, 0, 0]
    b = alea.normal(0, 1, (50, 8)) - np.r_[3, 0, 0, 0, 0, 0, 0, 0]
    X = np.concatenate([a, b]).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    y = np.r_[np.zeros(50, int), np.ones(50, int)]
    clf = Classifieur(8, ("x", "y"))
    assert clf.apprendre(X, y) > 0.9
    assert Classifieur.depuis(clf.etat()).probabilites(X[:3]).argmax(1).tolist() == [0, 0, 0]


def test_voter_ajoute_aux_cases_du_centre():
    votes = np.zeros((16, 16, 2))
    # vignette d'1 m centrée à 2 m du coin (pixel 200 à 1 cm) : cases de 25 cm n° 7 à 9 (sa moitié centrale)
    voter(votes, np.array([[200.0, 200.0]]), np.array([[0.9, 0.1]]), np.array([1.0]), resolution=0.01, case=0.25)
    assert votes[0, 0].sum() == 0 and votes[11, 11].sum() == 0  # loin du centre : rien
    assert votes[8, 8, 0] > votes[8, 8, 1] > 0
    assert (votes[..., 0] > 0).sum() == 9


def test_verite_zone_dans_une_piece():
    logement = {"pieces": [{"id": "sejour", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]],
                            "sol": {"matiere": "point_de_hongrie"},
                            "zones_sol": [{"contour": [[4, 0], [6, 0], [6, 4], [4, 4]], "sol": {"matiere": "carreaux_cubes"}}]},
                           {"id": "chambre", "contour": [[0, 4], [3, 4], [3, 7], [0, 7]]}]}
    X, Y = np.array([1.0, 5.0, 1.0, 9.0]), np.array([1.0, 2.0, 5.0, 9.0])
    assert list(matieres_verite(logement, X, Y)) == ["point_de_hongrie", "carreaux_cubes", "", ""]
    assert list(familles_verite(logement, X, Y)) == [FAMILLES.index("point_de_hongrie"), FAMILLES.index("carreaux"), -1, -1]


def test_une_case_vue_seulement_comme_meuble_reste_inconnue():
    from moteur.reconnaitre_sols import CLASSES_AVEC_MEUBLE, CarteDesSols, MEUBLE
    votes = np.zeros((1, 3, len(CLASSES_AVEC_MEUBLE)))
    votes[0, 0, FAMILLES.index("carreaux")] = 0.2
    votes[0, 0, CLASSES_AVEC_MEUBLE.index(MEUBLE)] = 0.9  # surtout un meuble, un peu de carreaux vus
    votes[0, 1, CLASSES_AVEC_MEUBLE.index(MEUBLE)] = 1.0  # rien que du meuble
    carte = CarteDesSols(votes, (0.0, 1.0), 0.25, CLASSES_AVEC_MEUBLE)
    assert carte.famille().tolist() == [[FAMILLES.index("carreaux"), -1, -1]]
    assert carte.vue().tolist() == [[True, False, False]]
    assert carte.part_meuble()[0, 1] == 1.0 and carte.part_meuble()[0, 2] == 0.0
