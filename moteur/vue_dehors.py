"""La VRAIE VUE par les fenêtres, tirée des photos du client (cinématique, étape 5, 12-13/11/2026).

Pourquoi : la maquette n'a rien autour du logement ; par les fenêtres du film on ne voit qu'un sol gris et un ciel pâle. Une rue
inventée est exclue (ce ne serait pas la vue du logement : risque de tromper l'acheteur). Les photos du client, elles, montrent
le vrai dehors (immeubles d'en face, arbres) par leurs fenêtres.

Méthode (« décor » de cinéma, demandée par NT le 12/11/2026 : un vrai objet posé dehors dans la maquette) :
- chaque CÔTÉ de l'immeuble qui a des fenêtres (murs dont le dehors regarde la même direction) reçoit une grande toile verticale,
  parallèle à la façade, à la distance des immeubles d'en face (`distance`), du niveau de la rue jusqu'au-dessus des toits ;
- pour chaque point de la toile, on cherche les photos qui le VOIENT par une fenêtre : la caméra de la photo est connue
  (moteur/camera_photo.py), le point est vu si sa projection tombe dans l'ouverture projetée (faces intérieure ET extérieure du
  trou dans le mur, un peu rétrécies pour ne pas prendre le cadre) ; sa couleur est celle de la photo à cet endroit ;
- plusieurs photos voient le même point : la mieux placée l'emporte (cœur de sa fenêtre, calage, netteté), couture courte ;
- CLARTÉ : le dehors s'affiche dans le film COMME SUR LA PHOTO (choix du photographe de l'annonce), teinte neutralisée sur le
  mur de la photo (bande de mur autour de ses fenêtres). On en déduit la couleur qu'il faut AVANT la pellicule d'Unreal (prise
  à l'envers, couleurs comprises : sans cela elle délave et désature tout ce qui est plus clair que les murs, essais du
  12/11/2026) ; dans Unreal, la toile la donne quelle que soit l'exposition de la caméra ;
- ce qu'aucune photo ne montre : la vraie vue y est PROLONGÉE EN FLOU (couleurs voisines, de plus en plus floues en s'éloignant,
  comme un dehors hors de la mise au point), sans objet inventé. Avant (12/11/2026) la toile y était transparente : des
  morceaux de vue flottaient dans le blanc (« collage », avis de NT), et ce blanc délavait toute la fenêtre.

Repère d'Atelya : mètres, x, y du plan, z vers le haut, 0 = sol du logement.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from moteur import camera_photo

DISTANCE_M = 35.0  # distance des immeubles d'en face, par défaut (pour un côté que moteur/distance_dehors.py ne sait pas mesurer
# sur les photos, étape 6 du 13/11/2026). app-002 (12/11/2026) : ~20 m pour le plus proche, ~55 m pour
# les plus lointains (hauteur des étages sur les photos 14 et 15), ~29 m côté ouest (photo 8) ; à 40 m la vue rendue depuis la
# place de la photo 15 retrouve sa composition, à 21 m les photos se mêlaient mal. Seul le décalage en marchant en dépend.
PAS_M = 0.03  # taille d'un point de la toile (une photo d'annonce donne ~3 cm par pixel à cette distance)
Z_BAS_M = -6.0  # la toile part du NIVEAU DE LA RUE (logement supposé au 2e étage, comme le sol du dehors d'Unreal) : en dessous,
# c'est la rue elle-même, un sol horizontal entre notre façade et les immeubles d'en face (NT, 13/11/2026 : « le décor à une
# distance plus juste » ; une toile descendue à -40 m mettait la rue sur un mur vertical à 35 m)
Z_HAUT_M = 26.0
ETENDUE_M = 25.0  # la toile dépasse le logement de chaque côté d'au moins ETENDUE_M et de 2 × sa distance (vues en biais)
RETRAIT_M = 0.12  # l'ouverture est rétrécie d'autant (dormant et ouvrant de la vraie fenêtre : 0,07 laissait le rail du haut)
MARGE_PX = 4.0  # marge (pixels) retirée en plus autour de ce qu'une photo voit dehors, + MARGE_PAR_ECART × l'écart de son calage
MARGE_PAR_ECART = 2.0
DEMI_MONTANT_M = 0.07  # demi-largeur d'un montant de la vraie fenêtre (profils coulissants)
FONDU_PX = 25.0  # fondu des bords de l'ouverture sur la photo (pixels d'une photo de 1206 px de large)
COUTURE_M = 0.25  # largeur du fondu entre deux photos sur la toile
FONDU_TOILE_M = 0.5  # fondu de la toile vers « rien » là où aucune photo ne voit
FORCE_TOILE = 10.0  # l'image de la toile garde (clarté avant pellicule) / FORCE_TOILE ; Unreal multiplie par FORCE_TOILE
BLANC_AFFICHE_MAX = 0.97  # un dehors plus clair est affiché à 0,97 (clarté avant pellicule ~9,4 < FORCE_TOILE)
LOGO = (0.22, 0.08)  # coins de la photo écartés (marque de l'annonce) : part de la largeur, part de la hauteur
POIDS_QUALITE = {"bonne": 1.0, "moyenne": 0.6, "approchée": 0.35, "approchee": 0.35}
GENRES_VITRES = ("fenetre", "porte_fenetre", "baie")


def _lineaire(srgb: np.ndarray) -> np.ndarray:
    s = srgb.astype(np.float32) / 255.0
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def _srgb(lin: np.ndarray) -> np.ndarray:
    lin = np.clip(lin, 0.0, 1.0)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return np.round(s * 255.0).astype(np.uint8)


def _dans(point, pieces) -> bool:
    from moteur.sol_a_plat import piece_de
    return piece_de(point, pieces) is not None


def ouvertures_vitrees(logement: dict) -> list[dict]:
    """Fenêtres et portes-fenêtres : bouts sur l'axe du mur, normale vers le DEHORS (côté sans pièce), épaisseur, hauteurs."""
    murs = {m["id"]: m for m in logement["murs"]}
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    res = []
    for o in logement.get("ouvertures", []):
        if o.get("type") not in GENRES_VITRES or o.get("mur") not in murs:
            continue
        m = murs[o["mur"]]
        a, b = np.array(m["debut"], float), np.array(m["fin"], float)
        long = float(np.linalg.norm(b - a))
        if long < 1e-6:
            continue
        t = (b - a) / long
        n = np.array([t[1], -t[0]])
        milieu = a + t * (float(o["position"]) + float(o["largeur"]) / 2)
        dedans_plus = _dans(milieu + 0.45 * n, logement["pieces"])
        dedans_moins = _dans(milieu - 0.45 * n, logement["pieces"])
        if dedans_plus and not dedans_moins:
            n = -n
        elif dedans_plus == dedans_moins:
            continue  # fenêtre entre deux pièces, ou mur mal placé : pas de dehors connu
        z0 = float(o.get("allege", 0.0) or 0.0)
        res.append({"id": o["id"], "mur": o["mur"], "a": a + t * float(o["position"]),
                    "b": a + t * (float(o["position"]) + float(o["largeur"])), "n": n,
                    "epaisseur": float(m.get("epaisseur", 0.2)), "z0": z0,
                    "z1": min(z0 + float(o.get("hauteur", 2.15)), hsp)})
    return res


