r"""LES RANGÉES DE CUISINE, dites par la lecture des photos et rangées par Atelya le long des murs du plan (17/11/2026).

Pourquoi (NT, 17/11/2026 : « travaille tous ces points-là ») : dans une petite pièce, la place de l'appareil photo n'est connue
qu'à 30-60 cm ; mesurer chaque élément de cuisine par les bords de son rectangle y donne des meubles éparpillés, trop courts, et
un réfrigérateur sans place. Or une cuisine est une SUITE d'éléments le long d'un mur, calée sur un coin : la lecture de la photo
dit cette suite (du SENS, aucun mètre), Atelya la range bout à bout sur le mur du plan, par modules de 60 cm.

Ce que la lecture dit, par photo (moteur/lecture_photos.py, champ `rangees`) : pour un mur,
- le mur : « vers n » (le mur que touche le regard vers le rectangle n), « gauche n » / « droite n » (le mur voisin, au bout
  gauche / droit — à l'image — du mur du rectangle n), « droite n +1 » (le mur d'après, de l'autre côté d'un pilier) ;
- la suite, de la GAUCHE vers la DROITE de l'image : `coin` (le bout du mur), `angle` (le bout du mur, dont les 60 premiers
  centimètres sont pris par la rangée du mur voisin), `cadre` (la rangée sort de la photo), et les éléments : colonne, meuble
  bas, réfrigérateur, vide ; un nombre de modules de 60 cm (1 par défaut), ou « le reste » (il remplit ce qui reste du mur).
Ce module trouve le mur sur le plan, range la suite, et rend les meubles ; les rectangles nommés ne sont plus posés un par un.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
MODULE_M = 0.6
RESTE_SEUL_M = 1.2  # un élément « le reste » dont la rangée n'est calée que d'un côté : deux modules
RESTE_MIN_M = 0.3  # en dessous, « le reste » ne tient pas : la rangée n'est pas rangée (les rectangles sont posés comme avant)
JEU_M = 0.02
ANGLE_M = MODULE_M + 2 * JEU_M  # la place que prend, dans un coin, la rangée du mur voisin (sa profondeur et son jeu au mur)
ALIGNES = math.radians(4.0)  # deux côtés du contour d'une pièce qui se suivent à moins de 4° sont le même mur
DECROCHE_M = 0.25  # un décroché de moins de 25 cm entre deux pans parallèles (un doublage, une gaine) : le même mur
PETIT_MUR_M = 0.5  # les côtés d'un pilier : on les saute pour aller « au mur suivant »
# profondeur et hauteur de chaque élément (la largeur vient de la suite)
ELEMENTS = {"colonne_cuisine": (0.6, 2.2), "meuble_cuisine_bas": (0.6, 0.9), "refrigerateur": (0.65, 1.8)}
ANCRES = ("coin", "angle")
SOURCE = "rangée de cuisine dite par les photos"  # ni « repérage » ni « lecture » : la réparation des collisions ne la déplace pas


def faces(logement: dict) -> list[dict]:
    """Les murs de chaque pièce, vus de dedans : {"piece", "a", "b", "normale" (vers l'intérieur), "rang"}, dans l'ordre du
    contour ; les côtés alignés qui se suivent sont réunis (un contour porte parfois un sommet au milieu d'un mur)."""
    sortie = []
    for piece in logement["pieces"]:
        pts = [np.asarray(p, float) for p in piece["contour"]]
        pts = [p for k, p in enumerate(pts) if np.linalg.norm(p - pts[k - 1]) > 1e-6]
        if len(pts) < 3:
            continue
        # les sommets où le contour TOURNE vraiment
        coins = []
        for k, p in enumerate(pts):
            avant, apres = p - pts[k - 1], pts[(k + 1) % len(pts)] - p
            tourne = abs(math.atan2(float(avant[0] * apres[1] - avant[1] * apres[0]), float(avant @ apres)))
            if tourne > ALIGNES:
                coins.append(p)
        # le dedans est à gauche quand on suit un contour qui tourne dans le sens inverse des aiguilles d'une montre
        aire = sum(float(p[0] * q[1] - q[0] * p[1]) for p, q in zip(pts, pts[1:] + pts[:1]))
        dedans = lambda u: np.array([-u[1], u[0]]) * (1.0 if aire > 0 else -1.0)
        coins = _sans_petits_decroches(coins, dedans)
        for k, a in enumerate(coins):
            b = coins[(k + 1) % len(coins)]
            ab = b - a
            L = float(np.linalg.norm(ab))
            if L < 1e-6:
                continue
            sortie.append({"piece": piece["id"], "a": a, "b": b, "normale": dedans(ab / L), "rang": k, "cotes": len(coins)})
    return sortie


def _sans_petits_decroches(coins: list, dedans) -> list:
    """Deux pans parallèles qui se suivent, décalés de moins de 25 cm, sont UN mur : celui des deux qui avance le plus dans la
    pièce, prolongé (un meuble rangé contre lui ne mord dans aucun des deux)."""
    coins = list(coins)
    encore = True
    while encore and len(coins) > 4:
        encore = False
        n = len(coins)
        for k in range(n):
            a, b, c, d = coins[k - 1], coins[k], coins[(k + 1) % n], coins[(k + 2) % n]
            saut = c - b
            if not 1e-6 < float(np.linalg.norm(saut)) < DECROCHE_M:
                continue
            u1, u2 = (b - a) / max(float(np.linalg.norm(b - a)), 1e-9), (d - c) / max(float(np.linalg.norm(d - c)), 1e-9)
            if float(u1 @ u2) < math.cos(ALIGNES):
                continue
            if float(saut @ dedans(u1)) < 0:  # le premier pan avance le plus : le second est ramené sur sa ligne
                nouveaux = {(k + 2) % n: a + float((d - a) @ u1) * u1}
            else:  # le second avance le plus : le premier est ramené sur sa ligne
                nouveaux = {(k - 1) % n: d + float((a - d) @ u2) * u2}
            coins = [nouveaux.get(i, p) for i, p in enumerate(coins) if i not in (k, (k + 1) % n)]
            encore = True
            break
    return coins


def face_visee(point, origine, toutes: list[dict]) -> dict | None:
    """Le mur (vu de dedans, du côté de l'appareil) le plus proche du point que le regard touche."""
    p, o = np.asarray(point, float), np.asarray(origine, float)
    meilleur, dmin = None, 0.6
    for f in toutes:
        if float((o - f["a"]) @ f["normale"]) <= 0:  # l'appareil est derrière ce mur : c'est la face de l'autre pièce
            continue
        ab = f["b"] - f["a"]
        q = f["a"] + float(np.clip((p - f["a"]) @ ab / float(ab @ ab), 0.0, 1.0)) * ab
        d = float(np.linalg.norm(p - q))
        if d < dmin:
            meilleur, dmin = f, d
    return meilleur


def sens_de_l_image(f: dict, cam) -> float:
    """+1 si, à l'image, on va vers la droite en allant de `a` vers `b` le long de ce mur ; −1 sinon. Jugé sur les points du mur
    qui sont DEVANT l'appareil : pour un mur de côté (qui file le long du regard), « la droite de l'appareil » ne dit rien —
    sur le mur de gauche, on va vers la droite de l'image en s'éloignant."""
    cap = math.radians(float(cam[3]))
    vue, droite = np.array([math.cos(cap), math.sin(cap)]), np.array([math.sin(cap), -math.cos(cap)])
    origine = np.array([float(cam[0]), float(cam[1])])
    vus = []
    for s in np.linspace(0.02, 0.98, 33):
        p = f["a"] + s * (f["b"] - f["a"]) - origine
        z = float(p @ vue)
        if z > 0.15:
            vus.append(float(p @ droite) / z)
    if len(vus) >= 2 and abs(vus[-1] - vus[0]) > 1e-6:
        return 1.0 if vus[-1] > vus[0] else -1.0
    return 1.0 if float(droite @ (f["b"] - f["a"])) > 0 else -1.0


def voisine(f: dict, cote: str, cam, toutes: list[dict], saut: int = 0) -> dict | None:
    """Le mur de la même pièce qui touche le bout gauche (ou droit, à l'image) de celui-ci. `saut` : et, de là, le n-ième mur
    suivant dans le même sens, sans compter les petits côtés (ceux d'un pilier) : « le mur d'après le pilier »."""
    pas = 1 if (sens_de_l_image(f, cam) > 0) == (cote == "droite") else -1
    du_rang = {g["rang"]: g for g in toutes if g["piece"] == f["piece"]}
    rang = (f["rang"] + pas) % f["cotes"]
    for _ in range(f["cotes"]):
        if saut <= 0:
            break
        rang = (rang + pas) % f["cotes"]
        g = du_rang.get(rang)
        if g is not None and float(np.linalg.norm(g["b"] - g["a"])) >= PETIT_MUR_M:
            saut -= 1
    return du_rang.get(rang) if saut <= 0 else None


def mur_designe(mur: dict, boites: dict[int, list[float]], cam, plan: dict, logement: dict, toutes: list[dict]) -> dict | None:
    from moteur.photos_lues import premier_mur, rayon

    boite = boites.get(int(mur["numero"]))
    if boite is None:
        return None
    origine = np.array([float(cam[0]), float(cam[1])])
    angle = rayon(cam, (boite[0] + boite[2]) / 2, (boite[1] + boite[3]) / 2)[0]
    distance, _ = premier_mur(plan, origine, angle, pieces=logement["pieces"])
    if not math.isfinite(distance):
        return None
    point = origine + distance * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    f = face_visee(point, origine, toutes)
    if f is None or mur["repere"] == "vers":
        return f
    return voisine(f, mur["repere"], cam, toutes, int(mur.get("saut") or 0))


def ranger(suite: list[dict], longueur: float) -> list[dict] | None:
    """La suite (de gauche à droite) rangée sur un mur de `longueur` mètres compté depuis son bout GAUCHE à l'image :
    [{"sorte", "debut", "fin", "numeros"}], sans les vides ; None si rien ne la cale (aucun coin) ou si « le reste » ne tient pas."""
    if not suite:
        return None
    gauche = suite[0]["sorte"] if suite[0]["sorte"] in (*ANCRES, "cadre") else None
    droite = suite[-1]["sorte"] if len(suite) > 1 and suite[-1]["sorte"] in (*ANCRES, "cadre") else None
    corps = [e for e in suite[(1 if gauche else 0):(len(suite) - 1 if droite else len(suite))] if e["sorte"] not in (*ANCRES, "cadre")]
    x0 = {"coin": 0.0, "angle": ANGLE_M}.get(gauche)
    x1 = {"coin": longueur, "angle": longueur - ANGLE_M}.get(droite)
    if not corps or (x0 is None and x1 is None):
        return None
    fixe = lambda e: float(e.get("modules") or 1.0) * MODULE_M
    restes = [e for e in corps if e.get("reste")]
    if x0 is not None and x1 is not None and restes:
        part = (x1 - x0 - sum(fixe(e) for e in corps if not e.get("reste"))) / len(restes)
        if part < RESTE_MIN_M:
            return None
    else:
        part = None
    largeurs = [(part if part is not None else float(e.get("modules") or RESTE_SEUL_M / MODULE_M) * MODULE_M) if e.get("reste") else fixe(e)
                for e in corps]
    depart = x0 if x0 is not None else x1 - sum(largeurs)
    sortie, x = [], depart
    for e, large in zip(corps, largeurs):
        debut, fin = max(x, 0.0), min(x + large, longueur)
        x += large
        if e["sorte"] == "vide" or fin - debut < RESTE_MIN_M:
            continue
        if sortie and sortie[-1]["sorte"] == e["sorte"] and abs(sortie[-1]["fin"] - debut) < 1e-6:  # deux colonnes qui se suivent : un meuble
            sortie[-1]["fin"] = fin
            sortie[-1]["numeros"] += list(e.get("numeros") or [])
        else:
            sortie.append({"sorte": e["sorte"], "debut": debut, "fin": fin, "numeros": list(e.get("numeros") or [])})
    return sortie or None


AVANCE_MAX_M = 0.15


def _sortir_du_mur(m: dict, n: np.ndarray, murs: list) -> None:
    """Le contour d'une pièce ne suit pas toujours le nu de ses murs au centimètre (un doublage, une gaine) : un élément rangé
    qui mord dans le mur de son dos est avancé vers la pièce, de ce qu'il faut (zéro collision), au plus de 15 cm."""
    from moteur import collisions as co

    total = 0.0
    for _ in range(4):
        pire = None
        for _, r, _ in murs:
            p = co.penetration(co.rect_du_meuble(m), r)
            if p is not None and p[0] > co.EPS and float(p[1] @ n) > 0.7 and (pire is None or p[0] > pire):
                pire = p[0]
        if pire is None or total + pire + co.JEU > AVANCE_MAX_M:
            return
        total += pire + co.JEU
        m["position"] = [round(float(m["position"][0] + n[0] * (pire + co.JEU)), 3), round(float(m["position"][1] + n[1] * (pire + co.JEU)), 3)]


def _note(d: dict) -> tuple:
    suite = d["suite"]
    return (sum(1 for e in (suite[0], suite[-1]) if e["sorte"] in ANCRES), sum(1 for e in suite if e["sorte"] in ELEMENTS))


def poser(declarations: list[dict], logement: dict, plan: dict, journal=lambda *_: None) -> dict:
    """`declarations` : [{"photo" (son nom), "cam", "mur", "suite", "boites" {numéro: rectangle}, "couleurs" {numéro: [r, v, b]}}].
    Rend {"meubles": les éléments rangés, "pris": {(photo, numéro)} — les rectangles qu'il ne faut plus poser un par un}.
    Quand plusieurs photos disent le même mur, la suite la mieux calée (deux coins, puis le plus d'éléments) est rangée."""
    from moteur import collisions as co

    toutes = faces(logement)
    murs = co.murs_solides(logement)
    par_mur: dict[tuple, list[tuple[dict, dict]]] = {}
    for d in declarations:
        f = mur_designe(d["mur"], d["boites"], d["cam"], plan, logement, toutes)
        if f is None:
            journal(f"  rangée de {d['photo']} : mur introuvable sur le plan ({d['mur']['repere']} {d['mur']['numero']})")
            continue
        par_mur.setdefault((f["piece"], f["rang"]), []).append((d, f))
    meubles, pris = [], set()
    for (piece, _), liste in par_mur.items():
        for d, f in sorted(liste, key=lambda df: _note(df[0]), reverse=True):
            L = float(np.linalg.norm(f["b"] - f["a"]))
            ranges = ranger(d["suite"], L)
            if ranges is None:
                continue
            sens = sens_de_l_image(f, d["cam"])
            depart, e = (f["a"], (f["b"] - f["a"]) / L) if sens > 0 else (f["b"], (f["a"] - f["b"]) / L)
            n = f["normale"]
            for r in ranges:
                profondeur, hauteur = ELEMENTS[r["sorte"]]
                centre = depart + e * (r["debut"] + r["fin"]) / 2 + n * (profondeur / 2 + JEU_M)
                m = {"id": f"rangee_{len(meubles) + 1}", "categorie": r["sorte"], "piece": piece,
                     "position": [round(float(centre[0]), 3), round(float(centre[1]), 3)],
                     "face": round(math.degrees(math.atan2(float(n[1]), float(n[0]))), 1),
                     "dimensions": [round(r["fin"] - r["debut"] - 0.01, 2), profondeur, hauteur], "statut": "estime",
                     "source": f"{SOURCE} ({d['photo']})", "confiance": 0.6}
                teintes = [d["couleurs"][k] for k in r["numeros"] if d.get("couleurs", {}).get(k) is not None]
                if teintes and r["sorte"] != "refrigerateur":
                    m["couleur"] = [int(round(float(np.mean([t[c] for t in teintes])))) for c in range(3)]
                _sortir_du_mur(m, n, murs)
                meubles.append(m)
            journal(f"  rangée du mur de {piece} (dite par {d['photo']}, {L:.2f} m) : "
                    + ", ".join(f"{r['sorte']} {r['fin'] - r['debut']:.2f} m" for r in ranges))
            # tous les rectangles que les photos rattachent à ce mur sont rangés : aucun n'est posé une seconde fois
            for autre, _ in liste:
                pris.update((autre["photo"], int(k)) for el in autre["suite"] for k in el.get("numeros") or [])
            break
    return {"meubles": meubles, "pris": pris}
