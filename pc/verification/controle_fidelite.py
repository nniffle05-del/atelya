"""Compare la commande de lecture complète au banc v041 (essai 5, sans noms) sur des niveaux déjà notés."""
import json, sys, time
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, ".")
sys.path.insert(0, "outils/atelya")
from lire_plan import colorieurs  # noqa
from moteur.lecture_complete import lire_plan, plans_du_fichier  # noqa

A = Path("../atelya")
banc = A / "banc-v041-apres-e5"
jeu = A / "jeu-test-6-13" / "exemples"
col_dir = A / "coloriages-a1-apres" / "exemples"
details = json.loads((banc / "details.json").read_text(encoding="utf-8"))
details = details if isinstance(details, list) else details.get("details", details.get("niveaux"))
print("exemple de clés :", sorted(details[0])[:12], flush=True)
print("logements :", sorted(p.name for p in (banc / "logements").iterdir())[:3], flush=True)
lus = [d for d in details if d.get("echelle_lue") and d["echelle_lue"].get("largeur")]
biais = [d for d in lus if d.get("redresse")]
plats = [d for d in lus if not d.get("redresse")]
choix = plats[:: max(1, len(plats) // 14)][:14] + biais[:: max(1, len(biais) // 6)][:6]
print(f"{len(lus)} lus dont {len(biais)} redressés ; choisis {len(choix)}", flush=True)
f = colorieurs(A, ["e5"])
bad = 0
for d in choix:
    plan, niv = d["plan"], d["niveau"]
    dossier = jeu / plan / f"niveau_{niv}"
    nom = (col_dir / plan / f"niveau_{niv}" / "dessin.txt")
    nom = nom.read_text(encoding="utf-8").strip() if nom.exists() else None
    fichier = next(x for x in ([dossier / nom] if nom else []) + [dossier / "plan.png", dossier / "plan.jpg"] if x.exists())
    t0 = time.time()
    p = lire_plan(plans_du_fichier(fichier)[0], f, avec_noms=False)
    g = p.gardee
    ref_col = np.array(Image.open(col_dir / plan / f"niveau_{niv}.png"))
    col_ok = g.coloriage.shape == ref_col.shape and int((g.coloriage != ref_col).sum())
    el = d["echelle_lue"]
    ecart = abs(g.echelle.get("px_par_m_largeur", 0) / el["largeur"] - 1) * 100
    ref_log = next((banc / "logements").glob(f"{plan}*{niv}*.json"), None)
    murs = "?"
    if ref_log:
        r = json.loads(ref_log.read_text(encoding="utf-8"))
        a = [(m["debut"], m["fin"]) for m in r["murs"]]
        b = [(m["debut"], m["fin"]) for m in (g.logement or {"murs": []})["murs"]]
        murs = "identiques" if a == b else f"{len(a)} vs {len(b)} DIFF"
    decision_ref = (d.get("doutes") or {}).get("decision")
    ok = col_ok == 0 and ecart < 1e-6 and murs == "identiques" and decision_ref == p.decision
    bad += not ok
    print(f"{plan} N{niv} redresse={d.get('redresse')} coloriage_diff_px={col_ok} echelle_ecart={ecart:.6f}% murs={murs} "
          f"decision={decision_ref}/{p.decision} {time.time()-t0:.1f}s {'OK' if ok else 'ECART'}", flush=True)
print(f"FINI : {len(choix) - bad}/{len(choix)} identiques", flush=True)
