"""Script lu par Blender : exporte la FORME de la maquette d'Atelya au format glTF, pour Unreal Engine (11/11/2026).

    blender -b maquette.blend --python exporter_gltf.py -- dossier_sortie [nom_de_scene]

Pourquoi : Unreal ne lit pas les fichiers .blend. Blender reste l'ATELIER qui construit le logement (murs, sols, plafonds,
menuiseries, sur-mesure, linge, rideaux, meubles ABO posés) ; Unreal est le STUDIO (matières, lumière, ombres, caméra,
cinématique, visite). glTF est un format ouvert que les deux lisent.

Ce qui part : toute la géométrie visible (instances des meubles ABO comprises), chaque surface avec le NOM de sa matière, les
textures (meubles ABO, photos des sols et de l'enduit des murs). Ce qui ne part PAS : les lampes, les caméras, le ciel (refaits
dans Unreal d'après la fiche de scène, moteur/export_unreal.py).

Placage des photos : dans la maquette, les photos des sols et de l'enduit sont posées « vues d'en haut » (sols) ou « de face »
(côtés), à leur taille réelle, d'après la position de chaque point. glTF ne sait pas décrire ce placage : sans rien faire, le
parquet partirait sans repères et serait étalé n'importe comment dans Unreal. Avant l'export, ce script CALCULE donc ces repères
(une « carte UV » : pour chaque coin de chaque face, le point de la photo qui doit s'y trouver), exactement comme Blender les
calcule au rendu, et y rebranche les photos. Le résultat est le même dans Blender, et il passe tel quel dans glTF.
Les motifs DESSINÉS par calcul (point de Hongrie, carreaux de ciment) ne passent pas : ils partent comme leur photo de base, et la
fiche de scène les signale (à cuire en image répétable : chantier à part).
Écrit : <dossier>/maquette.gltf + .bin + textures/ et <dossier>/export-blender.json (ce que Blender a exporté).
"""
import collections
import json
import math
import sys
import time
from pathlib import Path

import bpy

UV_MONDE = "atelya_monde"  # la carte UV calculée par ce script
ALPHA_VERRE = 0.06  # la part de reflet du verre de la maquette (moteur/blender/materiaux._verre)


def _amont(entree, type_noeud):
    """Le nœud de type `type_noeud` branché sur `entree`, ou None."""
    if not entree.is_linked:
        return None
    noeud = entree.links[0].from_node
    return noeud if noeud.type == type_noeud else None


def placage_photo(materiau):
    """Le placage d'une matière à photos posée par position réelle (moteur/blender/materiaux._coordonnees), ou None.

    Chaîne reconnue : coordonnées « objet » → rotation autour du haut → mise à l'échelle → photo(s) en projection boîte.
    Renvoie {angle, echelle (x, y, z), decalage (x, y, z), photos (nœuds image)}. Un motif dessiné par calcul (point de Hongrie,
    carreaux de ciment) n'a pas cette chaîne : None."""
    if not materiau or not materiau.use_nodes:
        return None
    photos, reglage = [], None
    for n in materiau.node_tree.nodes:
        if n.type != "TEX_IMAGE":
            continue
        mapping = _amont(n.inputs["Vector"], "MAPPING")
        rotation = mapping and _amont(mapping.inputs["Vector"], "VECTOR_ROTATE")
        coord = rotation and _amont(rotation.inputs["Vector"], "TEX_COORD")
        if not coord or rotation.rotation_type != "Z_AXIS" or rotation.inputs["Vector"].links[0].from_socket.name != "Object":
            return None
        r = (rotation.inputs["Angle"].default_value, tuple(mapping.inputs["Scale"].default_value),
             tuple(mapping.inputs["Location"].default_value))
        if reglage is not None and any(abs(a - b) > 1e-6 for a, b in zip(_aplatir(reglage), _aplatir(r))):
            return None  # deux placages différents dans une même matière : on ne sait pas faire, on laisse tel quel
        reglage = r
        photos.append(n)
    if not photos:
        return None
    return {"angle": reglage[0], "echelle": reglage[1], "decalage": reglage[2], "photos": photos}


def _aplatir(r):
    return [r[0], *r[1], *r[2]]


