r"""ZÉRO COLLISION : le contrôle et la réparation de ce qui est posé dans un logement (16/11/2026).

Pourquoi (NT, 16/11/2026 : « éviter les collisions entre les meubles et les murs, mais bon ça tu devrais le savoir ») : mesuré ce
jour-là sur les trois maquettes, jusqu'à 12 cm d'un meuble dans un mur et 25 paires d'objets qui se traversaient. Le rangement
des meubles (moteur/ranger_meubles.py) tolère exprès 10 % d'un meuble hors de sa pièce et 4 % de recouvrement, et il ne
regarde ni les objets accrochés au mur, ni les luminaires, ni les équipements, ni les rideaux. Ici, la règle est stricte et
vaut pour TOUT ce qui est posé.

Deux fonctions :
- mesurer(logement) : la liste des collisions. C'est le CONTRÔLE : une maquette ne se montre que s'il rend une liste vide.
- reparer(logement) : le logement sans collision. Chaque objet qui en touche un autre (ou un mur) est déplacé LE MOINS
  POSSIBLE ; ce qui n'a aucune place libre est retiré, et c'est dit. Ce qu'une personne a placé (relevé à la main, écran de
  vérification) n'est jamais déplacé : une collision entre deux objets placés par quelqu'un est seulement signalée.

Ce qu'on appelle une collision (tout se juge sur la BOÎTE de l'objet : son emprise au sol tournée, de son bas à son haut) :
- un objet entré de plus de 5 mm dans l'épaisseur d'un mur (le mur est plein partout, portes et fenêtres comprises : rien ne
  se pose dans une ouverture) ;
- deux objets dont les boîtes se pénètrent de plus de 5 mm, À LA MÊME HAUTEUR (un tableau au-dessus d'une commode, une
  suspension au-dessus d'une table, un meuble haut au-dessus d'un meuble bas ne se touchent pas) ;
- un objet dans un rideau ou un voilage (la nappe de tissu, de son bas à la tringle) ;
- un objet posé hors de toute pièce.
Ce qui n'en est PAS une : un tapis (à plat) sous un meuble ; un évier, une plaque, une vasque, un four dans le meuble qui les
porte ; une chaise glissée sous une table (jusqu'à 35 % de son assise, comme dans le rangement des meubles).
LIMITE : la boîte n'est pas la forme exacte du meuble (un modèle du catalogue a des pieds, un dossier incliné) : deux boîtes
qui ne se touchent pas garantissent deux meubles qui ne se touchent pas ; seule la chaise sous la table est jugée « à la boîte ».

Qui cède la place à qui, dans la réparation (du plus fixe au plus mobile) :
1. ce qu'une personne a placé ; 2. ce qui est bâti (cheminée, baignoire, douche, WC, lavabo, réfrigérateur) ; 3. les objets
MINCES accrochés au mur (radiateur, tableau, télévision, miroir, applique : 13 cm au plus) — un tableau ou une télévision qui
tombe derrière un meuble est d'abord REMONTÉ au-dessus de lui, comme dans la vraie vie ; un radiateur ne monte pas : c'est le
meuble qui avancera ; 4. les rideaux : la nappe s'écarte du mur pour passer DEVANT un radiateur, s'arrête au-dessus de ce qui
est bâti ; 5. les meubles posés au sol, du plus sûr au moins sûr (ordre du rangement), chacun avec ce qu'il porte ; 6. les
objets ÉPAIS accrochés (meubles hauts, étagères, hotte) : ils glissent le long de leur mur ; 7. les luminaires du plafond :
écartés des murs, raccourcis au-dessus d'un meuble haut.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

VERSION = "0.1.0"
EPS = 0.005  # m : deux boîtes qui se pénètrent de moins de 5 mm ne se touchent pas
EPS_Z = 0.01  # m : … ni deux objets dont les hauteurs se recouvrent de moins de 1 cm
JEU = 0.01  # m laissé entre deux objets qu'on vient de séparer
JEU_MUR = 0.02  # m entre un meuble posé au sol et un mur (la plinthe fait 1,5 cm)
GLISSE_MAX = 0.8  # m : déplacement maximal d'un objet pour le dégager
PRES_M = 0.25  # m : avant de chercher plus loin, on essaie de rester à moins de 25 cm (quitte à perdre 10 % de largeur)
PAS = 0.05
MINCE_M = 0.13  # un objet accroché d'au plus 13 cm d'épaisseur est « mince »
SOUS_LA_TABLE = 0.35
AU_MUR = ("television", "tableau", "miroir", "horloge", "meuble_cuisine_haut", "radiateur", "applique", "etagere_murale", "hotte")
AU_PLAFOND = ("suspension", "plafonnier")
BATI = ("cheminee", "baignoire", "douche", "wc", "lavabo", "refrigerateur", "electromenager")
ENCASTRES = ("evier", "plaque", "four")
PORTEURS = ("meuble_cuisine_bas", "ilot", "colonne_cuisine", "rangement", "commode", "table_de_chevet", "meuble_tv", "bureau", "table")
CHAISES, TABLES = ("chaise", "chaise_de_bureau", "tabouret_haut"), ("table", "bureau")
# objets accrochés qu'on peut REMONTER au-dessus d'un meuble : le bas le plus haut permis (m)
REMONTE_MAX = {"television": 1.5, "tableau": 1.9, "miroir": 1.8, "horloge": 2.0, "etagere_murale": 1.6}
SUPPORTS_TV = ("meuble_tv", "commode", "rangement", "table", "bureau", "table_basse", "etagere_cubes", "banc")  # ce qui peut porter une télévision
SUSPENSION_MIN = 0.25  # m : hauteur minimale d'un luminaire raccourci
LEGERS = ("chaise", "lampe", "plante", "table_d_appoint", "table_de_chevet")  # groupes ou sortes de petits meubles qu'on déplace d'un geste
GLISSE_LEGER = 1.2  # m : jusqu'où on leur cherche une place quand ils n'en ont aucune à GLISSE_MAX
# largeur minimale (m) à laquelle un objet accroché fait de modules peut être réduit pour tenir sur son mur ; les autres : 75 % de la leur
MODULE_MIN = {"meuble_cuisine_haut": 0.45, "etagere_murale": 0.4}
# rideaux (moteur/blender/rideaux.py) : distance au mur de la nappe, demi-épaisseur de ses plis, débord de chaque côté
ECART_VOILAGE, ECART_RIDEAUX, PLIS_VOILAGE, PLIS_RIDEAUX, DEBORD_RIDEAUX, PAN_RIDEAUX = 0.10, 0.16, 0.03, 0.05, 0.15, 0.45
ECART_MAX = 0.40  # au-delà, le rideau n'est plus un rideau : il est retiré
RIDEAU_MIN = 0.6  # m de tissu qu'il doit rester sous la tringle quand le rideau s'arrête au-dessus d'un objet


# ------------------------------------------------------------------ boîtes
@dataclass
class Rect:
    """Un rectangle tourné, vu de dessus : centre, deux axes unitaires perpendiculaires, deux demi-côtés."""
    c: np.ndarray
    e1: np.ndarray
    e2: np.ndarray
    h1: float
    h2: float


def rect_du_meuble(m: dict, gonfle: float = 0.0) -> Rect:
    a = math.radians(float(m.get("face", 0.0)))
    f, t = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    return Rect(np.asarray(m["position"], float), t, f, float(m["dimensions"][0]) / 2 + gonfle, float(m["dimensions"][1]) / 2 + gonfle)


def hauteurs(m: dict) -> tuple[float, float]:
    z0 = float(m.get("altitude") or 0.0)
    return z0, z0 + float(m["dimensions"][2])


def rect_du_mur(mur: dict, gonfle: float = 0.0) -> Rect | None:
    a, b = np.asarray(mur["debut"], float), np.asarray(mur["fin"], float)
    L = float(np.linalg.norm(b - a))
    if L < 1e-6:
        return None
    u = (b - a) / L
    return Rect((a + b) / 2, u, np.array([-u[1], u[0]]), L / 2, float(mur.get("epaisseur", 0.2)) / 2 + gonfle)


def penetration(a: Rect, b: Rect) -> tuple[float, np.ndarray] | None:
    """Deux rectangles tournés se pénètrent-ils ? (profondeur, direction dans laquelle pousser `a` pour le sortir de `b`) :
    le plus petit déplacement qui les sépare (axes séparateurs). None s'ils ne se touchent pas."""
    ecart = a.c - b.c
    mieux = None
    for axe in (a.e1, a.e2, b.e1, b.e2):
        ra = a.h1 * abs(float(a.e1 @ axe)) + a.h2 * abs(float(a.e2 @ axe))
        rb = b.h1 * abs(float(b.e1 @ axe)) + b.h2 * abs(float(b.e2 @ axe))
        d = float(ecart @ axe)
        recouvre = ra + rb - abs(d)
        if recouvre <= 0:
            return None
        if mieux is None or recouvre < mieux[0]:
            mieux = (recouvre, axe * (1.0 if d >= 0 else -1.0))
    return mieux


