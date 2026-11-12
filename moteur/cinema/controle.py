"""Le CONTRÔLEUR du film (12/11/2026, étape 1 du plan validé par NT) : Atelya relit son vol AVANT de le tourner, comme un
réalisateur relit son plan de tournage, et dit où sont les défauts, image par image, avec une note sur 100.

Il ne corrige rien (les corrections viendront avec le planificateur) : il MESURE. Ce qu'il regarde :

    nez_au_mur      la caméra a un mur (ou un meuble haut) juste devant elle : l'image est bouchée
    recul           la caméra avance dans un sens et regarde dans l'autre (elle recule)
    rotation        elle tourne trop vite pour un film (le décor « glisse »)
    a_coup          sa vitesse change brusquement (secousse)
    frole           elle passe trop près d'un obstacle
    traverse        elle passe À TRAVERS un meuble (un meuble haut de cuisine, une suspension) ou touche le plafond
    piece_trop_vite une pièce qu'on voulait montrer n'est vue que quelques secondes
    fin_ratee       le film se termine sur un mur au lieu d'une belle vue
    duree           le film dépasse le budget de durée (NT trouve 1 min 50 trop long ; le survol de 50 s lui plaît)

Le contrôle se fait sur le PLAN (rayons depuis la position de la caméra) : quelques secondes, aucun rendu.
"""
from __future__ import annotations

import numpy as np

from moteur import realisateur as rz
from moteur.cinema.navigation import Carte, portes_ouvertes
from moteur.cinema.reglages import IPS, MARGE_M

# ce qu'on accepte (seuils réglés sur le survol de 50 s d'app-002, défauts vus à l'œil le 12/11/2026)
CHAMP_DEMI_DEG = 45.0  # demi-champ horizontal d'un 18 mm sur un capteur de 36 mm
CENTRE_DEMI_DEG = 15.0  # le centre de l'image, là où l'œil regarde
MUR_BOUCHE_M = 1.2  # un rayon qui touche un obstacle à moins de ça « bouche » l'image
MUR_PART_MAX = 0.55  # au-delà de cette part du champ bouchée, l'image est un mur
MUR_CENTRE_MIN_M = 1.0  # … ou si le centre de l'image est à moins de ça d'un obstacle
RECUL_DEG = 100.0  # regard à plus de ça de la direction du mouvement = la caméra recule
VITESSE_EN_VOL = 0.15  # m/s : au-dessous, la caméra est (presque) à l'arrêt
ROTATION_MAX_VOL = 40.0  # °/s en vol
ROTATION_MAX_ARRET = 70.0  # °/s à l'arrêt (pivot)
ACCELERATION_MAX = 1.2  # m/s² (vitesse lissée sur 0,25 s)
FROLE_M = MARGE_M * 0.9
TRAVERSE_JEU_M = 0.1  # la caméra doit passer au moins à ça au-dessus / au-dessous d'un meuble
PLAFOND_JEU_M = 0.25
PIECE_MIN_S = 3.0  # une pièce montrée doit être vue au moins ça
FIN_PROFONDEUR_MIN_M = 2.0  # la dernière seconde doit regarder au moins aussi loin
DUREE_PAR_PIECE_S = 10.0  # budget par défaut : 10 s par pièce montrée, +10 s (app-002 : 4 pièces → 50 s, la durée validée par NT)
DUREE_FIXE_S = 10.0
EPISODE_MIN_S = {"nez_au_mur": 0.4, "recul": 0.3, "rotation": 0.25, "a_coup": 0.2, "frole": 0.2, "traverse": 0.0}
# ce que coûte chaque défaut sur la note /100 : par seconde pour les défauts qui durent, par occurrence sinon
COUT_PAR_S = {"nez_au_mur": 4.0, "recul": 6.0, "rotation": 3.0, "a_coup": 3.0, "frole": 1.5}
COUT_FIXE = {"traverse": 15.0, "piece_trop_vite": 4.0, "fin_ratee": 10.0}
COUT_DUREE_PAR_S = 0.5
TEXTES = {"nez_au_mur": "nez sur un mur", "recul": "la caméra recule", "rotation": "rotation trop rapide",
          "a_coup": "secousse (changement de vitesse brusque)", "frole": "frôle un obstacle",
          "traverse": "traverse un meuble ou touche le plafond", "piece_trop_vite": "pièce vue trop vite",
          "fin_ratee": "fin sur un mur", "duree": "film trop long"}


