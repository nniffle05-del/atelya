"""Ouvre le VRAI écran de vérification sur une vraie lecture, dans Chrome sans fenêtre, et en fait une capture.
Rien n'est installé et le dossier de l'écran n'est pas touché : on travaille sur une copie temporaire.
    python pc\\verification\\essai_ecran.py ..\\atelya\\lectures-verification\\fr-006 capture.png
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ECRAN = Path(__file__).resolve().parents[2] / "outils" / "verification-plan"

dossier, capture = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
if not (dossier / "verification.json").is_file():
    sys.exit(f"PLANTÉ : pas de verification.json dans {dossier}")
with tempfile.TemporaryDirectory() as t:
    copie = Path(t) / "ecran"
    shutil.copytree(ECRAN, copie)
    v = json.loads((dossier / "verification.json").read_text(encoding="utf-8"))
    image = "data:image/png;base64," + base64.b64encode((dossier / "plan.png").read_bytes()).decode()
    (copie / "exemples" / "exemple-cas-test-00.js").write_text(
        "window.EXEMPLE_VERIFICATION = " + json.dumps({"verification": v, "image": image}, ensure_ascii=False) + ";\n", encoding="utf-8")
    page = copie / "index.html"
    html = page.read_text(encoding="utf-8").replace(
        "</body>", '<script>addEventListener("load",()=>document.getElementById("exemple").click())</script></body>')
    page.write_text(html, encoding="utf-8")
    url = page.as_uri()
    profil = str(Path(t) / "profil")
    commun = [CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profil}", "--window-size=1500,1000", "--virtual-time-budget=8000"]
    r = subprocess.run(commun + [f"--screenshot={capture}", url], capture_output=True, timeout=120)
    if not capture.exists():
        sys.exit(f"PLANTÉ : pas de capture ({r.stderr.decode(errors='replace')[-300:]})")
    dom = subprocess.run(commun + ["--dump-dom", url], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
m = re.search(r'<ul class="doutes" id="doutes">(.*?)</ul>', dom, re.S)
print("doutes affichés :", len(re.findall(r"<li", m.group(1))) if m else "liste introuvable")
print("refusé ?", "Fichier de vérification refusé" in dom, "| écrits dans le fichier :", len(v["doutes"]))
