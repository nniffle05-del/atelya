"""La vraie vue par les fenêtres, tirée des photos du client (moteur/vue_dehors.py, cinématique étape 5)."""
import numpy as np

from moteur import pellicule_unreal, photographe
from moteur import vue_dehors as vd


def _logement():
    """Deux pièces côte à côte (4 × 3 m et 3 × 3 m) : fenêtre au sud de la première, porte-fenêtre à l'ouest ; la seconde a une
    fenêtre au sud ; un mur plein entre les deux (sans porte)."""
    return {
        "hauteur_sous_plafond": 2.5,
        "murs": [
            {"id": "S1", "debut": [0, 0], "fin": [4, 0], "epaisseur": 0.2},
            {"id": "S2", "debut": [4, 0], "fin": [7, 0], "epaisseur": 0.2},
            {"id": "E", "debut": [7, 0], "fin": [7, 3], "epaisseur": 0.2},
            {"id": "N", "debut": [7, 3], "fin": [0, 3], "epaisseur": 0.2},
            {"id": "O", "debut": [0, 3], "fin": [0, 0], "epaisseur": 0.2},
            {"id": "C", "debut": [4, 0], "fin": [4, 3], "epaisseur": 0.1},
        ],
        "ouvertures": [
            {"id": "F1", "type": "fenetre", "mur": "S1", "position": 1.0, "largeur": 1.6, "hauteur": 1.3, "allege": 0.9},
            {"id": "F2", "type": "porte_fenetre", "mur": "O", "position": 0.8, "largeur": 1.4, "hauteur": 2.1, "allege": 0.0},
            {"id": "F3", "type": "fenetre", "mur": "S2", "position": 1.0, "largeur": 1.0, "hauteur": 1.3, "allege": 0.9},
        ],
        "pieces": [{"id": "a", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]},
                   {"id": "b", "contour": [[4, 0], [7, 0], [7, 3], [4, 3]]}],
    }


def test_ouvertures_normale_vers_le_dehors():
    o = {x["id"]: x for x in vd.ouvertures_vitrees(_logement())}
    assert set(o) == {"F1", "F2", "F3"}
    assert np.allclose(o["F1"]["n"], [0, -1])  # sud : dehors vers -y
    assert np.allclose(o["F2"]["n"], [-1, 0])  # ouest : dehors vers -x
    assert o["F1"]["z0"] == 0.9 and abs(o["F1"]["z1"] - 2.2) < 1e-9


def test_facades_une_par_cote_et_coin_de_rue():
    fs = {f["id"]: f for f in vd.facades(_logement(), {"facade-sud": 20.0, "facade-ouest": 30.0})}
    assert set(fs) == {"facade-sud", "facade-ouest"}
    sud, ouest = fs["facade-sud"], fs["facade-ouest"]
    assert sorted(sud["fenetres"]) == ["F1", "F3"]
    assert abs(sud["decalage"] - (0.1 + 20.0)) < 1e-9  # plan y = -20,1 : face extérieure du mur + 20 m
    # la toile ouest s'arrête au coin, sur la toile sud (y ≥ -20,1) ; la toile sud s'arrête sur la toile ouest (x ≥ -30,1)
    assert abs(ouest["u0"] - (-20.1)) < 1e-6
    coin_sud = sud["n"] * sud["decalage"] + sud["u"] * sud["u0"]
    coin_sud2 = sud["n"] * sud["decalage"] + sud["u"] * sud["u1"]
    assert abs(min(coin_sud[0], coin_sud2[0]) - (-30.1)) < 1e-6


def _camera_piece_a():
    # au milieu de la pièce a, à 1,5 m, face au sud (cap -90°), focale 500 px pour une photo 1000 × 700
    return [2.0, 2.2, 1.5, -90.0, 0.0, 500.0, 500.0, 350.0]


