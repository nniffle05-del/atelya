"""Où pend chaque pan de rideau épais le long du mur de sa fenêtre (22/11/2026, rideaux 2e temps, étape b).

Avant : chaque pan faisait 45 cm, à cheval sur le bord de la fenêtre (30 cm devant la baie, 15 cm sur le mur), quel que soit
le rideau de la photo. Or la photo montre tantôt un pan de 25 cm ramassé à côté de la fenêtre (app-004 : il ne doit cacher ni
le vantail ni le garde-corps), tantôt des pans de 60 à 90 cm à demi tirés devant une grande baie (chambres d'app-001).

Un pan (moteur.logement.PanDeRideau) porte maintenant, quand les photos l'ont mesuré :
- `largeur` : sa largeur le long du mur (m) ;
- `recouvre` : la part de cette largeur qui pend DEVANT la baie, comptée depuis le bord de la baie de son côté (m) ; le reste
  pend sur le mur, à côté de la fenêtre ;
- `etat` : « ouvert » (ramassé sur le côté : plis serrés) ou « tire » (déployé devant la fenêtre : plis larges).
Sans mesure, rien ne change : 45 cm, dont 30 devant la baie, ouvert.

Ce module est la SEULE règle de géométrie des pans : la maquette (moteur.habillage.rideaux_du_plan → moteur/blender/rideaux.py)
et le contrôle des collisions (moteur.collisions.nappes) la partagent. Aucune dépendance : il se lit aussi sans numpy.
"""
from __future__ import annotations

PAN_RIDEAUX = 0.45  # m : largeur d'un pan jamais mesuré
DEBORD_RIDEAUX = 0.15  # m : ce dont un pan jamais mesuré (et le voilage) dépasse le bord de la baie, sur le mur
PAN_MIN = 0.12  # m : un pan plus étroit n'est plus un rideau (un trait) : la mesure est écartée
DEBORD_MIN = 0.05  # m : un pan pend toujours jusqu'au bord de sa baie, et un peu au-delà (sinon la vitre se voit à côté de lui)
PAN_TIRE_M = 0.55  # m : un pan aussi large n'est plus « ramassé sur le côté » (un rideau ouvert tient dans 20 à 45 cm)
PART_TIREE = 1 / 3  # un pan qui pend devant plus du tiers de la baie est tiré
SOUS_PLAFOND = 0.12  # m : une tringle jamais mesurée est 12 cm sous le plafond (comme dans un ancien)…
AU_DESSUS = 0.30  # … et au moins 30 cm au-dessus de la fenêtre
AU_DESSUS_MIN = 0.05  # m : une tringle mesurée reste au moins 5 cm au-dessus du haut de sa baie
RAYON_TRINGLE = 0.012  # m : le tissu pend juste sous l'axe de la tringle


def etendue(demi: float, pan: dict | None) -> tuple[float, float]:
    """(bord intérieur, bord extérieur) d'un pan le long du mur, en mètres depuis le milieu de la baie, du côté du pan
    (toujours positifs : multiplier par −1 pour le côté « début »). `demi` : la demi-largeur de la baie ; `pan` : ses champs
    (`largeur`, `recouvre`), ou None pour un pan jamais mesuré."""
    largeur = float((pan or {}).get("largeur") or PAN_RIDEAUX)
    recouvre = (pan or {}).get("recouvre")
    if recouvre is None:  # largeur seule : il dépasse le bord de la baie comme un pan jamais mesuré, le reste devant la baie
        recouvre = max(0.0, largeur - DEBORD_RIDEAUX)
    recouvre = min(float(recouvre), 2 * demi)
    exterieur = max(demi - recouvre + largeur, demi + DEBORD_MIN)
    return demi - recouvre, exterieur


def etat(pan: dict | None, demi: float) -> str:
    """« ouvert » ou « tire » : ce que dit le pan, sinon ce que sa mesure montre (large, ou devant plus du tiers de la baie)."""
    if (pan or {}).get("etat"):
        return pan["etat"]
    if not (pan or {}).get("largeur"):
        return "ouvert"
    interieur, exterieur = etendue(demi, pan)
    return "tire" if exterieur - interieur >= PAN_TIRE_M or demi - interieur >= PART_TIREE * 2 * demi else "ouvert"


def cotes(pans: list[dict] | None) -> list[tuple[int, dict | None]]:
    """Les pans d'une fenêtre : [(sens, pan)] avec sens = −1 du côté du début du mur, +1 du côté de la fin. Sans `pans` (rien
    de vu sur les photos) : un pan jamais mesuré de chaque côté."""
    if not pans:
        return [(-1, None), (1, None)]
    par_cote = {(1 if p["cote"] == "fin" else -1): p for p in pans}
    return sorted(par_cote.items(), key=lambda c: c[0])


def haut_du_tissu(rideaux: dict | None, plafond: float, allege: float, hauteur: float) -> float:
    """La hauteur (m) du haut du tissu, juste sous la tringle (23/11/2026, étape c). `rideaux` : le champ `rideaux` de la
    fenêtre ; `plafond` : la hauteur du mur ; `allege`, `hauteur` : ceux de la baie. Une tringle MESURÉE sur les photos
    (`tringle.hauteur`) est à sa hauteur, au moins 5 cm au-dessus de la baie et sous le plafond ; jamais mesurée : 12 cm sous
    le plafond, au moins 30 cm au-dessus de la fenêtre (la règle d'avant)."""
    sous = plafond - 0.02
    mesuree = ((rideaux or {}).get("tringle") or {}).get("hauteur")
    if mesuree:
        return min(max(float(mesuree) - RAYON_TRINGLE, allege + hauteur + AU_DESSUS_MIN), sous)
    return max(min(plafond - SOUS_PLAFOND, sous), min(allege + hauteur + AU_DESSUS, sous))
