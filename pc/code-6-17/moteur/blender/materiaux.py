"""Matériaux « procéduraux » de la maquette, lus par Blender.

Procédural veut dire : dessinés par un petit calcul (des lames de bois, une
grille de carreaux) au lieu d'une photo de texture. Rien à télécharger, et
ça reste net de près. Les tailles sont en mètres : une lame de parquet fait
1,20 m × 0,15 m, un carreau 0,60 m × 0,60 m.

Chaque matériau est un petit réseau de « nœuds » (des boîtes reliées entre
elles, comme dans l'éditeur de Blender), construit ici par programme.
"""

import bpy


def creer_materiaux() -> dict:
    """Crée tous les matériaux connus et les renvoie par nom."""
    fabriques = {
        "mur_blanc": lambda m: _uni(m, (0.86, 0.85, 0.82), rugosite=0.9),
        "plafond_blanc": lambda m: _uni(m, (0.9, 0.9, 0.9), rugosite=0.95),
        "menuiserie_blanche": lambda m: _uni(m, (0.92, 0.92, 0.91), rugosite=0.35),
        "porte_interieure": lambda m: _uni(m, (0.88, 0.87, 0.84), rugosite=0.45),
        "porte_entree": lambda m: _uni(m, (0.12, 0.13, 0.14), rugosite=0.4),
        "metal": lambda m: _uni(m, (0.75, 0.75, 0.76), rugosite=0.25, metal=1.0),
        "seuil": lambda m: _uni(m, (0.55, 0.53, 0.5), rugosite=0.6),
        "parquet": _parquet,
        "carrelage": _carrelage,
        "verre": _verre,
    }
    materiaux = {}
    for nom, fabrique in fabriques.items():
        materiau = bpy.data.materials.new(nom)
        materiau.use_nodes = True
        fabrique(materiau)
        materiaux[nom] = materiau
    return materiaux


def _noeuds(materiau):
    """Vide le réseau de nœuds et renvoie (nœuds, liens, sortie)."""
    arbre = materiau.node_tree
    arbre.nodes.clear()
    sortie = arbre.nodes.new("ShaderNodeOutputMaterial")
    return arbre.nodes, arbre.links, sortie


def _principled(noeuds, liens, sortie, rugosite, metal=0.0):
    bsdf = noeuds.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rugosite
    bsdf.inputs["Metallic"].default_value = metal
    liens.new(bsdf.outputs["BSDF"], sortie.inputs["Surface"])
    return bsdf


def _uni(materiau, couleur, rugosite, metal=0.0):
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite, metal)
    bsdf.inputs["Base Color"].default_value = (*couleur, 1.0)
    materiau.diffuse_color = (*couleur, 1.0)  # couleur dans la vue rapide de Blender


def _briques(noeuds, liens, largeur, hauteur, decalage, joint, couleur_1, couleur_2, couleur_joint):
    """Une grille de rectangles (lames ou carreaux), mesurée en mètres."""
    coordonnees = noeuds.new("ShaderNodeTexCoord")
    grille = noeuds.new("ShaderNodeTexBrick")
    grille.offset = decalage  # une rangée sur deux est décalée de cette fraction
    grille.offset_frequency = 2
    grille.inputs["Scale"].default_value = 1.0
    grille.inputs["Brick Width"].default_value = largeur
    grille.inputs["Row Height"].default_value = hauteur
    grille.inputs["Mortar Size"].default_value = joint
    grille.inputs["Mortar Smooth"].default_value = 0.1
    grille.inputs["Color1"].default_value = (*couleur_1, 1.0)
    grille.inputs["Color2"].default_value = (*couleur_2, 1.0)
    grille.inputs["Mortar"].default_value = (*couleur_joint, 1.0)
    # « Object » : la position réelle du point, en mètres (les objets sont posés à l'origine).
    liens.new(coordonnees.outputs["Object"], grille.inputs["Vector"])
    return coordonnees, grille


