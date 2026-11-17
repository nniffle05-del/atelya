r"""Mesure des LUMINAIRES SUSPENDUS trouvés seuls (moteur/objets_accroches.py) contre ceux relevés à la main (app-001, app-002,
caméras relevées à la main), et ce que le banc de fidélité en dit sur les trois logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_suspensions.py <dossier d'un banc de fidélité déjà passé>
"""
import json
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
from banc_fidelite import Detecteur, juger  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402

from moteur import fidelite_photos as fp  # noqa: E402
from moteur import moge, objets_accroches as oa  # noqa: E402
from moteur.owlv2 import charger  # noqa: E402

VERITES = {"app-001": RACINE / "verites/app-001/meubles.json", "app-002": RACINE / "verites/app-002/meubles.json"}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
banc = Path(sys.argv[1])
owl, modele, detecteur = charger(), moge.charger(), Detecteur()
avant, apres = [], []
for cas in CAS:
    logement, fiche = lire(banc / cas / "logement-meuble.json"), lire(CAS[cas]["fiche"])
    avant += list(juger(cas, logement, fiche, detecteur)["photos"].values())
    trouves = oa.reperer_suspensions(fiche, logement, RACINE, owl=owl, modele_moge=modele)
    ligne = f"{cas} : {len(trouves)} luminaires trouvés " + str([(m["piece"], m["position"], m["dimensions"], m["altitude"], m["source"][-11:]) for m in trouves])
    if cas in VERITES:
        vrais = [m for m in lire(VERITES[cas])["meubles"] if m["categorie"] == "suspension"]
        libres, ecarts = list(range(len(trouves))), []
        for v in vrais:
            c = [(math.dist(trouves[i]["position"], v["position"]), i) for i in libres]
            c = [x for x in c if x[0] <= 1.0]
            if c:
                d, i = min(c)
                libres.remove(i)
                ecarts.append(d)
        ligne += f"\n   relevé à la main : {len(vrais)} luminaires ; retrouvés {len(ecarts)} (à {sum(ecarts) / max(len(ecarts), 1):.2f} m en moyenne), en trop {len(libres)}"
    print(ligne, flush=True)
    logement["meubles"] = list(logement.get("meubles", [])) + trouves
    apres += list(juger(cas, logement, fiche, detecteur)["photos"].values())
a, b = fp.compter(avant), fp.compter(apres)
la, lb = a["par_sorte"].get("luminaire", {}), b["par_sorte"].get("luminaire", {})
print(f"BANC, les trois logements : fidélité {a['fidelite']:.1f} → {b['fidelite']:.1f} ; couverture {100 * a['couverture']:.1f} → {100 * b['couverture']:.1f} % ; "
      f"justesse {100 * a['justesse']:.1f} → {100 * b['justesse']:.1f} % ; luminaires présents {la.get('presents')} → {lb.get('presents')} sur {lb.get('vus')} "
      f"(bien placés {lb.get('bien_places')}, en trop {lb.get('en_trop')} sur {lb.get('dans_la_maquette')})", flush=True)
