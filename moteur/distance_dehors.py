"""DISTANCE des immeubles d'en face, mesurée seule sur les photos du client (cinématique, étape 6, 13/11/2026).

Pourquoi : la toile de la vraie vue (moteur/vue_dehors.py) était posée à 35 m pour tout le monde, distance réglée à la main
sur app-002. Sa distance règle la vitesse à laquelle les immeubles d'en face glissent quand la caméra marche, et l'endroit où
deux photos se raccordent. Règle 21 : le bon résultat doit sortir seul.

Méthode « les étages d'en face » : un étage d'immeuble mesure ~3 m (HAUTEUR_ETAGE_M). On connaît la caméra de chaque photo
(place, cap, focale : moteur/camera_photo.py). Pour une distance D essayée, on sait donc de combien de pixels descendre pour
passer d'un étage à l'étage du dessous, colonne par colonne. On fait glisser l'image de la vue d'un étage vers le bas : à la
bonne distance, les rangées de fenêtres retombent sur les rangées de fenêtres (accord = corrélation des traits horizontaux).

Ce que la mesure regarde : les traits HORIZONTAUX (haut et bas des fenêtres, balcons), contraste égalisé (vitre dépolie d'un
garde-corps), SANS les lignes continues sur toute la largeur d'une bande (barres, lisses, cadres : notre propre façade) et
sans ce qui est notre façade (barre d'appui à ~1 m d'une porte-fenêtre, haut des garde-corps des balcons).

Prudence (essais sur app-002, 13/11/2026) : une mesure n'est retenue que si la même photo donne la même distance (à 10 %
près) dans DEUX bandes qui ne se recouvrent pas (le même immeuble mesuré deux fois). Sinon le côté reste « non mesuré » et
garde la distance par défaut. Raison : avec ~2 étages visibles, une façade qui alterne balcons et fenêtres tous les
demi-étages donne une mesure fausse mais sûre d'elle (chambre 14 : 47 m pour ~20 m), et une petite fenêtre vue de loin donne
de faux immeubles à 9 m. Des photos différentes voient presque toujours des immeubles différents (seconde méthode « accord
des photos » essayée : aucun accord exploitable sur app-002), d'où l'accord demandé DANS une photo.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from moteur import vue_dehors

VERSION = "0.1.0"
HAUTEUR_ETAGE_M = 3.0  # d'un plancher au suivant (immeubles français : 2,8 à 3,3 m)
D_MIN_M, D_MAX_M, N_DISTANCES = 8.0, 120.0, 200  # distances essayées (de la face extérieure de notre mur), pas régulier en log
BORNES_M = (12.0, 80.0)  # distance retenue bornée (une erreur au-delà serait pire que la valeur par défaut)
LARGEUR_REF_PX = 1206.0  # les tailles en pixels ci-dessous valent pour une photo de cette largeur
BANDE_PX = 120  # largeur d'une bande de colonnes ; bandes posées tous les BANDE_PX / 2
LARGEUR_MIN_PX = 30  # largeur moyenne de vue dans la bande (une lamelle de fenêtre au bord de la photo ne mesure rien)
PIX_MIN = 1500  # pixels de vue minimum dans une bande, et en commun entre la bande et elle-même un étage plus bas
RECOUVREMENT_MIN = 0.35  # part de la bande retrouvée un étage plus bas (sinon la comparaison est du hasard : faux 9-14 m)
RECOUVREMENT_DOUBLE_MIN = 0.20  # idem deux étages plus bas (contrôle fait seulement si la fenêtre en montre assez)
ACCORD_MIN = 0.20  # corrélation minimale à la distance trouvée
DETACHE_MIN = 0.15  # et de combien elle doit dépasser la corrélation habituelle de la bande (médiane des distances essayées)
ETAGES_MIN = 1.5  # étages visibles dans la bande à la distance trouvée
ECART_ACCORD = 0.10  # deux bandes d'une même photo « d'accord » : distances à 10 % près
MARGE_BARRES_PX = 8  # marge (verticale) autour des barres et lisses de notre façade
SECOND_AVIS_PIX = 800  # pixels de la photo B qui voient l'endroit mesuré par A
SECOND_AVIS_RECOUVREMENT = 0.15  # part retrouvée un étage plus bas (plus petite admise : l'endroit est déjà désigné par A)
ECART_MARCHE = 0.15  # deux endroits mesurés à moins de 15 % l'un de l'autre = la même « marche » du décor
POIDS_QUALITE = vue_dehors.POIDS_QUALITE


def distances_essayees() -> np.ndarray:
    return np.exp(np.linspace(math.log(D_MIN_M), math.log(D_MAX_M), N_DISTANCES))


def _barres_de_notre_facade(c3: np.ndarray, d: np.ndarray, ouvertures: list[dict], balcons) -> np.ndarray:
    """Pour chaque rayon (directions d, N × 3, depuis c3) : passe-t-il sur une barre de NOTRE façade ? Lisse et barre
    basse d'un garde-corps de balcon (de hauteur − 0,30 m à hauteur + 0,10 m), barre d'appui d'une porte-fenêtre ou d'une
    fenêtre basse (0,80 à 1,20 m, dans la largeur de l'ouverture). Ces traits horizontaux, tout près, tromperaient la mesure."""
    sur = np.zeros(len(d), bool)
    for b in balcons or []:
        gc = b.get("garde_corps") or {}
        h = float(gc.get("hauteur", 1.0))
        for pa, pb in gc.get("cotes", []):
            pa, pb = np.asarray(pa, float), np.asarray(pb, float)
            seg = pb - pa
            den = d[:, 0] * seg[1] - d[:, 1] * seg[0]
            ok = np.abs(den) > 1e-9
            den = np.where(ok, den, 1.0)
            w = pa - c3[:2]
            t = (w[0] * seg[1] - w[1] * seg[0]) / den
            s = (w[0] * d[:, 1] - w[1] * d[:, 0]) / den
            z = c3[2] + t * d[:, 2]
            sur |= ok & (t > 0) & (s >= -0.02) & (s <= 1.02) & (z > h - 0.30) & (z < h + 0.10)
    for o in ouvertures:
        if o["z0"] >= 0.9:
            continue  # fenêtre à allège : pas de barre d'appui
        dn = d[:, :2] @ o["n"]
        devant = dn > 1e-6
        long = float(np.linalg.norm(o["b"] - o["a"]))
        t_ax = (o["b"] - o["a"]) / long
        for face in (-o["epaisseur"] / 2, o["epaisseur"] / 2):
            t = (float(o["a"] @ o["n"]) + face - float(c3[:2] @ o["n"])) / np.where(devant, dn, 1.0)
            z = c3[2] + t * d[:, 2]
            le_long = (c3[:2][None, :] + t[:, None] * d[:, :2] - o["a"]) @ t_ax
            dedans = (le_long > -0.05) & (le_long < long + 0.05)
            sur |= devant & dedans & (z > 0.80) & (z < 1.20)
    return sur


def _traits_horizontaux(image_rvb: np.ndarray, vue: np.ndarray) -> np.ndarray:
    """Traits horizontaux de la photo (dérivée verticale de la clarté), contraste égalisé dans la vue : une façade vue à
    travers une vitre dépolie compte autant qu'une façade vue à travers la vitre claire."""
    gris = cv2.cvtColor(image_rvb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gy = cv2.Sobel(cv2.GaussianBlur(gris, (0, 0), 1.2), cv2.CV_32F, 0, 1, ksize=3)
    v = vue.astype(np.float32)
    rms = np.sqrt(cv2.GaussianBlur(gy * gy * v, (0, 0), 15) / np.maximum(cv2.GaussianBlur(v, (0, 0), 15), 1e-3))
    return gy / (rms + 3.0)


def _accord(G: np.ndarray, vue: np.ndarray, vs: np.ndarray, us: np.ndarray, a: np.ndarray, decalage_px: np.ndarray,
            n_min: float) -> float | None:
    """Corrélation entre les traits de la bande et ceux de la même bande décalée vers le bas de `decalage_px` (par pixel).
    None si la partie commune est trop petite."""
    h = G.shape[0]
    v2 = vs + decalage_px
    v2i = np.floor(v2).astype(int)
    fr = v2 - v2i
    ok = v2i + 1 < h
    v2i = np.clip(v2i, 0, h - 2)
    ok &= (vue[v2i, us] > 0) & (vue[v2i + 1, us] > 0)
    if ok.sum() < n_min:
        return None
    b = (G[v2i, us] * (1 - fr) + G[v2i + 1, us] * fr)[ok]
    aa = a[ok]
    return float((aa * b).sum() / math.sqrt(float((aa * aa).sum() * (b * b).sum()) + 1e-12))


def preparer_vue(image_rvb: np.ndarray, cam, toile: dict, ouvertures: list[dict], murs=None, caches=(), balcons=None):
    """Ce qu'une photo voit d'un côté, prêt à mesurer : pixels de vue (sans notre façade), leurs rayons, traits horizontaux.
    None si la photo ne voit pas assez ce côté."""
    h, w = image_rvb.shape[:2]
    k = w / LARGEUR_REF_PX
    ouv = [o for o in ouvertures if o["id"] in toile["fenetres"]]
    if not ouv:
        return None
    vue, _ = vue_dehors.masque_fenetres(cam, (w, h), ouv, murs, caches, balcons=balcons)
    # bord de la vue rogné de 3 px seulement (pas de la marge du décor, liée au calage : elle mangeait la moitié de la petite
    # fenêtre de la cuisine d'app-002) ; un calage approximatif décale l'image entière, pas l'écart entre deux étages
    marge = max(1, int(round(3 * k)))
    vue = cv2.erode(vue, np.ones((2 * marge + 1, 2 * marge + 1), np.uint8))
    if vue.sum() < PIX_MIN * k * k:
        return None
    vs, us = np.nonzero(vue)
    d = vue_dehors._rayons(cam, us.astype(float), vs.astype(float))
    c3 = np.array(cam[:3], float)
    barres = np.zeros_like(vue)
    sur = _barres_de_notre_facade(c3, d, ouv, balcons)
    barres[vs[sur], us[sur]] = 1
    mb = max(1, int(round(MARGE_BARRES_PX * k)))
    barres = cv2.dilate(barres, np.ones((2 * mb + 1, 1), np.uint8))
    dn = d[:, :2] @ toile["n"]
    garde = (barres[vs, us] == 0) & (dn > 0.05)
    vue[vs[~garde], us[~garde]] = 0
    vs, us, d, dn = vs[garde], us[garde], d[garde], dn[garde]
    if len(vs) < PIX_MIN * k * k:
        return None
    return {"vue": vue, "vs": vs, "us": us, "d": d, "dn": dn, "G0": _traits_horizontaux(image_rvb, vue), "cam": cam,
            "k": k, "h": h, "w": w, "mur": float(toile["decalage"] - toile["distance"]),
            "cn": float(c3[:2] @ toile["n"]), "n": np.asarray(toile["n"], float), "u": np.asarray(toile["u"], float)}


def _sans_lignes_continues(ctx: dict, sel: np.ndarray):
    """Traits de la région `sel` sans les lignes continues sur toute la région (barres, lisses, cadres, toits : elles ne
    disent rien des étages)."""
    bv, bu = ctx["vs"][sel], ctx["us"][sel]
    G0 = ctx["G0"]
    somme = np.zeros(ctx["h"], np.float64)
    compte = np.zeros(ctx["h"], np.float64)
    np.add.at(somme, bv, G0[bv, bu])
    np.add.at(compte, bv, 1.0)
    G = np.zeros_like(G0)
    G[bv, bu] = G0[bv, bu] - (somme / np.maximum(compte, 1.0))[bv]
    return G, bv, bu, G[bv, bu].astype(np.float64)


def _sur_le_decor(ctx: dict, sel: np.ndarray, D: float) -> tuple[np.ndarray, np.ndarray]:
    """Où les pixels `sel` tombent sur un décor à D : position le long de la rue (u) et hauteur (z)."""
    t = (ctx["mur"] + D - ctx["cn"]) / ctx["dn"][sel]
    c3 = np.array(ctx["cam"][:3], float)
    p = c3[None, :] + t[:, None] * ctx["d"][sel]
    return p[:, :2] @ ctx["u"], p[:, 2]


def mesurer_photo(image_rvb: np.ndarray, cam, toile: dict, ouvertures: list[dict], murs=None, caches=(), balcons=None,
                  ecart_px: float = 3.0, ctx: dict | None = None) -> list[dict]:
    """Mesures d'une photo pour un côté (`toile` : une toile de vue_dehors.facades) : une par bande de colonnes où les étages
    d'en face se retrouvent. Chaque mesure : {colonne0, colonne1, distance_m, accord, detache, etages, pixels, pas_px,
    u0, u1 (l'endroit de la rue mesuré, le long du décor), z0, z1}."""
    if ctx is None:
        ctx = preparer_vue(image_rvb, cam, toile, ouvertures, murs, caches, balcons)
    if ctx is None:
        return []
    k, w = ctx["k"], ctx["w"]
    vs, us, dn = ctx["vs"], ctx["us"], ctx["dn"]
    mur, cn, f = ctx["mur"], ctx["cn"], float(cam[5])
    Ds = distances_essayees()
    bande = max(8, int(round(BANDE_PX * k)))
    mesures = []
    for b0 in range(0, w, bande // 2):
        m = (us >= b0) & (us < b0 + bande)
        n = int(m.sum())
        if n < PIX_MIN * k * k:
            continue
        if n / max(1, len(np.unique(vs[m]))) < LARGEUR_MIN_PX * k:
            continue
        G, bv, bu, a = _sans_lignes_continues(ctx, m)
        bdn = dn[m]
        n1 = max(PIX_MIN * k * k, RECOUVREMENT_MIN * n)
        n2 = max(1000 * k * k, RECOUVREMENT_DOUBLE_MIN * n)
        accords = np.full(len(Ds), np.nan)
        for i, D in enumerate(Ds):
            t = (mur + D - cn) / bdn  # profondeur (le long de l'axe de l'appareil) du point de la toile vu par chaque pixel
            pas = f * HAUTEUR_ETAGE_M / t
            un = _accord(G, ctx["vue"], bv, bu, a, pas, n1)
            if un is None:
                continue
            deux = _accord(G, ctx["vue"], bv, bu, a, 2 * pas, n2)
            # deux étages plus bas aussi (quand la fenêtre en montre assez) : écarte les traits qui ne se répètent qu'une fois
            accords[i] = un if deux is None else min(un, (un + deux) / 2)
        valides = np.isfinite(accords)
        if valides.sum() < 10:
            continue
        i = int(np.nanargmax(accords))
        detache = float(accords[i] - np.median(accords[valides]))
        if accords[i] < ACCORD_MIN or detache < DETACHE_MIN:
            continue
        t = (mur + Ds[i] - cn) / bdn
        pas = float(np.median(f * HAUTEUR_ETAGE_M / t))
        etages = float(np.percentile(bv, 97) - np.percentile(bv, 3)) / pas
        if etages < ETAGES_MIN:
            continue
        ub, zb = _sur_le_decor(ctx, m, float(Ds[i]))
        mesures.append({"colonne0": int(b0), "colonne1": int(min(w, b0 + bande)), "distance_m": round(float(Ds[i]), 2),
                        "accord": round(float(accords[i]), 3), "detache": round(detache, 3), "etages": round(etages, 2),
                        "pixels": n, "pas_px": round(pas, 1), "ligne0": int(bv.min()), "ligne1": int(bv.max()),
                        "u0": round(float(np.percentile(ub, 3)), 2), "u1": round(float(np.percentile(ub, 97)), 2),
                        "z0": round(float(np.percentile(zb, 3)), 2), "z1": round(float(np.percentile(zb, 97)), 2)})
    return mesures


def second_avis(mesure: dict, ctx_b: dict) -> dict | None:
    """Une AUTRE photo voit-elle, au même endroit de la rue, les étages à la même distance ? On prend les pixels de la photo B
    qui tombent sur l'endroit mesuré par A (à la distance de A), on y cherche la distance des étages entre 0,55 et 1,8 fois
    celle de A, avec une partie commune plus petite admise (SECOND_AVIS_RECOUVREMENT : l'endroit est déjà désigné par A).
    Confirmée si la meilleure distance de B est à ECART_ACCORD près de celle de A, avec un accord >= ACCORD_MIN.
    Renvoie {distance_m, accord, pixels} ou None (rien à comparer, ou désaccord)."""
    D = float(mesure["distance_m"])
    ub, zb = _sur_le_decor(ctx_b, np.ones(len(ctx_b["vs"]), bool), D)
    sel = (ub > mesure["u0"]) & (ub < mesure["u1"]) & (zb > mesure["z0"]) & (zb < mesure["z1"])
    k = ctx_b["k"]
    if sel.sum() < SECOND_AVIS_PIX * k * k:
        return None
    G, bv, bu, a = _sans_lignes_continues(ctx_b, sel)
    bdn = ctx_b["dn"][sel]
    f = float(ctx_b["cam"][5])
    Ds = distances_essayees()
    Ds = Ds[(Ds > 0.55 * D) & (Ds < 1.8 * D)]
    n1 = max(SECOND_AVIS_PIX * k * k * 0.75, SECOND_AVIS_RECOUVREMENT * len(bv))
    accords = np.full(len(Ds), np.nan)
    for i, D2 in enumerate(Ds):
        t = (ctx_b["mur"] + D2 - ctx_b["cn"]) / bdn
        r = _accord(G, ctx_b["vue"], bv, bu, a, f * HAUTEUR_ETAGE_M / t, n1)
        accords[i] = np.nan if r is None else r
    if not np.isfinite(accords).any():
        return None
    i = int(np.nanargmax(accords))
    if accords[i] < ACCORD_MIN or abs(math.log(Ds[i] / D)) > math.log(1 + ECART_ACCORD):
        return None
    return {"distance_m": round(float(Ds[i]), 2), "accord": round(float(accords[i]), 3), "pixels": int(sel.sum())}


def confirmees(mesures: list[dict]) -> list[dict]:
    """Les mesures d'UNE photo confirmées par une autre bande de la même photo qui ne la recouvre pas (le même immeuble
    mesuré à deux endroits de la fenêtre) à ECART_ACCORD près."""
    res = []
    for m in mesures:
        for autre in mesures:
            if autre is m or autre["colonne0"] < m["colonne1"] and m["colonne0"] < autre["colonne1"]:
                continue
            if abs(math.log(autre["distance_m"] / m["distance_m"])) <= math.log(1 + ECART_ACCORD):
                res.append(m)
                break
    return res


def _retenues(p: dict) -> list[dict]:
    """Mesures retenues d'une photo : confirmées dans la photo (confirmees) ou par le second avis d'une autre photo."""
    meme = {id(m) for m in confirmees(p["mesures"])}
    return [m for m in p["mesures"] if id(m) in meme or m.get("confirmee_par")]


def choisir(par_photo: dict[str, dict]) -> dict:
    """Distance(s) d'un côté à partir des mesures de chaque photo ({nom: {"mesures": [...], "qualite": …}}).

    MARCHES : les mesures retenues regroupées par distance (à ECART_MARCHE près) ; chaque marche = un endroit de la rue
    (u0..u1 le long du décor) et sa distance (moyenne en 1/D : la vitesse de glissement des immeubles quand on marche est en
    1/D), pondérée par l'accord, la taille de la bande et la qualité du calage de la photo ; bornée à BORNES_M.
    distance_m : une seule distance pour tout le côté (même moyenne sur toutes les mesures retenues), pour un décor d'un seul
    tenant. Aucune mesure retenue : non mesurée."""
    retenues = []
    for nom, p in par_photo.items():
        for m in _retenues(p):
            retenues.append((nom, m, m["accord"] * m["pixels"] * POIDS_QUALITE.get(p.get("qualite", "bonne"), 0.5)))
    if not retenues:
        return {"distance_m": None, "statut": "non_mesuree", "marches": [],
                "raison": "aucun immeuble mesuré deux fois (même photo, ou autre photo au même endroit)", "retenues": []}

    def moyenne(rs):
        poids = np.array([r[2] for r in rs])
        inv = np.array([1.0 / r[1]["distance_m"] for r in rs])
        return float(1.0 / (poids @ inv / poids.sum()))

    d = moyenne(retenues)
    groupes: list[list] = []
    for r in sorted(retenues, key=lambda r: r[1]["distance_m"]):
        if groupes and r[1]["distance_m"] <= moyenne(groupes[-1]) * (1 + ECART_MARCHE):
            groupes[-1].append(r)
        else:
            groupes.append([r])
    marches = []
    for g in groupes:
        marches.append({"distance_m": round(float(np.clip(moyenne(g), *BORNES_M)), 1),
                        "u0": round(min(r[1]["u0"] for r in g), 2), "u1": round(max(r[1]["u1"] for r in g), 2),
                        "photos": sorted({r[0] for r in g} | {r[1]["confirmee_par"] for r in g if r[1].get("confirmee_par")})})
    marches.sort(key=lambda m: (m["u0"] + m["u1"]) / 2)
    return {"distance_m": round(float(np.clip(d, *BORNES_M)), 1), "statut": "mesuree", "brute_m": round(d, 1),
            "etendue_m": [round(min(r[1]["distance_m"] for r in retenues), 1),
                          round(max(r[1]["distance_m"] for r in retenues), 1)],
            "marches": marches,
            "retenues": [{"photo": r[0], "colonnes": [r[1]["colonne0"], r[1]["colonne1"]], "distance_m": r[1]["distance_m"],
                          "accord": r[1]["accord"], "confirmee_par": r[1].get("confirmee_par", r[0])} for r in retenues]}


def mesurer_logement(logement: dict, photos: list[dict]) -> dict[str, dict]:
    """Distance de chaque côté du logement qui a des fenêtres. `photos` : [{nom, image (RVB), cam, qualite, caches,
    ecart_px}]. Renvoie {id du côté : choisir(...) + "par_photo": {nom: mesures}}. Une mesure seule dans sa photo est
    soumise au second avis des autres photos qui voient le même endroit de la rue (second_avis)."""
    ouv = vue_dehors.ouvertures_vitrees(logement)
    murs = vue_dehors.murs_et_trous(logement)
    res = {}
    for toile in vue_dehors.facades(logement, vue_dehors.DISTANCE_M):
        ctxs, par_photo = {}, {}
        for ph in photos:
            ctx = preparer_vue(ph["image"], ph["cam"], toile, ouv, murs, ph.get("caches", ()), logement.get("balcons"))
            if ctx is None:
                continue
            ctxs[ph["nom"]] = ctx
            ms = mesurer_photo(ph["image"], ph["cam"], toile, ouv, murs, ctx=ctx)
            if ms:
                par_photo[ph["nom"]] = {"mesures": ms, "qualite": ph.get("qualite", "bonne")}
        for nom, p in par_photo.items():
            deja = {id(m) for m in confirmees(p["mesures"])}
            for m in p["mesures"]:
                if id(m) in deja:
                    continue
                for autre, ctx in ctxs.items():
                    if autre == nom:
                        continue
                    avis = second_avis(m, ctx)
                    if avis is not None:
                        m["confirmee_par"] = autre
                        m["second_avis"] = avis
                        break
        r = choisir(par_photo)
        r["par_photo"] = {k: v["mesures"] for k, v in par_photo.items()}
        res[toile["id"]] = r
    return res


def dessiner(image_rvb: np.ndarray, mesures: list[dict], cam) -> np.ndarray:
    """La photo assombrie, et dans chaque bande mesurée les étages trouvés (traits espacés d'un étage) : vert = confirmée,
    orange = seule (non retenue). Pour montrer à l'œil ce qu'Atelya a compté."""
    out = (image_rvb.astype(np.float32) * 0.55).astype(np.uint8)
    ok = {id(m) for m in confirmees(mesures)} | {id(m) for m in mesures if m.get("confirmee_par")}
    v0 = float(cam[7])
    for m in mesures:
        couleur = (40, 220, 60) if id(m) in ok else (255, 150, 0)
        x0, x1 = m["colonne0"] + 4, m["colonne1"] - 4
        for j in range(-40, 41):
            v = int(round(v0 + j * m["pas_px"]))
            if m["ligne0"] <= v <= m["ligne1"]:
                cv2.line(out, (x0, v), (x1, v), couleur, 2)
        cv2.putText(out, f"{m['distance_m']:.0f} m", (x0, max(18, m["ligne0"] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)
    return out
