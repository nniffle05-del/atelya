"""Le sens des lames de parquet (17/11/2026, NT : « pas ressemblants […] sur la direction du parquet ») : lu sur les photos,
porté par le sol jusqu'à la maquette ; chaque photo de parquet du catalogue posée dans le bon sens."""
import math

import numpy as np

from moteur import reconnaitre_sols as rs
from moteur import sens_des_lames as sl
from moteur.habillage import materiau_de, sens_par_defaut
from moteur.geometrie import calculer_briques
from moteur.logement import Logement
from moteur.matieres import LAMES_DROITES, ROTATION_PHOTO, echelle_du_nom, matiere_et_teinte, nom_materiau, sens_du_nom


def _joints(sens_deg: float, nombre: int, pas: float, longueur: float = 1.5, origine=(2.0, 2.0)) -> list[dict]:
    """Des joints parallèles (traits du sol), dans le sens donné, écartés de `pas`."""
    a = math.radians(sens_deg)
    le_long, en_travers = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    traits = []
    for k in range(nombre):
        m = np.array(origine) + k * pas * en_travers
        traits.append({"piece": "sejour_1", "a": tuple(m - le_long * longueur / 2), "b": tuple(m + le_long * longueur / 2),
                       "angle": sens_deg % 180.0, "longueur": longueur, "milieu": (float(m[0]), float(m[1]))})
    return traits


def test_le_sens_est_choisi_entre_les_deux_sens_des_murs():
    lames = _joints(88.0, 20, 0.12)  # vingt joints à 12 cm, presque le long de y (appareil placé à 2° près)
    table = _joints(0.0, 2, 0.9, longueur=2.0)  # deux bords de table, longs, dans l'autre sens
    choix = sl.sens_parmi(lames + table, (0.0, 90.0))
    assert choix["sens"] == 90.0 and choix["sur"]  # beaucoup de joints parallèles l'emportent sur deux longs traits
    assert abs(sl.largeur_des_lames(lames + table, 90.0)["largeur_m"] - 0.12) < 0.015
    # deux bords de table seuls : pas assez pour décider
    assert not sl.sens_parmi(table, (0.0, 90.0))["sur"]
    assert sl.sens_parmi([], (0.0, 90.0)) is None


def test_les_sens_des_murs_du_logement():
    logement = {"murs": [{"debut": [0, 0], "fin": [0, 8]}, {"debut": [0, 8], "fin": [3, 8]}, {"debut": [3, 8], "fin": [3, 0]}]}
    assert sl.axes_du_logement(logement) == (90.0, 0.0)


def test_le_point_du_sol_vu_par_un_pixel():
    from moteur.camera_photo import projeter

    cam = [1.0, 2.0, 1.4, 30.0, -10.0, 600.0, 600.0, 400.0]
    u, v, _ = projeter((4.0, 3.5, 0.0), cam)
    x, y = sl.vers_le_sol(u, v, cam)
    assert abs(float(x) - 4.0) < 1e-6 and abs(float(y) - 3.5) < 1e-6
    assert np.isnan(sl.vers_le_sol(600.0, 0.0, cam)[0])  # au-dessus de l'horizon : pas de sol


def test_le_nom_du_materiau_porte_le_sens():
    nom = nom_materiau("chene_clair_photo", (1.2, 1.0, 0.8), 0.84, 90.0)
    assert nom == "chene_clair_photo@0.84^90~1.20,1.00,0.80"
    assert matiere_et_teinte(nom) == ("chene_clair_photo", (1.2, 1.0, 0.8))
    assert echelle_du_nom(nom) == 0.84 and sens_du_nom(nom) == 90.0
    assert sens_du_nom("chene_clair_photo~1.20,1.00,0.80") is None and matiere_et_teinte("stratifie^0")[0] == "stratifie"
    assert nom_materiau("stratifie", None, None, 0.0) == "stratifie^0"  # un sens lu de 0° s'écrit (ce n'est pas « rien »)


def test_les_photos_de_parquet_sont_posees_dans_le_meme_sens():
    """Les photos dont les lames vont de haut en bas sont tournées d'un quart de tour ; les trois listes restent d'accord."""
    import importlib.util
    import sys
    import types
    from pathlib import Path

    from moteur import export_unreal as eu

    # Blender pose une image de sol avec sa largeur le long de l'axe y : ce sont les photos aux lames EN TRAVERS de l'image
    # (stratifié, chêne à l'anglaise dessiné…) qui sont tournées, pas celles aux lames de haut en bas (chêne clair, vieux parquet)
    assert ROTATION_PHOTO["stratifie"] == 90.0 and ROTATION_PHOTO["lames_chene_anglaise"] == 90.0
    assert "chene_clair_photo" not in ROTATION_PHOTO and "vieux_parquet" not in ROTATION_PHOTO
    assert eu.ROTATION_PHOTO == ROTATION_PHOTO
    texte = (Path(__file__).resolve().parents[1] / "moteur" / "blender" / "materiaux.py").read_text(encoding="utf-8")
    for nom, angle in ROTATION_PHOTO.items():
        assert f'"{nom}": {angle}' in texte, nom
    assert set(LAMES_DROITES) & {"parquet_diagonal", "parquet_rectangulaire", "point_de_hongrie"} == set()


