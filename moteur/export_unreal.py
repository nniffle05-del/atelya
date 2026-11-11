"""Atelya → Unreal Engine 5 : le paquet d'une maquette (11/11/2026).

Pourquoi : décision NT du 10/11/2026, le produit est le TEMPS RÉEL (cinématique, puis visite libre) et Unreal Engine 5 en est le
studio ; Blender reste l'atelier automatique qui construit le logement. Unreal ne lit pas les fichiers .blend : Atelya lui
prépare un PAQUET, sans aucune intervention à la main (règle n° 21 : le bon résultat sort seul de la chaîne) :

    <sortie>/maquette.gltf (+ .bin, textures/)   la FORME : murs, sols, plafonds, menuiseries, linge, meubles ABO posés,
                                                  chaque surface avec sa matière (moteur/blender/exporter_gltf.py) ;
    <sortie>/scene-atelya.json                    la FICHE DE SCÈNE : tout ce que glTF ne transporte pas ou transporte mal
                                                  (vraies matières à leur taille réelle, teintes réglées, lumières, les cinq
                                                  éclairages, meubles, vues, crédits), pour reconstruire la scène nativement
                                                  dans Unreal ;
    <sortie>/matieres/<matière>/*.jpg             les photos des matières utilisées (bibliothèque CC0), pour les matériaux
                                                  natifs d'Unreal (placage « monde », à la taille réelle).

Repère : la fiche garde celui d'Atelya (mètres, x et y au sol, z vers le haut). glTF est en « y vers le haut » (Blender convertit
à l'export) ; Unreal compte en centimètres. La conversion côté Unreal sera vérifiée sur la première scène importée (Unreal n'est
pas encore installé au 11/11/2026).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from moteur.matieres import CALCULEES, echelle_du_nom, matiere_et_teinte

SCHEMA = "scene-unreal/0.1"

# Les mêmes valeurs que moteur/blender/materiaux.py (que ce module ne peut pas importer : il exige Blender) ; un test vérifie
# qu'elles restent d'accord.
COULEUR_PEINTURE = (0.86, 0.85, 0.82)
RUGOSITE_BOIS = (0.6, 0.85)
REFLET_BOIS = 0.15
ROTATION_PHOTO = {"carrelage_interieur": 45.0}
RUGOSITE_PEINTURE = (0.8, 0.95)  # moteur/blender/materiaux._enduit : une peinture mate
RELIEF_PEINTURE = 0.25
ALPHA_VERRE = 0.06  # moteur/blender/exporter_gltf.ALPHA_VERRE
UNIES = {  # nom : (couleur, rugosité, métal)
    "menuiserie_blanche": ((0.92, 0.92, 0.91), 0.35, 0.0),
    "porte_interieure": ((0.88, 0.87, 0.84), 0.45, 0.0),
    "porte_entree": ((0.12, 0.13, 0.14), 0.4, 0.0),
    "metal": ((0.75, 0.75, 0.76), 0.25, 1.0),
    "seuil": ((0.55, 0.53, 0.5), 0.6, 0.0),
}
PEINTURES = {"mur_blanc": COULEUR_PEINTURE, "plafond_blanc": (0.9, 0.9, 0.9)}
# Motifs dessinés par calcul dans Blender (moteur/blender/materiaux.py) : leurs dimensions, pour les refaire ou les cuire.
DESSINS = {
    "point_de_hongrie": {"lame_m": [0.50, 0.09], "joint_m": 0.002, "angle_deg": 45.0,
                         "note": "lames coupées à 45°, colonnes qui changent de sens ; chaque lame prend un morceau différent "
                                 "de la photo du chêne clair, avec une nuance à elle"},
    "carreaux_ciment": {"carreau_m": 0.20,
                        "note": "losanges et anneaux gris anthracite et gris bleu sur fond crème"},
}
COULEUR_LAMPES_DEFAUT = (1.0, 0.82, 0.62)  # ≈ 2 700 K (moteur/eclairages.COULEUR_LAMPES)
LINGE = re.compile(r"^(Couette|Oreillers|Plaid)_(.+)$")
# Ce que chaque sorte de ciel devient dans Unreal (les noms des outils d'Unreal 5, à vérifier à l'installation).
CIEL_UNREAL = {
    "physique": "Sky Atmosphere + Directional Light (soleil, hauteur et direction de la fiche) + Sky Light en capture temps réel",
    "couvert": "Sky Light seule (ciel uniforme, couleur_couvert × force_couvert), sans soleil direct",
    "nuit": "fond uni très sombre (couleur_nuit) ; les plafonniers allumés (Rect Light) éclairent seuls",
}
PERTES = [
    {"quoi": "Lampes, soleil, ciel, caméras", "pourquoi": "non transportés par choix : Unreal a les siens, meilleurs pour le temps "
     "réel", "remede": "refaits d'après la fiche (lumieres, eclairages, vues)"},
    {"quoi": "Motifs dessinés par calcul (point de Hongrie, carreaux de ciment)", "pourquoi": "un calcul de Blender, que glTF ne "
     "sait pas décrire : ces sols partent avec leur photo de base (lames droites)", "remede": "à cuire en image répétable "
     "(chantier à part) ; dimensions dans la fiche (materiaux.*.dessin)"},
    {"quoi": "Placage des photos par position réelle", "pourquoi": "glTF ne connaît que les cartes UV", "remede": "FAIT à "
     "l'export : la carte UV « atelya_monde » est calculée comme Blender au rendu (même image avant/après)"},
    {"quoi": "Brillance réglée (parquet satiné, peinture mate)", "pourquoi": "un calcul de Blender", "remede": "FAIT à l'export : "
     "les images de brillance sont cuites déjà réglées"},
    {"quoi": "Verre (mélange transparent + reflet)", "pourquoi": "n'existe pas dans glTF : il partait opaque", "remede": "FAIT à "
     "l'export : verre à 94 % transparent ; dans Unreal, matériau verre natif conseillé (fiche : materiaux.verre)"},
    {"quoi": "Exposition et balance des blancs « de photographe »", "pourquoi": "réglage de la caméra Blender",
     "remede": "à refaire dans Unreal (exposition automatique ou réglée sur la clarté des murs : eclairages.*.clarte_murs)"},
]


def _lire(chemin: Path, defaut=None):
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else defaut


def _arrondi(v, n=4):
    return [round(float(x), n) for x in v] if v is not None else None


def teintes_reglees(construction: dict, reglages: list | None) -> dict:
    """La teinte FINALE de chaque matériau teinté : celle réglée au rendu (regler_teintes.py) si elle existe, sinon celle de son
    nom (« matiere~r,g,b »)."""
    finales = {r["materiau"]: r.get("teinte_finale") for r in (reglages or construction.get("reglages_teinte") or [])}
    return {k: v for k, v in finales.items() if v}


def fiche_materiau(nom: str, fiches_bibliotheque: dict, teintes: dict, orientation_deg: float, sortes: dict,
                   linge: dict) -> dict:
    """Comment refaire un matériau de la maquette dans Unreal (voir le module)."""
    if nom in PEINTURES:
        return {"genre": "peinture", "couleur": list(PEINTURES[nom]), "rugosite": list(RUGOSITE_PEINTURE),
                "grain": "enduit_peint_blanc", "relief_force": RELIEF_PEINTURE, "placage": "monde"}
    if nom in UNIES:
        couleur, rugosite, metal = UNIES[nom]
        return {"genre": "uni", "couleur": list(couleur), "rugosite": rugosite, "metal": metal}
    if nom == "verre":
        return {"genre": "verre", "alpha": ALPHA_VERRE, "rugosite": 0.02, "projette_ombre": False,
                "note": "dans Unreal : matériau translucide (ou « Thin Translucent »), qui laisse passer le soleil"}
    m = LINGE.match(nom)
    if m:
        couleur = linge.get(nom)
        return {"genre": "tissu", "piece_de_linge": m.group(1).lower(), "meuble": m.group(2),
                "couleur": _arrondi([c / 255 for c in couleur]) if couleur else None, "rugosite": 0.85, "voile": 0.5}
    matiere, gains = matiere_et_teinte(nom)
    if matiere in fiches_bibliotheque or matiere in CALCULEES:
        echelle = echelle_du_nom(nom)
        f = {"genre": "dessin" if matiere in CALCULEES else "photo", "matiere": matiere, "sorte": sortes.get(matiere, "bois"),
             "echelle": round(echelle, 3), "rotation_deg": round(orientation_deg + ROTATION_PHOTO.get(matiere, 0.0), 3),
             "teinte": _arrondi(teintes.get(nom) or gains), "placage": "monde : vu d'en haut sur les sols, de face sur les côtés"}
        base = CALCULEES.get(matiere, matiere) if matiere in CALCULEES else matiere
        if matiere in CALCULEES:
            f["dessin"] = DESSINS.get(matiere, {})
            f["a_cuire"] = True
        if base and base in fiches_bibliotheque:
            taille = fiches_bibliotheque[base].get("taille_image_m") or [1.0, 1.0]
            f["photos"] = {"dossier": f"matieres/{base}", "taille_m": _arrondi([t * echelle for t in taille], 3)}
            f["credit"] = base
        if f["sorte"] == "bois":
            f["rugosite"], f["reflet"] = list(RUGOSITE_BOIS), REFLET_BOIS
        return f
    return {"genre": "meuble", "note": "matériau d'un meuble ABO : ses images sont dans le glTF (couleur, brillance, relief)"}


def fiche_de_scene(dossier_3d: Path, export: dict, bibliotheque: Path | None, gltf: str = "maquette.gltf") -> dict:
    """La fiche de scène d'une maquette (dossier_3d : construction.json, eclairages.json, reglages_teinte.json)."""
    construction = _lire(dossier_3d / "construction.json", {})
    eclairages = _lire(dossier_3d / "eclairages.json", [])
    reglages = _lire(dossier_3d / "reglages_teinte.json")
    fiches = _lire(bibliotheque / "matieres.json", {}) if bibliotheque else {}
    orientation = float(construction.get("orientation_sols") or 0.0)
    teintes = teintes_reglees(construction, reglages)
    meubles = construction.get("meubles") or []
    linge = {}
    for m in meubles:
        lit = m.get("literie") or {}
        if lit.get("couette"):
            linge[f"Couette_{m['id']}"] = lit["couette"]
            linge[f"Oreillers_{m['id']}"] = lit.get("couleur_oreillers") or lit["couette"]
        if lit.get("plaid"):
            linge[f"Plaid_{m['id']}"] = lit["plaid"]
    materiaux = {nom: fiche_materiau(nom, fiches, teintes, orientation, construction.get("sortes_sols") or {}, linge)
                 for nom in export.get("materiaux", [])}

    lumieres = []
    for l in construction.get("lumieres") or []:
        if l["type"] == "soleil":
            lumieres.append({"genre": "soleil", "direction": l.get("direction"), "note": "direction vers laquelle va la lumière"})
        elif l["type"] == "plafonnier":
            lumieres.append({"genre": "plafonnier", "id": l["id"], "piece": l.get("piece"), "position": l["position"],
                             "taille_m": l.get("taille"), "puissance_w": l.get("puissance"),
                             "couleur": list(COULEUR_LAMPES_DEFAUT), "unreal": "Rect Light au plafond, vers le bas"})
        elif l["type"] == "portail":
            lumieres.append({"genre": "fenetre", "id": l["id"], "position": l["position"], "taille_m": l.get("taille"),
                             "direction": l.get("direction"),
                             "note": "ouverture vers le ciel (Blender : « portail » qui guide la lumière du jour) ; "
                                     "Unreal (Lumen) n'en a pas besoin, gardée pour placer caméras et reflets"})
    ambiances = [{**a, "unreal": CIEL_UNREAL.get(a.get("ciel"), "")} for a in eclairages]

    mobilier = [{"id": m["id"], "noeud_gltf": f"Meuble_{m['id']}", "categorie": m.get("categorie"), "modele": m.get("modele"),
                 "position": m.get("position"), "altitude": m.get("altitude", 0.0), "face_deg": m.get("face"),
                 "dimensions_m": m.get("dimensions"), "sur_mesure": bool(m.get("sur_mesure")),
                 "literie": m.get("literie")} for m in meubles]
    modeles_abo = sorted({m["modele"] for m in meubles if m.get("modele")})

    credits = {"meubles": {"texte": "Meubles 3D : Amazon Berkeley Objects (ABO), Amazon.com, licence CC BY 4.0 "
                                    "(https://amazon-berkeley-objects.s3.amazonaws.com/index.html). Les marques et noms de "
                                    "produits ne sont pas couverts par la licence.",
                           "modeles": modeles_abo} if modeles_abo else None,
               "matieres": sorted({f"{base} : « {fiches[base].get('identifiant')} » de {fiches[base].get('source')}, par "
                                   f"{', '.join(fiches[base].get('auteurs') or [])}, {fiches[base].get('licence')}"
                                   for f in materiaux.values() for base in [f.get("credit") or ("enduit_peint_blanc" if
                                                                                                f.get("grain") else None)]
                                   if base and base in fiches}),
               "unreal": "Si le produit livré a un générique ou des mentions légales, y mettre la mention exigée par le CLUF "
                         "d'Unreal Engine (§7.a) : texte exact à reprendre du CLUF (..\\atelya\\licences)."}
    return {
        "schema": SCHEMA, "projet_id": construction.get("projet_id"), "cree_le": date.today().isoformat(),
        "maquette": gltf, "scene_blender": export.get("scene"),
        "repere": {"unite": "mètre", "haut": "z", "sol": "x, y (plan d'Atelya)", "gltf": "y vers le haut (converti par Blender)",
                   "unreal": "centimètres (× 100) ; conversion d'axes à vérifier sur la première scène importée"},
        "orientation_sols_deg": orientation,
        "materiaux": materiaux,
        "lumieres": lumieres,
        "eclairages": ambiances,
        "meubles": mobilier,
        "vues": construction.get("vues") or [],
        "credits": credits,
        "pertes": PERTES,
        "export": {"placages": export.get("placages"), "brillances_cuites": export.get("brillances_cuites"),
                   "retires": export.get("retires"), "instances_meubles": export.get("instances_meubles")},
    }


