"""Le modèle 3D d'un logement inventé, construit depuis la même géométrie que le plan.

On réutilise le moteur existant : chaque niveau est écrit au format logement/0.1, puis
moteur/geometrie.py le découpe en « briques » (morceaux de murs autour des ouvertures, allèges,
linteaux, sols, plafonds, seuils) et moteur/habillage.py ajoute les menuiseries (cadres, vitres,
battants) et les matériaux. Ce module :

- empile les niveaux d'un duplex (l'étage posé à hauteur sous plafond + plancher) ;
- enlève le plafond au-dessus de l'escalier et le sol de la trémie à l'étage, et pose des marches ;
- écrit le tout en GLB (glTF binaire, lisible par Blender, Unreal, three.js…), en OBJ, et au
  format construction/0.2 (le JSON que lit moteur/blender/poser_briques.py).

Les deux exports sont écrits par notre propre code (struct + json) : aucune bibliothèque 3D à
installer. Le GLB contient un nœud par élément (mur, ouverture, pièce), qui porte l'identifiant du
geometrie.json : la 2D et la 3D parlent des mêmes objets.

Repère glTF : y vers le haut. On convertit : (x, y_nord, z) du logement → (x, z, -y_nord).
"""

from __future__ import annotations

import json
import struct
from dataclasses import replace
from pathlib import Path

from moteur.generateur.logements import LogementGenere, Niveau, en_logement
from moteur.geometrie import Brique, _sens_direct
from moteur.habillage import plan_habille
from moteur.logement import Logement

VERSION_PLAN = "construction/0.2"

COULEURS = {  # matériau → (R, G, B, alpha), couleurs de base du GLB
    "mur": (0.92, 0.91, 0.88, 1.0), "mur_blanc": (0.92, 0.91, 0.88, 1.0), "plafond": (0.96, 0.96, 0.95, 1.0),
    "parquet": (0.72, 0.52, 0.32, 1.0), "carrelage": (0.80, 0.80, 0.78, 1.0), "seuil": (0.6, 0.6, 0.6, 1.0),
    "menuiserie_blanche": (0.95, 0.95, 0.95, 1.0), "verre": (0.6, 0.8, 0.95, 0.35),
    "porte_interieure": (0.85, 0.80, 0.70, 1.0), "porte_entree": (0.35, 0.30, 0.28, 1.0), "metal": (0.6, 0.6, 0.62, 1.0),
    "marche": (0.65, 0.48, 0.30, 1.0),
}


def briques_du_logement(log: LogementGenere) -> list[dict]:
    """Toutes les briques du logement (tous niveaux), avec leurs altitudes absolues, en dicts construction/0.2."""
    resultat: list[dict] = []
    for niveau in log.niveaux:
        logement = Logement.model_validate(en_logement(log, niveau))
        plan = plan_habille(logement)
        z0 = niveau.z_sol / 1000
        escaliers = {p.id for p in niveau.pieces if p.sorte == "escalier"}
        for b in plan["briques"]:
            if b["element"] in escaliers:
                if niveau.index == 0 and b["categorie"] == "plafond":
                    continue  # la trémie : pas de plafond au-dessus de l'escalier
                if niveau.index > 0 and b["categorie"] == "sol":
                    continue  # ni de sol à l'étage à cet endroit
            b = dict(b)
            b["id"] = f"n{niveau.index}__{b['id']}" if log.duplex else b["id"]
            b["niveau"] = niveau.index
            b["z_bas"] = round(b["z_bas"] + z0, 6)
            b["z_haut"] = round(b["z_haut"] + z0, 6)
            resultat.append(b)
        if log.duplex and niveau.index == 0:
            resultat += marches(log, niveau)
    return resultat


def marches(log: LogementGenere, niveau: Niveau) -> list[dict]:
    """Les marches d'un escalier droit : des boîtes de plus en plus hautes, jusqu'au plancher de l'étage."""
    esc = next((p for p in niveau.pieces if p.sorte == "escalier"), None)
    if esc is None:
        return []
    r = esc.rect
    le_long_de_x = r.largeur >= r.hauteur
    longueur = (r.largeur if le_long_de_x else r.hauteur) / 1000
    montee = (niveau.hsp + log.plancher) / 1000
    n = max(2, round(montee / 0.18))
    giron = longueur / n
    briques = []
    for k in range(n):
        if le_long_de_x:
            x0, x1 = r.x0 / 1000 + k * giron, r.x0 / 1000 + (k + 1) * giron
            contour = [(x0, r.y0 / 1000), (x1, r.y0 / 1000), (x1, r.y1 / 1000), (x0, r.y1 / 1000)]
        else:
            y0, y1 = r.y0 / 1000 + k * giron, r.y0 / 1000 + (k + 1) * giron
            contour = [(r.x0 / 1000, y0), (r.x1 / 1000, y0), (r.x1 / 1000, y1), (r.x0 / 1000, y1)]
        briques.append({"id": f"marche_{k + 1}", "categorie": "menuiserie", "element": esc.id,
                        "contour": [[round(x, 6), round(y, 6)] for x, y in _sens_direct(contour)],
                        "z_bas": 0.0, "z_haut": round(montee * (k + 1) / n, 6), "materiau": "marche", "niveau": 0})
    return briques


