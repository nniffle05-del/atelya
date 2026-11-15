r"""Le bilan des tirages rangés par jumelles.py : AVANT (chaîne du 14/11/2026) contre APRÈS (moteur/caler_photos.py 0.2.0 :
marge d'ensemble, sous-groupes de photos qui se revoient, seuil × racine du nombre de photos).

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles.py juger [détail] [regles]

Pour chaque logement : photos sûres et JUSTES, photos sûres et FAUSSES (séparées en « même sorte de pièce » : chambre prise
pour une autre chambre, séjour pour la salle à manger = le sujet de l'étape ; et « autre sorte » : cuisine, salle d'eau ou
chambre rangée dans le séjour = l'étape suivante). Les tirages « nouveaux » (plan ±3 % et ±8 %, deux photos en moins) n'ont
PAS été regardés pour choisir les règles : c'est le contrôle le moins flatteur.
« regles » : rejuge aussi les tirages d'après avec d'autres seuils, sans rien recalculer.
Sortie : ..\atelya\b2\cameras-seules\jumelles\bilan.json
"""
import json
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur import caler_photos as cp  # noqa: E402
from jumelles import LOGEMENTS, SORTIE  # noqa: E402

NOUVEAUX = ("plan+3", "plan-3", "plan+8", "plan-8", "sans-2-")  # tirages ajoutés APRÈS le choix des règles


def nouveau(titre: str) -> bool:
    return titre.startswith(NOUVEAUX)


def compter(tirages, vrai, quels):
    b = {"tirages": 0, "justes": 0, "fausses_meme_sorte": 0, "fausses_autre_sorte": 0, "cas": []}
    for titre, t in tirages.items():
        if not quels(titre):
            continue
        b["tirages"] += 1
        for n, d in t["cameras"].items():
            if not d["sure"]:
                continue
            if d["piece"] in vrai[n]:
                b["justes"] += 1
            else:
                meme = cp.sorte_de_piece(d["piece"]) in {cp.sorte_de_piece(p) for p in vrai[n]}
                b["fausses_meme_sorte" if meme else "fausses_autre_sorte"] += 1
                b["cas"].append(f"{titre} : photo {n[-2:]} ({vrai[n][0]}) → {d['piece']}")
    return b


def main(args):
    detail = "détail" in args or "detail" in args
    bilan = {}
    for nom, f in LOGEMENTS.items():
        chemin = SORTIE / f"{nom}.json"
        if not chemin.is_file():
            print(f"{nom} : pas encore mesuré"); continue
        tout = json.loads(chemin.read_text(encoding="utf-8"))
        bilan[nom] = {}
        for lot, quels in (("tirages regardés", lambda t: not nouveau(t)), ("tirages NOUVEAUX", nouveau)):
            for variante, titre in (("avant", "AVANT"), ("coupe", "APRÈS")):
                b = compter(tout[variante], f["vrai"], quels)
                bilan[nom][f"{lot} / {titre}"] = b
                print(f"{nom} {lot} {titre} : {b['tirages']} tirages, sûres et justes {b['justes']}, sûres et FAUSSES {b['fausses_meme_sorte']} (même sorte de pièce)"
                      f" + {b['fausses_autre_sorte']} (autre sorte)")
                for c in b["cas"] if (detail or variante == "coupe") else []:
                    print(f"      {c}")
        s = lambda v: [n for n, d in tout[v]["service"]["cameras"].items() if d["sure"]]
        bilan[nom]["service"] = {"avant": s("avant"), "apres": s("coupe"),
                                 "hesitations": {n: d["hesite_avec"] for n, d in tout["coupe"]["service"]["cameras"].items() if d.get("hesite_avec")}}
        print(f"{nom} EN SERVICE : sûres avant {len(s('avant'))}, après {len(s('coupe'))} ; ne sont plus sûres : {[n[-2:] for n in s('avant') if n not in s('coupe')]}"
              f" ; hésitations : { {n[-2:]: h for n, h in bilan[nom]['service']['hesitations'].items()} }")
    for lot in ("tirages regardés", "tirages NOUVEAUX"):
        for titre in ("AVANT", "APRÈS"):
            k = [b[f"{lot} / {titre}"] for b in bilan.values()]
            print(f"TOTAL {lot} {titre} : {sum(x['tirages'] for x in k)} tirages, sûres et justes {sum(x['justes'] for x in k)}, sûres et FAUSSES "
                  f"{sum(x['fausses_meme_sorte'] for x in k)} (même sorte) + {sum(x['fausses_autre_sorte'] for x in k)} (autre sorte)")
    (SORTIE / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    if "regles" in args:
        regles = {"0,4 fixe": lambda n: 0.4, "0,5 fixe": lambda n: 0.5, "0,4 × racine(n) [en service]": cp.seuil_sure, "0,5 × racine(n)": lambda n: 0.5 * math.sqrt(n)}
        for r, seuil in regles.items():
            j = x = 0
            for nom, f in LOGEMENTS.items():
                for t in json.loads((SORTIE / f"{nom}.json").read_text(encoding="utf-8"))["coupe"].values():
                    for u, k, m in zip(t["unites"], t["choix"], t["marges"]):
                        for n in u[k]["photos"]:
                            if n in t["cameras"] and m > seuil(len(u[k]["photos"])):
                                j += t["cameras"][n]["piece"] in f["vrai"][n]; x += t["cameras"][n]["piece"] not in f["vrai"][n]
            print(f"règle {r:30s} : sûres et justes {j}, sûres et FAUSSES {x}")


if __name__ == "__main__":
    main(sys.argv[1:])
