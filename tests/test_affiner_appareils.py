"""L'appareil de chaque photo affiné dans l'image (moteur/affiner_appareils.py, 24/11/2026).

Une pièce simple (4 × 3 m, 2,50 m sous plafond) et un appareil connu : on fabrique ce que MoGe-2 verrait (points, sens des
surfaces), on vérifie que les lignes du plafond et du sol sont trouvées là où la géométrie les met, puis qu'un appareil
déplacé, tourné et au zoom trop serré est ramené à sa vraie place.
"""
import math

import numpy as np
import pytest

from moteur import affiner_appareils as aa
from moteur.camera_photo import axes

HSP = 2.5
W, H = 1206, 804
VRAI = np.array([1.0, 1.1, 1.3, 25.0, 0.0, 520.0, W / 2, 420.0])  # x, y, z, cap, tangage, f, u0, v0


def logement(avec_limite: bool = False) -> dict:
    """Une pièce de 4 × 3 m ; avec_limite : coupée en deux pièces par une limite SANS mur (x = 2,6)."""
    murs = [{"id": f"M{i}", "debut": a, "fin": b, "epaisseur": 0.2}
            for i, (a, b) in enumerate([([0, 0], [4, 0]), ([4, 0], [4, 3]), ([4, 3], [0, 3]), ([0, 3], [0, 0])])]
    if avec_limite:
        pieces = [{"id": "sejour_1", "contour": [[0, 0], [2.6, 0], [2.6, 3], [0, 3]]}, {"id": "cuisine_1", "contour": [[2.6, 0], [4, 0], [4, 3], [2.6, 3]]}]
    else:
        pieces = [{"id": "sejour_1", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]}]
    return {"hauteur_sous_plafond": HSP, "murs": murs, "ouvertures": [{"id": "P1", "type": "porte", "mur": "M3", "position": 1.0, "largeur": 0.8, "hauteur": 2.1}],
            "pieces": pieces}


def releve(cam, boite=None) -> dict:
    """Ce que MoGe-2 mesurerait de la pièce depuis cet appareil : points (repère de l'appareil : x à droite, y en bas, z devant),
    sens des surfaces, « haut ». boite : (x0, y0, x1, y1, hauteur) d'un meuble plein posé au sol."""
    x, y, z, cap, _, f, u0, v0 = cam
    vue, droite, haut = axes(cap)
    v, u = np.mgrid[0:H, 0:W] + 0.5
    d = vue[None, None] + droite[None, None] * ((u - u0) / f)[..., None] - haut[None, None] * ((v - v0) / f)[..., None]
    o = np.array([x, y, z])
    plans = [((1, 0, 0), 0.0), ((-1, 0, 0), -4.0), ((0, 1, 0), 0.0), ((0, -1, 0), -3.0), ((0, 0, 1), 0.0), ((0, 0, -1), -HSP)]
    t = np.full((H, W), np.inf)
    normale = np.zeros((H, W, 3))
    for n, c in plans:  # le plan n·p = c, normale tournée vers la pièce
        n = np.array(n, float)
        den = d @ n
        ti = np.where(den < -1e-9, (c - o @ n) / np.where(den < -1e-9, den, 1.0), np.inf)
        prend = (ti > 0) & (ti < t)
        t[prend] = ti[prend]
        normale[prend] = n
    if boite is not None:
        x0, y0, x1, y1, hb = boite
        for n, c, limites in (((-1, 0, 0), -x0, None), ((1, 0, 0), x1, None), ((0, -1, 0), -y0, None), ((0, 1, 0), y1, None), ((0, 0, 1), hb, None)):
            n = np.array(n, float)
            den = d @ n
            ti = np.where(den < -1e-9, (c - o @ n) / np.where(den < -1e-9, den, 1.0), np.inf)
            p = o[None, None] + d * np.where(np.isfinite(ti), ti, 0.0)[..., None]
            dedans = (p[..., 0] > x0 - 1e-6) & (p[..., 0] < x1 + 1e-6) & (p[..., 1] > y0 - 1e-6) & (p[..., 1] < y1 + 1e-6) & (p[..., 2] < hb + 1e-6)
            prend = dedans & (ti > 0) & (ti < t)
            t[prend] = ti[prend]
            normale[prend] = n
    pts = np.stack([(u - u0) / f * t, (v - v0) / f * t, t], -1)
    nor = np.stack([normale @ droite, -(normale @ haut), normale @ vue], -1)
    return {"points": pts.astype(np.float32), "normales": nor.astype(np.float32), "masque": np.isfinite(t), "focale_px": float(f),
            "haut": np.array([0.0, -1.0, 0.0])}


