"""Test de bout en bout : Blender construit la maquette habillée, on la mesure,
puis on lui fait calculer ses images (en qualité brouillon, pour aller vite).

Ce test lance vraiment Blender (sans écran). Il est sauté si Blender est
introuvable sur la machine.
"""

import json
from pathlib import Path

import pytest

from moteur.construire import construire, mesurer, rendre, trouver_blender

CAS_TEST_00 = Path(__file__).parent.parent / "exemples" / "cas-test-00" / "logement.json"
MILLIMETRE = 0.001

pytestmark = pytest.mark.skipif(trouver_blender() is None, reason="Blender introuvable")


@pytest.fixture(scope="module")
def resultat(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("cas-test-00")
    maquette = construire(CAS_TEST_00, dossier)
    plan = json.loads((dossier / "construction.json").read_text(encoding="utf-8"))
    return maquette, plan, mesurer(maquette, dossier / "mesures.json")


def test_la_maquette_existe(resultat):
    maquette, _, _ = resultat
    assert maquette.is_file()


def test_une_brique_un_objet(resultat):
    _, plan, mesures = resultat
    assert sorted(mesures) == sorted(b["id"] for b in plan["briques"])


def test_cotes_au_millimetre(resultat):
    _, plan, mesures = resultat
    collections = {"mur": "Murs", "sol": "Sols", "plafond": "Plafonds",
                   "menuiserie": "Menuiseries"}
    for brique in plan["briques"]:
        mesure = mesures[brique["id"]]
        xs = [p[0] for p in brique["contour"]]
        ys = [p[1] for p in brique["contour"]]
        attendu_min = [min(xs), min(ys), brique["z_bas"]]
        attendu_max = [max(xs), max(ys), brique["z_haut"]]
        assert mesure["min"] == pytest.approx(attendu_min, abs=MILLIMETRE), brique["id"]
        assert mesure["max"] == pytest.approx(attendu_max, abs=MILLIMETRE), brique["id"]
        assert mesure["collection"] == collections[brique["categorie"]]
        assert mesure["element"] == brique["element"]


def test_faces_bien_orientees(resultat):
    """Un sol regarde vers le haut, un plafond vers le bas, un mur ou une menuiserie a 6 faces."""
    _, plan, mesures = resultat
    for brique in plan["briques"]:
        mesure = mesures[brique["id"]]
        if brique["categorie"] in ("mur", "menuiserie"):
            assert mesure["faces"] == 6
        elif brique["categorie"] == "sol":
            assert mesure["normales"] == [pytest.approx([0, 0, 1])]
        else:
            assert mesure["normales"] == [pytest.approx([0, 0, -1])]


def test_chaque_brique_a_son_materiau(resultat):
    _, plan, mesures = resultat
    for brique in plan["briques"]:
        assert mesures[brique["id"]]["materiaux"] == [brique["materiau"]], brique["id"]


def test_deux_images_ni_noires_ni_blanches(resultat, tmp_path):
    pytest.importorskip("cv2")
    from moteur.images import lire_image
    maquette, _, _ = resultat
    images = rendre(maquette, tmp_path / "images", qualite="brouillon")
    assert [i.name for i in images] == ["vue-dessus.png", "vue-sejour.png"]
    for image in images:
        pixels = lire_image(str(image))
        assert pixels.shape[:2] == (250, 400)  # 25 % de 1600 × 1000
        assert 60 < pixels.mean() < 230, image.name  # ni trop sombre, ni brûlée
        assert pixels.std() > 10, image.name  # pas une image toute unie


def test_une_scene_par_eclairage(resultat, tmp_path):
    """B2 temps 2 (09/11/2026) : la maquette a une scène par éclairage ; elles partagent murs et sols ; les lampes ne sont
    allumées qu'en soirée et la nuit ; chaque scène a son exposition déjà réglée."""
    from moteur.construire import lancer_blender
    from moteur.eclairages import AMBIANCES

    maquette, _, _ = resultat
    sortie = tmp_path / "scenes.json"
    code = (
        "import bpy, json\n"
        "d = {s.name: {'ambiance': s.get('ambiance'), 'collections': sorted(c.name for c in s.collection.children),"
        " 'lampes': sum(1 for o in s.objects if o.type == 'LIGHT' and not o.hide_render and o.data.type == 'AREA'"
        " and not o.data.cycles.is_portal), 'exposition': s.view_settings.exposure,"
        " 'murs': len(bpy.data.collections['Murs'].objects)} for s in bpy.data.scenes}\n"
        f"open(r'{sortie}', 'w', encoding='utf-8').write(json.dumps(d))\n"
    )
    lancer_blender(str(maquette), "--python-expr", code)
    scenes = json.loads(sortie.read_text(encoding="utf-8"))
    assert sorted(scenes) == sorted(a["nom"] for a in AMBIANCES)
    for a in AMBIANCES:
        s = scenes[a["nom"]]
        assert s["ambiance"] == a["id"]
        assert {"Murs", "Sols", "Plafonds", "Menuiseries"} <= set(s["collections"])
        assert (s["lampes"] > 0) == a["lampes"], a["nom"]
        assert s["exposition"] != 0.0, a["nom"]  # réglée par le « photographe »
        # chaque scène n'a QUE ses lampes (défaut du 09/11 : « 5 Nuit » avait aussi celles de « 4 Soirée »)
        propres = [c for c in s["collections"] if c.startswith("Lampes allumées")]
        assert propres == (["Lampes allumées " + a["nom"]] if a["lampes"] else []), a["nom"]
    allumees = {scenes[a["nom"]]["lampes"] for a in AMBIANCES if a["lampes"]}
    assert len(allumees) == 1  # autant de plafonniers allumés en soirée que la nuit
