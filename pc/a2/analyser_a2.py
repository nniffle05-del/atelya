"""Étape A2-6 : le tableau final du banc des PDF (à lancer depuis le dépôt atelya-code, après banc-a2.ps1).

    ..\\atelya\\.venv\\Scripts\\python.exe pc\\a2\\analyser_a2.py [--suffixe -essai3]

Compare, sur les mêmes plans du jeu de test (1 066 niveaux) :
- chaque sorte de PDF (vectorielle, piégée, scannée, réduite, tournée, dossier) ;
- les PDF vectoriels et les mêmes plans en image (banc-v041-apres-e5, le banc de référence de l'essai 5) ;
- les mêmes images des pages vectorielles lues avec les textes du PDF ou avec l'OCR ;
- le non-recul sur les images (banc-a2-images[-cache] contre banc-v041-apres-e5).
Les pages « tournées » ne sont notées que pour le tri et l'échelle : leur maquette sort tournée d'un quart de tour,
comme la page s'affiche, et ne se compare donc pas à la vérité mur par mur.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from moteur.banc_coloriage import bilan, bilan_echelle  # noqa: E402

A = Path("..") / "atelya"


def details(nom: str) -> list[dict] | None:
    f = A / nom / "details.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def ligne(rs: list[dict], geometrie: bool = True) -> dict:
    e = bilan_echelle(rs)["tous"]
    sortie = {"niveaux": len(rs), "echelle_lue_pct": e["lue_pct"], "plus_de_3_pct": e["plus_de_3_pct"],
              "ecart_median_pct": e["ecart_pct_median"], "a_0_5_pct_pres": e["a_0_5_pct_pres_pct"],
              "sources": {k[4:]: e[k] for k in ("par_barre", "par_surfaces", "par_echelle_ecrite", "par_cote_d_ensemble") if e.get(k)}}
    sortie["sources"]["cotes"] = sum(r.get("echelle_lue", {}).get("source") == "cotes" for r in rs)
    if geometrie:
        b = bilan(rs)
        sortie |= {"murs_justes": b["murs"]["justes_pct"], "ouv_justes": b["ouvertures"]["justes_pct"],
                   "pieces_bon_type": b["pieces"]["bon_type_pct"], "plans_parfaits": b["plans_parfaits_pct"],
                   "rates": b["niveaux_rates"]}
    return sortie


def cle(r: dict) -> tuple[str, int]:
    return r["plan"].split("-")[0], r["niveau"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffixe", default="")
    s = ap.parse_args().suffixe
    rapport: dict = {}
    pdf, ref = details(f"banc-a2-pdf{s}"), details("banc-v041-apres-e5")
    prep = A / f"jeu-pdf-a2{s}" / "preparation.json"
    if prep.exists():
        p = json.loads(prep.read_text(encoding="utf-8"))["bilan"]
        rapport["preparation"] = {k: (len(v) if isinstance(v, list) else v) for k, v in p.items()}
        rapport["preparation"]["erreurs_detail"] = p["erreurs"][:10]
    if pdf:
        par_sorte = {}
        for r in pdf:
            par_sorte.setdefault(r["plan"].split("-", 1)[1], []).append(r)
        rapport["par_sorte"] = {so: ligne(rs, geometrie=so != "tournee") for so, rs in sorted(par_sorte.items())}
        rapport["pdf_hors_tournees"] = ligne([r for r in pdf if not r["plan"].endswith("-tournee")])
        rapport["pdf_tous_echelle"] = ligne(pdf, geometrie=False)
        if ref:
            vecto = {cle(r): r for r in par_sorte.get("vectorielle", [])}
            memes = [r for r in ref if cle(r) in vecto]
            rapport["vectoriel_contre_images_memes_niveaux"] = {
                "images (banc-v041-apres-e5)": ligne(memes), "pdf vectoriels": ligne(list(vecto.values()))}
    ocr = details(f"banc-a2-ocr{s}")
    if ocr and pdf:
        vecto = {cle(r): r for r in pdf if r["plan"].endswith("-vectorielle")}
        rapport["memes_images_textes_pdf_contre_ocr"] = {
            "textes du PDF": ligne([vecto[cle(r)] for r in ocr if cle(r) in vecto]), "OCR": ligne(ocr)}
    for nom in (f"banc-a2-images-cache{s}", f"banc-a2-images{s}"):
        nouv = details(nom)
        if nouv and ref:
            anc = {cle(r): r for r in ref}
            communs = [r for r in nouv if cle(r) in anc]
            changes = [f"{r['plan']}-N{r['niveau']}" for r in communs
                       if r.get("echelle_lue", {}).get("source") != anc[cle(r)].get("echelle_lue", {}).get("source")
                       or r.get("echelle_lue", {}).get("ecart_largeur_pct") != anc[cle(r)].get("echelle_lue", {}).get("ecart_largeur_pct")]
            rapport[f"non_recul_{nom}"] = {"avant (banc-v041-apres-e5)": ligne([anc[cle(r)] for r in communs]),
                                           "apres (code A2)": ligne(communs), "echelles_changees": len(changes),
                                           "exemples_changes": changes[:15]}
    sortie = A / f"resultats-a2{s}.json"
    sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
