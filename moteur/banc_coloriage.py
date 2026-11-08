"""Banc d'essai du maillon coloriage → logement.json : la note en centimètres.

Pour chaque plan d'un jeu du générateur, on traduit un coloriage en logement.json
(moteur.coloriage) et on le compare à la vérité (logement_niveauN.json et
geometrie.json, écrits par le générateur au moment de dessiner le plan).

Deux sortes de coloriage :
- « parfait » : le masque exact du générateur (masque_semantique.png). La note
  mesure alors le traducteur seul ;
- « atelya » : le coloriage rendu par Atelya (un PNG par plan, dans un dossier).
  La note mesure toute la chaîne image → mesures.

Le coloriage est mis à la taille vue par Atelya (grand côté 768 px).

    uv run python -m moteur.banc_coloriage sorties/jeu-10000 --partie test --sortie sorties/banc-coloriage
    uv run python -m moteur.banc_coloriage sorties/jeu-10000 --coloriages coloriages-atelya/ ...
    uv run python -m moteur.banc_coloriage sorties/jeu-10000 --coloriages coloriages-atelya/ --noms ...  (noms lus sur le plan)
    uv run python -m moteur.banc_coloriage sorties/jeu-10000 --coloriages coloriages-atelya/ --echelle lue ...  (échelle lue sur les cotes)

Échelle : par défaut (« exacte »), le banc donne au traducteur l'échelle vraie du plan, et pour une
photo de biais les vraies proportions. Avec --echelle lue, elle est lue sur les cotes du dessin
(moteur.echelle_plan) — à défaut, sur la barre d'échelle ou les surfaces écrites des pièces —, comme pour
un vrai client ; un plan sans échelle lisible est compté « à vérifier »
et noté à part (avec l'échelle exacte, pour ne pas mélanger deux défauts).

08/11/2026 (echelle_plan 0.14) : une image à plusieurs blocs de bâti (plusieurs niveaux dessinés côte à côte) est repérée sur le
coloriage BRUT, avant le nettoyage des taches au bord, comme dans moteur.lecture_complete ; le cache des échelles lues garde ce
repérage (`plusieurs_blocs`), et une entrée de cache qui ne correspond pas au repérage du coloriage est relue.

08/11/2026 (moteur.doutes 0.2.0, lecture_complete 0.4.0) : avec --doutes, une telle image reçoit le doute fort « plusieurs_niveaux »,
comme dans moteur.lecture_complete (un seul niveau est lu) : sa décision passe « à vérifier ». Rien d'autre ne change.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from moteur.coloriage import PIECES, lire_coloriage
from moteur.doutes import doute_plusieurs_niveaux, examiner
from moteur.echelle_plan import coloriage_douteux, decider, lire_echelle_plan, plusieurs_blocs, sans_taches_au_bord
from moteur.noms_pieces import lire_textes, noms_depuis_textes
from moteur.redressement import (Redressement, corriger_proportions, estimer_redressement, photo_entiere, rapport_par_optique,
                                 rapport_plausible)

COTE_ATELYA = 768

# Seuils d'un élément « juste » (m).
AXE_JUSTE = 0.05
EPAISSEUR_JUSTE = 0.03
BOUT_JUSTE = 0.10
CENTRE_OUVERTURE = 0.30
LARGEUR_JUSTE = 0.10
IOU_PIECE = 0.5

TYPE_VERS_CLASSE = {"sejour": 5, "principale": 5, "sejour_cuisine": 5, "cuisine": 6, "chambre": 7,
                    "sdb": 8, "sde": 8, "salle_d_eau": 8, "wc": 9, "entree": 10, "degagement": 11, "placard": 12,
                    "buanderie": 13, "bureau": 14, "escalier": 15}
NOM_CLASSE = {c: t for c, (t, _) in PIECES.items()}


# ---------------------------------------------------------------- comparer

def _sens(m: dict) -> tuple[bool, float, float, float]:
    """(horizontal, axe, début, fin) d'un mur droit, début < fin."""
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    if abs(y2 - y1) <= abs(x2 - x1):
        return True, (y1 + y2) / 2, min(x1, x2), max(x1, x2)
    return False, (x1 + x2) / 2, min(y1, y2), max(y1, y2)


def _chaines(murs: list[dict]) -> list[dict]:
    """Regroupe les murs alignés bout à bout (même axe, même épaisseur) en « lignes de murs ».
    Un mur coupé en deux par une cloison qui le croise ou d'un seul tenant donne la même maquette :
    on compare donc des lignes, pas des morceaux."""
    groupes: list[dict] = []
    for m in sorted(murs, key=lambda m: _sens(m)[2]):
        h, axe, d, f = _sens(m)
        for g in groupes:
            if (g["h"] == h and abs(g["axe"] - axe) <= 0.03 and abs(g["ep"] - m["epaisseur"]) <= 0.03
                    and d <= g["fin"] + 0.45):
                g["fin"] = max(g["fin"], f)
                g["ids"].append(m["id"])
                break
        else:
            groupes.append({"h": h, "axe": axe, "ep": m["epaisseur"], "debut": d, "fin": f, "ids": [m["id"]]})
    return groupes


ANGLE_DROIT_MAX = 3.0  # degrés : au-delà, un mur est « libre » (en biais ou morceau d'arrondi), noté à part (A3)


def _est_libre(m: dict) -> bool:
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    a = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 90
    return min(a, 90 - a) > ANGLE_DROIT_MAX


def _groupe_libre(ident: str) -> str:
    """Les petits segments d'un même mur arrondi (« M_arrondi1-0 », « -1 »…) forment un seul mur."""
    return ident.rsplit("-", 1)[0] if "-" in ident else ident


def _distance_segments(p: tuple[float, float], segs: list[dict]) -> tuple[float, float | None]:
    """Distance du point p au plus proche des segments, et l'épaisseur de ce segment."""
    meilleur, ep = float("inf"), None
    for m in segs:
        (ax, ay), (bx, by) = m["debut"], m["fin"]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy or 1e-12
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2))
        d = math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)
        if d < meilleur:
            meilleur, ep = d, m["epaisseur"]
    return meilleur, ep


