"""Script lu par Blender : règle la teinte des sols vus sur une photo du client, AU RENDU (B2 temps 2, 09/11/2026).

Pourquoi : la teinte calculée sur la photo (moteur/teinte_photo.py) vise la couleur du bois. Mais au rendu, le reflet du ciel et
le réglage de pellicule de Blender (AgX) changent ce que l'œil voit : app-001, parquet miel sur la photo, rosé-gris au rendu. On
fait donc comme un photographe qui ajuste sa couleur : pour chaque sol à régler (plan de construction, clé « reglages_teinte »),
une petite image depuis une caméra posée dans la pièce, avec le même réglage d'exposition et de balance des blancs que l'image
finale (rendre.reglage_de_photographe) ; on y mesure le sol contre les murs blancs, exactement comme sur la photo du client (mur
blanc = étalon), et on corrige la teinte du matériau ; TOURS fois. La maquette est enregistrée avec les teintes réglées.

Utilisation (lancé par moteur/construire.py) :
    blender -b --factory-startup maquette.blend --python regler_teintes.py -- construction.json reglages.json
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from poser_briques import orienter  # noqa: E402
from rendre import reglage_de_photographe  # noqa: E402

TOURS = 3
ECHANTILLONS = 64
LARGEUR, HAUTEUR = 480, 300
BLANC_PEINTURE = 0.86  # même étalon que moteur/teinte_photo.py
GAIN_MIN, GAIN_MAX = 0.02, 4.0  # mêmes bornes que le format (moteur/logement.py, Sol.teinte)
PIXELS_MIN = 200  # en dessous, le sol ou les murs sont trop peu visibles depuis la caméra : pas de réglage


def lineaire(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lire(chemin: Path) -> np.ndarray:
    """Les pixels d'une image enregistrée, tels qu'écrits dans le fichier (0..1, RGBA), du haut vers le bas peu importe."""
    image = bpy.data.images.load(str(chemin))
    image.colorspace_settings.name = "Non-Color"  # les valeurs du fichier, sans conversion
    pixels = np.array(image.pixels[:], dtype=float).reshape(-1, 4)
    bpy.data.images.remove(image)
    return pixels


def rendre_vers(scene, chemin: Path, echantillons: int, transparent: bool) -> np.ndarray:
    scene.cycles.samples = echantillons
    scene.cycles.use_denoising = not transparent
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(chemin)
    bpy.ops.render.render(write_still=True)
    return lire(chemin)


def masque(scene, objets_gardes: set, chemin: Path) -> np.ndarray:
    """Les pixels où l'on voit ces objets (tous les autres « découpés »)."""
    maillages = [o for o in scene.objects if o.type == "MESH"]
    for o in maillages:
        o.is_holdout = o.name not in objets_gardes
    try:
        return rendre_vers(scene, chemin, 4, True)[:, 3] > 0.5
    finally:
        for o in maillages:
            o.is_holdout = False


def noeud_teinte(materiau):
    return next((n for n in materiau.node_tree.nodes if n.type == "RGB" and n.name.startswith("teinte")), None)


