"""Le banc d'essai : lancer la lecture sur une série de plans et noter chacun (étape 5a).

Un banc d'essai est un dossier qui contient un sous-dossier par logement :

    banc/
      cas-test-00/
        logement.json      ← le corrigé (la bonne réponse)
        plan.png           ← un ou plusieurs dessins de ce logement,
        plan-douteux.png      tous les fichiers dont le nom commence par « plan »

Pour chaque plan, le banc lance la lecture automatique (lecture_plan.py), la
compare au corrigé (correcteur.py) et affiche la note. À la fin, il fait le
bilan de toute la série et l'écrit dans un fichier rapport.json, pour pouvoir
comparer deux versions du moteur.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2

from moteur.correcteur import Note, corriger

EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass
class Resultat:
    """La note d'un plan du banc, ou la raison de son échec."""

    plan: Path
    note: Note | None
    echec: str | None
    duree: float  # secondes


def trouver_plans(dossier: Path) -> list[tuple[Path, Path]]:
    """Les couples (image du plan, corrigé) du banc, dans l'ordre alphabétique."""
    couples = []
    for corrige in sorted(dossier.rglob("logement.json")):
        for image in sorted(corrige.parent.iterdir()):
            if image.suffix.lower() in EXTENSIONS and image.name.lower().startswith("plan"):
                couples.append((image, corrige))
    return couples


def essayer(image: Path, corrige: Path) -> Resultat:
    """Lit un plan et le note. Un plan illisible est un échec noté, pas une panne du banc."""
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    debut = time.perf_counter()
    vrai = json.loads(corrige.read_text(encoding="utf-8"))
    gris = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
    if gris is None:
        return Resultat(image, None, "image illisible", 0.0)
    try:
        lu = logement_depuis_plan(lire_plan(gris), "BANC")
        note = corriger(lu, vrai)
    except Exception as erreur:  # noqa: BLE001 : toute panne de la lecture est une note de zéro
        return Resultat(image, None, f"{type(erreur).__name__} : {erreur}", time.perf_counter() - debut)
    return Resultat(image, note, None, time.perf_counter() - debut)


def bilan(resultats: list[Resultat]) -> dict:
    """Les chiffres de toute la série : ce qu'on compare d'une version du moteur à l'autre."""
    notes = [r.note for r in resultats if r.note is not None]

    def taux(justes: str, vrais: str) -> float | None:
        total = sum(getattr(n, vrais) for n in notes)
        return round(sum(getattr(n, justes) for n in notes) / total, 4) if total else None

    return {
        "plans": len(resultats),
        "echecs": sum(r.note is None for r in resultats),
        "verts": sum(n.vert for n in notes),
        "taux_verts": round(sum(n.vert for n in notes) / len(resultats), 4) if resultats else None,
        "murs_justes": taux("murs_justes", "murs_vrais"),
        "murs_inventes": sum(n.murs_inventes for n in notes),
        "ouvertures_justes": taux("ouvertures_justes", "ouvertures_vraies"),
        "ouvertures_inventees": sum(n.ouvertures_inventees for n in notes),
        "pieces_justes": taux("pieces_justes", "pieces_vraies"),
        "pieces_inventees": sum(n.pieces_inventees for n in notes),
        "dimensions_justes": round(sum(n.ecart_dimensions <= 0.01 for n in notes) / len(notes), 4) if notes else None,
        "duree_moyenne_s": round(sum(r.duree for r in resultats) / len(resultats), 2) if resultats else None,
    }


def famille(image: Path) -> str:
    """La sorte de dessin, d'après le nom de l'image : « plan-travers.png » → « travers », « plan.png » → « propre »."""
    reste = image.stem.lower().removeprefix("plan").lstrip("-_ ")
    return reste or "propre"


def bilans_par_famille(resultats: list[Resultat]) -> dict[str, dict]:
    """Un bilan par sorte de dessin (propre, travers, photocopie…), pour voir où la lecture casse."""
    familles: dict[str, list[Resultat]] = {}
    for r in resultats:
        familles.setdefault(famille(r.plan), []).append(r)
    return {f: bilan(rs) for f, rs in sorted(familles.items())}


