"""Étape 6-16 : examiner les échelles fausses (cotes lues une à une). Lancer depuis atelya/code-6-16."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from moteur.banc_coloriage import dessin_du_niveau, echelle_pour_atelya, echelles_apres_redressement
from moteur.echelle_plan import lire_echelle_plan
from moteur.redressement import corriger_proportions, estimer_redressement, photo_entiere, rapport_par_optique, rapport_plausible

JEU, COL = Path(sys.argv[1]), Path(sys.argv[2])
sortie = {}
for cas in sys.argv[3:]:
    plan, niv = cas.split(":")
    ex = JEU / "exemples" / plan
    niveau = ex / f"niveau_{niv}"
    ann = json.loads((niveau / "annotations.json").read_text(encoding="utf-8"))
    col = np.array(Image.open(COL / plan / f"niveau_{niv}.png"), np.uint8)
    taille = (ann["image"]["largeur"], ann["image"]["hauteur"])
    s, _ = echelle_pour_atelya(ann, taille)
    R = estimer_redressement(col)
    rapport = rapport_par_optique(R, col.shape) if photo_entiere(*taille) else None
    if rapport and rapport_plausible(rapport):
        R = corriger_proportions(R, rapport)
    vx, vy = echelles_apres_redressement(R, ann, s / ann["image"]["px_par_m"])
    dessin = dessin_du_niveau(niveau, None)
    e = lire_echelle_plan(np.array(Image.open(dessin).convert("L")), col, R)
    cotes = [{"valeur": c.valeur, "px": round(c.longueur_px, 2), "verticale": c.verticale,
              "px_par_m_dessin": round(c.px_par_m, 3), "texte": str(c.texte), "bouts": c.bouts} for c in e.cotes]
    sortie[cas] = {"vraie_largeur": vx, "vraie_hauteur": vy, "lue_largeur": e.largeur, "lue_hauteur": e.hauteur,
                   "sure": e.sure, "rapport_optique": rapport, "cote_max": [e.cote_max_largeur, e.cote_max_hauteur],
                   "interieur_px": e.interieur_px, "barre": e.barre, "surfaces": e.surfaces, "surfaces_sure": e.surfaces_sure,
                   "approchee": e.approchee, "douteux": e.douteux, "cotes": cotes}
print(json.dumps(sortie, ensure_ascii=False, indent=1, default=str))
