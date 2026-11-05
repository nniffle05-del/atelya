r"""Essai A/B des réglages du traducteur (coloriage → logement) sur les coloriages du banc, à échelle vraie, sans OCR.
Chaque variante relit les mêmes coloriages ; on compare pièces (trouvées, bon type, en trop) et ouvertures.
    ..\atelya\.venv\Scripts\python.exe pc\verification\ab_traducteur.py [--processus 5] [--nombre N]
"""
import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, ".")

A = Path("../atelya")
JEU = A / "jeu-test-6-13" / "exemples"
COLORIAGES = A / "coloriages-a1-apres" / "exemples"
DEFAUTS = None
VARIANTES = {
    "actuel": {},
    "sans fusion ouv.": {"FUSION_TYPES_DIFFERENTS": False},
    "séparation 1,0 m² / 10 %": {"SURFACE_MIN_SEPARATION": 1.0, "PART_MIN_SEPARATION": 0.10},
    "séparation 1,5 m² / 15 %": {"SURFACE_MIN_SEPARATION": 1.5, "PART_MIN_SEPARATION": 0.15},
    "séparation 2,0 m² / 20 %": {"SURFACE_MIN_SEPARATION": 2.0, "PART_MIN_SEPARATION": 0.20},
}


def niveaux(nombre: int) -> list[tuple[str, int]]:
    sortie = []
    for png in sorted(COLORIAGES.glob("*/niveau_*.png")):
        if png.stem.endswith("-doute"):
            continue
        plan, niv = png.parent.name, int(png.stem.split("_")[1])
        ann = json.loads((JEU / plan / f"niveau_{niv}" / "annotations.json").read_text(encoding="utf-8"))
        if ann["image"].get("perspective", 0):
            continue  # photos de biais : il faudrait le redressement ; les plans à plat suffisent pour comparer les réglages
        sortie.append((plan, niv))
    return sortie[:nombre] if nombre else sortie


def noter(args):
    plan, niv, reglages = args
    from moteur import coloriage as C
    from moteur.banc_coloriage import TYPE_VERS_CLASSE, comparer, echelle_pour_atelya

    global DEFAUTS
    if DEFAUTS is None:
        DEFAUTS = {k: getattr(C, k) for r in VARIANTES.values() for k in r}
    for k, v in {**DEFAUTS, **reglages}.items():  # chaque variante repart des réglages d'origine (les processus durent)
        setattr(C, k, v)
    d = JEU / plan / f"niveau_{niv}"
    ann = json.loads((d / "annotations.json").read_text(encoding="utf-8"))
    geo = json.loads((JEU / plan / "geometrie.json").read_text(encoding="utf-8"))
    vrai = json.loads((JEU / plan / f"logement_niveau{niv}.json").read_text(encoding="utf-8"))
    s, _ = echelle_pour_atelya(ann, (ann["image"]["largeur"], ann["image"]["hauteur"]))
    col = np.array(Image.open(COLORIAGES / plan / f"niveau_{niv}.png"), np.uint8)
    try:
        lu, details = C.lire_coloriage(col, s)
    except Exception as e:  # noqa: BLE001
        return {"plan": plan, "niveau": niv, "echec": str(e)[:80]}
    types_vrais = {p["id"]: TYPE_VERS_CLASSE.get(p["type"], 5) for n in geo["niveaux"] for p in n["pieces"]}
    r = comparer(vrai, lu, types_vrais, details["types_pieces"])
    return {"plan": plan, "niveau": niv, "pieces": r["pieces"], "pieces_lues": len(lu["pieces"]), "pieces_vraies": len(vrai["pieces"]),
            "ouvertures": r["ouvertures"], "ouvertures_en_trop": r.get("ouvertures_en_trop", 0), "murs": r["murs"]}


def resume(nom: str, resultats: list[dict]) -> dict:
    ok = [r for r in resultats if "echec" not in r]
    pieces = [p for r in ok for p in r["pieces"]]
    ouv = [o for r in ok for o in r["ouvertures"]]
    murs = [m for r in ok for m in r["murs"]]
    bilan = {"variante": nom, "niveaux": len(ok), "echecs": len(resultats) - len(ok),
             "pieces_trouvees_pct": round(100 * sum(p.get("trouve", False) for p in pieces) / len(pieces), 2),
             "bon_type_pct": round(100 * sum(p.get("bon_type", False) for p in pieces if p.get("trouve")) / max(1, sum(p.get("trouve", False) for p in pieces)), 2),
             "pieces_en_trop": sum(max(0, r["pieces_lues"] - r["pieces_vraies"]) for r in ok),
             "niveaux_pieces_en_trop": sum(r["pieces_lues"] > r["pieces_vraies"] for r in ok),
             "ouv_trouvees_pct": round(100 * sum(o.get("trouve", False) for o in ouv) / len(ouv), 2),
             "ouv_justes_pct": round(100 * sum(o.get("juste", False) for o in ouv) / len(ouv), 2),
             "ouv_bon_type_pct": round(100 * sum(o.get("bon_type", False) for o in ouv if o.get("trouve")) / max(1, sum(o.get("trouve", False) for o in ouv)), 2),
             "ouv_en_trop": sum(r["ouvertures_en_trop"] for r in ok),
             "murs_justes_pct": round(100 * sum(m.get("juste", False) for m in murs) / len(murs), 2)}
    return bilan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--processus", type=int, default=5)
    ap.add_argument("--nombre", type=int, default=0)
    a = ap.parse_args()
    liste = niveaux(a.nombre)
    print(f"{len(liste)} niveaux à plat", flush=True)
    bilans = []
    with Pool(a.processus) as pool:
        for nom, reglages in VARIANTES.items():
            res = pool.map(noter, [(p, n, reglages) for p, n in liste], chunksize=8)
            b = resume(nom, res)
            bilans.append(b)
            print(json.dumps(b, ensure_ascii=False), flush=True)
    (A / "ab-traducteur.json").write_text(json.dumps(bilans, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
