"""Les baies lues sur les photos (moteur/ouvertures_photos.py) : une fenêtre du plan qui descend jusqu'au sol sur les photos."""
import numpy as np

from moteur import ouvertures_photos as op


def _logement(type_baie="fenetre"):
    """Une pièce de 4 × 3 m ; une baie de 1,2 m au milieu du mur de droite (x = 4), une porte dans le mur du bas."""
    mur = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2, "statut": "estime", "source": "essai"}
    baie = {"id": "O1", "type": type_baie, "mur": "M2", "position": 1.0, "largeur": 1.2, "statut": "estime", "source": "essai"}
    baie.update({"allege": 0.95, "hauteur": 1.25} if type_baie == "fenetre" else {"allege": 0.0, "hauteur": 2.15})
    porte = {"id": "O2", "type": "porte", "mur": "M1", "position": 1.0, "largeur": 0.8, "hauteur": 2.04, "allege": 0.0,
             "statut": "estime", "source": "essai"}
    return {"schema": "logement/0.1", "projet_id": "essai", "unites": "m", "hauteur_sous_plafond": 2.5,
            "murs": [mur("M1", (-0.1, -0.1), (4.1, -0.1)), mur("M2", (4.1, -0.1), (4.1, 3.1)), mur("M3", (4.1, 3.1), (-0.1, 3.1)),
                     mur("M4", (-0.1, 3.1), (-0.1, -0.1))],
            "ouvertures": [baie, porte],
            "pieces": [{"id": "sejour_1", "nom": "Séjour", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]], "statut": "estime",
                        "source": "essai"}]}


CAMERA = {"x": 1.0, "y": 1.5, "cap": 0.0}  # au milieu de la pièce, regarde le mur de droite (la baie est droit devant, à 3 m)


def _profil(sol_devant: int, creux_devant: int = 1):
    """Une photo qui voit 60° : un creux droit devant (de −9° à +9°), dont le bas est `sol_devant` (1 sol, −1 allège, 0 caché)."""
    phi = np.arange(-30, 31, dtype=float)
    devant = np.abs(phi) <= 9
    r = 3.0 / np.cos(np.radians(phi))  # la distance du mur de droite dans chaque direction
    return {"phi": phi, "r": r, "creux": np.where(devant, creux_devant, 0).astype(np.int8),
            "sol": np.where(devant, sol_devant, -1).astype(np.int8)}


def test_baie_vue_jusqu_au_sol_devient_porte_fenetre():
    lg = _logement()
    votes = op.votes_d_une_photo(_profil(1), CAMERA, lg)
    assert set(votes) == {"O1"} and votes["O1"][0] >= op.VOTES_MIN and votes["O1"][1] == 0
    apres, changes = op.corriger(lg, votes)
    baie = apres["ouvertures"][0]
    assert baie["type"] == "porte_fenetre" and baie["allege"] == 0.0 and 2.1 <= baie["hauteur"] <= 2.35
    assert "photos" in baie["source"] and [c["id"] for c in changes] == ["O1"]
    assert lg["ouvertures"][0]["type"] == "fenetre"  # le logement d'entrée n'est pas modifié


def test_baie_sur_allege_reste_fenetre():
    lg = _logement()
    votes = op.votes_d_une_photo(_profil(-1), CAMERA, lg)
    assert votes["O1"][0] == 0 and votes["O1"][1] >= op.VOTES_MIN
    assert op.corriger(lg, votes) == (lg, [])


def test_bas_cache_ou_pas_de_creux_ne_vote_pas():
    lg = _logement()
    assert op.votes_d_une_photo(_profil(0), CAMERA, lg) == {}  # un canapé devant la baie
    assert op.votes_d_une_photo(_profil(1, creux_devant=0), CAMERA, lg) == {}  # voilages : pas de creux vu


def test_trop_peu_de_votes_ne_change_rien():
    lg = _logement()
    assert op.corriger(lg, {"O1": [op.VOTES_MIN - 1, 0]}) == (lg, [])
    assert op.corriger(lg, {"O1": [5, 5]}) == (lg, [])  # les photos ne sont pas d'accord


def test_photo_mal_placee_ne_vote_pas():
    lg = _logement()
    loin = {**_profil(1), "r": _profil(1)["r"] + 1.5}  # la photo voit son mur 1,5 m plus loin que le plan : place douteuse
    assert op.votes_d_une_photo(loin, CAMERA, lg) == {}


def test_porte_fenetre_vue_sur_allege_redevient_fenetre_et_porte_jamais_touchee():
    lg = _logement("porte_fenetre")
    apres, changes = op.corriger(lg, {"O1": [0, 12], "O2": [0, 30]})
    assert apres["ouvertures"][0]["type"] == "fenetre" and apres["ouvertures"][0]["allege"] == op.ALLEGE_FENETRE
    assert apres["ouvertures"][1] == lg["ouvertures"][1] and len(changes) == 1
