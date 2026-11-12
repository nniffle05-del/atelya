"""Le « photographe » d'Atelya pour Unreal Engine : exposition et balance des blancs AUTOMATIQUES (11/11/2026).

Pourquoi : un film de logement doit sortir juste SANS retouche (règle n° 21) et sans image de référence (Cycles). Blender le
fait déjà (moteur/blender/rendre.reglage_de_photographe) : une petite photo d'essai, on y regarde les murs et plafonds blancs,
on règle la clarté pour qu'ils aient la clarté visée de l'éclairage (`clarte_murs` : 0,55 en plein soleil, 0,35 la nuit…) et
on ramène presque au blanc leur teinte (la lumière rebondie sur un parquet orangé les rosit). Ici, MÊME règle, mêmes chiffres,
mesurée sur de petites images du FILM LUI-MÊME (même pellicule, même exposition, avec un masque des murs et plafonds :
moteur/unreal/preparer_cinematique.py) : on remonte la courbe des tons pour retrouver la lumière des murs, on corrige, et on
refait un essai jusqu'à tomber juste (outils/unreal/cinematique_unreal.py), puis on contrôle le film de la même façon.
Pourquoi pas un essai « sans courbe » (valeurs physiques en EXR), plus direct : essayé le 11/11/2026, il ne suit pas le film
dans Unreal (valeurs plafonnées à 100, lumière indirecte écrêtée par Lumen selon l'exposition) : au soleil, le film sortait
1,5 cran trop clair. On mesure donc ce que verra le client.

LA PELLICULE (même rendu des tons que Blender) : Blender passe ses images par la courbe « AgX », Unreal par sa courbe
« filmique ». Avec les réglages d'usine d'Unreal, les sombres sont écrasés (un parquet foncé à 0,01 sort à 5/255 au lieu de
18/255 : le « sol trop foncé » du comparatif du 11/11/2026) et les clairs poussés. Les 5 réglages de la courbe d'Unreal
(PELLICULE) ont été choisis UNE fois pour imiter AgX sur les gris : écart moyen 1,1/255 (14/255 avec les réglages d'usine),
mesuré sur une rampe de gris passée par le Blender d'Atelya (AGX_MESURES ci-dessous, gardées pour le test). Ce n'est pas un
réglage par logement : c'est le même « film » pour tous.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

# Les chiffres de moteur/blender/rendre.py (un test vérifie qu'ils restent d'accord).
CLARTE_MURS = 0.55
EXPOSITION_MIN, EXPOSITION_MAX = -12.0, 6.0
FORCE_BALANCE = 0.7
# Clarté visée des murs DANS UNREAL, par éclairage : celle des images de Blender que NT préfère (« Blender a un truc plus
# réaliste », 11/11/2026), MESURÉE sur ces images (masque des murs, AgX à l'envers) : le photographe de Blender vise
# `clarte_murs` (moteur/eclairages.py) mais, de jour, son essai granuleux (16 rayons, sans débruiteur) le fait exposer plus clair :
# soleil 0,91 au lieu de 0,55 (séjour), voilé 0,54 au lieu de 0,47 (chambre, image 1), fin de journée 1,30 au lieu de 0,50 ; soirée
# et nuit justes (0,47 et 0,37). Le style « photo d'annonce » (murs presque blancs, pièce aérée) vient de là : on le garde.
# Jour ensoleillé 0,90 -> 1,0 (12/11/2026, NT : « fais ce qu'il y a de mieux visuellement ») : jusqu'au film v3, le masque des murs
# comptait les meubles posés devant (plus sombres), et le photographe éclaircissait : murs réels du v3 0,32 cran AU-DESSUS de la
# visée (médiane, 185 images). Masque corrigé, le film perdait cet éclat que NT avait validé (« tu as retiré la lumière ?! ») :
# la visée est remontée pour le retrouver (film corrigé : -0,16 cran à 0,90 ; 0,90 x 2^(0,32 - 0,16) = 1,0). Les autres
# éclairages, non mesurés, restent tels quels.
CLARTE_UNREAL = {"jour_soleil": 1.0, "jour_voile": 0.55, "fin_de_journee": 1.30, "soiree": 0.45, "nuit": 0.35}


# EXPOSITION LOCALE d'Unreal (cinématique, étape 4, 12/11/2026) : comme l'œil (ou un vidéaste immobilier qui « garde » ses
# fenêtres), les grandes zones beaucoup plus claires que les murs (la vue par les fenêtres) sont adoucies, le reste ne bouge pas.
# Le PIVOT est la clarté visée des murs (au-dessus du gris moyen 0,18 d'Unreal) : avec le pivot au gris moyen, les murs eux-mêmes
# étaient assombris de 0,7 cran (mesuré). Essai sur 47 images du film v3 (contraste des hautes lumières 1 / 0,7 / 0,5, pivot sur
# les murs) : dehors presque blanc 99 -> 74 -> 55 %, blanc pur 20 -> 4 %, murs inchangés (-0,10 / -0,07 / -0,05 cran).
# ÉCARTÉE PAR DÉFAUT le même jour : sans vue réelle dehors (ciel brumeux, sol gris), baisser les fenêtres ne montre rien de plus
# et retire l'éclat de la pièce (NT : « tu as retiré la lumière ?! »). 1 = sans exposition locale ; réglage gardé pour le jour où
# une vraie vue sera posée derrière les fenêtres (essayé : 0,5).
EXPOSITION_LOCALE_HAUTES_LUMIERES = 1.0


def exposition_locale(clarte: float, hautes_lumieres: float = EXPOSITION_LOCALE_HAUTES_LUMIERES) -> dict | None:
    """Le réglage d'exposition locale de la préparation Unreal (moteur/unreal/preparer_cinematique : « exposition_locale ») ;
    None si elle est désactivée (hautes_lumieres = 1)."""
    if hautes_lumieres >= 1.0:
        return None
    return {"hautes_lumieres": hautes_lumieres, "pivot_crans": round(math.log2(clarte / 0.18), 3)}


def clarte_visee(ambiance: dict) -> float:
    """Clarté visée des murs pour cet éclairage dans Unreal (CLARTE_UNREAL ; à défaut, celle de la fiche)."""
    return float(CLARTE_UNREAL.get(ambiance.get("id"), ambiance.get("clarte_murs", CLARTE_MURS)))


POIDS = np.array([0.2126, 0.7152, 0.0722])  # clarté d'une couleur linéaire (Rec. 709)
MINIMUM_PIXELS = 20

# Réglages de la courbe filmique d'Unreal qui imitent AgX (Blender 5.2) sur les gris : pente, pied, épaule, coupure des noirs,
# coupure des blancs (noms d'Unreal : film_slope, film_toe, film_shoulder, film_black_clip, film_white_clip).
PELLICULE = {"film_slope": 0.514, "film_toe": 0.650, "film_shoulder": 0.545, "film_black_clip": 0.0, "film_white_clip": 0.0642}
# Réglages des couleurs (nuancier de 163 couleurs passé dans AgX, moteur/pellicule_unreal.py) : pas d'« expansion de gamme »,
# correction des bleus entière, saturation +4 % (noms d'Unreal : expand_gamut, blue_correction, color_saturation).
PELLICULE_COULEURS = {"expand_gamut": 0.0, "blue_correction": 1.0, "saturation": 1.04}
PELLICULE_USINE = {"film_slope": 0.88, "film_toe": 0.55, "film_shoulder": 0.26, "film_black_clip": 0.0, "film_white_clip": 0.04}
# AgX de Blender 5.2 mesuré le 11/11/2026 (rampe de gris, image.save_render) : clarté linéaire -> valeur affichée (sur 255).
AGX_MESURES = {0.003: 4.6, 0.01: 18.3, 0.03: 42.0, 0.1: 86.1, 0.18: 117.3, 0.3: 145.2, 0.55: 174.3, 1.0: 196.9, 2.0: 217.0,
               5.0: 237.2}


def courbe_unreal(x, film_slope, film_toe, film_shoulder, film_black_clip, film_white_clip):
    """La courbe filmique d'Unreal 5 sur les gris (Engine/Shaders/Private/TonemapCommon.ush, FilmToneMap), puis le codage
    sRGB de l'écran : clarté linéaire -> valeur affichée entre 0 et 1. Sert à vérifier la PELLICULE sans lancer Unreal."""
    x = np.maximum(np.asarray(x, dtype=float), 1e-10)
    pied = 1 + film_black_clip - film_toe
    epaule = 1 + film_white_clip - film_shoulder
    if film_toe > 0.8:
        accord_pied = (1 - film_toe - 0.18) / film_slope + math.log10(0.18)
    else:
        bt = (0.18 + film_black_clip) / pied - 1
        accord_pied = math.log10(0.18) - 0.5 * math.log((1 + bt) / (1 - bt)) * (pied / film_slope)
    accord_droit = (1 - film_toe) / film_slope - accord_pied
    accord_epaule = film_shoulder / film_slope - accord_droit
    lg = np.log10(x)
    droite = film_slope * (lg + accord_droit)
    bas = -film_black_clip + 2 * pied / (1 + np.exp((-2 * film_slope / pied) * (lg - accord_pied)))
    haut = (1 + film_white_clip) - 2 * epaule / (1 + np.exp((2 * film_slope / epaule) * (lg - accord_epaule)))
    bas = np.where(lg < accord_pied, bas, droite)
    haut = np.where(lg > accord_epaule, haut, droite)
    t = np.clip((lg - accord_pied) / (accord_epaule - accord_pied), 0, 1)
    if accord_epaule < accord_pied:
        t = 1 - t
    t = (3 - 2 * t) * t * t
    y = np.clip(bas + (haut - bas) * t, 0, 1)
    return np.where(y <= 0.0031308, 12.92 * y, 1.055 * y ** (1 / 2.4) - 0.055)


