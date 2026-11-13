"""Télécharge les meubles 3D d'ABO (Amazon Berkeley Objects), version officielle d'Amazon.

Pourquoi : pour meubler la maquette avec de vrais meubles (canapés, chaises,
tapis, lampes…) photographiés et modélisés par Amazon, textures 4096 points.
Essai du 08/11/2026 sur 5 meubles : version officielle et version allégée de
Hugging Face (codepawl/abo-glb, textures 2048) ont exactement la même forme ;
l'officielle est un peu plus fine de très près → NT : « le plus réaliste ».

Licence : CC BY 4.0 (texte lu). Obligation : créditer « Amazon.com » ; les
marques des produits ne sont pas couvertes (ne jamais les afficher).

La liste des meubles vient de metadata.jsonl (codepawl/abo-glb, mêmes
identifiants qu'ABO, taille d'origine de chaque fichier). On écarte ce qui
n'a rien à faire dans un appartement (bureautique, électronique, sport…).

Utilisation (chemins RELATIFS, à cause des accents) :
    python outils/bibliotheque/telecharger_meubles.py ../atelya/bibliotheque/meubles-essai/metadata-hf.jsonl ../atelya/bibliotheque/meubles-abo [--fils 4]

Reprend où il s'est arrêté (fichier déjà là et de la bonne taille = sauté).
Écrit progression.json (pour la surveillance) et CREDITS.txt.
Code de sortie 1 et ligne « PLANTÉ » si des fichiers n'ont pas pu être pris.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

NOM_PROGRAMME = "Atelya/0.1 (bibliotheque de meubles)"
ADRESSE = "https://amazon-berkeley-objects.s3.amazonaws.com/3dmodels/original/{dossier}/{ident}.glb"

# Types de produits ABO sans intérêt pour meubler un logement.
ECARTES = {
    "office products", "sporting goods", "electric fan", "flat screen display mount", "multiport hub",
    "professional healthcare", "auto accessory", "air conditioner", "ladder", "electronic cable",
    "building material", "portable electronic device stand", "exercise mat", "computer add on",
    "sound and recording equipment", "tools", "mouse pad", "writing board", "janitorial supply", "biss",
    "paper product", "ce accessory", "portable electronic device cover", "instrument parts and accessories",
    "dehumidifier", "handbag", "animal collar", "portable electronic device mount", "carrying case or bag",
    "computer", "accessory or part or supply", "battery", "electronic adapter", "wireless accessory",
    "file folder", "fitness bench", "consumer electronics", "cellular phone case", "body positioner",
    "rowing machine", "utility cart wagon", "freestanding shelter", "furniture cover",
}


def lire_url(url: str) -> bytes:
    requete = urllib.request.Request(url, headers={"User-Agent": NOM_PROGRAMME})
    with urllib.request.urlopen(requete, timeout=300) as reponse:
        return reponse.read()


def prendre(meuble: dict, dossier: Path) -> tuple[str, int, str]:
    """Renvoie (identifiant, octets écrits, erreur ou "")."""
    ident = meuble["id"]
    chemin = dossier / ident[-1] / f"{ident}.glb"
    attendu = meuble.get("source_bytes")
    if chemin.exists() and (attendu is None or chemin.stat().st_size == attendu):
        return ident, 0, ""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    derniere = ""
    for essai in range(4):
        try:
            donnees = lire_url(ADRESSE.format(dossier=ident[-1], ident=ident))
            if donnees[:4] != b"glTF":
                return ident, 0, "pas un fichier glb"
            if attendu is not None and len(donnees) != attendu:
                derniere = f"taille {len(donnees)} au lieu de {attendu}"
                time.sleep(5 * (essai + 1))
                continue
            provisoire = chemin.with_suffix(".part")
            provisoire.write_bytes(donnees)
            provisoire.replace(chemin)
            return ident, len(donnees), ""
        except OSError as erreur:
            derniere = str(erreur)
            time.sleep(10 * (essai + 1))
    return ident, 0, derniere


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("metadata")
    parametres.add_argument("dossier")
    parametres.add_argument("--fils", type=int, default=4, help="fichiers téléchargés en même temps")
    args = parametres.parse_args()
    dossier = Path(args.dossier)
    dossier.mkdir(parents=True, exist_ok=True)

    tous = [json.loads(ligne) for ligne in open(args.metadata, encoding="utf-8")]
    meubles = [m for m in tous if m.get("product_type") not in ECARTES]
    total = sum(m.get("source_bytes") or 0 for m in meubles)
    (dossier / "liste.json").write_text(json.dumps(
        [{k: m.get(k) for k in ("id", "name", "product_type", "color", "material", "style",
                                "size_metres", "source_texture_px", "source_bytes")} for m in meubles],
        ensure_ascii=False, indent=1), encoding="utf-8")
    (dossier / "CREDITS.txt").write_text(
        "Meubles 3D : Amazon Berkeley Objects (ABO), données et modèles 3D par Amazon.com,\n"
        "sous licence Creative Commons Attribution 4.0 International (CC BY 4.0).\n"
        "Jeu de données construit par M. Guillaumin, T. Dideriksen, K. Deng, H. Arora, A. Dhua, X. Zhang,\n"
        "T. Yago-Vicente (Amazon.com), J. Collins, S. Goel, J. Malik (UC Berkeley).\n"
        "Source : https://amazon-berkeley-objects.s3.amazonaws.com/index.html\n"
        "Les marques et noms de produits appartiennent à leurs propriétaires et ne sont pas couverts par la licence.\n",
        encoding="utf-8")

    verrou = threading.Lock()
    etat = {"meubles": len(meubles), "ecartes": len(tous) - len(meubles), "octets_attendus": total,
            "faits": 0, "octets_recus": 0, "echecs": {}, "debut": time.time()}

    def ecrire_progression(fini=False):
        ecoule = time.time() - etat["debut"]
        vitesse = etat["octets_recus"] / ecoule if ecoule > 0 else 0
        sortie = dict(etat, fini=fini, vitesse_mo_s=round(vitesse / 1e6, 2), minutes=round(ecoule / 60, 1),
                      maj=time.strftime("%Y-%m-%d %H:%M:%S"))
        (dossier / "progression.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.fils) as pool:
        taches = [pool.submit(prendre, m, dossier) for m in meubles]
        for tache in as_completed(taches):
            ident, octets, erreur = tache.result()
            with verrou:
                etat["faits"] += 1
                etat["octets_recus"] += octets
                if erreur:
                    etat["echecs"][ident] = erreur
                if etat["faits"] % 10 == 0 or erreur:
                    ecrire_progression()
                if etat["faits"] % 200 == 0:
                    print(f"{etat['faits']}/{len(meubles)} meubles, {etat['octets_recus'] / 1e9:.1f} Go reçus, "
                          f"{len(etat['echecs'])} échecs", flush=True)
    ecrire_progression(fini=True)
    presents = sum(1 for m in meubles if (dossier / m["id"][-1] / f"{m['id']}.glb").exists())
    print(f"FINI : {presents}/{len(meubles)} meubles présents, {len(etat['echecs'])} échecs", flush=True)
    if etat["echecs"]:
        print(f"PLANTÉ : {len(etat['echecs'])} meubles non pris (voir progression.json) ; relancer la même commande reprend",
              flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
