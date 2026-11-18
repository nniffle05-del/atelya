r"""POINT 2 (18/11/2026) : un petit plan EN MOUVEMENT tourné depuis la place d'une photo du client, pour juger un essai de
lumière quand la caméra bouge (CLAUDE.md § 0 : le produit est le film, pas une image à l'arrêt).

    ..\atelya\.venv\Scripts\python.exe pc\verification\panoramique_lumiere.py <paquet> <nom Unreal> <fiche des caméras> <photo>
        <sortie> [--tour 60] [--avance 0.4] [--secondes 6] [options du film, ex. --reglage ciel_couvert=uni]

La caméra part de la place de l'appareil de la photo, avance de <avance> mètres dans le sens du regard et tourne de <tour>
degrés en tout (moitié à gauche, moitié à droite du regard de la photo), à hauteur d'appareil, à l'horizontale. Pourquoi ce
plan et pas le vol du film entier : il reste dans une pièce que la photo montre (on sait à quoi comparer) et il fait défiler
les reflets du sol et les murs sous plusieurs angles en peu d'images. La maquette doit être DÉJÀ importée dans Unreal (éditeur
fermé). Les images sont copiées dans <sortie> (image-0001.png…), prêtes pour pc/verification/film_cote_a_cote.py.
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
sys.path.insert(0, str(RACINE / "outils" / "unreal"))

from moteur.juge_lumiere import cadre_du_film  # noqa: E402
from vues_photos_unreal import SCENES, STUDIO  # noqa: E402


def trajet_du_panoramique(d: dict, eclairage: str, tour: float, avance: float, secondes: float, ips: int = 24) -> dict:
    """Cinq points à pas égaux (en distance et en angle) : le film interpole entre eux."""
    c = d["camera"]
    cap = float(c["cap"])
    a = math.radians(cap)
    points = []
    for k in range(5):
        t = k / 4
        points.append([float(c["x"]) + avance * t * math.cos(a), float(c["y"]) + avance * t * math.sin(a), float(c["z"]),
                       cap + tour * (0.5 - t), 0.0])
    return {"points": points, "images": int(round(secondes * ips)), "ips": ips, "focale_mm": cadre_du_film(d)["focale_mm"],
            "format": [1280, 720], "scene": SCENES.get(eclairage, eclairage)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paquet", type=Path)
    ap.add_argument("nom")
    ap.add_argument("fiche", type=Path)
    ap.add_argument("photo")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--eclairage", default="jour_voile")
    ap.add_argument("--tour", type=float, default=60.0)
    ap.add_argument("--avance", type=float, default=0.4)
    ap.add_argument("--secondes", type=float, default=6.0)
    a, pour_le_film = ap.parse_known_args()
    fiche = json.loads(a.fiche.read_text(encoding="utf-8"))
    if a.photo not in fiche["cameras"]:
        print(f"PLANTÉ : pas de caméra pour {a.photo} dans {a.fiche}", flush=True)
        return 1
    a.sortie.mkdir(parents=True, exist_ok=True)
    trajet = a.sortie / "trajet.json"
    trajet.write_text(json.dumps(trajet_du_panoramique(fiche["cameras"][a.photo], a.eclairage, a.tour, a.avance, a.secondes),
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    suffixe = f"-pano-{a.photo}"
    debut = time.time()
    with open(a.sortie / "journal.txt", "w", encoding="utf-8") as journal:
        r = subprocess.run([sys.executable, "outils/unreal/cinematique_unreal.py", str(a.paquet), a.nom, str(trajet), "--eclairages",
                            a.eclairage, f"--suffixe={suffixe}", "--sans-import"] + pour_le_film, cwd=RACINE, stdout=journal,
                           stderr=subprocess.STDOUT, text=True, errors="replace")
    if r.returncode != 0:
        print(f"PLANTÉ : film depuis la place de {a.photo} (code {r.returncode}) : voir {a.sortie / 'journal.txt'}", flush=True)
        return 1
    dossiers = [p for p in (STUDIO / "Paquets" / "rendus" / a.nom).glob(f"*{suffixe}") if p.stat().st_mtime >= debut - 1
                and list(p.glob("image-*.png"))]
    if not dossiers:
        print(f"PLANTÉ : aucune image du film pour {a.photo} : voir {a.sortie / 'journal.txt'}", flush=True)
        return 1
    for ancienne in a.sortie.glob("image-*.png"):
        ancienne.unlink()
    images = sorted(max(dossiers, key=lambda p: p.stat().st_mtime).glob("image-*.png"))
    for image in images:
        shutil.copy2(image, a.sortie / image.name)
    print(f"{a.nom} {a.photo} : {len(images)} images en {time.time() - debut:.0f} s dans {a.sortie}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
