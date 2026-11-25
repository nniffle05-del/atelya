r"""LA LARGEUR D'UNE FENÊTRE, LUE SUR LES PHOTOS (étape F1, 20/11/2026).

Pourquoi (NT, 20/11/2026, devant le film : « si on regarde bien, la fenêtre est aussi longue que le mur ») : un plan d'annonce
dessine souvent ses fenêtres comme de petits symboles. Le coin repas d'app-001 : 1,21 m sur le plan dans un pan de mur de
2,10 m, alors que la photo montre une baie qui tient tout le mur. Le film montrait une petite fenêtre et un voilage étroit.
DÉCISION DE NT (20/11/2026, accord écrit) : les photos peuvent ÉLARGIR une fenêtre du plan quand elles le contredisent
NETTEMENT, et c'est montré pour confirmation (entorse voulue à « le plan fait foi », comme « fenêtre → porte-fenêtre » et le
passe-plat).

Comment :
1. CE QU'UNE PHOTO DIT (`mesures_d_une_photo`). Deux témoins, reportés sur le mur du plan par les rayons de leurs deux bords
   (jamais une vue rasante) :
   - un rectangle « fenêtre » ou « porte-fenêtre » : c'est la baie elle-même ;
   - un VOILAGE, seulement quand la lecture de la photo dit qu'on voit la baie derrière lui « sur toute la largeur »
     (un voilage peut aussi courir d'un mur à l'autre devant une petite fenêtre : sans cette mention il ne prouve rien) :
     la baie est le voilage moins ce qu'il déborde de chaque côté (MARGE_VOILAGE).
   Un bord coupé par le cadre de la photo, ou caché par un meuble, n'est pas « franc » : la baie va au moins jusque-là.
2. LA RÈGLE (`elargir`). Une baie n'est élargie que si une photo la voit plus large que le plan d'au moins ECART_MIN ET de
   RAPPORT_MIN fois sa largeur (la mesure vaut 30 à 50 cm : la place de l'appareil est connue à ce près), et si aucune photo
   qui la voit ENTIÈRE (ses deux bords francs) ne la voit comme le plan : dans ce cas rien ne change, c'est un doute. La
   baie est bornée par ce que le mur laisse libre (`portee_libre` : ni coin de la pièce, ni autre ouverture, et dehors de
   l'autre côté). Elle n'est JAMAIS rétrécie. Statut « estime », source « photos », et la largeur du plan est gardée dans le
   compte rendu (ce qui a changé) pour l'écran de vérification. Une baie mesurée sur une cote (statut « mesure ») ou qu'une
   personne a posée ou corrigée à l'écran n'est jamais touchée : c'est seulement un doute.

Mesuré le 20/11/2026 sur les 22 baies d'app-001, app-002 et app-004 (pc/verification/sonde_largeur_fenetres.py) : une seule
est nettement contredite (le coin repas d'app-001) ; toutes les autres sont vues à la largeur du plan à 30 cm près, ou plus
étroites. Écarté : la couche d'Atelya qui reconnaît une fenêtre à son aspect (moteur.caler_photos.Fenetres) : elle déborde
d'un mètre sur le mur blanc d'à côté (cuisine d'app-001 : 2,3 m vus pour 1,25 m).
"""
from __future__ import annotations

import copy
import math

import numpy as np

VERSION = "0.1.0"
ECART_MIN = 0.5  # m : la photo doit voir la baie plus large que le plan d'au moins 50 cm…
RAPPORT_MIN = 1.3  # … et d'au moins 1,3 fois sa largeur
GAIN_MIN = 0.3  # m : une fois bornée par le mur libre, la baie doit gagner au moins 30 cm (sinon rien ne change)
ACCORD_M = 0.25  # m : une photo qui voit la baie entière à moins de 25 cm de la largeur du plan dit « comme le plan »
DISTANCE_MAX = 8.0  # m : au-delà, la baie est trop loin pour être mesurée
MARGE_VOILAGE = 0.15  # m : ce qu'un voilage déborde de sa baie, de chaque côté
JAMBAGE = 0.10  # m : ce qui reste de mur entre le bord d'une baie et le coin de la pièce
ENTRE_BAIES = 0.25  # m : ce qui reste de mur entre deux ouvertures d'un même mur
BORD_IMAGE = 0.04  # un bord à moins de 4 % de la largeur de l'image de son cadre est « coupé »
VOIT_LE_MUR_M = 0.6  # le mur de la baie doit être le premier que le regard rencontre, à 60 cm près
BAIES = ("fenetre", "porte_fenetre")


