r"""L'EMPRISE des meubles qui ne sont pas contre un mur, mesurée vue par vue dans le relief de la photo (étape 3, 17/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_emprises.py [--cas app-001 app-002 app-004] [--sortes canape table …]

Pourquoi : la taille de ces meubles est aujourd'hui celle d'un meuble courant de leur sorte (tout canapé = 2,00 m, toute table =
1,40 m). Cette commande ne pose rien : pour chaque photo et chaque meuble lu d'une sorte « libre » (canapé, table, lit, îlot…),
elle mesure son emprise au sol (moteur.photos_lues.emprise_d_un_meuble) et la met à côté du meuble du relevé fait à la main le plus
proche de la même sorte : grand côté, petit côté, sens du grand côté, écart de place. C'est le diagnostic vue par vue ; la note
d'ensemble reste mesurer_tailles.py sur la chaîne.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import essai_lecture_photos as essai  # noqa: E402
import poser_photos_lues as ppl  # noqa: E402
from banc_ressemblance import CAS, PC  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur import moge, photos_lues  # noqa: E402
from moteur import reperer_meubles as rm  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.sol_a_plat import piece_de  # noqa: E402

# le canapé bleu d'app-004 n'a pas de relevé : deux places, ~1,5 m (photos 02 et 07 ; essai du 16/11/2026)
A_LA_MAIN = {"app-004": [{"id": "canape_bleu (estimé)", "categorie": "canape", "position": None, "dimensions": [1.5, 0.9, 0.85], "face": 0}]}


def cotes_du_vrai(v: dict) -> tuple[float, float, float]:
    """(grand côté, petit côté, direction du grand côté en degrés modulo 180) d'un meuble du relevé."""
    l, p = float(v["dimensions"][0]), float(v["dimensions"][1])
    face = float(v.get("face", 0.0) or 0.0)
    return (l, p, (face + 90.0) % 180.0) if l >= p else (p, l, face % 180.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--sortes", nargs="*", default=list(photos_lues.LIBRES))
    ap.add_argument("--depart", type=Path, default=PC / "lectures-photos/place-taille/etape2-rangees")
    a = ap.parse_args()
    modele = moge.charger()
    ecarts: dict[str, list[tuple[float, float]]] = {}
    for cas in a.cas:
        fiche = essai.lire(CAS[cas]["fiche"])
        logement = essai.lire(a.depart / cas / "c" / "logement-sols.json")
        hsp = float(logement.get("hauteur_sous_plafond", 2.5))
        objets = ppl.objets_des_photos(fiche, PC / "lectures-photos" / cas)
        releve = essai.charger_releve(cas) if cas in essai.VERITES else A_LA_MAIN.get(cas, [])
        dossier, fichier = RACINE / fiche["photos"], fiche.get("fichier", "{nom}.png")
        for nom, d in fiche["cameras"].items():
            lus = objets.get(nom) or []
            if not any(o["sorte"] in a.sortes for o in lus):
                continue
            image = lire_image(dossier / fichier.format(nom=nom))
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            hauteur, largeur = rgb.shape[:2]
            cam = camera_depuis_dict(d["camera"])
            repere = cp.repere(cp.mesurer(modele, rgb, float(d["camera"]["f"])), hsp)
            if repere is None:
                continue
            for o in lus:
                if o["sorte"] not in a.sortes:
                    continue
                autres = [x["boite"] for x in lus if x is not o and rm.groupe(x["sorte"]) in rm.TYPE_DE_GROUPE and rm.groupe(x["sorte"]) != "tapis"]
                e = photos_lues.emprise_d_un_meuble(o["boite"], o["sorte"], repere, d["camera"], largeur, hauteur, logement, autres=autres)
                if e is None:
                    print(f"{cas} {nom} n°{o['numero']:<3} {o['sorte']:14s} : rien de mesurable")
                    continue
                memes = [v for v in releve if v["categorie"] == o["sorte"]]
                vrai = min(memes, key=lambda v: math.dist(v["position"], e["position"]) if v["position"] else 0.0, default=None)
                ligne = (f"{cas} {nom} n°{o['numero']:<3} {o['sorte']:14s} à {e['distance']:.1f} m : mesuré {e['grand']:.2f} × {e['petit']:.2f} m, "
                         f"grand côté à {e['sens']:5.1f}°, milieu ({e['position'][0]:.2f} ; {e['position'][1]:.2f})" + (" (coupé)" if e["coupe"] else "") + f" [{e['points']} cases]")
                if vrai is not None and (vrai["position"] is None or math.dist(vrai["position"], e["position"]) < 1.5):
                    g, p, s = cotes_du_vrai(vrai)
                    ecart_sens = abs((e["sens"] - s + 90.0) % 180.0 - 90.0)
                    ligne += f" | vrai {g:.2f} × {p:.2f} m à {s:5.1f}° ({vrai["id"]})"
                    if vrai["position"] is not None:
                        ligne += f", centre à {math.dist(vrai['position'], e['position']):.2f} m"
                    if not e["coupe"]:
                        ecarts.setdefault(o["sorte"], []).append((abs(e["grand"] - g) / g, abs(e["petit"] - p) / p, ecart_sens))
                print(ligne, flush=True)
    print()
    for sorte, l in sorted(ecarts.items()):
        print(f"{sorte:14s} {len(l):2d} vues entières : grand côté faux de {100 * np.mean([x[0] for x in l]):.0f} % en moyenne, "
              f"petit côté de {100 * np.mean([x[1] for x in l]):.0f} %, sens faux (> 30°) {sum(1 for x in l if x[2] > 30)} fois")
    return 0


if __name__ == "__main__":
    sys.exit(main())
