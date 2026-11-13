"""Brique photos branchée sur la 3D : blanc des murs trouvé seul, matière choisie, sols écrits dans le logement."""
import numpy as np

from moteur.blanc_des_murs import blanc_des_murs, ouvertures_sur_le_contour, points_des_murs
from moteur.reconnaitre_sols import choisir_matiere, sols_vers_logement

PIECE = {"id": "sejour", "contour": [[0, 0], [5, 0], [5, 4], [0, 4]]}
LOGEMENT = {
    "murs": [{"id": "M1", "debut": [0, -0.1], "fin": [5, -0.1], "epaisseur": 0.2},
             {"id": "M2", "debut": [5.1, 0], "fin": [5.1, 4], "epaisseur": 0.2}],
    "ouvertures": [{"id": "F1", "type": "fenetre", "mur": "M1", "position": 2.0, "largeur": 1.0, "hauteur": 1.4, "allege": 0.9}],
    "pieces": [PIECE],
}


def test_la_fenetre_est_reportee_sur_le_bon_bord_et_ecartee():
    ouv = ouvertures_sur_le_contour(LOGEMENT, PIECE["contour"])
    assert len(ouv) == 1 and ouv[0][0] == 0 and abs(ouv[0][1] - 2.0) < 1e-6 and abs(ouv[0][2] - 3.0) < 1e-6
    pts = points_des_murs(LOGEMENT, PIECE)
    sud = pts[np.abs(pts[:, 1]) < 0.05]
    assert len(sud) and not ((sud[:, 0] > 1.9) & (sud[:, 0] < 3.1)).any()  # rien devant la fenêtre (± 15 cm)
    assert (pts[:, 2] >= 1.3).all() and (pts[:, 2] <= 2.2).all()


def test_blanc_des_murs_d_une_photo_unie():
    # photo grise unie : le blanc trouvé est ce gris, en lumière linéaire
    photo = np.full((600, 800, 3), 200, np.uint8)
    cam = [2.5, 3.5, 1.3, -90.0, 0.0, 400.0, 400.0, 300.0]  # au nord de la pièce, regardant vers le sud
    r = blanc_des_murs(photo, cam, LOGEMENT, PIECE)
    attendu = ((200 / 255 + 0.055) / 1.055) ** 2.4
    assert r is not None and r["points"] > 5
    assert np.allclose(r["blanc"], attendu, atol=1e-3)


def test_choix_de_la_matiere_par_empreinte_dans_la_famille():
    protos = {"chene_clair_photo": np.array([1.0, 0, 0]), "stratifie": np.array([0, 1.0, 0]),
              "tomettes": np.array([0, 0, 1.0])}
    assert choisir_matiere("lames", [0.1, 0.9, 0.2], protos) == "stratifie"
    assert choisir_matiere("lames", [0.9, 0.1, 0.0], protos) == "chene_clair_photo"
    assert choisir_matiere("carreaux", [0.9, 0.1, 0.0], protos) == "tomettes"  # seule candidate de la famille
    assert choisir_matiere("point_de_hongrie", [1, 0, 0], protos) == "point_de_hongrie"
    assert choisir_matiere("lames", None, protos) == "chene_naturel_photo"


def test_sols_ecrits_dans_le_logement_sans_bibliotheque():
    resultat = {"pieces": {"sejour": {"famille": "carreaux", "part": 0.8, "photos_couleur": 2, "zones": [
        {"famille": "lames", "contour": [[0, 0], [2, 0], [2, 2], [0, 2]]}]}}}
    logement = {"pieces": [{**PIECE, "zones_sol": []}, {"id": "chambre", "contour": [[0, 4], [3, 4], [3, 7], [0, 7]],
                                                       "sol": {"matiere": "tomettes"}}]}
    sortie = sols_vers_logement(resultat, logement, None, None)
    s = sortie["pieces"][0]
    assert s["sol"]["matiere"] == "carrelage_interieur" and s["sol"]["statut"] == "estime" and s["sol"]["confiance"] == 0.8
    assert s["zones_sol"][0]["sol"]["matiere"] == "chene_naturel_photo"
    assert sortie["pieces"][1]["sol"] == {"matiere": "tomettes"}  # pièce non vue : inchangée