def comparer_murs_libres(vrais: list[dict], lus: list[dict]) -> tuple[list[dict], int]:
    """A3 : chaque mur vrai en biais ou arrondi est suivi tous les 5 cm le long de son axe ; on cherche
    à quelle distance passe l'axe des murs libres lus. Trouvé : la moitié des points à moins de 15 cm ;
    juste : 90 % des points à moins de AXE_JUSTE + 5 cm, épaisseur à EPAISSEUR_JUSTE près, et toute la
    longueur couverte (bouts compris, à BOUT_JUSTE près). Les murs lus qu'aucun vrai n'explique sont en trop."""
    groupes: dict[str, list[dict]] = {}
    for m in vrais:
        groupes.setdefault(_groupe_libre(m["id"]), []).append(m)
    sortie, utiles = [], set()
    for ident, segs in groupes.items():
        pts = []
        for m in segs:
            (ax, ay), (bx, by) = m["debut"], m["fin"]
            n = max(2, int(math.dist((ax, ay), (bx, by)) / 0.05))
            pts += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n + 1)]
        if not lus:
            sortie.append({"vrai": ident, "trouve": False, "libre": True})
            continue
        res = [_distance_segments(p, lus) for p in pts]
        d = np.array([r[0] for r in res])
        if np.median(d) > 0.15:
            sortie.append({"vrai": ident, "trouve": False, "libre": True})
            continue
        for k, m in enumerate(lus):
            if any(_distance_segments(q, segs)[0] <= 0.15 for q in (m["debut"], m["fin"])):
                utiles.add(k)
        ep_lu = float(np.median([r[1] for r, dd in zip(res, d) if dd <= 0.15]))
        e = {"vrai": ident, "trouve": True, "libre": True, "axe": float(np.percentile(d, 90)),
             "epaisseur": abs(ep_lu - segs[0]["epaisseur"]),
             "bouts": float(max(d[0], d[-1]))}
        e["juste"] = e["axe"] <= AXE_JUSTE + 0.05 and e["epaisseur"] <= EPAISSEUR_JUSTE and e["bouts"] <= BOUT_JUSTE
        sortie.append(e)
    return sortie, len(lus) - len(utiles)


def comparer_murs(vrais: list[dict], lus: list[dict]) -> list[dict]:
    """Chaque mur vrai est noté sur sa ligne de murs : trouvée ou non, écart d'axe, d'épaisseur, de bouts.
    A3 : les murs en biais ou arrondis sont notés à part (comparer_murs_libres) ; sans eux, rien ne change."""
    lv, ll = [m for m in vrais if _est_libre(m)], [m for m in lus if _est_libre(m)]
    if lv or ll:
        droits, trop = comparer_murs([m for m in vrais if not _est_libre(m)], [m for m in lus if not _est_libre(m)])
        libres, trop_l = comparer_murs_libres(lv, ll)
        return droits + libres, trop + trop_l
    cv, cl = _chaines(vrais), _chaines(lus)
    candidats = []
    for i, v in enumerate(cv):
        for j, l in enumerate(cl):
            if v["h"] != l["h"] or abs(v["axe"] - l["axe"]) > 0.15:
                continue
            recouvre = min(v["fin"], l["fin"]) - max(v["debut"], l["debut"])
            if recouvre <= 0.5 * (v["fin"] - v["debut"]) and recouvre <= 0.5 * (l["fin"] - l["debut"]):
                continue
            candidats.append((-recouvre + abs(v["axe"] - l["axe"]), i, j))
    lien, pris = {}, set()
    for _, i, j in sorted(candidats):
        if i in lien or j in pris:
            continue
        lien[i] = j
        pris.add(j)
    sortie = []
    for i, v in enumerate(cv):
        for ident in v["ids"]:
            if i not in lien:
                sortie.append({"vrai": ident, "trouve": False})
                continue
            l = cl[lien[i]]
            e = {"vrai": ident, "trouve": True, "axe": abs(v["axe"] - l["axe"]), "epaisseur": abs(v["ep"] - l["ep"]),
                 "bouts": max(abs(v["debut"] - l["debut"]), abs(v["fin"] - l["fin"]))}
            e["juste"] = e["axe"] <= AXE_JUSTE and e["epaisseur"] <= EPAISSEUR_JUSTE and e["bouts"] <= BOUT_JUSTE
            sortie.append(e)
    return sortie, len(cl) - len(pris)


def _centre_ouverture(o: dict, murs: dict) -> tuple[float, float]:
    m = murs[o["mur"]]
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    L = math.dist(m["debut"], m["fin"]) or 1
    t = (o["position"] + o["largeur"] / 2) / L
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def comparer_ouvertures(vrai: dict, lu: dict) -> list[dict]:
    mv = {m["id"]: m for m in vrai["murs"]}
    ml = {m["id"]: m for m in lu["murs"]}
    lus = [(o, _centre_ouverture(o, ml), _sens(ml[o["mur"]])[0]) for o in lu["ouvertures"]]
    pris, sortie = set(), []
    for o in vrai["ouvertures"]:
        c = _centre_ouverture(o, mv)
        h = _sens(mv[o["mur"]])[0]
        meilleur, d_min = None, CENTRE_OUVERTURE
        for k, (ol, cl, hl) in enumerate(lus):
            d = math.dist(c, cl)
            if k not in pris and hl == h and d <= d_min:
                meilleur, d_min = k, d
        if meilleur is None:
            sortie.append({"vrai": o["id"], "type": o["type"], "trouve": False})
            continue
        pris.add(meilleur)
        ol = lus[meilleur][0]
        e = {"vrai": o["id"], "type": o["type"], "trouve": True, "bon_type": ol["type"] == o["type"],
             "centre": d_min, "largeur": abs(ol["largeur"] - o["largeur"])}
        e["juste"] = e["bon_type"] and e["largeur"] <= LARGEUR_JUSTE and d_min <= LARGEUR_JUSTE
        sortie.append(e)
    return sortie


