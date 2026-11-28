r"""LES OBJETS ACCROCHÉS vus sur les photos : d'abord les LUMINAIRES SUSPENDUS (16/11/2026).

Pourquoi : le banc de fidélité (outils/atelya/banc_fidelite.py) montre que les luminaires sont l'objet le plus souvent vu sur
les photos et jamais posé par Atelya (43 vus sur 35 photos, 0 dans les maquettes), alors que la bibliothèque en a 66 modèles
et que la maquette sait les porter (catégorie « suspension », posée à la main sur app-001 et app-002).

Un meuble posé au sol se place par son PIED (le bas de son rectangle touche le sol). Un luminaire suspendu n'a pas de pied : sa
place vient de la PROFONDEUR. MoGe-2 (moteur/moge.py) donne chaque point de la photo en mètres ; dans le rectangle du
luminaire, les points les plus proches sont le luminaire (le mur du fond est plus loin) ; leur direction, leur distance et leur
hauteur, reportées sur le plan avec la place de l'appareil, donnent sa place, le bas et le haut de son abat-jour.

Garde-fous : un luminaire suspendu est HAUT (bas à plus de BAS_MIN du sol) et DANS une pièce ; vu sur plusieurs photos, il ne
compte qu'une fois (FUSION_M) ; deux luminaires d'une même photo restent deux luminaires. Rien n'est inventé : un plafonnier
qu'aucune photo ne montre n'est pas posé.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
PHRASES = ("a ceiling light", "a pendant lamp", "a chandelier")  # ce que le détecteur appelle un luminaire suspendu
NOTE_MIN = 0.3
BAS_MIN = 1.5  # m : le bas d'un luminaire suspendu est au moins à cette hauteur (sinon c'est une lampe posée, un reflet…)
FUSION_M = 0.9  # deux vues à moins de 90 cm l'une de l'autre (à plat) sont le même luminaire
MEME_LUMINAIRE_M = 0.5  # … et à moins de 50 cm, même sur une seule photo (l'abat-jour et sa rosace vus comme deux objets)
PRES_DU_MUR_M = 0.25  # un luminaire à moins de 25 cm d'un mur…
SOUS_LE_PLAFOND_M = 0.5  # … dont le haut est à plus de 50 cm sous le plafond est une APPLIQUE murale, pas une suspension
# Une suspension pend du plafond : elle va jusqu'à lui, et son bas reste entre ces bornes (la hauteur mesurée sur la photo est
# juste à ± 30 cm : contre les relevés à la main d'app-001 et app-002, le bas mesuré va de 1,6 à 2,4 m pour 2,05 à 2,2 m vrais).
BAS_LE_PLUS_BAS = 1.8  # m : on passe dessous
CHUTE_MAX, CHUTE_MIN = 1.0, 0.25  # m sous le plafond : le bas n'est ni plus bas que 1 m sous le plafond, ni plus haut que 25 cm
LARGEUR = (0.2, 1.6)  # m : largeurs possibles
PROCHE_M = 0.5  # dans le rectangle, les points à moins de 50 cm du plus proche quart sont le luminaire
POINTS_MIN = 30


def place_dans_la_photo(boite, repere: dict, camera: dict, largeur: int, hauteur: int) -> dict | None:
    """La place en mètres de ce que montre le rectangle `boite` (pixels de la photo), d'après les points de MoGe-2 mis dans le
    repère de la pièce (moteur.caler_photos.repere : hauteur h, direction phi, distance à plat r) et la place de l'appareil.
    Rend {"position": [x, y], "bas", "haut", "largeur", "distance"} ; None si le rectangle n'a pas assez de points mesurés."""
    h, phi, r, M = repere["h"], repere["phi"], repere["r"], repere["M"]
    Hm, Wm = M.shape
    x0, y0, x1, y1 = (float(v) for v in boite)
    # le cœur du rectangle (les bords prennent le plafond et le mur derrière)
    u0, u1 = int((x0 + 0.15 * (x1 - x0)) * Wm / largeur), int(math.ceil((x1 - 0.15 * (x1 - x0)) * Wm / largeur))
    v0, v1 = int((y0 + 0.15 * (y1 - y0)) * Hm / hauteur), int(math.ceil((y1 - 0.15 * (y1 - y0)) * Hm / hauteur))
    u0, v0, u1, v1 = max(0, u0), max(0, v0), min(Wm, max(u1, u0 + 1)), min(Hm, max(v1, v0 + 1))
    ok = M[v0:v1, u0:u1] & repere["devant"][v0:v1, u0:u1]
    if ok.sum() < POINTS_MIN:
        return None
    rr, hh, pp = r[v0:v1, u0:u1][ok], h[v0:v1, u0:u1][ok], phi[v0:v1, u0:u1][ok]
    pres = np.abs(rr - np.percentile(rr, 25)) < PROCHE_M
    if pres.sum() < POINTS_MIN:
        return None
    distance, direction = float(np.median(rr[pres])), float(np.median(pp[pres]))
    angle = math.radians(float(camera["cap"]) + direction)
    bas, haut = float(np.percentile(hh[pres], 5)), float(np.percentile(hh[pres], 95))
    en_3d = math.hypot(distance, (bas + haut) / 2 - float(camera["z"]))
    return {"position": [float(camera["x"]) + distance * math.cos(angle), float(camera["y"]) + distance * math.sin(angle)],
            "bas": bas, "haut": haut, "largeur": (x1 - x0) / float(camera["f"]) * en_3d, "distance": distance}


