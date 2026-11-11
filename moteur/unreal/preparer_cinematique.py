"""Script lu par Unreal Engine (Python intégré) : prépare le plan de cinématique d'une maquette importée (11/11/2026).

    UnrealEditor-Cmd.exe AtelyaStudio.uproject -run=pythonscript
        -script="preparer_cinematique.py <paquet> <nom> <trajet.json> [exposition]" -nullrhi -unattended

Dans le niveau /Game/Logements/<nom>/Carte (fait par importer_maquette.py), d'après la fiche de scène (<paquet>/scene-atelya.json) :
- le CIEL de l'éclairage du trajet (« 2 Jour voilé » : un dôme uni blanc à peine bleuté, comme le ciel couvert de Blender ; « 1 Jour
  ensoleillé » : atmosphère physique + soleil à la direction de la fiche) et une lumière de ciel (Sky Light) qui éclaire par les
  fenêtres ; la lumière qui rebondit est calculée par Lumen ;
- les vitres ne font pas d'ombre (le jour passe) ;
- un réglage d'image (Post Process) : exposition fixe (`exposition`, en crans), qualité Lumen poussée pour le film ;
- la CAMÉRA : une caméra de cinéma (objectif `focale_mm`, capteur 36 mm, sans flou), au même trajet que la vidéo Blender
  (moteur/blender/video_trajet.py : mêmes points, mêmes images clés, courbes adoucies) ;
- la SÉQUENCE (/Game/Logements/<nom>/Plan) et le RÉGLAGE DU RENDU de film (/Game/Logements/<nom>/Rendu : PNG, format du trajet,
  8 sous-images par image pour lisser, 64 images de chauffe pour que Lumen se stabilise).

Repère : Atelya (m, y vers le haut du plan) → Unreal (cm, y inversé) : X = 100 x, Y = -100 y, Z = 100 z (vérifié à l'import
d'app-002 sur la position des meubles). Cap d'Atelya (degrés, sens inverse des aiguilles depuis x) → lacet Unreal = -cap.
"""
import json
import math
import sys
from pathlib import Path

import unreal

REPERTOIRE = "/Game/Logements"
CIEL_RAYON_CM = 20000.0
CHAUFFE_IMAGES = 64
SOUS_IMAGES = 8


def _args():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    exposition = float(args[3]) if len(args) > 3 else 0.0
    return Path(args[0]), args[1], Path(args[2]), exposition


def vers_unreal(x, y, z):
    return unreal.Vector(100.0 * x, -100.0 * y, 100.0 * z)


def _acteurs():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _poser(classe, position=unreal.Vector(0, 0, 0), rotation=unreal.Rotator(0, 0, 0), etiquette=None):
    a = _acteurs().spawn_actor_from_class(classe, position, rotation)
    if etiquette:
        a.set_actor_label(etiquette)
    return a


def _vider_studio():
    """Enlève ce qu'une préparation précédente a posé (étiquettes « Atelya_… »), pour pouvoir relancer."""
    for a in _acteurs().get_all_level_actors():
        if a.get_actor_label().startswith("Atelya_"):
            _acteurs().destroy_actor(a)


def _materiau_ciel(racine, couleur, force):
    """Un matériau « ciel » uni et lumineux (vu par la lumière de ciel), à poser à l'intérieur d'un grand dôme."""
    chemin = f"{racine}/Studio/M_Ciel"
    if unreal.EditorAssetLibrary.does_asset_exist(chemin):
        unreal.EditorAssetLibrary.delete_asset(chemin)
    outils = unreal.AssetToolsHelpers.get_asset_tools()
    m = outils.create_asset("M_Ciel", f"{racine}/Studio", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("is_sky", True)
    lib = unreal.MaterialEditingLibrary
    c = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -400, 0)
    c.set_editor_property("constant", unreal.LinearColor(couleur[0] * force, couleur[1] * force, couleur[2] * force, 1.0))
    lib.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def poser_ciel(racine, ambiance, fiche, centre):
    ciel = ambiance.get("ciel", "couvert")
    lumiere_ciel = _poser(unreal.SkyLight, centre, etiquette="Atelya_LumiereCiel")
    composant = lumiere_ciel.get_component_by_class(unreal.SkyLightComponent)
    composant.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    composant.set_editor_property("real_time_capture", True)
    composant.set_editor_property("lower_hemisphere_is_black", False)
    composant.set_editor_property("lower_hemisphere_color", unreal.LinearColor(0.25, 0.25, 0.25, 1.0))
    if ciel == "physique":
        _poser(unreal.SkyAtmosphere, etiquette="Atelya_Atmosphere")
        soleil = next((l for l in fiche.get("lumieres", []) if l["genre"] == "soleil"), None)
        d = soleil["direction"] if soleil else [0.6, 0.2, -0.77]
        direction = unreal.Vector(d[0], -d[1], d[2])
        rotation = unreal.MathLibrary.make_rot_from_x(direction)
        s = _poser(unreal.DirectionalLight, centre, rotation, etiquette="Atelya_Soleil")
        sc = s.get_component_by_class(unreal.DirectionalLightComponent)
        sc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property("atmosphere_sun_light", True)
        sc.set_editor_property("intensity", 10.0)
    else:
        couleur = ambiance.get("couleur_nuit") if ciel == "nuit" else ambiance.get("couleur_couvert", [0.92, 0.95, 1.0])
        force = 1.0 if ciel == "nuit" else float(ambiance.get("force_couvert", 1.2))
        dome = _poser(unreal.StaticMeshActor, centre, etiquette="Atelya_Ciel")
        mesh = dome.static_mesh_component
        mesh.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Sphere"))
        mesh.set_editor_property("cast_shadow", False)
        mesh.set_world_scale3d(unreal.Vector(CIEL_RAYON_CM / 50.0, CIEL_RAYON_CM / 50.0, CIEL_RAYON_CM / 50.0))
        mesh.set_material(0, _materiau_ciel(racine, couleur, force))
    return ciel


