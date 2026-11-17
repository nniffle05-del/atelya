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
    # Ajoutés le 09/11/2026 (accord écrit de NT : « Oui », ambientCG et Poly Haven, CC0) : parquets…
    "parquet_diagonal": ("Parquet posé en diagonale", "bois"),
    "parquet_rectangulaire": ("Parquet à fines lames", "bois"),
    "lames_parquet_1": ("Parquet à lames brunes", "bois"),
    "lames_parquet_2": ("Parquet à lames miel", "bois"),
    "parquet_use": ("Parquet usé", "bois"),
    "lames_bois": ("Plancher à lames courtes", "bois"),
    "stratifie_2": ("Stratifié (2)", "bois"),
    "lames_foncees_2": ("Lames de bois foncées", "bois"),
    # … et carrelages
    "ciment_motifs_1": ("Carreaux décorés bleus (1)", "carrelage"),
    "ciment_motifs_2": ("Carreaux décorés bleus (2)", "carrelage"),
    "ciment_motifs_3": ("Carreaux décorés bleus (3)", "carrelage"),
    "ciment_motifs_4": ("Carreaux décorés bleus (4)", "carrelage"),
    "ciment_motifs_5": ("Carreaux décorés bleus (5)", "carrelage"),
    "ciment_motifs_6": ("Carreaux décorés bleus (6)", "carrelage"),
    "damier_marbre_noir_blanc": ("Damier de marbre noir et blanc", "carrelage"),
    "damier_marbre_jaune": ("Damier de marbre clair et ocre", "carrelage"),
    "marbre_motif_noir_blanc": ("Grands carreaux de marbre noir et blanc", "carrelage"),
    "marbre_motif_bleu": ("Marbre bleu nuit et gris", "carrelage"),
    "damier_marbre": ("Petit damier noir et blanc", "carrelage"),
    "mosaique_hexa_blanche": ("Mosaïque hexagonale blanche", "carrelage"),
    "mosaique_hexa_noire": ("Mosaïque hexagonale noire", "carrelage"),
    "tomettes_hexa_orange": ("Tomettes hexagonales orange", "carrelage"),
    "tomettes_hexa_brunes": ("Tomettes hexagonales brunes", "carrelage"),
    "granito_beige": ("Granito beige", "carrelage"),
    "granito_beige_2": ("Granito beige (2)", "carrelage"),
    "granito_blanc": ("Granito blanc", "carrelage"),
    "granito_gris": ("Granito gris", "carrelage"),
    "granito_colore": ("Granito à éclats colorés", "carrelage"),
    "granito_colore_2": ("Granito à gros éclats", "carrelage"),
    "pierre_damier_claire": ("Pierre claire", "carrelage"),
    "marbre_dalles": ("Dalles de marbre noir et beige", "carrelage"),
    "grands_carreaux_gris": ("Grandes dalles grises", "carrelage"),
    "carrelage_blanc_moderne": ("Carrelage blanc moderne", "carrelage"),
    "pastilles_rondes": ("Pastilles rondes noires", "carrelage"),
    "pastilles_rondes_2": ("Pastilles rondes grèges", "carrelage"),
    "mosaique_marbre": ("Mosaïque de marbre brune", "carrelage"),
    "carreaux_longs_blancs": ("Carreaux longs blancs", "carrelage"),
    "carreaux_carres": ("Petits carreaux sombres", "carrelage"),
    "granit": ("Dalles de granit", "carrelage"),
    "vieux_carrelage": ("Vieux carrelage", "carrelage"),
    # Dessinés par Atelya d'après les photos d'app-001 (outils/bibliotheque/dessiner_carreaux.py, 09/11/2026).
    "carreaux_cubes": ("Carreaux de ciment en cubes (losanges)", "carrelage"),
    "petits_carreaux_clairs": ("Petits carreaux clairs, 10 cm", "carrelage"),
    # Ajoutés le 17/11/2026 (accord écrit de NT : « Ok », ambientCG, CC0) : six des 62 parquets téléchargés ce jour-là, gardés
    # après les avoir regardés un par un (pc/verification/trier_parquets.py). Les 56 autres restent dans la bibliothèque sous
    # leur nom provisoire (parquet_acg_NNN) : motifs dessinés par ordinateur, mosaïques, bois trop rustiques ou trop unis.
    "lames_chene_miel": ("Chêne miel, lames à l'anglaise", "bois"),
    "lames_chene_clair": ("Chêne clair, lames à l'anglaise", "bois"),
    "lames_chene_dore": ("Chêne doré, lames à l'anglaise", "bois"),
    "lames_miel_fines": ("Parquet miel, lames fines", "bois"),
    "lames_miel_moyennes": ("Parquet miel, lames moyennes", "bois"),
    "pin_clair_larges": ("Pin clair, larges lames", "bois"),
    # Dessiné par Atelya le 17/11/2026 (outils/bibliotheque/dessiner_parquet.py) d'après la vraie photo de chêne de la
    # bibliothèque : le parquet le plus courant des appartements français, que ni Poly Haven ni ambientCG n'avaient (NT).
    "lames_chene_anglaise": ("Chêne à l'anglaise, lames de 10 cm", "bois"),
}
# Écartées après essai à l'œil (08/11/2026) : « granito » (la photo terrazzo_tiles, brune et mouchetée, ressemble à du liège ou
# à de la moquette une fois posée : pas réaliste ; à remplacer par un vrai granito gris à éclats).
NOMS_SOLS = tuple(SOLS)

# Dessinées par un calcul dans Blender (moteur/blender/materiaux.py), à partir d'une photo de la bibliothèque ou de rien.
CALCULEES = {"point_de_hongrie": "chene_clair", "carreaux_ciment": None}

