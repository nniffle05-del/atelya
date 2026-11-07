"""La ligne de commande du générateur : `uv run python -m moteur.generateur <commande> …`.

Commandes :

  generer     fabrique un lot d'exemples (géométrie, images, masques, annotations, 3D en option)
  repartir    répartit les exemples acceptés entre train, validation et test (par familles)
  statistiques écrit rapports/statistiques.json et .txt
  controle    écrit les planches d'aperçu et la page rapports/controle.html
  doublons    cherche les doublons exacts et les plans trop semblables
  valider     revérifie les fichiers d'un jeu déjà écrit
  tout        generer + repartir + statistiques + controle, dans cet ordre

Exemples :

  uv run python -m moteur.generateur generer --nombre 100 --dossier sorties/jeu-100
  uv run python -m moteur.generateur generer --nombre 1000 --dossier sorties/jeu-1000 --processus 4
  uv run python -m moteur.generateur generer --nombre 50 --types T2,T3 --surface-min 40 --surface-max 80 --diversite 3
  uv run python -m moteur.generateur generer --nombre 20 --3d --variantes 2 --masques-par-classe --resolution 80
  uv run python -m moteur.generateur tout --nombre 100 --dossier sorties/jeu-100 --processus 4
  uv run python -m moteur.generateur generer --nombre 50 --familles photo --photo-realiste --dossier sorties/photos
  uv run python -m moteur.generateur generer --nombre 50 --lot2 --dossier sorties/lot2
  uv run python -m moteur.generateur repartir sorties/jeu-100 --parts 0.8,0.1,0.1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from moteur.generateur.exportateur import Options, ecrire_manifeste, generer_lot, repartir


def _options(args: argparse.Namespace) -> Options:
    return Options(
        dossier=Path(args.dossier), nombre=args.nombre, depart=args.depart, graine_styles=args.graine_styles,
        types=args.types.split(",") if args.types else None,
        surface_min=args.surface_min, surface_max=args.surface_max, pieces_min=args.pieces_min, pieces_max=args.pieces_max,
        resolution=args.resolution, diversite=args.diversite, variantes=args.variantes, modele_3d=args.modele_3d,
        masques_par_classe=args.masques_par_classe, reprise=not args.refaire, reglages=Path(args.reglages) if args.reglages else None,
        regles=Path(args.regles) if args.regles else None, familles=args.familles.split(",") if args.familles else None,
        vraie_camera=args.vraie_camera or args.photo_realiste, sans_cotes=args.sans_cotes,
        photo_realiste=args.photo_realiste, styles_monde=args.styles_monde, biais=args.biais, lot2=args.lot2,
    )


def _ajouter_options_generation(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dossier", default="sorties/jeu", help="dossier de sortie (par défaut : sorties/jeu)")
    p.add_argument("--nombre", type=int, default=100, help="nombre de graines à traiter (par défaut : 100)")
    p.add_argument("--depart", type=int, default=1, help="première graine (par défaut : 1)")
    p.add_argument("--graine-styles", type=int, default=0, help="décale le tirage des styles graphiques")
    p.add_argument("--types", help="types de logements, ex. T2,T3 (par défaut : tous)")
    p.add_argument("--surface-min", type=float, default=0.0, help="surface minimale en m²")
    p.add_argument("--surface-max", type=float, default=1e9, help="surface maximale en m²")
    p.add_argument("--pieces-min", type=int, default=0)
    p.add_argument("--pieces-max", type=int, default=99)
    p.add_argument("--resolution", type=float, help="pixels par mètre imposés (sinon 60 à 130 selon le style)")
    p.add_argument("--diversite", type=int, default=2, choices=[0, 1, 2, 3], help="diversité graphique, 0 sage à 3 maximale")
    p.add_argument("--familles", help="familles de style imposées, ex. architecte,agence,scan")
    p.add_argument("--vraie-camera", action="store_true", help="photos de biais vues par un vrai appareil (optique)")
    p.add_argument("--photo-realiste", action="store_true",
                   help="photos « vraie caméra » sur une vraie table : plis, ombres, reflets, flou (implique --vraie-camera)")
    p.add_argument("--styles-monde", action="store_true",
                   help="styles des vrais plans (sols dessinés, traits fins, gris clair, lettres A-D, capture, symboles du neuf) + styles absurdes")
    p.add_argument("--biais", action="store_true",
                   help="étape A3 : des angles du logement deviennent des pans coupés (30-60°) ou des angles arrondis")
    p.add_argument("--lot2", action="store_true",
                   help="styles du lot 2, vus sur 103 vrais plans (agence colorée, murs noirs, dimensions, légende Carrez, fenêtres cyan, cotes rouges, HSP, recadrage, page vue à l'écran…) ; certains plans ont en plus un exemple sœur <id>-ensemble (plusieurs niveaux ou deux logements sur une image)")
    p.add_argument("--sans-cotes", action="store_true", help="aucune cote dessinée (barre d'échelle, surfaces au hasard)")
    p.add_argument("--variantes", type=int, default=0, help="variantes graphiques supplémentaires par logement")
    p.add_argument("--3d", dest="modele_3d", action="store_true", help="écrit aussi modele.glb, modele.obj, construction.json")
    p.add_argument("--masques-par-classe", action="store_true", help="écrit un masque binaire par classe présente")
    p.add_argument("--refaire", action="store_true", help="refait les exemples déjà présents (sinon ils sont repris)")
    p.add_argument("--reglages", help="fichier JSON de réglages (surcharge de moteur/generateur/reglages.py)")
    p.add_argument("--regles", help="fichier JSON des règles du validateur")
    p.add_argument("--processus", type=int, default=1, help="exemples fabriqués en parallèle (par défaut : 1)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m moteur.generateur", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="commande", required=True)
    for nom in ("generer", "tout"):
        p = sous.add_parser(nom)
        _ajouter_options_generation(p)
        if nom == "tout":
            p.add_argument("--parts", default="0.8,0.1,0.1")
            p.add_argument("--graine-repartition", type=int, default=0)
            p.add_argument("--planches", type=int, default=30)
    p = sous.add_parser("repartir")
    p.add_argument("dossier")
    p.add_argument("--parts", default="0.8,0.1,0.1", help="parts train,validation,test (par défaut 0.8,0.1,0.1)")
    p.add_argument("--graine-repartition", type=int, default=0)
    p.add_argument("--seuil", type=float, help="distance en dessous de laquelle deux plans sont trop semblables")
    p = sous.add_parser("statistiques")
    p.add_argument("dossier")
    p = sous.add_parser("controle")
    p.add_argument("dossier")
    p.add_argument("--planches", type=int, default=30, help="nombre d'exemples sur la page (par défaut : 30)")
    p = sous.add_parser("doublons")
    p.add_argument("dossier")
    p.add_argument("--seuil", type=float)
    p = sous.add_parser("valider")
    p.add_argument("dossier")
    p.add_argument("--regles")
    args = parser.parse_args(argv)

    if args.commande in ("generer", "tout"):
        opt = _options(args)
        bilan = generer_lot(opt, processus=args.processus)
        print(json.dumps(bilan, ensure_ascii=False, indent=1))
        if bilan["acceptes_dans_le_manifeste"] == 0:
            sys.exit("Échec : aucun exemple accepté")
        if args.commande == "tout":
            dossier = opt.dossier
            parts = tuple(float(x) for x in args.parts.split(","))
            r = repartir(dossier, parts, args.graine_repartition)  # type: ignore[arg-type]
            print("répartition :", r["comptes"], "— déplacés vers train :", len(r["deplaces_vers_train"]))
            from moteur.generateur import controle_qualite, statistiques
            stats = statistiques.ecrire(dossier)
            print(statistiques.resume(stats))
            print("page de contrôle :", controle_qualite.page(dossier, args.planches))
    elif args.commande == "repartir":
        parts = tuple(float(x) for x in args.parts.split(","))
        r = repartir(Path(args.dossier), parts, args.graine_repartition, args.seuil)  # type: ignore[arg-type]
        print(json.dumps({k: r[k] for k in ("comptes", "familles", "deplaces_vers_train")}, ensure_ascii=False, indent=1))
        print(f"{len(r['doublons_exacts'])} groupes de doublons exacts, {len(r['trop_semblables'])} paires trop semblables")
    elif args.commande == "statistiques":
        from moteur.generateur import statistiques
        print(statistiques.resume(statistiques.ecrire(Path(args.dossier))))
    elif args.commande == "controle":
        from moteur.generateur import controle_qualite
        print("page de contrôle :", controle_qualite.page(Path(args.dossier), args.planches))
    elif args.commande == "doublons":
        from moteur.generateur.doublons import SEUIL_RESSEMBLANCE, chercher
        dossier = Path(args.dossier)
        entrees = []
        for m in sorted((dossier / "exemples").glob("*/manifeste.json")):
            e = json.loads(m.read_text(encoding="utf-8"))
            # Un -ensemble n'est pas un logement de plus : deux ensembles ne se ressemblent pas au sens où deux plans se ressemblent.
            if e["accepte"] and "parent" not in e:
                entrees.append({"id": e["id"], "empreinte": e["empreinte"], "signature": e["signature"]})
        rapport = chercher(entrees, args.seuil if args.seuil is not None else SEUIL_RESSEMBLANCE)
        (dossier / "rapports").mkdir(exist_ok=True)
        (dossier / "rapports" / "doublons.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{rapport['nombre']} exemples : {len(rapport['doublons_exacts'])} groupes de doublons exacts, "
              f"{len(rapport['trop_semblables'])} paires trop semblables (seuil {rapport['seuil']})")
    elif args.commande == "valider":
        from moteur.generateur.validateur import Regles, valider_dossier
        dossier = Path(args.dossier)
        regles = Regles.charger(args.regles)
        n = ko = 0
        for d in sorted((dossier / "exemples").glob("*/")):
            if not (d / "manifeste.json").exists():
                continue
            v = valider_dossier(d, regles)
            n += 1
            if not v.accepte:
                ko += 1
                print(d.name, ":", "; ".join(v.erreurs[:3]))
            m = json.loads((d / "manifeste.json").read_text(encoding="utf-8"))
            m["accepte"], m["erreurs"], m["avertissements"] = v.accepte, v.erreurs, v.avertissements
            (d / "manifeste.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / "validation.json").write_text(json.dumps(v.en_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        ecrire_manifeste(dossier)
        print(f"{n} exemples revérifiés, {ko} rejetés")


if __name__ == "__main__":
    main()
