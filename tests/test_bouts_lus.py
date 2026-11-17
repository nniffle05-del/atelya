"""Les BOUTS des grands meubles adossés, dits par la lecture des photos (17/11/2026, essai « vas-y » de NT ; lecture-photos/0.3) :
« jusqu'au coin », « touche tel rectangle », « sort du cadre », « le rectangle le montre entier », « pied caché »."""
import math

from moteur import caler_photos as cp
from moteur import lecture_photos as lp
from moteur import meubles_photos as mp
from moteur import photos_lues as pl

MUR = lambda i, a, b: {"id": i, "debut": list(a), "fin": list(b), "epaisseur": 0.2}
LOGEMENT = {"hauteur_sous_plafond": 2.5,
            "murs": [MUR("M1", (10.1, 0), (10.1, 6)), MUR("M3", (0, -0.1), (10, -0.1)), MUR("M4", (0, 6.1), (10, 6.1)), MUR("M5", (-0.1, 0), (-0.1, 6))],
            "ouvertures": [], "pieces": [{"id": "sejour_1", "contour": [[0, 0], [10, 0], [10, 6], [0, 6]]}]}
PLAN = cp.plan_du_logement(LOGEMENT)
# appareil au milieu de la pièce, qui regarde le mur nord (cap 90) ; photo de 1200 × 800, focale 600 px.
# À l'image, la GAUCHE est l'ouest (x petit) : le pixel 350 vise x = 4, le pixel 850 vise x = 6 sur la ligne des meubles.
CAM = [5.0, 3.0, 1.3, 90.0, 0.0, 600.0, 600.0, 400.0]
LISTE = [{"numero": 1, "boite": [350, 300, 850, 700], "note": 0.5, "detecteur": "cuisine", "phrase": "x"},
         {"numero": 2, "boite": [100, 100, 300, 700], "note": 0.5, "detecteur": "cuisine", "phrase": "x"},
         {"numero": 3, "boite": [900, 500, 1000, 600], "note": 0.5, "detecteur": "cuisine", "phrase": "x"}]


def test_les_notes_et_le_controle():
    fiche = lp.fiche_depuis_notes("1 meuble_cuisine_bas gris, linéaire du fond {g=d2 d=coin pied} ; 2 colonne_cuisine grise ; 3 rangement {entier}",
                                  manquants="placard 10,20,300,700 armoire {g=cadre d=u300}")
    un = fiche["objets"]["1"]
    assert (un["gauche"], un["droite"], un["pied_cache"]) == ("d2", "coin", True)
    assert un["note"] == "gris, linéaire du fond" and un["couleur"] == "gris"  # les repères ne restent pas dans ce qu'on en dit
    assert fiche["objets"]["3"]["gauche"] == fiche["objets"]["3"]["droite"] == "bord"
    assert fiche["manquants"][0]["gauche"] == "cadre" and fiche["manquants"][0]["droite"] == "u300"
    assert lp.controler(fiche, {1, 2, 3}) == []
    faux = {"objets": {"1": {"sorte": "rangement", "gauche": "d9"}, "2": {"sorte": "rangement", "droite": "jusqu'au bout"},
                       "3": {"sorte": "rangement"}}}
    defauts = lp.controler(faux, {1, 2, 3})
    assert len(defauts) == 2 and "numéro 9" in defauts[0] and "illisible" in defauts[1]


def test_les_bouts_prets_pour_la_geometrie():
    fiche = lp.fiche_depuis_notes("1 meuble_cuisine_bas {g=d2 d=coin pied} ; 2 colonne_cuisine {g=cadre} ; 3 rangement {entier}")
    lus = {o["numero"]: o for o in lp.objets_lus(fiche, LISTE)}
    assert lus[1]["bouts"] == {"gauche": 300.0, "droite": "coin"} and lus[1]["pied_cache"]  # le bord droit du rectangle 2
    assert lus[2]["bouts"] == {"gauche": "cadre"}
    assert lus[3]["bouts"] == {"gauche": 900.0, "droite": 1000.0}  # ses propres bords, confirmés
    # une fiche sans repère (0.1, 0.2) se lit comme avant
    sans = lp.objets_lus(lp.fiche_depuis_notes("1 meuble_cuisine_bas ; 2 colonne_cuisine ; 3 rangement"), LISTE)
    assert all("bouts" not in o and "pied_cache" not in o for o in sans)


