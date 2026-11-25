r"""LE JUGE DU DESSIN DES FENÊTRES, DANS LE FILM (F2 pièce 3, 20/11/2026) : la fenêtre de la photo du client et la même fenêtre
sur l'image du FILM prise du même endroit, toutes deux REDRESSÉES de face, côte à côte.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_dessin_fenetres.py <sortie> app-004=<dossier des vues> [app-002=…]
        [--avant app-004=<dossier des vues d'avant> …]

<dossier des vues> : celui d'outils/unreal/vues_photos_unreal.py (vue-<photo>.png, trajet-<photo>.json, contexte.json, qui dit
le logement ; le dessin lu des fenêtres, vitrages.json, est pris à côté de ce logement).

Pourquoi redresser : la fenêtre de la maquette est décalée de la vraie de 30 à 50 cm (place des photos calées) : comparer les
deux images point par point jugerait ce décalage, pas le dessin. Ici chaque fenêtre est mise à plat dans SON tour : celui lu sur
la photo (moteur/dessin_fenetres.tour_sur_la_photo), celui de la baie de la maquette projeté par la caméra du film. Restent les
PARTS de la fenêtre : où sont le cadre, le battement, les petits bois, la partie pleine, le garde-corps.

Mesure, par fenêtre : la place des BARRES. Le long de la largeur, la force des bords debout (cadre, battement, petits bois
debout) ; le long de la hauteur, celle des bords couchés (traverses, dessus de la partie pleine, main courante). Les deux courbes
de la photo et du film sont comparées (1 = mêmes barres aux mêmes places, 0 = aucun rapport). Ce que la photo cache (rideau,
meuble) est écarté des deux côtés. Sortie : <sortie>/fenetres-<logement>.jpg (photo | film avant | film), <sortie>/dessin.json.
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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import camera_photo, dessin_fenetres, vitrages, vue_dehors  # noqa: E402
from moteur import juge_lumiere as jl  # noqa: E402
from moteur.habillage import PROFONDEUR_CADRE, RETRAIT_FENETRE  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from banc_ressemblance import CAS  # noqa: E402
from preparer_vitrages import photo_de  # noqa: E402

HAUTEUR_PX = 420  # hauteur d'une fenêtre mise à plat
FACE_MIN_PX = 60  # une fenêtre plus étroite sur la photo n'est pas jugée (vue trop de biais ou trop loin)


def lire(chemin) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def a_plat(image: np.ndarray, quad, taille: tuple[int, int]) -> np.ndarray:
    largeur, hauteur = taille
    h = cv2.getPerspectiveTransform(np.array(quad, np.float32), np.array([[0, 0], [largeur, 0], [largeur, hauteur], [0, hauteur]], np.float32))
    return cv2.warpPerspective(image, h, (largeur, hauteur), flags=cv2.INTER_AREA if image.ndim == 3 else cv2.INTER_NEAREST)


def tour_dans_le_film(o: dict, cam) -> np.ndarray | None:
    """Les 4 coins de la baie de la maquette (dans le plan de son cadre) vus par la caméra : haut-gauche, haut-droit, bas-droit,
    bas-gauche de l'image. None si elle est derrière l'appareil."""
    vers_dedans = -(o["epaisseur"] / 2 - RETRAIT_FENETRE - PROFONDEUR_CADRE / 2)
    q = vue_dehors._quad(o, vers_dedans, 0.0)  # a bas, b bas, b haut, a haut
    u, v, p = vue_dehors.projeter_tableau(q, cam)
    if np.any(p <= 0.05):
        return None
    pts = np.stack([u, v], 1)
    a_bas, b_bas, b_haut, a_haut = pts
    return np.array([a_haut, b_haut, b_bas, a_bas] if a_haut[0] < b_haut[0] else [b_haut, a_haut, a_bas, b_bas], np.float32)


def barres(gris: np.ndarray, garde: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """La force des bords debout le long de la largeur, et des bords couchés le long de la hauteur (là où `garde` est vrai)."""
    g = cv2.GaussianBlur(gris.astype(np.float32), (0, 0), 1.2)
    debout = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    couche = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    poids = garde.astype(np.float32)
    en_x = (debout * poids).sum(0) / np.maximum(poids.sum(0), 1.0)
    en_y = (couche * poids).sum(1) / np.maximum(poids.sum(1), 1.0)
    lisse = lambda c: cv2.GaussianBlur(c.reshape(1, -1), (0, 0), 2.0).ravel()
    return lisse(en_x), lisse(en_y)


def accord(a: np.ndarray, b: np.ndarray, valide: np.ndarray) -> float:
    a, b = a[valide], b[valide]
    if len(a) < 20 or a.std() < 1e-6 or b.std() < 1e-6:
        return 0.0
    return float(max(0.0, np.corrcoef(a, b)[0, 1]))


def mesurer(photo_plate, film_plat, cache_plat) -> dict:
    """L'accord des barres de la photo et du film (voir le module)."""
    gris = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    garde = cache_plat == 0
    px, py = barres(gris(photo_plate), garde)
    fx, fy = barres(gris(film_plat), garde)
    vx, vy = garde.mean(0) > 0.3, garde.mean(1) > 0.3
    debout, couche = accord(px, fx, vx), accord(py, fy, vy)
    return {"debout": round(debout, 3), "couche": round(couche, 3), "dessin": round((debout + couche) / 2, 3)}


