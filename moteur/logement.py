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
from moteur.meubles import NOMS_MEUBLES

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


Couleur = tuple[Annotated[int, Field(ge=0, le=255)], Annotated[int, Field(ge=0, le=255)], Annotated[int, Field(ge=0, le=255)]]


class Rideaux(BaseModel):
    """Ce qui habille une fenêtre côté intérieur (B4, 09/11/2026) : un voilage (tissu fin qui laisse passer la lumière, tiré
    devant la vitre) et/ou des rideaux épais (deux pans ouverts sur les côtés). Couleur sRGB vue sur photo ; None = absent."""

    model_config = ConfigDict(extra="forbid")

    voilage: Couleur | None = None
    rideaux: Couleur | None = None
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


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
    rideaux: Rideaux | None = Field(default=None, description="Voilage et rideaux côté intérieur (fenêtres seulement)")


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
    teinte: tuple[Annotated[float, Field(ge=0.02, le=4.0)], Annotated[float, Field(ge=0.02, le=4.0)],
                  Annotated[float, Field(ge=0.02, le=4.0)]] | None = Field(
        default=None, description="Correction de couleur (rouge, vert, bleu) qui rapproche la matière de la photo du client")
    couleur_photo: tuple[Annotated[float, Field(ge=0, le=1)], Annotated[float, Field(ge=0, le=1)],
                         Annotated[float, Field(ge=0, le=1)]] | None = Field(
        default=None, description="Part de lumière (rouge, vert, bleu) que renvoie ce sol sur la photo du client, un mur blanc de la "
        "même photo servant d'étalon (moteur/teinte_photo.py) : la cible du réglage de la teinte au rendu (moteur/blender/regler_teintes.py)")
    echelle: Annotated[float, Field(ge=0.3, le=3.0)] | None = Field(
        default=None, description="Taille du motif par rapport à la matière du catalogue (1,13 = chevrons 13 % plus grands)")
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


class Corniche(BaseModel):
    """La moulure de plâtre qui fait le tour du plafond d'une pièce (B2 temps 2, 09/11/2026 : app-001, NT « la jonction des
    murs est trop brute ») : « aucune », « simple » (une bande) ou « moulure » (gradins). Même provenance que Plinthes."""

    model_config = ConfigDict(extra="forbid")

    choix: Literal["aucune", "simple", "moulure"]
    statut: Statut
    source: str = Field(min_length=1)
    confiance: float = Field(default=1.0, ge=0, le=1)


class ZoneSol(BaseModel):
    """Un morceau du sol d'une pièce posé dans un autre revêtement (B2 temps 2, 09/11/2026 : app-001, carreaux de ciment
    devant les meubles d'une cuisine ouverte sur un séjour en point de Hongrie).

    Ni mur, ni trait, ni plinthe : seul le revêtement change, la pièce reste UNE pièce (règle NT : jamais de limite absente du
    plan). Le contour est CONVEXE (un rectangle le plus souvent) ; ce qui sort de la pièce est coupé à la construction."""

    model_config = ConfigDict(extra="forbid")

    contour: list[Point] = Field(min_length=3)
    sol: Sol


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
    corniche: Corniche | None = Field(
        default=None, description="Moulure du plafond. Si absent : la règle par défaut (moteur.habillage.CORNICHE_PAR_DEFAUT)"
    )
    zones_sol: list[ZoneSol] = Field(
        default_factory=list, description="Morceaux du sol dans un autre revêtement (cuisine ouverte…), sans mur ni trait"
    )

    @property
    def surface_calculee(self) -> float:
        """Surface du contour, par la formule du lacet (polygone simple)."""
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.contour, self.contour[1:] + self.contour[:1]):
            total += x1 * y2 - x2 * y1
        return abs(total) / 2


