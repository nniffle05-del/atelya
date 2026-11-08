"""Matériaux « procéduraux » de la maquette, lus par Blender.

Procédural veut dire : dessinés par un petit calcul (des lames de bois, une
grille de carreaux) au lieu d'une photo de texture. Rien à télécharger, et
ça reste net de près. Les tailles sont en mètres : une lame de parquet fait
1,20 m × 0,15 m, un carreau 0,60 m × 0,60 m.

Chaque matériau est un petit réseau de « nœuds » (des boîtes reliées entre
elles, comme dans l'éditeur de Blender), construit ici par programme.

B2-3 (08/11/2026) : les SOLS sont de vraies matières, peintes avec les photos de la bibliothèque CC0
(..\\atelya\\bibliotheque\\matieres : couleur, relief et brillance de chaque matière, et sa taille réelle dans matieres.json).
Chaque photo est posée en « projection boîte » (vue d'en haut sur les sols, de face sur les côtés), à sa taille réelle, toutes
dans le même sens (`orientation` : le parquet suit le grand côté du logement, sans changer de sens d'une pièce à l'autre). Le
point de Hongrie et les carreaux de ciment sont dessinés par calcul (le premier avec le chêne clair de la bibliothèque). Les
murs et plafonds prennent le grain d'un enduit. Les photos sont rangées DANS la maquette (.blend) : elle reste complète si on
la déplace. Sans bibliothèque (Mac, tests) : l'ancien parquet ou carrelage dessiné par calcul, selon la sorte de la matière.
"""

import json
import math
from pathlib import Path

import bpy

# La sorte de chaque matière de sol (même liste que moteur/matieres.py, que ce script ne peut pas importer).
SORTES = {"parquet_chene_lames": "bois", "parquet_batons_rompus": "bois", "point_de_hongrie": "bois", "stratifie": "bois",
          "carrelage_interieur": "carrelage", "carreaux_ciment": "carrelage", "tomettes": "carrelage",
          "damier_pierre": "carrelage", "pierre_beige": "carrelage"}
# Photos dont les carreaux sont en biais : tournées pour que les joints suivent les murs (même liste que moteur/matieres.py).
ROTATION_PHOTO = {"carrelage_interieur": 45.0}
COULEUR_PEINTURE = (0.86, 0.85, 0.82)


class Materiaux(dict):
    """Les matériaux de la maquette, créés à la demande par leur nom (les sols : seulement ceux du logement)."""

    def __init__(self, bibliotheque=None, orientation=0.0):
        super().__init__()
        self.bibliotheque = Path(bibliotheque) if bibliotheque else None
        self.fiches = {}
        if self.bibliotheque and (self.bibliotheque / "matieres.json").is_file():
            self.fiches = json.loads((self.bibliotheque / "matieres.json").read_text(encoding="utf-8"))
        else:
            self.bibliotheque = None
        self.orientation = orientation

    def __missing__(self, nom):
        materiau = bpy.data.materials.new(nom)
        materiau.use_nodes = True
        _FABRIQUES.get(nom, _sol)(materiau, self)
        self[nom] = materiau
        return materiau

    def photo(self, nom):
        """(dossier, taille en m) d'une matière de la bibliothèque, ou None."""
        if self.bibliotheque is None or nom not in self.fiches or not (self.bibliotheque / nom / "couleur.jpg").is_file():
            return None
        taille = (self.fiches[nom].get("taille_image_m") or [1.0, 1.0])[0]
        return self.bibliotheque / nom, taille


def creer_materiaux(bibliotheque=None, orientation=0.0) -> dict:
    """Les matériaux connus, créés à la demande quand une brique les demande par leur nom."""
    return Materiaux(bibliotheque, orientation)


def _peinture(couleur, rugosite):
    def fabrique(materiau, m):
        if m.photo("enduit_peint_blanc") is None:
            return _uni(materiau, couleur, rugosite)
        _enduit(materiau, m, couleur)
    return fabrique


def _sol(materiau, m):
    """Une matière de sol : photo de la bibliothèque, ou dessin par calcul (point de Hongrie, carreaux de ciment).

    Un nom « matiere~r,g,b » porte une teinte : la couleur est multipliée par ces trois nombres (rouge, vert, bleu), pour
    rapprocher la matière de ce que montrent les photos du client."""
    nom, _, gains = materiau.name.partition("~")
    if nom == "carreaux_ciment":
        _carreaux_ciment(materiau, m)
    elif nom == "point_de_hongrie" and m.photo("chene_clair"):
        _point_de_hongrie(materiau, m)
    elif m.photo(nom):
        _photo(materiau, m, nom)
    else:
        (_carrelage if SORTES.get(nom, "carrelage" if "carrel" in nom else "bois") == "carrelage" else _parquet)(materiau)
    if gains:
        _teinter(materiau, [float(g) for g in gains.split(",")])