def test_le_choix_d_un_parquet_a_lames_droites():
    e = np.array([1.0, 0.0])
    prototypes = {"parquet_diagonal": np.array([1.0, 0.0]), "stratifie": np.array([0.8, 0.6]), "vieux_parquet": np.array([0.6, 0.8]),
                  "chene_clair_moderne": np.array([0.95, 0.3]), "lames_chene_anglaise": np.array([0.7, 0.7]),
                  "chene_clair_photo": np.array([0.7, 0.7])}
    # ni le parquet « en diagonale » (un motif) ni les petites lamelles : pour des lames étroites, moyennes ou non mesurées,
    # le chêne à l'anglaise, ou le vieux parquet si c'est lui qui ressemble
    assert rs.choisir_matiere("lames", e, prototypes) == "lames_chene_anglaise"
    assert rs.choisir_matiere("lames", e, prototypes, largeur_lames=0.09) == "lames_chene_anglaise"
    assert rs.choisir_matiere("lames", np.array([0.0, 1.0]), prototypes, largeur_lames=0.09) == "vieux_parquet"
    # lames mesurées à 18 cm : parmi les parquets à larges lames, le plus ressemblant
    assert rs.choisir_matiere("lames", e, prototypes, largeur_lames=0.18) == "stratifie"
    # un catalogue sans le chêne à l'anglaise ni le vieux parquet : les autres lames droites restent possibles
    assert rs.choisir_matiere("lames", e, {"chene_clair_moderne": np.array([1.0, 0.0])}) == "chene_clair_moderne"


def _logement(contour, sol=None):
    x0, y0 = min(p[0] for p in contour), min(p[1] for p in contour)
    x1, y1 = max(p[0] for p in contour), max(p[1] for p in contour)
    mur = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2, "statut": "mesure", "source": "essai"}
    piece = {"id": "chambre_1", "nom": "Chambre", "contour": [list(p) for p in contour], "statut": "mesure", "source": "essai"}
    if sol:
        piece["sol"] = sol
    # un grand mur le long de x (20 m) : le sens général du logement est 0°
    return Logement.model_validate({
        "schema": "logement/0.1", "projet_id": "ESSAI", "hauteur_sous_plafond": 2.5,
        "murs": [mur("M0", (-10, y0 - 0.1), (10, y0 - 0.1)), mur("M1", (x0 - 0.1, y1 + 0.1), (x1 + 0.1, y1 + 0.1)),
                 mur("M2", (x0 - 0.1, y0 - 0.1), (x0 - 0.1, y1 + 0.1)), mur("M3", (x1 + 0.1, y0 - 0.1), (x1 + 0.1, y1 + 0.1))],
        "ouvertures": [], "pieces": [piece]})


def test_sans_photo_les_lames_suivent_le_grand_cote_de_la_piece():
    haute = _logement([(0, 0), (2.6, 0), (2.6, 4.8), (0, 4.8)])  # une chambre allongée en travers du sens général
    piece = haute.pieces[0]
    assert sens_par_defaut(piece, "chene_naturel_photo", haute) == 90.0
    assert sens_par_defaut(piece, "point_de_hongrie", haute) is None  # un motif garde le sens général
    sol = next(b for b in calculer_briques(haute) if b.id == "sol__chambre_1")
    assert materiau_de(sol, haute) == "chene_naturel_photo^90"
    large = _logement([(0, 0), (4.8, 0), (4.8, 2.6), (0, 2.6)])  # allongée dans le sens général : rien à dire
    assert sens_par_defaut(large.pieces[0], "chene_naturel_photo", large) is None
    # un sens LU sur les photos passe devant
    lu = _logement([(0, 0), (2.6, 0), (2.6, 4.8), (0, 4.8)],
                   {"matiere": "stratifie", "sens": 0.0, "statut": "estime", "source": "brique photos (2 photos pour la couleur)"})
    sol = next(b for b in calculer_briques(lu) if b.id == "sol__chambre_1")
    assert materiau_de(sol, lu) == "stratifie^0"