def _raster(contour, x0, y0, pas, forme) -> np.ndarray:
    m = np.zeros(forme, np.uint8)
    pts = np.array([[(x - x0) / pas, (y - y0) / pas] for x, y in contour], np.float32)
    cv2.fillPoly(m, [np.round(pts * 4).astype(np.int32)], 1, shift=2)
    return m.astype(bool)


def comparer_pieces(vrai: dict, lu: dict, types_vrais: dict[str, int], types_lus: dict[str, str]) -> list[dict]:
    pts = [p for piece in vrai["pieces"] + lu["pieces"] for p in piece["contour"]]
    if not pts:
        return []
    x0, y0 = min(p[0] for p in pts) - 0.1, min(p[1] for p in pts) - 0.1
    x1, y1 = max(p[0] for p in pts) + 0.1, max(p[1] for p in pts) + 0.1
    pas = 0.02
    forme = (int((y1 - y0) / pas) + 2, int((x1 - x0) / pas) + 2)
    rl = [(p, _raster(p["contour"], x0, y0, pas, forme)) for p in lu["pieces"]]
    sortie, pris = [], set()
    for p in vrai["pieces"]:
        rv = _raster(p["contour"], x0, y0, pas, forme)
        meilleur, iou_max = None, IOU_PIECE
        for k, (pl, r) in enumerate(rl):
            if k in pris:
                continue
            inter = (rv & r).sum()
            if not inter:
                continue
            iou = inter / (rv | r).sum()
            if iou >= iou_max:
                meilleur, iou_max = k, iou
        classe = types_vrais.get(p["id"], 5)
        if meilleur is None:
            sortie.append({"vrai": p["id"], "classe": classe, "trouve": False})
            continue
        pris.add(meilleur)
        pl = rl[meilleur][0]
        sv, sl = rv.sum() * pas * pas, rl[meilleur][1].sum() * pas * pas
        bon = TYPE_VERS_CLASSE.get(types_lus.get(pl["id"], ""), -1) == classe
        sortie.append({"vrai": p["id"], "classe": classe, "trouve": True, "iou": float(iou_max), "bon_type": bon,
                       "surface_pct": abs(sl - sv) / sv * 100})
    return sortie


def _hors_tout(log: dict) -> tuple[float, float]:
    """Largeur et profondeur intérieures (cadre des pièces), en m."""
    pts = [p for piece in log["pieces"] for p in piece["contour"]]
    if not pts:
        return 0.0, 0.0
    return max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts)


def comparer(vrai: dict, lu: dict, types_vrais: dict[str, int], types_lus: dict[str, str]) -> dict:
    murs, lignes_en_trop = comparer_murs(vrai["murs"], lu["murs"])
    lv, pv = _hors_tout(vrai)
    ll, pl = _hors_tout(lu)
    return {"murs": murs, "murs_en_trop": lignes_en_trop,
            "ouvertures": comparer_ouvertures(vrai, lu),
            "ouvertures_en_trop": max(0, len(lu["ouvertures"]) - len(vrai["ouvertures"])),
            "pieces": comparer_pieces(vrai, lu, types_vrais, types_lus),
            "hors_tout": max(abs(lv - ll), abs(pv - pl))}


# ---------------------------------------------------------------- un plan

def echelle_pour_atelya(annotations: dict, taille: tuple[int, int]) -> tuple[float, float]:
    """(px par m, facteur de réduction) de l'image mise à la taille vue par Atelya."""
    r = COTE_ATELYA / max(taille)
    return annotations["image"]["px_par_m"] * r, r


def coloriage_parfait(niveau: Path) -> np.ndarray:
    msq = Image.open(niveau / "masque_semantique.png")
    r = COTE_ATELYA / max(msq.size)
    taille = (max(1, round(msq.width * r)), max(1, round(msq.height * r)))
    m = np.array(msq.resize(taille, Image.NEAREST), np.uint8)
    m[m >= 16] = 0
    return m


def echelles_apres_redressement(R: Redressement, annotations: dict, r: float) -> tuple[float, float]:
    """(px par m en largeur, en hauteur) de l'image redressée, d'après la vérité : c'est ce que donneraient
    des cotes parfaitement lues, comme l'échelle exacte donnée aux plans à plat."""
    M = np.array(annotations["image"]["matrice_m_vers_px"], np.float64)  # mètres → pixels du plan entier
    G = R.H @ np.diag([r, r, 1.0]) @ M  # mètres → pixels redressés
    pts = np.array([p for m in annotations["murs"] for p in m["polygone_px"]], np.float64)
    hp = np.c_[pts, np.ones(len(pts))] @ np.linalg.inv(M).T
    cx, cy = (hp[:, :2] / hp[:, 2:]).mean(0)  # le milieu du logement, en mètres
    w = G[2] @ (cx, cy, 1)
    J = (G[:2, :2] * w - np.outer(G[:2] @ (cx, cy, 1), G[2, :2])) / w ** 2
    return float(np.hypot(*J[:, 0])), float(np.hypot(*J[:, 1]))


def dessin_du_niveau(niveau: Path, images: Path | None) -> Path | None:
    """Le dessin qu'Atelya a colorié : plan.png (dessin propre) ou plan.jpg (plan abîmé).
    `images` : dossier « exemples » où se trouvent les dessins, s'ils ne sont pas à côté du niveau."""
    dossier = images / niveau.parent.name / niveau.name if images else niveau
    nom = (niveau / "dessin.txt").read_text(encoding="utf-8").strip() if (niveau / "dessin.txt").exists() else None
    for f in ([dossier / nom] if nom else []) + [dossier / "plan.png", dossier / "plan.jpg"]:
        if f.exists():
            return f
    return None


