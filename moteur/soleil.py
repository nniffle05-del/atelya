"""Le VRAI soleil d'un logement : sa direction et sa hauteur d'après l'orientation, le lieu, la date et l'heure (11/11/2026).

Pourquoi : règle 20 (NT) « moment flatteur oui, soleil inventé non ». Jusqu'ici la direction du soleil était PROVISOIRE
(habillage.SOLEIL_AZIMUT, 200°, sans rapport avec le logement). Il faut trois choses :
- l'ORIENTATION : où est le nord sur le plan (angle `nord_deg` du nord, compté depuis l'axe +y du plan, sens des aiguilles d'une
  montre : 0 = le haut du plan est au nord ; 90 = le nord est à droite du plan) ;
- le LIEU : latitude et longitude (la ville suffit, jamais l'adresse : RGPD) ;
- le MOMENT : date et heure légale (heure d'été comprise), choisis pour le client (« un après-midi d'avril »).
Calcul : formules de la NOAA (Global Monitoring Laboratory, « General Solar Position Calculations »), précises à quelques dixièmes
de degré, largement assez pour des taches de soleil ; aucune bibliothèque.

Repère d'Atelya (comme Blender) : x vers la droite du plan, y vers le haut, z vers le ciel. `vers_le_soleil` renvoie le vecteur
unitaire qui va du logement vers le soleil ; la lumière va dans l'autre sens.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

# Valeurs SUPPOSÉES tant que le client ne les donne pas (statut « ajoute » dans la fiche) : centre de la France, un 21 avril.
LIEU_DEFAUT = {"latitude": 46.6, "longitude": 2.4, "nom": "centre de la France (supposé)"}
DATE_DEFAUT = date(2026, 4, 21)
# Le moment de chaque éclairage : une heure légale, ou la hauteur du soleil voulue l'après-midi (« fin de journée » : soleil à 7° ;
# « soirée » : juste après le coucher, -3°). Voilé et nuit : pas de soleil.
MOMENTS = {"jour_soleil": {"heure": 15.0}, "fin_de_journee": {"hauteur": 7.0}, "soiree": {"hauteur": -3.0}}


def _decalage_heure_legale_france(jour: date) -> float:
    """+2 h en heure d'été (dernier dimanche de mars au dernier dimanche d'octobre), +1 h sinon."""
    def dernier_dimanche(mois):
        d = date(jour.year, mois, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    return 2.0 if dernier_dimanche(3) <= jour < dernier_dimanche(10) else 1.0


def position(latitude: float, longitude: float, quand_utc: datetime) -> tuple[float, float]:
    """(azimut, hauteur) du soleil en degrés : azimut compté depuis le nord vers l'est (90 = est, 180 = sud), hauteur au-dessus
    de l'horizon (négative la nuit). Formules NOAA."""
    jour_an = quand_utc.timetuple().tm_yday
    heures = quand_utc.hour + quand_utc.minute / 60 + quand_utc.second / 3600
    an_bissextile = quand_utc.year % 4 == 0 and (quand_utc.year % 100 != 0 or quand_utc.year % 400 == 0)
    g = 2 * math.pi / (366 if an_bissextile else 365) * (jour_an - 1 + (heures - 12) / 24)
    equation_temps = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                               - 0.040849 * math.sin(2 * g))
    declinaison = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
                   + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    temps_solaire = heures * 60 + equation_temps + 4 * longitude  # minutes
    angle_horaire = math.radians(temps_solaire / 4 - 180)
    lat = math.radians(latitude)
    cos_zenith = math.sin(lat) * math.sin(declinaison) + math.cos(lat) * math.cos(declinaison) * math.cos(angle_horaire)
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))
    hauteur = 90 - math.degrees(zenith)
    azimut = math.degrees(math.atan2(math.sin(angle_horaire),
                                     math.cos(angle_horaire) * math.sin(lat) - math.tan(declinaison) * math.cos(lat))) + 180
    return azimut % 360, hauteur


def a_l_heure(lieu: dict, jour: date, heure_legale: float) -> tuple[float, float]:
    h = heure_legale - _decalage_heure_legale_france(jour)
    quand = datetime(jour.year, jour.month, jour.day, tzinfo=timezone.utc) + timedelta(hours=h)
    return position(lieu["latitude"], lieu["longitude"], quand)


def heure_de_hauteur(lieu: dict, jour: date, hauteur: float, apres_midi: bool = True) -> float:
    """L'heure légale (en heures décimales) où le soleil passe à cette hauteur, l'après-midi (ou le matin)."""
    pas = [12 + k / 60 for k in range(0, 12 * 60)] if apres_midi else [12 - k / 60 for k in range(0, 12 * 60)]
    precedente = a_l_heure(lieu, jour, pas[0])[1]
    for h in pas[1:]:
        actuelle = a_l_heure(lieu, jour, h)[1]
        if (precedente - hauteur) * (actuelle - hauteur) <= 0:
            return h
        precedente = actuelle
    raise ValueError(f"le soleil ne passe pas à {hauteur}° ce jour-là")


def vers_le_soleil(azimut: float, hauteur: float, nord_deg: float = 0.0) -> list[float]:
    """Vecteur unitaire (repère du plan) qui va vers le soleil. nord_deg : direction du nord sur le plan (voir en tête)."""
    a = math.radians(azimut + nord_deg)  # angle compté depuis +y du plan, sens des aiguilles d'une montre
    h = math.radians(hauteur)
    return [math.cos(h) * math.sin(a), math.cos(h) * math.cos(a), math.sin(h)]


def soleils_des_eclairages(nord_deg: float, lieu: dict | None = None, jour: date | None = None) -> dict:
    """Pour chaque éclairage avec soleil : heure légale, azimut, hauteur, et la rotation / hauteur au format de Blender
    (moteur/eclairages : rotation 0 = soleil vers +y du plan, 90° = vers +x ; en radians), avec le repère choisi."""
    lieu, jour = lieu or LIEU_DEFAUT, jour or DATE_DEFAUT
    sortie = {}
    for ident, m in MOMENTS.items():
        heure = m["heure"] if "heure" in m else heure_de_hauteur(lieu, jour, m["hauteur"])
        az, h = a_l_heure(lieu, jour, heure)
        v = vers_le_soleil(az, h, nord_deg)
        sortie[ident] = {"heure_legale": round(heure, 3), "azimut_deg": round(az, 2), "hauteur_deg": round(h, 2),
                         "rotation_soleil": math.atan2(v[0], v[1]), "elevation_soleil": math.radians(h),
                         "vers_le_soleil": [round(c, 4) for c in v]}
    return sortie