def uv_du_point(co, normale, p):
    """Le point de la photo (u, v) pour un point `co` d'une face de normale `normale` (repère de l'objet), comme Blender au
    rendu : rotation autour du haut, mise à l'échelle, puis projection « boîte » selon le grand axe de la normale
    (dessus/dessous → x, y ; côtés face à x → y, z ; côtés face à y → x, z)."""
    c, s = math.cos(p["angle"]), math.sin(p["angle"])
    x, y, z = co[0] * c - co[1] * s, co[0] * s + co[1] * c, co[2]
    x, y, z = (x * p["echelle"][0] + p["decalage"][0], y * p["echelle"][1] + p["decalage"][1],
               z * p["echelle"][2] + p["decalage"][2])
    nx, ny, nz = (abs(v) for v in normale)
    if nz >= nx and nz >= ny:
        return x, y
    if nx >= ny:
        return y, z
    return x, z


def calculer_les_placages(scene) -> dict:
    """Pose la carte UV « monde » sur chaque objet dont une matière est plaquée par position, et y rebranche ses photos.

    Les modificateurs de ces objets (biseaux…) sont appliqués d'abord, pour que la carte suive la forme exacte exportée."""
    placages = {}
    for m in bpy.data.materials:
        p = placage_photo(m)
        if p:
            placages[m.name] = p
    if not placages:
        return {"materiaux_plaques": [], "objets": 0}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objets = 0
    for o in scene.objects:
        if o.type != "MESH" or not any(s.material and s.material.name in placages for s in o.material_slots):
            continue
        if o.modifiers:
            mesh = bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                                   depsgraph=depsgraph)
            o.modifiers.clear()
            o.data = mesh
        elif o.data.users > 1:
            o.data = o.data.copy()  # une forme partagée : sa carte UV dépend de l'objet, on la rend propre à lui
        mesh = o.data
        uv = mesh.uv_layers.get(UV_MONDE) or mesh.uv_layers.new(name=UV_MONDE)
        for poly in mesh.polygons:
            slot = o.material_slots[poly.material_index] if poly.material_index < len(o.material_slots) else None
            p = placages.get(slot.material.name) if slot and slot.material else None
            if p is None:
                continue
            for i in poly.loop_indices:
                uv.data[i].uv = uv_du_point(mesh.vertices[mesh.loops[i].vertex_index].co, poly.normal, p)
        objets += 1
    for nom, p in placages.items():
        arbre = bpy.data.materials[nom].node_tree
        carte = arbre.nodes.new("ShaderNodeUVMap")
        carte.uv_map = UV_MONDE
        for photo in p["photos"]:
            arbre.links.new(carte.outputs["UV"], photo.inputs["Vector"])
            photo.projection = "FLAT"
    return {"materiaux_plaques": sorted(placages), "objets": objets}


def verre_standard(materiau) -> None:
    """Le verre de la maquette (mélange « transparent + reflet », moteur/blender/materiaux._verre) n'existe pas dans glTF :
    il partait VIDE, donc opaque, et les pièces se retrouvaient fermées et noires. Il est remplacé, pour l'export seulement, par
    un verre que glTF et Unreal savent lire : une surface à 94 % transparente (ALPHA_VERRE), qui garde 6 % de reflet, comme
    dans la maquette. Pas de verre « qui dévie la lumière » (transmission) : essayé le 11/11, le soleil ne traversait plus
    les fenêtres au rendu (plus de taches de soleil au sol)."""
    arbre = materiau.node_tree
    arbre.nodes.clear()
    sortie = arbre.nodes.new("ShaderNodeOutputMaterial")
    bsdf = arbre.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)  # le peu qui reste visible est un reflet, pas un voile blanc
    bsdf.inputs["Roughness"].default_value = 0.02
    bsdf.inputs["Alpha"].default_value = ALPHA_VERRE
    arbre.links.new(bsdf.outputs["BSDF"], sortie.inputs["Surface"])


def _plage(noeud):
    """(de, à) d'un nœud « plage de valeurs » linéaire qui part de 0..1, ou None."""
    if noeud.type != "MAP_RANGE" or noeud.data_type != "FLOAT" or noeud.interpolation_type != "LINEAR":
        return None
    e = noeud.inputs
    if e["From Min"].is_linked or e["From Max"].is_linked or e["To Min"].is_linked or e["To Max"].is_linked:
        return None
    if abs(e["From Min"].default_value) > 1e-6 or abs(e["From Max"].default_value - 1.0) > 1e-6:
        return None
    return e["To Min"].default_value, e["To Max"].default_value


