"""Les réglages du générateur : toutes les distributions en un seul endroit, modifiables par un fichier JSON.

Une « distribution » dit avec quelle fréquence on tire chaque valeur : par exemple
`{"T2": 0.3, "T3": 0.3}` veut dire « un T2 trois fois sur dix ». Les longueurs sont
en millimètres entiers (le générateur calcule en millimètres pour éviter les erreurs
d'arrondi), les surfaces en mètres carrés.

Pour changer un réglage sans toucher au code : écrire un fichier JSON qui ne contient
que les clés à changer, et le passer avec `--reglages mon_fichier.json`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# ---- Types de logements et leurs programmes ----

# Fréquence de chaque type. « studio » : une pièce principale et une salle d'eau ;
# « chambre » : une chambre indépendante (chambre + salle d'eau, parfois une entrée).
TYPES = {"studio": 0.08, "chambre": 0.04, "T1": 0.10, "T2": 0.26, "T3": 0.26, "T4": 0.17, "T5": 0.09}
CHAMBRES = {"studio": 0, "chambre": 0, "T1": 0, "T2": 1, "T3": 2, "T4": 3, "T5": 4}

# Probabilité d'un duplex (deux niveaux reliés par un escalier) selon le type.
DUPLEX = {"studio": 0.0, "chambre": 0.0, "T1": 0.0, "T2": 0.05, "T3": 0.12, "T4": 0.20, "T5": 0.30}

# Probabilité, selon le type, de chaque pièce facultative.
CUISINE_SEPAREE = {"studio": 0.0, "chambre": 0.0, "T1": 0.15, "T2": 0.35, "T3": 0.5, "T4": 0.6, "T5": 0.65}
WC_SEPARE = {"studio": 0.0, "chambre": 0.0, "T1": 0.1, "T2": 0.5, "T3": 0.85, "T4": 1.0, "T5": 1.0}
ENTREE = {"studio": 0.3, "chambre": 0.4, "T1": 0.8, "T2": 0.85, "T3": 0.95, "T4": 1.0, "T5": 1.0}
DEGAGEMENT = {"studio": 0.0, "chambre": 0.0, "T1": 0.0, "T2": 0.15, "T3": 0.6, "T4": 0.85, "T5": 1.0}
DEUXIEME_DEGAGEMENT = {"studio": 0.0, "chambre": 0.0, "T1": 0.0, "T2": 0.0, "T3": 0.0, "T4": 0.2, "T5": 0.5}
PLACARD = {"studio": 0.3, "chambre": 0.4, "T1": 0.35, "T2": 0.5, "T3": 0.6, "T4": 0.7, "T5": 0.75}
BUANDERIE = {"studio": 0.0, "chambre": 0.0, "T1": 0.05, "T2": 0.15, "T3": 0.3, "T4": 0.45, "T5": 0.55}
BUREAU = {"studio": 0.0, "chambre": 0.0, "T1": 0.0, "T2": 0.05, "T3": 0.15, "T4": 0.25, "T5": 0.35}
DEUXIEME_SDB = {"studio": 0.0, "chambre": 0.0, "T1": 0.0, "T2": 0.0, "T3": 0.1, "T4": 0.5, "T5": 0.8}

# Surface visée de chaque sorte de pièce : (minimum, maximum) en m², avant les variations par type.
SURFACES = {
    "sejour": (17.0, 28.0), "cuisine": (6.0, 11.0), "chambre": (9.0, 14.0), "sdb": (3.2, 6.0), "sde": (2.8, 4.2),
    "wc": (1.2, 1.9), "entree": (2.2, 4.5), "degagement": (2.0, 5.5), "placard": (0.7, 2.0),
    "buanderie": (1.8, 4.0), "bureau": (6.0, 9.5), "escalier": (2.6, 3.6), "principale": (16.0, 26.0),
}

# Pour chaque sorte : plus petit côté (mm), allongement maximal (grand côté / petit côté), surface minimale (m²).
COTE_MIN = {
    "sejour": 3000, "cuisine": 1800, "chambre": 2600, "sdb": 1500, "sde": 1400, "wc": 850, "entree": 1100,
    "degagement": 900, "placard": 550, "buanderie": 1200, "bureau": 2200, "escalier": 900, "principale": 3200,
}
ALLONGEMENT_MAX = {
    "sejour": 2.2, "cuisine": 2.6, "chambre": 1.8, "sdb": 2.4, "sde": 2.6, "wc": 2.8, "entree": 4.0,
    "degagement": 12.0, "placard": 6.0, "buanderie": 2.6, "bureau": 1.9, "escalier": 4.2, "principale": 2.2,
}
SURFACE_MIN = {"sejour": 15.0, "principale": 14.0, "chambre": 8.5, "cuisine": 5.0, "bureau": 5.0}
COTE_MAX = {"wc": 2200, "placard": 3200}  # un WC ou un placard trop grand n'est plus un WC ni un placard
# Une pièce peut s'écarter de sa surface visée, mais pas du simple au double.
ECART_SURFACE = (0.6, 1.5)

# Les pièces par lesquelles on passe pour aller ailleurs.
DISTRIBUTION = {"entree", "degagement", "sejour", "principale", "escalier"}
# Les pièces de vie : une fenêtre obligatoire.
AVEC_FENETRE = {"sejour", "principale", "chambre", "cuisine", "bureau"}
# Les pièces qui peuvent s'ouvrir sur n'importe quelle pièce voisine (pas seulement une pièce de distribution).
DEPUIS_N_IMPORTE_OU = {"placard", "buanderie", "sde"}  # une salle d'eau peut s'ouvrir sur une chambre (suite parentale)

# ---- Enveloppe ----

FORMES = {"rectangle": 0.55, "L": 0.30, "irregulier": 0.15}  # irrégulier : deux encoches (U, T, Z…)
ALLONGEMENT_CADRE = (1.0, 1.9)  # largeur / profondeur du cadre
ENCOCHE = (0.22, 0.45)  # taille d'une encoche, en part des côtés
EPAISSEUR_EXTERIEURE = {150: 2, 200: 5, 250: 3, 300: 2, 350: 1, 400: 1}  # mm → poids
EPAISSEUR_CLOISON = {50: 1, 70: 3, 100: 6, 120: 1}
EPAISSEUR_PORTEUR = {150: 3, 180: 2, 200: 3, 250: 1}  # murs porteurs intérieurs simulés (entre les zones)
PORTEUR_ENTRE_ZONES = 0.6  # probabilité que le mur entre deux zones soit porteur plutôt qu'une cloison
HAUTEUR_SOUS_PLAFOND = {2400: 1, 2500: 4, 2550: 1, 2600: 2, 2700: 2, 2800: 1, 3000: 1, 3200: 0.5}
PLANCHER = (200, 300)  # épaisseur du plancher entre les deux niveaux d'un duplex (mm)
ESCALIER = {"largeur": (900, 1100), "longueur": (2600, 3400)}

# ---- Ouvertures ----

PAS = 50  # les pièces mesurent un nombre entier de fois 5 cm
MARGE_OUVERTURE = 150  # une fenêtre reste à 15 cm au moins des angles de sa pièce
MARGE_PORTE = 100  # une porte, à 10 cm au moins
ECART_OUVERTURES = 300  # deux ouvertures d'un même mur restent à 30 cm l'une de l'autre
LARGEURS_PORTES = {"petite": [700, 800], "normale": [800, 800, 900], "grande": [800, 900, 900]}
PORTE_ENTREE = [900, 900, 800]
BAIE = 0.35  # probabilité qu'un séjour ait une baie vitrée (porte-fenêtre large) plutôt qu'une fenêtre

ESSAIS_MAX = 1500  # tirages avant d'abandonner une graine
BUDGET_COUPES = 1200  # coupes essayées par tirage


class Reglages:
    """Tous les réglages ci-dessus, dans un objet qu'on peut modifier par JSON."""

    def __init__(self, surcharge: dict[str, Any] | None = None):
        for nom, valeur in globals().items():
            if nom.isupper() and not nom.startswith("_"):
                setattr(self, nom, copy.deepcopy(valeur))
        if surcharge:
            self.appliquer(surcharge)

    def appliquer(self, surcharge: dict[str, Any]) -> None:
        """Remplace les réglages donnés. Une table (dict) est fusionnée clé par clé, le reste est remplacé."""
        for nom, valeur in surcharge.items():
            if not hasattr(self, nom):
                raise KeyError(f"réglage inconnu : {nom}")
            actuel = getattr(self, nom)
            if isinstance(actuel, dict) and isinstance(valeur, dict):
                fusion = dict(actuel)
                fusion.update({_cle(k, actuel): v for k, v in valeur.items()})
                setattr(self, nom, fusion)
            else:
                setattr(self, nom, tuple(valeur) if isinstance(actuel, tuple) else valeur)

    def en_dict(self) -> dict[str, Any]:
        return {nom: _json(v) for nom, v in vars(self).items() if nom.isupper()}

    @classmethod
    def charger(cls, chemin: str | Path | None) -> Reglages:
        if chemin is None:
            return cls()
        return cls(json.loads(Path(chemin).read_text(encoding="utf-8")))


def _cle(k: Any, table: dict) -> Any:
    """Le JSON n'a que des clés texte : « 200 » redevient 200 si la table a des clés entières."""
    if isinstance(k, str) and table and all(isinstance(c, int) for c in table):
        return int(k)
    return k


def _json(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _json(x) for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    if isinstance(v, tuple):
        return list(v)
    return v
