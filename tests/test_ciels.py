"""Ciels photographiés (moteur/cinema/ciels.py) : réglage par éclairage et orientation du soleil de la photo."""
import math

from moteur.cinema import ciels


def test_ciel_seulement_de_jour_ensoleille():
    r = ciels.ciel_photo("jour_soleil", "D:/Atelya-Unreal/Paquets/ciels/")
    assert r["image"] == "D:/Atelya-Unreal/Paquets/ciels/" + ciels.CIELS["jour_soleil"]["fichier"]
    assert 0 <= r["soleil_u"] < 1
    assert ciels.ciel_photo("fin_de_journee", "x") is None  # un ciel de midi derrière une fin de journée serait faux
    assert ciels.ciel_photo("nuit", "x") is None


def test_le_soleil_de_la_photo_tombe_sur_le_vrai_soleil():
    """Avec le décalage, la colonne lue dans la direction du vrai soleil est celle du soleil de la photo (même formule que le
    matériau d'Unreal : u = azimut / 2π + décalage)."""
    for vers in [(1.0, 0.0, 0.5), (-0.3, -0.8, 0.6), (0.0, 1.0, 0.2)]:
        d = ciels.decalage(0.595, vers)
        u = (math.atan2(vers[1], vers[0]) / (2 * math.pi) + d) % 1.0
        assert abs(u - 0.595) < 1e-9
