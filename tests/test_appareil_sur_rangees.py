"""L'appareil d'une photo de cuisine repris sur les éléments rangés, en DERNIER RECOURS (moteur/appareil_sur_rangees.py, 28/11/2026).

Pourquoi ces tests : une photo de petite cuisine qui ne montre presque que des meubles (app-004, photo 05) laissait l'appareil à
1 m de sa place, face au flanc d'une colonne. Ici une cuisine fabriquée (une colonne puis un meuble bas le long d'un mur) est
« photographiée » par un appareil connu ; l'appareil est ensuite faussé, et la reprise doit le ramener.
"""
import math

from moteur import appareil_sur_rangees as ar
from moteur import caler_photos as cp

LARGEUR, HAUTEUR = 1200, 800
VRAI = {"x": 1.2, "y": 0.6, "z": 1.4, "cap": 90.0, "tangage": 0.0, "f": 500.0, "u0": 600.0, "v0": 400.0}
# le mur du fond (y = 3), de gauche à droite pour qui le regarde : le coin, une colonne, un meuble bas jusqu'à l'autre coin
RANGEES = [{"mur": {"repere": "vers", "numero": 2},  # le mur que touche le regard vers le meuble bas
            "suite": [{"sorte": "coin"}, {"sorte": "colonne_cuisine", "numeros": [1]}, {"sorte": "meuble_cuisine_bas", "reste": True, "numeros": [2]},
                      {"sorte": "coin"}]}]


def _logement() -> dict:
    murs = [((0, -0.1), (4, -0.1)), ((4.1, 0), (4.1, 3)), ((4, 3.1), (0, 3.1)), ((-0.1, 3), (-0.1, 0))]
    return {"hauteur_sous_plafond": 2.5, "pieces": [{"id": "cuisine_1", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]}],
            "murs": [{"id": f"m{i}", "debut": list(a), "fin": list(b), "epaisseur": 0.2} for i, (a, b) in enumerate(murs)], "ouvertures": []}


def _photo(camera: dict) -> dict[int, list[float]]:
    """Les rectangles que la lecture numéroterait sur la photo prise par `camera` : la colonne (1) et le meuble bas (2)."""
    logement = _logement()
    plan = cp.plan_du_logement(logement)
    amorce = {1: [200.0, 100.0, 400.0, 700.0], 2: [450.0, 500.0, 1200.0, 800.0]}  # seulement pour désigner le mur du fond
    els = ar.elements(RANGEES, amorce, camera, logement, plan)
    assert [e["sorte"] for e in els] == ["colonne_cuisine", "meuble_cuisine_bas"]
    return {k + 1: ar.prevu(ar._points(e), camera, LARGEUR, HAUTEUR) for k, e in enumerate(els)}


def test_les_bords_surs_sont_ceux_des_elements_hauts_et_de_leurs_voisins():
    logement = _logement()
    els = ar.elements(RANGEES, _photo(VRAI), VRAI, logement, cp.plan_du_logement(logement))
    colonne, bas = els
    assert colonne["surs"] == [True, True]  # rien ne cache une colonne
    assert bas["surs"] == [True, False]     # son bord contre la colonne se voit ; son autre bout est souvent caché
    assert abs(colonne["largeur"] - 0.6) < 1e-6 and abs(bas["largeur"] - 3.4) < 1e-6


def test_l_appareil_mal_place_revient_a_sa_place():
    # ce que la reprise sait faire : retrouver la PLACE d'un appareil bien orienté (l'orientation est la mesure la plus sûre du
    # calage). Elle ne sépare pas « glisser » de « tourner » : un appareil mal orienté de 6° reste à 25 cm de sa place.
    boites = _photo(VRAI)
    faux = {**VRAI, "x": VRAI["x"] + 0.5, "y": VRAI["y"] + 0.3}
    r = ar.affiner(faux, RANGEES, boites, LARGEUR, HAUTEUR, _logement())
    assert r is not None and r["garde"], r
    assert r["avant"] > 40 and r["apres"] < 10
    c = r["camera"]
    assert math.hypot(c["x"] - VRAI["x"], c["y"] - VRAI["y"]) < 0.15 and abs(c["cap"] - VRAI["cap"]) < 2.0


def test_un_appareil_deja_juste_n_est_pas_repris():
    r = ar.affiner(VRAI, RANGEES, _photo(VRAI), LARGEUR, HAUTEUR, _logement())
    assert r is not None and not r["garde"]  # il ne colle pas « nettement mieux » : l'appareil du calage reste
    assert math.hypot(r["camera"]["x"] - VRAI["x"], r["camera"]["y"] - VRAI["y"]) < 0.1


def test_les_lignes_lues_retiennent_l_appareil():
    # des lignes lues (ici : une fonction qui punit tout écart à la vraie place) l'emportent sur des rectangles de meubles faux
    boites = _photo({**VRAI, "x": VRAI["x"] + 0.6})  # des rectangles qui tireraient l'appareil 60 cm à côté
    sans = ar.affiner(VRAI, RANGEES, boites, LARGEUR, HAUTEUR, _logement())
    assert math.hypot(sans["camera"]["x"] - VRAI["x"], sans["camera"]["y"] - VRAI["y"]) > 0.4  # seuls, ils l'emmènent
    lignes = lambda c: 150.0 * math.hypot(c[0] - VRAI["x"], c[1] - VRAI["y"])  # noqa: E731
    r = ar.affiner(VRAI, RANGEES, boites, LARGEUR, HAUTEUR, _logement(), lignes=lignes)
    assert math.hypot(r["camera"]["x"] - VRAI["x"], r["camera"]["y"] - VRAI["y"]) < 0.15
