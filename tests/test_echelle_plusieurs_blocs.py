"""Images qui dessinent plusieurs niveaux (ou logements) séparés par du fond : l'échelle ne peut pas venir des surfaces d'un seul
niveau ni de la taille d'un seul niveau (moteur.echelle_plan 0.14, moteur.lecture_complete 0.3).

Le défaut (08/11/2026) : le logement lu (coloriage.bati_du_logement) ne garde qu'un bloc ; les surfaces écrites dans les autres
tombaient « dehors » et n'étaient même pas comptées ; deux pièces d'un seul niveau d'accord entre elles suffisaient à annoncer une
échelle sûre (vrai plan d'entraînement fr-025, 3 niveaux : +5,5 % ; plan fabriqué 129128-ensemble : −6,0 %).
"""

import numpy as np
import pytest

import moteur.echelle_plan as ep
from moteur.coloriage import MUR
from moteur.echelle_plan import decider, lire_echelle_plan
from moteur.lecture_cotes import TexteLu

# Les nouveautés de la version 0.14 sont appelées par ep.xxx (et non importées) : sur une copie du code d'avant, chaque test échoue
# sur son assertion (le comportement), pas à l'import.

S = 40.0  # vraie échelle des coloriages de test (px par m)
EP = 6  # épaisseur des murs (px)
FAUSSE = 1.058  # les surfaces écrites dans le 1er niveau donnent une échelle fausse de +5,8 % (pièces coloriées trop petites)


def _bloc(c: np.ndarray, x0: int, y0: int, w: int, h: int, classe: int) -> list[tuple[float, float, int]]:
    """Un niveau rectangulaire coupé en deux pièces par une cloison ; rend (centre x, centre y, surface en pixels) de chaque pièce."""
    c[y0:y0 + h, x0:x0 + w] = MUR
    w_in = (w - 3 * EP) // 2
    pieces = []
    for k in range(2):
        xa = x0 + EP + k * (w_in + EP)
        c[y0 + EP:y0 + h - EP, xa:xa + w_in] = classe
        pieces.append((xa + w_in / 2, y0 + h / 2, w_in * (h - 2 * EP)))
    c[y0 + EP:y0 + h - EP, x0 + EP + 2 * w_in + EP:x0 + w - EP] = classe  # reste éventuel du partage (0 ou 1 px de large)
    return pieces


def _texte(m2: float, x: float, y: float) -> TexteLu:
    t = f"{m2:.2f}".replace(".", ",") + " m²"
    return TexteLu(t, np.array([[x - 30, y - 7], [x + 30, y - 7], [x + 30, y + 7], [x - 30, y + 7]], float), 0.95)


def _plan(deux_blocs: bool, trompeuses: bool, y_second: int = 400) -> tuple[np.ndarray, list[TexteLu]]:
    """Coloriage 768 × 480 : un 1er niveau de 400 × 200 px ; un 2e de 300 × 180 px plus bas, séparé par du fond.
    Surfaces écrites : celles du 1er niveau trompeuses (échelle × FAUSSE) si demandé, celles du 2e justes."""
    c = np.zeros((768, 480), np.uint8)
    textes = []
    for x, y, a in _bloc(c, 40, 40, 400, 200, 7):
        textes.append(_texte(round(a / (S * (FAUSSE if trompeuses else 1.0)) ** 2, 2), x, y))
    if deux_blocs:
        for x, y, a in _bloc(c, 60, y_second, 300, 180, 5):
            textes.append(_texte(round(a / S ** 2, 2), x, y))
    return c, textes


def _lire(c: np.ndarray, textes: list[TexteLu], **kw):
    dessin = np.where(c == MUR, 30, 255).astype(np.uint8)
    return lire_echelle_plan(dessin, c, None, textes=textes, **kw)


def test_reperage_des_blocs():
    plusieurs_blocs = ep.plusieurs_blocs
    assert plusieurs_blocs(_plan(True, False)[0])
    assert not plusieurs_blocs(_plan(False, False)[0])
    # Un petit bloc isolé (cartouche, flèche du nord coloriée en mur) n'est pas un 2e niveau.
    c = _plan(False, False)[0]
    c[600:640, 100:140] = MUR
    c[606:634, 106:134] = 7
    assert not plusieurs_blocs(c)


