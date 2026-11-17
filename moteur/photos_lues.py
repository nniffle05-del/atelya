r"""LES PHOTOS LUES, POSÉES PAR ATELYA : de « ce que chaque rectangle montre » au logement (essai du 16/11/2026).

Pourquoi : dans l'essai « Claude lit les photos » (accord de NT du 16/11/2026), Claude ne donne que le SENS (moteur/lecture_photos.py :
la sorte de chaque rectangle numéroté, les doublons, les faux, la famille du sol, ce qui manque). Tout le reste est fait ici, par
Atelya, avec la place des appareils qu'il connaît déjà :
- un meuble POSÉ AU SOL (canapé, bureau, commode, meubles de cuisine…) : par son pied, comme avant (moteur/reperer_meubles.py),
  mais avec la sorte lue au lieu du mot du détecteur ; deux vues ne se fondent que si elles ont la MÊME sorte ;
- un luminaire SUSPENDU : par la profondeur (moteur/objets_accroches.py), seulement là où la lecture dit « suspension » ;
- un objet AU MUR que la maquette sait porter (télévision, tableau, miroir, horloge, meubles hauts de cuisine) : la profondeur
  mesurée dans son rectangle donne sa place à 10-15 % près, puis il est collé au mur du PLAN le plus proche (à moins de 80 cm) ;
  loin de tout mur, il reste où il est mesuré (une télévision sur une cloison-meuble que le plan n'a pas) ;
- les ÉQUIPEMENTS du logement (cheminée, radiateur, évier, four, baignoire, WC, appliques, rideaux, passe-plat…) : posés
  par moteur/equipements.py (adossés à un mur, encastrés dans un meuble de cuisine, au plafond ; rideaux à leur fenêtre ;
  passe-plat percé dans son mur), dessinés par moteur/blender/equipements.py (16/11/2026) ;
- les BAIES : un rectangle lu « porte_fenetre » ou « fenetre » vote pour la baie du plan que ses rayons touchent ;
- les SOLS : la famille que la lecture donne à la pièce où se tient le photographe.

La même pose sert à comparer, sur les mêmes rectangles, la sorte du DÉTECTEUR et la sorte LUE (moteur.lecture_photos.
objets_du_detecteur / objets_lus) : la différence est ce que la lecture apporte. Rien de ceci n'est en service.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
# accrochés au mur que la maquette sait porter : sorte → (largeur, épaisseur, hauteur courantes), (bas le plus bas, le plus haut)
AU_MUR = {"television": ((1.1, 0.08, 0.65), (0.3, 1.5)), "tableau": ((0.6, 0.03, 0.8), (0.6, 1.9)),
          "miroir": ((0.6, 0.04, 0.9), (0.0, 1.8)), "horloge": ((0.5, 0.05, 0.5), (1.0, 2.0)),
          "meuble_cuisine_haut": ((1.8, 0.35, 0.7), (1.3, 1.7))}
BAIES = ("fenetre", "porte_fenetre")
COLLE_AU_MUR_M = 0.8  # un objet accroché mesuré à moins de 80 cm d'un mur est sur ce mur
DE_BIAIS_MIN = 0.35  # borne de la correction de largeur d'un objet vu très de biais
FUSION_MUR_M = 0.9  # deux vues de la même sorte à moins de 90 cm (photos différentes) sont le même objet accroché
MEME_OBJET_M = 0.3  # … et à moins de 30 cm, même sur une seule photo
RAYONS_BAIE, RAYONS_MIN = 9, 3  # rayons tirés dans la largeur d'une baie lue ; il en faut 3 sur la même baie du plan
LARGEUR_MAX_M = 3.5
PASSE_PORTE_M = 0.12  # un rayon qui touche une porte repart 12 cm plus loin (l'épaisseur de la cloison)
BAS_AU_SOL_M = 0.25  # le bas d'un rectangle mesuré à plus de 25 cm du sol n'est pas le pied du meuble
POIDS_PROFONDEUR = 0.5  # poids d'une place tirée de la profondeur (moins sûre qu'un pied bien vu) dans la fusion entre photos
DERRIERE_LE_MUR_M = 0.6  # un meuble tombé à moins de 60 cm derrière un mur est ramené contre ce mur
CACHE_M = 0.05  # un meuble d'une autre pièce est gardé seulement si aucun mur plein n'est devant lui (vu par une porte)
POINTS_COEUR_MIN = 20  # points mesurés qu'il faut dans le cœur d'un rectangle pour en tirer une profondeur
PIED_CACHE = ("chaise", "fauteuil", "table", "lampe", "plante")  # groupes de petits meubles isolés dont le pied peut être caché
EPAISSEUR_VUE_M = 0.6  # dans le rectangle, les points à moins de 60 cm de la distance du cœur sont le meuble
MOITIE = 0.6  # un meuble vu moins large que 60 % de la plus petite largeur de sa sorte n'est pas à la distance mesurée
COEUR_LIBRE_MIN = 0.5  # part du cœur du rectangle qui doit rester visible (ni cachée par un meuble de devant, ni sans mesure)
DEVANT_PX = 12  # un meuble dont le bas du rectangle est 12 px plus bas dans l'image est posé devant (plus près de l'appareil)


def rayon(cam, u: float, v: float) -> tuple[float, float]:
    """La direction à plat (degrés) et la pente (montée par mètre à plat) du rayon qui part de l'appareil vers le pixel (u, v)."""
    from moteur.camera_photo import axes

    _, _, _, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    d = vue + (u - u0) / f * droite - (v - v0) / f * haut
    plat = float(np.hypot(d[0], d[1]))
    return math.degrees(math.atan2(d[1], d[0])), (float(d[2]) / plat if plat > 1e-6 else 0.0)


def mur_le_plus_proche(point, logement: dict, vers) -> tuple[np.ndarray, np.ndarray, float] | None:
    """La face de mur la plus proche du point, parmi celles qu'on voit depuis `vers` (leur pièce est du côté de `vers`) :
    (pied sur cette face, normale unitaire tournée vers `vers`, distance)."""
    from moteur.sol_a_plat import dans_polygone

    p, v = np.asarray(point, float), np.asarray(vers, float)
    meilleur = None
    for piece in logement["pieces"]:
        c = np.asarray(piece["contour"], float)
        for a, b in zip(c, np.roll(c, -1, axis=0)):
            ab = b - a
            L2 = float(ab @ ab)
            if L2 < 1e-9:
                continue
            q = a + float(np.clip((p - a) @ ab / L2, 0.0, 1.0)) * ab
            d = float(np.linalg.norm(p - q))
            if meilleur is not None and d >= meilleur[2]:
                continue
            n = np.array([-ab[1], ab[0]]) / math.sqrt(L2)
            if (v - q) @ n < 0:
                n = -n
            dedans = q + 0.05 * n
            if not dans_polygone(np.array([dedans[0]]), np.array([dedans[1]]), piece["contour"])[0]:
                continue  # l'autre face du mur (celle de la pièce voisine), qu'on ne voit pas d'ici
            meilleur = (q, n, d)
    return meilleur


