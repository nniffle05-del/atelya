"""L'APPAREIL DE CHAQUE PHOTO AFFINÉ DANS L'IMAGE (« la place des appareils des photos », 24/11/2026).

Pourquoi. Le calage (moteur/caler_photos.py) dit d'où chaque photo du client est prise à 0,3-0,5 m près, avec un zoom vu trop
serré de 14 à 30 % par MoGe-2. Tout ce qui se pose ou se compare « depuis la place des photos » en hérite (meubles décalés le
long du regard, fenêtre de la maquette à côté de la vraie, toiles de la vue par les fenêtres, comparaisons photo | film).
Mesuré le 24/11/2026 sur les repères relevés à la main des corrigés : vus par l'appareil d'Atelya, les arêtes des murs
tombaient à 23-36 pixels de leur place sur la photo (4 pixels pour un appareil relevé à la main).

Moyen : comme un géomètre qui « recale » sa vue, on cherche l'appareil qui fait tomber les murs du PLAN sur les murs de la
PHOTO. Ce que la photo montre des murs, Atelya le trouve SEUL :
  - la ligne où les murs touchent le PLAFOND et celle où ils touchent le SOL, colonne par colonne, dans le relief de MoGe-2
    (là où une surface à plat rencontre une surface debout) : `jonctions`. Pièges traités : la corniche (l'angle du mur et
    du plafond est pris dans le haut de la bande qu'elle fait sur la photo), la suspension et la retombée de poutre (debout
    elles aussi, mais pas à la place du mur), le meuble ou le rideau qui cache le mur et lui ressemble (rectangles d'OWLv2 :
    `cache_mur`) ; le sol est la surface à plat la plus BASSE (un lit montre parfois plus de surface que le sol :
    `repere_du_mur`) ;
  - en plus, quand la lecture des fenêtres existe (moteur/vitrages.py), les lignes LUES : pied et haut du mur de la fenêtre,
    tour de la menuiserie (`reperes_lus`).
L'appareil (place, hauteur, cap, zoom, horizon) est déplacé par petits pas, depuis celui du calage et depuis plusieurs autres
départs, jusqu'à ce que les murs du plan vus par lui tombent sur ces lignes (`affiner`). Il n'est gardé que s'il colle
vraiment (`accepte`) ; sinon l'appareil du calage reste (`affiner_une_photo`).

Une photo qui ne montre pas assez de murs n'est pas touchée : il faut le haut des murs sur au moins 30 % de sa largeur
(ETENDUE_MIN ; cuisines pleines de meubles, gros plans).

Ce que la méthode ne sait pas : un mur caché par un meuble qu'OWLv2 ne voit pas (l'appareil est alors déplacé de la profondeur
du meuble) ; glisser le long d'un mur sans repère (le rappel vers la place du calage décide ; les lignes lues des fenêtres
fixent ce glissement quand elles existent) ; un plan faux (la mesure ne vaut pas mieux que le plan) ; une hauteur sous plafond
fausse (les distances suivent) ; une corniche (l'angle caché est connu à quelques pixels près).
Mesures : pc/essais-place-appareils (caler.py, affiner.py, juger.py, chaine.py, non_recul_sols_meubles.py) et le journal.
"""
from __future__ import annotations

import math

import numpy as np

from . import caler_photos as cp
from .camera_photo import residus

VERSION = "0.1.0"
SOL_PARTAGE = cp.SOL_JUSTE_AU_CALAGE  # le sol et le plafond du relief par la règle partagée (2e temps du « sol pris pour un
                       #     lit ») : par défaut depuis le 26/11/2026 (accord de NT), suit ATELYA_SOL_JUSTE_AU_CALAGE
PAS_COLONNES = 6      # px : une colonne mesurée tous les 6 px (photo de 1206 px de large)
CORNICHE = 0.15        # où est l'angle du mur et du plafond dans la bande d'une corniche (0 = en haut de la bande, 1 = en bas)
BORNE_PX = 40.0        # px : au-delà, un écart ne compte pas plus (meuble pris pour un mur, porte ouverte)
NEUTRE_PX = 6.0        # px : écart compté pour une colonne dont le regard traverse une limite sans mur du plan
ACCEPTE_PX = 12.0      # px : l'appareil affiné n'est gardé que s'il colle à mieux que cela (sinon : celui du calage)
FAMILLE_PX = 25.0      # … et si aucune famille bien fournie (plafond, sol : 30 points) ne reste au-delà de cela
POINTS_MIN = 30        # points de plafond et de sol en dessous desquels la photo ne dit rien d'assez sûr
PLAFOND_MIN = 15       # … et points de plafond : le pied des murs seul ne suffit pas (un meuble bas lui ressemble, et sans le
                       #     haut des murs rien ne fixe ensemble la distance, la hauteur de l'appareil et le zoom)
