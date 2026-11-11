"""Cinématique d'un logement dans Unreal Engine 5, de bout en bout, en une commande (11/11/2026).

    python outils/unreal/cinematique_unreal.py <paquet> <nom> <trajet.json> [--exposition 0] [--sans-import] [--images 1,48,96]

<paquet> : dossier fait par outils/unreal/exporter_pour_unreal.py (maquette.gltf, scene-atelya.json, textures…) ; <nom> : nom court
sans accent (« app002 ») ; <trajet.json> : le trajet de caméra (même format que moteur/blender/video_trajet.py).
1. le paquet et le trajet sont copiés dans D:\\Atelya-Unreal\\Paquets\\<nom> (chemin sans accent : Unreal les gère mal) ;
2. import dans le niveau /Game/Logements/<nom>/Carte (moteur/unreal/importer_maquette.py), sauf --sans-import ;
3. ciel, lumière, réglage d'image, caméra, séquence et réglage du rendu (moteur/unreal/preparer_cinematique.py) ;
4. rendu du film par Movie Render Queue (images PNG), chronométré ; puis la vidéo plan.mp4.
Tout se fait sans écran ni clic. Le premier rendu d'un projet est long : Unreal y compile ses effets pour la carte graphique.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2

RACINE_CODE = Path(__file__).resolve().parents[2]
STUDIO = Path(r"D:\Atelya-Unreal")
PROJET = STUDIO / "AtelyaStudio" / "AtelyaStudio.uproject"
MOTEUR_UE = Path(r"D:\Epic Games\UE_5.8\Engine\Binaries\Win64")
SCRIPTS_UE = RACINE_CODE / "moteur" / "unreal"


def _python_unreal(script: Path, *arguments: str) -> None:
    """Lance un script Python dans Unreal, sans écran ; s'arrête net (« PLANTÉ ») si le script échoue."""
    copie = PROJET.parent / "Scripts" / script.name
    copie.parent.mkdir(exist_ok=True)
    shutil.copy2(script, copie)
    ligne = " ".join([copie.as_posix(), *arguments])
    r = subprocess.run([str(MOTEUR_UE / "UnrealEditor-Cmd.exe"), str(PROJET), "-run=pythonscript", f"-script={ligne}",
                        "-unattended", "-nop4", "-nosplash", "-nullrhi"], capture_output=True, text=True, errors="replace")
    journal = (PROJET.parent / "Saved" / "Logs" / "AtelyaStudio.log").read_text(encoding="utf-8", errors="replace")
    erreurs = [l for l in journal.splitlines() if "LogPython: Error" in l]
    for l in journal.splitlines():
        if "ATELYA" in l:
            print("   ", l.split("LogPython: ", 1)[-1][:300])
    if r.returncode != 0 or erreurs:
        sys.exit(f"PLANTÉ : {script.name} (code {r.returncode})\n" + "\n".join(erreurs[-12:]))


def rendre(nom: str) -> float:
    """Le film par Movie Render Queue ; renvoie la durée en secondes."""
    racine = f"/Game/Logements/{nom}"
    debut = time.time()
    r = subprocess.run([str(MOTEUR_UE / "UnrealEditor.exe"), str(PROJET), f"{racine}/Carte", "-game",
                        f"-LevelSequence={racine}/Plan", f"-MoviePipelineConfig={racine}/Rendu", "-windowed",
                        "-resx=1280", "-resy=720", "-RenderOffscreen", "-NoSplash", "-NoLoadingScreen", "-unattended",
                        "-log=Rendu.log"])
    if r.returncode != 0:
        sys.exit(f"PLANTÉ : rendu Unreal (code {r.returncode}) ; journal {PROJET.parent / 'Saved' / 'Logs' / 'Rendu.log'}")
    return time.time() - debut


