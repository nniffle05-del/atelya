"""Le MOTIF d'un garde-corps en ferronnerie, recopié des photos du client (F2 pièce 3, suite ; 20/11/2026).

POURQUOI. La maquette construisait devant les fenêtres un garde-corps à barreaux droits ; les photos montrent une ferronnerie à
volutes. NT : « pas fou […] ce sont des rambardes haussmanniennes, n'est-il pas possible d'en trouver en libre service ? » Un
modèle tout fait serait un SOSIE (chaque immeuble a son motif), à chercher et à lire (licence) pour chaque logement. Or un
garde-corps en fonte est un dessin PLAT, et la photo le montre en sombre sur le dehors clair : on le recopie.

COMMENT (géométrie seule, rien à télécharger) :
1. chaque vantail dont la lecture des fenêtres dit le dessus du garde-corps (moteur/vitrages.py, « garde_corps ») donne une
   BANDE : la photo entre ce dessus et le bas de la vitre, mise à plat à ses vraies proportions (`bande`) ;
2. dans la bande, le fer = ce qui est plus sombre que ce qui l'entoure et plus mince qu'une dizaine de centimètres (`fer`) ;
3. une ferronnerie RÉPÈTE un module (un barreau et ses volutes) : son pas est mesuré dans chaque bande (`pas_d_une_bande`),
   puis toutes les répétitions de toutes les photos sont superposées, recalées, et leur MÉDIANE donne un module propre
   (`module`) : ce qui n'est pas le fer (la façade d'en face, un reflet, un bord de rideau) change d'une répétition à
   l'autre et disparaît ; un module symétrique est rendu symétrique ;
4. le module devient des CONTOURS (`contours`), rangés dans le logement (GardeCorpsFenetre.motif), en parts : il vaut pour
   une fenêtre de n'importe quelle taille ;
5. à la construction, `panneau` répète le module sur la largeur de la baie (un nombre entier de fois) et rend les polygones
   du fer en mètres ; Blender en fait du vrai métal, avec son épaisseur (moteur/blender/ferronneries.py).

Sans photo lisible (moins de MODULES_MIN répétitions d'accord) : pas de motif, le garde-corps garde ses barreaux droits.
"""
from __future__ import annotations

import copy
import heapq
import math
import warnings
from pathlib import Path

import cv2
import numpy as np

from moteur import vitrages as vt
from moteur.images import lire_image

VERSION = "0.1.0"
HAUT_PX = 320  # hauteur d'une bande mise à plat (pixels) : trois à quatre fois ce que la photo montre
FOCALE = 0.75  # focale supposée d'une photo d'annonce, en parts de sa largeur (grand angle), si le quadrilatère ne la dit pas
FER_MAX = 0.14  # part de la hauteur du garde-corps : ce qui est sombre et plus large n'est pas un fer (fenêtre d'en face, toit)
PAS_MIN, PAS_MAX = 0.12, 0.60  # le module, en parts de la hauteur du garde-corps (7 à 40 cm pour un garde-corps de 65 cm)
ECART_DE_PAS = 0.15  # une bande dont le pas s'écarte davantage du pas commun est écartée (mal lue)
MODULES_MIN = 4  # il faut au moins autant de répétitions d'accord pour recopier un motif
ACCORD_MIN = 0.45  # ressemblance moyenne (corrélation) des répétitions avec leur médiane, en dessous : pas de motif
SYMETRIE_MIN = 0.75  # ressemblance du module avec son miroir à partir de laquelle il est rendu symétrique
SYMETRIE_DEBOUT_MIN = 0.5  # … et avec son miroir de haut en bas (barreau retiré) pour que le haut et le bas se complètent
RAYON_DU_TRAIT = 0.016  # part de la hauteur : un point est du fer s'il est presque aussi sombre que le plus sombre à cette distance
PART_DU_TRAIT = 0.6  # … « presque » : cette part du plus sombre (sépare deux fers voisins que le flou de la photo a collés)
FER_FAIBLE = 0.22  # part du fer le plus net du module en dessous de laquelle un point n'est jamais du fer (le fond)


