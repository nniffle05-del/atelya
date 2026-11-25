"""Le juge de la lumière du film (moteur/juge_lumiere.py) : cadrage exact de la photo, mesures, image rejouée."""
import math

import numpy as np

from moteur import juge_lumiere as jl
from moteur import pellicule_unreal, photographe
from moteur.camera_photo import axes, camera_depuis_dict, projeter

PHOTO = {"largeur": 1206, "hauteur": 804,
         "camera": {"x": 2.0, "y": 3.0, "z": 1.3, "cap": 40.0, "tangage": 0.0, "f": 540.0, "u0": 603.0, "v0": 311.0}}
POINTS = [(5.0, 5.5, 0.0), (6.0, 4.0, 2.4), (4.0, 7.0, 1.0), (7.5, 9.0, 0.2)]


def _pixel_du_film(point, cap, tangage, f, largeur, hauteur):
    """Où la caméra du film (qui regarde au centre de son image) voit un point."""
    return projeter(point, [PHOTO["camera"]["x"], PHOTO["camera"]["y"], PHOTO["camera"]["z"], cap, tangage, f, largeur / 2, hauteur / 2])


def test_le_cadre_du_film_est_celui_de_la_photo():
    cadre = jl.cadre_du_film(PHOTO)
    largeur, hauteur = cadre["format"]
    assert largeur % 2 == 0 and hauteur % 2 == 0 and hauteur >= PHOTO["hauteur"]
    f = cadre["focale_mm"] / jl.CAPTEUR_MM * largeur
    x0, y0, w, h = cadre["rognage"]
    assert (w, h) == (1206, 804) and y0 + h <= hauteur and x0 + w <= largeur
    cam = camera_depuis_dict(PHOTO["camera"])
    for point in POINTS:
        u, v, _ = projeter(point, cam)
        uf, vf, _ = _pixel_du_film(point, cam[3], cadre["tangage"], f, largeur, hauteur)
        assert abs(uf - x0 - u) < 0.6 and abs(vf - y0 - v) < 0.6


def test_une_vue_deja_rognee_est_rendue_telle_quelle():
    cadre = jl.cadre_du_film(PHOTO)
    image = np.random.default_rng(0).integers(0, 255, (804, 1206, 3), dtype=np.uint8)
    sortie, valide = jl.film_au_cadre(image, PHOTO, {"cadre": "photo", "rognage": cadre["rognage"]})
    assert np.array_equal(sortie, image) and valide.all()
    grande = np.zeros((cadre["format"][1], cadre["format"][0], 3), np.uint8)
    x0, y0, w, h = cadre["rognage"]
    grande[y0:y0 + h, x0:x0 + w] = image
    sortie, _ = jl.film_au_cadre(grande, PHOTO, {"cadre": "photo", "rognage": cadre["rognage"]})
    assert np.array_equal(sortie, image)


def test_l_ancienne_vue_penchee_revient_au_cadre_de_la_photo():
    """Les vues du 18/11/2026 : caméra penchée vers le centre de la photo. Un point peint sur l'image du film doit retomber
    là où l'appareil de la photo le voit."""
    c = PHOTO["camera"]
    tangage = -math.degrees(math.atan((PHOTO["hauteur"] / 2 - c["v0"]) / c["f"]))
    trajet = {"points": [[c["x"], c["y"], c["z"], c["cap"], tangage]], "focale_mm": c["f"] * 36.0 / 1206}
    film = np.zeros((804, 1206, 3), np.uint8)
    attendus = []
    cam = camera_depuis_dict(c)
    for point in POINTS:
        uf, vf, _ = _pixel_du_film(point, c["cap"], tangage, c["f"], 1206, 804)
        if 10 < uf < 1196 and 10 < vf < 794:
            film[int(round(vf)) - 3:int(round(vf)) + 4, int(round(uf)) - 3:int(round(uf)) + 4] = 255
            attendus.append(projeter(point, cam)[:2])
    assert len(attendus) >= 3
    image, valide = jl.film_au_cadre(film, PHOTO, trajet)
    assert not valide.all() and valide.mean() > 0.8  # une bande de la photo est hors du champ du film penché
    for u, v in attendus:
        if 10 < u < 1196 and 10 < v < 794:
            zone = image[int(round(v)) - 2:int(round(v)) + 3, int(round(u)) - 2:int(round(u)) + 3]
            assert zone.mean() > 200, (u, v)


def test_la_scene_du_film_remonte_la_pellicule():
    scene = np.array([[0.6, 0.6, 0.6], [0.30, 0.17, 0.08], [0.05, 0.08, 0.20], [1.5, 1.4, 1.3]])
    c = photographe.PELLICULE_COULEURS
    ecran = 255.0 * pellicule_unreal.affiche(scene, photographe.PELLICULE, c["saturation"], c["expand_gamut"], c["blue_correction"])
    retour = jl.scene_du_film(ecran)
    assert np.allclose(retour, scene, rtol=0.04, atol=0.004)


