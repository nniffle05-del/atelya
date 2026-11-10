r"""Les tests de l'écran de vérification (tests/verif.test.js, écrits pour Node.js) lancés dans Microsoft Edge, déjà présent sur
Windows : rien à installer (Node.js n'est ni sur le PC ni sur le Mac). 10/11/2026.

    ..\atelya\.venv\Scripts\python.exe outils\verification-plan\tests\lancer_dans_edge.py

Une page imite les deux outils de Node (`node:test`, `node:assert/strict`) et `require` d'un fichier JSON, charge
calculs-verif.js puis verif.test.js, et écrit les résultats ; Edge l'ouvre sans fenêtre (--headless) et rend la page.
Contrôle aussi la SYNTAXE de verification.js (une faute de frappe y casserait tout l'écran sans qu'aucun test le voie).
Rend (résultats, nombre d'échecs) ; None si Edge est absent.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DOSSIER = Path(__file__).resolve().parents[1]
EDGES = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
         Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body><pre id="r"></pre>
<script>
const resultats = [];
window.test = (nom, f) => { try { f(); resultats.push("OK   " + nom); } catch (e) { resultats.push("ÉCHEC " + nom + " : " + e.message); } };
const egal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
window.assertStrict = {
  ok: (c, m) => { if (!c) throw new Error(m || "faux"); },
  equal: (a, b, m) => { if (a !== b) throw new Error(m || `${a} !== ${b}`); },
  deepEqual: (a, b, m) => { if (!egal(a, b)) throw new Error(m || `${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`); },
  notEqual: (a, b, m) => { if (a === b) throw new Error(m || `${a} === ${b}`); },
  throws: (f, m) => { let ok = false; try { f(); } catch (e) { ok = true; } if (!ok) throw new Error("pas d'erreur"); },
  match: (s, r) => { if (!r.test(s)) throw new Error(`${s} ne correspond pas à ${r}`); },
};
const lire = (chemin) => { const x = new XMLHttpRequest(); x.open("GET", new URL(chemin, "BASE").href, false); x.send(); return x.responseText; };
window.require = (m) => {
  if (m === "node:test") return window.test;
  if (m === "node:assert/strict") return window.assertStrict;
  if (m.endsWith(".json")) return JSON.parse(lire(m.replace("../", "")));
  return window.CalculsVerif;
};
try { new Function(lire("verification.js")); resultats.push("OK   syntaxe de verification.js"); }
catch (e) { resultats.push("ÉCHEC syntaxe de verification.js : " + e.message); }
</script>
<script src="BASEcalculs-verif.js"></script>
<script src="BASEtests/verif.test.js"></script>
<script>document.getElementById("r").textContent = resultats.join(String.fromCharCode(10));</script>
</body></html>"""


def trouver_edge() -> Path | None:
    return next((e for e in EDGES if e.is_file()), None)


def lancer() -> tuple[list[str], int] | None:
    edge = trouver_edge()
    if edge is None:
        return None
    with tempfile.TemporaryDirectory() as d:
        page = Path(d) / "tests-ecran.html"
        page.write_text(PAGE.replace("BASE", DOSSIER.as_uri() + "/"), encoding="utf-8")
        r = subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                            "--virtual-time-budget=5000", "--dump-dom", page.as_uri()],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
    m = re.search(r'<pre id="r">(.*?)</pre>', r.stdout, re.S)
    if not m or not m.group(1).strip():
        raise RuntimeError(f"Edge n'a rien rendu : {r.stdout[:300]} {r.stderr[-500:]}")
    lignes = html.unescape(m.group(1)).splitlines()
    return lignes, sum(not l.startswith("OK") for l in lignes)


if __name__ == "__main__":
    res = lancer()
    if res is None:
        print("Edge introuvable : tests de l'écran non lancés")
        sys.exit(0)
    lignes, echecs = res
    print("\n".join(lignes))
    print(f"{len(lignes)} tests, {echecs} échec(s)")
    sys.exit(1 if echecs else 0)
