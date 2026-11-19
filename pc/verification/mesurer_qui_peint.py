r"""LE JUGE DE « UNE VUE PAR FENÊTRE » (18/11/2026) : depuis la place de chaque photo du client, QUELLE PHOTO a peint ce que le
film montre par la fenêtre ?

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_qui_peint.py app-001=<dossier des vues> app-002=<…> [--seuil 0.2]

<dossier des vues> : le dossier où outils/unreal/vue_dehors_photos.py a écrit vues-dehors.json (dans le studio Unreal :
D:\Atelya-Unreal\Paquets\vues\<nom Unreal>). Le calcul lui-même est fait à chaque préparation du décor
(moteur/vue_dehors.py, qui_peint) : « avant » = la toile commune seule, « apres » = avec une toile par fenêtre.

Pourquoi : une photo prise dans une pièce doit retrouver SA vue dans le film. Quand la part « autres » est grande, le film
montre par cette fenêtre ce qu'une autre photo a vu d'ailleurs (un arbre à la place d'un immeuble : chambre d'app-002).
Limite : le juge dit QUI a peint, pas si la vue ressemble ; la ressemblance se juge sur les images du film
(outils/unreal/juger_lumiere.py, mesures « dehors »).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    args = [a for a in sys.argv[1:] if "=" in a and not a.startswith("--")]
    seuil = float(sys.argv[sys.argv.index("--seuil") + 1]) if "--seuil" in sys.argv else 0.2
    if not args:
        print(__doc__)
        return 1
    totaux = {"avant": [0, 0], "apres": [0, 0]}
    for arg in args:
        cas, dossier = arg.split("=", 1)
        fiche = Path(dossier) / "vues-dehors.json"
        if not fiche.is_file():
            print(f"PLANTÉ : {fiche} introuvable")
            return 1
        d = json.loads(fiche.read_text(encoding="utf-8"))
        if "qui_peint" not in d:
            print(f"PLANTÉ : {fiche} date d'avant le juge (refaire le décor)")
            return 1
        print(f"{cas} (une vue par fenêtre : {'oui' if d.get('une_vue_par_fenetre') else 'non'})")
        for nom, q in d["qui_peint"].items():
            ligne = []
            for quand in ("avant", "apres"):
                x = q[quand]
                autres = sum(x["autres"].values())
                totaux[quand][0] += autres >= seuil
                totaux[quand][1] += 1
                ligne.append(f"{quand} : elle-même {100 * x['elle_meme']:3.0f} %, autres {100 * autres:3.0f} %, "
                             f"prolongé {100 * x['prolonge']:3.0f} %")
            reste = ", ".join(f"{k} {100 * v:.0f} %" for k, v in q["apres"]["autres"].items())
            print(f"  {nom} | " + " | ".join(ligne) + (f" | reste : {reste}" if reste else ""))
    print(f"\nPhotos dont au moins {100 * seuil:.0f} % de la vue est peinte par une AUTRE photo : "
          f"{totaux['avant'][0]} sur {totaux['avant'][1]} avant, {totaux['apres'][0]} sur {totaux['apres'][1]} après")
    return 0


if __name__ == "__main__":
    sys.exit(main())
