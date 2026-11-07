"""Le lot 2 du générateur : le témoin « rien n'a bougé » et la planche à regarder.

Pourquoi un témoin : sans --lot2, les jeux déjà fabriqués doivent rester identiques au pixel, sinon les
essais passés ne seraient plus comparables. Les tests unitaires ne comparent pas à l'ancienne version ;
seul un relevé fait AVANT la première ligne de code le prouve.

    python outils/atelya/planche_lot2.py temoin ..\\atelya\\planches\\temoin-lot2\\avant
    python outils/atelya/planche_lot2.py comparer ..\\atelya\\planches\\temoin-lot2\\avant ..\\atelya\\planches\\temoin-lot2\\apres-chantier1

Chemins relatifs vers ..\\atelya\\ : le chemin absolu contient des accents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from moteur.generateur import lot2 as L  # noqa: E402
from moteur.generateur.controle_qualite import colorer_semantique  # noqa: E402
from moteur.generateur.exportateur import Options, generer_lot, second_logement, style_pour  # noqa: E402
from moteur.generateur.logements import generer  # noqa: E402
from moteur.generateur.reglages import Reglages  # noqa: E402
from moteur.generateur.rendu import rendre  # noqa: E402
from moteur.generateur.validateur import Regles  # noqa: E402
from moteur.images import ecrire_image  # noqa: E402

# Une ligne par option du générateur, pour couvrir tous les chemins de dessin qui existent déjà.
GRAINES_TEMOIN = [
    ("simple", {"depart": 1, "nombre": 4}),
    ("monde", {"depart": 60001, "nombre": 2, "styles_monde": True}),
    ("photo", {"depart": 40002, "nombre": 1, "photo_realiste": True, "vraie_camera": True, "familles": ["photo"]}),
    ("biais", {"depart": 101, "nombre": 1, "biais": True}),
    ("variantes", {"depart": 60005, "nombre": 1, "variantes": 1}),
    # 40002 et non 40001 (conception A) : la graine 40001 ne donne aucun logement.
    # Ajouté à la conception : --sans-cotes a son propre tirage et le lot 2 y touche de près.
    ("sans-cotes", {"depart": 5, "nombre": 1, "sans_cotes": True}),
    # Ajouté aussi : un duplex meublé (deux niveaux, escalier, plan_sans_mobilier).
    ("duplex", {"depart": 62, "nombre": 1}),
]


def _empreinte(chemin: Path) -> str:
    if chemin.name == "geometrie.json":
        # La version du générateur y est écrite : elle seule a le droit de changer.
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        contenu.pop("version_generateur", None)
        return hashlib.md5(json.dumps(contenu, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if chemin.name == "reglages.json":
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        contenu.pop("generateur", None)
        contenu.get("options", {}).pop("dossier", None)  # le dossier du témoin change, forcément
        return hashlib.md5(json.dumps(contenu, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if chemin.name == "annotations.json":
        # rendu.py range « classes_masque_semantique » depuis un set : l'ordre de sdb et sde change d'un lancement de Python à
        # l'autre (hachage aléatoire), depuis bien avant le lot 2. Le contenu seul compte.
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        return hashlib.md5(json.dumps(contenu, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def _empreintes_du_dossier(dossier: Path) -> dict[str, str]:
    return {f.relative_to(dossier).as_posix(): _empreinte(f) for f in sorted(dossier.rglob("*"))
            if f.is_file() and f.name not in ("manifeste.json", "manifest.json", "journal.log", "empreintes.json")}


def temoin(dossier: Path) -> None:
    """Fabrique le témoin et écrit empreintes.json. Les manifestes portent une durée et une version : ignorés."""
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, reglages in GRAINES_TEMOIN:
        d = dossier / nom
        bilan = generer_lot(Options(dossier=d, reprise=False, **reglages))
        if bilan["statuts"]["echec"] or bilan["statuts"]["rejete"]:
            raise SystemExit(f"PLANTÉ témoin {nom} : {bilan['statuts']}")
    empreintes = _empreintes_du_dossier(dossier)
    (dossier / "empreintes.json").write_text(json.dumps(empreintes, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(empreintes)} fichiers relevés dans {dossier}")


def comparer(avant: Path, apres: Path) -> int:
    # Relevé sur les fichiers, pas lu dans empreintes.json : un témoin ancien profite ainsi de toute correction de _empreinte.
    a, b = _empreintes_du_dossier(avant), _empreintes_du_dossier(apres)
    differents = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    absents, nouveaux = sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())
    print(f"{len(a)} fichiers avant, {len(b)} après ; {len(differents)} différents, {len(absents)} disparus, {len(nouveaux)} nouveaux")
    for k in differents[:30] + absents[:30] + nouveaux[:30]:
        print("  ", k)
    return len(differents) + len(absents) + len(nouveaux)


# ---------------------------------------------------------------- la planche


def _releve(rng) -> L.Lot2:
    l = L.Lot2(famille="neutre")
    L._tirer_releve(l, rng)
    return l


# Une vignette par trait du chantier : (titre, plans d'entraînement à comparer, graine, famille, traits forcés).
VIGNETTES_1 = [
    ("Trait 1 agence coloree", ["fr-075", "fr-094", "fr-096"], 60002, "agence_coloree", {}),
    ("Trait 1 agence grise", ["fr-116"], 60005, "agence_coloree", {"palette": "agence_grise", "mobilier_fixes": True, "mobilier_couleur": True}),
    ("Trait 2 releve dimensions", ["fr-098", "fr-117", "fr-076"], 60013, "releve", {}),
    ("Trait 2 etiquette blanche", ["fr-096"], 60002, "agence_coloree", {"dimensions": "remplace", "format_dimensions": "3.87 x 4.65 m", "etiquettes": "bloc"}),
    ("Trait 4 murs noirs", ["fr-046"], 60002, "murs_noirs", {"parentheses_grises": True, "couleur_surface": (135, 135, 135), "arcs_pointilles": True}),
    ("Trait 4 surface encadree", ["fr-063"], 60013, "murs_noirs", {"parentheses_grises": False, "etiquettes": "surface", "couleur_etiquette": (245, 232, 220)}),
    ("Trait 5 tableau bas", ["fr-093"], 60002, "carrez_legende", {"tableau": "bas", "tableau_bordures": True, "tableau_prefixe": "3ème étage - ", "tableau_couleur": (30, 40, 110), "couleur_murs": (10, 10, 10)}),
    ("Trait 5 colonne gauche", ["fr-074"], 60013, "carrez_legende", {"tableau": "gauche", "tableau_bordures": False, "tableau_couleur": None}),
    ("Trait 8 fenetres cyan", ["fr-035", "fr-023"], 60002, "neutre", {"fenetres_pleines": True, "couleur_fenetres": (64, 200, 215), "murs_dessin": "trait", "epaisseur_trait_mur": 0.25}),
    ("Trait 16 cotes rouges", ["fr-031", "fr-105"], 60013, "cotes_rouges", {"couleur_cotes": (200, 35, 35), "cotes_interieures_rouges": True, "cote_point": True, "murs_dessin": "double", "epaisseur_trait_mur": 0.15, "echelle_ecrite": "Échelle : 1/50°"}),
    ("Trait 19 HSP cercle", ["fr-105"], 60002, "murs_noirs", {"hsp": "HSP cercle", "majuscules": True, "parentheses_grises": False}),
    ("Trait 19 HsP sol bleu", ["fr-067", "fr-120"], 60013, "neutre", {"hsp": "HsP :", "mention_sol": "(sol)", "palette": "bleu_uni", "couleur_murs": (198, 198, 198), "couleur_textes": (25, 25, 25), "sans_mobilier": True}),
    ("Trait 20 recadre", ["fr-027", "fr-076"], 60013, "murs_noirs", {"recadre": True, "marges": (3, 2, 5, 4)}),
]

_BALCON = {"sorte": "balcon", "cote": "bas", "part": 0.6, "position": 0.5, "profondeur_m": 1.5, "motif": "vide", "contour": "pointille", "couleur": None, "numero": 1}
_TERRASSE_CM = {**_BALCON, "sorte": "terrasse", "profondeur_m": 2.2, "motif": "carrelage", "contour": "fin"}
_LATTES = {**_BALCON, "sorte": "terrasse", "cote": "droite", "profondeur_m": 2.2, "motif": "lattes", "contour": "moyen"}
_JARDIN = {**_BALCON, "sorte": "jardin", "part": 1.0, "profondeur_m": 3.5, "motif": "vert", "contour": "gris", "couleur": (125, 235, 100)}
_JARDIN_HERBE = {**_JARDIN, "cote": "droite", "motif": "herbe", "contour": "moyen", "couleur": None}
_CM = {"unite_cotes": "cm", "cote_point": False, "cotes_interieures": True, "cercles_pmr": True, "sans_mobilier": False}

VIGNETTES_2 = [
    ("Trait 3 cm murs noirs", ["fr-108"], 26, "promoteur_gris", {**_CM, "couleur_murs": (10, 10, 10), "palette": "", "murs_dessin": "", "sans_chaines": True, "numero_lot": "{type} G206", "mentions_menuiseries": True, "abreviations": True, "noms_courts": False, "exterieurs": [{**_BALCON, "contour": "moyen"}]}),
    ("Trait 3 gris double lot", ["fr-106", "fr-110"], 60012, "promoteur_gris", {**_CM, "couleur_murs": (70, 70, 70), "palette": "", "murs_dessin": "double", "epaisseur_trait_mur": 0.12, "sans_chaines": True, "numero_lot": "45", "abreviations": True, "noms_courts": False, "sols": {"sejour": "parquet"}, "couleur_sol": (205, 205, 205), "pas_sol": 0.2}),
    ("Trait 3 gris moyen", ["fr-109"], 53, "promoteur_gris", {**_CM, "couleur_murs": (125, 125, 125), "palette": "", "murs_dessin": "", "sans_chaines": False, "numero_lot": "A1 14", "mentions_menuiseries": True, "noms_courts": True, "sols": {"chambre": "hachures"}, "couleur_sol": (200, 200, 200), "pas_sol": 0.18}),
    ("Trait 3 ardoise metres", ["fr-041"], 70, "promoteur_gris", {"unite_cotes": "m", "cote_point": True, "cotes_interieures": True, "cercles_pmr": True, "sans_mobilier": False, "couleur_murs": (66, 74, 78), "palette": "gris_clair", "murs_dessin": "", "sans_chaines": True, "numero_lot": "", "mentions_menuiseries": True, "abreviations": True, "noms_courts": True, "sols": {}}),
    ("Trait 3 promoteur vif", ["fr-062"], 60012, "promoteur_gris", {**_CM, "couleur_murs": (10, 10, 10), "palette": "promoteur_vif", "murs_dessin": "", "sans_chaines": True, "numero_lot": "", "noms_courts": True, "noms_gras": True, "sols": {}, "exterieurs": [{**_TERRASSE_CM, "couleur": (222, 222, 200)}]}),
    ("Trait 6 creme", ["fr-100", "fr-102"], 26, "logiciel_public", {"palette": "creme", "couleur_murs": (160, 160, 160), "couleur_cotes": (110, 110, 110), "sans_mobilier": True, "mobilier_couleur": False, "taille_cotes": 0.7, "exterieurs": []}),
    ("Trait 6 lilas meuble", ["fr-070", "fr-103"], 53, "logiciel_public", {"palette": "lilas", "couleur_murs": (74, 76, 104), "couleur_cotes": (150, 150, 215), "sans_mobilier": False, "mobilier_couleur": True, "taille_cotes": 0.85, "barre_echelle": True, "exterieurs": []}),
    ("Trait 6 terrasse verte", ["fr-102"], 60, "logiciel_public", {"palette": "creme", "couleur_murs": (165, 165, 165), "couleur_cotes": (100, 100, 100), "sans_mobilier": True, "mobilier_couleur": False, "taille_cotes": 0.9, "exterieurs": [{**_JARDIN, "sorte": "terrasse"}]}),
    ("Trait 7 etroites", ["fr-067"], 2, "neutre", {"textes_verticaux": "etroites", "couleur_murs": (20, 20, 20)}),
    ("Trait 7 toutes", ["fr-055"], 60012, "neutre", {"textes_verticaux": "toutes", "couleur_murs": (20, 20, 20), "fenetres_pleines": True, "couleur_fenetres": (120, 190, 240), "murs_dessin": "trait", "epaisseur_trait_mur": 0.25}),
    ("Trait 9 bleute cm", ["fr-036"], 7, "scan_ancien", {"papier": 228, "contraste": 0.9, "salissure": "grain", "teinte": (0.89, 0.93, 1.0), "unite_cotes": "cm", "cotes_interieures": True, "sans_chaines": True, "noms_courts": True, "dimensions": "", "tableau": "", "murs_dessin": "double", "epaisseur_trait_mur": 0.12, "majuscules": True, "mobilier_fixes": True, "cercles_pmr": True, "manuscrit": "", "rotation": None, "exterieurs": [_TERRASSE_CM]}),
    ("Trait 9 photocopie legende", ["fr-037", "fr-111"], 26, "scan_ancien", {"papier": 252, "contraste": 0.98, "salissure": "grain", "teinte": None, "unite_cotes": "m", "cotes_interieures": False, "sans_chaines": True, "noms_courts": False, "dimensions": "remplace", "format_dimensions": "2.70×4.33", "tableau": "gauche", "tableau_bordures": False, "murs_dessin": "hachure", "majuscules": False, "mobilier_fixes": True, "cercles_pmr": False, "manuscrit": "", "rotation": None, "exterieurs": [{**_BALCON, "motif": "croisillons", "contour": "fin"}]}),
    ("Trait 11 surfaces au stylo", ["fr-086"], 2, "neutre", {"manuscrit": "surfaces", "couleur_stylo": (25, 25, 30), "couleur_murs": (20, 20, 20), "murs_dessin": "trait", "epaisseur_trait_mur": 0.25, "surface_decimales": 1}),
    ("Trait 11 tout au stylo", ["fr-112"], 60012, "neutre", {"manuscrit": "tout", "couleur_stylo": (40, 60, 150), "couleur_murs": (35, 35, 35)}),
    ("Trait 14 pastilles", ["fr-059"], 60012, "agence_coloree", {"pastilles": "avec_noms", "mobilier_fixes": False, "mobilier_couleur": False, "surface_decimales": 2}),
    ("Trait 14 legende", ["fr-059"], 26, "murs_noirs", {"pastilles": "legende", "parentheses_grises": False}),
    ("Trait 15 placards fleches", ["fr-080", "fr-086"], 26, "murs_noirs", {"placards_fleches": True, "parentheses_grises": False, "exterieurs": [_BALCON]}),
    ("Trait 17 colimacon", ["fr-093"], 62, "murs_noirs", {"escalier": "colimacon"}),
    ("Trait 17 fleche ACCES", ["fr-120"], 60022, "neutre", {"escalier": "fleche_acces", "couleur_murs": (10, 10, 10), "majuscules": True}),
    ("Trait 18 terrasse lattes", ["fr-084"], 60, "neutre", {"exterieurs": [_LATTES], "couleur_murs": (5, 5, 5)}),
    ("Trait 18 jardin herbe", ["fr-084", "fr-065"], 60012, "neutre", {"exterieurs": [_JARDIN_HERBE], "couleur_murs": (5, 5, 5)}),
    ("Trait 4 balcon pointille", ["fr-046", "fr-085"], 60, "murs_noirs", {"exterieurs": [_BALCON, {**_BALCON, "cote": "droite", "contour": "fin", "numero": 2}]}),
]
_NIV = {"composition": "niveaux", "disposition": "empiles"}
_COTE = {"composition": "niveaux", "disposition": "cote_a_cote"}
_PALIER = {"composition": "deux_logements", "disposition": "palier"}
_MITOYEN = {"composition": "deux_logements", "disposition": "mitoyen"}
# Trait 13 : aucun plan cité. Les deux qui montrent le cas sont à l'examen (règle 15) : il est fabriqué de toutes pièces.
VIGNETTES_3 = [
    ("Trait 10 ecran bord noir", ["fr-024", "fr-040"], 60002, "neutre", {"ecran": True, "ecran_bordure": True, "couleur_murs": (70, 70, 70), "parentheses_grises": True, "couleur_surface": (120, 120, 120)}),
    ("Trait 10 ecran sans bord", ["fr-040", "fr-024"], 2, "neutre", {"ecran": True, "ecran_bordure": False, "murs_dessin": "trait", "epaisseur_trait_mur": 0.25, "surface_point": True}),
    ("Trait 10 ecran stylo", ["fr-086"], 60012, "neutre", {"ecran": True, "ecran_bordure": False, "manuscrit": "surfaces", "couleur_stylo": (20, 20, 30), "murs_dessin": "trait", "epaisseur_trait_mur": 0.25, "placards_fleches": True}),
    ("Trait 10 photo sans table", ["fr-024"], 40002, "photo", {"_photo": True}),
    ("Trait 12 RDC tirets", ["fr-025"], 62, "murs_noirs", {**_NIV, "titres_place": "haut", "titre_tirets": True, "couleur_murs": (120, 120, 120), "murs_dessin": "double", "epaisseur_trait_mur": 0.3, "arcs_pointilles": True}),
    ("Trait 12 cotes par niveau", ["fr-072"], 62, "cotes_rouges", {**_NIV, "couleur_cotes": (30, 30, 30), "cotes_interieures_rouges": False, "murs_dessin": "", "couleur_murs": (10, 10, 10), "titres_place": "haut", "titre_tirets": True, "filet": True, "echelle_ecrite": ""}),
    ("Trait 12 agence Niveau", ["fr-075"], 62, "agence_coloree", {**_NIV, "titres_place": "bas", "rose_des_vents": True}),
    ("Trait 12 releve sans titre", ["fr-118", "fr-119"], 60022, "releve", {**_NIV, "titres_place": ""}),
    ("Trait 12 sous plan surface", ["fr-120"], 62, "murs_noirs", {**_NIV, "titres_place": "bas", "titre_surface": True, "majuscules": True}),
    ("Trait 12 cote a cote", ["fr-075"], 60022, "murs_noirs", {**_COTE, "titres_place": "haut"}),
    ("Trait 12 plain-pied etages", ["fr-025"], 26, "neutre", {**_NIV, "titres_place": "haut"}),
    ("Trait 13 palier", [], 26, "promoteur_gris", {**_PALIER, "couleur_murs": (10, 10, 10), "palette": "", "murs_dessin": "", "sans_chaines": True, "titres_place": "haut"}),
    ("Trait 13 palier agence", [], 60, "agence_coloree", {**_PALIER, "titres_place": "bas"}),
    ("Trait 13 mitoyen", [], 60, "murs_noirs", {**_MITOYEN, "titres_place": "haut"}),
    ("Trait 13 mitoyen logiciel", [], 53, "logiciel_public", {**_MITOYEN, "exterieurs": []}),
]
VIGNETTES = {1: VIGNETTES_1, 2: VIGNETTES_2, 3: VIGNETTES_3}
TOUS = 0  # la planche de tous les traits : ..\\atelya\\planches\\lot2-exemples.jpg
# Les plans du chantier à comparer sur la planche ; une vignette sert aussi aux masques.
MASQUES_A_REGARDER = {1: (0, 2), 2: (0, 10), 3: (0, 4, 6, 11, 13), TOUS: ()}


def _style_force(graine: int, famille: str, traits: dict):
    """Un style à plat et propre : on juge le trait, pas une salissure tirée par ailleurs."""
    if traits.get("_photo"):  # sauf la vraie photo : sa page et sa lumière sont le sujet
        style = style_pour(graine, 0, Options(dossier=None, lot2=True, photo_realiste=True, vraie_camera=True, familles=["photo"]))
        style.lot2.ecran = style.realisme.ecran = True
        return style
    style = style_pour(graine, 0, Options(dossier=None, familles=["architecte"], diversite=1))
    style.rotation, style.perspective, style.salissure, style.contraste, style.papier = 0.0, 0.0, "", 1.0, 255
    rng = random.Random(f"planche-{graine}-{famille}")
    l = _releve(rng) if famille == "releve" else L.lot2_au_hasard(rng, famille=famille, transversaux=False)
    if traits.get("ecran"):
        L._tirer_ecran_force(l, rng)
    for k, v in traits.items():
        setattr(l, k, v)
    L.appliquer(style, l)
    return style


def _rendu_vignette(graine: int, famille: str, traits: dict):
    """Le rendu d'une vignette ; traits 12 et 13 : celui de l'exemple -ensemble, par le même chemin que l'exportateur."""
    style = _style_force(graine, famille, traits)
    log = generer(graine, Reglages())
    if not traits.get("composition"):
        return rendre(log, log.niveaux[0], style)
    rc = random.Random(f"lot2-compose-{graine}")
    log_b = None if log.duplex else second_logement(graine, Options(dossier=None), Reglages(), Regles(), rc)
    c = L.composer(log, log_b, traits["composition"], traits["disposition"], style, rc)
    L.vers_ensemble(style, c)
    for k in ("titres_place", "titre_tirets", "titre_surface", "filet"):  # la vignette montre ce trait-là, pas le tirage
        if k in traits:
            setattr(style.lot2, k, traits[k])
    if style.lot2.titres_place and not style.lot2.blocs[0]["titre"]:  # le tirage n'avait pas prévu de titre : on les écrit ici
        titres = L._titres_niveaux(style.lot2, rc) if c.compose == "niveaux" else L._titres_logements(log, log_b, rc)
        for b, titre in zip(style.lot2.blocs, titres):
            b["titre"] = titre
    return rendre(c.log, c.log.niveaux[0], style, "ensemble")


