"""Brique photos : mise à plat du sol vu sur une photo (moteur/sol_a_plat.py)."""
import numpy as np

from moteur.sol_a_plat import assembler, dans_polygone, mettre_a_plat, projeter_sol, visibles_depuis

# Appareil à (2, 1), 1,3 m du sol, regardant vers +y (cap 90°), de niveau, focale 500 px, photo 800 x 600.
CAM = [2.0, 1.0, 1.3, 90.0, 0.0, 500.0, 400.0, 300.0]
PIECE = [[0, 0], [4, 0], [4, 6], [0, 6]]


def damier(X, Y, pas=0.1):
    """Sol en damier noir et blanc de 10 cm, en couleurs RGB."""
    case = ((np.floor(X / pas) + np.floor(Y / pas)) % 2).astype(np.uint8)
    return np.stack([case * 255] * 3, axis=-1)


def photographier(cam, largeur=800, hauteur=600):
    """La photo qu'aurait prise l'appareil d'un sol en damier (les pixels au-dessus de l'horizon restent gris)."""
    from moteur.camera_photo import axes
    x, y, z, cap, tangage, f, u0, v0 = cam
    vue, droite, haut = axes(cap, tangage)
    uu, vv = np.meshgrid(np.arange(largeur) + 0.0, np.arange(hauteur) + 0.0)
    d = vue[None, None] + ((uu - u0) / f)[..., None] * droite + (-(vv - v0) / f)[..., None] * haut
    descend = d[..., 2] < -1e-6
    t = np.where(descend, -z / np.where(descend, d[..., 2], -1), 0)
    photo = damier(x + t * d[..., 0], y + t * d[..., 1])
    photo[~descend] = 128
    return photo


def test_le_damier_revient_a_plat():
    vue = mettre_a_plat(photographier(CAM), CAM, PIECE, resolution=0.01)
    vus = vue.finesse > 0
    assert vus.sum() * 1e-4 > 4.0  # plus de 4 m² vus devant l'appareil
    lignes, colonnes = np.nonzero(vus)
    X, Y = vue.vers_sol(lignes, colonnes)
    attendu = damier(X, Y)[:, 0].astype(float)
    obtenu = vue.image[lignes, colonnes, 0].astype(float)
    loin_des_bords = (np.abs((X / 0.1) % 1 - 0.5) < 0.35) & (np.abs((Y / 0.1) % 1 - 0.5) < 0.35)
    assert np.mean(np.abs(obtenu - attendu)[loin_des_bords]) < 10  # chaque case retrouve sa couleur


def test_rien_derriere_l_appareil_et_finesse_decroit_au_loin():
    vue = mettre_a_plat(photographier(CAM), CAM, PIECE, resolution=0.02)
    lignes, colonnes = np.nonzero(vue.finesse > 0)
    X, Y = vue.vers_sol(lignes, colonnes)
    assert Y.min() > CAM[1]  # seulement devant
    _, _, _, f_pres = projeter_sol(np.array([2.0]), np.array([2.5]), CAM)
    _, _, _, f_loin = projeter_sol(np.array([2.0]), np.array([5.5]), CAM)
    assert f_pres[0] > 3 * f_loin[0]


def test_un_mur_de_la_piece_cache_le_sol_derriere_lui():
    # Pièce en L : l'appareil, en bas à gauche, ne voit pas le fond de la branche de droite, derrière l'angle.
    en_l = [[0, 0], [2, 0], [2, 3], [5, 3], [5, 5], [0, 5]]
    X, Y = np.array([1.0, 4.5, 1.5]), np.array([4.0, 4.5, 2.0])
    assert list(dans_polygone(X, Y, en_l)) == [True, True, True]
    vus = visibles_depuis(X, Y, (1.0, 0.5), en_l)
    assert list(vus) == [True, False, True]


def test_assembler_prend_la_photo_la_plus_fine():
    cam1 = [2.0, 1.0, 1.3, 90.0, 0.0, 300.0, 400.0, 300.0]  # objectif large : le sol proche entre dans le cadre
    cam2 = [2.0, 5.5, 1.3, -90.0, 0.0, 300.0, 400.0, 300.0]  # en face, regardant vers -y
    a = mettre_a_plat(photographier(cam1), cam1, PIECE, emprise=(0, 0, 4, 6), resolution=0.05)
    b = mettre_a_plat(photographier(cam2), cam2, PIECE, emprise=(0, 0, 4, 6), resolution=0.05)
    _, finesse, choix = assembler([a, b])
    l_bas, l_haut = int((6 - 2.5) / 0.05), int((6 - 4.0) / 0.05)  # y = 2,5 m (près de a) et y = 4 m (près de b)
    assert choix[l_bas, 40] == 0 and choix[l_haut, 40] == 1  # chacun le côté proche de lui
    assert (finesse > 0).mean() > (a.finesse > 0).mean()
