"""Tests du correcteur : il doit reconnaître une lecture parfaite, et repérer chaque sorte d'erreur."""

import copy
import json
from pathlib import Path

import pytest

from moteur.banc_essai import bilan, essayer, trouver_plans
from moteur.correcteur import corriger

EXEMPLES = Path(__file__).parent.parent / "exemples"
VRAI = json.loads((EXEMPLES / "cas-test-00" / "logement.json").read_text(encoding="utf-8"))


def _lecture():
    """Une lecture parfaite, mais numérotée et ordonnée autrement que le corrigé, comme le fait la lecture auto."""
    lu = copy.deepcopy(VRAI)
    noms = {m["id"]: f"M{i}" for i, m in enumerate(reversed(lu["murs"]), start=1)}
    for m in lu["murs"]:
        m["id"] = noms[m["id"]]
        m["debut"], m["fin"] = m["fin"], m["debut"]  # dans l'autre sens
    for o in lu["ouvertures"]:
        mur = next(m for m in VRAI["murs"] if m["id"] == o["mur"])
        longueur = ((mur["fin"][0] - mur["debut"][0]) ** 2 + (mur["fin"][1] - mur["debut"][1]) ** 2) ** 0.5
        o["position"] = round(longueur - o["position"] - o["largeur"], 3)  # le mur est retourné
        o["mur"] = noms[o["mur"]]
    lu["murs"].reverse()
    for n, p in enumerate(lu["pieces"], start=1):
        p["id"] = f"piece_{n}"
        p["contour"] = p["contour"][2:] + p["contour"][:2]  # même pièce, autre coin de départ
    return lu


def test_lecture_parfaite():
    note = corriger(_lecture(), VRAI)
    assert (note.murs_justes, note.ouvertures_justes, note.pieces_justes) == (7, 7, 4)
    assert note.corrections == 0
    assert note.vert
    assert note.remarques == []


def test_mur_manquant_et_mur_invente():
    lu = _lecture()
    mur = lu["murs"].pop()  # le dernier mur lu ne porte pas d'ouverture qui nous gêne ici
    lu["ouvertures"] = [o for o in lu["ouvertures"] if o["mur"] != mur["id"]]
    lu["murs"].append({**mur, "id": "M99", "debut": [1.0, 1.0], "fin": [3.0, 1.0]})
    note = corriger(lu, VRAI)
    assert note.murs_trouves == 6
    assert note.murs_inventes == 1
    assert any("manquant" in r for r in note.remarques)
    assert any("M99 inventé" in r for r in note.remarques)


def test_mur_imprecis():
    lu = _lecture()
    lu["murs"][0]["fin"] = [lu["murs"][0]["fin"][0], lu["murs"][0]["fin"][1] + 0.08]
    lu["murs"][0]["debut"] = [lu["murs"][0]["debut"][0], lu["murs"][0]["debut"][1] + 0.08]
    note = corriger(lu, VRAI)
    assert note.murs_trouves == 7  # à 8 cm de l'axe : c'est bien le même mur…
    assert note.murs_justes == 6  # … mais pas assez précis


def test_erreur_d_echelle():
    """Tout est lu 2 % trop grand : les murs sont faux et les dimensions aussi."""
    lu = _lecture()
    for m in lu["murs"]:
        m["debut"] = [v * 1.02 for v in m["debut"]]
        m["fin"] = [v * 1.02 for v in m["fin"]]
    note = corriger(lu, VRAI)
    assert note.ecart_dimensions == pytest.approx(0.02, abs=0.002)
    assert not note.vert
    assert any("échelle" in r for r in note.remarques)


def test_ouvertures_type_largeur_manque():
    lu = _lecture()
    porte_fenetre = next(o for o in lu["ouvertures"] if o["type"] == "porte_fenetre")
    porte_fenetre["type"] = "fenetre"
    fenetre = next(o for o in lu["ouvertures"] if o["id"] == "F_chambre")
    fenetre["largeur"] = 1.20
    fenetre["position"] -= 0.10  # même milieu, plus large
    lu["ouvertures"] = [o for o in lu["ouvertures"] if o["id"] != "P_sdb"]
    note = corriger(lu, VRAI)
    assert note.ouvertures_trouvees == 6
    assert note.ouvertures_justes == 4
    assert note.ouvertures_inventees == 0
    assert any("lue comme fenêtre" in r for r in note.remarques)
    assert any("largeur 1.20" in r for r in note.remarques)
    assert any("P_sdb manquante" in r for r in note.remarques)


def test_ouverture_inventee():
    lu = _lecture()
    lu["ouvertures"].append({**lu["ouvertures"][0], "id": "F9", "position": 0.0, "largeur": 0.5})
    note = corriger(lu, VRAI)
    assert note.ouvertures_inventees == 1


def test_pieces_nom_surface():
    lu = _lecture()
    lu["pieces"][0]["nom"] = "SEJOUR + Cuisine"  # même nom, écrit autrement : juste
    lu["pieces"][1]["nom"] = "Chambre 2"
    lu["pieces"][2]["contour"] = [[4.90, 0.0], [6.20, 0.0], [6.20, 2.50], [4.90, 2.50]]  # entrée trop grande
    lu["pieces"].pop()
    note = corriger(lu, VRAI)
    assert (note.pieces_trouvees, note.pieces_justes) == (3, 1)
    assert any("« Salle d'eau » manquante" in r for r in note.remarques)


def test_hauteur_sous_plafond():
    lu = _lecture()
    lu["hauteur_sous_plafond"] = 2.40
    note = corriger(lu, VRAI)
    assert not note.hsp_juste
    assert note.corrections == 1


def test_banc_sur_les_exemples():
    """Le banc retrouve les deux plans du cas test n°0 et note la vraie lecture automatique."""
    couples = trouver_plans(EXEMPLES)
    assert [p.name for p, _ in couples] == ["plan-douteux.png", "plan.png"]
    resultats = [essayer(p, c) for p, c in couples]
    propre = resultats[1].note
    assert propre is not None and propre.corrections == 0
    douteux = resultats[0].note
    assert douteux is not None and douteux.corrections >= 1  # abîmé exprès : le correcteur doit le voir
    b = bilan(resultats)
    assert b["plans"] == 2 and b["echecs"] == 0
