r"""Noter Atelya sur les VRAIS plans, contre les vérités de outils/verite/faire_verite.py : la même note qu'au banc des plans
fabriqués (moteur.banc_coloriage.comparer : murs, ouvertures, pièces en centimètres), plus l'échelle et la décision.

Pourquoi : jusqu'ici la note « vrais plans » était une impression à l'œil ; ici c'est une mesure, refaite à chaque correctif.
Deux notes de géométrie : « à l'échelle lue » (ce que vit le client : échelle d'Atelya, comme les bancs) et « à l'échelle vraie »
(la lecture remise à la bonne échelle : juge le modèle et le traducteur seuls). Dans les deux cas, la lecture est d'abord
RECALÉE sur la vérité par une translation (l'origine de la lecture dépend du coloriage ; une pièce manquante la déplace), car
la 3D ne dépend pas de l'origine.

    ..\atelya\.venv\Scripts\python.exe outils\verite\noter_vrais_plans.py --lectures ..\atelya\lectures-dehors [--verites ..\atelya\verites] [--sortie ..\atelya\note-vrais-plans.json]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.banc_coloriage import TYPE_VERS_CLASSE, comparer, comparer_murs  # noqa: E402
from moteur.lecture_complete import COTE_ATELYA  # noqa: E402

PAS = 0.02  # m : grille du recalage
MARGE = 6.0  # m : translation maximale cherchée (une lecture qui n'a vu qu'une partie du plan a son origine loin de la vraie)


def _murs_en_masque(murs: list[dict], x0: float, y0: float, forme: tuple[int, int]) -> np.ndarray:
    m = np.zeros(forme, np.uint8)
    for w in murs:
        a = (int(round((w["debut"][0] - x0) / PAS)), int(round((w["debut"][1] - y0) / PAS)))
        b = (int(round((w["fin"][0] - x0) / PAS)), int(round((w["fin"][1] - y0) / PAS)))
        cv2.line(m, a, b, 1, max(1, int(round(w["epaisseur"] / PAS))))
    return m


def _translater(lu: dict, dx: float, dy: float) -> dict:
    out = copy.deepcopy(lu)
    for m in out["murs"]:
        m["debut"] = [m["debut"][0] + dx, m["debut"][1] + dy]
        m["fin"] = [m["fin"][0] + dx, m["fin"][1] + dy]
    for p in out["pieces"]:
        p["contour"] = [[x + dx, y + dy] for x, y in p["contour"]]
    return out


def _score(vrai: dict, lu: dict) -> float:
    """Combien de lignes de murs vraies la lecture retrouve, et à quelle distance : 1 point par ligne trouvée, moins l'écart d'axe."""
    murs, _ = comparer_murs(vrai["murs"], lu["murs"])
    return sum(1.0 - min(1.0, m.get("axe", 0.15) / 0.15) for m in murs if m.get("trouve"))


def recaler(vrai: dict, lu: dict) -> tuple[dict, tuple[float, float]]:
    """La lecture translatée pour que ses murs retrouvent le plus de vrais murs (recherche du décalage, 10 cm puis 1 cm).
    Point de départ : les deux coins sud-ouest intérieurs superposés (c'est déjà la convention des deux origines)."""
    meilleur, (bx, by) = _score(vrai, lu), (0.0, 0.0)
    for pas, portee in ((0.25, MARGE), (0.05, 0.30), (0.01, 0.06)):
        cx, cy = bx, by
        n = int(round(portee / pas))
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                dx, dy = cx + i * pas, cy + j * pas
                s = _score(vrai, _translater(lu, dx, dy))
                if s > meilleur + 1e-9:
                    meilleur, (bx, by) = s, (dx, dy)
    return _translater(lu, bx, by), (round(bx, 3), round(by, 3))


def remettre_a_l_echelle(lu: dict, f: float) -> dict:
    """La lecture dont toutes les longueurs sont multipliées par f (échelle lue → échelle vraie)."""
    out = copy.deepcopy(lu)
    for m in out["murs"]:
        m["debut"] = [v * f for v in m["debut"]]
        m["fin"] = [v * f for v in m["fin"]]
        m["epaisseur"] *= f
    for o in out["ouvertures"]:
        o["position"] *= f
        o["largeur"] *= f
    for p in out["pieces"]:
        p["contour"] = [[x * f, y * f] for x, y in p["contour"]]
    return out


def _resume(r: dict) -> dict:
    murs = r["murs"]
    ouv = r["ouvertures"]
    pieces = r["pieces"]
    trouves = [p for p in pieces if p.get("trouve")]
    return {"murs_trouves_pct": round(100 * sum(m.get("trouve", False) for m in murs) / max(1, len(murs)), 1),
            "murs_justes_pct": round(100 * sum(m.get("juste", False) for m in murs) / max(1, len(murs)), 1),
            # « placé » : l'axe du mur lu passe à moins de 10 cm du vrai (sans juger les bouts ni l'épaisseur) ; sur un vrai
            # plan colorié à ~40 px/m (1 px = 2,5 cm), le critère « juste » du banc (5 cm / 3 cm / 10 cm) est rarement tenu.
            "murs_places_pct": round(100 * sum(1 for m in murs if m.get("trouve") and m.get("axe", 1) <= 0.10) / max(1, len(murs)), 1),
            "murs_en_trop": r["murs_en_trop"],
            "ouv_trouvees_pct": round(100 * sum(o.get("trouve", False) for o in ouv) / max(1, len(ouv)), 1),
            "ouv_justes_pct": round(100 * sum(o.get("juste", False) for o in ouv) / max(1, len(ouv)), 1),
            "ouv_bon_type_pct": round(100 * sum(o.get("bon_type", False) for o in ouv if o.get("trouve")) / max(1, sum(o.get("trouve", False) for o in ouv)), 1),
            "ouv_en_trop": r["ouvertures_en_trop"],
            "pieces_trouvees_pct": round(100 * len(trouves) / max(1, len(pieces)), 1),
            "pieces_bon_type_pct": round(100 * sum(p.get("bon_type", False) for p in trouves) / max(1, len(trouves)), 1),
            "hors_tout_cm": round(100 * r["hors_tout"], 1),
            "parfait": all(m.get("juste") for m in murs) and all(o.get("juste") for o in ouv)
            and all(p.get("trouve") and p.get("bon_type") for p in pieces) and r["murs_en_trop"] == 0}


def noter_plan(verites: Path, lectures: Path, nom: str) -> dict | None:
    dv = verites / nom
    dl = lectures / nom
    if not dl.exists():  # un PDF est lu page par page : fr-019 → fr-019-page1
        pages = sorted(lectures.glob(f"{nom}-page*"))
        dl = pages[0] if pages else dl
    if not (dl / "logement.json").exists() or not (dl / "lecture.json").exists():
        return {"plan": nom, "erreur": "pas de lecture"}
    verite = json.loads((dv / "verite.json").read_text(encoding="utf-8"))
    vrai = json.loads((dv / "logement.json").read_text(encoding="utf-8"))
    lu = json.loads((dl / "logement.json").read_text(encoding="utf-8"))
    lecture = json.loads((dl / "lecture.json").read_text(encoding="utf-8"))
    types_vrais = {p["id"]: TYPE_VERS_CLASSE.get(t, 5) for p, t in zip(vrai["pieces"], [verite["types_pieces"][p["id"]] for p in vrai["pieces"]])}
    types_lus = (lecture.get("details") or {}).get("types_pieces") or {p["id"]: p["id"].rsplit("_", 1)[0] for p in lu["pieces"]}
    # Échelle : la lecture travaille sur le coloriage (grand côté COTE_ATELYA) ; la vérité est en pixels de l'image.
    r_col = COTE_ATELYA / max(verite["largeur"], verite["hauteur"])
    vrai_col = verite["px_par_m"] * r_col
    e = lecture.get("echelle") or {}
    lu_col = e.get("px_par_m_largeur") or e.get("px_par_m_hauteur") or (lecture.get("details") or {}).get("px_par_m")
    ligne = {"plan": nom, "decision": lecture.get("decision"), "modele": lecture.get("modele"), "echelle_etat": e.get("etat"),
             "echelle_source": e.get("source"), "echelle_inconnue": verite["echelle_inconnue"],
             "doutes_forts": sum(1 for d in lecture.get("doutes", []) if d.get("force") == "fort" or d.get("niveau") == "fort"),
             "incertain": verite.get("incertain", [])}
    if lu_col and not verite["echelle_inconnue"]:
        ligne["echelle_ecart_pct"] = round(100 * (lu_col / vrai_col - 1), 2)
        ligne["echelle_erreur_silencieuse"] = e.get("etat") == "lue" and abs(ligne["echelle_ecart_pct"]) > 3
    f = lu_col / vrai_col if lu_col else 1.0  # 1 m lu = lu_col px ; en vrais mètres : × lu_col / vrai_col
    lu_recale, decalage = recaler(vrai, lu)
    ligne["recalage_m"] = decalage
    ligne["echelle_lue"] = _resume(comparer(vrai, lu_recale, types_vrais, types_lus))
    lu_vrai, _ = recaler(vrai, remettre_a_l_echelle(lu, f))
    ligne["echelle_vraie"] = _resume(comparer(vrai, lu_vrai, types_vrais, types_lus))
    ligne["nb"] = {"murs_vrais": len(vrai["murs"]), "murs_lus": len(lu["murs"]), "ouv_vraies": len(vrai["ouvertures"]),
                   "ouv_lues": len(lu["ouvertures"]), "pieces_vraies": len(vrai["pieces"]), "pieces_lues": len(lu["pieces"])}
    return ligne


def _moyenne(lignes: list[dict], cle: str, champ: str) -> float:
    v = [l[cle][champ] for l in lignes if cle in l]
    return round(sum(v) / len(v), 1) if v else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verites", type=Path, default=Path("../atelya/verites"))
    ap.add_argument("--lectures", type=Path, required=True)
    ap.add_argument("--sortie", type=Path)
    a = ap.parse_args()
    lignes = []
    for d in sorted(a.verites.iterdir()):
        if (d / "verite.json").exists():
            lignes.append(noter_plan(a.verites, a.lectures, d.name))
    notees = [l for l in lignes if "echelle_lue" in l]
    print(f"{'plan':8} {'décision':11} {'échelle':>8} {'état':10} | {'murs tr/placé/juste':>20} {'trop':>4} | {'ouv tr/juste':>13} | {'pièces tr/type':>14} | à échelle vraie : murs / pièces")
    for l in lignes:
        if "echelle_lue" not in l:
            print(f"{l['plan']:8} {l.get('erreur')}")
            continue
        g, v = l["echelle_lue"], l["echelle_vraie"]
        ech = "inconnue" if l["echelle_inconnue"] else (f"{l['echelle_ecart_pct']:+.1f} %" if "echelle_ecart_pct" in l else "-")
        print(f"{l['plan']:8} {l['decision'] or '-':11} {ech:>8} {l['echelle_etat'] or '-':10} | {g['murs_trouves_pct']:5.1f}/{g['murs_places_pct']:5.1f}/{g['murs_justes_pct']:4.1f} {g['murs_en_trop']:4} | "
              f"{g['ouv_trouvees_pct']:5.1f}/{g['ouv_justes_pct']:5.1f} | {g['pieces_trouvees_pct']:5.1f}/{g['pieces_bon_type_pct']:5.1f} | "
              f"{v['murs_trouves_pct']:5.1f}/{v['murs_places_pct']:5.1f}  {v['pieces_trouvees_pct']:5.1f}/{v['pieces_bon_type_pct']:5.1f}")
    avec_ech = [l for l in notees if "echelle_ecart_pct" in l]
    bilan = {"plans": len(notees),
             "echelle": {"avec_verite": len(avec_ech), "lues": sum(1 for l in avec_ech if l["echelle_etat"] == "lue"),
                         "lues_justes_3pct": sum(1 for l in avec_ech if l["echelle_etat"] == "lue" and abs(l["echelle_ecart_pct"]) <= 3),
                         "erreurs_silencieuses": sum(1 for l in avec_ech if l.get("echelle_erreur_silencieuse"))},
             "a_echelle_lue": {k: _moyenne(notees, "echelle_lue", k) for k in ("murs_trouves_pct", "murs_places_pct", "murs_justes_pct", "ouv_trouvees_pct", "ouv_justes_pct", "pieces_trouvees_pct", "pieces_bon_type_pct")},
             "a_echelle_vraie": {k: _moyenne(notees, "echelle_vraie", k) for k in ("murs_trouves_pct", "murs_places_pct", "murs_justes_pct", "ouv_trouvees_pct", "ouv_justes_pct", "pieces_trouvees_pct", "pieces_bon_type_pct")},
             "murs_en_trop": sum(l["echelle_lue"]["murs_en_trop"] for l in notees),
             "parfaits": sum(1 for l in notees if l["echelle_lue"]["parfait"]),
             "decisions": {d: sum(1 for l in notees if l["decision"] == d) for d in ("lu", "a_verifier", "refuse")},
             "plans_detail": lignes}
    print("\nBILAN :", json.dumps({k: v for k, v in bilan.items() if k != "plans_detail"}, ensure_ascii=False))
    if a.sortie:
        a.sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