def _teinter(materiau, gains):
    """Multiplie la couleur de base du matériau par (rouge, vert, bleu)."""
    arbre = materiau.node_tree
    bsdf = next(n for n in arbre.nodes if n.type == "BSDF_PRINCIPLED")
    entree = bsdf.inputs["Base Color"]
    melange = _melange_multiplier(arbre.nodes)
    couleur = arbre.nodes.new("ShaderNodeRGB")
    couleur.outputs[0].default_value = (*gains, 1.0)
    if entree.is_linked:
        arbre.links.new(entree.links[0].from_socket, _entree(melange, "A"))
    else:
        _entree(melange, "A").default_value = entree.default_value
    arbre.links.new(couleur.outputs[0], _entree(melange, "B"))
    arbre.links.new(_sortie(melange, "Result"), entree)
    materiau.diffuse_color = tuple(min(1.0, c * g) for c, g in zip(materiau.diffuse_color[:3], gains)) + (1.0,)


def _fabriques_simples():
    return {
        "mur_blanc": _peinture(COULEUR_PEINTURE, 0.9),
        "plafond_blanc": _peinture((0.9, 0.9, 0.9), 0.95),
        "menuiserie_blanche": lambda m, _: _uni(m, (0.92, 0.92, 0.91), rugosite=0.35),
        "porte_interieure": lambda m, _: _uni(m, (0.88, 0.87, 0.84), rugosite=0.45),
        "porte_entree": lambda m, _: _uni(m, (0.12, 0.13, 0.14), rugosite=0.4),
        "metal": lambda m, _: _uni(m, (0.75, 0.75, 0.76), rugosite=0.25, metal=1.0),
        "seuil": lambda m, _: _uni(m, (0.55, 0.53, 0.5), rugosite=0.6),
        "parquet": lambda m, _: _parquet(m),
        "carrelage": lambda m, _: _carrelage(m),
        "verre": lambda m, _: _verre(m),
    }


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


_FABRIQUES = _fabriques_simples()


# ---------------------------------------------------------------- B2-3 : photos de vraies matières


def _image(chemin, couleur):
    image = bpy.data.images.load(str(Path(chemin).resolve()), check_existing=True)
    if not couleur:
        image.colorspace_settings.name = "Non-Color"
    if not image.packed_file:
        image.pack()  # rangée dans le .blend : la maquette reste complète si on la déplace
    return image


def _tourne(noeuds, liens, m, en_plus=0.0):
    """La position réelle du point (m, les objets sont posés à l'origine), tournée dans le sens des sols (+ en_plus degrés)."""
    coord = noeuds.new("ShaderNodeTexCoord")
    tourne = noeuds.new("ShaderNodeVectorRotate")
    tourne.rotation_type = "Z_AXIS"
    tourne.inputs["Angle"].default_value = -m.orientation + math.radians(en_plus)
    liens.new(coord.outputs["Object"], tourne.inputs["Vector"])
    return coord, tourne.outputs["Vector"]


def _coordonnees(noeuds, liens, m, taille, en_plus=0.0):
    """Les coordonnées d'une photo : position réelle, tournée dans le sens des sols, à la taille réelle de la photo."""
    _, vecteur = _tourne(noeuds, liens, m, en_plus)
    echelle = noeuds.new("ShaderNodeMapping")
    echelle.inputs["Scale"].default_value = (1 / taille, 1 / taille, 1 / taille)
    liens.new(vecteur, echelle.inputs["Vector"])
    return echelle.outputs["Vector"]


def _texture(noeuds, liens, chemin, couleur, vecteur):
    tex = noeuds.new("ShaderNodeTexImage")
    tex.image = _image(chemin, couleur)
    tex.projection = "BOX"  # vue d'en haut sur un sol, de face sur les côtés (plinthes)
    tex.projection_blend = 0.15
    liens.new(vecteur, tex.inputs["Vector"])
    return tex