def reglage(murs: np.ndarray, clarte: float = CLARTE_MURS, force_balance: float = FORCE_BALANCE
            ) -> tuple[float, tuple[float, float, float]] | None:
    """Exposition (en crans, à AJOUTER à celle de l'essai) et balance des blancs, d'après les couleurs linéaires des murs et
    plafonds de l'essai (tableau N × 3). Même calcul que moteur/blender/rendre.reglage_de_photographe. None si trop peu de murs.

    - exposition : la MÉDIANE de la clarté des murs devient `clarte` (une tache de soleil ou un coin d'ombre ne compte pas
      plus qu'un autre point) ;
    - balance : couleur moyenne des murs « ordinaires » (entre le 20e et le 90e centile de clarté), ramenée vers le blanc à
      `force_balance` (1 = murs parfaitement neutres ; le soir, on garde la chaleur des lampes)."""
    murs = np.asarray(murs, dtype=float).reshape(-1, 3)
    murs = murs[np.all(np.isfinite(murs), axis=1)]
    if len(murs) < MINIMUM_PIXELS:
        return None
    luminance = murs @ POIDS
    milieu = float(np.median(luminance))
    exposition = float(np.clip(math.log2(clarte / max(milieu, 1e-9)), EXPOSITION_MIN, EXPOSITION_MAX))
    bas, haut = np.percentile(luminance, [20, 90])
    ordinaires = murs[(luminance >= bas) & (luminance <= haut)]
    couleur = ordinaires.mean(axis=0) if len(ordinaires) else murs.mean(axis=0)
    teinte = couleur / max(float(couleur @ POIDS), 1e-9)
    blanc = 1 + force_balance * (teinte - 1)
    blanc = blanc / float(blanc @ POIDS)
    return exposition, tuple(float(v) for v in blanc)



