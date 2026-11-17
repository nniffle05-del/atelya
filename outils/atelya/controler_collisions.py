r"""LE CONTRÔLE « ZÉRO COLLISION » d'un logement meublé (NT, 16/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\atelya\controler_collisions.py <logement.json> [<logement.json> …] [--reparer]

Pourquoi : dans une maquette, aucun meuble ne doit entrer dans un mur, dans un autre objet ni dans un rideau (moteur/collisions.py).
Cette commande le MESURE sur un ou plusieurs logements et dit, en clair, ce qui se touche et de combien. La chaîne
(outils/atelya/de_l_ecran_au_film.py) répare déjà toute seule à l'étape « meubles » ; ici on peut contrôler n'importe quel
logement, par exemple un relevé fait à la main.

--reparer : écrit à côté <nom>-sans-collision.json (chaque objet déplacé le moins possible ; ce qu'une personne a placé ne
bouge pas) et dit ce qui a été fait.
Code de retour : 0 si aucun logement n'a de collision, 1 sinon (2 : fichier introuvable).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur import collisions  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EN_CLAIR = {"mur": "est entré dans le mur", "objet": "traverse", "rideau": "est dans le", "dehors": "est posé hors de toute pièce"}


def dire(collision: dict, logement: dict) -> str:
    noms = {m["id"]: f"{m['categorie']} {m['id']}" for m in logement.get("meubles", [])}
    a = noms.get(collision["a"], str(collision["a"]))
    if collision["type"] == "dehors":
        return f"  {a} {EN_CLAIR['dehors']}"
    b = noms.get(collision["b"], str(collision["b"]))
    return f"  {a} {EN_CLAIR[collision['type']]} {b} ({collision['profondeur_cm']} cm)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Contrôle « zéro collision » d'un logement meublé")
    ap.add_argument("logements", nargs="+", type=Path)
    ap.add_argument("--reparer", action="store_true", help="écrire <nom>-sans-collision.json à côté de chaque logement")
    a = ap.parse_args()
    total = 0
    for chemin in a.logements:
        if not chemin.is_file():
            print(f"PLANTÉ : introuvable : {chemin}", flush=True)
            return 2
        logement = json.loads(chemin.read_text(encoding="utf-8"))
        logement = logement.get("logement", logement)
        trouvees = collisions.mesurer(logement)
        r = collisions.resume(trouvees)
        print(f"{chemin} : {len(logement.get('meubles', []))} objets, {r['total']} collision(s)"
              + (f" (murs {r['mur']}, objets {r['objet']}, rideaux {r['rideau']}, hors des pièces {r['dehors']} ; au pire {r['au_pire_cm']} cm)" if trouvees else ""))
        for c in trouvees:
            print(dire(c, logement))
        if a.reparer and trouvees:
            repare, actions = collisions.reparer(logement, journal=print)
            sortie = chemin.with_name(chemin.stem + "-sans-collision.json")
            sortie.write_text(json.dumps(repare, ensure_ascii=False, indent=1), encoding="utf-8")
            trouvees = collisions.mesurer(repare)
            print(f"  réparé : {collisions.bilan(actions)} ; il reste {len(trouvees)} collision(s) : {sortie}")
        total += len(trouvees)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