def famille(m: dict) -> str:
    """plat (tapis), plafond, encastre, mur (accroché), bati (équipement au sol), sol (meuble)."""
    c, (z0, z1) = m["categorie"], hauteurs(m)
    if c in ENCASTRES or (c == "lavabo" and z0 >= 0.3):
        return "encastre"
    if c == "tapis" or (z1 - z0 <= 0.05 and z0 < 0.05):
        return "plat"
    if c in AU_PLAFOND:
        return "plafond"
    if c in AU_MUR:
        return "mur"
    if c in BATI:
        return "bati"
    return "sol"


def mobile(m: dict) -> bool:
    """Posé par Atelya d'après les photos (repérage ou lecture) : peut être déplacé. Tout le reste a été placé par quelqu'un."""
    s = str(m.get("source", ""))
    return m.get("statut") == "estime" and ("repérage" in s or "lecture" in s)


def porteurs(meubles: list[dict]) -> dict[int, dict]:
    """Pour chaque encastré (évier, plaque, vasque, four) : le meuble qui le porte ({id() de l'encastré: meuble porteur}).
    Sur le plan : son milieu est dans l'emprise du meuble et son bas est au niveau du dessus ; sur la façade (four) : son
    milieu est à moins de 12 cm devant le meuble."""
    sortie = {}
    for e in meubles:
        if famille(e) != "encastre":
            continue
        z0, _ = hauteurs(e)
        mieux = None
        for h in meubles:
            if h is e or h["categorie"] not in PORTEURS or famille(h) != "sol":
                continue
            a = math.radians(float(h.get("face", 0.0)))
            d = np.asarray(e["position"], float) - np.asarray(h["position"], float)
            x, y = float(d @ np.array([-math.sin(a), math.cos(a)])), float(d @ np.array([math.cos(a), math.sin(a)]))
            L, P, H = (float(v) for v in h["dimensions"])
            if e["categorie"] == "four":
                ok, cout = abs(x) <= L / 2 + 0.02 and P / 2 - 0.02 <= y <= P / 2 + 0.12, abs(y - P / 2)
            else:
                ok, cout = abs(x) <= L / 2 + 0.02 and abs(y) <= P / 2 + 0.02 and abs(z0 - H) <= 0.06, math.hypot(x, y)
            if ok and (mieux is None or cout < mieux[0]):
                mieux = (cout, h)
        if mieux is not None:
            sortie[id(e)] = mieux[1]
    return sortie


def _part_dessous(petit: dict, grand: dict) -> float:
    from moteur.ranger_meubles import recouvrement
    return recouvrement(petit, grand)


