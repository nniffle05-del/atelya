"""La vraie taille des meubles libres, mesurée dans le relief des photos (étape 3, 17/11/2026).

Pourquoi ces tests : un canapé sortait toujours à 2,00 m et une table à 1,40 m (la taille courante de leur sorte). La mesure
compte, vus de dessus, les points du DESSUS du meuble (plateau d'une table, assise d'un canapé) ; ces tests fabriquent le relief
d'une pièce simple (sol, mur, un meuble) comme MoGe-2 le rendrait, et vérifient la taille retrouvée, puis les règles qui
réunissent les mesures de plusieurs photos.
"""
import math

import numpy as np

from moteur import meubles_photos as mp
from moteur import photos_lues as pl
from moteur import reperer_meubles as rm
from moteur.camera_photo import axes

LARGEUR, HAUTEUR, F = 1200, 800, 600.0
CAMERA = {"x": 0.0, "y": 0.0, "z": 1.4, "cap": 0.0, "tangage": -12.0, "f": F}
LOGEMENT = {"pieces": [{"id": "sejour_1", "contour": [[-1.0, -3.0], [6.0, -3.0], [6.0, 3.0], [-1.0, 3.0]]}], "hauteur_sous_plafond": 2.5}


def relief(boites: list[tuple], pas: int = 4, mur: float = 6.0) -> dict:
    """Le relief d'une pièce (sol, mur du fond) avec des boîtes posées au sol : [(x0, x1, y0, y1, hauteur)], vu par CAMERA.
    Même contenu que moteur.caler_photos.repere : hauteur, direction (+ = à gauche), distance à plat, surface à plat ou debout."""
    vue, droite, haut = axes(CAMERA["cap"], CAMERA["tangage"])
    us, vs = np.arange(pas / 2, LARGEUR, pas), np.arange(pas / 2, HAUTEUR, pas)
    U, V = np.meshgrid(us, vs)
    D = vue[None, None] + ((U - LARGEUR / 2) / F)[..., None] * droite - ((V - HAUTEUR / 2) / F)[..., None] * haut
    o = np.array([CAMERA["x"], CAMERA["y"], CAMERA["z"]])
    t = np.full(U.shape, np.inf)
    nh = np.zeros(U.shape)

    def toucher(tt, valide, plat):
        mieux = valide & (tt > 0) & (tt < t)
        t[mieux] = tt[mieux]
        nh[mieux] = plat

    with np.errstate(divide="ignore", invalid="ignore"):
        toucher(-o[2] / D[..., 2], D[..., 2] < 0, 1.0)  # le sol
        toucher((mur - o[0]) / D[..., 0], D[..., 0] > 0, 0.0)  # le mur du fond
        for x0, x1, y0, y1, z in boites:
            tt = (z - o[2]) / D[..., 2]  # son dessus
            P = o + tt[..., None] * D
            toucher(tt, (P[..., 0] >= x0) & (P[..., 0] <= x1) & (P[..., 1] >= y0) & (P[..., 1] <= y1), 1.0)
            tt = (x0 - o[0]) / D[..., 0]  # sa face de devant
            P = o + tt[..., None] * D
            toucher(tt, (P[..., 1] >= y0) & (P[..., 1] <= y1) & (P[..., 2] >= 0) & (P[..., 2] <= z), 0.0)
    P = o + t[..., None] * D
    return {"h": P[..., 2], "phi": np.degrees(np.arctan2(P[..., 1] - o[1], P[..., 0] - o[0])) - CAMERA["cap"],
            "r": np.hypot(P[..., 0] - o[0], P[..., 1] - o[1]), "M": np.isfinite(t), "devant": np.ones(U.shape, bool), "nh": nh}


def boite_a_l_image(x0, x1, y0, y1, z) -> list[float]:
    """Le rectangle qui encadre la boîte sur la photo."""
    from moteur.camera_photo import camera_depuis_dict, projeter

    cam = camera_depuis_dict({**CAMERA, "u0": LARGEUR / 2, "v0": HAUTEUR / 2})
    pts = [projeter((x, y, h), cam)[:2] for x in (x0, x1) for y in (y0, y1) for h in (0.0, z)]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def test_une_table_est_mesuree_par_son_plateau():
    table = (2.5, 3.4, -0.95, 0.95, 0.75)  # 1,90 m en travers du regard, 0,90 m le long
    e = pl.emprise_d_un_meuble(boite_a_l_image(*table), "table", relief([table]), CAMERA, LARGEUR, HAUTEUR, LOGEMENT)
    assert e is not None and not e["coupe"]
    assert abs(e["grand"] - 1.9) < 0.15 and abs(e["petit"] - 0.9) < 0.15
    assert abs((e["sens"] - 90.0 + 90.0) % 180.0 - 90.0) < 1.0  # son grand côté est le long de l'axe y
    assert math.dist(e["position"], (2.95, 0.0)) < 0.15
    assert abs(e["dessus"] - 0.75) < 0.03


