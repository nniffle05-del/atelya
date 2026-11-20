r"""LE JUGE DE LA LARGEUR DES FENÊTRES (20/11/2026, étape F1) : ce qu'Atelya élargit, contre le relevé fait à l'œil.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_largeur_baies.py [app-001 app-002 app-004]

Le relevé (verites/<logement>/baies.json) dit, pour chaque baie du plan vue sur les photos, si les photos la montrent
NETTEMENT plus large que le plan (« plus_large ») ou non (« comme_le_plan »). Le juge compte : les baies élargies à raison,
élargies à tort, manquées, et laissées à raison. Les logements ne sont pas modifiés.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def juger(cas_demandes: list[str]) -> dict:
    from mesurer_largeur_baies import mesurer

    total = {"elargies_a_raison": 0, "elargies_a_tort": 0, "manquees": 0, "laissees_a_raison": 0, "hors_releve": 0}
    for cas in cas_demandes:
        releve = json.loads((RACINE / "verites" / cas / "baies.json").read_text(encoding="utf-8"))["baies"]
        with redirect_stdout(io.StringIO()):
            changes, doutes = mesurer(cas)
        elargies = {c["id"]: c for c in changes}
        lignes = []
        for ident, r in releve.items():
            large = r["verdict"] == "plus_large"
            cle = ("elargies_a_raison" if large else "elargies_a_tort") if ident in elargies else ("manquees" if large else "laissees_a_raison")
            total[cle] += 1
            if ident in elargies or large:
                c = elargies.get(ident)
                lignes.append(f"    {ident} : relevé « {r['verdict']} » ; Atelya : "
                              + (f"{c['avant']['largeur']:.2f} → {c['apres']['largeur']:.2f} m" if c else "pas élargie") + f" ({cle.replace('_', ' ')})")
        for ident in set(elargies) - set(releve):
            total["hors_releve"] += 1
            lignes.append(f"    {ident} : élargie, mais absente du relevé")
        print(f"  {cas} : {len(releve)} baie(s) au relevé, {len(elargies)} élargie(s), {len(doutes)} doute(s)")
        print("\n".join(lignes) if lignes else "    rien à élargir, rien d'élargi")
    print(f"JUGE DE LA LARGEUR DES FENÊTRES : élargies à raison {total['elargies_a_raison']}, à tort {total['elargies_a_tort']}, "
          f"manquées {total['manquees']}, laissées à raison {total['laissees_a_raison']}, hors relevé {total['hors_releve']}")
    return total


if __name__ == "__main__":
    juger(sys.argv[1:] or ["app-001", "app-002", "app-004"])
