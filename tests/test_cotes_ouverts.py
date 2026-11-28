"""Côtés ouverts entre pièces (26/11/2026, « l'appareil dans un meuble ») : une cuisine ouverte sur l'entrée, sans mur entre
elles. Le regard passe ce côté, et le photographe d'une photo rangée « cuisine » peut se tenir dans l'entrée, tourné vers la
cuisine, comme sur le seuil d'une porte ; jamais de l'autre côté d'un vrai mur."""
import numpy as np

from moteur import caler_photos as cp


def _cuisine_ouverte():
    """Cuisine 3 × 2 m ouverte à l'est sur une entrée 3 × 2 m ; une salle d'eau au nord derrière un mur (y = 2,1)."""
    murs = [((0, -0.1), (6, -0.1)), ((-0.1, 0), (-0.1, 4)), ((6.1, 0), (6.1, 2)), ((0, 2.1), (6, 2.1)),
            ((3.1, 2.2), (3.1, 4)), ((0, 4.1), (3, 4.1))]
    return {"hauteur_sous_plafond": 2.5,
            "pieces": [{"id": "cuisine_1", "contour": [[0, 0], [3, 0], [3, 2], [0, 2]]},
                       {"id": "entree_1", "contour": [[3, 0], [6, 0], [6, 2], [3, 2]]},
                       {"id": "salle_d_eau_1", "contour": [[0, 2.2], [3, 2.2], [3, 4], [0, 4]]}],
            "murs": [{"id": f"m{i}", "debut": list(a), "fin": list(b), "epaisseur": 0.2} for i, (a, b) in enumerate(murs)],
            "ouvertures": []}


def _plan(ouverts: bool):
    avant = cp.COTES_OUVERTS
    cp.COTES_OUVERTS = ouverts
    try:
        return cp.plan_du_logement(_cuisine_ouverte())
    finally:
        cp.COTES_OUVERTS = avant


def test_le_cote_sans_mur_est_reconnu_ouvert_et_seulement_lui():
    plan = _plan(True)
    ouv = np.where(plan["ouverte"])[0]
    assert len(ouv) == 2  # la limite cuisine | entrée, vue de chaque côté
    assert {plan["ids"][plan["face_piece"][i]] for i in ouv} == {"cuisine_1", "entree_1"}
    assert np.allclose(plan["A"][ouv][:, 0], 3.0) and np.allclose(plan["B"][ouv][:, 0], 3.0)
    assert not _plan(False)["ouverte"].any()  # interrupteur éteint : comme avant


def test_le_regard_passe_le_cote_ouvert():
    o = np.array([[4.5, 1.0]])
    d_ferme, _, _ = cp.tirs(_plan(False), o, np.array([180.0]))
    d_ouvert, _, _ = cp.tirs(_plan(True), o, np.array([180.0]))
    assert abs(d_ferme[0, 0] - 1.5) < 1e-6   # avant : arrêté par la limite, comme par un mur
    assert abs(d_ouvert[0, 0] - 4.5) < 1e-6  # maintenant : jusqu'au mur du fond de la cuisine


def test_photo_de_cuisine_prise_depuis_l_entree_mais_pas_a_travers_un_mur():
    plan = _plan(True)
    G = cp.grille(plan); pg = cp.piece_de(plan, G)
    montree, permis = cp.pieces_montrees(plan, G, pg, [plan["ids"].index("cuisine_1")])
    place = lambda x, y: int(np.argmin(np.hypot(G[:, 0] - x, G[:, 1] - y)))
    entree, loin, sde = place(3.8, 1.0), place(5.6, 1.0), place(2.6, 2.6)
    assert montree[entree] == 0 and permis[entree, 180] and not permis[entree, 0]  # dans l'entrée, tourné vers la cuisine
    assert montree[loin] == -1                                                       # au fond de l'entrée : non
    assert montree[sde] == -1                                                        # derrière le mur, à 60 cm : jamais
    m_ferme, _ = cp.pieces_montrees(_plan(False), G, pg, [0])
    assert m_ferme[entree] == -1  # avant : la cuisine ne se photographiait que de l'intérieur


def test_l_espace_ouvert_reunit_la_cuisine_et_l_entree_pas_la_salle_d_eau():
    # sert à ne pas poser une seconde fois, dans l'entrée ouverte, un élément de cuisine déjà rangé le long de son mur
    for ouverts in (True, False):  # ne dépend pas de l'interrupteur du calage
        avant = cp.COTES_OUVERTS
        cp.COTES_OUVERTS = ouverts
        try:
            g = cp.espaces_ouverts(_cuisine_ouverte())
        finally:
            cp.COTES_OUVERTS = avant
        assert g["cuisine_1"] == g["entree_1"] == {"cuisine_1", "entree_1"}
        assert g["salle_d_eau_1"] == {"salle_d_eau_1"}


def test_le_cote_ouvert_est_un_seuil_comme_une_porte():
    # l'affinage des appareils (moteur/affiner_appareils.py) laisse l'appareil d'une photo de cuisine se tenir près d'un SEUIL
    # de la cuisine : ses portes, et son côté sans mur (sinon l'appareil trouvé dans l'entrée ouverte était refusé d'office)
    plan = _plan(True)
    assert (cp._passages(plan) & (np.array(plan["face_piece"]) == plan["ids"].index("cuisine_1"))).any()
    assert not cp._passages(_plan(False)).any()  # ce logement n'a pas de porte : sans l'interrupteur, aucun seuil
