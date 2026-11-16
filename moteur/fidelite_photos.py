r"""LA FIDÉLITÉ DE LA MAQUETTE AUX PHOTOS, objet par objet : ce que chaque photo montre, la maquette l'a-t-elle au même endroit ?

Pourquoi (NT, 16/11/2026 : « c'est le modèle 3D, la priorité […] j'ai l'impression qu'on travaille que sur ce logement ») : il
faut un juge de la MAQUETTE, le même pour tous les logements, rapide (pas de rendu), et assez fin pour voir une fenêtre trop
petite ou un meuble en trop. Une première note « la photo et le rendu se ressemblent-ils » (moteur/ressemblance.py) s'est
révélée trop grossière : 46/100 pour trois versions très différentes de la maquette d'app-004.

Méthode, pour chaque photo placée d'un logement :
1. un détecteur (OWLv2, déjà dans Atelya) repère sur la photo les objets d'un vocabulaire large (VOCABULAIRE) : ce qu'Atelya
   sait poser (lit, canapé, chaise, table, rangement, tapis, baie, porte…) ET ce qu'il ne pose pas encore (cheminée, télévision,
   luminaire, rideaux, radiateur, baignoire, WC, lavabo, cuisine, électroménager…) ;
2. chaque élément de la maquette (meubles, portes, fenêtres) est projeté dans la photo avec la place de l'appareil : s'il est
   devant l'appareil, dans le cadre et pas derrière un mur, il donne un rectangle ;
3. les rectangles de la photo et ceux de la maquette sont mis par paires, sorte par sorte (recouvrement des rectangles) :
   - « présent » : la maquette a cet objet à peu près là (recouvrement ≥ PRESENT) ;
   - « bien placé » : au même endroit et à la même taille (recouvrement ≥ BIEN_PLACE) ;
   - « manque » : vu sur la photo, rien dans la maquette ; « en trop » : dans la maquette, rien sur la photo.
Notes (les gros objets comptent plus : poids = racine de la surface du rectangle) :
   couverture = part de ce que les photos montrent que la maquette a ; justesse = part de ce que la maquette montre que les
   photos confirment ; fidélité = moyenne harmonique des deux, sur 100.

Limites à connaître : le détecteur n'est pas la vérité (il rate des objets, en invente quelques-uns) ; il est le même pour toutes
les versions de la maquette, donc la COMPARAISON entre deux versions est juste même si la note absolue est sévère ou indulgente.
La place de l'appareil compte : une photo mal placée fait baisser la note d'une maquette juste (c'est aussi un défaut du produit).
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
PRESENT, BIEN_PLACE = 0.15, 0.4  # recouvrement des rectangles (surface commune / surface réunie)
SURFACE_MIN = 0.0015  # part de la photo en dessous de laquelle un rectangle est ignoré
DANS_LE_CADRE_MIN = 0.3  # part du rectangle projeté qui doit tomber dans la photo

# phrase donnée au détecteur → sorte du banc (None : repéré pour ne pas être pris pour autre chose, puis ignoré)
VOCABULAIRE: dict[str, str | None] = {
    "a bed": "lit", "a bed with a duvet": "lit", "a bunk bed": "lit",
    "a sofa": "canape", "a couch": "canape",
    "an armchair": "fauteuil",
    "a chair": "chaise", "a stool": "chaise", "an office chair": "chaise",
    "a dining table": "table", "a table": "table", "a coffee table": "table", "a desk": "table", "a side table": "table",
    "a chest of drawers": "rangement", "a cabinet": "rangement", "a bookshelf": "rangement", "a shelf": "rangement",
    "a tv stand": "rangement", "a nightstand": "rangement", "a bench": "rangement", "a wardrobe": "rangement",
    "a sideboard": "rangement",
    "a rug": "tapis", "a carpet": "tapis",
    "a floor lamp": "lampe", "a table lamp": "lampe",
    "a potted plant": "plante",
    "a window": "baie", "a door": "porte",
    "a fireplace": "cheminee",
    "a television": "television",
    "a ceiling light": "luminaire", "a pendant lamp": "luminaire", "a chandelier": "luminaire",
    "curtains": "rideaux", "a curtain": "rideaux",
    "a radiator": "radiateur",
    "a painting": "tableau", "a mirror": "miroir",
    "a bathtub": "baignoire", "a shower": "douche", "a toilet": "wc", "a sink": "lavabo", "a washbasin": "lavabo",
    "kitchen cabinets": "cuisine", "a kitchen counter": "cuisine",
    "an oven": "electromenager", "a refrigerator": "electromenager", "a stove": "electromenager",
    "a washing machine": "electromenager", "a microwave oven": "electromenager",
    "a pillow": None, "a laundry basket": None,
}
# note minimale du détecteur par sorte (celles des meubles sont celles du repérage en service, moteur/reperer_meubles.SEUILS_OWL)
SEUILS = {"canape": 0.5, "fauteuil": 0.5, "chaise": 0.3, "table": 0.3, "lit": 0.4, "rangement": 0.25, "tapis": 0.5,
          "lampe": 0.3, "plante": 0.5}
SEUIL_DEFAUT = 0.3
# sorte du banc de chaque catégorie de meuble de la maquette (None : trop petit pour être jugé)
SORTE_DU_MEUBLE = {
    "canape": "canape", "fauteuil": "fauteuil", "chaise": "chaise", "tabouret_haut": "chaise", "chaise_de_bureau": "chaise",
    "table_basse": "table", "table_d_appoint": "table", "table": "table", "bureau": "table",
    "lit": "lit", "lit_superpose": "lit",
    "table_de_chevet": "rangement", "commode": "rangement", "rangement": "rangement", "etagere_cubes": "rangement",
    "bibliotheque": "rangement", "meuble_tv": "rangement", "banc": "rangement", "caisson": "rangement", "placard": "rangement",
    "tapis": "tapis", "lampadaire": "lampe", "lampe": "lampe", "suspension": "luminaire", "tableau": "tableau",
    "miroir": "miroir", "plante": "plante", "television": "television",
    "meuble_cuisine_bas": "cuisine", "meuble_cuisine_haut": "cuisine", "colonne_cuisine": "cuisine", "ilot": "cuisine",
    "horloge": None, "coussin": None, "vase": None,
}
SORTES_SANS_MAQUETTE = ("cheminee", "rideaux", "radiateur", "baignoire", "douche", "wc", "lavabo", "electromenager")


# ---------------------------------------------------------------- les rectangles
def recouvrement(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    commun = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    reunion = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - commun
    return commun / reunion if reunion > 0 else 0.0


def part_dedans(a, b) -> float:
    """La part du rectangle a qui est dans le rectangle b."""
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    surface = (a[2] - a[0]) * (a[3] - a[1])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0) / surface if surface > 0 else 0.0


def famille(sorte: str) -> str:
    """Les sortes qui peuvent former une paire : une haute fenêtre jusqu'au sol est souvent vue « porte » par le détecteur."""
    return "ouverture" if sorte in ("baie", "porte") else sorte


