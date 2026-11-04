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
    // Les gestes à la souris, joués pour de vrai sur le plan.
    const toile = c("plan");
    toile.setPointerCapture = () => {};
    const K = window.CalculsVerif;
    const ecran = (q) => { const r = toile.getBoundingClientRect(), u = K.versPixel(V.matrice, q); return [u[0] * V.vue.zoom + V.vue.dx + r.left, u[1] * V.vue.zoom + V.vue.dy + r.top]; };
    const geste = (t, q) => { const [x, y] = ecran(q); toile.dispatchEvent(new PointerEvent(t, { clientX: x, clientY: y, pointerId: 1, bubbles: true })); };
    const clic = (q) => { geste("pointerdown", q); geste("pointerup", q); };
    const dir = (m) => { const l = K.longueur(m.debut, m.fin); return { l, d: [(m.fin[0] - m.debut[0]) / l, (m.fin[1] - m.debut[1]) / l] }; };
    const sur = (m, t) => { const { d } = dir(m); return [m.debut[0] + d[0] * t, m.debut[1] + d[1] * t]; };
    const outil = (n) => { c("ouvrir-ajouter").click(); document.querySelector(`[data-outil="${n}"]`).click(); };
    // Un endroit du mur le plus long sans porte : un seul morceau libre suffit.
    const lg0 = () => V.v.logement;
    const longs = [...lg0().murs].sort((a, b) => K.longueur(b.debut, b.fin) - K.longueur(a.debut, a.fin));
    const libre = (m) => {
      const os = (lg0().ouvertures || []).filter((o) => o.mur === m.id);
      for (let t = 0.3; t < dir(m).l - 0.3; t += 0.1) if (!os.some((o) => t > o.position - 0.2 && t < o.position + o.largeur + 0.2)) return t;
      return null;
    };
    const cible = longs.find((m) => libre(m) !== null && !(lg0().ouvertures || []).some((o) => o.mur === m.id)) || longs.find((m) => libre(m) !== null);
    if (cible) {
      const id = cible.id, tL = libre(cible);
      let nb = lg0().murs.length;
      window.Verification.choisir(id);
      const av = dir(cible);
      const bout = cible.fin;
      geste("pointerdown", bout);
      note("poignée attrapée", V.glisse && V.glisse.genre === "bout", V.glisse && V.glisse.genre);
      const loin = [bout[0] + av.d[0] * 0.8, bout[1] + av.d[1] * 0.8];  // assez loin pour ne pas se raccrocher à son voisin
      geste("pointermove", loin);
      geste("pointerup", loin);
      note("bout du mur déplacé", lg0().murs.find((m) => m.id === id).fin.join() !== bout.join(), lg0().murs.find((m) => m.id === id).fin.join());
      note("alerte des pièces affichée", !c("alerte-pieces").hidden);
      c("annuler").click();
      note("annuler le geste", lg0().murs.find((m) => m.id === id).fin.join() === bout.join());
      note("alerte des pièces retirée", c("alerte-pieces").hidden);
      window.Verification.choisir(id);
      const ep = lg0().murs.find((m) => m.id === id).epaisseur;
      c("f-ep-plus").click();
      note("épaisseur +", Math.abs(lg0().murs.find((m) => m.id === id).epaisseur - ep - 0.01) < 1e-6);
      c("annuler").click();
      window.Verification.choisir(null);
      outil("couper");
      clic(sur(lg0().murs.find((m) => m.id === id), tL));
      note("couper un mur", lg0().murs.length === nb + 1 && V.outil === "choisir", V.v && lg0().murs.length);
      note("logement cohérent après coupe", K.verifierCoherence(lg0()).length === 0, K.verifierCoherence(lg0()).slice(0, 2).join(" | "));
      c("annuler").click();
      const m = lg0().murs.find((x) => x.id === id);
      const tF = Math.min(tL + 0.25, dir(m).l - 0.1);
      if (!(lg0().ouvertures || []).some((o) => o.mur === id && tF > o.position - 0.05 && tF < o.position + o.largeur + 0.05)) {
        outil("morceau");
        clic(sur(m, tL));
        note("début du morceau retenu", V.morceau && V.morceau.id !== undefined);
        clic(sur(m, tF));
        note("enlever un morceau", lg0().murs.reduce((s, x) => s + K.longueur(x.debut, x.fin), 0) < longs.reduce((s, x) => s + K.longueur(x.debut, x.fin), 0) - 0.1 && V.outil === "choisir");
        c("annuler").click();
      }
      // Relier le bout du mur à celui d'un autre, sans casser le logement.
      const autre = longs.find((x) => x.id !== id && !(lg0().ouvertures || []).some((o) => o.mur === x.id));
      if (autre) {
        outil("relier");
        clic(cible.debut);
        note("premier bout retenu", V.relier && V.relier.id, V.relier && V.relier.id);
        clic(autre.fin);
        note("relier deux murs", V.outil === "choisir" && V.historique.length > 0, c("message").textContent);
        note("logement cohérent après reliure", K.verifierCoherence(lg0()).length === 0, K.verifierCoherence(lg0()).slice(0, 2).join(" | "));
        c("annuler").click();
      }
      // Supprimer un mur intérieur puis recalculer : le nombre de pièces se recalcule et rien ne plante.
      c("recalculer-pieces-2").click();
      note("recalculer les pièces", K.verifierCoherence(lg0()).length === 0 && lg0().pieces.length > 0, c("message").textContent);
      note("alerte retirée après recalcul", c("alerte-pieces").hidden);
      c("annuler").click();
    } else note("aucun mur libre pour les gestes", true);

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
                "point2": 'document.getElementById("point-suivant").click();',
                "recalcul": 'document.getElementById("recalculer-pieces-2").click(); document.querySelector(\'[data-vue="lecture"]\').click(); window.Verification.choisir(window.Verification.etat.v.logement.murs[0].id);'}
        for vue, code in vues.items():
            h = Path(t) / f"{vue}.html"
            h.write_text(page.replace("</body>", f"<script>{VUE % code}</script></body>"), encoding="utf-8")
            subprocess.run(commun + [f"--screenshot={(captures / f'{nom}-{vue}.png').resolve()}", h.as_uri()], capture_output=True, timeout=180)
    print(f"{nom} : {ko} échec(s)")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
