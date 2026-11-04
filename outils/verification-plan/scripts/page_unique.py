"""Fabrique, pour une lecture, une page unique « ecran.html » : l'écran de vérification, le plan et la lecture dans
un seul fichier. Un double-clic suffit : plus de fichiers à choisir. Le code de l'écran n'est pas modifié, il est recopié.

    python outils\\verification-plan\\scripts\\page_unique.py ..\\atelya\\lectures-verification\\fr-006 [autres dossiers...]
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ECRAN = Path(__file__).resolve().parents[1]
DEMARRAGE = ('addEventListener("load", () => { document.getElementById("exemple").click(); '
             'document.getElementById("exemple").style.display = "none"; });')


def _script(contenu: str) -> str:
    return "<script>" + contenu.replace("</script", "<\\/script") + "</script>"


def fabriquer(dossier: Path) -> Path:
    """Écrit <dossier>/ecran.html à partir de verification.json et plan.png, et renvoie son chemin."""
    v = json.loads((dossier / "verification.json").read_text(encoding="utf-8"))
    image = "data:image/png;base64," + base64.b64encode((dossier / "plan.png").read_bytes()).decode()
    donnees = "window.EXEMPLE_VERIFICATION = " + json.dumps({"verification": v, "image": image}, ensure_ascii=False) + ";"
    html = (ECRAN / "index.html").read_text(encoding="utf-8")
    for balise, contenu in (('<script src="calculs-verif.js"></script>', (ECRAN / "calculs-verif.js").read_text(encoding="utf-8")),
                            ('<script src="exemples/exemple-cas-test-00.js"></script>', donnees),
                            ('<script src="verification.js"></script>', (ECRAN / "verification.js").read_text(encoding="utf-8"))):
        if balise not in html:
            raise RuntimeError(f"index.html a changé : {balise} introuvable")
        html = html.replace(balise, _script(contenu))
    html = html.replace("</body>", _script(DEMARRAGE) + "</body>")
    sortie = dossier / "ecran.html"
    sortie.write_text(html, encoding="utf-8")
    return sortie


if __name__ == "__main__":
    for d in sys.argv[1:]:
        if not (Path(d) / "verification.json").is_file():
            print(f"{d} : pas de verification.json (plan refusé ou lecture ancienne), page non faite", flush=True)
            continue
        print(fabriquer(Path(d)), flush=True)