def poids(boite, largeur: int, hauteur: int) -> float:
    return math.sqrt(max(0.0, (boite[2] - boite[0]) * (boite[3] - boite[1])) / (largeur * hauteur))


# ---------------------------------------------------------------- 1. ce que la photo montre
def objets_de_la_photo(detections: list[dict], largeur: int, hauteur: int) -> list[dict]:
    """Les objets retenus sur une photo d'après les rectangles bruts du détecteur ({"nom", "note", "boite"}) : sorte du banc,
    note suffisante, assez grands, et un seul rectangle par objet (moteur.owlv2.objets_distincts)."""
    from moteur.owlv2 import objets_distincts

    return objets_distincts(detections, VOCABULAIRE, SEUILS, SEUIL_DEFAUT, SURFACE_MIN * largeur * hauteur)


# ---------------------------------------------------------------- 2. ce que la maquette montre, vue de la même place
def _points_du_meuble(m: dict) -> np.ndarray:
    l, p, h = (float(v) for v in m["dimensions"])
    a = math.radians(float(m.get("face", 0.0)))
    f, t = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    z0 = float(m.get("altitude", 0.0))
    pts = []
    for u in (-0.5, -0.25, 0.0, 0.25, 0.5):
        for v in (-0.5, -0.25, 0.0, 0.25, 0.5):
            xy = np.asarray(m["position"], float) + u * l * t + v * p * f
            pts += [(xy[0], xy[1], z) for z in (z0, z0 + h / 2, z0 + h)]
    return np.array(pts)


