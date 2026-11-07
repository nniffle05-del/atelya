"""Les statistiques d'un jeu généré : ce qu'il contient, ce qui a été rejeté, combien ça pèse.

Lit manifest.json (et les geometrie.json pour les détails) et écrit rapports/statistiques.json
plus un résumé lisible rapports/statistiques.txt.
"""

from __future__ import annotations

import json
from pathlib import Path


def _compter(valeurs) -> dict:
    c: dict = {}
    for v in valeurs:
        c[str(v)] = c.get(str(v), 0) + 1
    return dict(sorted(c.items()))


def _quantiles(valeurs: list[float]) -> dict:
    if not valeurs:
        return {}
    v = sorted(valeurs)
    n = len(v)
    return {"min": v[0], "q1": v[n // 4], "mediane": v[n // 2], "q3": v[3 * n // 4], "max": v[-1],
            "moyenne": round(sum(v) / n, 2)}


def calculer(dossier: Path) -> dict:
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    # Un -ensemble remontre des pièces déjà comptées chez son parent : à part, sinon types et surfaces seraient comptés deux fois.
    ensembles = [e for e in manifeste["exemples"] if "parent" in e]
    ex = [e for e in manifeste["exemples"] if "parent" not in e]
    acceptes = [e for e in ex if e["accepte"]]
    pieces_par_type: dict = {}
    ouvertures_par_type: dict = {}
    epaisseurs: dict = {}
    hsp: dict = {}
    styles: dict = {}
    for e in acceptes:
        geo = json.loads((dossier / "exemples" / e["id"] / "geometrie.json").read_text(encoding="utf-8"))
        for k, v in geo["resume"]["pieces_par_type"].items():
            pieces_par_type[k] = pieces_par_type.get(k, 0) + v
        for n in geo["niveaux"]:
            for o in n["ouvertures"]:
                k = o["sous_type"] or o["type"]
                ouvertures_par_type[k] = ouvertures_par_type.get(k, 0) + 1
        p = geo["parametres"]
        epaisseurs[str(p["epaisseur_murs_exterieurs"])] = epaisseurs.get(str(p["epaisseur_murs_exterieurs"]), 0) + 1
        hsp[str(p["hauteur_sous_plafond"])] = hsp.get(str(p["hauteur_sous_plafond"]), 0) + 1
        styles[e["style"]] = styles.get(e["style"], 0) + 1
    rejets: dict = {}
    for e in ex:
        if not e["accepte"]:
            for err in e["erreurs"]:
                cle = err.split(":")[-1].strip()[:50]
                rejets[cle] = rejets.get(cle, 0) + 1
    avert: dict = {}
    for e in acceptes:
        for a in e["avertissements"]:
            cle = a.split(":")[-1].strip()
            cle = " ".join(w for w in cle.split() if not any(ch.isdigit() for ch in w))[:50]
            avert[cle] = avert.get(cle, 0) + 1
    stats = {
        "schema": "statistiques/1.0", "version_generateur": manifeste["version_generateur"],
        "exemples": len(ex), "acceptes": len(acceptes), "rejetes": len(ex) - len(acceptes),
        "taux_acceptation_pct": round(100 * len(acceptes) / len(ex), 1) if ex else 0,
        "octets_total": manifeste["octets_total"], "mo_total": round(manifeste["octets_total"] / 1e6, 1),
        "ko_par_exemple": round(manifeste["octets_par_exemple"] / 1e3, 1),
        "duree_moyenne_s": round(sum(e["duree_s"] for e in acceptes) / len(acceptes), 3) if acceptes else None,
        "types": _compter(e["type"] for e in acceptes),
        "formes": _compter(e["forme"] for e in acceptes),
        "duplex": sum(e["duplex"] for e in acceptes),
        "familles": _compter(e["famille"] for e in acceptes),
        "styles": dict(sorted(styles.items())),
        "surface_m2": _quantiles([e["surface"] for e in acceptes]),
        "nombre_pieces": _quantiles([e["nombre_pieces"] for e in acceptes]),
        "nombre_murs": _quantiles([e["nombre_murs"] for e in acceptes]),
        "nombre_ouvertures": _quantiles([e["nombre_ouvertures"] for e in acceptes]),
        "pieces_par_type": dict(sorted(pieces_par_type.items())),
        "ouvertures_par_type": dict(sorted(ouvertures_par_type.items())),
        "epaisseur_murs_exterieurs_m": dict(sorted(epaisseurs.items())),
        "hauteur_sous_plafond_m": dict(sorted(hsp.items())),
        "essais_par_logement": _quantiles([e["essais"] for e in acceptes]),
        "motifs_de_rejet": dict(sorted(rejets.items(), key=lambda kv: -kv[1])),
        "avertissements": dict(sorted(avert.items(), key=lambda kv: -kv[1])),
        "rejetes_ids": [e["id"] for e in ex if not e["accepte"]],
    }
    if ensembles:
        stats["ensembles"] = {"nombre": len(ensembles), "acceptes": sum(e["accepte"] for e in ensembles),
                              "compose": _compter(e["compose"] for e in ensembles),
                              "disposition": _compter(e["disposition"] for e in ensembles),
                              "part_pct": round(100 * len(ensembles) / max(1, len(ex)), 1),
                              "rejetes_ids": [e["id"] for e in ensembles if not e["accepte"]]}
    rep = dossier / "repartition.json"
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        stats["repartition"] = {"comptes": r["comptes"], "doublons_exacts": len(r["doublons_exacts"]),
                                "trop_semblables": len(r["trop_semblables"]), "deplaces_vers_train": len(r["deplaces_vers_train"])}
    return stats


def resume(stats: dict) -> str:
    lignes = [
        f"Exemples : {stats['exemples']} (acceptés {stats['acceptes']}, rejetés {stats['rejetes']}, "
        f"taux {stats['taux_acceptation_pct']} %)",
        f"Taille : {stats['mo_total']} Mo au total, {stats['ko_par_exemple']} ko par exemple ; "
        f"durée moyenne {stats['duree_moyenne_s']} s par exemple",
        f"Types : {stats['types']}",
        f"Formes : {stats['formes']} ; duplex : {stats['duplex']}",
        f"Styles : {stats['styles']}",
        f"Surface (m²) : {stats['surface_m2']}",
        f"Pièces par logement : {stats['nombre_pieces']}",
        f"Pièces par type : {stats['pieces_par_type']}",
        f"Ouvertures par type : {stats['ouvertures_par_type']}",
        f"Épaisseur des murs extérieurs (m) : {stats['epaisseur_murs_exterieurs_m']}",
        f"Hauteur sous plafond (m) : {stats['hauteur_sous_plafond_m']}",
        f"Motifs de rejet : {stats['motifs_de_rejet']}",
        f"Avertissements : {stats['avertissements']}",
    ]
    if "ensembles" in stats:
        lignes.append(f"Exemples -ensemble (en plus) : {stats['ensembles']}")
    if "repartition" in stats:
        lignes.append(f"Répartition : {stats['repartition']}")
    return "\n".join(lignes)


def ecrire(dossier: Path) -> dict:
    stats = calculer(dossier)
    (dossier / "rapports").mkdir(exist_ok=True)
    (dossier / "rapports" / "statistiques.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    (dossier / "rapports" / "statistiques.txt").write_text(resume(stats) + "\n", encoding="utf-8")
    return stats