def cuire_les_brillances(materiaux) -> list[str]:
    """La brillance des photos est RÉGLÉE par un calcul dans la maquette (parquet vitrifié satiné : rugosité ramenée entre 0,6 et
    0,85 ; peinture mate : entre 0,8 et 0,95). glTF ne transporte pas ce calcul : le parquet partait avec la brillance brute de
    la photo, presque un miroir. Ici le calcul est fait une fois pour toutes sur l'image (« cuit ») : une nouvelle image de
    brillance déjà réglée remplace le calcul. Même résultat au rendu, et il passe dans glTF."""
    import numpy as np

    cuites, deja = [], {}
    for m in materiaux:
        if not m or not m.use_nodes:
            continue
        arbre = m.node_tree
        for noeud in list(arbre.nodes):
            plage = _plage(noeud)
            if plage is None or not noeud.inputs["Value"].is_linked or not noeud.outputs["Result"].is_linked:
                continue
            photo = noeud.inputs["Value"].links[0].from_node
            if photo.type != "TEX_IMAGE" or photo.image is None:
                continue
            cle = (photo.image.name, round(plage[0], 4), round(plage[1], 4))
            if cle not in deja:
                image = photo.image
                largeur, hauteur = image.size
                pixels = np.empty(largeur * hauteur * 4, dtype=np.float32)
                image.pixels.foreach_get(pixels)
                pixels = pixels.reshape(-1, 4)
                clarte = pixels[:, :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
                valeur = plage[0] + (plage[1] - plage[0]) * np.clip(clarte, 0.0, 1.0)
                cuite = bpy.data.images.new(f"{image.name}_reglee_{plage[0]:.2f}_{plage[1]:.2f}", largeur, hauteur)
                cuite.colorspace_settings.name = "Non-Color"
                cuite.pixels.foreach_set(np.repeat(valeur[:, None], 4, axis=1).ravel().astype(np.float32))
                cuite.file_format = "PNG"
                cuite.pack()
                deja[cle] = cuite
            nouvelle = arbre.nodes.new("ShaderNodeTexImage")
            nouvelle.image = deja[cle]
            nouvelle.projection = photo.projection
            if photo.inputs["Vector"].is_linked:
                arbre.links.new(photo.inputs["Vector"].links[0].from_socket, nouvelle.inputs["Vector"])
            for lien in list(noeud.outputs["Result"].links):
                arbre.links.new(nouvelle.outputs["Color"], lien.to_socket)
            arbre.nodes.remove(noeud)
            cuites.append(m.name)
    return sorted(set(cuites))


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    dossier = Path(args[0]).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    # La forme est la même dans toutes les scènes d'éclairage ; seules les lampes allumées changent (et elles ne partent pas).
    # Par défaut : la première scène (« 1 Jour ensoleillé »), pour un export qui ne dépend pas de la scène ouverte en dernier.
    scene = bpy.data.scenes[args[1]] if len(args) > 1 else sorted(bpy.data.scenes, key=lambda s: s.name)[0]
    if bpy.context.window:
        bpy.context.window.scene = scene
    # Les lampes et caméras restent dans Blender : Unreal aura les siennes (rien n'est enregistré dans le .blend).
    retires = collections.Counter()
    for o in list(bpy.data.objects):
        if o.type in {"LIGHT", "CAMERA", "LIGHT_PROBE"}:
            retires[o.type] += 1
            bpy.data.objects.remove(o, do_unlink=True)
    with bpy.context.temp_override(scene=scene):
        placages = calculer_les_placages(scene)
    for m in bpy.data.materials:
        if m.name.split(".")[0] == "verre" and m.use_nodes:
            verre_standard(m)
    brillances = cuire_les_brillances(bpy.data.materials)
    materiaux = sorted({s.material.name for o in scene.objects if o.type == "MESH" for s in o.material_slots if s.material})
    with bpy.context.temp_override(scene=scene):
        bpy.ops.export_scene.gltf(
            filepath=str(dossier / "maquette.gltf"),
            export_format="GLTF_SEPARATE",
            export_texture_dir="textures",
            export_apply=True,  # biseaux, subdivisions, plis du linge : appliqués (la forme exacte part)
            export_lights=False,
            export_cameras=False,
            export_extras=True,  # propriétés personnalisées (pièce de chaque brique…)
            export_materials="EXPORT",
            export_yup=True,
            use_active_scene=True,
        )
    bilan = {"maquette": bpy.data.filepath, "scene": scene.name, "duree_s": round(time.time() - debut, 1),
             "objets_scene": dict(collections.Counter(o.type for o in scene.objects)),
             "instances_meubles": sum(1 for o in scene.objects if o.instance_type == "COLLECTION"),
             "retires": dict(retires), "placages": placages, "brillances_cuites": brillances, "materiaux": materiaux}
    (dossier / "export-blender.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Export glTF : {dossier / 'maquette.gltf'} ({bilan['duree_s']} s ; placages calculés : "
          f"{len(placages['materiaux_plaques'])} matières, {placages['objets']} objets)")


if __name__ == "__main__":
    main()
