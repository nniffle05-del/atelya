"""Commande unique : d'un logement.json vérifié à la maquette Blender et ses images.

    uv run python -m moteur.construire exemples/cas-test-00/logement.json sorties/cas-test-00

Produit dans le dossier de sortie :
- construction.json : les briques calculées, avec leur matériau, les lampes
  et les caméras (lisible, utile pour vérifier) ;
- maquette.blend : la maquette habillée, à ouvrir dans Blender, avec une scène par éclairage (menu des scènes) ;
- images/vue-dessus.png et images/vue-<pièce>.png : les deux images rendues.

Options : --sans-images (maquette seulement, rapide) ; --brouillon (images
petites et vite calculées, pour essayer).

Blender est lancé « sans écran » (en arrière-plan). Pour utiliser un autre
Blender que celui installé dans Applications, définir la variable
d'environnement BLENDER avec son chemin.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from moteur.habillage import plan_habille
from moteur.logement import charger_logement

DOSSIER_SCRIPTS = Path(__file__).parent / "blender"
# B2-3 : la bibliothèque de matières (photos CC0, hors Git). Variable ATELYA_MATIERES, sinon à côté du dépôt sur le PC.
MATIERES_PC = Path(__file__).resolve().parents[2] / "atelya" / "bibliotheque" / "matieres"
BLENDER_MAC = "/Applications/Blender.app/Contents/MacOS/Blender"

# Qualité des images : (échantillons, pourcentage de la taille finale 1600 × 1000).
QUALITES = {"finale": (512, 100), "brouillon": (16, 25)}  # B2-4 : 512 passes, sinon la lumière du jour marbre les murs


def trouver_blender() -> str | None:
    """Le chemin de Blender, ou None s'il est introuvable."""
    for candidat in (os.environ.get("BLENDER"), shutil.which("blender"), BLENDER_MAC):
        if candidat and Path(candidat).is_file():
            return candidat
    return None


def trouver_matieres() -> Path | None:
    """Le dossier de la bibliothèque de matières, ou None (Blender dessine alors ses sols par calcul)."""
    for candidat in (os.environ.get("ATELYA_MATIERES"), MATIERES_PC):
        if candidat and (Path(candidat) / "matieres.json").is_file():
            return Path(candidat)
    return None


MEUBLES_PC = Path(__file__).resolve().parents[2] / "atelya" / "bibliotheque" / "meubles-abo"


def trouver_meubles() -> Path | None:
    """Le dossier de la bibliothèque de meubles ABO, ou None (Blender pose alors des blocs aux bonnes dimensions)."""
    for candidat in (os.environ.get("ATELYA_MEUBLES"), MEUBLES_PC):
        if candidat and (Path(candidat) / "liste.json").is_file():
            return Path(candidat)
    return None


def choisir_modeles(plan: dict, bibliotheque: Path | None) -> dict:
    """Pour chaque meuble du commerce du plan : le modèle ABO le plus proche (catégorie, dimensions, couleur) et son fichier.
    Deux meubles identiques (mêmes catégorie, dimensions et couleur, comme 4 chaises autour d'une table) prennent le même
    modèle ; deux meubles différents de même catégorie dans le logement évitent de prendre le même."""
    if bibliotheque is None or not plan.get("meubles"):
        return plan
    from moteur.meubles import chemin_modele, charger_liste, choisir
    liste = charger_liste(bibliotheque)
    deja: dict[tuple, str] = {}
    pris: dict[str, set] = {}
    for m in plan["meubles"]:
        if m["sur_mesure"]:
            continue
        cle = (m["categorie"], tuple(round(d, 2) for d in m["dimensions"]), tuple(m["couleur"] or ()))
        ident = m.get("modele") or deja.get(cle)
        if ident is None:
            e = choisir(m["categorie"], m["dimensions"], m["couleur"], liste, exclure=pris.get(m["categorie"], set()))
            ident = e["id"] if e else None
        if ident is None:
            continue
        deja[cle] = ident
        pris.setdefault(m["categorie"], set()).add(ident)
        fichier = chemin_modele(bibliotheque, ident)
        if fichier is not None:
            m["modele"], m["fichier"] = ident, str(fichier.resolve())
    return plan


