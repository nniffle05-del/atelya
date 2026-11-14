"""MapAnything « apache » (moteur/mapanything.py) : les calculs sans les poids, sur un réseau RÉDUIT aux poids tirés au
hasard ; si le fichier de poids est là, la correspondance des noms et des formes (sans lire les 4,9 Go) ; le réseau entier
seulement si ATELYA_TEST_MAPANYTHING=1 (il lit tout le fichier et demande une carte graphique ou ~6 Go de mémoire)."""
import os

import numpy as np
import pytest
import torch

from moteur import mapanything as ma
from moteur.oeil_dinov2 import dossier_poids

POIDS = dossier_poids() / "map-anything-apache" / "model.safetensors"


def petit_reseau(graine=0):
    torch.manual_seed(graine)
    return ma.MapAnything(dim=48, tetes=4, blocs_oeil=2, blocs_partage=4, sorties=(1, 2), f=16, canaux=(8, 16, 32, 64)).eval()


def photos_au_hasard(n, h=90, w=120):
    return [np.random.default_rng(i).integers(0, 255, (h, w, 3), dtype=np.uint8) for i in range(n)]


def test_quaternion_vers_matrice():
    assert torch.allclose(ma.quaternion_vers_matrice(torch.tensor([0.0, 0.0, 0.0, 1.0])), torch.eye(3), atol=1e-6)
    s = 2 ** -0.5  # quart de tour autour de z : x devient y
    R = ma.quaternion_vers_matrice(torch.tensor([0.0, 0.0, s, s]))
    assert torch.allclose(R @ torch.tensor([1.0, 0.0, 0.0]), torch.tensor([0.0, 1.0, 0.0]), atol=1e-6)
    R = ma.quaternion_vers_matrice(torch.tensor([0.3, -0.2, 0.5, 0.7]))  # non normé : reste une rotation
    assert torch.allclose(R @ R.T, torch.eye(3), atol=1e-5) and abs(float(torch.det(R)) - 1) < 1e-5


def test_taille_visee_comme_l_original():
    """Table « fixed_mapping » d'origine pour 518 : la taille suit le rapport large / haut MOYEN du lot."""
    paysage, portrait, carre = np.zeros((792, 1206, 3), np.uint8), np.zeros((1206, 792, 3), np.uint8), np.zeros((600, 600, 3), np.uint8)
    assert ma.taille_visee([paysage]) == (518, 336) and ma.taille_visee([portrait]) == (336, 518) and ma.taille_visee([carre]) == (518, 518)
    assert ma.taille_visee([np.zeros((900, 1200, 3), np.uint8)]) == (518, 392) and ma.taille_visee([np.zeros((1080, 1920, 3), np.uint8)]) == (518, 294)
    assert ma.taille_visee([paysage, portrait]) == (518, 518)  # moyenne de 1,52 et 0,66 : le carré est le plus proche
    for cote in (112, 224, 300):  # autre taille : plus grand côté ramené à un multiple de 14
        tw, th = ma.taille_visee([paysage], cote)
        assert tw % 14 == 0 and th % 14 == 0 and tw == cote // 14 * 14 and abs(tw / th - 1206 / 792) < 0.2


