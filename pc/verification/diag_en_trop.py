r"""« PLACE ET TAILLE JUSTES » : le détail, meuble par meuble, de ce qu'Atelya a posé contre le relevé fait à la main (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\diag_en_trop.py <dossier de l'essai> [--cas app-001 app-002] [--version c]

Lit <dossier>/<logement>/<version>/logement-meuble.json (écrit par essai_lecture_photos.py) et, avec la même règle de notation,
dit pour chaque meuble posé au sol : apparié (à quel meuble du relevé, à quelle distance, même sorte ou même famille) ou EN TROP
(et alors : le meuble du relevé le plus proche de la même famille, de n'importe quelle sorte, à quelle distance). Dit aussi les
meubles du relevé restés seuls, et compare les TAILLES des meubles appariés. Écrit <dossier>/<logement>/<version>/diag.png :
le plan vu de dessus, relevé en vert (contours), posés en bleu (appariés) ou rouge (en trop), accrochés en violet.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import essai_lecture_photos as essai  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402

PX = 80
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def detail(logement: dict, verite: list[dict], fiche: dict) -> dict:
    """La même notation que essai.noter_meubles, mais en gardant les objets : paires, en trop, restés seuls."""
    from moteur.camera_photo import camera_depuis_dict
    from moteur.meubles import EQUIPEMENTS
    from moteur.reperer_meubles import groupe as _groupe, vu_sur_une_photo
    # un réfrigérateur posé vaut la « colonne » que le relevé du 10/11/2026 appelait réfrigérateur (la sorte n'existait pas encore)
    groupe = lambda c: _groupe("colonne_cuisine" if c == "refrigerateur" else c)

    cams = [camera_depuis_dict(c["camera"]) for c in fiche["cameras"].values()]
    poses = [m for m in logement.get("meubles", []) if m["categorie"] not in EQUIPEMENTS or m["categorie"] == "refrigerateur"]
    au_sol = lambda m: bool(groupe(m["categorie"])) and float(m.get("altitude") or 0) < 0.3 and m["categorie"] not in essai.ACCROCHES
    vrais_sol = [v for v in verite if au_sol(v) and vu_sur_une_photo(v, cams, logement)]
    poses_sol = [m for m in poses if au_sol(m)]
    exacts, reste = essai._paires(vrais_sol, poses_sol, lambda v, m: v["categorie"] == m["categorie"])
    pris = {id(v) for v, _ in exacts}
    proches, en_trop = essai._paires([v for v in vrais_sol if id(v) not in pris], reste, lambda v, m: groupe(v["categorie"]) == groupe(m["categorie"]))
    hors_liste = [v for v in verite if au_sol(v) and not any(v is x for x in vrais_sol)]
    hors, en_trop = essai._paires(hors_liste, en_trop, lambda v, m: groupe(v["categorie"]) == groupe(m["categorie"]))
    pris |= {id(v) for v, _ in proches}
    seuls = [v for v in vrais_sol if id(v) not in pris]
    vrais_acc = [v for v in verite if v["categorie"] in essai.ACCROCHES and vu_sur_une_photo(v, cams, logement)]
    poses_acc = [m for m in poses if m["categorie"] in essai.ACCROCHES]
    acc, acc_en_trop = essai._paires(vrais_acc, poses_acc, lambda v, m: v["categorie"] == m["categorie"])
    acc_hors, acc_en_trop = essai._paires([v for v in verite if v["categorie"] in essai.ACCROCHES and not any(v is x for x in vrais_acc)],
                                          acc_en_trop, lambda v, m: v["categorie"] == m["categorie"])
    acc_seuls = [v for v in vrais_acc if not any(v is x for x, _ in acc)]
    return {"exacts": exacts, "proches": proches, "hors": hors, "en_trop": en_trop, "seuls": seuls, "vrais_sol": vrais_sol,
            "hors_liste": hors_liste, "acc": acc, "acc_en_trop": acc_en_trop, "acc_seuls": acc_seuls, "acc_hors": acc_hors,
            "verite_sol": [v for v in verite if au_sol(v)]}


def _coins(m: dict) -> list[tuple[float, float]]:
    a = math.radians(m.get("face", 0.0) or 0.0)
    av, cote = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    l, p = m["dimensions"][0] / 2, m["dimensions"][1] / 2
    x, y = m["position"]
    return [(x + s * cote[0] * l + t * av[0] * p, y + s * cote[1] * l + t * av[1] * p) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def dessiner(logement: dict, d: dict, sortie: Path) -> None:
    pts = [p for piece in logement["pieces"] for p in piece["contour"]]
    x0, y0 = min(p[0] for p in pts) - 0.5, min(p[1] for p in pts) - 0.5
    x1, y1 = max(p[0] for p in pts) + 0.5, max(p[1] for p in pts) + 0.5
    P = lambda p: ((p[0] - x0) * PX, (y1 - p[1]) * PX)
    im = Image.new("RGB", (int((x1 - x0) * PX), int((y1 - y0) * PX)), "white")
    g = ImageDraw.Draw(im)
    try:
        police = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        police = ImageFont.load_default()
    for piece in logement["pieces"]:
        g.polygon([P(p) for p in piece["contour"]], fill=(246, 244, 238), outline=(90, 90, 90))
    for m in logement.get("murs", []):
        g.line([P(m["debut"]), P(m["fin"])], fill=(90, 90, 90), width=max(2, int(m.get("epaisseur", 0.2) * PX)))
    apparies = {id(m) for _, m in d["exacts"] + d["proches"] + d["hors"] + d["acc"] + d["acc_hors"]}
    en_trop = {id(m) for m in d["en_trop"] + d["acc_en_trop"]}
    for m in logement.get("meubles", []):
        couleur = (40, 90, 220) if id(m) in apparies else (220, 40, 40) if id(m) in en_trop else (170, 170, 170)
        if m["categorie"] in essai.ACCROCHES and id(m) in apparies:
            couleur = (150, 60, 200)
        g.polygon([P(c) for c in _coins(m)], outline=couleur, width=2)
        if couleur != (170, 170, 170):
            g.text(P(m["position"]), f"{m['id'].replace('reperage_', 'r')} {m['categorie'][:10]}", fill=couleur, font=police)
    for v in d["verite_sol"] + [v for v, _ in d["acc"]] + d["acc_seuls"]:
        seul = any(v is s for s in d["seuls"] + d["acc_seuls"])
        g.polygon([P(c) for c in _coins(v)], outline=(0, 150, 0) if not seul else (230, 140, 0), width=1)
        if seul:
            g.text(P(v["position"]), v["categorie"][:12], fill=(230, 140, 0), font=police)
    im.save(sortie)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier", type=Path)
    ap.add_argument("--cas", nargs="*", default=["app-001", "app-002"])
    ap.add_argument("--version", default="c")
    a = ap.parse_args()
    from moteur.reperer_meubles import groupe

    for cas in a.cas:
        f = a.dossier / cas / a.version / "logement-meuble.json"
        logement = essai.lire(f)
        verite = essai.charger_releve(cas)
        d = detail(logement, verite, essai.lire(CAS[cas]["fiche"]))
        print(f"\n===== {cas} version {a.version} : à trouver {len(d['vrais_sol'])}, bonne sorte {len(d['exacts'])}, même famille {len(d['proches'])}, "
              f"en trop {len(d['en_trop'])}, seuls {len(d['seuls'])} | accrochés {len(d['acc'])}, en trop {len(d['acc_en_trop'])}, seuls {len(d['acc_seuls'])}")
        print("-- appariés (relevé ← posé) : distance, tailles relevé / posé")
        for nom, paires in (("=", d["exacts"]), ("~", d["proches"]), ("h", d["hors"])):
            for v, m in paires:
                print(f"  {nom} {v['id']:22s} {v['categorie']:18s} ← {m['id']:14s} {m['categorie']:18s} {math.dist(v['position'], m['position']):.2f} m  "
                      f"{v['dimensions']} / {m['dimensions']}  face {v.get('face')} / {m.get('face')}")
        print("-- EN TROP (posé sans vrai meuble de sa famille à 80 cm)")
        for m in d["en_trop"]:
            g = groupe(m["categorie"])
            meme = sorted(((math.dist(v["position"], m["position"]), v) for v in d["verite_sol"] if groupe(v["categorie"]) == g), key=lambda c: c[0])[:1]
            tout = sorted(((math.dist(v["position"], m["position"]), v) for v in d["verite_sol"]), key=lambda c: c[0])[:1]
            pose_proche = sorted(((math.dist(x["position"], m["position"]), x) for x in logement["meubles"] if x is not m and groupe(x["categorie"]) == g),
                                 key=lambda c: c[0])[:1]
            dit = lambda c: f"{c[0][1]['id']}({c[0][1]['categorie']}) {c[0][0]:.2f} m" if c else "-"
            print(f"  {m['id']:14s} {m['categorie']:18s} {m['piece']:12s} {m['position']} {m['dimensions']} conf {m.get('confiance')} {m.get('source', '')[-12:]}"
                  f"\n      même famille au relevé : {dit(meme)} | n'importe quoi : {dit(tout)} | posé même famille : {dit(pose_proche)}")
        print("-- relevé resté SEUL (vu sur une photo, pas retrouvé)")
        for v in d["seuls"]:
            g = groupe(v["categorie"])
            pres = sorted(((math.dist(x["position"], v["position"]), x) for x in logement["meubles"]), key=lambda c: c[0])[:2]
            print(f"  {v['id']:22s} {v['categorie']:18s} {v['piece']:12s} {v['position']} | posés proches : "
                  + ", ".join(f"{x['id']}({x['categorie']}) {dd:.2f} m" for dd, x in pres))
        print("-- accrochés en trop / seuls")
        for m in d["acc_en_trop"]:
            print(f"  en trop {m['id']:18s} {m['categorie']:18s} {m['piece']:12s} {m['position']} alt {m.get('altitude')}")
        for v in d["acc_seuls"]:
            print(f"  seul    {v['id']:18s} {v['categorie']:18s} {v['piece']:12s} {v['position']}")
        dessiner(logement, d, f.parent / "diag.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