def elements_de_la_maquette(logement: dict) -> list[dict]:
    """Ce que la maquette contient et qui se juge sur une photo : meubles et ouvertures, avec des points sur leur volume."""
    murs = {m["id"]: m for m in logement.get("murs", [])}
    sortie = []
    for m in logement.get("meubles", []):
        sorte = SORTE_DU_MEUBLE.get(m["categorie"])
        if sorte is None:
            continue
        sortie.append({"id": m["id"], "sorte": sorte, "categorie": m["categorie"], "points": _points_du_meuble(m),
                       "centre": (float(m["position"][0]), float(m["position"][1])), "mur": None})
    for o in logement.get("ouvertures", []):
        mur = murs.get(o.get("mur"))
        if mur is None:
            continue
        a, b = np.asarray(mur["debut"], float), np.asarray(mur["fin"], float)
        L = float(np.linalg.norm(b - a))
        if L < 1e-6:
            continue
        t = (b - a) / L
        z0, z1 = float(o.get("allege", 0.0) or 0.0), float(o.get("allege", 0.0) or 0.0) + float(o["hauteur"])
        pts = [(*(a + t * (float(o["position"]) + s * float(o["largeur"]))), z) for s in (0, 0.25, 0.5, 0.75, 1)
               for z in np.linspace(z0, z1, 5)]
        milieu = a + t * (float(o["position"]) + float(o["largeur"]) / 2)
        sortie.append({"id": o["id"], "sorte": "porte" if o["type"] == "porte" else "baie", "categorie": o["type"],
                       "points": np.array(pts), "centre": (float(milieu[0]), float(milieu[1])), "mur": o["mur"]})
    return sortie


def _murs_et_trous(logement: dict) -> list[tuple]:
    """Chaque mur de toute hauteur : (id, début, fin, [intervalles de ses ouvertures le long du mur, en mètres])."""
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    trous: dict[str, list] = {}
    for o in logement.get("ouvertures", []):
        trous.setdefault(o.get("mur"), []).append((float(o["position"]) - 0.05, float(o["position"]) + float(o["largeur"]) + 0.05))
    return [(m["id"], np.asarray(m["debut"], float), np.asarray(m["fin"], float), trous.get(m["id"], []))
            for m in logement.get("murs", []) if float(m.get("hauteur") or hsp) >= 0.8 * hsp]


def cache_par_un_mur(appareil, point, murs: list[tuple], sauf: str | None = None) -> bool:
    """Un mur plein passe-t-il entre l'appareil et le point (vus de dessus) ? Une porte ou une baie laisse voir à travers."""
    c, p = np.asarray(appareil, float), np.asarray(point, float)
    d = p - c
    for ident, a, b, trous in murs:
        if ident == sauf:
            continue
        e = b - a
        den = d[0] * e[1] - d[1] * e[0]
        if abs(den) < 1e-9:
            continue
        t = ((a[0] - c[0]) * e[1] - (a[1] - c[1]) * e[0]) / den  # le long du regard (0 = appareil, 1 = point)
        s = ((a[0] - c[0]) * d[1] - (a[1] - c[1]) * d[0]) / den  # le long du mur (0 à 1)
        if 0.02 < t < 0.97 and 0.0 <= s <= 1.0:
            place = s * float(np.linalg.norm(e))
            if not any(s0 <= place <= s1 for s0, s1 in trous):
                return True
    return False


def rectangle_dans_la_photo(points: np.ndarray, cam, largeur: int, hauteur: int) -> list[float] | None:
    """Le rectangle qu'occupe sur la photo un volume de la maquette (None s'il est derrière l'appareil ou hors du cadre)."""
    from moteur.camera_photo import axes

    x, y, z, cap, tangage, f, u0, v0 = (float(c) for c in cam)
    vue, droite, haut = axes(cap, tangage)
    r = points - np.array([x, y, z])
    prof = r @ vue
    devant = prof > 0.2
    if devant.mean() < 0.4:
        return None
    u = u0 + f * (r[devant] @ droite) / prof[devant]
    v = v0 - f * (r[devant] @ haut) / prof[devant]
    b = [float(u.min()), float(v.min()), float(u.max()), float(v.max())]
    surface = (b[2] - b[0]) * (b[3] - b[1])
    c = [max(0.0, b[0]), max(0.0, b[1]), min(float(largeur), b[2]), min(float(hauteur), b[3])]
    dans = max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])
    if surface <= 0 or dans / surface < DANS_LE_CADRE_MIN or dans < SURFACE_MIN * largeur * hauteur:
        return None
    return c