def test_masque_fenetre_vue_et_mur_qui_cache():
    log = _logement()
    ouv = vd.ouvertures_vitrees(log)
    murs = vd.murs_et_trous(log)
    vue, total = vd.masque_fenetres(_camera_piece_a(), (1000, 700), ouv, murs)
    assert vue.sum() > 20000  # la fenêtre F1 en face
    # le montant du milieu de la vraie fenêtre (x = 1,8 m, vu à droite du centre : u ≈ 500 + 500 × 0,2 / 2,2 ≈ 545) est retiré
    assert vue[:, 538:552].sum() == 0
    assert total[:, 538:552].sum() > 0
    # F3 (pièce b) est derrière la cloison C : jamais vue depuis la pièce a, même en regardant vers elle
    cam_vers_f3 = [2.0, 2.2, 1.5, -40.0, 0.0, 500.0, 500.0, 350.0]
    ouv_f3 = [o for o in ouv if o["id"] == "F3"]
    sans_murs, _ = vd.masque_fenetres(cam_vers_f3, (1000, 700), ouv_f3, None)
    avec_murs, _ = vd.masque_fenetres(cam_vers_f3, (1000, 700), ouv_f3, murs)
    assert sans_murs.sum() > 0 and avec_murs.sum() == 0


def test_meubles_devant_la_fenetre_ecartes():
    log = _logement()
    ouv = vd.ouvertures_vitrees(log)
    vue, _ = vd.masque_fenetres(_camera_piece_a(), (1000, 700), ouv, None, caches=[[300, 300, 700, 700]])
    assert vue[300:, 300:700].sum() == 0 and vue.sum() > 0


def test_couleur_avant_pellicule_retrouve_l_affichage():
    cible = np.array([[0.4, 0.6, 0.3], [0.9, 0.92, 0.95], [0.85, 0.7, 0.6], [0.5, 0.5, 0.5], [0.95, 0.95, 0.95]])
    e = vd.couleur_avant_pellicule(cible)
    affiche = pellicule_unreal.affiche(e, photographe.PELLICULE, **photographe.PELLICULE_COULEURS)
    assert np.abs(affiche - cible).max() < 1.0 / 255
    assert (e <= vd.FORCE_TOILE).all()  # tient dans l'image de la toile


def test_composer_une_photo_uniforme():
    log = _logement()
    ouv = vd.ouvertures_vitrees(log)
    image = np.full((700, 1000, 3), 200, np.uint8)
    image[:, :, 1] = 180  # mur et dehors un peu rosés : la teinte du mur est neutralisée
    ph = vd.preparer_photo(image, _camera_piece_a(), ouv, "bonne", vd.murs_et_trous(log), ecart_px=1.0)
    assert ph is not None
    ph["nom"] = "p"
    sud = next(f for f in vd.facades(log, 15.0) if f["id"] == "facade-sud")
    r = vd.composer(sud, [ph], pas=0.1, remplir=False)
    a = r["rvba"][..., 3]
    assert 0 < r["couverte"] < 0.2 and r["parts"] == {"p": 1.0}
    pleins = r["rvba"][a == 255][:, :3].astype(float)
    assert len(pleins) > 50
    assert np.ptp(pleins.mean(0)) < 2.0  # gris neutre
    assert (a == 0).mean() > 0.5  # sans remplissage : rien loin de ce que la photo voit
    # avec remplissage (défaut) : toute la toile est pleine, prolongée de la couleur vue (jamais de noir au bout)
    plein = vd.composer(sud, [ph], pas=0.1)["rvba"]
    assert (plein[..., 3] == 255).all()
    assert plein[..., :3].min() >= pleins.min() - 3


def test_vers_unreal_repere():
    sud = next(f for f in vd.facades(_logement(), 15.0) if f["id"] == "facade-sud")
    u = vd.vers_unreal(sud)
    assert abs(u["coin"][1] - 100 * 15.1) < 1e-6  # y d'Atelya = -15,1 m -> Y d'Unreal = +1510 cm
    assert abs(u["coin"][2] - 100 * vd.Z_HAUT_M) < 1e-6
    assert u["axe_v"] == [0.0, 0.0, -1.0]
    assert np.allclose(u["normale_vers_logement"], [0, -1, 0])  # vers +y d'Atelya = -Y d'Unreal