def _sans_accents(texte: str) -> str:
    from moteur.equipements import _sans_accents as sa

    return sa(texte)


def temoin(objet: dict) -> str | None:
    """Ce qu'un objet lu sur une photo peut dire de la largeur d'une baie : « fenetre » (la baie elle-même), « voilage »
    (un voilage derrière lequel la lecture voit la baie sur toute la largeur), ou None (rien)."""
    if objet.get("sorte") in BAIES:
        return "fenetre"
    dit = _sans_accents(objet.get("dit") or "")
    if objet.get("sorte") == "rideaux" and "voil" in dit and "avec voil" not in dit and "toute la largeur" in dit:
        return "voilage"
    return None


def _franc(x: float, boite, objets: list[dict], largeur: int) -> bool:
    """Le bord vertical d'abscisse `x` du rectangle `boite` est-il un VRAI bout (ni coupé par le cadre de la photo, ni caché
    par un autre objet lu dont le rectangle passe devant lui) ?"""
    if x < BORD_IMAGE * largeur or x > (1 - BORD_IMAGE) * largeur:
        return False
    y0, y1 = float(boite[1]), float(boite[3])
    marge = 0.02 * largeur
    for o in objets:
        if o.get("sorte") in BAIES or o.get("sorte") == "rideaux" or o.get("boite") is None:
            continue
        bx0, by0, bx1, by1 = (float(v) for v in o["boite"])
        if min(y1, by1) - max(y0, by0) >= 0.25 * (y1 - y0) and bx0 - marge <= x <= bx1 + marge:
            return False
    return True


def portee_libre(ouverture: dict, logement: dict) -> tuple[float, float] | None:
    """Jusqu'où la baie peut s'étendre le long de son mur, de part et d'autre de son milieu (mètres, négatif vers le début
    du mur) : tant que le devant du mur est dans la MÊME pièce (on s'arrête au coin, moins JAMBAGE), que l'autre côté du mur
    donne dehors, et jusqu'à ENTRE_BAIES d'une autre ouverture ou d'un passe-plat du même mur. None : mur inconnu."""
    from moteur.equipements import repere_de_la_baie
    from moteur.sol_a_plat import dans_polygone, piece_de

    baie = repere_de_la_baie(ouverture, logement)
    mur = next((m for m in logement.get("murs", []) if m["id"] == ouverture.get("mur")), None)
    if baie is None or mur is None:
        return None
    a, b = np.asarray(mur["debut"], float), np.asarray(mur["fin"], float)
    longueur = float(np.linalg.norm(b - a))
    ep = float(mur.get("epaisseur", 0.2))
    milieu = float(ouverture["position"]) + float(ouverture["largeur"]) / 2
    axe = baie["centre"] - baie["n"] * ep / 2
    pieces = logement.get("pieces", [])
    # le devant du mur : à 8 cm de sa face ; à 30 cm quand le contour de la pièce ne colle pas au mur (plan relevé à la main)
    devant = next((d for d in (0.08, 0.3) if piece_de(baie["centre"] + baie["n"] * d, pieces) is not None), None)
    if devant is None:
        return None
    piece = piece_de(baie["centre"] + baie["n"] * devant, pieces)

    def libre(s: float) -> bool:
        if not 0.0 <= milieu + s <= longueur:
            return False
        dedans = axe + baie["t"] * s + baie["n"] * (ep / 2 + devant)
        dehors = axe + baie["t"] * s - baie["n"] * (ep / 2 + 0.3)
        return bool(dans_polygone(np.array([dedans[0]]), np.array([dedans[1]]), piece["contour"])[0]) and piece_de(dehors, pieces) is None

    bornes = []
    for sens in (-1, 1):
        s = 0.0
        while libre(s + sens * 0.025):
            s += sens * 0.025
        bornes.append(s - sens * JAMBAGE)
    for o in [*logement.get("ouvertures", []), *logement.get("passe_plats", [])]:
        if o.get("mur") != mur["id"] or o.get("id") == ouverture.get("id"):
            continue
        d0, d1 = float(o["position"]) - milieu, float(o["position"]) + float(o["largeur"]) - milieu
        if d1 <= 0:
            bornes[0] = max(bornes[0], d1 + ENTRE_BAIES)
        elif d0 >= 0:
            bornes[1] = min(bornes[1], d0 - ENTRE_BAIES)
    demi = float(ouverture["largeur"]) / 2
    return min(bornes[0], -demi), max(bornes[1], demi)  # la baie du plan reste toujours dans sa portée