def _photo(materiau, m, nom):
    """Couleur, relief et brillance d'une photo de la bibliothèque, à sa taille réelle."""
    dossier, taille = m.photo(nom)
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.5)
    vecteur = _coordonnees(noeuds, liens, m, taille, ROTATION_PHOTO.get(nom, 0.0))
    couleur = _texture(noeuds, liens, dossier / "couleur.jpg", True, vecteur)
    liens.new(couleur.outputs["Color"], bsdf.inputs["Base Color"])
    if (dossier / "brillance.jpg").is_file():
        brillance = _texture(noeuds, liens, dossier / "brillance.jpg", False, vecteur)
        liens.new(brillance.outputs["Color"], bsdf.inputs["Roughness"])
    if (dossier / "relief.jpg").is_file():
        relief = _texture(noeuds, liens, dossier / "relief.jpg", False, vecteur)
        normale = noeuds.new("ShaderNodeNormalMap")
        normale.inputs["Strength"].default_value = 1.0
        liens.new(relief.outputs["Color"], normale.inputs["Color"])
        liens.new(normale.outputs["Normal"], bsdf.inputs["Normal"])
    materiau.diffuse_color = (0.5, 0.4, 0.3, 1.0) if SORTES.get(nom) == "bois" else (0.75, 0.73, 0.7, 1.0)


def _enduit(materiau, m, couleur):
    """Une peinture sur enduit : la couleur choisie, le grain et la brillance d'un vrai enduit (sans sa couleur tachée)."""
    dossier, taille = m.photo("enduit_peint_blanc")
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.9)
    bsdf.inputs["Base Color"].default_value = (*couleur, 1.0)
    vecteur = _coordonnees(noeuds, liens, m, taille)
    brillance = _texture(noeuds, liens, dossier / "brillance.jpg", False, vecteur)
    resserre = noeuds.new("ShaderNodeMapRange")  # une peinture mate : rugosité entre 0,8 et 0,95
    resserre.inputs["To Min"].default_value = 0.8
    resserre.inputs["To Max"].default_value = 0.95
    liens.new(brillance.outputs["Color"], resserre.inputs["Value"])
    liens.new(resserre.outputs["Result"], bsdf.inputs["Roughness"])
    relief = _texture(noeuds, liens, dossier / "relief.jpg", False, vecteur)
    normale = noeuds.new("ShaderNodeNormalMap")
    normale.inputs["Strength"].default_value = 0.25  # un grain discret
    liens.new(relief.outputs["Color"], normale.inputs["Color"])
    liens.new(normale.outputs["Normal"], bsdf.inputs["Normal"])
    materiau.diffuse_color = (*couleur, 1.0)


def _math(noeuds, liens, operation, a, b=None, valeur_b=None):
    """Un nœud de calcul : operation(a, b). a et b sont des sorties de nœuds ou des nombres."""
    n = noeuds.new("ShaderNodeMath")
    n.operation = operation
    _brancher(liens, n.inputs[0], a)
    if b is not None:
        _brancher(liens, n.inputs[1], b)
    elif valeur_b is not None:
        n.inputs[1].default_value = valeur_b
    return n.outputs[0]


def _brancher(liens, entree, valeur):
    if isinstance(valeur, (int, float)):
        entree.default_value = valeur
    else:
        liens.new(valeur, entree)


def _gris(noeuds, liens, valeur):
    """Une couleur grise dont les trois canaux valent `valeur` (pour teinter par multiplication)."""
    gris = noeuds.new("ShaderNodeCombineColor")
    for canal in ("Red", "Green", "Blue"):
        _brancher(liens, gris.inputs[canal], valeur)
    return gris.outputs["Color"]


