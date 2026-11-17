r"""Mesure des ZONES de sol (un autre sol dans une pièce) sur app-001 et app-002 (vérités des sols, caméras relevées à la main) et
sur app-004 : la règle « pas de zone là où la plupart des photos voient un meuble » (ZONE_PROPRE_MIN) retire-t-elle de vraies zones ?

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_zones_de_sol.py
"""
import json
import sys
from pathlib import Path

import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
from moteur import pas_du_sol, reconnaitre_sols as rs  # noqa: E402
from moteur.oeil_dinov2 import charger  # noqa: E402

CAS = {"app-001": (RACINE / "verites/app-001/cameras-photos.json", PC / "lectures-claude/app-001/logement.json", PC / "b2/app-001/brique-photos/verite-logement-sols.json"),
       "app-002": (RACINE / "verites/app-002/cameras-photos.json", RACINE / "verites/app-002/logement.json", PC / "b2/app-002/examen/logement-verite-sols.json"),
       "app-004": (PC / "b2/app-004/chaine-v2/cameras-photos-seul.json", PC / "b2/app-004/chaine-v2/logement-depart.json", None)}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
clf = rs.Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
oeil = charger(clf.oeil)
pds = pas_du_sol.charger(avec_dino=False)
for nom, (releve, logement, verite) in CAS.items():
    releve, logement = lire(releve), lire(logement)
    for p in logement["pieces"]:
        p.pop("sol", None)
        p["zones_sol"] = []
    for titre, seuil in (("sans la règle", 0.0), ("zones propres (0,5)", 0.5), ("zones propres (0,35)", 0.35)):
        rs.ZONE_PROPRE_MIN = seuil
        r = rs.reconnaitre(releve, logement, RACINE, oeil, clf, pas_du_sol=lambda n, rgb, cas=nom: pds.masque(f"{cas}/{n}", rgb))  # clé par logement : deux logements ont une « photo-01 »
        if verite:
            n = rs.noter(r, lire(verite))
            vz = sum(v["zones_attendues"] for v in n["pieces"].values()); tz = sum(v["zones_trouvees"] for v in n["pieces"].values())
            print(f"{nom} | {titre:22s} | sol juste {100 * n['surface_juste']:.1f} % sur {n['surface_jugee_m2']} m², pièces {n['pieces_justes']}, zones trouvées {tz} pour {vz} vraies", flush=True)
        else:
            print(f"{nom} | {titre:22s} | " + " ; ".join(f"{pid} {s['famille']}" + "".join(f" +zone {z['famille']} {z['surface_m2']} m²" for z in s["zones"]) for pid, s in r["pieces"].items()), flush=True)
