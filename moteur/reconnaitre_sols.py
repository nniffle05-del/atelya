"""Brique photos : reconnaître le sol sur les photos du client, sans aide (09/11/2026).

Le sol de chaque photo est d'abord mis à plat (moteur/sol_a_plat.py : vue de dessus, 1 cm par pixel). On le découpe en
« vignettes » de VIGNETTE_M × VIGNETTE_M mètres ; l'œil DINOv2 (moteur/oeil_dinov2.py) donne l'empreinte de chacune, et un
petit classificateur appris (une couche de calcul, « régression logistique ») dit à quelle FAMILLE de sol elle ressemble :
lames droites, point de Hongrie, bâtons rompus ou carreaux. Chaque endroit du sol est vu par plusieurs vignettes et souvent
par plusieurs photos : leurs avis sont additionnés, pondérés par la finesse (une photo qui voit le sol de près compte plus).

Pourquoi des familles : c'est ce qui se voit et se compte sans discussion (des chevrons ou des lames), et ce qui change le
plus l'image ; le choix exact de la matière dans la famille et sa couleur viennent ensuite (couleur mesurée sur la photo).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from moteur.matieres import NOMS_SOLS

FAMILLES = ("lames", "point_de_hongrie", "batons_rompus", "carreaux")
MEUBLE = "meuble"  # 5e réponse apprise (09/11/2026) : « ceci n'est pas du sol » (meuble, tapis étiré par la mise à plat)
CLASSES_AVEC_MEUBLE = (*FAMILLES, MEUBLE)
_FAMILLE = {
    "point_de_hongrie": "point_de_hongrie", "hongrie_naturel": "point_de_hongrie", "hongrie_grise": "point_de_hongrie",
    "parquet_batons_rompus": "batons_rompus", "batons_rompus_clair": "batons_rompus", "batons_rompus_tres_clair": "batons_rompus",
}
VIGNETTE_M = 1.0  # côté d'une vignette de sol (m) : quelques lames ou deux à trois rangs de chevrons
VIGNETTE_PX = 224  # taille donnée à l'œil (16 carrés de 14 px) : 0,45 cm par pixel
PAS_M = 0.25  # écart entre deux vignettes voisines
COUVERTURE_MIN = 0.85  # part de la vignette réellement vue sur la photo
DOUTEUX_REMPLI_MAX = 0.35  # vignette douteuse (meuble possible) à moins de 35 % : ces points sont remplacés par le sol propre
POIDS_DOUTEUX = 0.05  # au-delà : la vignette vote quand même, mais à 5 % (une pièce vue seulement derrière un lit reste jugée)
CASE_M = 0.25  # côté d'une case de la carte des sols


def famille(matiere: str) -> str:
    """La famille d'une matière du catalogue (moteur/matieres.py)."""
    if matiere in _FAMILLE:
        return _FAMILLE[matiere]
    from moteur.matieres import sorte
    return "carreaux" if sorte(matiere) == "carrelage" else "lames"


assert all(famille(m) in FAMILLES for m in NOMS_SOLS)


def vignettes(image: np.ndarray, finesse: np.ndarray, resolution: float, taille_m: float = VIGNETTE_M,
              pas_m: float = PAS_M, couverture_min: float = COUVERTURE_MIN, sortie_px: int = VIGNETTE_PX, douteux=None):
    """Découpe une image à plat en vignettes. Rend (vignettes N × sortie_px × sortie_px × 3, centres (N, 2) en pixels de
    l'image à plat (ligne, colonne), finesse moyenne (N,)). Le peu qui n'est pas vu dans une vignette est rempli par la
    couleur moyenne de ce qui est vu (sinon l'œil verrait un bord noir).
    douteux (facultatif, points vus derrière un meuble possible) : rend en plus le FACTEUR de vote de chaque vignette
    (1 − part douteuse, les points douteux remplacés par le sol propre, si elle est ≤ DOUTEUX_REMPLI_MAX ; POIDS_DOUTEUX
    au-delà)."""
    cote, pas = int(round(taille_m / resolution)), max(1, int(round(pas_m / resolution)))
    vu = finesse > 0
    integrale = cv2.integral(vu.astype(np.uint8))
    h, w = vu.shape
    images, centres, finesses, facteurs = [], [], [], []
    for l0 in range(0, h - cote + 1, pas):
        for c0 in range(0, w - cote + 1, pas):
            n = integrale[l0 + cote, c0 + cote] - integrale[l0, c0 + cote] - integrale[l0 + cote, c0] + integrale[l0, c0]
            if n < couverture_min * cote * cote:
                continue
            morceau = image[l0:l0 + cote, c0:c0 + cote].copy()
            m = vu[l0:l0 + cote, c0:c0 + cote]
            facteur = 1.0
            if douteux is not None:
                d = douteux[l0:l0 + cote, c0:c0 + cote] & m
                part = float(d.sum()) / max(int(m.sum()), 1)
                if 0 < part <= DOUTEUX_REMPLI_MAX:
                    m = m & ~d
                    facteur = 1.0 - part
                elif part > DOUTEUX_REMPLI_MAX:
                    facteur = POIDS_DOUTEUX
            morceau[~m] = morceau[m].mean(axis=0).astype(np.uint8)
            facteurs.append(facteur)
            images.append(cv2.resize(morceau, (sortie_px, sortie_px), interpolation=cv2.INTER_AREA if cote > sortie_px
                                     else cv2.INTER_LINEAR))
            centres.append((l0 + cote / 2, c0 + cote / 2))
            finesses.append(float(finesse[l0:l0 + cote, c0:c0 + cote][m].mean()))
    if not images:
        vide = (np.zeros((0, sortie_px, sortie_px, 3), np.uint8), np.zeros((0, 2)), np.zeros(0))
        return (*vide, np.zeros(0)) if douteux is not None else vide
    if douteux is not None:
        return np.stack(images), np.array(centres), np.array(finesses), np.array(facteurs)
    return np.stack(images), np.array(centres), np.array(finesses)


class Classifieur:
    """Régression logistique sur les empreintes de l'œil : une note par famille, transformée en probabilités."""

    def __init__(self, dimension: int, classes=FAMILLES, oeil: str = "vits14"):
        self.classes, self.oeil = tuple(classes), oeil
        self.poids = torch.zeros(dimension, len(self.classes))
        self.biais = torch.zeros(len(self.classes))

    def apprendre(self, X: np.ndarray, y: np.ndarray, pas: int = 400, regularisation: float = 1e-3) -> float:
        """y = indices des classes. Rend la justesse sur les exemples appris."""
        X_t, y_t = torch.from_numpy(X).float(), torch.from_numpy(y).long()
        w = torch.zeros_like(self.poids, requires_grad=True)
        b = torch.zeros_like(self.biais, requires_grad=True)
        # Classes déséquilibrées : chaque classe pèse autant au total.
        compte = torch.bincount(y_t, minlength=len(self.classes)).float().clamp(min=1)
        poids_classes = compte.sum() / (len(self.classes) * compte)
        opt = torch.optim.LBFGS([w, b], lr=1.0, max_iter=pas, line_search_fn="strong_wolfe")

        def perte():
            opt.zero_grad()
            p = F.cross_entropy(X_t @ w * 20 + b, y_t, weight=poids_classes) + regularisation * (w * w).sum()
            p.backward()
            return p

        opt.step(perte)
        self.poids, self.biais = w.detach(), b.detach()
        return float((self.probabilites(X).argmax(1) == y).mean())

    def probabilites(self, X: np.ndarray) -> np.ndarray:
        return torch.softmax(torch.from_numpy(X).float() @ self.poids * 20 + self.biais, 1).numpy()

    def etat(self) -> dict:
        return {"classes": list(self.classes), "oeil": self.oeil, "poids": self.poids, "biais": self.biais}

    @classmethod
    def depuis(cls, etat: dict) -> "Classifieur":
        c = cls(etat["poids"].shape[0], etat["classes"], etat["oeil"])
        c.poids, c.biais = etat["poids"].float(), etat["biais"].float()
        return c


