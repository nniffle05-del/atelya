r"""LE JUGE DE LA TRINGLE DANS LE FILM (23/11/2026, rideaux 2e temps, étape c) : la photo du client contre l'image du film prise
du même endroit.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_tringle_film.py <sortie> app-004=<vues hier>,<logement hier>,<vues aujourd'hui>,<logement aujourd'hui> [app-001=…]

Sur la PHOTO, la tringle est le trait fin trouvé à côté du haut de chaque rideau (moteur.equipements.trait_de_la_tringle, le
même que la mesure d'Atelya). Dans l'image du FILM, elle est là où la maquette la construit : ses deux bouts sont projetés par
l'appareil de la vue, puis le trait est cherché autour. Dans les deux, on lit :
- la CLARTÉ de la tringle contre le mur autour d'elle (0 = noire, 1 = comme le mur) : c'est sa teinte, à lumière égale ;
- sa PLACE dans l'image : à quelle part de la hauteur de l'image elle passe, à la colonne du rideau de la photo.
Sorties : le tableau, et <sortie>/tringle-<logement>-<photo>.jpg (photo | hier | aujourd'hui, cadrés sur la tringle, à REGARDER).
Ce juge dit si la tringle du film RESSEMBLE à celle de la photo ; la hauteur en mètres se juge contre le relevé (juger_rideaux.py).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "pc" / "verification"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GRIS = np.array([0.299, 0.587, 0.114])
QUAND = {"hier": "hier", "auj": "aujourd'hui"}


def tringles_de_la_maquette(logement: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Les deux bouts (3D) de la tringle de chaque fenêtre habillée, comme moteur/blender/rideaux.poser_rideaux la construit."""
    from moteur.habillage import rideaux_du_plan
    from moteur.logement import Logement

    sortie = {}
    for r in rideaux_du_plan(Logement.model_validate(logement)):
        a = math.radians(r["normale_deg"])
        n = np.array([math.cos(a), math.sin(a)])
        t = np.array([n[1], -n[0]])  # l'axe x que Blender donne à la fenêtre
        demi = r["largeur"] / 2
        pans = [p for p in (r.get("pans") or []) if isinstance(p, dict)] if r.get("rideaux") else []
        bouts = {cote: max([demi + 0.23] + [p["x1"] + 0.08 for p in pans if p["cote"] == cote]) for cote in (-1, 1)}
        ecart = (r.get("ecart") or 0.10) + (0.06 if r.get("rideaux") else 0.0)
        c = np.array(r["centre"], float) + n * ecart
        z = r["z_tringle"] + 0.012
        sortie[r["id"]] = (np.array([*(c - t * bouts[-1]), z]), np.array([*(c + t * bouts[1]), z]))
    return sortie


def lire_le_trait(rgb: np.ndarray, a, b) -> dict | None:
    """Le trait de la tringle cherché autour du segment a-b de l'image (pixels) : clarté contre le mur, couleur, place."""
    from moteur import equipements as eq

    (xa, ya), (xb, yb) = sorted([tuple(a), tuple(b)])
    H, W = rgb.shape[:2]
    xa, xb = max(2.0, xa), min(W - 3.0, xb)
    if xb - xa < eq.TRINGLE_COLONNES + 10:
        return None
    pente = (b[1] - a[1]) / (b[0] - a[0]) if abs(b[0] - a[0]) > 1 else 0.0
    xm = (xa + xb) / 2
    ym = a[1] + pente * (xm - a[0])
    trait = eq.trait_de_la_tringle(rgb, [xa, ym, xb, ym + 200.0], pente, dessus=True)
    if trait is None or trait["a"][0] < xa - 1 or trait["b"][0] > xb + 1:
        return None
    return {**trait, "clarte": float(np.asarray(trait["couleur"], float) @ GRIS) / max(1.0, float(np.asarray(trait["mur"], float) @ GRIS)),
            "pente": pente}


def y_a_la_colonne(trait: dict, x: float) -> float:
    (xa, ya), (xb, yb) = trait["a"], trait["b"]
    return ya + (yb - ya) * (x - xa) / max(1.0, xb - xa)