def par_image(trajet: dict) -> dict:
    """Les clés du trajet (une toutes les 2 images) → une valeur par image : x, y, z, cap (déroulé), tangage."""
    pts = np.asarray(trajet["points"], float)
    n = int(trajet["images"])
    cles = np.round(np.arange(len(pts)) * (n - 1) / max(len(pts) - 1, 1))
    images = np.arange(n)
    return {nom: np.interp(images, cles, pts[:, k]) for k, nom in enumerate(("x", "y", "z", "cap", "tangage"))}


def _episodes(drapeau: np.ndarray, min_images: int, trou: int = 6) -> list[tuple[int, int]]:
    """Les moments où le drapeau est levé (début, fin incluse), petits trous comblés, trop courts ignorés."""
    sortie, debut, dernier = [], None, None
    for k in np.nonzero(drapeau)[0]:
        if debut is None:
            debut = dernier = int(k)
        elif k - dernier <= trou:
            dernier = int(k)
        else:
            sortie.append((debut, dernier))
            debut = dernier = int(k)
    if debut is not None:
        sortie.append((debut, dernier))
    return [(a, b) for a, b in sortie if b - a + 1 >= max(1, min_images)]


def _piece_de(logement: dict, xy) -> str | None:
    return next((p["id"] for p in logement["pieces"] if len(p.get("contour") or []) >= 3 and rz._dedans(tuple(xy), p["contour"])),
                None)