ETENDUE_MIN = 0.3      # … et part de la largeur de la photo sur laquelle on voit le haut des murs : un bout de mur dans un coin
                       #     de l'image ne suffit pas à régler un appareil (cuisine d'app-002 : 31 points sur un cinquième de la
                       #     largeur, appareil tourné de 4° à tort, meubles de cuisine perdus)
RAPPEL_PX_M = 4.0      # px par mètre : ce que coûte de s'éloigner de la place du calage ; là où les lignes ne disent rien (glisser
                       #     le long d'un mur sans repère) l'appareil reste donc à la place du calage, et un vrai déplacement
                       #     (les lignes y gagnent bien plus) n'est pas freiné
RAPPEL_Z = 0.3         # m : … vers la hauteur de l'appareil vue par le relief
RAPPEL_V0 = 25.0       # px : … vers l'horizon du calage
RAPPEL_ZOOM = 0.08     # … vers le zoom commun du lot (quand les lignes de fuite des photos s'accordent), en logarithme
PORTE_M = 1.2          # m : l'appareil peut se tenir à moins de cela d'une porte de sa pièce (photo prise du seuil), et
                       #     une porte plus proche n'arrête pas son regard
LOIN_M = 1.5           # m : l'appareil affiné ne s'éloigne pas de plus de la place du calage
MARGE_MUR = 0.25       # m : un photographe ne colle pas son appareil à un mur : plus près, l'appareil est un peu pénalisé
                       #     (jusqu'à NEUTRE_PX) ; et jamais à moins de CONTACT_MUR. Sans cela l'affinage reculait l'appareil
                       #     DANS le mur pour voir plus large (app-004, séjour et chambre : à 1 cm du mur)
CONTACT_MUR = 0.10     # m : l'appareil affiné n'est jamais plus près d'un mur (sauf si le calage l'y avait mis)
ZOOMS = (0.70, 0.78, 0.86, 0.94)   # départs essayés pour le zoom, en part de celui du calage (MoGe-2 le voit trop serré)
PAS_M = (-0.8, -0.4, 0.4, 0.8)     # départs essayés le long du regard (appareil reculé ou avancé)
GARDES = 3                         # arrivées de la recherche grossière reprises par la recherche fine
# ce qui cache un mur et lui ressemble (debout, d'un seul tenant) : demandé à OWLv2 ; le pied ou le haut d'un mur n'est pas
# cherché là (un meuble de 60 cm de profondeur, pris pour le mur, déplacerait l'appareil d'autant)
CACHE_MUR = ("a cabinet", "a bookshelf", "a shelving unit", "a wardrobe", "kitchen cabinets", "a sideboard", "a chest of drawers",
             "a tv stand", "a refrigerator", "a curtain", "curtains", "sheer curtains", "a bed", "a sofa", "a couch")
SEUIL_CACHE = 0.25
NOMS = ("x", "y", "z", "cap", "tangage", "f", "u0", "v0")


# ================================================================ le plan
def faces_pleines(logement: dict, plan: dict) -> np.ndarray:
    """Les faces du plan (moteur.caler_photos.plan_du_logement) qui sont de vrais murs. Une limite entre deux pièces SANS mur
    (espace ouvert coupé en deux pièces, passe-plat dessiné comme un passage) n'arrête pas le regard, et le plan ne dit pas
    ce qu'il y a au-dessus d'elle. Un plan relevé en partie (moins de 80 % des faces portées par un mur) : toutes pleines.
    (Même règle que le calage : moteur.caler_photos.faces_pleines.)"""
    return cp.faces_pleines(logement, plan)


def tirer(A: np.ndarray, B: np.ndarray, o: np.ndarray, angles_deg: np.ndarray, portes: np.ndarray | None = None) -> np.ndarray:
    """Distance du premier mur depuis o, dans chaque direction (degrés). portes : les faces qui sont des portes ; une porte à
    moins de PORTE_M de l'appareil n'arrête pas le regard (photo prise du seuil : on regarde À TRAVERS elle)."""
    if not len(A):
        return np.full(len(angles_deg), np.inf)
    D = np.stack([np.cos(np.radians(angles_deg)), np.sin(np.radians(angles_deg))], 1)
    e = B - A
    ap = A - o[None]
    den = D[:, None, 0] * e[None, :, 1] - D[:, None, 1] * e[None, :, 0]
    ok = np.abs(den) > 1e-9
    den = np.where(ok, den, 1.0)
    t = (ap[None, :, 0] * e[None, :, 1] - ap[None, :, 1] * e[None, :, 0]) / den
    s = (ap[None, :, 0] * D[:, None, 1] - ap[None, :, 1] * D[:, None, 0]) / den
    touche = ok & (t > 0.03) & (s >= 0) & (s <= 1)
    if portes is not None:
        touche &= ~(portes[None, :] & (t < PORTE_M))
    return np.where(touche, t, np.inf).min(1)


