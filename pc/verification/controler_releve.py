r"""Le relevé des meubles fait à la main passe-t-il le contrôle « zéro collision » ? (17/11/2026)

    ..\atelya\.venv\Scripts\python.exe pc\verification\controler_releve.py [app-001 app-002]

Pourquoi : le relevé (verites/<logement>/meubles.json + meubles-complement.json) est le JUGE de la pose des meubles. Le
17/11/2026, NT a trouvé « louche » le complément que Claude venait d'écrire (« des meubles mis dans le vide ») : il avait
raison — 13 défauts (meubles l'un dans l'autre, dans un mur, un placard hors de toute pièce), que les boîtes dessinées sur les
photos n'avaient pas montrés. Règle depuis : un relevé se contrôle comme une maquette (moteur/collisions.py), AVANT de servir de
juge et avant d'être montré. Sont tolérés, comme dans le relevé d'origine : une chaise ou un tabouret rentré sous sa table ou
son plan, et les frôlements de moins de 3 cm.
Code de sortie 1 si le complément ajoute un défaut que le relevé d'origine n'avait pas.
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import essai_lecture_photos as essai  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402
from moteur import collisions  # noqa: E402
from moteur.sol_a_plat import piece_de  # noqa: E402

SOUS = ("chaise", "chaise_de_bureau", "tabouret_haut")  # ce qui se rentre sous une table, un bureau, un plan
FROLEMENT_CM = 3.0


def defauts(cas: str, complet: bool) -> list[str]:
    lg = essai.lire(CAS[cas]["logement"])
    lg = lg.get("logement", lg)
    releve = essai.charger_releve(cas, complet)
    sorte = {m["id"]: m["categorie"] for m in releve}
    lg["meubles"] = [dict(m, statut="estime") for m in releve]
    sortie = [f"{m['id']} hors de toute pièce" for m in releve if piece_de(m["position"], lg["pieces"]) is None]
    for c in collisions.mesurer(lg):
        if float(c.get("profondeur_cm") or 0) < FROLEMENT_CM or sorte.get(c["a"]) in SOUS or sorte.get(c["b"]) in SOUS:
            continue
        sortie.append(f"{c['a']} dans {c['b']} ({c['profondeur_cm']:.0f} cm)")
    return sortie


def main() -> int:
    code = 0
    for cas in sys.argv[1:] or ["app-001", "app-002"]:
        origine, complete = defauts(cas, False), defauts(cas, True)
        nouveaux = [d for d in complete if d not in origine]
        print(f"{cas} : relevé d'origine {len(origine)} défaut(s) ; complété {len(complete)} ; ajoutés par le complément : {len(nouveaux)}")
        for d in complete:
            print(f"   {'NOUVEAU ' if d in nouveaux else ''}{d}")
        code = code or (1 if nouveaux else 0)
    return code


if __name__ == "__main__":
    sys.exit(main())