@dataclass
class CarteDesSols:
    """Pour chaque case de CASE_M du sol : la somme des avis (probabilités × poids) par famille. `origine` = coin haut gauche."""

    votes: np.ndarray  # (lignes, colonnes, familles)
    origine: tuple[float, float]
    case: float
    classes: tuple[str, ...]
    # les avis des seules vignettes PROPRES (pas vues derrière un meuble possible) ; None = tout est propre (10/11/2026)
    votes_propres: np.ndarray | None = None
    # par case : combien de photos l'ont vue, et combien l'ont vue PROPREMENT (pas derrière un lit, un canapé, un tapis…)
    vues: np.ndarray | None = None
    vues_propres: np.ndarray | None = None

    @property
    def indices_sol(self) -> list[int]:
        """Les classes qui sont des familles de sol (la classe « meuble », si le classificateur la connaît, n'en est pas une)."""
        return [i for i, c in enumerate(self.classes) if c in FAMILLES]

    def votes_sol(self) -> np.ndarray:
        return self.votes[..., self.indices_sol]

    def vue(self) -> np.ndarray:
        """Cases où le SOL a été vu (une case vue seulement comme « meuble » reste inconnue)."""
        return self.votes_sol().sum(-1) > 1e-6

    def famille(self) -> np.ndarray:
        """Indice (dans `classes`) de la famille retenue par case (-1 : sol jamais vu)."""
        return np.where(self.vue(), np.array(self.indices_sol)[self.votes_sol().argmax(-1)], -1)

    def part_meuble(self) -> np.ndarray:
        """Part des avis « meuble » par case (0 si le classificateur ne connaît pas les meubles)."""
        if MEUBLE not in self.classes:
            return np.zeros(self.votes.shape[:2])
        total = self.votes.sum(-1)
        return np.where(total > 0, self.votes[..., self.classes.index(MEUBLE)] / np.maximum(total, 1e-9), 0.0)

    def confiance(self) -> np.ndarray:
        v = self.votes_sol()
        total = v.sum(-1)
        return np.where(total > 0, v.max(-1) / np.maximum(total, 1e-9), 0.0)

    def centres(self):
        lignes, colonnes = np.meshgrid(np.arange(self.votes.shape[0]), np.arange(self.votes.shape[1]), indexing="ij")
        return self.origine[0] + (colonnes + 0.5) * self.case, self.origine[1] - (lignes + 0.5) * self.case


def voter(carte_votes: np.ndarray, centres_px: np.ndarray, probabilites: np.ndarray, finesses: np.ndarray, resolution: float,
          case: float = CASE_M, taille_m: float = VIGNETTE_M, facteurs: np.ndarray | None = None) -> None:
    """Ajoute les avis des vignettes aux cases qu'elles couvrent (leur moitié centrale, pour rester précis aux limites).
    facteurs : poids en plus de chaque vignette (vignettes douteuses : peut-être un meuble)."""
    demi = int(round(taille_m / 4 / case))  # la moitié centrale de la vignette, en cases
    poids = np.sqrt(np.clip(finesses, 0, 4)) * probabilites.max(1)  # photo fine + avis tranché = plus de poids
    if facteurs is not None:
        poids = poids * facteurs
    for (l, c), p, w in zip(centres_px, probabilites, poids):
        lc, cc = int(l * resolution / case), int(c * resolution / case)
        l0, l1 = max(0, lc - demi), min(carte_votes.shape[0], lc + demi + 1)
        c0, c1 = max(0, cc - demi), min(carte_votes.shape[1], cc + demi + 1)
        carte_votes[l0:l1, c0:c1] += w * p


