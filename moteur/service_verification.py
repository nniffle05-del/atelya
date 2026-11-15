"""L'écran de vérification ENCHAÎNÉ : le plan, puis les photos, dans la même page (15/11/2026, demande de NT).

POURQUOI : l'écran est une page ; une page ne peut pas lancer un calcul d'Atelya. Jusqu'ici il fallait donc deux ouvertures :
le plan, puis (après une commande à part) la page des questions sur les photos. Ici Atelya reste À L'ÉCOUTE à côté de
l'écran, sur le PC même (adresse 127.0.0.1, jamais visible d'une autre machine) : quand la personne clique « Terminer » sur
le plan, l'écran lui remet le plan vérifié ; Atelya range les photos du client dessus (environ une minute), puis l'écran
affiche ses questions (« d'où est prise cette photo ? »), ou dit qu'il n'y en a aucune. Les réponses reviennent de la même
façon ; Atelya replace les photos avec elles, et c'est fini.

Deux morceaux, sans rien d'autre que la bibliothèque standard de Python :
  - `Enchainement` : où on en est (plan → calcul → questions → calcul → … → fini), ce qu'on écrit, ce qu'on dit à l'écran.
    Le calcul lui-même (caler les photos : moteur/caler_photos.py) lui est DONNÉ, pour que les tests s'en passent ;
  - `servir` : le petit serveur local qui donne la page de l'écran et fait passer les messages.
Outil : outils/atelya/verifier_plan_et_photos.py. Dans le site de l'associé, les mêmes états voyagent par messages
(outils/verification-plan/BRANCHEMENT.md) : ce module n'y sert pas.

Ce qui est écrit dans le dossier de lecture : resultat-verification.json (ce que l'écran a rendu pour le plan),
logement-verifie.json (le logement corrigé), questions-photos/cameras-photos-seul.json (la fiche du calage) ; dans le
dossier des photos : pieces-des-photos.json complété par les endroits pointés.
"""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import photos_verification as pv

VERSION = "0.1.0"
ECRAN = Path(__file__).resolve().parents[1] / "outils" / "verification-plan"
PAGES = {"/index.html": "text/html; charset=utf-8", "/calculs-verif.js": "text/javascript; charset=utf-8",
         "/verification.js": "text/javascript; charset=utf-8", "/exemples/exemple-cas-test-00.js": "text/javascript; charset=utf-8"}
PIECES_DES_PHOTOS = "pieces-des-photos.json"
TAILLE_MAX = 40_000_000  # octets : ce que l'écran peut envoyer d'un coup (un logement corrigé pèse quelques centaines de ko)
EXTENSIONS = (".jpg", ".jpeg", ".png")


class Refus(Exception):
    """Ce que l'écran envoie n'est pas acceptable maintenant (mauvais moment, mauvaise forme) : dit à l'écran, sans rien casser."""


def avancement(lignes: list[str], total: int) -> tuple[int, str]:
    """Le journal du calage → (photos déjà regardées, phrase simple pour la personne qui attend)."""
    faites = sum(1 for x in lignes if re.search(r": (mesurée|trop peu de murs visibles)", x))
    if not lignes:
        return 0, "Atelya se prépare…"
    if faites < total:
        return faites, f"Il regarde la photo {faites + 1} sur {total}…"
    if any("groupes" in x for x in lignes):
        return faites, "Il pose chaque pièce sur le plan…"
    return faites, "Il compare les photos entre elles…"


