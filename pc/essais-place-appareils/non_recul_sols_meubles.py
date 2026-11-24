r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : NON-RECUL des sols et des meubles posés d'après les appareils d'Atelya,
avant (« service » : calage sans affinage) et après (« defaut » : appareils affinés dans l'image), sur app-001 et app-002
(les deux logements dont les sols et les meubles ont été relevés à la main).

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\non_recul_sols_meubles.py [service defaut]

Les appareils sont ceux des fiches de caler.py (..\atelya\b2\place-appareils\<variante>\<logement>.json : pièce donnée par le
client pour chaque photo). Mêmes briques et même notation que pc\essais-cameras-seules\pieces_donnees.py (sols : part de la
surface jugée qui est juste ; meubles : retrouvés à moins de 80 cm, de la bonne sorte, en trop).
"""
import json
import sys
from pathlib import Path

import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from juger import SORTIE, lire  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.oeil_dinov2 import charger as charger_oeil  # noqa: E402
from moteur.pas_du_sol import charger as charger_pds  # noqa: E402
from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre  # noqa: E402
from moteur.reperer_meubles import noter_meubles, reperer_depuis_releve  # noqa: E402
from non_recul_examens import EXAMENS  # noqa: E402


def main():
    variantes = [a for a in sys.argv[1:] if not a.startswith("--")] or ["service", "defaut"]
    clf = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
    oeil = charger_oeil("vits14")
    pds = charger_pds(avec_dino=False)
    bilan = {}
    for nom, ex in EXAMENS.items():
        logement, main_ = lire(ex["logement"]), lire(ex["releve"])
        sans_sols = json.loads(json.dumps(logement))
        for p in sans_sols["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        cams = [camera_depuis_dict(d["camera"]) for d in main_["cameras"].values()]
        for v in variantes:
            f = lire(SORTIE / v / f"{nom}.json")
            fiche = {"photos": Path(f["photos"]).as_posix(), "fichier": f["fichier"], "cameras": {n: d for n, d in f["cameras"].items() if d["sure"]}}
            note = noter(reconnaitre(fiche, sans_sols, RACINE, oeil, clf, pas_du_sol=lambda n, rgb: pds.masque(f"{nom}/{n}", rgb)), lire(ex["verite_sols"]))
            m = noter_meubles(reperer_depuis_releve(fiche, logement, RACINE, owl=pds.owl), lire(ex["meubles"])["meubles"], cameras=cams, logement=logement)
            bilan[f"{nom} {v}"] = {"photos": len(fiche["cameras"]), "sols": {k: note.get(k) for k in ("surface_jugee_m2", "surface_juste", "pieces_justes")}, "meubles": m}
            print(f"{nom} [{v}] {len(fiche['cameras'])} photos | sols : {note.get('surface_juste')} justes sur {note.get('surface_jugee_m2')} m² jugés "
                  f"({note.get('pieces_justes')}) | meubles : {m}", flush=True)
    (SORTIE / "non-recul-sols-meubles.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
