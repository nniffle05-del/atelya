"""Le SOL et le PLAFOND dans le relief d'une photo (moteur.caler_photos.sol_et_plafond, 25/11/2026, « le sol pris pour un lit »).

Le relief d'une photo est fabriqué à la main : des hauteurs de points à plat (0 = l'appareil), une bosse par surface (sol, lit,
plafond, suspension…), dans une image de 800 000 points. On vérifie que le sol est la surface à plat la plus BASSE et le plafond
la plus HAUTE, que les garde-fous tiennent (bruit, rue vue par la fenêtre, pièce voisine, plafond à poutres, vide sur un étage),
et que `repere` remet bien les hauteurs entre le vrai sol et le vrai plafond.
"""
import numpy as np

from moteur import caler_photos as cp

PIXELS = 800_000


def relief(*surfaces, graine: int = 0):
    """Les hauteurs d'une image de PIXELS points : (niveau, nombre de points) par surface à plat ; le reste à 0 (ni sol ni plafond)."""
    rng = np.random.default_rng(graine)
    h = np.zeros(PIXELS, np.float32)
    i = 0
    for niveau, n in surfaces:
        h[i:i + n] = rng.normal(niveau, 0.012, n)
        i += n
    return h, np.ones(PIXELS, bool)


def test_un_lit_plus_grand_que_le_sol_n_est_pas_le_sol():
    h, plat = relief((-1.30, 40_000), (-0.75, 90_000), (1.40, 80_000))
    sol, plaf = cp.sol_et_plafond(h, plat, 2.7)
    assert abs(sol + 1.30) < 0.03 and abs(plaf - 1.40) < 0.03
    assert abs(cp._pic(h[h < -0.4]) + 0.75) < 0.03          # la règle d'avant prenait le lit


def test_un_coin_de_sol_suffit_quand_le_lit_remplit_l_image():
    # app-002 photo 11 : le vrai sol ne pèse que 17 % du lit (la règle « un quart » de la brique des appareils le manquait)
    h, plat = relief((-1.02, 15_000), (-0.48, 86_000), (1.32, 60_000))
    assert abs(cp.sol_et_plafond(h, plat, 2.5)[0] + 1.02) < 0.03


def test_sans_plafond_visible_le_sol_reste_le_plus_bas():
    h, plat = relief((-1.07, 5_000), (-0.65, 22_000))        # app-002 photo 13 : le banc de la douche
    sol, plaf = cp.sol_et_plafond(h, plat, 2.5)
    assert abs(sol + 1.07) < 0.03 and plaf is None


def test_un_bruit_plus_bas_que_le_sol_ne_compte_pas():
    h, plat = relief((-1.30, 100_000), (-1.80, 1_500), (1.40, 80_000))   # moins de 3 ‰ de l'image, moins de 10 % du sol
    assert abs(cp.sol_et_plafond(h, plat, 2.7)[0] + 1.30) < 0.03


def test_la_rue_vue_par_la_fenetre_n_est_pas_le_sol():
    h, plat = relief((-1.30, 100_000), (-6.0, 30_000), (1.40, 80_000))
    assert abs(cp.sol_et_plafond(h, plat, 2.7)[0] + 1.30) < 0.03


def test_le_sol_de_la_piece_voisine_est_le_meme_sol():
    # vu par une porte, le sol d'à côté sort quelques centimètres plus bas : c'est la même surface, on garde la plus fournie
    h, plat = relief((-1.30, 100_000), (-1.41, 14_000), (1.40, 80_000))
    assert abs(cp.sol_et_plafond(h, plat, 2.7)[0] + 1.30) < 0.03


def test_une_grande_suspension_n_est_pas_le_plafond():
    h, plat = relief((-1.08, 150_000), (1.04, 24_000), (2.40, 18_000))   # app-001 photo 01 : le disque de la suspension
    sol, plaf = cp.sol_et_plafond(h, plat, 3.0)
    assert abs(plaf - 2.40) < 0.03
    assert abs(cp._pic(h[h > 0.3]) - 1.04) < 0.03           # la règle d'avant prenait la suspension


