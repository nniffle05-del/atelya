"""Script lu par Unreal Engine (Python intégré) : prépare le plan de cinématique d'une maquette importée (11/11/2026).

    UnrealEditor-Cmd.exe AtelyaStudio.uproject -run=pythonscript
        -script="preparer_cinematique.py <paquet> <nom> <trajet.json> [reglage.json]" -nullrhi -unattended

Dans le niveau /Game/Logements/<nom>/Carte (fait par importer_maquette.py), d'après la fiche de scène (<paquet>/scene-atelya.json)
et le réglage (reglage.json : {"eclairage": id ou nom, "exposition": crans, "gain": [r, v, b]} ; sans lui : l'éclairage du trajet,
exposition 0, gain neutre) :
- l'ÉCLAIRAGE (les 5 de Blender, moteur/eclairages.py) : « physique » = atmosphère + soleil à la hauteur et la direction de
  l'ambiance (jour, fin de journée, soirée : soleil sous l'horizon) ; « couvert » = dôme uni blanc à peine bleuté ; « nuit » =
  dôme bleu nuit très sombre ; les plafonniers (Rect Light) allumés si l'ambiance le dit (soirée, nuit) ; une lumière de ciel
  (Sky Light) qui éclaire par les fenêtres ; la lumière qui rebondit est calculée par Lumen. Mêmes forces que Blender, converties
  en unités d'Unreal (1 W de Blender = 683 lumens ; 1 unité de ciel de Blender = 683 nits) : seuls les RAPPORTS comptent (ciel du
  soir contre lampes), la clarté d'ensemble étant réglée par le photographe ;
- les vitres ne font pas d'ombre (le jour passe) ;
- le RÉGLAGE D'IMAGE (Post Process) : exposition fixe, balance des blancs (gain), et la PELLICULE (courbe des tons réglée comme
  AgX de Blender, moteur/photographe.PELLICULE), sans « exposition locale » (Blender n'en a pas), Lumen en qualité maximale ;
- les MURS ET PLAFONDS marqués (« custom stencil » = 1) : le masque que regarde le photographe ;
- la CAMÉRA de cinéma au trajet (mêmes points et images clés que moteur/blender/video_trajet.py) et la SÉQUENCE (Plan) ;
- deux réglages de rendu Movie Render Queue : « Rendu » (le film, PNG, 8 sous-images, 64 images de chauffe CALCULÉES) et
  « Essai » (le photographe : petites images du film en PNG, une image sur `pas`, + le masque des murs et plafonds).

Repère : Atelya (m, y vers le haut du plan) → Unreal (cm, y inversé) : X = 100 x, Y = -100 y, Z = 100 z (vérifié à l'import
d'app-002 sur la position des meubles). Cap d'Atelya (degrés, sens inverse des aiguilles depuis x) → lacet Unreal = -cap.

Préchauffe : « render_warm_up_frames » doit être VRAI, sinon les images de chauffe ne sont pas calculées et Lumen n'a pas encore
« installé » la lumière à la 1re image (mur sombre de l'image 1 du comparatif du 11/11/2026 : murs 123/255 au lieu de ~170).
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
LUMENS_PAR_WATT = 683.0  # 1 W de lumière (Blender) = 683 lumens (Unreal)
NITS_PAR_UNITE = 683.0  # une clarté de ciel de Blender (W/m²/sr) en nits (cd/m²) d'Unreal
# Soleil hors atmosphère (Unreal applique lui-même la traversée de l'air). Mesuré le 11/11/2026 dans le ciel de Blender
# (« 1 Jour ensoleillé », soleil à 50°) : 138,6 W/m² face au soleil, soit ~94 700 lux au sol ; ÷ ~0,87 (air traversé à 50°).
SOLEIL_LUX = 110000.0
STENCIL_BLANCS = 1
STENCIL_DEHORS = 2  # le sol du dehors, pour le masque « dehors vu par une fenêtre »
PROFONDEUR_CIEL_CM = 1.0e6  # au-delà de 10 km, c'est le ciel (le sol du dehors est marqué à part)
NIVEAU_FLOU_CIEL = 6.0  # niveau de détail de la photo de ciel qui donne sa clarté moyenne locale (~32 pixels par face)
# Le photographe : images d'essai au quart de la taille, une image sur PAS_ESSAI (au moins ESSAI_MIN images par plan).
REDUCTION_ESSAI = 4
ESSAI_MIN = 12
CHAUFFE_ESSAI = 32
# MOTEUR DE LUMIÈRE du film (réglage « moteur ») : « lumen » (temps réel, celui de la future visite), « lumen_max » (Lumen avec
# ombres par rayons et lumière des rebonds calculée au point touché), « path_tracer » (le calcul de Cycles : rayons qui rebondissent
# vraiment, ombres douces exactes ; lent, pour le film seulement). Essais comparés le 11/11/2026 (demande NT : lumière réaliste).
MOTEURS = ("lumen", "lumen_max", "path_tracer")
ECHANTILLONS_PT = 256  # rayons par pixel du film au path tracer (puis débruiteur, comme Cycles)
ECHANTILLONS_PT_ESSAI = 16
REBONDS_PT = 32
# Le DEHORS : un sol gris sous le logement (rue, cour), qui renvoie le soleil comme en vrai et se voit par les fenêtres (au lieu
# du sol NOIR de la planète d'Unreal). Hauteur inconnue du plan : logement supposé au 2e étage (statut « ajouté »).
DEHORS_Z_M = -6.0
# Force de la lumière du CIEL (Sky Light) avec l'atmosphère et le soleil. Mesuré le 11/11/2026 (séjour d'app-002, soleil à 50°,
# path tracer, rendus avec et sans la lumière du ciel, même chose dans Cycles sans le disque du soleil) : le ciel apporte 59 % de
# la lumière d'un mur dans Blender (cohérent avec un vrai ciel bleu), 26 % dans Unreal ; il faut ×3,3 (médiane de 7 zones, de 1,9
# à 6,7) pour retrouver la part du ciel de Blender. Le ciel couvert (dôme) était déjà juste : inchangé.
FORCE_CIEL_PHYSIQUE = 3.3
FORCE_CIEL = 1.0
DEHORS_ALBEDO = 0.2  # un trottoir, un bitume clair
DEHORS_COTE_M = 20000.0  # 20 km : avec 2 km, le bord du sol faisait un trait sombre à l'horizon dans les fenêtres
PELLICULE = {"film_slope": 0.514, "film_toe": 0.650, "film_shoulder": 0.545, "film_black_clip": 0.0, "film_white_clip": 0.0642}
PELLICULE_COULEURS = {"expand_gamut": 0.0, "blue_correction": 1.0, "saturation": 1.04}


def _args():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    reglage = json.loads(Path(args[3]).read_text(encoding="utf-8")) if len(args) > 3 else {}
    return Path(args[0]), args[1], Path(args[2]), reglage


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


def _nouveau(racine, nom, classe, fabrique):
    """L'asset `nom`, VIDÉ s'il existe déjà (matériau sans ses nœuds, séquence sans pistes, réglage de rendu sans réglages),
    créé sinon. On ne le supprime pas : quand l'éditeur est ouvert (NT le regarde), il tient ses fichiers et Windows refuse
    de les effacer (erreur 32, vu le 11/11/2026)."""
    chemin = f"{racine}/{nom}"
    if unreal.EditorAssetLibrary.does_asset_exist(chemin):
        a = unreal.EditorAssetLibrary.load_asset(chemin)
        if isinstance(a, classe):
            if isinstance(a, unreal.Material):
                unreal.MaterialEditingLibrary.delete_all_material_expressions(a)
            elif isinstance(a, unreal.LevelSequence):
                for liaison in a.get_bindings():
                    liaison.remove()
                for piste in a.get_tracks():
                    a.remove_track(piste)
            elif isinstance(a, unreal.MoviePipelinePrimaryConfig):
                for reglage in list(a.get_all_settings()):
                    a.remove_setting(reglage)
            return a
        unreal.EditorAssetLibrary.delete_asset(chemin)
    dossier, court = chemin.rsplit("/", 1)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(court, dossier, classe, fabrique)


def _materiau_ciel(racine, couleur, force):
    """Un matériau « ciel » uni et lumineux (vu par la lumière de ciel), à poser à l'intérieur d'un grand dôme."""
    m = _nouveau(racine, "Studio/M_Ciel", unreal.Material, unreal.MaterialFactoryNew())
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


def _premiere_composante(m, texture, y):
    """La 1re composante d'une texture de scène (sa sortie a 4 composantes : comparée telle quelle à une couleur à 3
    composantes, le nœud « si » ne compile pas, « select_internal is ambiguous », vu le 12/11/2026)."""
    lib = unreal.MaterialEditingLibrary
    r = lib.create_material_expression(m, unreal.MaterialExpressionComponentMask, -500, y)
    for canal, garde in (("r", True), ("g", False), ("b", False), ("a", False)):
        r.set_editor_property(canal, garde)
    lib.connect_material_expressions(texture, "Color", r, "")
    return r


def _si_egal(m, entree, valeur, couleur, y):
    """Nœud « si entrée == valeur alors couleur sinon noir » (entrée : 1 composante ; couleur : 3 composantes)."""
    lib = unreal.MaterialEditingLibrary
    egal = lib.create_material_expression(m, unreal.MaterialExpressionIf, -300, y)
    lib.connect_material_expressions(entree, "", egal, "A")
    egal.set_editor_property("const_b", float(valeur))
    egal.set_editor_property("equals_threshold", 0.25)
    for broche, c in (("A > B", (0, 0, 0)), ("A == B", couleur), ("A < B", (0, 0, 0))):
        cst = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, y + 200)
        cst.set_editor_property("constant", unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0))
        lib.connect_material_expressions(cst, "", egal, broche)
    return egal


def _materiau_masque(racine):
    """Réglage d'image « masque », deux canaux : ROUGE là où la surface est un mur ou un plafond (custom stencil = 1 : ce que
    regarde le photographe) ; VERT là où l'on voit DEHORS par une fenêtre (sol du dehors, stencil = 2, ou ciel : profondeur au-delà
    de PROFONDEUR_CIEL_CM). Le vert sert à mesurer les fenêtres (moteur/cinema/lumiere.py, 12/11/2026) ; le photographe ne lit
    que le rouge.

    VU ET CORRIGÉ le 12/11/2026 : le marquage (« custom depth / stencil ») ne dessine QUE les objets marqués, entre eux : un
    meuble ou un sol non marqué devant un mur ne le cache pas. Le masque comptait donc comme « mur » les meubles posés devant
    les murs (un buffet en bois foncé faisait croire les murs plus sombres, et le photographe éclaircissait le film). Un pixel
    n'est plus marqué que si l'objet marqué est bien celui qu'on VOIT : sa profondeur marquée = la profondeur de l'image (à 1 %
    + 2 cm près)."""
    m = _nouveau(racine, "Studio/M_MasqueBlancs", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    lib = unreal.MaterialEditingLibrary
    stencil = lib.create_material_expression(m, unreal.MaterialExpressionSceneTexture, -700, 0)
    stencil.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_CUSTOM_STENCIL)
    s = _premiere_composante(m, stencil, 200)
    profondeur = lib.create_material_expression(m, unreal.MaterialExpressionSceneTexture, -700, 800)
    profondeur.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_SCENE_DEPTH)
    p = _premiere_composante(m, profondeur, 900)
    marquee = lib.create_material_expression(m, unreal.MaterialExpressionSceneTexture, -700, 1200)
    marquee.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_CUSTOM_DEPTH)
    pm = _premiere_composante(m, marquee, 1300)
    ecart = lib.create_material_expression(m, unreal.MaterialExpressionSubtract, -300, 1200)
    lib.connect_material_expressions(pm, "", ecart, "A")
    lib.connect_material_expressions(p, "", ecart, "B")
    ecart_abs = lib.create_material_expression(m, unreal.MaterialExpressionAbs, -200, 1200)
    lib.connect_material_expressions(ecart, "", ecart_abs, "")
    tolerance = lib.create_material_expression(m, unreal.MaterialExpressionMultiply, -300, 1400)
    lib.connect_material_expressions(p, "", tolerance, "A")
    tolerance.set_editor_property("const_b", 0.01)
    tolerance_cm = lib.create_material_expression(m, unreal.MaterialExpressionAdd, -200, 1400)
    lib.connect_material_expressions(tolerance, "", tolerance_cm, "A")
    tolerance_cm.set_editor_property("const_b", 2.0)
    vu = lib.create_material_expression(m, unreal.MaterialExpressionIf, -100, 1300)  # 1 si l'objet marqué est visible
    lib.connect_material_expressions(ecart_abs, "", vu, "A")
    lib.connect_material_expressions(tolerance_cm, "", vu, "B")
    for broche, valeur in (("A > B", 0.0), ("A == B", 1.0), ("A < B", 1.0)):
        cst = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -200, 1500)
        cst.set_editor_property("r", valeur)
        lib.connect_material_expressions(cst, "", vu, broche)
    murs_marques = _si_egal(m, s, STENCIL_BLANCS, (1, 0, 0), 0)
    sol_marque = _si_egal(m, s, STENCIL_DEHORS, (0, 1, 0), 400)
    marques = lib.create_material_expression(m, unreal.MaterialExpressionAdd, -100, 200)
    lib.connect_material_expressions(murs_marques, "", marques, "A")
    lib.connect_material_expressions(sol_marque, "", marques, "B")
    visibles = lib.create_material_expression(m, unreal.MaterialExpressionMultiply, 0, 300)
    lib.connect_material_expressions(marques, "", visibles, "A")
    lib.connect_material_expressions(vu, "", visibles, "B")
    loin = lib.create_material_expression(m, unreal.MaterialExpressionIf, -300, 800)
    lib.connect_material_expressions(p, "", loin, "A")
    loin.set_editor_property("const_b", PROFONDEUR_CIEL_CM)
    for broche, c in (("A > B", (0, 1, 0)), ("A == B", (0, 0, 0)), ("A < B", (0, 0, 0))):
        cst = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, 1000)
        cst.set_editor_property("constant", unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), 1.0))
        lib.connect_material_expressions(cst, "", loin, broche)
    somme = lib.create_material_expression(m, unreal.MaterialExpressionMax, 100, 300)  # ciel : vert ; sinon les marqués vus
    lib.connect_material_expressions(visibles, "", somme, "A")
    lib.connect_material_expressions(loin, "", somme, "B")
    lib.connect_material_property(somme, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def direction_soleil(ambiance, fiche):
    """Direction de la lumière du soleil (repère d'Atelya), comme Blender : hauteur et rotation de l'ambiance (rotation 0 =
    soleil vers +y, 90° vers +x) ; sans elles, la direction du soleil de la fiche."""
    if "elevation_soleil" in ambiance and "rotation_soleil" in ambiance:
        e, r = float(ambiance["elevation_soleil"]), float(ambiance["rotation_soleil"])
        vers = (math.cos(e) * math.sin(r), math.cos(e) * math.cos(r), math.sin(e))
        return [-v for v in vers]
    soleil = next((l for l in fiche.get("lumieres", []) if l["genre"] == "soleil"), None)
    return soleil["direction"] if soleil else [0.6, 0.2, -0.77]


def poser_ciel(racine, ambiance, fiche, centre, force_ciel=None):
    ciel = ambiance.get("ciel", "couvert")
    lumiere_ciel = _poser(unreal.SkyLight, centre, etiquette="Atelya_LumiereCiel")
    composant = lumiere_ciel.get_component_by_class(unreal.SkyLightComponent)
    composant.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    composant.set_editor_property("real_time_capture", True)
    composant.set_editor_property("lower_hemisphere_is_black", False)
    composant.set_editor_property("lower_hemisphere_color", unreal.LinearColor(0.25, 0.25, 0.25, 1.0))
    if force_ciel is None:
        force_ciel = FORCE_CIEL_PHYSIQUE if ciel == "physique" else FORCE_CIEL
    composant.set_editor_property("intensity", float(force_ciel))
    if ciel == "physique":
        _poser(unreal.SkyAtmosphere, etiquette="Atelya_Atmosphere")
        d = direction_soleil(ambiance, fiche)
        rotation = unreal.MathLibrary.make_rot_from_x(unreal.Vector(d[0], -d[1], d[2]))
        s = _poser(unreal.DirectionalLight, centre, rotation, etiquette="Atelya_Soleil")
        sc = s.get_component_by_class(unreal.DirectionalLightComponent)
        sc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property("atmosphere_sun_light", True)
        sc.set_editor_property("intensity", SOLEIL_LUX)
        sc.set_editor_property("light_source_angle", 0.5357)  # le disque du soleil vu de la Terre : ombres un peu floues
        if not ambiance.get("disque_soleil", True):
            sc.set_editor_property("atmosphere_sun_disk_color_scale", unreal.LinearColor(0, 0, 0, 1))
    else:
        couleur = ambiance.get("couleur_nuit") if ciel == "nuit" else ambiance.get("couleur_couvert", [0.92, 0.95, 1.0])
        force = (1.0 if ciel == "nuit" else float(ambiance.get("force_couvert", 1.2))) * NITS_PAR_UNITE
        dome = _poser(unreal.StaticMeshActor, centre, etiquette="Atelya_Ciel")
        mesh = dome.static_mesh_component
        mesh.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Sphere"))
        mesh.set_editor_property("cast_shadow", False)
        mesh.set_world_scale3d(unreal.Vector(CIEL_RAYON_CM / 50.0, CIEL_RAYON_CM / 50.0, CIEL_RAYON_CM / 50.0))
        mesh.set_material(0, _materiau_ciel(racine, couleur, force))
    return ciel


def poser_dehors(racine, centre, invisible=False):
    """Un grand sol gris (20 km) sous le logement, éclairé par le soleil et le ciel. `invisible` (quand la vraie vue est posée,
    13/11/2026) : la caméra ne le voit plus (il cachait le bas du décor : en plongeant vers la rue par le bas des fenêtres, on
    tombait sur lui avant le décor), mais il renvoie toujours la lumière du soleil dans les pièces (lumière indirecte de
    Lumen)."""
    m = _nouveau(racine, "Studio/M_Dehors", unreal.Material, unreal.MaterialFactoryNew())
    lib = unreal.MaterialEditingLibrary
    c = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -400, 0)
    c.set_editor_property("constant", unreal.LinearColor(DEHORS_ALBEDO, DEHORS_ALBEDO, DEHORS_ALBEDO, 1.0))
    lib.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 200)
    r.set_editor_property("r", 0.9)
    lib.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    sol = _poser(unreal.StaticMeshActor, unreal.Vector(centre.x, centre.y, 100.0 * DEHORS_Z_M), etiquette="Atelya_Dehors")
    mesh = sol.static_mesh_component
    mesh.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    mesh.set_world_scale3d(unreal.Vector(DEHORS_COTE_M, DEHORS_COTE_M, 1.0))  # le plan d'Unreal fait 1 m de côté
    mesh.set_material(0, m)
    mesh.set_render_custom_depth(True)  # marqué pour le masque « dehors » (mesure des fenêtres)
    mesh.set_custom_depth_stencil_value(STENCIL_DEHORS)
    if invisible:
        _proprietes(mesh, {"affect_indirect_lighting_while_hidden": True})
        mesh.set_visibility(False, False)
    return sol




def _proprietes(composant, valeurs):
    for nom, valeur in valeurs.items():
        try:
            composant.set_editor_property(nom, valeur)
        except Exception as e:  # noqa: BLE001 : propriété absente de cette version : signalée, pas bloquante
            unreal.log_warning(f"ATELYA propriété {nom} : {e}")


def _texture_ciel(racine, image):
    """Le ciel photographié importé. Unreal 5.8 (import « Interchange ») en fait toujours un CUBE, malgré le réglage
    LoadHdrAsLongLatCubemap=0 (vu le 12/11/2026) : on le garde en cube, et le matériau inverse lui-même le dépliage d'Unreal."""
    chemin = f"{racine}/Studio/T_CielPhoto_{Path(image).stem}"
    if not unreal.EditorAssetLibrary.does_asset_exist(chemin):
        tache = unreal.AssetImportTask()
        for nom, valeur in (("filename", str(image)), ("destination_path", chemin.rsplit("/", 1)[0]),
                            ("destination_name", chemin.rsplit("/", 1)[1]), ("automated", True), ("replace_existing", True),
                            ("save", True)):
            tache.set_editor_property(nom, valeur)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([tache])
    t = unreal.load_asset(chemin)
    if not isinstance(t, unreal.TextureCube):
        raise RuntimeError(f"PLANTÉ : ciel photographié non importé en cube ({chemin} : {type(t).__name__})")
    return t


def poser_ciel_photo(racine, ambiance, fiche, ciel):
    """Le CIEL PHOTOGRAPHIÉ (moteur/cinema/ciels.py), DÉCOR vu par les fenêtres, posé SUR L'IMAGE (réglage d'image, avant la
    courbe des tons) et non dans la scène : il ne remplace que les pixels de ciel (profondeur > PROFONDEUR_CIEL_CM) par la photo
    vue dans la direction du regard (colonne = azimut, tournée pour que le soleil de la photo tombe sur le vrai soleil ; ligne =
    hauteur). Il ne peut donc RIEN éclairer. Premier essai (12/11/2026) : une sphère de 15 km dans la scène assombrissait les murs
    de 1,2 cran malgré toutes ses protections (ombre, captures, Lumen, rayons). Sa clarté suit l'exposition (× exposition de la
    caméra, comme la scène). Renvoie le matériau (à poser dans le réglage d'image) et le décalage."""
    texture = _texture_ciel(racine, ciel["image"])
    d = direction_soleil(ambiance, fiche)
    azimut = math.atan2(d[1], -d[0])  # vers le soleil, repère d'Unreal (y inversé) : (-dx, +dy)
    decalage = (float(ciel["soleil_u"]) - azimut / (2 * math.pi)) % 1.0
    m = _nouveau(racine, "Studio/M_CielPhoto", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    m.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_DOF)
    lib = unreal.MaterialEditingLibrary
    regard = lib.create_material_expression(m, unreal.MaterialExpressionCameraVectorWS, -1100, 0)
    calcul = lib.create_material_expression(m, unreal.MaterialExpressionCustom, -800, 0)
    calcul.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    entree = unreal.CustomInput()
    entree.set_editor_property("input_name", "V")
    calcul.set_editor_property("inputs", [entree])
    # direction du regard -> (u, v) de l'image -> direction du cube d'Unreal qui lit ce pixel : l'inverse exact de son dépliage
    # (TextureCompressorModule.cpp, LookupLongLatDouble : u = (1 + atan2(x, -z) / pi) / 2, v = acos(y) / pi)
    calcul.set_editor_property("code", "float3 d = -normalize(V);\n"
                               f"float u = frac(atan2(d.y, d.x) / 6.28318531 + {decalage:.6f});\n"
                               "float v = acos(clamp(d.z, -1.0, 1.0)) / 3.14159265;\n"
                               "float t = 3.14159265 * (2.0 * u - 1.0);\n"
                               "float s = sin(3.14159265 * v);\n"
                               "return float3(sin(t) * s, cos(3.14159265 * v), -cos(t) * s);")
    lib.connect_material_expressions(regard, "", calcul, "V")
    image = lib.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, 0)
    image.set_editor_property("texture", texture)
    image.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    lib.connect_material_expressions(calcul, "", image, "UVs")
    # la même photo, très floue (niveau de détail 6 : ~32 pixels par face) = sa clarté moyenne autour de ce point
    flou = lib.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, 200)
    flou.set_editor_property("texture", texture)
    flou.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    flou.set_editor_property("mip_value_mode", unreal.TextureMipValueMode.TMVM_MIP_LEVEL)
    flou.set_editor_property("const_mip_value", NIVEAU_FLOU_CIEL)
    lib.connect_material_expressions(calcul, "", flou, "UVs")
    scene = lib.create_material_expression(m, unreal.MaterialExpressionSceneTexture, -700, 400)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    rvb = lib.create_material_expression(m, unreal.MaterialExpressionComponentMask, -500, 400)
    for canal, garde in (("r", True), ("g", True), ("b", True), ("a", False)):
        rvb.set_editor_property(canal, garde)
    lib.connect_material_expressions(scene, "Color", rvb, "")
    # CLARTÉ du vrai ciel calculé à ce pixel (déjà à l'exposition de la caméra) x DÉTAIL et COULEUR de la photo autour de sa
    # moyenne locale : physiquement juste, sans chiffre d'exposition à deviner (essai avec l'exposition d'Unreal : ciel noir)
    melange = lib.create_material_expression(m, unreal.MaterialExpressionCustom, -250, 150)
    melange.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    noms = []
    for nom in ("I", "F", "S"):
        e = unreal.CustomInput()
        e.set_editor_property("input_name", nom)
        noms.append(e)
    melange.set_editor_property("inputs", noms)
    melange.set_editor_property("code", "float3 w = float3(0.2126, 0.7152, 0.0722);\n"
                                f"return I * {float(ciel.get('force', 1.0)):.4f} * dot(S, w) / max(dot(F, w), 1e-6);")
    lib.connect_material_expressions(image, "RGB", melange, "I")
    lib.connect_material_expressions(flou, "RGB", melange, "F")
    lib.connect_material_expressions(rvb, "", melange, "S")
    expose = melange
    profondeur = lib.create_material_expression(m, unreal.MaterialExpressionSceneTexture, -700, 700)
    profondeur.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_SCENE_DEPTH)
    choix = lib.create_material_expression(m, unreal.MaterialExpressionIf, 0, 300)
    lib.connect_material_expressions(_premiere_composante(m, profondeur, 800), "", choix, "A")
    choix.set_editor_property("const_b", PROFONDEUR_CIEL_CM)
    lib.connect_material_expressions(expose, "", choix, "A > B")
    lib.connect_material_expressions(rvb, "", choix, "A == B")
    lib.connect_material_expressions(rvb, "", choix, "A < B")
    lib.connect_material_property(choix, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m, round(decalage, 4)


def _texture_vue(racine, image):
    """L'image d'une toile de vue (PNG RVBA, sRVB), importée en texture 2D (réimportée à chaque préparation : la toile change
    quand on la refait d'après les photos)."""
    chemin = f"{racine}/Studio/T_Vue_{Path(image).stem.replace('-', '_')}"
    tache = unreal.AssetImportTask()
    for nom, valeur in (("filename", str(image)), ("destination_path", chemin.rsplit("/", 1)[0]),
                        ("destination_name", chemin.rsplit("/", 1)[1]), ("automated", True), ("replace_existing", True),
                        ("save", True)):
        tache.set_editor_property(nom, valeur)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([tache])
    t = unreal.load_asset(chemin)
    if not isinstance(t, unreal.Texture2D):
        raise RuntimeError(f"PLANTÉ : toile de vue non importée ({chemin} : {type(t).__name__})")
    _proprietes(t, {"srgb": True, "lod_group": unreal.TextureGroup.TEXTUREGROUP_CINEMATIC,
                    "address_x": unreal.TextureAddress.TA_CLAMP, "address_y": unreal.TextureAddress.TA_CLAMP})
    unreal.EditorAssetLibrary.save_loaded_asset(t)
    return t


def _materiau_vue(racine, nom, texture, vue):
    """Matériau de la toile : TRANSLUCIDE et SANS ÉCLAIRAGE (il n'entre ni dans le calcul de la lumière de Lumen, ni dans ses
    traces à l'écran, ni dans la profondeur : derrière lui, le masque « dehors » voit toujours le sol et le ciel). L'image est
    lue d'après la position du point dans le monde (pas d'après le maillage) : coin haut-gauche, axes u (droite) et v (bas).
    Clarté AFFICHÉE indépendante de l'exposition de la caméra (× exposition inverse) : RVB de l'image (mur de la photo =
    BLANC_REF) × force, où force = clarté visée des murs / BLANC_REF ; le dehors garde l'écart aux murs de la photo."""
    m = _nouveau(racine, f"Studio/M_Vue_{nom}", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    _proprietes(m, {"use_translucency_vertex_fog": False, "apply_cloud_fogging": False, "allow_custom_depth_writes": False,
                    "translucency_pass": unreal.MaterialTranslucencyPass.MTP_BEFORE_DOF})
    lib = unreal.MaterialEditingLibrary
    position = lib.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1100, 0)
    uv = lib.create_material_expression(m, unreal.MaterialExpressionCustom, -800, 0)
    uv.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    e = unreal.CustomInput()
    e.set_editor_property("input_name", "P")
    uv.set_editor_property("inputs", [e])
    c, au, av = vue["coin"], vue["axe_u"], vue["axe_v"]
    uv.set_editor_property("code", f"float3 d = P - float3({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f});\n"
                           f"return float2(dot(d, float3({au[0]:.6f}, {au[1]:.6f}, {au[2]:.6f})) / {vue['largeur_cm']:.3f},\n"
                           f"              dot(d, float3({av[0]:.6f}, {av[1]:.6f}, {av[2]:.6f})) / {vue['hauteur_cm']:.3f});")
    lib.connect_material_expressions(position, "", uv, "P")
    image = lib.create_material_expression(m, unreal.MaterialExpressionTextureSample, -500, 0)
    image.set_editor_property("texture", texture)
    lib.connect_material_expressions(uv, "", image, "UVs")
    inverse = lib.create_material_expression(m, unreal.MaterialExpressionEyeAdaptationInverse, -500, 300)
    force = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 450)
    force.set_editor_property("r", float(vue.get("force", 1.0)))
    f1 = lib.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, 100)
    lib.connect_material_expressions(image, "RGB", f1, "A")
    lib.connect_material_expressions(force, "", f1, "B")
    f2 = lib.create_material_expression(m, unreal.MaterialExpressionMultiply, -100, 150)
    lib.connect_material_expressions(f1, "", f2, "A")
    lib.connect_material_expressions(inverse, "", f2, "B")
    lib.connect_material_property(f2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.connect_material_property(image, "A", unreal.MaterialProperty.MP_OPACITY)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def poser_vues_dehors(racine, vues):
    """La VRAIE VUE (moteur/vue_dehors.py) : une toile verticale par côté de l'immeuble, à la distance des immeubles d'en face,
    peinte d'après les photos du client. Un vrai objet de la scène (demande NT, 12/11/2026), mais tenu hors de TOUT calcul de
    lumière : pas d'ombre, pas dans Lumen (ni lumière indirecte, ni champs de distance), invisible aux rayons (Lumen matériel,
    reflets), aux captures de ciel et de reflets. Premier essai du 12/11/2026 (sphère opaque de 15 km) : murs −1,2 cran ; la
    toile translucide sans éclairage n'entre même pas dans les traces à l'écran de Lumen. Renvoie le nombre de toiles."""
    plan = unreal.load_asset("/Engine/BasicShapes/Plane")  # 100 × 100 cm, à plat (normale +Z), centré
    for i, vue in enumerate(vues):
        texture = _texture_vue(racine, vue["image"])
        m = _materiau_vue(racine, vue.get("id", str(i)).replace("-", "_"), texture, vue)
        c, au, av, n = (unreal.Vector(*vue[k]) for k in ("coin", "axe_u", "axe_v", "normale_vers_logement"))
        centre = c + au * (vue["largeur_cm"] / 2) + av * (vue["hauteur_cm"] / 2)
        rotation = unreal.MathLibrary.make_rot_from_zx(n, au)
        a = _poser(unreal.StaticMeshActor, centre, rotation, etiquette=f"Atelya_Vue_{vue.get('id', i)}")
        comp = a.static_mesh_component
        comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        comp.set_static_mesh(plan)
        comp.set_world_scale3d(unreal.Vector(vue["largeur_cm"] / 100.0, vue["hauteur_cm"] / 100.0, 1.0))
        comp.set_material(0, m)
        _proprietes(comp, {"cast_shadow": False, "cast_dynamic_shadow": False, "cast_static_shadow": False,
                           "cast_hidden_shadow": False, "affect_dynamic_indirect_lighting": False,
                           "affect_indirect_lighting_while_hidden": False, "affect_distance_field_lighting": False,
                           "visible_in_ray_tracing": False, "visible_in_reflection_captures": False,
                           "visible_in_real_time_sky_captures": False, "receives_decals": False})
    return len(vues)


DALLE_EPAISSEUR_CM = 30.0
DALLE_DEBORD_CM = 20.0  # recouvre le dessus des murs (14 à 20 cm d'épaisseur)


def poser_dalles(fiche):
    """Dalles de l'immeuble au-dessus des plafonds et sous les sols (fiche : dalles, moteur/export_unreal.dalles) : boîtes
    opaques de 30 cm, débordant de 20 cm sur les murs. La lumière n'entre plus que par les fenêtres (plus de fentes de ciel)."""
    d = fiche.get("dalles") or {}
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")  # 100 cm de côté, centré
    n = 0
    for genre, z_cm in (("plafonds", 100.0 * d.get("haut_m", 2.5) + 1.0 + DALLE_EPAISSEUR_CM / 2),
                        ("sols", 100.0 * d.get("bas_m", 0.0) - 1.0 - DALLE_EPAISSEUR_CM / 2)):
        for xmin, xmax, ymin, ymax in d.get(genre, []):
            centre = vers_unreal((xmin + xmax) / 2, (ymin + ymax) / 2, 0.0)
            a = _poser(unreal.StaticMeshActor, unreal.Vector(centre.x, centre.y, z_cm), etiquette=f"Atelya_Dalle_{genre}_{n}")
            m = a.static_mesh_component
            m.set_static_mesh(cube)
            m.set_world_scale3d(unreal.Vector((100.0 * (xmax - xmin) + 2 * DALLE_DEBORD_CM) / 100.0,
                                              (100.0 * (ymax - ymin) + 2 * DALLE_DEBORD_CM) / 100.0, DALLE_EPAISSEUR_CM / 100.0))
            n += 1
    return n


def allumer_lampes(ambiance, fiche, pieces=()):
    """Les plafonniers : un panneau lumineux sous le plafond, vers le bas, de la taille et de la force de Blender. Tous si
    l'ambiance les allume (soirée, nuit) ; sinon seulement ceux des `pieces` données : une pièce SANS FENÊTRE filmée de jour a son
    plafonnier allumé, comme le ferait un photographe d'immobilier (moteur/realisateur : plan["lumiere_du_jour"])."""
    pieces = set(pieces or ())
    if not ambiance.get("lampes") and not pieces:
        return 0
    couleur = ambiance.get("couleur_lampes") or [1.0, 0.82, 0.62]
    n = 0
    for l in fiche.get("lumieres", []):
        if l["genre"] != "plafonnier" or not l.get("puissance_w"):
            continue
        if not ambiance.get("lampes") and l.get("piece") not in pieces:
            continue
        x, y, z = l["position"]
        a = _poser(unreal.RectLight, vers_unreal(x, y, z), unreal.Rotator(0, -90, 0), etiquette=f"Atelya_{l['id']}")
        c = a.get_component_by_class(unreal.RectLightComponent)
        c.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        c.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
        c.set_editor_property("intensity", float(l["puissance_w"]) * LUMENS_PAR_WATT)
        # couleur LINÉAIRE nommée (r=, g=, b=) : unreal.Color est rangé bleu-vert-rouge, il donnait des lampes BLEUES (11/11/2026)
        c.set_light_color(unreal.LinearColor(r=float(couleur[0]), g=float(couleur[1]), b=float(couleur[2]), a=1.0))
        largeur, profondeur = l.get("taille_m") or [0.5, 0.5]
        c.set_editor_property("source_width", 100.0 * float(largeur))
        c.set_editor_property("source_height", 100.0 * float(profondeur))
        c.set_editor_property("attenuation_radius", 1500.0)
        c.set_editor_property("barn_door_angle", 90.0)
        n += 1
    return n


ORIGINE = "Atelya_origine:"


def refermer_portes():
    """Remet chaque battant ouvert par une préparation précédente à sa place d'origine (gardée dans une étiquette)."""
    n = 0
    for a in _acteurs().get_all_level_actors():
        tags = [str(x) for x in a.tags]
        origine = next((x for x in tags if x.startswith(ORIGINE)), None)
        if origine is None:
            continue
        v = [float(c) for c in origine[len(ORIGINE):].split(",")]
        a.set_actor_location_and_rotation(unreal.Vector(v[0], v[1], v[2]), unreal.Rotator(roll=v[3], pitch=v[4], yaw=v[5]),
                                          False, False)
        a.tags = [unreal.Name(x) for x in tags if not x.startswith(ORIGINE)]
        n += 1
    return n


def ouvrir_portes(portes):
    """Les portes ouvertes pour la balade (moteur/promeneur.portes_ouvertes) : le battant et ses poignées pivotent de
    `angle_deg` (sens trigonométrique du plan d'Atelya) autour du gond. Repère d'Unreal : y inversé, donc lacet = -angle."""
    n = 0
    par_id = {p["id"]: p for p in portes}
    for a in _acteurs().get_all_level_actors():
        etiquette = a.get_actor_label()
        ident = etiquette.split("__", 1)[0]
        p = par_id.get(ident)
        if p is None or not (etiquette.startswith(f"{ident}__battant") or etiquette.startswith(f"{ident}__poignee")):
            continue
        psi = math.radians(-float(p["angle_deg"]))
        g = vers_unreal(p["gond"][0], p["gond"][1], 0.0)
        loc = a.get_actor_location()
        rot = a.get_actor_rotation()
        a.tags = list(a.tags) + [unreal.Name(f"{ORIGINE}{loc.x},{loc.y},{loc.z},{rot.roll},{rot.pitch},{rot.yaw}")]
        dx, dy = loc.x - g.x, loc.y - g.y
        nouveau = unreal.Vector(g.x + dx * math.cos(psi) - dy * math.sin(psi), g.y + dx * math.sin(psi) + dy * math.cos(psi), loc.z)
        a.set_actor_location_and_rotation(nouveau, unreal.Rotator(roll=rot.roll, pitch=rot.pitch,
                                                                  yaw=rot.yaw + math.degrees(psi)), False, False)
        n += 1
    return n


def vitres_sans_ombre():
    n = 0
    for a in _acteurs().get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        comp = a.static_mesh_component
        for i in range(comp.get_num_materials()):
            m = comp.get_material(i)
            if m and m.get_name().lower().startswith(("verre", "mi_verre", "m_verreclair")):
                comp.set_editor_property("cast_shadow", False)
                n += 1
                break
    return n


VERRE_OPACITE = 0.06  # moteur/blender/exporter_gltf.ALPHA_VERRE : 6 % de reflet, 94 % de lumière qui passe


def _materiau_verre_clair(racine):
    """VITRE CLAIRE : translucide, SANS couleur propre (base noire) ; il ne lui reste que son reflet (6 %, poli). Le verre
    importé (glTF : surface BLANCHE à 94 % transparente) recevait le soleil et le ciel comme un mur : un voile laiteux sur tout
    le dehors (vu le 12/11/2026 sur la vraie vue tirée des photos : immeubles d'en face délavés)."""
    m = _nouveau(racine, "Studio/M_VerreClair", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    _proprietes(m, {"translucency_lighting_mode": unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING})
    lib = unreal.MaterialEditingLibrary
    for prop, valeur, y in ((unreal.MaterialProperty.MP_BASE_COLOR, 0.0, 0), (unreal.MaterialProperty.MP_METALLIC, 0.0, 100),
                            (unreal.MaterialProperty.MP_SPECULAR, 0.5, 200), (unreal.MaterialProperty.MP_ROUGHNESS, 0.03, 300),
                            (unreal.MaterialProperty.MP_OPACITY, VERRE_OPACITE, 400)):
        c = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -300, y)
        c.set_editor_property("r", valeur)
        lib.connect_material_property(c, "", prop)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def verre_clair(racine, actif=True):
    """Pose la VITRE CLAIRE sur toutes les vitres (actif) ou remet le verre importé (sinon : la carte garde le dernier choix,
    il faut pouvoir revenir en arrière). Renvoie le nombre de vitres et le nom du verre importé."""
    m = _materiau_verre_clair(racine)
    importes = [x for x in unreal.EditorAssetLibrary.list_assets(racine, recursive=True, include_folder=False)
                if x.rsplit("/", 1)[-1].split(".")[0].lower() in ("verre", "mi_verre")]
    origine = unreal.load_asset(importes[0]) if importes else None
    if not actif and origine is None:
        raise RuntimeError(f"PLANTÉ : verre importé introuvable sous {racine}")
    n = 0
    for a in _acteurs().get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor):
            continue
        comp = a.static_mesh_component
        for i in range(comp.get_num_materials()):
            mi = comp.get_material(i)
            if mi and mi.get_name().lower().startswith(("verre", "mi_verre", "m_verreclair")):
                comp.set_material(i, m if actif else origine)
                n += 1
    return n, (origine.get_path_name() if origine else None)