def test_les_chaises_ne_grossissent_pas_la_table():
    table = (2.5, 3.4, -0.6, 0.6, 0.75)
    chaises = [(2.1, 2.5, -0.5, -0.1, 0.45), (2.1, 2.5, 0.1, 0.5, 0.45)]  # deux assises devant la table, à 45 cm du sol
    e = pl.emprise_d_un_meuble(boite_a_l_image(2.1, 3.4, -0.6, 0.6, 0.75), "table", relief([table, *chaises]), CAMERA, LARGEUR, HAUTEUR, LOGEMENT)
    assert e is not None and abs(e["grand"] - 1.2) < 0.15 and abs(e["petit"] - 0.9) < 0.15


def test_le_mur_derriere_un_canape_n_est_pas_compte():
    canape = (3.1, 4.0, -0.8, 0.8, 0.45)  # dos au mur du fond : 1,60 m de large
    boite = boite_a_l_image(3.1, 4.0, -0.8, 0.8, 0.9)  # son rectangle monte jusqu'au haut du dossier : il contient du mur
    e = pl.emprise_d_un_meuble(boite, "canape", relief([canape], mur=4.0), CAMERA, LARGEUR, HAUTEUR, LOGEMENT)
    assert e is not None and abs(e["grand"] - 1.6) < 0.2


def test_sans_surface_a_plat_rien_n_est_mesure():
    r = relief([])
    assert pl.emprise_d_un_meuble([500, 300, 700, 420], "table", r, CAMERA, LARGEUR, HAUTEUR, LOGEMENT) is None
    sans_inclinaison = {k: v for k, v in r.items() if k != "nh"}  # une mesure d'avant le 17/11/2026
    assert pl.emprise_d_un_meuble([500, 300, 700, 420], "canape", sans_inclinaison, CAMERA, LARGEUR, HAUTEUR, LOGEMENT) is None


def vue(grand, petit, distance=2.5, coupe=False, sens=0.0):
    return {"grand": grand, "petit": petit, "sens": sens, "distance": distance, "coupe": coupe, "position": [0, 0]}


def test_les_vues_entieres_et_proches_font_foi():
    t = mp.taille_mesuree("canape", [vue(1.56, 0.9), vue(1.68, 0.96), vue(2.9, 1.3, distance=6.4)])
    assert t["grand"] == 1.62 and t["vues"] == 2  # la médiane des deux vues proches ; la vue à 6,4 m ne compte pas
    assert mp.taille_mesuree("canape", [vue(2.9, 1.3, distance=6.4)]) is None


def test_une_vue_coupee_ne_peut_que_grandir():
    # seule, une vue coupée par le cadre montre un minimum : le canapé garde au moins la taille courante de sa sorte
    assert mp.taille_mesuree("canape", [vue(1.74, 0.87, coupe=True)])["grand"] == 2.0
    assert mp.taille_mesuree("canape", [vue(2.6, 0.9, coupe=True)])["grand"] == 2.6
    # à côté de vues entières, elle ne compte que si elle montre nettement plus
    assert mp.taille_mesuree("canape", [vue(1.6, 0.9), vue(1.68, 0.9, coupe=True)])["grand"] == 1.6
    assert mp.taille_mesuree("canape", [vue(2.28, 0.9), vue(2.7, 0.9, coupe=True)])["grand"] == 2.7


def test_table_ronde_lit_et_bornes():
    ronde = mp.taille_mesuree("table", [vue(0.9, 0.84)], forme="ronde")
    assert ronde["grand"] == ronde["petit"] == 0.87 and ronde["sens"] is None
    lit = mp.taille_mesuree("lit", [vue(2.1, 1.66)])
    assert (lit["grand"], lit["petit"]) == (2.1, 1.6)  # la largeur d'un lit : la taille courante la plus proche
    assert mp.taille_mesuree("lit", [vue(2.2, 1.02)])["petit"] == 0.9
    table = mp.taille_mesuree("table", [vue(1.8, 1.56)])  # le petit côté, vu le long du regard, est borné
    assert table["grand"] == 1.8 and table["petit"] == round(1.2 * 0.8, 2)
    assert mp.taille_mesuree("canape", [vue(5.0, 0.9)])["grand"] == 3.2  # jamais plus grand que sa sorte ne peut l'être


def test_une_table_est_tournee_un_canape_garde_son_dos():
    mesuree = {"grand": 1.98, "petit": 0.96, "sens": 0.0}
    dims, face = rm.selon_la_mesure("table", (1.4, 0.8, 0.75), 0.0, mesuree)  # posée en travers : son grand côté était à 90°
    assert dims == (1.98, 0.96, 0.75) and abs(abs(face) - 90.0) < 0.1
    dims, face = rm.selon_la_mesure("table", (1.4, 0.8, 0.75), 90.0, mesuree)  # déjà dans le bon sens
    assert face == 90.0
    dims, face = rm.selon_la_mesure("canape", (2.0, 0.9, 0.85), 0.0, mesuree)  # la mesure ne dit pas où est son dos
    assert dims == (1.98, 0.96, 0.85) and face == 0.0
    dims, face = rm.selon_la_mesure("lit", (1.6, 2.05, 1.0), 180.0, {"grand": 2.1, "petit": 1.4, "sens": 90.0})
    assert dims == (1.4, 2.1, 1.0) and face == 180.0
