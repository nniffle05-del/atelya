"""Les luminaires suspendus trouvés sur les photos (moteur/objets_accroches.py) : les calculs, sans détecteur ni carte graphique."""
import numpy as np

from moteur import objets_accroches as oa
from moteur.ranger_meubles import chevauchements, ranger

W, H = 600, 400
CAMERA = {"x": 1.0, "y": 1.0, "z": 1.3, "cap": 0.0, "f": 300.0}  # regarde vers +x
LOGEMENT = {"hauteur_sous_plafond": 2.5, "pieces": [{"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]]}]}


def _repere(distance_lampe=2.0, hauteur_lampe=2.1):
    """Une photo mesurée : partout le mur du fond (à 4 m, à 1,3 m de haut), sauf un luminaire au milieu, plus près et plus haut."""
    h = np.full((H, W), 1.3, np.float32)
    r = np.full((H, W), 4.0, np.float32)
    phi = np.tile(np.linspace(30, -30, W, dtype=np.float32), (H, 1))  # + = à gauche
    h[40:120, 260:340], r[40:120, 260:340] = hauteur_lampe, distance_lampe
    return {"h": h, "phi": phi, "r": r, "M": np.ones((H, W), bool), "devant": np.ones((H, W), bool)}


def test_place_d_un_luminaire_par_la_profondeur():
    p = oa.place_dans_la_photo((255, 35, 345, 125), _repere(), CAMERA, W, H)
    assert abs(p["position"][0] - 3.0) < 0.05 and abs(p["position"][1] - 1.0) < 0.1  # 2 m devant l'appareil
    assert abs(p["bas"] - 2.1) < 0.05 and 0.4 < p["largeur"] < 0.9
    vide = {**_repere(), "M": np.zeros((H, W), bool)}
    assert oa.place_dans_la_photo((255, 35, 345, 125), vide, CAMERA, W, H) is None


def _objet(phrase="a pendant lamp", note=0.6, boite=(255, 35, 345, 125)):
    return {"sorte": "luminaire", "phrase": phrase, "note": note, "boite": list(boite)}


def test_un_luminaire_est_haut_et_dans_une_piece():
    assert len(oa.suspensions_d_une_photo([_objet()], _repere(), CAMERA, W, H, LOGEMENT, photo=0)) == 1
    assert oa.suspensions_d_une_photo([_objet()], _repere(hauteur_lampe=0.9), CAMERA, W, H, LOGEMENT) == []  # une lampe posée
    assert oa.suspensions_d_une_photo([_objet()], _repere(distance_lampe=3.9, hauteur_lampe=2.1), {**CAMERA, "x": 3.0}, W, H, LOGEMENT) == []  # hors de la pièce
    assert oa.suspensions_d_une_photo([_objet(phrase="a chair")], _repere(), CAMERA, W, H, LOGEMENT) == []
    assert oa.suspensions_d_une_photo([_objet(note=0.2)], _repere(), CAMERA, W, H, LOGEMENT) == []


def _vu(x, y, photo, note=0.6, bas=2.0, haut=2.4):
    return {"position": [x, y], "bas": bas, "haut": haut, "largeur": 0.5, "note": note, "photo": photo, "couleur": [200, 170, 120]}


def test_fusion_des_luminaires():
    assert len(oa.fusionner([_vu(3.0, 2.0, 0), _vu(3.4, 2.1, 1), _vu(3.2, 1.8, 2)])) == 1  # le même, vu sur trois photos
    assert len(oa.fusionner([_vu(3.0, 2.0, 0), _vu(3.7, 2.0, 0)])) == 2  # deux luminaires de la même photo
    assert len(oa.fusionner([_vu(3.0, 2.0, 0), _vu(3.3, 2.0, 0)])) == 1  # l'abat-jour et sa rosace : le même
    assert len(oa.fusionner([_vu(1.0, 1.0, 0), _vu(4.0, 3.0, 1)])) == 2


def test_vers_meubles_va_jusqu_au_plafond_et_ecarte_les_appliques():
    m, = oa.vers_meubles(oa.fusionner([_vu(3.0, 2.0, 0, bas=1.4, haut=1.9)]), LOGEMENT)  # mesuré trop bas : remonté
    assert m["categorie"] == "suspension" and m["altitude"] == 1.8 and abs(m["altitude"] + m["dimensions"][2] - 2.5) < 1e-6
    assert m["couleur"] == [200, 170, 120] and m["piece"] == "sejour_1" and m["statut"] == "estime"
    haut, = oa.vers_meubles(oa.fusionner([_vu(3.0, 2.0, 0, bas=2.45, haut=2.5)]), LOGEMENT)  # un plafonnier : 25 cm au moins
    assert haut["altitude"] == 2.25
    assert oa.vers_meubles(oa.fusionner([_vu(0.1, 2.0, 0, bas=1.7, haut=1.9)]), LOGEMENT) == []  # contre le mur, loin du plafond : une applique
    assert len(oa.vers_meubles(oa.fusionner([_vu(0.1, 2.0, 0, bas=2.2, haut=2.45)]), LOGEMENT)) == 1  # contre le mur mais au plafond


def test_une_suspension_au_dessus_d_une_table_ne_gene_personne():
    table = {"id": "t", "categorie": "table", "piece": "sejour_1", "position": [3.0, 2.0], "face": 0.0, "dimensions": [1.4, 0.8, 0.75],
             "statut": "estime", "source": "repérage photos (2 photo(s))", "confiance": 0.6}
    lampe, = oa.vers_meubles(oa.fusionner([_vu(3.0, 2.0, 0)]), LOGEMENT)
    ranges, actions = ranger([table, lampe], LOGEMENT)
    assert ranges == [table, lampe] and actions == [] and chevauchements(ranges) == []
