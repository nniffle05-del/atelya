r"""Rejoue, dans Chrome sans fenêtre, les gestes d'une personne qui répond aux questions « d'où est prise cette photo ? » de
l'écran de vérification (15/11/2026) : de quoi contrôler la page de bout en bout sans cliquer à la main.

    ..\atelya\.venv\Scripts\python.exe pc\verification\scenario_photos.py <ecran.html> <gestes.json> <dossier de sortie>

gestes.json : {"photo-10": [x, y, x2, y2], "photo-13": "passer", …} : pour chaque photo, soit le geste en MÈTRES du plan (on
clique en (x, y), là où se tenait le photographe, et on tire jusqu'à (x2, y2), vers ce qu'il regardait), soit "passer" (le
bouton « Je ne sais pas »). Une photo absente du fichier reste sans réponse.
Sorties : <projet>-photos.json (exactement ce que le bouton « Terminer » télécharge : à donner à
outils\habillage\questions_photos.py ranger), capture-<photo>.png (l'écran après chaque geste) et capture-fin.png.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

SCENARIO = """
addEventListener("load", () => setTimeout(() => {
  const V = window.Verification, C = window.CalculsVerif, toile = document.getElementById("plan");
  const sortie = document.createElement("pre"); sortie.id = "scenario"; sortie.hidden = true; document.body.appendChild(sortie);
  try {
    toile.setPointerCapture = () => {};
    const ecran = (q) => { const [u, v] = C.versPixel(V.etat.matrice, q), r = toile.getBoundingClientRect();
      return [u * V.etat.vue.zoom + V.etat.vue.dx + r.left, v * V.etat.vue.zoom + V.etat.vue.dy + r.top]; };
    const souris = (t, q) => { const [x, y] = ecran(q); toile.dispatchEvent(new PointerEvent(t, { clientX: x, clientY: y, pointerId: 1, bubbles: true })); };
    const gestes = GESTES, arret = ARRET, journal = [];
    const ph = V.etat.photos;
    for (let i = 0; i < ph.questions.length; i++) {
      const nom = ph.questions[ph.rang].nom, g = gestes[nom];
      if (Array.isArray(g)) { souris("pointerdown", [g[0], g[1]]); souris("pointermove", [g[2], g[3]]); souris("pointerup", [g[2], g[3]]); }
      else if (g === "passer") document.getElementById("photo-passer").click();
      journal.push({ nom, numero: document.getElementById("photo-numero").textContent, etat: document.getElementById("photo-etat").textContent,
                     question: document.getElementById("photo-question").textContent });
      if (nom === arret) break;
      if (ph.rang < ph.questions.length - 1) document.getElementById("photo-suivante").click();
    }
    const b = C.reponsesPhotos(ph.questions, ph.endroits, ph.passees);
    sortie.textContent = JSON.stringify({ projet_id: V.etat.v.logement.projet_id, photos: { endroits: b.endroits, passees: b.passees }, sans_reponse: b.sans_reponse, journal });
  } catch (e) { sortie.textContent = JSON.stringify({ erreur: String(e && e.stack || e) }); }
}, 400));
"""


def page_du_scenario(ecran: Path, gestes: dict, arret: str | None, dossier: Path) -> Path:
    html = ecran.read_text(encoding="utf-8")
    script = SCENARIO.replace("GESTES", json.dumps(gestes)).replace("ARRET", json.dumps(arret))
    p = dossier / f"scenario-{arret or 'fin'}.html"
    p.write_text(html.replace("</body>", "<script>" + script + "</script></body>"), encoding="utf-8")
    return p


def jouer(ecran: Path, gestes: dict, sortie: Path) -> dict:
    if not CHROME.is_file():
        raise FileNotFoundError(f"Chrome introuvable : {CHROME}")
    sortie.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        # un profil neuf à chaque lancement : sinon les réponses gardées par le navigateur d'un lancement reviendraient au suivant
        chrome = lambda k: [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={Path(t) / f'p{k}'}",
                            "--window-size=1500,950", "--virtual-time-budget=6000"]
        page = page_du_scenario(ecran, gestes, None, Path(t))
        dom = subprocess.run(chrome(0) + ["--dump-dom", page.as_uri()], capture_output=True, timeout=180).stdout.decode("utf-8", "replace")
        m = re.search(r'<pre id="scenario"[^>]*>(.*?)</pre>', dom, re.S)
        if not m:
            raise RuntimeError("le scénario n'a rien rendu (la page ne s'est pas ouverte ?)")
        import html as html_
        r = json.loads(html_.unescape(m.group(1)))
        if "erreur" in r:
            raise RuntimeError("le scénario a planté dans la page : " + r["erreur"])
        for k, nom in enumerate([j["nom"] for j in r["journal"]] + [None], 1):  # une capture après chaque geste, puis la fin
            page = page_du_scenario(ecran, gestes, nom, Path(t))
            subprocess.run(chrome(k) + [f"--screenshot={(sortie / f'capture-{nom or 'fin'}.png').resolve()}", page.as_uri()], capture_output=True, timeout=180)
    rendu = {"schema": "reponses-photos/0.1", "projet_id": r["projet_id"], "photos": r["photos"]}
    (sortie / f"{r['projet_id']}-photos.json").write_text(json.dumps(rendu, ensure_ascii=False, indent=2), encoding="utf-8")
    return r


if __name__ == "__main__":
    try:
        ecran_, gestes_, sortie_ = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3])
        resultat = jouer(ecran_, gestes_, sortie_)
        for j in resultat["journal"]:
            print(f"  {j['nom']} | {j['numero']} | {j['question']} → {j['etat']}", flush=True)
        print(f"endroits pointés : {resultat['photos']['endroits']}\npassées : {resultat['photos']['passees']} ; sans réponse : {resultat['sans_reponse']}\n→ {sortie_}", flush=True)
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
