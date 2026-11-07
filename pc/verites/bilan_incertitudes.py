r"""Bilan des incertitudes des vérités : ce que NT doit regarder à l'écran de vérification, et rien d'autre.

Pourquoi : valider 103 plans en entier prendrait des jours. Les traceurs et les relecteurs ont noté ce dont ils doutent ; ce bilan les range
par sujet et classe les plans du plus douteux au moins douteux, pour que NT passe son temps là où son œil change quelque chose.

    python pc\verites\bilan_incertitudes.py

Lit verites\journal-verites.json, écrit verites\bilan-incertitudes.md. Relancer après chaque passe.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

JOURNAL = Path("verites/journal-verites.json")
SORTIE = Path("verites/bilan-incertitudes.md")

# Du plus précis au plus général : une phrase va au premier sujet qui la reconnaît.
SUJETS = (
    ("Échelle", ("échelle", "px/m", "px_par_m", "barre", "surface")),
    ("Porte d'entrée ou porte supposée", ("porte d'entrée", "sans porte dessinée", "porte inventée", "pas d'arc", "seul accès", "supposée")),
    ("Passages ouverts (murs virtuels)", ("virtuel", "passage", "ouvert")),
    ("Fenêtre ou porte-fenêtre", ("porte-fenêtre", "porte_fenetre", "baie", "fenêtre", "vitr")),
    ("Nom ou type de pièce deviné", ("sans nom", "non nommée", "typé", "déduit", "type ", "étiquette", "nommé")),
    ("Extérieur ou dépendance (pas une pièce)", ("extérieur", "balcon", "terrasse", "loggia", "garage", "palier", "cour", "jardin")),
    ("Niveaux multiples", ("niveau", "étage")),
)
AUTRE = "Tracé (mur, épaisseur, équipement)"


def sujet(phrase: str) -> str:
    p = phrase.lower()
    for nom, mots in SUJETS:
        if any(m in p for m in mots):
            return nom
    return AUTRE


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    j = json.loads(JOURNAL.read_text(encoding="utf-8"))
    traces, revues = j["traces"], j["revues"]
    plans = sorted(traces, key=lambda p: (traces[p].get("confiance", 0), p))
    compte: Counter[str] = Counter()
    lignes = [
        "# Bilan des incertitudes des vérités",
        "",
        f"{len(revues)} plans relus sur 103, {len(traces)} tracés. Généré par `pc/verites/bilan_incertitudes.py` : à relancer, ne pas corriger à la main.",
        "",
        "Plans classés du moins sûr au plus sûr (confiance = note que le traceur se donne, pas une mesure).",
        "",
        "## Plans",
        "",
    ]
    corps = []
    for p in plans:
        t = traces[p]
        rv = revues.get(p)
        etat = "pas encore relu" if not rv else f"relu, {rv['verdict']}" + ("" if rv["echelle_plausible"] else ", **échelle douteuse**")
        corps.append(f"### {p} : confiance {t.get('confiance')}, {etat}")
        corps.append("")
        par_sujet: dict[str, list[str]] = {}
        for phrase in t.get("incertain", []):
            s = sujet(phrase)
            compte[s] += 1
            par_sujet.setdefault(s, []).append(phrase)
        for s in sorted(par_sujet):
            corps.append(f"- **{s}** : " + " / ".join(par_sujet[s]))
        if rv:
            for e in rv["erreurs"]:
                if e["gravite"] != "legere":
                    corps.append(f"- *Vu par le relecteur ({e['gravite']})* : {e['quoi']}")
        corps.append("")
    lignes += [f"- **{s}** : {n} doutes notés" for s, n in compte.most_common()]
    lignes += [""] + corps
    SORTIE.write_text("\n".join(lignes), encoding="utf-8")
    print(f"{SORTIE} : {len(plans)} plans")
    for s, n in compte.most_common():
        print(f"  {n:4d} {s}")
    print("Les moins sûrs :", ", ".join(f"{p} ({traces[p].get('confiance')})" for p in plans[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
