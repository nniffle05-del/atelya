"""Étape B1 (maquette sans défaut, 08/11/2026) : contrôle des trous, bouche-trous, zones sans pièce, murs qui se recouvrent.

Image simple : la maquette est en carton ; les murs sont des planches, le sol de chaque pièce une moquette. Ces tests vérifient
qu'il ne reste ni fente (on verrait le ciel), ni planches l'une dans l'autre (carrés noirs au rendu), et qu'un grand vide n'est
jamais bouché en silence."""
from __future__ import annotations

import pytest

from moteur.controle_maquette import controler, trous_a_signaler, vides_remplis
from moteur.geometrie import calculer_briques
from moteur.logement import Logement, Mur, Piece
from moteur.preparer_verification import doutes_de_construction

# Deux planches qui se TOUCHENT partagent un rang de cases (4 mm) dans la mesure : ~40 cm² de « recouvrement » sur ce plan. Un
# vrai coin l'un dans l'autre fait 400 cm² (20 × 20 cm) : au-delà de 100 cm², c'est un vrai recouvrement.
BRUIT_RECOUVREMENT = 0.01  # m²


def _mur(i, a, b, ep=0.20):
    return Mur(id=i, debut=a, fin=b, epaisseur=ep, statut="ajoute", source="test")


def _piece(i, nom, contour):
    return Piece(id=i, nom=nom, contour=contour, statut="ajoute", source="test")


def _log(murs, pieces):
    return Logement(schema="logement/0.1", projet_id="B1", hauteur_sous_plafond=2.5, murs=murs, ouvertures=[], pieces=pieces)


def _deux_pieces(gauche=True, droite=True, retrait=0.0):
    """6 × 4 m intérieur, murs de 20 cm, cloison de 10 cm à x = 3 ; `retrait` : contours lus un peu en retrait des murs."""
    murs = [_mur("S", (-0.1, -0.1), (6.1, -0.1)), _mur("E", (6.1, -0.1), (6.1, 4.1)), _mur("N", (6.1, 4.1), (-0.1, 4.1)),
            _mur("O", (-0.1, 4.1), (-0.1, -0.1)), _mur("C", (3.0, 0.0), (3.0, 4.0), 0.10)]
    r = retrait
    pieces = []
    if gauche:
        pieces.append(_piece("sejour_1", "Séjour", [(r, r), (2.95 - r, r), (2.95 - r, 4 - r), (r, 4 - r)]))
    if droite:
        pieces.append(_piece("chambre_1", "Chambre", [(3.05 + r, r), (6 - r, r), (6 - r, 4 - r), (3.05 + r, 4 - r)]))
    return murs, pieces


def test_contours_en_retrait_aucune_fente():
    murs, pieces = _deux_pieces(retrait=0.015)  # 1,5 cm de jour tout autour de chaque pièce avant B1
    log = _log(murs, pieces)
    r = controler(calculer_briques(log), 2.5)
    assert r["sol"]["trous"] == 0 and r["plafond"]["trous"] == 0


def test_cloison_en_t_ne_recouvre_pas_les_murs():
    murs, pieces = _deux_pieces()
    murs[4] = _mur("C", (3.0, -0.1), (3.0, 4.1), 0.10)  # la cloison lue « jusqu'à l'axe » des murs sud et nord
    r = controler(calculer_briques(_log(murs, pieces)), 2.5)
    assert r["murs_superposes_m2"] <= BRUIT_RECOUVREMENT and r["sol"]["trous"] == 0


def test_angle_lu_croise_ni_recouvrement_ni_trou():
    murs, pieces = _deux_pieces()
    murs[0] = _mur("S", (-0.25, -0.1), (6.1, -0.1))  # le mur sud dépasse de 15 cm à l'ouest…
    murs[3] = _mur("O", (-0.1, 4.1), (-0.1, -0.22))  # … et le mur ouest de 12 cm au sud : les deux traits se croisent
    briques = calculer_briques(_log(murs, pieces))
    r = controler(briques, 2.5)
    assert r["murs_superposes_m2"] <= BRUIT_RECOUVREMENT and r["sol"]["trous"] == 0
    murs_ = [p for b in briques if b.categorie == "mur" for p in b.contour]
    assert min(x for x, _ in murs_) >= -0.2 - 1e-6 and min(y for _, y in murs_) >= -0.2 - 1e-6  # plus de bout qui dépasse dehors


def test_piece_oubliee_signalee_jamais_bouchee():
    murs, pieces = _deux_pieces(droite=False)  # la chambre n'a pas été lue : 9,8 m² fermés sans pièce
    log = _log(murs, pieces)
    briques = calculer_briques(log)
    assert not any(b.id.startswith("joint_") and b.element == "chambre_1" for b in briques)
    trous = trous_a_signaler(briques, 2.5)
    assert len(trous) == 1 and trous[0]["aire_m2"] == pytest.approx(2.95 * 4, rel=0.03)
    doutes = doutes_de_construction(log.model_dump(by_alias=True))
    assert [d["code"] for d in doutes] == ["zone_sans_piece"] and doutes[0]["gravite"] == "fort"


def test_petite_gaine_remplie_et_signalee():
    murs, pieces = _deux_pieces()
    murs += [_mur("G1", (5.0, 4.0), (5.0, 3.15), 0.10), _mur("G2", (5.0, 3.2), (6.0, 3.2), 0.10)]  # gaine fermée d'environ 0,7 m²
    pieces[1] = _piece("chambre_1", "Chambre", [(3.05, 0.0), (6.0, 0.0), (6.0, 3.15), (5.05, 3.15), (5.05, 4.0), (3.05, 4.0)])
    log = _log(murs, pieces)
    briques = calculer_briques(log)
    assert controler(briques, 2.5)["sol"]["trous"] == 0
    assert any(b.id.startswith("joint_mur__") for b in briques)  # remplie comme un mur, du sol au plafond
    assert len(vides_remplis(briques)) == 1  # … et dite à la personne qui vérifie (WC ou placard oublié ?)
    assert "vide_rempli" in [d["code"] for d in doutes_de_construction(log.model_dump(by_alias=True))]


def test_bouche_trous_tournes_dans_le_bon_sens():
    murs, pieces = _deux_pieces(retrait=0.015)
    murs[4] = _mur("C", (3.0, 0.02), (3.0, 3.98), 0.10)  # cloison un peu courte : fentes aux deux bouts
    for b in calculer_briques(_log(murs, pieces)):
        if b.id.startswith("joint_"):
            aire = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(b.contour, b.contour[1:] + b.contour[:1])) / 2
            assert aire > 0, b.id  # sens direct, comme toutes les briques : sinon Blender voit la face de dos (noire)
