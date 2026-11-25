r"""F2 PIÈCE 3 (20/11/2026) : le DESSIN de chaque fenêtre qu'Atelya tire de la lecture des photos, dit en clair et en mètres.

    ..\atelya\.venv\Scripts\python.exe pc\verification\voir_dessins_fenetres.py <logement.json> <vitrages.json> [<logement de sortie>]

Pour chaque baie lue : ce que chaque photo dit (vantaux, petits bois, bords du cadre, partie pleine, garde-corps), puis le
dessin accordé posé dans la maquette. Avec un 3e chemin : écrit le logement avec ses dessins (pour reconstruire une maquette).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import dessin_fenetres  # noqa: E402
from moteur.logement import Logement  # noqa: E402


def dire(logement: dict, lecture: dict) -> None:
    par_baie: dict[str, dict[str, list[dict]]] = {}
    for photo, fenetres in (lecture.get("photos") or {}).items():
        for f in fenetres:
            par_baie.setdefault(f["baie"], {}).setdefault(photo, []).append(f)
    for o in logement["ouvertures"]:
        if o["id"] not in par_baie or o["type"] == "porte":
            continue
        l, h, allege = float(o["largeur"]), float(o["hauteur"]), float(o.get("allege", 0) or 0)
        print(f"\n{o['id']} ({o['type']}, {l:.2f} × {h:.2f} m, allège {allege:.2f} m)")
        for photo, fs in sorted(par_baie[o["id"]].items()):
            d = dessin_fenetres.d_une_photo(fs, l, h, allege < dessin_fenetres.ALLEGE_AU_SOL)
            if d is None:
                print(f"   {photo} : pas de vitrage dit")
                continue
            vitres = ", ".join(f"{(v['vitrage'][1] - v['vitrage'][0]) * l:.2f}" for v in d["vantaux"])
            entre = ", ".join(f"{(b['vitrage'][0] - a['vitrage'][1]) * l * 100:.0f}" for a, b in zip(d["vantaux"], d["vantaux"][1:]))
            print(f"   {photo} : {len(d['vantaux'])} vantail(aux), vitres {vitres} m ; bords gauche {d['vantaux'][0]['vitrage'][0] * l * 100:.0f} cm, "
                  f"droit {(1 - d['vantaux'][-1]['vitrage'][1]) * l * 100:.0f} cm" + (f", entre vantaux {entre} cm" if entre else "")
                  + f" ; vitres de {allege + d['vitrage_bas'] * h:.2f} à {allege + d['vitrage_haut'] * h:.2f} m"
                  + (f" ; partie pleine {d['soubassement'] * h:.2f} m" if d["soubassement"] else "")
                  + (f" ; garde-corps à {allege + d['garde_corps'] * h:.2f} m" if d["garde_corps"] is not None else "")
                  + ("" if d["cadre_lu"] else " ; TOUR NON LU (bords supposés)")
                  + f" ; petits bois couchés {[len(v['traverses']) for v in d['vantaux']]}, debout {[len(v['montants']) for v in d['vantaux']]}")
    pose, poses = dessin_fenetres.appliquer(logement, lecture, journal=lambda s: print("   → " + s))
    print(f"\n{len(poses)} fenêtre(s) dessinée(s) d'après les photos")
    Logement.model_validate(pose)
    return pose


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(1)
    logement = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    lecture = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    pose = dire(logement, lecture)
    if len(sys.argv) == 4:
        Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[3]).write_text(json.dumps(pose, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"écrit : {sys.argv[3]}")