def _reduire(image: np.ndarray, cote: int) -> np.ndarray:
    h, w = image.shape[:2]
    k = cote / max(h, w)
    if k >= 1:
        return image
    return cv2.resize(image, (max(1, round(w * k)), max(1, round(h * k))), interpolation=cv2.INTER_AREA)


def _case(image: np.ndarray, titre: str, cote: int) -> np.ndarray:
    """L'image centrée dans un carré, avec son étiquette."""
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    image = _reduire(image, cote)
    fond = np.full((cote + 30, cote, 3), 200, np.uint8)
    fond[:30] = 245
    cv2.putText(fond, titre, (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1, cv2.LINE_AA)
    h, w = image.shape[:2]
    y, x = 30 + (cote - h) // 2, (cote - w) // 2
    fond[y:y + h, x:x + w] = image
    return fond


def _assembler(cases: list[np.ndarray], colonnes: int) -> np.ndarray:
    lignes = []
    for i in range(0, len(cases), colonnes):
        ligne = cases[i:i + colonnes]
        ligne += [np.full_like(cases[0], 200)] * (colonnes - len(ligne))
        lignes.append(np.hstack(ligne))
    return np.vstack(lignes)


def _ecrire_rgb(chemin: Path, image: np.ndarray) -> None:
    ecrire_image(chemin, cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not chemin.exists():
        raise SystemExit(f"PLANTÉ : {chemin} n'a pas été écrit")


def _verifier_references(repartition: Path = Path("verites/repartition-vrais-plans.json")) -> None:
    """Règle 15 : aucun plan d'examen ne sert de référence."""
    r = json.loads(repartition.read_text(encoding="utf-8"))
    examen, entrainement = set(r["examen_nouveaux"]) | set(r["examen_anciens"]), set(r["entrainement"])
    for vignettes in VIGNETTES.values():
        for _, plans, *_ in vignettes:
            for p in plans:
                assert p in entrainement and p not in examen, p


def planche(sortie: Path, cote: int = 520, chantier: int = 1) -> None:
    """Écrit la planche, une image par vignette à 768 px (pour regarder de près), et les masques de deux exemples."""
    _verifier_references()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    dossier = sortie.with_name(sortie.stem + "-vignettes")
    dossier.mkdir(exist_ok=True)
    cases = []
    vignettes = VIGNETTES_1 + VIGNETTES_2 + VIGNETTES_3 if chantier == TOUS else VIGNETTES[chantier]
    for k, (titre, plans, graine, famille, traits) in enumerate(vignettes):
        rendu = _rendu_vignette(graine, famille, traits)
        plan = _reduire(rendu.images["plan"], 768)
        gris = cv2.cvtColor(plan, cv2.COLOR_RGB2GRAY)
        _ecrire_rgb(dossier / f"{k:02d}.jpg", plan)
        cases.append(_case(rendu.images["plan"], f"{titre} ({', '.join(plans)})", cote))
        cases.append(_case(gris, "gris 768 px", cote))
        if k in MASQUES_A_REGARDER[chantier]:
            masque = colorer_semantique(rendu.images["masque_semantique"])
            melange = (0.5 * rendu.images["plan"] + 0.5 * masque).astype(np.uint8)
            _ecrire_rgb(sortie.with_name(f"{sortie.stem}-masque{k}.jpg"), np.hstack([rendu.images["plan"], masque, melange]))
    _ecrire_rgb(sortie, _assembler(cases, 4))
    if chantier == TOUS:
        print("planche :", sortie)
        return
    hasard = []
    for graine in (60001, 60002, 60005, 60013, 1, 2, 4, 62, 6, 101, 102, 40002):
        style = style_pour(graine, 0, Options(dossier=None, lot2=True))
        log = generer(graine, Reglages())
        rendu = rendre(log, log.niveaux[0], style)
        hasard.append(_case(rendu.images["plan"], f"{graine} {style.lot2.famille} {style.salissure}", cote))
    _ecrire_rgb(sortie.with_name(sortie.stem + "-hasard.jpg"), _assembler(hasard, 4))
    print("planche :", sortie)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("temoin").add_argument("dossier", type=Path)
    p = sous.add_parser("comparer")
    p.add_argument("avant", type=Path)
    p.add_argument("apres", type=Path)
    p = sous.add_parser("planche")
    p.add_argument("--chantier", type=int, default=3, choices=[TOUS, *sorted(VIGNETTES)], help="0 : tous les traits (lot2-exemples.jpg)")
    p.add_argument("--sortie", type=Path, help="par défaut : ../atelya/planches/lot2-chantierN.jpg")
    args = parser.parse_args()
    if args.commande == "temoin":
        temoin(args.dossier)
    elif args.commande == "planche":
        defaut = "lot2-exemples.jpg" if args.chantier == TOUS else f"lot2-chantier{args.chantier}.jpg"
        planche(args.sortie or Path("../atelya/planches") / defaut, cote=380 if args.chantier == TOUS else 520, chantier=args.chantier)
    elif args.commande == "comparer":
        sys.exit(1 if comparer(args.avant, args.apres) else 0)


if __name__ == "__main__":
    main()
