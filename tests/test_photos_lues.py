"""Les photos lues, posées par Atelya (essai du 16/11/2026) : la géométrie qui reste à Atelya quand Claude donne le sens."""
import math

import numpy as np

from moteur import caler_photos as cp
from moteur import meubles_photos
from moteur import photos_lues as pl
from moteur.ranger_meubles import ranger

# deux pièces de 4 × 3 m côte à côte, séparées par une cloison de 20 cm percée d'une porte ; une fenêtre au fond de la seconde
MUR = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
LOGEMENT = {
    "hauteur_sous_plafond": 2.5,
    "murs": [MUR("M1", (4.1, 0), (4.1, 3)), MUR("M2", (8.3, 0), (8.3, 3)), MUR("M3", (0, -0.1), (8.2, -0.1)), MUR("M4", (0, 3.1), (8.2, 3.1)),
             MUR("M5", (-0.1, 0), (-0.1, 3))],
    "ouvertures": [{"id": "O1", "type": "porte", "mur": "M1", "position": 1.0, "largeur": 0.9, "hauteur": 2.05},
                   {"id": "O2", "type": "fenetre", "mur": "M2", "position": 0.9, "largeur": 1.2, "allege": 0.95, "hauteur": 1.25}],
    "pieces": [{"id": "sejour_1", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]},
               {"id": "chambre_1", "contour": [[4.2, 0], [8.2, 0], [8.2, 3], [4.2, 3]]}],
}
PLAN = cp.plan_du_logement(LOGEMENT)
# appareil au milieu du séjour, à 1,30 m du sol, qui regarde vers l'est (cap 0), photo de 1200 × 800, focale 600 px
CAM = [1.0, 1.5, 1.3, 0.0, 0.0, 600.0, 600.0, 400.0]


def test_rayon_direction_et_pente():
    assert pl.rayon(CAM, 600, 400) == (0.0, 0.0)
    angle, pente = pl.rayon(CAM, 1200, 100)  # à droite de l'image = vers le sud (y décroît) ; en haut = le rayon monte
    assert round(angle) == -45 and pente > 0


def test_premier_mur_traverse_les_portes():
    # à hauteur de la porte (y de 1,0 à 1,9) : le rayon passe et touche le fond de la chambre, sur sa fenêtre (y de 0,9 à 2,1)
    d, sorte = pl.premier_mur(PLAN, [1.0, 1.5], 0.0)
    assert abs(d - 7.2) < 0.02 and sorte == 2
    # à côté de la porte : la cloison l'arrête
    d, sorte = pl.premier_mur(PLAN, [1.0, 2.5], 0.0)
    assert abs(d - 3.0) < 0.02 and sorte == 0


def test_premier_mur_appareil_dans_l_epaisseur_d_un_mur():
    # appareil relevé 5 cm DANS la cloison (photo prise dans l'embrasure) : sans les pièces il bute tout de suite, avec elles non
    assert pl.premier_mur(PLAN, [4.05, 2.5], 0.0)[0] < 0.3
    d, _ = pl.premier_mur(PLAN, [4.05, 2.5], 0.0, pieces=LOGEMENT["pieces"])
    assert abs(d - 4.15) < 0.11


def test_mur_le_plus_proche_est_la_face_que_l_on_voit():
    # un point tombé 5 cm DERRIÈRE la cloison (côté chambre) vu du séjour : la face retenue est celle du séjour (x = 4), pas celle
    # de la chambre (x = 4,2), pourtant plus proche
    q, n, d = pl.mur_le_plus_proche([4.25, 2.5], LOGEMENT, [1.0, 1.5])
    assert np.allclose(q, [4.0, 2.5]) and np.allclose(n, [-1.0, 0.0]) and abs(d - 0.25) < 1e-6


def test_au_mur_sans_profondeur_puis_meuble():
    # un tableau droit devant, à côté de la porte (rayon à y = 2,5 : pixel 600 − 600 × 1/3 = 400 de large → u = 400)
    objets = [{"sorte": "tableau", "boite": [370, 300, 430, 380], "note": 0.6}]
    vus = pl.au_mur_d_une_photo(objets, CAM, {}, PLAN, None, 1200, 800, LOGEMENT, photo=0)
    assert len(vus) == 1 and vus[0]["sur_le_mur"] and abs(vus[0]["position"][0] - 4.0) < 0.02 and abs(vus[0]["face"]) == 180
    assert vus[0]["bas"] < vus[0]["haut"]
    meubles = pl.vers_meubles_au_mur(pl.fusionner_au_mur(vus), LOGEMENT)
    assert [(m["categorie"], m["piece"]) for m in meubles] == [("tableau", "sejour_1")] and 0.6 <= meubles[0]["altitude"] <= 1.9
    assert meubles[0]["position"][0] < 4.0 and "repérage" in meubles[0]["source"]


