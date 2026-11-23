"""Le bas et le haut d'une fenêtre lus sur les photos (23/11/2026, moteur/hauteur_baies.py) : par les lignes du sol, de la
menuiserie et du plafond du mur de la fenêtre, contrôlées par le relief de la photo ; un haut vu « au moins » (voilage) ne fait
que monter ; rien ne change quand les deux mesures ne s'accordent pas."""
import math

import numpy as np
import pytest

from moteur import dessin_fenetres, vitrages
from moteur import hauteur_baies as hb

HSP = 2.7


def photo_d_un_mur(bas: float, haut: float, biais: float = 35.0, tangage: float = 0.0, distance: float = 3.5, hauteur_appareil: float = 1.3,
                   focale: float = 520.0):
    """Une fenêtre (de `bas` à `haut` m, large de 1,2 m) dans un mur vu de biais, photographiée : rend (cadre, sol, plafond) en
    pixels. Appareil sans roulis, éventuellement penché (`tangage`, degrés, positif vers le haut)."""
    c, s = math.cos(math.radians(biais)), math.sin(math.radians(biais))
    t = math.radians(tangage)

    def pixel(le_long: float, z: float):
        # le mur passe à `distance` devant l'appareil et tourne de `biais` ; repère appareil : x à droite, y devant, z en haut
        x, y, zz = le_long * c, distance + le_long * s, z - hauteur_appareil
        y2, z2 = y * math.cos(t) + zz * math.sin(t), -y * math.sin(t) + zz * math.cos(t)  # penché autour de l'axe x
        return [600 + focale * x / y2, 400 - focale * z2 / y2]

    cadre = [pixel(-0.6, haut), pixel(0.6, haut), pixel(0.6, bas), pixel(-0.6, bas)]
    return cadre, [pixel(-1.5, 0.0), pixel(1.4, 0.0)], [pixel(-1.2, HSP), pixel(1.6, HSP)]


def fenetre(cadre, sol=None, plafond=None, **plus) -> dict:
    f = {"baie": "O1", "cadre": cadre, **plus}
    if sol is not None:
        f["sol"] = sol
    if plafond is not None:
        f["plafond"] = plafond
    return f


def logement(**baie) -> dict:
    return {"hauteur_sous_plafond": HSP,
            "ouvertures": [{"id": "O1", "type": "porte_fenetre", "mur": "M1", "position": 1.0, "largeur": 1.2, "hauteur": 2.15, "allege": 0.0,
                            "statut": "estime", "source": "lecture_claude", **baie}]}


@pytest.mark.parametrize("biais,tangage", [(0.0, 0.0), (35.0, 0.0), (-50.0, 0.0), (30.0, 6.0), (-20.0, -8.0)])
def test_les_lignes_donnent_le_bas_et_le_haut_sans_connaitre_l_appareil(biais, tangage):
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38, biais, tangage)
    n = hb.niveaux_d_une_photo([fenetre(cadre, sol, plafond)])
    assert n["bas"] * HSP == pytest.approx(0.35, abs=0.01) and n["haut"] * HSP == pytest.approx(2.38, abs=0.01)
    # un seul point du sol et un seul du plafond suffisent : leur ligne vise le point de fuite du mur
    n = hb.niveaux_d_une_photo([fenetre(cadre, sol[1], plafond[0])])
    assert n["bas"] * HSP == pytest.approx(0.35, abs=0.02) and n["haut"] * HSP == pytest.approx(2.38, abs=0.02)


def test_deux_photos_qui_se_completent():
    """L'une ne voit que le sol du mur, l'autre que son plafond (un lit devant) : ensemble elles disent tout."""
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38, 40.0)
    cadre2, sol2, plafond2 = photo_d_un_mur(0.35, 2.38, -25.0, distance=2.8)
    a = hb.niveaux_d_une_photo([fenetre(cadre, sol=sol)])
    b = hb.niveaux_d_une_photo([fenetre(cadre2, plafond=plafond2)])
    assert "bas" not in a and "dessous" in a and "dessus" in b
    accord = hb.accorder([{"photo": "p1", **a}, {"photo": "p2", **b}], HSP)
    assert accord["bas"] * HSP == pytest.approx(0.35, abs=0.01) and accord["haut"] * HSP == pytest.approx(2.38, abs=0.01)
    assert accord["par"] == "sol et plafond de deux photos"


def test_une_lecture_fausse_ne_mesure_rien():
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38)
    assert hb.niveaux_d_une_photo([fenetre(cadre)]) is None  # ni sol ni plafond
    assert hb.niveaux_d_une_photo([{"baie": "O1", "vue": "non"}]) is None  # pas de tour
    assert hb.niveaux_d_une_photo([fenetre(cadre, sol=plafond, plafond=sol)]) is None  # sol et plafond échangés