def lancer_blender(*arguments: str) -> None:
    blender = trouver_blender()
    if blender is None:
        raise FileNotFoundError("Blender introuvable (définir la variable BLENDER)")
    # -b : sans écran ; --factory-startup : sans les réglages ni modules perso ;
    # --python-exit-code 1 : signaler l'échec si le script plante.
    commande = [blender, "-b", "--factory-startup", "--python-exit-code", "1", *arguments]
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        raise RuntimeError(f"Blender a échoué :\n{resultat.stdout}\n{resultat.stderr}")


def construire(chemin_logement: str | Path, dossier_sortie: str | Path) -> Path:
    """Lit et vérifie le logement, calcule et habille les briques, fait construire Blender."""
    logement = charger_logement(chemin_logement)
    dossier = Path(dossier_sortie)
    dossier.mkdir(parents=True, exist_ok=True)

    plan = dossier / "construction.json"
    plan.write_text(json.dumps(choisir_modeles(plan_habille(logement), trouver_meubles()), indent=2, ensure_ascii=False),
                    encoding="utf-8")

    maquette = dossier / "maquette.blend"
    matieres = trouver_matieres()
    lancer_blender("--python", str(DOSSIER_SCRIPTS / "poser_briques.py"),
                   "--", str(plan), str(maquette), *([str(matieres.resolve())] if matieres else []))
    if json.loads(plan.read_text(encoding="utf-8")).get("reglages_teinte"):
        # B2 temps 2 : la teinte des sols vus sur une photo du client est réglée au rendu (voir regler_teintes.py).
        lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "regler_teintes.py"),
                       "--", str(plan), str(dossier / "reglages_teinte.json"))
    if json.loads(plan.read_text(encoding="utf-8")).get("vues"):
        # B2 temps 2 (09/11/2026) : une scène Blender par éclairage (jour, voilé, fin de journée, soirée, nuit) ; la scène
        # active reste le jour ensoleillé, où la teinte des sols vient d'être réglée (voir moteur/eclairages.py).
        from moteur.eclairages import poser as poser_eclairages
        poser_eclairages(plan, maquette, maquette)
    return maquette


def rendre(maquette: str | Path, dossier_images: str | Path,
           qualite: str = "finale") -> list[Path]:
    """Fait calculer par Blender une image par caméra de la maquette."""
    dossier = Path(dossier_images)
    dossier.mkdir(parents=True, exist_ok=True)
    for ancienne in dossier.glob("vue-*.png"):
        ancienne.unlink()
    echantillons, pourcentage = QUALITES[qualite]
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "rendre.py"),
                   "--", str(dossier), str(echantillons), str(pourcentage))
    return sorted(dossier.glob("vue-*.png"))


def mesurer(maquette: str | Path, sortie_json: str | Path) -> dict:
    """Fait mesurer par Blender chaque objet de la maquette (utilisé par les tests)."""
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "mesurer.py"),
                   "--", str(sortie_json))
    return json.loads(Path(sortie_json).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit la maquette Blender d'un logement.")
    parser.add_argument("logement", help="chemin du fichier logement.json")
    parser.add_argument("sortie", help="dossier où écrire construction.json, maquette.blend et images/")
    parser.add_argument("--sans-images", action="store_true", help="ne pas calculer les images")
    parser.add_argument("--brouillon", action="store_true", help="images petites et rapides")
    args = parser.parse_args()
    try:
        maquette = construire(args.logement, args.sortie)
        print(f"Maquette prête : {maquette}")
        if not args.sans_images:
            print("Calcul des images (quelques minutes)…")
            qualite = "brouillon" if args.brouillon else "finale"
            for image in rendre(maquette, Path(args.sortie) / "images", qualite):
                print(f"Image prête : {image}")
    except Exception as erreur:
        sys.exit(f"Échec : {erreur}")


if __name__ == "__main__":
    main()