def textes_du_plan(dessin: Path, cache: Path | None) -> list:
    """Les textes lus sur le dessin (RapidOCR), gardés dans un fichier cache pour les fois suivantes."""
    f = cache / f"{dessin.parent.parent.name}-{dessin.parent.name}.json" if cache else None
    if f and f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    img = np.array(Image.open(dessin).convert("RGB"))
    textes = lire_textes(img)
    if f:
        f.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
    return textes


def textes_pdf(niveau: Path) -> tuple[list, float] | None:
    """Étape A2-6 : les textes exacts d'un plan venu d'un PDF vectoriel (moteur.generateur.plan_pdf.preparer_niveau),
    au format de l'OCR, et les pixels par point PDF ; None si le niveau n'en a pas (image, PDF piégé ou scanné)."""
    f = niveau / "textes-pdf.json"
    if not f.exists():
        return None
    from moteur.lecture_cotes import TexteLu

    d = json.loads(f.read_text(encoding="utf-8"))
    return [TexteLu(t["texte"], np.array(t["boite"], float), 1.0) for t in d["textes"]], d["px_par_pt"]


def echelle_du_plan(niveau: Path, dessin: Path, col: np.ndarray, R: Redressement | None, cache: Path | None,
                    suffixe: str = "", pdf: bool = False, blocs: bool | None = None) -> dict:
    """L'échelle lue sur les cotes du dessin (px par m du coloriage, en largeur et en hauteur), gardée en cache.
    `suffixe` : un coloriage nettoyé (voir sans_taches_au_bord) a son propre fichier cache.
    `blocs` : plusieurs_blocs du coloriage brut (None : calculé sur `col`)."""
    f = cache / f"{niveau.parent.name}-{niveau.name}{suffixe}.json" if cache else None
    if f and f.exists():
        lu = json.loads(f.read_text(encoding="utf-8"))
        if blocs is None or lu.get("plusieurs_blocs", False) == bool(blocs):  # un ancien cache ne connaît pas les blocs : relu s'il le faut
            return lu
    tp = textes_pdf(niveau) if pdf else None
    e = lire_echelle_plan(np.array(Image.open(dessin).convert("L")), col, R,
                          textes=tp[0] if tp else None, px_par_pt=tp[1] if tp else None, blocs=blocs)
    lu = {"largeur": e.largeur, "hauteur": e.hauteur, "sure": e.sure, "cotes": len(e.cotes), "redresse": R is not None,
          "cote_max_largeur": e.cote_max_largeur, "cote_max_hauteur": e.cote_max_hauteur, "interieur_px": e.interieur_px,
          "barre": e.barre, "barre_sure": e.barre_sure, "barre_detail": e.barre_detail,
          "surfaces": e.surfaces, "surfaces_sure": e.surfaces_sure, "surfaces_detail": e.surfaces_detail,
          "approchee": e.approchee, "ecrite": e.ecrite, "ecrite_detail": e.ecrite_detail, "textes_pdf": tp is not None,
          "ambigue": e.ambigue, "plusieurs_blocs": e.plusieurs_blocs, "surfaces_blocs": e.surfaces_blocs}
    if f:
        f.write_text(json.dumps(lu), encoding="utf-8")
    return lu


