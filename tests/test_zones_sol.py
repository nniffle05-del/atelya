"""Zones de sol (un autre revêtement dans une pièce, sans mur ni trait), échelle du motif, réglage de la teinte au rendu
(B2 temps 2, app-001, 09/11/2026)."""


import numpy as np
import pytest
from pydantic import ValidationError

from moteur.geometrie import ZONE_SOL_Z, _couper_par_convexe, calculer_briques
from moteur.habillage import materiau_de, plan_habille
from moteur.logement import Logement
from moteur.matieres import echelle_du_nom, matiere_et_teinte, nom_materiau
from test_habillage import _aire, _piece_simple


def _avec_zones(zones, sol=None):
    donnees = _piece_simple().model_dump(by_alias=True, mode="json")
    piece = donnees["pieces"][0]
    piece["zones_sol"] = zones
    if sol:
        piece["sol"] = sol
    return Logement.model_validate(donnees)


def _sol(matiere, **plus):
    return {"matiere": matiere, "statut": "estime", "source": "photo", **plus}


def test_une_zone_de_sol_est_coupee_sur_la_piece_et_posee_au_dessus():
    """Une zone qui déborde de la pièce (sous les murs, dehors) est coupée sur son contour ; elle est posée un demi-millimètre
    au-dessus du sol de la pièce (à la même hauteur, les deux surfaces se disputent les points : taches noires)."""
    log = _avec_zones([{"contour": [[-1, 2], [5, 2], [5, 9], [-1, 9]], "sol": _sol("carreaux_cubes")}],
                      _sol("point_de_hongrie", echelle=1.13, teinte=[1.25, 0.93, 0.78]))
    briques = calculer_briques(log)
    zone = [b for b in briques if b.id.startswith("zone_sol__")]
    assert [b.id for b in zone] == ["zone_sol__sejour__1"]
    assert _aire(zone[0].contour) == pytest.approx(4 * 1, abs=1e-6)  # la bande y 2 → 3 de la pièce de 4 × 3 m
    assert zone[0].z_bas == zone[0].z_haut == ZONE_SOL_Z > 0
    sol = next(b for b in briques if b.id == "sol__sejour")
    assert _aire(sol.contour) == pytest.approx(12, abs=1e-6)  # le sol de la pièce reste entier, la zone est par-dessus
    assert materiau_de(zone[0], log) == "carreaux_cubes"
    assert materiau_de(sol, log) == "point_de_hongrie@1.13~1.25,0.93,0.78"


def test_une_zone_doit_etre_convexe():
    with pytest.raises(ValidationError, match="convexe"):
        _avec_zones([{"contour": [[0, 0], [2, 0], [2, 2], [1, 1], [0, 2]], "sol": _sol("tomettes")}])


def test_decoupe_d_une_piece_en_l():
    """Pièce en L (creux permis) coupée par un rectangle : la bonne surface, même quand le rectangle traverse le creux."""
    piece_l = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]  # 12 m²
    for rectangle, attendu in [([(1, 1), (5, 1), (5, 3), (1, 3)], 3 + 1), ([(-1, -1), (9, -1), (9, 9), (-1, 9)], 12),
                               ([(3, 3), (5, 3), (5, 5), (3, 5)], 0)]:
        morceau = _couper_par_convexe(piece_l, rectangle)
        aire = _aire(morceau) if len(morceau) >= 3 else 0.0
        assert aire == pytest.approx(attendu, abs=1e-6), rectangle


def test_nom_du_materiau_porte_echelle_et_teinte():
    nom = nom_materiau("chene_clair_photo", (1.57, 1.2, 1.02), 0.32)
    assert nom == "chene_clair_photo@0.32~1.57,1.20,1.02"
    assert matiere_et_teinte(nom) == ("chene_clair_photo", (1.57, 1.2, 1.02))
    assert echelle_du_nom(nom) == pytest.approx(0.32) and echelle_du_nom("tomettes") == 1.0
    assert nom_materiau("tomettes", None, 1.0) == "tomettes"  # échelle 1 : rien d'écrit


def test_reglage_de_teinte_pour_les_sols_vus_sur_photo():
    """Un sol avec sa couleur sur la photo du client → un réglage au rendu, caméra DANS la pièce qui regarde le sol."""
    log = _avec_zones([], _sol("point_de_hongrie", teinte=[1.2, 0.9, 0.8], couleur_photo=[0.45, 0.2, 0.08]))
    reglages = plan_habille(log)["reglages_teinte"]
    assert len(reglages) == 1
    r = reglages[0]
    assert r["materiau"] == "point_de_hongrie~1.20,0.90,0.80" and r["cible"] == [0.45, 0.2, 0.08]
    x, y, z = r["camera"]["position"]
    assert 0 < x < 4 and 0 < y < 3 and z == pytest.approx(1.5)
    assert r["camera"]["cible"][2] < z  # regarde vers le bas
    sans_photo = _avec_zones([], _sol("point_de_hongrie"))
    assert plan_habille(sans_photo)["reglages_teinte"] == []


def test_carreaux_dessines_se_raccordent():
    """Les carrelages dessinés par Atelya : posés bout à bout, le motif continue (même pixel de part et d'autre du bord)."""
    import importlib.util
    from pathlib import Path

    chemin = Path(__file__).parents[1] / "outils" / "bibliotheque" / "dessiner_carreaux.py"
    spec = importlib.util.spec_from_file_location("dessiner_carreaux", chemin)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    couleur, brillance, relief, taille = d.carreaux_cubes(cote_m=0.04, colonnes=3, rangs=4)
    assert couleur.shape[:2] == brillance.shape == relief.shape[:2]
    assert taille == pytest.approx((couleur.shape[1] / 1000, couleur.shape[0] / 1000))
    # le joint (gris foncé) occupe une petite part, les quatre couleurs sont présentes
    joint = np.all(couleur == d.CUBES_JOINT, axis=2).mean()
    assert 0.03 < joint < 0.25
    c, *_ = d.petits_carreaux_clairs(cote_m=0.05, n=4)
    assert c.shape == (200, 200, 3)
    # raccord : le joint du bord gauche et celui du bord droit forment ensemble UN joint de 2 mm (1 px de chaque côté)
    joint_bords = np.all(c[:, 0] == d.CLAIRS_JOINT, axis=1) & np.all(c[:, -1] == d.CLAIRS_JOINT, axis=1)
    assert joint_bords.all()
    # au milieu d'un carreau : du joint seulement là où passent les joints horizontaux (2 px par carreau de 50 px)
    assert np.all(c[:, 25] == d.CLAIRS_JOINT, axis=1).mean() == pytest.approx(2 / 50)
