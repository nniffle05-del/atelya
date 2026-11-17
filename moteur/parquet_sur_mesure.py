"""Le parquet dessiné SUR MESURE d'après ce qui a été mesuré sur les photos du client (18/11/2026).

Pourquoi : NT : « je veux que le sens soit le même, et aussi le parquet ». Aucun catalogue n'a « le même parquet » que chaque
logement. Atelya mesure donc le parquet sur les photos (moteur/parquet_photo.py : largeur et longueur des lames, nuances d'une
lame à l'autre, joints) et le DESSINE : une vraie image de matière (couleur, relief, brillance), comme celles de la
bibliothèque. Elle passe donc dans Blender ET dans Unreal, se teinte et se tourne comme les autres.

Comment : le bois vient d'une VRAIE photo de chêne de la bibliothèque (« chene_clair », plaquage de chêne de Poly Haven, CC0).
Chaque lame est un morceau différent de cette photo, pris dans le fil du bois ; sa nuance (plus claire, plus foncée, plus
chaude) est tirée au hasard avec l'ampleur MESURÉE sur les photos ; les lames ont la largeur mesurée, des longueurs inégales
autour de la longueur mesurée, leurs bouts décalés d'un rang à l'autre (pose « à l'anglaise ») ; le joint a la force mesurée.
L'image se raccorde sans couture sur ses quatre bords. Les lames vont de HAUT EN BAS de l'image : sur un sol, Blender pose une
image avec sa largeur le long de l'axe y de la maquette, ces images suivent donc le sens demandé sans être tournées.

Le dessin ne dépend que de sa fiche (le hasard est tiré d'après elle) : deux pièces qui ont la même fiche ont la même image, et
une maquette refaite demain redonne le même parquet. Ce module ne dépend ni de Blender ni du reste du moteur.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

VERSION = "0.2.1"
MATIERE = "parquet_sur_mesure"  # le nom de la matière dans le format (moteur/matieres.py, moteur/logement.py)
PREFIXE = "psm_"  # le nom d'un parquet dessiné : « psm_ » + sa clé (voir cle)
BOIS = "chene_clair"  # la photo de chêne dont les lames sont tirées (fil du bois de haut en bas de l'image)
COTE_M = 2.4  # côté visé de l'image (les lames longues en demandent plus : voir cote)
COTE_MAX_M = 4.8
PX_PAR_M_SORTIE = 2048 / 2.4  # finesse de l'image rendue : 1,2 mm par pixel
PIXELS_MAX = 4096
# Les valeurs SUPPOSÉES quand une mesure manque (dites comme telles dans la fiche : champ « supposes »).
DEFAUTS = {"largeur": 0.09, "nuance": 0.06, "chaleur": 0.02, "joint_mm": 0.8}
BORNES = {"largeur": (0.04, 0.35), "longueur": (0.25, 2.5), "nuance": (0.0, 0.25), "chaleur": (0.0, 0.12), "joint_mm": (0.0, 3.0)}


def longueur_supposee(largeur: float) -> float:
    """La longueur moyenne des lames quand elle n'a pas pu être mesurée : des lames étroites sont des lames courtes (parquet
    massif ancien, 40 cm à 1,2 m), de larges lames sont longues (1 à 2 m). Une supposition, dite comme telle."""
    return round(float(np.clip(8.0 * largeur, 0.6, 1.6)), 2)


def fiche(mesures: dict | None = None, **forces) -> dict:
    """La fiche d'un parquet à lames droites d'après des mesures (moteur.parquet_photo.mesurer_parquet) : chaque valeur est
    bornée, arrondie (deux mesures presque égales donnent le même parquet), et les valeurs non mesurées sont SUPPOSÉES et
    listées dans « supposes »."""
    m = dict(mesures or {})
    m.update(forces)
    valeurs = {"largeur": m.get("largeur_m", m.get("largeur")), "longueur": m.get("longueur_m", m.get("longueur")),
               "nuance": m.get("nuance"), "chaleur": m.get("chaleur"), "joint_mm": m.get("creux_mm", m.get("joint_mm"))}
    supposes = [k for k, v in valeurs.items() if v is None]
    pose = m.get("pose", "lames")
    for k in supposes:
        valeurs[k] = DEFAUTS[k] if k != "longueur" else None
    if valeurs["longueur"] is None:  # un chevron de point de Hongrie : cinq à six fois plus long que large
        valeurs["longueur"] = longueur_supposee(valeurs["largeur"]) if pose == "lames" else 5.5 * valeurs["largeur"]
    pas = {"largeur": 0.005, "longueur": 0.05, "nuance": 0.01, "chaleur": 0.005, "joint_mm": 0.1}
    sortie = {"pose": pose}
    if pose == "point_de_hongrie":
        sortie["angle"] = float(np.clip(round(float(m.get("angle", 45.0)) / 5) * 5, 30, 60))
    for k, v in valeurs.items():
        v = float(np.clip(v, *BORNES[k]))
        sortie[k] = round(round(v / pas[k]) * pas[k], 3)
    sortie["bois"] = m.get("bois", BOIS)
    if supposes:
        sortie["supposes"] = sorted(supposes)
    return sortie


def cle(fiche_: dict) -> str:
    """La clé d'un parquet : huit caractères tirés de ce qui change son DESSIN (pas de la liste des valeurs supposées)."""
    dessin = {k: fiche_[k] for k in ("pose", "largeur", "longueur", "nuance", "chaleur", "joint_mm", "bois", "angle")
              if fiche_.get(k) is not None}
    return hashlib.sha1((json.dumps(dessin, sort_keys=True) + VERSION).encode()).hexdigest()[:8]


