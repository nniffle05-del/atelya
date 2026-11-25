r"""LES ÉQUIPEMENTS DU LOGEMENT : de ce que la lecture des photos a compris à ce qu'Atelya pose (16/11/2026).

Pourquoi (demande de NT du 16/11/2026) : la lecture des photos comprend la cheminée, les radiateurs, le four, la plaque, le
réfrigérateur, la hotte, l'évier, le lavabo, la baignoire, le WC, les rideaux, les appliques, les niches, le passe-plat ; la
maquette n'en dessinait aucun (57 compris sur trois logements, 0 dessiné : cuisine et salle de bains vides, séjour sans
cheminée). Ici Atelya décide OÙ et à quelle TAILLE chacun se pose ; moteur/blender/equipements.py le dessine.

Le partage reste celui de la lecture : elle dit CE QUE C'EST (une sorte, un mot), jamais où ni combien ça mesure.
Quatre façons de poser, selon la sorte :
- ADOSSÉ À UN MUR (cheminée, radiateur, applique, étagères, hotte ; et les volumes posés au sol : réfrigérateur, lave-linge,
  lavabo, baignoire, douche, WC) : la profondeur mesurée dans le rectangle (MoGe-2) donne un point à 10-15 % près ; l'objet
  est collé à la face de MUR de sa pièce la plus proche de ce point, glissé le long du mur hors des portes, des fenêtres
  qu'il masquerait, de ce qui est déjà accroché là et — pour un volume — des meubles déjà posés ; s'il n'y a pas de place à
  moins d'un mètre, il n'est pas posé (et c'est dit) ;
- ENCASTRÉ (four, micro-ondes, plaque, évier, vasque) : porté par le meuble de cuisine (ou le meuble vasque) le plus proche,
  SUR son plan ou SUR sa façade ; sans meuble pour le porter, il n'est pas posé (Atelya n'invente pas le meuble) ;
- AU PLAFOND (plafonnier, rampe de spots) : à la place mesurée, collé au plafond ;
- les RIDEAUX habillent la fenêtre du plan la plus proche (champ `rideaux` de l'ouverture) ; un PASSE-PLAT perce le mur que
  les rayons de son rectangle touchent — ou REFERME EN MURET le vide que le plan a laissé à cet endroit (un plan dessine
  souvent le passe-plat comme un passage : app-004) : champ `passe_plats` du logement, un trou sans menuiserie.
Le même équipement vu sur plusieurs photos ne compte qu'une fois ; une pièce n'a qu'UNE cheminée, hotte, baignoire, douche.

Qui cède la place à qui : une CHEMINÉE est bâtie dans le mur — elle se pose d'abord, et un meuble posé d'après les photos
qui la traverse s'écarte (moteur/ranger_meubles.py). Tous les autres équipements se glissent à côté des meubles déjà posés,
qui ne bougent pas : sans cheminée, les meubles sont exactement ceux qu'Atelya posait sans les équipements.
"""
from __future__ import annotations

import math
import re
import unicodedata

import numpy as np

VERSION = "0.1.0"

# ------------------------------------------------------------------ ce que chaque sorte devient
# fixés au mur : taille courante (largeur, épaisseur, hauteur), bas (min, max), largeur (min, max), hauteur (min, max)
AU_MUR = {
    "cheminee": ((1.3, 0.35, 1.15), (0.0, 0.0), (1.0, 1.7), (1.0, 1.3)),
    "radiateur": ((0.9, 0.10, 0.6), (0.08, 0.25), (0.6, 1.4), (0.5, 0.8)),
    "seche_serviettes": ((0.5, 0.08, 1.3), (0.5, 0.9), (0.4, 0.6), (1.0, 1.7)),
    "applique": ((0.2, 0.12, 0.25), (1.4, 2.0), (0.14, 0.35), (0.18, 0.4)),
    "etagere_murale": ((0.9, 0.25, 1.2), (0.2, 1.6), (0.4, 2.0), (0.3, 2.0)),
    "niche": ((0.9, 0.12, 1.2), (0.2, 1.6), (0.4, 2.0), (0.3, 2.0)),
    "hotte": ((0.7, 0.45, 0.6), (1.5, 1.75), (0.55, 1.0), (0.09, 1.1)),
}
# volumes posés au sol, adossés : taille courante (largeur le long du mur, profondeur, hauteur)
AU_SOL = {"refrigerateur": (0.6, 0.65, 1.8), "electromenager": (0.6, 0.6, 0.85), "lavabo": (0.7, 0.48, 0.88),
          "baignoire": (1.7, 0.75, 0.58), "douche": (0.9, 0.9, 2.0), "wc": (0.38, 0.66, 0.8)}
# encastrés : taille (largeur, profondeur ou saillie, hauteur), meubles qui peuvent les porter, où (« plan » ou « facade »)
ENCASTRES = {
    "plaque": ((0.6, 0.52, 0.01), ("meuble_cuisine_bas", "ilot"), "plan"),
    "evier": ((0.8, 0.5, 0.02), ("meuble_cuisine_bas", "ilot"), "plan"),
    "four": ((0.6, 0.03, 0.6), ("colonne_cuisine", "meuble_cuisine_bas", "ilot"), "facade"),
    "micro_ondes": ((0.6, 0.03, 0.38), ("colonne_cuisine",), "facade"),
    "vasque": ((0.5, 0.4, 0.13), ("rangement", "commode", "meuble_cuisine_bas", "table_de_chevet"), "plan"),
}
AU_PLAFOND = {"plafonnier": (0.38, 0.38, 0.1), "rampe": (1.2, 0.08, 0.1)}
CATEGORIE = {"seche_serviettes": "radiateur", "niche": "etagere_murale", "micro_ondes": "four", "vasque": "lavabo", "rampe": "plafonnier"}
# une pièce n'en a qu'une : toutes ses vues se fondent (deux vues de la plaque à 1,50 m l'une de l'autre sont LA plaque)
UNE_PAR_PIECE = ("cheminee", "hotte", "baignoire", "douche", "plaque", "evier", "four", "micro_ondes", "refrigerateur")
VOLUMES = ("cheminee", *AU_SOL)  # ne traversent ni un meuble ni un autre volume
BATI = ("cheminee",)  # bâti dans le mur : posé d'abord, ce sont les meubles qui s'écartent
SANS_DESSIN = ("store",)  # compris par la lecture, pas encore dessinés
SORTES_LUES = (*AU_MUR, *AU_SOL, *ENCASTRES, *AU_PLAFOND, "lave_linge", "lave_vaisselle", "rideaux", "passe_plat", *SANS_DESSIN)

FUSION_M = 1.0  # deux vues de la même sorte (photos différentes) à moins de 1 m sont le même équipement
MEME_OBJET_M = 0.3  # … et à moins de 30 cm, même sur une seule photo
RAYON_MUR_M = 1.5  # un équipement adossé cherche son mur à moins de 1,5 m du point mesuré
GLISSE_MAX_M = 1.0  # il glisse le long du mur d'au plus 1 m pour trouver sa place
PAS_M = 0.05
MARGE_BAIE_M = 0.05
MARGE_HAUTEUR_M = 0.15
DANS_LA_PIECE = 0.9
DEVANT_M = 0.12
FOYER_M = 0.4  # le sol devant une cheminée (son foyer) reste libre
GLISSE_REGARD_M = 1.2  # un meuble mesuré dans la cheminée glisse d'au plus 1,2 m le long du regard de l'appareil qui l'a vu
FACE_MIN_M = 0.3
PORTEUR_MAX_M = 1.2  # un encastré cherche son meuble à moins de 1,2 m du point mesuré
VASQUE_MAX_M = 0.35  # … et une vasque, à moins de 35 cm du meuble qui la porte (sinon c'est un lavabo sur son propre meuble)
MODULE = 0.6  # largeur d'un élément de cuisine
RIDEAU_MAX_M = 1.2  # un rideau habille la fenêtre du plan à moins de 1,2 m du point où il est mesuré
VOILAGE = (244, 243, 238)
# passe-plat : bornes (m)
PP_LARGEUR, PP_ALLEGE, PP_HAUT_MAX, PP_HAUTEUR_MIN, PP_BORD = (0.5, 2.6), (0.8, 1.2), 2.2, 0.5, 0.15
PP_RAYONS, PP_RAYONS_MIN = 9, 5
PP_PORTEE_M = 9.0
VIDE_MIN_M = 0.4  # un vide du plan plus court n'est pas un passage

COULEURS = {"blanc cassé": (236, 232, 222), "blanc": (240, 240, 236), "blanche": (240, 240, 236), "noir": (30, 30, 32), "noire": (30, 30, 32),
            "gris clair": (200, 200, 198), "gris anthracite": (70, 72, 76), "gris": (140, 140, 140), "grise": (140, 140, 140),
            "bleu": (70, 100, 150), "bleue": (70, 100, 150), "jaune": (225, 185, 60), "beige": (214, 200, 172), "crème": (235, 226, 205),
            "rouge": (165, 55, 50), "vert": (90, 125, 85), "verte": (90, 125, 85), "rose": (225, 170, 180), "mauve": (170, 140, 190),
            "brun": (110, 78, 55), "marron": (110, 78, 55), "doré": (200, 165, 80), "inox": (188, 190, 193), "bois clair": (200, 170, 125),
            "bois foncé": (95, 65, 45), "bois": (170, 130, 90), "pin": (215, 180, 125), "rotin": (190, 155, 105)}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


def preciser(sorte: str, dit: str | None) -> str | None:
    """La sorte PRÉCISE d'un équipement lu (clé de AU_MUR, AU_SOL, ENCASTRES, AU_PLAFOND, ou « rideaux », « voilage »,
    « passe_plat »), d'après la sorte de la lecture et ce qu'elle en dit (« electromenager four encastré », « radiateur
    sèche-serviettes », « plafonnier rampe de spots »). None : compris mais pas dessiné (un store, un appareil sans nom)."""
    mots = _sans_accents(dit or "")
    if sorte == "electromenager":
        for cles, precise in ((("refrig", "frigo", "congel"), "refrigerateur"), (("micro",), "micro_ondes"), (("four",), "four"),
                              (("plaque", "cuisson"), "plaque"), (("lave", "seche-linge", "machine"), "electromenager")):
            if any(c in mots for c in cles):
                return precise
        return None
    if sorte == "radiateur":
        return "seche_serviettes" if "seche" in mots else "radiateur"
    if sorte == "plafonnier":
        return "rampe" if ("spot" in mots or "rampe" in mots) else "plafonnier"
    if sorte == "etagere_murale":
        return "niche" if "niche" in mots else "etagere_murale"
    if sorte == "rideaux":
        # « rideaux beiges, avec voilages » : des rideaux épais DEVANT un voilage (les deux : voir rideaux_des_fenetres)
        return "voilage" if ("voil" in mots and "avec voil" not in mots) else "rideaux"
    if sorte in ("lave_linge", "lave_vaisselle"):
        return "electromenager"
    if sorte in SANS_DESSIN:
        return None
    return sorte if sorte in (*AU_MUR, *AU_SOL, *ENCASTRES, *AU_PLAFOND, "passe_plat") else None


def couleur_dite(mots: str | None) -> tuple[int, int, int] | None:
    """La couleur qu'un mot de la lecture désigne (« blanche », « inox », « mauve ») ; None si elle n'en dit rien."""
    if not mots:
        return None
    bas = " " + mots.lower().replace(",", " ").replace(";", " ") + " "
    for nom, rgb in COULEURS.items():  # « blanc cassé » et « gris clair » avant « blanc » et « gris »
        if f" {nom} " in bas:
            return rgb
    return None


# ------------------------------------------------------------------ géométrie : faces de murs, baies, place libre
def faces_de_la_piece(piece: dict, logement: dict) -> list[dict]:
    """Les faces de MURS qui bordent la pièce : pour chaque mur et chacun de ses deux côtés, les morceaux de face dont le
    devant (8 cm) est dans la pièce. On part des murs et non du contour de la pièce : un contour relu à l'écran est dentelé
    (la salle de bains d'app-004 : 12 petits côtés pour deux murs en biais), un mur est droit.
    {"mur", "cote", "a" (début de la face), "t" (direction), "n" (normale, vers la pièce), "longueur", "s0" (place de `a` le
    long de l'axe du mur), "piece"}."""
    from moteur.sol_a_plat import dans_polygone

    sortie = []
    for m in logement.get("murs", []):
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        L = float(np.linalg.norm(b - a))
        if L < FACE_MIN_M:
            continue
        t = (b - a) / L
        ep = float(m.get("epaisseur", 0.2))
        for cote in (1, -1):
            n = cote * np.array([-t[1], t[0]])
            s = np.arange(0.025, L, 0.05)
            devant = a[None] + s[:, None] * t[None] + n[None] * (ep / 2 + 0.08)
            dedans = dans_polygone(devant[:, 0], devant[:, 1], piece["contour"])
            k = 0
            while k < len(s):
                if not dedans[k]:
                    k += 1
                    continue
                j = k
                while j + 1 < len(s) and dedans[j + 1]:
                    j += 1
                s0, s1 = float(s[k]) - 0.025, float(s[j]) + 0.025
                if s1 - s0 >= FACE_MIN_M:
                    sortie.append({"mur": m["id"], "cote": cote, "a": a + s0 * t + n * ep / 2, "t": t, "n": n, "longueur": s1 - s0, "s0": s0,
                                   "piece": piece})
                k = j + 1
    return sortie