def marquer_blancs(fiche):
    """Murs et plafonds (fiche : surfaces_blanches) marqués pour le masque du photographe."""
    noms = set(fiche.get("surfaces_blanches") or [])
    n = 0
    for a in _acteurs().get_all_level_actors():
        if not isinstance(a, unreal.StaticMeshActor) or a.get_actor_label() == "Atelya_Dehors":
            continue
        comp = a.static_mesh_component
        blanc = a.get_actor_label() in noms
        comp.set_render_custom_depth(blanc)
        comp.set_custom_depth_stencil_value(STENCIL_BLANCS if blanc else 0)
        n += blanc
    return n


def poser_reglage_image(exposition, gain, moteur="lumen", intensite_max=None, locale=None, halo=0.2):
    """Le réglage d'image (Post Process). `locale` : exposition LOCALE {"hautes_lumieres": 0..1, "pivot_crans": crans,
    "flou": 0..1} : les grandes zones plus claires que le pivot (les fenêtres) voient leur contraste réduit (1 = rien) ; le pivot
    est placé au-dessus du gris moyen d'Unreal (0,18) ; None = pas d'exposition locale."""
    v = _poser(unreal.PostProcessVolume, etiquette="Atelya_ReglageImage")
    v.set_editor_property("unbound", True)
    r = v.get_editor_property("settings")
    reglages = {
        "auto_exposure_method": unreal.AutoExposureMethod.AEM_MANUAL,
        "auto_exposure_bias": float(exposition),
        "auto_exposure_apply_physical_camera_exposure": False,
        "color_gain": unreal.Vector4(float(gain[0]), float(gain[1]), float(gain[2]), 1.0),
        "local_exposure_highlight_contrast_scale": float((locale or {}).get("hautes_lumieres", 1.0)),
        "local_exposure_shadow_contrast_scale": 1.0,
        "local_exposure_middle_grey_bias": float((locale or {}).get("pivot_crans", 0.0)),
        "local_exposure_blurred_luminance_blend": float((locale or {}).get("flou", 0.6)),
        "lumen_final_gather_quality": 4.0,
        "lumen_scene_lighting_quality": 4.0,
        "lumen_scene_detail": 4.0,
        "lumen_reflection_quality": 4.0,
        # flou de mouvement du cinéma : obturateur à 180° (0,5) ; Movie Render Queue l'obtient en accumulant ses sous-images sur
        # la demi-image d'ouverture. Sans lui, à 24 images/s, tout panoramique paraît saccadé (NT, 12/11/2026)
        "motion_blur_amount": 0.5,
        "vignette_intensity": 0.0,
        "bloom_intensity": float(halo),
        **PELLICULE,
        "expand_gamut": PELLICULE_COULEURS["expand_gamut"],
        "blue_correction": PELLICULE_COULEURS["blue_correction"],
        "color_saturation": unreal.Vector4(1.0, 1.0, 1.0, PELLICULE_COULEURS["saturation"]),
    }
    if moteur == "path_tracer":
        reglages.update({"path_tracing_max_bounces": REBONDS_PT, "path_tracing_enable_denoiser": True,
                         "path_tracing_enable_emissive_materials": True})
        if intensite_max is not None:  # garde-fou des chemins trop forts (points blancs) ; essai du 11/11/2026
            reglages["path_tracing_max_path_intensity"] = float(intensite_max)
    for nom, valeur in reglages.items():
        r.set_editor_property(nom, valeur)
        drapeau = "override_" + nom
        try:
            r.set_editor_property(drapeau, True)
        except Exception as e:  # noqa: BLE001 : un réglage absent de cette version d'Unreal est signalé, pas bloquant
            unreal.log_warning(f"ATELYA réglage {drapeau} : {e}")
    v.set_editor_property("settings", r)
    return v


