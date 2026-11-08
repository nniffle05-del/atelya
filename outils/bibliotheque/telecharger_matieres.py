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


def ambientcg(dossier: Path, nom: str, ident: str, taille=None) -> dict:
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
    catalogue = {}
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
        lignes.append(f"{nom} : « {e['identifiant']} » de {e['source']} ({e['page']}), "
                      f"par {', '.join(e['auteurs']) or 'non précisé'}, CC0 1.0.")
    (dossier / "CREDITS.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    total = sum(e["octets"] for e in catalogue.values())
    print(f"FINI : {len(catalogue)} matières, {total / 1e6:.1f} Mo dans {dossier}")


if __name__ == "__main__":
    main()