def noter_niveau(args) -> dict:
    exemple, niveau_nom, fichier_coloriage, *options = args
    redresser, proportions, noms_opt, echelle_opt, doutes_opt = (list(options) + [None, None, None])[:5] if options else (True, "cotes", None, None, None)
    exemple, niveau = Path(exemple), Path(exemple) / niveau_nom
    idx = int(niveau_nom.split("_")[1])
    ann = json.loads((niveau / "annotations.json").read_text(encoding="utf-8"))
    geo = json.loads((exemple / "geometrie.json").read_text(encoding="utf-8"))
    vrai = json.loads((exemple / f"logement_niveau{idx}.json").read_text(encoding="utf-8"))
    taille = (ann["image"]["largeur"], ann["image"]["hauteur"])
    s, _ = echelle_pour_atelya(ann, taille)
    if fichier_coloriage:
        col = np.array(Image.open(fichier_coloriage), np.uint8)
    else:
        col = coloriage_parfait(niveau)
    types_vrais = {p["id"]: TYPE_VERS_CLASSE.get(p["type"], 5) for n in geo["niveaux"] for p in n["pieces"]}
    resultat = {"plan": exemple.name, "niveau": idx, "perspective": float(ann["image"].get("perspective", 0) or 0),
                "rotation": float(ann["image"].get("rotation_deg", 0) or 0)}
    nettoye = False
    blocs = plusieurs_blocs(col)  # sur le coloriage brut, avant le nettoyage (voir moteur.lecture_complete)
    if blocs:
        resultat["plusieurs_blocs"] = True
    if fichier_coloriage and coloriage_douteux(col):
        propre = sans_taches_au_bord(col)  # taches au bord de l'image, séparées du logement (table, bord de feuille)
        if not coloriage_douteux(propre):
            col, nettoye = propre, True
            resultat["coloriage_nettoye"] = True
    # Étape A2-6 : une page de PDF vectoriel ou piégé est à plat par construction (jamais photographiée de biais).
    a_plat_pdf = bool(ann.get("pdf", {}).get("a_plat"))
    R = estimer_redressement(col) if redresser and not a_plat_pdf else None
    if R is not None:
        resultat["deformation_lue"] = round(R.deformation, 5)
    if R is not None and not R.de_biais:
        R = None  # page vue de face : la lecture habituelle (avec sa rotation) suffit
    optique = R is not None and proportions == "optique"
    if optique and not photo_entiere(*taille):  # photo recadrée : l'optique ne sait pas, la photo garde ses proportions
        optique = False
        resultat["photo_recadree"] = True
    if optique:  # les proportions retrouvées par l'optique, avant toute lecture d'échelle
        rapport = rapport_par_optique(R, col.shape)
        resultat["rapport_optique"] = round(rapport, 5)
        if rapport_plausible(rapport):
            R = corriger_proportions(R, rapport)
        else:  # points de fuite douteux : la photo garde ses proportions
            optique = False
            resultat["optique_douteuse"] = True
    vx = vy = s  # l'échelle vraie, en largeur et en hauteur
    if R is not None:
        vx, vy = echelles_apres_redressement(R, ann, s / ann["image"]["px_par_m"])
        resultat["perspective_lue"] = round(R.perspective, 4)
    lu = lx = ly = None
    if echelle_opt is not None:
        images, cache, *reste = echelle_opt
        pdf = bool(reste and reste[0])
        dessin = dessin_du_niveau(niveau, Path(images) if images else None)
        lu = echelle_du_plan(niveau, dessin, col, R, Path(cache) if cache else None, "-nettoye" if nettoye else "",
                             pdf, blocs) if dessin else {"largeur": None, "hauteur": None}
        douteux = coloriage_douteux(col)  # calculé ici et non gardé en cache : il ne dépend que du coloriage brut
        if douteux:
            resultat["coloriage_douteux"] = True
        lx, ly, source = decider(lu["largeur"], lu["hauteur"], lu.get("sure", False), lu.get("cote_max_largeur"), lu.get("cote_max_hauteur"),
                                 lu.get("interieur_px"), R is not None, lu.get("barre") if lu.get("barre_sure") else None,
                                 lu.get("surfaces") if lu.get("surfaces_sure") else None, optique, lu.get("approchee"),
                                 douteux, lu.get("surfaces"), ecrite=lu.get("ecrite"), ambigue=lu.get("ambigue", False),
                                 plusieurs_blocs=blocs)
        if R is None:
            lx = ly = lx or ly
        if lu.get("textes_pdf"):
            resultat["textes_pdf"] = True
        resultat["echelle_lue"] = {"largeur": lx, "hauteur": ly, "cotes": lu.get("cotes", 0), "source": source,
                                   "ecart_largeur_pct": round(100 * (lx / vx - 1), 3) if lx else None,
                                   "ecart_hauteur_pct": round(100 * (ly / vy - 1), 3) if ly else None}
        resultat["echelle_a_verifier"] = not (lx or ly)
        if not (lx or ly) and lu.get("approchee"):  # échelle approchée par les portes, pour la vérification seulement
            resultat["echelle_lue"]["ecart_approchee_pct"] = round(100 * (lu["approchee"] / vx - 1), 1)
        if lx or ly:  # sinon : plan « à vérifier », noté avec l'échelle exacte (bilan à part)
            vx, vy = lx or ly, ly or lx
            if R is not None and not (lx and ly):  # un seul sens coté : la photo garde ses proportions
                resultat["proportions_de_la_photo"] = True
    if R is not None:
        if proportions == "cotes" and not resultat.get("proportions_de_la_photo"):
            R = corriger_proportions(R, vx / vy)
        elif proportions == "optique" and lx and ly:  # échelle lue dans les deux sens : elle a le dernier mot
            R = corriger_proportions(R, vx / vy)
        else:  # l'image redressée garde les proportions de l'optique (ou de la photo) ; écart à la vérité :
            resultat["proportions_ecart_pct"] = round(100 * abs(vy / vx - 1), 2)
    s = vx
    resultat["redresse"] = R is not None
    noms = None
    if noms_opt is not None:
        images, cache, *reste = noms_opt
        dessin = dessin_du_niveau(niveau, Path(images) if images else None)
        tp = textes_pdf(niveau) if reste and reste[0] else None
        if dessin is not None:
            r = col.shape[1] / Image.open(dessin).width  # dessin d'origine → coloriage (grand côté 768 px)
            if tp:  # textes exacts du PDF, pas d'OCR
                from moteur.lecture_pdf import pour_les_noms

                noms = noms_depuis_textes(pour_les_noms(tp[0]))
            else:
                noms = noms_depuis_textes(textes_du_plan(dessin, Path(cache) if cache else None))
            for n in noms:
                n.x, n.y = (n.x + 0.5) * r - 0.5, (n.y + 0.5) * r - 0.5
        resultat["noms_lus"] = len(noms or [])
    try:
        lu, details = lire_coloriage(col, s, projet_id=f"{exemple.name}-N{idx}",
                                     hauteur_sous_plafond=vrai["hauteur_sous_plafond"], redressement=R, noms=noms)
    except Exception as e:  # noqa: BLE001 — un plan raté est noté comme tel
        resultat["erreur"] = f"{type(e).__name__}: {str(e)[:200]}"
        if doutes_opt:
            resultat["doutes"] = examiner(None, erreur=resultat["erreur"])
        return resultat
    resultat["angle_lu"] = details["angle_deg"]
    resultat.update(comparer(vrai, lu, types_vrais, details["types_pieces"]))
    if doutes_opt:
        carte = None
        if fichier_coloriage:
            f = Path(fichier_coloriage).with_name(Path(fichier_coloriage).stem + "-doute.png")
            if f.exists():
                carte = np.array(Image.open(f), np.uint8)
        autres = []
        if resultat.get("echelle_a_verifier"):
            autres.append({"code": "echelle", "element": None, "raison": "échelle illisible", "gravite": "fort"})
        if resultat.get("coloriage_douteux"):
            autres.append({"code": "coloriage_douteux", "element": None, "raison": "coloriage collé au bord de l'image",
                           "gravite": "faible"})
        if blocs:  # un seul niveau lu (voir moteur.lecture_complete 0.4.0) ; le banc n'a pas besoin de situer les autres
            autres.append(doute_plusieurs_niveaux())
        resultat["doutes"] = examiner(lu, details, carte=carte, redressement=R, autres=autres)
        resultat["erreurs_zones"] = zones_des_erreurs(vrai, resultat)
    resultat["pieces_nom_lu"] = len(details["pieces_nom_lu"])
    resultat["logement"] = lu
    return resultat