def plan_de_construction(log: LogementGenere) -> dict:
    """Le JSON construction/0.2 de tout le logement, lisible par moteur/blender/poser_briques.py."""
    return {"schema": VERSION_PLAN, "projet_id": f"SYNTHESE-{log.graine:06d}", "briques": briques_du_logement(log),
            "lumieres": [], "vues": []}


# ---------------------------------------------------------------- maillage


def _maillage(brique: dict) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Les sommets (repère glTF, y vers le haut) et les triangles d'une brique (prisme droit ou surface)."""
    contour = [tuple(p) for p in brique["contour"]]
    zb, zh = brique["z_bas"], brique["z_haut"]
    n = len(contour)
    if abs(zh - zb) < 1e-9:  # une surface (sol, plafond) : deux faces pour être visible des deux côtés
        sommets = [(x, zb, -y) for x, y in contour]
        tris = [(0, i, i + 1) for i in range(1, n - 1)]
        return sommets, tris + [(a, c, b) for a, b, c in tris]
    bas = [(x, zb, -y) for x, y in contour]
    haut = [(x, zh, -y) for x, y in contour]
    sommets = bas + haut
    tris = []
    # Contour dans le sens direct vu de dessus (y_nord), donc, vu d'en haut en glTF (y vers le haut), les
    # faces latérales (bas_i, bas_{i+1}, haut_{i+1}, haut_i) tournent vers l'extérieur.
    for i in range(n):
        j = (i + 1) % n
        tris += [(i, j, n + j), (i, n + j, n + i)]
    for i in range(1, n - 1):  # dessus (vers +y) et dessous
        tris.append((n, n + i + 1, n + i))
        tris.append((0, i, i + 1))
    return sommets, tris


def _nom_du_noeud(brique: dict) -> str:
    return brique["element"]


