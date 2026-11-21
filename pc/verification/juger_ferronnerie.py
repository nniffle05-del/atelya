r"""LE JUGE DE LA FERRONNERIE, DANS LE FILM (20/11/2026) : le motif du garde-corps que montrent les photos du client, et celui
qu'on retrouve sur les images du FILM prises du même endroit.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_ferronnerie.py <sortie> app-004=<dossier des vues>
        [--avant app-004=<dossier des vues d'avant>]

<dossier des vues> : celui d'outils/unreal/vues_photos_unreal.py (vue-<photo>.png, trajet-<photo>.json, contexte.json).

Mesure. La même lecture est faite des deux côtés (moteur/ferronnerie.py) : chaque garde-corps est mis à plat (sur la photo :
entre le dessus lu du garde-corps et le bas de la vitre ; dans le film : le garde-corps de la maquette projeté par la caméra),
le fer y est repéré, le module qui se répète en est tiré. On compare alors :
- le PAS du motif (largeur d'une répétition, en parts de la hauteur du garde-corps) : photo contre film ;
- la RESSEMBLANCE des deux modules (1 = le même dessin, 0 = aucun rapport), une fois mis à la même taille et recalés,
  barreau retiré (deux garde-corps quelconques ont un barreau debout en commun : il ne prouve rien) ;
- par vue : la ressemblance de chaque garde-corps du film avec le module de la photo.
Avec des barreaux droits, le film n'a pas de volutes : ressemblance faible. Ce juge ne dit rien de la place du garde-corps
(jugée par juger_dessin_fenetres.py) ni de la vue derrière lui (juger_lumiere.py).
Sorties : <sortie>/ferronnerie-<logement>.jpg (module de la photo | du film avant | du film), <sortie>/ferronnerie.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import camera_photo, vue_dehors  # noqa: E402
from moteur import ferronnerie as fe  # noqa: E402
from moteur import juge_lumiere as jl  # noqa: E402
from moteur.habillage import PIED_GARDE_CORPS, RETRAIT_GARDE_CORPS  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402
from preparer_vitrages import photo_de  # noqa: E402


def lire(chemin) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def bandes_du_film(image: np.ndarray, o: dict, baie: dict, cam) -> list[dict]:
    """Le garde-corps de la maquette vu par la caméra du film, une bande par vantail du dessin de la baie (comme sur la
    photo : ce qui est derrière un montant de la fenêtre ne se voit pas)."""
    dessin = baie.get("dessin") or {}
    gc = dessin.get("garde_corps")
    if not gc:
        return []
    h = float(baie["hauteur"])
    z0 = float(baie.get("allege", 0.0) or 0.0)
    z_bas, z_haut = z0 + gc["bas"] * h + PIED_GARDE_CORPS, z0 + gc["haut"] * h
    t = (o["b"] - o["a"]) / np.linalg.norm(o["b"] - o["a"])
    large = float(np.linalg.norm(o["b"] - o["a"]))
    dehors = o["n"] * max(0.0, o["epaisseur"] / 2 - RETRAIT_GARDE_CORPS)
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sortie = []
    for v in dessin.get("vantaux") or []:
        a, b = o["a"] + t * v["debut"] * large + dehors, o["a"] + t * v["fin"] * large + dehors
        coins = np.array([[a[0], a[1], z_haut], [b[0], b[1], z_haut], [b[0], b[1], z_bas], [a[0], a[1], z_bas]], np.float32)
        us, vs, p = vue_dehors.projeter_tableau(coins, cam)
        if np.any(p <= 0.05):
            continue
        quad = np.stack([us, vs], 1).astype(np.float32)
        if quad[0][0] > quad[1][0]:
            quad = quad[[1, 0, 3, 2]]
        if abs(quad[1][0] - quad[0][0]) < 12 or abs(quad[3][1] - quad[0][1]) < 25:
            continue
        aspect = (v["fin"] - v["debut"]) * large / (z_haut - z_bas)  # dans le film, les vraies proportions sont connues
        largeur = max(8, int(round(fe.HAUT_PX * aspect)))
        m = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [largeur, 0], [largeur, fe.HAUT_PX], [0, fe.HAUT_PX]], np.float32))
        plat = cv2.warpPerspective(gris, m, (largeur, fe.HAUT_PX), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        dans = cv2.warpPerspective(np.full(gris.shape, 255, np.uint8), m, (largeur, fe.HAUT_PX), flags=cv2.INTER_NEAREST) > 0
        sortie.append({"fer": fe.fer(plat), "vu": dans, "aspect": float(aspect), "face": float(abs(quad[3][1] - quad[0][1])), "plat": plat})
    return sortie


def ressemblance(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Ressemblance de deux modules (0 à 1) : mis à la même taille, le second glissé de quelques pour cent pour coller au
    mieux. Le BARREAU ne compte pas (un trait debout, pareil à toutes les hauteurs : deux garde-corps quelconques l'ont en
    commun) : la moyenne de chaque colonne est retirée ; reste le dessin, volutes et frises."""
    if a is None or b is None:
        return 0.0
    h, l = 320, int(round(320 * a.shape[1] / a.shape[0]))
    a = cv2.resize(a, (l, h), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b, (l, h), interpolation=cv2.INTER_AREA)
    a = a - a.mean(0, keepdims=True)
    meilleur = 0.0
    for dx in range(-int(0.1 * l), int(0.1 * l) + 1, 2):
        for dy in range(-int(0.06 * h), int(0.06 * h) + 1, 3):
            c = np.roll(np.roll(b, dx, 1), dy, 0)
            meilleur = max(meilleur, fe._correlation(a, c - c.mean(0, keepdims=True)))
    return float(meilleur)


