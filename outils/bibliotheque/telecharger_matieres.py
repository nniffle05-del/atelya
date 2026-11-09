"""Télécharge la bibliothèque de vraies matières d'Atelya (étape B2-3).

Pourquoi : au lieu d'un parquet « dessiné », la maquette pose la photo d'un
vrai parquet, avec son relief (les joints) et sa brillance (le vernis).
Chaque matière = 3 images de 2048 × 2048 points :
    couleur.jpg     la photo à plat, sans ombre
    relief.jpg      les creux et les bosses (carte « normale », convention OpenGL)
    brillance.jpg   où ça brille ou non (carte de « rugosité » : blanc = mat)

Sources (licence CC0 = domaine public, lue le 08/11/2026, accord écrit de NT
le 08/11/2026) :
- Poly Haven, par son API publique (https://api.polyhaven.com), libre y
  compris pour un usage commercial ; aspirer le site est interdit, l'API non.
- ambientCG (https://ambientcg.com), archive zip officielle de chaque matière.

Utilisation (depuis le dépôt, chemin RELATIF à cause des accents) :
    python outils/bibliotheque/telecharger_matieres.py ../atelya/bibliotheque/matieres

Rien n'est retéléchargé si la matière est déjà là et intacte.
Écrit aussi CREDITS.txt et matieres.json (taille réelle de chaque matière).
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

NOM_PROGRAMME = "Atelya/0.1 (bibliotheque de matieres)"
RESOLUTION = "2k"

# nom Atelya, identifiant Poly Haven, taille réelle d'une pièce couverte par une image (m), description
POLY_HAVEN = [
    ("parquet_batons_rompus", "herringbone_parquet", "parquet bâtons rompus"),
    ("parquet_chene_lames", "wood_floor", "parquet chêne à lames droites"),
    ("stratifie", "laminate_floor_02", "stratifié"),
    ("chene_clair", "oak_veneer_01", "chêne clair (base du point de Hongrie)"),
    ("chene_blanchi", "white_oak_veneer", "chêne blanchi (placards, meubles)"),
    ("bois_cuisine", "kitchen_wood", "bois de cuisine"),
    ("carrelage_interieur", "interior_tiles", "carrelage de sol intérieur"),
    ("damier_pierre", "floor_tiles_06", "damier de pierre clair et foncé"),
    ("tomettes", "terracotta_floor_tiles", "tomettes"),
    ("pierre_beige", "marble_01", "dalles de pierre beige (fiche « marble »)"),
    ("granito", "terrazzo_tiles", "granito (terrazzo)"),
    ("enduit_peint_blanc", "white_plaster_02", "enduit au léger grain (gris taché : servira pour le grain, couleur choisie par Atelya)"),
    ("mosaique_rayee", "square_tiled_wall", "petite mosaïque à rayures brunes et grises"),
    # Parquets en plus (accord écrit de NT le 08/11/2026 : « Oui »), vraies photos
    ("chene_clair_photo", "laminate_floor_03", "parquet chêne clair (photo)"),
    ("chene_naturel_photo", "oak_wood_planks", "parquet chêne naturel (photo)"),
    ("vieux_parquet", "old_wooden_floor_03", "vieux parquet (photo)"),
    # Sols en plus (accord écrit de NT le 09/11/2026 : « Oui », liste et tailles données avant)
    ("parquet_diagonal", "diagonal_parquet", "parquet posé en diagonale"),
    ("parquet_rectangulaire", "rectangular_parquet", "parquet à motif rectangulaire"),
    ("lames_parquet_1", "plank_flooring", "parquet à lames (1)"),
    ("lames_parquet_2", "plank_flooring_02", "parquet à lames (2)"),
    ("parquet_use", "wood_floor_worn", "parquet usé"),
    ("lames_bois", "wooden_floor_01", "plancher à lames"),
    ("stratifie_2", "laminate_floor", "stratifié (2)"),
    ("lames_foncees_2", "dark_wooden_planks", "lames de bois foncées"),
    ("mosaique_marbre", "marble_mosaic_tiles", "mosaïque de marbre"),
    ("carreaux_longs_blancs", "long_white_tiles", "carreaux longs blancs"),
    ("carreaux_carres", "square_tiles_02", "carreaux carrés"),
    ("granit", "granite_tile", "dalles de granit"),
    ("vieux_carrelage", "worn_tile_floor", "vieux carrelage"),
]
# carte Poly Haven → nom de fichier Atelya
CARTES_PH = {"Diffuse": "couleur.jpg", "nor_gl": "relief.jpg", "Rough": "brillance.jpg"}

# nom Atelya, identifiant ambientCG, description, taille réelle couverte par une image (m) : celle donnée par ambientCG, sinon
# estimée d'après la largeur des lames (marquée « estimée » dans matieres.json)
AMBIENTCG = [
    ("faience_blanche", "Tiles036", "faïence blanche à carreaux carrés", None),
    # Parquets en plus (accord écrit de NT le 08/11/2026 : « Oui »)
    ("chene_clair_moderne", "WoodFloor051", "parquet chêne clair moderne", 1.8),
    ("chene_beige", "WoodFloor062", "parquet chêne beige", (1.5, "estimée")),
    ("chene_grise", "WoodFloor056", "parquet chêne grisé", 3.2),
    ("chene_noeuds", "WoodFloor040", "parquet chêne à nœuds, larges lames", 1.9),
    ("lames_foncees", "WoodFloor064", "parquet à lames foncées", (1.5, "estimée")),
    ("hongrie_naturel", "WoodFloor052", "parquet point de Hongrie naturel", 1.8),
    ("hongrie_grise", "WoodFloor057", "parquet point de Hongrie grisé", 3.2),
    ("batons_rompus_clair", "WoodFloor053", "parquet bâtons rompus clair", 1.8),
    ("batons_rompus_tres_clair", "WoodFloor058", "parquet bâtons rompus très clair", 2.4),
    ("versailles_clair", "WoodFloor055", "parquet Versailles clair", 1.2),
    ("versailles_chaud", "WoodFloor060", "parquet Versailles chaud", 1.0),
    ("mosaique_parquet", "WoodFloor069", "parquet mosaïque (années 60-70)", (1.0, "estimée")),
    # Sols en plus (accord écrit de NT le 09/11/2026 : « Oui ») ; taille « api » = celle de la fiche ambientCG (dimensionX, cm)
    ("ciment_motifs_1", "Tiles099", "carreaux de ciment à motifs (1)", "api"),
    ("ciment_motifs_2", "Tiles100", "carreaux de ciment à motifs (2)", "api"),
    ("ciment_motifs_3", "Tiles101", "carreaux de ciment à motifs (3)", "api"),
    ("ciment_motifs_4", "Tiles102", "carreaux de ciment à motifs (4)", "api"),
    ("ciment_motifs_5", "Tiles103", "carreaux de ciment à motifs (5)", "api"),
    ("ciment_motifs_6", "Tiles104", "carreaux de ciment à motifs (6)", "api"),
    ("damier_marbre_noir_blanc", "Tiles012", "damier de marbre noir et blanc", "api"),
    ("damier_marbre_jaune", "Tiles013", "damier de marbre clair et jaune", "api"),
    ("marbre_motif_noir_blanc", "Tiles014", "marbre à motif noir et blanc", "api"),
    ("marbre_motif_bleu", "Tiles015", "marbre à motif bleu et noir", "api"),
    ("damier_marbre", "Tiles016", "damier de marbre", "api"),
    ("mosaique_hexa_blanche", "Tiles071", "mosaïque hexagonale blanche", "api"),
    ("mosaique_hexa_noire", "Tiles072", "mosaïque hexagonale noire", "api"),
    ("tomettes_hexa_orange", "Tiles064", "tomettes hexagonales orange", "api"),
    ("tomettes_hexa_brunes", "Tiles066", "tomettes hexagonales brunes", "api"),
    ("granito_beige", "Tiles109", "granito beige", "api"),
    ("granito_beige_2", "Tiles110", "granito beige (2)", "api"),
    ("granito_blanc", "Tiles040", "granito blanc", "api"),
    ("granito_gris", "Tiles043", "granito gris", "api"),
    ("granito_colore", "Terrazzo013", "granito coloré", "api"),
    ("granito_colore_2", "Terrazzo018", "granito coloré (2)", "api"),
    ("pierre_damier_claire", "Tiles139", "pierre claire en damier", "api"),
    ("marbre_dalles", "Tiles074", "dalles de marbre", "api"),
    ("grands_carreaux_gris", "Tiles050", "grands carreaux gris foncé", "api"),
    ("carrelage_blanc_moderne", "Tiles025", "carrelage blanc moderne", "api"),
    ("pastilles_rondes", "Tiles129B", "petites pastilles rondes", "api"),
    ("pastilles_rondes_2", "Tiles120", "petites pastilles rondes (2)", "api"),
]
# fin du nom de fichier dans le zip ambientCG → nom Atelya
CARTES_ACG = {"_Color.jpg": "couleur.jpg", "_NormalGL.jpg": "relief.jpg", "_Roughness.jpg": "brillance.jpg"}


def lire_url(url: str) -> bytes:
    requete = urllib.request.Request(url, headers={"User-Agent": NOM_PROGRAMME})
    for essai in range(3):
        try:
            with urllib.request.urlopen(requete, timeout=120) as reponse:
                return reponse.read()
        except OSError as erreur:
            if essai == 2:
                raise
            print(f"  nouvel essai après : {erreur}")
            time.sleep(5)
    raise AssertionError


def lire_json(url: str):
    return json.loads(lire_url(url).decode("utf-8"))


def poly_haven(dossier: Path, nom: str, ident: str) -> dict:
    fiche = lire_json(f"https://api.polyhaven.com/info/{ident}")
    fichiers = lire_json(f"https://api.polyhaven.com/files/{ident}")
    cible = dossier / nom
    cible.mkdir(parents=True, exist_ok=True)
    for carte, sortie in CARTES_PH.items():
        info = fichiers[carte][RESOLUTION]["jpg"]
        chemin = cible / sortie
        if chemin.exists() and hashlib.md5(chemin.read_bytes()).hexdigest() == info.get("md5"):
            continue
        donnees = lire_url(info["url"])
        if info.get("md5") and hashlib.md5(donnees).hexdigest() != info["md5"]:
            raise SystemExit(f"PLANTÉ : {ident} {carte} abîmé au téléchargement (somme de contrôle fausse)")
        chemin.write_bytes(donnees)
    # dimensions réelles couvertes par une image (en mètres), si Poly Haven les donne
    taille = fiche.get("dimensions")
    return {
        "source": "Poly Haven", "identifiant": ident, "licence": "CC0 1.0",
        "page": f"https://polyhaven.com/a/{ident}",
        "auteurs": sorted(fiche.get("authors", {})),
        "taille_image_m": [round(t / 1000, 3) for t in taille] if taille else None,
    }


def taille_api(ident: str):
    """La taille réelle couverte par une image d'après la fiche ambientCG (dimensionX en cm), sinon None (à estimer)."""
    fiche = lire_json(f"https://ambientcg.com/api/v2/full_json?id={ident}&include=dimensionsData")["foundAssets"]
    x = fiche[0].get("dimensionX") if fiche else 0
    return round(x / 100, 3) if x else None