# ---------------------------------------------------------------- doutes (étape A1)

MUR_GRAVE_BOUTS, MUR_GRAVE_AXE = 0.30, 0.10  # m : au-delà, l'erreur se voit sur la maquette
OUVERTURE_GRAVE_LARGEUR = 0.20


def _boite_mur(m: dict) -> list[float]:
    e = m["epaisseur"] / 2
    (x1, y1), (x2, y2) = m["debut"], m["fin"]
    return [min(x1, x2) - e, min(y1, y2) - e, max(x1, x2) + e, max(y1, y2) + e]


def _boite_mur_vrai(mv: dict, ident: str) -> list[float]:
    """Boîte d'un mur vrai ; un mur arrondi (« M_arrondi1 ») est fait de morceaux « M_arrondi1-k »."""
    if ident in mv:
        return _boite_mur(mv[ident])
    boites = [_boite_mur(m) for k, m in mv.items() if k.startswith(ident + "-")]
    if not boites:
        return [0.0, 0.0, 0.0, 0.0]
    return [min(b[0] for b in boites), min(b[1] for b in boites), max(b[2] for b in boites), max(b[3] for b in boites)]


def zones_des_erreurs(vrai: dict, r: dict) -> list[dict]:
    """Où sont les vraies erreurs de lecture (repère du logement vrai, en m), et si elles sont graves."""
    mv = {m["id"]: m for m in vrai["murs"]}
    zones = []
    for m in r["murs"]:
        if m.get("juste"):
            continue
        grave = not m["trouve"] or m["bouts"] > MUR_GRAVE_BOUTS or m["axe"] > MUR_GRAVE_AXE
        zones.append({"quoi": "mur", "id": m["vrai"], "grave": grave, "zone": _boite_mur_vrai(mv, m["vrai"])})
    for o in r["ouvertures"]:
        if o.get("juste"):
            continue
        ov = next(x for x in vrai["ouvertures"] if x["id"] == o["vrai"])
        cx, cy = _centre_ouverture(ov, mv)
        d = ov["largeur"] / 2 + 0.1
        grave = not o["trouve"] or not o["bon_type"] or o["largeur"] > OUVERTURE_GRAVE_LARGEUR
        zones.append({"quoi": "ouverture", "id": o["vrai"], "grave": grave, "zone": [cx - d, cy - d, cx + d, cy + d]})
    for p in r["pieces"]:
        if p.get("trouve") and p.get("bon_type"):
            continue
        pv = next(x for x in vrai["pieces"] if x["id"] == p["vrai"])
        xs, ys = [q[0] for q in pv["contour"]], [q[1] for q in pv["contour"]]
        zones.append({"quoi": "piece", "id": p["vrai"], "grave": True, "zone": [min(xs), min(ys), max(xs), max(ys)]})
    return zones


def _touche(a: list[float], b: list[float], marge: float = 0.2) -> bool:
    return a[0] - marge <= b[2] and b[0] - marge <= a[2] and a[1] - marge <= b[3] and b[1] - marge <= a[3]


def bilan_doutes(resultats: list[dict]) -> dict:
    """Les doutes attrapent-ils les erreurs ? Plan par plan et erreur par erreur."""
    rs = [r for r in resultats if "doutes" in r]

    def echelle_fausse(r):
        e = r.get("echelle_lue")
        if not e or r.get("echelle_a_verifier"):
            return False
        return any(e[k] is not None and abs(e[k]) > 3 for k in ("ecart_largeur_pct", "ecart_hauteur_pct"))

    def erreur(r, grave):
        if "erreur" in r or echelle_fausse(r):
            return True
        if r["murs_en_trop"] or r["ouvertures_en_trop"]:
            return True
        return any(z["grave"] or not grave for z in r.get("erreurs_zones", []))

    sortie = {"niveaux": len(rs)}
    dec = [r["doutes"]["decision"] for r in rs]
    sortie["decisions"] = {k: dec.count(k) for k in ("lu", "a_verifier", "refuse")}
    for nom, grave in (("graves", True), ("toutes", False)):
        avec = [r for r in rs if erreur(r, grave)]
        sans = [r for r in rs if not erreur(r, grave)]
        silencieuses = [r for r in avec if r["doutes"]["decision"] == "lu"]
        fausses = [r for r in sans if r["doutes"]["decision"] != "lu"]
        sortie[nom] = {"plans_avec_erreur": len(avec), "erreurs_silencieuses": len(silencieuses),
                       "attrapees_pct": round(100 * (1 - len(silencieuses) / len(avec)), 1) if avec else None,
                       "plans_justes": len(sans), "justes_envoyes_en_verification": len(fausses),
                       "fausses_alertes_pct": round(100 * len(fausses) / len(sans), 1) if sans else None,
                       "silencieuses_exemples": [f"{r['plan']}-N{r['niveau']}" for r in silencieuses[:30]]}
    # Erreur par erreur : un doute fort posé dessus (zone qui la touche) ?
    tot = vues = 0
    for r in rs:
        fortes = [d for d in r["doutes"]["doutes"] if d["gravite"] == "fort"]
        for z in r.get("erreurs_zones", []):
            if not z["grave"]:
                continue
            tot += 1
            vues += any("zone_m" not in d or _touche(d["zone_m"], z["zone"]) for d in fortes)
    sortie["erreurs_graves_localisees"] = {"nombre": tot, "avec_doute_dessus_pct": round(100 * vues / tot, 1) if tot else None}
    codes: dict[str, int] = {}
    for r in rs:
        for c in {d["code"] for d in r["doutes"]["doutes"] if d["gravite"] == "fort"}:
            codes[c] = codes.get(c, 0) + 1
    sortie["plans_par_code"] = dict(sorted(codes.items(), key=lambda kv: -kv[1]))
    return sortie


# ---------------------------------------------------------------- bilan

