"""La VRAIE VUE par les fenêtres, tirée des photos du client : fabrique les toiles de chaque côté de l'immeuble (cinématique,
étape 5, 13/11/2026 ; méthode : moteur/vue_dehors.py).

    python outils/unreal/vue_dehors_photos.py <logement.json> <cameras-photos.json> <dossier de sortie> [--distance 35]

Distance des immeubles d'en face : MESURÉE SEULE sur les photos, côté par côté (moteur/distance_dehors.py : les étages d'en
face, étape 6, 13/11/2026) ; un côté non mesuré garde la distance par défaut (vue_dehors.DISTANCE_M) ; --distance l'impose
partout (ancien comportement). Le détail est dans <sortie>/distances-dehors.json, les étages trouvés dessinés sur les photos
dans <sortie>/distances-etages.jpg.

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
from moteur import camera_photo, distance_dehors, vue_dehors  # noqa: E402
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


def mesurer_distances(logement: dict, photos: list[dict], sortie: Path) -> dict:
    """Distance de chaque côté mesurée sur les photos (distance_dehors) ; écrit distances-dehors.json et la planche
    distances-etages.jpg (étages trouvés dessinés : vert = retenu, orange = seul, écarté)."""
    mesure = distance_dehors.mesurer_logement(logement, photos)
    (sortie / "distances-dehors.json").write_text(json.dumps(
        {"version": distance_dehors.VERSION, "hauteur_etage_m": distance_dehors.HAUTEUR_ETAGE_M,
         "par_defaut_m": vue_dehors.DISTANCE_M, "cotes": mesure}, indent=1, ensure_ascii=False), encoding="utf-8")
    vignettes = []
    for ph in photos:
        ms = [m for r in mesure.values() for m in r["par_photo"].get(ph["nom"], [])]
        if ms:
            im = distance_dehors.dessiner(ph["image"], ms, ph["cam"])
            cv2.putText(im, ph["nom"], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            vignettes.append(cv2.resize(im, (603, int(im.shape[0] * 603 / im.shape[1]))))
    if vignettes:
        h = max(v.shape[0] for v in vignettes)
        vignettes = [np.pad(v, ((0, h - v.shape[0]), (0, 0), (0, 0))) for v in vignettes]
        if len(vignettes) % 2:
            vignettes.append(np.zeros_like(vignettes[0]))
        planche = np.vstack([np.hstack(vignettes[i:i + 2]) for i in range(0, len(vignettes), 2)])
        cv2.imencode(".jpg", cv2.cvtColor(planche, cv2.COLOR_RGB2BGR))[1].tofile(str(sortie / "distances-etages.jpg"))
    return mesure


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
    pour_mesure = []
    for nom, chemin in fichiers.items():
        c = cameras["cameras"][nom]
        rvb = cv2.cvtColor(lire_image(str(chemin)), cv2.COLOR_BGR2RGB)
        pour_mesure.append({"nom": nom, "image": rvb, "cam": camera_photo.camera_depuis_dict(c["camera"]),
                            "qualite": c.get("qualite", "bonne"), "caches": caches.get(nom, []),
                            "ecart_px": float(c.get("ecart_moyen_px", 3.0))})
        ph = vue_dehors.preparer_photo(rvb, camera_photo.camera_depuis_dict(c["camera"]), ouvertures, c.get("qualite", "bonne"),
                                       murs, caches.get(nom, []), ecart_px=float(c.get("ecart_moyen_px", 3.0)),
                                       balcons=logement.get("balcons"))
        if ph is not None:
            ph["nom"] = nom
            photos.append(ph)
    distances, mesure, marches = distance, {}, None
    if distance is None:
        mesure = mesurer_distances(logement, pour_mesure, sortie)
        distances = {cote: m["distance_m"] for cote, m in mesure.items() if m["distance_m"] is not None}
        # un côté aux immeubles à plusieurs distances : décor qui SUIT LA RUE (une toile par distance, en biais entre deux)
        marches = {cote: m["marches"] for cote, m in mesure.items() if len(m.get("marches") or []) >= 2}
    vues, bilan, apercus = [], [], []
    toiles = vue_dehors.facades(logement, distances, marches)
    immeubles = [t for t in toiles if t["genre"] == "immeubles"]
    rues = {r["id"]: r for r in vue_dehors.rues(toiles)}

    def ecrire(plan, res, f):
        png = sortie / f"toile-{plan['id']}.png"
        cv2.imencode(".png", cv2.cvtColor(res["rvba"], cv2.COLOR_RGBA2BGRA))[1].tofile(str(png))
        vues.append({**vue_dehors.vers_unreal(plan), "id": plan["id"], "image": png.as_posix(), "force": vue_dehors.FORCE_TOILE})
        bilan.append({"cote": plan["id"], "distance_m": plan["distance"],
                      "distance": ("imposée" if distance is not None
                                   else mesure.get(f["cote"], {}).get("statut", "non_mesuree")),
                      "fenetres": plan["fenetres"], "part_couverte": res["couverte"], "photos": res["parts"]})
        a = res["rvba"][..., 3:4] / 255.0
        apercus.append((res["rvba"][..., :3] * a + np.array([60, 60, 60]) * (1 - a)).astype(np.uint8))

    couleurs, faits = {}, {}
    for f in immeubles:
        # une photo ne peint pas sur une toile ce qui est caché derrière une autre toile du même côté (décor qui suit la rue)
        ecrans = [g for g in immeubles if g["cote"] == f["cote"] and g is not f]
        r = vue_dehors.composer(f, photos, ecrans=ecrans)
        faits[f["id"]] = r
        if r["couverte"] > 0:
            couleurs[f["id"]] = np.median(r["_couleur"][r["_vu"]], axis=0)
    # la RUE au pied des immeubles d'en face : sol au niveau de la rue, UNIE (les photos ne voient pas la chaussée ; ce qu'elles
    # montrent sous les fenêtres est le sol des BALCONS, qui collé sur la rue y faisait des plaques beiges, 13/11/2026), d'UNE
    # seule couleur par côté (moyenne des pieds des toiles vues, pondérée par leur part vue) : avec un décor qui suit la rue,
    # une couleur par toile faisait des coins de teintes différentes
    rue_cote, couverture = {}, []
    for cote in {f["cote"] for f in immeubles}:
        cs = [(vue_dehors.couleur_de_la_rue(f, faits[f["id"]]), faits[f["id"]]["couverte"] * f["longueur_u"])
              for f in immeubles if f["cote"] == cote and faits[f["id"]]["couverte"] > 0]
        if cs:
            rue_cote[cote] = (np.sum([c * w for c, w in cs], axis=0) / sum(w for _, w in cs)).astype(np.float32)
    for f in immeubles:
        r = faits[f["id"]]
        if f["cote"] not in rue_cote:
            continue
        if r["couverte"] <= 0:
            # une toile qu'aucune photo ne voit : couleur unie de ses voisines (sinon un trou dans la rue)
            voisines = [couleurs[g["id"]] for g in immeubles if g["cote"] == f["cote"] and g["id"] in couleurs]
            r = vue_dehors.composer(f, [], defaut=np.median(voisines, axis=0))
        else:
            # ce qui est SOUS la vue (jamais photographié) : gardé en petit pour que la caméra du film l'évite
            sous = vue_dehors.sous_la_vue(r, f)
            png = sortie / f"sous-la-vue-{f['id']}.png"
            petit = cv2.resize(sous.astype(np.uint8) * 255, (max(1, sous.shape[1] // 8), max(1, sous.shape[0] // 8)),
                               interpolation=cv2.INTER_AREA)
            cv2.imencode(".png", petit)[1].tofile(str(png))
            couverture.append({"id": f["id"], "n": [float(x) for x in f["n"]], "decalage": float(f["decalage"]),
                               "origine": [float(x) for x in f["origine"]], "axe_u": [float(x) for x in f["axe_u"]],
                               "longueur_u": float(f["longueur_u"]), "longueur_v": float(f["longueur_v"]),
                               "sous_la_vue": png.as_posix()})
            r = vue_dehors.fondre_le_bas(r, f, rue_cote[f["cote"]])
        rue = rues[f["id"].replace("facade-", "rue-")]
        ecrire(f, r, f)
        ecrire(rue, vue_dehors.composer(rue, [], defaut=rue_cote[f["cote"]]), f)
    (sortie / "vues-dehors.json").write_text(json.dumps({"vues": vues, "bilan": bilan, "couverture": couverture,
                                                          "niveau_rue_m": vue_dehors.Z_BAS_M,
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
    p.add_argument("--distance", type=float, default=None, help="impose la distance des immeubles d'en face partout (défaut : mesurée sur les photos, "
                   f"{vue_dehors.DISTANCE_M} m pour un côté non mesuré)")
    a = p.parse_args()
    vues = preparer(Path(a.logement), Path(a.cameras), Path(a.sortie), a.distance)
    bilan = json.loads((Path(a.sortie) / "vues-dehors.json").read_text(encoding="utf-8"))["bilan"]
    for b in bilan:
        print(f"{b['cote']} : {b['distance_m']} m ({b['distance']}), fenêtres {b['fenetres']}, couverte {b['part_couverte']}, photos {b['photos']}")
    print(f"{len(vues)} toile(s) dans {a.sortie}")


if __name__ == "__main__":
    main()