def test_preparer_couvre_puis_rogne_au_centre():
    xx, yy = np.meshgrid(np.arange(1206), np.arange(792))
    photo = np.stack([xx * 255 // 1206, yy * 255 // 792, np.full_like(xx, 90)], -1).astype(np.uint8)
    im, cadre = ma.preparer(photo, (518, 336))
    assert im.shape == (336, 518, 3)
    # toute la largeur est gardée, 2 lignes sur 340 sont rognées en haut et en bas
    assert np.allclose(cadre, [0, 2 * 792 / 340, 1206, 338 * 792 / 340], atol=1e-6)
    assert abs(int(im[168, 0, 0]) - 0) <= 2 and abs(int(im[168, -1, 0]) - 254) <= 2 and abs(int(im[168, 259, 0]) - 127) <= 2
    im, cadre = ma.preparer(photo, (518, 518))  # photo plus large que la cible : les côtés sont rognés
    assert im.shape == (518, 518, 3) and cadre[1] == 0 and abs(cadre[3] - 792) < 1e-6 and abs((cadre[0] + cadre[2]) / 2 - 603) < 1.6
    im, _ = ma.preparer(np.full((100, 150, 3), 77, np.uint8), (518, 336))  # petite photo : agrandie
    assert im.shape == (336, 518, 3) and int(im.min()) == 77 and int(im.max()) == 77


def test_reduction_comme_pillow():
    """La réduction écrite ici (Lanczos, bicubique) rend la même image que Pillow, à l'arrondi près."""
    Image = pytest.importorskip("PIL.Image")
    rng = np.random.default_rng(0)
    im = np.kron(rng.integers(0, 255, (12, 18, 3)).astype(np.uint8), np.ones((20, 20, 1), np.uint8))
    im = (im * 0.7 + rng.integers(0, 76, im.shape)).astype(np.uint8)  # (240, 360, 3) : aplats + grain
    for (nw, nh), lanczos, filtre in (((155, 103), True, Image.LANCZOS), ((500, 333), False, Image.BICUBIC)):
        a = ma._redimensionner(im, nw, nh, lanczos)
        b = np.asarray(Image.fromarray(im).resize((nw, nh), resample=filtre))
        ecart = np.abs(a.astype(int) - b.astype(int))
        assert a.shape == b.shape and ecart.max() <= 3 and ecart.mean() < 0.1


def test_zoom_retrouve_depuis_les_rayons():
    h, w, fx, fy, cx, cy = 84, 112, 95.0, 101.0, 57.5, 40.25
    xs, ys = np.meshgrid(np.arange(w), np.arange(h))
    r = np.stack([(xs - cx) / fx, (ys - cy) / fy, np.ones_like(xs, float)], -1)
    r /= np.linalg.norm(r, axis=-1, keepdims=True)
    assert np.allclose(ma.zoom_depuis_rayons(r.astype(np.float32)), [fx, fy, cx, cy], atol=1e-2)


def test_formes_du_reseau_sans_les_poids():
    r = ma.lire(petit_reseau(), photos_au_hasard(3), cote=112)
    h, w = r["taille"]
    assert (h, w) == (84, 112)
    for cle in ("profondeur", "confiance", "masque"):
        assert r[cle].shape == (3, h, w)
    assert r["appareils"].shape == (3, 3, 4) and r["focale_px"].shape == (3, 2) and r["rayons"].shape == (3, h, w, 3)
    assert r["cadre"].shape == (3, 4) and r["echelle"] > 0 and (r["confiance"] >= 1).all() and r["masque"].dtype == bool
    assert np.isfinite(r["profondeur"]).all() and np.isfinite(r["appareils"]).all()
    assert np.allclose(np.linalg.norm(r["rayons"], axis=-1), 1, atol=1e-4)
    for R in r["appareils"][:, :, :3]:
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-4) and abs(np.linalg.det(R) - 1) < 1e-4


def test_la_premiere_photo_est_le_repere_les_autres_s_echangent():
    """Entre photos, le réseau ne connaît pas d'ordre : échanger la 2e et la 3e échange leurs sorties sans rien changer
    d'autre ; mais la 1re est marquée « repère » : la mettre ailleurs change le résultat."""
    m = petit_reseau(1)
    with torch.no_grad():
        m.info_sharing.view_pos_table.mul_(3.0)  # marque du repère bien visible malgré les poids au hasard
    p = photos_au_hasard(3, 84, 112)
    a, b = ma.lire(m, p, cote=112), ma.lire(m, [p[0], p[2], p[1]], cote=112)
    for cle in ("profondeur", "appareils", "focale_px"):
        assert np.allclose(a[cle][0], b[cle][0], rtol=1e-3, atol=1e-4)
        assert np.allclose(a[cle][1], b[cle][2], rtol=1e-3, atol=1e-4) and np.allclose(a[cle][2], b[cle][1], rtol=1e-3, atol=1e-4)
    assert abs(a["echelle"] - b["echelle"]) < 1e-4 * a["echelle"]
    c = ma.lire(m, [p[1], p[0], p[2]], cote=112)
    assert not np.allclose(a["profondeur"][0], c["profondeur"][1], rtol=1e-3, atol=1e-4)


def test_attention_par_paquets_de_tetes(monkeypatch):
    """Quand il y a beaucoup de jetons, l'attention est calculée quelques têtes à la fois : même résultat."""
    m, p = petit_reseau(2), photos_au_hasard(2, 84, 112)
    a = ma.lire(m, p, cote=112)
    monkeypatch.setattr(ma, "MEMOIRE_ATTENTION", 1.0)
    b = ma.lire(m, p, cote=112)
    assert np.allclose(a["profondeur"], b["profondeur"], rtol=1e-4, atol=1e-5) and np.allclose(a["appareils"], b["appareils"], atol=1e-5)


def test_demi_precision_sans_les_poids():
    """Œil et partage en float16, normes et têtes en float32 (seulement sur la carte : le float16 du processeur est lent)."""
    if not torch.cuda.is_available():
        pytest.skip("pas de carte graphique")
    torch.manual_seed(0)
    m16 = ma.MapAnything(dim=48, tetes=4, blocs_oeil=2, blocs_partage=4, sorties=(1, 2), f=16, canaux=(8, 16, 32, 64), demi=True, appareil="cuda").eval()
    assert m16.encoder.model.blocks[0].attn.qkv.weight.dtype == torch.float16 and m16.pose_head.fc_t.weight.dtype == torch.float32
    m32 = petit_reseau()
    m32.load_state_dict({k: v.float().cpu() for k, v in m16.state_dict().items()})
    p = photos_au_hasard(2, 84, 112)
    a, b = ma.lire(m16, p, cote=112), ma.lire(m32, p, cote=112)
    # écarts absolus : avec des poids au hasard un rayon peut être presque de côté (profondeur z proche de 0)
    assert np.allclose(a["profondeur"], b["profondeur"], rtol=0.02, atol=2e-3) and np.allclose(a["appareils"], b["appareils"], atol=5e-3)
    assert abs(a["echelle"] / b["echelle"] - 1) < 0.01


def test_chaque_poids_a_sa_place_si_les_poids_sont_la():
    """Sans lire les nombres (en-tête du fichier contre un réseau « sans mémoire ») : aucun poids manquant, aucun en trop,
    toutes les formes justes ; seuls les encodeurs des entrées géométriques (non réécrits) sont laissés de côté."""
    if not POIDS.is_file():
        pytest.skip("poids MapAnything absents")
    c = ma.comparer_aux_poids()
    assert c["manquants"] == [] and c["en_trop"] == [] and c["formes_fausses"] == []
    assert len(c["source"]) == 660 and len(c["ignores"]) == 76 and all(n.startswith(ma.IGNORES) for n in c["ignores"])
    # les noms en double du fichier (alias) désignent tous un tenseur que nous prenons sous son nom d'écriture
    assert set(c["alias"].values()) <= set(c["source"].values())
    pris = sum(c["nombres"][n] for n in set(c["source"].values()))
    assert pris == 1_163_101_182 and pris + sum(c["nombres"][n] for n in c["ignores"]) == sum(c["nombres"].values())


def test_reseau_entier_si_demande():
    if not POIDS.is_file() or os.environ.get("ATELYA_TEST_MAPANYTHING") != "1":
        pytest.skip("réseau entier : poids MapAnything absents, ou ATELYA_TEST_MAPANYTHING=1 non demandé")
    m = ma.charger()  # lève une erreur si un poids manque, est en trop ou n'a pas la bonne forme
    xx, yy = np.meshgrid(np.arange(600), np.arange(400))
    photo = np.stack([(xx * 255 // 600), (yy * 255 // 400), np.full_like(xx, 90)], -1).astype(np.uint8)
    r = ma.lire(m, [photo, photo[:, ::-1].copy()])
    assert r["taille"] == (336, 518) and r["profondeur"].shape == (2, 336, 518)
    assert np.isfinite(r["profondeur"]).all() and (r["profondeur"] > 0).all() and np.isfinite(r["appareils"]).all()
    assert 0.01 < r["echelle"] < 100 and (r["focale_px"] > 50).all()
    # la 1re photo sert de repère : son appareil sort à l'origine, sans rotation
    assert np.allclose(r["appareils"][0][:, :3], np.eye(3), atol=0.02) and np.abs(r["appareils"][0][:, 3]).max() < 0.05 * r["echelle"]