def bilan(resultats: list[dict]) -> dict:
    ok = [r for r in resultats if "erreur" not in r]
    murs = [m for r in ok for m in r["murs"]]
    mt = [m for m in murs if m["trouve"]]
    ouv = [o for r in ok for o in r["ouvertures"]]
    ot = [o for o in ouv if o["trouve"]]
    pie = [p for r in ok for p in r["pieces"]]
    pt = [p for p in pie if p["trouve"]]

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    def moy_cm(v):
        return round(100 * float(np.mean(v)), 1) if v else None

    def med_cm(v):
        return round(100 * float(np.median(v)), 1) if v else None

    par_type = {}
    for t in ("porte", "fenetre", "porte_fenetre"):
        o = [x for x in ouv if x["type"] == t]
        par_type[t] = {"trouvees_pct": pct(sum(x["trouve"] for x in o), len(o)),
                       "bon_type_pct": pct(sum(x.get("bon_type", False) for x in o), len(o))}
    par_piece = {}
    for c, (t, _) in PIECES.items():
        p = [x for x in pie if x["classe"] == c]
        if p:
            par_piece[t] = {"nombre": len(p), "trouvees_pct": pct(sum(x["trouve"] for x in p), len(p)),
                            "bon_type_pct": pct(sum(x.get("bon_type", False) for x in p), len(p))}
    ht = [r["hors_tout"] for r in ok]
    return {
        "niveaux_notes": len(resultats), "niveaux_rates": len(resultats) - len(ok),
        "murs": {"nombre": len(murs), "trouves_pct": pct(len(mt), len(murs)), "justes_pct": pct(sum(m["juste"] for m in mt), len(murs)),
                 "ecart_axe_cm_moyen": moy_cm([m["axe"] for m in mt]), "ecart_axe_cm_median": med_cm([m["axe"] for m in mt]),
                 "ecart_epaisseur_cm_moyen": moy_cm([m["epaisseur"] for m in mt]),
                 "ecart_bouts_cm_moyen": moy_cm([m["bouts"] for m in mt]), "ecart_bouts_cm_median": med_cm([m["bouts"] for m in mt]),
                 "en_trop": sum(r["murs_en_trop"] for r in ok),
                 # A3 : les murs en biais / arrondis seuls (absent s'il n'y en a aucun)
                 **({"libres": {"nombre": len(ml), "trouves_pct": pct(sum(m["trouve"] for m in ml), len(ml)),
                                "justes_pct": pct(sum(m.get("juste", False) for m in ml), len(ml))}}
                    if (ml := [m for m in murs if m.get("libre")]) else {})},
        "ouvertures": {"nombre": len(ouv), "trouvees_pct": pct(len(ot), len(ouv)), "justes_pct": pct(sum(o["juste"] for o in ot), len(ouv)),
                       "bon_type_pct": pct(sum(o["bon_type"] for o in ot), len(ot)),
                       "ecart_largeur_cm_moyen": moy_cm([o["largeur"] for o in ot]),
                       "ecart_centre_cm_moyen": moy_cm([o["centre"] for o in ot]), "par_type": par_type},
        "pieces": {"nombre": len(pie), "trouvees_pct": pct(len(pt), len(pie)),
                   "bon_type_pct": pct(sum(p["bon_type"] for p in pt), len(pie)),
                   "ecart_surface_pct_moyen": round(float(np.mean([p["surface_pct"] for p in pt])), 1) if pt else None,
                   "par_type": par_piece},
        "hors_tout": {"ecart_cm_moyen": moy_cm(ht), "ecart_cm_median": med_cm(ht),
                      "justes_10cm_pct": pct(sum(h <= 0.10 for h in ht), len(ht))},
        "plans_parfaits_pct": pct(sum(all(m.get("juste") for m in r["murs"]) and all(o.get("juste") for o in r["ouvertures"])
                                      and all(p.get("trouve") and p.get("bon_type") for p in r["pieces"]) for r in ok), len(resultats)),
    }


def bilan_echelle(resultats: list[dict]) -> dict:
    """Combien de plans ont une échelle lue, et à quel point elle est juste."""
    def part(rs):
        lus = [r["echelle_lue"] for r in rs if "echelle_lue" in r and not r.get("echelle_a_verifier")]
        ec = [abs(e[k]) for e in lus for k in ("ecart_largeur_pct", "ecart_hauteur_pct") if e[k] is not None]
        pire = [max(abs(e[k]) for k in ("ecart_largeur_pct", "ecart_hauteur_pct") if e[k] is not None) for e in lus]
        n = len(rs)
        approchees = [abs(r["echelle_lue"]["ecart_approchee_pct"]) for r in rs
                      if r.get("echelle_a_verifier") and "ecart_approchee_pct" in r.get("echelle_lue", {})]
        return {"niveaux": n, "echelle_lue": len(lus), "a_verifier": n - len(lus),
                "lue_pct": round(100 * len(lus) / n, 1) if n else None,
                "ecart_pct_median": round(float(np.median(ec)), 3) if ec else None,
                "ecart_pct_moyen": round(float(np.mean(ec)), 3) if ec else None,
                "a_0_5_pct_pres_pct": round(100 * sum(p <= 0.5 for p in pire) / len(pire), 1) if pire else None,
                "a_1_pct_pres_pct": round(100 * sum(p <= 1 for p in pire) / len(pire), 1) if pire else None,
                "plus_de_3_pct": sum(p > 3 for p in pire),
                "par_cote_d_ensemble": sum(r["echelle_lue"].get("source") == "cote d'ensemble" for r in rs if "echelle_lue" in r),
                "par_barre": sum(r["echelle_lue"].get("source") == "barre" for r in rs if "echelle_lue" in r),
                "par_surfaces": sum(r["echelle_lue"].get("source") == "surfaces" for r in rs if "echelle_lue" in r),
                "par_echelle_ecrite": sum(r["echelle_lue"].get("source") == "échelle écrite" for r in rs if "echelle_lue" in r),
                # Les plans « à vérifier » : combien reçoivent une échelle approchée par les portes, et à quel point.
                "a_verifier_avec_approchee": len(approchees),
                "approchee_a_10_pct_pres": sum(a <= 10 for a in approchees)}
    return {"tous": part(resultats), "a_plat": part([r for r in resultats if r["perspective"] == 0]),
            "de_biais": part([r for r in resultats if r["perspective"] > 0])}


