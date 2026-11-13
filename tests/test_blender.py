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
                   "menuiserie": "Menuiseries", "dalle": "Dalles"}
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
        if brique["categorie"] in ("mur", "menuiserie", "dalle"):  # dalle de l'immeuble (12/11/2026) : une boîte épaisse
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
        " 'murs': len(bpy.data.collections['Murs'].objects),"
        " 'apercu': [s.cycles.device, s.cycles.use_preview_denoising, s.cycles.preview_adaptive_threshold]}"
        " for s in bpy.data.scenes}\n"
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
        # aperçu « Rendu » de Blender propre (carte graphique, débruité) : NT le 09/11, « l'image est un peu pixelisée »
        assert s["apercu"][:2] == ["GPU", True] and s["apercu"][2] <= 0.02 + 1e-6, a["nom"]
        # chaque scène n'a QUE ses lampes (défaut du 09/11 : « 5 Nuit » avait aussi celles de « 4 Soirée »)
        propres = [c for c in s["collections"] if c.startswith("Lampes allumées")]
        assert propres == (["Lampes allumées " + a["nom"]] if a["lampes"] else []), a["nom"]
    allumees = {scenes[a["nom"]]["lampes"] for a in AMBIANCES if a["lampes"]}
    assert len(allumees) == 1  # autant de plafonniers allumés en soirée que la nuit


def test_meubles_sur_mesure_poses_tournes_et_mesures(tmp_path):
    """B4 (09/11/2026) : un îlot (bloc) posé à sa place, tourné selon sa « face », aux bonnes dimensions ; un meuble accroché
    (meuble haut de cuisine) à son altitude."""
    logement = json.loads(CAS_TEST_00.read_text(encoding="utf-8"))
    piece = logement["pieces"][0]
    xs, ys = [p[0] for p in piece["contour"]], [p[1] for p in piece["contour"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    logement["meubles"] = [
        {"id": "ilot_t", "categorie": "ilot", "piece": piece["id"], "position": [cx, cy], "face": 0,
         "dimensions": [2.0, 0.6, 0.9], "couleur": [170, 170, 170], "statut": "estime", "source": "test"},
        {"id": "haut_t", "categorie": "meuble_cuisine_haut", "piece": piece["id"], "position": [cx, cy], "face": 90,
         "dimensions": [1.2, 0.35, 0.7], "altitude": 1.5, "statut": "estime", "source": "test"},
    ]
    for o in logement["ouvertures"]:
        if o["id"] == "PF_sejour":
            o["rideaux"] = {"voilage": [245, 245, 242], "rideaux": [150, 105, 125], "statut": "estime", "source": "test"}
    chemin = tmp_path / "logement.json"
    chemin.write_text(json.dumps(logement), encoding="utf-8")
    mesures = mesurer(construire(chemin, tmp_path / "3d"), tmp_path / "mesures.json")
    ilot, haut = mesures["Bloc_ilot_t"], mesures["Bloc_haut_t"]
    # sur mesure dessiné en détail : portes des deux côtés de l'îlot (modules de ~60 cm), portes du meuble haut
    assert {"Porte_ilot_t_av1", "Porte_ilot_t_av3", "Porte_ilot_t_ar1", "Porte_haut_t_av2"} <= set(mesures)
    assert "Porte_ilot_t_av4" not in mesures
    # voilage de la porte-fenêtre : de 1 cm au-dessus du sol jusqu'à la tringle ; deux pans de rideaux
    voilage = mesures["Voilage_PF_sejour"]
    assert voilage["min"][2] == pytest.approx(0.01, abs=1e-3) and voilage["max"][2] > 2.1
    assert {"Rideau_PF_sejour_g", "Rideau_PF_sejour_d"} <= set(mesures)
    assert ilot["collection"] == "Meubles"
    # face 0 (avant vers +x) : la largeur (2 m) court le long de y, la profondeur (0,6 m) le long de x
    assert [ilot["max"][i] - ilot["min"][i] for i in range(3)] == pytest.approx([0.6, 2.0, 0.9], abs=0.01)
    assert [(ilot["max"][i] + ilot["min"][i]) / 2 for i in range(2)] == pytest.approx([cx, cy], abs=0.01)
    assert haut["min"][2] == pytest.approx(1.5, abs=0.01) and haut["max"][2] == pytest.approx(2.2, abs=0.01)
    assert [haut["max"][i] - haut["min"][i] for i in range(2)] == pytest.approx([1.2, 0.35], abs=0.01)
