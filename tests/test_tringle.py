"""La tringle d'une fenêtre d'après les photos (23/11/2026, rideaux 2e temps, étape c) : sa hauteur et sa couleur. Avant :
toujours 12 cm sous le plafond, toujours en métal sombre, alors que les photos d'app-004 montrent une tringle en acier brossé
gris clair, une vingtaine de centimètres sous le plafond."""
import numpy as np
import pytest

from moteur import collisions as co
from moteur import equipements as eq
from moteur import pans_rideaux as pr
from moteur.habillage import rideaux_du_plan
from moteur.logement import Logement
from tests.test_equipements import logement

MUR, TRINGLE, TISSU = (230, 228, 224), (120, 118, 114), (150, 140, 128)
BOITE = [200.0, 100.0, 260.0, 420.0]  # le rectangle du rideau lu sur la photo
PENTE = 0.10  # la tringle descend de 1 pixel tous les 10 pixels vers la droite


def photo(tringle: bool = True, corniche: bool = True, couleur=TRINGLE) -> np.ndarray:
    """Un mur clair, un pan de rideau (BOITE), sa tringle qui passe par le haut du pan et continue à droite au-dessus de la
    fenêtre, et une corniche 12 pixels plus haut (une MARCHE de clarté, pas un trait)."""
    img = np.empty((480, 640, 3), np.uint8)
    img[:] = MUR
    xs = np.arange(640)
    ligne = 100 + PENTE * (xs - 230)
    if corniche:
        for x in xs:
            img[:int(ligne[x]) - 12, x] = (212, 210, 206)
    x0, y0, x1, y1 = (int(c) for c in BOITE)
    img[y0:y1, x0:x1] = TISSU
    if tringle:
        for x in range(150, 520):
            y = int(round(ligne[x]))
            img[y - 1:y + 2, x] = couleur
    return img


def test_la_tringle_est_le_trait_fin_qui_passe_par_le_haut_du_tissu():
    t = eq.trait_de_la_tringle(photo(), BOITE, PENTE)
    assert t is not None and t["signe"] == "sombre"
    # le trait trouvé suit la tringle (à 2 pixels près à ses deux bouts), pas la corniche 12 pixels plus haut
    for x, y in (t["a"], t["b"]):
        assert abs(y - (100 + PENTE * (x - 230))) <= 2
    assert t["couleur"] == pytest.approx(TRINGLE, abs=6) and t["mur"] == pytest.approx(MUR, abs=6)


def test_la_pente_peut_etre_mal_prevue():
    """La pente vient du plan et de la place de l'appareil (connue à 30-50 cm) : fausse de 0,06, le trait est encore trouvé."""
    t = eq.trait_de_la_tringle(photo(), BOITE, PENTE + 0.06)
    assert t is not None and t["couleur"] == pytest.approx(TRINGLE, abs=25)


def test_une_corniche_n_est_pas_une_tringle():
    """Sans tringle visible (un rail caché, une tringle blanche sur un mur blanc) : la corniche, simple marche de clarté,
    n'est pas prise pour elle. Rien n'est mesuré : la tringle d'avant."""
    assert eq.trait_de_la_tringle(photo(tringle=False), BOITE, PENTE) is None
    assert eq.tringle_d_une_fenetre([{"tringle_vue": {"haut": None, "trait": None, "hauteur": None}}], 2.7) is None


def test_une_tringle_claire_sur_un_mur_de_couleur():
    img = photo(couleur=(245, 245, 242))
    img[np.all(img == MUR, axis=-1)] = (150, 160, 170)
    t = eq.trait_de_la_tringle(img, BOITE, PENTE)
    assert t is not None and t["signe"] == "clair" and t["couleur"] == pytest.approx((245, 245, 242), abs=6)


def test_le_haut_du_tissu_coupe_par_le_cadre_ne_dit_rien():
    assert eq.tringle_d_une_vue(photo(), [200.0, 4.0, 260.0, 420.0], None) is None


def vue(hauteur, haut=None, couleur=(120, 118, 114), mur=(190, 188, 184), dit=None) -> dict:
    trait = None if couleur is None else {"couleur": list(couleur), "mur": list(mur)}
    return {"dit": dit, "tringle_vue": {"haut": haut if haut is not None else hauteur, "hauteur": hauteur if trait else None, "trait": trait}}


def test_la_hauteur_est_la_mediane_des_traits_vus():
    t = eq.tringle_d_une_fenetre([vue(2.45), vue(2.61), vue(2.55), vue(None, haut=2.20, couleur=None)], 2.70)
    assert t["hauteur"] == pytest.approx(2.55)  # le haut du tissu (2,20 m) ne compte pas quand une photo montre le trait


