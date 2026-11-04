"""La page unique de l'écran de vérification contient tout : plus aucun fichier à aller chercher à côté."""
import base64
import importlib.util
import json
from pathlib import Path

CHEMIN = Path(__file__).resolve().parents[1] / "outils" / "verification-plan" / "scripts" / "page_unique.py"
spec = importlib.util.spec_from_file_location("page_unique", CHEMIN)
page_unique = importlib.util.module_from_spec(spec)
spec.loader.exec_module(page_unique)


def test_page_autonome_avec_le_plan_et_la_lecture(tmp_path):
    (tmp_path / "plan.png").write_bytes(b"image-du-plan")
    (tmp_path / "verification.json").write_text(json.dumps({"schema": "verification/0.1", "note": "Séjour </script> fin"}), encoding="utf-8")
    html = page_unique.fabriquer(tmp_path).read_text(encoding="utf-8")
    assert '<script src="' not in html
    assert base64.b64encode(b"image-du-plan").decode() in html
    assert "Séjour <\\/script> fin" in html  # le texte du plan ne peut pas fermer le code de la page
    assert html.index("window.EXEMPLE_VERIFICATION") < html.index('addEventListener("load"')