def juger(cas: str, spec: str, sortie: Path) -> list[dict]:
    import cv2

    from moteur import equipements as eq
    from moteur.camera_photo import camera_depuis_dict, projeter
    from moteur.images import ecrire_image, lire_image
    from banc_ressemblance import CAS
    from sonde_tringle import vues_des_tringles

    vues_hier, logement_hier, vues_auj, logement_auj = (Path(p) for p in spec.split(","))
    logements = {"hier": json.loads(logement_hier.read_text(encoding="utf-8")), "auj": json.loads(logement_auj.read_text(encoding="utf-8"))}
    dossiers = {"hier": vues_hier, "auj": vues_auj}
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    logement, vues, photos = vues_des_tringles(cas, logements["auj"])
    eq.rideaux_des_fenetres([v for v in vues if v.get("point")], logement)  # range chaque vue à sa fenêtre (v["pan"], v["tringle"])
    lignes = []
    for v in vues:
        t = (v.get("tringle") or {}).get("trait")
        fenetre = (v.get("pan") or {}).get("fenetre")
        if not t or not fenetre or v["sorte"] != "rideaux":
            continue
        nom = v["nom_photo"]
        photo = photos[nom]
        Hp, Wp = photo.shape[:2]
        x_pan = (v["boite"][0] + v["boite"][2]) / 2
        mur = np.asarray(t["mur"], float) @ GRIS
        ligne = {"cas": cas, "photo": nom, "fenetre": fenetre, "photo_clarte": float(np.asarray(t["couleur"], float) @ GRIS) / max(1.0, mur),
                 "photo_place": y_a_la_colonne(t, x_pan) / Hp}
        cam = camera_depuis_dict(fiche["cameras"][nom]["camera"])
        cases = [("la photo du client", cv2.cvtColor(photo, cv2.COLOR_RGB2BGR), t, 1.0, y_a_la_colonne(t, x_pan))]
        for quand in QUAND:
            fichier = dossiers[quand] / f"vue-{nom}.png"
            bouts = tringles_de_la_maquette(logements[quand]).get(fenetre)
            if not fichier.exists() or bouts is None:
                continue
            film = cv2.cvtColor(lire_image(fichier), cv2.COLOR_BGR2RGB)
            k = film.shape[1] / Wp
            pa, pb = (projeter(p, cam) for p in bouts)
            if pa[2] <= 0.1 or pb[2] <= 0.1:
                continue
            trait = lire_le_trait(film, (pa[0] * k, pa[1] * k), (pb[0] * k, pb[1] * k))
            if trait is not None:
                ligne[f"{quand}_clarte"] = trait["clarte"]
                ligne[f"{quand}_place"] = y_a_la_colonne(trait, x_pan * k) / film.shape[0]
            else:  # pas de trait net : la place où la maquette la met
                ligne[f"{quand}_place"] = (pa[1] + (pb[1] - pa[1]) * (x_pan - pa[0]) / (pb[0] - pa[0] if abs(pb[0] - pa[0]) > 1 else 1.0)) * k / film.shape[0]
            cases.append((f"le film, {QUAND[quand]}", cv2.cvtColor(film, cv2.COLOR_RGB2BGR), trait, k, ligne[f"{quand}_place"] * film.shape[0]))
        # l'image de contrôle : chaque image cadrée sur la tringle de la photo, le trait lu marqué de deux tirets
        bandes = []
        for titre, img, trait, k, y_trait in cases:
            cx, cy = int(x_pan * k), int(y_trait)
            l, h = int(260 * k), int(110 * k)
            x0, y0 = max(0, min(img.shape[1] - 2 * l, cx - l)), max(0, min(img.shape[0] - 2 * h, cy - h))
            coupe = img[y0:y0 + 2 * h, x0:x0 + 2 * l].copy()
            if trait is not None:
                for bout in (trait["a"], trait["b"]):
                    cv2.line(coupe, (int(bout[0] - x0), int(bout[1] - y0) - 9), (int(bout[0] - x0), int(bout[1] - y0) + 9), (0, 0, 255), 1)
            coupe = cv2.resize(coupe, (520, 220), interpolation=cv2.INTER_AREA)
            cv2.rectangle(coupe, (0, 0), (300, 20), (255, 255, 255), -1)
            cv2.putText(coupe, titre.replace("'", " "), (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            bandes.append(coupe)
        ecrire_image(sortie / f"tringle-{cas}-{nom}.jpg", np.hstack(bandes))
        lignes.append(ligne)
    return lignes


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    lignes = []
    for arg in sys.argv[2:]:
        cas, _, spec = arg.partition("=")
        lignes += juger(cas, spec, sortie)
    dire = lambda x: "  —  " if x is None else f"{x:5.2f}"
    print("vue                 fenêtre | clarté de la tringle contre le mur : photo, hier, aujourd'hui | place dans l'image : photo, hier, aujourd'hui")
    for l in lignes:
        print(f"{l['cas']} {l['photo']:9s} {l['fenetre']:6s} | {dire(l['photo_clarte'])} {dire(l.get('hier_clarte'))} {dire(l.get('auj_clarte'))}"
              f" | {dire(l['photo_place'])} {dire(l.get('hier_place'))} {dire(l.get('auj_place'))}")
    for quand in QUAND:
        clartes = [abs(l[f"{quand}_clarte"] - l["photo_clarte"]) for l in lignes if l.get(f"{quand}_clarte") is not None]
        sans = sum(1 for l in lignes if l.get(f"{quand}_clarte") is None)
        places = [abs(l[f"{quand}_place"] - l["photo_place"]) for l in lignes if l.get(f"{quand}_place") is not None]
        print(f"{QUAND[quand]:12s}: écart de clarté moyen {np.mean(clartes) if clartes else float('nan'):.2f} sur {len(clartes)} vue(s) "
              f"({sans} sans trait lisible) ; écart de place moyen {100 * np.mean(places) if places else float('nan'):.1f} % de la hauteur de l'image")
    (sortie / "tringle-film.json").write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
