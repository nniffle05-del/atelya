"""Photos calées seules (moteur/caler_photos.py) : la géométrie, les notes et les choix, sans aucun réseau."""
import math

import numpy as np
import torch

from moteur import caler_photos as cp


def _logement_en_l():
    """Une pièce en L (6 × 4 m, coin de 2 × 2 retiré) et une chambre de 3 × 4 à côté ; une porte, une fenêtre."""
    return {"hauteur_sous_plafond": 2.5,
            "pieces": [{"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 2], [4, 2], [4, 4], [0, 4]]},
                       {"id": "chambre_1", "contour": [[6.2, 0], [9.2, 0], [9.2, 4], [6.2, 4]]}],
            "murs": [{"id": "m1", "debut": [0, -0.1], "fin": [6, -0.1], "epaisseur": 0.2},
                     {"id": "m2", "debut": [6.1, 0], "fin": [6.1, 2], "epaisseur": 0.2}],
            "ouvertures": [{"mur": "m1", "type": "fenetre", "position": 2.0, "largeur": 1.5, "allege": 0.9, "hauteur": 1.3},
                           {"mur": "m2", "type": "porte", "position": 0.5, "largeur": 0.8, "hauteur": 2.1}]}


def test_plan_murs_portes_fenetres():
    plan = cp.plan_du_logement(_logement_en_l())
    assert plan["ids"] == ["sejour_1", "chambre_1"]
    assert (plan["sorte"] == 2).sum() == 1 and (plan["sorte"] == 1).sum() == 2  # la porte se voit des deux pièces
    d, sorte, appui = cp.tirs(plan, np.array([[2.75, 1.0]]), np.array([0.0, 90.0, 180.0, 270.0]))
    assert np.allclose(d[0], [3.25, 3.0, 2.75, 1.0], atol=1e-6)
    assert sorte[0].tolist() == [1, 0, 0, 2] and appui[0].tolist() == [False, False, False, True]
    assert cp.piece_de(plan, np.array([[1.0, 1.0], [5.0, 3.0], [7.0, 1.0]])).tolist() == [0, -1, 1]


def test_grille_dans_les_pieces():
    plan = cp.plan_du_logement(_logement_en_l())
    G = cp.grille(plan)
    assert len(G) > 500 and (cp.piece_de(plan, G) >= 0).all()
    assert not ((G[:, 0] > 4.05) & (G[:, 0] < 5.95) & (G[:, 1] > 2.05)).any()  # rien dans le coin retiré du L


def test_note_identique_en_numpy_et_en_torch():
    rng = np.random.default_rng(0)
    n = 40
    rm, rp = rng.uniform(1, 6, n).astype(np.float32), rng.uniform(1, 6, (7, n)).astype(np.float32)
    creux, sol = rng.integers(0, 4, n), rng.integers(-1, 2, n)
    sorte, appui = rng.integers(0, 3, (7, n)), rng.random((7, n)) > 0.5
    a = cp._note(np, rm, rp, creux, sol, sorte, appui)
    b = cp._note(torch, torch.from_numpy(rm), torch.from_numpy(rp), torch.from_numpy(creux), torch.from_numpy(sol), torch.from_numpy(sorte),
                 torch.from_numpy(appui)).numpy()
    assert np.allclose(a, b, atol=1e-5)


def test_la_bonne_place_a_la_meilleure_note():
    """Une « photo » fabriquée depuis une place connue du plan : la grille des notes la retrouve."""
    plan = cp.plan_du_logement(_logement_en_l())
    G = cp.grille(plan)
    t = cp.tirs(plan, G, np.arange(360.0))
    tp = (torch.from_numpy(t[0]).float(), torch.from_numpy(t[1]).to(torch.int8), torch.from_numpy(t[2]))
    g = int(np.argmin(np.hypot(G[:, 0] - 1.4, G[:, 1] - 2.8))); cap = 320
    phi = np.arange(-42.0, 43.0)
    d, sorte, _ = cp.tirs(plan, G[g][None], cap + phi)
    pr = {"phi": phi, "r": d[0] / 0.88, "creux": np.where(sorte[0] == 2, 3, 0).astype(np.int8), "sol": np.zeros(len(phi), np.int8)}  # vue 12 % trop profonde
    N, E = cp.notes_sur_le_plan(tp, pr, "cpu")
    i, k = np.unravel_index(N.argmax(), N.shape)
    assert np.hypot(*(G[i] - G[g])) < 0.25 and abs((k - cap + 180) % 360 - 180) <= 1 and cp.ECHELLES[int(E[i, k])] == 0.88
    cam, v = cp.regler(plan, pr, np.array([G[g][0] + 0.15, G[g][1] - 0.1, cap + 3.0, 0.96]))
    assert np.hypot(cam[0] - G[g][0], cam[1] - G[g][1]) < 0.1 and abs(cam[2] - cap) < 1.5 and v > 0.95


def test_bloc_de_deux_photos_pose_d_un_coup():
    T = {n: np.zeros((20, 30, 360), np.float32) for n in "ab"}
    T["a"][5, 10, 30] = 1.0; T["b"][8, 15, 120] = 1.0
    T["a"][12, 3, 200] = 0.9; T["b"][2, 25, 10] = 0.9  # de bonnes places chacune de son côté, mais pas ensemble
    c, s = math.cos(math.radians(-30)), math.sin(math.radians(-30))
    rel = {"a": (np.zeros(2), 0.0), "b": (np.array([c * 1.0 - s * 0.6, s * 1.0 + c * 0.6]), math.radians(90))}
    places = cp.poser_bloc(T, rel, ["a", "b"])
    assert places[0] == {"a": (10, 5, 30), "b": (15, 8, 120)}


def test_meubles_et_type_de_piece():
    assert cp.indices_des_meubles([]) == {}
    lit = cp.indices_des_meubles([{"nom": "a bed", "note": 0.6}])
    assert lit["chambre"] == 1.0 and cp._facteur(lit, "chambre_2") == 1.0 and cp._facteur(lit, "cuisine_1") == 0.25
    assert cp.indices_des_meubles([{"nom": "a sofa", "note": 0.5}])["sejour"] == 1.0


def test_choix_d_ensemble_une_photo_par_chambre():
    """Deux photos seules qui préfèrent toutes deux la chambre 1, de peu : chaque chambre doit être montrée."""
    def c(piece, x, note):
        return {"photos": {"p": {"cam": [x, 1.0, 0.0, 1.0], "note": note, "piece": piece}}}
    unites = [[c("chambre_1", 1.0, 0.80), c("chambre_2", 5.0, 0.78)], [c("chambre_1", 1.2, 0.80), c("chambre_2", 5.2, 0.70)]]
    ch, marges = cp.choisir_les_blocs(unites)
    assert ch == [1, 0]
    # une photo seule qui hésite entre deux chambres : pas « sûre » ; si l'une colle nettement mieux : sûre
    assert cp.choisir_les_blocs([[c("chambre_1", 1.0, 0.80), c("chambre_2", 5.0, 0.78)]])[1][0] < cp.MARGE_SURE
    assert cp.choisir_les_blocs([[c("chambre_1", 1.0, 0.80), c("chambre_2", 5.0, 0.30)]])[1][0] > cp.MARGE_SURE


def test_verticale_depuis_sol_et_plafond():
    rng = np.random.default_rng(1)
    n = np.zeros((80, 120, 3), np.float32)
    n[:30] = (0.05, 0.99, 0.1); n[50:] = (0.05, -0.99, -0.1); n[30:50] = (1, 0, 0)  # plafond, sol, mur
    n += rng.normal(0, 0.01, n.shape).astype(np.float32)
    haut = cp.verticale(n, np.ones((80, 120), bool))
    assert haut[1] < -0.98 and abs(np.linalg.norm(haut) - 1) < 1e-6
