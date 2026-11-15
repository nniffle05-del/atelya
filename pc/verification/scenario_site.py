r"""Essai de l'écran de vérification enchaîné quand il est affiché DANS UN SITE (balise <iframe>, messages postMessage) :
le cas du site interne. Aucun vrai site ni vrai calcul : une page d'essai joue le site (elle ouvre le plan, reçoit « valide »,
puis envoie ce qu'Atelya dirait : attente, questions, fin), et on contrôle que l'écran suit. Voir BRANCHEMENT.md.

    ..\atelya\.venv\Scripts\python.exe pc\verification\scenario_site.py <dossier de lecture> <dossier de sortie>
"""
from __future__ import annotations

import functools
import json
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chrome_pilote import Chrome  # noqa: E402

ECRAN = Path(__file__).resolve().parents[2] / "outils" / "verification-plan"
SITE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Site d'essai</title>
<style>body{margin:0;font:15px sans-serif;background:#1f2937;color:#fff}h1{font-size:15px;margin:0;padding:8px 14px}iframe{width:100%;height:calc(100vh - 36px);border:0;background:#fff}</style></head>
<body><h1>Site interne (page d'essai) · onglet « Plans à vérifier »</h1><iframe id="ecran" src="/index.html"></iframe>
<script>
const ecran = document.getElementById("ecran"); window.recus = [];
addEventListener("message", async (ev) => {
  if (ev.origin !== location.origin || ev.source !== ecran.contentWindow) return;
  const m = ev.data || {}; window.recus.push(m);
  if (m.type === "atelya-verification:pret") {
    const v = await (await fetch("/essai/verification.json")).json();
    v.photos = { a_suivre: true, nombre: 2 };
    ecran.contentWindow.postMessage({ type: "atelya-verification:ouvrir", verification: v, plan: "/essai/plan.png" }, location.origin);
  }
});
window.atelyaDit = (etat) => ecran.contentWindow.postMessage({ type: "atelya-verification:photos", etat }, location.origin);
</script></body></html>"""
POINT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
E = 'document.getElementById("ecran").contentWindow'
D = 'document.getElementById("ecran").contentDocument'


def jouer(lecture: Path, sortie: Path) -> dict:
    class Pages(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            chemin = self.path.split("?", 1)[0]
            donnees = {"/site.html": (SITE.encode("utf-8"), "text/html; charset=utf-8"),
                       "/essai/verification.json": ((lecture / "verification.json").read_bytes(), "application/json"),
                       "/essai/plan.png": ((lecture / "plan.png").read_bytes(), "image/png")}.get(chemin)
            if donnees is None:
                return super().do_GET()
            self.send_response(200); self.send_header("Content-Type", donnees[1]); self.send_header("Content-Length", str(len(donnees[0]))); self.end_headers()
            self.wfile.write(donnees[0])

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Pages, directory=str(ECRAN)))
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    bilan = {}
    try:
        with Chrome() as c:
            phase = lambda: c.lire(f"{E}.Verification.etat.suite && {E}.Verification.etat.suite.phase")
            texte = lambda i: c.lire(f'{D}.getElementById("{i}").textContent')
            clic = lambda i: c.lire(f'{D}.getElementById("{i}").click()')
            types = lambda: c.lire("window.recus.map((m) => m.type.split(':')[1] + (m.resultat && m.resultat.photos ? '+photos' : ''))")
            c.ouvrir(f"http://127.0.0.1:{serveur.server_port}/site.html")
            c.attendre(f"{E}.Verification && !!{E}.Verification.etat.v", quoi="le site ouvre le plan dans l'écran")
            assert phase() == "plan" and texte("valider") == "✓ Terminer le plan", (phase(), texte("valider"))

            clic("valider"); time.sleep(0.4)
            if not c.lire(f'{D}.getElementById("fond-confirmation").hidden'):
                clic("confirmation-oui"); time.sleep(0.4)
            assert types() == ["pret", "valide"] and phase() == "calcul", (types(), phase())  # le site a reçu le plan vérifié ; l'écran attend
            assert not c.lire(f'{D}.getElementById("fond-attente").hidden')
            c.lire('window.atelyaDit({ etape: "calcul", total: 2, faites: 1, detail: "Il regarde la photo 2 sur 2…", secondes: 12 })'); time.sleep(0.4)
            bilan["attente"] = [texte("attente-titre"), texte("attente-detail"), c.lire(f'{D}.getElementById("attente-part").style.width')]
            assert bilan["attente"] == ["Atelya range vos photos", "Il regarde la photo 2 sur 2… · 12 s", "50%"], bilan["attente"]

            question = {"nom": "photo-02", "image": POINT, "largeur": 1, "hauteur": 1, "question": "Atelya hésite entre « Chambre 2 » et « Chambre 3 ». Pointez d'où la photo est prise.",
                        "piece": "chambre_1", "hesite_avec": ["chambre_2"], "proposition": {"x": 13.2, "y": 4.4, "cap": -62.0}}
            c.lire(f"window.atelyaDit({json.dumps({'etape': 'questions', 'total': 2, 'rangees': 1, 'photos': {'questions': [question]}})})"); time.sleep(0.6)
            assert phase() == "questions" and texte("valider") == "✓ Terminer les photos" and c.lire(f'{D}.getElementById("fond-attente").hidden')
            bilan["question"] = [texte("photo-numero"), texte("photo-question"), texte("message")]
            c.capture(sortie / "site-1-question.png")
            clic("photo-accepter"); time.sleep(0.3)
            clic("valider"); time.sleep(0.5)
            assert types() == ["pret", "valide", "valide+photos"] and phase() == "calcul", (types(), phase())
            bilan["reponses_recues_par_le_site"] = c.lire("window.recus[2].resultat.photos")
            assert bilan["reponses_recues_par_le_site"] == {"endroits": {"photo-02": [13.2, 4.4, -62.0]}, "passees": []}, bilan["reponses_recues_par_le_site"]
            assert texte("attente-texte").startswith("Il replace les photos avec vos réponses")

            fin = {"etape": "fini", "total": 2, "rangees": 2, "tour": 2, "places": [{"nom": "photo-01", "x": 3.0, "y": 3.0, "cap": 20.0}, {"nom": "photo-02", "x": 13.2, "y": 4.4, "cap": -62.0}]}
            c.lire(f"window.atelyaDit({json.dumps(fin)})"); time.sleep(0.6)
            bilan["fin"] = [phase(), texte("attente-titre"), texte("attente-texte"), texte("attente-fermer")]
            assert bilan["fin"] == ["fini", "C'est terminé", "Merci pour vos réponses. Les 2 photos sont rangées.", "Voir les photos sur le plan"], bilan["fin"]
            assert c.lire(f'{D}.getElementById("valider").disabled')
            c.capture(sortie / "site-2-fin.png")
            bilan["erreurs_de_la_page"] = c.erreurs
            assert not c.erreurs, c.erreurs
    finally:
        serveur.shutdown()
    return bilan


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        print(json.dumps(jouer(Path(sys.argv[1]), Path(sys.argv[2])), ensure_ascii=False, indent=1), flush=True)
        print("Écran dans un site : l'enchaînement suit les messages. OK", flush=True)
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