TOLERANCE = 0.15  # crans : écart toléré entre la clarté des murs (essai ou film) et la clarté visée
ESSAIS_MAX = 5  # petits essais (quelques secondes de rendu chacun) avant le film
FILMS_MAX = 2  # le film, et au plus une reprise si son contrôle s'écarte encore
# Le film (8 sous-images, pleine taille) sort un peu plus clair que les essais (1 sous-image, quart de taille) : mesuré sur les
# 5 éclairages d'app-002 le 11/11/2026, -0,26 / -0,29 / -0,19 / -0,05 / -0,12 cran, moyenne -0,18. Compté d'office.
ESSAI_VERS_FILM = -0.18
# Le premier essai, à une exposition « moyenne » d'Unreal pour un intérieur (app-002, 11/11/2026 : de -6 à -12 crans selon
# l'éclairage) ; les suivants sont calculés.
PREMIER_ESSAI = -8.0


def prochaine_exposition(historique: list[tuple[float, float]]) -> float:
    """L'exposition d'Unreal à essayer après des essais (exposition, écart en crans : + = trop sombre). Avec un seul essai : on
    corrige de l'écart (1 cran pour 1 cran). Ensuite : la pente mesurée entre les deux derniers essais, bornée (la clarté monte
    toujours avec l'exposition, de 0,3 à 1,5 cran par cran) : dans Unreal elle n'est pas toujours de 1 (écrêtage de Lumen,
    valeurs plafonnées ; vu au soleil le 11/11/2026)."""
    b, e = historique[-1]
    if len(historique) < 2:
        return _borner(b + e)
    b0, e0 = historique[-2]
    pente = (e0 - e) / (b - b0) if b != b0 else 1.0  # crans de clarté gagnés par cran d'exposition
    pente = min(max(pente, 0.3), 1.5)
    return _borner(b + e / pente)


