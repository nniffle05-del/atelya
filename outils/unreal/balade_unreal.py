"""La BALADE d'un logement dans Unreal : une seule prise continue, choisie par Atelya, de bout en bout (12/11/2026).

    python outils/unreal/balade_unreal.py <paquet> <nom> <logement.json> [--eclairage jour_soleil] [--moteur lumen_max]

1. le PROMENEUR (moteur/promeneur.py) trace la balade d'après le plan : portes à ouvrir, chemin, regard ; balade.json et
   balade.png (vue de dessus) ;
2. Unreal : portes ouvertes, plafonniers allumés dans les pièces sans fenêtre, caméra sur le chemin ;
3. le photographe EN MARCHANT : un essai par seconde de film, l'exposition voulue à chaque essai, lissée comme un œil qui
   s'adapte (moteur/photographe.exposition_en_marchant), posée en clés sur la séquence ; un second essai la corrige ;
4. le film (Movie Render Queue), son contrôle (murs à la clarté visée, image par image) et sa vidéo.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cinematique_unreal as cu  # noqa: E402

from moteur import photographe, promeneur  # noqa: E402

PREMIER_ESSAI = -9.0
PASSES = 2  # essais du photographe en marchant


def numero(chemin: Path) -> int:
    """Image de la séquence (0 = la première) d'après le nom d'un fichier de Movie Render Queue (« …0001.png » = 0)."""
    return int(chemin.name.rsplit(".", 2)[-2]) - 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paquet")
    p.add_argument("nom")
    p.add_argument("logement")
    p.add_argument("--eclairage", default="jour_soleil")
    p.add_argument("--moteur", default="lumen_max", choices=["lumen", "lumen_max", "path_tracer"])
    a = p.parse_args()
    debut = time.time()
    paquet = Path(a.paquet)
    fiche = json.loads((paquet / "scene-atelya.json").read_text(encoding="utf-8"))
    ambiance = next((x for x in fiche.get("eclairages", []) if a.eclairage in (x.get("id"), x.get("nom"))), None)
    if ambiance is None:
        sys.exit(f"PLANTÉ : éclairage « {a.eclairage} » absent de la fiche")
    nom_dossier = f"balade-{ambiance['id']}"
    sortie = cu.STUDIO / "Paquets" / "rendus" / a.nom / nom_dossier
    sortie.mkdir(parents=True, exist_ok=True)
    logement = json.loads(Path(a.logement).read_text(encoding="utf-8"))
    print("1. Le promeneur trace la balade", flush=True)
    b = promeneur.balade(logement, scene_eclairage=ambiance.get("nom"))
    (sortie / "balade.json").write_text(json.dumps(b, indent=1, ensure_ascii=False), encoding="utf-8")
    promeneur.dessiner(logement, b, sortie / "balade.png")
    print(f"   {b['longueur_m']} m, {b['duree_s']} s ; portes ouvertes {[x['id'] for x in b['portes_ouvertes']]}", flush=True)
    trajet = paquet / "trajet-balade.json"
    trajet.write_text(json.dumps({**b["trajet"], "essai_pas": promeneur.IPS}, ensure_ascii=False), encoding="utf-8")
    reglage = sortie.parent / f"reglage-{nom_dossier}.json"
    clarte = photographe.clarte_visee(ambiance)
    balance = float(ambiance.get("balance", photographe.FORCE_BALANCE))
    base = {"eclairage": ambiance["id"], "moteur": a.moteur, "dossier": nom_dossier, "portes_ouvertes": b["portes_ouvertes"],
            "lampes_pieces": [] if ambiance.get("lampes") else b["pieces_sans_fenetre"]}

    def preparer(exposition, gain, cles=None):
        contenu = {**base, "exposition": exposition, "gain": list(gain)}
        if cles:
            contenu["exposition_cles"] = cles
        reglage.write_text(json.dumps(contenu, indent=1, ensure_ascii=False), encoding="utf-8")
        cu._python_unreal(cu.SCRIPTS_UE / "preparer_cinematique.py", paquet.as_posix(), a.nom, trajet.as_posix(),
                          reglage.as_posix())

    essai = sortie / "essai"
    cles, gain, historique = None, [1.0, 1.0, 1.0], []
    for passe in range(PASSES):
        preparer(PREMIER_ESSAI if cles is None else cles[0][1], gain, cles)
        if essai.exists():
            shutil.rmtree(essai)
        duree = cu.rendre(a.nom, "Essai")
        images, masques = cu.images_d_essai(essai)
        m = photographe.mesurer(images, masques, clarte, balance, gain)
        numeros = [numero(x) for x in images]
        if cles is None:
            actuelles = [PREMIER_ESSAI] * len(numeros)
        else:
            actuelles = list(np.interp(numeros, [c[0] for c in cles], [c[1] for c in cles]))
        voulues = [None if i["correction"] is None else e + i["correction"] for e, i in zip(actuelles, m["images"])]
        cles = photographe.exposition_en_marchant(numeros, voulues, promeneur.IPS)
        gain = m["gain"]
        ecarts = [abs(i["correction"]) for i in m["images"] if i["correction"] is not None]
        historique.append({"passe": passe + 1, "essais": len(images), "duree_s": round(duree, 1),
                           "ecart_median_crans": round(float(np.median(ecarts)), 2) if ecarts else None})
        print(f"2. Essai {passe + 1} : {len(images)} images en {duree:.0f} s ; écart médian des murs "
              f"{historique[-1]['ecart_median_crans']} cran", flush=True)
    cles_film = [[c[0], round(c[1] + photographe.ESSAI_VERS_FILM, 3)] for c in cles]
    preparer(cles_film[0][1], gain, cles_film)
    for ancienne in sortie.glob("image-*.png"):
        ancienne.unlink()
    print(f"3. Rendu du film ({b['trajet']['images']} images)", flush=True)
    duree = cu.rendre(a.nom, "Rendu")
    pngs = [sortie / f"image-{numero(x) + 1:04d}.png" for x in masques]
    presents = [(x, y) for x, y in zip(pngs, masques) if x.is_file()]
    controle = photographe.mesurer([x for x, _ in presents], [y for _, y in presents], clarte, balance, gain)
    ecarts = [i["correction"] for i in controle["images"] if i["correction"] is not None]
    film = cu.video(sortie, promeneur.IPS)
    bilan = {"logement": logement.get("projet_id"), "eclairage": ambiance["id"], "moteur": a.moteur,
             "duree_film_s": b["duree_s"], "longueur_m": b["longueur_m"], "images": len(list(sortie.glob("image-*.png"))),
             "rendu_min": round(duree / 60, 1), "calcul_total_min": round((time.time() - debut) / 60, 1),
             "essais": historique, "controle_murs_crans": {"median": round(float(np.median(ecarts)), 2),
                                                           "max_abs": round(float(np.max(np.abs(ecarts))), 2)},
             "portes_ouvertes": [x["id"] for x in b["portes_ouvertes"]], "video": str(film)}
    (sortie / "balade-bilan.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"4. Balade : {film} ({bilan['duree_film_s']} s) ; murs {bilan['controle_murs_crans']} cran ; "
          f"calcul {bilan['calcul_total_min']} min", flush=True)


if __name__ == "__main__":
    main()
