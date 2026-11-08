r"""La lecture de Claude, de bout en bout, SANS appeler l'API (aucune dépense) : préparer ce qu'on enverrait, puis traduire la
fiche rendue en logement et en écran de vérification.

Pourquoi : au lancement, c'est Claude qui lit les plans (décision NT du 08/11/2026) ; Atelya fait tout le reste. Cet outil est
le « reste » : il ne parle pas à l'API (ça viendra plus tard, avec l'accord de NT), il travaille sur une fiche déjà écrite.

Depuis le dossier du dépôt (atelya-code) :

    # 1. L'image exacte à envoyer à Claude (réduite comme l'API le ferait, pour que ses pixels soient les nôtres) + la consigne
    ..\atelya\.venv\Scripts\python.exe outils\lecture_claude\traduire_fiche.py preparer mon-plan.pdf --sortie ..\atelya\lectures-claude

    # 2. La fiche rendue par Claude (lecture-claude/0.1) → logement.json, verification.json, ecran.html (double-clic)…
    ..\atelya\.venv\Scripts\python.exe outils\lecture_claude\traduire_fiche.py traduire mon-plan.pdf --fiche fiche.json --sortie ..\atelya\lectures-claude

Sorties dans <sortie>\<nom du plan>\ : envoi.png et consigne.txt (preparer) ; ecran.html, plan.png, verification.json,
logement.json, lecture.json, coloriage.png = la fiche dessinée en classes du U-Net (traduire).
Une fiche refusée n'est pas un plantage : la commande le dit et finit normalement. Un plantage finit par un code ≠ 0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))

from lire_plan import ecrire  # noqa: E402  (mêmes fichiers de sortie que la lecture par Atelya)

from moteur.lecture_claude import consigne, controler_fiche, image_pour_claude  # noqa: E402
from moteur.lecture_complete import FichierNonLisible, PlanSource, plans_du_fichier  # noqa: E402
from moteur.traduire_claude import traduire  # noqa: E402


def _source(fichier: Path, page: int | None) -> PlanSource:
    sources = plans_du_fichier(fichier)
    if page is None:
        return sources[0]
    for s in sources:
        if s.page == page:
            return s
    raise FichierNonLisible(f"page {page} introuvable (pages lues : {[s.page for s in sources]})")


def preparer(source: PlanSource, dossier: Path) -> dict:
    dossier.mkdir(parents=True, exist_ok=True)
    envoi, facteur = image_pour_claude(source.image)
    Image.fromarray(envoi).save(dossier / "envoi.png")
    (dossier / "consigne.txt").write_text(consigne(), encoding="utf-8")
    infos = {"plan": source.nom, "page": source.page, "taille_plan": list(source.image.shape[1::-1]),
             "taille_envoi": list(envoi.shape[1::-1]), "facteur": facteur}
    (dossier / "envoi.json").write_text(json.dumps(infos, ensure_ascii=False, indent=1), encoding="utf-8")
    return infos


def main() -> int:
    ap = argparse.ArgumentParser(description="Lecture de Claude sans API : préparer l'envoi, traduire la fiche")
    ap.add_argument("action", choices=["preparer", "traduire"])
    ap.add_argument("plan", type=Path, help="le plan (image ou PDF)")
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--fiche", type=Path, help="traduire : la fiche lecture-claude/0.1 rendue par Claude")
    ap.add_argument("--page", type=int, help="PDF : la page lue (par défaut, celle que choisit le tri)")
    ap.add_argument("--textes-atelya", action="store_true",
                    help="traduire : textes du plan lus par l'OCR d'Atelya (fiche tirée d'une vérité, qui n'a pas de textes)")
    a = ap.parse_args()

    if not a.plan.is_file():
        print(f"PLANTÉ : plan introuvable : {a.plan}", flush=True)
        return 2
    try:
        source = _source(a.plan, a.page)
    except FichierNonLisible as e:
        print(f"{a.plan.name} : REFUSÉ, {e}", flush=True)
        return 0
    dossier = a.sortie / source.nom
    if a.action == "preparer":
        infos = preparer(source, dossier)
        print(f"{source.nom} : image à envoyer {infos['taille_envoi'][0]} × {infos['taille_envoi'][1]} px "
              f"(facteur {infos['facteur']:.4f}) : {dossier}", flush=True)
        return 0

    if a.fiche is None or not a.fiche.is_file():
        print(f"PLANTÉ : fiche introuvable : {a.fiche}", flush=True)
        return 2
    t0 = time.time()
    if a.textes_atelya and source.textes is None:
        import numpy as np

        from moteur.lecture_cotes import lire_textes_et_echelle

        source.textes, _ = lire_textes_et_echelle(np.asarray(Image.fromarray(source.image).convert("L")))
    envoi, facteur = image_pour_claude(source.image)
    controlee = controler_fiche(json.loads(a.fiche.read_text(encoding="utf-8")), (envoi.shape[1], envoi.shape[0]))
    plan = traduire(source, controlee, facteur)
    duree = time.time() - t0
    ecrire(plan, dossier, duree)
    g = plan.gardee
    if g.logement is None:
        print(f"{source.nom} : REFUSÉ ({g.erreur})", flush=True)
        return 0
    forts = sum(d["gravite"] == "fort" for d in g.examen["doutes"])
    print(f"{source.nom} : {plan.decision}, échelle {g.echelle['etat']} ({g.echelle['source']}), "
          f"{len(g.logement['murs'])} murs, {len(g.logement['ouvertures'])} ouvertures, {len(g.logement['pieces'])} pièces, "
          f"{forts} doutes forts, {duree:.1f} s : {dossier / 'ecran.html'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