def test_la_baie_prend_le_bas_et_le_haut_des_photos():
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38)
    lecture = {"photos": {"photo-01": [fenetre(cadre, sol, plafond)]}}
    lg = logement()
    apres, changes, doutes = hb.corriger(lg, hb.lire(lg, lecture))
    o = apres["ouvertures"][0]
    assert (o["type"], o["allege"]) == ("fenetre", 0.35) and o["allege"] + o["hauteur"] == pytest.approx(2.38, abs=0.01)
    assert o["statut"] == "estime" and hb.mesuree(o) and "de 0.00 à 2.15 m" in o["source"]
    assert changes[0]["avant"] == {"type": "porte_fenetre", "allege": 0.0, "hauteur": 2.15} and not doutes
    assert lg["ouvertures"][0]["hauteur"] == 2.15  # le logement donné n'est pas touché
    # une baie refusée par une personne (écran de vérification) n'est jamais touchée
    assert hb.corriger(lg, hb.lire(lg, lecture), refusees={"O1"})[1] == []


def test_un_bas_pres_du_sol_descend_jusqu_au_sol_et_une_marche_reste_une_porte_fenetre():
    for bas, attendu in ((0.03, ("porte_fenetre", 0.0)), (0.17, ("porte_fenetre", 0.17)), (0.95, ("fenetre", 0.95))):
        cadre, sol, plafond = photo_d_un_mur(bas, 2.3)
        lg = logement()
        o = hb.corriger(lg, hb.lire(lg, {"photos": {"p": [fenetre(cadre, sol, plafond)]}}))[0]["ouvertures"][0]
        assert (o["type"], o["allege"]) == (attendu[0], pytest.approx(attendu[1], abs=0.011))
    # la sorte choisie par une personne à l'écran de vérification n'est pas changée ; sa hauteur, que personne ne règle, l'est
    cadre, sol, plafond = photo_d_un_mur(0.4, 2.3)
    lg = logement(source="verification")
    o = hb.corriger(lg, hb.lire(lg, {"photos": {"p": [fenetre(cadre, sol, plafond)]}}))[0]["ouvertures"][0]
    assert o["type"] == "porte_fenetre" and o["allege"] == pytest.approx(0.4, abs=0.011)


def test_un_petit_ecart_ne_change_rien():
    cadre, sol, plafond = photo_d_un_mur(0.02, 2.18)
    lg = logement()
    apres, changes, doutes = hb.corriger(lg, hb.lire(lg, {"photos": {"p": [fenetre(cadre, sol, plafond)]}}))
    assert apres == lg and not changes and not doutes


def mesure(par: str = "sol et plafond", **plus) -> dict:
    return {"O1": {"bas": 0.35 / HSP, "haut": 2.38 / HSP, "par": par, "photos": ["p"], "ecart_entre_photos": 0.0, **plus}}


def test_les_deux_cles_le_relief_doit_dire_la_meme_chose():
    lg = logement()
    assert hb.corriger(lg, mesure(relief={"bas": 0.31, "haut": 2.40}))[1]  # d'accord à 5 cm : la baie change
    apres, changes, doutes = hb.corriger(lg, mesure(relief={"bas": 0.31, "haut": 2.05}))  # le relief voit le haut 33 cm plus bas
    assert apres == lg and not changes and "relief" in doutes[0]["raison"]
    # une mesure complétée par le relief (un bout pris chez lui) ne vaut que si son autre bout la contrôle
    assert hb.corriger(lg, mesure("plafond et relief", relief={"bas": 0.35, "haut": 2.30}))[1]
    assert hb.corriger(lg, mesure("plafond et relief", relief={"bas": 0.35}))[1] == []
    assert hb.corriger(lg, mesure("sol et relief", relief={"bas": -0.5, "haut": 2.38}))[1] == []  # relief faux (bas sous le sol)


def test_des_photos_qui_ne_s_accordent_pas_ne_changent_rien():
    lg = logement()
    apres, changes, doutes = hb.corriger(lg, mesure(ecart_entre_photos=0.30))
    assert apres == lg and not changes and "s'accordent pas" in doutes[0]["raison"]
    assert hb.corriger(lg, {"O1": {**mesure()["O1"], "haut": 3.3 / HSP}})[2][0]["raison"].startswith("ce n'est pas")


