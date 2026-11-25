r"""Mesure du rangement des meubles (moteur/ranger_meubles.py) sur les logements à corrigé (app-001, app-002, caméras relevées
à la main) et sur app-004 : meubles retrouvés / en trop et paires de meubles qui se traversent, AVANT et APRÈS le rangement.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_rangement_meubles.py
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.owlv2 import charger  # noqa: E402
from moteur.ranger_meubles import chevauchements, ranger  # noqa: E402
from moteur.reperer_meubles import groupe, noter_meubles, reperer_depuis_releve, vers_meubles_du_logement  # noqa: E402

CAS = {"app-001": (RACINE / "verites/app-001/cameras-photos.json", PC / "lectures-claude/app-001/logement.json", RACINE / "verites/app-001/meubles.json"),
       "app-002": (RACINE / "verites/app-002/cameras-photos.json", RACINE / "verites/app-002/logement.json", RACINE / "verites/app-002/meubles.json"),
       "app-004": (PC / "lectures-claude/app-004/questions-photos/cameras-photos-seul.json", PC / "b2/app-004/chaine/logement-sols.json", None)}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
owl = charger()
for nom, (releve, logement, verite) in CAS.items():
    releve, logement = lire(releve), lire(logement)
    logement["meubles"] = []
    avant = vers_meubles_du_logement(reperer_depuis_releve(releve, logement, RACINE, owl=owl), logement)
    apres, actions = ranger(avant, logement)
    cams = [camera_depuis_dict(d["camera"]) for d in releve["cameras"].values()]
    for titre, ms in (("avant", avant), ("après", apres)):
        ligne = f"{nom} {titre} : {len(ms)} meubles, {len(chevauchements(ms))} paires qui se traversent"
        if verite:
            n = noter_meubles([{"groupe": groupe(m["categorie"]), "position": m["position"]} for m in ms], lire(verite)["meubles"], cameras=cams, logement=logement)
            ligne += f" ; retrouvés {n['retrouves']}, en trop {n['en_trop']}, écart {n['ecart_moyen_m']} m ; {n['par_groupe']}"
        print(ligne, flush=True)
    for a in actions:
        print(f"     {a['categorie']} {a['id']} {a['action']} : {a['raison']}", flush=True)