@pytest.fixture(scope="module")
def scene():
    return aa.Scene(logement())


@pytest.fixture(scope="module")
def jon():
    return aa.jonctions(releve(VRAI), HSP)


def test_les_faces_sans_mur_ne_sont_pas_pleines():
    log = logement(avec_limite=True)
    s = aa.Scene(log)
    assert len(s.limites[0]) == 2                       # la limite entre les deux pièces, vue des deux côtés
    assert all(abs(a[0] - 2.6) < 1e-6 and abs(b[0] - 2.6) < 1e-6 for a, b in zip(*s.limites))
    assert s.portes.sum() == 1


def test_plan_releve_en_partie_toutes_les_faces_comptent():
    log = logement()
    log["murs"] = log["murs"][:1]                       # un seul mur relevé sur quatre
    assert len(aa.Scene(log).limites[0]) == 0


def test_le_sol_est_la_surface_a_plat_la_plus_basse():
    rng = np.random.default_rng(0)
    lit = rng.normal(-0.75, 0.01, 6000)                 # le dessus d'un lit : plus de surface que le sol
    sol = rng.normal(-1.30, 0.01, 2500)
    assert abs(aa._niveau(np.concatenate([lit, sol]), True) - (-1.30)) < 0.03
    assert abs(aa._niveau(np.concatenate([lit, sol, rng.normal(-1.9, 0.01, 40)]), True) - (-1.30)) < 0.03  # trois points perdus ne comptent pas


def test_les_lignes_du_plafond_et_du_sol_sont_trouvees_ou_la_geometrie_les_met(scene, jon):
    assert len(jon["plafond"]) > 120 and len(jon["sol"]) > 120
    assert abs(jon["z"] - VRAI[2]) < 0.03
    for quoi, k in (("plafond", 0), ("sol", 1)):
        attendu = aa.lignes_du_plan(VRAI, scene.A, scene.B, HSP, jon[quoi][:, 0], scene.portes)[k]
        assert np.median(np.abs(jon[quoi][:, 1] - attendu)) < 1.5
    assert aa.cout(VRAI, scene, jon) < 2.0


def test_un_meuble_devant_le_mur_n_est_pas_pris_pour_le_pied_du_mur(scene):
    # un meuble bas (80 cm) contre le mur d'en face : le sol s'arrête à son pied, 50 cm devant le mur
    j = aa.jonctions(releve(VRAI, boite=(3.5, 0.5, 4.0, 2.5, 0.8)), HSP)
    attendu = aa.lignes_du_plan(VRAI, scene.A, scene.B, HSP, j["sol"][:, 0], scene.portes)[1]
    assert len(j["sol"]) > 40
    assert np.percentile(np.abs(j["sol"][:, 1] - attendu), 90) < 3.0   # aucun point posé au pied du meuble