def matieres_verite(logement: dict, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """La matière du sol en chaque point (X, Y) d'après un logement dont les pièces ont leur `sol` (et leurs `zones_sol`) ;
    "" hors des pièces ou pour une pièce sans sol connu."""
    from moteur.sol_a_plat import dans_polygone
    sortie = np.full(np.shape(X), "", dtype=object)
    for p in logement["pieces"]:
        if not p.get("sol"):
            continue
        dedans = dans_polygone(X, Y, p["contour"])
        sortie[dedans] = p["sol"]["matiere"]
        for z in p.get("zones_sol", []):
            sortie[dedans & dans_polygone(X, Y, z["contour"])] = z["sol"]["matiere"]
    return sortie


def familles_verite(logement: dict, X: np.ndarray, Y: np.ndarray, classes=FAMILLES) -> np.ndarray:
    """Indice de la famille du sol en chaque point (-1 : hors des pièces ou inconnu)."""
    m = matieres_verite(logement, X, Y)
    index = {f: i for i, f in enumerate(classes)}
    return np.vectorize(lambda v: index[famille(v)] if v else -1, otypes=[int])(m) if m.size else np.zeros(np.shape(X), int)


# ---------------------------------------------------------------- temps 3 : le sol de chaque pièce et ses zones
ZONE_MIN_M2 = 1.0  # en dessous, une tache d'une autre famille est du bruit (un meuble, un reflet), pas une zone de sol
SURFACE_VUE_MIN_M2 = 1.0  # une pièce dont on voit moins que ça n'est pas jugée
# Une ZONE (un autre sol dans la pièce) n'est pas gardée là où la plupart des photos voient un MEUBLE (16/11/2026, app-004 : le
# lit, écarté sur quatre photos, laissait quand même une « zone de carrelage » de 3 m² à sa place, à cause de quelques avis
# venus d'une photo mal placée). ZONE_PROPRE_MIN : part des vues de la zone qui doivent être propres.
ZONE_PROPRE_MIN = 0.5
ZONE_MEUBLE_MAX = 1.0  # DÉSACTIVÉ (09/11/2026) : à 0,35-0,5, +5 points sur le contrôle fabriqué MAIS app-001 81,5 → 52 % (sur vraies photos l'œil dit « meuble » bien plus souvent : la vraie zone de cubes et le point de Hongrie étaient retirés)


def _lisses(carte: CarteDesSols, votes: np.ndarray):
    """Les cases où un sol a été vu, et les avis par famille de sol lissés sur 3 × 3 cases."""
    sol = votes[..., carte.indices_sol]
    lisses = np.stack([cv2.blur(sol[..., k].astype(np.float32), (3, 3)) for k in range(sol.shape[-1])], -1)
    return sol.sum(-1) > 1e-6, lisses


def _famille_par_case(carte: CarteDesSols, vue: np.ndarray, lisses: np.ndarray, permises: tuple | None = None) -> np.ndarray:
    """Indice (dans carte.classes) de la famille la plus votée de chaque case vue (-1 : jamais vue). `permises` : seules ces
    familles peuvent être choisies (les sols que la LECTURE des photos dit pour la pièce, le premier étant son sol principal) ;
    une case sans aucun avis pour elles prend la première."""
    indices = np.array(carte.indices_sol)
    if permises is None:
        return np.where(vue, indices[lisses.argmax(-1)], -1)
    principale = carte.classes.index(permises[0])
    colonnes = [k for k, i in enumerate(indices) if carte.classes[i] in permises]
    choisie = indices[np.array(colonnes)][lisses[..., colonnes].argmax(-1)]
    choisie = np.where(lisses[..., colonnes].sum(-1) > 1e-9, choisie, principale)
    return np.where(vue, choisie, -1)


def _plein(tache: np.ndarray) -> float:
    """Part de son enveloppe convexe qu'une tache de cases remplit (1 : convexe ; un L : ~0,6)."""
    lignes, colonnes = np.nonzero(tache)
    coins = np.concatenate([np.stack([colonnes + dc, lignes + dl], 1) for dc in (0, 1) for dl in (0, 1)]).astype(np.float32)
    return float(tache.sum()) / max(float(cv2.contourArea(cv2.convexHull(coins))), 1e-9)


def morceaux_convexes(tache: np.ndarray, plein_min: float = 0.8, au_plus: int = 4) -> list[np.ndarray]:
    """Une tache de cases découpée en morceaux à peu près CONVEXES (le format veut des zones convexes ; une zone en L rendue
    par son enveloppe recouvrirait le sol voisin) : tant qu'un morceau remplit moins de `plein_min` de son enveloppe, il est
    coupé en deux par la ligne ou la colonne de la carte qui laisse les deux parts les plus pleines."""
    faits, a_voir = [], [tache]
    while a_voir:
        m = a_voir.pop()
        if len(faits) + len(a_voir) + 1 >= au_plus or _plein(m) >= plein_min:
            faits.append(m)
            continue
        lignes, colonnes = np.nonzero(m)
        meilleur = None
        for axe, valeurs in ((0, lignes), (1, colonnes)):
            for coupe in range(int(valeurs.min()) + 1, int(valeurs.max()) + 1):
                d_un_cote = np.zeros_like(m)
                if axe == 0:
                    d_un_cote[:coupe] = True
                else:
                    d_un_cote[:, :coupe] = True
                a, b = m & d_un_cote, m & ~d_un_cote
                if a.sum() < 4 or b.sum() < 4:
                    continue
                note = (_plein(a) * a.sum() + _plein(b) * b.sum()) / m.sum()
                if meilleur is None or note > meilleur[0]:
                    meilleur = (note, a, b)
        if meilleur is None or meilleur[0] <= _plein(m) + 0.05:
            faits.append(m)
            continue
        a_voir += [meilleur[1], meilleur[2]]
    return faits


def sols_des_pieces(carte: CarteDesSols, logement: dict, zone_min_m2: float = ZONE_MIN_M2, lus: dict | None = None) -> dict:
    """Pour chaque pièce assez vue : la famille de son sol (la plus votée) et ses zones d'une autre famille (contours
    convexes en mètres). Les votes sont d'abord lissés sur 3 × 3 cases (75 cm) : une case isolée suit ses voisines.
    Si la pièce est assez vue PROPREMENT (pas derrière un meuble possible), seules les cases propres décident ; sinon
    toutes (une pièce vue seulement derrière un lit reste jugée).
    `lus` (17/11/2026) : ce que la LECTURE des photos dit du sol de chaque pièce (moteur.photos_lues.sols_lus : {id de pièce :
    {"famille", "autres"}}). Le sol principal de la pièce est alors celui qui est LU, et chaque case choisit seulement entre les
    sols lus pour la pièce : la lecture donne le SENS (quels sols), les avis des cases la GÉOMÉTRIE (où). Avant, la lecture
    était appliquée APRÈS cette décision : quand la brique avait pris pour sol principal celui que la lecture dit second
    (app-001 : « lames » pour un séjour en point de Hongrie dont l'entrée est en lames), l'ancien sol principal était effacé
    au lieu de devenir une zone, et la couleur du sol principal était mesurée sur l'autre sol."""
    from moteur.sol_a_plat import dans_polygone
    vue_tout, lisses_tout = _lisses(carte, carte.votes)
    vue_propre, lisses_propre = _lisses(carte, carte.votes_propres) if carte.votes_propres is not None else (vue_tout, lisses_tout)
    meuble = carte.part_meuble()
    X, Y = carte.centres()
    case2 = carte.case ** 2
    sorties = {}
    for p in logement["pieces"]:
        lu = (lus or {}).get(p["id"])
        permises = (lu["famille"], *lu.get("autres", ())) if lu else None
        dans = dans_polygone(X, Y, p["contour"])
        if (dans & vue_propre).sum() * case2 >= SURFACE_VUE_MIN_M2:
            dedans, fam = dans & vue_propre, _famille_par_case(carte, vue_propre, lisses_propre, permises)
        else:
            dedans, fam = dans & vue_tout, _famille_par_case(carte, vue_tout, lisses_tout, permises)
        if dedans.sum() * case2 < SURFACE_VUE_MIN_M2:
            continue
        compte = np.bincount(fam[dedans], minlength=len(carte.classes))
        votee = int(compte.argmax())
        principale = carte.classes.index(lu["famille"]) if lu else votee
        zones = []
        # sans lecture : une tache = des cases voisines d'un AUTRE sol que le principal (comme toujours) ; avec la lecture : une
        # tache par famille (un carrelage et des lames qui se touchent, tous deux « autres », ne font pas une seule zone)
        if lu:
            taches = []
            for i in carte.indices_sol:
                if i != principale:
                    n, etiquettes = cv2.connectedComponents((dedans & (fam == i)).astype(np.uint8), connectivity=8)
                    taches += [etiquettes == k for k in range(1, n)]
        else:
            n, etiquettes = cv2.connectedComponents((dedans & (fam != principale)).astype(np.uint8), connectivity=8)
            taches = [etiquettes == k for k in range(1, n)]
        for tache in taches:
            if tache.sum() * case2 < zone_min_m2:
                continue
            if float(meuble[tache].mean()) > ZONE_MEUBLE_MAX:
                continue  # l'œil y voit surtout des meubles (un lit, un tapis) : pas une zone de sol
            if carte.vues is not None and carte.vues[tache].sum() > 0 \
                    and carte.vues_propres[tache].sum() / carte.vues[tache].sum() < ZONE_PROPRE_MIN:
                continue  # la plupart des photos y voient un lit, un canapé, un tapis : pas un autre sol
            f = int(np.bincount(fam[tache], minlength=len(carte.classes)).argmax())
            for morceau in (morceaux_convexes(tache) if lu else [tache]):
                lignes, colonnes = np.nonzero(morceau)
                coins = np.concatenate([np.stack([colonnes + dc, lignes + dl], 1) for dc in (0, 1) for dl in (0, 1)]).astype(np.float32)
                enveloppe = cv2.convexHull(coins)[:, 0]
                contour = [[round(float(carte.origine[0] + c * carte.case), 3), round(float(carte.origine[1] - l * carte.case), 3)]
                           for c, l in enveloppe]
                zones.append({"famille": carte.classes[f], "contour": contour[::-1], "surface_m2": round(float(morceau.sum() * case2), 2)})
        sorties[p["id"]] = {"famille": carte.classes[principale], "surface_vue_m2": round(float(dedans.sum() * case2), 2),
                            "part": round(float(compte[principale] / max(compte.sum(), 1)), 3), "zones": zones}
        if lu:
            # les grandes zones d'abord : là où deux enveloppes se recouvrent un peu, la plus petite l'emporte (dernière posée)
            zones.sort(key=lambda z: -z["surface_m2"])
            sorties[p["id"]]["famille_brique"] = carte.classes[votee]
    return sorties


# ---------------------------------------------------------------- temps 4 : la couleur d'un sol
def lab(rgb: np.ndarray) -> np.ndarray:
    """Pixels sRGB 0-255 → CIELAB (L clarté 0-100, a rouge (+) / vert (-), b jaune (+) / bleu (-)), blanc D65."""
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def couleur_du_sol(pixels_rgb: np.ndarray) -> dict | None:
    """La couleur d'un sol telle que la photo la montre (CIELAB), robuste aux meubles et tapis posés dessus : médiane des
    pixels, après avoir écarté ceux trop loin de la couleur dominante (écart à la médiane > 2,5 fois l'écart médian)."""
    if len(pixels_rgb) < 50:
        return None
    L = lab(pixels_rgb.reshape(-1, 3))
    med = np.median(L, 0)
    ecart = np.linalg.norm(L - med, axis=1)
    garde = ecart <= 2.5 * max(float(np.median(ecart)), 1.0)
    m = np.median(L[garde], 0)
    return {"L": round(float(m[0]), 1), "a": round(float(m[1]), 1), "b": round(float(m[2]), 1), "pixels": int(garde.sum())}


def ecart_lab(c1: dict, c2: dict) -> float:
    """Écart entre deux couleurs (ΔE 1976) : ~2 à peine visible, ~10 nettement différent."""
    return float(np.sqrt((c1["L"] - c2["L"]) ** 2 + (c1["a"] - c2["a"]) ** 2 + (c1["b"] - c2["b"]) ** 2))


# ---------------------------------------------------------------- tout l'enchaînement, et sa note
def avis_parmi(probabilites: np.ndarray, classes, permises) -> np.ndarray:
    """Les avis des vignettes d'UNE photo, ramenés aux seuls sols que la lecture dit pour CETTE photo (`permises`, la première
    famille étant son sol principal ; None ou vide : avis inchangés). La part de « sol » de chaque vignette est gardée (ce que
    l'œil dit « meuble » le reste) et répartie entre les sols permis, au prorata de leurs avis ; sans aucun avis pour eux,
    tout va au premier. Une photo lue « point de Hongrie » ne peut donc plus voter « carrelage » pour son tapis."""
    if not permises:
        return probabilites
    sols = [i for i, c in enumerate(classes) if c in FAMILLES]
    gardes = [i for i in sols if classes[i] in permises]
    if not gardes:
        return probabilites
    sortie = probabilites.copy()
    masse = probabilites[:, sols].sum(1)
    part = probabilites[:, gardes]
    total = part.sum(1)
    sortie[:, sols] = 0.0
    sortie[:, gardes] = part / np.maximum(total, 1e-12)[:, None] * masse[:, None]
    vides = total <= 1e-12
    if vides.any():
        premier = classes.index(permises[0]) if permises[0] in classes else gardes[0]
        sortie[np.ix_(vides, gardes)] = 0.0
        sortie[vides, premier] = masse[vides]
    return sortie


def reconnaitre(releve: dict, logement: dict, racine, oeil, clf: Classifieur, journal=lambda *_: None, pas_du_sol=None,
                lus: dict | None = None, sols_des_photos: dict | None = None) -> dict:
    """Photos calées du client → sol de chaque pièce (famille, zones, couleur). Rend aussi la carte et le sol assemblé.
    pas_du_sol : fonction (nom, photo RGB) → masque de ce qui n'est pas du sol (lits, canapés…), écarté avant la mise à plat
    (moteur/pas_du_sol.py) ; None = rien d'écarté (comme avant le 10/11/2026).
    LA LECTURE DES PHOTOS (17/11/2026 ; None = Atelya décide seul, comme en service) :
    - sols_des_photos : {nom de la photo : (familles lues sur cette photo)} : chaque photo ne vote que parmi SES sols (avis_parmi) ;
    - lus : le sol de chaque pièce d'après la lecture (voir sols_des_pieces)."""
    from moteur.sol_a_plat import assembler, dans_polygone, photos_a_plat
    from moteur.oeil_dinov2 import empreintes
    vues = photos_a_plat(releve, logement, racine, journal=journal, pas_du_sol=pas_du_sol)
    if not vues:
        return {"pieces": {}, "carte": None, "image": None, "finesse": None}
    v0 = vues[0][2]
    h, w = v0.image.shape[:2]
    votes = np.zeros((int(np.ceil(h * v0.resolution / CASE_M)), int(np.ceil(w * v0.resolution / CASE_M)), len(clf.classes)))
    propres = np.zeros_like(votes) if any(v.douteux is not None for _, _, v in vues) else None
    nb_vues, nb_propres = np.zeros(votes.shape[:2], np.int32), np.zeros(votes.shape[:2], np.int32)
    tuiles_xy, tuiles_e = [], []  # centre (x, y) et empreinte de chaque vignette : pour choisir la matière d'une région
    for nom, _, vue in vues:
        if vue.douteux is not None:
            v, centres, finesses, facteurs = vignettes(vue.image, vue.finesse, vue.resolution, douteux=vue.douteux)
        else:
            (v, centres, finesses), facteurs = vignettes(vue.image, vue.finesse, vue.resolution), None
        if len(v):
            e = empreintes(oeil, v)
            pr = avis_parmi(clf.probabilites(e), clf.classes, (sols_des_photos or {}).get(nom))
            voter(votes, centres, pr, finesses, vue.resolution, facteurs=facteurs)
            ok = np.ones(len(v), bool) if facteurs is None else facteurs >= 1.0 - DOUTEUX_REMPLI_MAX
            if propres is not None:
                voter(propres, centres[ok], pr[ok], finesses[ok], vue.resolution,
                      facteurs=None if facteurs is None else facteurs[ok])
            for compte, lesquelles in ((nb_vues, np.ones(len(v), bool)), (nb_propres, ok)):  # les cases que CETTE photo voit
                de_la_photo = np.zeros_like(votes)
                voter(de_la_photo, centres[lesquelles], pr[lesquelles], finesses[lesquelles], vue.resolution)
                compte += de_la_photo.sum(-1) > 1e-9
            garde = np.ones(len(v), bool) if facteurs is None else facteurs >= 1.0 - DOUTEUX_REMPLI_MAX
            # le choix de la matière ne regarde que les vignettes propres (pas le lit vu à la place du parquet)
            tuiles_xy.append(np.stack(vue.vers_sol(centres[garde, 0], centres[garde, 1]), 1))
            tuiles_e.append(e[garde])
        journal(f"  {nom} : {len(v)} vignettes")
    carte = CarteDesSols(votes, v0.origine, CASE_M, tuple(clf.classes), votes_propres=propres, vues=nb_vues,
                         vues_propres=nb_propres)
    pieces = sols_des_pieces(carte, logement, lus=lus)
    image, finesse, choisie = assembler([v for _, _, v in vues])
    douteux = np.zeros(finesse.shape, bool)  # le point retenu est vu derrière un meuble possible
    for k, (_, _, v) in enumerate(vues):
        if v.douteux is not None:
            douteux |= (choisie == k) & v.douteux
    # la couleur se mesure là où l'œil voit du SOL : pas dans les cases où il voit surtout des meubles (lit, tapis…)
    meuble = carte.part_meuble()
    case_l = np.minimum((np.arange(h) * v0.resolution / CASE_M).astype(int), meuble.shape[0] - 1)
    case_c = np.minimum((np.arange(w) * v0.resolution / CASE_M).astype(int), meuble.shape[1] - 1)
    pas_meuble = meuble[case_l][:, case_c] < 0.5
    sol_pur = (finesse > 0) & pas_meuble & ~douteux
    lignes, colonnes = np.nonzero(sol_pur)
    X, Y = v0.vers_sol(lignes, colonnes)
    contours = {p["id"]: p["contour"] for p in logement["pieces"]}
    for pid, s in pieces.items():
        dans_piece = dans_polygone(X, Y, contours[pid])
        hors_zones = dans_piece.copy()
        for z in s["zones"]:
            dz = dans_piece & dans_polygone(X, Y, z["contour"])
            hors_zones &= ~dz
            z["couleur"] = couleur_du_sol(image[lignes[dz], colonnes[dz]])
        s["couleur"] = couleur_du_sol(image[lignes[hors_zones], colonnes[hors_zones]])
    # couleur pour Blender (part de lumière renvoyée), photo par photo contre le blanc des murs de la même photo
    albedos_par_region(pieces, vues, logement, pas_meuble, contours)
    if tuiles_e:
        txy, te = np.concatenate(tuiles_xy), np.concatenate(tuiles_e)
        for pid, s in pieces.items():
            dans_piece = dans_polygone(txy[:, 0], txy[:, 1], contours[pid])
            hors_zones = dans_piece.copy()
            for z in s["zones"]:
                dz = dans_piece & dans_polygone(txy[:, 0], txy[:, 1], z["contour"])
                hors_zones &= ~dz
                z["empreinte"] = te[dz].mean(0) if dz.any() else None
            s["empreinte"] = te[hors_zones].mean(0) if hors_zones.any() else None
    zones_d_un_meme_sol(pieces)
    sens_des_sols(pieces, vues, logement, pas_du_sol)
    return {"pieces": pieces, "carte": carte, "image": image, "finesse": finesse, "origine": v0.origine,
            "resolution": v0.resolution}


LARGEUR_ECARTS_MIN = 25  # la largeur des lames n'est retenue que mesurée sur au moins 25 écarts entre joints voisins


def sens_des_sols(pieces: dict, vues, logement: dict, pas_du_sol=None) -> None:
    """Le SENS des lames de chaque parquet (pièce, zones d'un même sol) et, quand elle se mesure, leur LARGEUR, lus sur les
    photos (moteur/sens_des_lames.py ; 17/11/2026, NT : « pas ressemblants […] sur la direction du parquet »). Clés « sens »
    (degrés, repère du logement ; absente si les photos ne tranchent pas : le sens général du logement reste) et
    « largeur_lames » (m). Lames droites : le sens des joints. Point de Hongrie, bâtons rompus : le sens des longs joints qui
    séparent les rangs de chevrons, tourné d'un quart de tour (c'est ainsi que la maquette oriente ces motifs)."""
    from moteur import sens_des_lames as sl
    from moteur.sol_a_plat import dans_polygone

    axes = sl.axes_du_logement(logement)
    traits = []
    for nom, _, vue in vues:
        if vue.photo is None:
            continue
        masque = pas_du_sol(nom, vue.photo) if pas_du_sol is not None else None
        traits += sl.traits_du_sol(vue.photo, vue.camera, logement, masque)
    for pid, s in pieces.items():
        groupes: dict[str, tuple[list, list]] = {"": ([s], [])}  # "" : le sol de la pièce ; sinon les zones d'une même famille
        for z in s["zones"]:
            groupes.setdefault(z["famille"], ([], []))[0].append(z)
        for tr in (x for x in traits if x["piece"] == pid):
            cle = ""
            for z in s["zones"]:  # la dernière zone qui contient le trait l'emporte (les petites sont posées après les grandes)
                if dans_polygone(np.array([tr["milieu"][0]]), np.array([tr["milieu"][1]]), z["contour"])[0]:
                    cle = z["famille"]
            groupes[cle][1].append(tr)
        for sols, les_traits in groupes.values():
            if sols[0]["famille"] not in BOIS:
                continue
            choix = sl.sens_parmi(les_traits, axes)
            if choix is None or not choix["sur"]:
                continue
            droites = sols[0]["famille"] == "lames"
            largeur = sl.largeur_des_lames(les_traits, choix["sens"]) if droites else None
            for sol in sols:
                sol["sens"] = choix["sens"] if droites else (choix["sens"] + 90.0) % 180.0
                sol["sens_note"] = [choix["note"], choix["autre"]]
                if largeur and largeur["ecarts"] >= LARGEUR_ECARTS_MIN:
                    sol["largeur_lames"] = largeur["largeur_m"]


def zones_d_un_meme_sol(pieces: dict) -> None:
    """Dans une pièce, les zones d'une MÊME famille sont un seul et même sol (les lames de l'entrée, rendues en plusieurs
    morceaux convexes) : elles prennent toutes la couleur et l'aspect du morceau le mieux mesuré (le plus de photos, puis le
    plus grand), sinon la maquette montrerait une couture entre deux morceaux du même parquet."""
    for s in pieces.values():
        par_famille: dict[str, list] = {}
        for z in s.get("zones", []):
            par_famille.setdefault(z["famille"], []).append(z)
        for zones in par_famille.values():
            mesurees = [z for z in zones if z.get("couleur_photo")]
            if len(zones) < 2 or not mesurees:
                continue
            reference = max(mesurees, key=lambda z: (z.get("photos_couleur", 0), z.get("surface_m2", 0.0)))
            for z in zones:
                if z is not reference:
                    for cle in ("couleur_photo", "photos_couleur", "empreinte", "couleur"):
                        if reference.get(cle) is not None:
                            z[cle] = reference[cle]


def mediane_ponderee(valeurs, poids) -> float:
    """La valeur qui partage le poids total en deux (une photo qui voit beaucoup de sol compte plus)."""
    valeurs, poids = np.asarray(valeurs, float), np.asarray(poids, float)
    ordre = np.argsort(valeurs)
    return float(valeurs[ordre][min(int(np.searchsorted(np.cumsum(poids[ordre]), poids.sum() / 2)), len(valeurs) - 1)])


JOURNAL_COULEURS: list | None = None  # une liste : chaque mesure de couleur (photo, région) y est notée (diagnostic)


def albedos_par_region(pieces: dict, vues, logement: dict, pas_meuble: np.ndarray, contours: dict) -> None:
    """Pour chaque sol (pièce, zone) : la part de lumière qu'il renvoie (r, g, b), mesurée sur chaque photo qui le voit contre
    le blanc des murs de LA MÊME photo (moteur/blanc_des_murs.py), puis médiane des photos pondérée par le sol vu. Clé
    « couleur_photo » (même sens que Sol.couleur_photo du format, que Blender vise au rendu)."""
    from moteur.blanc_des_murs import blanc_des_murs
    from moteur.sol_a_plat import dans_polygone
    from moteur.teinte_photo import BLANC_PEINTURE, lineaire
    mesures: dict[tuple, list] = {}
    for nom_photo, _, vue in vues:
        if vue.photo is None:
            continue
        blanc = blanc_des_murs(vue.photo, vue.camera, logement, vue.piece, vue.point_de_vue)
        if blanc is None:
            continue
        propre = (vue.finesse > 0) & pas_meuble
        if vue.douteux is not None:  # pas les points vus derrière un lit, un canapé, un rangement (10/11/2026)
            propre &= ~vue.douteux
        lignes, colonnes = np.nonzero(propre)
        if not len(lignes):
            continue
        X, Y = vue.vers_sol(lignes, colonnes)
        for pid, s in pieces.items():
            dans_piece = dans_polygone(X, Y, contours[pid])
            regions = [(("piece", pid), dans_piece.copy(), s["famille"])]
            for k, z in enumerate(s["zones"]):
                dz = dans_piece & dans_polygone(X, Y, z["contour"])
                regions[0][1][dz] = False
                regions.append(((pid, k), dz, z["famille"]))
            for cle, m, fam in regions:
                if m.sum() < 2000:  # moins de 0,2 m² vus sur cette photo : pas assez sûr
                    continue
                pixels = vue.image[lignes[m], colonnes[m]]
                L = lab(pixels)
                if fam != "carreaux":  # un parquet est « bois » : un peu orangé (écarte tapis, linge, meubles blancs ou gris)
                    bois = (L[:, 1] > 4) & (L[:, 2] > 12) & (L[:, 0] > 20) & (L[:, 0] < 88)
                    if bois.sum() < 1000:
                        continue
                    pixels, L = pixels[bois], L[bois]
                # pixels proches de la couleur dominante seulement (restes de lit, de tapis, de pied de meuble écartés)
                ecart = np.linalg.norm(L - np.median(L, 0), axis=1)
                proches = ecart <= 2.0 * max(float(np.median(ecart)), 1.0)
                lumiere = lineaire(pixels[proches])
                sol = np.median(lumiere, axis=0)
                if fam != "carreaux":
                    # La TEINTE d'un parquet se lit sur sa moitié la plus VIVE (17/11/2026) : le reflet d'une fenêtre ou d'un
                    # voilage sur le sol y ajoute du blanc, qui délave la couleur (séjour d'app-001 : sur les photos 03 et 04,
                    # la moitié du point de Hongrie est sous ce reflet ; le parquet sortait beige pâle). La clarté reste celle
                    # de tous les points (médiane du rouge).
                    rouge = np.maximum(lumiere[:, 0], 1e-6)
                    bleu_sur_rouge = lumiere[:, 2] / rouge
                    vifs = bleu_sur_rouge <= np.median(bleu_sur_rouge)
                    sol = np.array([sol[0], sol[0] * np.median(lumiere[vifs, 1] / rouge[vifs]), sol[0] * np.median(bleu_sur_rouge[vifs])])
                mesures.setdefault(cle, []).append((sol / max(float(blanc["blanc"].max()), 1e-6) * BLANC_PEINTURE, int(m.sum())))
                if JOURNAL_COULEURS is not None:  # pc/verification/diag_couleur_sols.py : d'où vient la couleur de chaque sol
                    JOURNAL_COULEURS.append({"photo": nom_photo, "region": cle, "albedo": mesures[cle][-1][0], "pixels": int(proches.sum()),
                                             "blanc": blanc["blanc"]})
    for cle, liste in mesures.items():
        valeurs = np.array([a for a, _ in liste])
        poids = np.array([n for _, n in liste], float)
        cible = pieces[cle[1]] if cle[0] == "piece" else pieces[cle[0]]["zones"][cle[1]]
        if cible["famille"] in BOIS:
            # Un PARQUET (17/11/2026) : la clarté (le rouge, sa couleur la plus forte) et la TEINTE (vert / rouge, bleu / rouge)
            # sont réunies séparément. Le reflet d'une fenêtre sur le sol ajoute du blanc : il délave la couleur sans beaucoup
            # changer la clarté. Canal par canal, la photo « du milieu » pouvait être justement celle du reflet, et le parquet
            # sortait gris (séjour d'app-001 : [0,56 ; 0,37 ; 0,26], la photo 03, pour un bois miel [0,56 ; 0,31 ; 0,15]).
            rouge = np.maximum(valeurs[:, 0], 1e-6)
            r = mediane_ponderee(valeurs[:, 0], poids)
            albedo = [r, r * mediane_ponderee(valeurs[:, 1] / rouge, poids), r * mediane_ponderee(valeurs[:, 2] / rouge, poids)]
        else:
            albedo = [mediane_ponderee(valeurs[:, c], poids) for c in range(3)]  # médiane pondérée par canal
        cible["couleur_photo"] = [round(min(max(a, 0.0), 1.0), 4) for a in albedo]
        cible["photos_couleur"] = len(liste)


MATIERE_PAR_DEFAUT = {"lames": "chene_naturel_photo", "point_de_hongrie": "point_de_hongrie",
                      "batons_rompus": "parquet_batons_rompus", "carreaux": "carrelage_interieur"}


LAMES_LARGES_M = 0.145  # à partir de 14,5 cm, des lames sont « larges »
LAMES_COURANTES = ("lames_chene_anglaise", "vieux_parquet")  # le choix d'Atelya pour des lames étroites ou moyennes
ECHELLE_LAMES = (0.6, 1.6)  # de combien une matière peut être agrandie ou réduite pour avoir des lames de la largeur mesurée


def choisir_matiere(famille_: str, empreinte, prototypes: dict | None, largeur_lames: float | None = None) -> str:
    """La matière du catalogue de cette famille dont l'aspect (empreinte moyenne de l'œil sur la bibliothèque) est le plus
    proche de ce que montrent les photos. Le point de Hongrie garde la matière dessinée par Atelya (la plus réaliste au rendu).
    Lames droites (17/11/2026) : seulement parmi les vrais parquets à lames droites du catalogue (moteur.matieres.LAMES_DROITES ;
    avant, « parquet posé en diagonale » et les mosaïques pouvaient être choisis pour des lames droites) et, si la largeur
    des lames a été mesurée sur les photos, parmi ceux dont les lames ont à peu près cette largeur."""
    from moteur.matieres import LAMES_DROITES, NOMS_SOLS
    if famille_ == "point_de_hongrie" or empreinte is None or not prototypes:
        return MATIERE_PAR_DEFAUT[famille_]
    candidates = [m for m in NOMS_SOLS if famille(m) == famille_ and m in prototypes]
    if famille_ == "lames":
        candidates = [m for m in candidates if m in LAMES_DROITES]
        if largeur_lames is not None and largeur_lames >= LAMES_LARGES_M:
            # de LARGES lames : parmi les parquets à larges lames du catalogue, le plus ressemblant
            candidates = [m for m in candidates if LAMES_DROITES[m] >= LAMES_LARGES_M] or candidates
        else:
            # lames étroites ou moyennes, ou largeur non mesurée : le parquet de chêne « à l'anglaise » (le plus courant des
            # appartements français, dessiné par Atelya à la largeur voulue), ou le vieux parquet si c'est lui qui ressemble.
            # Laissé à lui-même, l'œil prenait de petites lamelles courtes pour les longues lames de l'entrée d'app-001.
            candidates = [m for m in LAMES_COURANTES if m in candidates] or candidates
    if not candidates:
        return MATIERE_PAR_DEFAUT[famille_]
    e = np.asarray(empreinte, float)
    e = e / max(np.linalg.norm(e), 1e-9)
    return max(candidates, key=lambda m: float(np.asarray(prototypes[m]) @ e))


def sols_vers_logement(resultat: dict, logement: dict, bibliotheque, prototypes: dict | None = None) -> dict:
    """Le logement avec les sols reconnus sur les photos : matière, zones (convexes), teinte et couleur visée au rendu ;
    statut « estime » (vu sur photo), source « brique photos », confiance = part des avis. Les pièces non vues gardent leur sol."""
    import json as _json
    from pathlib import Path
    from moteur.teinte_photo import albedo_de_la_matiere, teinte_pour

    def sol(s, part):
        from moteur.matieres import LAMES_DROITES

        matiere = choisir_matiere(s["famille"], s.get("empreinte"), prototypes, s.get("largeur_lames"))
        d = {"matiere": matiere, "statut": "estime", "confiance": round(float(min(max(part, 0.05), 1.0)), 2),
             "source": f"brique photos ({s.get('photos_couleur', 0)} photos pour la couleur)"}
        if s.get("sens") is not None:  # le sens des lames lu sur les photos
            d["sens"] = round(float(s["sens"]) % 180.0, 1)
        if s.get("largeur_lames") and matiere in LAMES_DROITES:  # les lames à la largeur mesurée sur les photos
            echelle = float(np.clip(s["largeur_lames"] / LAMES_DROITES[matiere], *ECHELLE_LAMES))
            if abs(echelle - 1.0) > 0.05:
                d["echelle"] = round(echelle, 2)
        if s.get("couleur_photo") and bibliotheque is not None:
            d["couleur_photo"] = s["couleur_photo"]
            d["teinte"] = list(teinte_pour(albedo_de_la_matiere(Path(bibliotheque), matiere), s["couleur_photo"]))
        return d

    couleur_sure_du_bois(resultat["pieces"])
    sortie = _json.loads(_json.dumps(logement))
    for p in sortie["pieces"]:
        s = resultat["pieces"].get(p["id"])
        if s is None:
            continue
        p["sol"] = sol(s, s.get("part", 1.0))
        p["zones_sol"] = [{"contour": z["contour"], "sol": sol(z, s.get("part", 1.0))} for z in s["zones"]]
    return sols_des_espaces_ouverts(sortie)


PHOTOS_COULEUR_SURES = 2  # une couleur mesurée sur au moins 2 photos est gardée telle quelle
BOIS = ("lames", "point_de_hongrie", "batons_rompus")


def couleur_sure_du_bois(pieces: dict) -> None:
    """La couleur d'un parquet mesurée sur UNE SEULE photo est peu sûre (16/11/2026, app-004 : la chambre sortait deux fois plus
    claire que le séjour, [0,70 ; 0,47 ; 0,26] contre [0,26 ; 0,13 ; 0,05], alors que c'est le même bois : sur cette photo, la
    mise à plat avait pris du linge et du mur avec le parquet). Si un autre parquet du logement a sa couleur mesurée sur au
    moins PHOTOS_COULEUR_SURES photos, la pièce vue une seule fois prend cette couleur-là (celle du parquet le plus vu) : dans
    un logement, les parquets sont presque toujours du même bois. Sans autre parquet sûr, rien ne change."""
    surs = [s for s in pieces.values() if s.get("famille") in BOIS and s.get("couleur_photo")
            and s.get("photos_couleur", 0) >= PHOTOS_COULEUR_SURES]
    if not surs:
        return
    reference = max(surs, key=lambda s: s.get("photos_couleur", 0))
    for s in pieces.values():
        if s.get("famille") in BOIS and s.get("couleur_photo") and s.get("photos_couleur", 0) < PHOTOS_COULEUR_SURES:
            s["couleur_photo_seule"] = s["couleur_photo"]  # gardée pour mémoire
            s["couleur_photo"] = list(reference["couleur_photo"])


PIECES_SECHES = ("entree", "degagement", "sejour", "chambre", "bureau", "placard")  # pas les pièces d'eau : leur sol change


def sols_des_espaces_ouverts(logement: dict) -> dict:
    """Une pièce SANS sol reconnu (aucune photo ne montre son sol) qui s'ouvre SANS CLOISON sur une pièce au sol reconnu prend
    le même sol (16/11/2026, app-004 : l'entrée, ouverte sur le séjour, recevait un carrelage par défaut alors que le parquet du
    séjour s'y prolonge). Seulement pour les pièces sèches (une cuisine ou une salle d'eau ouverte a souvent un autre sol).
    Le sol repris est marqué « ajoute » (supposé), avec la pièce d'où il vient ; de proche en proche (entrée, puis dégagement)."""
    from moteur.preparer_verification import limites_sans_mur
    from moteur.sol_a_plat import dans_polygone

    pieces = logement.get("pieces", [])
    voisins: dict[str, set] = {p["id"]: set() for p in pieces}
    for lim in limites_sans_mur(logement):
        (x0, y0), (x1, y1) = lim["debut"], lim["fin"]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        L = float(np.hypot(x1 - x0, y1 - y0)) or 1.0
        nx, ny = -(y1 - y0) / L * 0.15, (x1 - x0) / L * 0.15  # 15 cm de chaque côté du milieu de la limite
        cotes = []
        for sx, sy in ((mx + nx, my + ny), (mx - nx, my - ny)):
            cotes.append(next((p["id"] for p in pieces if dans_polygone(np.array([sx]), np.array([sy]), p["contour"])[0]), None))
        if cotes[0] and cotes[1] and cotes[0] != cotes[1]:
            voisins[cotes[0]].add(cotes[1])
            voisins[cotes[1]].add(cotes[0])
    par_id = {p["id"]: p for p in pieces}
    reconnu = lambda p: str((p.get("sol") or {}).get("source", "")).startswith(("brique photos", "même sol que"))
    # Seule une pièce SANS sol, ou au sol posé par la règle par défaut, reprend le sol de sa voisine : un sol choisi par quelqu'un
    # (à l'écran de vérification, dans un relevé) n'est jamais remplacé (défaut trouvé par la série de tests le 16/11/2026).
    libre = lambda p: p.get("sol") is None or p["sol"].get("source") == "regle_par_defaut"
    change = True
    while change:
        change = False
        for p in pieces:
            if reconnu(p) or not libre(p) or not p["id"].rsplit("_", 1)[0] in PIECES_SECHES:
                continue
            sources = [par_id[v] for v in sorted(voisins[p["id"]]) if reconnu(par_id[v])]
            if not sources:
                continue
            origine = max(sources, key=lambda q: float(q["sol"].get("confiance", 0.0)))
            p["sol"] = {**{k: v for k, v in origine["sol"].items() if k in ("matiere", "teinte", "couleur_photo", "echelle", "sens")},
                        "statut": "ajoute", "confiance": round(0.8 * float(origine["sol"].get("confiance", 0.5)), 2),
                        "source": f"même sol que {origine['id']} (espace ouvert, sans cloison)"}
            change = True
    return logement


def famille_decidee(pieces: dict, logement: dict, X: np.ndarray, Y: np.ndarray, classes=FAMILLES) -> np.ndarray:
    """Ce qu'Atelya a décidé en chaque point : la famille de la pièce, ou celle de sa zone (-1 : pièce non jugée)."""
    from moteur.sol_a_plat import dans_polygone
    sortie = np.full(np.shape(X), -1)
    contours = {p["id"]: p["contour"] for p in logement["pieces"]}
    for pid, s in pieces.items():
        dedans = dans_polygone(X, Y, contours[pid])
        sortie[dedans] = classes.index(s["famille"])
        for z in s["zones"]:
            sortie[dedans & dans_polygone(X, Y, z["contour"])] = classes.index(z["famille"])
    return sortie


def noter(resultat: dict, logement_verite: dict, couleurs_visees: dict | None = None) -> dict:
    """Note de la brique photos contre une vérité (logement dont les pièces ont leur sol et leurs zones) :
    - surface_juste : part du sol VU par les photos dont la famille décidée est la bonne ;
    - pieces_justes : pièces jugées dont le sol principal a la bonne famille ;
    - couleurs : écart (ΔE) entre la couleur mesurée et la couleur visée de la vérité, quand elle est donnée
      (couleurs_visees : {id de pièce: {"L", "a", "b"}}, ou {"<pièce>/zone<n>": …})."""
    carte = resultat["carte"]
    if carte is None:
        return {}
    X, Y = carte.centres()
    vue = carte.vue()
    verite = familles_verite(logement_verite, X[vue], Y[vue], carte.classes)
    decide = famille_decidee(resultat["pieces"], logement_verite, X[vue], Y[vue], carte.classes)
    jugees = (verite >= 0) & (decide >= 0)
    par_famille = {}
    for i, f in enumerate(carte.classes):
        m = jugees & (verite == i)
        if m.any():
            par_famille[f] = {"m2": round(float(m.sum() * carte.case ** 2), 1), "juste": round(float((decide[m] == i).mean()), 3)}
    pieces, couleurs = {}, {}
    for p in logement_verite["pieces"]:
        s = resultat["pieces"].get(p["id"])
        if s is None or not p.get("sol"):
            continue
        pieces[p["id"]] = {"trouve": s["famille"], "attendu": famille(p["sol"]["matiere"]), "zones_trouvees": len(s["zones"]),
                           "zones_attendues": len(p.get("zones_sol", []))}
        if couleurs_visees and p["id"] in couleurs_visees and s.get("couleur"):
            couleurs[p["id"]] = round(ecart_lab(s["couleur"], couleurs_visees[p["id"]]), 1)
    return {"surface_jugee_m2": round(float(jugees.sum() * carte.case ** 2), 1),
            "surface_juste": round(float((decide[jugees] == verite[jugees]).mean()), 3) if jugees.any() else None,
            "par_famille": par_famille,
            "pieces_justes": f"{sum(v['trouve'] == v['attendu'] for v in pieces.values())}/{len(pieces)}",
            "pieces": pieces, "ecarts_couleur": couleurs}


def prototypes_bibliotheque(oeil, bibliotheque, par_matiere: int = 16, graine: int = 3) -> dict:
    """L'empreinte moyenne (normée) de chaque matière de la bibliothèque, vue de dessus à sa vraie échelle (vignettes d'1 m,
    tournées de 0 ou 90°, un peu floutées comme un sol vu sur photo). Les matières dessinées par calcul dans Blender (sans
    photo) n'en ont pas."""
    import json as _json
    from pathlib import Path
    from moteur.images import lire_image
    from moteur.matieres import CALCULEES, NOMS_SOLS
    from moteur.oeil_dinov2 import empreintes
    alea = np.random.default_rng(graine)
    bib = Path(bibliotheque)
    infos = _json.loads((bib / "matieres.json").read_text(encoding="utf-8"))
    sortie = {}
    for matiere in NOMS_SOLS:
        if matiere in CALCULEES or matiere not in infos or not (bib / matiere / "couleur.jpg").is_file():
            continue
        tex = lire_image(bib / matiere / "couleur.jpg")
        tex = cv2.cvtColor(tex, cv2.COLOR_BGR2RGB)
        cote = int(tex.shape[1] / infos[matiere]["taille_image_m"][0] * VIGNETTE_M)
        copies = int(np.ceil(cote / min(tex.shape[:2]))) + 1  # une matière de 30 cm se répète plusieurs fois dans 1 m
        grand = np.tile(tex, (copies, copies, 1))
        vignettes_m = []
        for _ in range(par_matiere):
            l0 = int(alea.integers(0, max(1, grand.shape[0] - cote)))
            c0 = int(alea.integers(0, max(1, grand.shape[1] - cote)))
            v = cv2.resize(grand[l0:l0 + cote, c0:c0 + cote], (VIGNETTE_PX, VIGNETTE_PX), interpolation=cv2.INTER_AREA)
            if alea.random() < 0.5:
                v = np.rot90(v).copy()
            vignettes_m.append(cv2.GaussianBlur(v, (0, 0), float(alea.uniform(0.5, 2.0))))
        e = empreintes(oeil, np.stack(vignettes_m)).mean(0)
        sortie[matiere] = e / max(np.linalg.norm(e), 1e-9)
    return sortie
