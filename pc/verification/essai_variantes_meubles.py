r"""Essai de VARIANTES du repérage des meubles, jugées sur les trois logements du banc à la fois : contre les meubles relevés à
la main (app-001, app-002) ET par le banc de fidélité (présence et place des objets sur chaque photo).

    ..\atelya\.venv\Scripts\python.exe pc\verification\essai_variantes_meubles.py <dossier d'un banc de fidélité déjà passé>

Le dossier du banc donne, pour chaque logement, le logement avec ses sols (logement-sols.json) : seuls les meubles sont refaits.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
from banc_fidelite import Detecteur, juger  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402

from moteur import fidelite_photos as fp  # noqa: E402
from moteur import reperer_meubles as rm  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.owlv2 import charger  # noqa: E402
from moteur.ranger_meubles import ranger  # noqa: E402

VERITES = {"app-001": RACINE / "verites/app-001/meubles.json", "app-002": RACINE / "verites/app-002/meubles.json"}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def variantes() -> dict:
    """nom → fonction qui règle le module reperer_meubles (rendre une fonction qui remet tout en place n'est pas utile : chaque
    variante règle TOUT ce qu'elle touche)."""
    def regler(uniques, grappes, precis=True):
        def f():
            rm.UNIQUES, rm.EN_GRAPPE = uniques, grappes
            return precis
        return f
    return {"groupe seul (avant ce soir)": regler(("table", "canape", "lit", "fauteuil"), ("chaise",), precis=False),
            "précis, plafond des tables": regler(("table", "canape", "lit", "fauteuil"), ("chaise",)),
            "précis, sans plafond de tables (en service)": regler(("canape", "lit", "fauteuil"), ("chaise",))}


def main() -> int:
    banc = Path(sys.argv[1])
    owl, detecteur = charger(), Detecteur()
    for titre, regler in variantes().items():
        precis = regler()
        toutes, lignes = [], []
        for cas in CAS:
            logement, fiche = lire(banc / cas / "logement-sols.json"), lire(CAS[cas]["fiche"])
            logement["meubles"] = []
            ms, _ = ranger(rm.vers_meubles_du_logement(rm.reperer_depuis_releve(fiche, logement, RACINE, owl=owl, precis=precis), logement), logement)
            logement["meubles"] = ms
            j = juger(cas, logement, fiche, detecteur)
            toutes += list(j["photos"].values())
            ligne = f"{cas} fidélité {j['resume']['fidelite']:.1f} ({len(ms)} meubles)"
            if cas in VERITES:
                cams = [camera_depuis_dict(d["camera"]) for d in fiche["cameras"].values()]
                n = rm.noter_meubles([{"groupe": rm.groupe(m["categorie"]), "position": m["position"]} for m in ms], lire(VERITES[cas])["meubles"],
                                     cameras=cams, logement=logement)
                ligne += f", relevé : retrouvés {n['retrouves']}, en trop {n['en_trop']}"
            lignes.append(ligne)
        e = fp.compter(toutes)
        print(f"{titre:34s} | ENSEMBLE fidélité {e['fidelite']:.1f} (couverture {100 * e['couverture']:.1f} %, justesse {100 * e['justesse']:.1f} %) | " + " | ".join(lignes), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
