"""Joue le vrai écran dans Chrome sans fenêtre, comme une personne : vues, points, réunion de pièces, annuler, terminer.
Fabrique des captures et dit si chaque étape a marché. Rien n'est installé.
    ..\\atelya\\.venv\\Scripts\\python.exe pc\\verification\\scenario_ecran.py ..\\atelya\\lectures-verification\\fr-006 dossier-captures
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "outils" / "verification-plan" / "scripts"))
from page_unique import fabriquer  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCENARIO = r"""
const J = [];
const V = window.Verification.etat;
const c = (id) => document.getElementById(id);
const note = (quoi, ok, plus) => J.push({ quoi, ok: !!ok, plus: plus === undefined ? "" : String(plus) });
const bouton = (t) => [...document.querySelectorAll("#point-actions button")].find((b) => b.textContent === t);
window.addEventListener("error", (e) => note("erreur JavaScript", false, e.message));
window.addEventListener("load", () => setTimeout(() => {
  try {
    note("plan ouvert", V.v && c("accueil").style.display === "none", V.v.logement.projet_id);
    note("nombre de points", V.points.length > 0, `${V.points.length} points pour ${V.doutes.length} doutes`);
    note("textes sans code interne", !V.points.some((p) => /[a-z]+_\d/.test(p.texte) || /\b[MO]\d+\b/.test(p.texte)), V.points.map((p) => p.texte).filter((t) => /[a-z]+_\d/.test(t) || /\b[MO]\d+\b/.test(t)).slice(0, 2).join(" | "));
    document.querySelector('[data-vue="plan"]').click();
    note("vue plan", V.affichage === "plan");
    document.querySelector('[data-vue="lecture"]').click();
    note("vue lecture", V.affichage === "lecture");
    document.querySelector('[data-vue="deux"]').click();
    const premier = V.points[0].cle;
    if (V.points.length > 1) { c("point-suivant").click(); note("suivant", V.rangPoint === 1); c("point-precedent").click(); note("précédent", V.rangPoint === 0 && V.points[0].cle === premier); }
    const groupes = V.points.filter((p) => p.genre === "morceaux");
    note("groupes de morceaux", true, groupes.map((p) => p.elements.length).join("+"));
    let avant = V.v.logement.pieces.length;
    const rang = V.points.findIndex((p) => p.genre === "morceaux");
    if (rang >= 0) {
      V.rangPoint = rang; window.Verification.choisir(null);
      const ids = V.points[V.rangPoint].elements;
      bouton("Les réunir").click();
      note("réunir", V.v.logement.pieces.length === avant - ids.length + 1, `${avant} → ${V.v.logement.pieces.length} pièces`);
      note("logement cohérent après réunion", window.CalculsVerif.verifierCoherence(V.v.logement).length === 0, window.CalculsVerif.verifierCoherence(V.v.logement).slice(0, 2).join(" | "));
      c("annuler").click();
      note("annuler la réunion", V.v.logement.pieces.length === avant);
      note("rétablir visible", !c("refaire").hidden);
      c("refaire").click();
      note("rétablir", V.v.logement.pieces.length === avant - ids.length + 1);
    }
    c("ouvrir-ajouter").click();
    note("menu ajouter", !c("menu-ajouter").hidden);
    document.querySelector('[data-outil="porte"]').click();
    note("outil porte", V.outil === "porte" && !c("consigne-outil").hidden && c("menu-ajouter").hidden);
    c("arreter-outil").click();
    note("arrêter l'outil", V.outil === "choisir" && c("consigne-outil").hidden);
    c("ouvrir-pieces").click();
    note("liste des pièces", !c("liste-pieces").hidden && document.querySelectorAll("#pieces tr").length === V.v.logement.pieces.length);
    c("ouvrir-pieces").click();
    const mur = V.v.logement.murs[0].id;
    window.Verification.choisir(mur);
    note("fiche d'un mur", !c("choix").hidden && /^Mur de/.test(c("choix-titre").textContent), c("choix-titre").textContent);
    c("fermer-choix").click();
    let garde = 0;
    while (V.points.length && garde++ < 1000) {
      const p = V.points[V.rangPoint];
      const a = p.actions.find((x) => x.action.type === "regler");
      if (!a) { c("point-suivant").click(); if (V.rangPoint === V.points.length - 1 && !V.points[V.rangPoint].actions.some((x) => x.action.type === "regler")) break; continue; }
      bouton(a.libelle).click();
    }
    note("tous les points réglés", V.points.length === 0, `reste ${V.points.length} ; ${V.doutes.length} doutes`);
    const vraiClic = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () { note("fichier enregistré", /-logement\.json$/.test(this.download), this.download); };  // Chrome sans fenêtre se bloque sur un vrai téléchargement
    c("valider").click();
    setTimeout(() => {
      HTMLAnchorElement.prototype.click = vraiClic;
      note("terminer", V.resultat && V.resultat.statut === "valide", V.resultat && V.resultat.statut);
      document.title = "FINI";
      const pre = document.createElement("pre"); pre.id = "journal"; pre.textContent = JSON.stringify(J); document.body.append(pre);
    }, 200);
  } catch (e) {
    note("plantage du scénario", false, e.stack);
    const pre = document.createElement("pre"); pre.id = "journal"; pre.textContent = JSON.stringify(J); document.body.append(pre);
  }
}, 500));
"""
VUE = """window.addEventListener("load", () => setTimeout(() => { %s }, 400));"""


def main() -> int:
    dossier, captures = Path(sys.argv[1]), Path(sys.argv[2])
    captures.mkdir(parents=True, exist_ok=True)
    page = fabriquer(dossier).read_text(encoding="utf-8")
    nom = dossier.name
    ko = 0
    with tempfile.TemporaryDirectory() as t:
        commun = [CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={Path(t) / 'p'}", "--window-size=1500,900", "--virtual-time-budget=20000"]
        scen = Path(t) / "scenario.html"
        scen.write_text(page.replace("</body>", f"<script>{SCENARIO}</script></body>"), encoding="utf-8")
        dom = subprocess.run(commun + ["--dump-dom", scen.as_uri()], capture_output=True, timeout=180).stdout.decode("utf-8", "replace")
        m = re.search(r'<pre id="journal">(.*?)</pre>', dom, re.S)
        if not m:
            print(f"{nom} : ÉCHEC, le scénario n'a pas fini")
            ko += 1
        else:
            texte = m.group(1).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            for x in json.loads(texte):
                if not x["ok"]:
                    ko += 1
                print(f"{nom} {'OK ' if x['ok'] else 'ÉCHEC'} {x['quoi']} {x['plus']}")
        vues = {"deux": "", "plan": 'document.querySelector(\'[data-vue="plan"]\').click();', "lecture": 'document.querySelector(\'[data-vue="lecture"]\').click();',
                "point2": 'document.getElementById("point-suivant").click();'}
        for vue, code in vues.items():
            h = Path(t) / f"{vue}.html"
            h.write_text(page.replace("</body>", f"<script>{VUE % code}</script></body>"), encoding="utf-8")
            subprocess.run(commun + [f"--screenshot={(captures / f'{nom}-{vue}.png').resolve()}", h.as_uri()], capture_output=True, timeout=180)
    print(f"{nom} : {ko} échec(s)")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
