"""Cinématique d'un logement dans Unreal Engine 5, de bout en bout, en une commande (11/11/2026).

    python outils/unreal/cinematique_unreal.py <paquet> <nom> <trajet.json> [--eclairages tous|jour_voile,nuit…] [--sans-import]

<paquet> : dossier fait par outils/unreal/exporter_pour_unreal.py (maquette.gltf, scene-atelya.json, textures…) ; <nom> : nom court
sans accent (« app002 ») ; <trajet.json> : le trajet de caméra (même format que moteur/blender/video_trajet.py).
1. le paquet et le trajet sont copiés dans D:\\Atelya-Unreal\\Paquets\\<nom> (chemin sans accent : Unreal les gère mal) ;
2. import dans le niveau /Game/Logements/<nom>/Carte (moteur/unreal/importer_maquette.py), sauf --sans-import ;
3. pour chaque éclairage demandé (défaut : celui du trajet ; « tous » : les 5 de la fiche) :
   a. ciel, lumières, caméra, séquence, réglages de rendu (moteur/unreal/preparer_cinematique.py) ;
   b. ESSAIS du photographe (moteur/photographe.py, la règle de Blender) : petites images du film + masque des murs et
      plafonds ; exposition et balance des blancs corrigées d'un essai à l'autre jusqu'à la clarté visée (± 0,15 cran) ;
   c. rendu du film (Movie Render Queue, PNG), chronométré ; vidéo plan.mp4 ;
   d. CONTRÔLE du film (mêmes mesures sur les vraies images) ; une reprise s'il s'écarte encore.
Tout se fait sans écran ni clic, sans image de référence. Sorties : D:\\Atelya-Unreal\\Paquets\\rendus\\<nom>\\<éclairage>\\.
Le premier rendu d'un projet est long : Unreal y compile ses effets pour la carte graphique.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

RACINE_CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE_CODE))
from moteur import photographe  # noqa: E402

STUDIO = Path(r"D:\Atelya-Unreal")
PROJET = STUDIO / "AtelyaStudio" / "AtelyaStudio.uproject"
MOTEUR_UE = Path(r"D:\Epic Games\UE_5.8\Engine\Binaries\Win64")
SCRIPTS_UE = RACINE_CODE / "moteur" / "unreal"
PASSES_IMAGE, PASSE_MASQUE = ("FinalImage", "PathTracer"), "M_MasqueBlancs"  # Lumen, path tracer


NODE = STUDIO / "outils" / "node" / "node.exe"
EDITEUR_PYTHON = Path(__file__).resolve().parent / "editeur_python.js"


def editeur_ouvert() -> bool:
    """L'éditeur Unreal est-il ouvert sur le studio (fenêtre, pas un rendu « -game » ni une ligne de commande) ?"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | ForEach-Object { $_.CommandLine }"],
                       capture_output=True, text=True, errors="replace")
    return any("AtelyaStudio" in l and "-game" not in l.lower() and "-run=" not in l.lower() for l in r.stdout.splitlines())


