"""La note de ressemblance photo / maquette (moteur/ressemblance.py) : les calculs, sans l'œil ni la carte graphique."""
import numpy as np

from moteur import ressemblance as rs

H, W = rs.HAUTEUR // 14, rs.LARGEUR // 14


def _image(graine: int) -> np.ndarray:
    """Une « image » décrite carré par carré (vecteurs de longueur 1), reproductible."""
    g = np.random.default_rng(graine).normal(size=(H, W, 16))
    return g / np.linalg.norm(g, axis=-1, keepdims=True)


def test_locale_vaut_1_pour_la_meme_image_et_presque_0_pour_deux_images_sans_rapport():
    a = _image(1)
    assert abs(rs.locale(a, a) - 1.0) < 1e-9
    assert abs(rs.locale(a, _image(2))) < 0.05


def test_les_coins_des_logos_ne_comptent_pas():
    a, b = _image(1), _image(1).copy()
    b[:3, :10] = _image(3)[:3, :10]  # seul le coin haut gauche diffère (logo de l'annonce)
    assert abs(rs.locale(a, b) - 1.0) < 1e-9
    assert not rs.masque_utile()[0, 0] and rs.masque_utile()[H // 2, W // 2]


def test_tableau_reconnait_la_vue_de_chaque_photo():
    photos = {f"photo-{k}": _image(k) for k in range(4)}
    bruit = lambda k: (photos[f"photo-{k}"] + 0.8 * _image(100 + k)) / np.linalg.norm(photos[f"photo-{k}"] + 0.8 * _image(100 + k), axis=-1, keepdims=True)
    rendus = {f"photo-{k}": bruit(k) for k in range(4)}
    t = rs.tableau(photos, rendus)
    assert all(v["rang"] == 1 and v["locale"] > v["meilleure_autre"] + 0.3 for v in t.values())
    r = rs.resume(t)
    assert r["photos"] == 4 and r["reconnues"] == 4 and r["marge"] > 0.3


def test_maquette_partout_pareille_n_est_pas_reconnue():
    photos = {f"photo-{k}": _image(k) for k in range(4)}
    meme = _image(50)
    t = rs.tableau(photos, {n: meme for n in photos})  # quatre vues identiques (murs blancs partout)
    assert rs.resume(t)["marge"] == 0.0 and all(abs(v["locale"]) < 0.05 for v in t.values())


def test_resume_vide():
    assert rs.resume({}) == {"photos": 0}