def aspect_vrai(quad: np.ndarray, taille: tuple[int, int]) -> float:
    """Largeur / hauteur VRAIES du rectangle que la photo montre en `quad` (haut gauche, haut droit, bas droit, bas gauche).
    Vu de biais, un rectangle paraît plus étroit : on le redresse avec la focale de l'appareil, tirée du quadrilatère
    lui-même quand ses fuyantes sont nettes, supposée (FOCALE) sinon."""
    largeur, hauteur = taille
    c = np.array([largeur / 2.0, hauteur / 2.0])
    carre = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
    h = cv2.getPerspectiveTransform(carre, (np.asarray(quad, float) - c).astype(np.float32)).astype(float)
    h1, h2 = h[:, 0], h[:, 1]
    f2 = None
    if abs(h1[2] * h2[2]) > 1e-4:  # les deux fuyantes existent : la focale se lit (h1 et h2 sont à angle droit)
        v = -(h1[0] * h2[0] + h1[1] * h2[1]) / (h1[2] * h2[2])
        if (0.35 * largeur) ** 2 < v < (1.6 * largeur) ** 2:
            f2 = v
    f2 = f2 if f2 is not None else (FOCALE * largeur) ** 2
    r1 = math.sqrt((h1[0] ** 2 + h1[1] ** 2) / f2 + h1[2] ** 2)
    r2 = math.sqrt((h2[0] ** 2 + h2[1] ** 2) / f2 + h2[2] ** 2)
    return r1 / r2


def fer(gris: np.ndarray) -> np.ndarray:
    """(H, L) de 0 à 1 : à quel point chaque point de la bande est un FER : plus sombre que ce qui l'entoure, et mince."""
    gris = gris.astype(np.float32)
    cote = max(5, int(round(FER_MAX * gris.shape[0])) | 1)
    fond = cv2.morphologyEx(gris, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cote, cote)))
    return np.clip((fond - gris) / np.maximum(fond, 40.0), 0.0, 1.0)


