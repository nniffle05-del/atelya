"""Tests du plan 2D propre (étape P7) : la page à livrer au client."""

import json
import math
from pathlib import Path

import pytest

from moteur.plan_propre import (
    DPI,
    Infos,
    _angle_de_murs,
    dessiner_page,
    dimensions_rectangle,
    est_exterieur,
    faire_plan,
    lire_entree,
    main,
    point_etiquette,
)

RACINE = Path(__file__).resolve().parent.parent
LOGEMENT = json.loads((RACINE / "exemples" / "cas-test-00" / "logement.json").read_text(encoding="utf-8"))
CORRIGE = RACINE / "outils" / "verification-plan" / "exemples" / "exemple-cas-test-00.logement-corrige.json"


def test_page_a4_a_300_points_par_pouce_et_surface_totale():
    page = dessiner_page(LOGEMENT, Infos(titre="Appartement T2", adresse="12 rue des Lilas\n75011 Paris"))
    assert page.format == "A4"
    largeur_mm = page.image.width / DPI * 25.4
    hauteur_mm = page.image.height / DPI * 25.4
    assert sorted([round(largeur_mm), round(hauteur_mm)]) == [210, 297]
    assert page.echelle in (50, 75, 100)  # une échelle d'architecte
    attendu = sum(p["surface"] for p in LOGEMENT["pieces"])
    assert page.surface_habitable == pytest.approx(attendu, abs=0.01)


def test_les_exterieurs_ne_comptent_pas_dans_la_surface_habitable():
    lg = json.loads(json.dumps(LOGEMENT))
    lg["pieces"][0]["nom"] = "Balcon"
    page = dessiner_page(lg)
    s0 = lg["pieces"][0]["surface"]
    assert page.surface_exterieurs == pytest.approx(s0, abs=0.01)
    assert page.surface_habitable == pytest.approx(sum(p["surface"] for p in lg["pieces"]) - s0, abs=0.01)
    assert est_exterieur("Terrasse 2") and not est_exterieur("Séjour")


def test_un_logement_incoherent_est_refuse():
    lg = json.loads(json.dumps(LOGEMENT))
    lg["pieces"][0]["surface"] = 99.0  # la surface annoncée ne correspond plus au contour
    with pytest.raises(ValueError):
        dessiner_page(lg)


def test_brouillon_tant_que_personne_n_a_verifie(tmp_path):
    entree = tmp_path / "logement.json"
    entree.write_text(json.dumps(LOGEMENT), encoding="utf-8")
    assert lire_entree(LOGEMENT)[1] is False
    infos = Infos()
    faire_plan(entree, tmp_path / "plan.pdf", infos)
    assert infos.brouillon
    assert (tmp_path / "plan.pdf").read_bytes()[:5] == b"%PDF-"
    assert (tmp_path / "plan.png").exists()


def test_sorti_de_l_ecran_de_verification_ce_n_est_plus_un_brouillon(tmp_path):
    infos = Infos()
    faire_plan(CORRIGE, tmp_path / "plan.pdf", infos, png=False)
    assert not infos.brouillon
    resultat = {"schema": "resultat-verification/0.1", "statut": "valide", "logement": LOGEMENT,
                "infos": {"adresse": "1 place du Marché", "nord_deg": 15}}
    _, verifie, extra = lire_entree(resultat)
    assert verifie and extra["adresse"] == "1 place du Marché"
    assert lire_entree({"schema": "verification/0.1", "logement": LOGEMENT})[1] is False


def test_la_commande_ecrit_le_pdf(tmp_path, capsys):
    sortie = tmp_path / "client" / "plan.pdf"
    main([str(CORRIGE), "--sortie", str(sortie), "--titre", "Appartement T2", "--adresse", "12 rue X|75011 Paris"])
    assert sortie.exists()
    assert "échelle 1/" in capsys.readouterr().out


def test_angle_droit_bouche_jusqu_au_coin_exterieur():
    a = {"debut": [0, 0], "fin": [5, 0], "epaisseur": 0.2}
    b = {"debut": [0, 0], "fin": [0, 4], "epaisseur": 0.2}
    coins = _angle_de_murs((0, 0), a, b)
    assert any(math.dist(c, (-0.1, -0.1)) < 1e-9 for c in coins)
    assert all(c[0] >= -0.1 - 1e-9 and c[1] >= -0.1 - 1e-9 for c in coins)  # rien ne dépasse


def test_mur_en_biais_coin_sans_pointe():
    # Deux murs presque alignés (un arrondi découpé en morceaux) : le coin ne doit pas faire de pointe.
    a = {"debut": [0, 0], "fin": [-2, 0], "epaisseur": 0.2}
    angle = math.radians(15)
    b = {"debut": [0, 0], "fin": [2 * math.cos(angle), 2 * math.sin(angle)], "epaisseur": 0.2}
    coins = _angle_de_murs((0, 0), a, b)
    assert max(math.dist(c, (0, 0)) for c in coins) < 0.2


def test_page_avec_murs_en_biais_et_arrondis():
    murs, pts = [], [(0, 0), (8, 0), (8, 4), (6, 6)]
    pts += [(1.5 + 1.5 * math.cos(math.radians(t)), 4.5 + 1.5 * math.sin(math.radians(t))) for t in range(90, 181, 30)]
    for i, (p, q) in enumerate(zip(pts, pts[1:] + pts[:1])):
        murs.append({"id": f"m{i}", "statut": "mesure", "source": "test", "debut": list(p), "fin": list(q),
                     "epaisseur": 0.2})
    lg = {"schema": "logement/0.1", "projet_id": "biais", "hauteur_sous_plafond": 2.5, "murs": murs,
          "ouvertures": [{"id": "f", "statut": "mesure", "source": "test", "type": "fenetre", "mur": "m2",
                          "position": 0.5, "largeur": 1.0, "hauteur": 1.2, "allege": 0.9}],
          "pieces": [{"id": "p", "statut": "mesure", "source": "test", "nom": "Séjour",
                      "contour": [[0.1, 0.1], [7.9, 0.1], [7.9, 3.95], [5.95, 5.9], [0.1, 5.9]]}]}
    page = dessiner_page(lg, Infos(nord_deg=30))
    assert page.surface_habitable > 40


def test_dimensions_et_etiquettes():
    assert dimensions_rectangle([[0, 0], [4, 0], [4, 3], [0, 3]]) == pytest.approx((4, 3))
    assert dimensions_rectangle([[0, 0], [4, 0], [4, 3], [2, 4], [0, 3]]) is None
    contour = [[0, 0], [6, 0], [6, 2], [2, 2], [2, 6], [0, 6]]  # une pièce en L
    x, y = point_etiquette(contour)
    assert not (x > 2 and y > 2)  # jamais dans le coin qui manque
