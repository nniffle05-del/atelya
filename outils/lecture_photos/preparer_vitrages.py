r"""LE DESSIN DES FENÊTRES, à faire lire (F2, 20/11/2026) : Atelya montre chaque fenêtre claire de chaque photo, en grand.

    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\preparer_vitrages.py <logement.json> <cameras-photos.json> <sortie>
    ..\atelya\.venv\Scripts\python.exe outils\lecture_photos\preparer_vitrages.py controle <logement.json> <cameras-photos.json> <vitrages.json> <sortie>

1re forme : pour chaque photo et chaque fenêtre non voilée qu'elle montre (trou d'au moins 3 000 pixels d'après le plan et la
place de l'appareil), écrit <sortie>/<photo>-<baie>.jpg : la photo recadrée autour de la fenêtre, agrandie, avec une RÈGLE
graduée en pixels de la photo entière et un quadrillage léger tous les 25 pixels ; et <sortie>/liste.json (ce qu'il faut lire).
La lecture rend le dessin de chaque fenêtre (moteur/vitrages.py : coins, montants, traverses, caches, vue).

2e forme (« controle ») : dessine la lecture sur les mêmes images (VERT = les vitres nues gardées pour la vue, ROUGE = barres et
caches écartés, trait JAUNE = le vitrage lu) : à REGARDER avant de s'en servir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import camera_photo, vitrages, vue_dehors  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402

TROU_MIN = 3000  # pixels (photo de 1206 px de large) : en dessous la fenêtre est trop petite ou trop coupée pour être lue
MARGE = 70  # pixels de la photo gardés autour du trou (la place de l'appareil est connue à 30-50 cm : le trou tombe à côté)
QUADRILLAGE = 25
COTE_VOULU = 1700  # le grand côté de l'image agrandie, en pixels


def photo_de(fiche: dict, base: Path, nom: str) -> Path | None:
    dossier = Path(fiche.get("photos", "."))
    if not dossier.is_absolute():
        dossier = (RACINE / dossier) if (RACINE / dossier).is_dir() else (base / dossier)
    modeles = [fiche["fichier"]] if fiche.get("fichier") else ["{nom}.png", "{nom}.jpg"]
    return next((dossier / m.format(nom=nom) for m in modeles if (dossier / m.format(nom=nom)).is_file()), None)


def cadres(logement: dict, fiche: dict, base: Path) -> list[dict]:
    """Chaque (photo, fenêtre claire) à lire : {photo, baie, chemin, cadre [x0, y0, x1, y1], trou (pixels)}."""
    ouvertures = vue_dehors.ouvertures_vitrees(logement)
    murs = vue_dehors.murs_et_trous(logement)
    res = []
    for nom, d in fiche["cameras"].items():
        chemin = photo_de(fiche, base, nom)
        if chemin is None:
            raise SystemExit(f"PLANTÉ : photo introuvable pour {nom}")
        image = lire_image(chemin)
        h, w = image.shape[:2]
        cam = camera_photo.camera_depuis_dict(d["camera"])
        for o in ouvertures:
            if o.get("voilee"):
                continue
            _, trou = vue_dehors.masque_fenetres(cam, (w, h), [o], murs)
            if trou.sum() < TROU_MIN * (w / 1206.0) ** 2:
                continue
            vs, us = np.nonzero(trou)
            m = int(round(MARGE * w / 1206.0))
            res.append({"photo": nom, "baie": o["id"], "chemin": str(chemin), "trou": int(trou.sum()),
                        "cadre": [int(max(0, us.min() - m)), int(max(0, vs.min() - m)), int(min(w, us.max() + m)), int(min(h, vs.max() + m))]})
    return res


def agrandir(image: np.ndarray, cadre: list[int], dessus=None) -> np.ndarray:
    """La photo recadrée et agrandie, avec sa règle (pixels de la photo entière) ; `dessus(vue, k, x0, y0)` dessine en plus."""
    x0, y0, x1, y1 = cadre
    k = max(1.0, min(7.0, COTE_VOULU / max(x1 - x0, y1 - y0)))
    vue = cv2.resize(image[y0:y1, x0:x1], None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    if dessus is not None:
        vue = dessus(vue, k, x0, y0)
    hv, wv = vue.shape[:2]
    bord = 34
    toile = np.full((hv + 2 * bord, wv + 2 * bord, 3), 255, np.uint8)
    toile[bord:bord + hv, bord:bord + wv] = vue
    for x in range((x0 // 5) * 5, x1 + 1, 5):
        if x < x0:
            continue
        px = bord + int(round((x - x0) * k))
        grand = x % QUADRILLAGE == 0
        for ybase, sens in ((bord, -1), (bord + hv, 1)):
            cv2.line(toile, (px, ybase), (px, ybase + sens * (9 if grand else 4)), (0, 0, 0), 1)
        if grand:
            cv2.line(toile, (px, bord), (px, bord + hv), (0, 200, 255), 1)
            for ytexte in (12, bord + hv + 26):
                cv2.putText(toile, str(x), (px - 14, ytexte), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    for y in range((y0 // 5) * 5, y1 + 1, 5):
        if y < y0:
            continue
        py = bord + int(round((y - y0) * k))
        grand = y % QUADRILLAGE == 0
        for xbase, sens in ((bord, -1), (bord + wv, 1)):
            cv2.line(toile, (xbase, py), (xbase + sens * (9 if grand else 4), py), (0, 0, 0), 1)
        if grand:
            cv2.line(toile, (bord, py), (bord + wv, py), (0, 200, 255), 1)
            for xtexte in (1, bord + wv + 3):
                cv2.putText(toile, str(y), (xtexte, py + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1, cv2.LINE_AA)
    # le quadrillage est repassé en très léger sur l'image elle-même (il ne doit pas cacher les bords des montants)
    net = np.full_like(toile, 255)
    net[bord:bord + hv, bord:bord + wv] = vue
    zone = (slice(bord, bord + hv), slice(bord, bord + wv))
    toile[zone] = (0.25 * toile[zone] + 0.75 * net[zone]).astype(np.uint8)
    return toile


def preparer(logement_json: Path, cameras_json: Path, sortie: Path) -> list[dict]:
    logement = json.loads(logement_json.read_text(encoding="utf-8"))
    fiche = json.loads(cameras_json.read_text(encoding="utf-8"))
    sortie.mkdir(parents=True, exist_ok=True)
    liste = cadres(logement, fiche, cameras_json.parent)
    for c in liste:
        image = lire_image(c["chemin"])
        c["image"] = f"{c['photo']}-{vue_dehors.nom_de_fichier(c['baie'])}.jpg"
        c["taille"] = [int(image.shape[1]), int(image.shape[0])]
        ecrire_image(sortie / c["image"], agrandir(image, c["cadre"]))
        print(f"{c['photo']} {c['baie']} : trou {c['trou']} px, cadre {c['cadre']} → {c['image']}", flush=True)
    (sortie / "liste.json").write_text(json.dumps({"format": vitrages.FORMAT, "consigne": vitrages.consigne(),
                                                    "a_lire": [{k: v for k, v in c.items() if k != "chemin"} for c in liste]},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    return liste


def controle(logement_json: Path, cameras_json: Path, vitrages_json: Path, sortie: Path) -> int:
    logement = json.loads(logement_json.read_text(encoding="utf-8"))
    fiche = json.loads(cameras_json.read_text(encoding="utf-8"))
    lecture = json.loads(vitrages_json.read_text(encoding="utf-8"))
    sortie.mkdir(parents=True, exist_ok=True)
    liste = cadres(logement, fiche, cameras_json.parent)
    tailles = {}
    for c in liste:
        image = lire_image(c["chemin"])
        h, w = image.shape[:2]
        tailles[c["photo"]] = (w, h)
        dits = [f for f in (lecture.get("photos") or {}).get(c["photo"], []) if f["baie"] == c["baie"]]
        lu = vitrages.d_une_photo(lecture, c["photo"], (w, h)).get(c["baie"])
        if lu is None:
            print(f"{c['photo']} {c['baie']} : PAS LUE (ancien comportement : le trou du plan)", flush=True)
            continue
        if lu["vue"] != "oui":
            print(f"{c['photo']} {c['baie']} : lue « {lu['vue']} »", flush=True)
            continue
        entier, nues = lu["vitrage"], lu["vitres"]

        def dessus(vue, k, x0, y0, entier=entier, nues=nues, dits=dits):
            hv, wv = vue.shape[:2]
            h0, w0 = int(round(hv / k)), int(round(wv / k))
            e = cv2.resize(entier[y0:y0 + h0, x0:x0 + w0], (wv, hv), interpolation=cv2.INTER_NEAREST)
            n = cv2.resize(nues[y0:y0 + h0, x0:x0 + w0], (wv, hv), interpolation=cv2.INTER_NEAREST)
            v = vue.astype(np.float32)
            v[n > 0] = v[n > 0] * 0.6 + np.array([0, 255, 0]) * 0.4
            rouge = (e > 0) & (n == 0)
            v[rouge] = v[rouge] * 0.6 + np.array([0, 0, 255]) * 0.4
            v = v.astype(np.uint8)
            for f in dits:
                pts = np.round((np.array(f["coins"], float) - [x0, y0]) * k).astype(np.int32)
                cv2.polylines(v, [pts], True, (0, 255, 255), 1, cv2.LINE_AA)
            return v

        ecrire_image(sortie / f"{c['photo']}-{vue_dehors.nom_de_fichier(c['baie'])}.jpg", agrandir(image, c["cadre"], dessus))
        print(f"{c['photo']} {c['baie']} : vitrage {int(entier.sum())} px, vitres nues {int(nues.sum())} px", flush=True)
    defauts = vitrages.controler(lecture, tailles, {o["id"] for o in logement.get("ouvertures", [])})
    for d in defauts:
        print(f"DÉFAUT : {d}", flush=True)
    return 1 if defauts else 0


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "controle":
        sys.exit(controle(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])))
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    preparer(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
