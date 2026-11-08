r"""Faire lire des plans par Claude (API Anthropic) et écrire, pour chaque plan, un logement.json + lecture.json
au même format que les lectures d'Atelya : outils/verite/noter_vrais_plans.py les note alors contre les vérités.

Pourquoi : savoir, chiffres à l'appui, si Claude lit les vrais plans assez bien (et pour combien) pour lui confier la
lecture au lancement, Atelya faisant le reste (photos, Blender, rendus). Les 13 plans d'examen restent un EXAMEN : on ne
règle pas la consigne sur eux.

Il faut : la bibliothèque `anthropic` (accord NT) et la variable d'environnement ANTHROPIC_API_KEY (jamais dans le dépôt).
Chaque appel COÛTE de l'argent : le script affiche le coût de chaque plan et s'arrête au-delà de --plafond-dollars.

    python outils/lecture_api/lire_plans_claude.py --plans /mnt/project-files/vrais-plans-recus/lot-2026-10-31 \
        --modele claude-sonnet-5-5 --sortie lectures-api/sonnet [--effort medium] [--plafond-dollars 10] [--seulement fr-006]
    python outils/verite/noter_vrais_plans.py --verites verites --lectures lectures-api/sonnet

Une seule passe par plan (une image, une réponse), sans zoom : c'est la version la moins chère.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
COTE_ATELYA = 768  # = moteur.lecture_complete.COTE_ATELYA (recopié pour ne pas charger OpenCV)
from moteur.logement import Logement  # noqa: E402

# Tarifs officiels lus le 08/11/2026 (platform.claude.com/docs/en/about-claude/pricing), $ par million de tokens.
TARIFS = {"claude-fable-5-1": (10.0, 50.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}
CACHE_LU = {"claude-fable-5-1": 0.25, "claude-opus-5-5": 0.20, "claude-sonnet-5-5": 0.10}  # $ / M tokens lus en cache
TYPES = ["sejour", "cuisine", "chambre", "sdb", "salle_d_eau", "wc", "entree", "degagement", "placard", "buanderie",
         "bureau", "escalier"]

CONSIGNE = f"""Tu lis un plan d'appartement (image jointe) et tu le décris en JSON, pour construire sa maquette 3D.

Règles :
- Longueurs en mètres. Repère vu de dessus : x vers la droite de l'image (est), y vers le HAUT de l'image (nord).
  Origine (0, 0) = coin intérieur en bas à gauche du logement.
- Échelle : déduis-la des cotes écrites, sinon des surfaces écrites (m²), sinon d'une barre d'échelle, sinon des portes
  (une porte intérieure fait ~0,83 m). Donne l'échelle en pixels de l'image par mètre.
- Murs : axe (ligne au milieu du mur) de « debut » à « fin », et épaisseur. Un mur droit par segment ; un mur courbe
  découpé en segments de 0,5 m environ.
- Ouvertures : type "porte", "porte_fenetre" ou "fenetre" ; id du mur qui la porte ; position = distance depuis le début
  du mur jusqu'au premier bord ; largeur. Hauteurs : porte 2,04 ; porte-fenêtre 2,15 ; fenêtre 1,35 avec allège 0,95.
- Pièces : contour intérieur (liste de points), nom écrit sur le plan s'il existe, et type parmi : {", ".join(TYPES)}.
  L'id d'une pièce est "<type>_<n>" (ex. "chambre_2").
- Ne recopie aucun nom de personne ni aucune adresse.

