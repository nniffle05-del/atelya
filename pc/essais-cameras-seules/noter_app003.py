r"""Note en mètres des photos calées seules sur app-003, contre le corrigé verites/app-003/cameras-photos.json (15/11/2026).
Atelya cale les 19 photos (comme en service) ; on note les 10 du corrigé. Variantes : avec / sans le zoom des lignes de fuite.

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\noter_app003.py [sans] [avec]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
import caler_photos_seul as outil  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402


def noter(resultat, corrige, titre):
    lignes = []
    for n, k in corrige.items():
        d = resultat["cameras"].get(n)
        if d is None:
            print(f"  {n} : non calée"); continue
        c, v = d["camera"], k["camera"]
        e = math.hypot(c["x"] - v["x"], c["y"] - v["y"]); dc = abs((c["cap"] - v["cap"] + 180) % 360 - 180)
        ax = (math.cos(math.radians(v["cap"])), math.sin(math.radians(v["cap"])))
        recul = (c["x"] - v["x"]) * ax[0] + (c["y"] - v["y"]) * ax[1]
        lignes.append((e, dc, d["piece"] == k["piece"], d["sure"]))
        print(f"  {n} {d['piece']:10s} {e:.2f} m (recul {recul:+.2f}) {dc:4.1f}° zoom {c['f']:.0f} {'sûre' if d['sure'] else 'PAS SÛRE'}{'' if d['piece'] == k['piece'] else '  MAUVAISE PIÈCE'}")
    t = np.array(lignes, float)
    print(f"== {titre} : médiane {np.median(t[:, 0]):.2f} m, moyenne {t[:, 0].mean():.2f}, pire {t[:, 0].max():.2f} ; cap médian {np.median(t[:, 1]):.1f}° ;"
          f" bien (<0,5 m, <8°) {int(((t[:, 0] < 0.5) & (t[:, 1] < 8)).sum())}, à peu près (<1 m, <15°) {int(((t[:, 0] < 1) & (t[:, 1] < 15)).sum())},"
          f" bonne pièce {int(t[:, 2].sum())}, sûres {int(t[:, 3].sum())} sur {len(t)}")
    return t


def main():
    logement = json.loads((RACINE / "verites/app-003/logement.json").read_text(encoding="utf-8"))
    corrige = json.loads((RACINE / "verites/app-003/cameras-photos.json").read_text(encoding="utf-8"))["cameras"]
    dossier = RACINE / "../atelya/photos-clients/app-003/photos"
    photos, modele = outil.lire_photos(dossier)
    o = cp.Outils()
    for variante in (sys.argv[1:] or ["sans", "avec"]):
        r = cp.caler(logement, photos, outils=o, journal=lambda *a: None, zoom_par_fuites={"sans": False, "avec": True, "fin": "fin"}[variante])
        sures = sum(1 for d in r["cameras"].values() if d["sure"])
        print(f"\n--- {variante} le zoom des lignes de fuite : {sures} photos sûres sur {len(photos)}")
        for n, d in r["cameras"].items():
            if n not in corrige:
                print(f"  ({n} {d['piece']} {'sûre' if d['sure'] else 'pas sûre'})")
        noter(r, corrige, variante)
        sortie = RACINE / f"../atelya/b2/app-003/corrige/cameras-seul-{variante}.json"
        sortie.write_text(json.dumps(outil.fiche(r, dossier, modele), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
