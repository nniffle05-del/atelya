r"""LE SOL PRIS POUR UN LIT, 2e TEMPS (25/11/2026) : le banc des pièces jumelles rejoué avec la règle partagée du sol et du
plafond DANS LE CALAGE (moteur.caler_photos.SOL_JUSTE_AU_CALAGE), contre le calage d'aujourd'hui.

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles_sol.py mesurer temoin|sol [app-001 app-002 app-003]
    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles_sol.py juger [détail]

Mêmes tirages que jumelles.py (99 rejouements des trois logements : photo(s) en moins, plan faux de 3 à 8 %, autre zoom), avec
les règles en service (« coupe »). Un lancement par variante (la mémoire des profils ne connaît pas le drapeau). L'affinage des
appareils est éteint ici : il vient APRÈS le choix des pièces et du « sûr », qu'il ne change pas.
Sorties : ..\atelya\b2\cameras-seules\jumelles-sol\<temoin|sol>\<logement>.json
Ce qu'on compte : les photos « sûres » dans une MAUVAISE pièce (il en faut le moins possible, aucune de plus qu'aujourd'hui),
et les photos sûres et justes (il n'en faut pas moins).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import jumelles  # noqa: E402
from jumelles import LOGEMENTS, PC, cp  # noqa: E402
from jumelles_juger import compter, nouveau  # noqa: E402

SORTIE = PC / "b2/cameras-seules/jumelles-sol"
DRAPEAU = {"temoin": False, "sol": True}


def mesurer(variante: str, noms: list[str]) -> None:
    cp.SOL_JUSTE_AU_CALAGE = DRAPEAU[variante]
    cp.AFFINER = False
    jumelles.VARIANTES = {"coupe": True}
    jumelles.SORTIE = SORTIE / variante
    print(f"variante {variante} : sol juste au calage = {cp.SOL_JUSTE_AU_CALAGE}", flush=True)
    jumelles.mesurer(noms or list(LOGEMENTS))


def juger(detail: bool) -> None:
    total = {v: {"tirages": 0, "justes": 0, "meme": 0, "autre": 0, "sures_service": 0} for v in DRAPEAU}
    for nom, f in LOGEMENTS.items():
        tout = {}
        for v in DRAPEAU:
            chemin = SORTIE / v / f"{nom}.json"
            if chemin.is_file():
                tout[v] = json.loads(chemin.read_text(encoding="utf-8"))["coupe"]
        if len(tout) < 2:
            print(f"{nom} : pas encore mesuré dans les deux variantes"); continue
        for lot, quels in (("tirages regardés", lambda t: not nouveau(t)), ("tirages NOUVEAUX", nouveau), ("TOUS", lambda t: True)):
            for v in DRAPEAU:
                b = compter(tout[v], f["vrai"], quels)
                print(f"{nom} {lot:17s} {v:7s} : {b['tirages']} tirages, sûres et justes {b['justes']}, sûres et FAUSSES {b['fausses_meme_sorte']} (même sorte)"
                      f" + {b['fausses_autre_sorte']} (autre sorte)")
                if lot == "TOUS":
                    t = total[v]
                    t["tirages"] += b["tirages"]; t["justes"] += b["justes"]; t["meme"] += b["fausses_meme_sorte"]; t["autre"] += b["fausses_autre_sorte"]
                    for c in b["cas"] if detail else []:
                        print(f"      {c}")
        # en service (toutes les photos, plan tel quel) : photo par photo
        a, b = tout["temoin"]["service"]["cameras"], tout["sol"]["service"]["cameras"]
        for v, t in (("temoin", a), ("sol", b)):
            total[v]["sures_service"] += sum(d["sure"] for d in t.values())
        for n in sorted(set(a) | set(b)):
            da, db = a.get(n), b.get(n)
            if da is None or db is None:
                print(f"   {nom} {n} : placée seulement dans {'temoin' if db is None else 'sol'}"); continue
            juste = lambda d: "juste" if d["piece"] in f["vrai"][n] else "FAUX"
            bouge = ((da["cam"][0] - db["cam"][0]) ** 2 + (da["cam"][1] - db["cam"][1]) ** 2) ** 0.5
            if da["piece"] != db["piece"] or da["sure"] != db["sure"] or bouge > 0.3 or detail:
                print(f"   {nom} {n} : {da['piece']} ({juste(da)}{', sûre' if da['sure'] else ''}) → {db['piece']} ({juste(db)}{', sûre' if db['sure'] else ''})"
                      f", déplacée de {bouge:.2f} m")
    for v, t in total.items():
        print(f"TOTAL {v:7s} : {t['tirages']} tirages, sûres et justes {t['justes']}, sûres et FAUSSES {t['meme']} (même sorte) + {t['autre']} (autre sorte)"
              f" ; en service : {t['sures_service']} photos sûres")
    (SORTIE / "bilan.json").write_text(json.dumps(total, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    try:
        if sys.argv[1] == "mesurer":
            mesurer(sys.argv[2], sys.argv[3:])
        else:
            juger("détail" in sys.argv or "detail" in sys.argv)
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
