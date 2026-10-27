"""Lire le nom écrit dans chaque pièce (« WC », « Placard », « Chambre »…) pour en connaître le type.

Atelya reconnaît le type d'une pièce à sa forme et à ce qu'il voit dedans. Pour les petites
pièces (WC, placard, buanderie), c'est difficile : un WC et un placard de 1,5 m² se
ressemblent beaucoup. Mais presque tous les plans écrivent le nom de chaque pièce. On le lit
donc avec RapidOCR (le même outil de lecture de texte que pour les cotes), et le nom, quand
il est clair, l'emporte sur la couleur d'Atelya.

Un nom qui peut désigner deux types (« Cellier » : placard ou buanderie) ne décide rien :
c'est alors Atelya qui garde la main.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

# Mots du plan → type de pièce (types de moteur.coloriage.PIECES). L'ordre compte : le premier
# mot trouvé décide, d'où « bureau » avant « chambre » (« Chambre / bureau ») et « séjour »
# avant « cuisine » (« Séjour / cuisine » est une seule pièce de vie).
MOTS = [
    ("bureau", r"bureau|cabinet de travail"),
    ("sejour", r"sejour|sej|salon|living|piece de vie|piece principale|studio|salle a manger|sam"),
    ("cuisine", r"cuisine|cuis|kitchenette|coin cuisine"),
    ("chambre", r"chambre|ch|cbre|suite parentale"),
    ("salle_d_eau", r"salle de bains?|salle d eau|sdb|sde|douche|bains?"),
    ("wc", r"wc|w c|toilettes?|cab(inet)? de toilette|lave mains?"),
    ("entree", r"entree|hall|vestibule|sas"),
    ("degagement", r"degagement|dgt|deg|couloir|circulation|palier"),
    ("placard", r"placard|plac|pl|rangement|rgt|range|dressing|penderie|debarras"),
    ("buanderie", r"buanderie|lingerie|laverie"),
    ("escalier", r"escaliers?|esc|tremie"),
]
AMBIGUS = r"cellier|local|annexe|cave"  # placard ou buanderie, ou autre : on ne décide pas

_MOTS = [(t, re.compile(rf"^({m})(\s|$)")) for t, m in MOTS]
_AMBIGUS = re.compile(rf"^({AMBIGUS})(\s|$)")


@dataclass
class NomLu:
    """Un nom de pièce lu sur le plan : son type et le milieu du texte, en pixels de l'image lue."""

    type: str
    x: float
    y: float
    texte: str


def _simplifier(texte: str) -> str:
    """Minuscules, sans accents, sans chiffres ni ponctuation : « Chambre 2 » → « chambre »."""
    t = unicodedata.normalize("NFKD", texte.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def type_depuis_nom(texte: str) -> str | None:
    """Le type de pièce qu'annonce un texte du plan, ou None (texte sans nom de pièce, ou ambigu).

    Chaque mot du texte est essayé ; s'il y en a plusieurs, c'est l'ordre de MOTS qui décide
    (« Chambre / bureau » → bureau, « Séjour / cuisine » → séjour)."""
    t = _simplifier(texte)
    if not t:
        return None
    mots = t.split(" ")
    restes = [" ".join(mots[k:]) for k in range(len(mots))]
    if any(_AMBIGUS.match(r) for r in restes):
        return None
    for type_, motif in _MOTS:
        if any(motif.match(r) for r in restes):
            return type_
    return None


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr import RapidOCR  # chargé seulement si on lit des noms (le modèle met ~1 s)

    return RapidOCR(params={"Global.log_level": "error"})


def lire_textes(image: np.ndarray) -> list[tuple[str, float, float, float]]:
    """Tous les textes de l'image : (texte, x du milieu, y du milieu, confiance)."""
    r = _ocr()(image)
    if r is None or r.boxes is None:
        return []
    sortie = []
    for boite, texte, score in zip(r.boxes, r.txts, r.scores):
        b = np.asarray(boite, np.float64)
        sortie.append((str(texte), float(b[:, 0].mean()), float(b[:, 1].mean()), float(score)))
    return sortie


def noms_depuis_textes(textes: list[tuple[str, float, float, float]], confiance_min: float = 0.6) -> list[NomLu]:
    """Garde les textes qui sont des noms de pièce."""
    sortie = []
    for texte, x, y, score in textes:
        if score < confiance_min:
            continue
        t = type_depuis_nom(texte)
        if t is not None:
            sortie.append(NomLu(t, x, y, texte))
    return sortie


def lire_noms(image: np.ndarray) -> list[NomLu]:
    """Les noms de pièces écrits sur un plan (image en gris ou en couleurs, à sa taille d'origine)."""
    return noms_depuis_textes(lire_textes(image))