def lignes_du_plan(cam, A: np.ndarray, B: np.ndarray, hsp: float, u: np.ndarray, portes: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ce que cet appareil verrait du plan, aux colonnes `u` de la photo : la ligne (pixels) où les murs touchent le plafond,
    celle où ils touchent le sol, et la distance du mur (m). Appareil de niveau (moteur/camera_photo.py)."""
    x, y, z, cap, _, f, u0, v0 = cam
    theta = np.arctan((np.asarray(u, float) - u0) / f)
    rho = tirer(A, B, np.array([x, y]), cap - np.degrees(theta), portes)
    devant = np.maximum(rho * np.cos(theta), 1e-3)
    return v0 - f * (hsp - z) / devant, v0 + f * z / devant, rho


# ================================================================ la photo
def _niveau(v: np.ndarray, vers_le_bas: bool, pas: float = 0.02, part: float = 0.25) -> float | None:
    """Le niveau d'une grande surface à plat (sol ou plafond) parmi les hauteurs `v` : le pic le plus BAS (sol) ou le plus HAUT
    (plafond) qui pèse au moins `part` du plus gros pic. Le plus gros pic seul se trompe quand un lit ou un plan de travail
    montre plus de surface à plat que le sol (app-004 : chambre, appareil vu à 0,97 m pour 1,33 ; cuisine, 0,47 m pour 1,47)."""
    if len(v) < 30:
        return None
    h, b = np.histogram(v, bins=np.arange(v.min() - pas, v.max() + 2 * pas, pas))  # une case de marge de chaque côté
    h = np.convolve(h, np.ones(3), "same")
    pics = [i for i in range(len(h)) if h[i] >= part * h.max() and h[i] >= h[max(0, i - 3):i + 4].max()]
    i = min(pics) if vers_le_bas else max(pics)
    return float(b[i] + pas / 2)


def repere_du_mur(mes: dict, hsp: float) -> dict | None:
    """Comme moteur.caler_photos.repere (chaque point de la photo : hauteur au-dessus du sol, direction, distance à plat), mais
    le sol est la surface à plat la plus BASSE et le plafond la plus HAUTE (`_niveau`).
    SOL_PARTAGE : la règle partagée d'Atelya à la place (moteur.caler_photos.sol_et_plafond, 25/11/2026)."""
    if SOL_PARTAGE:
        return cp.repere(mes, hsp, juste=True, plafond_haut=True)
    P, N, M, haut = mes["points"], mes["normales"], mes["masque"], mes["haut"]
    av = np.array([0, 0, 1.0]) - haut * haut[2]
    av /= np.linalg.norm(av)
    dr = np.cross(av, haut)
    if dr[0] < 0:
        dr = -dr
    h, a, b = P @ haut, P @ dr, P @ av
    nh = N @ haut
    horiz = M & (np.abs(nh) > 0.95)
    sol, plaf = _niveau(h[horiz & (h < -0.4)], True), _niveau(h[horiz & (h > 0.3)], False)
    ech = 1.0
    if sol is not None and plaf is not None and 0.75 < hsp / (plaf - sol) < 1.33:
        ech = hsp / (plaf - sol)
    elif sol is None and plaf is None:
        return None
    if sol is None:
        sol = plaf - hsp / ech
    return {"h": (h - sol) * ech, "phi": np.degrees(np.arctan2(-a, b)), "r": np.hypot(a, b) * ech, "M": M,
            "vert": np.abs(nh) < 0.35, "devant": b > 0.2, "ech": ech, "z": -sol * ech, "nh": nh}


def cache_mur(owl, requetes, rgb: np.ndarray) -> np.ndarray:
    """Le masque des rectangles où OWLv2 voit un meuble ou un rideau qui cache le mur (requetes = owl.textes(CACHE_MUR))."""
    from .owlv2 import objets

    m = np.zeros(rgb.shape[:2], bool)
    for o in objets(owl.detecter(rgb, requetes), list(CACHE_MUR), seuil=SEUIL_CACHE, recouvrement_max=0.9):
        x0, y0, x1, y1 = (int(round(c)) for c in o["boite"])
        m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def jonctions(mes: dict, hsp: float, caches: np.ndarray | None = None) -> dict:
    """Sur la photo, colonne par colonne : où le mur touche le plafond, où il touche le sol (pixels), d'après le relief de
    MoGe-2 (`mes` : moteur.caler_photos.mesurer). → {"plafond": (u, v), "sol": (u, v)} (tableaux n × 2), "z" (hauteur de
    l'appareil vue par le relief), "largeur" (de la photo).
    Le plafond : sous la dernière ligne de vrai plafond (bien à plat) vient le mur (debout, à la distance du mur : une
    suspension, debout elle aussi mais plus près, est écartée). Entre les deux, une CORNICHE fait une bande ni à plat ni debout
    (20 à 35 px sur app-002) ; l'angle caché du mur et du plafond est dans le haut de cette bande (tout en haut pour une frise
    plaquée au mur, au quart pour une corniche aussi saillante que haute) : on le prend à CORNICHE de la bande.
    Le sol : au-dessus de la première ligne de sol à plat vient le mur, s'il est bien à la distance du mur (pas un meuble).
    caches : là où un meuble ou un rideau cache le mur (`cache_mur`) : rien n'y est mesuré."""
    vide = {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
    R = repere_du_mur(mes, hsp)
    if R is None:
        return vide
    H, W = R["M"].shape
    aplat = R["M"] & (np.abs(R["nh"]) > 0.85)
    plaf = R["M"] & (np.abs(R["nh"]) > 0.95) & (R["h"] > hsp - 0.12)   # le vrai plafond, bien à plat (pas les pans d'une corniche)
    sol, debout = aplat & (R["h"] < 0.25), R["M"] & R["vert"]
    mur = cp._mur_par_direction(R, hsp)
    if len(mur) < 15:
        return {**vide, "z": float(R["z"])}
    d = np.array(sorted(mur))
    rel = R["r"] - np.interp(R["phi"], d, np.array([mur[i] for i in d]), left=np.nan, right=np.nan)
    if caches is None:
        caches = np.zeros((H, W), bool)
    ech = W / 1206
    court, long_, prolonge = int(round(4 * ech)), int(round(50 * ech)), int(round(45 * ech))
    jp, js = [], []
    for u in range(int(3 * ech), W - int(3 * ech), max(1, int(round(PAS_COLONNES * ech)))):
        p, s, m, h = plaf[:, u], sol[:, u], debout[:, u], R["h"][:, u]
        lignes = np.flatnonzero(p)
        if len(lignes) >= court:
            bas = int(lignes[-1])                                    # dernière ligne de vrai plafond (bien à plat)
            dessous = np.flatnonzero(m[bas + 1:bas + 1 + long_])
            if p[max(0, bas - court + 1):bas + 1].all() and len(dessous):
                v1 = bas + 1 + int(dessous[0])                       # première ligne de mur sous le plafond
                rangs = np.arange(v1 + 2, min(H, v1 + 2 + prolonge))
                rangs = rangs[m[rangs] & (np.abs(rel[rangs, u]) < 0.25)]
                if len(rangs) >= 15 and caches[rangs, u].mean() < 0.5:
                    # contrôle : ce mur, prolongé vers le haut (sa hauteur varie en ligne droite le long d'une colonne),
                    # atteint bien la hauteur du plafond dans la bande ; sinon ce n'est pas le mur de CE plafond (retombée
                    # de poutre, coffre, plafond à caissons, meuble haut)
                    a, b = np.polyfit(rangs, h[rangs], 1)
                    if a < -1e-5 and bas - 8 * ech <= (float(np.median(h[lignes[-min(len(lignes), 3 * prolonge):]])) - b) / a <= v1 + 8 * ech:
                        jp.append((u + 0.5, bas + 0.5 + CORNICHE * (v1 - bas - 1)))
        lignes = np.flatnonzero(s)
        if len(lignes) >= court:
            haut = int(lignes[0])
            if s[haut:haut + court].all():
                dessus = np.flatnonzero(m[max(0, haut - long_):haut][::-1])
                if len(dessus):
                    v1 = haut - 1 - int(dessus[0])                   # premier pixel debout au-dessus du sol
                    rangs = np.arange(max(0, v1 - 5 * court), v1 + 1)
                    r = rel[rangs, u][m[rangs]]
                    if len(r) >= 2 * court and np.isfinite(r).any() and np.nanmedian(np.abs(r)) < 0.15 and caches[rangs, u].mean() < 0.5:
                        js.append((u + 0.5, (haut + v1 + 1) / 2))
    return {"plafond": np.array(jp).reshape(-1, 2), "sol": np.array(js).reshape(-1, 2), "z": float(R["z"]), "largeur": W}


def reperes_lus(logement: dict, fenetres: list[dict]) -> list[dict]:
    """Les lignes LUES des fenêtres d'une photo (moteur/vitrages.py) → repères au format de moteur/camera_photo.py, chacun avec
    « quoi » (sol, plafond, haut, bas : des horizontales du mur de la fenêtre ; gauche, droite : les montants du tour de la
    menuiserie) et « baie ». Le logement doit porter les fenêtres à la hauteur vue sur les photos (moteur/hauteur_baies.py)."""
    from .equipements import repere_de_la_baie
    from .hauteur_baies import points

    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    par_baie: dict[str, list[dict]] = {}
    for f in fenetres:
        par_baie.setdefault(f.get("baie"), []).append(f)
    sortie = []
    for baie, fs in par_baie.items():
        o = next((o for o in logement.get("ouvertures", []) if o.get("id") == baie), None)
        rep = repere_de_la_baie(o, logement) if o else None
        if rep is None:
            continue
        c, n = rep["centre"], rep["n"]
        d = np.array([-n[1], n[0]])  # la droite de l'image pour qui regarde le mur depuis la pièce (regard = −n)
        z0 = float(o.get("allege", 0.0) or 0.0)
        z1 = z0 + float(o.get("hauteur", 2.1))
        p3 = lambda s, z: [float(c[0] + d[0] * s), float(c[1] + d[1] * s), float(z)]  # noqa: E731
        sol = next((points(f.get("sol")) for f in fs if f.get("sol") is not None), [])
        plafond = next((points(f.get("plafond")) for f in fs if f.get("plafond") is not None), [])
        for quoi, pts, z in (("sol", sol, 0.0), ("plafond", plafond, hsp)):
            if pts:
                sortie.append({"type": "ligne", "a": p3(-1.0, z), "b": p3(1.0, z), "p1": list(pts[0]), "p2": list(pts[-1]), "quoi": quoi, "baie": baie})
        porteur = next((f for f in fs if f.get("cadre")), None)
        if porteur is None:
            continue
        hg, hd, bd, bg = (list(map(float, p)) for p in porteur["cadre"])
        demi = rep["demi"]
        if not porteur.get("haut_au_moins"):
            sortie.append({"type": "ligne", "a": p3(-demi, z1), "b": p3(demi, z1), "p1": hg, "p2": hd, "quoi": "haut", "baie": baie})
        if not porteur.get("bas_cache"):
            sortie.append({"type": "ligne", "a": p3(-demi, z0), "b": p3(demi, z0), "p1": bg, "p2": bd, "quoi": "bas", "baie": baie})
        sortie.append({"type": "ligne", "a": p3(-demi, z0), "b": p3(-demi, z1), "p1": hg, "p2": bg, "quoi": "gauche", "baie": baie})
        sortie.append({"type": "ligne", "a": p3(demi, z0), "b": p3(demi, z1), "p1": hd, "p2": bd, "quoi": "droite", "baie": baie})
    return sortie


# ================================================================ le coût d'un appareil
class Scene:
    """Le plan prêt pour la mesure : faces pleines, portes, limites sans mur, hauteur sous plafond."""

    def __init__(self, logement: dict, plan: dict | None = None):
        self.plan = plan or cp.plan_du_logement(logement)
        pleines = faces_pleines(logement, self.plan)
        self.A, self.B = self.plan["A"][pleines], self.plan["B"][pleines]
        self.portes = self.plan["sorte"][pleines] == 1
        self.limites = (self.plan["A"][~pleines], self.plan["B"][~pleines])
        self.hsp = float(self.plan["hsp"])


def cout(cam, scene: Scene, jon: dict, reperes: list[dict] | None = None, detail: bool = False, borne: float = BORNE_PX):
    """Écart moyen (pixels, borné) entre ce que la photo montre et ce que cet appareil verrait du plan. detail : par famille
    (« plafond », « sol », « lus »)."""
    x, y, z, cap, _, f, u0, v0 = cam
    parts = {}
    n_p, n_s = len(jon["plafond"]), len(jon["sol"])
    if n_p + n_s:
        pts = np.concatenate([jon["plafond"], jon["sol"]]) if n_p and n_s else (jon["plafond"] if n_p else jon["sol"])
        o = np.array([x, y])
        theta = np.arctan((pts[:, 0] - u0) / f)
        angles = cap - np.degrees(theta)
        rho = tirer(scene.A, scene.B, o, angles, scene.portes)
        haut = np.where(np.arange(len(pts)) < n_p, -(scene.hsp - z), z)   # le plafond au-dessus de l'horizon, le sol en dessous
        e = np.minimum(np.abs(pts[:, 1] - (v0 + f * haut / np.maximum(rho * np.cos(theta), 1e-3))), borne)
        if len(scene.limites[0]):
            # le regard traverse une limite SANS mur du plan avant de toucher un mur : le plan ne dit pas s'il y a une retombée
            # au-dessus ; ces colonnes ne jugent pas l'appareil (écart « neutre » : ni gagné ni perdu, pour qu'un appareil ne
            # se cache pas derrière elles)
            e = np.where(tirer(scene.limites[0], scene.limites[1], o, angles) < rho - 0.05, NEUTRE_PX, e)
        if n_p:
            parts["plafond"] = e[:n_p]
        if n_s:
            parts["sol"] = e[n_p:]
    if reperes:
        try:
            e = np.abs(residus(cam, reperes))
            parts["lus"] = np.minimum(np.where(np.isfinite(e), e, borne), borne)
        except (ZeroDivisionError, FloatingPointError):
            parts["lus"] = np.full(2 * len(reperes), borne)
    if detail:
        return {k: float(v.mean()) for k, v in parts.items()}
    # chaque famille pèse selon ce qu'elle sait : le plafond et le sol ensemble (beaucoup de points), les lignes lues à part
    moyennes = []
    if "plafond" in parts or "sol" in parts:
        moyennes.append(float(np.concatenate([parts[k] for k in ("plafond", "sol") if k in parts]).mean()))
    if "lus" in parts:
        moyennes.append(float(parts["lus"].mean()))
    return float(np.mean(moyennes)) if moyennes else 0.0


def affiner(cam0, scene: Scene, jon: dict, reperes: list[dict] | None, rappels: dict, piece: int | None = None, departs=()) -> tuple[np.ndarray, float]:
    """L'appareil qui colle le mieux, cherché par petits pas depuis `cam0` et depuis plusieurs autres départs (zoom plus large,
    avec ou sans rapprochement ; appareil avancé ou reculé ; `departs`). En deux temps : d'abord, de chaque départ, une recherche
    GROSSIÈRE avec une borne large sur les écarts (un appareil faux de 80 px « sent » encore dans quel sens aller) et un point
    sur trois ; puis une recherche FINE, avec la borne de service, depuis les GARDES meilleures arrivées. rappels : {indice du paramètre: (valeur, écart toléré)} : tire doucement vers une valeur plausible.
    piece : l'appareil reste dans cette pièce (numéro), ou à moins de PORTE_M d'une de ses portes."""
    plan = scene.plan
    cam0 = np.array(cam0, float)
    seuils = (plan["face_piece"] == piece) & (plan["sorte"] == 1) if piece is not None else None
    murs = (scene.A[~scene.portes], scene.B[~scene.portes])  # les murs pleins (pas les portes : on se tient sur un seuil)
    contact = min(CONTACT_MUR, float(cp._dist_seg(cam0[None, :2], murs[0], murs[1]).min())) - 1e-6 if len(murs[0]) else 0.0

    gros = {"plafond": jon["plafond"][::3], "sol": jon["sol"][::3]}

    def total(c, borne=BORNE_PX, j=jon):
        if not (0.4 <= c[2] <= scene.hsp - 0.25) or c[5] < 150:
            return 1e9
        if math.hypot(c[0] - cam0[0], c[1] - cam0[1]) > LOIN_M:
            return 1e9
        ou = cp.piece_de(plan, c[None, :2])[0]
        if ou < 0:
            return 1e9
        if piece is not None and ou != piece and not (seuils.any() and cp._dist_seg(c[None, :2], plan["A"][seuils], plan["B"][seuils]).min() < PORTE_M):
            return 1e9
        v = cout(c, scene, j, reperes, borne=borne) + RAPPEL_PX_M * math.hypot(c[0] - cam0[0], c[1] - cam0[1])
        if len(murs[0]):
            d = float(cp._dist_seg(c[None, :2], murs[0], murs[1]).min())
            if d < contact:
                return 1e9
            v += NEUTRE_PX * max(0.0, MARGE_MUR - d) / (MARGE_MUR - CONTACT_MUR)
        for i, (val, tol) in rappels.items():
            ecart = (math.log(c[i] / val) if i == 5 else c[i] - val) / tol
            v += BORNE_PX / 4 * ecart * ecart / (1 + abs(ecart))  # doux près de la valeur, pas plus qu'en ligne droite au loin
        return v

    def bouger(c, quoi, pas):
        """Un petit pas de l'appareil : le long de son regard, de côté, en hauteur, en cap, en zoom, en horizon ; et deux pas
        COUPLÉS, ceux que les lignes d'un mur distinguent le moins bien (le long desquels une recherche paramètre par
        paramètre piétine) : avancer en élargissant le zoom d'autant, glisser de côté en tournant d'autant."""
        c = c.copy()
        ax, ay = math.cos(math.radians(c[3])), math.sin(math.radians(c[3]))
        loin = devant if math.isfinite(devant) else 3.0
        if quoi in ("regard", "travelling"):
            c[0] += pas * 0.1 * ax
            c[1] += pas * 0.1 * ay
            if quoi == "travelling":
                c[5] *= max(0.5, 1 - pas * 0.1 / max(loin, 0.5))
        elif quoi in ("cote", "glisser"):
            c[0] -= pas * 0.1 * ay
            c[1] += pas * 0.1 * ax
            if quoi == "glisser":
                c[3] -= math.degrees(pas * 0.1 / max(loin, 0.5))
        elif quoi == "hauteur":
            c[2] += pas * 0.05
        elif quoi == "cap":
            c[3] += pas * 1.0
        elif quoi == "zoom":
            c[5] *= 1 + pas * 0.03
        else:
            c[7] += pas * 4.0
        return c

    def descendre(c, borne, j, fin):
        best = total(c, borne, j)
        pas = 1.0
        for _ in range(80):
            bouge = False
            for quoi in ("regard", "cote", "hauteur", "cap", "zoom", "horizon", "travelling", "glisser"):
                for sg in (-1, 1):
                    c2 = bouger(c, quoi, sg * pas)
                    v = total(c2, borne, j)
                    if v < best - 1e-6:
                        best, c, bouge = v, c2, True
            if not bouge:
                pas = pas / 2
                if pas * 0.1 < fin:
                    break
        return c

    devant = float(tirer(scene.A, scene.B, cam0[:2], np.array([cam0[3]]), scene.portes)[0])
    a = math.radians(cam0[3])
    lances = [cam0.copy()]
    for k in ZOOMS:
        c = cam0.copy()
        c[5] *= k
        lances.append(c)                                       # zoom plus large, appareil à sa place
        if math.isfinite(devant):                              # … ou rapproché d'autant (le mur d'en face garde sa taille)
            recul = min(devant * (1 - k), LOIN_M * 0.9)
            c2 = c.copy()
            c2[0] += recul * math.cos(a)
            c2[1] += recul * math.sin(a)
            lances.append(c2)
    for pas_m in PAS_M:                                        # appareil reculé ou avancé, même zoom
        c = cam0.copy()
        c[0] += pas_m * math.cos(a)
        c[1] += pas_m * math.sin(a)
        lances.append(c)
    lances += [np.array(d, float) for d in departs]
    arrivees = []
    for c in lances:
        if total(c) < 1e8:
            c = descendre(c, 3 * BORNE_PX, gros, 0.02)
            arrivees.append((total(c), c))
    arrivees.sort(key=lambda t: t[0])
    meilleur = (total(cam0), cam0)
    for _, c in arrivees[:GARDES]:
        c = descendre(c, BORNE_PX, jon, 0.004)
        v = total(c)
        if v < meilleur[0] - 1e-6:
            meilleur = (v, c)
    return meilleur[1], meilleur[0]


def accepte(cam, scene: Scene, jon: dict, reperes: list[dict] | None) -> bool:
    """L'appareil colle-t-il assez pour remplacer celui du calage ?"""
    fin = cout(cam, scene, jon, reperes, detail=True)
    return cout(cam, scene, jon, reperes) <= ACCEPTE_PX and all(fin[k] <= FAMILLE_PX for k in ("plafond", "sol") if len(jon[k]) >= 30)


def affiner_une_photo(cam0, scene: Scene, jon: dict, reperes: list[dict] | None, rappels: dict, piece: int | None = None,
                      z_vu: float | None = None) -> tuple[np.ndarray, str]:
    """L'appareil affiné d'une photo, et comment : « lignes+lus », « lignes », « lus », ou « depart » (rien d'assez sûr :
    l'appareil du calage reste). D'abord avec les lignes du plafond et du sol trouvées seules (si la photo en montre assez),
    puis en y ajoutant les lignes lues des fenêtres ; chaque étage n'est gardé que s'il colle (`accepte`), sinon on
    redescend d'un étage. z_vu : la hauteur de l'appareil vue par le relief (un départ de plus)."""
    cam0 = np.array(cam0, float)
    vide = {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
    assez = (len(jon["plafond"]) + len(jon["sol"]) >= POINTS_MIN and len(jon["plafond"]) >= PLAFOND_MIN
             and float(np.ptp(jon["plafond"][:, 0])) >= ETENDUE_MIN * float(jon.get("largeur", 1206)))
    autres = [np.array([*cam0[:2], z_vu, *cam0[3:]], float)] if z_vu is not None and abs(z_vu - cam0[2]) > 0.1 else []
    seul = None
    if assez:
        c, _ = affiner(cam0, scene, jon, None, rappels, piece, departs=autres)
        if accepte(c, scene, jon, None):
            seul = c
    if reperes:
        if assez:
            c, _ = affiner(cam0, scene, jon, reperes, rappels, piece, departs=([seul] if seul is not None else []) + autres)
            if accepte(c, scene, jon, reperes):
                return c, "lignes+lus"
        else:
            c, _ = affiner(cam0, scene, vide, reperes, rappels, piece, departs=autres)
            if accepte(c, scene, vide, reperes):
                return c, "lus"
    return (seul, "lignes") if seul is not None else (cam0, "depart")


# ================================================================ toutes les photos d'un logement
def affiner_les_appareils(logement: dict, photos: dict[str, np.ndarray], cameras: dict[str, dict], mesures: dict[str, dict],
                          owl=None, zoom_du_lot: float | None = None, lus: dict[str, list[dict]] | None = None, journal=print,
                          jonctions_de: dict | None = None) -> dict:
    """Affine l'appareil de chaque photo placée par le calage (`cameras` : la sortie de moteur.caler_photos.caler, modifiée
    sur place : champs x, y, z, cap, f, v0 de « camera », et « affine » = {"comment", "avant" : l'appareil du calage,
    "ecart" : par famille, avant → après}).
    mesures : {photo: mesure MoGe-2 (moteur.caler_photos.mesurer)} ; owl : OWLv2 (pour écarter meubles et rideaux) ;
    zoom_du_lot : le zoom commun des photos, en part de leur largeur (moteur.fuites.zoom_du_lot), ou None ;
    lus : {photo: repères lus (`reperes_lus`)} quand la lecture des fenêtres existe ;
    jonctions_de : {photo: jonctions déjà mesurées} (essais). → {photo: comment}."""
    scene = Scene(logement)
    requetes = owl.textes(list(CACHE_MUR)) if owl is not None else None
    bilan = {}
    for n, d in cameras.items():
        if n not in photos or n not in mesures and not (jonctions_de and n in jonctions_de):
            continue
        rgb = photos[n]
        if jonctions_de and n in jonctions_de:
            jon = jonctions_de[n]
        else:
            jon = jonctions(mesures[n], scene.hsp, cache_mur(owl, requetes, rgb) if owl is not None else None)
        c = d["camera"]
        cam0 = np.array([float(c.get(k, 0.0)) for k in NOMS])
        piece = scene.plan["ids"].index(d["piece"]) if d.get("piece") in scene.plan["ids"] else None
        z_vu = float(np.clip(jon.get("z", cam0[2]), 0.5, scene.hsp - 0.3))
        rappels = {2: (z_vu, RAPPEL_Z), 7: (float(cam0[7]), RAPPEL_V0)}
        if zoom_du_lot:
            rappels[5] = (zoom_du_lot * rgb.shape[1], RAPPEL_ZOOM)
        reps = (lus or {}).get(n) or None
        cam, comment = affiner_une_photo(cam0, scene, jon, reps, rappels, piece, z_vu)
        bilan[n] = comment
        avant, apres = cout(cam0, scene, jon, reps, detail=True), cout(cam, scene, jon, reps, detail=True)
        d["affine"] = {"comment": comment, "avant": dict(c), "points": {"plafond": int(len(jon["plafond"])), "sol": int(len(jon["sol"])), "lus": len(reps or [])},
                       "ecart": {k: [round(avant[k], 1), round(apres[k], 1)] for k in avant}}
        if comment != "depart":
            c.update(x=round(float(cam[0]), 3), y=round(float(cam[1]), 3), z=round(float(cam[2]), 3), cap=round(float((cam[3] + 180) % 360 - 180), 2),
                     f=round(float(cam[5]), 2), v0=round(float(cam[7]), 2))
            journal(f"  {n} : appareil affiné ({comment}) : déplacé de {math.hypot(cam[0] - cam0[0], cam[1] - cam0[1]):.2f} m, cap "
                    f"{(cam[3] - cam0[3] + 180) % 360 - 180:+.1f}°, zoom {cam0[5]:.0f} → {cam[5]:.0f}, hauteur {cam0[2]:.2f} → {cam[2]:.2f} m")
        else:
            journal(f"  {n} : appareil laissé à sa place (les murs vus sur la photo ne suffisent pas, ou ne collent pas au plan)")
    return bilan
