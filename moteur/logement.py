"""Format JSON d'un logement (version 0.1).

Ce module décrit, sous forme de règles, ce qu'un fichier « logement.json »
a le droit de contenir. Toutes les longueurs sont en mètres. Le repère est
vu de dessus : x vers l'est, y vers le nord, origine au coin intérieur
sud-ouest du logement.

Deux niveaux de contrôle :
1. la forme de chaque élément (types, nombres positifs, champs obligatoires),
   vérifiée automatiquement par la bibliothèque pydantic ;
2. la cohérence de l'ensemble (une fenêtre tient dans son mur, les
   identifiants sont uniques, la surface annoncée correspond au contour),
   vérifiée par les fonctions plus bas.
"""

from __future__ import annotations

import json
import math
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from moteur.matieres import NOMS_SOLS

VERSION_SCHEMA = "logement/0.1"

# Écart toléré entre une surface annoncée et la surface calculée (m²).
TOLERANCE_SURFACE = 0.01

Longueur = Annotated[float, Field(gt=0, description="Longueur en mètres, strictement positive")]
Point = tuple[float, float]


class Statut(str, Enum):
    """D'où vient une information. C'est la base de la traçabilité."""

    MESURE = "mesure"  # lue sur une cote ou prise au mètre
    ESTIME = "estime"  # déduite d'une photo ou d'une hypothèse
    AJOUTE = "ajoute"  # ajoutée pour la décoration, n'existe pas forcément


