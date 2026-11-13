"""Le contrôleur du film (moteur/cinema/controle.py) : il repère seul, sur le plan, la caméra qui a le nez sur un mur, qui recule,
qui traverse un meuble posé en hauteur, qui finit sur un mur ; et laisse tranquille un vol propre."""
from moteur import promeneur as pm
from moteur.cinema import controle as ct


def _piece():
    # une pièce de 6 m × 4 m, fenêtre au sud
    murs = [{"id": "Ms", "debut": [0, 0], "fin": [6, 0], "epaisseur": 0.2}, {"id": "Mn", "debut": [0, 4], "fin": [6, 4], "epaisseur": 0.2},
            {"id": "Mo", "debut": [0, 0], "fin": [0, 4], "epaisseur": 0.2}, {"id": "Me", "debut": [6, 0], "fin": [6, 4], "epaisseur": 0.2}]
    ouvertures = [{"id": "F1", "type": "fenetre", "mur": "Ms", "position": 2.0, "largeur": 2.0, "hauteur": 1.4, "allege": 0.9}]
    return {"murs": murs, "ouvertures": ouvertures, "pieces": [{"id": "sejour_1", "contour": [[0, 0], [6, 0], [6, 4], [0, 4]]}],
            "meubles": [], "hauteur_sous_plafond": 2.5}


def _vol(points, etapes=None):
    """Un vol à la main : une clé toutes les 2 images (x, y, z, cap, tangage)."""
    return {"trajet": {"points": points, "images": (len(points) - 1) * 2 + 1}, "portes_ouvertes": [], "etapes": etapes or []}


def _glisse(x0, x1, y, cap, z=1.6, secondes=4.0):
    n = int(secondes * 12) + 1
    return [[x0 + (x1 - x0) * k / (n - 1), y, z, cap, -7.0] for k in range(n)]


def test_vol_propre_sans_defaut():
    """On avance vers l'est au milieu de la pièce en regardant devant soi, puis on ralentit : rien à redire (hors fin)."""
    c = ct.controler(_piece(), _vol(_glisse(1.0, 4.0, 2.0, 0.0)), budget_s=60)
    genres = {d["genre"] for d in c["defauts"]}
    assert not genres & {"nez_au_mur", "recul", "traverse", "rotation", "frole"}


def test_nez_au_mur():
    """À 40 cm du mur est, en le regardant : l'image est un mur."""
    c = ct.controler(_piece(), _vol(_glisse(5.5, 5.5, 2.0, 0.0)), budget_s=60)
    assert any(d["genre"] == "nez_au_mur" for d in c["defauts"])
    assert any(d["genre"] == "fin_ratee" for d in c["defauts"])
    assert c["note"] < 100


def test_la_camera_recule():
    """On se déplace vers l'est en regardant vers l'ouest : la caméra recule."""
    c = ct.controler(_piece(), _vol(_glisse(4.5, 1.5, 2.0, 0.0)), budget_s=60)
    assert any(d["genre"] == "recul" for d in c["defauts"])


def test_traverse_un_meuble_en_hauteur():
    """Un meuble haut de cuisine (bas à 1,40 m, 70 cm de haut) sur le chemin, caméra à 1,60 m : traversé. Une table basse
    (40 cm) au même endroit : survolée sans souci."""
    piece = _piece()
    piece["meubles"] = [{"id": "haut", "position": [3.0, 2.0], "face": 0.0, "dimensions": [0.8, 0.4, 0.7], "altitude": 1.4}]
    vol = _vol(_glisse(1.0, 5.0, 2.0, 0.0))
    assert any(d["genre"] == "traverse" for d in ct.controler(piece, vol, budget_s=60)["defauts"])
    piece["meubles"] = [{"id": "table", "position": [3.0, 2.0], "face": 0.0, "dimensions": [0.8, 0.4, 0.4]}]
    assert not any(d["genre"] == "traverse" for d in ct.controler(piece, vol, budget_s=60)["defauts"])


def test_rotation_trop_rapide():
    """Un tour complet en une seconde, en avançant : bien trop vite pour un film."""
    pts = _glisse(1.0, 4.0, 2.0, 0.0, secondes=2.0)
    for k, p in enumerate(pts):
        p[3] = 360.0 * k / 12
    assert any(d["genre"] == "rotation" for d in ct.controler(_piece(), _vol(pts), budget_s=60)["defauts"])


def test_budget_de_duree():
    c = ct.controler(_piece(), _vol(_glisse(1.0, 4.0, 2.0, 0.0, secondes=8.0)), budget_s=5.0)
    assert any(d["genre"] == "duree" for d in c["defauts"])


def test_controle_d_un_vol_d_atelya():
    """Sur un vrai vol d'Atelya : un rapport complet, une note entre 0 et 100, le temps passé dans chaque pièce montrée."""
    from tests.test_promeneur import _logement
    log = _logement()
    vol = pm.vol(log)
    c = ct.controler(log, vol)
    assert 0 <= c["note"] <= 100
    assert set(c["temps_par_piece_s"]) == {e["piece"] for e in vol["etapes"] if e["genre"] in ("point_de_vue", "coeur", "conclusion")}
    assert len(c["courbes"]["vitesse"]) == vol["trajet"]["images"]
    assert "Note du vol" in ct.rapport(c)


def test_collisions_en_hauteur():
    """Étape 2 : un meuble haut de cuisine (1,40 → 2,10 m) bloque la caméra volante, une table basse se survole, une suspension
    (bas à 1,95 m) se passe DESSOUS : la caméra y descend à au moins 30 cm sous l'objet, puis remonte. Le vol d'Atelya ne
    traverse plus rien (contrôleur)."""
    import numpy as np

    from moteur import realisateur as rz
    from moteur.cinema import camera, navigation
    from moteur.cinema.reglages import SOUS_OBJET_M, VOL_HAUTEUR_M
    from tests.test_promeneur import _logement
    log = _logement()
    log["hauteur_sous_plafond"] = 2.5
    haut = {"id": "haut", "position": [4.5, 3.5], "face": 0.0, "dimensions": [1.2, 0.4, 0.7], "altitude": 1.4}
    table = {"id": "table", "position": [1.5, 2.5], "face": 0.0, "dimensions": [0.8, 0.5, 0.4]}
    suspension = {"id": "lustre", "position": [3.0, 1.0], "face": 0.0, "dimensions": [0.6, 0.6, 0.5], "altitude": 1.95}
    log["meubles"] += [haut, table, suspension]
    assert navigation.bloque_le_vol(haut, VOL_HAUTEUR_M)
    assert not navigation.bloque_le_vol(table, VOL_HAUTEUR_M) and not navigation.bloque_le_vol(suspension, VOL_HAUTEUR_M)
    carte = navigation.Carte(log, [], hauteur_camera=VOL_HAUTEUR_M)
    assert not carte.libre[carte.case((4.5, 3.5))] and carte.libre[carte.case((1.5, 2.5))] and carte.libre[carte.case((3.0, 1.0))]
    # une traversée en ligne droite sous la suspension : la caméra passe dessous, assez bas
    positions = np.stack([np.linspace(0.5, 5.5, 240), np.full(240, 1.0)], 1)
    h, _ = camera.hauteurs_du_vol(positions, rz.Scene2D(log), log)
    sous = np.abs(positions[:, 0] - 3.0) <= 0.3
    assert h[sous].max() <= 1.95 - SOUS_OBJET_M + 1e-6
    assert not any(d["genre"] == "traverse" for d in ct.controler(log, pm.vol(log))["defauts"])