def test_sans_trait_le_haut_du_tissu():
    t = eq.tringle_d_une_fenetre([vue(None, haut=2.31, couleur=None), vue(None, haut=2.35, couleur=None)], 2.70)
    assert t == {"hauteur": pytest.approx(2.33)}  # pas de couleur vue : le métal sombre d'avant


def test_un_trait_plus_haut_que_le_plafond_n_est_pas_une_tringle():
    """Coin repas d'app-001 : le relief de la photo met le haut du voilage à 3,46 m sous un plafond de 3,00 m, et le trait
    trouvé est le bord clair d'une corniche. Ni sa hauteur ni sa couleur ne sont gardées."""
    assert eq.tringle_d_une_fenetre([vue(3.46, couleur=(197, 190, 190), mur=(186, 182, 181))], 3.00) is None


def test_la_couleur_est_etalonnee_par_le_mur_blanc_autour():
    """La couleur gardée est la clarté de la tringle CONTRE le mur clair autour d'elle, pas sa couleur brute : la même tringle
    photographiée près d'un mur à l'ombre (190 sur 255) ou en pleine lumière (235) garde à peu près la même couleur. Un mur
    sombre ou coloré n'étalonne rien."""
    ombre = eq.tringle_d_une_fenetre([vue(2.5)], 2.7)["couleur"]
    lumiere = eq.tringle_d_une_fenetre([vue(2.5, couleur=(150, 148, 143), mur=(235, 233, 228))], 2.7)["couleur"]
    assert 115 <= ombre[0] <= 140 and ombre[0] > ombre[2] and abs(ombre[0] - lumiere[0]) <= 8
    assert eq.tringle_d_une_fenetre([vue(2.5, mur=(90, 100, 120))], 2.7)["couleur"] == [120, 118, 114]


def test_le_mot_de_la_lecture_fait_foi_pour_la_couleur():
    t = eq.tringle_d_une_fenetre([vue(2.5, dit="gris, ouverts, tringle noire")], 2.7)
    assert t["couleur"] == [30, 30, 32] and t["hauteur"] == pytest.approx(2.5)
    # la couleur du RIDEAU n'est pas celle de la tringle
    assert eq.tringle_d_une_fenetre([vue(2.5, dit="rideaux noirs")], 2.7)["couleur"] != [30, 30, 32]


def test_sans_mesure_la_tringle_d_avant():
    """12 cm sous le plafond, au moins 30 cm au-dessus de la fenêtre : la règle d'avant, au chiffre près."""
    for plafond, allege, hauteur in ((2.5, 0.0, 2.15), (2.7, 0.9, 1.25), (3.0, 0.0, 2.15), (2.4, 0.0, 2.25)):
        avant = max(min(plafond - 0.12, plafond - 0.02), min(allege + hauteur + 0.3, plafond - 0.02))
        assert pr.haut_du_tissu(None, plafond, allege, hauteur) == pytest.approx(avant)
        assert pr.haut_du_tissu({"rideaux": [1, 2, 3]}, plafond, allege, hauteur) == pytest.approx(avant)


def test_une_tringle_mesuree_reste_entre_la_baie_et_le_plafond():
    assert pr.haut_du_tissu({"tringle": {"hauteur": 2.40}}, 3.0, 0.0, 2.15) == pytest.approx(2.40 - pr.RAYON_TRINGLE)
    assert pr.haut_du_tissu({"tringle": {"hauteur": 2.00}}, 3.0, 0.0, 2.15) == pytest.approx(2.20)  # 5 cm au-dessus de la baie
    assert pr.haut_du_tissu({"tringle": {"hauteur": 3.20}}, 3.0, 0.0, 2.15) == pytest.approx(2.98)  # sous le plafond


def test_la_maquette_et_le_controle_des_collisions_suivent_la_tringle():
    lg = logement()
    for o in lg["ouvertures"]:
        if o["id"] == "baie":
            o["rideaux"] = {"rideaux": [150, 140, 130], "statut": "estime", "source": "lecture des photos (2 photo(s))",
                            "tringle": {"hauteur": 2.30, "couleur": [168, 160, 148]}}
    (r,) = rideaux_du_plan(Logement.model_validate(lg))
    assert r["z_tringle"] == pytest.approx(2.30 - pr.RAYON_TRINGLE) and r["couleur_tringle"] == [168, 160, 148]
    (f,) = co.fenetres_habillees(lg)
    assert f["z_tringle"] == pytest.approx(r["z_tringle"])
    assert all(n["z"][1] == pytest.approx(r["z_tringle"]) for n in co.nappes(f))
    # sans le champ : la tringle d'avant, sans couleur
    for o in lg["ouvertures"]:
        if o["id"] == "baie":
            del o["rideaux"]["tringle"]
    (r,) = rideaux_du_plan(Logement.model_validate(lg))
    assert r["couleur_tringle"] is None and r["z_tringle"] == pytest.approx(co.fenetres_habillees(lg)[0]["z_tringle"])
