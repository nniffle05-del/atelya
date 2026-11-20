r"""LE DESSIN DE CHAQUE FENÊTRE LU SUR LES PHOTOS : où sont ses VITRES (F2, « une vue propre par les fenêtres », 20/11/2026).

Pourquoi. La vue par les fenêtres du film est peinte d'après les photos du client : tout ce qu'une photo montre dans le trou
d'une fenêtre était pris pour le dehors et peint au loin (à 35 m). Or dans ce trou il y a aussi des choses qui sont À LA
FENÊTRE : les montants et les petits bois, un battant ouvert, le rideau, une plante, la marque de l'agence. Dans le film on les
voyait flotter dans la vue, en double des montants de la maquette. Et le trou lui-même, placé d'après le plan et la place de
l'appareil (connue à 30-50 cm), tombait souvent à côté de la vraie fenêtre de la photo (un cinquième de sa largeur sur app-004).

Essai écarté (mesuré) : le relief de la photo (MoGe-2) voit la vitre comme une surface plate, à la distance du mur ; il ne
sépare pas un immeuble d'en face d'un montant (pc/verification/sonde_profondeur_dehors.py).

Moyen retenu : comme pour le plan et pour les meubles, la LECTURE dit le sens, Atelya garde la géométrie. Atelya montre chaque
fenêtre claire de chaque photo, en grand, avec une règle graduée en pixels de la photo (outils/lecture_photos/
preparer_vitrages.py). La lecture rend le DESSIN de la fenêtre :
  - `coins` : les quatre coins d'un vitrage (le bord intérieur de son cadre), dans l'ordre haut-gauche, haut-droit,
    bas-droit, bas-gauche, en pixels de la photo. Une fenêtre peut être dite en PLUSIEURS vitrages (un par vantail : deux
    battants qui ne sont pas tout à fait dans le même plan, un coulissant devant l'autre) ;
  - `montants` : chaque barre verticale (battement du milieu, petits bois) : [x en haut bord gauche, x en haut bord droit,
    x en bas bord gauche, x en bas bord droit] : là où la barre coupe le bord du HAUT puis le bord du BAS du vitrage ;
  - `traverses` : chaque barre horizontale : [y à gauche bord haut, y à gauche bord bas, y à droite bord haut, y à droite bord
    bas] : là où elle coupe le bord GAUCHE puis le bord DROIT du vitrage ;
  - `caches` : ce qui cache le vitrage et n'est pas le dehors (rideau, plante, poignée, marque de l'agence, meuble, sol et
    muret plein d'un balcon) : rectangles [x0, y0, x1, y1] ou polygones [[x, y], …] ;
  - `vue` : « oui » (défaut), « non » (cette photo ne montre pas le dehors par cette fenêtre : trop coupée, cachée), ou
    « lueur » (vitrage dépoli : on ne voit qu'une clarté, comme derrière un voilage).
Atelya en tire le masque des VITRES NUES (le quadrilatère moins les barres et les caches) : seuls ces pixels peignent la vue.
Le même dessin dit aussi combien de vantaux et de petits bois a la vraie fenêtre (pour la maquette : `partage`).

Chaque lecture est gardée : ce sont les leçons du futur lecteur d'Atelya (décision de NT du 16/11/2026).

Format « vitrages-photos/0.1 » :
    {"format": "vitrages-photos/0.1", "photos": {"photo-10": [{"baie": "O7", "coins": [[x, y] × 4], "montants": [[…] …],
                                                              "traverses": [[…] …], "caches": [[…] …], "vue": "oui"}, …]}}
"""
from __future__ import annotations

import cv2
import numpy as np

VERSION = "0.1.0"
FORMAT = "vitrages-photos/0.1"
MARGE_PX = 4.0  # les vitres sont rétrécies d'autant, et les barres élargies (lecture à 2-3 pixels près ; photo de 1206 px de large)
AUTOUR_DES_BARRES = 3.0  # pixels comblés en plus de chaque côté d'une barre (son bord flou sur la photo)
ENTRE_VANTAUX_MAX = 45.0  # pixels : le battement entre deux vantaux est comblé s'il est plus mince (au-delà : un trumeau, un mur)
VUES = ("oui", "non", "lueur")