class Element(BaseModel):
    """Ce que partagent tous les éléments : un identifiant et une provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    statut: Statut
    source: str = Field(min_length=1, description="Ex. « cote_plan », « photo_07 »")
    confiance: float = Field(default=1.0, ge=0, le=1)


class Mur(Element):
    """Un mur, décrit par la ligne qui passe en son milieu (son axe)."""

    debut: Point
    fin: Point
    epaisseur: Longueur
    hauteur: Longueur | None = Field(default=None, description="Si absent : hauteur sous plafond")

    @property
    def longueur(self) -> float:
        return math.dist(self.debut, self.fin)

    @model_validator(mode="after")
    def _debut_different_de_fin(self) -> Mur:
        if self.longueur == 0:
            raise ValueError(f"le mur {self.id} a un début et une fin identiques")
        return self


class Ouverture(Element):
    """Une porte, une porte-fenêtre ou une fenêtre percée dans un mur."""

    type: Literal["porte", "porte_fenetre", "fenetre"]
    mur: str = Field(description="Identifiant du mur qui porte l'ouverture")
    position: Annotated[float, Field(ge=0)] = Field(
        description="Distance le long du mur, depuis son début jusqu'au premier bord de l'ouverture"
    )
    largeur: Longueur
    hauteur: Longueur
    allege: Annotated[float, Field(ge=0)] = Field(
        default=0, description="Hauteur entre le sol et le bas de l'ouverture"
    )


class Plinthes(BaseModel):
    """Les plinthes d'une pièce (B2, 08/11/2026) : décidées pièce par pièce, pas une règle fixe pour tout le logement.

    Le plan n'en dit rien, d'où la provenance, avec les mêmes mots que le reste du format :
    - « ajoute » : supposé par la règle par défaut d'Atelya, personne ne l'a vu (source « regle_par_defaut ») ;
    - « estime » : vu par Atelya sur une photo du client (source « photo_07 », par exemple) ;
    - « mesure » : choisi ou confirmé par une personne à l'écran de vérification (source « verification »).
    """

    model_config = ConfigDict(extra="forbid")

    choix: Literal["bois", "carrelage", "aucune"]
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


class PortesPlacard(BaseModel):
    """Les portes d'un placard (B2-2, 08/11/2026) : décidées pièce par pièce, comme les plinthes.

    « battantes » (des portes qui s'ouvrent comme une armoire), « coulissantes » (des panneaux qui glissent sur un rail) ou
    « aucune » (placard ouvert, une simple niche). Même provenance que Plinthes : « ajoute » (règle par défaut), « estime »
    (vu sur une photo), « mesure » (choisi à l'écran de vérification).
    """

    model_config = ConfigDict(extra="forbid")

    choix: Literal["battantes", "coulissantes", "aucune"]
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


class Sol(BaseModel):
    """Le revêtement du sol d'une pièce (B2-3, 08/11/2026) : une matière du catalogue (moteur/matieres.py).

    Même provenance que Plinthes : « ajoute » (règle par défaut), « estime » (vu sur une photo), « mesure » (choisi à
    l'écran de vérification).
    """

    model_config = ConfigDict(extra="forbid")

    matiere: Literal[*NOMS_SOLS]
    teinte: tuple[Annotated[float, Field(ge=0.2, le=4.0)], Annotated[float, Field(ge=0.2, le=4.0)],
                  Annotated[float, Field(ge=0.2, le=4.0)]] | None = Field(
        default=None, description="Correction de couleur (rouge, vert, bleu) qui rapproche la matière de la photo du client")
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


class Piece(Element):
    """Une pièce, décrite par son contour intérieur."""

    nom: str = Field(min_length=1)
    contour: list[Point] = Field(min_length=3)
    surface: Longueur | None = Field(default=None, description="Surface annoncée, en m²")
    plinthes: Plinthes | None = Field(
        default=None, description="Si absent : la règle par défaut d'Atelya (moteur.habillage.plinthes_par_defaut)"
    )
    placard: PortesPlacard | None = Field(
        default=None, description="Portes d'un placard. Si absent : la règle par défaut (moteur.habillage.choix_placard)"
    )
    sol: Sol | None = Field(
        default=None, description="Revêtement du sol. Si absent : la règle par défaut (moteur.habillage.sol_par_defaut)"
    )

    @property
    def surface_calculee(self) -> float:
        """Surface du contour, par la formule du lacet (polygone simple)."""
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.contour, self.contour[1:] + self.contour[:1]):
            total += x1 * y2 - x2 * y1
        return abs(total) / 2


class Logement(BaseModel):
    """Le logement complet, tel qu'il sera transmis à Blender."""

    model_config = ConfigDict(extra="forbid")

    schema_: Literal["logement/0.1"] = Field(alias="schema")
    projet_id: str = Field(min_length=1)
    unites: Literal["m"] = "m"
    hauteur_sous_plafond: Longueur
    murs: list[Mur] = Field(min_length=1)
    ouvertures: list[Ouverture] = Field(default_factory=list)
    pieces: list[Piece] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherence(self) -> Logement:
        erreurs = verifier_coherence(self)
        if erreurs:
            raise ValueError("incohérences : " + " ; ".join(erreurs))
        return self


def verifier_coherence(logement: Logement) -> list[str]:
    """Renvoie la liste des incohérences trouvées (vide si tout va bien)."""
    erreurs: list[str] = []

    tous_les_ids = [e.id for e in [*logement.murs, *logement.ouvertures, *logement.pieces]]
    doublons = sorted({i for i in tous_les_ids if tous_les_ids.count(i) > 1})
    if doublons:
        erreurs.append(f"identifiants en double : {', '.join(doublons)}")

    murs = {m.id: m for m in logement.murs}
    for o in logement.ouvertures:
        mur = murs.get(o.mur)
        if mur is None:
            erreurs.append(f"l'ouverture {o.id} désigne un mur inconnu : {o.mur}")
            continue
        if o.position + o.largeur > mur.longueur + 1e-9:
            erreurs.append(
                f"l'ouverture {o.id} dépasse du mur {mur.id} "
                f"({o.position + o.largeur:.2f} m pour un mur de {mur.longueur:.2f} m)"
            )
        hauteur_mur = mur.hauteur or logement.hauteur_sous_plafond
        if o.allege + o.hauteur > hauteur_mur + 1e-9:
            erreurs.append(f"l'ouverture {o.id} dépasse le haut du mur {mur.id}")

    for p in logement.pieces:
        if p.surface is not None and abs(p.surface - p.surface_calculee) > TOLERANCE_SURFACE:
            erreurs.append(
                f"la pièce {p.id} annonce {p.surface:.2f} m² "
                f"mais son contour mesure {p.surface_calculee:.2f} m²"
            )

    return erreurs


def charger_logement(chemin: str | Path) -> Logement:
    """Lit un fichier logement.json et le vérifie. Lève une erreur s'il est invalide."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return Logement.model_validate(donnees)