def mesures_d_une_photo(objets: list[dict], cam, largeur: int, logement: dict, plan: dict | None = None, photo=None) -> list[dict]:
    """Ce qu'UNE photo placée dit de la largeur des baies du plan : une mesure par baie vue,
    {"baie", "photo", "s": [s0, s1] (étendue le long du mur, en mètres depuis le milieu de la baie du plan, positive vers la
    fin du mur), "francs": [le bout s0 est-il un vrai bout ?, le bout s1 ?], "par": "fenetre" | "voilage", "distance"}.
    `objets` : les objets lus sur la photo (sorte, boite, dit) ; `cam` : l'appareil (x, y, z, cap, tangage, f, u0, v0)."""
    from moteur import caler_photos as cp
    from moteur.equipements import ECART_RIDEAUX_M, _sur_le_mur, repere_de_la_baie
    from moteur.photos_lues import premier_mur, rayon

    plan = plan or cp.plan_du_logement(logement)
    origine = np.array([float(cam[0]), float(cam[1])])
    baies = [(o, r) for o in logement.get("ouvertures", []) if o["type"] != "porte" and (r := repere_de_la_baie(o, logement)) is not None]
    par_baie: dict[str, dict] = {}
    for objet in objets:
        par = temoin(objet)
        if par is None:
            continue
        x0, y0, x1, y1 = (float(v) for v in objet["boite"])
        ecart = ECART_RIDEAUX_M if par == "voilage" else 0.0
        candidates = []
        for o, baie in baies:
            if float((origine - baie["centre"]) @ baie["n"]) < 0.3:
                continue  # l'appareil n'est pas du côté de la pièce
            distance = float(np.linalg.norm(origine - baie["centre"]))
            if distance > DISTANCE_MAX:
                continue
            s = {x: _sur_le_mur(cam, x, (y0 + y1) / 2, baie, ecart) for x in (x0, x1)}
            if None in s.values():
                continue  # vue rasante : le point où le rayon coupe le mur ne veut rien dire
            # le mur de la baie est-il bien ce que le regard rencontre au milieu du rectangle ? (sinon : une autre pièce derrière)
            angle = rayon(cam, (x0 + x1) / 2, (y0 + y1) / 2)[0]
            d = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
            den = float(d @ baie["n"])
            if den >= 0:
                continue
            jusqu_au_mur = float(-((origine - baie["centre"]) @ baie["n"]) / den)
            vu = premier_mur(plan, origine, angle, pieces=logement.get("pieces"))[0]
            if not math.isfinite(vu) or abs(vu - jusqu_au_mur) > VOIT_LE_MUR_M:
                continue
            s0, s1 = sorted(s.values())
            commun = min(s1, baie["demi"]) - max(s0, -baie["demi"])
            if commun < 0.5 * min(s1 - s0, 2 * baie["demi"]):
                continue  # le rectangle ne tombe pas sur cette baie
            a_gauche, a_droite = sorted(s, key=s.get)  # l'abscisse dans l'image du bout s0, du bout s1
            candidates.append((commun, o["id"], {"s": [s0, s1], "francs": [_franc(a_gauche, objet["boite"], objets, largeur),
                                                                             _franc(a_droite, objet["boite"], objets, largeur)],
                                                 "par": par, "distance": distance, "mur": o["mur"],
                                                 "centre": float(o["position"]) + float(o["largeur"]) / 2}))
        if not candidates:
            continue
        _, ident, m = max(candidates, key=lambda c: c[0])
        # un rectangle qui couvre AUSSI une autre baie du même mur (deux fenêtres encadrées d'un seul trait) ne mesure aucune des deux
        double = False
        for o, baie in baies:
            if o["id"] == ident or o["mur"] != m["mur"]:
                continue
            d0 = float(o["position"]) - m["centre"]
            if min(m["s"][1], d0 + float(o["largeur"])) - max(m["s"][0], d0) > 0.5 * float(o["largeur"]):
                double = True
        if double:
            continue
        if par == "voilage":  # la baie est le voilage moins ce qu'il déborde, là où son bout est un vrai bout
            m["s"] = [m["s"][0] + (MARGE_VOILAGE if m["francs"][0] else 0.0), m["s"][1] - (MARGE_VOILAGE if m["francs"][1] else 0.0)]
        deja = par_baie.get(ident)
        if deja is None:
            par_baie[ident] = m
        else:  # deux rectangles pour la même baie (ses deux vantaux) : la baie est leur réunion
            if m["s"][0] < deja["s"][0]:
                deja["s"][0], deja["francs"][0] = m["s"][0], m["francs"][0]
            if m["s"][1] > deja["s"][1]:
                deja["s"][1], deja["francs"][1] = m["s"][1], m["francs"][1]
            if m["par"] == "fenetre":
                deja["par"] = "fenetre"
    return [{"baie": ident, "photo": photo, "s": [round(v, 3) for v in m["s"]], "francs": m["francs"], "par": m["par"],
             "distance": round(m["distance"], 2)} for ident, m in par_baie.items()]