def objets_de_la_maquette(logement: dict, cam, largeur: int, hauteur: int, elements=None, murs=None) -> list[dict]:
    """Ce que la maquette montre depuis la place d'une photo : {id, sorte, boite}."""
    elements = elements_de_la_maquette(logement) if elements is None else elements
    murs = _murs_et_trous(logement) if murs is None else murs
    sortie = []
    for e in elements:
        if cache_par_un_mur(cam[:2], e["centre"], murs, sauf=e["mur"]):
            continue
        boite = rectangle_dans_la_photo(e["points"], cam, largeur, hauteur)
        if boite is not None:
            sortie.append({"id": e["id"], "sorte": e["sorte"], "categorie": e["categorie"], "boite": boite})
    return sortie


# ---------------------------------------------------------------- 3. les paires, et les notes
def apparier(photo: list[dict], maquette: list[dict]) -> None:
    """Met par paires les objets de même sorte qui se recouvrent le plus (un objet ne sert qu'une fois). Écrit dans chaque
    objet « paire » (l'autre objet, ou None) et « recouvrement »."""
    for o in (*photo, *maquette):
        o["paire"], o["recouvrement"] = None, 0.0
    candidats = sorted(((recouvrement(p["boite"], m["boite"]), i, j) for i, p in enumerate(photo) for j, m in enumerate(maquette)
                        if famille(p["sorte"]) == famille(m["sorte"])), reverse=True)
    for r, i, j in candidats:
        if r < PRESENT:
            break
        if photo[i]["paire"] is None and maquette[j]["paire"] is None:
            photo[i]["paire"], maquette[j]["paire"] = maquette[j]["id"], f"photo:{i}"
            photo[i]["recouvrement"] = maquette[j]["recouvrement"] = round(r, 3)


def compter(photos: list[dict]) -> dict:
    """Le bilan d'une liste de photos jugées ([{"largeur", "hauteur", "photo": [...], "maquette": [...]}], après apparier)."""
    par_sorte: dict[str, dict] = {}
    vu = vu_ok = vu_bien = montre = montre_ok = 0.0
    for ph in photos:
        w, h = ph["largeur"], ph["hauteur"]
        for o in ph["photo"]:
            s = par_sorte.setdefault(o["sorte"], {"vus": 0, "presents": 0, "bien_places": 0, "dans_la_maquette": 0, "en_trop": 0, "poids_manque": 0.0})
            p = poids(o["boite"], w, h)
            s["vus"] += 1
            vu += p
            if o["paire"] is not None:
                s["presents"] += 1
                vu_ok += p
                if o["recouvrement"] >= BIEN_PLACE:
                    s["bien_places"] += 1
                    vu_bien += p
            else:
                s["poids_manque"] += p
        for o in ph["maquette"]:
            s = par_sorte.setdefault(o["sorte"], {"vus": 0, "presents": 0, "bien_places": 0, "dans_la_maquette": 0, "en_trop": 0, "poids_manque": 0.0})
            p = poids(o["boite"], w, h)
            s["dans_la_maquette"] += 1
            if o["paire"] is not None:
                montre += p
                montre_ok += p
            else:
                s["en_trop"] += 1
                # une porte ou une fenêtre du plan que le détecteur ne voit pas sur la photo n'est pas « en trop » : le plan fait
                # foi pour les ouvertures (le détecteur manque souvent les fenêtres derrière des voilages) ; elle ne pèse donc
                # pas sur la justesse (elle reste comptée dans la colonne « en trop », pour information)
                if famille(o["sorte"]) != "ouverture":
                    montre += p
    couverture = vu_ok / vu if vu else 0.0
    justesse = montre_ok / montre if montre else 0.0
    fidelite = 2 * couverture * justesse / (couverture + justesse) if couverture + justesse else 0.0
    for s in par_sorte.values():
        s["poids_manque"] = round(s["poids_manque"], 3)
    return {"photos": len(photos), "couverture": round(couverture, 4), "bien_place": round(vu_bien / vu if vu else 0.0, 4),
            "justesse": round(justesse, 4), "fidelite": round(100 * fidelite, 1), "par_sorte": dict(sorted(par_sorte.items()))}


def juger_une_photo(detections: list[dict], logement: dict, cam, largeur: int, hauteur: int, elements=None, murs=None) -> dict:
    photo = objets_de_la_photo(detections, largeur, hauteur)
    maquette = objets_de_la_maquette(logement, cam, largeur, hauteur, elements, murs)
    apparier(photo, maquette)
    return {"largeur": largeur, "hauteur": hauteur, "photo": photo, "maquette": maquette}
