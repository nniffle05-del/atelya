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


def comparer_murs(vrais: list[dict], lus: list[dict]) -> list[dict]:
    """Chaque mur vrai est noté sur sa ligne de murs : trouvée ou non, écart d'axe, d'épaisseur, de bouts."""
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


def noter_niveau(args) -> dict:
    exemple, niveau_nom, fichier_coloriage = args
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
    try:
        lu, details = lire_coloriage(col, s, projet_id=f"{exemple.name}-N{idx}",
                                     hauteur_sous_plafond=vrai["hauteur_sous_plafond"])
    except Exception as e:  # noqa: BLE001 — un plan raté est noté comme tel
        resultat["erreur"] = f"{type(e).__name__}: {str(e)[:200]}"
        return resultat
    resultat["angle_lu"] = details["angle_deg"]
    resultat.update(comparer(vrai, lu, types_vrais, details["types_pieces"]))
    resultat["logement"] = lu
    return resultat


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
                 "en_trop": sum(r["murs_en_trop"] for r in ok)},
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
    a = ap.parse_args()
    taches = lister(a.jeu, a.partie, a.coloriages, a.nombre)
    t0 = time.time()
    with ProcessPoolExecutor(a.processus) as ex:
        resultats = list(ex.map(noter_niveau, taches, chunksize=8))
    a.sortie.mkdir(parents=True, exist_ok=True)
    b = bilan(resultats)
    # Plans « photographiés » (page vue de biais) : le traducteur ne sait pas encore les redresser.
    b["plans_a_plat"] = bilan([r for r in resultats if r["perspective"] == 0])
    b["plans_de_biais"] = bilan([r for r in resultats if r["perspective"] > 0])
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