# Exposition d'Unreal raisonnable pour un intérieur (app-002, 5 éclairages : de -6 à -12,6). Au-delà, la pièce n'a pas de lumière
# (vu le 11/11/2026 : entrée sans fenêtre, portes fermées, de jour : le photographe partait à +22) : on s'arrête aux bornes.
EXPOSITION_UNREAL_BORNES = (-16.0, -3.0)


def _borner(biais: float) -> float:
    return min(max(biais, EXPOSITION_UNREAL_BORNES[0]), EXPOSITION_UNREAL_BORNES[1])


def lineaire_affiche(valeur_affichee, pellicule=None):
    """La clarté linéaire (après exposition) qui donne cette valeur affichée (0 à 1) avec la pellicule : la courbe à l'envers."""
    x = np.logspace(-5, 3, 4000)
    y = courbe_unreal(x, **(pellicule or PELLICULE))
    return np.exp(np.interp(valeur_affichee, y, np.log(x)))


def _lire(chemin: Path) -> np.ndarray:
    import cv2

    image = cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"PLANTÉ : image illisible {chemin}")
    return image[..., ::-1].astype(float) / 255.0


def murs_lineaires(image: Path, masque: Path, gain=(1.0, 1.0, 1.0)) -> np.ndarray:
    """Les couleurs des murs et plafonds d'une image du film (ou d'un essai), ramenées à la lumière AVANT pellicule et AVANT
    balance des blancs (couleur par couleur, courbe à l'envers, divisée par le gain appliqué). Le masque (même image, passe
    « M_MasqueBlancs ») est mis à la taille de l'image ; ses bords sont retirés (pixels mêlés au reste)."""
    import cv2

    rvb = _lire(image)
    m = _lire(masque)[..., 0]
    if rvb.shape[0] > m.shape[0]:  # image du film (pleine taille) : mesurée à la taille du masque. 185 images Full HD en entier
        # = 1,8 Go de couleurs de murs, plantage mémoire au contrôle du film (12/11/2026)
        rvb = cv2.resize(rvb, (m.shape[1], m.shape[0]), interpolation=cv2.INTER_AREA)
    m = cv2.resize(m, (rvb.shape[1], rvb.shape[0]), interpolation=cv2.INTER_NEAREST) > 0.5
    m = cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    return lineaire_affiche(rvb[m]) / np.asarray(gain, dtype=float)


def mesurer(images: list[Path], masques: list[Path], clarte: float, force_balance: float, gain=(1.0, 1.0, 1.0)) -> dict:
    """Ce que dit le photographe d'un essai ou du film : de combien de crans corriger l'exposition (+ : trop sombre) et
    quelle balance des blancs (Blender : rendre.reglage_de_photographe). Tous les murs vus pendant le plan comptent ensemble
    (réglage UNE fois par plan, pas de pompage d'une image à l'autre) ; la correction de chaque image seule est gardée pour
    juger la stabilité. Les murs « brûlés » (blanc pur) comptent comme très clairs : la correction va dans le bon sens et
    l'essai suivant précise."""
    tous, par_image = [], []
    for image, masque in zip(images, masques):
        murs = murs_lineaires(image, masque, gain)
        tous.append(murs)
        seul = reglage(murs, clarte, force_balance)
        par_image.append({"image": Path(image).name, "murs_pixels": int(len(murs)),
                          "correction": None if seul is None else round(seul[0], 2)})
    resultat = reglage(np.concatenate(tous) if tous else np.zeros((0, 3)), clarte, force_balance)
    if resultat is None:
        raise ValueError("PLANTÉ : aucun mur ni plafond vu (masque vide)")
    correction, blanc = resultat
    murs = np.concatenate(tous)
    return {"correction": round(correction, 3), "murs_lineaire": round(float(np.median(murs @ POIDS)), 4),
            "blanc": [round(v, 4) for v in blanc], "gain": [round(v, 4) for v in gain_unreal(blanc)],
            "clarte_visee": clarte, "force_balance": force_balance, "images": par_image}


