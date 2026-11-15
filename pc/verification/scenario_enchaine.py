r"""Essai DE BOUT EN BOUT de l'écran de vérification enchaîné (le plan, puis les photos), comme le ferait une personne :
Atelya est lancé pour de bon (outils\atelya\verifier_plan_et_photos.py, vrai calage des photos sur la carte graphique), la
page est ouverte dans Chrome sans fenêtre, et une vraie souris clique « Terminer le plan », attend, répond aux questions
sur les photos, clique « Terminer les photos », attend la fin. Une capture d'écran à chaque moment.

    ..\atelya\.venv\Scripts\python.exe pc\verification\scenario_enchaine.py <dossier de lecture> <dossier des photos> <gestes.json> <sortie>

gestes.json : comme pour scenario_photos.py : {"photo-10": [x, y, x2, y2], "photo-13": "passer", "photo-09": "accepter", …} en MÈTRES du plan (on
clique en (x, y), on tire jusqu'à (x2, y2)) ; une photo absente reste sans réponse. --recharger : au milieu des questions, la
page est rechargée (touche F5 par mégarde) : les réponses déjà données doivent revenir.
ATTENTION : le dossier des photos est modifié (pieces-des-photos.json reçoit les endroits pointés) : travailler sur une copie.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chrome_pilote import Chrome  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
PORT = 8791

PHASE = "window.Verification && window.Verification.etat.suite && window.Verification.etat.suite.phase"
ECRAN_DE = """(() => { const V = window.Verification, C = window.CalculsVerif, t = document.getElementById("plan").getBoundingClientRect();
  const [u, v] = C.versPixel(V.etat.matrice, %s); return [u * V.etat.vue.zoom + V.etat.vue.dx + t.left, v * V.etat.vue.zoom + V.etat.vue.dy + t.top]; })()"""
ATTENTE = """(() => ({ visible: !document.getElementById("fond-attente").hidden, titre: document.getElementById("attente-titre").textContent,
  texte: document.getElementById("attente-texte").textContent, detail: document.getElementById("attente-detail").textContent,
  barre: document.getElementById("attente-part").style.width, bouton: document.getElementById("valider").textContent,
  grise: document.getElementById("valider").disabled, message: document.getElementById("message").textContent,
  etapes: [...document.querySelectorAll("#etapes span")].map((e) => e.textContent + (e.className ? " [" + e.className + "]" : "")) }))()"""
PHOTO = """(() => ({ nom: window.Verification.etat.photos.questions[window.Verification.etat.photos.rang].nom,
  numero: document.getElementById("photo-numero").textContent, question: document.getElementById("photo-question").textContent,
  etat: document.getElementById("photo-etat").textContent }))()"""


def dire(*a) -> None:
    print(*a, flush=True)


if hasattr(sys.stdout, "reconfigure"):  # sortie redirigée dans un fichier : pas de plantage sur un « ✓ »
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def jouer(lecture: Path, photos: Path, gestes: dict, sortie: Path, recharger: bool) -> dict:
    sortie.mkdir(parents=True, exist_ok=True)
    journal = (sortie / "journal-atelya.txt").open("w", encoding="utf-8")
    atelya = subprocess.Popen([sys.executable, "-u", str(RACINE / "outils" / "atelya" / "verifier_plan_et_photos.py"), str(lecture), str(photos),
                               "--sans-navigateur", "--port", str(PORT)], stdout=journal, stderr=subprocess.STDOUT, cwd=str(RACINE))
    bilan = {"captures": [], "photos": []}
    try:
        adresse = f"http://127.0.0.1:{PORT}/"
        fin = time.time() + 60
        while True:  # Atelya est-il à l'écoute ?
            try:
                urllib.request.urlopen(adresse + "atelya/etat", timeout=2).read(); break
            except OSError:
                if atelya.poll() is not None or time.time() > fin:
                    raise RuntimeError("Atelya ne s'est pas mis à l'écoute (voir journal-atelya.txt)")
                time.sleep(0.5)
        with Chrome() as c:
            capture = lambda nom: bilan["captures"].append(c.capture(sortie / f"{len(bilan['captures']) + 1}-{nom}.png").name)
            c.ouvrir(adresse)
            c.attendre("window.Verification && !!window.Verification.etat.v && !!window.Verification.etat.matrice", quoi="le plan s'ouvre")
            time.sleep(0.8)
            bilan["plan"] = c.lire(ATTENTE)
            bilan["points_du_plan"] = c.lire("window.Verification.etat.points.length")
            capture("plan")

            # « Terminer le plan » (et « Terminer quand même » s'il reste des points)
            t0 = time.time()
            c.cliquer("#valider")
            time.sleep(0.4)
            if not c.lire('document.getElementById("fond-confirmation").hidden'):
                c.cliquer("#confirmation-oui")
            c.attendre(f'{PHASE} === "calcul"', quoi="l'attente s'affiche")
            time.sleep(6)
            bilan["attente_1"] = c.lire(ATTENTE)
            capture("attente")
            vus = set()
            while c.lire(PHASE) == "calcul":  # on regarde passer les phrases de l'attente
                vus.add(c.lire('document.getElementById("attente-detail").textContent.split(" · ")[0]'))
                if time.time() - t0 > 600:
                    raise TimeoutError("Atelya range toujours les photos après 10 min")
                time.sleep(1)
            bilan["phrases_de_l_attente"] = sorted(vus)
            bilan["attente_1_s"] = round(time.time() - t0, 1)
            time.sleep(0.8)
            bilan["apres_le_plan"] = c.lire(ATTENTE)

            if c.lire(PHASE) == "questions":
                capture("questions")
                n = c.lire("window.Verification.etat.photos.questions.length")
                bilan["questions"] = n
                for i in range(n):
                    q = c.lire(PHOTO)
                    g = gestes.get(q["nom"])
                    if isinstance(g, list):
                        a, b = c.lire(ECRAN_DE % json.dumps(g[:2])), c.lire(ECRAN_DE % json.dumps(g[2:4]))
                        c.tirer(*a, *b)
                    elif g == "passer":
                        c.cliquer("#photo-passer")
                    elif g == "accepter":  # « C'est bien la place proposée »
                        c.cliquer("#photo-accepter")
                    time.sleep(0.3)
                    q = {**q, **c.lire(PHOTO), "geste": g}
                    bilan["photos"].append(q)
                    capture(q["nom"])
                    if recharger and i == 1:  # F5 par mégarde au milieu des questions : les réponses reviennent
                        c.recharger()
                        time.sleep(1)
                        c.attendre(f'{PHASE} === "questions" && !!window.Verification.etat.photos', quoi="les questions reviennent après rechargement")
                        time.sleep(0.8)
                        bilan["apres_rechargement"] = c.lire("(() => { const p = window.Verification.etat.photos; return { endroits: Object.keys(p.endroits), passees: p.passees, rang: p.rang }; })()")
                        capture("apres-rechargement")
                        c.lire(f"(() => {{ const p = window.Verification.etat.photos; p.rang = {i}; document.getElementById('photo-suivante').disabled = false; }})()")
                    if i < n - 1:
                        c.cliquer("#photo-suivante")
                        time.sleep(0.3)
                bilan["reponses"] = c.lire("(() => { const p = window.Verification.etat.photos; return window.CalculsVerif.reponsesPhotos(p.questions, p.endroits, p.passees); })()")

                t1 = time.time()
                c.cliquer("#valider")
                time.sleep(0.4)
                if not c.lire('document.getElementById("fond-confirmation").hidden'):
                    c.cliquer("#confirmation-oui")
                c.attendre(f'{PHASE} === "calcul"', quoi="la seconde attente s'affiche")
                time.sleep(5)
                bilan["attente_2"] = c.lire(ATTENTE)
                capture("attente-2")
                c.attendre(f'{PHASE} !== "calcul"', delai=600, pas=1, quoi="Atelya a replacé les photos")
                bilan["attente_2_s"] = round(time.time() - t1, 1)
                time.sleep(0.8)
            bilan["fin"] = {**c.lire(ATTENTE), "phase": c.lire(PHASE)}
            capture("fin")
            bilan["places"] = c.lire("(window.Verification.etat.suite.places || []).length")
            c.cliquer("#attente-fermer")  # « Voir les photos sur le plan »
            time.sleep(0.6)
            bilan["message_de_fin"] = c.lire('document.getElementById("message").textContent')
            capture("photos-sur-le-plan")
            bilan["erreurs_de_la_page"] = c.erreurs
        try:  # Atelya s'arrête tout seul une fois la fin affichée
            bilan["atelya_arrete_seul"] = atelya.wait(30) == 0
        except subprocess.TimeoutExpired:
            bilan["atelya_arrete_seul"] = False
    finally:
        if atelya.poll() is None:
            atelya.kill()
        journal.close()
    (sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return bilan


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Essai de bout en bout de l'écran enchaîné")
    ap.add_argument("lecture", type=Path); ap.add_argument("photos", type=Path); ap.add_argument("gestes", type=Path); ap.add_argument("sortie", type=Path)
    ap.add_argument("--recharger", action="store_true")
    args = ap.parse_args()
    try:
        b = jouer(args.lecture, args.photos, json.loads(args.gestes.read_text(encoding="utf-8")), args.sortie, args.recharger)
        dire(json.dumps({k: v for k, v in b.items() if k != "captures"}, ensure_ascii=False, indent=1))
        dire(f"captures : {b['captures']}\n→ {args.sortie}")
    except Exception as e:
        dire(f"PLANTÉ : {type(e).__name__} : {e}")
        raise