def vitres_sans_ombre():
    n = 0
    for a in _acteurs().get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        comp = a.static_mesh_component
        for i in range(comp.get_num_materials()):
            m = comp.get_material(i)
            if m and m.get_name().lower().startswith(("verre", "mi_verre")):
                comp.set_editor_property("cast_shadow", False)
                n += 1
                break
    return n


def poser_reglage_image(exposition):
    v = _poser(unreal.PostProcessVolume, etiquette="Atelya_ReglageImage")
    v.set_editor_property("unbound", True)
    r = v.get_editor_property("settings")
    reglages = {
        "auto_exposure_method": unreal.AutoExposureMethod.AEM_MANUAL,
        "auto_exposure_bias": exposition,
        "auto_exposure_apply_physical_camera_exposure": False,
        "lumen_final_gather_quality": 2.0,
        "lumen_scene_lighting_quality": 2.0,
        "lumen_scene_detail": 2.0,
        "lumen_reflection_quality": 2.0,
        "motion_blur_amount": 0.0,
        "vignette_intensity": 0.0,
        "bloom_intensity": 0.2,
    }
    for nom, valeur in reglages.items():
        r.set_editor_property(nom, valeur)
        drapeau = "override_" + nom
        try:
            r.set_editor_property(drapeau, True)
        except Exception as e:  # noqa: BLE001 : un réglage absent de cette version d'Unreal est signalé, pas bloquant
            unreal.log_warning(f"ATELYA réglage {drapeau} : {e}")
    v.set_editor_property("settings", r)
    return v