def consigne() -> str:
    """Ce qu'on demande à la lecture, pour chaque image de fenêtre préparée par Atelya."""
    return (
        "Chaque image montre UNE fenêtre d'une photo, agrandie, avec une règle graduée : les nombres sont des pixels de la photo "
        "entière. Pour cette fenêtre, rendre :\n"
        "- coins : les quatre coins du vitrage (le bord intérieur de son cadre, là où commencent les vitres), dans l'ordre "
        "haut-gauche, haut-droit, bas-droit, bas-gauche. Si un coin est caché ou hors de l'image, l'estimer en prolongeant les "
        "bords. Dire UN VITRAGE PAR VANTAIL (deux battants, deux coulissants : deux vitrages de la même baie).\n"
        "- montants : chaque barre verticale entre deux vitres (le battement du milieu, les petits bois) : x de son bord gauche et "
        "de son bord droit là où elle coupe le bord du haut du vitrage, puis les mêmes là où elle coupe le bord du bas.\n"
        "- traverses : chaque barre horizontale : y de son bord haut et de son bord bas là où elle coupe le bord gauche du "
        "vitrage, puis les mêmes là où elle coupe le bord droit.\n"
        "- caches : tout ce qui cache une vitre et n'est pas le dehors : rideau, plante, poignée, marque de l'agence, meuble, "
        "battant ouvert, toile ou moustiquaire, muret plein et sol d'un balcon : un rectangle [x0, y0, x1, y1] ou un polygone.\n"
        "- vue : « oui » si l'on voit le dehors à travers les vitres ; « lueur » si le vitrage est dépoli ; « non » si la "
        "fenêtre est trop coupée ou trop cachée pour montrer le dehors.\n"
        "Ne rien inventer : une barre que l'on ne voit pas n'est pas dite. Le garde-corps (dehors, devant la fenêtre) n'est pas "
        "une barre de la fenêtre : le signaler par « garde_corps » : y de son bord haut à gauche et à droite du vitrage."
    )


def controler(lecture: dict, tailles: dict[str, tuple[int, int]] | None = None, baies: set[str] | None = None) -> list[str]:
    """Les défauts d'une lecture des vitrages (liste vide = bonne) : format, coins dans l'ordre, barres dans le vitrage."""
    defauts = []
    if lecture.get("format") != FORMAT:
        defauts.append(f"format {lecture.get('format')!r} au lieu de {FORMAT!r}")
    for photo, fenetres in (lecture.get("photos") or {}).items():
        dit: dict[str, set[str]] = {}
        for f in fenetres:
            ou = f"{photo} {f.get('baie')}"
            if not f.get("baie"):
                defauts.append(f"{photo} : fenêtre sans « baie »")
                continue
            dit.setdefault(f["baie"], set()).add(f.get("vue", "oui"))
            if len(dit[f["baie"]]) > 1:
                defauts.append(f"{ou} : dite à la fois {' et '.join(sorted(dit[f['baie']]))}")
            if baies is not None and f["baie"] not in baies:
                defauts.append(f"{ou} : baie inconnue du logement")
            if f.get("vue", "oui") not in VUES:
                defauts.append(f"{ou} : vue {f.get('vue')!r} (attendu : {', '.join(VUES)})")
            if f.get("vue", "oui") != "oui" and not f.get("coins"):
                continue
            coins = f.get("coins")
            if not (isinstance(coins, list) and len(coins) == 4 and all(len(c) == 2 for c in coins)):
                defauts.append(f"{ou} : il faut 4 coins [x, y]")
                continue
            (hg, hd, bd, bg) = [np.array(c, float) for c in coins]
            if not (hg[0] < hd[0] and bg[0] < bd[0] and hg[1] < bg[1] and hd[1] < bd[1]):
                defauts.append(f"{ou} : coins dans le désordre (haut-gauche, haut-droit, bas-droit, bas-gauche)")
                continue
            aire = 0.5 * abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip((hg, hd, bd, bg), (hd, bd, bg, hg))))
            if aire < 400:
                defauts.append(f"{ou} : vitrage minuscule ({aire:.0f} px²)")
            if tailles and photo in tailles:
                w, h = tailles[photo]
                if any(c[0] < -0.5 * w or c[0] > 1.5 * w or c[1] < -0.5 * h or c[1] > 1.5 * h for c in (hg, hd, bd, bg)):
                    defauts.append(f"{ou} : un coin est très loin hors de la photo")
            for nom, k, lo, hi in (("montants", 0, min(hg[0], bg[0]), max(hd[0], bd[0])),
                                   ("traverses", 1, min(hg[1], hd[1]), max(bg[1], bd[1]))):
                for b in f.get(nom) or []:
                    if len(b) != 4:
                        defauts.append(f"{ou} : une barre de « {nom} » a 4 nombres")
                    elif not (b[0] < b[1] and b[2] < b[3]):
                        defauts.append(f"{ou} : barre {b} de « {nom} » : bords dans le désordre")
                    elif min(b) < lo - 15 or max(b) > hi + 15:
                        defauts.append(f"{ou} : barre {b} de « {nom} » hors du vitrage")
            for c in f.get("caches") or []:
                if _polygone(c) is None:
                    defauts.append(f"{ou} : cache {c} : attendu [x0, y0, x1, y1] ou [[x, y], …]")
    return defauts