def vignette(module: dict | None, texte: str, hauteur: int = 480) -> np.ndarray:
    if module is None:
        image = np.full((hauteur, 200), 255, np.uint8)
        cv2.putText(image, "pas de motif", (10, hauteur // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
    else:
        f = module["fer"]
        image = np.clip(255 - np.tile(f, (1, 3)) / max(float(f.max()), 1e-6) * 255, 0, 255).astype(np.uint8)
        image = cv2.resize(image, (int(round(image.shape[1] * hauteur / image.shape[0])), hauteur), interpolation=cv2.INTER_CUBIC)
    bande = np.full((26, image.shape[1]), 255, np.uint8)
    cv2.putText(bande, texte, (3, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1, cv2.LINE_AA)
    return np.concatenate([bande, image], 0)


def juger(cas: str, dossier: Path, avant: Path | None, sortie: Path) -> dict:
    contexte = lire(dossier / "contexte.json")
    logements = {"film": lire(contexte["logement"])}
    if avant is not None:
        logements["avant"] = lire(lire(avant / "contexte.json")["logement"])
    logements = {k: v.get("logement", v) for k, v in logements.items()}
    lecture = lire(Path(contexte["logement"]).with_name("vitrages.json"))
    chemin_fiche = Path(contexte["fiche"]) if contexte.get("fiche") else Path(CAS[cas]["fiche"])
    chemin_fiche = chemin_fiche if chemin_fiche.is_absolute() else RACINE / chemin_fiche
    fiche, base = lire(chemin_fiche), chemin_fiche.parent
    dossiers = {"film": dossier, **({"avant": avant} if avant is not None else {})}
    photo_bandes, film_bandes = [], {cle: [] for cle in dossiers}
    par_vue: dict[tuple[str, str], dict] = {}
    for image_film in sorted(dossier.glob("vue-*.png")):
        nom = image_film.stem[4:]
        d = fiche["cameras"].get(nom)
        lues = [f for f in (lecture.get("photos") or {}).get(nom, []) if f.get("garde_corps") and f.get("coins")]
        if d is None or not lues:
            continue
        cam = camera_photo.camera_depuis_dict(d["camera"])
        photo = lire_image(photo_de(fiche, base, nom))
        for f in lues:
            b = fe.bande(photo, f)
            if b is not None:
                photo_bandes.append(b)
        for cle, dos in dossiers.items():
            if not (dos / f"vue-{nom}.png").is_file():
                continue
            trajet = lire(dos / f"trajet-{nom}.json") if (dos / f"trajet-{nom}.json").is_file() else {}
            image, _ = jl.film_au_cadre(lire_image(dos / f"vue-{nom}.png"), d, trajet)
            image = image if image.shape[:2] == photo.shape[:2] else cv2.resize(image, photo.shape[1::-1])
            vitrees = {o["id"]: o for o in vue_dehors.ouvertures_vitrees(logements[cle])}
            baies = {o["id"]: o for o in logements[cle]["ouvertures"]}
            for ident in sorted({f["baie"] for f in lues}):
                if ident in vitrees:
                    bs = bandes_du_film(image, vitrees[ident], baies[ident], cam)
                    film_bandes[cle] += bs
                    par_vue.setdefault((nom, ident), {})[cle] = bs
    m_photo = fe.module(photo_bandes)
    bilan = {"logement": cas, "photo": None if m_photo is None else {"pas": round(m_photo["pas"], 3), "repetitions": m_photo["repetitions"]}}
    vignettes = [vignette(m_photo, "les photos" + ("" if m_photo is None else f" (pas {m_photo['pas']:.2f})"))]
    for cle in ("avant", "film"):
        if cle not in dossiers:
            continue
        m = fe.module(film_bandes[cle])
        note = ressemblance(None if m_photo is None else m_photo["fer"], None if m is None else m["fer"])
        bilan[cle] = {"pas": None if m is None else round(m["pas"], 3), "repetitions": 0 if m is None else m["repetitions"],
                      "ressemblance": round(note, 3), "vues": []}
        for (nom, ident), bs in sorted(par_vue.items()):
            mv = fe.module(bs.get(cle, []), repetitions_min=2)
            bilan[cle]["vues"].append({"photo": nom, "baie": ident, "ressemblance": round(
                ressemblance(None if m_photo is None else m_photo["fer"], None if mv is None else mv["fer"]), 3)})
        vignettes.append(vignette(m, ("le film, avant" if cle == "avant" else "le film") + ("" if m is None else f" (pas {m['pas']:.2f})") + f" : {note:.2f}"))
        print(f"{cas} {'avant' if cle == 'avant' else 'film '} : pas {bilan[cle]['pas']} (photos {bilan['photo'] and bilan['photo']['pas']}), "
              f"ressemblance du motif {note:.2f} ; par vue : "
              + ", ".join(f"{v['photo'][6:]} {v['baie']} {v['ressemblance']:.2f}" for v in bilan[cle]["vues"]), flush=True)
    haut = max(v.shape[0] for v in vignettes)
    planche = [np.concatenate([v, np.full((haut - v.shape[0], v.shape[1]), 255, np.uint8)], 0) for v in vignettes]
    blanc = np.full((haut, 30), 255, np.uint8)
    ecrire_image(sortie / f"ferronnerie-{cas}.jpg", np.concatenate([x for v in planche for x in (v, blanc)], 1))
    return bilan


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sortie", type=Path)
    p.add_argument("vues", nargs="+", help="<logement>=<dossier des vues>")
    p.add_argument("--avant", nargs="*", default=[], help="<logement>=<dossier des vues d'avant>")
    a = p.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    avant = dict(x.split("=", 1) for x in a.avant)
    bilans = []
    for x in a.vues:
        cas, dossier = x.split("=", 1)
        bilans.append(juger(cas, Path(dossier), Path(avant[cas]) if cas in avant else None, a.sortie))
    (a.sortie / "ferronnerie.json").write_text(json.dumps(bilans, ensure_ascii=False, indent=1), encoding="utf-8")