class Literie(BaseModel):
    """Le linge d'un lit (10/11/2026) : sur une vraie photo, un lit c'est surtout une couette (souvent blanche, plissée), des
    oreillers et parfois un plaid. Blender les pose sur le matelas du lit (moteur/blender/literie.py)."""

    model_config = ConfigDict(extra="forbid")

    couette: Couleur = Field(description="Couleur de la couette (sRGB)")
    oreillers: Annotated[int, Field(ge=0, le=4)] = 2
    couleur_oreillers: Couleur | None = Field(default=None, description="Par défaut, celle de la couette")
    plaid: Couleur | None = Field(default=None, description="Plaid replié au pied du lit, s'il y en a un")


class Meuble(Element):
    """Un meuble (B4, 09/11/2026), voir moteur/meubles.py : du commerce (choisi dans la bibliothèque ABO) ou sur mesure (bloc).

    `statut` : « estime » = vu sur une photo du client, « mesure » = placé à l'écran de vérification, « ajoute » = proposé par
    Atelya pour meubler (le type de pièce n'impose pas les meubles : règle NT n° 19)."""

    categorie: Literal[*NOMS_MEUBLES]
    piece: str | None = Field(default=None, description="Identifiant de la pièce où il se trouve")
    position: Point = Field(description="Milieu du pied du meuble au sol (m)")
    face: float = Field(default=0.0, description="Direction vers laquelle regarde l'avant (degrés, 0 = +x, 90 = +y)")
    dimensions: tuple[Longueur, Longueur, Longueur] = Field(description="Largeur (le long de l'avant), profondeur, hauteur (m)")
    altitude: Annotated[float, Field(ge=0)] = Field(default=0.0, description="Bas du meuble (m) : 0 = posé au sol")
    couleur: tuple[Annotated[int, Field(ge=0, le=255)], Annotated[int, Field(ge=0, le=255)],
                   Annotated[int, Field(ge=0, le=255)]] | None = Field(default=None, description="Couleur principale vue (sRGB)")
    modele: str | None = Field(default=None, description="Modèle ABO imposé ; sinon Atelya choisit le plus proche")
    description: str | None = None
    literie: Literie | None = Field(default=None, description="Couette, oreillers, plaid (lits seulement)")


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
    meubles: list[Meuble] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherence(self) -> Logement:
        erreurs = verifier_coherence(self)
        if erreurs:
            raise ValueError("incohérences : " + " ; ".join(erreurs))
        return self


def verifier_coherence(logement: Logement) -> list[str]:
    """Renvoie la liste des incohérences trouvées (vide si tout va bien)."""
    erreurs: list[str] = []

    tous_les_ids = [e.id for e in [*logement.murs, *logement.ouvertures, *logement.pieces, *logement.meubles]]
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
        for k, z in enumerate(p.zones_sol, start=1):
            if not _convexe(z.contour):
                erreurs.append(f"la zone de sol n° {k} de la pièce {p.id} n'est pas convexe (découper en rectangles)")

    pieces = {p.id for p in logement.pieces}
    for m in logement.meubles:
        if m.piece is not None and m.piece not in pieces:
            erreurs.append(f"le meuble {m.id} désigne une pièce inconnue : {m.piece}")
        if m.altitude + m.dimensions[2] > logement.hauteur_sous_plafond + 1e-9:
            erreurs.append(f"le meuble {m.id} dépasse le plafond")

    return erreurs


def _convexe(contour: list[Point]) -> bool:
    """Vrai si le polygone tourne toujours du même côté (points alignés tolérés) et n'est pas plat."""
    signes = set()
    n = len(contour)
    for i in range(n):
        (ax, ay), (bx, by), (cx, cy) = contour[i], contour[(i + 1) % n], contour[(i + 2) % n]
        v = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(v) > 1e-9:
            signes.add(v > 0)
    return len(signes) == 1


def charger_logement(chemin: str | Path) -> Logement:
    """Lit un fichier logement.json et le vérifie. Lève une erreur s'il est invalide."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    return Logement.model_validate(donnees)
