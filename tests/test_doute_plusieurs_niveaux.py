"""Image qui dessine plusieurs niveaux (ou logements) séparés : la lecture n'en garde qu'un, et la personne qui vérifie doit le savoir
(moteur.doutes 0.2.0, moteur.lecture_complete 0.4.0, moteur.preparer_verification 0.2.0).

Le défaut (08/11/2026) : coloriage.bati_du_logement ne garde que le plus gros bloc de bâti ; echelle_plan.plusieurs_blocs repérait
bien l'image, mais aucun doute n'était posé : une lecture à l'échelle sûre et sans autre doute fort sortait « lu », un étage entier
manquant, sans un mot à l'écran de vérification.

Les nouveautés sont appelées par leur nom de code (« plusieurs_niveaux ») et non importées : sur une copie du code d'avant, chaque
test échoue sur son assertion (le comportement), pas à l'import.
"""

import numpy as np

from moteur import lecture_complete as L
from moteur.coloriage import FENETRE, MUR, PORTE
from moteur.lecture_cotes import TexteLu

S = 40.0  # échelle des coloriages de test (px par m)
EP = 6  # épaisseur des murs (px)


def _bloc(c: np.ndarray, x0: int, y0: int, w: int, h: int) -> list[tuple[float, float, int]]:
    """Un niveau rectangulaire : un séjour et une chambre séparés par une cloison percée d'une porte, une fenêtre en façade.
    Rend (centre x, centre y, surface en pixels) de chaque pièce."""
    c[y0:y0 + h, x0:x0 + w] = MUR
    w_in = (w - 3 * EP) // 2
    pieces = []
    for k, classe in enumerate((5, 7)):
        xa = x0 + EP + k * (w_in + EP)
        c[y0 + EP:y0 + h - EP, xa:xa + w_in] = classe
        pieces.append((xa + w_in / 2, y0 + h / 2, w_in * (h - 2 * EP)))
    xc = x0 + EP + w_in  # la cloison
    c[y0 + h // 2 - 18:y0 + h // 2 + 18, xc:xc + EP] = PORTE
    c[y0:y0 + EP, x0 + 40:x0 + 90] = FENETRE
    return pieces


def _texte(m2: float, x: float, y: float) -> TexteLu:
    t = f"{m2:.2f}".replace(".", ",") + " m²"
    return TexteLu(t, np.array([[x - 30, y - 7], [x + 30, y - 7], [x + 30, y + 7], [x - 30, y + 7]], float), 0.95)


def _plan(deux_niveaux: bool) -> tuple[np.ndarray, L.PlanSource]:
    """Coloriage 768 × 480 (et image de même taille) : un 1er niveau de 400 × 220 px en haut ; un 2e de 300 × 200 px plus bas,
    séparé par du fond. Les surfaces écrites, justes, se confirment d'un niveau à l'autre : l'échelle est lue et sûre."""
    c = np.zeros((768, 480), np.uint8)
    textes = [_texte(round(a / S ** 2, 2), x, y) for x, y, a in _bloc(c, 40, 40, 400, 220)]
    if deux_niveaux:
        textes += [_texte(round(a / S ** 2, 2), x, y) for x, y, a in _bloc(c, 60, 420, 300, 200)]
    image = np.repeat(np.where(c == MUR, 30, 255).astype(np.uint8)[:, :, None], 3, axis=2)
    return c, L.PlanSource("niveaux", image, textes=textes, px_par_pt=1.0, a_plat=True)


def _forts(lu) -> list[str]:
    return [d["code"] for d in lu.examen["doutes"] if d["gravite"] == "fort"]


def test_deux_niveaux_doute_fort_en_tete_et_decision_a_verifier():
    c, source = _plan(True)
    lu = L.lire_avec_coloriage(source, c, None)
    assert lu.logement is not None and lu.infos.get("plusieurs_blocs")
    # L'échelle est lue et sûre (surfaces de deux niveaux d'accord) : seul le niveau manquant envoie le plan à la vérification.
    assert lu.echelle["etat"] == "lue", lu.echelle
    d = lu.examen["doutes"][0]
    assert d["code"] == "plusieurs_niveaux" and d["gravite"] == "fort" and d["element"] is None
    assert "plusieurs niveaux ou logements" in d["raison"] and "un seul a été lu" in d["raison"]
    assert "La partie non lue est entourée en orange." in d["raison"]
    assert _forts(lu) == ["plusieurs_niveaux"], _forts(lu)
    assert lu.examen["decision"] == "a_verifier"
    # La partie non lue est le 2e niveau (60, 420, 300 × 200), en pixels de l'image ; le 1er (lu) n'est pas entouré.
    (x, y, w, h), = d["blocs_px"]
    assert abs(x - 60) <= 6 and abs(y - 420) <= 6 and abs(w - 300) <= 12 and abs(h - 200) <= 12, d["blocs_px"]
    assert d["zone_px"] == d["blocs_px"][0]
    # La lecture du logement elle-même ne change pas : un seul niveau, celui du haut (2 pièces).
    assert len(lu.logement["pieces"]) == 2


def test_un_seul_niveau_rien_ne_change():
    c, source = _plan(False)
    lu = L.lire_avec_coloriage(source, c, None)
    assert not lu.infos.get("plusieurs_blocs")
    assert "plusieurs_niveaux" not in {d["code"] for d in lu.examen["doutes"]}
    assert lu.echelle["etat"] == "lue" and lu.examen["decision"] == "lu", (lu.echelle, lu.examen["doutes"])


def test_niveau_efface_par_le_nettoyage_du_bord_reste_signale():
    # Le 2e niveau est dessiné au bord haut de l'image : sans_taches_au_bord l'efface avant la lecture ; il reste signalé et situé.
    c = np.zeros((768, 480), np.uint8)
    textes = [_texte(round(a / S ** 2, 2), x, y) for x, y, a in _bloc(c, 60, 4, 300, 180)]
    textes += [_texte(round(a / S ** 2, 2), x, y) for x, y, a in _bloc(c, 40, 380, 400, 220)]
    image = np.repeat(np.where(c == MUR, 30, 255).astype(np.uint8)[:, :, None], 3, axis=2)
    lu = L.lire_avec_coloriage(L.PlanSource("bord", image, textes=textes, px_par_pt=1.0, a_plat=True), c, None)
    assert lu.infos.get("coloriage_nettoye")
    d = lu.examen["doutes"][0]
    assert d["code"] == "plusieurs_niveaux" and lu.examen["decision"] == "a_verifier"
    (x, y, w, h), = d["blocs_px"]
    assert y < 20 and abs(x - 60) <= 6, d["blocs_px"]


def test_le_bloc_non_lu_est_celui_que_le_logement_ne_recouvre_pas():
    # Piège vu sur le vrai plan fr-025 : le niveau LU n'est pas forcément le plus grand bloc (le traducteur choisit après avoir
    # régularisé les ouvertures). Ici le logement lu est posé sur le PETIT bloc (le 2e) : c'est le GRAND qui doit être signalé.
    c, _ = _plan(True)
    x0, y0, w, h = 60, 420, 300, 200  # le 2e bloc, plus petit
    logement = {"murs": [{"id": "M1", "debut": [0.0, 0.0], "fin": [w / S, 0.0], "epaisseur": 0.15},
                         {"id": "M2", "debut": [0.0, 0.0], "fin": [0.0, h / S], "epaisseur": 0.15}]}
    details = {"px_par_m": S, "origine_px": [float(x0), float(y0 + h)], "angle_deg": 0.0}
    blocs_non_lus = getattr(L, "blocs_non_lus", lambda *a, **k: None)
    boites = blocs_non_lus(c, logement, details, None, c.shape)
    assert boites is not None and len(boites) == 1, boites
    bx, by, bw, bh = boites[0]
    assert abs(bx - 40) <= 6 and abs(by - 40) <= 6 and abs(bw - 400) <= 12 and abs(bh - 220) <= 12, boites


def test_ecran_de_verification_recoit_le_doute_et_la_place_des_niveaux_non_lus():
    from moteur.preparer_verification import verification_du_plan

    c, source = _plan(True)
    plan = L.lire_plan(source, {"e5": lambda img: (c, None)}, avec_noms=False)
    v = verification_du_plan(plan)
    assert v is not None and v["lecture"]["decision"] == "a_verifier"
    d = v["doutes"][0]
    assert d["code"] == "plusieurs_niveaux" and d["gravite"] == "fort"
    assert d["zone_px"] == plan.gardee.examen["doutes"][0]["zone_px"] and len(d["blocs_px"]) == 1
