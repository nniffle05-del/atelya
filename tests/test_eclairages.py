"""Les éclairages de la maquette (moteur/eclairages.py) : définitions, sans Blender."""
import math

from moteur.eclairages import AMBIANCE_DE_REFERENCE, AMBIANCES, ambiances


def test_cinq_ambiances_dans_l_ordre():
    assert [a["id"] for a in AMBIANCES] == ["jour_soleil", "jour_voile", "fin_de_journee", "soiree", "nuit"]
    assert AMBIANCES[0]["id"] == AMBIANCE_DE_REFERENCE  # la scène d'origine, où la teinte des sols est réglée
    assert len({a["nom"] for a in AMBIANCES}) == 5


def test_lampes_seulement_le_soir():
    assert [a["lampes"] for a in AMBIANCES] == [False, False, False, True, True]


def test_soleil_suit_la_direction_du_plan():
    # lumière venant du sud (elle va vers +y) : le soleil est vers -y, rotation de Blender ±180°
    for a in ambiances({"direction": [0.0, 0.7, -0.7]}):
        if a["ciel"] == "physique":
            assert abs(abs(a["rotation_soleil"]) - math.pi) < 1e-9
            assert a["elevation_soleil"] == math.radians(a["hauteur_soleil"])
    hauteurs = [a["hauteur_soleil"] for a in AMBIANCES if a["ciel"] == "physique"]
    assert hauteurs == sorted(hauteurs, reverse=True)  # le soleil descend du jour au crépuscule


def test_murs_neutres_de_jour_couleur_gardee_le_soir():
    par_id = {a["id"]: a for a in AMBIANCES}
    assert par_id["jour_soleil"]["balance"] >= 0.8 and par_id["jour_voile"]["balance"] >= 0.9
    assert par_id["fin_de_journee"]["balance"] < 0.5 and par_id["soiree"]["balance"] < 0.5
