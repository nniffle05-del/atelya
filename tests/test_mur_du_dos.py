"""Le mur où un lit met sa tête (28/11/2026). Pourquoi ces tests : dans la chambre d'app-004 le lit est à 1,15 m de DEUX murs ;
une vue de plus l'a déplacé de 1 cm, « le mur le plus proche » a changé, et le lit a tourné d'un quart de tour (tête vers la
fenêtre) alors que cinq photos mesurent toutes son grand côté dans l'autre sens. Quand les photos ont mesuré le sens du meuble,
c'est ce sens qui choisit entre deux murs presque aussi proches ; sans mesure, rien ne change."""
from moteur import reperer_meubles as rm

CHAMBRE = {"id": "chambre_1", "contour": [[4.376, 2.946], [4.376, 0.0], [8.318, 0.0], [8.318, 2.946]]}


def _emprise(sens: float, distance: float = 2.0) -> dict:
    return {"grand": 1.9, "petit": 1.4, "sens": sens, "distance": distance, "coupe": False}


def _lit(x: float, y: float, sens: float | None = 90.0) -> dict:
    m = {"groupe": "lit", "categorie": "lit", "position": [x, y], "distance_min": 2.9}
    if sens is not None:
        m["emprises"] = [_emprise(sens), _emprise(sens, 2.7), _emprise(sens, 2.9)]
    return m


def test_un_centimetre_ne_fait_plus_tourner_le_lit():
    # les deux places mesurées sur app-004, à 1 cm l'une de l'autre : le mur du bas (y = 0) puis le mur de droite sont « le plus proche »
    for x, y in ((7.164, 1.149), (7.177, 1.161)):
        colle = rm.coller_au_mur(_lit(x, y), CHAMBRE)
        assert abs(colle["position"][1] - (2.05 / 2 + 0.03)) < 1e-3 and colle["position"][0] == x  # tête contre le mur du bas
        assert abs(rm.orienter(colle, CHAMBRE) - 90.0) < 1e-6                                      # le lit regarde vers le haut


def test_le_sens_mesure_ne_l_emporte_que_si_les_deux_murs_sont_presque_aussi_pres():
    # tout près du mur de droite (0,4 m) et loin du mur du bas (1,45 m) : le mur de droite reste le mur du dos
    colle = rm.coller_au_mur(_lit(7.9, 1.45), CHAMBRE)
    assert colle["position"][1] == 1.45 and abs(rm.orienter(colle, CHAMBRE) - 180.0) < 1e-6


def test_sans_mesure_le_mur_le_plus_proche_comme_avant():
    assert rm.axe_du_dos(_lit(7.177, 1.161, sens=None)) is None
    colle = rm.coller_au_mur(_lit(7.177, 1.161, sens=None), CHAMBRE)
    assert colle["position"][1] == 1.161 and abs(abs(rm.orienter(colle, CHAMBRE)) - 180.0) < 1e-6  # le mur de droite, 2 cm plus près


def test_un_canape_met_son_dos_le_long_de_son_grand_cote():
    # un canapé est plus large que profond : mesuré « grand côté le long de x », son dos va au mur du bas ou du haut
    canape = {"groupe": "canape", "categorie": "canape", "position": [7.6, 0.75], "distance_min": 2.5,
              "emprises": [_emprise(0.0), _emprise(0.0, 2.5)]}
    assert rm.axe_du_dos(canape) == 90.0
    assert abs(rm.orienter(rm.coller_au_mur(canape, CHAMBRE), CHAMBRE) - 90.0) < 1e-6  # mur de droite à 0,72 m, mur du bas à 0,75 m


def test_une_seule_photo_ne_suffit_pas_a_choisir_le_mur():
    # app-002, chambre 1 : un lit d'une place mesuré par UNE photo à 3 m, en travers de son vrai sens → on ne la croit pas
    lit = {"groupe": "lit", "categorie": "lit", "position": [7.177, 1.161], "distance_min": 2.9, "emprises": [_emprise(90.0, 3.0)]}
    assert rm.axe_du_dos(lit) is None
    # ni deux photos qui se contredisent
    lit["emprises"] = [_emprise(90.0), _emprise(90.0, 2.5), _emprise(0.0, 2.2)]
    assert rm.axe_du_dos(lit) is None