def _essayer_couple(couple: tuple[Path, Path]) -> Resultat:
    return essayer(*couple)


def _pourcent(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.0f} %"


def main() -> None:
    parser = argparse.ArgumentParser(description="Lance la lecture sur tous les plans d'un banc d'essai et les note.")
    parser.add_argument("dossier", nargs="?", default="exemples", help="dossier du banc (par défaut : exemples)")
    parser.add_argument("--rapport", default="sorties/banc/rapport.json", help="fichier où écrire le bilan détaillé")
    parser.add_argument("--seulement", help="ne lire que ces sortes de dessin, séparées par des virgules (ex. : propre,travers)")
    parser.add_argument("--processus", type=int, default=1,
                        help=f"nombre de plans lus en même temps (cet ordinateur a {os.cpu_count()} cœurs ; par défaut : 1)")
    args = parser.parse_args()

    dossier = Path(args.dossier)
    couples = trouver_plans(dossier)
    if not couples:
        sys.exit(f"Échec : aucun plan avec son logement.json dans {dossier}")

    if args.seulement:
        voulues = {f.strip() for f in args.seulement.split(",")}
        couples = [c for c in couples if famille(c[0]) in voulues]

    if args.processus > 1:
        from multiprocessing import Pool

        pool = Pool(args.processus)
        suite = pool.imap(_essayer_couple, couples)
    else:
        suite = map(_essayer_couple, couples)
    resultats = []
    for r in suite:
        resultats.append(r)
        image = r.plan
        nom = image.relative_to(dossier)
        if r.note is None:
            print(f"✗ {nom} : ÉCHEC de la lecture ({r.echec})")
            continue
        n = r.note
        print(
            f"{'✓' if n.vert else '✗'} {nom} : {'VERT' if n.vert else 'ROUGE'}, "
            f"{n.corrections} correction(s) ; murs {n.murs_justes}/{n.murs_vrais}, "
            f"ouvertures {n.ouvertures_justes}/{n.ouvertures_vraies}, pièces {n.pieces_justes}/{n.pieces_vraies} "
            f"({r.duree:.1f} s)"
        )
        for remarque in n.remarques:
            print(f"    - {remarque}")

    b = bilan(resultats)
    print()
    print(f"Bilan sur {b['plans']} plan(s) : {b['verts']} vert(s) ({_pourcent(b['taux_verts'])}), {b['echecs']} échec(s)")
    print(f"  murs justes {_pourcent(b['murs_justes'])} (inventés : {b['murs_inventes']})")
    print(f"  portes et fenêtres justes {_pourcent(b['ouvertures_justes'])} (inventées : {b['ouvertures_inventees']})")
    print(f"  pièces justes {_pourcent(b['pieces_justes'])} (inventées : {b['pieces_inventees']})")
    print(f"  dimensions justes à 1 % près : {_pourcent(b['dimensions_justes'])}")
    par_famille = bilans_par_famille(resultats)
    if len(par_famille) > 1:
        print("Par sorte de dessin :")
        for f, bf in par_famille.items():
            print(f"  {f:<12} {bf['verts']:>4}/{bf['plans']:<4} verts ({_pourcent(bf['taux_verts'])}), {bf['echecs']} échec(s), "
                  f"murs {_pourcent(bf['murs_justes'])}, ouvertures {_pourcent(bf['ouvertures_justes'])}, "
                  f"pièces {_pourcent(bf['pieces_justes'])}, dimensions {_pourcent(bf['dimensions_justes'])}")

    rapport = Path(args.rapport)
    rapport.parent.mkdir(parents=True, exist_ok=True)
    rapport.write_text(json.dumps({
        "bilan": b,
        "par_famille": par_famille,
        "plans": [
            {
                "plan": str(r.plan.relative_to(dossier)),
                "famille": famille(r.plan),
                "duree_s": round(r.duree, 2),
                "echec": r.echec,
                "note": r.note.en_dict() if r.note else None,
            }
            for r in resultats
        ],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"→ {rapport}")


if __name__ == "__main__":
    main()
