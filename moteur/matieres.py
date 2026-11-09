"""Le catalogue des matières de sol qu'Atelya sait poser (B2-3, 08/11/2026).

Une matière, c'est l'apparence d'une surface : un parquet de chêne, des tomettes, du granito. Chaque pièce du logement
choisit la sienne (champ `sol` de la pièce, voir moteur/logement.py), comme ses plinthes et ses portes de placard.

La plupart viennent de la bibliothèque de matières téléchargée (photos de vraies surfaces sous licence CC0, dossier
..\\atelya\\bibliotheque\\matieres, hors Git, voir outils/bibliotheque/telecharger_matieres.py). Deux sont dessinées par un
calcul dans Blender, parce qu'aucune photo libre ne les montre bien : le point de Hongrie (fait avec le chêne clair) et les
carreaux de ciment. Sans la bibliothèque (Mac, tests), Blender retombe sur son parquet ou son carrelage dessinés par calcul.

Ce module ne dépend de rien : le format (logement.py), l'habillage et l'écran de vérification lisent la même liste.
"""

from __future__ import annotations

# nom → (libellé pour l'écran, sorte : « bois » ou « carrelage »). L'ordre est celui de la liste à l'écran.
SOLS: dict[str, tuple[str, str]] = {
    "parquet_chene_lames": ("Parquet chêne, lames droites", "bois"),
    "parquet_batons_rompus": ("Parquet bâtons rompus", "bois"),
    "point_de_hongrie": ("Parquet point de Hongrie", "bois"),
    "stratifie": ("Stratifié", "bois"),
    "chene_clair_moderne": ("Chêne clair moderne", "bois"),
    "chene_grise": ("Chêne grisé", "bois"),
    "chene_noeuds": ("Chêne à nœuds, larges lames", "bois"),
    "chene_clair_photo": ("Chêne clair, larges lames", "bois"),
    "chene_naturel_photo": ("Chêne naturel", "bois"),
    "vieux_parquet": ("Vieux parquet", "bois"),
    "hongrie_naturel": ("Point de Hongrie naturel", "bois"),
    "hongrie_grise": ("Point de Hongrie grisé", "bois"),
    "batons_rompus_clair": ("Bâtons rompus clair", "bois"),
    "batons_rompus_tres_clair": ("Bâtons rompus très clair", "bois"),

    "carrelage_interieur": ("Carrelage beige", "carrelage"),
    "carreaux_ciment": ("Carreaux de ciment", "carrelage"),
    "tomettes": ("Tomettes", "carrelage"),
    "damier_pierre": ("Damier de pierre", "carrelage"),
    "pierre_beige": ("Dalles de pierre beige", "carrelage"),
    # Dessinés par Atelya d'après les photos d'app-001 (outils/bibliotheque/dessiner_carreaux.py, 09/11/2026).
    "carreaux_cubes": ("Carreaux de ciment en cubes (losanges)", "carrelage"),
    "petits_carreaux_clairs": ("Petits carreaux clairs, 10 cm", "carrelage"),
}
# Écartées après essai à l'œil (08/11/2026) : « granito » (la photo terrazzo_tiles, brune et mouchetée, ressemble à du liège ou
# à de la moquette une fois posée : pas réaliste ; à remplacer par un vrai granito gris à éclats).
NOMS_SOLS = tuple(SOLS)

# Dessinées par un calcul dans Blender (moteur/blender/materiaux.py), à partir d'une photo de la bibliothèque ou de rien.
CALCULEES = {"point_de_hongrie": "chene_clair", "carreaux_ciment": None}

# Photos dont les carreaux sont en biais : tournées pour que les joints suivent les murs (degrés).
ROTATION_PHOTO = {"carrelage_interieur": 45.0}

# Essayées le 08/11/2026 dans le séjour de fr-031 et ÉCARTÉES du choix (téléchargées, gardées dans la bibliothèque) : chêne
# beige (WoodFloor062) et lames foncées (WoodFloor064) trop unis, effet plastique ; Versailles clair et chaud (WoodFloor055,
# 060) pas convaincants à la distance d'une photo de pièce (motif trop petit et rosé) ; mosaïque (WoodFloor069) terne et boueuse.

# Le sol supposé quand rien ne l'a vu, selon la sorte de la pièce (moteur.habillage.sol_de_la_piece).
SOL_PAR_SORTE = {"bois": "chene_naturel_photo", "carrelage": "carrelage_interieur"}  # NT 08/11 : l'ancien défaut (parquet_chene_lames) était trop foncé


def nom_materiau(matiere: str, teinte=None, echelle: float | None = None) -> str:
    """Le nom du matériau d'une brique : la matière, son échelle de motif si elle n'est pas 1 (« @1.13 »), puis sa teinte
    s'il y en a une (« hongrie_naturel@1.13~1.20,1.00,0.80 »)."""
    nom = matiere
    if echelle and abs(echelle - 1.0) > 0.005:
        nom += f"@{echelle:.2f}"
    if not teinte:
        return nom
    return nom + "~" + ",".join(f"{g:.2f}" for g in teinte)


def matiere_et_teinte(nom: str) -> tuple[str, tuple[float, float, float] | None]:
    """L'inverse de nom_materiau (sans l'échelle du motif, voir echelle_du_nom)."""
    matiere, _, gains = nom.partition("~")
    matiere = matiere.split("@", 1)[0]
    if not gains:
        return matiere, None
    return matiere, tuple(float(g) for g in gains.split(","))


def echelle_du_nom(nom: str) -> float:
    """L'échelle du motif écrite dans le nom d'un matériau (1 si rien n'est écrit)."""
    debut = nom.partition("~")[0]
    return float(debut.split("@", 1)[1]) if "@" in debut else 1.0


def sorte(matiere: str) -> str:
    """« bois » ou « carrelage » (un nom inconnu, ancien « parquet » compris, compte comme du bois)."""
    matiere = matiere_et_teinte(matiere)[0]
    if matiere in SOLS:
        return SOLS[matiere][1]
    return "carrelage" if "carrel" in matiere else "bois"