def test_fusion_au_mur_meme_sorte_photos_differentes():
    v = lambda sorte, x, photo: {"sorte": sorte, "position": [x, 0.0], "face": 90.0, "bas": 1.2, "haut": 1.8, "largeur": 0.6, "note": 0.5,
                                 "photo": photo, "poids": 100.0, "couleur": None, "sur_le_mur": True}
    assert len(pl.fusionner_au_mur([v("tableau", 1.0, 0), v("tableau", 1.5, 1)])) == 1  # le même, vu de deux photos
    assert len(pl.fusionner_au_mur([v("tableau", 1.0, 0), v("tableau", 1.5, 0)])) == 2  # deux tableaux sur la même photo
    assert len(pl.fusionner_au_mur([v("tableau", 1.0, 0), v("miroir", 1.1, 1)])) == 2  # deux sortes


def test_les_baies_lues_votent_pour_la_baie_du_plan():
    # la fenêtre de la chambre, vue par la porte : rectangle autour du rayon droit devant
    lus = pl.baies_d_une_photo([{"sorte": "porte_fenetre", "boite": [560, 250, 640, 520], "note": 0.5}], CAM, PLAN, LOGEMENT)
    assert lus == {"O2": [1, 0]}
    lg, changes, desaccords = pl.corriger_les_baies(LOGEMENT, lus)
    assert [c["apres"] for c in changes] == ["porte_fenetre"] and desaccords == []
    assert next(o for o in lg["ouvertures"] if o["id"] == "O2")["allege"] == 0.0
    # à deux clés : la mesure du bas de la baie dit nettement « sur allège » → rien n'est changé, le désaccord est rendu
    lg, changes, desaccords = pl.corriger_les_baies(LOGEMENT, lus, {"O2": [1, 20]})
    assert changes == [] and desaccords[0]["id"] == "O2" and desaccords[0]["lu"] == "porte_fenetre"
    assert next(o for o in lg["ouvertures"] if o["id"] == "O2")["type"] == "fenetre"
    # égalité des lectures : rien
    assert pl.corriger_les_baies(LOGEMENT, {"O2": [1, 1]})[1] == []


def test_les_sols_lus_et_leur_application():
    releve = {"cameras": {"photo-01": {"camera": {"x": 1.0, "y": 1.5, "z": 1.3, "cap": 0.0, "f": 600.0}},
                          "photo-02": {"camera": {"x": 2.0, "y": 1.0, "z": 1.3, "cap": 90.0, "f": 600.0}},
                          "photo-03": {"camera": {"x": 6.0, "y": 1.5, "z": 1.3, "cap": 180.0, "f": 600.0}}}}
    lecture = {"photos": {"photo-01": {"sol": {"famille": "point_de_hongrie", "uniforme": True}},
                          "photo-02": {"sol": {"famille": "point_de_hongrie", "uniforme": False, "autre_famille": "carreaux"}},
                          "photo-03": {"sol": {"famille": None, "uniforme": True}}}}
    lus = pl.sols_lus(lecture, releve, LOGEMENT)
    assert lus == {"sejour_1": {"famille": "point_de_hongrie", "uniforme": False, "autres": ["carreaux"], "photos": 2}}
    brique = {"sejour_1": {"famille": "lames", "zones": [{"famille": "point_de_hongrie", "contour": []}, {"famille": "carreaux", "contour": []},
                                                         {"famille": "batons_rompus", "contour": []}]},
              "chambre_1": {"famille": "lames", "zones": []}}
    corrige = pl.appliquer_les_sols(brique, lus)
    # la famille lue prime ; la zone de la famille lue rejoint le sol, celle que personne n'a lue est retirée, « carreaux » reste
    assert corrige["sejour_1"]["famille"] == "point_de_hongrie" and [z["famille"] for z in corrige["sejour_1"]["zones"]] == ["carreaux"]
    assert corrige["sejour_1"]["famille_brique"] == "lames" and corrige["chambre_1"] is brique["chambre_1"]