def permis(a: dict, b: dict, liens: dict[int, dict]) -> bool:
    """Ces deux objets ont-ils le droit de partager la même place ?"""
    fa, fb = famille(a), famille(b)
    if "plat" in (fa, fb):
        return True
    if liens.get(id(a)) is b or liens.get(id(b)) is a:
        return True
    for chaise, table in ((a, b), (b, a)):
        if chaise["categorie"] in CHAISES and table["categorie"] in TABLES and _part_dessous(chaise, table) <= SOUS_LA_TABLE:
            return True
    return False


# ------------------------------------------------------------------ murs et rideaux
def murs_solides(logement: dict, gonfle: float = 0.0) -> list[tuple[str, Rect, float]]:
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    sortie = []
    for m in logement.get("murs", []):
        r = rect_du_mur(m, gonfle)
        if r is not None:
            sortie.append((m["id"], r, float(m.get("hauteur") or hsp)))
    return sortie


def fenetres_habillees(logement: dict) -> list[dict]:
    """Chaque fenêtre qui a un voilage ou des rideaux : son milieu sur la face intérieure du mur, sa normale (vers la pièce),
    la direction du mur, sa largeur, la hauteur de la tringle (mêmes règles que moteur.habillage.rideaux_du_plan)."""
    from moteur.sol_a_plat import piece_de

    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    murs = {m["id"]: m for m in logement.get("murs", [])}
    sortie = []
    for o in logement.get("ouvertures", []):
        r = o.get("rideaux")
        m = murs.get(o.get("mur"))
        if not r or m is None or (not r.get("voilage") and not r.get("rideaux")):
            continue
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        u = (b - a) / max(float(np.linalg.norm(b - a)), 1e-9)
        n = np.array([-u[1], u[0]])
        ep = float(m.get("epaisseur", 0.2))
        c = a + u * (float(o["position"]) + float(o["largeur"]) / 2)
        if piece_de(c + n * (ep / 2 + 0.3), logement.get("pieces", [])) is None:
            n = -n
        haut = float(m.get("hauteur") or hsp)
        allege, hauteur = float(o.get("allege", 0.0) or 0.0), float(o.get("hauteur", 2.1))
        sortie.append({"ouverture": o, "centre": c + n * ep / 2, "n": n, "t": u, "demi": float(o["largeur"]) / 2,
                       "z_tringle": max(min(haut - 0.12, haut - 0.02), min(allege + hauteur + 0.3, haut - 0.02))})
    return sortie


def nappes(fenetre: dict) -> list[dict]:
    """Les nappes de tissu d'une fenêtre habillée, comme des boîtes : le voilage (toute la largeur) et les pans de rideaux
    (deux, ou ceux que les photos montrent)."""
    r = fenetre["ouverture"]["rideaux"]
    ecart = r.get("ecart")
    bas = float(r.get("bas") or 0.01)
    c, n, t, demi = fenetre["centre"], fenetre["n"], fenetre["t"], fenetre["demi"]
    ident = fenetre["ouverture"]["id"]
    sortie = []
    if r.get("voilage"):
        e = float(ecart) if ecart else ECART_VOILAGE
        sortie.append({"id": f"voilage de {ident}", "rect": Rect(c + n * e, t, n, demi + DEBORD_RIDEAUX, PLIS_VOILAGE), "z": (bas, fenetre["z_tringle"])})
    if r.get("rideaux"):
        e = float(ecart) + (ECART_RIDEAUX - ECART_VOILAGE) if ecart else ECART_RIDEAUX
        # un pan de chaque côté, ou les seuls pans vus sur les photos (`pans` ; t va du début vers la fin du mur)
        for cote in sorted({1 if p["cote"] == "fin" else -1 for p in r["pans"]}) if r.get("pans") else (-1, 1):
            milieu = cote * (demi + DEBORD_RIDEAUX - PAN_RIDEAUX / 2)
            sortie.append({"id": f"rideau de {ident}", "rect": Rect(c + t * milieu + n * e, t, n, PAN_RIDEAUX / 2, PLIS_RIDEAUX),
                           "z": (bas, fenetre["z_tringle"])})
    return sortie


def toutes_les_nappes(logement: dict) -> list[dict]:
    return [nappe for f in fenetres_habillees(logement) for nappe in nappes(f)]


# ------------------------------------------------------------------ le contrôle
def heurts(m: dict, autres: list[dict], murs: list[tuple[str, Rect, float]], liens: dict[int, dict], tissus: list[dict] = (),
           gonfle: float = 0.0) -> list[tuple[float, np.ndarray, str, str]]:
    """Tout ce que l'objet `m` pénètre : [(profondeur, direction pour l'en sortir, « mur » | « objet » | « rideau », identifiant)].
    `gonfle` : jeu exigé en plus autour de l'objet (contre les murs seulement)."""
    r = rect_du_meuble(m)
    z0, z1 = hauteurs(m)
    sortie = []
    grossi = rect_du_meuble(m, gonfle) if gonfle else r
    for ident, rm, haut in murs:
        if z0 >= haut - EPS_Z:
            continue
        p = penetration(grossi, rm)
        if p is not None and p[0] > EPS:
            sortie.append((p[0], p[1], "mur", ident))
    for o in autres:
        if o is m or permis(m, o, liens):
            continue
        o0, o1 = hauteurs(o)
        if min(z1, o1) - max(z0, o0) <= EPS_Z:
            continue
        p = penetration(r, rect_du_meuble(o))
        if p is not None and p[0] > EPS:
            sortie.append((p[0], p[1], "objet", o["id"]))
    for nappe in tissus:
        if min(z1, nappe["z"][1]) - max(z0, nappe["z"][0]) <= EPS_Z:
            continue
        p = penetration(r, nappe["rect"])
        if p is not None and p[0] > EPS:
            sortie.append((p[0], p[1], "rideau", nappe["id"]))
    return sortie