def creer_sequence(racine, trajet):
    chemin = f"{racine}/Plan"
    if unreal.EditorAssetLibrary.does_asset_exist(chemin):
        unreal.EditorAssetLibrary.delete_asset(chemin)
    outils = unreal.AssetToolsHelpers.get_asset_tools()
    seq = outils.create_asset("Plan", racine, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    ips = int(trajet.get("ips", 24))
    n = int(trajet.get("images", 96))
    seq.set_display_rate(unreal.FrameRate(ips, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(n)
    # La caméra est posée dans le niveau puis confiée à la séquence (« possédée ») : ses réglages se font directement sur elle.
    acteur = _poser(unreal.CineCameraActor, vers_unreal(*trajet["points"][0][:3]), etiquette="Atelya_Camera")
    cc = acteur.get_cine_camera_component()
    largeur, hauteur = trajet.get("format", [1280, 720])
    filmback = cc.get_editor_property("filmback")
    filmback.set_editor_property("sensor_width", 36.0)
    filmback.set_editor_property("sensor_height", 36.0 * hauteur / largeur)
    cc.set_editor_property("filmback", filmback)
    cc.set_editor_property("current_focal_length", float(trajet.get("focale_mm", 18)))
    focus = cc.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", focus)
    camera = seq.add_possessable(acteur)

    piste = camera.add_track(unreal.MovieScene3DTransformTrack)
    section = piste.add_section()
    section.set_range(0, n)
    canaux = section.get_all_channels()  # x, y, z, roulis, tangage, lacet, échelles
    points = trajet["points"]
    for k, (x, y, z, cap, tangage) in enumerate(points):
        image = round(k * (n - 1) / max(len(points) - 1, 1))
        p = vers_unreal(x, y, z)
        valeurs = [p.x, p.y, p.z, 0.0, float(tangage), -float(cap)]
        for canal, valeur in zip(canaux[:6], valeurs):
            canal.add_key(unreal.FrameNumber(image), valeur, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                          unreal.MovieSceneKeyInterpolation.AUTO)
    coupes = seq.add_track(unreal.MovieSceneCameraCutTrack)
    coupe = coupes.add_section()
    coupe.set_range(0, n)
    lien = unreal.MovieSceneObjectBindingID()
    lien.set_editor_property("guid", camera.get_id())
    coupe.set_camera_binding_id(seq.get_binding_id(camera) if hasattr(seq, "get_binding_id") else lien)
    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    return seq


def creer_reglage_rendu(racine, trajet, sortie):
    chemin = f"{racine}/Rendu"
    if unreal.EditorAssetLibrary.does_asset_exist(chemin):
        unreal.EditorAssetLibrary.delete_asset(chemin)
    outils = unreal.AssetToolsHelpers.get_asset_tools()
    config = outils.create_asset("Rendu", racine, unreal.MoviePipelinePrimaryConfig, None)
    if config is None:
        raise RuntimeError("PLANTÉ : réglage de rendu non créé")
    largeur, hauteur = trajet.get("format", [1280, 720])
    sortie_r = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    sortie_r.set_editor_property("output_resolution", unreal.IntPoint(largeur, hauteur))
    dossier = unreal.DirectoryPath()
    dossier.set_editor_property("path", str(sortie))
    sortie_r.set_editor_property("output_directory", dossier)
    sortie_r.set_editor_property("file_name_format", "image-{frame_number}")
    sortie_r.set_editor_property("zero_pad_frame_numbers", 4)
    sortie_r.set_editor_property("frame_number_offset", 1)
    config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    lissage = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    lissage.set_editor_property("spatial_sample_count", 1)
    lissage.set_editor_property("temporal_sample_count", SOUS_IMAGES)
    lissage.set_editor_property("override_anti_aliasing", True)
    lissage.set_editor_property("anti_aliasing_method", unreal.AntiAliasingMethod.AAM_NONE)
    lissage.set_editor_property("engine_warm_up_count", CHAUFFE_IMAGES)
    lissage.set_editor_property("render_warm_up_count", CHAUFFE_IMAGES)
    lissage.set_editor_property("use_camera_cut_for_warm_up", False)
    variables = config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    for nom, valeur in (("r.Lumen.ScreenProbeGather.TracingOctahedronResolution", 16),
                        ("r.Lumen.ScreenProbeGather.DownsampleFactor", 8),
                        ("r.Shadow.Virtual.SMRT.RayCountDirectional", 16),
                        ("r.Shadow.Virtual.SMRT.RayCountLocal", 16),
                        ("r.MotionBlurQuality", 0),
                        ("r.ScreenPercentage", 100)):
        variables.add_or_update_console_variable(nom, valeur)
    unreal.EditorAssetLibrary.save_loaded_asset(config)
    return config


def main():
    paquet, nom, trajet_json, exposition = _args()
    racine = f"{REPERTOIRE}/{nom}"
    fiche = json.loads((paquet / "scene-atelya.json").read_text(encoding="utf-8"))
    trajet = json.loads(trajet_json.read_text(encoding="utf-8"))
    niveaux = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not niveaux.load_level(f"{racine}/Carte"):
        raise RuntimeError(f"PLANTÉ : niveau {racine}/Carte introuvable (lancer importer_maquette.py)")
    _vider_studio()
    nom_scene = trajet.get("scene", "")
    ambiance = next((a for a in fiche.get("eclairages", []) if a.get("nom") == nom_scene), None) \
        or next((a for a in fiche.get("eclairages", []) if a.get("id") == "jour_voile"), {"ciel": "couvert"})
    p0 = trajet["points"][0]
    centre = vers_unreal(p0[0], p0[1], 1.5)
    ciel = poser_ciel(racine, ambiance, fiche, centre)
    vitres = vitres_sans_ombre()
    poser_reglage_image(exposition)
    creer_sequence(racine, trajet)
    sortie = Path(str(paquet)).parent / "rendus" / nom
    creer_reglage_rendu(racine, trajet, sortie)
    niveaux.save_current_level()
    unreal.log("ATELYA prépare " + json.dumps({"ambiance": ambiance.get("id"), "ciel": ciel, "vitres_sans_ombre": vitres,
                                                 "exposition": exposition, "sortie": str(sortie)}, ensure_ascii=False))


main()