def _point_de_hongrie(materiau, m):
    """Le point de Hongrie : des lames coupées en biais (45°), en colonnes qui changent de sens, comme des chevrons.

    Dans chaque colonne (largeur = la lame vue de face), les lames sont parallèles, penchées d'un côté puis de l'autre
    d'une colonne à la suivante. Chaque lame prend un morceau différent de la photo du chêne clair, et une nuance à elle."""
    dossier, taille = m.photo("chene_clair")
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.45)
    longueur, largeur, joint = 0.50, 0.09, 0.002
    c45 = math.cos(math.radians(45))
    colonne_l = longueur * c45
    pas = largeur / c45  # écart vertical entre deux joints d'une même colonne

    _, vecteur = _tourne(noeuds, liens, m)
    xyz = noeuds.new("ShaderNodeSeparateXYZ")
    liens.new(vecteur, xyz.inputs[0])
    x, y = xyz.outputs["X"], xyz.outputs["Y"]

    col = _math(noeuds, liens, "FLOOR", _math(noeuds, liens, "DIVIDE", x, valeur_b=colonne_l))
    xl = _math(noeuds, liens, "SUBTRACT", x, _math(noeuds, liens, "MULTIPLY", col, valeur_b=colonne_l))
    pair = _math(noeuds, liens, "FLOORED_MODULO", col, valeur_b=2.0)
    sens = _math(noeuds, liens, "SUBTRACT", 1.0, _math(noeuds, liens, "MULTIPLY", pair, valeur_b=2.0))
    v = _math(noeuds, liens, "SUBTRACT", y, _math(noeuds, liens, "MULTIPLY", sens, xl))
    rang = _math(noeuds, liens, "FLOOR", _math(noeuds, liens, "DIVIDE", v, valeur_b=pas))
    fv = _math(noeuds, liens, "FRACT", _math(noeuds, liens, "DIVIDE", v, valeur_b=pas))

    # un tirage au hasard par lame (colonne, rang) : décalage dans la photo et nuance
    lame = noeuds.new("ShaderNodeCombineXYZ")
    liens.new(col, lame.inputs["X"])
    liens.new(rang, lame.inputs["Y"])
    hasard = noeuds.new("ShaderNodeTexWhiteNoise")
    hasard.noise_dimensions = "3D"
    liens.new(lame.outputs["Vector"], hasard.inputs["Vector"])
    alea = noeuds.new("ShaderNodeSeparateXYZ")
    liens.new(hasard.outputs["Color"], alea.inputs[0])

    # coordonnées dans la photo : en travers de la lame (x de la photo) et le long du fil (y de la photo)
    le_long = _math(noeuds, liens, "DIVIDE", xl, valeur_b=c45)
    en_travers = _math(noeuds, liens, "MULTIPLY", fv, valeur_b=largeur)
    uv = noeuds.new("ShaderNodeCombineXYZ")
    liens.new(_math(noeuds, liens, "DIVIDE", _math(noeuds, liens, "ADD", en_travers,
                                                    _math(noeuds, liens, "MULTIPLY", alea.outputs["X"], valeur_b=1.6)),
                    valeur_b=taille), uv.inputs["X"])
    liens.new(_math(noeuds, liens, "DIVIDE", _math(noeuds, liens, "ADD", le_long,
                                                    _math(noeuds, liens, "MULTIPLY", alea.outputs["Y"], valeur_b=1.6)),
                    valeur_b=taille), uv.inputs["Y"])
    bois = noeuds.new("ShaderNodeTexImage")
    bois.image = _image(dossier / "couleur.jpg", True)
    liens.new(uv.outputs["Vector"], bois.inputs["Vector"])
    rugo = noeuds.new("ShaderNodeTexImage")
    rugo.image = _image(dossier / "brillance.jpg", False)
    liens.new(uv.outputs["Vector"], rugo.inputs["Vector"])
    liens.new(rugo.outputs["Color"], bsdf.inputs["Roughness"])

    # nuance par lame (±12 %) et joints sombres
    nuance = _math(noeuds, liens, "ADD", 0.88, _math(noeuds, liens, "MULTIPLY", alea.outputs["Z"], valeur_b=0.24))
    dans_joint = _math(noeuds, liens, "MAXIMUM", _math(noeuds, liens, "LESS_THAN", fv, valeur_b=joint / pas),
                       _math(noeuds, liens, "LESS_THAN", xl, valeur_b=joint))
    facteur = _math(noeuds, liens, "MULTIPLY", nuance,
                    _math(noeuds, liens, "SUBTRACT", 1.0, _math(noeuds, liens, "MULTIPLY", dans_joint, valeur_b=0.75)))
    teinte = _melange_multiplier(noeuds)
    liens.new(bois.outputs["Color"], _entree(teinte, "A"))
    liens.new(_gris(noeuds, liens, facteur), _entree(teinte, "B"))
    liens.new(_sortie(teinte, "Result"), bsdf.inputs["Base Color"])
    _relief(noeuds, liens, _math(noeuds, liens, "SUBTRACT", 1.0, dans_joint), bsdf, force=0.4)
    materiau.diffuse_color = (0.62, 0.45, 0.3, 1.0)


