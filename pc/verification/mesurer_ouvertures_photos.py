r"""Mesure de la lecture des baies sur les photos (moteur/ouvertures_photos.py) : votes par baie, contre la sorte connue."""
import json, sys
from pathlib import Path
RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
from moteur import moge, ouvertures_photos as op

CAS = {"app-001": (RACINE / "verites/app-001/cameras-photos.json", PC / "lectures-claude/app-001/logement.json"),
       "app-002": (RACINE / "verites/app-002/cameras-photos.json", RACINE / "verites/app-002/logement.json"),
       "app-003": (RACINE / "verites/app-003/cameras-photos.json", RACINE / "verites/app-003/logement.json"),
       "app-004": (PC / "lectures-claude/app-004/questions-photos/cameras-photos-seul.json", PC / "lectures-claude/app-004/logement-verifie.json")}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
class O: pass
o = O(); o.moge = moge.charger()
for nom, (releve, logement) in CAS.items():
    releve, logement = lire(releve), lire(logement)
    votes = op.lire(logement, releve, RACINE, outils=o, journal=print if "--detail" in sys.argv else None)
    print(f"== {nom}", flush=True)
    for ouv in logement["ouvertures"]:
        if ouv["type"] == "porte": continue
        s, a = votes.get(ouv["id"], (0, 0))
        print(f"   {ouv['id']:5s} {ouv['type']:14s} allège {ouv.get('allege', 0):.2f} largeur {ouv['largeur']:.2f} | jusqu'au sol {s:3d}, sur allège {a:3d}")
    _, ch = op.corriger(logement, votes)
    print("   changements :", [(c["id"], c["avant"], "→", c["apres"], c["votes"]) for c in ch], flush=True)