def bande(image: np.ndarray, fenetre: dict, haut_px: int = HAUT_PX) -> dict | None:
    """La bande du garde-corps d'un vantail lu, mise à plat : {"fer": (haut_px, L) de 0 à 1, "vu": (haut_px, L) bool (vitre
    nue : ni rideau, ni meuble, ni barre de la fenêtre), "aspect": largeur / hauteur vraies, "face": sa hauteur sur la photo}.
    None sans garde-corps lu, ou si la photo ne montre pas le dehors par ce vantail."""
    if not fenetre.get("garde_corps") or not fenetre.get("coins") or fenetre.get("vue", "oui") != "oui":
        return None
    h_img, l_img = image.shape[:2]
    hg, hd, bd, bg = [np.array(c, float) for c in fenetre["coins"]]
    y_g, y_d = fenetre["garde_corps"]
    quad = np.array([vt._sur_le_bord(hg, bg, y_g, 1), vt._sur_le_bord(hd, bd, y_d, 1), bd, bg], np.float32)
    face = float(np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2
    if face < 25 or np.linalg.norm(quad[1] - quad[0]) < 12:
        return None  # trop petite sur la photo pour y lire un dessin
    aspect = aspect_vrai(quad, (l_img, h_img))
    largeur = max(8, int(round(haut_px * aspect)))
    m = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [largeur, 0], [largeur, haut_px], [0, haut_px]], np.float32))
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    plat = cv2.warpPerspective(gris, m, (largeur, haut_px), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    nues = vt.vitres_nues(fenetre, (l_img, h_img), marge=1.0)
    vu = cv2.warpPerspective(nues * 255, m, (largeur, haut_px), flags=cv2.INTER_LINEAR) > 127
    return {"fer": fer(plat), "vu": vu, "aspect": float(aspect), "face": face}


def _profil(b: dict) -> tuple[np.ndarray, np.ndarray]:
    """Par colonne de la bande : la part de fer (moyenne sur ce qui est vu), et si la colonne est assez vue pour compter."""
    vu = b["vu"].astype(np.float32)
    compte = vu.sum(0)
    p = (b["fer"] * vu).sum(0) / np.maximum(compte, 1.0)
    return p, compte > 0.6 * b["vu"].shape[0]


def _ressemblances(b: dict) -> dict[int, tuple[float, float]]:
    """Le profil des colonnes d'une bande (un barreau = une colonne très « fer ») comparé à lui-même décalé de d pixels :
    {d: (ressemblance de −1 à 1, nombre de colonnes comparées)}, pour les décalages qui peuvent être le pas d'un motif."""
    p, ok = _profil(b)
    h = b["fer"].shape[0]
    if ok.sum() < 8:
        return {}
    x = np.where(ok, p - p[ok].mean(), 0.0)
    notes = {}
    for d in range(int(PAS_MIN * h), min(int(PAS_MAX * h), len(p) - 4) + 1):
        ensemble = ok[:-d] & ok[d:]
        if ensemble.sum() < max(8, 0.5 * d):  # il faut voir au moins une demi-répétition en double
            continue
        a, c = x[:-d][ensemble], x[d:][ensemble]
        den = math.sqrt(float((a * a).sum() * (c * c).sum()))
        notes[d] = (float((a * c).sum()) / den if den > 1e-9 else 0.0, float(ensemble.sum()))
    return notes


def _premier_sommet(notes: dict[int, float]) -> tuple[int, float] | None:
    """Le PREMIER sommet net d'une courbe de ressemblance : le pas du motif, et non son double (qui ressemble autant)."""
    ds = sorted(notes)
    if len(ds) < 3:
        return None
    sommet = max(notes.values())
    for d0, d1, d2 in zip(ds, ds[1:], ds[2:]):
        if notes[d1] >= notes[d0] and notes[d1] >= notes[d2] and notes[d1] >= 0.75 * sommet and notes[d1] > 0.25:
            return d1, notes[d1]
    return None


def pas_commun(bandes: list[dict]) -> float | None:
    """Le PAS du motif (pixels d'une bande) d'après TOUTES les bandes d'un même garde-corps : une bande ne montre que deux ou
    trois répétitions, en partie cachées, et se trompe facilement du simple au double ; leurs courbes de ressemblance
    additionnées (chacune pesée par ce qu'elle voit) ne se trompent pas."""
    somme: dict[int, float] = {}
    poids: dict[int, float] = {}
    for b in bandes:
        for d, (note, n) in _ressemblances(b).items():
            somme[d] = somme.get(d, 0.0) + note * n
            poids[d] = poids.get(d, 0.0) + n
    if not somme:
        return None
    plein = max(poids.values())
    trouve = _premier_sommet({d: somme[d] / poids[d] for d in somme if poids[d] >= 0.4 * plein})
    return float(trouve[0]) if trouve else None


def pas_d_une_bande(b: dict, commun: float | None = None) -> tuple[float, float] | None:
    """Le pas du motif dans UNE bande (pixels) et la netteté de sa répétition (0 à 1) : son premier sommet de ressemblance ;
    ou, si le pas commun du garde-corps est connu, le sommet de CETTE bande à ECART_DE_PAS près de lui (les proportions
    redressées d'une photo à l'autre ne sont justes qu'à quelques pour cent). None si la bande ne répète rien de net."""
    notes = {d: n for d, (n, _) in _ressemblances(b).items()}
    if commun is not None:
        notes = {d: n for d, n in notes.items() if abs(d / commun - 1) <= ECART_DE_PAS}
        if not notes:
            return None
        d = max(notes, key=notes.get)
        return (float(d), float(notes[d])) if notes[d] > 0.25 else None
    trouve = _premier_sommet(notes)
    return (float(trouve[0]), float(trouve[1])) if trouve else None


def _barreaux(b: dict, pas: float) -> list[float]:
    """Les colonnes des BARREAUX d'une bande (centres des modules) : la grille de pas `pas` qui tombe sur le plus de fer."""
    p, ok = _profil(b)
    lisse = cv2.GaussianBlur(np.where(ok, p, 0.0).astype(np.float32).reshape(1, -1), (0, 0), max(1.0, 0.03 * pas)).ravel()
    n = max(1, int(round(pas)))
    notes = [float(np.mean([lisse[int(x)] for x in np.arange(d, len(p), pas) if ok[int(x)]] or [0.0])) for d in range(n)]
    depart = int(np.argmax(notes))
    return [float(x) for x in np.arange(depart, len(p), pas)]


def _correlation(a: np.ndarray, b: np.ndarray, poids: np.ndarray | None = None) -> float:
    w = np.ones_like(a, np.float32) if poids is None else poids.astype(np.float32)
    s = float(w.sum())
    if s < 1:
        return 0.0
    a0, b0 = a - float((a * w).sum()) / s, b - float((b * w).sum()) / s
    den = math.sqrt(float((a0 * a0 * w).sum() * (b0 * b0 * w).sum()))
    return float((a0 * b0 * w).sum()) / den if den > 1e-9 else 0.0


def _decaler(image: np.ndarray, dx: float, dy: float, valeur=0.0) -> np.ndarray:
    m = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
    return cv2.warpAffine(image, m, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderValue=valeur)


def module(bandes: list[dict], journal=None, repetitions_min: int = MODULES_MIN) -> dict | None:
    """Le MODULE du motif d'après toutes les bandes d'un même garde-corps : {"fer": (HAUT_PX, L) de 0 à 1 (médiane des
    répétitions, barreau au milieu), "pas": largeur du module en parts de la hauteur, "repetitions": leur nombre,
    "accord": ressemblance moyenne des répétitions avec la médiane, "symetrique": bool}. None si le motif ne se lit pas."""
    commun = pas_commun(bandes)
    if commun is None:
        return None
    mesures = [(b, m) for b in bandes if (m := pas_d_une_bande(b, commun)) is not None]
    if not mesures:
        return None
    commun = float(np.median([m[0] for _, m in mesures]))
    largeur = int(round(commun))
    h = HAUT_PX
    morceaux, vus = [], []
    for b, (pas, _) in mesures:
        for x in _barreaux(b, pas):
            x0, x1 = x - pas / 2, x + pas / 2
            m = np.array([[largeur / pas, 0, -x0 * largeur / pas], [0, 1, 0]], np.float32)
            f = cv2.warpAffine(b["fer"], m, (largeur, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            v = cv2.warpAffine(b["vu"].astype(np.float32), m, (largeur, h), flags=cv2.INTER_LINEAR)
            if v.mean() < 0.6:
                continue  # trop cachée (rideau, meuble) ou coupée par le bord du vantail
            f = f / max(float(np.percentile(f[v > 0.5], 97)), 0.05)  # chaque photo a son contraste : le fer vaut 1 partout
            morceaux.append(np.clip(f, 0, 1.5))
            vus.append(v)
    if len(morceaux) < repetitions_min:
        return None

    def mediane(ms, vs):
        pile, poids = np.stack(ms), np.stack(vs) > 0.5
        pile = np.where(poids, pile, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # un point qu'aucune répétition ne montre : pas de médiane
            med = np.nanmedian(pile, axis=0)
        return np.nan_to_num(med, nan=0.0).astype(np.float32)

    med = mediane(morceaux, vus)
    for _ in range(3):  # chaque répétition est recalée sur la médiane (le dessus du garde-corps est lu à 2 pixels près)
        recales, revus = [], []
        for f, v in zip(morceaux, vus):
            essais = [(_correlation(_decaler(f, dx, dy), med, _decaler(v, dx, dy)), dx, dy)
                      for dx in range(-int(0.08 * largeur), int(0.08 * largeur) + 1, 2) for dy in range(-int(0.06 * h), int(0.06 * h) + 1, 3)]
            _, dx, dy = max(essais)
            recales.append(_decaler(f, dx, dy))
            revus.append(_decaler(v, dx, dy))
        med = mediane(recales, revus)
    notes = [_correlation(f, med, v) for f, v in zip(recales, revus)]
    gardes = [i for i, n in enumerate(notes) if n >= 0.6 * float(np.median(notes))]
    if len(gardes) < repetitions_min:
        return None
    med = mediane([recales[i] for i in gardes], [revus[i] for i in gardes])
    # le DOUTE en chaque point : l'écart des répétitions entre elles (grand là où un rideau, un reflet, le bas de la fenêtre
    # ont brouillé une partie d'entre elles)
    pile = np.where(np.stack([revus[i] for i in gardes]) > 0.5, np.stack([recales[i] for i in gardes]), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        doute = np.nanmedian(np.abs(pile - med[None]), axis=0)
    connu = ~np.isnan(doute)  # au moins une répétition montre ce point
    doute = np.nan_to_num(doute, nan=1.0).astype(np.float32)
    accord = float(np.mean([notes[i] for i in gardes]))
    if journal:
        journal(f"motif : {len(gardes)} répétitions d'accord sur {len(morceaux)} (ressemblance {accord:.2f}), pas {commun / h:.3f} de la hauteur")
    if accord < ACCORD_MIN:
        return None
    # le barreau au milieu exact, puis la symétrie de gauche à droite
    colonnes = med[int(0.3 * h):int(0.7 * h)].mean(0)
    centre = float(np.argmax(cv2.GaussianBlur(colonnes.reshape(1, -1), (0, 0), 2).ravel()))
    med, doute, connu = (np.roll(a, int(round(largeur / 2 - centre)), axis=1) for a in (med, doute, connu))
    symetrie = _correlation(med, med[:, ::-1], connu & connu[:, ::-1])
    if symetrie >= SYMETRIE_MIN:
        poids = np.where(connu, 1.0, 0.0).astype(np.float32)
        ensemble = np.maximum(poids + poids[:, ::-1], 1e-9)
        med = (med * poids + med[:, ::-1] * poids[:, ::-1]) / ensemble
        doute = np.where(connu | connu[:, ::-1], (doute * poids + doute[:, ::-1] * poids[:, ::-1]) / ensemble, 1.0).astype(np.float32)
        connu = connu | connu[:, ::-1]
    # … puis de haut en bas : le bas d'un garde-corps est le plus mal vu (caché par la traverse basse de la fenêtre, un meuble,
    # l'appui) ; si le motif est le même en haut et en bas, chaque moitié complète l'autre, la plus sûre pesant le plus
    axe, debout = axe_de_symetrie(med, connu)
    if debout >= SYMETRIE_DEBOUT_MIN:
        med = completer_par_le_miroir(med, np.where(connu, doute, np.inf), axe)
    return {"fer": med, "pas": commun / med.shape[0], "repetitions": len(gardes), "accord": accord,
            "symetrique": symetrie >= SYMETRIE_MIN, "symetrie": float(symetrie),
            "symetrie_debout": float(debout), "axe": float(axe / h)}


def axe_de_symetrie(med: np.ndarray, connu: np.ndarray | None = None) -> tuple[int, float]:
    """La ligne autour de laquelle le module se ressemble le plus de haut en bas, et cette ressemblance (−1 à 1). Le barreau,
    pareil à toutes les hauteurs, ne compte pas : la moyenne de chaque colonne est retirée avant de comparer. Seuls comptent
    les points que les photos montrent des DEUX côtés de la ligne (`connu`) ; s'il y en a trop peu, pas de symétrie mesurée."""
    h, l = med.shape
    connu = np.ones((h, l), bool) if connu is None else connu
    compte = np.maximum(connu.sum(0, keepdims=True), 1)
    sans_barreau = np.where(connu, med - (med * connu).sum(0, keepdims=True) / compte, 0.0)
    meilleur = (h // 2, -1.0)
    for a in range(int(0.38 * h), int(0.72 * h) + 1):
        n = min(a, h - a)
        deux = connu[a - n:a][::-1] & connu[a:a + n]
        if deux.sum() < 0.12 * h * l:
            continue
        note = _correlation(sans_barreau[a - n:a][::-1], sans_barreau[a:a + n], deux)
        if note > meilleur[1]:
            meilleur = (a, note)
    return meilleur


def completer_par_le_miroir(med: np.ndarray, doute: np.ndarray, axe: int) -> np.ndarray:
    """Le module rendu symétrique autour de la ligne `axe` : (2 × axe) lignes. En chaque point, la moyenne du point et de son
    miroir, pesés par l'inverse de leur doute ; au-delà de ce que la photo montre (axe plus bas que le milieu), le miroir seul."""
    h, l = med.shape
    total = 2 * axe
    valeur = np.zeros((total, l), np.float32)
    poids = np.zeros((total, l), np.float32)
    n = min(h, total)
    valeur[:n], poids[:n] = med[:n], 1.0 / (doute[:n] + 0.04) ** 2  # un point jamais vu (doute infini) ne pèse rien
    v2, p2 = valeur[::-1], poids[::-1]
    return ((valeur * poids + v2 * p2) / np.maximum(poids + p2, 1e-9)).astype(np.float32)


def _relier(plein: np.ndarray, large: np.ndarray, k: int) -> np.ndarray:
    """Aucun morceau de fer ne FLOTTE : dans une vraie ferronnerie tout tient à la main courante ou à la lisse basse. La mise
    au trait perd les fers les plus fins (la spirale qui mène au bout d'une volute) : le bout reste seul en l'air, ce qui se
    verrait de près dans la visite. Chaque morceau qui ne tient ni au haut ni au bas du module (directement ou par un autre
    morceau) est relié au fer tenu par le chemin le plus SOMBRE de la carte du fer (`large`, la même que `plein`, trois
    modules côte à côte) : là où la photo montrait le fer fin. Rend `plein` complété (les trois modules, mêmes ponts)."""
    h, l3 = plein.shape
    l = l3 // 3
    nombre, etiquettes, stats, centres = cv2.connectedComponentsWithStats(plein, connectivity=8)
    marge = max(1, int(round(0.02 * h)))
    tenus = (set(np.unique(etiquettes[:marge])) | set(np.unique(etiquettes[-marge:]))) - {0}
    flottants = [e for e in range(1, nombre) if e not in tenus and stats[e, cv2.CC_STAT_AREA] >= 0.00015 * h * l
                 and l <= centres[e][0] < 2 * l]
    if not flottants or not tenus:
        return plein
    hb, lb = h // k, l3 // k
    petit = cv2.resize(large, (lb, hb), interpolation=cv2.INTER_AREA)
    cout = 1.0 / (petit / max(float(petit.max()), 1e-9) + 0.05)  # passer dans le sombre coûte peu

    def en_petit(masque: np.ndarray) -> np.ndarray:
        return cv2.resize(masque.astype(np.uint8) * 255, (lb, hb), interpolation=cv2.INTER_AREA) > 0

    depart = en_petit(np.isin(etiquettes, list(tenus)))
    loin = np.full((hb, lb), np.inf)
    d_ou = np.full((hb, lb, 2), -1, np.int32)
    tas = [(0.0, int(y), int(x)) for y, x in zip(*np.nonzero(depart))]
    for _, y, x in tas:
        loin[y, x] = 0.0
    heapq.heapify(tas)
    voisins = [(dy, dx, math.hypot(dy, dx)) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    while tas:
        d, y, x = heapq.heappop(tas)
        if d > loin[y, x]:
            continue
        for dy, dx, pas in voisins:
            yy, xx = y + dy, x + dx
            if 0 <= yy < hb and 0 <= xx < lb:
                nd = d + pas * float(cout[yy, xx])
                if nd < loin[yy, xx]:
                    loin[yy, xx] = nd
                    d_ou[yy, xx] = (y, x)
                    heapq.heappush(tas, (nd, yy, xx))
    sortie = plein.copy()
    trait = max(2, int(round(0.012 * h)))
    for e in flottants:
        ys, xs = np.nonzero(en_petit(etiquettes == e))
        if not len(ys):
            continue
        i = int(np.argmin(loin[ys, xs]))
        y, x = int(ys[i]), int(xs[i])
        chemin = [(x, y)]
        while d_ou[y, x][0] >= 0:
            y, x = (int(v) for v in d_ou[y, x])
            chemin.append((x, y))
        points = (np.array(chemin, np.float64) * k + k / 2).round().astype(np.int32)
        for decalage in (-l, 0, l):
            cv2.polylines(sortie, [points + np.array([decalage, 0], np.int32)], False, 1, trait, cv2.LINE_8)
    return sortie


def contours(fer_du_module: np.ndarray, seuil: float | None = None) -> list[list[tuple[float, float]]]:
    """Les CONTOURS fermés du fer d'un module : pleins et trous mêlés (un point est dans le fer s'il est dans un nombre impair
    de contours). x en parts de la largeur du module (0 à 1), y en parts de la hauteur, 0 en BAS. Le module est agrandi et
    adouci avant d'être mis au trait : des courbes, pas des marches d'escalier.

    Mise au trait : le flou de la photo colle deux fers voisins (une volute et son barreau) ; un seuil unique les fond en une
    tache. Un point est donc du fer s'il est presque aussi sombre (PART_DU_TRAIT) que le plus sombre des points à moins de
    RAYON_DU_TRAIT de lui : le creux entre deux fers, plus clair qu'eux, redevient un vide. `seuil` : un seuil unique, pour
    un essai."""
    k = 3
    grand = cv2.resize(fer_du_module, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    # répété de chaque côté avant d'adoucir : le bord du module se raccorde au module voisin
    large = np.hstack([grand, grand, grand])
    large = cv2.GaussianBlur(large, (0, 0), 1.0 * k)
    if seuil is None:
        cote = 2 * max(1, int(round(RAYON_DU_TRAIT * HAUT_PX * k))) + 1
        autour = cv2.dilate(large, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cote, cote)))
        plein = (large >= PART_DU_TRAIT * autour) & (large >= FER_FAIBLE * float(large.max()))
    else:
        plein = large >= seuil
    plein = cv2.morphologyEx(plein.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))  # les miettes
    plein = _relier(plein, large, k)
    plein = plein[:, grand.shape[1]:2 * grand.shape[1]]
    trouves, _ = cv2.findContours(plein, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    h, l = plein.shape
    sortie = []
    for c in trouves:
        if cv2.contourArea(c) < 0.00015 * h * l:
            continue  # une miette, un trou d'épingle
        c = cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2).astype(float)
        if len(c) >= 3:
            sortie.append([(round(float(x + 0.5) / l, 4), round(1 - float(y + 0.5) / h, 4)) for x, y in c])
    return sortie


def dessiner(motif: dict, largeur_px: int, haut_px: int, repetitions: int = 1) -> np.ndarray:
    """Le motif (ses contours) redessiné en image : (haut_px, repetitions × largeur_px) uint8, 1 dans le fer."""
    image = np.zeros((haut_px, largeur_px), np.uint8)
    polys = [np.round(np.array([[x * largeur_px - 0.5, (1 - y) * haut_px - 0.5] for x, y in c]) * 16).astype(np.int32)
             for c in motif["contours"]]
    cv2.fillPoly(image, polys, 1, lineType=cv2.LINE_8, shift=4)  # règle pair-impair : les trous restent des trous
    return np.tile(image, (1, repetitions))


def panneau(motif: dict, largeur: float, hauteur: float, pixel: float = 0.0015) -> list[dict]:
    """Le garde-corps entier d'une baie : le module répété un nombre ENTIER de fois sur `largeur` (m ; il est étiré ou serré
    de quelques pour cent pour tomber juste), sur `hauteur` (m). Rend les morceaux de fer, chacun {"contour": [(x, z) …],
    "trous": [[(x, z) …] …]} en mètres, x de 0 à largeur, z de 0 (bas) à hauteur. Dessiné à `pixel` mètres près."""
    nombre = max(1, int(round(largeur / (motif["pas"] * hauteur))))
    l_px = max(16, int(round(largeur / nombre / pixel)))
    h_px = max(16, int(round(hauteur / pixel)))
    image = dessiner(motif, l_px, h_px, nombre)
    image = cv2.copyMakeBorder(image, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    trouves, hierarchie = cv2.findContours(image, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchie is None:
        return []
    ex, ez = largeur / (nombre * l_px), hauteur / h_px

    def en_metres(c):
        c = cv2.approxPolyDP(c, 0.35, True).reshape(-1, 2).astype(float)
        return [(round(float(x - 1 + 0.5) * ex, 5), round(hauteur - float(y - 1 + 0.5) * ez, 5)) for x, y in c]

    morceaux = {}
    for i, (c, (_, _, _, parent)) in enumerate(zip(trouves, hierarchie[0])):
        if parent < 0 and len(c) >= 3 and cv2.contourArea(c) >= 6:
            morceaux[i] = {"contour": en_metres(c), "trous": []}
    for i, (c, (_, _, _, parent)) in enumerate(zip(trouves, hierarchie[0])):
        if parent in morceaux and len(c) >= 3 and cv2.contourArea(c) >= 4:
            morceaux[parent]["trous"].append(en_metres(c))
    return [m for m in morceaux.values() if len(m["contour"]) >= 3]


def lire(logement: dict, lecture: dict | None, photos: str | Path, journal=None) -> dict[str, dict]:
    """Pour chaque baie dont le dessin a un garde-corps et dont les photos montrent la ferronnerie : {id de la baie: motif
    (MotifFerronnerie en dict)}. Les garde-corps d'un même logement qui montrent le même motif (même pas à ECART_DE_PAS près)
    sont lus ENSEMBLE : toutes leurs répétitions servent au même module."""
    photos = Path(photos)
    par_baie: dict[str, list[dict]] = {}
    sources: dict[str, list[str]] = {}
    for photo, fenetres in sorted(((lecture or {}).get("photos") or {}).items()):
        lues = [f for f in fenetres if f.get("garde_corps") and f.get("coins") and f.get("vue", "oui") == "oui"]
        if not lues:
            continue
        chemin = next((c for c in (photos / f"{photo}{ext}" for ext in (".jpg", ".jpeg", ".png", ".webp")) if c.exists()), None)
        if chemin is None:
            if journal:
                journal(f"{photo} : photo introuvable dans {photos} (garde-corps non lu)")
            continue
        image = lire_image(chemin)
        if image is None:
            continue
        for f in lues:
            b = bande(image, f)
            if b is not None:
                par_baie.setdefault(f["baie"], []).append(b)
                if photo not in sources.setdefault(f["baie"], []):
                    sources[f["baie"]].append(photo)
    concernees = [o["id"] for o in logement.get("ouvertures", [])
                  if o["id"] in par_baie and ((o.get("dessin") or {}).get("garde_corps") or {}).get("genre") in ("fer_forge", "barreaudage")]
    if not concernees:
        return {}
    # un seul motif pour le logement si les baies s'accordent (même immeuble, même fonderie), sinon un par baie
    groupes = [concernees]
    ensemble = module([b for i in concernees for b in par_baie[i]], journal)
    if ensemble is None and len(concernees) > 1:
        groupes = [[i] for i in concernees]
    sortie = {}
    for groupe in groupes:
        m = ensemble if groupe is concernees else module([b for i in groupe for b in par_baie[i]], journal)
        if m is None:
            continue
        c = contours(m["fer"])
        if not c:
            continue
        vues = sorted({p for i in groupe for p in sources[i]})
        motif = {"pas": round(m["pas"], 4), "contours": c, "statut": "estime",
                 "source": f"photos (ferronnerie recopiée de {', '.join(vues)} ; {m['repetitions']} répétitions)",
                 "confiance": round(min(0.9, max(0.3, m["accord"])), 2)}
        for i in groupe:
            sortie[i] = motif
    return sortie


def appliquer(logement: dict, lecture: dict | None, photos: str | Path, journal=None) -> tuple[dict, list[dict]]:
    """Le logement avec le MOTIF de la ferronnerie de chaque garde-corps de fenêtre que les photos montrent
    (ouverture.dessin.garde_corps.motif), et la liste de ce qui a été posé. Rien n'est touché sans motif lisible."""
    logement = copy.deepcopy(logement)
    motifs = lire(logement, lecture, photos, journal)
    poses = []
    for o in logement.get("ouvertures", []):
        m = motifs.get(o["id"])
        if m is None or (o.get("dessin") or {}).get("statut") == "mesure":
            continue
        o["dessin"]["garde_corps"]["motif"] = m
        poses.append({"baie": o["id"], "pas": m["pas"], "contours": len(m["contours"]), "source": m["source"]})
        if journal:
            journal(f"{o['id']} : ferronnerie du garde-corps recopiée des photos ({len(m['contours'])} contours)")
    return logement, poses