Réponds uniquement par un bloc ```json contenant :
{{"echelle": {{"px_par_m": nombre, "source": "cotes|surfaces|barre|portes", "sure": true|false, "explication": "courte"}},
  "logement": {{"schema": "logement/0.1", "projet_id": "plan", "hauteur_sous_plafond": 2.5,
    "murs": [{{"id": "M1", "statut": "estime", "source": "lecture_claude", "debut": [x, y], "fin": [x, y], "epaisseur": e}}],
    "ouvertures": [{{"id": "O1", "statut": "estime", "source": "lecture_claude", "type": "porte", "mur": "M1",
                     "position": p, "largeur": l, "hauteur": h, "allege": a}}],
    "pieces": [{{"id": "chambre_1", "statut": "estime", "source": "lecture_claude", "nom": "Chambre",
                 "contour": [[x, y], ...]}}]}},
  "doutes": ["ce qui est incertain, en une phrase chacun"]}}"""


def _image(chemin: Path) -> tuple[dict, int, int]:
    from PIL import Image
    w, h = Image.open(chemin).size
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[chemin.suffix.lower()]
    data = base64.standard_b64encode(chemin.read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}, w, h


def _json_de(texte: str) -> dict:
    m = re.search(r"```json\s*(.*?)```", texte, re.S)
    return json.loads(m.group(1) if m else texte)


def lire(client, modele: str, effort: str, chemin: Path) -> tuple[dict, dict]:
    bloc, w, h = _image(chemin)
    debut = time.time()
    with client.messages.stream(
        model=modele, max_tokens=64000, output_config={"effort": effort},
        system=[{"type": "text", "text": CONSIGNE, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [bloc, {"type": "text", "text": "Voici le plan."}]}],
    ) as flux:
        rep = flux.get_final_message()
    u = rep.usage
    pe, ps = TARIFS[modele]
    entree = (u.input_tokens + (u.cache_creation_input_tokens or 0) * 1.25) * pe / 1e6 + (u.cache_read_input_tokens or 0) * CACHE_LU[modele] / 1e6
    cout = {"tokens_entree": u.input_tokens, "cache_ecrit": u.cache_creation_input_tokens, "cache_lu": u.cache_read_input_tokens,
            "tokens_sortie": u.output_tokens, "dollars": round(entree + u.output_tokens * ps / 1e6, 4),
            "secondes": round(time.time() - debut, 1), "stop_reason": rep.stop_reason, "largeur": w, "hauteur": h}
    if rep.stop_reason != "end_turn":  # refus, sortie coupée… : noté, pas de lecture
        return {}, cout
    texte = "".join(b.text for b in rep.content if b.type == "text")
    return _json_de(texte), cout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", type=Path, required=True)
    ap.add_argument("--modele", choices=sorted(TARIFS), required=True)
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--plafond-dollars", type=float, default=10.0)
    ap.add_argument("--seulement", nargs="*")
    a = ap.parse_args()
    import anthropic  # importé ici : le reste du dépôt ne dépend pas de la bibliothèque
    client = anthropic.Anthropic()
    total, bilan = 0.0, []
    for chemin in sorted(p for p in a.plans.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")):
        if a.seulement and chemin.stem not in a.seulement:
            continue
        if total >= a.plafond_dollars:
            print(f"ARRÊT : plafond de {a.plafond_dollars} $ atteint ({total:.2f} $)")
            break
        dossier = a.sortie / chemin.stem
        dossier.mkdir(parents=True, exist_ok=True)
        try:
            lu, cout = lire(client, a.modele, a.effort, chemin)
        except anthropic.APIError as e:
            print(f"{chemin.stem} : ERREUR API {e}")
            bilan.append({"plan": chemin.stem, "erreur": str(e)})
            continue
        total += cout["dollars"]
        ligne = {"plan": chemin.stem, **cout}
        try:
            log = Logement.model_validate(lu["logement"])
            (dossier / "logement.json").write_text(log.model_dump_json(by_alias=True, indent=1), encoding="utf-8")
            ech = lu.get("echelle") or {}
            r_col = COTE_ATELYA / max(cout["largeur"], cout["hauteur"])  # même convention que les lectures d'Atelya
            lecture = {"modele": a.modele, "decision": "a_verifier",
                       "echelle": {"etat": "lue" if ech.get("sure") else "a_verifier", "source": ech.get("source"),
                                   "px_par_m_largeur": (ech.get("px_par_m") or 0) * r_col or None},
                       "details": {"types_pieces": {p.id: p.id.rsplit("_", 1)[0] for p in log.pieces}},
                       "doutes": [{"texte": d, "force": "faible"} for d in lu.get("doutes", [])], "cout": cout}
            (dossier / "lecture.json").write_text(json.dumps(lecture, ensure_ascii=False, indent=1), encoding="utf-8")
            ligne["valide"] = True
        except Exception as e:  # JSON absent ou logement incohérent : compté comme lecture ratée
            (dossier / "reponse-brute.json").write_text(json.dumps(lu, ensure_ascii=False, indent=1), encoding="utf-8")
            ligne["valide"], ligne["erreur"] = False, str(e)[:300]
        bilan.append(ligne)
        print(f"{chemin.stem} : {cout['dollars']:.3f} $ ({cout['tokens_sortie']} tokens écrits, {cout['secondes']} s) "
              f"{'OK' if ligne['valide'] else 'INVALIDE'}   total {total:.2f} $")
    (a.sortie / "couts.json").write_text(json.dumps({"modele": a.modele, "effort": a.effort, "total_dollars": round(total, 3),
                                                     "plans": bilan}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TOTAL {a.modele} : {total:.2f} $ pour {len(bilan)} plans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
