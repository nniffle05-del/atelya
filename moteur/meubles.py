"""Les meubles qu'Atelya sait poser (B4, 09/11/2026 ; demande NT : meubler app-001 comme sur les photos de l'annonce).

Deux sortes :
- les meubles « du commerce » (canapé, chaise, lit, tapis…) : Atelya choisit lui-même, dans la bibliothèque ABO (Amazon
  Berkeley Objects, CC BY 4.0, créditer « Amazon.com », jamais de marque affichée ; ..\\atelya\\bibliotheque\\meubles-abo), le
  modèle 3D le plus proche de ce qui est demandé : bonne catégorie, dimensions proches, couleur proche ;
- les meubles « sur mesure » (cuisine, îlot, caisson, placard, dressing) : propres à chaque logement, absents de tout
  catalogue ; Blender les dessine comme des blocs aux dimensions et à la couleur relevées.

Repère d'un meuble : `position` = milieu de son pied au sol (m, repère du logement) ; `face` = direction vers laquelle regarde
son avant (degrés, 0 = vers +x / l'est, 90 = vers +y / le nord), comme le cap des caméras ; `dimensions` = largeur (le long de
l'avant), profondeur, hauteur. Un meuble accroché (tableau, suspension, meuble haut) a une `altitude` (bas du meuble, m).

Ce module ne dépend que de la bibliothèque standard (lu aussi par Blender et par l'écran de vérification).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# catégorie → (libellé, types de produits ABO, mots du nom (anglais, l'un d'eux au moins), mots qui excluent)
# Types ABO : liste.json de la bibliothèque (« chair », « sofa », « rug », « table »…). None = sur mesure (bloc).
CATEGORIES: dict[str, tuple[str, tuple[str, ...] | None, tuple[str, ...], tuple[str, ...]]] = {
    "canape": ("Canapé", ("sofa",), (), ("sleeper", "futon", "bed", "loveseat chair", "outdoor")),
    "fauteuil": ("Fauteuil", ("chair", "sofa"), ("armchair", "accent chair", "club chair", "lounge chair", "arm chair"),
                 ("office", "desk", "dining", "gaming", "outdoor", "kids")),
    "chaise": ("Chaise", ("chair",), ("dining", "side chair", "kitchen chair"), ("office", "desk", "gaming", "arm", "outdoor", "kids")),
    "tabouret_haut": ("Tabouret haut", ("stool seating", "chair"), ("bar stool", "barstool", "counter stool", "counter height"), ("kids",)),
    "table_basse": ("Table basse", ("table",), ("coffee",), ("outdoor",)),
    "table_d_appoint": ("Table d'appoint", ("table",), ("side table", "end table", "accent table", "nightstand"), ("outdoor",)),
    "table": ("Table de repas", ("table",), ("dining", "kitchen table"), ("outdoor", "coffee", "side", "end table")),
    "bureau": ("Bureau", ("desk",), (), ("standing", "gaming", "laptop", "pedestal")),
    "chaise_de_bureau": ("Chaise de bureau", ("chair",), ("office", "desk chair", "task chair"), ("gaming",)),
    "lit": ("Lit", ("bed", "bed frame"), ("bed",), ("air", "airbed", "luchtbed", "inflatable", "kids", "bunk", "daybed", "dog", "pet")),
    "lit_superpose": ("Lit superposé ou mezzanine", ("bed", "bed frame"), ("bunk", "loft"), ()),
    "table_de_chevet": ("Table de chevet", ("cabinet", "home furniture and decor", "table", "dresser"), ("nightstand", "bedside"), ()),
    "commode": ("Commode", ("dresser", "cabinet"), ("dresser", "chest of drawers", "drawer"), ("nightstand",)),
    "rangement": ("Meuble de rangement", ("cabinet", "shelf", "dresser"), ("sideboard", "buffet", "cabinet", "storage"), ("bathroom", "medicine", "kitchen")),
    "etagere_cubes": ("Étagère à cases", ("shelf",), ("cube",), ()),
    "bibliotheque": ("Bibliothèque", ("shelf",), ("bookcase", "bookshelf"), ("cube", "ladder", "corner")),
    "meuble_tv": ("Meuble télé", ("cabinet", "table", "home furniture and decor"), ("tv stand", "tv console", "media console", "tv cabinet", "entertainment"), ()),
    "banc": ("Banc", ("bench", "shelf"), ("bench", "shoe"), ("outdoor", "weight")),
    "tapis": ("Tapis", ("rug",), (), ("runner", "outdoor", "door mat", "doormat", "bath")),
    "lampadaire": ("Lampadaire", ("lamp",), ("floor lamp",), ()),
    "lampe": ("Lampe à poser", ("lamp",), ("table lamp", "desk lamp"), ("floor",)),
    "suspension": ("Suspension", ("light fixture", "lamp"), ("pendant", "chandelier"), ("wall", "floor", "table", "flush")),
    "tableau": ("Tableau", ("wall art",), (), ()),
    "miroir": ("Miroir", ("home mirror",), (), ("vanity", "compact")),
    "horloge": ("Horloge murale", ("clock", "wall art"), ("clock",), ("alarm", "desk", "table")),
    "plante": ("Plante", ("planter", "artificial plant"), (), ()),
    "coussin": ("Coussin", ("pillow",), (), ("bed pillow", "sleeping")),
    # sur mesure : dessinés en bloc (couleur relevée)
    "meuble_cuisine_bas": ("Meubles bas de cuisine", None, (), ()),
    "meuble_cuisine_haut": ("Meubles hauts de cuisine", None, (), ()),
    "colonne_cuisine": ("Colonne de cuisine (four, frigo)", None, (), ()),
    "ilot": ("Îlot de cuisine", None, (), ()),
    "caisson": ("Caisson, cloison meuble", None, (), ()),
    "placard": ("Placard, dressing", None, (), ()),
    "television": ("Télévision", None, (), ()),
}
NOMS_MEUBLES = tuple(CATEGORIES)
SUR_MESURE = {c for c, v in CATEGORIES.items() if v[1] is None}

# Couleurs des mots de couleur d'ABO (champ « color », souvent un nom commercial : on garde le premier mot connu).
COULEURS_NOMMEES = {
    "white": (235, 235, 230), "ivory": (236, 230, 210), "cream": (232, 222, 198), "beige": (210, 193, 160),
    "natural": (190, 160, 120), "oak": (180, 140, 95), "walnut": (110, 75, 50), "brown": (115, 80, 55),
    "espresso": (60, 45, 35), "black": (30, 30, 30), "grey": (128, 128, 128), "gray": (128, 128, 128),
    "charcoal": (65, 65, 68), "silver": (180, 180, 185), "blue": (60, 90, 150), "navy": (35, 45, 80),
    "teal": (40, 120, 120), "green": (80, 120, 70), "yellow": (220, 180, 50), "mustard": (200, 150, 40),
    "gold": (200, 165, 80), "orange": (220, 120, 50), "red": (170, 50, 45), "pink": (225, 160, 170),
    "purple": (110, 70, 130), "multi": (150, 130, 110), "multicolor": (150, 130, 110), "taupe": (140, 125, 110),
    "wood": (170, 130, 90), "light": (200, 200, 195), "dark": (60, 55, 50),
}


def couleur_abo(nom: str | None) -> tuple[int, int, int] | None:
    if not nom:
        return None
    for mot in nom.lower().replace("/", " ").replace("-", " ").replace(",", " ").split():
        if mot in COULEURS_NOMMEES:
            return COULEURS_NOMMEES[mot]
    return None


def candidats(categorie: str, liste: list[dict]) -> list[dict]:
    """Les meubles ABO de la catégorie (type de produit, puis mots du nom ; sans mot exigé, tous ceux du type)."""
    _, types, mots, exclus = CATEGORIES[categorie]
    if types is None:
        return []
    sortie = []
    for e in liste:
        if e.get("product_type") not in types:
            continue
        nom = (e.get("name") or "").lower()
        if mots and not any(m in nom for m in mots):
            continue
        if any(x in nom for x in exclus):
            continue
        sortie.append(e)
    return sortie


def ecart(e: dict, dimensions, couleur=None) -> float:
    """Distance entre un meuble ABO et ce qui est demandé : dimensions (rapports en logarithme : 10 % trop grand ou trop
    petit coûtent pareil), puis couleur si elle est connue des deux côtés. ABO donne size_metres = [largeur, hauteur,
    profondeur] (avant tourné vers -y dans Blender)."""
    l, h, p = e["size_metres"]
    L, P, H = dimensions
    d = abs(math.log(max(l, 1e-3) / L)) + 0.7 * abs(math.log(max(p, 1e-3) / P)) + 0.7 * abs(math.log(max(h, 1e-3) / H))
    c = couleur_abo(e.get("color")) or couleur_abo(e.get("name"))
    if couleur is not None and c is not None:
        d += 0.6 * math.dist(c, couleur) / 255.0
    elif couleur is not None:
        d += 0.25  # couleur inconnue : un peu moins bon qu'une couleur sûre
    return d


def choisir(categorie: str, dimensions, couleur, liste: list[dict], exclure=()) -> dict | None:
    """Le meuble ABO le plus proche (None pour un meuble sur mesure ou une catégorie vide). Le choix est fixe pour une même
    demande (pas de hasard) ; `exclure` évite de reprendre le même modèle pour deux meubles voisins différents."""
    c = [e for e in candidats(categorie, liste) if e["id"] not in exclure]
    if not c:
        return None
    return min(c, key=lambda e: (ecart(e, dimensions, couleur), e["id"]))


def charger_liste(bibliotheque: str | Path) -> list[dict]:
    return json.loads((Path(bibliotheque) / "liste.json").read_text(encoding="utf-8"))


def chemin_modele(bibliotheque: str | Path, ident: str) -> Path | None:
    for p in Path(bibliotheque).glob(f"*/{ident}.glb"):
        return p
    return None