def ecrire_glb(log: LogementGenere, chemin: Path, briques: list[dict] | None = None) -> dict:
    """Écrit le GLB ; renvoie un petit bilan (nombre de nœuds, triangles, octets)."""
    briques = briques if briques is not None else briques_du_logement(log)
    # Un nœud par élément du logement (mur, ouverture, pièce) ; dans chaque nœud, une primitive par matériau.
    groupes: dict[str, dict[str, tuple[list, list]]] = {}
    for b in briques:
        verts, tris = _maillage(b)
        sommets, triangles = groupes.setdefault(_nom_du_noeud(b), {}).setdefault(b["materiau"] or "mur", ([], []))
        base = len(sommets)
        sommets.extend(verts)
        triangles.extend((a + base, b_ + base, c + base) for a, b_, c in tris)

    materiaux = sorted({m for g in groupes.values() for m in g})
    index_materiau = {m: i for i, m in enumerate(materiaux)}
    bin_ = bytearray()
    accessors, buffer_views, meshes, nodes = [], [], [], []

    def ajouter_vue(donnees: bytes, cible: int) -> int:
        while len(bin_) % 4:
            bin_.append(0)
        buffer_views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(donnees), "target": cible})
        bin_.extend(donnees)
        return len(buffer_views) - 1

    n_triangles = 0
    for nom, prims in groupes.items():
        primitives = []
        for materiau, (sommets, triangles) in prims.items():
            xs = [s[0] for s in sommets]
            ys = [s[1] for s in sommets]
            zs = [s[2] for s in sommets]
            pos = struct.pack(f"<{3 * len(sommets)}f", *[c for s in sommets for c in s])
            vue_pos = ajouter_vue(pos, 34962)
            accessors.append({"bufferView": vue_pos, "componentType": 5126, "count": len(sommets), "type": "VEC3",
                              "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
            i_pos = len(accessors) - 1
            idx = [i for t in triangles for i in t]
            if len(sommets) < 65536:
                ind = struct.pack(f"<{len(idx)}H", *idx)
                comp = 5123
            else:
                ind = struct.pack(f"<{len(idx)}I", *idx)
                comp = 5125
            vue_ind = ajouter_vue(ind, 34963)
            accessors.append({"bufferView": vue_ind, "componentType": comp, "count": len(idx), "type": "SCALAR"})
            primitives.append({"attributes": {"POSITION": i_pos}, "indices": len(accessors) - 1,
                               "material": index_materiau[materiau], "mode": 4})
            n_triangles += len(triangles)
        meshes.append({"name": nom, "primitives": primitives})
        nodes.append({"name": nom, "mesh": len(meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "moteur-3d/generateur", "extras": {"identifiant": f"SYNTHESE-{log.graine:06d}"}},
        "scene": 0,
        "scenes": [{"name": f"SYNTHESE-{log.graine:06d}", "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": [
            {"name": m, "pbrMetallicRoughness": {"baseColorFactor": list(COULEURS.get(m, (0.8, 0.8, 0.8, 1.0))),
                                                 "metallicFactor": 0.0, "roughnessFactor": 0.8},
             "doubleSided": True, **({"alphaMode": "BLEND"} if COULEURS.get(m, (0, 0, 0, 1))[3] < 1 else {})}
            for m in materiaux
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_)}],
    }
    json_octets = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_octets) % 4:
        json_octets += b" "
    while len(bin_) % 4:
        bin_.append(0)
    total = 12 + 8 + len(json_octets) + 8 + len(bin_)
    with open(chemin, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(json_octets), 0x4E4F534A))
        f.write(json_octets)
        f.write(struct.pack("<II", len(bin_), 0x004E4942))
        f.write(bin_)
    return {"noeuds": len(nodes), "triangles": n_triangles, "materiaux": len(materiaux), "octets": total}


def ecrire_obj(log: LogementGenere, chemin: Path, briques: list[dict] | None = None) -> None:
    """Écrit un OBJ (texte) avec un objet par élément et un matériau par brique ; repère y vers le haut."""
    briques = briques if briques is not None else briques_du_logement(log)
    lignes = [f"# SYNTHESE-{log.graine:06d} — moteur-3d/generateur", "mtllib materiaux.mtl"]
    base = 1
    courant = None
    for b in briques:
        verts, tris = _maillage(b)
        if b["element"] != courant:
            courant = b["element"]
            lignes.append(f"o {courant}")
        lignes.append(f"usemtl {b['materiau'] or 'mur'}")
        lignes.extend(f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts)
        lignes.extend(f"f {a + base} {b_ + base} {c + base}" for a, b_, c in tris)
        base += len(verts)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    mtl = []
    for m, (r, g, b_, a) in COULEURS.items():
        mtl += [f"newmtl {m}", f"Kd {r:.3f} {g:.3f} {b_:.3f}", f"d {a:.2f}", ""]
    (chemin.parent / "materiaux.mtl").write_text("\n".join(mtl), encoding="utf-8")


def lire_glb(chemin: Path) -> dict:
    """Relit l'en-tête et le JSON d'un GLB (pour les contrôles) ; lève une erreur s'il est corrompu."""
    donnees = Path(chemin).read_bytes()
    magic, version, longueur = struct.unpack_from("<III", donnees, 0)
    if magic != 0x46546C67 or version != 2 or longueur != len(donnees):
        raise ValueError(f"GLB invalide : {chemin}")
    taille_json, type_json = struct.unpack_from("<II", donnees, 12)
    if type_json != 0x4E4F534A:
        raise ValueError(f"GLB sans bloc JSON : {chemin}")
    gltf = json.loads(donnees[20:20 + taille_json].decode("utf-8"))
    taille_bin, type_bin = struct.unpack_from("<II", donnees, 20 + taille_json)
    if type_bin != 0x004E4942 or gltf["buffers"][0]["byteLength"] != taille_bin:
        raise ValueError(f"GLB : bloc binaire incohérent : {chemin}")
    return gltf


def emprise_des_murs(briques: list[dict]) -> float:
    """La surface au sol (m²) des morceaux de murs du niveau 0, pour comparer 2D et 3D."""
    total = 0.0
    for b in briques:
        if b["categorie"] == "mur" and b.get("niveau", 0) == 0 and b["z_bas"] < 1e-9:
            c = b["contour"]
            aire = 0.0
            for (x1, y1), (x2, y2) in zip(c, c[1:] + c[:1]):
                aire += x1 * y2 - x2 * y1
            total += abs(aire) / 2
    return total