def _bout_vers(f: dict, g: dict) -> bool:
    """La toile f est-elle le bout de son côté tourné vers le côté de g (là où les deux côtés se rencontrent) ?"""
    mu = float(g["n"] @ f["u"])
    return f.get("bout1", True) if mu > 0 else f.get("bout0", True)


def facades(logement: dict, distances: dict | float | None = None, marches: dict | None = None) -> list[dict]:
    """Les toiles : une par direction de dehors (normales à moins de 20° regroupées). `distances` : {id: m} ou un nombre.
    Chaque toile : normale `n` (vers le dehors), axe horizontal `u` (la droite de qui regarde dehors), `decalage` (le plan est
    {p : p·n = decalage}), étendue [u0, u1] × [z0, z1] ; les toiles voisines se coupent à leur rencontre (coin de rue).

    `marches` ({id du côté : [{u0, u1, distance_m}, …]}, moteur/distance_dehors.py, étape 6 du 13/11/2026) : quand un côté a
    des immeubles à plusieurs distances (app-002 sud : un immeuble proche à ~24 m, des lointains à ~44 m), son décor SUIT LA
    RUE : une toile droite par endroit mesuré, à sa distance (id « facade-sud-1 », « -3 »… ; « cote » = le côté), et entre deux
    endroits mesurés une toile EN BIAIS qui les relie (« facade-sud-2 », « biais »). Les photos voient ce pan en biais et le
    peignent ; une marche franche (joint perpendiculaire, essai du 13/11/2026) n'était vue par aucune photo : bande unie au
    milieu de la vue du séjour."""
    ouv = ouvertures_vitrees(logement)
    groupes: list[list[dict]] = []
    for o in ouv:
        for g in groupes:
            if float(g[0]["n"] @ o["n"]) > math.cos(math.radians(20)):
                g.append(o)
                break
        else:
            groupes.append([o])
    tous = np.array([pt for p in logement["pieces"] for pt in p["contour"]], float)
    res = []
    for g in groupes:
        n = np.mean([o["n"] for o in g], axis=0)
        n /= np.linalg.norm(n)
        ident = "facade-" + "nord ouest sud est".split()[int(((math.degrees(math.atan2(n[1], n[0])) - 90) % 360 + 45) // 90) % 4]
        d = distances.get(ident, DISTANCE_M) if isinstance(distances, dict) else (distances or DISTANCE_M)
        mur = max(float(o["a"] @ n) + o["epaisseur"] / 2 for o in g)
        u = np.array([n[1], -n[0]])
        proj = tous @ u
        ms = sorted((marches or {}).get(ident) or [], key=lambda m: (m["u0"] + m["u1"]) / 2)
        if len(ms) < 2:
            ms = [{"distance_m": float(d)}]
        dmax = max(float(m["distance_m"]) for m in ms)
        u0_cote = float(proj.min() - max(ETENDUE_M, 2 * dmax))
        u1_cote = float(proj.max() + max(ETENDUE_M, 2 * dmax))
        # bouts des toiles droites : chaque endroit mesuré garde sa distance sur toute sa largeur ; entre deux endroits, le
        # pan en biais (s'ils se touchent ou se chevauchent : pan de 1 m centré entre leurs milieux)
        fins, debuts = [], []
        for a, b in zip(ms, ms[1:]):
            if a["u1"] < b["u0"] - 1.0:
                fins.append(float(a["u1"]))
                debuts.append(float(b["u0"]))
            else:
                mi = ((a["u0"] + a["u1"]) / 2 + (b["u0"] + b["u1"]) / 2) / 2
                fins.append(float(mi - 0.5))
                debuts.append(float(mi + 0.5))
        droites = []
        for k, m in enumerate(ms):
            dk = float(m["distance_m"])
            droites.append({"cote": ident, "n": n, "u": u, "distance": dk, "decalage": mur + dk,
                            "u0": u0_cote if k == 0 else debuts[k - 1], "u1": u1_cote if k == len(ms) - 1 else fins[k],
                            "z0": Z_BAS_M, "z1": Z_HAUT_M, "fenetres": [o["id"] for o in g],
                            "bout0": k == 0, "bout1": k == len(ms) - 1})
        cote = []
        for k, t in enumerate(droites):
            cote.append(t)
            if k + 1 < len(droites):
                b = droites[k + 1]
                A = n * t["decalage"] + u * t["u1"]
                B = n * b["decalage"] + u * b["u0"]
                axe = (B - A) / np.linalg.norm(B - A)
                nb = np.array([axe[1], -axe[0]])
                if nb @ n < 0:
                    nb = -nb
                cote.append({"cote": ident, "biais": True, "n": nb, "u": axe, "decalage": float(nb @ A),
                             "u0": float(A @ axe), "u1": float(B @ axe),
                             "distance": round((t["distance"] + b["distance"]) / 2, 2),
                             "distances": [t["distance"], b["distance"]], "z0": Z_BAS_M, "z1": Z_HAUT_M,
                             "fenetres": [o["id"] for o in g], "bout0": False, "bout1": False,
                             # sa rue : le rectangle du côté, de notre façade jusqu'au plus loin des deux toiles
                             "rue": {"n": n, "u": u, "mur": mur, "u0": t["u1"], "u1": b["u0"],
                                     "profondeur": max(t["distance"], b["distance"])}})
        for k, t in enumerate(cote):
            t["id"] = ident if len(cote) == 1 else f"{ident}-{k + 1}"
        res.extend(cote)
    for f in res:  # coin de rue : le bout de chaque côté s'arrête sur le bout de l'autre côté (du côté du logement)
        for g in res:
            if g.get("cote") == f.get("cote"):
                continue
            mu = float(g["n"] @ f["u"])
            if abs(mu) < 1e-3 or not _bout_vers(f, g) or not _bout_vers(g, f):
                continue
            borne = (g["decalage"] - f["decalage"] * float(g["n"] @ f["n"])) / mu
            if mu > 0:
                f["u1"] = min(f["u1"], borne)
            else:
                f["u0"] = max(f["u0"], borne)
    for f in res:
        base = f["n"] * f["decalage"] + f["u"] * f["u0"]
        f.update({"genre": "immeubles", "origine": np.array([base[0], base[1], f["z1"]]),
                  "axe_u": np.array([f["u"][0], f["u"][1], 0.0]), "axe_v": np.array([0.0, 0.0, -1.0]),
                  "longueur_u": f["u1"] - f["u0"], "longueur_v": f["z1"] - f["z0"]})
    return res


def rues(toiles: list[dict]) -> list[dict]:
    """La RUE devant chaque côté : un sol horizontal au niveau de la rue (Z_BAS_M), du pied de notre façade jusqu'au pied de
    sa toile (les immeubles d'en face). Image : colonnes le long de la façade (comme la toile), lignes en s'éloignant. Au coin,
    la rue du premier côté va jusqu'à la toile de l'autre ; celle de l'autre s'arrête au pied de notre façade (pas de
    recouvrement)."""
    res = []
    toiles = [t for t in toiles if t.get("genre", "immeubles") == "immeubles"]
    for i, f in enumerate(toiles):
        if f.get("biais"):
            r = f["rue"]
            base = r["n"] * r["mur"] + r["u"] * r["u0"]
            res.append({"id": f["id"].replace("facade-", "rue-"), "cote": f["cote"], "genre": "rue", "n": r["n"], "u": r["u"],
                        "distance": r["profondeur"], "decalage": r["mur"] + r["profondeur"], "u0": r["u0"], "u1": r["u1"],
                        "z0": Z_BAS_M, "z1": Z_BAS_M, "fenetres": f["fenetres"],
                        "origine": np.array([base[0], base[1], Z_BAS_M]),
                        "axe_u": np.array([r["u"][0], r["u"][1], 0.0]), "axe_v": np.array([r["n"][0], r["n"][1], 0.0]),
                        "longueur_u": r["u1"] - r["u0"], "longueur_v": r["profondeur"]})
            continue
        mur = f["decalage"] - f["distance"]
        u0, u1 = f["u0"], f["u1"]
        for j, g in enumerate(toiles):
            if g is f or g.get("cote") == f.get("cote", f["id"]) and g.get("cote") is not None:
                continue
            mu = float(g["n"] @ f["u"])
            if abs(mu) < 1e-3 or not _bout_vers(f, g) or not _bout_vers(g, f):
                continue
            limite = g["decalage"] if j > i else g["decalage"] - g["distance"]
            borne = (limite - mur * float(g["n"] @ f["n"])) / mu
            if mu > 0:
                u1 = min(u1, borne)
            else:
                u0 = max(u0, borne)
        base = f["n"] * mur + f["u"] * u0
        res.append({"id": f["id"].replace("facade-", "rue-"), "cote": f.get("cote", f["id"]), "genre": "rue",
                    "n": f["n"], "u": f["u"],
                    "distance": f["distance"], "decalage": f["decalage"], "u0": u0, "u1": u1, "z0": Z_BAS_M, "z1": Z_BAS_M,
                    "fenetres": f["fenetres"], "origine": np.array([base[0], base[1], Z_BAS_M]),
                    "axe_u": np.array([f["u"][0], f["u"][1], 0.0]), "axe_v": np.array([f["n"][0], f["n"][1], 0.0]),
                    "longueur_u": u1 - u0, "longueur_v": f["distance"]})
    return res


def points_toile(f: dict, pas: float = PAS_M) -> tuple[np.ndarray, int, int]:
    """Points 3D (H, L, 3) au centre de chaque point de l'image d'un plan (toile des immeubles ou rue) : origine = coin de
    l'image (ligne 0, colonne 0), colonnes le long de `axe_u`, lignes le long de `axe_v`."""
    largeur = max(1, int(math.ceil(f["longueur_u"] / pas)))
    hauteur = max(1, int(math.ceil(f["longueur_v"] / pas)))
    a = (np.arange(largeur) + 0.5) * pas
    b = (np.arange(hauteur) + 0.5) * pas
    P = (np.asarray(f["origine"], np.float32)[None, None, :] + a[None, :, None] * np.asarray(f["axe_u"], np.float32)
         + b[:, None, None] * np.asarray(f["axe_v"], np.float32))
    return P.astype(np.float32), largeur, hauteur


def projeter_tableau(P: np.ndarray, cam) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """projeter() de camera_photo, pour un tableau de points (…, 3)."""
    x, y, z, cap, tangage, f, u0, v0 = cam
    vue, droite, haut = camera_photo.axes(cap, tangage)
    r = P - np.array([x, y, z], np.float32)
    p = r @ vue.astype(np.float32)
    ps = np.where(p > 1e-3, p, 1e-3)
    return u0 + f * (r @ droite.astype(np.float32)) / ps, v0 - f * (r @ haut.astype(np.float32)) / ps, p


def _quad(o: dict, decalage: float, retrait: float) -> np.ndarray:
    """Les 4 coins 3D de l'ouverture, rétrécie de `retrait`, sur le plan du mur décalé de `decalage` le long de la normale."""
    t = (o["b"] - o["a"]) / np.linalg.norm(o["b"] - o["a"])
    a = o["a"] + t * retrait + o["n"] * decalage
    b = o["b"] - t * retrait + o["n"] * decalage
    z0, z1 = o["z0"] + retrait, o["z1"] - retrait
    return np.array([[a[0], a[1], z0], [b[0], b[1], z0], [b[0], b[1], z1], [a[0], a[1], z1]], np.float32)


def murs_et_trous(logement: dict) -> list[tuple[np.ndarray, np.ndarray, list[tuple[float, float]]]]:
    """Chaque mur (bouts sur son axe) et ses trous (portes, fenêtres : intervalles le long du mur), pour savoir si un mur se
    trouve entre l'appareil d'une photo et une fenêtre."""
    trous: dict[str, list] = {}
    for o in logement.get("ouvertures", []):
        trous.setdefault(o.get("mur"), []).append((float(o["position"]), float(o["position"]) + float(o["largeur"])))
    return [(np.array(m["debut"], float), np.array(m["fin"], float), trous.get(m["id"], [])) for m in logement["murs"]]


def _rayons(cam, us: np.ndarray, vs: np.ndarray) -> np.ndarray:
    """Directions 3D (N, 3) des pixels (us, vs) de la photo."""
    x, y, z, cap, tangage, f, u0, v0 = cam
    vue, droite, haut = camera_photo.axes(cap, tangage)
    return vue[None, :] + ((us - u0) / f)[:, None] * droite[None, :] - ((vs - v0) / f)[:, None] * haut[None, :]


def _bloques(c: np.ndarray, q: np.ndarray, murs, propre: int | None) -> np.ndarray:
    """Pour chaque point q (N, 2) : un mur plein (hors de ses trous) coupe-t-il le segment appareil c -> q ? (le mur de la
    fenêtre elle-même, d'indice `propre`, est ignoré)."""
    bloque = np.zeros(len(q), bool)
    d = q - c[None, :]
    for i, (a, b, trous) in enumerate(murs):
        if i == propre:
            continue
        e = b - a
        longueur = float(np.linalg.norm(e))
        if longueur < 1e-6:
            continue
        den = d[:, 0] * e[1] - d[:, 1] * e[0]
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1.0)
        w = a - c
        s = (w[0] * e[1] - w[1] * e[0]) / den  # le long du segment appareil -> q
        t = (w[0] * d[:, 1] - w[1] * d[:, 0]) / den  # le long du mur (0..1)
        coupe = ok & (s > 0.02) & (s < 0.995) & (t >= 0) & (t <= 1)
        if trous and coupe.any():
            le_long = t * longueur
            for g, h in trous:
                coupe &= ~((le_long > g + 0.02) & (le_long < h - 0.02))
        bloque |= coupe
    return bloque


def _bandes_montants(o: dict) -> list[tuple[float, float]]:
    """Montants de la VRAIE fenêtre à retirer de la photo (la maquette a les siens) : le milieu d'une fenêtre à deux vantaux,
    les tiers d'une baie de plus de 2,5 m (trois vantaux coulissants) ; intervalles le long de l'ouverture, en mètres."""
    largeur = float(np.linalg.norm(o["b"] - o["a"]))
    if largeur < 1.0:
        return []
    positions = [largeur / 2] + ([largeur / 3, 2 * largeur / 3] if largeur > 2.5 else [])
    return [(p - DEMI_MONTANT_M, p + DEMI_MONTANT_M) for p in positions]


def _remplir_quad(q: np.ndarray, cam, taille) -> np.ndarray:
    largeur, hauteur = taille
    u, v, _ = projeter_tableau(q, cam)
    un = np.zeros((hauteur, largeur), np.uint8)
    cv2.fillPoly(un, [np.round(np.stack([u, v], 1) * 4).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=2)
    return un


def _dans_polygone(x: np.ndarray, y: np.ndarray, contour) -> np.ndarray:
    dedans = np.zeros(x.shape, bool)
    pts = [tuple(map(float, q)) for q in contour]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        coupe = (y1 > y) != (y2 > y)
        xc = x1 + (y - y1) * (x2 - x1) / np.where(coupe, y2 - y1, 1.0)
        dedans ^= coupe & (x < xc)
    return dedans


def touche_un_balcon(c3: np.ndarray, d: np.ndarray, balcons, hauteur_etage: float = 2.5) -> np.ndarray:
    """Pour chaque rayon (origine c3, directions d : N × 3), touche-t-il un BALCON (sa dalle, un garde-corps plein ou un mur de
    côté) ? Ce que la photo montre là est le balcon, construit dans la maquette : il ne doit pas partir au loin sur le décor."""
    touche = np.zeros(len(d), bool)
    for b in balcons or []:
        niveau = float(b.get("niveau", -0.05))
        descend = d[:, 2] < -1e-6
        t = np.where(descend, (niveau - c3[2]) / np.where(descend, d[:, 2], -1.0), -1.0)
        px, py = c3[0] + t * d[:, 0], c3[1] + t * d[:, 1]
        touche |= (t > 0) & _dans_polygone(px, py, b["contour"])
        gc = b.get("garde_corps") or {}
        # un garde-corps en VERRE ou à BARREAUX laisse voir le dehors (sur la photo, la rue est derrière lui) : seuls un
        # garde-corps plein et les murs de côté cachent la vue (essai du 13/11/2026 : tout retirer vidait la vue du séjour)
        parois = [(q, float(gc.get("hauteur", 1.0))) for q in gc.get("cotes", [])] if gc.get("genre") == "plein" else []
        parois += [(q, hauteur_etage) for q in b.get("joues", [])]
        for (a, e), h in parois:
            a, e = np.asarray(a, float), np.asarray(e, float)
            seg = e - a
            den = d[:, 0] * seg[1] - d[:, 1] * seg[0]
            ok = np.abs(den) > 1e-9
            den = np.where(ok, den, 1.0)
            w = a - c3[:2]
            tr = (w[0] * seg[1] - w[1] * seg[0]) / den
            s_ = (w[0] * d[:, 1] - w[1] * d[:, 0]) / den
            z = c3[2] + tr * d[:, 2]
            touche |= ok & (tr > 0) & (s_ >= 0) & (s_ <= 1) & (z >= niveau - 0.2) & (z <= niveau + h)
    return touche


def masque_fenetres(cam, taille: tuple[int, int], ouvertures: list[dict], murs=None, caches=(),
                    retrait: float = RETRAIT_M, balcons=None) -> tuple[np.ndarray, np.ndarray]:
    """Masques (H, L) des pixels de la photo par où l'on voit DEHORS : (vue, ouvertures). « ouvertures » : ouvertures projetées,
    faces intérieure ET extérieure du trou (le tableau de la fenêtre cache le reste), sans les pixels où un mur plein se trouve
    entre l'appareil et la fenêtre (`murs`, murs_et_trous) ; « vue » : la même chose sans les montants de la vraie fenêtre,
    sans les rectangles `caches` (meubles devant la fenêtre : [x0, y0, x1, y1] en pixels), ni la marque de l'annonce, ni ce qui
    est un BALCON (`balcons` du logement : construits dans la maquette, touche_un_balcon)."""
    largeur, hauteur = taille
    total = np.zeros((hauteur, largeur), np.uint8)
    montants = np.zeros((hauteur, largeur), np.uint8)
    c = np.array(cam[:2], float)
    for o in ouvertures:
        if float((c - o["a"]) @ o["n"]) > -o["epaisseur"] / 2 - 0.05:
            continue  # l'appareil est dans l'embrasure ou dehors : cette ouverture ne lui montre pas le dehors
        m = None
        for face in (-o["epaisseur"] / 2, o["epaisseur"] / 2):
            q = _quad(o, face, retrait)
            if np.any(projeter_tableau(q, cam)[2] <= 0.05):
                m = None
                break
            un = _remplir_quad(q, cam, taille)
            m = un if m is None else (m & un)
        if m is None or not m.any():
            continue
        if murs is not None:
            vs, us = np.nonzero(m)
            d = _rayons(cam, us.astype(float), vs.astype(float))
            den = d[:, :2] @ o["n"]
            s = (float(o["a"] @ o["n"]) - float(c @ o["n"])) / np.where(np.abs(den) > 1e-9, den, 1e-9)
            q2 = c[None, :] + s[:, None] * d[:, :2]
            propre = next((i for i, (a, b, _) in enumerate(murs)
                           if abs(float((o["a"] - a) @ o["n"])) < 1e-3 and abs(float((b - a) @ o["n"])) < 1e-3), None)
            bloque = _bloques(c, q2, murs, propre)
            m[vs[bloque], us[bloque]] = 0
        total |= m
        t = (o["b"] - o["a"]) / np.linalg.norm(o["b"] - o["a"])
        for g, h in _bandes_montants(o):
            bo = {**o, "a": o["a"] + t * g, "b": o["a"] + t * h}
            for face in (-o["epaisseur"] / 2, o["epaisseur"] / 2):
                montants |= _remplir_quad(_quad(bo, face, 0.0), cam, taille)
    vue = total & (1 - montants)
    if balcons and vue.any():
        vs, us = np.nonzero(vue)
        d = _rayons(cam, us.astype(float), vs.astype(float))
        b = touche_un_balcon(np.array(cam[:3], float), d, balcons)
        vue[vs[b], us[b]] = 0
    for x0, y0, x1, y1 in caches:
        vue[max(0, int(y0)):int(math.ceil(y1)), max(0, int(x0)):int(math.ceil(x1))] = 0
    lx, ly = int(LOGO[0] * largeur), int(LOGO[1] * hauteur)
    for x0, y0 in ((0, 0), (largeur - lx, 0), (0, hauteur - ly), (largeur - lx, hauteur - ly)):
        vue[y0:y0 + ly, x0:x0 + lx] = 0
    return vue, total


def blanc_des_murs(image_lin: np.ndarray, masque: np.ndarray, caches=()) -> np.ndarray | None:
    """Couleur (linéaire) du MUR autour des fenêtres de la photo : bande de 12 à 60 px autour des ouvertures, moitié la plus
    claire (le mur blanc ; écarte rideaux, meubles, ombres), médiane par canal."""
    if not masque.any():
        return None
    k = max(3, int(round(image_lin.shape[1] / 1206 * 60)))
    pres = cv2.dilate(masque, np.ones((12, 12), np.uint8))
    loin = cv2.dilate(masque, np.ones((k, k), np.uint8))
    bande = (loin > 0) & (pres == 0)
    for x0, y0, x1, y1 in caches:
        bande[max(0, int(y0)):int(math.ceil(y1)), max(0, int(x0)):int(math.ceil(x1))] = False
    px = image_lin[bande]
    if len(px) < 200:
        return None
    lum = px @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    garde = px[lum >= np.percentile(lum, 50)]
    return np.median(garde, axis=0)


def couleur_avant_pellicule(cible: np.ndarray, iterations: int = 14) -> np.ndarray:
    """Couleurs linéaires (avant pellicule, N × 3) qu'Unreal affiche comme `cible` (N × 3, affichage sRVB de 0 à 1) : la
    pellicule complète d'Unreal (moteur/pellicule_unreal.affiche, réglages du film) prise à l'envers, pas à pas. Sans cela, la
    pellicule désature les clairs : tout le dehors (plus clair que les murs) sortait GRIS, arbres compris (essai du 12/11)."""
    from moteur import pellicule_unreal, photographe
    cible = np.clip(np.asarray(cible, float).reshape(-1, 3), 0.0, BLANC_AFFICHE_MAX)
    voulu = photographe.lineaire_affiche(cible)
    e = voulu.copy()
    for _ in range(iterations):
        a = pellicule_unreal.affiche(e, photographe.PELLICULE, **photographe.PELLICULE_COULEURS)
        obtenu = photographe.lineaire_affiche(np.clip(a, 0.0, 0.999))
        e = np.clip(e * (voulu / np.maximum(obtenu, 1e-6)) ** 0.8, 1e-5, FORCE_TOILE)
    return e.astype(np.float32)


def clarte_avant_pellicule(image_rvb: np.ndarray, blanc_lin: np.ndarray, clarte: float, masque=None,
                           regle: str = "photo") -> np.ndarray:
    """Pour chaque pixel de la photo (seulement ceux du `masque` s'il est donné, 0 ailleurs), la couleur (avant pellicule,
    linéaire) qu'il faut à Unreal pour l'afficher comme voulu, la pellicule d'Unreal prise à l'envers (couleur_avant_pellicule).
    Règle « photo » (défaut, 13/11/2026) : le dehors s'affiche COMME SUR LA PHOTO du client (le choix de son photographe), teinte
    du mur de la photo neutralisée. Règle « murs » (essai du 12/11) : le mur de la photo devient le mur du film (`clarte`) et le
    dehors garde sa place entre le mur et le blanc : les murs du film étant plus clairs que ceux d'une photo d'annonce, le
    dehors était poussé vers le blanc et perdait son contraste."""
    from moteur import photographe
    v = image_rvb.astype(np.float32) / 255.0
    mur_photo = _srgb(np.asarray(blanc_lin, np.float32)).astype(np.float32) / 255.0
    if regle == "murs":
        mur_film = float(photographe.courbe_unreal(np.array([clarte]), **photographe.PELLICULE)[0])
        dessous = v * (mur_film / np.maximum(mur_photo, 1e-3))
        dessus = 1.0 - (1.0 - v) * ((1.0 - mur_film) / np.maximum(1.0 - mur_photo, 1e-3))
        voulu = np.where(v <= mur_photo, dessous, dessus)
    else:
        voulu = v * (float(mur_photo.mean()) / np.maximum(mur_photo, 1e-3))
    sortie = np.zeros_like(v)
    garde = np.ones(v.shape[:2], bool) if masque is None else masque > 0
    sortie[garde] = couleur_avant_pellicule(voulu[garde])
    return sortie


def preparer_photo(image_rvb: np.ndarray, cam, ouvertures: list[dict], qualite: str = "bonne", murs=None,
                   caches=(), clarte: float = 1.0, ecart_px: float = 3.0, balcons=None) -> dict | None:
    """Ce qu'une photo apporte : clarté avant pellicule de chaque pixel (clarte_avant_pellicule, murs du film à `clarte`), poids
    par pixel (fondu au bord de ce qu'elle voit dehors × qualité du calage). None si la photo ne voit aucune fenêtre."""
    h, w = image_rvb.shape[:2]
    vue, ouv = masque_fenetres(cam, (w, h), ouvertures, murs, caches, balcons=balcons)
    # plus le calage de la photo est incertain (écart moyen de ses repères), plus on ne garde que le CŒUR de ses fenêtres : un
    # calage à 10 px près peignait sur la vue des bouts de cadre, de mur et d'interrupteur (essai du 12/11/2026)
    marge = int(round((MARGE_PX + MARGE_PAR_ECART * float(ecart_px)) * w / 1206.0))
    if marge > 0:
        vue = cv2.erode(vue, np.ones((2 * marge + 1, 2 * marge + 1), np.uint8))
    if vue.sum() < 500:
        return None
    blanc = blanc_des_murs(_lineaire(image_rvb), ouv, caches)
    if blanc is None:
        return None
    fondu = FONDU_PX * w / 1206.0
    dist = cv2.distanceTransform(vue, cv2.DIST_L2, 5)
    poids = np.clip(dist / fondu, 0.0, 1.0) * POIDS_QUALITE.get(qualite, 0.5)
    garde = cv2.dilate(vue, np.ones((5, 5), np.uint8))
    return {"cam": cam, "image": clarte_avant_pellicule(image_rvb, blanc, clarte, garde), "poids": poids.astype(np.float32),
            "masque": vue, "blanc": [round(float(x), 4) for x in blanc]}


def echantillonner(photo: dict, P: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Couleur et poids de la photo pour chaque point P de la toile (poids 0 : la photo ne le voit pas)."""
    u, v, p = projeter_tableau(P, photo["cam"])
    mx, my = u.astype(np.float32), v.astype(np.float32)
    couleur = cv2.remap(photo["image"], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    poids = cv2.remap(photo["poids"], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    poids = np.where(p > 0.3, poids, 0.0).astype(np.float32)
    return couleur, poids


def _remplir(couleur: np.ndarray, poids: np.ndarray) -> np.ndarray:
    """Couleur étendue sous les trous (pyramide « push-pull ») : le bord de la toile, qui s'efface en fondu, garde la couleur
    de ce qu'il prolonge au lieu de virer au noir."""
    niveaux = []
    c, w = couleur * poids[..., None], poids.copy()
    while min(w.shape) > 4:
        niveaux.append((c, w))
        c = cv2.pyrDown(c)
        w = cv2.pyrDown(w)
    moyenne = c.reshape(-1, 3).sum(0) / max(float(w.sum()), 1e-6)
    # au niveau le plus grossier, une case que rien n'atteint prend la couleur moyenne (elle restait NOIRE : bande sombre au
    # bout de la toile sud, vu le 13/11/2026)
    a = np.clip(w / 0.25, 0.0, 1.0)[..., None]
    rempli = (c / np.maximum(w, 1e-6)[..., None]) * a + moyenne[None, None, :] * (1 - a)
    for c, w in reversed(niveaux):
        haut = cv2.resize(rempli, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR)
        a = np.clip(w / 0.25, 0.0, 1.0)[..., None]
        rempli = (c / np.maximum(w, 1e-6)[..., None]) * a + haut * (1 - a)
    return rempli


def caches_par_les_marches(P: np.ndarray, cam, ecrans) -> np.ndarray:
    """Pour chaque point P (H, L, 3) d'une toile : une toile PLUS PROCHE du même côté (`ecrans`, décor en marches) se
    trouve-t-elle entre l'appareil de la photo et P ? Ce que la photo montre là est l'immeuble proche : il ne doit pas être
    peint sur l'immeuble lointain."""
    c = np.array(cam[:3], np.float32)
    r = P - c
    cache = np.zeros(P.shape[:2], bool)
    for g in ecrans:
        n3 = np.array([g["n"][0], g["n"][1], 0.0], np.float32)
        u3 = np.array([g["u"][0], g["u"][1], 0.0], np.float32)
        den = r @ n3
        t = (float(g["decalage"]) - float(c @ n3)) / np.where(np.abs(den) > 1e-6, den, 1e-6)
        q = c + t[..., None] * r
        uq, zq = q @ u3, q[..., 2]
        cache |= (t > 0) & (t < 0.999) & (uq >= g["u0"]) & (uq <= g["u1"]) & (zq >= g["z0"]) & (zq <= g["z1"])
    return cache


def composer(f: dict, photos: list[dict], pas: float = PAS_M, remplir: bool = True, defaut=None, ecrans=()) -> dict:
    """L'image de la toile `f` : RVBA (sRVB 8 bits ; RVB = clarté avant pellicule / FORCE_TOILE ; A = la toile est vue par au
    moins une photo, fondu vers « rien » ailleurs), la part de la toile couverte et la part prise à chaque photo.

    En chaque point, UNE photo : celle qui le voit le mieux (au cœur de sa fenêtre, bien calée, la plus NETTE : le plus de pixels
    par mètre de toile) ; couture courte (COUTURE_M) entre deux photos. Une moyenne de photos prises de plusieurs endroits
    doublait les immeubles (la toile n'est qu'à peu près à leur distance) et délavait la vue (essais du 12/11/2026)."""
    P, largeur, hauteur = points_toile(f, pas)
    vues = []
    for ph in photos:
        c, w = echantillonner(ph, P)
        if ecrans and float(w.max()) > 0:
            w = np.where(caches_par_les_marches(P, ph["cam"], ecrans), 0.0, w).astype(np.float32)
        if float(w.max()) <= 0:
            continue
        _, _, prof = projeter_tableau(P, ph["cam"])
        nettete = float(ph["cam"][5]) / np.maximum(prof, 0.5)  # pixels de la photo par mètre de toile
        vues.append((ph.get("nom"), c, w, w * nettete))
    if not vues:
        image = np.zeros((hauteur, largeur, 4), np.uint8)
        if remplir and defaut is not None:  # aucune photo ne voit ce plan : couleur unie `defaut` (avant pellicule)
            image[..., :3] = _srgb(np.asarray(defaut, np.float32) / FORCE_TOILE)[None, None, :]
            image[..., 3] = 255
        return {"rvba": image, "largeur": largeur, "hauteur": hauteur, "couverte": 0.0, "parts": {}, "_couleur": None}
    notes = np.stack([v[3] for v in vues])
    gagnant = notes.argmax(0)
    vu = notes.max(0) > 0
    sigma = max(1.0, COUTURE_M / pas / 2)
    somme = np.zeros((hauteur, largeur, 3), np.float32)
    total = np.zeros((hauteur, largeur), np.float32)
    parts = {}
    for i, (nom, c, w, _) in enumerate(vues):
        choisi = ((gagnant == i) & vu).astype(np.float32)
        parts[nom] = round(float(choisi.sum() / max(vu.sum(), 1)), 3)
        doux = cv2.GaussianBlur(choisi, (0, 0), sigma) * (w > 0)
        somme += c * doux[..., None]
        total += doux
    couleur = somme / np.maximum(total, 1e-6)[..., None]
    rempli = _remplir(couleur, (total > 1e-3).astype(np.float32))
    k = max(1, int(round(FONDU_TOILE_M / pas)))
    # OPAQUE partout où une photo voit (une toile à demi transparente laissait passer le blanc d'avant : voile laiteux, vu le
    # 12/11/2026), fondu vers « rien » au-delà, sur FONDU_TOILE_M
    loin = cv2.distanceTransform((~vu).astype(np.uint8), cv2.DIST_L2, 5)
    alpha = np.ones_like(loin) if remplir else np.clip(1.0 - loin / k, 0.0, 1.0)
    rvba = np.dstack([_srgb(rempli / FORCE_TOILE), np.round(alpha * 255).astype(np.uint8)])
    return {"rvba": rvba, "largeur": largeur, "hauteur": hauteur, "couverte": round(float(vu.mean()), 4), "parts": parts,
            "_couleur": rempli, "_vu": vu}


def couleur_de_la_rue(toile: dict, r: dict) -> np.ndarray:
    """Couleur unie (avant pellicule) de la rue devant une toile : médiane de ce que les photos montrent dans les 2 m du bas de
    la toile (pied des immeubles d'en face, trottoir, bas des arbres) ; à défaut, de tout ce qu'elles montrent."""
    vu, c = r.get("_vu"), r.get("_couleur")
    if vu is None or not vu.any():
        return np.array([0.18, 0.18, 0.18], np.float32)
    lignes = int(round(2.0 / (toile["longueur_v"] / vu.shape[0])))
    bas = vu.copy()
    bas[:-lignes] = False
    choix = bas if bas.sum() > 50 else vu
    m = np.median(c[choix], axis=0)
    # GRIS NEUTRE de même clarté (une chaussée ; la teinte du bas de la vue venait du verre bleuté des garde-corps : rue lavande)
    return np.full(3, float(m @ np.array([0.2126, 0.7152, 0.0722])), np.float32)


FONDU_BAS_M = 1.5  # sous ce que les photos voient, le bas d'une toile passe à la couleur de la rue sur cette hauteur
LARGEUR_BAS_M = 6.0  # la ligne vue la plus basse est prise sur cette largeur de toile (pas colonne par colonne)


def fondre_le_bas(r: dict, toile: dict, couleur_rue) -> dict:
    """Le BAS d'une toile d'immeubles qu'aucune photo ne voit (le pied des immeubles, à hauteur de rue : les photos prises
    d'un étage voient par-dessus le garde-corps) prend la couleur de la rue, en fondu sous la dernière ligne vue de chaque
    colonne. Sinon le prolongement flou de ce qui est vu (souvent le verre bleuté d'un garde-corps) faisait un coin bleuté au
    bord net contre la rue grise, surtout avec un décor qui suit la rue (étape 6, 13/11/2026). Modifie et renvoie `r`."""
    vu, c = r.get("_vu"), r.get("_couleur")
    if vu is None or c is None or not vu.any():
        return r
    hauteur, largeur = vu.shape
    lignes = np.arange(hauteur)
    vues = vu.any(0)
    dernier = np.where(vues, hauteur - 1 - np.argmax(vu[::-1], axis=0), -1).astype(float)
    cols = np.arange(largeur)
    dernier = np.interp(cols, cols[vues], dernier[vues])  # colonnes non vues : comme leurs voisines vues
    pas = toile["longueur_v"] / hauteur
    # la plus basse ligne vue sur LARGEUR_BAS_M de large, adoucie : une colonne étroite vue seulement en haut (derrière un
    # montant de fenêtre, un meuble) faisait sinon un rectangle gris de haut en bas (film du 13/11/2026)
    k_l = max(3, int(round(LARGEUR_BAS_M / pas)) | 1)
    dernier = cv2.dilate(dernier.astype(np.float32)[None, :], np.ones((1, k_l), np.uint8))[0]
    dernier = cv2.GaussianBlur(dernier[None, :], (0, 0), k_l / 4)[0]
    k = max(1.0, FONDU_BAS_M / pas)
    a = np.clip((lignes[:, None] - dernier[None, :]) / k, 0.0, 1.0)[..., None]
    c = c * (1 - a) + np.asarray(couleur_rue, np.float32)[None, None, :] * a
    r["_couleur"] = c.astype(np.float32)
    r["rvba"] = np.dstack([_srgb(c / FORCE_TOILE), r["rvba"][..., 3]])
    return r


def vers_unreal(f: dict) -> dict:
    """Le plan en coordonnées d'Unreal (cm ; X = 100 x, Y = −100 y, Z = 100 z) : coin de l'image (ligne 0, colonne 0), axes de
    l'image (u : colonnes, v : lignes), taille ; normale (face tournée vers le logement pour une toile, vers le ciel pour la rue)."""
    o, au, av = (np.asarray(f[k], float) for k in ("origine", "axe_u", "axe_v"))
    n = np.array([0.0, 0.0, 1.0]) if f.get("genre") == "rue" else np.array([-f["n"][0], -f["n"][1], 0.0])
    unr = lambda v, k=1.0: [k * float(v[0]), -k * float(v[1]), k * float(v[2])]
    return {"coin": unr(o, 100.0), "axe_u": unr(au), "axe_v": unr(av), "normale_vers_logement": unr(n),
            "largeur_cm": 100 * float(f["longueur_u"]), "hauteur_cm": 100 * float(f["longueur_v"])}
