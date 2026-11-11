"""Le vrai soleil (moteur/soleil.py, outils/atelya/soleil_reel.py) : positions connues, orientation du plan, fiche de scène."""
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from moteur import soleil as s

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils" / "atelya"))


def test_positions_connues():
    # Paris : au midi solaire, hauteur = 90 - latitude + déclinaison (solstice d'été +23,44°, équinoxe ~0°)
    az, h = s.position(48.85, 2.35, datetime(2026, 6, 21, 11, 51, tzinfo=timezone.utc))
    assert h == pytest.approx(64.6, abs=0.3) and az == pytest.approx(180, abs=2)
    az, h = s.position(48.85, 2.35, datetime(2026, 3, 20, 11, 58, tzinfo=timezone.utc))
    assert h == pytest.approx(41.1, abs=0.6)
    assert s.position(48.85, 2.35, datetime(2026, 6, 21, 23, 0, tzinfo=timezone.utc))[1] < 0  # la nuit
    az, _ = s.position(48.85, 2.35, datetime(2026, 6, 21, 7, 0, tzinfo=timezone.utc))
    assert 60 < az < 120  # le matin, le soleil est à l'est


def test_heure_legale_et_orientation():
    assert s._decalage_heure_legale_france(date(2026, 4, 21)) == 2.0
    assert s._decalage_heure_legale_france(date(2026, 12, 1)) == 1.0
    # soleil plein sud, plan « nord en haut » : la direction vers le soleil va vers le bas du plan (-y)
    v = s.vers_le_soleil(180, 0, nord_deg=0)
    assert v[0] == pytest.approx(0, abs=1e-9) and v[1] == pytest.approx(-1)
    # même soleil, nord à droite du plan (nord_deg 90) : le sud est à gauche (-x)
    v = s.vers_le_soleil(180, 0, nord_deg=90)
    assert v[0] == pytest.approx(-1) and v[1] == pytest.approx(0, abs=1e-9)
    h = s.heure_de_hauteur(s.LIEU_DEFAUT, date(2026, 4, 21), 7.0)
    assert 19 < h < 21 and s.a_l_heure(s.LIEU_DEFAUT, date(2026, 4, 21), h)[1] == pytest.approx(7.0, abs=0.2)


def test_inscrire_dans_la_fiche(tmp_path):
    import soleil_reel
    fiche = {"eclairages": [{"id": "jour_soleil", "ciel": "physique"}, {"id": "jour_voile", "ciel": "couvert"},
                            {"id": "fin_de_journee", "ciel": "physique"}],
             "lumieres": [{"genre": "soleil", "direction": [0.6, 0.2, -0.77]}]}
    chemin = tmp_path / "scene-atelya.json"
    chemin.write_text(json.dumps(fiche), encoding="utf-8")
    bloc = soleil_reel.inscrire(chemin, 0.0, "NT : le soleil vient du sud")
    f = json.loads(chemin.read_text(encoding="utf-8"))
    jour = f["eclairages"][0]
    assert jour["hauteur_soleil"] == pytest.approx(51.9, abs=0.5) and jour["heure_legale"] == 15.0
    # rotation au format de Blender (0 = soleil vers +y, 90° vers +x) : SSO, plan nord en haut → soleil vers -x et -y
    assert -math.pi < jour["rotation_soleil"] < -math.pi / 2
    assert "rotation_soleil" not in f["eclairages"][1]  # voilé : pas de soleil
    assert f["lumieres"][0]["direction"][2] < 0  # la lumière descend
    assert bloc["orientation"]["statut"] == "estime" and bloc["lieu"]["statut"] == "ajoute"