def _relief(noeuds, liens, hauteur, bsdf, force):
    """Creuse légèrement les joints, pour qu'ils accrochent la lumière."""
    relief = noeuds.new("ShaderNodeBump")
    relief.inputs["Strength"].default_value = force
    relief.inputs["Distance"].default_value = 0.002
    liens.new(hauteur, relief.inputs["Height"])
    liens.new(relief.outputs["Normal"], bsdf.inputs["Normal"])


def _parquet(materiau):
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.45)
    coordonnees, lames = _briques(noeuds, liens, largeur=1.20, hauteur=0.15, decalage=0.5,
                                  joint=0.002, couleur_1=(0.3, 0.17, 0.08),
                                  couleur_2=(0.42, 0.25, 0.12), couleur_joint=(0.16, 0.1, 0.06))
    lames.inputs["Bias"].default_value = 0.0

    # Le fil du bois : un bruit étiré dans le sens des lames (axe x).
    etirement = noeuds.new("ShaderNodeMapping")
    etirement.inputs["Scale"].default_value = (1.5, 40.0, 1.0)
    liens.new(coordonnees.outputs["Object"], etirement.inputs["Vector"])
    fil = noeuds.new("ShaderNodeTexNoise")
    fil.inputs["Scale"].default_value = 3.0
    fil.inputs["Detail"].default_value = 6.0
    liens.new(etirement.outputs["Vector"], fil.inputs["Vector"])
    nuances = noeuds.new("ShaderNodeValToRGB")
    nuances.color_ramp.elements[0].color = (0.75, 0.75, 0.75, 1.0)
    nuances.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    liens.new(fil.outputs["Fac"], nuances.inputs["Fac"])

    melange = _melange_multiplier(noeuds)
    liens.new(lames.outputs["Color"], _entree(melange, "A"))
    liens.new(nuances.outputs["Color"], _entree(melange, "B"))
    liens.new(_sortie(melange, "Result"), bsdf.inputs["Base Color"])
    _relief(noeuds, liens, lames.outputs["Fac"], bsdf, force=0.3)
    materiau.diffuse_color = (0.5, 0.32, 0.18, 1.0)


def _carrelage(materiau):
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.25)
    _, carreaux = _briques(noeuds, liens, largeur=0.60, hauteur=0.60, decalage=0.0,
                           joint=0.004, couleur_1=(0.7, 0.68, 0.64),
                           couleur_2=(0.74, 0.72, 0.68), couleur_joint=(0.45, 0.44, 0.42))
    liens.new(carreaux.outputs["Color"], bsdf.inputs["Base Color"])
    _relief(noeuds, liens, carreaux.outputs["Fac"], bsdf, force=0.5)
    materiau.diffuse_color = (0.7, 0.68, 0.64, 1.0)


def _verre(materiau):
    """Un verre simple : on voit à travers et la lumière du soleil passe."""
    noeuds, liens, sortie = _noeuds(materiau)
    transparent = noeuds.new("ShaderNodeBsdfTransparent")
    reflet = noeuds.new("ShaderNodeBsdfGlossy")
    reflet.inputs["Roughness"].default_value = 0.02
    melange = noeuds.new("ShaderNodeMixShader")
    melange.inputs["Fac"].default_value = 0.06
    liens.new(transparent.outputs["BSDF"], melange.inputs[1])
    liens.new(reflet.outputs["BSDF"], melange.inputs[2])
    liens.new(melange.outputs["Shader"], sortie.inputs["Surface"])
    materiau.diffuse_color = (0.6, 0.75, 0.8, 0.3)


def _melange_multiplier(noeuds):
    melange = noeuds.new("ShaderNodeMix")
    melange.data_type = "RGBA"
    melange.blend_type = "MULTIPLY"
    melange.inputs["Factor"].default_value = 1.0
    return melange


def _entree(noeud, nom):
    # Le nœud « Mix » a plusieurs entrées du même nom (nombre, vecteur, couleur) :
    # on prend celle qui est une couleur.
    return next(s for s in noeud.inputs if s.name == nom and s.type == "RGBA")


def _sortie(noeud, nom):
    return next(s for s in noeud.outputs if s.name == nom and s.type == "RGBA")
