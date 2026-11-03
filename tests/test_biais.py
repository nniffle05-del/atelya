"""Étape A3 : pans coupés et angles arrondis du générateur (--biais)."""
import json
import random

import pytest

from moteur.generateur.annotations import decrire
from moteur.generateur.biais import angles_saillants, couper_angles
from moteur.generateur.logements import aire, contour_piece, en_logement, generer, surface_piece
from moteur.generateur.validateur import Regles, valider_geometrie


def _coupe(graine):
    log = generer(graine)
    faits = couper_angles(log, random.Random(f"biais-{graine}"))
    return log, faits


def test_angles_saillants_rectangle():
    assert sorted(angles_saillants([(0, 0), (10, 0), (10, 5), (0, 5)])) == [0, 1, 2, 3]
    # forme en L : le coin rentrant n'est pas saillant
    assert 3 not in angles_saillants([(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)])


@pytest.mark.parametrize("graine", [101, 102, 106, 111, 121])
def test_coupe_valide_et_surfaces_justes(graine):
    log, faits = _coupe(graine)
    assert faits, "au moins un angle coupé"
    v = valider_geometrie(log, decrire(log), Regles())
    assert v.accepte, v.erreurs
    for niv in log.niveaux:
        assert len(niv.murs_libres) == len(faits)
        # pièces + murs intérieurs ≈ enveloppe recoupée (le validateur le vérifie aussi)
        coupees = [p for p in niv.pieces if p.contour]
        assert coupees
        for p in coupees:
            assert surface_piece(p) == pytest.approx(aire(contour_piece(p)))
            assert surface_piece(p) < p.rect.surface


def test_logement_json_contient_les_murs_obliques():
    log, faits = _coupe(106)
    j = en_logement(log, log.niveaux[0])
    obliques = [m for m in j["murs"] if m["debut"][0] != m["fin"][0] and m["debut"][1] != m["fin"][1]]
    attendus = sum(1 if f["forme"] == "biais" else 12 for f in faits)
    assert len(obliques) == attendus
    json.dumps(j)


def test_sans_option_rien_ne_change():
    a, b = generer(101), generer(101)
    assert en_logement(a, a.niveaux[0]) == en_logement(b, b.niveaux[0])
    assert all(p.contour is None for p in a.pieces) and not a.niveaux[0].murs_libres
