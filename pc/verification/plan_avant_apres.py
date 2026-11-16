r"""Le plan vu de dessus AVANT | APRÈS, avec le relevé fait à la main, pour montrer à NT un changement de la pose (16/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\verification\plan_avant_apres.py <dossier avant> <dossier après> <logement> <sortie.jpg> [--version c]

Les deux dossiers sont des sorties de essai_lecture_photos.py : <dossier>/<logement>/<version>/logement-meuble.json.
En vert : les meubles relevés à la main. En bleu : les meubles posés par Atelya que le relevé retrouve à moins de 80 cm.
En rouge : les meubles posés que le relevé n'a pas à cet endroit (doublon, meuble mal placé… ou vrai meuble oublié par le relevé).
En orange : les meubles du relevé qu'Atelya n'a pas retrouvés.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import diag_en_trop as diag  # noqa: E402
import essai_lecture_photos as essai  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402

NOMS = {"chaise": "chaise", "table": "table", "rangement": "buffet", "placard": "armoire", "bibliotheque": "bibliothèque", "canape": "canapé",
        "fauteuil": "fauteuil", "bureau": "bureau", "commode": "commode", "lit": "lit", "tapis": "tapis", "lampadaire": "lampadaire",
        "tabouret_haut": "tabouret", "chaise_de_bureau": "chaise de bureau", "meuble_tv": "meuble télé", "table_basse": "table basse",
        "colonne_cuisine": "colonne", "meuble_cuisine_bas": "cuisine", "ilot": "îlot", "caisson": "cloison bleue", "banc": "banc",
        "etagere_cubes": "étagère", "lit_superpose": "lit superposé", "table_de_chevet": "chevet", "table_d_appoint": "table d'appoint"}


def _police(taille: int, gras: bool = False):
    try:
        return ImageFont.truetype("arialbd.ttf" if gras else "arial.ttf", taille)
    except OSError:
        return ImageFont.load_default()


def plan(logement: dict, d: dict, px: int = 62) -> Image.Image:
    pts = [p for piece in logement["pieces"] for p in piece["contour"]]
    x0, y0 = min(p[0] for p in pts) - 0.4, min(p[1] for p in pts) - 0.4
    x1, y1 = max(p[0] for p in pts) + 0.4, max(p[1] for p in pts) + 0.4
    P = lambda p: ((p[0] - x0) * px, (y1 - p[1]) * px)
    im = Image.new("RGB", (int((x1 - x0) * px), int((y1 - y0) * px)), "white")
    g = ImageDraw.Draw(im)
    police = _police(13)
    for piece in logement["pieces"]:
        g.polygon([P(p) for p in piece["contour"]], fill=(246, 244, 238))
    for m in logement.get("murs", []):
        g.line([P(m["debut"]), P(m["fin"])], fill=(70, 70, 70), width=max(2, int(m.get("epaisseur", 0.2) * px)))
    for v in d["verite_sol"]:
        seul = any(v is s for s in d["seuls"])
        g.polygon([P(c) for c in diag._coins(v)], outline=(230, 140, 0) if seul else (0, 150, 0), width=3 if seul else 2)
    apparies = {id(m) for _, m in d["exacts"] + d["proches"] + d["hors"]}
    en_trop = {id(m) for m in d["en_trop"]}
    for m in logement.get("meubles", []):
        if id(m) in apparies:
            g.polygon([P(c) for c in diag._coins(m)], outline=(40, 90, 220), width=2)
    for m in logement.get("meubles", []):
        if id(m) in en_trop:
            g.polygon([P(c) for c in diag._coins(m)], outline=(220, 30, 30), width=3)
            g.text(P(m["position"]), NOMS.get(m["categorie"], m["categorie"]), fill=(200, 20, 20), font=police, anchor="mm")
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("avant", type=Path)
    ap.add_argument("apres", type=Path)
    ap.add_argument("cas")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--version", default="c")
    a = ap.parse_args()
    verite = essai.lire(essai.VERITES[a.cas]["meubles"])["meubles"]
    fiche = essai.lire(CAS[a.cas]["fiche"])
    images, titres = [], []
    for nom, dossier in (("AVANT", a.avant), ("APRÈS", a.apres)):
        logement = essai.lire(dossier / a.cas / a.version / "logement-meuble.json")
        d = diag.detail(logement, verite, fiche)
        images.append(plan(logement, d))
        titres.append(f"{nom} : {len(d['exacts']) + len(d['proches'])} meubles retrouvés sur {len(d['vrais_sol'])}, {len(d['en_trop'])} en rouge")
    l, h = images[0].size
    feuille = Image.new("RGB", (2 * l + 30, h + 96), "white")
    g = ImageDraw.Draw(feuille)
    for k, (im, titre) in enumerate(zip(images, titres)):
        feuille.paste(im, (10 + k * (l + 10), 50))
        g.text((16 + k * (l + 10), 12), titre, fill="black", font=_police(24, True))
    legende = [((0, 150, 0), "relevé fait à la main"), ((40, 90, 220), "posé par Atelya, retrouvé par le relevé"),
               ((220, 30, 30), "posé par Atelya, absent du relevé à cet endroit"), ((230, 140, 0), "du relevé, non retrouvé")]
    x = 16
    for couleur, texte in legende:
        g.rectangle([x, h + 62, x + 26, h + 80], outline=couleur, width=3)
        g.text((x + 34, h + 61), texte, fill=(40, 40, 40), font=_police(17))
        x += 60 + int(g.textlength(texte, font=_police(17)))
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    feuille.save(a.sortie, quality=90)
    print(a.sortie, feuille.size, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
