"""Paquet Unreal d'une maquette (moteur/export_unreal.py, moteur/blender/exporter_gltf.py) : fiche de scène et placage des
photos. Les scripts Blender sont chargés avec un faux module bpy (seuls leurs calculs purs sont testés ici)."""
import importlib.util
import json
import math
import sys
import types
from pathlib import Path

import pytest

from moteur import export_unreal as eu

SCRIPTS = Path(__file__).resolve().parents[1] / "moteur" / "blender"


def _script_blender(nom):
    """Charge un script Blender sans Blender (faux bpy)."""
    faux = sys.modules.setdefault("bpy", types.ModuleType("bpy"))
    spec = importlib.util.spec_from_file_location(f"_essai_{nom}", SCRIPTS / f"{nom}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if faux is sys.modules.get("bpy") and not hasattr(faux, "data"):
        del sys.modules["bpy"]
    return module


def test_les_valeurs_de_la_fiche_sont_celles_de_blender():
    """La fiche recopie des réglages de moteur/blender/materiaux.py : ils doivent rester d'accord."""
    texte = (SCRIPTS / "materiaux.py").read_text(encoding="utf-8")
    m = _script_blender("materiaux")
    assert tuple(m.COULEUR_PEINTURE) == eu.COULEUR_PEINTURE
    assert tuple(m.RUGOSITE_BOIS) == eu.RUGOSITE_BOIS
    assert m.REFLET_BOIS == eu.REFLET_BOIS
    assert m.ROTATION_PHOTO == eu.ROTATION_PHOTO
    for nom, (couleur, rugosite, metal) in eu.UNIES.items():
        ligne = next(l for l in texte.splitlines() if f'"{nom}":' in l)
        assert str(couleur) in ligne and f"rugosite={rugosite}" in ligne, nom
        assert ("metal=1.0" in ligne) == (metal == 1.0), nom
    assert "To Min\"].default_value = 0.8" in texte and "To Max\"].default_value = 0.95" in texte  # RUGOSITE_PEINTURE
    assert 'inputs["Fac"].default_value = 0.06' in texte  # ALPHA_VERRE : la part de reflet du verre
    assert _script_blender("exporter_gltf").ALPHA_VERRE == eu.ALPHA_VERRE


def test_fiche_materiau_par_genre():
    fiches = {"parquet_diagonal": {"taille_image_m": [2.36, 2.36]}, "chene_clair": {"taille_image_m": [1.83, 1.83]},
              "carrelage_interieur": {"taille_image_m": [1.9, 1.9]}}
    sortes = {"parquet_diagonal": "bois", "carrelage_interieur": "carrelage", "point_de_hongrie": "bois"}
    teintes = {"parquet_diagonal@1.20~1.14,1.74,3.21": [0.3, 0.25, 0.15]}

    def f(nom, linge=None):
        return eu.fiche_materiau(nom, fiches, teintes, 10.0, sortes, linge or {})

    assert f("mur_blanc")["genre"] == "peinture" and f("mur_blanc")["grain"] == "enduit_peint_blanc"
    assert f("metal") == {"genre": "uni", "couleur": [0.75, 0.75, 0.76], "rugosite": 0.25, "metal": 1.0}
    assert f("verre")["genre"] == "verre" and f("verre")["projette_ombre"] is False
    bois = f("parquet_diagonal@1.20~1.14,1.74,3.21")
    assert bois["genre"] == "photo" and bois["matiere"] == "parquet_diagonal"
    assert bois["teinte"] == [0.3, 0.25, 0.15]  # la teinte réglée au rendu prime sur celle du nom
    assert bois["photos"] == {"dossier": "matieres/parquet_diagonal", "taille_m": [2.832, 2.832]}  # × l'échelle du motif
    assert bois["rugosite"] == list(eu.RUGOSITE_BOIS) and bois["rotation_deg"] == 10.0
    carreau = f("carrelage_interieur~1.55,1.39,1.41")
    assert carreau["teinte"] == [1.55, 1.39, 1.41] and carreau["rotation_deg"] == 55.0 and "rugosite" not in carreau
    hongrie = f("point_de_hongrie")
    assert hongrie["genre"] == "dessin" and hongrie["a_cuire"] and hongrie["photos"]["dossier"] == "matieres/chene_clair"
    assert f("carreaux_ciment")["genre"] == "dessin" and "photos" not in f("carreaux_ciment")
    linge = f("Couette_reperage_8", {"Couette_reperage_8": [255, 0, 51]})
    assert linge["genre"] == "tissu" and linge["meuble"] == "reperage_8" and linge["couleur"] == [1.0, 0.0, 0.2]
    assert f("B086TG9Q4V_TRB_MDL_MR")["genre"] == "meuble"


def test_fiche_de_scene(tmp_path):
    d3 = tmp_path / "3d"
    d3.mkdir()
    construction = {
        "projet_id": "essai", "orientation_sols": 0.0, "sortes_sols": {"chene_clair": "bois"},
        "lumieres": [{"id": "Soleil", "type": "soleil", "direction": [0.6, 0.2, -0.77]},
                     {"id": "Plafonnier_sejour", "type": "plafonnier", "piece": "sejour", "position": [1, 2, 2.48],
                      "taille": [1.0, 1.0], "puissance": 50.0},
                     {"id": "Portail_O1", "type": "portail", "position": [0, 1, 1.5], "taille": [1, 1.2], "direction": [1, 0, 0]}],
        "meubles": [{"id": "lit_1", "categorie": "lit", "position": [3, 4], "face": 90, "dimensions": [1.6, 2, 0.5],
                     "modele": "B0ABC", "literie": {"couette": [200, 200, 200], "oreillers": 2, "couleur_oreillers": [10, 20, 30],
                                                    "plaid": None}}],
        "vues": [{"id": "dessus"}], "reglages_teinte": [],
    }
    (d3 / "construction.json").write_text(json.dumps(construction), encoding="utf-8")
    (d3 / "eclairages.json").write_text(json.dumps([{"id": "jour_soleil", "ciel": "physique"}, {"id": "nuit", "ciel": "nuit"}]),
                                        encoding="utf-8")
    biblio = tmp_path / "biblio"
    (biblio / "chene_clair").mkdir(parents=True)
    (biblio / "chene_clair" / "couleur.jpg").write_bytes(b"x")
    (biblio / "enduit_peint_blanc").mkdir()
    (biblio / "enduit_peint_blanc" / "relief.jpg").write_bytes(b"y")
    (biblio / "matieres.json").write_text(json.dumps({
        "chene_clair": {"taille_image_m": [1.83, 1.83], "identifiant": "oak", "source": "Poly Haven", "auteurs": ["A"],
                        "licence": "CC0 1.0"},
        "enduit_peint_blanc": {"taille_image_m": [2, 2], "identifiant": "plaster", "source": "Poly Haven", "auteurs": ["B"],
                               "licence": "CC0 1.0"}}), encoding="utf-8")
    sortie = tmp_path / "export"
    sortie.mkdir()
    with pytest.raises(FileNotFoundError):
        eu.ecrire_fiche(d3, sortie, biblio)
    (sortie / "export-blender.json").write_text(json.dumps({
        "scene": "1 Jour ensoleillé", "materiaux": ["mur_blanc", "point_de_hongrie", "Couette_lit_1", "Oreillers_lit_1", "verre"]}),
        encoding="utf-8")
    fiche = json.loads(eu.ecrire_fiche(d3, sortie, biblio).read_text(encoding="utf-8"))
    assert fiche["schema"] == eu.SCHEMA and fiche["projet_id"] == "essai"
    assert [l["genre"] for l in fiche["lumieres"]] == ["soleil", "plafonnier", "fenetre"]
    assert fiche["lumieres"][1]["puissance_w"] == 50.0
    assert [e["unreal"] != "" for e in fiche["eclairages"]] == [True, True]
    assert fiche["meubles"][0]["noeud_gltf"] == "Meuble_lit_1"
    assert fiche["materiaux"]["Oreillers_lit_1"]["couleur"] == [round(10 / 255, 4), round(20 / 255, 4), round(30 / 255, 4)]
    assert fiche["credits"]["meubles"]["modeles"] == ["B0ABC"] and "Amazon.com" in fiche["credits"]["meubles"]["texte"]
    assert len(fiche["credits"]["matieres"]) == 2  # le chêne du point de Hongrie et le grain de la peinture
    assert fiche["photos_copiees"] == ["chene_clair", "enduit_peint_blanc"]
    assert (sortie / "matieres" / "chene_clair" / "couleur.jpg").is_file()
    assert any("point de Hongrie" in p["quoi"] for p in fiche["pertes"])


def test_placage_comme_blender_au_rendu():
    """Carte UV « monde » : rotation autour du haut, taille réelle, projection vue d'en haut (sol) ou de face (côtés)."""
    uv = _script_blender("exporter_gltf").uv_du_point
    p = {"angle": 0.0, "echelle": (0.5, 0.5, 0.5), "decalage": (0.0, 0.0, 0.0)}
    assert uv((2.0, 3.0, 0.0), (0, 0, 1), p) == (1.0, 1.5)  # sol : x, y à l'échelle d'une photo de 2 m
    assert uv((2.0, 3.0, 0.1), (1, 0, 0), p) == (1.5, 0.05)  # côté face à x : y, z
    assert uv((2.0, 3.0, 0.1), (0, -1, 0), p) == (1.0, 0.05)  # côté face à y : x, z
    tourne = dict(p, angle=math.radians(90))  # photo tournée d'un quart de tour : x devient y
    u, v = uv((2.0, 0.0, 0.0), (0, 0, 1), tourne)
    assert abs(u) < 1e-9 and abs(v - 1.0) < 1e-9
