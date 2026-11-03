"""Étape A1 : régler les seuils des doutes sur les bancs déjà notés (sans rien recalculer d'Atelya).

    python calibrer_doutes.py banc-a1-apres-e5 banc-a1-psc-e5 banc-a1-reel-cotes-e5 banc-a1-reel-sc-e5

Lit details.json de chaque banc (lancé avec --doutes) et rejoue la décision « lu / à vérifier » pour
une grille de réglages : seuil de doute d'un élément, taille minimale d'une zone douteuse orpheline,
contrôles de bon sens gardés. Les plans sont coupés en deux moitiés (selon leur numéro) : on choisit
sur la moitié A, on contrôle sur la moitié B (pour ne pas se flatter). Écrit calibrage.json.
Seulement la bibliothèque standard : tourne partout.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

CODES_BON_SENS = ["surface", "fenetre_interieure", "largeur_porte", "largeur_fenetre", "chevauchement",
                  "sans_acces", "epaisseur", "pas_un_plan"]


def echelle_fausse(r):
    e = r.get("echelle_lue")
    if not e or r.get("echelle_a_verifier"):
        return False
    return any(e[k] is not None and abs(e[k]) > 3 for k in ("ecart_largeur_pct", "ecart_hauteur_pct"))


def erreur_grave(r):
    if "erreur" in r or echelle_fausse(r) or r.get("murs_en_trop") or r.get("ouvertures_en_trop"):
        return True
    return any(z["grave"] for z in r.get("erreurs_zones", []))


def decision(r, t_elem, a_orph, codes, faible_type=False):
    d = r["doutes"]
    if d["decision"] == "refuse":
        return True
    for x in d["doutes"]:
        if x["code"] == "echelle":
            return True
        if x["code"] in codes and x["gravite"] == "fort":
            return True
    m = d.get("mesures", {})
    if t_elem is not None and any(v >= t_elem for v in m.get("elements", {}).values()):
        return True
    if a_orph is not None and any(a >= a_orph for a, _ in m.get("orphelines", [])):
        return True
    return False


def noter(plans, regle):
    avec = [r for r in plans if r["_err"]]
    sans = [r for r in plans if not r["_err"]]
    sil = sum(not decision(r, *regle) for r in avec)
    fa = sum(decision(r, *regle) for r in sans)
    return {"plans": len(plans), "avec_erreur": len(avec), "silencieuses": sil,
            "attrapees_pct": round(100 * (1 - sil / len(avec)), 1) if avec else None,
            "justes": len(sans), "fausses_alertes": fa,
            "fausses_alertes_pct": round(100 * fa / len(sans), 1) if sans else None,
            "a_verifier_pct": round(100 * (sum(decision(r, *regle) for r in plans)) / len(plans), 1) if plans else None}


def main():
    bancs = {}
    for b in sys.argv[1:]:
        rs = [r for r in json.loads((Path(b) / "details.json").read_text(encoding="utf-8")) if "doutes" in r]
        for r in rs:
            r["_err"] = erreur_grave(r)
            r["_moitie"] = "A" if int("".join(c for c in r["plan"] if c.isdigit()) or 0) % 2 == 0 else "B"
        bancs[Path(b).name] = rs
    sortie = {"avant_A1": {}, "par_code": {}, "grille": []}
    # Avant A1 : seule l'échelle illisible envoyait en vérification.
    avant = (None, None, [])
    for nom, rs in bancs.items():
        sortie["avant_A1"][nom] = noter(rs, avant)
    # Utilité de chaque contrôle seul : plans signalés, dont avec vraie erreur grave.
    for c in CODES_BON_SENS + ["carte", "zone_douteuse", "type_hesitant"]:
        n = e = 0
        for rs in bancs.values():
            for r in rs:
                if any(x["code"] == c and x["gravite"] == "fort" for x in r["doutes"]["doutes"]):
                    n += 1
                    e += r["_err"]
        sortie["par_code"][c] = {"plans": n, "avec_erreur_pct": round(100 * e / n, 1) if n else None}
    t_elems = [None, 0.25, 0.35, 0.45, 0.55, 0.7]
    a_orphs = [None, 0.06, 0.1, 0.2, 0.35, 0.6, 1.0]
    jeux_codes = {"tous": CODES_BON_SENS,
                  "sans_largeur_porte": [c for c in CODES_BON_SENS if c != "largeur_porte"],
                  "sans_surface": [c for c in CODES_BON_SENS if c != "surface"],
                  "geometrie": ["chevauchement", "sans_acces", "epaisseur", "pas_un_plan", "fenetre_interieure"],
                  "aucun": ["pas_un_plan"]}
    for t, a, (nc, codes) in itertools.product(t_elems, a_orphs, jeux_codes.items()):
        regle = (t, a, codes)
        ligne = {"seuil_element": t, "zone_min_m2": a, "controles": nc, "A": {}, "B": {}}
        for nom, rs in bancs.items():
            for moitie in ("A", "B"):
                ligne[moitie][nom] = noter([r for r in rs if r["_moitie"] == moitie], regle)
        tot = {}
        for moitie in ("A", "B"):
            s = sum(v["silencieuses"] for v in ligne[moitie].values())
            e = sum(v["avec_erreur"] for v in ligne[moitie].values())
            f = sum(v["fausses_alertes"] for v in ligne[moitie].values())
            j = sum(v["justes"] for v in ligne[moitie].values())
            tot[moitie] = {"silencieuses": s, "attrapees_pct": round(100 * (1 - s / e), 1) if e else None,
                           "fausses_alertes_pct": round(100 * f / j, 1) if j else None}
        ligne["total"] = tot
        sortie["grille"].append(ligne)
    Path("calibrage.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    # Résumé lisible : les meilleurs compromis sur la moitié A, contrôlés sur B.
    print("AVANT A1 :", json.dumps({k: (v["silencieuses"], v["avec_erreur"], v["fausses_alertes_pct"]) for k, v in sortie["avant_A1"].items()}))
    print("PAR CODE :", json.dumps(sortie["par_code"], ensure_ascii=False))
    for fa_max in (10, 15, 20, 25, 30, 40):
        ok = [l for l in sortie["grille"] if l["total"]["A"]["fausses_alertes_pct"] is not None and l["total"]["A"]["fausses_alertes_pct"] <= fa_max]
        if not ok:
            continue
        best = max(ok, key=lambda l: l["total"]["A"]["attrapees_pct"] or 0)
        print(f"FA<={fa_max}% : elem={best['seuil_element']} zone={best['zone_min_m2']} controles={best['controles']} | "
              f"A {best['total']['A']} | B {best['total']['B']} | par banc B : "
              + json.dumps({k: (v['silencieuses'], v['avec_erreur'], v['fausses_alertes_pct']) for k, v in best['B'].items()}))


if __name__ == "__main__":
    main()
