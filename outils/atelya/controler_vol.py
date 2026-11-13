"""Contrôler un vol d'Atelya AVANT de le tourner (moteur/cinema/controle.py) : note /100 et défauts, seconde par seconde.

    python outils/atelya/controler_vol.py <logement.json> [--vol balade.json] [--budget 55] [--sortie controle.json]

Sans --vol, Atelya calcule le vol de ce logement (moteur/promeneur.vol) puis le contrôle ; avec --vol, il contrôle un vol déjà
tourné (le balade.json du dossier du film).
"""
import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from moteur import promeneur  # noqa: E402
from moteur.cinema import controle  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("logement")
    p.add_argument("--vol", help="un vol déjà calculé (balade.json) ; sinon Atelya le calcule")
    p.add_argument("--budget", type=float, help="durée voulue du film en secondes (défaut : selon le nombre de pièces)")
    p.add_argument("--sortie", help="où écrire le contrôle complet (JSON)")
    a = p.parse_args()
    logement = json.loads(Path(a.logement).read_text(encoding="utf-8"))
    vol = json.loads(Path(a.vol).read_text(encoding="utf-8")) if a.vol else promeneur.vol(logement)
    c = controle.controler(logement, vol, a.budget)
    print(controle.rapport(c))
    if a.sortie:
        Path(a.sortie).write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