def titre(texte: str, largeur: int, hauteur: int = 24) -> np.ndarray:
    bande = np.full((hauteur, largeur, 3), 255, np.uint8)
    cv2.putText(bande, texte, (3, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    return bande


def juger(cas: str, dossier: Path, avant: Path | None, sortie: Path, lecture_json: Path | None = None) -> list[dict]:
    contexte = lire(dossier / "contexte.json")
    logement = lire(contexte["logement"])
    logement = logement.get("logement", logement)
    lecture = lire(lecture_json or Path(contexte["logement"]).with_name("vitrages.json"))
    chemin_fiche = Path(contexte["fiche"]) if contexte.get("fiche") else Path(CAS[cas]["fiche"])  # la même que le juge de la lumière
    chemin_fiche = chemin_fiche if chemin_fiche.is_absolute() else RACINE / chemin_fiche
    fiche, base = lire(chemin_fiche), chemin_fiche.parent
    vitrees = {o["id"]: o for o in vue_dehors.ouvertures_vitrees(logement)}
    baies = {o["id"]: o for o in logement["ouvertures"]}
    lignes, mesures = [], []
    for image_film in sorted(dossier.glob("vue-*.png")):
        nom = image_film.stem[4:]
        d = fiche["cameras"].get(nom)
        if d is None:
            continue
        cam = camera_photo.camera_depuis_dict(d["camera"])
        photo = lire_image(photo_de(fiche, base, nom))
        films = {}
        for cle, dos in (("avant", avant), ("film", dossier)):
            if dos is None or not (dos / f"vue-{nom}.png").is_file():
                continue
            trajet = lire(dos / f"trajet-{nom}.json") if (dos / f"trajet-{nom}.json").is_file() else {}
            image, _ = jl.film_au_cadre(lire_image(dos / f"vue-{nom}.png"), d, trajet)
            films[cle] = image if image.shape[:2] == photo.shape[:2] else cv2.resize(image, photo.shape[1::-1])
        par_baie: dict[str, list[dict]] = {}
        for f in (lecture.get("photos") or {}).get(nom, []):
            if f.get("coins"):
                par_baie.setdefault(f["baie"], []).append(f)
        for ident, fs in sorted(par_baie.items()):
            if ident not in vitrees or not any(f.get("cadre") for f in fs):
                continue
            o, b = vitrees[ident], baies[ident]
            au_sol = float(b.get("allege", 0.0) or 0.0) < dessin_fenetres.ALLEGE_AU_SOL
            tour, _ = dessin_fenetres.tour_sur_la_photo(fs, float(b["hauteur"]), au_sol)
            if min(tour[1][0] - tour[0][0], tour[2][0] - tour[3][0]) < FACE_MIN_PX * photo.shape[1] / 1206.0:
                continue
            quad_film = tour_dans_le_film(o, cam)
            if quad_film is None:
                continue
            taille = (int(round(HAUTEUR_PX * float(b["largeur"]) / float(b["hauteur"]))), HAUTEUR_PX)
            caches = np.zeros(photo.shape[:2], np.uint8)
            for f in fs:
                for c in f.get("caches") or []:
                    cv2.fillPoly(caches, [np.round(vitrages._polygone(c)).astype(np.int32)], 1)
            cache_plat = a_plat(caches, tour, taille)
            photo_plate = a_plat(photo, tour, taille)
            mesure = {"logement": cas, "photo": nom, "baie": ident}
            images = [("la photo", photo_plate)]
            for cle, image in films.items():
                plat = a_plat(image, quad_film, taille)
                mesure[cle] = mesurer(photo_plate, plat, cache_plat)
                images.append((f"le film{', avant' if cle == 'avant' else ''} : {mesure[cle]['dessin']:.2f}", plat))
            mesures.append(mesure)
            blanc = np.full((HAUTEUR_PX + 24, 10, 3), 255, np.uint8)
            ligne = [np.concatenate([titre(f"{cas} {nom} {ident}", 170), np.full((HAUTEUR_PX, 170, 3), 255, np.uint8)], 0)]
            for t, im in images:
                ligne += [np.concatenate([titre(t, im.shape[1]), im], 0), blanc]
            lignes.append(np.concatenate(ligne, 1))
            print(f"{cas} {nom} {ident} : " + " ; ".join(
                f"{cle} dessin {mesure[cle]['dessin']:.2f} (debout {mesure[cle]['debout']:.2f}, couché {mesure[cle]['couche']:.2f})"
                for cle in ("avant", "film") if cle in mesure), flush=True)
    if lignes:
        largeur = max(l.shape[1] for l in lignes)
        planche = [np.concatenate([l, np.full((l.shape[0], largeur - l.shape[1], 3), 255, np.uint8)], 1) for l in lignes]
        ecrire_image(sortie / f"fenetres-{cas}.jpg", np.concatenate(planche, 0))
    return mesures


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sortie", type=Path)
    p.add_argument("vues", nargs="+", help="<logement>=<dossier des vues>")
    p.add_argument("--avant", nargs="*", default=[], help="<logement>=<dossier des vues d'avant>")
    p.add_argument("--vitrages", nargs="*", default=[], help="<logement>=<vitrages.json> (sinon celui rangé à côté du logement)")
    a = p.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    avant = dict(x.split("=", 1) for x in a.avant)
    lectures = dict(x.split("=", 1) for x in a.vitrages)
    toutes = []
    for x in a.vues:
        cas, dossier = x.split("=", 1)
        toutes += juger(cas, Path(dossier), Path(avant[cas]) if cas in avant else None, a.sortie,
                        Path(lectures[cas]) if cas in lectures else None)
    resume = {}
    for cle in ("avant", "film"):
        communes = [m for m in toutes if "film" in m and (cle in m) and ("avant" in m or not avant)]
        if communes:
            resume[cle] = {k: round(float(np.mean([m[cle][k] for m in communes])), 3) for k in ("dessin", "debout", "couche")}
            resume[cle]["fenetres"] = len(communes)
    (a.sortie / "dessin.json").write_text(json.dumps({"resume": resume, "fenetres": toutes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nDESSIN DES FENÊTRES (1 = mêmes barres aux mêmes places que sur la photo)")
    for cle, r in resume.items():
        print(f"   {'avant' if cle == 'avant' else 'film '} : dessin {r['dessin']:.2f} (debout {r['debout']:.2f}, couché {r['couche']:.2f}) sur {r['fenetres']} fenêtre(s)")