def test_un_plafond_a_poutres_reste_une_seule_surface():
    h, plat = relief((-1.30, 50_000), (1.66, 14_000), (1.78, 13_000))    # dessous des poutres et plafond entre elles : 12 cm
    assert abs(cp.sol_et_plafond(h, plat, 2.9)[1] - 1.66) < 0.03         # la plus fournie, comme avant


def test_pour_la_ligne_du_mur_le_plafond_a_poutres_est_le_niveau_le_plus_haut():
    # l'affinage des appareils cherche où le MUR touche le plafond : il monte jusqu'au plafond, pas jusqu'au dessous des poutres
    # (app-003 photos 07 et 08, 25/11/2026 : appareil reculé de 0,7 m avec le niveau le plus fourni)
    h, plat = relief((-1.30, 50_000), (1.66, 14_000), (1.78, 13_000))
    assert abs(cp.sol_et_plafond(h, plat, 2.9, plafond_haut=True)[1] - 1.78) < 0.03
    # … sans rien changer au sol ni au garde-fou de la suspension
    h, plat = relief((-1.02, 15_000), (-0.48, 86_000), (1.04, 24_000), (1.48, 18_000))
    sol, plaf = cp.sol_et_plafond(h, plat, 2.5, plafond_haut=True)
    assert abs(sol + 1.02) < 0.03 and abs(plaf - 1.48) < 0.03


def test_un_vide_sur_un_etage_laisse_la_place_au_plafond_de_la_piece():
    h, plat = relief((-1.30, 100_000), (1.20, 60_000), (4.00, 30_000))   # 5,30 m du sol : pas la hauteur de cette pièce (2,50 m)
    assert abs(cp.sol_et_plafond(h, plat, 2.5)[1] - 1.20) < 0.03
    assert abs(cp.sol_et_plafond(h, plat, None)[1] - 4.00) < 0.03        # sans hauteur connue : le plus haut


def test_une_piece_ordinaire_ne_change_pas():
    h, plat = relief((-1.30, 100_000), (-0.75, 20_000), (-0.45, 9_000), (1.40, 80_000), (1.10, 6_000))
    sol, plaf = cp.sol_et_plafond(h, plat, 2.7)
    assert sol == cp._pic(h[h < -0.4]) and plaf == cp._pic(h[h > 0.3])   # au chiffre près, la règle d'avant


def _mesure(sol: float, lit: float, plafond: float) -> dict:
    """Ce que MoGe-2 verrait d'une chambre regardée droit devant : un sol, un grand lit, un plafond (appareil à l'origine)."""
    pts, nor = [], []
    rng = np.random.default_rng(1)
    for niveau, n in ((sol, 3_000), (lit, 9_000), (plafond, 6_000)):
        x, z = rng.uniform(-1.5, 1.5, n), rng.uniform(1.0, 4.0, n)
        pts.append(np.stack([x, np.full(n, -niveau), z], 1))   # repère de l'appareil : y vers le bas
        nor.append(np.tile([0.0, -1.0, 0.0], (n, 1)))
    P, N = np.concatenate(pts).astype(np.float32), np.concatenate(nor).astype(np.float32)
    cote = 300
    P, N = np.resize(P, (cote, cote, 3)), np.resize(N, (cote, cote, 3))
    return {"points": P, "normales": N, "masque": np.ones((cote, cote), bool), "haut": np.array([0.0, -1.0, 0.0])}


def test_repere_remet_les_hauteurs_entre_le_vrai_sol_et_le_vrai_plafond():
    mes = _mesure(sol=-1.30, lit=-0.75, plafond=1.40)
    R = cp.repere(mes, 2.70)
    assert abs(R["z"] - 1.30) < 0.03 and abs(R["ech"] - 1.0) < 0.02
    sur_le_lit = np.abs(mes["points"][..., 1] - 0.75) < 0.01
    assert abs(float(np.median(R["h"][sur_le_lit])) - 0.55) < 0.03       # le dessus du lit est à 55 cm du sol
    avant = cp.repere(mes, 2.70, juste=False)                            # la règle d'avant : le lit à 0, le relief étiré
    assert abs(float(np.median(avant["h"][sur_le_lit]))) < 0.03 and avant["ech"] > 1.2