class Enchainement:
    """Le plan, puis les photos. `ranger(logement, journal)` cale les photos sur ce logement et rend la fiche du calage
    (format de outils/habillage/caler_photos_seul.py : cameras, a_pointer, incertaines, a_verifier, non_calees, fichier)."""

    def __init__(self, lecture: Path, photos: Path, ranger: Callable[[dict, Callable], dict], journal: Callable = print):
        self.lecture, self.photos, self.ranger, self.journal = Path(lecture), Path(photos), ranger, journal
        for f in (self.lecture / "verification.json", self.lecture / "plan.png"):
            if not f.is_file():
                raise FileNotFoundError(f"introuvable : {f}")
        self.noms = sorted(p.stem for p in self.photos.iterdir() if p.suffix.lower() in EXTENSIONS) if self.photos.is_dir() else []
        if not self.noms:
            raise FileNotFoundError(f"aucune photo dans {self.photos}")
        self.depart = json.loads((self.lecture / "verification.json").read_text(encoding="utf-8"))
        self.verrou = threading.Lock()
        self.etape = "plan"          # plan | calcul | questions | fini | erreur
        self.retour = "plan"         # où l'écran revient après une erreur
        self.tour = 0                # nombre de calculs lancés
        self.logement = None         # le logement vérifié, rendu par l'écran
        self.lignes: list[str] = []  # le journal du calcul en cours
        self.debut = 0.0
        self.bloc = None             # les questions à poser : {"questions": [...]}
        self.rangees = 0
        self.laissees = 0            # photos « je ne sais pas » restées sans place à la fin
        self.places: list[dict] = []  # où Atelya a rangé chaque photo : dessiné sur le plan à la fin
        self.passees: set[str] = set()  # « je ne sais pas » : photos qu'on ne redemande pas
        self.erreur = None
        self.temps: dict[str, float] = {}  # le chronomètre de la personne : secondes passées sur le plan, puis sur les photos
        self._t_ouverture = self._t_questions = None
        self.fin_vue = threading.Event()  # l'écran a reçu « fini » : le service peut s'arrêter
        self.fil = None

    # ---- ce que l'écran lit
    def verification(self) -> dict:
        """Le fichier de vérification donné à l'écran : la lecture d'Atelya tant que le plan n'est pas terminé, le logement
        vérifié ensuite (page rouverte en cours de route). « a_suivre » annonce les photos à l'écran."""
        with self.verrou:
            if self._t_ouverture is None:  # le chronomètre du plan part quand l'écran le reçoit pour la première fois
                self._t_ouverture = time.time()
            v = dict(self.depart)
            if self.logement is not None:
                v.update(logement=self.logement, doutes=[])
            v["photos"] = {"a_suivre": True, "nombre": len(self.noms)}
            return v

    def etat(self) -> dict:
        with self.verrou:
            s = {"etape": self.etape, "total": len(self.noms), "tour": max(1, self.tour), "rangees": self.rangees, "laissees": self.laissees}
            if self.etape == "calcul":
                s["faites"], s["detail"] = avancement(self.lignes, len(self.noms))
                s["secondes"] = round(time.time() - self.debut, 1)
            elif self.etape == "questions":
                s["photos"] = self.bloc
            elif self.etape == "erreur":
                s.update(erreur=self.erreur, retour=self.retour)
            if self.etape == "fini":
                s["places"] = self.places
                self.fin_vue.set()
            return s

    # ---- ce que l'écran envoie
    def plan_valide(self, resultat: dict) -> None:
        """« Terminer » sur le plan : on garde le logement vérifié et on range les photos dessus."""
        lg = resultat.get("logement") if isinstance(resultat, dict) else None
        if not isinstance(lg, dict) or lg.get("schema") != "logement/0.1" or not lg.get("murs") or not lg.get("pieces"):
            raise Refus("le plan rendu par l'écran n'a pas de logement lisible (murs et pièces)")
        with self.verrou:
            if self.etape == "calcul":
                raise Refus("Atelya range déjà les photos")
            if self.etape != "plan" and not (self.etape == "erreur" and self.retour == "plan"):
                raise Refus("le plan a déjà été terminé")
            self.logement = lg
            if self._t_ouverture is not None and "plan_s" not in self.temps:
                self._chronometrer("plan_s", time.time() - self._t_ouverture)
            (self.lecture / "resultat-verification.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
            (self.lecture / "logement-verifie.json").write_text(json.dumps(lg, ensure_ascii=False, indent=1), encoding="utf-8")
            self.journal(f"Plan vérifié reçu ({len(lg['murs'])} murs, {len(lg['pieces'])} pièces) : Atelya range les {len(self.noms)} photos.")
            self._lancer("plan")

    def photos_repondues(self, resultat: dict) -> None:
        """« Terminer » sur les photos : les endroits pointés sont rangés avec ce que le client a dit, puis Atelya replace les
        photos avec eux. Une photo « je ne sais pas » n'est plus redemandée."""
        reponses = resultat.get("photos") if isinstance(resultat, dict) else None
        if not isinstance(reponses, dict):
            raise Refus("pas de réponses sur les photos dans ce que l'écran a rendu")
        with self.verrou:
            if self.etape != "questions" and not (self.etape == "erreur" and self.retour == "questions"):
                raise Refus("Atelya n'attend pas de réponses sur les photos en ce moment")
            posees = {q["nom"] for q in (self.bloc or {}).get("questions", [])}
            endroits = {n: v for n, v in (reponses.get("endroits") or {}).items() if n in posees}
            chemin = self.photos / PIECES_DES_PHOTOS
            avant = json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None
            try:
                apres = pv.ranger_les_reponses(avant, {"endroits": endroits})
            except ValueError as e:
                raise Refus(str(e)) from e
            chemin.write_text(json.dumps(apres, ensure_ascii=False, indent=1), encoding="utf-8")
            if self._t_questions is not None:
                self._chronometrer("photos_s", self.temps.get("photos_s", 0.0) + time.time() - self._t_questions)
                self._t_questions = None
            self.passees |= posees - set(endroits)  # « je ne sais pas » et photos laissées sans réponse : on n'y revient pas
            self.journal(f"Réponses reçues : {len(endroits)} endroits pointés, {len(posees - set(endroits))} photos laissées de côté.")
            self._lancer("questions")

    def _chronometrer(self, quoi: str, secondes: float) -> None:
        """Le temps passé par la personne (objectif NT : ~2 min de vérification) : gardé dans temps-verification.json."""
        self.temps[quoi] = round(secondes, 1)
        (self.lecture / "temps-verification.json").write_text(json.dumps(self.temps, ensure_ascii=False, indent=1), encoding="utf-8")
        self.journal(f"Temps de la personne, {'le plan' if quoi == 'plan_s' else 'les photos'} : {int(secondes // 60)} min {int(secondes % 60):02d} s")

    # ---- le calcul
    def _lancer(self, retour: str) -> None:
        self.etape, self.retour, self.erreur, self.lignes, self.debut = "calcul", retour, None, [], time.time()
        self.tour += 1
        self.fin_vue.clear()
        self.fil = threading.Thread(target=self._calculer, daemon=True)
        self.fil.start()

    def _note(self, *a) -> None:
        ligne = " ".join(str(x) for x in a)
        with self.verrou:
            self.lignes.append(ligne)
        self.journal(ligne)

    def _calculer(self) -> None:
        try:
            fiche = self.ranger(self.logement, self._note)
            # les « endroits douteux » (pièce sûre, place incertaine) ne sont demandés qu'au premier passage : ensuite Atelya
            # replace les photos avec les réponses et ne redemande que ce qu'il ne sait vraiment pas ranger
            bloc = pv.questions_pour_l_ecran(fiche, self.photos, logement=self.logement, endroits=self.tour == 1)
            bloc["questions"] = [q for q in bloc["questions"] if q["nom"] not in self.passees]
            with self.verrou:
                cameras = fiche.get("cameras", {})
                self.rangees = len(set(cameras) - {q["nom"] for q in bloc["questions"]})  # rangées SANS question en attente
                self.laissees = len(self.passees - set(cameras))  # une photo passée peut être rangée quand même, par sa voisine pointée
                self.places = [{"nom": n, "x": d["camera"]["x"], "y": d["camera"]["y"], "cap": d["camera"]["cap"], "piece": d.get("piece")}
                               for n, d in sorted(cameras.items())]
                self.bloc = bloc
                self.etape = "questions" if bloc["questions"] else "fini"
                self._t_questions = time.time() if bloc["questions"] else None  # le chronomètre des photos part quand les questions arrivent
                duree = time.time() - self.debut
            if bloc["questions"]:
                self.journal(f"{self.rangees} photos rangées sur {len(self.noms)} en {duree:.0f} s ; {len(bloc['questions'])} questions posées à l'écran.")
            else:
                self.journal(f"TERMINÉ en {duree:.0f} s : {self.rangees} photos rangées sur {len(self.noms)}"
                             + (f", {self.laissees} laissées de côté." if self.laissees else "."))
        except Exception as e:  # le calcul a planté : l'écran le dit, et on peut recliquer « Terminer »
            traceback.print_exc()
            with self.verrou:
                self.etape, self.erreur = "erreur", f"{type(e).__name__} : {e}"
            self.journal(f"PLANTÉ pendant le rangement des photos : {type(e).__name__} : {e}")

    def attendre(self, delai: float | None = None) -> None:
        """Attend la fin du calcul en cours (tests)."""
        if self.fil is not None:
            self.fil.join(delai)


def _reponse(h: BaseHTTPRequestHandler, code: int, corps: bytes, sorte: str) -> None:
    h.send_response(code)
    h.send_header("Content-Type", sorte)
    h.send_header("Content-Length", str(len(corps)))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    h.wfile.write(corps)


def _json(h: BaseHTTPRequestHandler, code: int, objet) -> None:
    _reponse(h, code, json.dumps(objet, ensure_ascii=False, default=float).encode("utf-8"), "application/json; charset=utf-8")


def servir(enchainement: Enchainement, port: int = 8765, essais: int = 20) -> tuple[ThreadingHTTPServer, str]:
    """Ouvre le service sur ce PC seulement (127.0.0.1) et rend (serveur, adresse de la page à ouvrir). Si le port est pris,
    les suivants sont essayés. `serveur.serve_forever()` le fait tourner ; `serveur.shutdown()` l'arrête."""
    e = enchainement

    class Service(BaseHTTPRequestHandler):
        def log_message(self, *a):  # pas une ligne par demande dans la fenêtre : l'écran interroge chaque seconde
            pass

        def _chez_nous(self) -> bool:
            """Seule la page servie ici a le droit de parler à Atelya (ni un autre site ouvert dans le navigateur, ni une
            autre machine)."""
            ici = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            origine = self.headers.get("Origin")
            return self.headers.get("Host") in ici and (origine is None or origine.split("://", 1)[-1] in ici)

        def do_GET(self):
            chemin = self.path.split("?", 1)[0]
            if not self._chez_nous():
                return _json(self, 403, {"erreur": "adresse refusée"})
            if chemin == "/":
                self.send_response(302)
                self.send_header("Location", "/index.html?verification=/atelya/verification.json&plan=/atelya/plan.png&service=/atelya")
                self.end_headers()
            elif chemin in PAGES:
                _reponse(self, 200, (ECRAN / chemin.lstrip("/")).read_bytes(), PAGES[chemin])
            elif chemin == "/atelya/verification.json":
                _json(self, 200, e.verification())
            elif chemin == "/atelya/plan.png":
                _reponse(self, 200, (e.lecture / "plan.png").read_bytes(), "image/png")
            elif chemin == "/atelya/etat":
                _json(self, 200, e.etat())
            else:
                _json(self, 404, {"erreur": "page inconnue"})

        def do_POST(self):
            chemin = self.path.split("?", 1)[0]
            if not self._chez_nous():
                return _json(self, 403, {"erreur": "adresse refusée"})
            if chemin not in ("/atelya/plan", "/atelya/photos"):
                return _json(self, 404, {"erreur": "page inconnue"})
            try:
                taille = int(self.headers.get("Content-Length") or 0)
                if not 0 < taille <= TAILLE_MAX:
                    raise Refus("envoi vide ou trop gros")
                resultat = json.loads(self.rfile.read(taille).decode("utf-8"))
                (e.plan_valide if chemin == "/atelya/plan" else e.photos_repondues)(resultat)
            except Refus as x:
                return _json(self, 409, {"erreur": str(x)})
            except (ValueError, UnicodeDecodeError):
                return _json(self, 400, {"erreur": "envoi illisible"})
            _json(self, 202, {"etape": "calcul"})

    dernier = None
    for p in ([port + k for k in range(essais)] if port else [0]):
        try:
            serveur = ThreadingHTTPServer(("127.0.0.1", p), Service)
            serveur.daemon_threads = True
            return serveur, f"http://127.0.0.1:{serveur.server_port}/"
        except OSError as x:
            dernier = x
    raise OSError(f"aucun port libre à partir de {port} : {dernier}")