def _temoin_retenu(mesures: list[dict]) -> dict:
    """La photo dont on garde l'étendue, parmi celles qui voient la baie plus large que le plan : UNE seule, jamais un bout
    pris sur une photo et l'autre sur une autre (chaque appareil est placé à 30-50 cm près : mêler deux photos ajoute leurs
    deux erreurs — banc des fenêtres rétrécies, séjour d'app-001 : 2,06 m rendus pour 1,47). Celles qui voient la baie
    ENTIÈRE d'abord (la largeur médiane) ; sinon celle qui en voit le plus (un bord coupé ou caché ne fait que raccourcir)."""
    large = lambda m: m["s"][1] - m["s"][0]  # noqa: E731
    entieres = sorted((m for m in mesures if all(m["francs"])), key=large)
    if entieres:
        return entieres[len(entieres) // 2]
    return max(mesures, key=large)


def elargir(logement: dict, mesures: list[dict], journal=None, refusees=()) -> tuple[dict, list[dict], list[dict]]:
    """Le logement dont les fenêtres ont la largeur que les photos montrent quand elles contredisent NETTEMENT le plan.
    Rend le logement, ce qui a changé ([{"id", "mur", "avant": {position, largeur}, "apres": {…}, "photos", "vue": largeur
    vue}]) et les doutes (rien n'est changé) : photos qui ne s'accordent pas, ou baie qu'une personne a posée ou qui vient
    d'une cote (« ce qu'une personne a placé ne bouge jamais » ; le plan coté fait foi).
    refusees : les baies qu'une personne a refusé d'élargir (réponse de l'écran de vérification) : jamais touchées."""
    lg = copy.deepcopy(logement)
    changes, doutes = [], []
    refusees = set(refusees)
    for o in lg.get("ouvertures", []):
        de_la_baie = [m for m in mesures if m["baie"] == o["id"]]
        if o["type"] == "porte" or not de_la_baie:
            continue
        largeur = float(o["largeur"])
        large = lambda m: m["s"][1] - m["s"][0]  # noqa: E731
        pour = [m for m in de_la_baie if large(m) >= largeur + ECART_MIN and large(m) >= RAPPORT_MIN * largeur]
        if not pour:
            continue
        if o["id"] in refusees:
            continue
        if o.get("statut") == "mesure" or "verification" in str(o.get("source", "")):
            doutes.append({"id": o["id"], "largeur_du_plan": round(largeur, 3), "plus_large": [[m["photo"], round(large(m), 2)] for m in pour],
                           "raison": "baie mesurée sur une cote ou posée par une personne : gardée telle quelle"})
            if journal:
                journal(f"  baie {o['id']} : vue plus large par {len(pour)} photo(s), mais mesurée ou posée par une personne : rien n'est changé")
            continue
        contre = [m for m in de_la_baie if all(m["francs"]) and large(m) <= largeur + ACCORD_M]
        if contre:
            doutes.append({"id": o["id"], "largeur_du_plan": round(largeur, 3), "plus_large": [[m["photo"], round(large(m), 2)] for m in pour],
                           "comme_le_plan": [[m["photo"], round(large(m), 2)] for m in contre]})
            if journal:
                journal(f"  baie {o['id']} : vue plus large par {len(pour)} photo(s) et comme le plan par {len(contre)} : désaccord, rien n'est changé")
            continue
        portee = portee_libre(o, lg)
        if portee is None:
            continue
        retenu = _temoin_retenu(pour)
        s0 = max(min(retenu["s"][0], -largeur / 2), portee[0])
        s1 = min(max(retenu["s"][1], largeur / 2), portee[1])
        if (s1 - s0) - largeur < GAIN_MIN:
            if journal:
                journal(f"  baie {o['id']} : vue plus large ({max(large(m) for m in pour):.2f} m pour {largeur:.2f}), mais le mur ne laisse pas la place")
            continue
        milieu = float(o["position"]) + largeur / 2
        avant = {"position": round(float(o["position"]), 3), "largeur": round(largeur, 3)}
        apres = {"position": round(milieu + s0, 3), "largeur": round(s1 - s0, 3)}
        photos = sorted({str(m["photo"]) for m in pour})
        changes.append({"id": o["id"], "mur": o["mur"], "avant": avant, "apres": apres, "photos": photos,
                        "vue": round(max(large(m) for m in pour), 2), "par": sorted({m["par"] for m in pour})})
        o.update(apres, statut="estime", source=f"photos (largeur vue sur {len(photos)} photo(s) du client ; plan : {largeur:.2f} m)")
        if journal:
            journal(f"  baie {o['id']} : {largeur:.2f} m sur le plan → {apres['largeur']:.2f} m (vue {changes[-1]['vue']:.2f} m sur "
                    f"{', '.join(photos)} ; le mur laisse {portee[1] - portee[0]:.2f} m)")
    return lg, changes, doutes


def lire(logement: dict, fiche: dict, objets_par_photo: dict[str, list[dict]]) -> list[dict]:
    """Les mesures de toutes les photos placées d'une fiche (cameras-photos.json), d'après les objets lus sur chacune."""
    from moteur import caler_photos as cp
    from moteur.camera_photo import camera_depuis_dict

    plan = cp.plan_du_logement(logement)
    mesures = []
    for nom, objets in objets_par_photo.items():
        d = fiche["cameras"].get(nom)
        if d is None:
            continue
        cam = [float(c) for c in camera_depuis_dict(d["camera"])]
        largeur = int(d.get("largeur") or round(2 * float(d["camera"]["u0"])))
        mesures += mesures_d_une_photo(objets, cam, largeur, logement, plan, photo=nom)
    return mesures