def _python_unreal(script: Path, *arguments: str) -> None:
    """Lance un script Python dans Unreal ; s'arrête net (« PLANTÉ ») si le script échoue. Éditeur ouvert (NT regarde) : le
    script tourne DANS l'éditeur (outils/unreal/editeur_python.js), qui tient les fichiers du projet ; sinon : sans écran."""
    copie = PROJET.parent / "Scripts" / script.name
    copie.parent.mkdir(exist_ok=True)
    shutil.copy2(script, copie)
    if editeur_ouvert():
        r = subprocess.run([str(NODE), str(EDITEUR_PYTHON), str(copie), *arguments], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        journal = r.stdout + r.stderr
    else:
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


def rendre(nom: str, reglage: str = "Rendu") -> float:
    """Rendu Movie Render Queue de la séquence avec le réglage « Rendu » (le film) ou « Essai » ; renvoie la durée en s."""
    racine = f"/Game/Logements/{nom}"
    debut = time.time()
    r = subprocess.run([str(MOTEUR_UE / "UnrealEditor.exe"), str(PROJET), f"{racine}/Carte", "-game",
                        f"-LevelSequence={racine}/Plan", f"-MoviePipelineConfig={racine}/{reglage}", "-windowed",
                        "-resx=1280", "-resy=720", "-RenderOffscreen", "-NoSplash", "-NoLoadingScreen", "-unattended",
                        f"-log={reglage}.log"])
    if r.returncode != 0:
        sys.exit(f"PLANTÉ : rendu Unreal {reglage} (code {r.returncode}) ; journal "
                 f"{PROJET.parent / 'Saved' / 'Logs' / (reglage + '.log')}")
    return time.time() - debut


def video(dossier: Path, ips: int) -> Path:
    images = sorted(dossier.glob("image-*.png"))
    if not images:
        sys.exit(f"PLANTÉ : aucune image dans {dossier}")
    h, w = cv2.imdecode(np.fromfile(str(images[0]), dtype="uint8"), cv2.IMREAD_COLOR).shape[:2]
    sortie = dossier / "plan.mp4"
    ecrivain = cv2.VideoWriter(str(sortie), cv2.VideoWriter_fourcc(*"mp4v"), ips, (w, h))
    for f in images:
        ecrivain.write(cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR))
    ecrivain.release()
    return sortie