def nom(fiche_: dict) -> str:
    """Le nom de la matière dessinée pour cette fiche (« psm_3fa2c1b0 »)."""
    return PREFIXE + cle(fiche_)


def est_sur_mesure(matiere: str) -> bool:
    return matiere.startswith(PREFIXE)


def cote(fiche_: dict) -> tuple[float, int]:
    """(côté de l'image en m, nombre de rangs) : assez grand pour deux longueurs de lame, et un nombre entier de rangs."""
    vise = float(np.clip(max(COTE_M, 2.2 * fiche_["longueur"] * 1.5), COTE_M, COTE_MAX_M))
    rangs = max(4, int(round(vise / fiche_["largeur"])))
    return rangs * fiche_["largeur"], rangs


def _normales(hauteur: np.ndarray, force: float) -> np.ndarray:
    """Une carte de relief (bleutée) d'après une hauteur 0-1 ; bords raccordés."""
    dx = (np.roll(hauteur, -1, 1) - np.roll(hauteur, 1, 1)) * force
    dy = (np.roll(hauteur, -1, 0) - np.roll(hauteur, 1, 0)) * force
    n = np.stack([-dx, dy, np.ones_like(hauteur)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def _lineaire(c: np.ndarray) -> np.ndarray:
    """Valeurs d'image (0-255) → lumière (0-1). Tout le dessin se fait en LUMIÈRE : une lame « 10 % plus claire » renvoie 10 %
    de lumière en plus, comme ce qui est mesuré sur les photos (moteur/parquet_photo.py)."""
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _image(lumiere: np.ndarray) -> np.ndarray:
    """L'inverse de _lineaire : lumière (0-1) → valeurs d'image (0-255, uint8)."""
    c = np.clip(lumiere, 0.0, 1.0)
    return (np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255 + 0.5).astype(np.uint8)


def _dessiner_hongrie(fiche_: dict, photo_bois: np.ndarray, px_par_m_bois: float, mm_par_px: float | None = None) -> dict:
    """Le POINT DE HONGRIE dessiné en vraie image (18/11/2026 : dans le film Unreal, le point de Hongrie calculé par Blender
    n'existait pas, le séjour d'app-001 avait un sol brun tout uni). Des RANGS de lames coupées en biais (angle de la fiche),
    penchées d'un côté puis de l'autre d'un rang au suivant : les pointes des chevrons se rejoignent. Chaque lame est un morceau
    de la vraie photo de chêne, avec sa nuance. Dessin de travail : les rangs à l'horizontale ; image rendue : rangs de HAUT EN
    BAS (comme les lames droites : le « sens » du sol est celui des rangs, donc des longs joints entre les rangs)."""
    import cv2
    from PIL import Image, ImageFilter

    mm = mm_par_px or 1.0
    px = 1000.0 / mm  # pixels par mètre du dessin de travail
    largeur, longueur, angle = fiche_["largeur"], fiche_["longueur"], math.radians(float(fiche_.get("angle", 45.0)))
    rang_px = max(6, int(round(longueur * math.sin(angle) * px)))  # hauteur d'un rang de chevrons
    pas_px = max(4, int(round(largeur / math.sin(angle) * px)))  # écart entre deux lames le long du rang
    paires = max(1, int(round(COTE_M * px / (2 * rang_px))))
    lames = max(2, int(round(COTE_M * px / pas_px)))
    haut, large = 2 * paires * rang_px, lames * pas_px  # nombres entiers de rangs et de lames : raccord sans couture
    source = Image.fromarray(photo_bois)
    taille = (max(8, int(round(source.width / px_par_m_bois * px))), max(8, int(round(source.height / px_par_m_bois * px))))
    bois = _lineaire(np.asarray(source.resize(taille, Image.LANCZOS).rotate(90, expand=True), np.float32))  # fil de gauche à droite
    yy, xx = np.mgrid[0:haut, 0:large].astype(np.float32)
    rang = (yy // rang_px).astype(np.int32)
    dans_rang = yy - rang * rang_px
    monte = rang % 2 == 0
    glisse = xx - np.where(monte, dans_rang, rang_px - dans_rang) / math.tan(angle)  # constant le long d'une lame
    lame = np.floor(glisse / pas_px).astype(np.int32)
    en_travers = (glisse / pas_px - lame) * (largeur * px)  # pixels en travers de la lame
    le_long = dans_rang / math.sin(angle)  # pixels le long de la lame
    r, l = rang % (2 * paires), lame % lames
    alea = np.random.default_rng(int(cle(fiche_), 16))
    forme = (2 * paires, lames)
    long_px, large_px = longueur * px, largeur * px
    depart_long = alea.uniform(0, max(1.0, bois.shape[1] - long_px - 1), forme).astype(np.float32)
    depart_travers = alea.uniform(0, max(1.0, bois.shape[0] - large_px - 1), forme).astype(np.float32)
    retourne = alea.random(forme) < 0.5
    n = max(float(fiche_["nuance"]), 1e-6)
    clarte = np.exp(np.clip(alea.normal(0.0, n, forme), -2.2 * n, 2.2 * n)).astype(np.float32) if fiche_["nuance"] > 0 else np.ones(forme, np.float32)
    c = max(float(fiche_["chaleur"]), 1e-6)
    chaud = np.clip(alea.normal(0.0, c, forme), -2.2 * c, 2.2 * c).astype(np.float32) if fiche_["chaleur"] > 0 else np.zeros(forme, np.float32)
    carte_x = depart_long[r, l] + np.where(retourne[r, l], long_px - le_long, le_long)
    carte_y = depart_travers[r, l] + en_travers
    couleur = cv2.remap(bois, carte_x.astype(np.float32), carte_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    couleur *= clarte[r, l][..., None]
    couleur[..., 0] *= np.exp(chaud[r, l] / 2)
    couleur[..., 2] *= np.exp(-chaud[r, l] / 2)
    # les joints : entre deux lames d'un rang, et le long joint entre deux rangs
    joint_mm = float(fiche_["joint_mm"])
    demi = max(1, int(math.ceil(joint_mm / (0.85 * 2 * mm))))
    sombre = float(np.clip(joint_mm / (2 * demi * mm), 0.0, 0.85))
    bord = (glisse / pas_px - lame) * pas_px
    creux = np.ones((haut, large), np.float32)
    creux[(bord < demi) | (bord > pas_px - demi) | (dans_rang < demi) | (dans_rang > rang_px - demi)] = 0.0
    doux = np.asarray(Image.fromarray((creux * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    couleur *= (1.0 - sombre * (1.0 - doux))[..., None]
    haut_m, large_m = haut / px, large / px
    sortie = (int(min(PIXELS_MAX, round(large_m * PX_PAR_M_SORTIE / 4) * 4)), int(min(PIXELS_MAX, round(haut_m * PX_PAR_M_SORTIE / 4) * 4)))
    image = Image.fromarray(_image(couleur)).resize(sortie, Image.LANCZOS).transpose(Image.ROTATE_90)
    hauteur = np.asarray(Image.fromarray((doux * 255).astype(np.uint8)).resize(sortie, Image.LANCZOS).transpose(Image.ROTATE_90), np.float32) / 255
    relief = Image.fromarray(_normales(hauteur, 3.0 * float(np.clip(joint_mm / 1.5, 0.2, 1.0))))
    gris = np.asarray(image.convert("L"), np.float32) / 255
    mat = np.clip(0.78 + 0.15 * (1 - hauteur) + 0.10 * (gris - gris.mean()), 0, 1)
    # l'image rendue : sa largeur est le travers des rangs, sa hauteur le long des rangs. La taille est écrite [le long, en
    # travers] : sur un sol, Blender étale la HAUTEUR de l'image sur la première taille et sa largeur sur la seconde
    return {"couleur": image, "relief": relief, "brillance": Image.fromarray((mat * 255).astype(np.uint8)),
            "taille_m": [round(large_m, 4), round(haut_m, 4)], "plan": {"rang_m": rang_px / px, "pas_m": pas_px / px, "rangs": 2 * paires, "lames": lames}}


def dessiner(fiche_: dict, photo_bois: np.ndarray, px_par_m_bois: float, mm_par_px: float | None = None) -> dict:
    """Dessine le parquet de `fiche_` avec le bois de `photo_bois` (RGB uint8, fil de haut en bas, `px_par_m_bois` pixels par
    mètre). Rend {"couleur", "relief", "brillance" (images PIL), "taille_m" (côté), "plan" (les lames posées : pour les tests)}.
    mm_par_px : finesse du dessin de travail (1 mm par défaut ; plus grossier pour un essai rapide)."""
    from PIL import Image, ImageFilter

    if fiche_.get("pose") == "point_de_hongrie":
        return _dessiner_hongrie(fiche_, photo_bois, px_par_m_bois, mm_par_px)
    cote_m, rangs = cote(fiche_)
    mm = mm_par_px or (1.0 if cote_m <= 3.0 else 1.5)
    h_lame = max(3, int(round(fiche_["largeur"] * 1000 / mm)))
    cote_px = rangs * h_lame
    # la photo du bois ramenée à la finesse du dessin et couchée : le fil va de gauche à droite, comme les lames du dessin
    source = Image.fromarray(photo_bois)
    taille = (max(8, int(round(source.width / px_par_m_bois * 1000 / mm))), max(8, int(round(source.height / px_par_m_bois * 1000 / mm))))
    bois = _lineaire(np.asarray(source.resize(taille, Image.LANCZOS).rotate(90, expand=True), np.float32))
    moyenne_bois = bois.reshape(-1, 3).mean(0)
    alea = np.random.default_rng(int(cle(fiche_), 16))
    couleur = np.zeros((cote_px, cote_px, 3), np.float32)
    creux = np.ones((cote_px, cote_px), np.float32)  # 1 = surface, 0 = fond d'un joint
    # le joint : une largeur réelle de 1 à 3 mm, d'autant plus sombre que la photo le montre marqué (« millimètres de noir »)
    joint_mm = float(fiche_["joint_mm"])
    # le joint dessiné fait 2 × demi pixels de large (un demi-joint de chaque côté de la limite entre deux lames) ; il est
    # d'autant plus sombre que la photo le montre marqué : largeur × noirceur = les « millimètres de noir » mesurés
    demi = max(1, int(math.ceil(joint_mm / (0.85 * 2 * mm))))
    sombre = float(np.clip(joint_mm / (2 * demi * mm), 0.0, 0.85))
    l_min, l_max = 0.5 * fiche_["longueur"] * 1000 / mm, 1.5 * fiche_["longueur"] * 1000 / mm
    plan = []
    for rang in range(rangs):
        y0 = rang * h_lame
        longueurs = []
        while sum(longueurs) < cote_px:
            longueurs.append(alea.uniform(l_min, l_max))
        if len(longueurs) > 1 and sum(longueurs[:-1]) > 0.8 * cote_px:
            longueurs = longueurs[:-1]
        longueurs = np.array(longueurs) * cote_px / sum(longueurs)  # ajustées pour remplir exactement (raccord sans couture)
        x = float(alea.uniform(0, cote_px))  # le premier bout de lame, décalé d'un rang à l'autre
        for longueur in longueurs:
            n = max(2, int(round(longueur)))
            by = int(alea.integers(0, max(1, bois.shape[0] - h_lame)))
            bx = int(alea.integers(0, max(1, bois.shape[1] - n)))
            morceau = bois[by:by + h_lame, bx:bx + n]
            while morceau.shape[1] < n:  # lame plus longue que la photo : prolongée en miroir
                morceau = np.concatenate([morceau, morceau[:, ::-1]], 1)
            while morceau.shape[0] < h_lame:
                morceau = np.concatenate([morceau, morceau[::-1]], 0)
            morceau = morceau[:h_lame, :n]
            if alea.random() < 0.5:
                morceau = morceau[:, ::-1]
            if alea.random() < 0.5:
                morceau = morceau[::-1]
            # la nuance de la lame, à l'ampleur mesurée : le morceau est d'abord ramené à la couleur moyenne du bois (sinon la
            # nuance propre à l'endroit de la photo s'ajouterait à celle qu'on veut)
            clarte = math.exp(float(np.clip(alea.normal(0.0, fiche_["nuance"]), -2.2 * fiche_["nuance"], 2.2 * fiche_["nuance"]))) \
                if fiche_["nuance"] > 0 else 1.0
            chaud = float(np.clip(alea.normal(0.0, fiche_["chaleur"]), -2.2 * fiche_["chaleur"], 2.2 * fiche_["chaleur"])) \
                if fiche_["chaleur"] > 0 else 0.0
            gain = clarte * moyenne_bois / np.maximum(morceau.reshape(-1, 3).mean(0), 1e-4)
            morceau = morceau * (gain * np.array([math.exp(chaud / 2), 1.0, math.exp(-chaud / 2)])).astype(np.float32)
            colonnes = (int(round(x)) + np.arange(n)) % cote_px
            couleur[y0:y0 + h_lame, colonnes] = morceau
            creux[y0:y0 + h_lame, colonnes[:demi]] = 0.0  # le bout de la lame
            creux[y0:y0 + h_lame, colonnes[-demi:]] = 0.0
            plan.append({"rang": rang, "debut_m": round((x % cote_px) * mm / 1000, 4), "longueur_m": round(n * mm / 1000, 4), "clarte": clarte})
            x += longueur
        creux[y0:y0 + demi] = 0.0  # le long joint entre deux rangs
        creux[y0 + h_lame - demi:y0 + h_lame] = 0.0
    doux = np.asarray(Image.fromarray((creux * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    couleur *= (1.0 - sombre * (1.0 - doux))[..., None]
    sortie_px = int(min(PIXELS_MAX, round(cote_m * PX_PAR_M_SORTIE / 4) * 4))
    # lames de HAUT EN BAS de l'image rendue (voir le module) : le dessin de travail, couché, est tourné d'un quart de tour
    image = Image.fromarray(_image(couleur)).resize((sortie_px, sortie_px), Image.LANCZOS).transpose(Image.ROTATE_90)
    hauteur = np.asarray(Image.fromarray((doux * 255).astype(np.uint8)).resize((sortie_px, sortie_px), Image.LANCZOS)
                         .transpose(Image.ROTATE_90), np.float32) / 255
    # le relief des joints suit leur force : un joint serré (parquet récent) ne creuse presque pas. (Mesuré le 18/11/2026 sur
    # les rendus : avec un relief fort partout, un joint demandé à 0,3 mm de noir en montrait 1,8.)
    relief = Image.fromarray(_normales(hauteur, 3.0 * float(np.clip(joint_mm / 1.5, 0.2, 1.0))))
    # la brillance : un vernis SATINÉ, comme les parquets de la bibliothèque (leur image de brillance vaut 0,75 à 0,85 : avec
    # 0,45, le parquet sur mesure renvoyait plus le blanc du ciel et sortait moins jaune que le même sol du catalogue), plus
    # mat dans les joints ; un rien de variation d'une lame à l'autre
    gris = np.asarray(image.convert("L"), np.float32) / 255
    mat = np.clip(0.78 + 0.15 * (1 - hauteur) + 0.10 * (gris - gris.mean()), 0, 1)
    brillance = Image.fromarray((mat * 255).astype(np.uint8))
    return {"couleur": image, "relief": relief, "brillance": brillance, "taille_m": round(cote_m, 4), "plan": plan}


def bois_de_la_bibliotheque(bibliotheque: Path, bois: str = BOIS):
    """(photo RGB uint8, pixels par mètre) de la photo de bois `bois` de la bibliothèque de matières."""
    from PIL import Image

    fiches = json.loads((Path(bibliotheque) / "matieres.json").read_text(encoding="utf-8"))
    photo = Image.open(Path(bibliotheque) / bois / "couleur.jpg").convert("RGB")
    return np.asarray(photo), photo.width / float((fiches[bois].get("taille_image_m") or [1.0])[0])


_ALBEDOS: dict[tuple, np.ndarray] = {}


def albedo(fiche_: dict, bibliotheque: Path) -> np.ndarray:
    """La couleur moyenne (linéaire) du parquet dessiné pour cette fiche : ce qu'il faut pour calculer sa teinte
    (moteur/teinte_photo.py), sans attendre la construction. Dessin d'essai grossier (4 mm par pixel), gardé en mémoire."""
    k = (cle(fiche_), str(bibliotheque))
    if k not in _ALBEDOS:
        photo, px_par_m = bois_de_la_bibliotheque(Path(bibliotheque), fiche_.get("bois", BOIS))
        image = np.asarray(dessiner(fiche_, photo, px_par_m, mm_par_px=4.0)["couleur"].resize((256, 256)), np.float32)
        _ALBEDOS[k] = _lineaire(image).reshape(-1, 3).mean(0)
    return _ALBEDOS[k]


def ecrire(fiche_: dict, bibliotheque: Path, dossier: Path) -> dict:
    """Dessine le parquet de la fiche dans `dossier`/<nom>/ (couleur.jpg, relief.jpg, brillance.jpg), sauf s'il y est déjà.
    Rend sa fiche de matière, au format de matieres.json : {"taille_image_m", "dossier" (chemin absolu), "parquet", …}."""
    n = nom(fiche_)
    cible = Path(dossier) / n
    fiche_matiere = cible / "fiche.json"
    if fiche_matiere.is_file() and all((cible / f).is_file() for f in ("couleur.jpg", "relief.jpg", "brillance.jpg")):
        return {**json.loads(fiche_matiere.read_text(encoding="utf-8")), "dossier": str(cible.resolve())}
    photo, px_par_m = bois_de_la_bibliotheque(Path(bibliotheque), fiche_.get("bois", BOIS))
    d = dessiner(fiche_, photo, px_par_m)
    cible.mkdir(parents=True, exist_ok=True)
    for cle_, fichier in (("couleur", "couleur.jpg"), ("relief", "relief.jpg"), ("brillance", "brillance.jpg")):
        d[cle_].save(cible / fichier, quality=92)
    sortie = {"description": f"parquet sur mesure d'après les photos du client ({fiche_.get('pose', 'lames')}) : lames de {100 * fiche_['largeur']:.1f} cm, "
                             f"longues de {fiche_['longueur']:.2f} m en moyenne (dessiné par Atelya)",
              "source": f"dessiné par Atelya (moteur/parquet_sur_mesure.py {VERSION}) d'après la photo de chêne « {fiche_.get('bois', BOIS)} »",
              "identifiant": n, "licence": "CC0 1.0 (photo d'origine : Poly Haven, oak_veneer_01)", "auteurs": ["Atelya"],
              "taille_image_m": list(d["taille_m"]) if isinstance(d["taille_m"], (list, tuple)) else [d["taille_m"], d["taille_m"]],
              "parquet": fiche_}
    fiche_matiere.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**sortie, "dossier": str(cible.resolve())}