# Photos dont les carreaux sont en biais : tournées pour que les joints suivent les murs (degrés). Et, depuis le 17/11/2026,
# photos de parquet tournées d'un quart de tour pour que les lames de TOUTES les matières suivent le sens demandé (NT : « la
# direction du parquet »). ATTENTION, MESURÉ dans Blender le 17/11/2026 au soir : sur un sol, Blender pose une image avec SA
# LARGEUR le long de l'axe y de la maquette (projection « boîte »). Sans rotation, ce sont donc les photos aux lames DE HAUT
# EN BAS qui suivent le sens demandé ; celles aux lames EN TRAVERS de l'image (de gauche à droite) doivent être tournées :
# ce sont elles qui sont listées ici. (La première correction, l'après-midi, avait fait l'inverse : tous les parquets
# étaient d'accord entre eux, et tous en travers des photos — vu par le juge pc/verification/comparer_sens_photo_rendu.py.)
ROTATION_PHOTO = {"carrelage_interieur": 45.0, "stratifie": 90.0, "chene_clair_moderne": 90.0, "chene_grise": 90.0,
                  "chene_naturel_photo": 90.0, "parquet_use": 90.0, "lames_bois": 90.0, "stratifie_2": 90.0, "lames_foncees_2": 90.0,
                  "lames_chene_miel": 90.0, "lames_chene_clair": 90.0, "lames_chene_dore": 90.0, "lames_miel_fines": 90.0,
                  "lames_miel_moyennes": 90.0, "lames_chene_anglaise": 90.0}

# Les parquets à LAMES DROITES qu'Atelya peut choisir seul d'après une photo, et la largeur de leurs lames (m), mesurée sur la
# photo de la matière. Les autres « bois » du catalogue ont un motif (posé en diagonale, mosaïque, pavés) : ils ne sont posés
# que si quelqu'un les choisit (avant : la brique photos prenait « parquet posé en diagonale » pour des lames droites).
LAMES_DROITES = {"parquet_chene_lames": 0.18, "stratifie": 0.20, "chene_clair_moderne": 0.07, "chene_grise": 0.08, "chene_noeuds": 0.17,
                 "chene_clair_photo": 0.19, "chene_naturel_photo": 0.15, "vieux_parquet": 0.08, "lames_parquet_2": 0.11,
                 "parquet_use": 0.15, "lames_bois": 0.07, "stratifie_2": 0.04, "lames_foncees_2": 0.23,
                 "lames_chene_miel": 0.08, "lames_chene_clair": 0.08, "lames_chene_dore": 0.08, "lames_miel_fines": 0.08, "lames_miel_moyennes": 0.12, "pin_clair_larges": 0.19, "lames_chene_anglaise": 0.10}

# Essayées le 08/11/2026 dans le séjour de fr-031 et ÉCARTÉES du choix (téléchargées, gardées dans la bibliothèque) : chêne
# beige (WoodFloor062) et lames foncées (WoodFloor064) trop unis, effet plastique ; Versailles clair et chaud (WoodFloor055,
# 060) pas convaincants à la distance d'une photo de pièce (motif trop petit et rosé) ; mosaïque (WoodFloor069) terne et boueuse.

# Le sol supposé quand rien ne l'a vu, selon la sorte de la pièce (moteur.habillage.sol_de_la_piece).
SOL_PAR_SORTE = {"bois": "chene_naturel_photo", "carrelage": "carrelage_interieur"}  # NT 08/11 : l'ancien défaut (parquet_chene_lames) était trop foncé


def nom_materiau(matiere: str, teinte=None, echelle: float | None = None, sens: float | None = None) -> str:
    """Le nom du matériau d'une brique : la matière, son échelle de motif si elle n'est pas 1 (« @1.13 »), le sens de ses
    lames s'il a été lu sur les photos (« ^90 », degrés dans le repère du logement), puis sa teinte s'il y en a une
    (« hongrie_naturel@1.13~1.20,1.00,0.80 », « chene_clair_photo^90~1.20,1.00,0.80 »)."""
    nom = matiere
    if echelle and abs(echelle - 1.0) > 0.005:
        nom += f"@{echelle:.2f}"
    if sens is not None:
        nom += f"^{float(sens) % 180.0:.0f}"
    if not teinte:
        return nom
    return nom + "~" + ",".join(f"{g:.2f}" for g in teinte)


def matiere_et_teinte(nom: str) -> tuple[str, tuple[float, float, float] | None]:
    """L'inverse de nom_materiau (sans l'échelle du motif, voir echelle_du_nom)."""
    matiere, _, gains = nom.partition("~")
    matiere = matiere.split("^", 1)[0].split("@", 1)[0]
    if not gains:
        return matiere, None
    return matiere, tuple(float(g) for g in gains.split(","))


def echelle_du_nom(nom: str) -> float:
    """L'échelle du motif écrite dans le nom d'un matériau (1 si rien n'est écrit)."""
    debut = nom.partition("~")[0].split("^", 1)[0]
    return float(debut.split("@", 1)[1]) if "@" in debut else 1.0


def sens_du_nom(nom: str) -> float | None:
    """Le sens des lames écrit dans le nom d'un matériau (degrés, repère du logement) ; None : le sens général du logement."""
    debut = nom.partition("~")[0]
    return float(debut.split("^", 1)[1]) if "^" in debut else None


def sorte(matiere: str) -> str:
    """« bois » ou « carrelage » (un nom inconnu, ancien « parquet » compris, compte comme du bois)."""
    matiere = matiere_et_teinte(matiere)[0]
    if matiere in SOLS:
        return SOLS[matiere][1]
    return "carrelage" if "carrel" in matiere else "bois"