def _carreaux_ciment(materiau, m):
    """Des carreaux de ciment de 20 cm : un motif de losanges et d'anneaux, gris anthracite et gris bleu sur fond crème."""
    noeuds, liens, sortie = _noeuds(materiau)
    bsdf = _principled(noeuds, liens, sortie, rugosite=0.55)
    cote = 0.20
    coord, vecteur = _tourne(noeuds, liens, m)
    xyz = noeuds.new("ShaderNodeSeparateXYZ")
    liens.new(vecteur, xyz.inputs[0])

    def local(axe):  # de -0,5 à 0,5 dans le carreau
        return _math(noeuds, liens, "SUBTRACT", _math(noeuds, liens, "FRACT",
                                                       _math(noeuds, liens, "DIVIDE", axe, valeur_b=cote)), valeur_b=0.5)
    tx, ty = local(xyz.outputs["X"]), local(xyz.outputs["Y"])
    ax, ay = _math(noeuds, liens, "ABSOLUTE", tx), _math(noeuds, liens, "ABSOLUTE", ty)
    carre = _math(noeuds, liens, "MAXIMUM", ax, ay)
    petit = _math(noeuds, liens, "MINIMUM", ax, ay)
    losange = _math(noeuds, liens, "ADD", ax, ay)  # |x| + |y|
    # distance au coin le plus proche : quatre carreaux voisins y dessinent ensemble un cercle et un disque
    cx = _math(noeuds, liens, "SUBTRACT", 0.5, ax)
    cy = _math(noeuds, liens, "SUBTRACT", 0.5, ay)
    coin = _math(noeuds, liens, "SQRT", _math(noeuds, liens, "ADD", _math(noeuds, liens, "MULTIPLY", cx, cx),
                                              _math(noeuds, liens, "MULTIPLY", cy, cy)))
    disque = _math(noeuds, liens, "LESS_THAN", coin, valeur_b=0.15)
    arc = _math(noeuds, liens, "MULTIPLY", _math(noeuds, liens, "GREATER_THAN", coin, valeur_b=0.30),
                _math(noeuds, liens, "LESS_THAN", coin, valeur_b=0.37))
    # au centre : une étoile à quatre branches (croix fine qui s'affine) et un losange rouge
    branche = _math(noeuds, liens, "LESS_THAN", petit,
                    _math(noeuds, liens, "MULTIPLY", _math(noeuds, liens, "SUBTRACT", 0.30, carre), valeur_b=0.35))
    etoile = _math(noeuds, liens, "MULTIPLY", branche, _math(noeuds, liens, "LESS_THAN", carre, valeur_b=0.30))
    coeur = _math(noeuds, liens, "LESS_THAN", losange, valeur_b=0.09)
    joint = _math(noeuds, liens, "GREATER_THAN", carre, valeur_b=0.493)

    def couleur(c):
        n = noeuds.new("ShaderNodeRGB")
        n.outputs[0].default_value = (*c, 1.0)
        return n.outputs[0]

    def melange(facteur, a, b):
        n = noeuds.new("ShaderNodeMix")
        n.data_type = "RGBA"
        liens.new(facteur, n.inputs["Factor"])
        liens.new(a, _entree(n, "A"))
        liens.new(b, _entree(n, "B"))
        return _sortie(n, "Result")

    c = melange(arc, couleur((0.78, 0.75, 0.68)), couleur((0.30, 0.38, 0.44)))
    c = melange(disque, c, couleur((0.10, 0.11, 0.12)))
    c = melange(etoile, c, couleur((0.10, 0.11, 0.12)))
    c = melange(coeur, c, couleur((0.50, 0.20, 0.15)))
    c = melange(joint, c, couleur((0.55, 0.54, 0.51)))
    # un léger voile irrégulier : le ciment n'est jamais parfaitement uni
    voile = noeuds.new("ShaderNodeTexNoise")
    voile.inputs["Scale"].default_value = 18.0
    liens.new(coord.outputs["Object"], voile.inputs["Vector"])
    plage = noeuds.new("ShaderNodeMapRange")
    plage.inputs["To Min"].default_value = 0.92
    plage.inputs["To Max"].default_value = 1.05
    liens.new(voile.outputs["Fac"], plage.inputs["Value"])
    teinte = _melange_multiplier(noeuds)
    liens.new(c, _entree(teinte, "A"))
    liens.new(_gris(noeuds, liens, plage.outputs["Result"]), _entree(teinte, "B"))
    liens.new(_sortie(teinte, "Result"), bsdf.inputs["Base Color"])
    _relief(noeuds, liens, _math(noeuds, liens, "SUBTRACT", 1.0, joint), bsdf, force=0.4)
    materiau.diffuse_color = (0.6, 0.58, 0.54, 1.0)