def test_rejouer_sans_rien_changer_rend_la_meme_image():
    # une vraie image du film : des couleurs de scène passées par la pellicule (toute couleur d'écran n'en sort pas)
    # … ni toute couleur de scène : une couleur très vive sort de ce que l'écran sait montrer (une couleur à 0 ne se remonte pas)
    rng = np.random.default_rng(1)
    scene = rng.uniform(0.02, 1.2, (40 * 60, 1)) * rng.uniform(0.75, 1.25, (40 * 60, 3))
    c = photographe.PELLICULE_COULEURS
    ecran = pellicule_unreal.affiche(scene, photographe.PELLICULE, c["saturation"], c["expand_gamut"], c["blue_correction"])
    image = np.round(255.0 * ecran).astype(np.uint8).reshape(40, 60, 3)
    assert np.abs(jl.refaire_l_image(image).astype(int) - image.astype(int)).max() <= 3
    plus_claire = jl.refaire_l_image(image, crans=1.0)
    assert plus_claire.mean() > image.mean() + 10


def test_le_blanc_et_le_relief_des_murs():
    rng = np.random.default_rng(2)
    plats = {k: np.full(3, 0.5) + rng.normal(0, 0.002, 3) for k in range(60)}
    m = jl.mesurer_murs(plats)
    assert abs(m["L"] - 76.1) < 1.0 and m["C"] < 1.5 and m["relief"] < 1.5
    contrastes = {k: np.full(3, 0.15 if k % 2 else 0.7) for k in range(60)}
    assert jl.mesurer_murs(contrastes)["relief"] > 30
    assert jl.mesurer_murs({k: np.full(3, 0.5) for k in range(5)}) is None


def test_le_sol_contre_le_mur_ne_depend_pas_de_l_exposition():
    murs, sol = {"lineaire": [0.8, 0.8, 0.8]}, {"lineaire": [0.4, 0.2, 0.1]}
    r = jl.sol_contre_mur(sol, murs)
    plus_clair = jl.sol_contre_mur({"lineaire": [0.8, 0.4, 0.2]}, {"lineaire": [1.6, 1.6, 1.6]})
    assert r == plus_clair and abs(r["rvb"][0] - 0.5) < 1e-6
    assert jl.sol_contre_mur(None, murs) is None


def test_l_image_entiere_et_l_ecart():
    image = np.full((50, 70, 3), 128, np.uint8)
    image[:10] = 255
    d = jl.mesurer_image(image)
    assert abs(d["brule"] - 20.0) < 2.0 and d["C"] < 0.5
    assert jl.ecart(jl.couleur([0.5, 0.5, 0.5]), jl.couleur([0.5, 0.5, 0.5])) == 0.0
    assert jl.ecart(jl.couleur([0.5, 0.5, 0.5]), jl.couleur([0.2, 0.2, 0.2])) > 20
    assert jl.ecart(None, jl.couleur([0.5, 0.5, 0.5])) is None
    assert axes(0.0)[0][0] == 1.0


def _vue_fabriquee(decalage=(0, 0), pale=False):
    """Une « photo » de 200 × 300 avec une fenêtre qui montre des immeubles (rayures et carrés), et le « film » de la même vue."""
    rng = np.random.default_rng(5)
    dehors = np.full((260, 360, 3), 150, np.uint8)
    for k in range(0, 360, 24):
        dehors[:, k:k + 9] = (90, 100, 120)
    for _ in range(40):
        y, x = int(rng.integers(0, 240)), int(rng.integers(0, 340))
        dehors[y:y + 12, x:x + 12] = rng.integers(40, 220, 3)
    dx, dy = decalage
    image = np.full((200, 300, 3), 235, np.uint8)
    image[40:160, 60:240] = dehors[70 - dy:190 - dy, 90 - dx:270 - dx]
    if pale:
        image[40:160, 60:240] = (0.35 * image[40:160, 60:240] + 0.65 * 255).astype(np.uint8)
    masque = np.zeros((200, 300), bool)
    masque[44:156, 64:236] = True
    return image, masque


def test_la_vue_par_les_fenetres_identique_decalee_ou_pale():
    photo, masque = _vue_fabriquee()
    pareil = jl.mesurer_dehors(photo, photo.copy(), masque)
    assert pareil["ecart_point"] < 0.5 and pareil["ressemblance"] > 0.99 and pareil["decalage_px"] == [0, 0]
    assert abs(pareil["nettete"] - 1.0) < 0.01 and pareil["vide"] == 0.0
    glisse, _ = _vue_fabriquee(decalage=(7, -4))
    d = jl.mesurer_dehors(photo, glisse, masque)
    assert d["decalage_px"] == [7, -4] and d["ressemblance_recalee"] > 0.8 and d["ressemblance"] < d["ressemblance_recalee"] - 0.3
    assert d["ecart_point"] > 5 * max(pareil["ecart_point"], 0.5)
    pale, _ = _vue_fabriquee(pale=True)
    p = jl.mesurer_dehors(photo, pale, masque)
    assert p["film"]["L"] > p["photo"]["L"] + 10 and p["ecart_couleur"] > 10 and p["nettete"] < 0.6
    assert p["decalage_px"] == [0, 0] and p["ressemblance"] > 0.9  # le même dessin, seulement délavé
    assert jl.mesurer_dehors(photo, photo, np.zeros_like(masque)) is None
    blanc = photo.copy()
    blanc[40:160, 60:240] = 255
    assert jl.mesurer_dehors(photo, blanc, masque)["vide"] > 90
