r"""LA COLLECTION DE RIDEAUX D'ATELYA : de vrais plis, calculés une fois par Blender (19/11/2026).

    ..\atelya\blender-5.2.2\blender.exe --background --python outils\bibliotheque\fabriquer_rideaux.py -- <sortie> [sorte …] [--apercu]

Pourquoi : les rideaux de la maquette étaient une feuille ondulée régulière (une tôle). NT, 19/11/2026 : « comment avoir de
beaux rideaux fidèles ? je ne les trouve pas fous ». Un vrai rideau est froncé en haut, et ses plis s'ouvrent et se dérèglent
en descendant. On ne le dessine pas : on le CALCULE. Une bande de tissu est accrochée à sa tringle, froncée, et Blender la
laisse tomber (simulation de tissu : poids, raideur, le tissu ne se traverse pas lui-même). La forme au repos est gardée.

Trois sortes (SORTES) : « voilage » (tissu fin, petits plis serrés), « rideau » (tissu épais tiré devant la fenêtre),
« rideau_ouvert » (le même, ramassé sur le côté). Chacune est une BANDE longue (LARGEUR_M de tringle) : la maquette y découpe la
largeur qu'il lui faut (moteur/blender/rideaux.py), le pas des plis reste le vrai.

Sortie : <sortie>/<sorte>.npz : « points » (lignes × colonnes × 3, mètres : x le long de la tringle, y = profondeur des plis
autour de 0, z de 0 en bas à HAUTEUR_M en haut), « tissu » (abscisse de chaque colonne sur le tissu À PLAT, en mètres : pour
poser un tissage sans l'étirer). --apercu : une image <sortie>/<sorte>.png (outil de travail, pas un juge).
Rien n'est téléchargé : seul Blender travaille. La collection rangée dans moteur/modeles/rideaux/ est celle du dépôt.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HAUTEUR_M = 2.6
# tringle : largeur de la bande ; ampleur : mètres de tissu par mètre de tringle ; pas : distance entre deux plis à la tringle ;
# maille : taille d'un carreau du tissu calculé (le long de la tringle à plat, en hauteur) ; masse (kg/m²) et raideurs de Blender
SORTES = {
    # (voilage : avec une flexion de 0,03 le tissu sortait FROISSÉ partout, comme chiffonné, essai du 19/11/2026)
    "voilage": {"tringle": 4.0, "ampleur": 2.0, "pas": 0.075, "maille": (0.012, 0.035), "masse": 0.08, "tension": 12.0,
                "flexion": 0.35, "desordre": 0.008},
    "rideau": {"tringle": 4.0, "ampleur": 2.0, "pas": 0.13, "maille": (0.016, 0.04), "masse": 0.35, "tension": 20.0,
               "flexion": 0.6, "desordre": 0.02},
    "rideau_ouvert": {"tringle": 1.6, "ampleur": 3.2, "pas": 0.085, "maille": (0.014, 0.04), "masse": 0.35, "tension": 20.0,
                      "flexion": 0.6, "desordre": 0.012},
}
IMAGES = 90  # durée du calcul (images de 1/24 s) : le tissu est au repos bien avant


def amplitude_pour(ampleur: float, pas: float) -> float:
    """Profondeur A d'une ondulation y = A sin(2 pi x / pas) dont la longueur vaut `ampleur` fois sa largeur."""
    x = np.linspace(0.0, pas, 400)
    bas, haut = 0.0, 1.0
    for _ in range(40):
        a = (bas + haut) / 2
        y = a * np.sin(2 * np.pi * x / pas)
        if np.hypot(np.diff(x), np.diff(y)).sum() / pas < ampleur:
            bas = a
        else:
            haut = a
    return (bas + haut) / 2


def bande(sorte: str, graine: int = 7):
    """Le tissu de départ : déjà froncé comme à la tringle (plis de profondeur un peu inégale), droit jusqu'en bas."""
    r = SORTES[sorte]
    rng = np.random.default_rng(graine)
    n_plis = max(2, int(round(r["tringle"] / r["pas"])))
    a = amplitude_pour(r["ampleur"], r["tringle"] / n_plis)
    # courbe de la tringle, très finement, puis colonnes à pas égal SUR LE TISSU (il n'est pas étiré)
    fin = np.linspace(0.0, r["tringle"], n_plis * 200 + 1)
    force = np.interp(fin, np.linspace(0, r["tringle"], n_plis + 1), 1.0 + 0.25 * rng.uniform(-1, 1, n_plis + 1))
    y = a * force * np.sin(2 * np.pi * fin * n_plis / r["tringle"])
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(fin), np.diff(y)))])
    colonnes = int(round(arc[-1] / r["maille"][0])) + 1
    s = np.linspace(0.0, arc[-1], colonnes)
    xs, ys = np.interp(s, arc, fin), np.interp(s, arc, y)
    lignes = int(round(HAUTEUR_M / r["maille"][1])) + 1
    zs = np.linspace(HAUTEUR_M, 0.0, lignes)  # ligne 0 = la tringle
    # un léger désordre qui grandit vers le bas : c'est lui que le calcul transforme en plis naturels
    lisse = np.cumsum(rng.normal(0, 1, colonnes))
    lisse = np.convolve(lisse - lisse.mean(), np.ones(25) / 25, mode="same")
    lisse /= max(float(np.abs(lisse).max()), 1e-6)
    P = np.zeros((lignes, colonnes, 3), np.float32)
    P[..., 0] = xs[None, :]
    P[..., 1] = ys[None, :] + r["desordre"] * lisse[None, :] * ((HAUTEUR_M - zs) / HAUTEUR_M)[:, None] ** 2
    P[..., 2] = zs[:, None]
    return P, s