def test_derriere_un_voilage_le_haut_vu_ne_fait_que_monter():
    """On ne voit les vitres que jusqu'au haut du tissu : la fenêtre monte AU MOINS jusque-là ; son bas caché reste."""
    cadre, sol, plafond = photo_d_un_mur(0.5, 2.6)
    vue = fenetre(cadre, sol, plafond, vue="voilee", haut_au_moins=True, bas_cache=True)
    lg = logement()
    mesures = hb.lire(lg, {"photos": {"p": [vue]}})
    assert mesures["O1"]["bas"] is None and mesures["O1"]["haut_au_moins"]
    o = hb.corriger(lg, mesures)[0]["ouvertures"][0]
    assert (o["type"], o["allege"]) == ("porte_fenetre", 0.0) and o["hauteur"] == pytest.approx(2.6, abs=0.01)
    assert not hb.mesuree(o)  # son bas n'a pas été mesuré : son dessin garde sa règle d'avant
    # un haut vu plus bas que celui de la baie ne l'abaisse pas
    cadre, sol, plafond = photo_d_un_mur(0.5, 1.9)
    bas_vu = hb.lire(lg, {"photos": {"p": [fenetre(cadre, sol, plafond, vue="voilee", haut_au_moins=True, bas_cache=True)]}})
    assert hb.corriger(lg, bas_vu)[1] == []
    # une photo qui voit le tour ENTIER fait foi sur celles qui n'en voient qu'une partie
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38)
    accord = hb.accorder([{"photo": "a", **hb.niveaux_d_une_photo([fenetre(cadre, sol, plafond)])},
                          {"photo": "b", "haut": 2.6 / HSP, "haut_au_moins": True, "bas_cache": True}], HSP)
    assert not accord.get("haut_au_moins") and accord["haut"] * HSP == pytest.approx(2.38, abs=0.01)


def test_le_relief_ne_lit_le_bas_que_sur_le_mur():
    """Un lit devant le bas de la fenêtre : le relief y est celui du lit (plus près de l'appareil), il ne compte pas."""
    H, W = 80, 120
    h = np.tile(np.linspace(HSP, 0.0, H)[:, None], (1, W))  # la hauteur baisse de haut en bas de l'image
    r = np.full((H, W), 3.5)
    repere = {"M": np.ones((H, W), bool), "h": h, "r": r}
    cadre = [[400, 200], [800, 200], [800, 600], [400, 600]]
    vu = hb.relief_d_une_photo(repere, [fenetre(cadre)], (1200, 800))
    assert vu["haut"] == pytest.approx(HSP * (1 - 196 / 800), abs=0.05) and vu["bas"] == pytest.approx(HSP * (1 - 604 / 800), abs=0.05)
    r[55:, :] = 2.2  # le lit : 1,3 m devant le mur, sous la fenêtre
    assert "bas" not in hb.relief_d_une_photo(repere, [fenetre(cadre)], (1200, 800))


def test_le_format_accepte_le_tour_seul_et_la_fenetre_voilee():
    cadre, sol, plafond = photo_d_un_mur(0.35, 2.38)
    lecture = {"format": vitrages.FORMAT, "photos": {"p": [fenetre(cadre, sol, plafond),  # tour seul : ni coins ni vue
                                                             {"baie": "O2", "vue": "voilee", "cadre": cadre, "haut_au_moins": True},
                                                             {"baie": "O3", "vue": "voilee"}]}}
    assert vitrages.controler(lecture) == []
    assert vitrages.d_une_photo(lecture, "p", (1200, 800)) == {}  # rien n'y est dit de la vue : comme avant
    assert vitrages.controler({"format": vitrages.FORMAT, "photos": {"p": [{"baie": "O1", "plafond": [10, 20]}]}})  # plafond sans tour
    assert "plafond" in vitrages.consigne() and "voilee" in vitrages.consigne()


def test_une_baie_mesuree_est_la_menuiserie_son_dessin_n_a_plus_de_partie_pleine():
    """Avant : la partie pleine sous la menuiserie était comptée DANS la baie (du sol). Mesurée, la baie commence à la menuiserie."""
    coins = [[440, 240], [760, 240], [760, 560], [440, 560]]
    vitrage = {"baie": "O1", "coins": coins, "cadre": [[420, 220], [780, 220], [780, 580], [420, 580]], "sol": [600, 640]}
    lg = {"hauteur_sous_plafond": HSP, "murs": [], "pieces": [],
          "ouvertures": [{"id": "O1", "type": "porte_fenetre", "mur": "M1", "position": 1.0, "largeur": 1.2, "hauteur": 2.2, "allege": 0.0}]}
    avant = dessin_fenetres.lire(lg, {"photos": {"p": [vitrage]}})["O1"]
    assert avant["soubassement"] > 0.1
    lg["ouvertures"][0].update(type="fenetre", allege=0.2, hauteur=2.0, source=f"{hb.MARQUE} lus sur 1 photo(s) du client)")
    assert dessin_fenetres.lire(lg, {"photos": {"p": [vitrage]}})["O1"]["soubassement"] == 0.0
