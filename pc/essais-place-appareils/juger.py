r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : le JUGE, sans tourner le film.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\juger.py <variante> [<variante>…] [--detail]

Pour chaque variante (un dossier ..\atelya\b2\place-appareils\<variante>\ écrit par caler.py ; « corrige » = les appareils
relevés à la main, pour voir ce que vaut un bon appareil devant chaque juge), trois mesures :
  1. EN MÈTRES contre les corrigés soignés (app-002, app-003 ; app-001 : relevé plus ancien, plusieurs « approchée ») ;
  2. DANS L'IMAGE, sur les REPÈRES relevés à la main dans ces corrigés (arêtes de murs, montants de portes… dont on connaît la
     place dans le logement) : où l'appareil d'Atelya les fait-il tomber sur la photo ? Écart moyen en pixels (photo de 1206 px
     de large). C'est ce que le film montre : une image prise de cet appareil, à côté de la photo.
  3. DANS L'IMAGE, sur les LIGNES LUES des fenêtres (vitrages.json : pied et haut du mur, tour de la menuiserie), contre la
     maquette d'aujourd'hui : « hauteurs » = sol, plafond, haut et bas de la menuiserie (ne dépend pas de la place de la fenêtre
     le long du mur) ; « côtés » = ses deux montants (dépend aussi de la place et de la largeur de la fenêtre sur le plan).
     Seul juge possible sur app-004 (pas de corrigé).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur.camera_photo import camera_depuis_dict, residus  # noqa: E402
from moteur.affiner_appareils import reperes_lus  # noqa: E402

PC = RACINE.parent / "atelya"
SORTIE = PC / "b2/place-appareils"
CORRIGES = {"app-001": RACINE / "verites/app-001/cameras-photos.json", "app-002": RACINE / "verites/app-002/cameras-photos-soigne.json",
            "app-003": RACINE / "verites/app-003/cameras-photos.json"}
# la maquette d'aujourd'hui (fenêtres à la largeur et à la hauteur vues sur les photos) et la lecture de ses fenêtres
MAQUETTES = {"app-001": PC / "lectures-photos/hauteur-baies/app-001", "app-002": PC / "lectures-photos/hauteur-baies/chaine/app-002/c",
             "app-004": PC / "lectures-photos/hauteur-baies/app-004"}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731


def ecarts_px(cam, reperes: list[dict]) -> list[float]:
    """Écart moyen (pixels, en valeur absolue) de chaque repère vu par cet appareil ; un repère derrière l'appareil : 999."""
    sortie = []
    for r in reperes:
        try:
            e = np.abs(residus(cam, [r]))
            sortie.append(float(min(e.mean(), 999.0)) if np.isfinite(e).all() else 999.0)
        except (ZeroDivisionError, FloatingPointError):
            sortie.append(999.0)
    return sortie


def cameras_de(variante: str, logement: str) -> dict | None:
    if variante == "corrige":
        return lire(CORRIGES[logement])["cameras"] if logement in CORRIGES else None
    if variante == "film-004":  # la fiche avec laquelle app-004 est filmé aujourd'hui
        return lire(PC / "b2/app-004/chaine-v2/cameras-photos-seul.json")["cameras"] if logement == "app-004" else None
    f = SORTIE / variante / f"{logement}.json"
    return lire(f)["cameras"] if f.is_file() else None


def juger(variante: str, detail: bool = False) -> dict:
    bilan = {}
    for logement in ("app-001", "app-002", "app-003", "app-004"):
        cams = cameras_de(variante, logement)
        if cams is None:
            continue
        b = bilan[logement] = {"metres": {}, "cap": {}, "avance": {}, "zoom": {}, "reperes": {}, "hauteurs": {}, "cotes": {}}
        if logement in CORRIGES:
            for n, k in lire(CORRIGES[logement])["cameras"].items():
                if n not in cams:
                    continue
                c, v = cams[n]["camera"], k["camera"]
                a = math.radians(v["cap"])
                b["metres"][n] = math.hypot(c["x"] - v["x"], c["y"] - v["y"])
                b["cap"][n] = abs((c["cap"] - v["cap"] + 180) % 360 - 180)
                b["avance"][n] = (c["x"] - v["x"]) * math.cos(a) + (c["y"] - v["y"]) * math.sin(a)
                b["zoom"][n] = c["f"] / v["f"]
                b["reperes"][n] = float(np.mean(ecarts_px(camera_depuis_dict(c), k["reperes"])))
        if logement in MAQUETTES:
            maquette, lecture = lire(MAQUETTES[logement] / "logement-meuble.json"), lire(MAQUETTES[logement] / "vitrages.json")
            maquette = maquette.get("logement", maquette)
            for n, fenetres in lecture["photos"].items():
                if n not in cams:
                    continue
                reps = reperes_lus(maquette, fenetres)
                e = ecarts_px(camera_depuis_dict(cams[n]["camera"]), reps)
                h = [x for x, r in zip(e, reps) if r["quoi"] in ("sol", "plafond", "haut", "bas")]
                c = [x for x, r in zip(e, reps) if r["quoi"] in ("gauche", "droite")]
                if h:
                    b["hauteurs"][n] = float(np.mean(h))
                if c:
                    b["cotes"][n] = float(np.mean(c))
        if detail:
            for n in sorted(cams):
                ligne = [f"{k} {b[k][n]:.2f}" for k in ("metres", "avance", "cap", "zoom") if n in b[k]] + [f"{k} {b[k][n]:.0f} px" for k in ("reperes", "hauteurs", "cotes") if n in b[k]]
                print(f"    {logement} {n} {cams[n].get('piece', ''):14s} " + ", ".join(ligne))
    return bilan


def resume(bilan: dict, cle: str, logements=None) -> str:
    v = [x for l, b in bilan.items() if logements is None or l in logements for x in b[cle].values()]
    if not v:
        return "      -      "
    v = np.array(v)
    return f"{np.median(v):5.2f} / {v.max():5.2f}" if cle == "metres" else f"{np.median(v):4.0f} / {v.mean():4.0f} ({len(v)})"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    detail = "--detail" in sys.argv
    print("variante        | mètres médiane / pire      | repères à la main, px : médiane / moyenne (photos)        | lignes lues, px : hauteurs | côtés")
    print("                | app-002       app-003     | app-001          app-002          app-003          | app-001  app-002  app-004 : médiane / moyenne (photos)")
    for v in args:
        b = juger(v, detail)
        print(f"{v:15s} | {resume(b, 'metres', ['app-002'])} {resume(b, 'metres', ['app-003'])} | "
              + " ".join(resume(b, 'reperes', [l]) for l in ("app-001", "app-002", "app-003")) + " | "
              + " ".join(resume(b, 'hauteurs', [l]) for l in ("app-001", "app-002", "app-004")) + " | "
              + " ".join(resume(b, 'cotes', [l]) for l in ("app-001", "app-002", "app-004")))
        (SORTIE / v).mkdir(parents=True, exist_ok=True)
        (SORTIE / v / "juge.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
