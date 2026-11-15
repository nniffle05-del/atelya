r"""L'écran de vérification ENCHAÎNÉ : le plan, puis les photos du client, dans la même page (15/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\atelya\verifier_plan_et_photos.py <dossier de lecture> <dossier des photos>

<dossier de lecture> : celui du plan lu (verification.json, plan.png : sorties de outils\atelya\lire_plan.py ou de
outils\lecture_claude\traduire_fiche.py). <dossier des photos> : les photos du client (et, s'il a nommé les pièces,
pieces-des-photos.json).

Ce qui se passe : la page de l'écran s'ouvre dans le navigateur. On vérifie le plan, on clique « Terminer le plan » ; Atelya
range les photos sur le plan vérifié (environ une minute, l'écran montre où il en est) ; ses questions « d'où est prise cette
photo ? » arrivent dans la même page, ou l'écran dit qu'il n'y en a aucune. « Terminer les photos » renvoie les réponses ;
Atelya replace les photos avec elles, puis s'arrête tout seul. Pendant la vérification du plan, Atelya charge déjà ses
réseaux : l'attente en est raccourcie.

Écrit dans le dossier de lecture : logement-verifie.json, resultat-verification.json,
questions-photos\cameras-photos-seul.json (la fiche à donner aux sols et aux meubles) ; dans le dossier des photos :
pieces-des-photos.json complété par les endroits pointés.

--port : 8765 par défaut (le suivant si pris). --sans-navigateur : ne pas ouvrir la page (essais). --rester : ne pas
s'arrêter à la fin (essais). --raccourci : écrit seulement « Verifier le plan et les photos.bat » dans le dossier de lecture
(un double-clic relance cette commande), sans rien lancer.
Tout se passe sur ce PC (adresse 127.0.0.1) : rien ne sort sur le réseau.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
from moteur import service_verification as sv  # noqa: E402

RACCOURCI = "Verifier le plan et les photos.bat"


def dire(*a) -> None:
    print(*a, flush=True)


if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):  # sortie redirigée dans un fichier (essais) : en UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ecrire_raccourci(lecture: Path, photos: Path) -> Path:
    """Un fichier à double-cliquer, dans le dossier de lecture. Que des chemins RELATIFS à lui-même et sans accent : un .bat
    est lu dans l'ancien codage de Windows, un accent écrit dedans serait mal lu (« %~dp0 », lui, est toujours juste)."""
    ici = lecture.resolve()
    rel = lambda p: os.path.relpath(Path(p).resolve(), ici)
    python, outil, dossier = rel(sys.executable), rel(__file__), rel(photos)
    for c in (python, outil, dossier):
        if not c.isascii():
            raise ValueError(f"chemin avec accent dans le raccourci : {c}")
    bat = ici / RACCOURCI
    bat.write_text('@echo off\r\ntitle Atelya - verification du plan puis des photos\r\n'
                   f'"%~dp0{python}" "%~dp0{outil}" "%~dp0." "%~dp0{dossier}" %*\r\n'
                   'if errorlevel 1 pause\r\n', encoding="ascii", newline="")
    return bat


def main() -> int:
    ap = argparse.ArgumentParser(description="Écran de vérification : le plan, puis les photos")
    ap.add_argument("lecture", type=Path)
    ap.add_argument("photos", type=Path)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--sans-navigateur", action="store_true")
    ap.add_argument("--rester", action="store_true")
    ap.add_argument("--raccourci", action="store_true")
    args = ap.parse_args()
    for f in (args.lecture / "verification.json", args.lecture / "plan.png", args.photos):
        if not f.exists():
            dire(f"PLANTÉ : introuvable : {f}")
            return 2
    if args.raccourci:
        dire(f"Raccourci écrit : {ecrire_raccourci(args.lecture, args.photos)}")
        return 0

    # Les réseaux se chargent pendant que la personne vérifie le plan : l'attente après « Terminer » en est raccourcie.
    outils, pret = {}, threading.Event()

    def charger():
        try:
            from moteur import caler_photos as cp
            t0 = time.time()
            outils["o"] = cp.Outils()
            dire(f"  (Atelya est prêt à ranger les photos : réseaux chargés en {time.time() - t0:.0f} s)")
        except Exception as e:  # sera redit au moment du calcul, à l'écran
            outils["erreur"] = e
        finally:
            pret.set()

    def ranger(logement: dict, journal) -> dict:
        from caler_photos_seul import fiche_ou_photos
        pret.wait()
        if "erreur" in outils:
            raise outils["erreur"]
        return fiche_ou_photos(args.photos, logement, args.lecture / "questions-photos" / "cameras-photos-seul.json", journal=journal, outils=outils["o"])

    try:
        enchainement = sv.Enchainement(args.lecture, args.photos, ranger, journal=dire)
    except FileNotFoundError as e:
        dire(f"PLANTÉ : {e}")
        return 2
    serveur, adresse = sv.servir(enchainement, args.port)
    threading.Thread(target=charger, daemon=True).start()
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    dire(f"Atelya est à l'écoute : {adresse}")
    dire(f"  plan : {args.lecture}    photos : {args.photos} ({len(enchainement.noms)} photos)")
    dire("  Vérifiez le plan dans la page qui s'ouvre, puis cliquez « Terminer le plan ». Laissez cette fenêtre ouverte.")
    if not args.sans_navigateur:
        webbrowser.open(adresse)
    try:
        while True:
            if enchainement.fin_vue.wait(0.5) and not args.rester:
                time.sleep(2)  # le temps que la page ait bien reçu la fin
                break
    except KeyboardInterrupt:
        dire("Arrêt demandé.")
    serveur.shutdown()
    if enchainement.etape == "fini":
        dire(f"Fini. Logement vérifié : {args.lecture / 'logement-verifie.json'}")
        dire(f"      Photos rangées  : {args.lecture / 'questions-photos' / 'cameras-photos-seul.json'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
