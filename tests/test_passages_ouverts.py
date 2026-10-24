"""Cloisons qui s'arrêtent au milieu d'une pièce, sans porte (étape 5d, vrais plans suisses)."""

from moteur.correcteur import corriger
from tests.test_murs_courts import _logement, _lire, _mur, _ouverture


def _sans_cloison() -> dict:
    vrai = _logement()
    vrai["murs"] = [m for m in vrai["murs"] if m["id"] != "C1"]
    vrai["ouvertures"], vrai["pieces"] = [], []
    return vrai


def test_cloison_arretee_au_milieu_de_la_piece():
    """Une cloison qui s'arrête à 1,80 m du mur d'en face, sans porte : elle n'est pas prolongée jusqu'à lui."""
    vrai = _sans_cloison()
    vrai["murs"].append(_mur("C1", [4.85, 0.0], [4.85, 3.6], 0.10))
    note = corriger(_lire(vrai), vrai)
    assert note.murs_justes == note.murs_vrais and note.murs_inventes == 0, note.remarques


def test_porte_dans_une_cloison():
    """Une cloison percée d'une porte reste un seul mur, avec sa porte, comme avant."""
    vrai = _sans_cloison()
    vrai["murs"].append(_mur("C1", [4.85, 0.0], [4.85, 5.4], 0.10))
    vrai["ouvertures"].append(_ouverture("P1", "porte", "C1", 2.2, 0.9))
    note = corriger(_lire(vrai), vrai)
    assert note.murs_justes == note.murs_vrais and note.murs_inventes == 0, note.remarques
    assert note.ouvertures_justes == 1, note.remarques
