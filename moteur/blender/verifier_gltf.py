"""Script lu par Blender : vérifie que l'export glTF garde la maquette d'Atelya intacte (11/11/2026).

    blender -b maquette.blend --python verifier_gltf.py -- maquette.gltf dossier_images [echantillons] [pourcentage] [scène]

Pourquoi : avant d'ouvrir le fichier dans Unreal, on s'assure que ce qui part de Blender est juste. Méthode « toutes choses
égales » : dans la maquette d'origine, on fait les images de ses caméras ; puis on ENLÈVE toute la maquette (murs, sols,
meubles…) en gardant exactement la même lumière, le même ciel et les mêmes caméras, on la remplace par le fichier glTF relu, et
on refait les mêmes images, avec la même exposition. Toute différence vient donc de l'export.
Écrit : vue-<nom>-origine.png, vue-<nom>-gltf.png et verification-gltf.json (temps, objets relus) dans le dossier.
"""
import collections
import json
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rendre import appliquer_reglage, choisir_processeur, reglage_de_photographe  # noqa: E402


def _images(scene, cameras, dossier, suffixe, reglages):
    for camera in cameras:
        nom = camera.name.removeprefix("Vue_")
        scene.camera = camera
        masquer = set(camera.get("masquer", []))
        for collection in scene.collection.children:
            collection.hide_render = collection.name in masquer
        largeur, hauteur = camera.get("format", (1600, 1000))
        scene.render.resolution_x, scene.render.resolution_y = largeur, hauteur
        if nom not in reglages:
            reglages[nom] = reglage_de_photographe(scene, dossier) if scene.get("jour") else (0.0, (1.0, 1.0, 1.0))
        appliquer_reglage(scene, *reglages[nom])
        scene.render.filepath = str(dossier / f"vue-{nom}-{suffixe}.png")
        debut = time.time()
        bpy.ops.render.render(write_still=True, scene=scene.name)
        print(f"Image {nom} ({suffixe}) en {time.time() - debut:.0f} s", flush=True)
    for collection in scene.collection.children:
        collection.hide_render = False


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    gltf, dossier = Path(args[0]).resolve(), Path(args[1]).resolve()
    echantillons = int(args[2]) if len(args) > 2 else 64
    pourcentage = int(args[3]) if len(args) > 3 else 50
    dossier.mkdir(parents=True, exist_ok=True)
    scene = bpy.data.scenes[args[4]] if len(args) > 4 else sorted(bpy.data.scenes, key=lambda s: s.name)[0]
    scene.render.engine = "CYCLES"
    scene.cycles.samples = echantillons
    scene.cycles.use_denoising = True
    scene.cycles.sample_clamp_indirect = 10.0
    scene.render.resolution_percentage = pourcentage
    scene.render.image_settings.file_format = "PNG"
    print("Calcul sur :", choisir_processeur(scene))
    cameras = sorted((o for o in scene.objects if o.type == "CAMERA"), key=lambda o: o.name)
    reglages = {}
    _images(scene, cameras, dossier, "origine", reglages)

    # La maquette enlevée (lampes, portails et caméras gardés), puis remplacée par le glTF relu.
    rangement = {}  # nom d'objet → collection de 1er niveau d'origine (pour masquer les plafonds de la vue de dessus)
    for collection in scene.collection.children:
        for o in collection.all_objects:
            rangement.setdefault(o.name, collection.name)
    enleves = collections.Counter()
    for o in list(scene.objects):
        if o.type not in {"LIGHT", "CAMERA", "LIGHT_PROBE"}:
            enleves[o.type] += 1
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    accueil = bpy.data.collections.new("Relu du glTF")
    scene.collection.children.link(accueil)
    debut = time.time()
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0], collection=accueil):
        bpy.ops.import_scene.gltf(filepath=str(gltf))
    duree_import = time.time() - debut
    relus = [o for o in accueil.all_objects]
    for o in relus:  # chaque objet relu retrouve sa collection d'origine (Plafonds, Murs…) s'il en avait une
        nom = rangement.get(o.name)
        if nom and nom in scene.collection.children and o.parent is None:
            cible = scene.collection.children[nom]
            cible.objects.link(o)
            accueil.objects.unlink(o)
            for enfant in o.children_recursive:
                for c in list(enfant.users_collection):
                    c.objects.unlink(enfant)
                cible.objects.link(enfant)
    _images(scene, cameras, dossier, "gltf", reglages)
    bilan = {"gltf": str(gltf), "scene": scene.name, "echantillons": echantillons, "pourcentage": pourcentage,
             "enleves": dict(enleves), "relus": dict(collections.Counter(o.type for o in relus)),
             "import_s": round(duree_import, 1),
             "reglages": {k: {"exposition": v[0], "blanc": list(v[1])} for k, v in reglages.items()}}
    (dossier / "verification-gltf.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Vérification :", json.dumps(bilan, ensure_ascii=False))


if __name__ == "__main__":
    main()