def video(dossier: Path, ips: int) -> Path:
    images = sorted(dossier.glob("image-*.png"))
    if not images:
        sys.exit(f"PLANTÉ : aucune image dans {dossier}")
    h, w = cv2.imdecode(__import__("numpy").fromfile(str(images[0]), dtype="uint8"), cv2.IMREAD_COLOR).shape[:2]
    sortie = dossier / "plan.mp4"
    ecrivain = cv2.VideoWriter(str(sortie), cv2.VideoWriter_fourcc(*"mp4v"), ips, (w, h))
    import numpy as np
    for f in images:
        ecrivain.write(cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR))
    ecrivain.release()
    return sortie


def _lineaire(image):
    """Clarté « physique » (linéaire) d'une image 8 bits sRGB, pixel par pixel."""
    import numpy as np
    v = image.astype(float).mean(axis=2) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def ecart_d_exposition(dossier: Path, reference: Path, images=(1, 48, 96)) -> float:
    """De combien de crans éclaircir (+) ou assombrir (-) le rendu pour qu'il ait la clarté de la référence (médiane des
    images 1, 48 et 96, en clarté linéaire)."""
    import numpy as np
    ecarts = []
    for f in images:
        u = cv2.imdecode(np.fromfile(str(dossier / f"image-{f:04d}.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
        r = cv2.imdecode(np.fromfile(str(reference / f"image-{f:04d}.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
        ecarts.append(float(np.log2(np.median(_lineaire(r)) / max(np.median(_lineaire(u)), 1e-6))))
    return float(np.median(ecarts))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paquet")
    p.add_argument("nom")
    p.add_argument("trajet")
    p.add_argument("--exposition", type=float, default=0.0, help="exposition fixe, en crans (+1 = deux fois plus clair)")
    p.add_argument("--sans-import", action="store_true", help="garder la maquette déjà importée")
    p.add_argument("--reference", help="dossier d'images de référence (même trajet, ex. Cycles) : l'exposition est calée dessus")
    p.add_argument("--tours", type=int, default=2, help="nombre de rendus de calage de l'exposition (avec --reference)")
    a = p.parse_args()
    paquet = STUDIO / "Paquets" / a.nom
    if Path(a.paquet).resolve() != paquet.resolve():
        if paquet.exists():
            shutil.rmtree(paquet)
        shutil.copytree(a.paquet, paquet)
    trajet = paquet / "trajet.json"
    shutil.copy2(a.trajet, trajet)
    debut = time.time()
    if not a.sans_import:
        print("1. Import de la maquette dans Unreal")
        _python_unreal(SCRIPTS_UE / "importer_maquette.py", paquet.as_posix(), a.nom)
    sortie = STUDIO / "Paquets" / "rendus" / a.nom
    exposition = a.exposition
    tours = (a.tours + 1) if a.reference else 1
    for tour in range(tours):
        print(f"2. Ciel, lumière, caméra, séquence, réglage du rendu (exposition {exposition:+.2f})")
        _python_unreal(SCRIPTS_UE / "preparer_cinematique.py", paquet.as_posix(), a.nom, trajet.as_posix(), str(exposition))
        for ancienne in sortie.glob("image-*.png"):
            ancienne.unlink()
        print("3. Rendu du film (Movie Render Queue)")
        duree = rendre(a.nom)
        n = len(list(sortie.glob("image-*.png")))
        print(f"   {n} images en {duree / 60:.1f} min ({duree / max(n, 1):.1f} s par image, chauffe et chargement compris)")
        if not a.reference or tour == tours - 1:
            break
        ecart = ecart_d_exposition(sortie, Path(a.reference))
        print(f"   Calage sur la référence : {ecart:+.2f} cran(s)")
        if abs(ecart) < 0.1:
            break
        exposition += ecart
    a.exposition = exposition
    film = video(sortie, int(json.loads(trajet.read_text(encoding="utf-8")).get("ips", 24)))
    (sortie / "rendu-unreal.json").write_text(json.dumps({"images": n, "rendu_s": round(duree, 1), "total_s": round(time.time() - debut, 1),
                                                         "exposition": a.exposition}, indent=1), encoding="utf-8")
    print(f"4. Vidéo : {film}")


if __name__ == "__main__":
    main()
