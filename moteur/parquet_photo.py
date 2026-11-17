"""Le parquet MESURÉ sur les photos du client : largeur et longueur des lames, nuances d'une lame à l'autre, joints (18/11/2026).

Pourquoi : NT, devant les maquettes : « tu as tout mis parquet à l'anglaise, alors que je veux que le sens soit le même, et aussi
le parquet ». Un catalogue ne donnera jamais « le même parquet » : Atelya mesure donc CE parquet-là sur les photos, puis le
dessine sur mesure (moteur/parquet_sur_mesure.py).

Comment : pour chaque photo, le sol de la pièce est « mis à plat » (vu de dessus) dans un repère TOURNÉ dans le sens des lames
(moteur/sens_des_lames.py) : sur cette image, les lames sont des bandes horizontales. Finement : 3 mm de sol par pixel, et
seulement là où la photo est assez nette (une lame de 7 cm doit faire au moins 7 pixels sur la photo). Puis, par petites
fenêtres (la place de l'appareil n'est connue qu'à quelques degrés près : chaque fenêtre est redressée à part) :

- LARGEUR des lames : les longs joints sont des lignes sombres régulièrement espacées ; leur écart est la période du profil
  « en travers » (sa première ressemblance avec lui-même décalé) ;
- NUANCES : la clarté moyenne de chaque rang de lames, comparée à celle du rang voisin AU MÊME ENDROIT (même lumière, même
  reflet : seule la différence de bois reste) ;
- LONGUEUR des lames : le long d'un rang, la différence avec le rang voisin reste la même tant qu'aucune des deux lames ne
  finit. Plus les lames sont courtes, plus vite cette différence « oublie » sa valeur : la pente de cet oubli donne la longueur
  moyenne des lames, sans avoir à repérer un par un des bouts de lames de 2 pixels ;
- JOINTS : la profondeur du creux sombre entre deux rangs, comptée en « millimètres de noir » (un joint de 1 mm tout noir ou
  un joint de 2 mm gris foncé se voient pareil à cette distance).

Rien n'est appris ni réglé sur un logement : ce sont des mesures. Chaque mesure dit sur combien de sol elle repose ; trop peu,
elle n'est pas rendue (None) et le dessin prend une valeur SUPPOSÉE, dite comme telle.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

VERSION = "0.1.0"
RESOLUTION_M = 0.003  # 3 mm de sol par pixel de l'image à plat
FINESSE_MIN = 1.0  # pixels de la photo par cm de sol : en dessous, une lame de 7 cm fait moins de 7 pixels
FENETRE_LONG_M = 0.60  # fenêtre de mesure de la largeur : 60 cm le long des lames…
FENETRE_TRAVERS_M = 0.90  # … sur 90 cm en travers (5 à 12 lames)
PLEIN_MIN = 0.40  # part de la fenêtre qui doit être du parquet bien vu (le sol se voit souvent en bande étroite, de biais)
LIGNE_MIN_M = 0.18  # chaque ligne du profil doit reposer sur au moins 18 cm de parquet
PENCHES = tuple(np.arange(-10.0, 10.01, 1.0))  # degrés : chaque fenêtre est redressée (la place de l'appareil est approchée)
LARGEUR_MIN_M, LARGEUR_MAX_M = 0.045, 0.30
RESSEMBLANCE_MIN = 0.22  # hauteur du premier pic du profil comparé à lui-même décalé (0 à 1)
FENETRES_MIN = 6  # il faut au moins 6 fenêtres d'accord pour dire une largeur (elles se recouvrent : ~3 endroits distincts)
BANDE_LONG_M = 1.50  # bande de mesure des nuances et de la longueur : 1,5 m le long des lames
RANGS_M_MIN = 12.0  # il faut au moins 12 m de rangs comparés pour dire une longueur de lame
LONGUEUR_MIN_M, LONGUEUR_MAX_M = 0.25, 2.5
BRUIT_CHALEUR = 0.04  # ce que la mesure de « chaleur » rend sur un parquet sans aucune nuance de couleur (grain, bruit de la photo)
CHALEUR_MAX = 0.06  # le bleu d'un bois orangé est faible et bruité sur une photo d'annonce : la nuance de couleur est plafonnée
DECALAGE_BRUIT_M = 0.03  # deux points d'un rang à 3 cm l'un de l'autre : même lame, grain du bois différent


def sol_dans_le_sens(photo_rgb: np.ndarray, cam, contour, sens_deg: float, pas_du_sol: np.ndarray | None = None,
                     point_de_vue=None, resolution: float = RESOLUTION_M, finesse_min: float = FINESSE_MIN, garder=None):
    """Le sol d'une pièce vu de dessus, tourné pour que les lames (sens_deg, repère du logement) soient HORIZONTALES.
    Rend (image RGB uint8, masque des points bien vus et pas sur un meuble). Colonne = le long des lames, ligne = en travers.
    garder : fonction (X, Y) → masque des points du sol à garder (la part de la pièce qui porte CE sol, sans ses zones)."""
    from moteur.sol_a_plat import dans_polygone, projeter_sol, visibles_depuis

    c = np.asarray(contour, float)
    a = math.radians(sens_deg)
    le_long, travers = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    s, t = c @ le_long, c @ travers
    S, T = np.meshgrid(np.arange(s.min(), s.max(), resolution), np.arange(t.max(), t.min(), -resolution))
    X, Y = S * le_long[0] + T * travers[0], S * le_long[1] + T * travers[1]
    with np.errstate(invalid="ignore"):
        u, v, p, finesse = projeter_sol(X, Y, cam)
        h, w = photo_rgb.shape[:2]
        vu = np.isfinite(u) & (p > 0.3) & (u >= 1) & (u <= w - 2) & (v >= 1) & (v <= h - 2) & (finesse >= finesse_min)
    if not vu.any():
        return np.zeros((1, 1, 3), np.uint8), np.zeros((1, 1), bool)
    # recadré sur ce que la photo voit assez finement (souvent un dixième de la pièce) ; les contrôles coûteux (dans la pièce,
    # pas caché par un mur, pas sur un meuble) ne se font que sur ces points-là
    lignes, colonnes = np.nonzero(vu.any(1))[0], np.nonzero(vu.any(0))[0]
    cadre = (slice(lignes[0], lignes[-1] + 1), slice(colonnes[0], colonnes[-1] + 1))
    X, Y, u, v, vu = X[cadre], Y[cadre], u[cadre], v[cadre], vu[cadre]
    ou = np.nonzero(vu)
    x, y = X[ou], Y[ou]
    garde = dans_polygone(x, y, c)
    garde[garde] = visibles_depuis(x[garde], y[garde], point_de_vue or (float(cam[0]), float(cam[1])), c)
    if garder is not None:
        garde &= garder(x, y)
    if pas_du_sol is not None:
        garde &= ~pas_du_sol[np.clip(np.round(v[ou]).astype(int), 0, h - 1), np.clip(np.round(u[ou]).astype(int), 0, w - 1)]
    vu = np.zeros(vu.shape, bool)
    vu[ou] = garde
    image = cv2.remap(photo_rgb, np.where(vu, u, -1).astype(np.float32), np.where(vu, v, -1).astype(np.float32), cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    image[~vu] = 0
    return image, vu


def bois_propre(image: np.ndarray, vu: np.ndarray) -> np.ndarray:
    """Les points qui sont du PARQUET bien éclairé : couleur de bois (un peu orangée), ni brûlée par le reflet d'une fenêtre,
    ni dans l'ombre profonde. Écarte tapis, linge, pieds de meubles clairs, logos blancs des annonces."""
    L = _lab_des_points_vus(image, vu)
    ok = vu & (L[..., 1] > 3) & (L[..., 2] > 10) & (L[..., 0] > 22) & (L[..., 0] < 86)
    if ok.sum() < 500:
        return ok
    # le reflet d'une fenêtre délave le bois (moins de jaune) : on garde ce qui est proche de la couleur dominante
    b = L[..., 2][ok]
    ok &= L[..., 2] > 0.55 * float(np.median(b))
    ok = cv2.erode(ok.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0  # pas le bord d'un meuble ou d'un tapis
    return ok


def bois_vu(image: np.ndarray, vu: np.ndarray) -> np.ndarray:
    """Les points qui sont du parquet, MÊME délavé par le reflet d'une fenêtre : assez pour compter les joints (la largeur des
    lames), pas pour mesurer une couleur. Écarte ce qui est gris ou bleu (tapis, carrelage, pieds de meubles) et le noir."""
    L = _lab_des_points_vus(image, vu)
    return vu & (L[..., 1] > 0) & (L[..., 2] > 5) & (L[..., 0] > 22)


def _lab_des_points_vus(image: np.ndarray, vu: np.ndarray) -> np.ndarray:
    """La couleur (clarté, rouge, jaune : CIELAB) des points vus ; zéro ailleurs (calculée seulement là où il le faut)."""
    from moteur.reconnaitre_sols import lab

    L = np.zeros(image.shape, np.float32)
    if vu.any():
        L[vu] = lab(image[vu])
    return L


def _lumiere(image: np.ndarray) -> np.ndarray:
    """Valeurs d'image (0-255) → lumière (0-1), par une table (même formule que moteur.teinte_photo.lineaire)."""
    from moteur.teinte_photo import lineaire

    return lineaire(np.arange(256, dtype=np.uint8)).astype(np.float32)[image]


def _clarte(image: np.ndarray) -> np.ndarray:
    """Le logarithme de la lumière renvoyée (une différence de 0,10 = 10 % plus clair ou plus foncé)."""
    lum = _lumiere(image) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return np.log(np.maximum(lum, 1e-3)).astype(np.float32)


def _pencher(tableau: np.ndarray, degres: float, remplissage=0.0) -> np.ndarray:
    """La fenêtre cisaillée : chaque colonne glisse en travers, pour remettre à l'horizontale des joints penchés de `degres`."""
    h, w = tableau.shape[:2]
    k = math.tan(math.radians(degres))
    m = np.float32([[1, 0, 0], [k, 1, -k * w / 2]])
    return cv2.warpAffine(tableau, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=remplissage)


def _profil(clarte: np.ndarray, ok: np.ndarray):
    """Le profil en travers d'une fenêtre : pour chaque ligne, à quel point elle est plus SOMBRE que ses voisines (un long
    joint), moyenné le long des lames. Rend (profil, clarté moyenne de chaque ligne), NaN là où la ligne est trop peu vue."""
    poids = ok.astype(np.float32)
    n = poids.sum(1)
    moyenne = np.where(n >= 0.5 * ok.shape[1], (clarte * poids).sum(1) / np.maximum(n, 1), np.nan)
    lisse = moyenne.copy()
    creux = np.full_like(moyenne, np.nan)
    creux[2:-2] = np.minimum(lisse[:-4], lisse[4:]) - lisse[2:-2]  # > 0 : ligne plus sombre que 6 mm au-dessus et au-dessous
    return creux, moyenne


def _periode(profil: np.ndarray, resolution: float, mini: float | None = None, maxi: float | None = None):
    """La période du profil (m) et sa force (0 à 1) : premier pic de la ressemblance du profil avec lui-même décalé."""
    bon = np.isfinite(profil)
    if bon.sum() < 0.85 * len(profil):
        return None
    p = np.maximum(np.where(bon, profil, 0.0), 0.0)  # seuls les creux comptent (une lame plus claire n'est pas un joint)
    p = np.where(bon, p - p[bon].mean(), 0.0)
    n = len(p)
    d_min, d_max = int((mini or LARGEUR_MIN_M) / resolution), min(int((maxi or LARGEUR_MAX_M) / resolution), n // 2)
    energie = float((p * p).sum())
    if energie <= 1e-12 or d_max <= d_min + 2:
        return None
    auto = np.array([float((p[:n - d] * p[d:]).sum()) / energie * n / (n - d) for d in range(d_max + 1)])
    pics = [d for d in range(max(d_min, 1), d_max) if auto[d] >= auto[d - 1] and auto[d] > auto[d + 1] and auto[d] >= RESSEMBLANCE_MIN]
    if not pics:
        return None
    haut = max(auto[d] for d in pics)
    d = next(d for d in pics if auto[d] >= 0.7 * haut)  # le PREMIER pic franc : la période, pas son double
    # … et pas le double non plus quand un joint sur deux est discret (parquet aux joints serrés, peu de nuances : le pic de la
    # vraie période passe sous le seuil et celui du double est retenu ; vu par la boucle de contrôle le 18/11/2026). Si la
    # moitié de la période est elle aussi un pic, même faible, c'est elle la largeur des lames. (Pour de vraies lames de
    # largeur d, la ressemblance à d / 2 est nulle ou négative : aucun risque de couper une vraie largeur en deux.)
    m = d // 2
    if m - 2 >= max(d_min, 1):
        m = max(range(m - 2, m + 3), key=lambda k: auto[k])
        if auto[m] >= 0.5 * auto[d] and auto[m] >= auto[m - 1] and auto[m] >= auto[m + 1]:
            d = m
    # position fine du pic (parabole sur trois points)
    y0, y1, y2 = auto[d - 1], auto[d], auto[d + 1]
    fin = d + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if abs(y0 - 2 * y1 + y2) > 1e-9 else float(d)
    return fin * resolution, float(auto[d])


def _redresser(clarte: np.ndarray, ok: np.ndarray, resolution: float):
    """La fenêtre redressée au mieux : le penché qui rend le profil en travers le plus NET (joints bien alignés).
    Rend (penché en degrés, clarté redressée, masque redressé, profil, moyennes) ou None."""
    meilleur = None
    for degres in PENCHES:
        c = _pencher(clarte, degres)
        m = _pencher(ok.astype(np.float32), degres) > 0.99
        profil, moyenne = _profil_partiel(c, m, int(LIGNE_MIN_M / resolution))
        bon = np.isfinite(profil)
        if bon.sum() < 0.85 * len(profil):
            continue
        nettete = float(np.maximum(profil[bon], 0).var())
        if meilleur is None or nettete > meilleur[0]:
            meilleur = (nettete, degres, c, m, profil, moyenne)
    return meilleur[1:] if meilleur else None


def largeurs_par_fenetre(image: np.ndarray, propre: np.ndarray, resolution: float = RESOLUTION_M, travers_m: float = FENETRE_TRAVERS_M,
                         mini: float | None = None, maxi: float | None = None) -> list[dict]:
    """La largeur des lames mesurée dans chaque fenêtre assez pleine : [{"largeur_m", "force", "penche", "ligne", "colonne"}].
    travers_m, mini, maxi : pour mesurer autre chose que des lames (les RANGS d'un point de Hongrie, larges de 30 à 50 cm)."""
    clarte = _clarte(image)
    fl, ft = int(FENETRE_LONG_M / resolution), int(travers_m / resolution)
    sortie = []
    h, w = propre.shape
    plein = cv2.boxFilter(propre.astype(np.float32), -1, (fl, ft), anchor=(0, 0), borderType=cv2.BORDER_CONSTANT)
    # fenêtres serrées (tous les 18 cm en travers, 20 cm le long) : la mesure ne doit pas dépendre de l'endroit où tombe la grille
    for ligne in range(0, h - ft + 1, max(1, ft // 5)):
        for colonne in range(0, w - fl + 1, max(1, fl // 3)):
            if plein[ligne, colonne] < PLEIN_MIN:
                continue
            r = _redresser(clarte[ligne:ligne + ft, colonne:colonne + fl], propre[ligne:ligne + ft, colonne:colonne + fl], resolution)
            if r is None:
                continue
            penche, _, _, profil, _ = r
            periode = _periode(profil, resolution, mini, maxi)
            if periode is None:
                continue
            sortie.append({"largeur_m": periode[0], "force": periode[1], "penche": float(penche), "ligne": ligne, "colonne": colonne})
    return sortie


def largeur_retenue(fenetres: list[dict]) -> dict | None:
    """La largeur des lames d'après les fenêtres de TOUTES les photos d'un même parquet : la valeur la plus souvent mesurée
    (une fenêtre posée sur une ombre ou un reflet donne n'importe quoi ; les bonnes fenêtres sont d'accord entre elles).
    {"largeur_m", "fenetres" (d'accord à 12 % près), "sur" (toutes), "accord"} ; None s'il y en a trop peu."""
    if len(fenetres) < FENETRES_MIN:
        return None
    valeurs = np.array([f["largeur_m"] for f in fenetres])
    poids = np.array([f["force"] for f in fenetres])
    # la valeur autour de laquelle le plus de poids se rassemble (à 12 % près)
    notes = [float(poids[np.abs(valeurs / v - 1.0) <= 0.12].sum()) for v in valeurs]
    centre = valeurs[int(np.argmax(notes))]
    autour = np.abs(valeurs / centre - 1.0) <= 0.12
    if autour.sum() < FENETRES_MIN:
        return None
    ordre = np.argsort(valeurs[autour])
    cumul = np.cumsum(poids[autour][ordre])
    largeur = float(valeurs[autour][ordre][int(np.searchsorted(cumul, cumul[-1] / 2))])
    return {"largeur_m": round(largeur, 4), "fenetres": int(autour.sum()), "sur": int(len(fenetres)),
            "accord": round(float(poids[autour].sum() / poids.sum()), 2)}


def _rangs(profil: np.ndarray, largeur_px: float):
    """Les lignes des longs joints d'une fenêtre redressée, sachant la largeur des lames : le peigne régulier qui tombe le
    mieux sur les creux du profil. Rend la liste des lignes (float)."""
    p = np.where(np.isfinite(profil), np.maximum(profil, 0.0), 0.0)
    meilleur, depart = -1.0, 0.0
    for d in np.arange(0.0, largeur_px, 0.5):
        lignes = np.arange(d, len(p) - 1, largeur_px)
        note = float(np.interp(lignes, np.arange(len(p)), p).sum())
        if note > meilleur:
            meilleur, depart = note, d
    return np.arange(depart, len(p) - 1, largeur_px)


def rangs_par_bande(image: np.ndarray, propre: np.ndarray, largeur_m: float, resolution: float = RESOLUTION_M) -> list[dict]:
    """Pour chaque bande de sol assez pleine (1,5 m le long des lames) : la clarté de chaque RANG de lames le long de la bande.
    [{"rangs": tableau (nombre de rangs, colonnes) de clartés (NaN = pas vu), "chaleur": idem pour le rouge contre le bleu,
      "creux_mm": millimètres de noir d'un long joint, "ligne", "colonne", "penche", "joints": lignes des joints}]."""
    clarte = _clarte(image)
    lin = _lumiere(image)
    chaleur = (np.log(np.maximum(lin[..., 0], 1e-3)) - np.log(np.maximum(lin[..., 2], 1e-3))).astype(np.float32)
    largeur_px = largeur_m / resolution
    fl = int(BANDE_LONG_M / resolution)
    ft = int(max(FENETRE_TRAVERS_M, 6 * largeur_m) / resolution)
    h, w = propre.shape
    fl, ft = min(fl, w), min(ft, h)
    sortie = []
    plein = cv2.boxFilter(propre.astype(np.float32), -1, (fl, ft), anchor=(0, 0), borderType=cv2.BORDER_CONSTANT)
    for ligne in range(0, h - ft + 1, max(1, ft // 3)):
        for colonne in range(0, w - fl + 1, max(1, fl // 3)):
            if plein[ligne, colonne] < 0.55:
                continue
            zone = (slice(ligne, ligne + ft), slice(colonne, colonne + fl))
            r = _redresser_bande(clarte[zone], propre[zone])
            if r is None:
                continue
            penche, c, m, profil, moyenne = r
            ch = _pencher(chaleur[zone], penche)
            joints = _rangs(profil, largeur_px)
            if len(joints) < 4:
                continue
            marge = 0.22 * largeur_px  # le cœur de la lame seulement : ni le joint, ni la lame d'à côté si le peigne glisse
            rangs, chaleurs = [], []
            for haut, bas in zip(joints[:-1], joints[1:]):
                l0, l1 = int(math.ceil(haut + marge)), int(math.floor(bas - marge)) + 1
                if l1 - l0 < 2:
                    continue
                poids = m[l0:l1].astype(np.float32)
                n = poids.sum(0)
                vu = n >= 0.6 * (l1 - l0)
                rangs.append(np.where(vu, (c[l0:l1] * poids).sum(0) / np.maximum(n, 1), np.nan))
                chaleurs.append(np.where(vu, (ch[l0:l1] * poids).sum(0) / np.maximum(n, 1), np.nan))
            if len(rangs) < 3:
                continue
            # le creux d'un long joint : ce qu'il manque de lumière autour de la ligne du joint, en millimètres de noir
            creux = []
            for j in joints[1:-1]:
                # le joint est cherché à 2 pixels près ; de part et d'autre (à 4 pixels), le bois des deux lames sert de fond
                l0, l1 = int(round(j)) - 6, int(round(j)) + 7
                if l0 < 0 or l1 > len(moyenne) or not np.isfinite(moyenne[l0:l1]).all():
                    continue
                lumiere = np.exp(moyenne[l0:l1])
                c = 4 + int(np.argmin(lumiere[4:9]))  # le fond du joint, dans la fenêtre de 13 lignes
                fond = np.interp(np.arange(c - 2, c + 3), [c - 4, c + 4], [lumiere[c - 4], lumiere[c + 4]])
                creux.append(float(np.maximum(1.0 - lumiere[c - 2:c + 3] / np.maximum(fond, 1e-6), 0.0).sum()) * resolution * 1000)
            # la MOYENNE des joints de la bande (chacun plafonné à 4 mm : au-delà, c'est le bord d'une ombre ou d'un meuble) : dans
            # un vieux parquet, quelques joints sont ouverts et la plupart serrés ; c'est leur moyenne que l'œil retient
            sortie.append({"rangs": np.array(rangs), "chaleur": np.array(chaleurs), "creux_mm": float(np.mean(np.minimum(creux, 4.0))) if creux else None,
                           "ligne": ligne, "colonne": colonne, "penche": float(penche), "joints": joints})
    return sortie


def _redresser_bande(clarte: np.ndarray, ok: np.ndarray):
    """Comme _redresser, pour une bande longue et pas forcément pleine."""
    meilleur = None
    for degres in PENCHES:
        c = _pencher(clarte, degres)
        m = _pencher(ok.astype(np.float32), degres) > 0.99
        profil, moyenne = _profil_partiel(c, m)
        bon = np.isfinite(profil)
        if bon.sum() < 0.6 * len(profil):
            continue
        nettete = float(np.maximum(profil[bon], 0).var())
        if meilleur is None or nettete > meilleur[0]:
            meilleur = (nettete, degres, c, m, profil, moyenne)
    return meilleur[1:] if meilleur else None


def _profil_partiel(clarte: np.ndarray, ok: np.ndarray, colonnes_min: int | None = None):
    """Le profil en travers d'une bande à moitié vue : chaque ligne est comparée à ses voisines SUR LES MÊMES COLONNES."""
    poids = ok.astype(np.float32)
    c = clarte * poids
    creux_px = np.zeros_like(clarte)
    commun = poids[2:-2] * poids[:-4] * poids[4:]
    creux_px[2:-2] = (np.minimum(clarte[:-4], clarte[4:]) - clarte[2:-2]) * commun
    n = np.zeros(len(clarte), np.float32)
    n[2:-2] = commun.sum(1)
    mini = 0.3 * ok.shape[1] if colonnes_min is None else colonnes_min
    profil = np.where(n >= mini, creux_px.sum(1) / np.maximum(n, 1), np.nan)
    np_ = poids.sum(1)
    moyenne = np.where(np_ >= mini, c.sum(1) / np.maximum(np_, 1), np.nan)
    return profil, moyenne


def nuances_et_longueur(bandes: list[dict], resolution: float = RESOLUTION_M) -> dict | None:
    """Des rangs de plusieurs bandes (et de plusieurs photos) : les NUANCES d'une lame à l'autre et la LONGUEUR moyenne des
    lames. On compare chaque rang à son voisin au même endroit (D = clarté du rang − clarté du rang d'à côté) :
    - nuance : l'écart type de D, divisé par racine de 2 (deux lames y contribuent), en ne comptant que ce qui tient sur 3 cm
      (le grain fin du bois et le bruit de la photo ne sont pas une nuance de lame) ;
    - longueur : D(s) × D(s + d) vaut en moyenne nuance² × (part des couples de points restés sur les mêmes lames), et cette
      part décroît comme 1 − d / longueur moyenne : la pente donne la longueur.
    {"nuance" (0,08 = 8 %), "chaleur", "longueur_m" ou None, "rangs_m" (m de rangs comparés), "creux_mm"} ; None sans rang."""
    pas = max(1, int(round(0.03 / resolution)))  # tous les 3 cm
    decalages = np.arange(1, int(0.75 / (pas * resolution)) + 1)  # de 3 cm à 75 cm
    produits = np.zeros(len(decalages) + 1)
    comptes = np.zeros(len(decalages) + 1)
    produits_ch, comptes_ch = np.zeros(2), np.zeros(2)
    metres = 0.0
    creux = [b["creux_mm"] for b in bandes if b.get("creux_mm") is not None]
    for b in bandes:
        for cle, (pr, co) in (("rangs", (produits, comptes)), ("chaleur", (produits_ch, comptes_ch))):
            r = b[cle]
            # moyenne par pas de 3 cm le long des lames (le grain fin s'efface)
            n = r.shape[1] // pas
            if n < 4:
                continue
            blocs = r[:, :n * pas].reshape(r.shape[0], n, pas)
            vus = np.isfinite(blocs).sum(2)
            somme = np.where(np.isfinite(blocs), blocs, 0.0).sum(2)
            valeurs = np.where(vus >= max(1, pas // 2), somme / np.maximum(vus, 1), np.nan)
            D = valeurs[:-1] - valeurs[1:]  # rang contre rang voisin, au même endroit
            ok = np.isfinite(D)
            if D.shape[0] >= 4:
                # la lumière qui change en travers des lames (on s'éloigne de la fenêtre) décale TOUS les couples de rangs du
                # même endroit de la même façon : retirée par leur médiane, endroit par endroit
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    commun = np.nanmedian(D, axis=0, keepdims=True)
                D = D - np.where(np.isfinite(commun), commun, 0.0)
            D0 = np.where(ok, D, 0.0)
            if cle == "rangs":
                metres += float(ok.sum()) * pas * resolution
            for k in range(len(pr)):
                if k >= D.shape[1]:
                    break
                a, bb = (D0, D0) if k == 0 else (D0[:, :-k], D0[:, k:])
                ensemble = ok if k == 0 else ok[:, :-k] & ok[:, k:]
                pr[k] += float((a * bb)[ensemble].sum())
                co[k] += float(ensemble.sum())
    if comptes[1] < 50:
        return None
    courbe = produits / np.maximum(comptes, 1)  # courbe[k] : moyenne de D(s) D(s + k pas)
    variance = max(float(courbe[1]), 0.0)  # à 3 cm : le bruit de la photo ne se ressemble plus, la nuance des lames oui
    sortie = {"nuance": round(math.sqrt(variance / 2), 4), "rangs_m": round(metres, 1),
              "creux_mm": round(float(np.mean(creux)), 2) if creux else None,
              "chaleur": round(min(math.sqrt(max(float(produits_ch[1] / max(comptes_ch[1], 1)) / 2 - BRUIT_CHALEUR ** 2, 0.0)), CHALEUR_MAX), 4)}
    sortie["longueur_m"] = None
    if metres >= RANGS_M_MIN and variance > 1e-6:
        # D(s) D(s + d) / variance = 1 − d / longueur : la pente de cette droite est −1 / longueur
        d = decalages * pas * resolution
        y = courbe[1:] / variance
        garde = (comptes[1:] >= 0.3 * comptes[1]) & (d <= 0.60)
        if garde.sum() >= 6:
            pente = float(np.polyfit(d[garde] - d[0], y[garde], 1)[0])
            sortie["pente"] = round(pente, 3)
            if pente < -1e-3:
                sortie["longueur_m"] = round(float(np.clip(-1.0 / pente, LONGUEUR_MIN_M, LONGUEUR_MAX_M)), 2)
            else:
                sortie["longueur_m"] = LONGUEUR_MAX_M  # la différence ne s'oublie pas sur 60 cm : de très longues lames
    return sortie


def mesurer_parquet(vues: list[tuple], resolution: float = RESOLUTION_M) -> dict:
    """Un parquet mesuré sur plusieurs vues [(image dans le sens des lames, masque « parquet propre »[, masque « parquet vu »])]
    (le troisième, plus large, sert à compter les joints : bois_vu ; absent, le masque propre sert aux deux).
    {"largeur_m", "largeur" (détail), "nuance", "chaleur", "longueur_m", "creux_mm", "rangs_m", "sol_m2"} ; les clés absentes
    n'ont pas pu être mesurées."""
    fenetres = []
    vues = [(v[0], v[1], v[2] if len(v) > 2 else v[1]) for v in vues]
    for image, _, large in vues:
        fenetres += largeurs_par_fenetre(image, large, resolution)
    sortie: dict = {"sol_m2": round(float(sum(p.sum() for _, p, _ in vues)) * resolution ** 2, 2), "fenetres": len(fenetres)}
    largeur = largeur_retenue(fenetres)
    if largeur is None:
        return sortie
    sortie["largeur_m"], sortie["largeur"] = largeur["largeur_m"], largeur
    bandes = []
    for image, propre, _ in vues:
        bandes += rangs_par_bande(image, propre, largeur["largeur_m"], resolution)
    detail = nuances_et_longueur(bandes, resolution)
    if detail:
        sortie.update({k: v for k, v in detail.items() if v is not None})
    return sortie