def suspensions_d_une_photo(objets: list[dict], repere: dict | None, camera: dict, largeur: int, hauteur: int, logement: dict,
                            rgb: np.ndarray | None = None, photo: int | None = None) -> list[dict]:
    """Les luminaires suspendus qu'UNE photo montre (`objets` : rectangles distincts du détecteur, {"phrase", "note", "boite"})."""
    from moteur.sol_a_plat import piece_de

    if repere is None:
        return []
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    sortie = []
    for o in objets:
        if o["phrase"] not in PHRASES or o["note"] < NOTE_MIN:
            continue
        p = place_dans_la_photo(o["boite"], repere, camera, largeur, hauteur)
        if p is None or p["bas"] < BAS_MIN or p["bas"] > hsp or piece_de(p["position"], logement["pieces"]) is None:
            continue
        x0, y0, x1, y1 = (int(v) for v in o["boite"])
        couleur = None
        if rgb is not None:
            coeur = rgb[y0 + (y1 - y0) // 4:max(y0 + (y1 - y0) // 4 + 1, y1 - (y1 - y0) // 4),
                        x0 + (x1 - x0) // 4:max(x0 + (x1 - x0) // 4 + 1, x1 - (x1 - x0) // 4)].reshape(-1, 3)
            couleur = [int(v) for v in np.median(coeur, axis=0)] if len(coeur) else None
        sortie.append({**p, "note": float(o["note"]), "photo": photo, "couleur": couleur,
                       "appareil": [float(camera["x"]), float(camera["y"])]})
    return sortie


def fusionner(vus: list[dict]) -> list[dict]:
    """Le même luminaire vu sur plusieurs photos ne compte qu'une fois ; deux luminaires d'une même photo restent deux."""
    from moteur.meubles_photos import reunir

    # des vues les plus proches aux plus lointaines : un luminaire vu de l'autre bout de la pièce (place à 1 - 2 m près) rejoint
    # celui qu'une photo proche a déjà placé, au lieu d'en faire un second (16/11/2026, « place et taille justes »)
    def place(paquet: list[dict]) -> np.ndarray:
        poids = np.array([v["note"] / max(float(v.get("distance") or 1.0), 0.5) ** 2 for v in paquet])
        return (np.array([v["position"] for v in paquet]) * poids[:, None]).sum(0) / poids.sum()

    # Les vues rejoignent la vue la plus PROCHE déjà posée ; quand la limite tombe entre deux vues d'un même luminaire (app-004,
    # 28/11/2026 : 0,90 m pour 0,90 m), il sort en DEUX luminaires collés l'un à l'autre (62 cm). Deux luminaires dont les
    # places finales sont à moins de FUSION_M et qu'AUCUNE photo ne montre ensemble sont le même : réunis. (Une rangée de
    # suspensions au-dessus d'un îlot se voit sur une même photo : elle reste une rangée.)
    paquets = reunir(vus, FUSION_M, MEME_LUMINAIRE_M)
    while True:
        paires = [(float(np.linalg.norm(place(a) - place(b))), i, j) for i, a in enumerate(paquets) for j, b in enumerate(paquets)
                  if i < j and all(v.get("photo") is not None for v in a + b)
                  and not {v["photo"] for v in a} & {v["photo"] for v in b}]
        paires = [p for p in paires if p[0] < FUSION_M]
        if not paires:
            break
        _, i, j = min(paires)
        paquets[i] = sorted(paquets[i] + paquets[j], key=lambda v: float(v.get("distance") or 0.0))
        del paquets[j]
    sortie = []
    for paquet in paquets:
        poids = np.array([v["note"] / max(float(v.get("distance") or 1.0), 0.5) ** 2 for v in paquet])
        position = place(paquet)
        couleurs = [v["couleur"] for v in paquet if v.get("couleur")]
        sortie.append({"position": [round(float(position[0]), 3), round(float(position[1]), 3)], "vues": len(paquet),
                       "note": round(float(np.mean([v["note"] for v in paquet])), 3), "bas": float(np.median([v["bas"] for v in paquet])),
                       "haut": float(np.median([v["haut"] for v in paquet])), "largeur": float(np.median([v["largeur"] for v in paquet])),
                       "couleur": [int(c) for c in np.median(np.array(couleurs), axis=0)] if couleurs else None})
    return sortie


def distance_au_mur(position, piece: dict) -> float:
    """La distance (m) du point au bord le plus proche de sa pièce."""
    c = np.asarray(piece["contour"], float)
    p = np.asarray(position, float)
    meilleur = math.inf
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        ab = b - a
        s = float(np.clip((p - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0))
        meilleur = min(meilleur, float(np.linalg.norm(p - (a + s * ab))))
    return meilleur


def vers_meubles(trouves: list[dict], logement: dict, prefixe: str = "suspension") -> list[dict]:
    """Luminaires trouvés → meubles de catégorie « suspension » (statut « estime », source « repérage photos »). Une APPLIQUE
    murale (près d'un mur, loin sous le plafond) n'est pas posée : la maquette n'a pas encore cette sorte, et une suspension
    flottant à hauteur de tête contre un mur serait fausse."""
    from moteur.sol_a_plat import piece_de

    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    sortie = []
    for k, t in enumerate(trouves, start=1):
        piece = piece_de(t["position"], logement["pieces"])
        if piece is None:
            continue
        if distance_au_mur(t["position"], piece) < PRES_DU_MUR_M and t["haut"] < hsp - SOUS_LE_PLAFOND_M:
            continue  # une applique murale
        largeur = min(max(t["largeur"], LARGEUR[0]), LARGEUR[1])
        altitude = min(max(t["bas"], BAS_LE_PLUS_BAS, hsp - CHUTE_MAX), hsp - CHUTE_MIN)
        hauteur = hsp - altitude  # jusqu'au plafond (fil compris), comme dans les maquettes faites à la main
        m = {"id": f"{prefixe}_{k}", "categorie": "suspension", "piece": piece["id"], "position": t["position"], "face": 0.0,
             "dimensions": [round(largeur, 2), round(largeur, 2), round(hauteur, 2)], "altitude": round(altitude, 2),
             "statut": "estime", "source": f"repérage photos ({t['vues']} photo(s))", "confiance": min(1.0, t["note"])}
        if t.get("couleur"):
            m["couleur"] = t["couleur"]
        sortie.append(m)
    return sortie


def reperer_suspensions(releve: dict, logement: dict, racine, owl=None, modele_moge=None, journal=lambda *_: None) -> list[dict]:
    """Photos placées du client (fiche cameras-photos.json) → luminaires suspendus, prêts à entrer dans le logement."""
    from pathlib import Path

    import cv2

    from moteur import caler_photos as cp
    from moteur import moge
    from moteur.fidelite_photos import VOCABULAIRE
    from moteur.images import lire_image
    from moteur.owlv2 import charger as charger_owl, objets, objets_distincts

    owl = owl or charger_owl()
    modele_moge = modele_moge or moge.charger()
    phrases = list(VOCABULAIRE)
    requetes = owl.textes(phrases)
    sorte_de = {p: ("luminaire" if p in PHRASES else VOCABULAIRE[p]) for p in phrases}
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    dossier, fichier = Path(racine) / releve["photos"], releve.get("fichier", "{nom}.png")
    vus = []
    for k, (nom, d) in enumerate(releve["cameras"].items()):
        image = lire_image(dossier / fichier.format(nom=nom))
        if image is None:
            raise FileNotFoundError(dossier / fichier.format(nom=nom))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        distincts = objets_distincts(objets(owl.detecter(rgb, requetes), phrases, seuil=0.1, recouvrement_max=0.7), sorte_de, {}, NOTE_MIN)
        if not any(o["phrase"] in PHRASES for o in distincts):
            continue
        repere = cp.repere(cp.mesurer(modele_moge, rgb, float(d["camera"]["f"])), hsp)
        de_la_photo = suspensions_d_une_photo(distincts, repere, d["camera"], rgb.shape[1], rgb.shape[0], logement, rgb, photo=k)
        vus += de_la_photo
        if de_la_photo:
            journal(f"  {nom} : {len(de_la_photo)} luminaire(s) suspendu(s)")
    return vers_meubles(fusionner(vus), logement)