def calculer(sorte: str):
    r = SORTES[sorte]
    P, s = bande(sorte)
    lignes, colonnes = P.shape[:2]
    faces = [(i * colonnes + j, i * colonnes + j + 1, (i + 1) * colonnes + j + 1, (i + 1) * colonnes + j)
             for i in range(lignes - 1) for j in range(colonnes - 1)]
    me = bpy.data.meshes.new(sorte)
    me.from_pydata(P.reshape(-1, 3).tolist(), [], faces)
    me.update()
    o = bpy.data.objects.new(sorte, me)
    bpy.context.scene.collection.objects.link(o)
    tringle = o.vertex_groups.new(name="tringle")
    tringle.add(list(range(colonnes)), 1.0, "REPLACE")
    m = o.modifiers.new("Tissu", "CLOTH")
    c = m.settings
    c.quality = 8
    c.mass = r["masse"] * r["maille"][0] * r["maille"][1]  # masse d'un point = masse au m² × surface d'une maille
    c.tension_stiffness = c.compression_stiffness = r["tension"]
    c.shear_stiffness = r["tension"] / 4
    c.bending_stiffness = r["flexion"]
    c.tension_damping = c.compression_damping = 5.0
    c.bending_damping = 0.5
    c.air_damping = 2.0
    c.vertex_group_mass = "tringle"
    m.collision_settings.use_self_collision = True
    m.collision_settings.self_distance_min = 0.004
    m.collision_settings.collision_quality = 3
    m.point_cache.frame_start, m.point_cache.frame_end = 1, IMAGES
    scene = bpy.context.scene
    for image in range(1, IMAGES + 1):
        scene.frame_set(image)
    bpy.context.view_layer.update()
    eo = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = np.array([v.co[:] for v in eo.data.vertices], np.float32).reshape(lignes, colonnes, 3)
    return o, points, s


def apercu(o, chemin: Path) -> None:
    """Une image du tissu au repos, de face un peu en biais (outil de travail)."""
    scene = bpy.context.scene
    for autre in list(scene.objects):
        if autre is not o and autre.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(autre)
    for p in o.data.polygons:
        p.use_smooth = True
    largeur = max(v.co.x for v in o.data.vertices)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    cam.location = (largeur / 2 + 1.2, -4.2, 1.5)
    cam.rotation_euler = (math.radians(88), 0.0, math.radians(14))
    cam.data.lens = 32
    scene.camera = cam
    soleil = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
    scene.collection.objects.link(soleil)
    soleil.rotation_euler = (math.radians(60), 0.0, math.radians(-55))
    soleil.data.energy = 3.0
    mat = bpy.data.materials.new("tissu")
    mat.diffuse_color = (0.8, 0.78, 0.72, 1.0)
    o.data.materials.append(mat)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_cavity = True
    scene.display.shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 800
    scene.render.filepath = str(chemin)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        print(__doc__)
        return
    sortie = Path(args[0]).resolve()  # chemin entier : Blender écrit ses images ailleurs avec un chemin relatif (vu le 19/11/2026)
    sortie.mkdir(parents=True, exist_ok=True)
    voulu = [a for a in args[1:] if not a.startswith("--")] or list(SORTES)
    for sorte in voulu:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        o, points, s = calculer(sorte)
        z = points[..., 2]
        # remis d'aplomb : la tringle en haut à HAUTEUR_M, le bas le plus bas à 0 ; la profondeur centrée
        points[..., 2] = (z - z.min()) * (HAUTEUR_M / max(float(z.max() - z.min()), 1e-6))
        points[..., 1] -= float(np.median(points[..., 1]))
        np.savez_compressed(sortie / f"{sorte}.npz", points=points.astype(np.float16), tissu=s.astype(np.float32),
                            hauteur=np.float32(HAUTEUR_M))
        print(f"ATELYA rideau {sorte} : {points.shape[1]} x {points.shape[0]} points, tringle {points[0, :, 0].max():.2f} m, "
              f"profondeur des plis {np.ptp(points[..., 1]):.3f} m, largeur en bas {np.ptp(points[-1, :, 0]):.2f} m", flush=True)
        if "--apercu" in args:
            fige = bpy.data.objects.new(sorte + "_fige", bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get())))
            bpy.context.scene.collection.objects.link(fige)
            o.hide_render = True
            apercu(fige, sortie / f"{sorte}.png")


main()