def _polygone(cache) -> np.ndarray | None:
    """Un cache (rectangle [x0, y0, x1, y1] ou polygone [[x, y], …]) en polygone (N × 2), None s'il est mal écrit."""
    try:
        if len(cache) == 4 and all(isinstance(v, (int, float)) for v in cache):
            x0, y0, x1, y1 = (float(v) for v in cache)
            return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) if x0 < x1 and y0 < y1 else None
        pts = np.array(cache, float)
        return pts if pts.ndim == 2 and pts.shape[1] == 2 and len(pts) >= 3 else None
    except (TypeError, ValueError):
        return None


def _sur_le_bord(a: np.ndarray, b: np.ndarray, valeur: float, axe: int) -> np.ndarray:
    """Le point de la droite (a, b) dont la coordonnée `axe` vaut `valeur` (bord du haut ou du bas : axe 0 ; gauche, droit : 1)."""
    d = b - a
    if abs(d[axe]) < 1e-9:
        return a.copy()
    return a + d * ((valeur - a[axe]) / d[axe])


def barres(fenetre: dict) -> list[np.ndarray]:
    """Les barres de la fenêtre, chacune en quadrilatère (4 × 2, pixels de la photo)."""
    hg, hd, bd, bg = [np.array(c, float) for c in fenetre["coins"]]
    res = []
    for g_h, d_h, g_b, d_b in fenetre.get("montants") or []:
        res.append(np.array([_sur_le_bord(hg, hd, g_h, 0), _sur_le_bord(hg, hd, d_h, 0),
                             _sur_le_bord(bg, bd, d_b, 0), _sur_le_bord(bg, bd, g_b, 0)]))
    for h_g, b_g, h_d, b_d in fenetre.get("traverses") or []:
        res.append(np.array([_sur_le_bord(hg, bg, h_g, 1), _sur_le_bord(hd, bd, h_d, 1),
                             _sur_le_bord(hd, bd, b_d, 1), _sur_le_bord(hg, bg, b_g, 1)]))
    return res


def _remplir(masque: np.ndarray, quad: np.ndarray, valeur: int) -> None:
    cv2.fillPoly(masque, [np.round(np.asarray(quad, float) * 4).astype(np.int32)], valeur, lineType=cv2.LINE_8, shift=2)