def test_au_sol_sans_profondeur_comme_le_reperage_en_service():
    # une commode dont le pied (bas du rectangle) est à 2 m devant l'appareil : v = 400 + 600 × 1,3 / 2 = 790
    objets = [{"sorte": "commode", "boite": [540, 500, 660, 790], "note": 0.5, "forme": None},
              {"sorte": "cheminee", "boite": [100, 300, 200, 600], "note": 0.5}]  # un équipement n'est pas un meuble posé
    vus = pl.au_sol_d_une_photo(objets, CAM, 1200, 800, LOGEMENT["pieces"][0], photo=0)
    assert len(vus) == 1 and vus[0]["categorie"] == "commode" and vus[0]["groupe"] == "rangement"
    assert abs(vus[0]["position"][0] - (3.0 + 0.45 / 2)) < 0.05 and abs(vus[0]["position"][1] - 1.5) < 0.05


def test_fusion_par_sorte_exacte():
    v = lambda cat, groupe, x, photo: {"groupe": groupe, "categorie": cat, "position": [x, 0.0], "largeur_vue": 1.0, "confiance": 0.5,
                                       "poids": 1.0, "photo": photo, "forme": "ronde" if cat == "table" else None}
    vus = [v("bureau", "table", 0.0, 0), v("table", "table", 1.0, 1), v("table", "table", 1.4, 2)]
    # par groupe (comme en service) : tout se fond ; par sorte lue : un bureau et une table voisins restent deux meubles
    assert len(meubles_photos.fusionner(vus)) == 1
    par_sorte = meubles_photos.fusionner(vus, par_sorte=True)
    assert sorted(m["categorie"] for m in par_sorte) == ["bureau", "table"]
    assert next(m for m in par_sorte if m["categorie"] == "table")["forme"] == "ronde"
    # deux chevets de part et d'autre d'un lit (1,6 m) ne se fondent pas ; deux vues d'un long buffet (2 m d'écart), si
    chevets = [v("table_de_chevet", "rangement", 0.0, 0), v("table_de_chevet", "rangement", 1.6, 1)]
    assert len(meubles_photos.fusionner(chevets, par_sorte=True)) == 2
    buffet = [v("rangement", "rangement", 0.0, 0), v("rangement", "rangement", 2.0, 1)]
    assert len(meubles_photos.fusionner(buffet, par_sorte=True)) == 1


def test_la_forme_lue_donne_la_taille():
    assert meubles_photos.selon_la_forme("table", (1.4, 0.8, 0.75), "ronde") == (1.0, 1.0, 0.75)
    assert meubles_photos.selon_la_forme("lit", (1.6, 2.05, 1.0), "une place") == (0.9, 2.05, 1.0)
    assert meubles_photos.selon_la_forme("table", (1.4, 0.8, 0.75), None) == (1.4, 0.8, 0.75)
    assert meubles_photos.taille_courante("tabouret_haut")[2] == 1.0 and meubles_photos.taille_courante("colonne_cuisine")[2] == 2.2


def test_deux_sortes_lues_au_meme_endroit_restent_deux_meubles():
    """app-004 : l'armoire (3 photos) était retirée « au même endroit que la table de chevet » ; lues, ce sont deux vrais meubles."""
    piece = {"id": "chambre_1", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]}
    lg = {"pieces": [piece]}
    m = lambda i, cat, x, dims, source: {"id": i, "categorie": cat, "piece": "chambre_1", "position": [x, 0.35], "face": 90.0,
                                         "dimensions": dims, "statut": "estime", "source": source, "confiance": 0.5}
    lus = [m("a", "placard", 1.0, [1.5, 0.6, 2.2], "repérage par lecture des photos (3 photo(s))"),
           m("b", "table_de_chevet", 1.3, [0.45, 0.4, 0.55], "repérage par lecture des photos (2 photo(s))")]
    ranges, _ = ranger(lus, lg)
    assert sorted(x["categorie"] for x in ranges) == ["placard", "table_de_chevet"]
    # sans lecture (mot vague du détecteur) : la règle d'avant, un seul objet pris pour deux
    vagues = [dict(x, source=x["source"].replace("par lecture des photos", "photos")) for x in lus]
    assert len(ranger(vagues, lg)[0]) == 1