def faces_proches(point, piece: dict, logement: dict, rayon: float = RAYON_MUR_M) -> list[dict]:
    """Les faces de murs de la pièce à moins de `rayon` du point, de la plus proche à la plus lointaine ; chacune porte en plus
    "s" (la place du point le long d'elle) et "d" (sa distance)."""
    p = np.asarray(point, float)
    sortie = []
    for f in faces_de_la_piece(piece, logement):
        s = float(np.clip((p - f["a"]) @ f["t"], 0.0, f["longueur"]))
        d = float(np.linalg.norm(p - (f["a"] + s * f["t"])))
        if d <= rayon:
            sortie.append({**f, "s": s, "d": d})
    return sorted(sortie, key=lambda f: f["d"])


def baies_de_la_face(face: dict, logement: dict) -> list[tuple[float, float, float, float]]:
    """Les portes, fenêtres et passe-plats percés dans le mur de cette face : (début, fin le long de la face, bas, haut)."""
    sortie = []
    for o in [*logement.get("ouvertures", []), *logement.get("passe_plats", [])]:
        if o.get("mur") != face["mur"]:
            continue
        s0, s1 = float(o["position"]) - face["s0"], float(o["position"]) + float(o["largeur"]) - face["s0"]
        if s1 < 0 or s0 > face["longueur"]:
            continue
        bas = float(o.get("allege", 0.0) or 0.0)
        sortie.append((s0, s1, bas, bas + float(o.get("hauteur", 2.1))))
    return sortie


def _meuble(face: dict, s: float, dims, altitude: float = 0.0) -> dict:
    """L'emprise d'un objet de taille `dims` adossé à la face, son milieu à `s` le long d'elle."""
    centre = face["a"] + s * face["t"] + face["n"] * (dims[1] / 2 + 0.01)
    return {"position": [float(centre[0]), float(centre[1])], "face": math.degrees(math.atan2(face["n"][1], face["n"][0])),
            "dimensions": [float(d) for d in dims], "altitude": float(altitude)}


def place_libre(face: dict, s: float, dims, altitude: float, logement: dict, obstacles: list[dict] = (), accroches: list[dict] = (),
                glisse: float = GLISSE_MAX_M) -> float | None:
    """La place la plus proche de `s`, le long de la face, où l'objet tient : tout entier sur la face, hors de toute baie qu'il
    croiserait (une porte ; une fenêtre s'il monte au-dessus de son appui), hors de ce qui est déjà accroché à cette face à sa
    hauteur (`accroches` : {"mur", "cote", "s0", "s1", "z0", "z1"}, le long de l'axe du mur), dans sa pièce, sans traverser un
    `obstacle` (meubles et volumes déjà posés). None s'il n'y en a pas à moins de `glisse`."""
    from moteur.ranger_meubles import TOUCHE, part_dans_la_piece, recouvrement

    largeur, hauteur = float(dims[0]), float(dims[2])
    if largeur > face["longueur"] + 1e-6:
        return None
    pris = [b for b in baies_de_la_face(face, logement) if b[2] < altitude + hauteur - 0.02 and b[3] > altitude + 0.02]
    # … deux objets l'un au-dessus de l'autre (une niche au-dessus d'un radiateur) peuvent se chevaucher de 15 cm en hauteur :
    # leurs hauteurs sont mesurées à 10-15 cm près
    pris += [(o["s0"] - face["s0"], o["s1"] - face["s0"], o["z0"], o["z1"]) for o in accroches
             if o["mur"] == face["mur"] and o["cote"] == face["cote"] and o["z0"] < altitude + hauteur - MARGE_HAUTEUR_M
             and o["z1"] > altitude + MARGE_HAUTEUR_M]

    def tient(x: float) -> bool:
        if x - largeur / 2 < -1e-6 or x + largeur / 2 > face["longueur"] + 1e-6:
            return False
        if any(x + largeur / 2 > b0 - MARGE_BAIE_M and x - largeur / 2 < b1 + MARGE_BAIE_M for b0, b1, _, _ in pris):
            return False
        m = _meuble(face, x, dims, altitude)
        # « dans sa pièce » se juge 12 cm en avant : le contour d'une pièce passe souvent quelques centimètres devant la face
        # du mur (plan relevé à la main), et un radiateur de 10 cm d'épaisseur serait tout entier « hors de la pièce »
        devant = {**m, "position": [m["position"][0] + DEVANT_M * float(face["n"][0]), m["position"][1] + DEVANT_M * float(face["n"][1])]}
        if part_dans_la_piece(devant, face["piece"]) < DANS_LA_PIECE:
            return False
        return not any(recouvrement(m, o) > TOUCHE for o in obstacles)

    s = float(np.clip(s, largeur / 2, face["longueur"] - largeur / 2))
    for k in range(int(glisse / PAS_M) + 1):
        for signe in ((0,) if k == 0 else (1, -1)):
            x = s + signe * k * PAS_M
            if tient(x):
                return x
    return None


def point_vu(origine, point, plan: dict, logement: dict) -> np.ndarray | None:
    """Le point mesuré, ramené DEVANT le premier mur plein que le plan met entre l'appareil et lui (la profondeur est juste à
    10-15 % près, la place de l'appareil à 30-40 cm : un objet accroché au mur tombe souvent un peu derrière)."""
    from moteur.photos_lues import premier_mur

    o, p = np.asarray(origine, float), np.asarray(point, float)
    distance = float(np.linalg.norm(p - o))
    if distance < 1e-6:
        return None
    angle = math.degrees(math.atan2(p[1] - o[1], p[0] - o[0]))
    mur = premier_mur(plan, o, angle, pieces=logement["pieces"])[0]
    if math.isfinite(mur) and mur < distance:
        p = o + (p - o) / distance * max(mur - 0.03, 0.05)
    return p


# ------------------------------------------------------------------ 1. ce qu'UNE photo montre
def vues_d_une_photo(objets: list[dict], cam, camera: dict, plan: dict, repere: dict | None, largeur: int, hauteur: int,
                     logement: dict, rgb=None, photo: int | None = None, vides: list[dict] | None = None) -> list[dict]:
    """Les équipements qu'UNE photo montre : sorte précise, point mesuré (ramené devant les murs), bas, haut, largeur vue,
    pièce, couleur dite. Un passe-plat porte en plus le mur (ou le vide du plan) que ses rayons traversent : `trou`.
    `vides` : les limites sans mur du logement (vides_du_plan), calculées une fois pour toutes les photos."""
    from moteur.objets_accroches import place_dans_la_photo
    from moteur.photos_lues import _couleur, place_d_un_meuble, premier_mur, rayon
    from moteur.sol_a_plat import piece_de, piece_de_l_appareil

    origine = np.array([float(cam[0]), float(cam[1])])
    piece_cam, dedans = piece_de_l_appareil(cam, logement["pieces"])
    vers = np.asarray(dedans, float) if dedans is not None else origine
    sortie = []
    for o in objets:
        if o["sorte"] not in SORTES_LUES:
            continue
        precise = preciser(o["sorte"], o.get("dit"))
        x0, y0, x1, y1 = (float(v) for v in o["boite"])
        base = {"lu": o["sorte"], "sorte": precise, "photo": photo, "dit": o.get("dit"), "poids": (x1 - x0) * (y1 - y0),
                "note": float(o.get("note", 0.5)), "couleur": couleur_dite(o.get("couleur_dite") or o.get("dit")),
                "couleur_vue": _couleur(rgb, o["boite"]), "piece": piece_cam["id"] if piece_cam else None, "point": None}
        if o["sorte"] == "rideaux":  # de quoi mesurer ses PANS (pans_d_une_fenetre) : son rectangle, l'appareil, les fenêtres lues
            base.update(boite=[x0, y0, x1, y1], appareil=[float(c) for c in cam], image=(int(largeur), int(hauteur)),
                        baies_vues=[[float(c) for c in f["boite"]] for f in objets if f["sorte"] in ("fenetre", "porte_fenetre")])
            # … et sa TRINGLE (23/11/2026) : le trait fin qui passe par le haut du tissu, sa hauteur dans le relief, sa couleur
            base["tringle_vue"] = tringle_d_une_vue(rgb, [x0, y0, x1, y1], repere, precise == "voilage",
                                                   pente_d_une_horizontale(cam, plan, logement, x0, x1, y0))
        if precise is None:
            sortie.append(base)
            continue
        mesure = None
        if repere is not None:
            volume = precise in VOLUMES
            mesure = (place_d_un_meuble if volume else place_dans_la_photo)(o["boite"], repere, camera, largeur, hauteur)
            if mesure is None and volume:
                mesure = place_dans_la_photo(o["boite"], repere, camera, largeur, hauteur)
        if precise == "passe_plat":
            trou = trou_d_une_photo(o["boite"], cam, logement, vides if vides is not None else vides_du_plan(logement),
                                    profondeur_du_cadre(o["boite"], repere, largeur, hauteur) if repere is not None else None)
            sortie.append({**base, "trou": trou})
            continue
        if mesure is not None:
            point = np.asarray(mesure["position"], float)
            bas, haut, etendue = float(mesure["bas"]), float(mesure["haut"]), float(mesure["largeur"])
        else:  # sans profondeur : le premier mur dans la direction du rectangle
            angle = rayon(cam, (x0 + x1) / 2, (y0 + y1) / 2)[0]
            distance = premier_mur(plan, origine, angle, pieces=logement["pieces"])[0]
            if not math.isfinite(distance):
                sortie.append(base)
                continue
            point = origine + distance * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
            bas, haut = (float(cam[2]) + rayon(cam, (x0 + x1) / 2, v)[1] * distance for v in (y1, y0))
            etendue = (x1 - x0) / float(cam[5]) * math.hypot(distance, (bas + haut) / 2 - float(cam[2]))
        point = point_vu(vers, point, plan, logement)
        piece = piece_de(point, logement["pieces"]) if point is not None else None
        if piece is None:
            piece = piece_cam
        sortie.append({**base, "point": [float(point[0]), float(point[1])] if point is not None else None,
                       "piece": piece["id"] if piece else None, "bas": bas, "haut": haut, "largeur": etendue})
    return sortie


def vides_du_plan(logement: dict) -> list[dict]:
    """Les VIDES du plan : les morceaux de contour où deux pièces se touchent SANS MUR entre elles (cuisine ouverte sur
    l'entrée, baie libre entre deux murs), chacun une seule fois : {"a", "b"} en mètres. C'est là qu'un plan a pu dessiner un
    passe-plat comme un simple passage. (moteur.preparer_verification.limites_sans_mur sert l'écran : ses limites sont
    prolongées à travers les murs, on ne peut pas s'en servir ici.)"""
    from moteur.sol_a_plat import piece_de

    murs = [(np.asarray(m["debut"], float), np.asarray(m["fin"], float), float(m.get("epaisseur", 0.2))) for m in logement.get("murs", [])]

    def sur_un_mur(q: np.ndarray) -> bool:
        for a, b, ep in murs:  # dans l'épaisseur du mur, entre ses deux bouts (pas au-delà : le vide commence au bout du mur)
            L = float(np.linalg.norm(b - a))
            u = (b - a) / max(L, 1e-9)
            x = float((q - a) @ u)
            if -0.02 <= x <= L + 0.02 and abs(float((q - a) @ np.array([-u[1], u[0]]))) <= ep / 2 + 0.06:
                return True
        return False

    sortie: list[dict] = []
    for piece in logement["pieces"]:
        c = np.asarray(piece["contour"], float)
        for a, b in zip(c, np.roll(c, -1, axis=0)):
            L = float(np.linalg.norm(b - a))
            if L < VIDE_MIN_M:
                continue
            t = (b - a) / L
            n = np.array([-t[1], t[0]])
            places = np.arange(0.025, L, 0.05)
            libre = []
            for x in places:
                q = a + x * t
                voisines = {(piece_de(q + cote * 0.15 * n, logement["pieces"]) or {}).get("id") for cote in (-1, 1)}
                libre.append(not sur_un_mur(q) and len(voisines - {None}) == 2)
            k = 0
            while k < len(places):
                if not libre[k]:
                    k += 1
                    continue
                j = k
                while j + 1 < len(places) and libre[j + 1]:
                    j += 1
                p0, p1 = a + (float(places[k]) - 0.025) * t, a + (float(places[j]) + 0.025) * t
                if float(np.linalg.norm(p1 - p0)) >= VIDE_MIN_M and not any(
                        float(np.linalg.norm((p0 + p1) / 2 - (v["a"] + v["b"]) / 2)) < 0.25 for v in sortie):
                    sortie.append({"a": p0, "b": p1})
                k = j + 1
    return sortie