def test_jusqu_au_coin():
    # un linéaire dont l'îlot ne laisse voir qu'un morceau (x de 4 à 6) : la lecture dit qu'il file jusqu'au coin de droite (est)
    morceau = pl.contre_le_mur((5.0, 5.67), "meuble_cuisine_bas", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67)
    assert abs(morceau["largeur_mur"] - 2.0) < 0.15 and "mur_lu" not in morceau
    lu = pl.contre_le_mur((5.0, 5.67), "meuble_cuisine_bas", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67, bouts={"droite": "coin"})
    assert lu["mur_lu"] and not lu["coupe_mur"]
    assert abs(lu["largeur_mur"] - 6.0) < 0.15 and abs(lu["position"][0] - 7.0) < 0.1  # de x = 4 au coin x = 10
    # « coin » à gauche : jusqu'au coin ouest ; des deux côtés : tout le mur, plus large que les meubles courants de sa sorte
    assert abs(pl.contre_le_mur((5.0, 5.67), "meuble_cuisine_bas", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67,
                                bouts={"gauche": "coin"})["position"][0] - 3.0) < 0.1
    tout = pl.contre_le_mur((5.0, 5.67), "meuble_cuisine_bas", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67,
                            bouts={"gauche": "coin", "droite": "coin"})
    assert abs(tout["largeur_mur"] - 10.0) < 0.01 and math.dist(tout["position"], (5.0, 5.67)) < 0.05


def test_un_bout_donne_en_pixels_ou_hors_du_cadre():
    # le bout droit, caché, est à peu près au pixel 1100 (x = 7) : le meuble va de 4 à 7
    lu = pl.contre_le_mur((5.0, 5.67), "rangement", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67, bouts={"droite": 1100.0})
    assert abs(lu["largeur_mur"] - 3.0) < 0.2 and abs(lu["position"][0] - 5.5) < 0.15
    # il sort de la photo à droite : mesuré jusqu'au bord de l'image, et marqué « coupé » (sa largeur est un minimum)
    sorti = pl.contre_le_mur((5.0, 5.67), "rangement", [350, 300, 850, 700], CAM, LOGEMENT, 1200, 2.67, bouts={"droite": "cadre"})
    assert sorti["coupe_mur"] and sorti["largeur_mur"] > 3.0


def test_une_vue_aux_bouts_lus_fait_foi_entre_les_photos():
    def vue(photo, large, appareil, lu=False, x=5.0):
        v = {"groupe": "rangement", "categorie": "rangement", "position": [x, 5.77], "appareil": appareil, "photo": photo,
             "distance": math.dist((x, 5.77), appareil), "confiance": 0.5, "poids": 2.0, "largeur_vue": 0.5, "piece": "sejour_1",
             "largeur_mur": large, "coupe_mur": False, "normale": [0.0, -1.0]}
        if lu:
            v["mur_lu"] = True
        return v
    # trois vues proches sans mesure sur le mur ne font plus retomber le buffet à sa largeur courante : la vue lue l'emporte
    sans_mur = [{k: v for k, v in vue(p, 0, [5.0, 3.0 + 0.2 * p]).items() if k not in ("largeur_mur", "coupe_mur", "normale")} for p in (0, 1, 2)]
    lue = vue(3, 2.25, [5.0, 1.5], lu=True)
    trouve = mp.associer(sans_mur + [lue])
    assert len(trouve) == 1 and trouve[0]["largeur_mur"] == 2.25 and trouve[0]["mur_lu"]
    # et elle l'emporte sur une vue plus proche qui n'en montre qu'un bout
    assert mp.associer([vue(0, 0.9, [5.0, 3.5]), lue])[0]["largeur_mur"] == 2.25
