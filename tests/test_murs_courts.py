"""Bouts de mur trop courts pour être lus seuls (étape 5d, vrais plans suisses)."""

from moteur.correcteur import corriger
from moteur.dessin_plan import Style, dessiner_plan


def _mur(id_, a, b, e):
    return {"id": id_, "debut": a, "fin": b, "epaisseur": e, "statut": "mesure", "source": "test"}


def _ouverture(id_, type_, mur, position, largeur):
    hauteur, allege = (1.35, 0.95) if type_ == "fenetre" else (2.04, 0.0)
    return {"id": id_, "type": type_, "mur": mur, "position": position, "largeur": largeur,
            "hauteur": hauteur, "allege": allege, "statut": "mesure", "source": "test"}


def _logement(ep: float = 0.27) -> dict:
    """Un T2 de 8,00 × 5,40 m intérieur, murs extérieurs d'épaisseur ep, une cloison de 10 cm avec une porte."""
    d = ep / 2
    return {
        "schema": "logement/0.1", "projet_id": "MURS-COURTS", "unites": "m", "hauteur_sous_plafond": 2.5,
        "murs": [
            _mur("M_sud", [-d, -d], [8 + d, -d], ep),
            _mur("M_est", [8 + d, -d], [8 + d, 5.4 + d], ep),
            _mur("M_nord", [-d, 5.4 + d], [8 + d, 5.4 + d], ep),
            _mur("M_ouest", [-d, -d], [-d, 5.4 + d], ep),
            _mur("C1", [4.85, 0.0], [4.85, 5.4], 0.10),
        ],
        "ouvertures": [_ouverture("P1", "porte", "C1", 2.0, 0.8)],
        "pieces": [
            {"id": "s", "nom": "Séjour", "contour": [[0, 0], [4.8, 0], [4.8, 5.4], [0, 5.4]], "surface": 25.92,
             "statut": "mesure", "source": "test"},
            {"id": "c", "nom": "Chambre", "contour": [[4.9, 0], [8, 0], [8, 5.4], [4.9, 5.4]], "surface": 16.74,
             "statut": "mesure", "source": "test"},
        ],
    }


def _lire(vrai: dict, px_par_m: int = 80) -> dict:
    from moteur.lecture_plan import lire_plan, logement_depuis_plan

    return logement_depuis_plan(lire_plan(dessiner_plan(vrai, Style(px_par_m=px_par_m)), px_par_m=px_par_m), "TEST")


def test_trumeaux_entre_fenetres():
    """Trois fenêtres séparées par des bouts de mur de 25 cm : le mur reste entier, avec ses trois fenêtres."""
    vrai = _logement()
    for i, position in enumerate((0.70, 2.25, 3.80)):
        vrai["ouvertures"].append(_ouverture(f"F{i + 1}", "fenetre", "M_ouest", position, 1.30))
    note = corriger(_lire(vrai), vrai)
    assert note.murs_justes == note.murs_vrais and note.murs_inventes == 0, note.remarques
    assert note.ouvertures_justes == 4, note.remarques


def test_cloison_fine_terminee_par_un_bout_de_mur_epais():
    """Une cloison de 7 cm qui finit par un bout de mur de 30 cm (gaine, coffre) : elle n'est plus perdue.

    Ensemble, ils ne remplissent pas la moitié de leur cadre ; la lecture les jetait comme un dessin troué.
    """
    vrai = _logement()
    vrai["murs"] += [
        _mur("C2", [0.0, 2.70], [3.80, 2.70], 0.07),
        _mur("Bout", [3.80, 2.815], [4.80, 2.815], 0.30),  # même face du bas que la cloison
    ]
    note = corriger(_lire(vrai), vrai)
    assert note.murs_trouves == note.murs_vrais, note.remarques
