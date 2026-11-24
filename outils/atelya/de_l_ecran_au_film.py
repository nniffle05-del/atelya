r"""LA SUITE DE LA CHAÎNE, EN UNE COMMANDE : de l'écran de vérification terminé jusqu'au film (examen app-004, 15/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\atelya\de_l_ecran_au_film.py <dossier de lecture> <dossier des photos>
        [--sortie ..\atelya\b2\<logement>\chaine] [--eclairage jour_voile] [--depuis enveloppe|baies|sols|meubles|maquette|paquet|import|film]
        [--jusqu-a …] [--sans-vue] [--sans-verification]

Pourquoi : jusqu'ici chaque brique se lançait à la main, avec des copies de fichiers entre elles (carte du 16/11/2026 dans
docs/projet/memoire/produit-livre-client.md, « LA SUITE DE LA CHAÎNE »). Ici chaque JOINTURE est écrite une fois pour toutes :

    écran terminé (logement-verifie.json + questions-photos\cameras-photos-seul.json, voir fin-verification.json)
      0. enveloppe moteur
accorder_murs.fermer_les_fentes      → logement-depart.json (fentes entre bouts de murs refermées)
         baies     moteur/ouvertures_photos                             → les baies qui descendent jusqu'au sol, lues sur les photos
                   (avec --lecture-photos : largeur des baies, leur bas et leur haut mesurés sur les photos — moteur/hauteur_baies —,
                   dessin des fenêtres, ferronnerie)
      1. sols      outils\habillage\sols_photos.py logement         → logement-sols.json
      2. meubles   outils\habillage\reperer_meubles_photos.py       → logement-meuble.json
      3. maquette  python -m moteur.construire … --sans-images      → 3d\maquette.blend           (Blender)
      4. paquet    outils\unreal\exporter_pour_unreal.py            → unreal\export
                   + copie dans D:\Atelya-Unreal\Paquets\<nom sans accent>   (Unreal ne veut pas d'accents)
      5. import    moteur\unreal\importer_maquette.py               → /Game/Logements/<nom>       (Unreal, éditeur FERMÉ)
      6. film      outils\unreal\balade_unreal.py                   → film.mp4, recopié dans <sortie>\film

--sans-verification : un PREMIER FILM sans passer par l'écran (logement tel qu'il a été lu, photos rangées par Atelya seul avec
ce que le client a dit de chaque photo) : pour voir tout de suite ce que donne la lecture, ou refaire un film après une correction
d'Atelya sans redemander la vérification.

Sans orientation connue (pas de nord), le film est tourné en « Jour voilé » (règle proposée à NT le 11/11/2026). La vraie vue
par les fenêtres est tirée des photos rangées à l'écran (--sans-vue pour s'en passer). L'ordinateur est tenu éveillé pendant
toute la chaîne. Une étape qui échoue arrête tout avec une ligne « PLANTÉ … » et un code ≠ 0 ; --depuis reprend à une étape.
Chaque étape écrit son journal dans <sortie>\journaux\ et sa durée dans <sortie>\chaine.json.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "unreal"))

ETAPES = ("enveloppe", "baies", "sols", "meubles", "maquette", "paquet", "import", "film")
MODELE_SOLS = RACINE / "moteur" / "modeles" / "sols-vits14-v2.pt"
FICHE_PHOTOS = Path("questions-photos") / "cameras-photos-seul.json"


def dire(*a) -> None:
    print(*a, flush=True)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def nom_sans_accent(projet: str) -> str:
    """« app-004 » → « app004 » : le nom du logement dans Unreal (lettres et chiffres seulement)."""
    nom = re.sub(r"[^A-Za-z0-9]", "", projet)
    if not nom:
        raise ValueError(f"nom de logement inutilisable pour Unreal : {projet!r}")
    return nom


def lancer(etape: str, commande: list, journaux: Path, env: dict | None = None) -> float:
    """Une étape = une commande ; sa sortie va à l'écran et dans journaux\\<étape>.txt ; code ≠ 0 → on arrête tout."""
    journaux.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    dire(f"\n=== {etape} : {' '.join(str(c) for c in commande[1:4])} …")
    with open(journaux / f"{etape}.txt", "w", encoding="utf-8") as j:
        p = subprocess.Popen([str(c) for c in commande], cwd=RACINE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace",
                             env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **(env or {})})
        for ligne in p.stdout:
            j.write(ligne)
            j.flush()
            dire("   " + ligne.rstrip()[:300])
        code = p.wait()
    duree = time.time() - debut
    if code != 0:
        dire(f"PLANTÉ à l'étape « {etape} » (code {code}) : voir {journaux / (etape + '.txt')}")
        sys.exit(code or 1)
    dire(f"=== {etape} : fait en {duree:.0f} s")
    return duree