def dans_une_piece(m: dict, pieces: list[dict]) -> bool:
    """Le milieu de l'objet est-il dans une pièce ? (ou, pour un objet mince collé au mur, le point 15 cm devant lui : le
    contour d'une pièce passe parfois quelques centimètres devant la face du mur)"""
    from moteur.sol_a_plat import piece_de

    a = math.radians(float(m.get("face", 0.0)))
    x, y = float(m["position"][0]), float(m["position"][1])
    return piece_de((x, y), pieces) is not None or piece_de((x + 0.15 * math.cos(a), y + 0.15 * math.sin(a)), pieces) is not None


def mesurer(logement: dict) -> list[dict]:
    """LE CONTRÔLE : toutes les collisions du logement, de la plus profonde à la moins profonde.
    [{"type": "mur" | "objet" | "rideau" | "dehors", "a": id de l'objet, "b": id du mur, de l'autre objet ou du rideau,
      "profondeur_cm"}] ; une paire d'objets n'est comptée qu'une fois."""
    from moteur.sol_a_plat import piece_de

    meubles = [m for m in logement.get("meubles", []) if famille(m) != "plat"]
    liens = porteurs(logement.get("meubles", []))
    murs, tissus = murs_solides(logement), toutes_les_nappes(logement)
    sortie = []
    for k, m in enumerate(meubles):
        touche_un_mur = False
        for prof, _, sorte, ident in heurts(m, meubles[k + 1:], murs, liens, tissus):
            sortie.append({"type": sorte, "a": m["id"], "b": ident, "profondeur_cm": round(prof * 100, 1), "categorie": m["categorie"]})
            touche_un_mur = touche_un_mur or sorte == "mur"
        if not touche_un_mur and famille(m) != "encastre" and not dans_une_piece(m, logement.get("pieces", [])):
            sortie.append({"type": "dehors", "a": m["id"], "b": None, "profondeur_cm": 0.0, "categorie": m["categorie"]})
    return sorted(sortie, key=lambda c: -c["profondeur_cm"])


def resume(collisions: list[dict]) -> dict:
    """Le compte par sorte et la plus profonde : {"total", "mur", "objet", "rideau", "dehors", "au_pire_cm"}."""
    r = {"total": len(collisions), "mur": 0, "objet": 0, "rideau": 0, "dehors": 0,
         "au_pire_cm": max((c["profondeur_cm"] for c in collisions), default=0.0)}
    for c in collisions:
        r[c["type"]] += 1
    return r


# ------------------------------------------------------------------ la réparation
def _score(m: dict) -> float:
    from moteur.ranger_meubles import _score as score
    return score(m)


def _deplacer(groupe: list[dict], delta) -> None:
    for x in groupe:
        x["position"] = [round(float(x["position"][0] + delta[0]), 3), round(float(x["position"][1] + delta[1]), 3)]


