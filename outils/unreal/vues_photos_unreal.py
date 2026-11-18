r"""LE JUGE DANS LE FILM : la photo du client à côté d'une image du FILM Unreal prise du même endroit (18/11/2026).

    python outils/unreal/vues_photos_unreal.py <dossier 3d> <nom> <fiche des caméras> <sortie> [--photos photo-01 photo-07]
        [--eclairage jour_voile] [--sans-export] [--sans-import] [--paquet <paquet déjà fait>] [options du film…]

Pourquoi : le produit d'Atelya est la cinématique et la visite dans Unreal, pas des images fixes de Blender (CLAUDE.md § 0).
On juge donc là où le client regardera : pour chaque photo du client, la caméra du film est posée à la place de l'appareil
(même endroit, même direction, même angle de champ, MÊME CADRE : moteur/juge_lumiere.cadre_du_film) et le film y tourne trois
images, avec les réglages du film (lumière, exposition du « photographe »). Les photos ne sont qu'un modèle pour comparer.
--paquet : reprendre un paquet pour Unreal déjà fait (essais de lumière sur la même maquette : rien n'est refait ni réimporté
si --sans-import). Les options inconnues ici sont passées telles quelles au film (outils/unreal/cinematique_unreal.py :
--moteur path_tracer, --force-ciel 2, --exposition-fixe -5…).
<dossier 3d> : la maquette faite par Atelya (maquette.blend, construction.json…) ; <nom> : nom court sans accent du niveau Unreal.
1. le paquet pour Unreal est refait (outils/unreal/exporter_pour_unreal.py), sauf --sans-export ;
2. pour chaque photo : un trajet immobile à la place de l'appareil, rendu par outils/unreal/cinematique_unreal.py (la maquette
   est importée au premier, sauf --sans-import) ;
3. <sortie>/vue-<photo>.png (l'image du film) et <sortie>/film-contre-photos.jpg (la photo | l'image du film).
L'éditeur Unreal doit être FERMÉ pendant le calcul. S'arrête au premier plantage.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur.juge_lumiere import cadre_du_film  # noqa: E402

STUDIO = Path("D:/Atelya-Unreal")
SCENES = {"jour_voile": "2 Jour voilé", "jour_soleil": "1 Jour ensoleillé"}


def lancer(commande: list, journal: Path, quoi: str) -> None:
    r = subprocess.run([str(c) for c in commande], cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with journal.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {quoi}\n" + r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"PLANTÉ : {quoi} (code {r.returncode}) : voir {journal}", flush=True)
        sys.exit(r.returncode or 1)


def trajet_de_la_photo(d: dict, eclairage: str) -> dict:
    """Le trajet immobile qui met la caméra du film à la place de l'appareil de la photo, AU CADRE EXACT de la photo : l'appareil
    regarde à l'horizontale avec un horizon décalé dans l'image ; le film est tourné sur une image plus grande, centrée sur
    l'horizon, puis rogné au cadre de la photo (« rognage »). Jusqu'au 18/11/2026 la caméra était penchée vers le centre de la
    photo : cadrage plus plongeant, verticales qui fuyaient."""
    c = d["camera"]
    cadre = cadre_du_film(d)
    a = math.radians(float(c["cap"]))
    p0 = [float(c["x"]), float(c["y"]), float(c["z"]), float(c["cap"]), cadre["tangage"]]
    p1 = [p0[0] + 0.01 * math.cos(a), p0[1] + 0.01 * math.sin(a), *p0[2:]]  # un centimètre : immobile à l'œil
    return {"points": [p0, p1], "images": 3, "focale_mm": cadre["focale_mm"], "format": cadre["format"],
            "cadre": "photo", "rognage": cadre["rognage"], "scene": SCENES.get(eclairage, eclairage)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier_3d", type=Path)
    ap.add_argument("nom")
    ap.add_argument("fiche", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--photos", nargs="*")
    ap.add_argument("--eclairage", default="jour_voile")
    ap.add_argument("--sans-export", action="store_true")
    ap.add_argument("--sans-import", action="store_true")
    ap.add_argument("--paquet", type=Path, help="un paquet pour Unreal déjà fait (essais de lumière sur la même maquette)")
    a, pour_le_film = ap.parse_known_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    journal = a.sortie / "journal.txt"
    py = sys.executable
    paquet = a.paquet or a.sortie / "paquet"
    if not a.sans_export and a.paquet is None:
        debut = time.time()
        lancer([py, "outils/unreal/exporter_pour_unreal.py", a.dossier_3d, paquet], journal, "paquet pour Unreal")
        print(f"paquet pour Unreal fait en {time.time() - debut:.0f} s", flush=True)
    fiche = json.loads(a.fiche.read_text(encoding="utf-8"))
    cameras = {n: d for n, d in fiche["cameras"].items() if not a.photos or n in a.photos}
    importee = a.sans_import
    faites = []
    for nom, d in cameras.items():
        debut = time.time()
        trajet = a.sortie / f"trajet-{nom}.json"
        trajet.write_text(json.dumps(trajet_de_la_photo(d, a.eclairage), ensure_ascii=False, indent=1), encoding="utf-8")
        suffixe = f"-{nom}"
        lancer([py, "outils/unreal/cinematique_unreal.py", paquet, a.nom, trajet, "--eclairages", a.eclairage, f"--suffixe={suffixe}"]
               + (["--sans-import"] if importee else []) + pour_le_film, journal, f"film depuis la place de {nom}")
        importee = True
        dossiers = [p for p in (STUDIO / "Paquets" / "rendus" / a.nom).glob(f"*{suffixe}") if p.stat().st_mtime >= debut - 1
                    and list(p.glob("image-*.png"))]
        if not dossiers:
            print(f"PLANTÉ : aucune image du film pour {nom} : voir {journal}", flush=True)
            return 1
        images = sorted(max(dossiers, key=lambda p: p.stat().st_mtime).glob("image-*.png"))
        from moteur.images import ecrire_image, lire_image

        x, y, w, h = json.loads(trajet.read_text(encoding="utf-8"))["rognage"]
        grande = lire_image(images[len(images) // 2])
        if grande is None or grande.shape[0] < y + h or grande.shape[1] < x + w:
            print(f"PLANTÉ : image du film de {nom} illisible ou trop petite pour le cadre de la photo : voir {journal}", flush=True)
            return 1
        ecrire_image(a.sortie / f"vue-{nom}.png", grande[y:y + h, x:x + w])
        faites.append(nom)
        print(f"{nom} : image du film prise en {time.time() - debut:.0f} s", flush=True)
    # la planche : la photo | l'image du film
    import cv2
    import numpy as np

    from moteur.images import ecrire_image, lire_image

    largeur, lignes = 760, []
    for nom in faites:
        photo = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
        film = lire_image(a.sortie / f"vue-{nom}.png")
        h = int(round(photo.shape[0] * largeur / photo.shape[1]))
        paire = np.concatenate([cv2.resize(photo, (largeur, h), interpolation=cv2.INTER_AREA), np.full((h, 10, 3), 255, np.uint8),
                                cv2.resize(film, (largeur, h), interpolation=cv2.INTER_AREA)], 1)
        bandeau = np.full((30, paire.shape[1], 3), 255, np.uint8)
        cv2.putText(bandeau, f"{a.nom}  {nom}", (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1, cv2.LINE_AA)
        lignes += [bandeau, paire]
    if lignes:
        titre = np.full((44, lignes[0].shape[1], 3), 255, np.uint8)
        cv2.putText(titre, "la photo du client (le modele)", (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(titre, "l'image du FILM Unreal, prise du meme endroit", (largeur + 16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
        ecrire_image(a.sortie / "film-contre-photos.jpg", np.concatenate([titre] + lignes, 0))
        print(f"planche : {a.sortie / 'film-contre-photos.jpg'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