def _lineaire(image):
    """Clarté « physique » (linéaire) d'une image 8 bits sRGB, pixel par pixel."""
    v = image.astype(float).mean(axis=2) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def ecart_d_exposition(dossier: Path, reference: Path, images=(1, 48, 96)) -> float:
    """POUR JUGER seulement (jamais pour régler) : de combien de crans le rendu est plus sombre (+) ou plus clair (-) que
    la référence (médiane des images 1, 48 et 96, en clarté linéaire)."""
    ecarts = []
    for f in images:
        u = cv2.imdecode(np.fromfile(str(dossier / f"image-{f:04d}.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
        r = cv2.imdecode(np.fromfile(str(reference / f"image-{f:04d}.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
        ecarts.append(float(np.log2(np.median(_lineaire(r)) / max(np.median(_lineaire(u)), 1e-6))))
    return float(np.median(ecarts))


def images_d_essai(dossier: Path) -> tuple[list[Path], list[Path]]:
    """Les paires (image, masque des murs et plafonds) d'un rendu d'essai, appariées par numéro d'image. Movie Render Queue
    nomme la passe du masque « FinalImage » (ou « PathTracer ») + nom du matériau (vu le 11/11/2026)."""
    images = {p.name.rsplit(".", 2)[-2]: p for passe in PASSES_IMAGE for p in dossier.glob(f"{passe}.*.png")}
    masques = {p.name.rsplit(".", 2)[-2]: p for p in dossier.glob(f"*{PASSE_MASQUE}.*.png")}
    communs = sorted(set(images) & set(masques))
    if not communs:
        sys.exit(f"PLANTÉ : aucune paire image + masque dans {dossier} ({sorted(p.name for p in dossier.glob('*'))[:6]})")
    return [images[k] for k in communs], [masques[k] for k in communs]


def un_eclairage(paquet: Path, nom: str, trajet: Path, ambiance: dict, moteur: str = "lumen",
                 echantillons: int | None = None, intensite_max: float | None = None, exposition_fixe: float | None = None,
                 force_ciel: float | None = None, suffixe: str = "", temporel: bool = False,
                 lampes_pieces: list[str] | None = None) -> dict:
    """Le photographe règle l'exposition et la balance sur de petits essais, puis le film est rendu et contrôlé."""
    ident = ambiance["id"]
    dossier = ident if moteur == "lumen" else f"{ident}-{moteur}" + (f"-{echantillons}" if echantillons else "")
    dossier += (f"-max{intensite_max:g}" if intensite_max is not None else "") + suffixe
    sortie = STUDIO / "Paquets" / "rendus" / nom / dossier
    essai = sortie / "essai"
    print(f"== {ambiance.get('nom', ident)}")
    debut = time.time()
    clarte = photographe.clarte_visee(ambiance)
    balance = float(ambiance.get("balance", photographe.FORCE_BALANCE))
    reglage = sortie.parent / f"reglage-{dossier}.json"
    reglage.parent.mkdir(parents=True, exist_ok=True)

    def preparer(biais, gain):
        reglage.write_text(json.dumps({"eclairage": ident, "exposition": biais, "gain": list(gain), "moteur": moteur,
                                      "dossier": dossier, **({"echantillons": echantillons} if echantillons else {}),
                                      **({"intensite_max": intensite_max} if intensite_max is not None else {}),
                                      **({"force_ciel": force_ciel} if force_ciel is not None else {}),
                                      "debruiteur_temporel": temporel,
                                      **({"lampes_pieces": lampes_pieces} if lampes_pieces else {})}, indent=1), encoding="utf-8")
        _python_unreal(SCRIPTS_UE / "preparer_cinematique.py", paquet.as_posix(), nom, trajet.as_posix(), reglage.as_posix())

    # a-b. ESSAIS : petites images du film, mesurées ; exposition corrigée (pente apprise) jusqu'à tomber juste.
    biais, gain, essais = photographe.PREMIER_ESSAI, [1.0, 1.0, 1.0], []
    if exposition_fixe is not None:  # mesures de calage (pas un film) : exposition imposée, ni essais ni contrôle
        preparer(exposition_fixe, gain)
        for ancienne in sortie.glob("image-*.png"):
            ancienne.unlink()
        duree = rendre(nom, "Rendu")
        print(f"  rendu à exposition imposée {exposition_fixe:+.2f} en {duree:.0f} s : {sortie}")
        return {"eclairage": ident, "dossier": str(sortie), "exposition_fixe": exposition_fixe, "rendu_s": round(duree, 1)}
    for k in range(photographe.ESSAIS_MAX):
        preparer(biais, gain)
        if essai.exists():
            shutil.rmtree(essai)
        duree_essai = rendre(nom, "Essai")
        images, masques = images_d_essai(essai)
        mesure = photographe.mesurer(images, masques, clarte, balance, gain)
        essais.append({"exposition_unreal": round(biais, 3), "correction": mesure["correction"], "gain": gain,
                       "duree_s": round(duree_essai, 1)})
        print(f"  essai {k + 1} : exposition Unreal {biais:+.2f} : murs à {mesure['correction']:+.2f} cran de la clarté visée "
              f"({len(images)} images, {duree_essai:.0f} s)")
        gain = mesure["gain"]  # la balance mesurée sur cet essai (gain appliqué retiré) sert à l'essai suivant et au film
        if abs(mesure["correction"]) <= photographe.TOLERANCE:
            break
        biais = photographe.prochaine_exposition([(e["exposition_unreal"], e["correction"]) for e in essais])
    else:
        print(f"  ATTENTION : {photographe.ESSAIS_MAX} essais sans tomber juste ; film à l'exposition {biais:+.2f}")
    # le reste de correction du dernier essai, et l'écart régulier essai → film
    biais = essais[-1]["exposition_unreal"] + essais[-1]["correction"] + photographe.ESSAI_VERS_FILM

    # c-d. Le FILM, puis son CONTRÔLE sur les vraies images (une reprise au plus).
    controles = []
    for tour in range(photographe.FILMS_MAX):
        preparer(biais, gain)
        for ancienne in sortie.glob("image-*.png"):
            ancienne.unlink()
        duree = rendre(nom, "Rendu")
        pngs = [sortie / f"image-{m.name.rsplit('.', 2)[-2]}.png" for m in masques]
        presents = [(p, m) for p, m in zip(pngs, masques) if p.is_file()]
        controle = photographe.mesurer([p for p, _ in presents], [m for _, m in presents], clarte, balance, gain)
        controles.append({"exposition_unreal": round(biais, 3), "correction": controle["correction"],
                          "murs_lineaire": controle["murs_lineaire"], "gain": gain})
        print(f"  film{' (reprise)' if tour else ''} : murs à {controle['correction']:+.2f} cran de la clarté visée")
        if abs(controle["correction"]) <= photographe.TOLERANCE:
            break
        historique = [(e["exposition_unreal"], e["correction"]) for e in essais + controles]
        biais = photographe.prochaine_exposition(historique)
    else:
        print(f"  ATTENTION : film encore à {controles[-1]['correction']:+.2f} cran de la clarté visée (gardé, à regarder)")
    n = len(list(sortie.glob("image-*.png")))
    film = video(sortie, int(json.loads(trajet.read_text(encoding="utf-8")).get("ips", 24)))
    bilan = {"eclairage": ident, "moteur": moteur, "images": n, "rendu_s": round(duree, 1), "essais": essais, "controles": controles,
             "total_s": round(time.time() - debut, 1), "video": str(film)}
    (sortie / "rendu-unreal.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {n} images en {duree / 60:.1f} min ({duree / max(n, 1):.2f} s par image, chauffe et chargement compris) ; "
          f"tout l'éclairage : {bilan['total_s'] / 60:.1f} min ; vidéo {film}")
    return bilan


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paquet")
    p.add_argument("nom")
    p.add_argument("trajet")
    p.add_argument("--eclairages", default="", help="« tous », ou des identifiants séparés par des virgules (défaut : celui du "
                                                    "trajet)")
    p.add_argument("--sans-import", action="store_true", help="garder la maquette déjà importée")
    p.add_argument("--moteur", default="lumen_max", choices=["lumen", "lumen_max", "path_tracer"],
                   help="calcul de la lumière : lumen (temps réel), lumen_max, path_tracer (comme Cycles, plus lent)")
    p.add_argument("--echantillons", type=int, help="path tracer : rayons par pixel du film (défaut 256)")
    p.add_argument("--intensite-max", type=float, help="path tracer : garde-fou des chemins trop forts (défaut d'Unreal)")
    p.add_argument("--exposition-fixe", type=float, help="mesures de calage : exposition Unreal imposée, sans essais")
    p.add_argument("--force-ciel", type=float, help="force de la lumière du ciel (Sky Light), 1 par défaut")
    p.add_argument("--suffixe", default="", help="ajouté au nom du dossier de sortie")
    p.add_argument("--temporel", action="store_true", help="path tracer : débruiteur temporel (NFOR) en plus")
    a = p.parse_args()
    paquet = STUDIO / "Paquets" / a.nom
    if Path(a.paquet).resolve() != paquet.resolve():
        if paquet.exists():
            shutil.rmtree(paquet)
        shutil.copytree(a.paquet, paquet)
    trajet = paquet / "trajet.json"
    if Path(a.trajet).resolve() != trajet.resolve():
        shutil.copy2(a.trajet, trajet)
    fiche = json.loads((paquet / "scene-atelya.json").read_text(encoding="utf-8"))
    ambiances = fiche.get("eclairages", [])
    if a.eclairages == "tous":
        choisies = ambiances
    else:
        voulus = a.eclairages.split(",") if a.eclairages else [json.loads(trajet.read_text(encoding="utf-8")).get("scene", "")]
        choisies = [x for x in ambiances if x.get("id") in voulus or x.get("nom") in voulus]
    if not choisies:
        sys.exit(f"PLANTÉ : aucun éclairage reconnu ({a.eclairages or 'celui du trajet'})")
    if not a.sans_import:
        print("1. Import de la maquette dans Unreal")
        _python_unreal(SCRIPTS_UE / "importer_maquette.py", paquet.as_posix(), a.nom)
    bilans = [un_eclairage(paquet, a.nom, trajet, x, a.moteur, a.echantillons, a.intensite_max, a.exposition_fixe, a.force_ciel,
                           a.suffixe, a.temporel) for x in choisies]
    (STUDIO / "Paquets" / "rendus" / a.nom / "bilan.json").write_text(json.dumps(bilans, indent=1, ensure_ascii=False),
                                                                      encoding="utf-8")


if __name__ == "__main__":
    main()