def reparer(logement: dict, journal=None) -> tuple[dict, list[dict]]:
    """Le logement sans collision et la liste de ce qui a été fait : [{"id", "categorie", "action", "raison"}]
    (actions : « déplacé », « remonté », « raccourci », « rétréci », « tourné », « retiré », « rideau écarté », « rideau
    raccourci », « rideau retiré », « signalé »). Le logement reçu n'est pas modifié."""
    from moteur import equipements as eq
    from moteur.ranger_meubles import RANG, RETRECIT, groupe_de
    from moteur.sol_a_plat import piece_de

    lg = {**logement, "meubles": [dict(m) for m in logement.get("meubles", [])],
          "ouvertures": [{**o, "rideaux": dict(o["rideaux"])} if o.get("rideaux") else dict(o) for o in logement.get("ouvertures", [])]}
    meubles: list[dict] = lg["meubles"]
    pieces = lg.get("pieces", [])
    par_id = {p["id"]: p for p in pieces}
    hsp = float(lg.get("hauteur_sous_plafond", 2.5))
    actions: list[dict] = []

    def note(m: dict, action: str, raison: str, silencieux: bool = False) -> None:
        actions.append({"id": m["id"], "categorie": m["categorie"], "action": action, "raison": raison})
        if journal and not silencieux:
            journal(f"  collisions : {m['categorie']} {m['id']} {action} ({raison})")

    murs = murs_solides(lg)
    liens = porteurs(meubles)
    portes: dict[int, list[dict]] = {}
    for e in meubles:
        if id(e) in liens:
            portes.setdefault(id(liens[id(e)]), []).append(e)
    fam = {id(m): famille(m) for m in meubles}
    retires: set[int] = set()
    poses: list[dict] = []  # ce qui est installé : les objets suivants s'y adaptent
    tissus: list[dict] = []

    def groupe(m: dict) -> list[dict]:
        return [m] + portes.get(id(m), [])

    def heurts_du_groupe(m: dict, jeu_mur: float) -> list[tuple[float, np.ndarray, str, str]]:
        tout = heurts(m, poses, murs, liens, tissus, gonfle=jeu_mur)
        for e in portes.get(id(m), []):  # ce que le meuble porte ne touche ni un autre objet ni un rideau (les murs : c'est le meuble qui compte)
            tout += [h for h in heurts(e, poses, [], liens, tissus) if h[3] != m["id"]]
        return tout

    def dans_sa_piece(m: dict, piece0) -> bool:
        p = piece_de(m["position"], pieces)
        return p is not None and (piece0 is None or p["id"] == piece0["id"])

    def installer(m: dict) -> None:
        poses.extend(x for x in groupe(m) if fam[id(x)] != "plat")

    def retirer(m: dict, raison: str) -> None:
        for x in groupe(m):
            retires.add(id(x))
        note(m, "retiré", raison)

    # ---- ce qu'une personne a placé ne bouge pas (et ce que ces meubles portent non plus)
    fixes = [m for m in meubles if not mobile(m) and not (id(m) in liens and mobile(liens[id(m)]))]
    for m in fixes:
        if fam[id(m)] != "plat":
            poses.append(m)
        poses.extend(e for e in portes.get(id(m), []) if mobile(e))  # ce qu'il porte reste avec lui
    ids_fixes = {id(m) for m in fixes}
    libres = [m for m in meubles if id(m) not in ids_fixes and fam[id(m)] not in ("plat",) and id(m) not in liens]
    orphelins = [m for m in meubles if id(m) not in ids_fixes and fam[id(m)] == "encastre" and id(m) not in liens]

    # ---- au sol (bâti puis meubles) : poussé hors de ce qu'il touche, sinon cherché autour, sinon tourné, rétréci, retiré
    def placer_au_sol(m: dict, jeu_mur: float) -> bool:
        """L'objet (et ce qu'il porte) à la place libre la plus proche. Du moins visible au plus visible : (1) tel quel, à 25 cm
        au plus ; (2) 10 % de moins en largeur, à 25 cm au plus (un meuble télé de 1,40 m pris entre une cheminée et un mur
        distants de 1,40 m : il perd 14 cm, il ne part pas à 60 cm) ; (3) tel quel puis 10 % plus étroit, jusqu'à 80 cm ;
        (4) tourné d'un quart de tour ; (5) 20 % de moins ; (6) une table ou un rangement, qui existent en petit (table
        d'appoint, chevet) : jusqu'à moitié moins ; (7) un meuble léger (chaise, lampe, plante) : cherché jusqu'à 1,20 m.
        Un meuble qui porte un évier ou une plaque n'est ni rétréci ni tourné."""
        origine = [dict(x) for x in groupe(m)]
        piece0 = piece_de(m["position"], pieces) or par_id.get(m.get("piece"))
        base = origine

        def remettre(sur: list[dict]) -> None:
            for x, o in zip(groupe(m), sur):
                x.update(position=list(o["position"]), face=o.get("face", 0.0), dimensions=list(o["dimensions"]))

        def bon() -> bool:
            return dans_sa_piece(m, piece0) and not heurts_du_groupe(m, jeu_mur)

        def chercher(portee: float) -> bool:
            if bon():
                return True
            depart = np.asarray(base[0]["position"], float)
            for _ in range(12):  # poussées successives, chaque fois hors de ce qui est le plus enfoncé
                h = heurts_du_groupe(m, jeu_mur)
                if not h:
                    break
                prof, direction, _, _ = max(h, key=lambda x: x[0])
                _deplacer(groupe(m), direction * (prof + JEU))
                if float(np.linalg.norm(np.asarray(m["position"], float) - depart)) > portee:
                    break
            if bon() and float(np.linalg.norm(np.asarray(m["position"], float) - depart)) <= portee:
                return True
            for k in range(1, int(portee / PAS) + 1):  # la place libre la plus proche, de proche en proche
                for j in range(16):
                    a = 2 * math.pi * j / 16
                    remettre(base)
                    _deplacer(groupe(m), (math.cos(a) * PAS * k, math.sin(a) * PAS * k))
                    if bon():
                        return True
            remettre(base)
            return False

        seul = len(groupe(m)) == 1
        petit = seul and groupe_de(m["categorie"]) in RETRECIT
        leger = groupe_de(m["categorie"]) in LEGERS or m["categorie"] in LEGERS
        essais = [(1.0, 0.0, PRES_M)]
        if seul:
            essais += [(0.9, 0.0, PRES_M)]
        essais += [(1.0, 0.0, GLISSE_MAX)]
        if seul:
            essais += [(0.9, 0.0, GLISSE_MAX), (1.0, 90.0, GLISSE_MAX), (0.8, 0.0, GLISSE_MAX), (0.9, 90.0, GLISSE_MAX)]
        if petit:
            essais += [(0.65, 0.0, GLISSE_MAX), (0.5, 0.0, GLISSE_MAX)]
        if leger:
            essais += [(1.0, 0.0, GLISSE_LEGER)]
        for part, tour, portee in essais:
            remettre(origine)
            if tour:
                m["face"] = round(float(origine[0].get("face", 0.0)) + tour, 1)
            if part < 1.0:
                # jamais sous 35 cm de large ni 30 cm de profondeur… sauf si l'objet était déjà plus petit (il n'est alors pas agrandi)
                l0, p0 = float(origine[0]["dimensions"][0]), float(origine[0]["dimensions"][1])
                m["dimensions"] = [round(min(l0, max(l0 * part, 0.35)), 2),
                                   round(min(p0, max(p0 * part, 0.3)), 2) if petit and part < 0.8 else origine[0]["dimensions"][1],
                                   origine[0]["dimensions"][2]]
            base = [dict(x) for x in groupe(m)]
            if chercher(portee):
                if tour:
                    note(m, "tourné", "il ne tenait pas dans ce sens")
                if part < 1.0:
                    note(m, "rétréci", f"largeur {float(origine[0]['dimensions'][0]):.2f} → {float(m['dimensions'][0]):.2f} m : pas de place pour sa taille courante")
                return True
        remettre(origine)
        return False

    # une chaise rangée à sa table la suit (moteur/tablees.py, 17/11/2026) : avant, la table était poussée hors d'un obstacle,
    # puis chaque chaise écartée de la table de son côté, et la tablée était défaite
    from moteur.tablees import sieges_ranges

    table_de = sieges_ranges(meubles)
    depart_des_tables = {id(t): np.asarray(t["position"], float) for t in table_de.values()}

    def au_sol(liste: list[dict], jeu_mur: float) -> None:
        for m in liste:
            table = table_de.get(id(m))
            if table is not None and id(table) not in retires and mobile(m):
                suivi = np.asarray(table["position"], float) - depart_des_tables[id(table)]
                if float(np.linalg.norm(suivi)) > 1e-6:
                    _deplacer([m], suivi)
            avant = list(m["position"])
            if not placer_au_sol(m, jeu_mur):
                retirer(m, "aucune place libre à moins de 80 cm")
                continue
            ecart = math.dist(avant, m["position"])
            if ecart > 1e-6:
                note(m, "déplacé", f"{ecart * 100:.0f} cm, pour ne rien toucher", silencieux=ecart < 0.03)
            installer(m)

    # ---- accroché au mur : recollé à la face de son mur, glissé le long d'elle, remonté au-dessus d'un meuble
    def sur_cette_face(m: dict, face: dict, point: np.ndarray, largeur: float, niveaux: list[float], glisse: float = 1.0) -> bool:
        """L'objet collé à cette face, à la largeur donnée, au plus près de `point` : glissé le long d'elle (1 m au plus), hors
        des portes et des fenêtres qu'il croiserait, sans rien toucher. Vrai s'il a trouvé sa place (l'objet est alors modifié)."""
        _, ep, h = (float(v) for v in m["dimensions"])
        if largeur > face["longueur"] - 0.02:
            return False
        baies = eq.baies_de_la_face(face, lg)
        s0 = float(np.clip((point - face["a"]) @ face["t"], largeur / 2, face["longueur"] - largeur / 2))
        garde = dict(m)
        if abs(largeur - float(m["dimensions"][0])) > 1e-9:
            m["dimensions"] = [round(largeur, 2), ep, h]
        m["face"] = round(math.degrees(math.atan2(face["n"][1], face["n"][0])), 1)
        for z in niveaux:
            for k in range(int(glisse / PAS) + 1):
                for signe in ((0,) if k == 0 else (1, -1)):
                    x = s0 + signe * k * PAS
                    if x - largeur / 2 < -1e-6 or x + largeur / 2 > face["longueur"] + 1e-6:
                        continue
                    if any(x + largeur / 2 > b0 - 0.02 and x - largeur / 2 < b1 + 0.02 and b2 < z + h - 0.02 and b3 > z + 0.02 for b0, b1, b2, b3 in baies):
                        continue
                    centre = face["a"] + x * face["t"] + face["n"] * (ep / 2 + 0.01)
                    m["position"] = [round(float(centre[0]), 3), round(float(centre[1]), 3)]
                    m["altitude"] = round(z, 3)
                    if not heurts(m, poses, murs, liens, tissus):
                        return True
        m.update(position=garde["position"], face=garde.get("face", 0.0), dimensions=garde["dimensions"], altitude=garde.get("altitude", 0.0))
        return False

    def largeurs_reduites(m: dict, face: dict, z: float) -> list[float]:
        """Les largeurs (au moins 75 % de la sienne) auxquelles l'objet tiendrait entre deux portes ou fenêtres de cette face."""
        l, _, h = (float(v) for v in m["dimensions"])
        mini = min(MODULE_MIN.get(m["categorie"], 0.75 * l), l)
        bords = sorted((max(b0, 0.0), min(b1, face["longueur"])) for b0, b1, b2, b3 in eq.baies_de_la_face(face, lg) if b2 < z + h - 0.02 and b3 > z + 0.02)
        libres, curseur = [], 0.0
        for b0, b1 in bords:
            libres.append(b0 - curseur)
            curseur = max(curseur, b1)
        libres.append(face["longueur"] - curseur)
        return sorted({round(v - 0.06, 2) for v in libres if mini <= v - 0.06 < l}, reverse=True)

    def sur_son_meuble(m: dict, a_venir: list[dict]) -> bool:
        """Une télévision qui n'a pas de mur libre derrière elle est POSÉE sur le meuble qui est sous elle (app-002 : la
        télévision de la chambre est sur son meuble, devant la porte-fenêtre). Elle le suivra s'il bouge."""
        if m["categorie"] != "television":
            return False
        z0, h = float(m.get("altitude") or 0.0), float(m["dimensions"][2])
        choix = []
        for f in [*a_venir, *(x for x in poses if fam.get(id(x)) == "sol")]:
            dessus = hauteurs(f)[1]
            if f["categorie"] not in SUPPORTS_TV or not (dessus - 0.15 <= z0 <= dessus + 0.6) or dessus + 0.02 + h > hsp - 0.05:
                continue
            r = rect_du_meuble(f, 0.35)
            d = np.asarray(m["position"], float) - r.c
            if abs(float(d @ r.e1)) <= r.h1 and abs(float(d @ r.e2)) <= r.h2:
                choix.append((float(np.linalg.norm(d)), id(f), f))
        if not choix:
            return False
        f = min(choix)[2]
        r = rect_du_meuble(f)
        jeu = max(float(f["dimensions"][0]) - float(m["dimensions"][0]), 0.0) / 2
        x = float(np.clip((np.asarray(m["position"], float) - r.c) @ r.e1, -jeu, jeu))
        centre = r.c + x * r.e1
        m.update(position=[round(float(centre[0]), 3), round(float(centre[1]), 3)], face=f.get("face", 0.0), altitude=round(hauteurs(f)[1] + 0.02, 3))
        liens[id(m)] = f
        portes.setdefault(id(f), []).append(m)
        return True

    def placer_au_mur(m: dict, a_venir: list[dict]) -> str | None:
        """Comment l'objet accroché a trouvé sa place : « mur » (le sien), « sur son meuble », « rétréci », « autre mur »,
        « posé » (loin de tout mur) ; None s'il n'en a aucune."""
        a = math.radians(float(m.get("face", 0.0)))
        n = np.array([math.cos(a), math.sin(a)])
        p = np.asarray(m["position"], float)
        piece = piece_de(p + n * 0.1, pieces) or piece_de(p, pieces) or par_id.get(m.get("piece"))
        faces = eq.faces_proches(p, piece, lg, rayon=1.2) if piece is not None else []
        siennes = [f for f in faces if f["d"] <= 0.45 and float(f["n"] @ n) > 0.85]
        if not siennes:  # loin de tout mur (une télévision sur une cloison-meuble que le plan n'a pas)
            if sur_son_meuble(m, a_venir):
                return "sur son meuble"
            return "posé" if placer_au_sol(m, 0.0) else None
        face = siennes[0]
        l, ep, h = (float(v) for v in m["dimensions"])
        z0 = float(m.get("altitude") or 0.0)
        niveaux = [z0]
        # un meuble est-il devant lui, à sa hauteur ? S'il peut monter au-dessus, il monte (un tableau au-dessus d'une commode, un
        # miroir au-dessus d'une cheminée) ; sinon c'est le meuble qui avancera, à son tour
        devant = [*a_venir, *(x for x in poses if fam.get(id(x)) in ("sol", "bati"))]
        dessous = [f for f in devant if hauteurs(f)[1] > z0 + EPS_Z and hauteurs(f)[0] < z0 + h - EPS_Z
                   and penetration(rect_du_meuble(m), rect_du_meuble(f)) is not None]
        # un sèche-serviettes (radiateur d'un mètre de haut ou plus) se fixe plus ou moins haut ; un radiateur ordinaire, non
        plafond_du_bas = REMONTE_MAX.get(m["categorie"], 1.0 if m["categorie"] == "radiateur" and h >= 1.0 - 1e-6 else None)
        if dessous and plafond_du_bas is not None and not (m["categorie"] == "miroir" and z0 < 0.3):
            plus_haut = round(max(hauteurs(f)[1] for f in dessous) + 0.08, 2)
            if plus_haut <= plafond_du_bas and plus_haut + h <= hsp - 0.05:
                niveaux = [plus_haut, z0]
        # une télévision reste sur son mur si elle y tient à 30 cm près ; sinon elle est d'abord posée sur le meuble qui est sous elle
        if sur_cette_face(m, face, p, l, niveaux, glisse=0.3 if m["categorie"] == "television" else 1.0):
            return "mur"
        if sur_son_meuble(m, a_venir):
            return "sur son meuble"
        if m["categorie"] == "television" and sur_cette_face(m, face, p, l, niveaux):
            return "mur"
        for largeur in largeurs_reduites(m, face, niveaux[0]):
            if sur_cette_face(m, face, p, largeur, niveaux):
                return "rétréci"
        for autre in faces:  # la place mesurée est juste à 40 cm près : dans un angle, le bon mur est parfois celui d'à côté
            if autre is face or autre["mur"] == face["mur"] and autre["cote"] == face["cote"]:
                continue
            if sur_cette_face(m, autre, p, l, niveaux):
                return "autre mur"
        return None

    def au_mur(liste: list[dict], a_venir: list[dict]) -> None:
        for m in liste:
            avant, z_avant, l_avant = list(m["position"]), float(m.get("altitude") or 0.0), float(m["dimensions"][0])
            comment = placer_au_mur(m, a_venir)
            if comment is None:
                retirer(m, "aucune place libre sur un mur à moins d'un mètre")
                continue
            ecart = math.dist(avant, m["position"])
            if comment == "sur son meuble":
                note(m, "posé sur son meuble", f"pas de mur libre derrière elle : elle est posée sur {liens[id(m)]['categorie']} {liens[id(m)]['id']}")
            elif comment == "autre mur":
                note(m, "déplacé", f"sur le mur d'à côté ({ecart * 100:.0f} cm) : le sien n'avait pas de place")
            elif comment == "rétréci":
                note(m, "rétréci", f"largeur {l_avant:.2f} → {float(m['dimensions'][0]):.2f} m, pour tenir sur son mur")
            elif abs(float(m.get("altitude") or 0.0) - z_avant) > 0.02:
                note(m, "remonté", f"au-dessus de ce qui est devant lui (bas à {float(m['altitude']):.2f} m)")
            elif ecart > 1e-6:
                note(m, "déplacé", f"{ecart * 100:.0f} cm le long de son mur", silencieux=ecart < 0.03)
            if not (id(m) in liens and any(liens[id(m)] is f for f in a_venir)):  # portée par un meuble à venir : installée avec lui
                installer(m)

    # ---- rideaux : devant ce qui est accroché sous la fenêtre, au-dessus de ce qui est bâti
    def regler_les_rideaux() -> None:
        for f in fenetres_habillees(lg):
            o = f["ouverture"]
            r = o["rideaux"]
            for _ in range(3):
                genants = []
                for nappe in nappes(f):
                    for x in poses:
                        x0, x1 = hauteurs(x)
                        if min(x1, nappe["z"][1]) - max(x0, nappe["z"][0]) > EPS_Z and penetration(rect_du_meuble(x), nappe["rect"]) is not None:
                            genants.append(x)
                if not genants:
                    break
                minces = [x for x in genants if fam[id(x)] == "mur"]
                if minces and not r.get("ecart_regle"):
                    # la nappe passe DEVANT ce qui est accroché sous la fenêtre (un radiateur) : sa distance au mur = la saillie de l'objet + 5 cm
                    saillie = max(float(((np.asarray(x["position"], float) - f["centre"]) @ f["n"])) + float(x["dimensions"][1]) / 2 for x in minces)
                    r["ecart"] = round(max(ECART_VOILAGE, saillie + PLIS_VOILAGE + 0.02), 2)
                    r["ecart_regle"] = True
                    if r["ecart"] > ECART_MAX:
                        break
                    continue
                dessus = max(hauteurs(x)[1] for x in genants) + 0.02
                if f["z_tringle"] - dessus >= RIDEAU_MIN and not r.get("bas_regle"):
                    r["bas"] = round(dessus, 2)
                    r["bas_regle"] = True
                    continue
                break
            restants = [x for nappe in nappes(f) for x in poses
                        if min(hauteurs(x)[1], nappe["z"][1]) - max(hauteurs(x)[0], nappe["z"][0]) > EPS_Z
                        and penetration(rect_du_meuble(x), nappe["rect"]) is not None]
            regle_ecart, regle_bas = r.pop("ecart_regle", False), r.pop("bas_regle", False)
            if restants or float(r.get("ecart") or 0.0) > ECART_MAX:
                o["rideaux"] = None
                actions.append({"id": o["id"], "categorie": "rideaux", "action": "rideau retiré", "raison": "un objet fixe occupe sa place"})
                if journal:
                    journal(f"  collisions : rideaux de {o['id']} retirés (un objet fixe occupe leur place)")
                continue
            if regle_ecart:
                actions.append({"id": o["id"], "categorie": "rideaux", "action": "rideau écarté", "raison": f"à {r['ecart']:.2f} m du mur, devant ce qui est accroché"})
            if regle_bas:
                actions.append({"id": o["id"], "categorie": "rideaux", "action": "rideau raccourci", "raison": f"il s'arrête à {r['bas']:.2f} m, au-dessus de ce qui est bâti"})

    # ---- luminaires du plafond : hors des murs, raccourcis au-dessus de ce qui monte haut
    def placer_au_plafond(m: dict) -> bool:
        depart = np.asarray(m["position"], float)
        for _ in range(8):
            h = [x for x in heurts(m, [], murs, liens, [], gonfle=JEU)]
            if not h:
                break
            prof, direction, _, _ = max(h, key=lambda x: x[0])
            _deplacer([m], direction * (prof + JEU))
        gene = [x for x in heurts(m, poses, murs, liens, tissus) if x[2] != "mur"]
        if gene:
            noms = {x[3] for x in gene}
            dessus = max([hauteurs(o)[1] for o in poses if o["id"] in noms] + [t["z"][1] for t in tissus if t["id"] in noms]) + 0.1
            haut = hauteurs(m)[1]
            if haut - dessus >= SUSPENSION_MIN:
                m["altitude"], m["dimensions"] = round(dessus, 2), [m["dimensions"][0], m["dimensions"][1], round(haut - dessus, 2)]
                note(m, "raccourci", f"il descendait dans un meuble (bas à {dessus:.2f} m)")
        if not heurts(m, poses, murs, liens, tissus) and piece_de(m["position"], pieces) is not None:
            return True
        base = list(m["position"])
        for k in range(1, int(0.6 / PAS) + 1):
            for j in range(16):
                a = 2 * math.pi * j / 16
                m["position"] = [round(base[0] + math.cos(a) * PAS * k, 3), round(base[1] + math.sin(a) * PAS * k, 3)]
                if not heurts(m, poses, murs, liens, tissus) and piece_de(m["position"], pieces) is not None:
                    return True
        m["position"] = [float(depart[0]), float(depart[1])]
        return False

    rang = lambda m: (RANG.get(groupe_de(m["categorie"]), 9), -_score(m))
    batis = sorted((m for m in libres if fam[id(m)] == "bati"), key=lambda m: -_score(m))
    minces = sorted((m for m in libres if fam[id(m)] == "mur" and float(m["dimensions"][1]) <= MINCE_M),
                    key=lambda m: (m["categorie"] != "radiateur", -_score(m)))
    epais = sorted((m for m in libres if fam[id(m)] == "mur" and float(m["dimensions"][1]) > MINCE_M), key=lambda m: -_score(m))
    sols = sorted((m for m in libres if fam[id(m)] == "sol"), key=rang)
    plafond = sorted((m for m in libres if fam[id(m)] == "plafond"), key=lambda m: -_score(m))

    au_sol(batis, 0.0)
    au_mur(minces, sols)
    regler_les_rideaux()
    tissus.extend(toutes_les_nappes(lg))
    au_sol(sols, JEU_MUR)
    au_mur(epais, [])
    for m in plafond:
        avant = list(m["position"])
        if not placer_au_plafond(m):
            retirer(m, "aucune place libre au plafond")
            continue
        if math.dist(avant, m["position"]) > 1e-6:
            ecart = math.dist(avant, m["position"])
            note(m, "déplacé", f"{ecart * 100:.0f} cm, pour ne toucher ni mur ni meuble", silencieux=ecart < 0.03)
        installer(m)
    for m in orphelins:  # un évier, une plaque, un four sans meuble pour le porter : gardé seulement s'il ne touche rien
        if heurts(m, poses, murs, liens, tissus):
            retirer(m, "plus de meuble pour le porter, et il touche autre chose")
        else:
            installer(m)

    lg["meubles"] = [m for m in meubles if id(m) not in retires]
    # ---- la garantie : tant qu'il reste une collision où un objet mobile est en cause, le moins sûr des deux est retiré
    encastres = [e for e in meubles if id(e) in liens and mobile(e)]
    ordre = {id(m): k for k, m in enumerate([*orphelins, *encastres, *plafond, *epais, *reversed(sols), *reversed(minces), *reversed(batis)])}
    for _ in range(len(lg["meubles"]) + 1):
        restes = mesurer(lg)
        par_ident = {m["id"]: m for m in lg["meubles"]}
        fautifs = [m for c in restes for m in (par_ident.get(c["a"]), par_ident.get(c["b"])) if m is not None and id(m) in ordre]
        if not fautifs:
            for c in restes:  # il ne reste que des objets placés par quelqu'un : signalés, jamais déplacés
                m = par_ident.get(c["a"])
                if m is not None:
                    note(m, "signalé", f"placé par quelqu'un, il touche {c['b'] or 'le dehors'} ({c['profondeur_cm']} cm)")
            break
        pire = min(fautifs, key=lambda m: ordre[id(m)])
        note(pire, "retiré", "il touchait encore quelque chose après réparation")
        lg["meubles"] = [m for m in lg["meubles"] if m is not pire and liens.get(id(m)) is not pire]
    return lg, actions


def bilan(actions: list[dict]) -> str:
    """Une ligne pour le journal : combien d'objets déplacés, remontés, retirés…"""
    compte: dict[str, int] = {}
    for a in actions:
        compte[a["action"]] = compte.get(a["action"], 0) + 1
    return ", ".join(f"{n} {action}" for action, n in sorted(compte.items())) or "rien à faire"
