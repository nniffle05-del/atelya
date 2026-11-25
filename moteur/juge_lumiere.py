"""Le JUGE DE LA LUMIÈRE du film (point 2, 18/11/2026) : la photo du client contre l'image du FILM prise du même endroit.

Pourquoi : le film Unreal est gris et terne à côté des photos des clients (murs gris, pas de soleil, parquet moins doré). Avant
de toucher à la lumière, il faut des CHIFFRES, pris sur les images du film (jamais sur des rendus de Blender : CLAUDE.md § 0),
et les mêmes des deux côtés. Pour chaque photo et son image du film (outils/unreal/vues_photos_unreal.py) :
- les MURS : des points posés sur les murs de la pièce (moteur/blanc_des_murs.py), lus sur les deux images. Le « blanc » = les
  murs bien éclairés ; le « relief » = l'écart de clarté entre les murs les plus sombres et les plus clairs (une lumière plate
  n'en a pas) ;
- le SOL : le sol que la photo montre proprement, mis à plat, et les mêmes points du sol sur l'image du film ;
- le SOL CONTRE LE MUR : ce que le sol renvoie si le mur vaut 1 (ne dépend plus de l'exposition) ;
- l'IMAGE ENTIÈRE : clarté des sombres, du milieu et des clairs, vivacité des couleurs, part de l'image brûlée (blanc pur :
  les fenêtres, les taches de soleil).
Et, pour l'image du film seulement, la lumière DANS LA SCÈNE (avant la pellicule : la courbe des tons à l'envers) : elle sépare
ce qui vient de la lumière et des matières de ce qui vient des réglages d'image (exposition, courbe, vivacité).

`refaire_l_image` rejoue une image du film avec d'autres réglages d'image SANS relancer Unreal : une prévision, à confirmer par
un vrai rendu.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from moteur import pellicule_unreal, photographe
from moteur.blanc_des_murs import DEMI_CARRE, points_des_murs
from moteur.camera_photo import axes, camera_depuis_dict
from moteur.reconnaitre_sols import lab
from moteur.sol_a_plat import visibles_depuis
from moteur.teinte_photo import lineaire

POIDS = np.array([0.2126, 0.7152, 0.0722])
CAPTEUR_MM = 36.0
NEUTRE_C = 14.0  # un point de mur « neutre » : peu de couleur (un meuble en bois, un mur peint vif n'en sont pas)
NEUTRE_L = 30.0  # … et pas un objet noir
BRULE = 250  # blanc pur : les trois couleurs au-dessus
PIXELS_SOL_MIN = 3000  # 0,3 m² de sol propre au moins
POINTS_MURS_MIN = 12
LINEAIRE_MAX = 60.0  # un pixel brûlé du film n'a pas de lumière connue : plafonné


# ------------------------------------------------------------------------------------------------------------------------------
# Le cadrage : la caméra du film à la place de l'appareil de la photo
# ------------------------------------------------------------------------------------------------------------------------------
def cadre_du_film(d: dict) -> dict:
    """Le cadrage EXACT de la photo par la caméra du film. L'appareil de la photo regarde à l'horizontale avec l'horizon
    décalé dans l'image (les verticales restent verticales, comme le font les photographes d'annonces) ; une caméra de film
    regarde au centre de son image. Le film est donc tourné sur une image plus grande, centrée sur le point de fuite de la
    photo, puis ROGNÉ au cadre de la photo : mêmes points aux mêmes pixels, sans pencher la caméra.
    Rend {tangage, focale_mm, format [largeur, hauteur], rognage [colonne, ligne, largeur, hauteur]}."""
    c = d["camera"]
    largeur, hauteur = int(d.get("largeur", 1206)), int(d.get("hauteur", 804))
    f, u0, v0 = float(c["f"]), float(c.get("u0", largeur / 2)), float(c["v0"])
    demi_l = int(math.ceil(max(u0, largeur - u0)))
    demi_h = int(math.ceil(max(v0, hauteur - v0)))
    grand = [2 * demi_l, 2 * demi_h]
    return {"tangage": float(c.get("tangage", 0.0)), "focale_mm": round(f * CAPTEUR_MM / grand[0], 4), "format": grand,
            "rognage": [int(round(demi_l - u0)), int(round(demi_h - v0)), largeur, hauteur]}


def film_au_cadre(film: np.ndarray, d: dict, trajet: dict) -> tuple[np.ndarray, np.ndarray]:
    """L'image du film remise dans le cadre de la photo : (image, masque des pixels connus).
    - trajet « cadre : photo » (cadre_du_film) : simple rognage ;
    - ancien trajet (caméra penchée vers le centre de la photo, vues du 18/11/2026) : même place, autre direction → les deux
      images se déduisent exactement l'une de l'autre (chaque pixel de la photo est un rayon ; on lit où ce rayon tombe sur
      l'image du film) ; une bande de la photo, hors du champ du film, reste inconnue."""
    c = d["camera"]
    largeur, hauteur = int(d.get("largeur", 1206)), int(d.get("hauteur", 804))
    if trajet.get("cadre") == "photo":
        x, y, w, h = trajet["rognage"]
        image = film if film.shape[:2] == (h, w) else film[y:y + h, x:x + w]  # vue-<photo>.png est déjà rognée
        if image.shape[:2] != (hauteur, largeur):
            raise ValueError(f"PLANTÉ : rognage {trajet['rognage']} hors de l'image du film {film.shape[:2]}")
        return image.copy(), np.ones((hauteur, largeur), bool)
    cam = camera_depuis_dict(c)
    hf, wf = film.shape[:2]
    f_film = float(trajet["focale_mm"]) / CAPTEUR_MM * wf
    vue_p, droite_p, haut_p = axes(cam[3], cam[4])
    vue_f, droite_f, haut_f = axes(float(trajet["points"][0][3]), float(trajet["points"][0][4]))
    u, v = np.meshgrid(np.arange(largeur, dtype=float), np.arange(hauteur, dtype=float))
    a, b = (u - cam[6]) / cam[5], (v - cam[7]) / cam[5]
    rayon = vue_p[None, None, :] + a[..., None] * droite_p[None, None, :] - b[..., None] * haut_p[None, None, :]
    p = rayon @ vue_f
    uf = wf / 2 + f_film * (rayon @ droite_f) / p
    vf = hf / 2 - f_film * (rayon @ haut_f) / p
    valide = (p > 1e-6) & (uf >= 0) & (uf <= wf - 1) & (vf >= 0) & (vf <= hf - 1)
    image = cv2.remap(film, uf.astype(np.float32), vf.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                      borderValue=0)
    image[~valide] = 0
    return image, valide


# ------------------------------------------------------------------------------------------------------------------------------
# Les mesures (mêmes fonctions pour la photo et pour l'image du film)
# ------------------------------------------------------------------------------------------------------------------------------
def affiche(lin) -> np.ndarray:
    """Lumière linéaire 0-1 → valeurs d'écran 0-255 (sRGB)."""
    c = np.clip(np.asarray(lin, float), 0, 1)
    return 255.0 * np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def couleur(lin) -> dict:
    """Une couleur (lumière linéaire) décrite comme on la voit : valeurs d'écran et CIELAB (L clarté, a rouge, b jaune,
    C vivacité)."""
    rgb = affiche(lin)
    L, a, b = (float(x) for x in lab(rgb))
    return {"rgb": [int(round(x)) for x in rgb], "L": round(L, 1), "a": round(a, 1), "b": round(b, 1),
            "C": round(math.hypot(a, b), 1)}


def points_de_murs_vus(image: np.ndarray, cam, logement: dict, piece: dict, point_de_vue=None, valide=None) -> dict[int, np.ndarray]:
    """{n° du point de mur : sa couleur linéaire sur l'image} pour les points des murs de la pièce vus par l'appareil."""
    from moteur.camera_photo import projeter

    pts = points_des_murs(logement, piece)
    if not len(pts):
        return {}
    vue = point_de_vue or (float(cam[0]), float(cam[1]))
    visibles = visibles_depuis(pts[:, 0], pts[:, 1], vue, piece["contour"])
    h, w = image.shape[:2]
    vus = {}
    for k, ((x, y, z), ok) in enumerate(zip(pts, visibles)):
        if not ok:
            continue
        u, v, p = projeter((x, y, z), cam)
        if p <= 0.3 or not (DEMI_CARRE <= u < w - DEMI_CARRE and DEMI_CARRE <= v < h - DEMI_CARRE):
            continue
        if valide is not None and not valide[int(v) - DEMI_CARRE:int(v) + DEMI_CARRE + 1, int(u) - DEMI_CARRE:int(u) + DEMI_CARRE + 1].all():
            continue
        carre = image[int(v) - DEMI_CARRE:int(v) + DEMI_CARRE + 1, int(u) - DEMI_CARRE:int(u) + DEMI_CARRE + 1, :3]
        vus[k] = np.median(lineaire(carre.reshape(-1, 3)), axis=0)
    return vus


def mesurer_murs(points: dict[int, np.ndarray]) -> dict | None:
    """Le BLANC des murs (murs bien éclairés mais pas éblouis : clarté entre la médiane et le 9e dixième, comme
    blanc_des_murs) et leur RELIEF (clarté L des murs neutres : 1er dixième, médiane, 9e dixième). None si trop peu de mur."""
    if len(points) < POINTS_MURS_MIN:
        return None
    c = np.array(list(points.values()))
    clarte = c @ POIDS
    bas, haut = np.percentile(clarte, [50, 90])
    blanc = c[(clarte >= bas) & (clarte <= haut)].mean(axis=0)
    L = lab(affiche(c))
    neutres = L[(np.hypot(L[:, 1], L[:, 2]) < NEUTRE_C) & (L[:, 0] > NEUTRE_L)]
    d = {**couleur(blanc), "lineaire": [round(float(x), 4) for x in blanc], "points": int(len(c))}
    if len(neutres) >= POINTS_MURS_MIN:
        l10, l50, l90 = np.percentile(neutres[:, 0], [10, 50, 90])
        d.update({"L10": round(float(l10), 1), "L50": round(float(l50), 1), "L90": round(float(l90), 1),
                  "relief": round(float(l90 - l10), 1), "neutres": int(len(neutres))})
    return d


def dominante(pixels: np.ndarray) -> np.ndarray | None:
    """Les pixels proches de la couleur dominante (restes de meubles, tapis, reflets écartés) ; None s'il y en a trop peu."""
    if len(pixels) < PIXELS_SOL_MIN:
        return None
    L = lab(pixels)
    ecart = np.linalg.norm(L - np.median(L, 0), axis=1)
    return pixels[ecart <= 2.0 * max(float(np.median(ecart)), 1.0)]


def mesurer_sol(pixels: np.ndarray | None) -> dict | None:
    """La couleur du sol (pixels 0-255 du sol mis à plat, déjà triés par `dominante`)."""
    if pixels is None or not len(pixels):
        return None
    lin = np.median(lineaire(pixels), axis=0)
    return {**couleur(lin), "lineaire": [round(float(x), 4) for x in lin], "pixels": int(len(pixels))}


def sol_contre_mur(sol: dict | None, murs: dict | None) -> dict | None:
    """Ce que le sol renvoie si le blanc des murs vaut 1 : par couleur, et en clarté. Ne dépend pas de l'exposition."""
    if not sol or not murs:
        return None
    s, m = np.array(sol["lineaire"]), np.maximum(np.array(murs["lineaire"]), 1e-6)
    return {"rvb": [round(float(x), 3) for x in s / m], "clarte": round(float((s @ POIDS) / (m @ POIDS)), 3)}


def mesurer_image(image: np.ndarray, valide=None) -> dict:
    """L'image entière : clarté des sombres (5e centième), du milieu, des clairs (95e), vivacité moyenne des couleurs, part de
    l'image brûlée (blanc pur)."""
    px = image[valide] if valide is not None else image.reshape(-1, 3)
    px = px[::7]
    L = lab(px)
    return {"L5": round(float(np.percentile(L[:, 0], 5)), 1), "L50": round(float(np.percentile(L[:, 0], 50)), 1),
            "L95": round(float(np.percentile(L[:, 0], 95)), 1), "C": round(float(np.hypot(L[:, 1], L[:, 2]).mean()), 1),
            "brule": round(100.0 * float((px.min(axis=1) >= BRULE).mean()), 1)}


def ecart(a: dict | None, b: dict | None) -> float | None:
    """L'écart de couleur entre deux couleurs décrites par `couleur` (distance en CIELAB : 2 = à peine visible, 10 = net)."""
    if not a or not b:
        return None
    return round(float(np.linalg.norm([a[k] - b[k] for k in "Lab"])), 1)


# ------------------------------------------------------------------------------------------------------------------------------
# La lumière dans la scène, et l'image rejouée avec d'autres réglages
# ------------------------------------------------------------------------------------------------------------------------------
def scene_du_film(rgb, pellicule=None, couleurs=None, tours: int = 12) -> np.ndarray:
    """La lumière DANS LA SCÈNE (après exposition et balance, avant la pellicule) qui donne ces valeurs d'écran : le chemin
    d'Unreal à l'envers. La courbe des gris s'inverse couleur par couleur ; les mélanges de couleurs de la pellicule
    (désaturation, correction des bleus) sont rattrapés par quelques tours de correction."""
    pellicule = pellicule or photographe.PELLICULE
    couleurs = couleurs or photographe.PELLICULE_COULEURS
    forme = np.shape(rgb)
    cible = np.clip(np.asarray(rgb, float).reshape(-1, 3) / 255.0, 1e-4, 0.9995)
    x = np.minimum(photographe.lineaire_affiche(cible, pellicule), LINEAIRE_MAX)
    lin_cible = x.copy()
    for _ in range(tours):
        y = np.clip(pellicule_unreal.affiche(x, pellicule, couleurs["saturation"], couleurs["expand_gamut"],
                                             couleurs["blue_correction"]), 1e-4, 0.9995)
        x = np.clip(x * lin_cible / np.maximum(photographe.lineaire_affiche(y, pellicule), 1e-9), 1e-7, LINEAIRE_MAX)
    return x.reshape(forme)


def refaire_l_image(rgb: np.ndarray, crans: float = 0.0, pellicule=None, couleurs=None, gain=(1.0, 1.0, 1.0)) -> np.ndarray:
    """Une image du film (0-255, RGB) rejouée avec `crans` d'exposition en plus, une autre pellicule (courbe des tons), d'autres
    réglages de couleurs, un autre gain : une PRÉVISION sans relancer Unreal (les pixels brûlés restent brûlés ; les limites
    de Lumen, qui dépendent de l'exposition, ne sont pas rejouées)."""
    scene = scene_du_film(rgb).reshape(-1, 3) * (2.0 ** crans) * np.asarray(gain, float)
    c = couleurs or photographe.PELLICULE_COULEURS
    y = pellicule_unreal.affiche(scene, pellicule or photographe.PELLICULE, c["saturation"], c["expand_gamut"], c["blue_correction"])
    sortie = np.clip(np.round(255.0 * y), 0, 255).astype(np.uint8).reshape(rgb.shape)
    sortie[rgb.min(axis=-1) >= 254] = 255
    return sortie


# ------------------------------------------------------------------------------------------------------------------------------
# La VUE PAR LES FENÊTRES : la photo contre le film, sur les mêmes pixels (18/11/2026, NT : « pas fidèle aux photos à 100 % »)
# ------------------------------------------------------------------------------------------------------------------------------
DEHORS_PIXELS_MIN = 1500  # en dessous, la photo ne voit presque pas dehors : rien à juger
DEHORS_CHERCHE_PX = 40  # décalage cherché entre la vue de la photo et celle du film, en pixels de la photo, de chaque côté


def _lab_image(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def masque_du_dehors(cam, taille: tuple[int, int], logement: dict, caches=(), marge_px: int = 4) -> np.ndarray:
    """Les pixels (H, L, bool) par où l'appareil de la photo voit DEHORS d'après le plan (moteur/vue_dehors.masque_fenetres :
    sans les montants, les balcons, les meubles `caches`, la marque de l'annonce), rétrécis de `marge_px` (calage approché)."""
    from moteur import vue_dehors

    vue, _ = vue_dehors.masque_fenetres(cam, taille, vue_dehors.ouvertures_vitrees(logement), vue_dehors.murs_et_trous(logement),
                                        caches, balcons=logement.get("balcons"))
    if marge_px > 0:
        vue = cv2.erode(vue, np.ones((2 * marge_px + 1, 2 * marge_px + 1), np.uint8))
    # les MEUBLES DE LA MAQUETTE qui passent devant la fenêtre dans le film (les meubles de la photo sont dans `caches`) : la
    # boîte de chacun, vue par l'appareil, est retirée ; sans cela une chaise sombre du film comptait comme du « dehors »
    from moteur.camera_photo import projeter
    from moteur.collisions import hauteurs, rect_du_meuble

    for meuble in logement.get("meubles") or []:
        try:
            r, (z0, z1) = rect_du_meuble(meuble, 0.05), hauteurs(meuble)
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        coins = [projeter([*(r.c + i * r.h1 * r.e1 + j * r.h2 * r.e2), z], cam) for i in (-1, 1) for j in (-1, 1) for z in (z0, z1)]
        if any(prof <= 0.05 for _, _, prof in coins):
            continue  # boîte en partie derrière l'appareil : pas devant une fenêtre vue de face
        pts = np.array([[u, v] for u, v, _ in coins], np.float32)
        if np.abs(pts).max() > 20000:
            continue
        cv2.fillConvexPoly(vue, cv2.convexHull(pts).astype(np.int32), 0)
    return vue > 0


def mesurer_dehors(photo: np.ndarray, film: np.ndarray, masque: np.ndarray, valide=None, cherche_px: int = DEHORS_CHERCHE_PX) -> dict | None:
    """Ce qu'on voit PAR LES FENÊTRES, photo contre film (deux images RGB de même taille, même cadre), sur `masque` :
    - « photo », « film » : la couleur du dehors (médiane ; L clarté, C vivacité), ses « sombres » et ses « clairs » (10e et 90e
      centièmes de clarté) et leur écart, le « contraste » (un voile blanc sur la vue relève les sombres : contraste perdu) ;
      « ecart_couleur » entre les deux médianes ;
    - « ecart_point » : l'écart de couleur moyen POINT PAR POINT (images adoucies de 3 pixels) : 0 = la même vue au même
      endroit ; il compte à la fois la couleur, le dessin et sa place ;
    - « ressemblance » : le DESSIN de la vue (immeubles, fenêtres d'en face ; les grandes plages de clarté sont retirées),
      de 0 (rien de commun) à 1 (le même), sans bouger le film ; « ressemblance_recalee » et « decalage_px » : la même après
      avoir fait glisser le film jusqu'à la meilleure place (le glissement trouvé, en pixels de la photo : → droite, ↓ bas) ;
    - « nettete » : finesse du dessin du film rapportée à celle de la photo (1 = aussi net) ;
    - « vide » : part du dehors où la photo montre quelque chose et où le film est blanc (%).
    None si la photo ne voit presque pas dehors."""
    m = masque.astype(bool)
    if valide is not None:
        m &= valide
    if int(m.sum()) < DEHORS_PIXELS_MIN:
        return None
    lp, lf = _lab_image(photo), _lab_image(film)

    def mediane(lab_px):
        L, a, b = (float(x) for x in np.median(lab_px, axis=0))
        sombres, clairs = (float(x) for x in np.percentile(lab_px[:, 0], [10, 90]))
        return {"L": round(L, 1), "a": round(a, 1), "b": round(b, 1), "C": round(math.hypot(a, b), 1),
                "sombres": round(sombres, 1), "clairs": round(clairs, 1), "contraste": round(clairs - sombres, 1)}

    p, f = mediane(lp[m]), mediane(lf[m])
    doux = lambda im: cv2.GaussianBlur(im, (0, 0), 3.0)
    point = float(np.linalg.norm(doux(lp)[m] - doux(lf)[m], axis=1).mean())
    # le dessin : la clarté sans ses grandes plages
    detail = lambda L: (L - cv2.GaussianBlur(L, (0, 0), 10.0)).astype(np.float32)
    dp, df = detail(lp[..., 0]), detail(lf[..., 0])
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    c = int(cherche_px)
    gabarit, poids = dp[y0:y1, x0:x1].copy(), m[y0:y1, x0:x1].astype(np.float32)
    gabarit *= poids
    champ = cv2.copyMakeBorder(df, c, c, c, c, cv2.BORDER_REFLECT)[y0:y1 + 2 * c, x0:x1 + 2 * c]
    carte = cv2.matchTemplate(champ, gabarit, cv2.TM_CCORR_NORMED, mask=poids)
    carte = np.nan_to_num(carte, nan=0.0, posinf=0.0, neginf=0.0)
    iy, ix = np.unravel_index(int(np.argmax(carte)), carte.shape)
    force = lambda L: float(np.abs(cv2.Laplacian(cv2.GaussianBlur(L, (0, 0), 1.0), cv2.CV_32F))[m].mean())
    vide = (lf[..., 0] > 96.0) & (np.hypot(lf[..., 1], lf[..., 2]) < 4.0) & (lp[..., 0] < 90.0)
    return {"pixels": int(m.sum()), "photo": p, "film": f,
            "ecart_couleur": round(float(np.linalg.norm([p[k] - f[k] for k in "Lab"])), 1), "ecart_point": round(point, 1),
            "ressemblance": round(float(carte[c, c]), 3), "ressemblance_recalee": round(float(carte[iy, ix]), 3),
            "decalage_px": [int(ix - c), int(iy - c)],
            "nettete": round(force(lf[..., 0]) / max(force(lp[..., 0]), 1e-6), 2),
            "vide": round(100.0 * float(vide[m].mean()), 1)}