def masque_du_vitrage(fenetre: dict, taille: tuple[int, int]) -> np.ndarray:
    """(H, L) uint8 : 1 dans le vitrage ENTIER de la fenêtre (vitres et barres), rien n'est retiré."""
    largeur, hauteur = taille
    m = np.zeros((hauteur, largeur), np.uint8)
    if fenetre.get("vue", "oui") != "non" and fenetre.get("coins"):
        _remplir(m, np.array(fenetre["coins"], float), 1)
    return m


def vitres_nues(fenetre: dict, taille: tuple[int, int], marge: float | None = None) -> np.ndarray:
    """(H, L) uint8 : 1 là où la photo montre le DEHORS à travers une vitre de cette fenêtre : le vitrage rétréci de `marge`,
    sans ses barres (élargies de `marge`) ni ses caches. Vide si la lecture dit « non » ou « lueur »."""
    largeur, hauteur = taille
    if fenetre.get("vue", "oui") != "oui":
        return np.zeros((hauteur, largeur), np.uint8)
    marge = MARGE_PX * largeur / 1206.0 if marge is None else marge
    k = max(0, int(np.ceil(marge)))
    noyau = np.ones((2 * k + 1, 2 * k + 1), np.uint8)
    m = masque_du_vitrage(fenetre, taille)
    if k:
        m = cv2.erode(m, noyau)
    plein = np.zeros_like(m)
    for q in barres(fenetre):
        _remplir(plein, q, 1)
    for c in fenetre.get("caches") or []:
        _remplir(plein, _polygone(c), 1)
    if k and plein.any():
        plein = cv2.dilate(plein, noyau)
    m[plein > 0] = 0
    # le garde-corps (« garde_corps ») est DEHORS, devant la fenêtre : il reste dans la vue tant que la maquette n'en construit pas
    return m


def d_une_photo(lecture: dict | None, photo: str, taille: tuple[int, int]) -> dict[str, dict]:
    """Pour chaque fenêtre lue sur cette photo : {id de la baie: {"vue": « oui » / « non » / « lueur », "vitres": masque des
    vitres nues, "vitrage": masque du vitrage entier, "debout" et "couchees" : ses barres minces à combler (barres_a_combler)}}.
    Une fenêtre absente de la lecture n'y est pas (ancien comportement)."""
    res: dict[str, dict] = {}
    vantaux: dict[str, list[dict]] = {}
    for f in ((lecture or {}).get("photos") or {}).get(photo) or []:
        nues, entier = vitres_nues(f, taille), masque_du_vitrage(f, taille)
        if f["baie"] in res:  # un autre vantail de la même fenêtre
            res[f["baie"]]["vitres"] |= nues
            res[f["baie"]]["vitrage"] |= entier
        else:
            res[f["baie"]] = {"vue": f.get("vue", "oui"), "vitres": nues, "vitrage": entier}
        if f.get("vue", "oui") == "oui":
            vantaux.setdefault(f["baie"], []).append(f)
    for baie, fs in vantaux.items():
        res[baie]["debout"], res[baie]["couchees"] = barres_a_combler(fs, taille)
        res[baie]["vitrage"] |= res[baie]["debout"] | res[baie]["couchees"]
    return res


