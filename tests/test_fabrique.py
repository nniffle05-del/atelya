"""Tests de la fabrique de plans : des logements valides, habitables, variés, et toujours les mêmes pour une graine."""

import json
import math

import cv2
import pytest

from moteur.banc_essai import essayer
from moteur.dessin_plan import Style, dessiner_plan
from moteur.fabrique import COTE_MIN, battants, en_logement, fabriquer, fabriquer_dossier
from moteur.geometrie import calculer_briques
from moteur.logement import Logement

GRAINES = range(1, 41)


@pytest.fixture(scope="module")
def fabrications():
    return {g: fabriquer(g) for g in GRAINES}


def test_meme_graine_meme_logement():
    assert en_logement(fabriquer(7)) == en_logement(fabriquer(7))
    assert en_logement(fabriquer(7)) != en_logement(fabriquer(8))


def test_logements_valides_et_constructibles(fabrications):
    for g, fab in fabrications.items():
        logement = Logement.model_validate(en_logement(fab))  # les règles de l'étape 1
        assert calculer_briques(logement), g  # Blender saurait le construire (étape 2)


def test_pieces_habitables_et_sans_chevauchement(fabrications):
    for g, fab in fabrications.items():
        rects = [p.rect for p in fab.pieces]
        for p in fab.pieces:
            assert min(p.rect.largeur, p.rect.hauteur) >= COTE_MIN[p.sorte], (g, p.nom)
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                chevauche = a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1
                assert not chevauche, g


def test_chaque_piece_accessible_depuis_la_porte_d_entree(fabrications):
    for g, fab in fabrications.items():
        logement = en_logement(fab)
        murs = {m["id"]: m for m in logement["murs"]}
        pieces = logement["pieces"]

        def pieces_de_part_et_d_autre(o):
            """Les pièces touchées en avançant de 15 cm de chaque côté du milieu de l'ouverture."""
            m = murs[o["mur"]]
            (ax, ay), (bx, by) = m["debut"], m["fin"]
            lg = math.dist((ax, ay), (bx, by))
            t = o["position"] + o["largeur"] / 2
            x, y = ax + t * (bx - ax) / lg, ay + t * (by - ay) / lg
            d = m["epaisseur"] / 2 + 0.15
            vertical = abs(bx - ax) < 1e-9
            cotes = [(x + d, y), (x - d, y)] if vertical else [(x, y + d), (x, y - d)]
            return [next((p["id"] for p in pieces if _dedans(c, p["contour"])), None) for c in cotes]

        portes = [pieces_de_part_et_d_autre(o) for o in logement["ouvertures"] if o["type"] == "porte"]
        entree = [p for p in portes if None in p]
        assert len(entree) == 1, g  # une seule porte donne dehors
        atteintes = {next(i for i in entree[0] if i)}
        while True:
            nouvelles = {b for a, b in portes for a, b in ((a, b), (b, a)) if a in atteintes and b} - atteintes
            if not nouvelles:
                break
            atteintes |= nouvelles
        assert atteintes == {p["id"] for p in pieces}, g


def test_pieces_de_vie_avec_fenetre(fabrications):
    for g, fab in fabrications.items():
        for p in fab.pieces:
            if p.sorte in {"sejour", "chambre", "cuisine"}:
                r = p.rect
                fenetres = [o for o in fab.ouvertures if o.type != "porte" and o.mur.dehors and _borde(o, r)]
                assert fenetres, (g, p.nom)


def test_variete(fabrications):
    types = {f.type for f in fabrications.values()}
    formes = {f.forme for f in fabrications.values()}
    assert types == {"T1", "T2", "T3", "T4"}
    assert formes == {"rectangle", "L"}


def test_dossier_pour_le_banc(tmp_path):
    fiche = fabriquer_dossier(3, tmp_path / "plan-00003")
    dossier = tmp_path / "plan-00003"
    assert {f.name for f in dossier.iterdir()} == {"logement.json", "plan.png", "fiche.json"}
    assert json.loads((dossier / "fiche.json").read_text(encoding="utf-8")) == fiche
    image = cv2.imread(str(dossier / "plan.png"), cv2.IMREAD_GRAYSCALE)
    assert image is not None and image.shape[0] > 400


def test_plan_fabrique_relu_par_la_lecture(tmp_path):
    """Un plan simple, dessiné dans le style du cas test n°0 : la lecture doit le retrouver presque sans faute."""
    fab = next(f for f in (fabriquer(g) for g in range(1, 100)) if f.type == "T1" and f.ep_cloison == 100)
    logement = en_logement(fab)
    dossier = tmp_path / "plan"
    dossier.mkdir()
    (dossier / "logement.json").write_text(json.dumps(logement), encoding="utf-8")
    cv2.imwrite(str(dossier / "plan.png"), dessiner_plan(logement, Style(), battants=battants(fab)))
    resultat = essayer(dossier / "plan.png", dossier / "logement.json")
    assert resultat.note is not None, resultat.echec
    assert resultat.note.ecart_dimensions <= 0.01  # l'échelle lue sur les cotes dessinées est juste
    assert resultat.note.murs_justes == resultat.note.murs_vrais


def _borde(o, r) -> bool:
    m = o.mur
    e = m.epaisseur / 2
    if m.vertical:
        return m.axe in (r.x0 - e, r.x1 + e) and r.y0 <= o.u0 and o.u1 <= r.y1
    return m.axe in (r.y0 - e, r.y1 + e) and r.x0 <= o.u0 and o.u1 <= r.x1


def _dedans(point, contour) -> bool:
    x, y = point
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans
