"""Script lu par Blender : fait une image par caméra de la maquette.

Le « rendu », c'est le calcul de l'image : Blender suit le trajet de la
lumière (moteur Cycles), depuis le soleil et les lampes jusqu'à la caméra.
Plus on suit de rayons (les « échantillons »), plus l'image est propre ;
un « débruiteur » nettoie ensuite le grain qui reste.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup maquette.blend --python rendre.py -- dossier_images echantillons pourcentage
"""

import sys
import time
from pathlib import Path

import bpy


def main() -> None:
    dossier, echantillons, pourcentage = sys.argv[sys.argv.index("--") + 1:][:3]
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(echantillons)
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = int(pourcentage)
    scene.render.image_settings.file_format = "PNG"
    scene.cycles.sample_clamp_indirect = 10.0  # B2-4 : pas de points blancs isolés (« lucioles ») dans les reflets
    print(f"Calcul sur : {choisir_processeur(scene)}")

    cameras = sorted((o for o in scene.objects if o.type == "CAMERA"), key=lambda o: o.name)
    for camera in cameras:
        debut = time.time()
        scene.camera = camera
        masquer = set(camera.get("masquer", []))
        for collection in scene.collection.children:
            collection.hide_render = collection.name in masquer
        largeur, hauteur = camera.get("format", (1600, 1000))
        scene.render.resolution_x, scene.render.resolution_y = largeur, hauteur
        nom = camera.name.removeprefix("Vue_")
        if scene.get("jour"):
            exposition, blanc = reglage_de_photographe(scene, Path(dossier))
            scene.view_settings.exposure = exposition
            scene.view_settings.use_curve_mapping = True
            courbes = scene.view_settings.curve_mapping
            courbes.white_level = blanc  # balance des blancs : la couleur des murs devient le blanc
            courbes.update()
            print(f"Réglage {nom} : exposition {exposition:+.2f}, blanc {tuple(round(v, 3) for v in blanc)}")
        scene.render.filepath = str(Path(dossier).resolve() / f"vue-{nom}.png")
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
        print(f"Image {scene.render.filepath} en {time.time() - debut:.0f} s")

    for collection in scene.collection.children:
        collection.hide_render = False


CLARTE_MURS = 0.55  # clarté (linéaire) visée pour les murs et plafonds blancs : une pièce claire, comme sur une photo d'annonce
EXPOSITION_MIN, EXPOSITION_MAX = -12.0, 6.0
FORCE_BALANCE = 0.7  # la balance des blancs corrige 70 % de la teinte des murs : il reste un peu de la chaleur de la lumière


def reglage_de_photographe(scene, dossier: Path) -> tuple[float, tuple[float, float, float]]:
    """B2-4 : comme un photographe, on fait d'abord une petite photo d'essai et on y regarde les murs et plafonds blancs.

    - l'EXPOSITION : on règle la clarté pour que ces murs aient la clarté voulue (la médiane : une tache de soleil ou une
      fenêtre ne compte pas plus qu'un coin d'ombre) ;
    - la BALANCE DES BLANCS : la lumière qui rebondit sur un parquet orangé teinte les murs en rose ; on mesure leur couleur
      et on la ramène presque au blanc, sans toucher au reste (le parquet garde sa couleur, à peu près).
    Pour ne mesurer que les murs et plafonds, tout le reste est « découpé » de la photo d'essai (il éclaire toujours)."""
    import numpy as np

    reglages = (scene.render.resolution_percentage, scene.cycles.samples, scene.cycles.use_denoising,
                scene.render.image_settings.file_format, scene.view_settings.exposure, scene.render.film_transparent)
    blancs = {"Murs", "Plafonds"}
    decoupes = [o for c in scene.collection.children if c.name not in blancs for o in c.objects if o.type == "MESH"]
    for o in decoupes:
        o.is_holdout = True
    scene.render.film_transparent = True  # le fond et les objets découpés ne comptent pas
    scene.render.resolution_percentage = max(5, reglages[0] // 5)
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False
    scene.render.image_settings.file_format = "OPEN_EXR"  # valeurs brutes, avant tout réglage de couleur
    scene.view_settings.exposure = 0.0
    essai = dossier.resolve() / "_essai_exposition.exr"
    scene.render.filepath = str(essai)
    try:
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(str(essai))
        pixels = np.array(image.pixels[:], dtype=float).reshape(-1, 4)
        bpy.data.images.remove(image)
    finally:
        essai.unlink(missing_ok=True)
        for o in decoupes:
            o.is_holdout = False
        (scene.render.resolution_percentage, scene.cycles.samples, scene.cycles.use_denoising,
         scene.render.image_settings.file_format, _, scene.render.film_transparent) = reglages
    murs = pixels[pixels[:, 3] > 0.5, :3]
    poids = np.array([0.2126, 0.7152, 0.0722])
    if len(murs) < 20:
        return 0.0, (1.0, 1.0, 1.0)
    luminance = murs @ poids
    milieu = float(np.median(luminance))
    exposition = float(np.clip(np.log2(CLARTE_MURS / max(milieu, 1e-9)), EXPOSITION_MIN, EXPOSITION_MAX))
    # couleur des murs « ordinaires » (entre le 20e et le 90e centile de clarté : ni coins sombres ni taches de soleil)
    bas, haut = np.percentile(luminance, [20, 90])
    ordinaires = murs[(luminance >= bas) & (luminance <= haut)]
    couleur = ordinaires.mean(axis=0) if len(ordinaires) else murs.mean(axis=0)
    teinte = couleur / max(float(couleur @ poids), 1e-9)  # (1, 1, 1) pour des murs parfaitement blancs
    blanc = 1 + FORCE_BALANCE * (teinte - 1)
    blanc = blanc / float(blanc @ poids)
    return exposition, tuple(float(v) for v in blanc)


def choisir_processeur(scene) -> str:
    """Utilise la carte graphique si Blender en trouve une (Metal sur Mac), sinon le processeur."""
    reglages = bpy.context.preferences.addons["cycles"].preferences
    # CUDA avant OptiX : sur le PC (pilote NVIDIA 555.97), le module OptiX de Blender 5.2 ne se charge pas et ferait tout échouer.
    for type_ in ("METAL", "CUDA", "OPTIX", "HIP", "ONEAPI"):
        try:
            reglages.compute_device_type = type_
        except TypeError:
            continue  # ce type n'existe pas sur cette machine
        reglages.get_devices()
        cartes = [d for d in reglages.devices if d.type == type_]
        if cartes:
            for d in reglages.devices:
                d.use = d.type == type_
            scene.cycles.device = "GPU"
            return f"carte graphique ({type_} : {', '.join(d.name for d in cartes)})"
    scene.cycles.device = "CPU"
    return "processeur"


main()