def test_deux_niveaux_dont_les_surfaces_trompent_partent_a_verifier():
    c, textes = _plan(True, True)
    e = _lire(c, textes)
    # Deux pièces du 1er niveau d'accord entre elles ne suffisent plus : les pièces du 2e niveau comptent, et aucun groupe d'accord
    # ne réunit deux niveaux → à vérifier (avant : « surfaces », +5,8 %, sans alerte).
    assert e.decision(de_biais=False) == (None, None, "à vérifier")
    assert e.plusieurs_blocs and not e.surfaces_sure
    # Le défaut, reproduit en lisant comme avant (le 2e niveau ignoré) : deux pièces d'accord, +5,8 % annoncé sûr.
    avant = _lire(c, textes, blocs=False)
    lx, _, source = avant.decision(de_biais=False)
    assert source == "surfaces" and lx == pytest.approx(S * FAUSSE, rel=0.01)


def test_deux_niveaux_qui_se_confirment_donnent_l_echelle():
    c, textes = _plan(True, False)
    e = _lire(c, textes)
    lx, ly, source = e.decision(de_biais=False)
    assert source == "surfaces" and lx == pytest.approx(S, rel=0.01) and e.surfaces_blocs == 2
    # Mais jamais sur une image jugée de biais : le redressement ne vaut que pour un seul plan de logement.
    assert decider(None, None, False, None, None, e.interieur_px, True, None, e.surfaces, True,
                   plusieurs_blocs=True) == (None, None, "à vérifier")


def test_niveau_efface_par_le_nettoyage_du_bord_reste_repere():
    pytest.importorskip("PIL")
    from moteur.lecture_complete import PlanSource, lire_avec_coloriage

    # Le 2e niveau est dessiné au bord haut de l'image : sans_taches_au_bord l'efface avant la lecture. Repéré sur le coloriage brut,
    # il interdit quand même aux surfaces trompeuses du 1er niveau de donner l'échelle.
    c = np.zeros((768, 480), np.uint8)
    textes = [_texte(round(a / S ** 2, 2), x, y) for x, y, a in _bloc(c, 60, 4, 300, 180, 5)]
    textes += [_texte(round(a / (S * FAUSSE) ** 2, 2), x, y) for x, y, a in _bloc(c, 40, 380, 400, 200, 7)]
    image = np.repeat(np.where(c == MUR, 30, 255).astype(np.uint8)[:, :, None], 3, axis=2)
    lu = lire_avec_coloriage(PlanSource("deux-niveaux", image, textes=textes), c, None)
    assert lu.echelle["etat"] == "a_verifier", lu.echelle.get("source")
    assert lu.infos.get("plusieurs_blocs") and lu.infos.get("coloriage_nettoye")


def test_un_seul_niveau_ne_change_pas():
    c, textes = _plan(False, False)
    e = _lire(c, textes)
    lx, ly, source = e.decision(de_biais=False)
    assert source == "surfaces" and lx == pytest.approx(S, rel=0.01)
    assert not getattr(e, "plusieurs_blocs", False) and getattr(e, "surfaces_blocs", 0) == 0
    if hasattr(ep, "plusieurs_blocs"):  # le même résultat, que le repérage soit fait ici ou donné
        e2 = _lire(c, textes, blocs=False)
        assert (e2.surfaces, e2.surfaces_sure, e2.surfaces_detail) == (e.surfaces, e.surfaces_sure, e.surfaces_detail)
    # Surfaces trompeuses sur un seul niveau : comme avant (deux pièces d'accord suffisent ; aucun contrôle de plus ici).
    c, textes = _plan(False, True)
    assert _lire(c, textes).decision(de_biais=False)[2] == "surfaces"


def test_regles_de_la_decision_sur_plusieurs_blocs():
    interieur = (380.0, 180.0)
    # La taille d'un seul niveau ne donne plus l'échelle (secours « cote d'ensemble ») …
    assert decider(None, None, False, 9.5, 4.5, interieur, False, plusieurs_blocs=True)[2] == "à vérifier"
    assert decider(None, None, False, 9.5, 4.5, interieur, False)[2] == "cote d'ensemble"
    # … ni ne rend une cote seule acceptable ; des cotes sûres, si.
    assert decider(S, S, False, None, None, interieur, False)[2] == "cotes"
    assert decider(S, S, False, None, None, interieur, False, plusieurs_blocs=True)[2] == "à vérifier"
    assert decider(S, S, True, None, None, interieur, False, plusieurs_blocs=True) == (S, S, "cotes")
    # La barre d'échelle dessinée reste valable.
    assert decider(None, None, False, None, None, interieur, False, S, plusieurs_blocs=True) == (S, S, "barre")