def cles_exposition(seq, volume, cles):
    """L'exposition qui VARIE au fil du film (balade d'une pièce à l'autre, comme l'œil ou une vraie caméra qui s'adapte) :
    clés [[image, exposition Unreal], …] sur le réglage d'image (Post Process), interpolées en douceur."""
    liaison = seq.add_possessable(volume)
    piste = liaison.add_track(unreal.MovieSceneFloatTrack)
    piste.set_property_name_and_path("AutoExposureBias", "Settings.AutoExposureBias")
    section = piste.add_section()
    section.set_range(0, int(max(c[0] for c in cles)) + 1)
    canal = section.get_all_channels()[0]
    for image, biais in cles:
        canal.add_key(unreal.FrameNumber(int(image)), float(biais), 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                      unreal.MovieSceneKeyInterpolation.AUTO)
    return len(cles)


def creer_sequence(racine, trajet):
    seq = _nouveau(racine, "Plan", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
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


def _sortie(config, largeur, hauteur, dossier, nom_fichier, pas=1):
    s = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    s.set_editor_property("output_resolution", unreal.IntPoint(largeur, hauteur))
    d = unreal.DirectoryPath()
    d.set_editor_property("path", str(dossier))
    s.set_editor_property("output_directory", d)
    s.set_editor_property("file_name_format", nom_fichier)
    s.set_editor_property("zero_pad_frame_numbers", 4)
    s.set_editor_property("frame_number_offset", 1)
    s.set_editor_property("output_frame_step", int(pas))
    s.set_editor_property("override_existing_output", True)


def _lissage(config, sous_images, chauffe, spatial=1):
    lissage = config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    lissage.set_editor_property("spatial_sample_count", spatial)
    lissage.set_editor_property("temporal_sample_count", sous_images)
    lissage.set_editor_property("override_anti_aliasing", True)
    lissage.set_editor_property("anti_aliasing_method", unreal.AntiAliasingMethod.AAM_NONE)
    lissage.set_editor_property("engine_warm_up_count", chauffe)
    lissage.set_editor_property("render_warm_up_count", chauffe)
    lissage.set_editor_property("render_warm_up_frames", True)  # chauffe CALCULÉE : Lumen installe la lumière avant l'image 1
    lissage.set_editor_property("use_camera_cut_for_warm_up", False)


def _variables(config, moteur="lumen", temporel=False, ombres_contact=False):
    variables = config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    if moteur == "lumen_max":
        for nom, valeur in (("r.Lumen.ScreenProbeGather.ShortRangeAO", 1 if ombres_contact else 0),  # ombres de contact (coins)
                            ("r.Lumen.ScreenProbeGather.Temporal.MaxFramesAccumulated", 32),  # lumière plus calme d'une image à l'autre
                            ("r.Lumen.RadianceCache.ProbeResolution", 32),  # cache de la lumière renvoyée plus fin
                            ("r.Lumen.RadianceCache.NumProbesToTraceBudget", 800),
                            ("r.LumenScene.SurfaceCache.CardTexelDensityScale", 4),  # lumière des surfaces plus détaillée
                            ("r.Lumen.ScreenProbeGather.ScreenTraces.HZBTraversal.FullResDepth", 1),
                            ("r.RayTracing.Shadows", 1),  # ombres par rayons (douces et justes) au lieu des cartes d'ombres
                            # (« r.Lumen.HardwareRayTracing.LightingMode 2 », lumière calculée au point touché : fait planter le
                            # pilote NVIDIA 555.97 du PC à la compilation, 11/11/2026 ; à réessayer après mise à jour du pilote)
                            ("r.Lumen.ScreenProbeGather.MaxRayIntensity", 100),  # moins d'écrêtage des taches de soleil
                            ("r.Lumen.Reflections.MaxRayIntensity", 400)):
            variables.add_or_update_console_variable(nom, valeur)
    if moteur == "path_tracer":
        variables.add_or_update_console_variable("r.PathTracing.Denoiser", 1)
        # débruiteur TEMPOREL (NFOR, fourni avec Unreal) : nettoie le grain en regardant les images voisines (film sans grain
        # qui grouille, essai du 11/11/2026)
        variables.add_or_update_console_variable("r.PathTracing.TemporalDenoiser", 1 if temporel else 0)
    for nom, valeur in (("r.Lumen.ScreenProbeGather.TracingOctahedronResolution", 16),
                        ("r.Lumen.ScreenProbeGather.DownsampleFactor", 8),
                        ("r.Shadow.Virtual.SMRT.RayCountDirectional", 16),
                        ("r.Shadow.Virtual.SMRT.RayCountLocal", 16),
                        ("r.MotionBlurQuality", 0),
                        ("r.CustomDepth", 3),
                        ("r.ScreenPercentage", 100)):
        variables.add_or_update_console_variable(nom, valeur)


def _passe(config, moteur):
    classe = unreal.MoviePipelineDeferredPass_PathTracer if moteur == "path_tracer" else unreal.MoviePipelineDeferredPassBase
    return config.find_or_add_setting_by_class(classe)


def creer_reglage_rendu(racine, trajet, sortie, moteur="lumen", echantillons=ECHANTILLONS_PT, temporel=False, ombres_contact=False):
    config = _nouveau(racine, "Rendu", unreal.MoviePipelinePrimaryConfig, None)
    if config is None:
        raise RuntimeError("PLANTÉ : réglage de rendu non créé")
    largeur, hauteur = trajet.get("format", [1280, 720])
    _sortie(config, largeur, hauteur, sortie, "image-{frame_number}")
    _passe(config, moteur)
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    if moteur == "path_tracer":  # chaque image repart de zéro : pas de chauffe de la lumière, des rayons
        _lissage(config, 1, 8, spatial=int(echantillons))
    else:
        _lissage(config, SOUS_IMAGES, CHAUFFE_IMAGES)
    _variables(config, moteur, temporel, ombres_contact)
    unreal.EditorAssetLibrary.save_loaded_asset(config)
    return config


def creer_reglage_essai(racine, trajet, sortie, moteur="lumen", ombres_contact=False):
    """Le rendu d'essai du photographe : petites images du film (PNG, même pellicule et même exposition) + masque des murs et
    plafonds. (Un essai « sans courbe des tons » en EXR ne suit pas le film dans Unreal : abandonné le 11/11/2026.)"""
    config = _nouveau(racine, "Essai", unreal.MoviePipelinePrimaryConfig, None)
    if config is None:
        raise RuntimeError("PLANTÉ : réglage d'essai non créé")
    largeur, hauteur = trajet.get("format", [1280, 720])
    n = int(trajet.get("images", 96))
    pas = int(trajet.get("essai_pas") or max(1, n // ESSAI_MIN))  # une balade : un essai par seconde de film
    _sortie(config, max(64, largeur // REDUCTION_ESSAI), max(36, hauteur // REDUCTION_ESSAI), sortie,
            "{render_pass}.{frame_number}", pas)
    passe = _passe(config, moteur)
    masque = unreal.MoviePipelinePostProcessPass()
    masque.set_editor_property("enabled", True)
    masque.set_editor_property("material", _materiau_masque(racine))
    passe.set_editor_property("additional_post_process_materials", [masque])
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    if moteur == "path_tracer":
        _lissage(config, 1, 8, spatial=ECHANTILLONS_PT_ESSAI)
    else:
        _lissage(config, 1, CHAUFFE_ESSAI)
    _variables(config, moteur, ombres_contact=ombres_contact)
    unreal.EditorAssetLibrary.save_loaded_asset(config)
    return config


def main():
    paquet, nom, trajet_json, reglage = _args()
    racine = f"{REPERTOIRE}/{nom}"
    fiche = json.loads((paquet / "scene-atelya.json").read_text(encoding="utf-8"))
    trajet = json.loads(trajet_json.read_text(encoding="utf-8"))
    niveaux = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    monde = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    deja_ouvert = monde is not None and monde.get_path_name().startswith(f"{racine}/Carte")
    if not deja_ouvert and not niveaux.load_level(f"{racine}/Carte"):
        raise RuntimeError(f"PLANTÉ : niveau {racine}/Carte introuvable (lancer importer_maquette.py)")
    _vider_studio()
    voulu = reglage.get("eclairage") or trajet.get("scene", "")
    ambiances = fiche.get("eclairages", [])
    ambiance = next((a for a in ambiances if voulu in (a.get("nom"), a.get("id"))), None)
    if ambiance is None:
        raise RuntimeError(f"PLANTÉ : éclairage « {voulu} » absent de la fiche ({[a.get('id') for a in ambiances]})")
    p0 = trajet["points"][0]
    centre = vers_unreal(p0[0], p0[1], 1.5)
    moteur = reglage.get("moteur", "lumen")
    if moteur not in MOTEURS:
        raise RuntimeError(f"PLANTÉ : moteur « {moteur} » inconnu ({MOTEURS})")
    ciel = poser_ciel(racine, ambiance, fiche, centre, reglage.get("force_ciel"))
    if ciel == "physique" and reglage.get("dehors", True):
        poser_dehors(racine, centre, invisible=bool(reglage.get("vues_dehors")) and not reglage.get("dehors_visible", False))
    ciel_photo, materiau_ciel = None, None
    if reglage.get("ciel_photo"):
        materiau_ciel, ciel_photo = poser_ciel_photo(racine, ambiance, fiche, reglage["ciel_photo"])
    vues = poser_vues_dehors(racine, reglage["vues_dehors"]) if reglage.get("vues_dehors") else 0
    lampes = allumer_lampes(ambiance, fiche, reglage.get("lampes_pieces") or ())
    nb_dalles = poser_dalles(fiche)
    vitres_claires, verre_importe = verre_clair(racine, bool(reglage.get("verre_clair", False)))
    vitres = vitres_sans_ombre()
    refermer_portes()
    portes = ouvrir_portes(reglage.get("portes_ouvertes") or [])
    blancs = marquer_blancs(fiche)
    if not blancs:
        raise RuntimeError("PLANTÉ : aucun mur ni plafond reconnu (fiche : surfaces_blanches)")
    exposition = float(reglage.get("exposition", 0.0))
    gain = reglage.get("gain") or [1.0, 1.0, 1.0]
    volume = poser_reglage_image(exposition, gain, moteur, reglage.get("intensite_max"), reglage.get("exposition_locale"),
                                 reglage.get("halo", 0.2))
    if materiau_ciel is not None:  # le ciel photographié, posé sur l'image (réglage d'image)
        r = volume.get_editor_property("settings")
        r.set_editor_property("weighted_blendables", unreal.WeightedBlendables(
            array=[unreal.WeightedBlendable(weight=1.0, object=materiau_ciel)]))
        volume.set_editor_property("settings", r)
    seq = creer_sequence(racine, trajet)
    nb_cles = 0
    if reglage.get("exposition_cles"):
        nb_cles = cles_exposition(seq, volume, reglage["exposition_cles"])
        unreal.EditorAssetLibrary.save_loaded_asset(seq)
    rendus = Path(str(paquet)).parent / "rendus" / nom
    dossier = rendus / (reglage.get("dossier") or ambiance["id"])
    creer_reglage_rendu(racine, trajet, dossier, moteur, reglage.get("echantillons", ECHANTILLONS_PT),
                        bool(reglage.get("debruiteur_temporel", False)), bool(reglage.get("ombres_contact", False)))
    creer_reglage_essai(racine, trajet, dossier / "essai", moteur, bool(reglage.get("ombres_contact", False)))
    niveaux.save_current_level()
    unreal.log("ATELYA prépare " + json.dumps({"ambiance": ambiance.get("id"), "ciel": ciel, "lampes": lampes,
                                                 "vitres_sans_ombre": vitres, "murs_et_plafonds": blancs, "dalles": nb_dalles, "cles_exposition": nb_cles, "pieces_de_portes_ouvertes": portes,
                                                 "exposition": exposition, "gain": gain, "moteur": moteur,
                                                 "ciel_photo_decalage": ciel_photo, "vues_dehors": vues,
                                                 "vitres_claires": vitres_claires if reglage.get("verre_clair") else 0,
                                                 "verre_importe": verre_importe,
                                                 "sortie": str(dossier)},
                                                ensure_ascii=False))


main()