def main() -> None:
    plan_json, sortie_json = sys.argv[sys.argv.index("--") + 1:][:2]
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = LARGEUR, HAUTEUR, 100
    scene.cycles.sample_clamp_indirect = 10.0
    dossier = Path(sortie_json).resolve().parent / "_reglage"
    dossier.mkdir(exist_ok=True)
    murs = {o.name for c in scene.collection.children if c.name == "Murs" for o in c.objects}
    camera_avant, mode_avant = scene.camera, scene.render.image_settings.color_mode
    # B4 (09/11/2026) : les meubles masqués pendant la mesure. Sinon la caméra de réglage voit le tapis et le canapé à la place
    # du parquet, le croit trop clair et l'assombrit à chaque tour (app-001 meublé : point de Hongrie réglé à 0,22 ; 0,02 ; 0,02).
    meubles = [c for c in scene.collection.children if c.name == "Meubles"]
    for c in meubles:
        c.hide_render = True
    resultats = []
    for r in plan.get("reglages_teinte", []):
        materiau = bpy.data.materials.get(r["materiau"])
        teinte = noeud_teinte(materiau) if materiau else None
        ligne = {"materiau": r["materiau"], "piece": r["piece"], "cible": r["cible"]}
        if teinte is None:
            resultats.append({**ligne, "erreur": "matériau sans teinte"})
            continue
        donnees = bpy.data.cameras.new("Reglage")
        donnees.lens, donnees.sensor_width, donnees.sensor_fit = r["camera"]["focale"], r["camera"]["capteur"], "HORIZONTAL"
        donnees.clip_start = 0.05
        camera = bpy.data.objects.new("Reglage", donnees)
        scene.collection.objects.link(camera)
        camera.location = r["camera"]["position"]
        orienter(camera, [c - p for p, c in zip(r["camera"]["position"], r["camera"]["cible"])])
        scene.camera = camera
        try:
            sols = {o.name for o in scene.objects if o.type == "MESH" and o.active_material is not None
                    and o.active_material.name == r["materiau"]}
            m_sol, m_mur = masque(scene, sols, dossier / "sol.png"), masque(scene, murs, dossier / "murs.png")
            if m_sol.sum() < PIXELS_MIN or m_mur.sum() < PIXELS_MIN:
                resultats.append({**ligne, "erreur": f"trop peu visible ({int(m_sol.sum())} px de sol, {int(m_mur.sum())} px de murs)"})
                continue
            gains = np.array(teinte.outputs[0].default_value[:3], dtype=float)
            cible = np.asarray(r["cible"], dtype=float)
            tours = []
            for _ in range(TOURS):
                exposition, blanc = reglage_de_photographe(scene, dossier)
                scene.view_settings.exposure = exposition
                scene.view_settings.use_curve_mapping = True
                scene.view_settings.curve_mapping.white_level = blanc
                scene.view_settings.curve_mapping.update()
                pixels = rendre_vers(scene, dossier / "essai.png", ECHANTILLONS, False)[:, :3]
                sol = lineaire(pixels[m_sol]).mean(axis=0)
                mur = lineaire(pixels[m_mur])
                clarte = mur @ np.array([0.2126, 0.7152, 0.0722])
                bas, haut = np.percentile(clarte, [50, 90])  # les murs bien éclairés, comme le morceau de mur blanc choisi sur la photo
                etalon = mur[(clarte >= bas) & (clarte <= haut)].mean(axis=0)
                vu = sol / max(float(etalon.max()), 1e-6) * BLANC_PEINTURE
                tours.append({"teinte": [round(float(g), 3) for g in gains], "vu": [round(float(v), 4) for v in vu]})
                gains = np.clip(gains * cible / np.maximum(vu, 1e-4), GAIN_MIN, GAIN_MAX)
                teinte.outputs[0].default_value = (*gains, 1.0)
            resultats.append({**ligne, "teinte_finale": [round(float(g), 3) for g in gains], "tours": tours})
            print(f"Teinte réglée : {r['materiau']} → {tuple(round(float(g), 2) for g in gains)} (vu {tours[-1]['vu']}, visé {r['cible']})")
        finally:
            bpy.data.objects.remove(camera)
            bpy.data.cameras.remove(donnees)
    for c in meubles:
        c.hide_render = False
    scene.view_settings.exposure = 0.0
    scene.view_settings.use_curve_mapping = False
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = mode_avant
    scene.camera = camera_avant
    for f in dossier.glob("*"):
        f.unlink()
    dossier.rmdir()
    Path(sortie_json).write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    bpy.ops.wm.save_mainfile()


if __name__ == "__main__":  # lancé par Blender (--python) ; importé par un autre script : rien ne démarre
    main()