def _couleur(rgb: np.ndarray | None, boite) -> list[int] | None:
    if rgb is None:
        return None
    x0, y0, x1, y1 = (int(v) for v in boite)
    coeur = rgb[max(0, y0 + (y1 - y0) // 4):max(y0 + (y1 - y0) // 4 + 1, y1 - (y1 - y0) // 4),
                max(0, x0 + (x1 - x0) // 4):max(x0 + (x1 - x0) // 4 + 1, x1 - (x1 - x0) // 4)].reshape(-1, 3)
    return [int(v) for v in np.median(coeur, axis=0)] if len(coeur) else None


def premier_mur(plan: dict, origine, angle_deg: float, portes_max: int = 3, pieces: list[dict] | None = None) -> tuple[float, int]:
    """Dans cette direction, la distance du premier mur PLEIN (sorte 0) ou de la première fenêtre (2) : les portes sont
    traversées (un appareil tenu sur le pas d'une porte, une pièce vue par une porte ouverte). (inf, 0) si rien n'est touché.
    Avec `pieces` : un appareil placé DANS l'épaisseur d'un mur (photo prise dans l'embrasure d'une porte, place à 30 cm près)
    ne bute pas sur ce mur : le rayon ne commence à compter qu'une fois entré dans une pièce (au plus 1 m plus loin)."""
    from moteur import caler_photos as cp
    from moteur.sol_a_plat import piece_de

    d = np.array([math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))])
    p, total = np.asarray(origine, float), 0.0
    if pieces is not None:
        for avance in np.arange(0.0, 1.01, 0.1):
            if piece_de(p + avance * d, pieces) is not None:
                p, total = p + avance * d, float(avance)
                break
    for _ in range(portes_max + 1):
        T, S, _ = cp.tirs(plan, p[None], np.array([angle_deg]))
        t, s = float(T[0, 0]), int(S[0, 0])
        if not np.isfinite(t):
            return math.inf, 0
        if s != 1:
            return total + t, s
        total += t + PASSE_PORTE_M
        p = p + (t + PASSE_PORTE_M) * d
    return math.inf, 0


def place_d_un_meuble(boite, repere: dict, camera: dict, largeur: int, hauteur: int, devant: list | None = None) -> dict | None:
    """La place d'un meuble PLEIN d'après la profondeur de la photo (MoGe-2, moteur.caler_photos.repere) : le cœur de son
    rectangle (sa moitié centrale) est le meuble lui-même ; sa distance est la MÉDIANE de ce cœur — et non les points les plus
    proches (moteur.objets_accroches.place_dans_la_photo, fait pour un luminaire devant un mur lointain), qui sont ici ce qui
    passe DEVANT le meuble (un buffet vu par-dessus un meuble télé). Rend position de sa face vue, bas, haut, largeur, distance."""
    h, phi, r, M = repere["h"], repere["phi"], repere["r"], repere["M"]
    Hm, Wm = M.shape
    x0, y0, x1, y1 = (float(v) for v in boite)

    def fenetre(part: float):
        u0, u1 = int((x0 + part * (x1 - x0)) * Wm / largeur), int(math.ceil((x1 - part * (x1 - x0)) * Wm / largeur))
        v0, v1 = int((y0 + part * (y1 - y0)) * Hm / hauteur), int(math.ceil((y1 - part * (y1 - y0)) * Hm / hauteur))
        u0, v0 = max(0, u0), max(0, v0)
        return slice(v0, min(Hm, max(v1, v0 + 1))), slice(u0, min(Wm, max(u1, u0 + 1)))

    # ce qui passe DEVANT le meuble (`devant` : les rectangles des meubles de la photo posés plus près, leur bas plus bas dans
    # l'image) n'est pas lui : une chaise derrière une table, dont le cœur du rectangle est le dossier de la chaise de devant
    libre = np.ones(M.shape, bool)
    for b in devant or []:
        libre[max(0, int(b[1] * Hm / hauteur)):int(math.ceil(b[3] * Hm / hauteur)), max(0, int(b[0] * Wm / largeur)):int(math.ceil(b[2] * Wm / largeur))] = False
    coeur = fenetre(0.25)
    ok = M[coeur] & repere["devant"][coeur] & libre[coeur]
    if ok.sum() < max(POINTS_COEUR_MIN, COEUR_LIBRE_MIN * ok.size):
        return None  # cœur caché par un meuble posé devant : rien de sûr à mesurer ici (ce qui dépasse autour est souvent le mur du fond)
    distance, direction = float(np.median(r[coeur][ok])), float(np.median(phi[coeur][ok]))
    tout = fenetre(0.05)
    du_meuble = M[tout] & repere["devant"][tout] & libre[tout] & (np.abs(r[tout] - distance) < EPAISSEUR_VUE_M)
    if du_meuble.sum() < POINTS_COEUR_MIN:
        return None
    bas, haut = float(np.percentile(h[tout][du_meuble], 5)), float(np.percentile(h[tout][du_meuble], 95))
    angle = math.radians(float(camera["cap"]) + direction)
    en_3d = math.hypot(distance, (bas + haut) / 2 - float(camera["z"]))
    return {"position": [float(camera["x"]) + distance * math.cos(angle), float(camera["y"]) + distance * math.sin(angle)],
            "bas": bas, "haut": haut, "largeur": (x1 - x0) / float(camera["f"]) * en_3d, "distance": distance}


# ---------------------------------------------------------------- les grands meubles ADOSSÉS (17/11/2026, étape 2)
# Un meuble adossé (armoire, buffet, bibliothèque, linéaire de cuisine…) a son dos sur un mur du PLAN, qui est exact. Les deux
# bords de son rectangle sont deux directions sûres (à 3°) : là où elles coupent le mur, c'est le meuble — sa place le long du
# mur ET sa largeur, sans passer par la distance (ce que la photo mesure mal). Avant : tout meuble avait la largeur courante de
# sa sorte (un placard de 1,50 m pour un dressing de 3 m, une étagère de 1,50 m pour une colonne de 50 cm), posée là où
# tombait le milieu du bas du rectangle ; les meubles d'un même mur se chassaient les uns les autres.
ADOSSES = ("rangement", "commode", "bibliotheque", "placard", "meuble_tv", "etagere_cubes", "colonne_cuisine", "meuble_cuisine_bas")
ADOSSES_HAUTS = ("bibliotheque", "placard", "colonne_cuisine")  # assez hauts pour être vus par-dessus ce qui cache leur pied
RASANT = 0.3  # un regard qui fait moins de 17° avec le mur ne mesure rien dessus (sinus de l'angle)
JEU_AU_MUR_M = 0.03


def face_la_plus_proche(point, logement: dict, vers) -> dict | None:
    """Comme mur_le_plus_proche, avec les deux bouts de la face : {"pied", "normale", "distance", "a", "b"}."""
    from moteur.sol_a_plat import dans_polygone

    p, v = np.asarray(point, float), np.asarray(vers, float)
    meilleur = None
    for piece in logement["pieces"]:
        c = np.asarray(piece["contour"], float)
        for a, b in zip(c, np.roll(c, -1, axis=0)):
            ab = b - a
            L2 = float(ab @ ab)
            if L2 < 1e-9:
                continue
            q = a + float(np.clip((p - a) @ ab / L2, 0.0, 1.0)) * ab
            d = float(np.linalg.norm(p - q))
            if meilleur is not None and d >= meilleur["distance"]:
                continue
            n = np.array([-ab[1], ab[0]]) / math.sqrt(L2)
            if (v - q) @ n < 0:
                n = -n
            dedans = q + 0.05 * n
            if not dans_polygone(np.array([dedans[0]]), np.array([dedans[1]]), piece["contour"])[0]:
                continue
            meilleur = {"pied": q, "normale": n, "distance": d, "a": a, "b": b}
    return meilleur


def contre_le_mur(position, sorte: str, boite, cam, logement: dict, largeur: int, distance: float, bouts: dict | None = None) -> dict | None:
    """Le meuble adossé que ce rectangle montre, mesuré SUR LE MUR : {"position" (son milieu), "largeur_mur", "coupe_mur"
    (un de ses bords est coupé par le cadre de la photo : la largeur est un minimum), "normale"}. None s'il n'est pas contre
    un mur (plus loin que ce dont la vue peut se tromper), ou si le regard rase le mur.
    `bouts` : où le meuble finit vraiment de chaque côté de l'image, d'après la lecture de la photo (moteur.lecture_photos :
    {"gauche" / "droite": "coin" (le bout de son mur), "cadre" (il sort de la photo) ou une abscisse en pixels}) ; le
    résultat porte alors "mur_lu"."""
    from moteur import meubles_photos as mp

    bouts = bouts or {}
    profondeur = mp.taille_courante(sorte)[1]
    origine = np.array([float(cam[0]), float(cam[1])])
    f = face_la_plus_proche(position, logement, origine)
    if f is None or f["distance"] > profondeur / 2 + min(1.0, mp.incertitude(distance) + 0.2):
        return None
    n = f["normale"]
    t = np.array([-n[1], n[0]])
    base = f["pied"] + n * (profondeur / 2 + JEU_AU_MUR_M)  # la ligne à mi-profondeur du meuble
    x0, y0, x1, y1 = (float(v) for v in boite)
    sa, sb = sorted((float((f["a"] - base) @ t), float((f["b"] - base) @ t)))
    bords, biais = [], []
    for cote, u in (("gauche", x0), ("droite", x1)):
        lu = bouts.get(cote)
        if lu == "cadre":
            u = 0.0 if cote == "gauche" else float(largeur)
        angle = math.radians(rayon(cam, float(lu) if isinstance(lu, (int, float)) else u, (y0 + y1) / 2)[0])
        d = np.array([math.cos(angle), math.sin(angle)])
        k = float((base - origine) @ n) / float(d @ n) if abs(float(d @ n)) >= RASANT else -1.0
        if k <= 0:
            if lu != "coin":
                return None
            bords.append(None)  # le regard rase le mur de ce côté, mais la lecture dit que le meuble va jusqu'au coin
            biais.append(0.0)
            continue
        bords.append(float((origine + k * d - base) @ t))
        biais.append(float(d @ t) / float(d @ n))
    # vu de côté, un meuble profond paraît plus large : d'un bord on voit son coin de devant, de l'autre son coin du fond
    # (une demi-profondeur × la tangente de l'angle de vue, de chaque côté) ; son milieu, lui, ne bouge pas
    trop = profondeur / 2 * (abs(biais[0]) + abs(biais[1])) / 2
    if None not in bords and abs(bords[1] - bords[0]) > 2 * trop + 0.2:
        vers = 1.0 if bords[1] >= bords[0] else -1.0
        bords = [bords[0] + vers * trop, bords[1] - vers * trop]
    # un bout « au coin » : le bout du mur, du côté de l'image que la lecture a dit (le sens de l'image le long du mur)
    a0, a1 = (math.radians(rayon(cam, u, (y0 + y1) / 2)[0]) for u in (x0, x1))
    sens = 1.0 if float(np.array([math.cos(a1) - math.cos(a0), math.sin(a1) - math.sin(a0)]) @ t) > 0 else -1.0
    if bouts.get("gauche") == "coin":
        bords[0] = sa if sens > 0 else sb
    if bouts.get("droite") == "coin":
        bords[1] = sb if sens > 0 else sa
    # le meuble ne dépasse pas des bouts de son mur
    s0, s1 = max(min(bords), sa), min(max(bords), sb)
    mini, maxi = mp.TAILLES.get(sorte, mp.TAILLES["rangement"])[1]
    if bouts:  # la lecture a dit où il finit : sa largeur n'est plus bornée par celle des meubles courants de sa sorte
        maxi = sb - sa
    if s1 - s0 < 0.5 * mini:
        return None
    coupe = ((x0 <= mp.BORD_PX and "gauche" not in bouts) or (x1 >= largeur - mp.BORD_PX and "droite" not in bouts)
             or "cadre" in bouts.values())
    large = min(max(s1 - s0, mini), maxi, sb - sa)
    milieu = min(max((s0 + s1) / 2, sa + large / 2), sb - large / 2)
    centre = base + milieu * t
    sortie = {"position": [float(centre[0]), float(centre[1])], "largeur_mur": float(large), "coupe_mur": bool(coupe),
              "normale": [float(n[0]), float(n[1])]}
    if bouts:
        sortie["mur_lu"] = True
    return sortie


# ---------------------------------------------------------------- 1. les meubles posés au sol
def au_sol_d_une_photo(objets: list[dict], cam, largeur: int, hauteur: int, piece: dict | None, rgb=None, photo: int | None = None,
                       repere: dict | None = None, camera: dict | None = None, plan: dict | None = None, logement: dict | None = None,
                       adosser: bool = True) -> list[dict]:
    """Les meubles posés au sol qu'UNE photo montre, avec la sorte donnée (`objets` : {"sorte", "boite", "note"…}).

    Par le PIED, comme le repérage en service. Avec la profondeur de la photo (`repere`, MoGe-2) et le plan, trois cas que le pied
    seul perdait sont rattrapés :
    - le bas du rectangle n'est PAS le pied du meuble (coupé par le bas de la photo, ou rectangle arrêté au-dessus du sol : le haut
      d'une colonne de cuisine) : la place vient de la profondeur mesurée dans le rectangle ;
    - le meuble tombe un peu DERRIÈRE un mur (place de l'appareil à 30-40 cm près) : il est ramené contre ce mur ;
    - le meuble est dans une AUTRE pièce, vue par une porte (appareil sur le pas de la porte de la cuisine) : gardé si rien ne le
      cache (aucun mur plein entre l'appareil et lui)."""
    from moteur import meubles_photos
    from moteur import reperer_meubles as rm
    from moteur.sol_a_plat import piece_de

    origine = np.array([float(cam[0]), float(cam[1])])
    sortie = []
    for o in objets:
        g = rm.groupe(o["sorte"])
        if g not in rm.TYPE_DE_GROUPE:
            continue
        x0, y0, x1, y1 = (float(v) for v in o["boite"])
        if repere is None or logement is None:  # sans profondeur : exactement le repérage en service
            vu = rm.vu_au_sol(g, o["sorte"], o["boite"], o["note"], cam, largeur, hauteur, piece)
        else:
            vu = rm.vu_au_sol(g, o["sorte"], o["boite"], o["note"], cam, largeur, hauteur, None)
            # ce qui est posé devant lui sur la photo : les autres meubles au sol dont le bas du rectangle est nettement plus bas
            devant = [x["boite"] for x in objets if x is not o and rm.groupe(x["sorte"]) in rm.TYPE_DE_GROUPE
                      and rm.groupe(x["sorte"]) != "tapis" and float(x["boite"][3]) > y1 + DEVANT_PX] if g in PIED_CACHE else None
            mesure = place_d_un_meuble(o["boite"], repere, camera, largeur, hauteur, devant) if g != "tapis" else None
            # le pied caché : toujours si le rectangle est coupé par le bas de la photo ou si le pied ne donne rien ; et, pour un
            # petit meuble isolé (chaise derrière une table), si le bas mesuré de son rectangle n'est pas au sol. Un grand meuble
            # adossé (buffet vu derrière des chaises) garde son pied : le cœur de son rectangle est ce qui passe devant lui.
            cache = vu is None or y1 >= hauteur - 3 or (g in PIED_CACHE and mesure is not None and mesure["bas"] > BAS_AU_SOL_M)
            if cache and vu is not None and mesure is not None and y1 < hauteur - 3:
                # la TAILLE de la sorte départage : à la distance de la profondeur, le rectangle ferait-il un meuble trop étroit pour
                # sa sorte (une chaise de 20 cm), alors qu'à la distance du pied il a sa largeur ? Le cœur montrait autre chose,
                # posé devant (une chaise lointaine vue contre le bord d'un téléviseur) : le pied est gardé.
                etroit = MOITIE * meubles_photos.TAILLES.get(o["sorte"], meubles_photos.TAILLES["rangement"])[1][0]
                au_pied = (x1 - x0) / float(cam[5]) * float(np.linalg.norm(np.asarray(vu["position"], float) - origine))
                if mesure["largeur"] < etroit <= au_pied:
                    cache = False
            if mesure is not None and cache:
                point = np.asarray(mesure["position"], float)
                direction = (point - origine) / max(float(np.linalg.norm(point - origine)), 1e-9)
                centre = point + direction * meubles_photos.taille_courante(o["sorte"])[1] / 2
                vu = {"groupe": g, "position": [float(centre[0]), float(centre[1])], "largeur_vue": float(mesure["largeur"]),
                      "confiance": float(o["note"]), "poids": float((x1 - x0) * (y1 - y0) / (largeur * hauteur) * 100) * POIDS_PROFONDEUR}
            def par_le_regard(lu: bool = False) -> dict | None:
                """Un meuble HAUT adossé dont le pied est caché (une bibliothèque derrière un canapé) : le bas de son rectangle
                n'est pas son pied, il « tombe » derrière le mur. Sa place : contre le mur plein que son regard touche.
                `lu` : la lecture de la photo a dit « pied caché » — pour tout meuble adossé, même bas, même sous une fenêtre."""
                if not lu and (o["sorte"] not in ADOSSES_HAUTS or o.get("approche")):
                    return None
                angle = rayon(cam, (x0 + x1) / 2, (y0 + y1) / 2)[0]
                mur, plein = premier_mur(plan, origine, angle, pieces=logement["pieces"])
                if not math.isfinite(mur) or (plein != 0 and not lu):
                    return None
                recul = mur - meubles_photos.taille_courante(o["sorte"])[1] / 2 - JEU_AU_MUR_M
                place = origine + recul * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
                return {"groupe": g, "position": [float(place[0]), float(place[1])], "largeur_vue": float((x1 - x0) / float(cam[5]) * mur),
                        "confiance": float(o["note"]), "poids": float((x1 - x0) * (y1 - y0) / (largeur * hauteur) * 100) * POIDS_PROFONDEUR}

            if o.get("pied_cache") and o["sorte"] in ADOSSES:
                vu = par_le_regard(lu=True) or vu
            if vu is None:
                vu = par_le_regard()
            if vu is None:
                continue
            centre = np.asarray(vu["position"], float)
            dans = piece_de(centre, logement["pieces"])
            if dans is None:  # un peu derrière un mur : ramené contre lui, dedans
                m = mur_le_plus_proche(centre, logement, origine)
                if m is None or m[2] > DERRIERE_LE_MUR_M:
                    vu = par_le_regard()
                    if vu is None:
                        continue
                    centre = np.asarray(vu["position"], float)
                else:
                    centre = m[0] + m[1] * (meubles_photos.taille_courante(o["sorte"])[1] / 2 + 0.03)
                dans = piece_de(centre, logement["pieces"])
                if dans is None:
                    continue
                vu["position"] = [float(centre[0]), float(centre[1])]
            if piece is not None and dans["id"] != piece["id"]:  # une autre pièce : seulement si rien ne la cache
                distance = float(np.linalg.norm(centre - origine))
                angle = math.degrees(math.atan2(centre[1] - origine[1], centre[0] - origine[0]))
                mur = premier_mur(plan, origine, angle, pieces=logement["pieces"])[0]
                if mur < distance - CACHE_M:
                    # un mur plein est devant lui : il n'est pas dans l'autre pièce, il a traversé la cloison (place à 30-40 cm
                    # près). Tombé juste derrière : ramené devant ce mur, dans la pièce de l'appareil. Plus loin : écarté.
                    if distance - mur > DERRIERE_LE_MUR_M:
                        continue
                    recul = max(mur - meubles_photos.taille_courante(o["sorte"])[1] / 2 - 0.03, 0.1)
                    centre = origine + (centre - origine) / max(distance, 1e-9) * recul
                    devant = piece_de(centre, logement["pieces"])
                    if devant is None or devant["id"] != piece["id"]:
                        continue
                    vu["position"] = [float(centre[0]), float(centre[1])]
        if vu is None:
            continue
        if logement is not None:
            # un rectangle approché (tracé à l'œil) ne mesure rien sur le mur, sauf si la lecture a dit où le meuble finit
            if adosser and o["sorte"] in ADOSSES and (not o.get("approche") or o.get("bouts")):
                sur = contre_le_mur(vu["position"], o["sorte"], o["boite"], cam, logement, largeur,
                                    float(np.linalg.norm(np.asarray(vu["position"], float) - origine)), bouts=o.get("bouts"))
                if sur is not None and piece_de(sur["position"], logement["pieces"]) is not None:
                    vu.update(sur)
            vu["piece"] = (piece_de(vu["position"], logement["pieces"]) or {}).get("id")
        vu.update(categorie=o["sorte"], photo=photo, phrase=o.get("dit") or o["sorte"], forme=o.get("forme"), numero=o.get("numero"),
                  distance=float(np.linalg.norm(np.asarray(vu["position"], float) - origine)), approche=bool(o.get("approche")),
                  appareil=[float(origine[0]), float(origine[1])], coupe=bool(y1 >= hauteur - meubles_photos.BORD_PX and g != "tapis"),
                  mesure={**meubles_photos.mesurer(o["boite"], cam, largeur, hauteur, rgb), "appareil": [float(c) for c in cam[:3]]})
        sortie.append(vu)
    return sortie


LOIN_M = 4.5  # un meuble vu seulement d'aussi loin n'a pas de place sûre (moteur.meubles_photos.incertitude : plus de 1,1 m)
PLUS_PRES = 0.6  # une photo prise à moins de 60 % de cette distance, qui regarde l'endroit, fait foi sur ce qui s'y trouve
MARGE_CADRE = 0.08  # l'endroit doit être dans le cadre de cette photo, à 8 % du bord au moins
LARGE_LOINTAIN = 1.5  # un meuble lointain rejoint un meuble de son GROUPE vu de près jusqu'à 1,5 fois la limite habituelle


HAUTEURS_VOISINES = 1.5  # deux sortes dont les hauteurs courantes diffèrent de moins de 50 % peuvent nommer le même meuble


def confirmer_les_lointains(trouves: list[dict], appareils: list[tuple], plan: dict, logement: dict, journal=lambda *_: None,
                            par_sorte: bool = True, objets_par_photo: dict[int, list[dict]] | None = None) -> list[dict]:
    """Un meuble vu SEULEMENT de loin (place incertaine de plus d'un mètre) est rarement un meuble de plus. D'abord il rejoint
    le meuble déjà posé de son groupe qu'il peut être (c'est lui, nommé autrement d'une photo à l'autre : « buffet » et
    « commode », ou tombé loin de sa place). Sinon, si une photo bien plus proche regarde l'endroit sans rien y montrer de son
    groupe, il est écarté (cette photo, lue elle aussi, l'aurait montré). Sinon il est gardé : c'est le seul témoin de ce
    meuble (le fond d'une grande pièce photographiée d'un seul bout).
    `appareils` : [(caméra 8 nombres, (largeur, hauteur) de la photo)], dans l'ordre des photos.
    Les meubles viennent de moteur.meubles_photos.associer (ils gardent leurs vues, `_vues`)."""
    from moteur import meubles_photos as mp
    from moteur.camera_photo import projeter

    def regarde(k: int, place) -> bool:
        cam, (largeur, hauteur) = appareils[k]
        u, v, d = projeter((float(place[0]), float(place[1]), 0.4), cam)
        if not (d > 0.3 and MARGE_CADRE * largeur <= u <= (1 - MARGE_CADRE) * largeur and 0 <= v <= hauteur):
            return False
        origine = np.array([float(cam[0]), float(cam[1])])
        distance = float(np.linalg.norm(np.asarray(place, float) - origine))
        angle = math.degrees(math.atan2(place[1] - origine[1], place[0] - origine[0]))
        return premier_mur(plan, origine, angle, pieces=logement["pieces"])[0] >= distance - CACHE_M

    def montre(k: int, t: dict) -> bool:
        """La photo k a-t-elle, dans la direction de ce meuble, un rectangle lu de son groupe (même si Atelya n'a pas su le
        poser : pied caché derrière un canapé) ?"""
        cam, _ = appareils[k]
        u, _, d = projeter((float(t["position"][0]), float(t["position"][1]), 0.4), cam)
        marge = float(cam[5]) * min(1.0, mp.incertitude(t["distance_min"])) / max(d, 0.5)
        return any(rm.groupe(o["sorte"]) == t["groupe"] and semblables(o["sorte"], t["categorie"])
                   and float(o["boite"][0]) - marge <= u <= float(o["boite"][2]) + marge for o in (objets_par_photo or {}).get(k, []))

    def semblables(a: str, b: str) -> bool:
        """Deux sortes d'un même groupe qui peuvent nommer le même meuble d'une photo à l'autre (un buffet et une commode,
        une armoire et une bibliothèque ; pas une bibliothèque et un meuble télé) : leurs hauteurs courantes sont voisines."""
        ha, hb = mp.taille_courante(a)[2], mp.taille_courante(b)[2]
        return max(ha, hb) <= HAUTEURS_VOISINES * min(ha, hb)

    from moteur import reperer_meubles as rm

    gardes = [t for t in trouves if t["distance_min"] < LOIN_M]
    for t in sorted((t for t in trouves if t["distance_min"] >= LOIN_M), key=lambda t: t["distance_min"]):
        # 1. c'est un meuble déjà posé, plus sûr que lui : même groupe, même pièce, hauteurs voisines, vu par d'AUTRES photos,
        #    et à sa portée (la limite d'une vue lointaine, une fois et demie)
        vue = min(t["_vues"], key=mp.eloignement)
        memes = [(c, g) for g in gardes if g["groupe"] == t["groupe"] and semblables(g["categorie"], t["categorie"])
                 and g["_vues"][0].get("piece") == t["_vues"][0].get("piece") and not set(g["photos"]) & set(t["photos"])
                 and (c := mp.meme_meuble(vue, g["position"], mp.seuil_de(vue, par_sorte), LARGE_LOINTAIN)) is not None]
        if memes:
            g = min(memes, key=lambda c: c[0])[1]
            g["vues"] += t["vues"]
            g["photos"] = sorted(set(g["photos"]) | set(t["photos"]))
            g["membres"] = g["membres"] + t["membres"]
            journal(f"  {t['categorie']} vu de loin ({t['distance_min']:.1f} m) = {g['categorie']} déjà posé en {g['position']}")
            continue
        # 2. sinon : une photo bien plus proche regarde-t-elle l'endroit ? Si elle n'y montre rien de son groupe, il est écarté ;
        #    si personne ne regarde de plus près, il est gardé (le seul témoin du fond d'une grande pièce)
        proches = [k for k, (cam, _) in enumerate(appareils) if k not in t["photos"]
                   and math.dist(cam[:2], t["position"]) <= PLUS_PRES * t["distance_min"] and regarde(k, t["position"])]
        if not proches or any(montre(k, t) for k in proches):
            gardes.append(t)
        else:
            journal(f"  {t['categorie']} vu seulement de loin ({t['distance_min']:.1f} m) en {t['position']}, qu'une photo plus proche "
                    f"regarde sans le montrer : écarté")
    return [t for t in trouves if any(t is g for g in gardes)]  # l'ordre d'origine est gardé


# ---------------------------------------------------------------- 2. les objets au mur
def au_mur_d_une_photo(objets: list[dict], cam, camera: dict, plan: dict, repere: dict | None, largeur: int, hauteur: int,
                       logement: dict, rgb=None, photo: int | None = None, sortes=tuple(AU_MUR)) -> list[dict]:
    """Les objets accrochés qu'UNE photo montre : sorte, place sur le mur, face, bas, haut, largeur.

    La place vient de la profondeur mesurée dans le rectangle (MoGe-2), puis l'objet est collé au mur le plus proche s'il en est à
    moins de COLLE_AU_MUR_M (la profondeur est juste à 10-15 % près ; le mur du plan, lui, est exact) ; plus loin de tout mur, il
    reste où il est mesuré, face à l'appareil (une télévision sur une cloison-meuble que le plan n'a pas). Sans profondeur : le
    premier mur que le plan met dans la direction du rectangle."""
    from moteur.objets_accroches import place_dans_la_photo
    from moteur.sol_a_plat import piece_de_l_appareil

    origine = np.array([float(cam[0]), float(cam[1])])
    _, dedans = piece_de_l_appareil(cam, logement["pieces"])
    vers = np.asarray(dedans, float) if dedans is not None else origine  # d'où l'on voit, DANS la pièce (appareil sur un seuil)
    sortie = []
    for o in objets:
        if o["sorte"] not in sortes:
            continue
        x0, y0, x1, y1 = (float(v) for v in o["boite"])
        mesure = place_dans_la_photo(o["boite"], repere, camera, largeur, hauteur) if repere is not None else None
        if mesure is not None:
            point, distance = np.asarray(mesure["position"], float), float(mesure["distance"])
        else:
            angle = rayon(cam, (x0 + x1) / 2, (y0 + y1) / 2)[0]
            distance = premier_mur(plan, origine, angle, pieces=logement["pieces"])[0]
            if not math.isfinite(distance):
                continue
            point = origine + distance * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        regard = (point - origine) / max(float(np.linalg.norm(point - origine)), 1e-9)
        m = mur_le_plus_proche(point, logement, vers)
        if m is not None and m[2] <= COLLE_AU_MUR_M:
            position, n = m[0], m[1]
            face, sur_le_mur, de_face = math.degrees(math.atan2(n[1], n[0])), True, abs(float(n @ regard))
        else:
            position, sur_le_mur, de_face = point, False, 1.0
            face = math.degrees(math.atan2(-regard[1], -regard[0]))
        if mesure is not None:
            bas, haut = mesure["bas"], mesure["haut"]
        else:
            bas, haut = (float(cam[2]) + rayon(cam, (x0 + x1) / 2, v)[1] * distance for v in (y1, y0))
        # la largeur vraie d'un objet plat vu de biais est sa largeur apparente divisée par le cosinus de l'angle de vue
        etendue = (x1 - x0) / float(cam[5]) * math.hypot(distance, (bas + haut) / 2 - float(cam[2])) / max(de_face, DE_BIAIS_MIN)
        sortie.append({"sorte": o["sorte"], "position": [float(position[0]), float(position[1])], "face": float(face), "bas": float(bas),
                       "haut": float(haut), "largeur": float(etendue) if etendue < LARGEUR_MAX_M else None, "note": float(o["note"]),
                       "photo": photo, "poids": (x1 - x0) * (y1 - y0), "couleur": _couleur(rgb, o["boite"]), "sur_le_mur": sur_le_mur,
                       "dit": o.get("dit"), "distance": float(distance), "appareil": [float(origine[0]), float(origine[1])]})
    return sortie


def fusionner_au_mur(vus: list[dict], fusion_m: float = FUSION_MUR_M) -> list[dict]:
    """Le même objet accroché vu sur plusieurs photos ne compte qu'une fois (même sorte, à moins de `fusion_m`, plus loin le
    long du regard pour une vue lointaine : moteur.meubles_photos.reunir) ; la place et la face sont celles de sa vue la plus
    PROCHE, les hauteurs et la largeur les médianes."""
    from moteur.meubles_photos import reunir

    sortie = []
    for paquet in reunir(vus, fusion_m, MEME_OBJET_M, cle="sorte"):  # la vue la plus proche en tête : la plus sûre
        tete = paquet[0]
        largeurs = [v["largeur"] for v in paquet if v.get("largeur")]
        couleurs = [v["couleur"] for v in paquet if v.get("couleur")]
        sortie.append({**tete, "vues": len(paquet), "bas": float(np.median([v["bas"] for v in paquet])),
                       "haut": float(np.median([v["haut"] for v in paquet])), "largeur": float(np.median(largeurs)) if largeurs else None,
                       "note": float(np.mean([v["note"] for v in paquet])),
                       "couleur": [int(c) for c in np.median(np.array(couleurs), axis=0)] if couleurs else None})
    return sortie


def vers_meubles_au_mur(trouves: list[dict], logement: dict, source: str = "repérage par lecture des photos") -> list[dict]:
    """Objets accrochés trouvés → meubles du logement (statut « estime ») : collés au mur, bas et taille bornés par leur sorte."""
    from moteur.sol_a_plat import piece_de

    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    sortie, rang = [], {}
    for t in trouves:
        (l0, ep, h0), (bas_min, bas_max) = AU_MUR[t["sorte"]]
        n = np.array([math.cos(math.radians(t["face"])), math.sin(math.radians(t["face"]))])
        position = np.asarray(t["position"], float) + (n * (ep / 2 + 0.01) if t.get("sur_le_mur", True) else 0.0)
        piece = piece_de(position + n * 0.05, logement["pieces"]) or piece_de(position, logement["pieces"])
        if piece is None:
            continue
        largeur = min(max(t["largeur"] or l0, 0.5 * l0), 2.5 * l0)
        hauteur = min(max(t["haut"] - t["bas"], 0.5 * h0), 2.0 * h0)
        if t["sorte"] == "horloge":
            largeur = hauteur = (largeur + hauteur) / 2
        altitude = min(max(t["bas"], bas_min), bas_max, hsp - 0.05 - hauteur)
        if t["sorte"] == "miroir" and t["bas"] < 0.25:
            altitude = 0.0  # un miroir posé au sol, appuyé au mur
        rang[t["sorte"]] = rang.get(t["sorte"], 0) + 1
        m = {"id": f"{t['sorte']}_lu_{rang[t['sorte']]}", "categorie": t["sorte"], "piece": piece["id"],
             "position": [round(float(position[0]), 3), round(float(position[1]), 3)], "face": round(t["face"], 1),
             "dimensions": [round(largeur, 2), ep, round(hauteur, 2)], "altitude": round(max(altitude, 0.0), 2), "statut": "estime",
             "source": f"{source} ({t['vues']} photo(s))", "confiance": min(1.0, t["note"])}
        if t.get("couleur") and t["sorte"] != "miroir":
            m["couleur"] = t["couleur"]
        sortie.append(m)
    return sortie


# ---------------------------------------------------------------- 4. les baies
def baies_d_une_photo(objets: list[dict], cam, plan: dict, logement: dict) -> dict[str, list[int]]:
    """Ce que la lecture d'UNE photo dit des baies du plan : {id de la baie: [fois lue « porte_fenetre », fois lue « fenetre »]}."""
    from moteur import caler_photos as cp
    from moteur.ouvertures_photos import _baies, _touche

    origine = np.array([float(cam[0]), float(cam[1])])
    baies = _baies(logement)
    votes: dict[str, list[int]] = {}
    for o in objets:
        if o["sorte"] not in BAIES:
            continue
        x0, y0, x1, y1 = (float(v) for v in o["boite"])
        touchees: dict[str, int] = {}
        for u in np.linspace(x0, x1, RAYONS_BAIE + 2)[1:-1]:
            angle = rayon(cam, float(u), (y0 + y1) / 2)[0]
            distance, sorte = premier_mur(plan, origine, angle, pieces=logement["pieces"])
            if sorte != 2:
                continue
            proches = [(t, b["id"]) for b in baies if (t := _touche(origine, angle, b["a"], b["b"])) is not None]
            proches = [c for c in proches if abs(c[0] - distance) <= 0.5]
            if proches:
                ident = min(proches, key=lambda c: abs(c[0] - distance))[1]
                touchees[ident] = touchees.get(ident, 0) + 1
        if touchees and max(touchees.values()) >= RAYONS_MIN:
            votes.setdefault(max(touchees, key=touchees.get), [0, 0])[0 if o["sorte"] == "porte_fenetre" else 1] += 1
    return votes


def corriger_les_baies(logement: dict, votes: dict[str, list[int]], mesures: dict[str, list[int]] | None = None,
                       journal=None) -> tuple[dict, list[dict], list[dict]]:
    """Le logement dont les baies ont la sorte LUE sur les photos (majorité des photos qui la montrent ; égalité : rien ne
    change), à DEUX CLÉS : quand la mesure du bas de la baie (moteur.ouvertures_photos, `mesures` : directions « jusqu'au sol »,
    « sur allège ») a un avis net et CONTRAIRE, rien n'est changé et le désaccord est rendu (un doute à montrer). Rend le
    logement, ce qui a changé, les désaccords."""
    from moteur.ouvertures_photos import PART_MIN, VOTES_MIN, corriger

    tranches, desaccords = {}, []
    for ident, (pf, f) in votes.items():
        if pf == f:
            continue
        lu = "porte_fenetre" if pf > f else "fenetre"
        sol, allege = (mesures or {}).get(ident, (0, 0))
        if sol + allege >= VOTES_MIN:
            mesure = "porte_fenetre" if sol / (sol + allege) >= PART_MIN else "fenetre" if allege / (sol + allege) >= PART_MIN else None
            if mesure is not None and mesure != lu:
                desaccords.append({"id": ident, "lu": lu, "mesure": mesure, "votes_lus": [pf, f], "votes_mesure": [sol, allege]})
                if journal:
                    journal(f"  baie {ident} : lue « {lu} », mesurée « {mesure} » : désaccord, rien n'est changé")
                continue
        tranches[ident] = [VOTES_MIN * 10, 0] if lu == "porte_fenetre" else [0, VOTES_MIN * 10]
    lg, changes = corriger(logement, tranches, journal)
    return lg, changes, desaccords


# ---------------------------------------------------------------- 5. les sols
def sols_lus(lecture: dict, releve: dict, logement: dict) -> dict[str, dict]:
    """La famille du sol de chaque pièce d'après la lecture : {id de pièce: {"famille", "uniforme", "autres", "photos"}}.
    La pièce d'une photo est celle où se tient son appareil ; la famille est celle que le plus de photos donnent."""
    from moteur.camera_photo import camera_depuis_dict
    from moteur.sol_a_plat import piece_de_l_appareil

    voix: dict[str, dict] = {}
    for nom, d in releve["cameras"].items():
        sol = (lecture["photos"].get(nom) or {}).get("sol") or {}
        if not sol.get("famille"):
            continue
        piece, _ = piece_de_l_appareil(camera_depuis_dict(d["camera"]), logement["pieces"])
        if piece is None:
            continue
        v = voix.setdefault(piece["id"], {"familles": {}, "autres": set(), "photos": 0})
        v["familles"][sol["famille"]] = v["familles"].get(sol["famille"], 0) + 1
        v["photos"] += 1
        if not sol.get("uniforme", True) and sol.get("autre_famille"):
            v["autres"].add(sol["autre_famille"])
    sortie = {}
    for pid, v in voix.items():
        famille = max(v["familles"], key=v["familles"].get)
        autres = sorted((v["autres"] | set(v["familles"])) - {famille})
        sortie[pid] = {"famille": famille, "uniforme": not autres, "autres": autres, "photos": v["photos"]}
    return sortie


def appliquer_les_sols(pieces: dict, lus: dict[str, dict]) -> dict:
    """Le résultat de la brique photos (moteur.reconnaitre_sols.reconnaitre → « pieces ») corrigé par la lecture : la famille de
    la pièce est celle qui est LUE ; ses zones d'un autre sol ne sont gardées que si la lecture dit que la pièce a aussi CE sol
    (une zone de la famille lue rejoint le sol de la pièce ; une zone d'un sol que personne n'a lu est une erreur de la brique)."""
    sortie = {}
    for pid, s in pieces.items():
        lu = lus.get(pid)
        if lu is None:
            sortie[pid] = s
            continue
        zones = [z for z in s.get("zones", []) if z["famille"] != lu["famille"] and z["famille"] in lu["autres"]]
        sortie[pid] = {**s, "famille": lu["famille"], "zones": zones, "famille_brique": s["famille"]}
    return sortie


# ---------------------------------------------------------------- l'ensemble
def poser(releve: dict, logement: dict, racine, objets_par_photo: dict[str, list[dict]], modele_moge=None, par_sorte: bool = True,
          source: str = "repérage par lecture des photos", journal=lambda *_: None, equiper: bool = True, associer: bool = True,
          adosser: bool = True) -> dict:
    """Photos placées (fiche cameras-photos.json) + objets de chaque photo avec leur sorte → ce qu'Atelya en fait :
    {"meubles": meubles à ajouter au logement (au sol rangés, suspendus, au mur), "baies": votes,
     "equipements": ce que moteur.equipements.poser rend (équipements à ajouter, rideaux, passe-plats, non posés)}.
    `equiper` faux : les équipements sont seulement comptés (rien n'est posé), comme avant le 16/11/2026."""
    from pathlib import Path

    import cv2

    from moteur import caler_photos as cp
    from moteur import equipements as eq
    from moteur import meubles_photos, moge
    from moteur import objets_accroches as oa
    from moteur import reperer_meubles as rm
    from moteur.camera_photo import camera_depuis_dict
    from moteur.images import lire_image
    from moteur.ranger_meubles import ranger
    from moteur.sol_a_plat import piece_de, piece_de_l_appareil

    modele_moge = modele_moge or moge.charger()
    plan = cp.plan_du_logement(logement)
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    dossier, fichier = Path(racine) / releve["photos"], releve.get("fichier", "{nom}.png")
    vus, par_photo, suspendus, au_mur, vues_equipements, baies, tailles = [], [], [], [], [], {}, []
    vides = eq.vides_du_plan(logement) if equiper else []
    for k, (nom, d) in enumerate(releve["cameras"].items()):
        objets = objets_par_photo.get(nom) or []
        image = lire_image(dossier / fichier.format(nom=nom))
        if image is None:
            raise FileNotFoundError(dossier / fichier.format(nom=nom))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        hauteur, largeur = rgb.shape[:2]
        tailles.append((largeur, hauteur))
        cam = camera_depuis_dict(d["camera"])
        piece, _ = piece_de_l_appareil(cam, logement["pieces"])
        repere = cp.repere(cp.mesurer(modele_moge, rgb, float(d["camera"]["f"])), hsp) if objets else None
        de_la_photo = au_sol_d_une_photo(objets, cam, largeur, hauteur, piece, rgb, photo=k, repere=repere, camera=d["camera"], plan=plan,
                                         logement=logement, adosser=adosser)
        vus += de_la_photo
        par_photo.append(de_la_photo)
        suspendus += oa.suspensions_d_une_photo(
            [{"phrase": oa.PHRASES[0], "note": max(float(o["note"]), oa.NOTE_MIN), "boite": o["boite"]} for o in objets if o["sorte"] == "suspension"],
            repere, d["camera"], largeur, hauteur, logement, rgb, photo=k)
        au_mur += au_mur_d_une_photo(objets, cam, d["camera"], plan, repere, largeur, hauteur, logement, rgb, photo=k)
        vues_equipements += eq.vues_d_une_photo(objets, cam, d["camera"], plan, repere, largeur, hauteur, logement, rgb, photo=k, vides=vides)
        for ident, (pf, f) in baies_d_une_photo(objets, cam, plan, logement).items():
            t = baies.setdefault(ident, [0, 0])
            t[0] += pf
            t[1] += f
        journal(f"  {nom} : {len(de_la_photo)} meuble(s) au sol, {sum(1 for o in objets if o['sorte'] == 'suspension')} suspension(s), "
                f"{sum(1 for o in objets if o['sorte'] in AU_MUR)} au mur, {sum(1 for o in objets if o['sorte'] in eq.SORTES_LUES)} équipement(s)")
    if associer:  # le même meuble d'une photo à l'autre : des vues les plus sûres aux moins sûres (16/11/2026)
        trouves = meubles_photos.associer(vus, par_sorte=par_sorte)
        appareils = [(camera_depuis_dict(d["camera"]), t) for d, t in zip(releve["cameras"].values(), tailles)]
        lus = {k: objets_par_photo.get(nom) or [] for k, nom in enumerate(releve["cameras"])}
        trouves = confirmer_les_lointains(trouves, appareils, plan, logement, journal, par_sorte=par_sorte, objets_par_photo=lus)
    else:
        trouves = meubles_photos.fusionner(vus, par_sorte=par_sorte)
    for t in trouves:
        t.pop("_vues", None)
    # un meuble mesuré SUR son mur (contre_le_mur) y est déjà : le coller de nouveau le déplacerait vers un autre mur
    trouves = [m if m.get("largeur_mur") else rm.coller_au_mur(m, piece_de(m["position"], logement["pieces"])) for m in trouves]
    trouves = rm.plafonner(trouves, par_photo, logement)
    nouveaux = rm.vers_meubles_du_logement(trouves, logement)
    # d'où chaque meuble a été vu (clé privée, retirée avant de rendre les meubles) : un meuble mesuré dans une cheminée glisse
    # le long de ce regard (moteur.equipements.faire_place). « reperage_k » est le k-ième des meubles trouvés.
    regards = {f"reperage_{k}": [mes["appareil"] for mes in t.get("mesures", []) if mes.get("appareil")] for k, t in enumerate(trouves, start=1)}
    for m in nouveaux:
        m["source"] = m["source"].replace("repérage photos", source)
        if equiper and regards.get(m["id"]):
            m["_appareils"] = regards[m["id"]]
    deja = list(logement.get("meubles", []))
    ranges, _ = ranger(deja + nouveaux, logement, journal=journal)
    nouveaux = [m for m in ranges if not any(m["id"] == x["id"] for x in deja)]
    accroches = oa.vers_meubles(oa.fusionner(suspendus), logement) + vers_meubles_au_mur(fusionner_au_mur(au_mur), logement, source)
    for m in accroches:
        m["source"] = m["source"].replace("repérage photos", source)
    pris = {m["id"] for m in deja} | {p["id"] for p in logement["pieces"]}
    for m in nouveaux + accroches:
        while m["id"] in pris:
            m["id"] += "b"
        pris.add(m["id"])
    poses = nouveaux + accroches
    if equiper:
        equipements = eq.poser(vues_equipements, logement, deja + poses, journal, vides=vides)
        # une cheminée est bâtie : les meubles posés d'après les photos qui la traversaient se sont écartés (ou sont retirés)
        ranges = {m["id"]: m for m in equipements.pop("meubles_ranges")}
        poses = [ranges[m["id"]] for m in poses if m["id"] in ranges]
        for m in equipements["meubles"]:
            while m["id"] in pris:
                m["id"] += "b"
            pris.add(m["id"])
    else:
        equipements = {"meubles": [], "rideaux": {}, "passe_plats": [], "murs": [], "colonnes": [], "mesures": [],
                       "non_poses": [{"sorte": v["sorte"] or v["lu"], "piece": v["piece"], "raison": "équipements non demandés"}
                                     for v in vues_equipements]}
    for m in poses:
        m.pop("_appareils", None)
    return {"meubles": poses, "equipements": equipements, "baies": baies, "trace": {"trouves": trouves, "photos": list(releve["cameras"])}}
