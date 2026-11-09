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
CASE_M = 0.25  # côté d'une case de la carte des sols


def famille(matiere: str) -> str:
    """La famille d'une matière du catalogue (moteur/matieres.py)."""
    if matiere in _FAMILLE:
        return _FAMILLE[matiere]
    from moteur.matieres import sorte
    return "carreaux" if sorte(matiere) == "carrelage" else "lames"


assert all(famille(m) in FAMILLES for m in NOMS_SOLS)


def vignettes(image: np.ndarray, finesse: np.ndarray, resolution: float, taille_m: float = VIGNETTE_M,
              pas_m: float = PAS_M, couverture_min: float = COUVERTURE_MIN, sortie_px: int = VIGNETTE_PX):
    """Découpe une image à plat en vignettes. Rend (vignettes N × sortie_px × sortie_px × 3, centres (N, 2) en pixels de
    l'image à plat (ligne, colonne), finesse moyenne (N,)). Le peu qui n'est pas vu dans une vignette est rempli par la
    couleur moyenne de ce qui est vu (sinon l'œil verrait un bord noir)."""
    cote, pas = int(round(taille_m / resolution)), max(1, int(round(pas_m / resolution)))
    vu = finesse > 0
    integrale = cv2.integral(vu.astype(np.uint8))
    h, w = vu.shape
    images, centres, finesses = [], [], []
    for l0 in range(0, h - cote + 1, pas):
        for c0 in range(0, w - cote + 1, pas):
            n = integrale[l0 + cote, c0 + cote] - integrale[l0, c0 + cote] - integrale[l0 + cote, c0] + integrale[l0, c0]
            if n < couverture_min * cote * cote:
                continue
            morceau = image[l0:l0 + cote, c0:c0 + cote].copy()
            m = vu[l0:l0 + cote, c0:c0 + cote]
            morceau[~m] = morceau[m].mean(axis=0).astype(np.uint8)
            images.append(cv2.resize(morceau, (sortie_px, sortie_px), interpolation=cv2.INTER_AREA if cote > sortie_px
                                     else cv2.INTER_LINEAR))
            centres.append((l0 + cote / 2, c0 + cote / 2))
            finesses.append(float(finesse[l0:l0 + cote, c0:c0 + cote][m].mean()))
    if not images:
        return np.zeros((0, sortie_px, sortie_px, 3), np.uint8), np.zeros((0, 2)), np.zeros(0)
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
          case: float = CASE_M, taille_m: float = VIGNETTE_M) -> None:
    """Ajoute les avis des vignettes aux cases qu'elles couvrent (leur moitié centrale, pour rester précis aux limites)."""
    demi = int(round(taille_m / 4 / case))  # la moitié centrale de la vignette, en cases
    poids = np.sqrt(np.clip(finesses, 0, 4)) * probabilites.max(1)  # photo fine + avis tranché = plus de poids
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


def sols_des_pieces(carte: CarteDesSols, logement: dict, zone_min_m2: float = ZONE_MIN_M2) -> dict:
    """Pour chaque pièce assez vue : la famille de son sol (la plus votée) et ses zones d'une autre famille (contours
    convexes en mètres). Les votes sont d'abord lissés sur 3 × 3 cases (75 cm) : une case isolée suit ses voisines."""
    from moteur.sol_a_plat import dans_polygone
    sol = carte.votes_sol()
    lisses = np.stack([cv2.blur(sol[..., k].astype(np.float32), (3, 3)) for k in range(sol.shape[-1])], -1)
    vue = carte.vue()
    fam = np.where(vue, np.array(carte.indices_sol)[lisses.argmax(-1)], -1)
    X, Y = carte.centres()
    case2 = carte.case ** 2
    sorties = {}
    for p in logement["pieces"]:
        dedans = dans_polygone(X, Y, p["contour"]) & vue
        if dedans.sum() * case2 < SURFACE_VUE_MIN_M2:
            continue
        compte = np.bincount(fam[dedans], minlength=len(carte.classes))
        principale = int(compte.argmax())
        zones = []
        autre = (dedans & (fam != principale)).astype(np.uint8)
        n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(autre, connectivity=8)
        for k in range(1, n):
            morceau = etiquettes == k
            if morceau.sum() * case2 < zone_min_m2:
                continue
            f = int(np.bincount(fam[morceau], minlength=len(carte.classes)).argmax())
            lignes, colonnes = np.nonzero(morceau)
            coins = np.concatenate([np.stack([colonnes + dc, lignes + dl], 1) for dc in (0, 1) for dl in (0, 1)]).astype(np.float32)
            enveloppe = cv2.convexHull(coins)[:, 0]
            contour = [[round(float(carte.origine[0] + c * carte.case), 3), round(float(carte.origine[1] - l * carte.case), 3)]
                       for c, l in enveloppe]
            zones.append({"famille": carte.classes[f], "contour": contour[::-1], "surface_m2": round(float(morceau.sum() * case2), 2)})
        sorties[p["id"]] = {"famille": carte.classes[principale], "surface_vue_m2": round(float(dedans.sum() * case2), 2),
                            "part": round(float(compte[principale] / max(compte.sum(), 1)), 3), "zones": zones}
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
def reconnaitre(releve: dict, logement: dict, racine, oeil, clf: Classifieur, journal=lambda *_: None) -> dict:
    """Photos calées du client → sol de chaque pièce (famille, zones, couleur). Rend aussi la carte et le sol assemblé."""
    from moteur.sol_a_plat import assembler, dans_polygone, photos_a_plat
    from moteur.oeil_dinov2 import empreintes
    vues = photos_a_plat(releve, logement, racine, journal=journal)
    if not vues:
        return {"pieces": {}, "carte": None, "image": None, "finesse": None}
    v0 = vues[0][2]
    h, w = v0.image.shape[:2]
    votes = np.zeros((int(np.ceil(h * v0.resolution / CASE_M)), int(np.ceil(w * v0.resolution / CASE_M)), len(clf.classes)))
    for nom, _, vue in vues:
        v, centres, finesses = vignettes(vue.image, vue.finesse, vue.resolution)
        if len(v):
            voter(votes, centres, clf.probabilites(empreintes(oeil, v)), finesses, vue.resolution)
        journal(f"  {nom} : {len(v)} vignettes")
    carte = CarteDesSols(votes, v0.origine, CASE_M, tuple(clf.classes))
    pieces = sols_des_pieces(carte, logement)
    image, finesse, _ = assembler([v for _, _, v in vues])
    # la couleur se mesure là où l'œil voit du SOL : pas dans les cases où il voit surtout des meubles (lit, tapis…)
    meuble = carte.part_meuble()
    case_l = np.minimum((np.arange(h) * v0.resolution / CASE_M).astype(int), meuble.shape[0] - 1)
    case_c = np.minimum((np.arange(w) * v0.resolution / CASE_M).astype(int), meuble.shape[1] - 1)
    sol_pur = (finesse > 0) & (meuble[case_l][:, case_c] < 0.5)
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
    return {"pieces": pieces, "carte": carte, "image": image, "finesse": finesse, "origine": v0.origine,
            "resolution": v0.resolution}


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