def profondeur_du_cadre(boite, repere: dict, largeur: int, hauteur: int) -> float | None:
    """La distance (à plat) du MUR qui entoure un trou : la médiane des points mesurés dans une bande AUTOUR du rectangle (à
    gauche, à droite, au-dessus : le mur percé), et non dedans — dedans, on voit la pièce d'après, plus loin."""
    r, M = repere["r"], repere["M"] & repere["devant"]
    Hm, Wm = M.shape
    x0, y0, x1, y1 = (float(v) for v in boite)
    bande = max(0.12 * (x1 - x0), 0.02 * largeur)
    px = lambda u: int(min(max(u * Wm / largeur, 0), Wm))
    py = lambda v: int(min(max(v * Hm / hauteur, 0), Hm))
    autour = np.zeros_like(M)
    autour[py(y0 - bande):py(y1), px(x0 - bande):px(x1 + bande)] = True
    autour[py(y0):py(y1), px(x0):px(x1)] = False
    ok = autour & M
    return float(np.median(r[ok])) if int(ok.sum()) >= 30 else None


def _croise(origine: np.ndarray, d: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[float, float] | None:
    """Le rayon (origine, direction d) croise-t-il le segment [a, b] ? (distance le long du rayon, place le long du segment)."""
    e = b - a
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    ao = a - origine
    t = (ao[0] * e[1] - ao[1] * e[0]) / den
    s = (ao[0] * d[1] - ao[1] * d[0]) / den
    if t <= 0.05 or s < 0.0 or s > 1.0:
        return None
    return float(t), float(s * np.linalg.norm(e))


def trou_d_une_photo(boite, cam, logement: dict, vides: list[dict], profondeur: float | None) -> dict | None:
    """Ce qu'un passe-plat perce, d'après UNE photo. Les rayons tirés dans la largeur de son rectangle traversent des murs
    pleins et des vides du plan (limites sans mur) ; celui qui porte le passe-plat est le croisement le plus proche de la
    profondeur mesurée dans le rectangle (le cadre du passe-plat) — sans profondeur, le premier mur plein. Rend
    {"mur": id, "s0", "s1" (le long de l'axe du mur), "bas", "haut"} ou {"vide": n° du vide, "bas", "haut"} ; None si les
    rayons se dispersent."""
    from moteur.photos_lues import rayon

    origine = np.array([float(cam[0]), float(cam[1])])
    x0, y0, x1, y1 = (float(v) for v in boite)
    murs = [(m["id"], np.asarray(m["debut"], float), np.asarray(m["fin"], float)) for m in logement.get("murs", [])]
    touches: dict[tuple, list] = {}
    for u in np.linspace(x0, x1, PP_RAYONS):
        angle = math.radians(rayon(cam, float(u), (y0 + y1) / 2)[0])
        d = np.array([math.cos(angle), math.sin(angle)])
        croisements = []
        for ident, a, b in murs:
            c = _croise(origine, d, a, b)
            if c is not None and c[0] <= PP_PORTEE_M:
                croisements.append((c[0], ("mur", ident), c[1]))
        for k, v in enumerate(vides):
            c = _croise(origine, d, v["a"], v["b"])
            if c is not None and c[0] <= PP_PORTEE_M:
                croisements.append((c[0], ("vide", k), c[1]))
        if not croisements:
            continue
        if profondeur is not None:
            proche = min(croisements, key=lambda c: abs(c[0] - profondeur))
            if abs(proche[0] - profondeur) > max(0.8, 0.3 * profondeur):
                continue
        else:
            pleins = [c for c in croisements if c[1][0] == "mur"]
            if not pleins or min(croisements)[1][0] != "mur":
                continue
            proche = min(pleins)
        touches.setdefault(proche[1], []).append((proche[2], proche[0]))
    if not touches:
        return None
    cle = max(touches, key=lambda k: len(touches[k]))
    pts = touches[cle]
    if len(pts) < PP_RAYONS_MIN:
        return None
    distance = float(np.median([p[1] for p in pts]))
    bas, haut = (float(cam[2]) + rayon(cam, (x0 + x1) / 2, v)[1] * distance for v in (y1, y0))
    if cle[0] == "vide":
        return {"vide": cle[1], "bas": bas, "haut": haut}
    s = sorted(p[0] for p in pts)
    # les rayons couvrent la largeur du rectangle : ses deux bords sont les deux bords du trou (ramenés à ce mur)
    part = (len(pts) - 1) / (PP_RAYONS - 1)
    centre, demi = (s[0] + s[-1]) / 2, (s[-1] - s[0]) / 2 / max(part, 0.3)
    return {"mur": cle[1], "s0": centre - demi, "s1": centre + demi, "bas": bas, "haut": haut}


# ------------------------------------------------------------------ 2. le même équipement vu plusieurs fois
def fusionner(vues: list[dict]) -> list[dict]:
    """Les vues du même équipement réunies : même catégorie et, pour une cheminée, une hotte, une baignoire, une douche, même
    pièce ; sinon à moins de FUSION_M (photos différentes) ou de MEME_OBJET_M (même photo). La place est la médiane des points
    mesurés ; bas, haut et largeur aussi ; la sorte précise et la couleur dite sont celles que le plus de vues donnent."""
    categorie = lambda v: CATEGORIE.get(v["sorte"], v["sorte"]) if v["sorte"] not in ENCASTRES else v["sorte"]
    restants = sorted((v for v in vues if v.get("point") is not None), key=lambda v: -v["poids"])
    sortie = []
    while restants:
        tete = restants.pop(0)
        paquet, photos = [tete], {tete["photo"]}
        for v in sorted(restants, key=lambda v: math.dist(v["point"], tete["point"])):
            if categorie(v) != categorie(tete):
                continue
            if v["piece"] != tete["piece"]:
                continue  # jamais à travers un mur : un radiateur du séjour et celui de la chambre, dos à dos
            if tete["sorte"] not in UNE_PAR_PIECE:
                ecart = math.dist(v["point"], tete["point"])
                if ecart >= FUSION_M or (ecart >= MEME_OBJET_M and v["photo"] is not None and v["photo"] in photos):
                    continue
            paquet.append(v)
            photos.add(v["photo"])
        restants = [v for v in restants if not any(v is p for p in paquet)]
        mediane = lambda cle: float(np.median([v[cle] for v in paquet]))
        couleurs: dict[tuple, int] = {}
        sortes: dict[str, int] = {}
        for v in paquet:
            sortes[v["sorte"]] = sortes.get(v["sorte"], 0) + 1
            if v.get("couleur"):
                couleurs[tuple(v["couleur"])] = couleurs.get(tuple(v["couleur"]), 0) + 1
        dits = [v["dit"] for v in paquet if v.get("dit")]
        sortie.append({"sorte": max(sortes, key=sortes.get), "piece": tete["piece"],
                       "point": [float(np.median([v["point"][0] for v in paquet])), float(np.median([v["point"][1] for v in paquet]))],
                       "bas": mediane("bas"), "haut": mediane("haut"), "largeur": mediane("largeur"), "vues": len(photos),
                       "note": float(np.mean([v["note"] for v in paquet])), "dit": dits[0] if dits else None,
                       "couleur": list(max(couleurs, key=couleurs.get)) if couleurs else None})
    return sortie


def _muret_dans_le_vide(vide: dict, logement: dict) -> dict | None:
    """Le mur qui referme un vide du plan : dans l'axe et à l'épaisseur du mur qui le prolonge d'un côté ou de l'autre (ses
    bouts sont ceux des murs voisins). None si aucun mur ne prolonge ce vide (deux pièces ouvertes l'une sur l'autre, sans
    mur à continuer : pas de quoi porter un passe-plat)."""
    a, b = vide["a"], vide["b"]
    L = float(np.linalg.norm(b - a))
    t = (b - a) / L
    n = np.array([-t[1], t[0]])
    bouts = {}  # côté du vide (0 : vers a, 1 : vers b) → (écart, bout du mur voisin, épaisseur)
    for m in logement.get("murs", []):
        ma, mb = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        u = (mb - ma) / max(float(np.linalg.norm(mb - ma)), 1e-9)
        ep = float(m.get("epaisseur", 0.2))
        if abs(float(u @ t)) < 0.97:
            continue
        for bout in (ma, mb):
            if abs(float((bout - a) @ n)) > ep / 2 + 0.08:
                continue
            s = float((bout - a) @ t)
            for cote, cible in ((0, 0.0), (1, L)):
                ecart = abs(s - cible)
                if ecart <= 0.25 and (cote not in bouts or ecart < bouts[cote][0]):
                    bouts[cote] = (ecart, bout, ep)
    if not bouts:
        return None
    ep = min(v[2] for v in bouts.values())
    axe = float(np.mean([(v[1] - a) @ n for v in bouts.values()]))
    debut = bouts[0][1] if 0 in bouts else a + n * axe
    fin = bouts[1][1] if 1 in bouts else b + n * axe
    if float(np.linalg.norm(fin - debut)) < PP_LARGEUR[0]:
        return None
    return {"debut": [round(float(debut[0]), 3), round(float(debut[1]), 3)], "fin": [round(float(fin[0]), 3), round(float(fin[1]), 3)],
            "epaisseur": round(ep, 3)}


def fusionner_les_trous(vues: list[dict], logement: dict, vides: list[dict], journal=lambda *_: None) -> tuple[list[dict], list[dict]]:
    """Les passe-plats du logement et les murets qu'il faut ajouter pour les porter : (passe_plats, murs).
    - dans un MUR plein : les vues qui le percent au même endroit (milieux à moins de 1 m, ou intervalles qui se touchent) sont
      un seul trou (médianes), borné, tenu loin des bouts du mur et des autres ouvertures, gardé seulement s'il y a une PIÈCE
      de chaque côté (jamais un trou vers dehors) ;
    - dans un VIDE du plan : le vide est refermé par un muret (dans l'axe des murs voisins), percé sur toute sa longueur."""
    from moteur.sol_a_plat import piece_de

    murs = {m["id"]: m for m in logement.get("murs", [])}
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    trous = [v["trou"] for v in vues if v.get("trou")]
    # Plusieurs murs ou vides désignés par des photos différentes : presque toujours LE MÊME passe-plat, mal situé par une
    # photo (profondeur trop longue : le vide d'après, dans l'axe). Celui que le plus de photos désignent reste ; un autre
    # n'est gardé que s'il a au moins la moitié de ses voix.
    cle = lambda t: ("vide", t["vide"]) if "vide" in t else ("mur", t["mur"])
    voix: dict[tuple, int] = {}
    for t in trous:
        voix[cle(t)] = voix.get(cle(t), 0) + 1
    for k, n in voix.items():
        if n < max(voix.values()) / 2:
            journal(f"  passe-plat : {n} vue(s) le situent ailleurs ({k[0]} {k[1]}) que les {max(voix.values())} autres : écartée(s)")
    trous = [t for t in trous if voix[cle(t)] >= max(voix.values()) / 2]

    def hauteurs(g: list[dict]) -> tuple[float, float]:
        """Bas et haut du trou : médianes des vues plausibles (une vue dont le rectangle descend jusqu'au meuble posé dessous
        ou dont l'appareil est mal calé en hauteur donne un bas sous 50 cm ou un haut sous 1,50 m : écartée s'il en reste)."""
        bons = [x for x in g if 0.5 <= x["bas"] <= 1.5 and 1.5 <= x["haut"] <= 2.7] or g
        return float(np.clip(np.median([x["bas"] for x in bons]), *PP_ALLEGE)), float(np.median([x["haut"] for x in bons]))
    passe_plats, nouveaux = [], []
    for k in sorted({t["vide"] for t in trous if "vide" in t}):
        g = [t for t in trous if t.get("vide") == k]
        muret = _muret_dans_le_vide(vides[k], logement)
        longueur = math.dist(muret["debut"], muret["fin"]) if muret else 0.0
        if muret is None or longueur > PP_LARGEUR[1]:
            journal("  passe-plat lu dans un vide du plan : " + ("aucun mur à prolonger" if muret is None else f"vide trop large ({longueur:.2f} m)")
                    + ", rien n'est fait")
            continue
        allege, haut = hauteurs(g)
        haut = float(np.clip(haut, allege + PP_HAUTEUR_MIN, min(PP_HAUT_MAX, hsp - 0.2)))
        ident = f"M_passe_plat_{len(nouveaux) + 1}"
        while ident in murs:
            ident += "b"
        nouveaux.append({"id": ident, **muret, "statut": "estime", "source": f"lecture des photos, passe-plat ({len(g)} vue(s))", "confiance": 0.6})
        # percé sur TOUTE sa longueur : la largeur du trou est exactement la longueur du muret (pas d'arrondi : il resterait
        # un fil de mur d'un dixième de millimètre au bout)
        passe_plats.append({"id": f"passe_plat_lu_{len(passe_plats) + 1}", "mur": ident, "position": 0.0, "largeur": longueur,
                            "hauteur": round(haut - allege, 2), "allege": round(allege, 2), "statut": "estime",
                            "source": f"lecture des photos ({len(g)} vue(s)) : vide du plan refermé en muret", "confiance": 0.6})
    groupes: list[list[dict]] = []
    for t in sorted((t for t in trous if "mur" in t), key=lambda t: (t["mur"], t["s0"])):
        for g in groupes:
            c = float(np.median([(x["s0"] + x["s1"]) / 2 for x in g]))
            if g[0]["mur"] == t["mur"] and (abs((t["s0"] + t["s1"]) / 2 - c) < 1.0 or (t["s0"] < max(x["s1"] for x in g) and t["s1"] > min(x["s0"] for x in g))):
                g.append(t)
                break
        else:
            groupes.append([t])
    for g in groupes:
        m = murs[g[0]["mur"]]
        a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
        L = float(np.linalg.norm(b - a))
        u = (b - a) / L
        n = np.array([-u[1], u[0]])
        centre = float(np.median([(x["s0"] + x["s1"]) / 2 for x in g]))
        largeur = min(float(np.clip(np.median([x["s1"] - x["s0"] for x in g]), *PP_LARGEUR)), L - 2 * PP_BORD)
        if largeur < PP_LARGEUR[0]:
            journal(f"  passe-plat : le mur {m['id']} est trop court ({L:.2f} m), rien n'est percé")
            continue
        allege, haut = hauteurs(g)
        haut = float(np.clip(haut, allege + PP_HAUTEUR_MIN, min(PP_HAUT_MAX, hsp - 0.2)))
        ep = float(m.get("epaisseur", 0.2))
        occupe = [(float(o["position"]) - 0.1, float(o["position"]) + float(o["largeur"]) + 0.1)
                  for o in [*logement.get("ouvertures", []), *logement.get("passe_plats", []), *passe_plats] if o.get("mur") == m["id"]]

        def tient(c: float) -> bool:
            s0, s1 = c - largeur / 2, c + largeur / 2
            if s0 < PP_BORD or s1 > L - PP_BORD or any(s1 > o0 and s0 < o1 for o0, o1 in occupe):
                return False
            for s in (s0 + 0.05, c, s1 - 0.05):  # une pièce de chaque côté, sur toute la largeur du trou
                p = a + u * s
                if any(piece_de(p + cote * n * (ep / 2 + 0.15), logement["pieces"]) is None for cote in (-1, 1)):
                    return False
            return True

        place = next((c for i in range(int(GLISSE_MAX_M / PAS_M) + 1) for c in ((centre,) if i == 0 else (centre + i * PAS_M, centre - i * PAS_M))
                      if tient(c)), None)
        if place is None:
            journal(f"  passe-plat lu sur le mur {m['id']} : pas de place (bouts du mur, autre ouverture ou pas de pièce derrière), rien n'est percé")
            continue
        passe_plats.append({"id": f"passe_plat_lu_{len(passe_plats) + 1}", "mur": m["id"], "position": round(place - largeur / 2, 3),
                            "largeur": round(largeur, 2), "hauteur": round(haut - allege, 2), "allege": round(allege, 2), "statut": "estime",
                            "source": f"lecture des photos ({len(g)} vue(s))", "confiance": 0.6})
    return passe_plats, nouveaux


# ------------------------------------------------------------------ 3. poser
def _bornes(valeur: float | None, bornes: tuple[float, float], defaut: float) -> float:
    if valeur is None or not math.isfinite(valeur):
        return defaut
    return float(min(max(valeur, bornes[0]), bornes[1]))


def _adosser(e: dict, dims, altitude: float, largeur_min: float, logement: dict, pieces: dict, obstacles: list[dict],
             accroches: list[dict], au_dessus: bool = False) -> dict | None:
    """L'équipement collé à la face de mur de sa pièce la plus proche où il tient (de proche en proche, à moins de RAYON_MUR_M).
    Sur une face plus courte que lui il rétrécit jusqu'à `largeur_min` (une cheminée sur son avancée de mur, une baignoire
    d'un mur à l'autre). `au_dessus` (étagères, niche) : s'il y a déjà un objet bas accroché là (un radiateur), l'équipement
    commence 5 cm au-dessus de lui au lieu de glisser à côté (son haut ne bouge pas)."""
    from moteur.sol_a_plat import piece_de

    piece = piece_de(e["point"], logement["pieces"]) or pieces.get(e["piece"])
    if piece is None:
        return None
    for face in faces_proches(e["point"], piece, logement):
        d, bas = list(dims), altitude
        if face["longueur"] < d[0]:
            if face["longueur"] < largeur_min:
                continue
            d[0] = round(face["longueur"] - 0.01, 2)
        if au_dessus:
            g, dr = face["s0"] + face["s"] - d[0] / 2, face["s0"] + face["s"] + d[0] / 2
            dessous = [o["z1"] for o in accroches if o["mur"] == face["mur"] and o["cote"] == face["cote"] and o["s1"] > g and o["s0"] < dr
                       and bas + MARGE_HAUTEUR_M < o["z1"] <= 1.2]
            if dessous and bas + d[2] - (max(dessous) + 0.05) >= 0.3:
                d[2] = round(bas + d[2] - (max(dessous) + 0.05), 3)
                bas = max(dessous) + 0.05
        s = place_libre(face, face["s"], d, bas, logement, obstacles, accroches)
        if s is not None:
            return {**_meuble(face, s, d, bas), "piece": piece["id"], "glisse": abs(s - face["s"]), "sur": {**face, "s": s},
                    "accroche": {"mur": face["mur"], "cote": face["cote"], "s0": face["s0"] + s - d[0] / 2, "s1": face["s0"] + s + d[0] / 2,
                                 "z0": bas, "z1": bas + d[2]}}
    return None


def _local(porteur: dict, point) -> tuple[float, float]:
    """Le point dans le repère du meuble : x le long de sa largeur, y vers son avant."""
    a = math.radians(float(porteur.get("face", 0.0)))
    d = np.asarray(point, float) - np.asarray(porteur["position"], float)
    return float(d @ np.array([-math.sin(a), math.cos(a)])), float(d @ np.array([math.cos(a), math.sin(a)]))


def _distance_au_meuble(porteur: dict, point) -> float:
    x, y = _local(porteur, point)
    dx, dy = max(abs(x) - float(porteur["dimensions"][0]) / 2, 0.0), max(abs(y) - float(porteur["dimensions"][1]) / 2, 0.0)
    return math.hypot(dx, dy)


def _du_meuble(porteur: dict, x: float, y: float) -> list[float]:
    a = math.radians(float(porteur.get("face", 0.0)))
    p = np.asarray(porteur["position"], float) + x * np.array([-math.sin(a), math.cos(a)]) + y * np.array([math.cos(a), math.sin(a)])
    return [round(float(p[0]), 3), round(float(p[1]), 3)]


def porteur_de(e: dict, meubles: list[dict], rayon: float = PORTEUR_MAX_M) -> dict | None:
    """Le meuble qui porte un encastré : le plus proche du point mesuré parmi les sortes qui peuvent le porter."""
    _, sortes, _ = ENCASTRES[e["sorte"]]
    cands = [(_distance_au_meuble(m, e["point"]), k) for k, m in enumerate(meubles)
             if m["categorie"] in sortes and float(m.get("altitude") or 0.0) < 0.3]
    cands = [c for c in cands if c[0] <= rayon]
    return meubles[min(cands)[1]] if cands else None


def encastrer(e: dict, porteur: dict, hsp: float) -> dict:
    """L'encastré à sa place sur son meuble : sur le plan (plaque, évier, vasque), au milieu de la profondeur ; sur la façade
    (four, micro-ondes), à fleur, au milieu d'un élément de 60 cm. Sa largeur ne dépasse pas celle du meuble."""
    (l, p, h), _, ou = ENCASTRES[e["sorte"]]
    L, P, H = (float(v) for v in porteur["dimensions"])
    l = min(l, L)
    x, _ = _local(porteur, e["point"])
    if ou == "facade":
        n = max(1, round(L / MODULE))
        pas = L / n
        l = min(l, pas)
        x = -L / 2 + (min(max(int((x + L / 2) / pas), 0), n - 1) + 0.5) * pas
        if porteur["categorie"] == "colonne_cuisine":
            bas = _bornes(e.get("bas"), (0.45, max(0.45, H - h - 0.1)), 0.85)
        else:
            bas = 0.135
        position, altitude = _du_meuble(porteur, x, P / 2 + p / 2 + 0.02), bas
    else:
        x = float(np.clip(x, -L / 2 + l / 2 + 0.02, L / 2 - l / 2 - 0.02)) if L > l + 0.04 else 0.0
        p = min(p, P - 0.06)
        position, altitude = _du_meuble(porteur, x, 0.0), H + 0.002
    return {"position": position, "face": float(porteur.get("face", 0.0)), "dimensions": [round(l, 2), round(p, 3), h],
            "altitude": round(min(altitude, hsp - h - 0.01), 3), "piece": porteur.get("piece"), "porteur": porteur["id"], "x": x}


def _ecarter_sur_le_plan(poses: list[dict], meubles: dict[str, dict]) -> list[dict]:
    """Deux encastrés posés sur le même plan (plaque et évier) ne se recouvrent pas : écartés de part et d'autre de leur
    milieu, puis ramenés sur le meuble ; s'il n'y a pas la place pour tous, le moins vu est retiré."""
    sortie = list(poses)
    for ident in {p["porteur"] for p in poses}:
        sur = sorted((p for p in sortie if p["porteur"] == ident and p["ou"] == "plan"), key=lambda p: p["x"])
        L = float(meubles[ident]["dimensions"][0])
        while len(sur) > 1 and sum(p["dimensions"][0] for p in sur) + 0.1 * (len(sur) - 1) > L - 0.04:
            retire = min(sur, key=lambda p: (p["vues"], p["note"]))
            sur = [p for p in sur if p is not retire]
            sortie = [p for p in sortie if p is not retire]
        for _ in range(6):
            for g, d in zip(sur, sur[1:]):
                manque = (g["dimensions"][0] + d["dimensions"][0]) / 2 + 0.1 - (d["x"] - g["x"])
                if manque > 0:
                    g["x"] -= manque / 2
                    d["x"] += manque / 2
            for p in sur:
                p["x"] = float(np.clip(p["x"], -L / 2 + p["dimensions"][0] / 2 + 0.02, L / 2 - p["dimensions"][0] / 2 - 0.02))
        for p in sur:
            p["position"] = _du_meuble(meubles[ident], p["x"], 0.0)
    return sortie


def _plaque_sous_la_hotte(encastres: list[dict], poses: list[dict], meubles: dict[str, dict], logement: dict, accroches: list[dict]) -> None:
    """Une hotte est au-dessus de la plaque. Les deux sont mesurées à 30-50 cm près, chacune de son côté : quand la hotte de la
    pièce surplombe le meuble qui porte la plaque (à 30 cm près), la plaque est mise à son aplomb ; sinon c'est la hotte qui
    glisse le long de son mur jusqu'au-dessus de la plaque (si elle y tient, et à moins de 1,5 m)."""
    for plaque in (e for e in encastres if e["sorte"] == "plaque"):
        hotte = next((p for p in poses if p["sorte"] == "hotte" and p["piece"] == plaque["piece"]), None)
        if hotte is None:
            continue
        porteur = meubles[plaque["porteur"]]
        x, y = _local(porteur, hotte["position"])
        L = float(porteur["dimensions"][0])
        if abs(x) <= L / 2 + 0.3 and abs(y) <= float(porteur["dimensions"][1]) / 2 + 0.6:
            plaque["x"] = float(min(max(x, -L / 2 + plaque["dimensions"][0] / 2 + 0.02), L / 2 - plaque["dimensions"][0] / 2 - 0.02))
            plaque["position"] = _du_meuble(porteur, plaque["x"], 0.0)
            continue
        face = hotte["sur"]
        vers = np.asarray(plaque["position"], float) - face["a"]
        s = float(vers @ face["t"])
        if abs(s - face["s"]) > 1.5 or abs(float(vers @ face["n"])) > 0.9:
            continue
        autres = [a for a in accroches if a is not hotte["accroche"]]
        place = place_libre(face, s, hotte["dimensions"], hotte["altitude"], logement, (), autres, glisse=0.2)
        if place is not None:
            d = hotte["dimensions"]
            hotte.update(_meuble(face, place, d, hotte["altitude"]))
            hotte["sur"] = {**face, "s": place}
            hotte["accroche"].update(s0=face["s0"] + place - d[0] / 2, s1=face["s0"] + place + d[0] / 2)


def _empiler_sur_la_facade(poses: list[dict], hsp: float) -> None:
    """Un four et un micro-ondes lus dans le même élément d'une colonne : le micro-ondes au-dessus du four."""
    for a in poses:
        for b in poses:
            if a is b or a["ou"] != "facade" or b["ou"] != "facade" or a["porteur"] != b["porteur"] or abs(a["x"] - b["x"]) > 0.3:
                continue
            if a["sorte"] == "four" and b["sorte"] == "micro_ondes" and b["altitude"] < a["altitude"] + a["dimensions"][2] + 0.02:
                b["altitude"] = round(min(a["altitude"] + a["dimensions"][2] + 0.03, hsp - b["dimensions"][2] - 0.01), 3)


def faire_place(meubles: list[dict], batis: list[dict], logement: dict, journal=lambda *_: None) -> list[dict]:
    """Les meubles, écartés de ce qui est BÂTI (une cheminée et les 40 cm de sol devant elle, son foyer). Sans rien de bâti :
    inchangés. Seuls les meubles posés AU SOL d'après les photos et qui touchent le bâti bougent ; tous les autres, et tout ce
    qui est accroché au mur (télévision, tableau, miroir), restent exactement où ils étaient.

    Un meuble qui traverse la cheminée a été mal situé EN PROFONDEUR : sa direction, vue de l'appareil, est sûre, sa distance ne
    l'est pas (10-20 %). Il glisse donc d'abord LE LONG DE CE REGARD (clé privée « _appareils » du meuble : la place des appareils
    qui l'ont vu ; vers l'appareil ou à l'opposé, au plus près, à moins de GLISSE_REGARD_M) : la chaise d'app-004 mesurée dans la
    cheminée retourne ainsi près de sa table, au lieu d'être posée devant le foyer. Sans appareil connu ou sans place sur ce
    regard, il s'écarte au plus court (moteur.ranger_meubles._glisser) ; sans place du tout, il est retiré."""
    if not batis:
        return list(meubles)
    from moteur import ranger_meubles as rg

    fixes = []
    for k, b in enumerate(batis):
        a = math.radians(float(b["face"]))
        l, p, h = (float(v) for v in b["dimensions"])
        fixes.append({"id": f"__bati_{k}", "categorie": CATEGORIE.get(b["sorte"], b["sorte"]), "piece": b["piece"],
                      "position": [b["position"][0] + math.cos(a) * FOYER_M / 2, b["position"][1] + math.sin(a) * FOYER_M / 2], "face": b["face"],
                      "dimensions": [l, p + FOYER_M, h], "altitude": 0.0, "statut": "mesure", "source": "bâti"})
    pieces = {p["id"]: p for p in logement.get("pieces", [])}
    au_sol = lambda m: float(m.get("altitude") or 0.0) < 0.3 and float(m["dimensions"][2]) > 0.1 and rg.groupe_de(m["categorie"]) not in rg.A_PLAT
    sortie = [dict(m) for m in meubles]
    for i, m in enumerate(sortie):
        if m is None or not au_sol(m) or rg._fixe(m) or not any(rg.recouvrement(m, f) > rg.TOUCHE for f in fixes):
            continue
        g_m = rg.groupe_de(m["categorie"])

        def accepte(e: dict) -> bool:
            if rg.part_dans_la_piece(e, pieces.get(e.get("piece"))) < rg.DANS_LA_PIECE or any(rg.recouvrement(e, f) > rg.TOUCHE for f in fixes):
                return False
            for j, autre in enumerate(sortie):
                if j == i or autre is None or not au_sol(autre):
                    continue
                permis = rg.SOUS_LA_TABLE if {g_m, rg.groupe_de(autre["categorie"])} == {"chaise", "table"} else rg.TOUCHE
                if rg.recouvrement(e, autre) > permis:
                    return False
            return True

        degage = None
        for appareil in m.get("_appareils") or []:
            regard = np.asarray(m["position"], float) - np.asarray(appareil[:2], float)
            if float(np.linalg.norm(regard)) < 1e-6:
                continue
            regard /= float(np.linalg.norm(regard))
            for k in range(1, int(GLISSE_REGARD_M / PAS_M) + 1):
                if degage is not None and k * PAS_M >= math.dist(degage["position"], m["position"]):
                    break
                essai = next((e for e in ({**m, "position": [round(float(m["position"][0] + signe * k * PAS_M * regard[0]), 3),
                                                             round(float(m["position"][1] + signe * k * PAS_M * regard[1]), 3)]}
                                          for signe in (1, -1)) if accepte(e)), None)
                if essai is not None:
                    degage = essai
                    break
        comment = "le long du regard de l'appareil"
        if degage is None:
            proche = min(fixes, key=lambda f: math.dist(f["position"], m["position"]))
            degage = rg._glisser(m, np.asarray(m["position"], float) - np.asarray(proche["position"], float), accepte)
            comment = "au plus court"
        if degage is None:
            journal(f"  meubles : {m['categorie']} {m['id']} retiré (mesuré dans la cheminée, sans place libre à côté)")
            sortie[i] = None
            continue
        if g_m == "chaise":  # une chaise qui arrive près d'une table la regarde
            tables = [t for t in sortie if t is not None and t is not m and rg.groupe_de(t["categorie"]) == "table"
                      and math.dist(t["position"], degage["position"]) < max(float(t["dimensions"][0]), float(t["dimensions"][1])) / 2 + 0.7]
            if tables:
                t = min(tables, key=lambda t: math.dist(t["position"], degage["position"]))
                vers = np.asarray(t["position"], float) - np.asarray(degage["position"], float)
                tournee = {**degage, "face": round(math.degrees(math.atan2(vers[1], vers[0])), 1)}
                if accepte(tournee):
                    degage = tournee
        journal(f"  meubles : {m['categorie']} {m['id']} écarté de la cheminée ({comment}, {math.dist(degage['position'], m['position']):.2f} m)")
        sortie[i] = degage
    return [m for m in sortie if m is not None]


def poser(vues: list[dict], logement: dict, meubles: list[dict], journal=lambda *_: None, vides: list[dict] | None = None) -> dict:
    """Toutes les vues d'équipements des photos d'un logement (vues_d_une_photo) → ce qu'Atelya en fait :
    {"meubles": équipements à ajouter au logement (statut « estime »), "rideaux": {id d'ouverture: champ rideaux},
     "passe_plats": trous à percer, "murs": murets à ajouter (vide du plan refermé sous un passe-plat),
     "non_poses": [{"sorte", "piece", "raison"}], "colonnes": ids des colonnes de cuisine lues (leur four est celui qui est lu),
     "meubles_ranges": les `meubles` reçus, écartés de ce qui est bâti (identiques s'il n'y a pas de cheminée),
     "mesures": où chaque équipement a été mesuré sur les photos, avant la pose (pour contrôler)}.
    `meubles` : les meubles déjà posés ; les volumes ne les traversent pas, les encastrés s'y logent."""
    from moteur.sol_a_plat import piece_de

    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    pieces = {p["id"]: p for p in logement["pieces"]}
    vides = vides if vides is not None else vides_du_plan(logement)
    non_poses, poses = [], []

    def refuse(e: dict, raison: str) -> None:
        non_poses.append({"sorte": e.get("sorte") or e.get("lu"), "piece": e.get("piece"), "raison": raison, "dit": e.get("dit")})
        journal(f"  équipement non posé : {e.get('sorte') or e.get('lu')} ({e.get('piece')}) : {raison}")

    for v in vues:
        if v["sorte"] is None:
            refuse(v, "compris, pas encore dessiné")
    connues = [v for v in vues if v["sorte"] is not None]
    for v in connues:
        if v["sorte"] != "passe_plat" and v.get("point") is None:
            refuse(v, "sa place n'a pas pu être mesurée")

    # --- les rideaux : la fenêtre du plan la plus proche
    rideaux = rideaux_des_fenetres([v for v in connues if v["sorte"] in ("rideaux", "voilage") and v.get("point")], logement, refuse)
    # --- les passe-plats
    passe_plats, murets = fusionner_les_trous([v for v in connues if v["sorte"] == "passe_plat"], logement, vides, journal)
    if any(v["sorte"] == "passe_plat" for v in connues) and not passe_plats:
        refuse({"sorte": "passe_plat"}, "aucun mur percé (rayons dispersés ou pas de place)")
    avec_trous = {**logement, "murs": [*logement.get("murs", []), *murets], "passe_plats": [*logement.get("passe_plats", []), *passe_plats]}

    fusionnes = fusionner([v for v in connues if v["sorte"] not in ("rideaux", "voilage", "passe_plat")])
    # --- une vasque lue sur (ou tout près d')un meuble est portée par lui ; sinon c'est un lavabo sur son propre meuble
    for e in fusionnes:
        if e["sorte"] == "lavabo" and porteur_de({**e, "sorte": "vasque"}, meubles, VASQUE_MAX_M) is not None:
            e["sorte"] = "vasque"

    def taille(e: dict) -> tuple[tuple, float, float]:
        """(largeur, épaisseur, hauteur), bas, largeur minimale sur une face trop courte."""
        if e["sorte"] in AU_SOL:
            dims = AU_SOL[e["sorte"]]
            return dims, 0.0, (1.4 if e["sorte"] == "baignoire" else dims[0])
        (l0, ep, h0), bas, larg, haut = AU_MUR[e["sorte"]]
        if e["sorte"] == "cheminee":
            return (_bornes(e["largeur"], larg, l0), ep, _bornes(e["haut"], haut, h0)), 0.0, 0.9
        if e["sorte"] == "hotte":
            altitude = _bornes(e["bas"], bas, 1.6)
            return (_bornes(e["largeur"], larg, l0), ep, round(hsp - altitude - 0.01, 2) if hsp - altitude <= haut[1] else haut[0]), altitude, larg[0]
        h = _bornes(e["haut"] - e["bas"], haut, h0)
        return (_bornes(e["largeur"], larg, l0), ep, h), min(_bornes(e["bas"], bas, sum(bas) / 2), hsp - h - 0.05), larg[0]

    def adosse(e: dict, obstacles: list[dict], accroches: list[dict]) -> dict | None:
        dims, altitude, largeur_min = taille(e)
        pose = _adosser(e, dims, altitude, largeur_min, avec_trous, pieces, obstacles, accroches, au_dessus=e["sorte"] in ("etagere_murale", "niche"))
        if pose is None:
            refuse(e, "pas de place contre un mur de sa pièce à moins d'un mètre de l'endroit mesuré")
            return None
        pose.update(sorte=e["sorte"], vues=e["vues"], note=e["note"], dit=e["dit"], couleur=e["couleur"], ou="mur")
        return pose

    par_vues = lambda liste: sorted(liste, key=lambda e: (-e["vues"], -e["note"]))
    accroches: list[dict] = []
    # --- 1. ce qui est BÂTI (cheminée) : posé d'abord, sans regarder les meubles ; ce sont eux qui s'écartent
    batis: list[dict] = []
    for e in par_vues([e for e in fusionnes if e["sorte"] in BATI]):
        pose = adosse(e, batis, accroches)
        if pose is not None:
            batis.append(pose)
            accroches.append(pose["accroche"])
    meubles = faire_place(meubles, batis, logement, journal)
    au_sol = [m for m in meubles if float(m.get("altitude") or 0.0) < 0.3 and float(m["dimensions"][2]) > 0.1]
    # --- 2. les autres volumes posés au sol : ils se glissent à côté des meubles et des volumes déjà là
    volumes = list(batis)
    for e in par_vues([e for e in fusionnes if e["sorte"] in AU_SOL]):
        pose = adosse(e, [*au_sol, *volumes], accroches)
        if pose is not None:
            volumes.append(pose)
            accroches.append(pose["accroche"])
    # --- 3. les objets minces accrochés au mur : les radiateurs d'abord (leur hauteur est fixe, une niche se pose au-dessus)
    minces = []
    for e in sorted(par_vues([e for e in fusionnes if e["sorte"] in AU_MUR and e["sorte"] not in BATI]),
                    key=lambda e: e["sorte"] not in ("radiateur", "seche_serviettes")):
        pose = adosse(e, [], accroches)
        if pose is not None:
            minces.append(pose)
            accroches.append(pose["accroche"])
    poses += volumes + minces

    # --- au plafond
    for e in (e for e in fusionnes if e["sorte"] in AU_PLAFOND):
        piece = piece_de(e["point"], logement["pieces"]) or pieces.get(e["piece"])
        if piece is None:
            refuse(e, "hors de toute pièce")
            continue
        l, p, h = AU_PLAFOND[e["sorte"]]
        face = 0.0
        if e["sorte"] == "rampe":  # le long du plus grand côté de la pièce
            c = np.asarray(piece["contour"], float)
            cotes = np.roll(c, -1, axis=0) - c
            long = cotes[np.argmax(np.linalg.norm(cotes, axis=1))]
            face = math.degrees(math.atan2(long[1], long[0])) + 90.0
        position = e["point"] if piece_de(e["point"], logement["pieces"]) is not None else [float(v) for v in np.asarray(piece["contour"], float).mean(0)]
        poses.append({"position": [round(position[0], 3), round(position[1], 3)], "face": face, "dimensions": [l, p, h],
                      "altitude": round(hsp - h, 3), "piece": piece["id"], "sorte": e["sorte"], "vues": e["vues"], "note": e["note"],
                      "dit": e["dit"], "couleur": e["couleur"], "ou": "plafond"})

    # --- encastrés : un seul de chaque sorte par meuble porteur (le plus vu) ; deux vasques possibles sur un long meuble
    tous = {m["id"]: m for m in meubles}
    encastres: dict[tuple, dict] = {}
    for e in par_vues([e for e in fusionnes if e["sorte"] in ENCASTRES]):
        porteur = porteur_de(e, meubles, VASQUE_MAX_M if e["sorte"] == "vasque" else PORTEUR_MAX_M)
        if porteur is None:
            refuse(e, "aucun meuble pour le porter à moins de 1,2 m")
            continue
        pose = encastrer(e, porteur, hsp)
        cle = (porteur["id"], e["sorte"], round(pose["x"] / 0.5) if e["sorte"] == "vasque" else 0)
        if cle in encastres:
            continue
        pose.update(sorte=e["sorte"], vues=e["vues"], note=e["note"], dit=e["dit"], couleur=e["couleur"], ou=ENCASTRES[e["sorte"]][2])
        encastres[cle] = pose
    _plaque_sous_la_hotte(list(encastres.values()), poses, tous, avec_trous, accroches)
    sur_meuble = _ecarter_sur_le_plan(list(encastres.values()), tous)
    _empiler_sur_la_facade(sur_meuble, hsp)
    poses += sur_meuble

    sortie, rang = [], {}
    for p in poses:
        categorie = CATEGORIE.get(p["sorte"], p["sorte"])
        rang[categorie] = rang.get(categorie, 0) + 1
        m = {"id": f"{categorie}_lu_{rang[categorie]}", "categorie": categorie, "piece": p["piece"],
             "position": [round(float(p["position"][0]), 3), round(float(p["position"][1]), 3)], "face": round(float(p["face"]), 1),
             "dimensions": [round(float(d), 3) for d in p["dimensions"]], "altitude": round(max(float(p["altitude"]), 0.0), 3),
             "statut": "estime", "source": f"lecture des photos, équipement ({p['vues']} photo(s))", "confiance": min(1.0, p["note"])}
        if p.get("couleur"):
            m["couleur"] = [int(c) for c in p["couleur"]]
        if p.get("dit"):
            m["description"] = p["dit"]
        sortie.append(m)
    colonnes = [m["id"] for m in meubles if m["categorie"] == "colonne_cuisine" and "lecture" in str(m.get("source", ""))]
    mesures = [{"sorte": e["sorte"], "piece": e["piece"], "point": [round(v, 2) for v in e["point"]], "vues": e["vues"]} for e in fusionnes]
    return {"meubles": sortie, "rideaux": rideaux, "passe_plats": passe_plats, "murs": murets, "non_poses": non_poses, "colonnes": colonnes,
            "meubles_ranges": meubles, "mesures": mesures}


def rideaux_des_fenetres(vues: list[dict], logement: dict, refuse=lambda *_: None) -> dict[str, dict]:
    """Les rideaux lus → le champ `rideaux` de la fenêtre du plan la plus proche de chacun (à moins de RIDEAU_MAX_M) :
    voilage (un mot « voil… » dans la lecture) et/ou rideaux épais ; couleur dite, sinon blanc pour un voilage et la couleur
    vue sur la photo pour des rideaux."""
    from moteur.ouvertures_photos import _baies

    baies = _baies(logement)
    voix: dict[str, dict] = {}
    for v in vues:
        p = np.asarray(v["point"], float)
        proches = []
        for b in baies:
            ab = b["b"] - b["a"]
            s = float(np.clip((p - b["a"]) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0))
            proches.append((float(np.linalg.norm(p - (b["a"] + s * ab))), b["id"]))
        proches = [c for c in proches if c[0] <= RIDEAU_MAX_M]
        if not proches:
            refuse(v, "aucune fenêtre du plan à moins de 1,2 m")
            continue
        r = voix.setdefault(min(proches)[1], {"voilage": [], "rideaux": [], "photos": set(), "epais": [], "toutes": []})
        r["toutes"].append(v)
        # la couleur d'un rideau épais est celle VUE sur la photo (« le même que sur la photo ») ; le mot de la lecture (« beige »,
        # « mauve » : une couleur de nuancier, bien plus pâle que les rideaux d'app-001) ne sert que sans mesure. Un voilage,
        # éclairé par derrière, garde sa couleur dite, sinon blanc.
        if v["sorte"] == "voilage":
            r["voilage"].append(v.get("couleur") or VOILAGE)
        else:
            r["rideaux"].append(v.get("couleur_vue") or v.get("couleur") or (200, 195, 185))
            r["epais"].append(v)
        if v["sorte"] == "rideaux" and "avec voil" in _sans_accents(v.get("dit") or ""):
            r["voilage"].append(VOILAGE)  # des rideaux épais devant un voilage : la fenêtre a les deux
        r["photos"].add(v["photo"])
    sortie = {}
    ouvertures = {o["id"]: o for o in logement.get("ouvertures", [])}
    for ident, r in voix.items():
        teinte = lambda liste: [int(c) for c in np.median(np.array(liste), axis=0)] if liste else None
        sortie[ident] = {"voilage": teinte(r["voilage"]), "rideaux": teinte(r["rideaux"]), "statut": "estime",
                         "source": f"lecture des photos ({len(r['photos'])} photo(s))", "confiance": 0.7}
        # combien de pans de rideaux épais, et de quel côté de la fenêtre (19/11/2026) ; sans preuve : deux pans, comme avant
        # (22/11/2026 : et la largeur de chacun, la part devant la baie, tiré ou ouvert)
        if r["epais"]:
            from moteur.largeur_baies import portee_libre

            pans = pans_d_une_fenetre(r["epais"], repere_de_la_baie(ouvertures[ident], logement), portee_libre(ouvertures[ident], logement))
            if pans:
                sortie[ident]["pans"] = pans
        # la tringle (23/11/2026) : sa hauteur et sa couleur vues sur les photos ; sans mesure, celle d'avant
        tringle = tringle_d_une_fenetre(r["toutes"], float(logement.get("hauteur_sous_plafond", 2.5)))
        if tringle:
            sortie[ident]["tringle"] = tringle
    return sortie


# ------------------------------------------------------------------ les pans de rideaux d'une fenêtre (19/11/2026)
ECART_RIDEAUX_M = 0.16  # distance au mur de la nappe des rideaux épais (moteur/blender/rideaux.py)
PAN_COTE_MIN = 0.4  # un pan est « d'un côté » si son milieu est à plus de 0,4 demi-largeur du milieu de la fenêtre
BORD_IMAGE = 0.04  # « visible » : à plus de 4 % de la largeur de l'image de son bord
RASANT = 0.42  # sinus de 25° : un rayon qui arrive sur le mur sous un angle plus faible ne le mesure pas (photo-03 d'app-004 : pan
# vu presque le long du mur, placé 1,4 m à côté, du mauvais côté de la fenêtre)
AU_DELA_M = 0.25  # l'autre côté de la fenêtre se regarde 25 cm au-delà de son bord, là où pendrait le second pan
FENETRE_VUE = (0.6, 1.5)  # la fenêtre lue sur une photo ne sert d'étalon que si sa largeur vaut 0,6 à 1,5 fois celle du plan


def repere_de_la_baie(ouverture: dict, logement: dict) -> dict | None:
    """Le repère d'une fenêtre du plan : son milieu sur la face INTÉRIEURE du mur (`centre`), la direction du mur du début vers
    la fin (`t`), la normale tournée vers la pièce (`n`), sa demi-largeur (`demi`), le milieu de sa hauteur (`z`). Mêmes règles
    que moteur.habillage.rideaux_du_plan et moteur.collisions.fenetres_habillees."""
    from moteur.sol_a_plat import piece_de

    m = next((m for m in logement.get("murs", []) if m["id"] == ouverture.get("mur")), None)
    if m is None:
        return None
    a, b = np.asarray(m["debut"], float), np.asarray(m["fin"], float)
    t = (b - a) / max(float(np.linalg.norm(b - a)), 1e-9)
    n = np.array([-t[1], t[0]])
    ep = float(m.get("epaisseur", 0.2))
    c = a + t * (float(ouverture["position"]) + float(ouverture["largeur"]) / 2)
    if piece_de(c + n * (ep / 2 + 0.3), logement.get("pieces", [])) is None:
        n = -n
    return {"id": ouverture["id"], "centre": c + n * ep / 2, "t": t, "n": n, "demi": float(ouverture["largeur"]) / 2,
            "z": float(ouverture.get("allege", 0.0) or 0.0) + float(ouverture.get("hauteur", 2.1)) / 2}


def _sur_le_mur(appareil, u: float, v: float, baie: dict, ecart: float = ECART_RIDEAUX_M) -> float | None:
    """Où le rayon du pixel (u, v) coupe la nappe des rideaux de la fenêtre (à `ecart` du mur ; 0 : la face du mur elle-même) :
    abscisse le long du mur (m), comptée depuis le milieu de la fenêtre, positive vers la fin du mur. None si le rayon ne va
    pas vers ce mur."""
    from moteur.photos_lues import rayon

    angle = math.radians(rayon(appareil, u, v)[0])
    d = np.array([math.cos(angle), math.sin(angle)])
    o = np.array([float(appareil[0]), float(appareil[1])]) - (baie["centre"] + baie["n"] * ecart)
    den = float(d @ baie["n"])
    if den > -RASANT:  # le rayon s'éloigne du mur, ou le longe de trop près : le point où il le coupe ne veut rien dire
        return None
    return float((o + d * (-(o @ baie["n"]) / den)) @ baie["t"])


def pan_d_une_vue(vue: dict, baie: dict) -> dict | None:
    """Ce qu'UNE vue (un rectangle « rideaux » d'une photo) dit du pan qu'elle montre, pour la fenêtre `baie` du plan :
    {"cote": "debut" | "fin" | None (le pan pend du côté du début ou de la fin du mur ; None : devant la fenêtre, ou on ne
    sait pas), "par": "image" | "mur" (comment on le sait), "s": (s0, s1) son étendue le long du mur, depuis le milieu de la
    fenêtre, "autre_cote_visible": la photo montre-t-elle aussi l'AUTRE côté de la fenêtre (là où pendrait un second pan) ?}.
    Deux mesures : DANS L'IMAGE, contre le rectangle de la fenêtre lu sur la même photo quand il touche le rideau (ne dépend
    pas de la place de l'appareil) ; sinon SUR LE MUR du plan, par les rayons des deux bords du rectangle.
    None : l'appareil n'est pas du côté de la pièce (rien à en dire)."""
    from moteur.camera_photo import projeter

    appareil, (largeur, _) = vue["appareil"], vue["image"]
    x0, y0, x1, y1 = vue["boite"]
    o = np.array([float(appareil[0]), float(appareil[1])])
    if float((o - baie["centre"]) @ baie["n"]) < 0.05:
        return None
    # vu de la pièce, ce qui est plus loin vers la FIN du mur paraît à gauche quand la normale est à gauche du mur
    a_droite = "debut" if float(baie["t"][0] * baie["n"][1] - baie["t"][1] * baie["n"][0]) > 0 else "fin"
    a_gauche = "fin" if a_droite == "debut" else "debut"
    marge = BORD_IMAGE * largeur
    s = [_sur_le_mur(appareil, u, (y0 + y1) / 2, baie) for u in (x0, x1)]
    etendue = tuple(sorted(s)) if None not in s else None
    # la LARGEUR du pan (22/11/2026) : l'écart de ses deux bords sur le mur ; un rectangle qui touche le bord de l'image est
    # un pan COUPÉ par le cadre : sa largeur n'est qu'un minimum
    commun = {"s": etendue, "largeur": None if etendue is None else etendue[1] - etendue[0],
              "coupe": x0 < marge or x1 > largeur - marge, "a_gauche": a_gauche, "a_droite": a_droite, "part": None}
    # --- dans l'image : la fenêtre lue sur la même photo, si elle touche le rideau (écart plus petit que sa largeur)
    voisines = []
    for fx0, fy0, fx1, fy1 in vue.get("baies_vues") or []:
        haut_commun = min(y1, fy1) - max(y0, fy0)
        ecart = max(0.0, fx0 - x1, x0 - fx1)
        if haut_commun >= 0.5 * min(y1 - y0, fy1 - fy0) and ecart <= fx1 - fx0:
            voisines.append((ecart, fx0, fx1, (fy0 + fy1) / 2))
    if voisines:
        _, fx0, fx1, fy = min(voisines)
        milieu, decale = (x0 + x1) / 2, PAN_COTE_MIN * (fx1 - fx0) / 2
        cote = a_gauche if milieu < (fx0 + fx1) / 2 - decale else a_droite if milieu > (fx0 + fx1) / 2 + decale else None
        if cote is None:
            return {**commun, "cote": None, "par": "image", "autre_cote_visible": False}
        # le pan mesuré CONTRE sa fenêtre, en PARTS de la largeur de celle-ci : les deux sont reportés sur le mur par le même
        # appareil, donc ni sa place (fausse de 30-50 cm quand la photo est calée seule) ni son recul ne comptent. Il faut la
        # fenêtre ENTIÈRE (ses deux bords dans le cadre, une largeur compatible avec celle du plan : le détecteur rend parfois
        # un seul vantail, photo-12 d'app-004)
        f = [_sur_le_mur(appareil, u, fy, baie, 0.0) for u in (fx0, fx1)]
        if etendue is not None and None not in f and fx0 >= marge and fx1 <= largeur - marge:
            f0, f1 = sorted(f)
            if FENETRE_VUE[0] * 2 * baie["demi"] <= f1 - f0 <= FENETRE_VUE[1] * 2 * baie["demi"]:
                devant = (f1 - etendue[0]) if cote == "fin" else (etendue[1] - f0)  # ce qui pend devant la fenêtre vue
                commun["part"] = {"largeur": commun["largeur"] / (f1 - f0),
                                  "recouvre": float(np.clip(devant, 0.0, commun["largeur"])) / (f1 - f0)}
        return {**commun, "cote": cote, "par": "image", "autre_cote_visible": (fx1 <= largeur - marge) if cote == a_gauche else (fx0 >= marge)}
    # --- sur le mur du plan
    if etendue is None:
        return {**commun, "cote": None, "par": "mur", "autre_cote_visible": False}
    milieu = (etendue[0] + etendue[1]) / 2
    cote = None if abs(milieu) < PAN_COTE_MIN * baie["demi"] else ("fin" if milieu > 0 else "debut")
    visible = False
    if cote is not None:  # l'autre côté de la fenêtre, là où pendrait un second pan, est-il dans le cadre ?
        autre = (baie["demi"] + AU_DELA_M) * (-1 if cote == "fin" else 1)
        p = baie["centre"] + baie["n"] * ECART_RIDEAUX_M + baie["t"] * autre
        u, _, profondeur = projeter([p[0], p[1], baie["z"]], appareil)
        visible = profondeur > 0.1 and marge <= u <= largeur - marge
    return {**commun, "cote": cote, "par": "mur", "autre_cote_visible": visible}


def pans_d_une_fenetre(vues: list[dict], baie: dict | None, portee: tuple[float, float] | None = None) -> list[dict] | None:
    """Les pans de rideaux épais d'une fenêtre d'après toutes ses vues : [{"cote": "debut"}] ou [{"cote": "fin"}] (UN seul
    pan, de ce côté), [{"cote": "debut"}, {"cote": "fin"}] (deux pans, VUS), ou None (pas de preuve : deux pans, comme avant).
    Depuis le 22/11/2026 chaque pan porte aussi ce que les photos en mesurent (largeurs_des_pans) : `largeur`, `recouvre`,
    `etat` ; `portee` : jusqu'où le mur est libre de part et d'autre de la baie.
    - deux rectangles de rideaux sur une même photo, l'un à côté de l'autre : ce sont les deux pans ;
    - un seul pan n'est retenu que si TOUTES les photos le voient du même côté et qu'une au moins montre aussi l'autre côté de
      la fenêtre, sans rideau (un second pan hors du cadre ne se devine pas)."""
    if baie is None:
        return None
    par_photo: dict = {}
    for v in vues:
        if not v.get("boite") or not v.get("appareil"):
            continue
        mesure = pan_d_une_vue(v, baie)
        if mesure is not None:
            mesure["dit"] = v.get("dit")
            v["pan"] = {**mesure, "fenetre": baie["id"]}  # gardé sur la vue : pour contrôler (pc/verification/sonde_largeur_pans.py)
            par_photo.setdefault(v["photo"], []).append((v, mesure))

    def combien() -> list[str] | None:
        for de_la_photo in par_photo.values():
            if len(de_la_photo) >= 2:
                # deux rectangles pour la même fenêtre sur une photo : s'ils ne se recouvrent pas, ce sont ses deux pans
                de_la_photo.sort(key=lambda vm: vm[0]["boite"][0])
                g, d = de_la_photo[0][0]["boite"], de_la_photo[-1][0]["boite"]
                if g[2] <= d[0] + 0.25 * (d[2] - d[0]):
                    de_la_photo[0][1]["cote"], de_la_photo[-1][1]["cote"] = de_la_photo[0][1]["a_gauche"], de_la_photo[-1][1]["a_droite"]
                    return ["debut", "fin"]
        # la mesure faite DANS L'IMAGE fait foi (elle ne dépend pas de la place de l'appareil, connue à 30-50 cm) ; celle faite
        # sur le mur du plan ne sert que si aucune photo ne montre le rideau contre sa fenêtre
        mesures = [m for de_la_photo in par_photo.values() for _, m in de_la_photo if m["cote"]]
        mesures = [m for m in mesures if m["par"] == "image"] or mesures
        vus = {m["cote"] for m in mesures}
        libres = {m["cote"] for m in mesures if m["autre_cote_visible"]}
        if len(vus) == 2:
            return ["debut", "fin"]
        if len(vus) == 1 and libres:
            return [next(iter(vus))]
        return None

    cotes = combien()
    mesures = largeurs_des_pans(par_photo, baie, portee)
    if cotes is None:
        if not mesures:
            return None  # ni preuve du nombre, ni mesure : deux pans de 45 cm, comme avant
        cotes = ["debut", "fin"]  # pas de preuve du nombre (deux pans, comme avant), mais une largeur vue : elle vaut pour les deux
    for cote, autre in (("debut", "fin"), ("fin", "debut")):
        if cote in cotes and cote not in mesures and autre in mesures:  # le pan mal vu est le pendant de celui qui est mesuré
            mesures[cote] = dict(mesures[autre])
    return [{"cote": c, **mesures.get(c, {})} for c in cotes]


TIRES = re.compile(r"\b(tires?|tirees?|fermes?|fermees?|deploye[es]*)\b")
OUVERTS = re.compile(r"\b(ouverts?|ouvertes?|retenus?|retenues?|embrasses?|attaches?|ramasses?)\b")


def largeurs_des_pans(par_photo: dict, baie: dict, portee: tuple[float, float] | None = None) -> dict[str, dict]:
    """La LARGEUR de chaque pan d'une fenêtre, la part qui pend devant la baie et son état (22/11/2026, étape b) :
    {"debut" | "fin": {"largeur", "recouvre", "etat"}} pour les côtés que les photos mesurent (moteur/pans_rideaux.py).
    - Un pan vu CONTRE sa fenêtre (la fenêtre entière lue sur la même photo) est mesuré en PARTS de cette fenêtre, puis rendu
      en mètres par la largeur de la baie du plan : ni la place de l'appareil ni l'échelle de la photo ne comptent, et le
      rideau garde dans le film la proportion qu'il a sur la photo. Cette mesure fait foi.
    - Sinon : la largeur mesurée sur le mur du plan par les rayons de ses deux bords (jamais une vue rasante). Deux pans vus
      ainsi sur une même photo : l'ensemble (du bord extérieur de l'un à celui de l'autre) est CENTRÉ sur la baie, comme une
      tringle l'est sur sa fenêtre ; cela retire le décalage de l'appareil. Un pan seul vu ainsi : sa largeur seulement.
    - Plusieurs photos : la médiane. Un pan coupé par le cadre de la photo ne donne qu'un minimum.
    - Un pan pend toujours jusqu'au bord de sa baie (+ 5 cm) ; il ne dépasse ni le coin de la pièce ni une autre ouverture
      (`portee` : moteur.largeur_baies.portee_libre) ; deux pans ne se croisent pas.
    - État : le mot de la lecture (« tirés », « ouverts », « retenus »…), sinon la mesure (moteur.pans_rideaux.etat)."""
    from moteur import pans_rideaux as pr

    demi = baie["demi"]
    parts, murs, minima, centres, dits = {}, {}, {}, {}, []
    for de_la_photo in par_photo.values():
        cotes_vus = {}
        for _, m in de_la_photo:
            if m.get("dit"):
                dits.append(_sans_accents(m["dit"]))
            if not m["cote"] or m["largeur"] is None:
                continue
            if m["coupe"]:
                minima.setdefault(m["cote"], []).append(m["largeur"])
            elif m["part"]:
                parts.setdefault(m["cote"], []).append(m["part"])
            else:
                murs.setdefault(m["cote"], []).append(m["largeur"])
                cotes_vus[m["cote"]] = m
        if len(cotes_vus) == 2:  # les deux pans sur le mur, sans fenêtre vue : l'ensemble centré sur la baie
            milieu = (cotes_vus["debut"]["s"][0] + cotes_vus["fin"]["s"][1]) / 2
            centres.setdefault("debut", []).append(demi + (cotes_vus["debut"]["s"][1] - milieu))
            centres.setdefault("fin", []).append(demi - (cotes_vus["fin"]["s"][0] - milieu))
    sortie = {}
    for cote in ("debut", "fin"):
        largeur = recouvre = None
        if parts.get(cote):
            largeur = float(np.median([p["largeur"] for p in parts[cote]])) * 2 * demi
            recouvre = float(np.median([p["recouvre"] for p in parts[cote]])) * 2 * demi
        elif murs.get(cote):
            largeur = float(np.median(murs[cote]))
            if centres.get(cote):
                recouvre = float(np.median(centres[cote]))
        au_moins = max(minima.get(cote) or [0.0])
        if au_moins > (largeur if largeur is not None else pr.PAN_RIDEAUX):  # un pan coupé par le cadre, vu plus large que le reste
            largeur = au_moins
        if largeur is None or largeur < pr.PAN_MIN:
            continue
        if recouvre is not None:
            recouvre = float(np.clip(recouvre, 0.0, 2 * demi))
            largeur = max(largeur, recouvre + pr.DEBORD_MIN)  # il pend jusqu'au bord de sa baie, et un peu au-delà
        if portee is not None:  # ni dans le mur d'à côté, ni devant une autre ouverture : le tissu se ramasse
            from moteur.largeur_baies import JAMBAGE
            libre = max(demi + pr.DEBORD_RIDEAUX, abs(portee[0 if cote == "debut" else 1]) + JAMBAGE)
            devant = recouvre if recouvre is not None else max(0.0, largeur - pr.DEBORD_RIDEAUX)
            largeur = max(pr.PAN_MIN, min(largeur, libre - demi + devant))
        sortie[cote] = {"largeur": round(largeur, 2), **({} if recouvre is None else {"recouvre": round(recouvre, 2)})}
    if len(sortie) == 2 and all("recouvre" in p for p in sortie.values()):  # deux pans ne se croisent pas
        trop = sortie["debut"]["recouvre"] + sortie["fin"]["recouvre"] - 2 * demi
        if trop > 0:
            for p in sortie.values():
                p["recouvre"] = round(p["recouvre"] - trop / 2, 2)
    dit = " ; ".join(dits)
    for p in sortie.values():
        p["etat"] = "tire" if TIRES.search(dit) else "ouvert" if OUVERTS.search(dit) else pr.etat(p, demi)
    return sortie


# ------------------------------------------------------------------ la tringle d'une fenêtre (23/11/2026, rideaux étape c)
# Avant : la tringle était toujours 12 cm sous le plafond et toujours en métal sombre. Les photos montrent sa vraie hauteur
# (app-004 : une vingtaine de centimètres sous le plafond ; ailleurs elle peut être juste au-dessus d'une fenêtre basse) et sa
# vraie couleur (app-004 : acier brossé gris clair). Sur une photo la tringle est un TRAIT FIN, presque horizontal, qui passe
# par le haut du tissu et continue à côté de lui, au-dessus de la fenêtre.
TRINGLE_TOL = 0.04  # le trait passe par le haut du rectangle du tissu, à 4 % de sa hauteur près (au moins 8 pixels)
TRINGLE_PENTES = 0.10  # … avec la pente d'une horizontale du mur vue par l'appareil, à 0,10 près
TRINGLE_ECART_PX = 5  # le mur se regarde 5 pixels au-dessus et au-dessous du trait (une tringle fait 2 à 5 pixels d'épaisseur)
TRINGLE_FORCE = 14.0  # écart de clarté (sur 255) entre le trait et le mur, tenu sur 60 % de sa longueur
TRINGLE_COLONNES = 30  # longueur minimale du trait (pixels)
TRINGLE_HAUTEUR_MIN = 1.6  # m : plus bas, ce n'est pas une tringle
TRINGLE_SOUS_PLAFOND = 0.03  # m : … et une tringle est au moins à 3 cm sous le plafond
# L'étalon de la couleur de la tringle : la couleur gardée = sa clarté contre le mur clair autour d'elle × ETALON_TRINGLE.
# RÉGLÉ DANS LE FILM le 23/11/2026 (pc/verification/juger_tringle_film.py, 8 vues d'app-001 et d'app-004, un seul réglage pour
# tous) : avec 0,85 (ce que renvoie un mur blanc) la tringle du film était trop claire contre son mur sur TOUTES les vues
# (0,73 pour 0,63 sur les photos : la pellicule du film et le reflet du métal l'éclaircissent) ; 0,60 la remet à la clarté vue.
ETALON_TRINGLE = 0.60
MUR_CLAIR = 150  # clarté (sur 255) au-dessus de laquelle le mur autour de la tringle sert d'étalon
TRINGLE_DITE = re.compile(r"\btringles?\b(.*)")


def pente_d_une_horizontale(cam, plan: dict, logement: dict, u0: float, u1: float, v: float) -> float:
    """La pente, dans l'image, d'une ligne HORIZONTALE du mur que l'appareil voit entre les colonnes u0 et u1 à la ligne v
    (pixels descendus par pixel vers la droite). 0 si le mur n'est pas trouvé."""
    from moteur.camera_photo import projeter
    from moteur.photos_lues import premier_mur, rayon

    origine = np.array([float(cam[0]), float(cam[1])])
    points = []
    for u in (u0, u1):
        angle, pente = rayon(cam, u, v)
        distance = premier_mur(plan, origine, angle, pieces=logement.get("pieces"))[0]
        if not math.isfinite(distance) or distance < 0.3:
            return 0.0
        points.append((origine + distance * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))]),
                       float(cam[2]) + pente * distance))
    (pa, za), (pb, _) = points
    ua, va, da = projeter([pa[0], pa[1], za], cam)
    ub, vb, db = projeter([pb[0], pb[1], za], cam)
    if da <= 0.1 or db <= 0.1 or abs(ub - ua) < 2:
        return 0.0
    return float(np.clip((vb - va) / (ub - ua), -0.8, 0.8))