def ambientcg(dossier: Path, nom: str, ident: str, taille=None) -> dict:
    if taille == "api":
        taille = taille_api(ident)
    cible = dossier / nom
    estimee = isinstance(taille, tuple)
    taille_m = [taille[0], taille[0]] if estimee else ([taille, taille] if taille else None)
    if all((cible / s).exists() for s in CARTES_ACG.values()):
        source = json.loads((cible / "source.json").read_text(encoding="utf-8"))
        source["taille_image_m"] = source.get("taille_image_m") or taille_m
        return source
    archive = lire_url(f"https://ambientcg.com/get?file={ident}_2K-JPG.zip")
    cible.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as zip_:
        for entree in zip_.namelist():
            for fin, sortie in CARTES_ACG.items():
                # on ne garde que les 3 images voulues, écrites sous NOTRE nom (jamais le chemin du zip)
                if Path(entree).name == f"{ident}_2K-JPG{fin}":
                    (cible / sortie).write_bytes(zip_.read(entree))
    manquantes = [s for s in CARTES_ACG.values() if not (cible / s).exists()]
    if manquantes:
        raise SystemExit(f"PLANTÉ : {ident} : images absentes de l'archive : {manquantes}")
    source = {"source": "ambientCG", "identifiant": ident, "licence": "CC0 1.0",
              "page": f"https://ambientcg.com/a/{ident}", "auteurs": ["ambientCG (Lennart Demes)"],
              "taille_image_m": taille_m, **({"taille_estimee": True} if estimee else {})}
    (cible / "source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    return source


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    dossier = Path(sys.argv[1])
    dossier.mkdir(parents=True, exist_ok=True)
    # on COMPLÈTE le catalogue : les matières qui n'en viennent pas (dessinées par Atelya) y restent
    ancien = dossier / "matieres.json"
    catalogue = json.loads(ancien.read_text(encoding="utf-8")) if ancien.is_file() else {}
    for nom, ident, description in POLY_HAVEN:
        print(f"{nom} <- Poly Haven {ident}")
        catalogue[nom] = {"description": description, **poly_haven(dossier, nom, ident)}
    for nom, ident, description, taille in AMBIENTCG:
        print(f"{nom} <- ambientCG {ident}")
        catalogue[nom] = {"description": description, **ambientcg(dossier, nom, ident, taille)}
    for nom, entree in catalogue.items():
        entree["octets"] = sum(f.stat().st_size for f in (dossier / nom).glob("*.jpg"))
    (dossier / "matieres.json").write_text(json.dumps(catalogue, ensure_ascii=False, indent=2), encoding="utf-8")
    lignes = ["Matières de la bibliothèque d'Atelya : toutes sous licence CC0 1.0 (domaine public).",
              "Crédit non obligatoire, donné par reconnaissance.", ""]
    for nom, e in catalogue.items():
        lignes.append(f"{nom} : « {e.get('identifiant', nom)} » de {e.get('source', '?')} ({e.get('page', '-')}), "
                      f"par {', '.join(e.get('auteurs', [])) or 'non précisé'}, {e.get('licence', 'CC0 1.0')}.")
    (dossier / "CREDITS.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    total = sum(e["octets"] for e in catalogue.values())
    print(f"FINI : {len(catalogue)} matières, {total / 1e6:.1f} Mo dans {dossier}")


if __name__ == "__main__":
    main()