def test_ce_qu_owlv2_cache_n_est_pas_mesure():
    caches = np.zeros((H, W), bool)
    caches[:, :W // 2] = True
    j = aa.jonctions(releve(VRAI), HSP, caches)
    assert len(j["plafond"]) > 60 and j["plafond"][:, 0].min() > W // 2 - 10
    assert len(j["sol"]) > 40 and j["sol"][:, 0].min() > W // 2 - 10


def test_un_appareil_faux_est_ramene_a_sa_place(scene, jon):
    faux = VRAI.copy()
    faux[0] -= 0.35; faux[1] += 0.25; faux[2] = 1.05; faux[3] += 5.0; faux[5] *= 1.2; faux[7] += 10
    assert aa.cout(faux, scene, jon) > 20
    rappels = {2: (1.3, aa.RAPPEL_Z), 7: (faux[7], aa.RAPPEL_V0)}
    cam, comment = aa.affiner_une_photo(faux, scene, jon, None, rappels, piece=0, z_vu=1.3)
    assert comment == "lignes"
    assert math.hypot(cam[0] - VRAI[0], cam[1] - VRAI[1]) < 0.18   # parti à 0,43 m ; le rappel vers la place de départ garde une dizaine de centimètres
    assert abs(cam[3] - VRAI[3]) < 1.0 and abs(cam[5] / VRAI[5] - 1) < 0.07   # zoom laissé libre (aucun zoom commun du lot)
    assert aa.cout(cam, scene, jon) < 3.0


def test_sans_assez_de_murs_l_appareil_reste(scene, jon):
    faux = VRAI.copy()
    faux[0] -= 0.3
    for peu in ({"plafond": jon["plafond"][:5], "sol": jon["sol"][:60], "z": 1.3, "largeur": W},        # presque pas de plafond
                {"plafond": jon["plafond"][:35], "sol": jon["sol"][:60], "z": 1.3, "largeur": W}):      # un coin de l'image seulement
        assert np.ptp(peu["plafond"][:, 0]) < aa.ETENDUE_MIN * W
        cam, comment = aa.affiner_une_photo(faux, scene, peu, None, {}, piece=0)
        assert comment == "depart" and np.allclose(cam, faux)


def test_des_lignes_qui_ne_collent_pas_au_plan_l_appareil_reste(scene, jon):
    rng = np.random.default_rng(3)
    brouille = {k: np.column_stack([jon[k][:, 0], rng.uniform(0, H, len(jon[k]))]) for k in ("plafond", "sol")}
    cam, comment = aa.affiner_une_photo(VRAI, scene, brouille, None, {}, piece=0)
    assert comment == "depart" and np.allclose(cam, VRAI)


def test_le_regard_qui_traverse_une_limite_sans_mur_ne_juge_pas():
    s = aa.Scene(logement(avec_limite=True))
    j = aa.jonctions(releve(VRAI), HSP)
    # le plan ne dit pas ce qu'il y a au-dessus de la limite : les colonnes qui la traversent comptent « neutre »
    d = aa.cout(VRAI, s, j, detail=True)
    assert d["plafond"] <= aa.NEUTRE_PX + 0.5 and d["sol"] <= aa.NEUTRE_PX + 0.5
    assert aa.accepte(VRAI, s, j, None)


def test_une_porte_toute_proche_n_arrete_pas_le_regard(scene):
    # l'appareil juste derrière la porte (mur x = 0, porte de y = 1,2 à 2,0) regarde dans la pièce : il voit le mur d'en face
    o = np.array([-0.3, 1.6])
    assert abs(aa.tirer(scene.A, scene.B, o, np.array([0.0]), scene.portes)[0] - 4.3) < 0.02
    assert aa.tirer(scene.A, scene.B, o, np.array([0.0]))[0] < 0.5         # sans la règle : arrêté par la porte


def test_les_lignes_lues_d_une_fenetre_deviennent_des_reperes():
    log = logement()
    log["ouvertures"].append({"id": "O1", "type": "fenetre", "mur": "M1", "position": 1.0, "largeur": 1.2, "allege": 0.9, "hauteur": 1.3})
    cam = np.array([1.0, 1.5, 1.3, 0.0, 0.0, 520.0, W / 2, 420.0])  # face au mur x = 4 (M1), fenêtre de y = 1,0 à 2,2
    from moteur.camera_photo import projeter, residus
    coin = lambda yy, zz: list(projeter([3.9, yy, zz], cam)[:2])  # noqa: E731 : face intérieure du mur (épaisseur 0,2)
    fen = [{"baie": "O1", "cadre": [coin(2.2, 2.2), coin(1.0, 2.2), coin(1.0, 0.9), coin(2.2, 0.9)],
            "sol": [coin(0.3, 0.0), coin(2.8, 0.0)], "plafond": coin(1.5, HSP)}]
    reps = aa.reperes_lus(log, fen)
    assert sorted(r["quoi"] for r in reps) == ["bas", "droite", "gauche", "haut", "plafond", "sol"]
    assert np.abs(residus(cam, reps)).max() < 0.5        # l'appareil vrai fait tomber chaque ligne lue à sa place
    recule = cam.copy()
    recule[0] -= 0.5
    assert np.abs(residus(recule, reps)).max() > 5.0
    # avec ces seules lignes (aucune ligne trouvée dans le relief), l'appareil reculé de 50 cm revient vers le mur
    vide = {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
    rappels = {2: (1.3, aa.RAPPEL_Z), 5: (520.0, aa.RAPPEL_ZOOM), 7: (420.0, aa.RAPPEL_V0)}
    c, comment = aa.affiner_une_photo(recule, aa.Scene(log), vide, reps, rappels, piece=0)
    assert comment == "lus" and abs(c[0] - cam[0]) < 0.15


def test_affiner_les_appareils_ecrit_l_appareil_et_garde_l_ancien():
    log = logement()
    faux = VRAI.copy()
    faux[0] -= 0.3; faux[5] *= 1.15
    cameras = {"photo-01": {"camera": dict(zip(aa.NOMS, (float(v) for v in faux))), "piece": "sejour_1", "sure": True}}
    photos = {"photo-01": np.zeros((H, W, 3), np.uint8)}
    bilan = aa.affiner_les_appareils(log, photos, cameras, {"photo-01": releve(VRAI)}, journal=lambda *a: None)
    d = cameras["photo-01"]
    assert bilan == {"photo-01": "lignes"} and d["affine"]["comment"] == "lignes"
    assert abs(d["affine"]["avant"]["x"] - faux[0]) < 1e-9 and abs(d["camera"]["x"] - VRAI[0]) < 0.15
    assert abs(d["camera"]["f"] / VRAI[5] - 1) < 0.04
    assert d["affine"]["ecart"]["plafond"][1] < d["affine"]["ecart"]["plafond"][0]


def test_l_appareil_affine_ne_se_colle_pas_au_mur(scene, jon):
    # des lignes qui « demandent » de reculer derrière le mur (photo plus large que la pièce ne le permet) : l'appareil
    # recule, mais s'arrête à distance du mur au lieu d'entrer dedans
    recule = VRAI.copy()
    recule[0] -= 1.3 * math.cos(math.radians(VRAI[3]))
    recule[1] -= 1.3 * math.sin(math.radians(VRAI[3]))           # 1,3 m en arrière : hors de la pièce
    large = aa.Scene({**logement(), "pieces": [{"id": "sejour_1", "contour": [[-3, -3], [4, -3], [4, 3], [-3, 3]]}]})
    j = {k: np.column_stack([jon[k][:, 0], aa.lignes_du_plan(recule, scene.A, scene.B, HSP, jon[k][:, 0])[i]]) for i, k in enumerate(("plafond", "sol"))}
    del large
    cam, _ = aa.affiner(VRAI, scene, {**j, "z": 1.3, "largeur": W}, None, {2: (1.3, aa.RAPPEL_Z), 5: (VRAI[5], aa.RAPPEL_ZOOM)}, piece=0)
    from moteur import caler_photos as cp
    assert float(cp._dist_seg(cam[None, :2], scene.A[~scene.portes], scene.B[~scene.portes]).min()) >= aa.CONTACT_MUR - 1e-3
