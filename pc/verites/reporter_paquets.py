r"""Reporter dans le dépôt le résultat d'un passage du workflow des vérités (verites-fable-paquets.js).

Pourquoi : les vérités sont fabriquées hors dépôt (..\atelya\verites-lot2\) ; on n'en garde dans Git que le texte (saisie, verite.json,
logement.json), sans images, et on note plan par plan les incertitudes du traceur et le verdict du relecteur pour le bilan à montrer à NT.

    python pc\verites\reporter_paquets.py <sortie du workflow>

Écrit verites\<plan>\ et verites\journal-verites.json, puis affiche un résumé par plan. Le fichier de sortie contient le résultat du
workflow, en JSON ; seuls les paquets non interrompus sont copiés.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

SOURCE = Path("../atelya/verites-lot2")
SORTIE = Path("verites")
FICHIERS = ("verite-saisie.json", "verite.json", "logement.json")


def lire_resultat(chemin: Path) -> dict:
    texte = chemin.read_text(encoding="utf-8")
    debut = texte.find("{")
    d = json.JSONDecoder().raw_decode(texte[debut:])[0]
    return d.get("result", d)  # le fichier de sortie enveloppe le résultat dans {"summary", "logs", "result"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    r = lire_resultat(Path(sys.argv[1]))
    jf = SORTIE / "journal-verites.json"
    journal = json.loads(jf.read_text(encoding="utf-8"))
    for paquet in r["resultats"]:
        perdu = paquet.get("perdu")
        for t in (paquet.get("trace") or {}).get("plans", []):
            journal["traces"][t["plan"]] = t
        revues = {p["plan"]: p for p in (paquet.get("revue") or {}).get("plans", [])}
        for plan in paquet["groupe"]:
            if plan in revues and not perdu:
                journal["revues"][plan] = dict(revues[plan], tours=paquet.get("tours", 0))
                for f in FICHIERS:
                    if not (SOURCE / plan / f).exists():
                        print(f"PLANTÉ : {plan} n'a pas de {f}")
                        return 1
                    (SORTIE / plan).mkdir(exist_ok=True)
                    shutil.copyfile(SOURCE / plan / f, SORTIE / plan / f)
            rv = journal["revues"].get(plan)
            t = journal["traces"].get(plan, {})
            if rv:
                g = [e["gravite"] for e in rv["erreurs"]]
                print(f"{plan} {rv['verdict']:8} tours={rv['tours']} graves={g.count('grave')} moyennes={g.count('moyenne')} legeres={g.count('legere')} "
                      f"échelle_ok={rv['echelle_plausible']} confiance={t.get('confiance')} incertitudes={len(t.get('incertain', []))}")
            else:
                print(f"{plan} NON RELU ({perdu})")
    jf.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Journal : {len(journal['traces'])} tracés, {len(journal['revues'])} relus. Paquets : {r['faits']}/{r['total']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