def trait_de_la_tringle(rgb: np.ndarray, boite, pente: float = 0.0, dessus: bool = False) -> dict | None:
    """La tringle cherchée dans l'image : un trait fin, plus sombre (ou plus clair) que le mur au-dessus ET au-dessous de lui,
    qui passe par le haut du rectangle du tissu avec la pente d'une horizontale du mur, à gauche ou à droite du tissu (et
    au-dessus de lui pour un voilage, `dessus`). Rend {"a", "b" : ses deux bouts (pixels), "force" : son écart de clarté avec
    le mur, "couleur" : sa couleur, "mur" : celle du mur autour, "points" : quelques-uns de ses pixels} ; None sans trait net."""
    H, W = rgb.shape[:2]
    gris = rgb[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    x0, y0, x1, y1 = (float(c) for c in boite)
    xc, d = (x0 + x1) / 2, TRINGLE_ECART_PX
    tol = max(8, int(round(TRINGLE_TOL * (y1 - y0))))
    portee = max(60, int(round(1.5 * (x1 - x0))))
    zones = {"gauche": np.arange(max(0, int(x0) - portee), max(0, int(x0) - 2)),
             "droite": np.arange(min(W, int(x1) + 3), min(W, int(x1) + portee))}
    if dessus:
        zones["dessus"] = np.arange(max(0, int(x0 + 0.1 * (x1 - x0))), min(W, int(x1 - 0.1 * (x1 - x0))))
    departs = np.arange(int(y0) - tol, int(y0) + tol + 1, dtype=np.float32)[:, None]
    meilleur = None
    for nom, xs in zones.items():
        if len(xs) < TRINGLE_COLONNES:
            continue
        for p in pente + np.linspace(-TRINGLE_PENTES, TRINGLE_PENTES, 11):
            ys = np.rint(departs + p * (xs[None, :] - xc)).astype(int)
            dedans = (ys >= d + 2).all(axis=1) & (ys < H - d - 2).all(axis=1)
            if not dedans.any():
                continue
            ys = ys[dedans]
            xx = np.broadcast_to(xs[None, :], ys.shape)
            trois = np.stack([gris[ys - 1, xx], gris[ys, xx], gris[ys + 1, xx]])
            dehors = np.stack([gris[ys - d, xx], gris[ys + d, xx]])
            for signe, ecart in (("sombre", dehors.min(axis=0) - trois.min(axis=0)), ("clair", trois.max(axis=0) - dehors.max(axis=0))):
                force = np.percentile(ecart, 40, axis=1)  # tenu sur 60 % de la longueur : un trait, pas une tache
                # … et, entre deux droites qui tiennent aussi bien, celle qui suit le trait d'un bout à l'autre (la moyenne)
                rang = force + np.clip(ecart, 0.0, None).mean(axis=1)
                k = int(np.argmax(np.where(force >= TRINGLE_FORCE, rang, -1.0)))
                if force[k] >= TRINGLE_FORCE and (meilleur is None or rang[k] > meilleur[0]):
                    meilleur = (float(rang[k]), signe, xs, ys[k], ecart[k], float(force[k]))
    if meilleur is None:
        return None
    _, signe, xs, ys, ecart, force = meilleur
    net = ecart >= 0.6 * force
    x, y = xs[net], ys[net]
    lignes = np.stack([y - 1, y, y + 1])
    choix = (np.argmin if signe == "sombre" else np.argmax)(gris[lignes, x[None, :]], axis=0)
    couleur = np.median(rgb[lignes[choix, np.arange(len(x))], x, :3].astype(np.float32), axis=0)
    # le mur : le plus clair du dessus et du dessous (dessous, ce peut être le cadre de la fenêtre ou le tissu)
    haut, bas = rgb[y - d - 1, x, :3].astype(np.float32), rgb[y + d + 1, x, :3].astype(np.float32)
    mur = np.median(np.where((gris[y - d - 1, x] >= gris[y + d + 1, x])[:, None], haut, bas), axis=0)
    pas = max(1, len(x) // 12)
    return {"a": [float(xs[0]), float(ys[0])], "b": [float(xs[-1]), float(ys[-1])], "force": force, "signe": signe,
            "couleur": [int(c) for c in couleur], "mur": [int(c) for c in mur],
            "points": [[float(a), float(b)] for a, b in zip(x[::pas], y[::pas])]}


def _du_relief(repere: dict | None, points, largeur: int, hauteur: int) -> float | None:
    """La hauteur au-dessus du sol (m) de ces pixels de la photo, dans le relief remis entre le sol et le plafond de la pièce
    (moteur.caler_photos.repere) : la médiane des points mesurés ; None s'il y en a moins de trois."""
    if repere is None:
        return None
    Hm, Wm = repere["M"].shape
    valeurs = []
    for u, v in points:
        i, j = int(v * Hm / hauteur), int(u * Wm / largeur)
        if 0 <= i < Hm and 0 <= j < Wm and repere["M"][i, j] and np.isfinite(repere["h"][i, j]):
            valeurs.append(float(repere["h"][i, j]))
    return float(np.median(valeurs)) if len(valeurs) >= 3 else None


def tringle_d_une_vue(rgb: np.ndarray | None, boite, repere: dict | None, voilage: bool = False, pente: float = 0.0) -> dict | None:
    """Ce qu'UN rectangle de rideaux ou de voilage dit de sa tringle : {"haut" : la hauteur du haut du tissu dans le relief de
    la photo (m), "trait" : la tringle trouvée dans l'image (trait_de_la_tringle) ou None, "hauteur" : la hauteur de ce trait
    dans le relief (m)}. None quand le haut du tissu est coupé par le cadre de la photo (ou sans image)."""
    if rgb is None:
        return None
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = (float(c) for c in boite)
    if y0 < BORD_IMAGE * H:
        return None
    ligne = y0 + 0.02 * (y1 - y0)
    haut = _du_relief(repere, [(x0 + f * (x1 - x0), ligne) for f in np.linspace(0.15, 0.85, 15)], W, H)
    trait = trait_de_la_tringle(rgb, boite, pente, dessus=voilage)
    # le relief d'un trait de 3 pixels est celui du MUR qui le porte : il se lit juste au-dessus de lui
    hauteur = _du_relief(repere, [(u, v - 2) for u, v in trait["points"]], W, H) if trait else None
    return {"haut": haut, "trait": trait, "hauteur": hauteur}


def _a_blanc_de_mur(couleur, mur) -> list[int]:
    """La couleur de la tringle ramenée à ce qu'elle serait à côté d'un mur blanc bien exposé : le mur clair autour d'elle
    sert d'étalon (ETALON_TRINGLE, réglé dans le film). Un mur sombre ou coloré n'étalonne rien : couleur telle quelle."""
    lin = lambda c: ((np.asarray(c, float) / 255 + 0.055) / 1.055) ** 2.4
    srgb = lambda v: 255 * (1.055 * np.clip(v, 0, 1) ** (1 / 2.4) - 0.055)
    clarte = float(np.asarray(mur, float) @ [0.299, 0.587, 0.114])
    if clarte < MUR_CLAIR:
        return [int(c) for c in couleur]
    return [int(round(float(c))) for c in np.clip(srgb(lin(couleur) / max(float(lin(mur).mean()), 1e-3) * ETALON_TRINGLE), 0, 255)]


def tringle_d_une_fenetre(vues: list[dict], hsp: float) -> dict | None:
    """La tringle d'une fenêtre d'après toutes les vues de ses rideaux et de son voilage : {"hauteur" (m au-dessus du sol),
    "couleur" (sRGB)}, chaque champ seulement s'il est mesuré ; None sans aucune mesure (la tringle d'avant : 12 cm sous le
    plafond, métal sombre).
    - HAUTEUR : celle du trait de la tringle trouvé sur chaque photo, lue dans le relief de la photo (qui est remis entre le
      sol et le plafond de la pièce : elle ne dépend pas de la place de l'appareil) ; sans trait : le haut du tissu. Médiane.
    - COULEUR : celle du trait, étalonnée par le mur blanc autour de lui ; médiane. Le mot de la lecture (« tringle noire »)
      fait foi quand il existe."""
    traits, tissus, couleurs, dite = [], [], [], None
    for v in vues:
        mots = TRINGLE_DITE.search(_sans_accents(v.get("dit") or ""))
        if mots and couleur_dite(mots.group(1)):
            dite = couleur_dite(mots.group(1))
        t = v.get("tringle_vue")
        if not t:
            continue
        mesure = {"haut": t.get("haut"), "hauteur": t.get("hauteur"), "trait": t.get("trait")}
        # une tringle lue AU-DESSUS du plafond : le relief est faux à cet endroit (mur lointain, étalé), sa hauteur ne dit rien
        # (jusqu'au 25/11/2026 : plafond + 15 cm, puis rabattue sous le plafond ; avec le vrai plafond du séjour d'app-001, deux
        # tringles lues à 3,05 et 3,10 m sous un plafond de 3,00 m entraient ainsi à 2,97 m, plus haut que la tringle d'avant)
        plausible = lambda h: h is not None and TRINGLE_HAUTEUR_MIN <= h <= hsp - TRINGLE_SOUS_PLAFOND
        # un trait dont la hauteur n'est pas celle d'une tringle (une corniche, le bord d'une poutre) ne dit pas sa couleur
        if t.get("trait") and plausible(t.get("hauteur")):
            mesure["couleur"] = _a_blanc_de_mur(t["trait"]["couleur"], t["trait"]["mur"])
            mesure["mur"] = t["trait"]["mur"]
            mesure["clarte"] = float(np.asarray(t["trait"]["couleur"], float) @ [0.299, 0.587, 0.114]) / max(
                1.0, float(np.asarray(t["trait"]["mur"], float) @ [0.299, 0.587, 0.114]))
            couleurs.append(mesure["couleur"])
        v["tringle"] = mesure  # gardé sur la vue : pour contrôler (pc/verification/sonde_tringle.py)
        if plausible(t.get("hauteur")):
            traits.append(t["hauteur"])
        if plausible(t.get("haut")):
            tissus.append(t["haut"])
    sortie = {}
    hauteurs = traits or tissus
    if hauteurs:
        sortie["hauteur"] = round(float(np.clip(np.median(hauteurs), TRINGLE_HAUTEUR_MIN, hsp - TRINGLE_SOUS_PLAFOND)), 2)
    if dite or couleurs:
        sortie["couleur"] = [int(c) for c in (dite or np.median(np.array(couleurs), axis=0))]
    return sortie or None


def appliquer(logement: dict, resultat: dict) -> dict:
    """Le logement avec les équipements posés (resultat de poser) : meubles ajoutés, rideaux mis aux fenêtres qui n'en ont
    pas déjà de choisis, murets et passe-plats ajoutés, colonnes de cuisine lues marquées « sans four » (leur four est celui
    qui est lu, à sa place, ou aucun)."""
    lg = {**logement, "meubles": [dict(m) for m in logement.get("meubles", [])] + resultat["meubles"],
          "ouvertures": [dict(o) for o in logement.get("ouvertures", [])]}
    for m in lg["meubles"]:
        if m["id"] in resultat.get("colonnes", ()) and "sans four" not in str(m.get("description") or ""):
            m["description"] = ((m.get("description") or "") + " (sans four)").strip()
    for o in lg["ouvertures"]:
        r = resultat["rideaux"].get(o["id"])
        if r is not None and (o.get("rideaux") is None or o["rideaux"].get("statut") == "ajoute"):
            o["rideaux"] = r
    if resultat.get("murs"):
        lg["murs"] = [*logement.get("murs", []), *resultat["murs"]]
    if resultat["passe_plats"]:
        lg["passe_plats"] = [*logement.get("passe_plats", []), *resultat["passe_plats"]]
    return lg