def main() -> int:
    ap = argparse.ArgumentParser(description="De l'écran de vérification terminé jusqu'au film, sans commande entre les étapes")
    ap.add_argument("lecture", type=Path, help="le dossier de lecture (logement-verifie.json, questions-photos\\…)")
    ap.add_argument("photos", type=Path, help="le dossier des photos du client")
    ap.add_argument("--sortie", type=Path, help="défaut : ..\\atelya\\b2\\<logement>\\chaine")
    ap.add_argument("--eclairage", default="jour_voile", help="jour_voile par défaut (aucune orientation connue)")
    ap.add_argument("--depuis", choices=ETAPES, default=ETAPES[0])
    ap.add_argument("--jusqu-a", choices=ETAPES, default=ETAPES[-1])
    ap.add_argument("--sans-vue", action="store_true", help="ne pas tirer la vue par les fenêtres des photos")
    ap.add_argument("--sans-verification", action="store_true",
                    help="pas d'écran : le logement tel qu'il a été lu (verification.json) et les photos rangées par Atelya seul")
    ap.add_argument("--logement", type=Path, help="banc : partir de CE logement (au lieu de celui du dossier de lecture)")
    ap.add_argument("--fiche", type=Path, help="banc : la fiche des photos placées à utiliser (ex. caméras relevées à la main)")
    ap.add_argument("--lecture-photos", type=Path,
                    help="essai : le dossier d'une lecture des photos (lecture.json et dossier envoi, outils/lecture_photos) ; les baies, "
                         "les sols, les meubles et les équipements (cheminée, radiateurs, cuisine, salle de bains, rideaux, passe-plat : "
                         "moteur/equipements.py) suivent ce que la lecture dit")
    ap.add_argument("--sortes-du-detecteur", action="store_true",
                    help="essai, avec --lecture-photos : les mêmes rectangles, mais avec la sorte du détecteur (la référence)")
    a = ap.parse_args()

    verifie, fiche = a.lecture / "logement-verifie.json", a.lecture / FICHE_PHOTOS
    lu = a.lecture / "verification.json"
    if a.logement is not None:  # le banc de ressemblance : un logement et une fiche donnés, rien à ranger
        if a.fiche is None:
            dire("PLANTÉ : --logement va avec --fiche")
            return 2
        verifie, fiche, a.sans_verification = a.logement, a.fiche, False
    attendus = (lu, a.photos, MODELE_SOLS) if a.sans_verification else (verifie, fiche, a.photos, MODELE_SOLS)
    for f in attendus:
        if not f.exists():
            dire(f"PLANTÉ : introuvable : {f}")
            return 2
    if a.sans_verification:
        logement_de_depart = json.loads(lu.read_text(encoding="utf-8"))["logement"]
    else:
        logement_de_depart = json.loads(verifie.read_text(encoding="utf-8"))
    projet = logement_de_depart.get("projet_id") or a.lecture.name
    nom = nom_sans_accent(projet)
    sortie = a.sortie or RACINE.parent / "atelya" / "b2" / projet / "chaine"
    sortie.mkdir(parents=True, exist_ok=True)
    journaux = sortie / "journaux"
    depart = sortie / "logement-depart.json"
    sols, meuble, d3, export = sortie / "logement-sols.json", sortie / "logement-meuble.json", sortie / "3d", sortie / "unreal" / "export"
    py = sys.executable
    faire = ETAPES[ETAPES.index(a.depuis):ETAPES.index(a.jusqu_a) + 1]
    bilan_f = sortie / "chaine.json"
    bilan = json.loads(bilan_f.read_text(encoding="utf-8")) if bilan_f.is_file() else {}
    bilan.update(logement=projet, nom_unreal=nom, eclairage=a.eclairage)
    bilan.setdefault("durees_s", {})

    def note(etape: str, duree: float) -> None:
        bilan["durees_s"][etape] = round(duree, 1)
        bilan_f.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")

    # l'ordinateur reste éveillé tant que cette commande tourne (une veille coupe un rendu)
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)

    import cinematique_unreal as cu
    paquet = cu.STUDIO / "Paquets" / nom
    if {"import", "film"} & set(faire) and cu.editeur_ouvert():
        dire("PLANTÉ : l'éditeur Unreal est ouvert ; le fermer avant un rendu (éditeur + rendu = plantage de la carte graphique)")
        return 3

    if "enveloppe" in faire or not depart.is_file():
        # jointure : les fentes entre deux bouts de murs (mur raccourci à l'écran…) sont refermées avant de construire
        from moteur.raccorder_murs import fermer_les_fentes
        debut = time.time()
        dire("\n=== enveloppe : les murs sont-ils raccordés ?")
        logement, bilan_env = fermer_les_fentes(logement_de_depart, journal=lambda s: dire("   " + s))
        depart.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
        bilan["enveloppe"] = bilan_env
        note("enveloppe", time.time() - debut)
    if a.sans_verification:
        fiche = sortie / "cameras-photos-seul.json"
        if "enveloppe" in faire or not fiche.is_file():  # pas d'écran : Atelya range les photos seul, sur le logement lu
            note("photos", lancer("photos", [py, "outils/habillage/caler_photos_seul.py", depart, a.photos, fiche], journaux))
    if "baies" in faire:
        # jointure : ce que le plan ne dit pas et que les photos montrent (une baie qui descend jusqu'au sol)
        from moteur import ouvertures_photos
        debut = time.time()
        dire("\n=== baies : que montrent les photos ?")
        logement = json.loads(depart.read_text(encoding="utf-8"))
        if a.lecture_photos and not a.sortes_du_detecteur:
            # F1 (20/11/2026, accord de NT) : une fenêtre que les photos montrent NETTEMENT plus large que le plan est élargie
            # (moteur/largeur_baies.py) ; d'abord, pour que la sorte de baie (ci-dessous) se lise sur la baie entière
            sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
            import poser_photos_lues
            from moteur import largeur_baies
            fiche_lue = json.loads(fiche.read_text(encoding="utf-8"))
            mesures = largeur_baies.lire(logement, fiche_lue, poser_photos_lues.objets_des_photos(fiche_lue, a.lecture_photos))
            logement, elargies, doutes_largeur = largeur_baies.elargir(logement, mesures, journal=lambda s: dire("   " + s))
            bilan["largeur_des_baies"] = {"mesures": mesures, "changements": elargies, "doutes": doutes_largeur}
            dire(f"   {len(elargies)} baie(s) élargie(s) d'après les photos, {len(doutes_largeur)} doute(s)")
        votes = ouvertures_photos.lire(logement, json.loads(fiche.read_text(encoding="utf-8")), RACINE, journal=lambda s: dire("   " + s))
        logement, changes = ouvertures_photos.corriger(logement, votes, journal=lambda s: dire("   " + s))
        if a.lecture_photos and not a.sortes_du_detecteur:
            # essai : la sorte de baie LUE sur les photos (« porte_fenetre » ou « fenetre ») prime sur la mesure du bas de la baie
            sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
            import poser_photos_lues
            lus = poser_photos_lues.baies_lues(logement, json.loads(fiche.read_text(encoding="utf-8")), a.lecture_photos)
            logement, changes_lus, desaccords = poser_photos_lues.photos_lues.corriger_les_baies(
                logement, lus, votes, journal=lambda s: dire("   lu : " + s))
            bilan["baies_lues"] = {"votes": lus, "changements": changes_lus, "desaccords": desaccords}
            changes = changes + changes_lus
        if a.lecture_photos and not a.sortes_du_detecteur and (a.lecture_photos / "vitrages.json").is_file():
            # F2 pièce 3 (20/11/2026) : le DESSIN de chaque fenêtre lu sur les photos (vantaux, petits bois, largeur du cadre,
            # partie pleine sous les vitres, garde-corps) est posé sur l'ouverture ; la maquette la construit ainsi
            # (moteur/dessin_fenetres.py). Après la sorte de baie : une baie qui descend au sol garde sa partie pleine.
            from moteur import dessin_fenetres, hauteur_baies
            lecture_des_fenetres = json.loads((a.lecture_photos / "vitrages.json").read_text(encoding="utf-8"))
            # LE BAS ET LE HAUT de chaque fenêtre mesurés sur les photos (moteur/hauteur_baies.py, 23/11/2026, accord de NT) : le
            # plan n'en dit rien (hauteurs par défaut). Par les lignes lues (sol, tour de la menuiserie, plafond), contrôlées
            # par le relief de la photo. Après la sorte de baie (que la mesure du bas précise), avant le dessin (posé en parts
            # de la baie : la baie mesurée EST la menuiserie).
            fiche_des_photos = json.loads(fiche.read_text(encoding="utf-8"))
            a_mesurer = {p for p, fs in (lecture_des_fenetres.get("photos") or {}).items() if any(f.get("cadre") for f in fs)}
            reperes, tailles = hauteur_baies.reperes_des_photos(fiche_des_photos, RACINE, float(logement.get("hauteur_sous_plafond", 2.5)),
                                                                 noms=a_mesurer & set(fiche_des_photos.get("cameras", {})))
            hauteurs = hauteur_baies.lire(logement, lecture_des_fenetres, reperes, tailles)
            logement, rehaussees, doutes_hauteur = hauteur_baies.corriger(logement, hauteurs, journal=lambda s: dire("   " + s))
            bilan["hauteur_des_baies"] = {"mesures": {b: {k: v for k, v in m.items() if k != "mesures"} for b, m in hauteurs.items()},
                                          "par_photo": {b: [{k: v for k, v in p.items() if k != "points"} for p in m["mesures"]]
                                                        for b, m in hauteurs.items()},
                                          "changements": rehaussees, "doutes": doutes_hauteur}
            dire(f"   {len(rehaussees)} baie(s) au bas ou au haut corrigés d'après les photos, {len(doutes_hauteur)} doute(s)")
            del reperes
            logement, dessinees = dessin_fenetres.appliquer(logement, lecture_des_fenetres, journal=lambda s: dire("   dessin : " + s))
            bilan["dessin_des_fenetres"] = dessinees
            dire(f"   {len(dessinees)} fenêtre(s) dessinée(s) d'après les photos")
            # … et la FERRONNERIE de leurs garde-corps, recopiée des photos (moteur/ferronnerie.py, 20/11/2026) : un garde-corps
            # en fonte est un dessin plat, que la photo montre en sombre sur le dehors ; sans motif lisible : barreaux droits
            from moteur import ferronnerie
            # les photos : celles de la fiche des photos placées (le banc ne donne pas le dossier du client), sinon le dossier donné
            dossier_de_la_fiche = RACINE / str(json.loads(fiche.read_text(encoding="utf-8")).get("photos") or "")
            photos_des_fenetres = dossier_de_la_fiche if dossier_de_la_fiche.is_dir() and dossier_de_la_fiche != RACINE else a.photos
            logement, ferronneries = ferronnerie.appliquer(logement, lecture_des_fenetres, photos_des_fenetres,
                                                           journal=lambda s: dire("   ferronnerie : " + s))
            bilan["ferronneries"] = ferronneries
            dire(f"   {len(ferronneries)} garde-corps à la ferronnerie recopiée des photos")
        depart.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
        bilan["baies"] = {"votes": votes, "changements": changes}
        dire(f"   {len(changes)} baie(s) corrigée(s) d'après les photos, sur {len(votes)} vue(s)")
        note("baies", time.time() - debut)
        import gc

        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if a.lecture_photos and not a.sortes_du_detecteur and (a.lecture_photos / "vitrages.json").is_file():
            # LES APPAREILS DES PHOTOS repris avec les lignes LUES des fenêtres (24/11/2026, moteur/affiner_appareils.py) : le
            # calage a déjà affiné chaque appareil sur les lignes du plafond et du sol qu'il trouve seul ; maintenant que les
            # fenêtres du logement sont celles que les photos montrent (largeur, bas, haut), le pied et le haut de leur mur et
            # le tour de leur menuiserie, lus sur chaque photo, fixent ce qui restait libre (glisser le long du mur). Avant
            # les sols et les meubles, qui se posent depuis ces appareils. Une fiche relevée à la main n'est pas touchée.
            fiche_affinee = sortie / "cameras-photos-affinees.json"
            note("appareils", lancer("appareils", [py, "outils/habillage/affiner_appareils_lus.py", fiche, depart, a.lecture_photos / "vitrages.json",
                                                   "--sortie", fiche_affinee], journaux))
            fiche = fiche_affinee
    elif a.lecture_photos and not a.sortes_du_detecteur and (sortie / "cameras-photos-affinees.json").is_file():
        fiche = sortie / "cameras-photos-affinees.json"  # chaîne reprise après l'étape des baies : les appareils déjà repris
    lecture_seule = a.lecture_photos and not a.sortes_du_detecteur
    if "sols" in faire:
        commande = [py, "outils/habillage/sols_photos.py", "logement", fiche, depart, MODELE_SOLS, sols]
        note("sols", lancer("sols", commande + (["--lecture", a.lecture_photos / "lecture.json"] if lecture_seule else []), journaux))
    if "meubles" in faire:
        if a.lecture_photos:  # essai : les meubles posés d'après la lecture des photos (ou, en référence, la sorte du détecteur)
            commande = [py, "outils/lecture_photos/poser_photos_lues.py", fiche, sols, meuble, a.lecture_photos]
            note("meubles", lancer("meubles", commande + (["--detecteur"] if a.sortes_du_detecteur else []), journaux))
        else:
            note("meubles", lancer("meubles", [py, "outils/habillage/reperer_meubles_photos.py", fiche, sols, meuble], journaux))
        # LE DESSIN DES FENÊTRES lu sur les photos (moteur/vitrages.py, F2, 20/11/2026) : rangé à côté du logement meublé, où le
        # décor du film le prend (outils/unreal/vue_dehors_photos.lire_vitrages) : la vue n'est peinte que par les vitres nues
        if a.lecture_photos and (a.lecture_photos / "vitrages.json").is_file():
            shutil.copy2(a.lecture_photos / "vitrages.json", meuble.with_name("vitrages.json"))
            dire("   dessin des fenêtres lu sur les photos : pris pour la vue par les fenêtres")
        # LE CONTRÔLE « ZÉRO COLLISION » (NT, 16/11/2026) : mesuré sur le logement meublé, écrit dans le bilan. Les deux outils
        # ci-dessus réparent eux-mêmes ; il ne peut rester que des objets placés par quelqu'un (jamais déplacés par Atelya).
        from moteur import collisions
        restes = collisions.mesurer(json.loads(meuble.read_text(encoding="utf-8")))
        bilan["collisions"] = {**collisions.resume(restes), "detail": restes[:20]}
        bilan_f.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
        dire(f"   contrôle : {len(restes)} collision(s) dans le logement meublé"
             + ("" if not restes else " — objets placés par quelqu'un, à corriger à l'écran de vérification : "
                + ", ".join(sorted({str(c['a']) for c in restes})[:8])))
    if "maquette" in faire:
        if d3.exists():
            shutil.rmtree(d3)
        note("maquette", lancer("maquette", [py, "-m", "moteur.construire", meuble, d3, "--sans-images"], journaux))
    if "paquet" in faire:
        if export.exists():
            shutil.rmtree(export)
        duree = lancer("paquet", [py, "outils/unreal/exporter_pour_unreal.py", d3, export], journaux)
        if paquet.exists():  # jointure : le paquet va dans le studio Unreal, sous un nom sans accent
            shutil.rmtree(paquet)
        shutil.copytree(export, paquet)
        dire(f"   paquet copié : {paquet}")
        note("paquet", duree)
    if "import" in faire:
        debut = time.time()
        dire("\n=== import : la maquette entre dans Unreal")
        cu._python_unreal(cu.SCRIPTS_UE / "importer_maquette.py", paquet.as_posix(), nom)
        note("import", time.time() - debut)
        dire(f"=== import : fait en {time.time() - debut:.0f} s")
    if "film" in faire:
        commande = [py, "outils/unreal/balade_unreal.py", paquet, nom, meuble, "--eclairage", a.eclairage]
        if not a.sans_vue:
            commande += ["--photos", fiche]
        note("film", lancer("film", commande, journaux))
        rendus = cu.STUDIO / "Paquets" / "rendus" / nom / f"vol-{a.eclairage}"
        cible = sortie / "film"
        cible.mkdir(exist_ok=True)
        for f in [*rendus.glob("*.mp4"), *rendus.glob("balade*.json"), *rendus.glob("balade.png"), *rendus.glob("controle.json"),
                  *rendus.glob("lumiere.*")]:
            shutil.copy2(f, cible / f.name)  # jointure : le film et ses bilans reviennent à côté du logement
        dire(f"   film et bilans recopiés : {cible}")
    dire(f"\nCHAÎNE TERMINÉE ({', '.join(faire)}) : {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
