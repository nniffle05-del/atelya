"""Lance les tests JavaScript de l'écran de vérification dans Chrome sans fenêtre (Node n'est pas installé sur le PC) :
une petite page imite node:test et node:assert, puis exécute tests/verif.test.js tel quel.
    ..\\atelya\\.venv\\Scripts\\python.exe pc\\verification\\tests_ecran.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ECRAN = Path(__file__).resolve().parents[2] / "outils" / "verification-plan"
IMITATION = r"""
const resultats = [];
const egal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const assert = {
  ok(v, m) { if (!v) throw new Error(m || "ok : faux"); },
  equal(a, b, m) { if (!Object.is(a, b)) throw new Error(m || `${a} ≠ ${b}`); },
  deepEqual(a, b, m) { if (!egal(a, b)) throw new Error(m || `${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`); },
  match(t, r, m) { if (!r.test(t)) throw new Error(m || `${t} ne correspond pas à ${r}`); },
  throws(f, attendu) {
    let e = null;
    try { f(); } catch (x) { e = x; }
    if (!e) throw new Error("aucune erreur levée");
    if (attendu instanceof RegExp && !attendu.test(e.message)) throw new Error(`erreur inattendue : ${e.message}`);
  },
};
const test = (nom, f) => {
  try { f(); resultats.push(`OK ${nom}`); } catch (e) { resultats.push(`ÉCHEC ${nom} : ${e.message}`); }
};
const require = (n) => (n === "node:test" ? test : n === "node:assert/strict" ? assert : n.endsWith(".json") ? window.EXEMPLE : window.CalculsVerif);
"""
FIN = """
document.getElementById("r").textContent = resultats.join("\\n");
"""


def main() -> int:
    calculs = (ECRAN / "calculs-verif.js").read_text(encoding="utf-8")
    essais = (ECRAN / "tests" / "verif.test.js").read_text(encoding="utf-8")
    essais = essais.replace('"use strict";', "", 1)
    exemple = (ECRAN / "exemples" / "exemple-cas-test-00.verification.json").read_text(encoding="utf-8")
    html = f'<!doctype html><meta charset="utf-8"><pre id="r">PAS FINI</pre><script>{calculs}</script><script>window.EXEMPLE = {exemple};</script><script>{IMITATION}\n(function (require) {{\n{essais}\n}})(require);\n{FIN}</script>'
    with tempfile.TemporaryDirectory() as t:
        page = Path(t) / "tests.html"
        page.write_text(html, encoding="utf-8")
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={Path(t) / 'p'}", "--virtual-time-budget=20000", "--dump-dom", page.as_uri()],
                           capture_output=True, timeout=120)
    dom = r.stdout.decode("utf-8", "replace")
    m = re.search(r'<pre id="r">(.*?)</pre>', dom, re.S)
    lignes = m.group(1).splitlines() if m else ["ÉCHEC : page illisible"]
    echecs = [x for x in lignes if not x.startswith("OK ")]
    for x in echecs:
        print(x.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&"))
    print(f"{len(lignes) - len(echecs)} tests OK, {len(echecs)} échecs")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