def barres_a_combler(vantaux: list[dict], taille: tuple[int, int], marge: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Les BARRES MINCES d'une fenêtre, derrière lesquelles le dehors continue : (debout, couchées), deux masques (H, L) uint8.
    Debout : ses montants et le battement entre deux vantaux voisins (s'il fait moins d'ENTRE_VANTAUX_MAX) ; couchées : ses
    traverses. Sans les caches, ni leurs abords (un rideau ne doit pas baver dans la vue). Ces pixels seront COMBLÉS d'après
    les vitres qui les bordent (combler) : une bande floue en travers de la vue se voyait plus qu'une barre de 5 cm prolongée."""
    largeur, hauteur = taille
    marge = MARGE_PX * largeur / 1206.0 if marge is None else marge
    k = max(1, int(np.ceil(marge)))
    noyau = np.ones((2 * k + 1, 2 * k + 1), np.uint8)
    debout = np.zeros((hauteur, largeur), np.uint8)
    couchees = np.zeros((hauteur, largeur), np.uint8)
    caches = np.zeros((hauteur, largeur), np.uint8)
    dedans = np.zeros((hauteur, largeur), np.uint8)
    for f in vantaux:
        dedans |= cv2.erode(masque_du_vitrage(f, taille), noyau)
        n = len(f.get("montants") or [])
        for i, q in enumerate(barres(f)):
            _remplir(debout if i < n else couchees, q, 1)
        for c in f.get("caches") or []:
            _remplir(caches, _polygone(c), 1)
    # le bord d'une barre est flou sur la photo (3 à 4 pixels de gris) : on comble LARGE (AUTOUR_DES_BARRES de plus), sinon ce
    # gris est recopié dans toute la barre (traînée grise à la place du battement, vue le 20/11/2026)
    k3 = k + max(1, int(round(AUTOUR_DES_BARRES * largeur / 1206.0)))
    large = np.ones((2 * k3 + 1, 2 * k3 + 1), np.uint8)
    debout = cv2.dilate(debout, large) & dedans
    couchees = cv2.dilate(couchees, large) & dedans
    ordre = sorted(vantaux, key=lambda f: f["coins"][0][0])
    for g, d in zip(ordre, ordre[1:]):
        (_, g_hd, g_bd, _), (d_hg, _, _, d_bg) = (np.array(f["coins"], float) for f in (g, d))
        ecart = ((d_hg[0] - g_hd[0]) + (d_bg[0] - g_bd[0])) / 2
        if 0 < ecart <= ENTRE_VANTAUX_MAX * largeur / 1206.0:
            entre = np.zeros((hauteur, largeur), np.uint8)
            _remplir(entre, np.array([g_hd, d_hg, d_bg, g_bd]), 1)
            haut_bas = np.ones((2 * k + 1, 1), np.uint8)  # rétréci en haut et en bas comme les vitres, élargi sur les côtés
            debout |= cv2.dilate(cv2.erode(entre, haut_bas), np.ones((1, 2 * k3 + 1), np.uint8))
    if caches.any():
        k2 = 2 * k + 6
        pres = cv2.dilate(caches, np.ones((2 * k2 + 1, 2 * k2 + 1), np.uint8)) > 0
        debout[pres] = 0
        couchees[pres] = 0
    return debout, couchees


def _combler_le_long(image: np.ndarray, masque: np.ndarray, valide: np.ndarray, pris: int = 3) -> np.ndarray:
    """Comble `image` (H, L, 3) sur `masque`, ligne par ligne : chaque suite de pixels à combler prend la couleur de ses deux
    bouts (moyenne des `pris` pixels VALIDES qui la bordent), fondue de l'un à l'autre ; un seul bout valide : sa couleur ;
    aucun : rien n'est comblé. Rend le masque de ce qui a été comblé ; `image` et `valide` sont modifiés."""
    fait = np.zeros_like(masque)
    largeur = masque.shape[1]
    for y in np.nonzero(masque.any(1))[0]:
        ligne = masque[y] > 0
        bords = np.flatnonzero(np.diff(np.concatenate([[0], ligne.view(np.int8), [0]])))
        for x0, x1 in zip(bords[::2], bords[1::2]):  # [x0, x1[
            g = [x for x in range(max(0, x0 - pris), x0) if valide[y, x]]
            d = [x for x in range(x1, min(largeur, x1 + pris)) if valide[y, x]]
            if not g and not d:
                continue
            cg = image[y, g].astype(np.float32).mean(0) if g else None
            cd = image[y, d].astype(np.float32).mean(0) if d else None
            if cg is None or cd is None:
                image[y, x0:x1] = np.round(cg if cd is None else cd).astype(image.dtype)
            else:
                part = ((np.arange(x0, x1) - x0 + 0.5) / (x1 - x0))[:, None]
                image[y, x0:x1] = np.round(cg * (1 - part) + cd * part).astype(image.dtype)
            fait[y, x0:x1] = 1
    valide |= fait > 0
    return fait


def combler(image: np.ndarray, debout: np.ndarray, couchees: np.ndarray, vitres: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """La photo dont les barres minces sont COMBLÉES d'après les vitres qui les bordent, et le masque de ce qui l'a été.
    Une barre couchée (traverse) est comblée de haut en bas, une barre debout (montant, battement) de gauche à droite : chaque
    point prend la couleur des deux vitres voisines, fondue de l'une à l'autre. Les lignes des immeubles d'en face (corniches,
    balcons, bords de fenêtres) se prolongent ainsi droit derrière la barre ; un comblement « flou » (cv2.inpaint) y laissait
    une traînée grise. Rien n'est comblé là où aucune vitre ne borde la barre."""
    sortie = np.ascontiguousarray(image).copy()
    valide = vitres > 0
    fait = np.zeros(vitres.shape, np.uint8)
    if couchees.any():  # de haut en bas : on tourne l'image d'un quart de tour, on comble le long des lignes, on la retourne
        tournee, v = np.ascontiguousarray(sortie.transpose(1, 0, 2)), np.ascontiguousarray(valide.T)
        f = _combler_le_long(tournee, np.ascontiguousarray((couchees & ~debout).T), v)
        sortie, valide = np.ascontiguousarray(tournee.transpose(1, 0, 2)), np.ascontiguousarray(v.T)
        fait |= np.ascontiguousarray(f.T)
    if debout.any():
        fait |= _combler_le_long(sortie, debout, valide)
    return sortie, fait


def depolies(lecture: dict | None) -> set[str]:
    """Les baies dont au moins une photo dit le vitrage DÉPOLI (« lueur ») et aucune ne montre le dehors."""
    dit: dict[str, set[str]] = {}
    for fenetres in ((lecture or {}).get("photos") or {}).values():
        for f in fenetres:
            dit.setdefault(f["baie"], set()).add(f.get("vue", "oui"))
    return {b for b, v in dit.items() if "lueur" in v and "oui" not in v}


def partage(fenetre: dict) -> dict | None:
    """Le PARTAGE de la vraie fenêtre d'après son dessin, dans le plan de la fenêtre (parts de 0 à 1, redressées de la
    perspective) : {"montants": [(début, fin) …] de gauche à droite, "traverses": [(début, fin) …] de haut en bas}. Sert à
    construire dans la maquette les mêmes vantaux et petits bois que sur la photo. None sans dessin."""
    if fenetre.get("vue", "oui") == "non" or not fenetre.get("coins"):
        return None
    coins = np.array(fenetre["coins"], np.float32)
    vers_carre = cv2.getPerspectiveTransform(coins, np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32))

    def au_carre(p):
        return cv2.perspectiveTransform(np.array([[p]], np.float32), vers_carre)[0, 0]

    hg, hd, bd, bg = [np.array(c, float) for c in fenetre["coins"]]
    montants, traverses = [], []
    for g_h, d_h, g_b, d_b in fenetre.get("montants") or []:
        a = [au_carre(_sur_le_bord(hg, hd, x, 0))[0] for x in (g_h, d_h)] + [au_carre(_sur_le_bord(bg, bd, x, 0))[0] for x in (g_b, d_b)]
        montants.append((round(float((a[0] + a[2]) / 2), 3), round(float((a[1] + a[3]) / 2), 3)))
    for h_g, b_g, h_d, b_d in fenetre.get("traverses") or []:
        a = [au_carre(_sur_le_bord(hg, bg, y, 1))[1] for y in (h_g, b_g)] + [au_carre(_sur_le_bord(hd, bd, y, 1))[1] for y in (h_d, b_d)]
        traverses.append((round(float((a[0] + a[2]) / 2), 3), round(float((a[1] + a[3]) / 2), 3)))
    return {"montants": sorted(montants), "traverses": sorted(traverses)}