def copier_photos(fiche: dict, bibliotheque: Path | None, sortie: Path) -> list[str]:
    """Copie dans le paquet les photos des matières utilisées (et le grain de la peinture), pour les matériaux natifs d'Unreal."""
    if not bibliotheque:
        return []
    noms = {f["photos"]["dossier"].split("/", 1)[1] for f in fiche["materiaux"].values() if f.get("photos")}
    if any(f.get("grain") for f in fiche["materiaux"].values()):
        noms.add("enduit_peint_blanc")
    copies = []
    for nom in sorted(noms):
        source = bibliotheque / nom
        if not source.is_dir():
            continue
        cible = sortie / "matieres" / nom
        cible.mkdir(parents=True, exist_ok=True)
        for photo in ("couleur.jpg", "relief.jpg", "brillance.jpg"):
            if (source / photo).is_file():
                shutil.copy2(source / photo, cible / photo)
        copies.append(nom)
    return copies


def ecrire_fiche(dossier_3d: str | Path, sortie: str | Path, bibliotheque: str | Path | None = None) -> Path:
    """Écrit scene-atelya.json (et copie les photos) d'après un export glTF déjà fait dans `sortie`."""
    dossier_3d, sortie = Path(dossier_3d), Path(sortie)
    bibliotheque = Path(bibliotheque) if bibliotheque else None
    export = _lire(sortie / "export-blender.json")
    if export is None:
        raise FileNotFoundError(f"export-blender.json introuvable dans {sortie} : lancer d'abord l'export glTF")
    fiche = fiche_de_scene(dossier_3d, export, bibliotheque)
    fiche["photos_copiees"] = copier_photos(fiche, bibliotheque, sortie)
    chemin = sortie / "scene-atelya.json"
    chemin.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    return chemin