def controler(logement: dict, vol: dict, budget_s: float | None = None) -> dict:
    """Le contrôle d'un vol (le résultat de promeneur.vol) : défauts (genre, début et fin en secondes, pièce, détail),
    mesures image par image et note /100."""
    f = par_image(vol["trajet"])
    n = len(f["x"])
    xy = np.stack([f["x"], f["y"]], 1)
    ids_ouvertes = {p["id"] for p in vol.get("portes_ouvertes", [])}
    portes = [p for p in portes_ouvertes(logement) if p["id"] in ids_ouvertes]
    voir = rz.Scene2D({**logement, "ouvertures": [o for o in logement.get("ouvertures", [])
                                                  if o["type"] != "porte" or o["id"] in ids_ouvertes]}, portes_fermees=False)
    hauteur_type = float(np.median(f["z"]))
    carte = Carte(logement, portes, hauteur_camera=hauteur_type)

    # 1. ce que la caméra a devant elle (une mesure toutes les 2 images, les rayons coûtent)
    part_bouchee = np.zeros(n)
    centre = np.full(n, 99.0)
    profondeur = np.zeros(n)
    for k in range(0, n, 2):
        r = voir.rayons((float(xy[k, 0]), float(xy[k, 1])))
        ecart = np.abs((r["angles"] - f["cap"][k] + 180) % 360 - 180)
        champ = r["distance"][ecart <= CHAMP_DEMI_DEG]
        part_bouchee[k:k + 2] = float(np.mean(champ < MUR_BOUCHE_M)) if len(champ) else 1.0
        milieu = r["distance"][ecart <= CENTRE_DEMI_DEG]
        centre[k:k + 2] = float(np.min(milieu)) if len(milieu) else 0.0
        profondeur[k:k + 2] = float(np.median(np.minimum(champ, 8.0))) if len(champ) else 0.0
    nez = (part_bouchee > MUR_PART_MAX) | (centre < MUR_CENTRE_MIN_M)

    # 2. le mouvement : vitesse, accélération, sens, rotation
    lisse = max(1, int(0.25 * IPS))
    noyau = np.ones(lisse) / lisse
    dxy = np.gradient(xy, axis=0) * IPS
    vitesse = np.convolve(np.pad(np.linalg.norm(dxy, axis=1), lisse, mode="edge"), noyau, mode="same")[lisse:-lisse]
    acceleration = np.abs(np.gradient(vitesse) * IPS)
    sens = np.degrees(np.arctan2(dxy[:, 1], dxy[:, 0]))
    ecart_sens = np.abs((f["cap"] - sens + 180) % 360 - 180)
    recul = (vitesse > VITESSE_EN_VOL) & (ecart_sens > RECUL_DEG)
    rotation = np.abs(np.gradient(f["cap"]) * IPS)
    rotation = np.convolve(np.pad(rotation, lisse, mode="edge"), noyau, mode="same")[lisse:-lisse]
    trop_tourne = rotation > np.where(vitesse > VITESSE_EN_VOL, ROTATION_MAX_VOL, ROTATION_MAX_ARRET)
    a_coup = acceleration > ACCELERATION_MAX

    # 3. les obstacles : au sol (la grille), en hauteur (meubles posés en l'air, suspensions, plafond)
    degagement = np.array([carte.distance[i, j] if 0 <= i < carte.forme[0] and 0 <= j < carte.forme[1] else 0.0
                           for i, j in (carte.case(q) for q in xy)])
    frole = degagement < FROLE_M
    hsp = float(logement.get("hauteur_sous_plafond") or 2.5)
    traverse = f["z"] > hsp - PLAFOND_JEU_M
    for m in logement.get("meubles", []):
        if not (m.get("position") and m.get("dimensions")):
            continue
        bas = float(m.get("altitude") or 0.0)
        haut = bas + (float(m["dimensions"][2]) if len(m["dimensions"]) > 2 else 1.0)
        poly = [tuple(q) for q in rz._rectangle_meuble(m)]
        dessous = np.array([rz._dedans((float(q[0]), float(q[1])), poly) for q in xy])
        traverse |= dessous & (f["z"] > bas - TRAVERSE_JEU_M) & (f["z"] < haut + TRAVERSE_JEU_M)

    defauts = []
    for genre, drapeau in (("nez_au_mur", nez), ("recul", recul), ("rotation", trop_tourne), ("a_coup", a_coup),
                           ("frole", frole), ("traverse", traverse)):
        for a, b in _episodes(drapeau, int(EPISODE_MIN_S[genre] * IPS)):
            milieu = (a + b) // 2
            d = {"genre": genre, "debut_s": round(a / IPS, 2), "fin_s": round((b + 1) / IPS, 2),
                 "piece": _piece_de(logement, xy[milieu]), "texte": TEXTES[genre]}
            if genre == "nez_au_mur":
                d["detail"] = {"part_bouchee": round(float(part_bouchee[a:b + 1].max()), 2),
                               "centre_m": round(float(centre[a:b + 1].min()), 2)}
            elif genre == "rotation":
                d["detail"] = {"deg_par_s": round(float(rotation[a:b + 1].max()), 1)}
            elif genre == "a_coup":
                d["detail"] = {"m_par_s2": round(float(acceleration[a:b + 1].max()), 2)}
            elif genre == "frole":
                d["detail"] = {"distance_m": round(float(degagement[a:b + 1].min()), 2)}
            defauts.append(d)

    # 4. le temps passé dans chaque pièce qu'on voulait montrer
    pieces_images = [_piece_de(logement, q) for q in xy]
    montrees = [e["piece"] for e in vol.get("etapes", []) if e["genre"] == "point_de_vue"]
    temps = {pid: round(pieces_images.count(pid) / IPS, 1) for pid in dict.fromkeys(montrees)}
    for pid, t in temps.items():
        if t < PIECE_MIN_S:
            defauts.append({"genre": "piece_trop_vite", "debut_s": None, "fin_s": None, "piece": pid,
                            "texte": TEXTES["piece_trop_vite"], "detail": {"secondes": t}})

    # 5. la fin et la durée
    derniere = slice(max(0, n - IPS), n)
    fin_profondeur = float(np.median(profondeur[derniere]))
    if fin_profondeur < FIN_PROFONDEUR_MIN_M or bool(np.mean(nez[derniere]) > 0.5):
        defauts.append({"genre": "fin_ratee", "debut_s": round(max(0, n - IPS) / IPS, 2), "fin_s": round(n / IPS, 2),
                        "piece": pieces_images[-1], "texte": TEXTES["fin_ratee"],
                        "detail": {"profondeur_m": round(fin_profondeur, 2)}})
    duree = n / IPS
    if budget_s is None:
        budget_s = DUREE_FIXE_S + DUREE_PAR_PIECE_S * len(temps)
    if duree > budget_s:
        defauts.append({"genre": "duree", "debut_s": None, "fin_s": None, "piece": None, "texte": TEXTES["duree"],
                        "detail": {"duree_s": round(duree, 1), "budget_s": round(budget_s, 1)}})

    # 6. la note
    perte = 0.0
    for d in defauts:
        if d["genre"] in COUT_PAR_S:
            perte += COUT_PAR_S[d["genre"]] * (d["fin_s"] - d["debut_s"])
        elif d["genre"] in COUT_FIXE:
            perte += COUT_FIXE[d["genre"]]
        elif d["genre"] == "duree":
            perte += COUT_DUREE_PAR_S * (duree - budget_s)
    defauts.sort(key=lambda d: (d["debut_s"] is None, d["debut_s"] or 0.0))
    resume = {}
    for d in defauts:
        r = resume.setdefault(d["genre"], {"nombre": 0, "secondes": 0.0})
        r["nombre"] += 1
        if d["debut_s"] is not None and d["genre"] in COUT_PAR_S:
            r["secondes"] = round(r["secondes"] + d["fin_s"] - d["debut_s"], 2)
    return {"note": round(max(0.0, 100.0 - perte), 1), "duree_s": round(duree, 1), "budget_s": round(budget_s, 1),
            "defauts": defauts, "resume": resume, "temps_par_piece_s": temps,
            "mesures": {"vitesse_max_m_s": round(float(vitesse.max()), 2),
                        "acceleration_max_m_s2": round(float(acceleration.max()), 2),
                        "rotation_max_deg_s": round(float(rotation.max()), 1),
                        "part_nez_au_mur": round(float(np.mean(nez)), 3),
                        "profondeur_mediane_m": round(float(np.median(profondeur)), 2),
                        "degagement_min_m": round(float(degagement.min()), 2)},
            "courbes": {"part_bouchee": part_bouchee.round(2).tolist(), "centre_m": np.minimum(centre, 12).round(2).tolist(),
                        "vitesse": vitesse.round(3).tolist(), "rotation": rotation.round(1).tolist()}}


def rapport(c: dict) -> str:
    """Le contrôle en mots simples, une ligne par défaut."""
    lignes = [f"Note du vol : {c['note']}/100 ; durée {c['duree_s']} s (budget {c['budget_s']} s)"]
    for d in c["defauts"]:
        quand = f"{d['debut_s']:5.1f}-{d['fin_s']:5.1f} s" if d["debut_s"] is not None else "        —    "
        detail = ", ".join(f"{k} {v}" for k, v in (d.get("detail") or {}).items())
        lignes.append(f"  {quand}  {d['texte']:<40} {d['piece'] or '':<6} {detail}")
    lignes.append("  temps par pièce montrée : " + ", ".join(f"{k} {v} s" for k, v in c["temps_par_piece_s"].items()))
    return "\n".join(lignes)

