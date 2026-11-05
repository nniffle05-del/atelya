"""Compare les bancs du correctif d'échelle à leurs références, niveau par niveau.
    ..\\atelya\\.venv\\Scripts\\python.exe pc\\verification\\comparer_echelle.py
"""
import json
import sys
from pathlib import Path

A = Path("../atelya")
PAIRES = {"apres": "banc-v041-apres-e5", "pdf": "banc-a2-pdf", "reel-cotes": "banc-v041-reel-cotes-e5", "biais-e7": "banc-v041-biais-e7"}
# comparer_echelle.py banc-dehors banc-echelle : compare les dossiers banc-dehors-* aux banc-echelle-* (références = les
# derniers bancs complets d'un correctif précédent).
PREFIXE = sys.argv[1] if len(sys.argv) > 1 else "banc-echelle"
if len(sys.argv) > 2:
    PAIRES = {nom: f"{sys.argv[2]}-{nom}" for nom in PAIRES}


def details(dossier: Path) -> dict:
    d = json.loads((dossier / "details.json").read_text(encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("details", d.get("niveaux"))
    return {(x["plan"], x["niveau"]): x for x in d}


def lue(x: dict) -> bool:
    e = x.get("echelle_lue") or {}
    return not x.get("echelle_a_verifier") and bool(e.get("largeur") or e.get("hauteur"))


def erreur(x: dict) -> float:
    e = x.get("echelle_lue") or {}
    return max((abs(v) for v in (e.get("ecart_largeur_pct"), e.get("ecart_hauteur_pct")) if v is not None), default=0.0)


sortie = {}
for nom, ref in PAIRES.items():
    nouveau = A / f"{PREFIXE}-{nom}"
    if not (nouveau / "bilan.json").exists():
        print(f"{nom} : pas encore fini")
        continue
    b0 = json.loads((A / ref / "bilan.json").read_text(encoding="utf-8"))
    b1 = json.loads((nouveau / "bilan.json").read_text(encoding="utf-8"))
    d0, d1 = details(A / ref), details(nouveau)
    communs = sorted(set(d0) & set(d1))
    lus0 = [k for k in communs if lue(d0[k])]
    lus1 = [k for k in communs if lue(d1[k])]
    perdus = [k for k in lus0 if not lue(d1[k])]
    gagnes = [k for k in lus1 if not lue(d0[k])]
    changes = [k for k in communs if lue(d0[k]) and lue(d1[k]) and d0[k]["echelle_lue"] != d1[k]["echelle_lue"]]
    pires0 = [k for k in lus0 if erreur(d0[k]) > 3]
    pires1 = [k for k in lus1 if erreur(d1[k]) > 3]
    ligne = {"niveaux": len(communs), "lus": [len(lus0), len(lus1)], "plus_de_3pct": [len(pires0), len(pires1)],
             "murs_justes": [b0["murs"]["justes_pct"], b1["murs"]["justes_pct"]],
             "murs_en_trop": [b0["murs"]["en_trop"], b1["murs"]["en_trop"]],
             "pieces_trouvees": [b0["pieces"]["trouvees_pct"], b1["pieces"]["trouvees_pct"]],
             "ouvertures_justes": [b0["ouvertures"]["justes_pct"], b1["ouvertures"]["justes_pct"]],
             "bon_type": [b0["pieces"]["bon_type_pct"], b1["pieces"]["bon_type_pct"]],
             "parfaits": [b0["plans_parfaits_pct"], b1["plans_parfaits_pct"]],
             "graves_silencieuses": [(b0.get("doutes") or {}).get("erreurs_silencieuses_graves"), (b1.get("doutes") or {}).get("erreurs_silencieuses_graves")],
             "perdus": len(perdus), "gagnes": len(gagnes), "echelles_changees": len(changes)}
    sortie[nom] = ligne
    print(f"\n=== {nom} (référence {ref}) : avant → après")
    for k, v in ligne.items():
        print(f"  {k} : {v}")
    print("  erreurs > 3 % après :", [(k, round(erreur(d1[k]), 2), d1[k]["echelle_lue"].get("source")) for k in pires1][:10])
    print("  échelles perdues :", [(k, d0[k]["echelle_lue"].get("source"), round(erreur(d0[k]), 2), d1[k].get("coloriage_douteux")) for k in perdus][:12])
    print("  échelles gagnées :", [(k, d1[k]["echelle_lue"].get("source"), round(erreur(d1[k]), 2)) for k in gagnes][:12])
    print("  plus grands changements :", sorted(((round(erreur(d1[k]) - erreur(d0[k]), 2), k) for k in changes), key=lambda t: -abs(t[0]))[:6])
(A / "comparaison-echelle.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
