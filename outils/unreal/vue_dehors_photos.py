"""La VRAIE VUE par les fenêtres, tirée des photos du client : fabrique les toiles de chaque côté de l'immeuble (cinématique,
étape 5, 13/11/2026 ; méthode : moteur/vue_dehors.py).

    python outils/unreal/vue_dehors_photos.py <logement.json> <cameras-photos.json> <dossier de sortie> [--distance 35]

<cameras-photos.json> : la caméra de chaque photo du client (moteur/camera_photo.py ; « photos » = dossier des photos,
« fichier » = modèle de nom, « cameras » = {nom: {camera, qualite, …}}). Les meubles posés devant les fenêtres (chaises, télé…)
sont repérés par OWLv2 (moteur/owlv2.py, déjà en service pour les meubles) et écartés : ils ne sont pas peints sur la vue ;
le repérage est gardé dans <sortie>/meubles-devant-fenetres.json (refait seulement si les photos changent).
Sorties : <sortie>/toile-<côté>.png (RVBA : immeubles d'en face « facade-… » et rue à leurs pieds « rue-… ») et <sortie>/vues-dehors.json (la liste à donner à Unreal : coin, axes, taille, image,
force ; moteur/unreal/preparer_cinematique.poser_vues_dehors) + une planche toiles.jpg pour l'œil.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur import camera_photo, vue_dehors  # noqa: E402
from moteur.images import lire_image  # noqa: E402

SEUIL_MEUBLES = 0.2
GARDER = ("a television", "a lamp")  # « autre » pour le repérage des meubles, mais bien devant les fenêtres


def _photos(cameras: dict, base: Path) -> dict[str, Path]:
    """Les photos du client : « photos » est relatif à la racine du dépôt (comme dans verites/*/cameras-photos.json) ou, à défaut,
    au dossier du fichier des caméras."""
    dossier = Path(cameras.get("photos", "."))
    if not dossier.is_absolute():
        dossier = (RACINE / dossier) if (RACINE / dossier).is_dir() else (base / dossier)
    modele = cameras.get("fichier", "{nom}.jpg")
    res = {}
    for nom in cameras["cameras"]:
        chemin = dossier / modele.format(nom=nom)
        if not chemin.is_file():
            sys.exit(f"PLANTÉ : photo introuvable {chemin}")
        res[nom] = chemin
    return res


def meubles_devant(photos: dict[str, Path], cache: Path) -> dict[str, list]:
    """Rectangles (pixels) des meubles de chaque photo, repérés par OWLv2 ; gardés dans `cache` (empreinte des photos)."""
    empreinte = hashlib.sha256(b"".join(p.read_bytes() for p in photos.values())).hexdigest()[:16]
    if cache.is_file():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("empreinte") == empreinte:
            return d["boites"]
    from moteur import owlv2
    from moteur.pas_du_sol import NOMS, REQUETES
    modele = owlv2.charger()
    requetes = modele.textes(NOMS)
    boites = {}
    for nom, chemin in photos.items():
        rvb = cv2.cvtColor(lire_image(str(chemin)), cv2.COLOR_BGR2RGB)
        h, w = rvb.shape[:2]
        objets = owlv2.objets(modele.detecter(rvb, requetes), NOMS, seuil=SEUIL_MEUBLES, recouvrement_max=0.7)
        garde = [o["boite"] for o in objets
                 if (REQUETES[o["nom"]] not in ("autre", "tapis") or o["nom"] in GARDER)
                 and (o["boite"][2] - o["boite"][0]) * (o["boite"][3] - o["boite"][1]) < 0.5 * w * h]
        boites[nom] = garde
    cache.write_text(json.dumps({"empreinte": empreinte, "boites": boites}), encoding="utf-8")
    return boites


def preparer(logement_json: Path, cameras_json: Path, sortie: Path, distance: float | None = None) -> list[dict]:
    """Fabrique les toiles et renvoie la liste des vues à poser dans Unreal ([] si aucune photo ne voit dehors)."""
    logement = json.loads(logement_json.read_text(encoding="utf-8"))
    cameras = json.loads(cameras_json.read_text(encoding="utf-8"))
    sortie.mkdir(parents=True, exist_ok=True)
    fichiers = _photos(cameras, cameras_json.parent)
    caches = meubles_devant(fichiers, sortie / "meubles-devant-fenetres.json")
    ouvertures = vue_dehors.ouvertures_vitrees(logement)
    murs = vue_dehors.murs_et_trous(logement)
    photos = []
    for nom, chemin in fichiers.items():
        c = cameras["cameras"][nom]
        rvb = cv2.cvtColor(lire_image(str(chemin)), cv2.COLOR_BGR2RGB)
        ph = vue_dehors.preparer_photo(rvb, camera_photo.camera_depuis_dict(c["camera"]), ouvertures, c.get("qualite", "bonne"),
                                       murs, caches.get(nom, []), ecart_px=float(c.get("ecart_moyen_px", 3.0)),
                                       balcons=logement.get("balcons"))
        if ph is not None:
            ph["nom"] = nom
            photos.append(ph)
    vues, bilan, apercus = [], [], []
    toiles = vue_dehors.facades(logement, distance)
    for f, rue in zip(toiles, vue_dehors.rues(toiles)):
        r = vue_dehors.composer(f, photos)
        if r["couverte"] <= 0:
            continue
        # la toile des immeubles d'en face, puis la RUE à ses pieds (sol au niveau de la rue, couleur du bas de la vraie vue)
        # rue UNIE : les photos ne voient pas la chaussée ; ce qu'elles montrent sous les fenêtres est le sol des BALCONS (absents
        # de la maquette), qui collé sur la rue y faisait des plaques beiges (13/11/2026)
        r_rue = vue_dehors.composer(rue, [], defaut=vue_dehors.couleur_de_la_rue(f, r))
        for plan, res in ((f, r), (rue, r_rue)):
            png = sortie / f"toile-{plan['id']}.png"
            cv2.imencode(".png", cv2.cvtColor(res["rvba"], cv2.COLOR_RGBA2BGRA))[1].tofile(str(png))
            vues.append({**vue_dehors.vers_unreal(plan), "id": plan["id"], "image": png.as_posix(),
                         "force": vue_dehors.FORCE_TOILE})
            bilan.append({"cote": plan["id"], "distance_m": plan["distance"], "fenetres": plan["fenetres"],
                          "part_couverte": res["couverte"], "photos": res["parts"]})
            a = res["rvba"][..., 3:4] / 255.0
            apercus.append((res["rvba"][..., :3] * a + np.array([60, 60, 60]) * (1 - a)).astype(np.uint8))
    (sortie / "vues-dehors.json").write_text(json.dumps({"vues": vues, "bilan": bilan,
                                                          "photos_utilisees": [p["nom"] for p in photos]},
                                                         indent=1, ensure_ascii=False), encoding="utf-8")
    if apercus:
        h = 600
        planche = np.hstack([cv2.resize(x, (int(x.shape[1] * h / x.shape[0]), h)) for x in apercus])
        cv2.imencode(".jpg", cv2.cvtColor(planche, cv2.COLOR_RGB2BGR))[1].tofile(str(sortie / "toiles.jpg"))
    return vues


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("logement")
    p.add_argument("cameras")
    p.add_argument("sortie")
    p.add_argument("--distance", type=float, default=None, help=f"distance des immeubles d'en face (défaut {vue_dehors.DISTANCE_M} m)")
    a = p.parse_args()
    vues = preparer(Path(a.logement), Path(a.cameras), Path(a.sortie), a.distance)
    bilan = json.loads((Path(a.sortie) / "vues-dehors.json").read_text(encoding="utf-8"))["bilan"]
    for b in bilan:
        print(f"{b['cote']} : {b['distance_m']} m, fenêtres {b['fenetres']}, couverte {b['part_couverte']}, photos {b['photos']}")
    print(f"{len(vues)} toile(s) dans {a.sortie}")


if __name__ == "__main__":
    main()