def gain_unreal(blanc) -> list[float]:
    """Blender divise chaque couleur par `blanc` (niveau du blanc des courbes) ; Unreal la multiplie par son « color gain »
    (appliqué comme Blender : en valeurs linéaires, avant la courbe)."""
    return [1.0 / max(float(v), 1e-6) for v in blanc]


# ---------------------------------------------------------------------------------------------------------------------------
# L'exposition EN MARCHANT (balade, 12/11/2026) : comme l'œil ou une vraie caméra, elle suit la pièce où l'on est, en douceur.
# Réglages revus le 12/11/2026 (cinématique, étape 4), MESURÉS sur les murs du film v3 (outils/unreal/mesurer_lumiere.py) : avec un
# essai par seconde, une moyenne de 2 s et 0,75 cran/s, l'exposition arrivait EN RETARD dans chaque pièce : en sortant d'un couloir
# sans fenêtre (embrasure à l'ombre plein cadre), la chambre au soleil restait sur-exposée de +1,1 cran pendant 3 s ; 34 % du film
# avait des murs à plus d'un demi-cran de la visée. Simulé sur les mêmes images : essais toutes les 0,25 s, MÉDIANE glissante de
# 1,5 s (un moment bref, une embrasure qu'on frôle, ne fait plus bouger l'exposition), moyenne de 0,75 s et jusqu'à 2 crans/s (le
# changement se fait PENDANT le passage de la porte, comme un opérateur qui tourne la bague) : 5 % du film, sur-exposition à
# l'entrée de la chambre -1,1 -> -0,05 cran.
ADAPTATION_MEDIANE_S = 1.5  # médiane glissante des réglages voulus : un regard bref ne compte pas
ADAPTATION_FENETRE_S = 0.75  # puis moyenne glissante (pas de « pompage »)
ADAPTATION_MAX_CRAN_S = 2.0  # au plus 2 crans par seconde
ESSAI_PAS_IMAGES = 6  # un essai toutes les 6 images (0,25 s à 24 images/s)


def exposition_en_marchant(images: list[int], voulues: list, ips: int = 24, fenetre_s: float = ADAPTATION_FENETRE_S,
                           max_cran_s: float = ADAPTATION_MAX_CRAN_S, mediane_s: float = ADAPTATION_MEDIANE_S) -> list[list]:
    """Clés [[image, exposition], …] d'après les expositions voulues aux images d'essai (None = pas assez de murs vus : on
    prend celle des voisines). Médiane glissante (les moments brefs ne comptent pas), lissées (moyenne glissante), bornées en
    vitesse d'adaptation (dans les deux sens du temps : la caméra anticipe un peu au lieu de seulement suivre), puis bornées
    comme une exposition d'intérieur."""
    if not images:
        return []
    v = np.array([np.nan if x is None else float(x) for x in voulues], float)
    if np.all(np.isnan(v)):
        raise ValueError("PLANTÉ : aucune image d'essai ne voit de murs")
    k = np.arange(len(v))
    v = np.interp(k, k[~np.isnan(v)], v[~np.isnan(v)])
    pas = max(1, int(np.median(np.diff(images)))) if len(images) > 1 else ips
    m = int(round(mediane_s * ips / pas / 2))
    if m > 0:
        v = np.array([np.median(v[max(0, i - m):i + m + 1]) for i in range(len(v))])
    n = max(1, int(round(fenetre_s * ips / pas / 2)))
    lisse = np.convolve(np.pad(v, n, mode="edge"), np.ones(2 * n + 1) / (2 * n + 1), mode="valid")
    borne = max_cran_s * pas / ips
    sortie = [float(lisse[0])]
    for x in lisse[1:]:
        sortie.append(sortie[-1] + max(-borne, min(borne, float(x) - sortie[-1])))
    for i in range(len(sortie) - 2, -1, -1):
        sortie[i] = sortie[i + 1] + max(-borne, min(borne, sortie[i] - sortie[i + 1]))
    return [[int(i), round(_borner(x), 3)] for i, x in zip(images, sortie)]