def lister(jeu: Path, partie: str, coloriages: Path | None, nombre: int) -> list[tuple]:
    rep = json.loads((jeu / "repartition.json").read_text(encoding="utf-8"))
    parts = rep.get("partitions", rep)
    ids = []
    for nom, liste in parts.items():
        if isinstance(liste, list) and (partie in nom or (partie == "validation" and nom.startswith("val"))):
            ids += [str(i).zfill(6) if str(i).isdigit() else str(i) for i in liste]
    ids = sorted(ids)[:nombre] if nombre else sorted(ids)
    taches = []
    for i in ids:
        ex = jeu / "exemples" / i
        for niv in sorted(n for n in ex.glob("niveau_*") if n.is_dir()):
            f = None
            if coloriages:
                f = coloriages / i / f"{niv.name}.png"
                if not f.exists():
                    continue
            taches.append((str(ex), niv.name, str(f) if f else None))
    return taches


def _en_json(v):
    return v.item() if hasattr(v, "item") else str(v)


def main() -> None:
    ap = argparse.ArgumentParser(description="Noter la traduction coloriage → logement.json (écarts en cm)")
    ap.add_argument("jeu", type=Path)
    ap.add_argument("--partie", default="test")
    ap.add_argument("--coloriages", type=Path, help="dossier des coloriages d'Atelya (sinon : coloriage parfait)")
    ap.add_argument("--nombre", type=int, default=0)
    ap.add_argument("--processus", type=int, default=4)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--sans-redressement", action="store_true",
                    help="ne pas remettre les plans à plat avant de les lire (comme avant la version 0.2)")
    ap.add_argument("--proportions", choices=("cotes", "photo", "optique"), default="cotes",
                    help="après redressement, rapport largeur/hauteur donné par les cotes (exactes), gardé de la photo, "
                         "ou retrouvé par l'optique (photo sans cotes ; des cotes lues ont le dernier mot)")
    ap.add_argument("--noms", action="store_true",
                    help="lire aussi les noms de pièces écrits sur le plan (RapidOCR) : ils décident du type")
    ap.add_argument("--images", type=Path, help="dossier « exemples » des dessins, s'ils ne sont pas dans le jeu")
    ap.add_argument("--echelle", choices=("exacte", "lue"), default="exacte",
                    help="échelle donnée au traducteur : l'exacte (vérité du jeu) ou celle lue sur les cotes du dessin")
    ap.add_argument("--textes-pdf", action="store_true",
                    help="étape A2 : sur les niveaux venus d'un PDF vectoriel (textes-pdf.json), prendre les textes exacts "
                         "du PDF et son échelle écrite au lieu de l'OCR")
    ap.add_argument("--doutes", action="store_true",
                    help="étape A1 : examiner chaque lecture (moteur.doutes) et mesurer si les doutes attrapent les erreurs ; "
                         "carte des doutes lue à côté du coloriage (<niveau>-doute.png) si elle existe")
    a = ap.parse_args()
    noms_opt = None
    if a.noms:
        cache = a.sortie / "textes-lus"
        cache.mkdir(parents=True, exist_ok=True)
        noms_opt = (str(a.images) if a.images else None, str(cache), a.textes_pdf)
    echelle_opt = None
    if a.echelle == "lue":
        cache = a.sortie / "echelles-lues"
        cache.mkdir(parents=True, exist_ok=True)
        echelle_opt = (str(a.images) if a.images else None, str(cache), a.textes_pdf)
    taches = [(*t, not a.sans_redressement, a.proportions, noms_opt, echelle_opt, a.doutes) for t in lister(a.jeu, a.partie, a.coloriages, a.nombre)]
    t0 = time.time()
    with ProcessPoolExecutor(a.processus) as ex:
        resultats = list(ex.map(noter_niveau, taches, chunksize=8))
    a.sortie.mkdir(parents=True, exist_ok=True)
    b = bilan(resultats)
    # Plans « photographiés » (page vue de biais) : notés à part, car ils passent par le redressement.
    b["plans_a_plat"] = bilan([r for r in resultats if r["perspective"] == 0])
    b["plans_de_biais"] = bilan([r for r in resultats if r["perspective"] > 0])
    if a.echelle == "lue":
        lus = [r for r in resultats if not r.get("echelle_a_verifier", False)]
        b["echelle_lue"] = bilan_echelle(resultats)
        b["plans_echelle_lue"] = bilan(lus)
        b["plans_echelle_lue_a_plat"] = bilan([r for r in lus if r["perspective"] == 0])
        b["plans_echelle_lue_de_biais"] = bilan([r for r in lus if r["perspective"] > 0])
    if a.doutes:
        b["doutes"] = bilan_doutes(resultats)
    b["source"] = "atelya" if a.coloriages else "parfait"
    b["duree_s"] = round(time.time() - t0, 1)
    (a.sortie / "bilan.json").write_text(json.dumps(b, ensure_ascii=False, indent=1, default=_en_json), encoding="utf-8")
    (a.sortie / "details.json").write_text(json.dumps([{k: v for k, v in r.items() if k != "logement"} for r in resultats],
                                                       ensure_ascii=False, default=_en_json), encoding="utf-8")
    logs = a.sortie / "logements"
    logs.mkdir(exist_ok=True)
    for r in resultats:
        if "logement" in r:
            (logs / f"{r['plan']}-N{r['niveau']}.json").write_text(json.dumps(r["logement"], ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(b, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
