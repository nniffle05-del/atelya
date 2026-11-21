"""La FERRONNERIE d'un garde-corps recopiée des photos (20/11/2026) : moteur/ferronnerie.py (de la photo au motif, du motif au
panneau), moteur/habillage.py (le panneau posé dehors devant la fenêtre), moteur/logement.py (le motif dans le format).

Les photos d'essai sont FABRIQUÉES : un motif connu (un barreau, un anneau en haut, un anneau en bas) répété devant un dehors
clair, vu de face puis de biais ; on vérifie que le motif retrouvé est bien celui qu'on a dessiné."""
import math

import cv2
import numpy as np
import pytest

from moteur import ferronnerie as fe
from moteur.habillage import ferronneries_du_plan, menuiseries
from moteur.images import ecrire_image
from moteur.logement import Logement

PAS = 0.30  # largeur du module vrai, en parts de sa hauteur
TAILLE = (1206, 800)


def module_vrai(haut: int = 640, anneau_bas: bool = True) -> np.ndarray:
    """Le motif connu, en grand : (haut, haut × PAS) uint8, 1 dans le fer."""
    large = int(round(haut * PAS))
    m = np.zeros((haut, large), np.uint8)
    cv2.line(m, (large // 2, 0), (large // 2, haut), 1, thickness=int(0.035 * haut))
    for y in (0.2, 0.8) if anneau_bas else (0.2,):
        cv2.circle(m, (large // 2, int(y * haut)), int(0.105 * haut), 1, thickness=int(0.03 * haut))
    return m


def photo_de_face(cache_le_bas: float = 0.0, anneau_bas: bool = True) -> tuple[np.ndarray, list[dict]]:
    """Une photo : deux vantaux de 90 × 300 pixels de vitre, le garde-corps (100 pixels de haut, trois répétitions par
    vantail) dans leur tiers bas. cache_le_bas : part du bas du garde-corps couverte par un aplat gris (un meuble), que la lecture dit dans « caches »."""
    image = np.full((TAILLE[1], TAILLE[0]), 235.0, np.float32)
    grand = np.tile(module_vrai(anneau_bas=anneau_bas), (1, 3)).astype(np.float32)
    petit = cv2.resize(grand, (90, 100), interpolation=cv2.INTER_AREA)
    fenetres = []
    for x in (300, 420):
        image[400:500, x:x + 90] *= 1 - 0.8 * petit
        if cache_le_bas:
            image[int(500 - 100 * cache_le_bas):500, x:x + 90] = 120
        fenetres.append({"baie": "F1", "coins": [[x, 200], [x + 90, 200], [x + 90, 500], [x, 500]], "garde_corps": [400, 400],
                         "genre_garde_corps": "fer_forge",
                         "caches": [[x - 5, int(500 - 100 * cache_le_bas), x + 95, 510]] if cache_le_bas else []})
    image += np.random.default_rng(3).normal(0, 2, image.shape)
    return cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR), fenetres


def de_biais(image: np.ndarray, fenetres: list[dict], lacet_deg: float = 28.0) -> tuple[np.ndarray, list[dict]]:
    """La même scène vue par un appareil tourné de `lacet_deg` (focale 0,75 × largeur) : la photo et les vantaux déplacés."""
    f = 0.75 * TAILLE[0]
    k = np.array([[f, 0, TAILLE[0] / 2], [0, f, TAILLE[1] / 2], [0, 0, 1]])
    a = math.radians(lacet_deg)
    r = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    h = k @ r @ np.linalg.inv(k)
    # la fenêtre est d'abord ramenée au milieu de l'image (sinon elle sort du cadre en tournant)
    h = h @ np.array([[1, 0, TAILLE[0] / 2 - 405], [0, 1, 0], [0, 0, 1.0]])

    def p(x, y):
        v = h @ np.array([x, y, 1.0])
        return [float(v[0] / v[2]), float(v[1] / v[2])]

    tournee = cv2.warpPerspective(image, h, TAILLE, flags=cv2.INTER_AREA, borderValue=(235, 235, 235))
    sortie = []
    for fen in fenetres:
        coins = [p(*c) for c in fen["coins"]]
        x0, x1 = fen["coins"][0][0], fen["coins"][1][0]
        sortie.append({**fen, "coins": coins, "garde_corps": [p(x0, 400)[1], p(x1, 400)[1]]})
    return tournee, sortie


def ressemblance(motif: dict) -> float:
    """Part commune (intersection / union) du motif retrouvé et du motif vrai, dessinés à la même taille."""
    vrai = module_vrai(320) > 0
    trouve = fe.dessiner(motif, vrai.shape[1], vrai.shape[0]) > 0
    return float((vrai & trouve).sum()) / float((vrai | trouve).sum())


def motif_de(photos: list[tuple[np.ndarray, list[dict]]]) -> tuple[dict | None, dict | None]:
    bandes = [b for image, fenetres in photos for f in fenetres if (b := fe.bande(image, f)) is not None]
    m = fe.module(bandes)
    return m, (None if m is None else {"pas": m["pas"], "contours": fe.contours(m["fer"])})


def test_le_motif_d_une_photo_de_face_est_retrouve():
    m, motif = motif_de([photo_de_face()])
    assert m is not None and m["pas"] == pytest.approx(PAS, rel=0.06)
    assert m["repetitions"] >= 5 and m["accord"] > 0.7 and m["symetrique"]
    assert ressemblance(motif) > 0.5
    # les anneaux sont restés des anneaux : leur trou est un contour à part (au moins le barreau, deux anneaux, leurs trous)
    assert len(motif["contours"]) >= 3
    milieu_de_l_anneau = fe.dessiner(motif, 96, 320)[int(0.2 * 320), 96 // 2 + int(0.06 * 320)]
    assert milieu_de_l_anneau == 0


def test_vue_de_biais_les_proportions_sont_redressees():
    """De biais, le garde-corps paraît plus étroit ; le pas du motif (en parts de sa hauteur) doit rester le vrai."""
    image, fenetres = de_biais(*photo_de_face())
    largeur_vue = fenetres[0]["coins"][1][0] - fenetres[0]["coins"][0][0]
    hauteur_vue = fenetres[0]["coins"][3][1] - fenetres[0]["garde_corps"][0]
    b = fe.bande(image, fenetres[0])
    assert b["aspect"] == pytest.approx(0.9, rel=0.08) and largeur_vue / hauteur_vue != pytest.approx(0.9, rel=0.08)
    m, motif = motif_de([(image, fenetres), photo_de_face()])
    assert m is not None and m["pas"] == pytest.approx(PAS, rel=0.08) and ressemblance(motif) > 0.45


def test_le_bas_cache_est_complete_par_le_haut():
    """Un meuble cache le quart bas du garde-corps sur toutes les photos : le motif, le même en haut et en bas, est complété."""
    m, motif = motif_de([photo_de_face(cache_le_bas=0.27)])
    assert m is not None and m["symetrie_debout"] >= fe.SYMETRIE_DEBOUT_MIN
    bas = fe.dessiner(motif, 96, 320)[int(0.72 * 320):int(0.9 * 320)]
    assert bas[:, :30].any() and bas[:, 66:].any()  # l'anneau du bas est là, des deux côtés du barreau


def test_sans_repetition_nette_pas_de_motif():
    image = np.full((TAILLE[1], TAILLE[0], 3), 230, np.uint8)
    image[430:470, 320:360] = 60  # une tache, pas un garde-corps
    _, fenetres = photo_de_face()
    assert motif_de([(image, fenetres)]) == (None, None)
    assert fe.bande(image, {**fenetres[0], "garde_corps": None}) is None
    assert fe.bande(image, {**fenetres[0], "vue": "non"}) is None


def test_le_panneau_repete_le_module_un_nombre_entier_de_fois():
    _, motif = motif_de([photo_de_face()])
    morceaux = fe.panneau(motif, 1.20, 0.60)
    points = [p for m in morceaux for b in (m["contour"], *m["trous"]) for p in b]
    assert morceaux and min(x for x, _ in points) >= -1e-6 and max(x for x, _ in points) <= 1.2 + 1e-6
    assert min(z for _, z in points) >= -1e-6 and max(z for _, z in points) <= 0.6 + 1e-6
    # 1,20 m pour un module de 0,30 × 0,60 = 18 cm : 7 répétitions (serrées à 17 cm) ; un barreau au milieu de chacune
    image = np.zeros((300, 600), np.uint8)
    for m in morceaux:
        cv2.fillPoly(image, [np.round(np.array([[x * 500, (0.6 - z) * 500] for x, z in b])).astype(np.int32) for b in (m["contour"], *m["trous"])], 1)
    barreaux = image[140:160].mean(0) > 0.9
    assert int(((barreaux[1:] != barreaux[:-1]).sum() + 1) // 2) == 7
    assert sum(len(m["trous"]) for m in morceaux) >= 14  # deux anneaux par répétition, chacun avec ses vides


def test_aucun_morceau_de_fer_ne_flotte():
    """Le bout d'une volute, que la mise au trait a séparé de son fer (spirale trop fine), est relié par le chemin le plus
    sombre : le garde-corps construit est d'un seul tenant, il tient à la main courante et à la lisse."""
    h, l = fe.HAUT_PX, 90
    carte = np.zeros((h, l), np.float32)
    carte[:, l // 2 - 3:l // 2 + 4] = 1.0  # le barreau, de haut en bas
    cv2.circle(carte, (l // 2 + 26, h // 2), 7, 1.0, -1)  # le bout d'une volute, seul
    cv2.line(carte, (l // 2 + 4, h // 2 + 30), (l // 2 + 26, h // 2), 0.12, 2)  # la spirale fine : trop pâle pour le trait
    motif = {"pas": l / h, "contours": fe.contours(carte)}
    image = fe.dessiner(motif, l * 3, h * 3)
    nombre, _ = cv2.connectedComponents(image, connectivity=8)
    assert nombre - 1 == 1  # un seul morceau : le bout tient au barreau
    morceaux = fe.panneau(motif, 3 * (l / h) * 0.6, 0.6)
    assert len(morceaux) == 3  # trois répétitions : trois barreaux, chacun avec son bout ; aucun bout à part


def logement(**garde_corps) -> dict:
    """Une pièce de 4 × 3 m, une porte-fenêtre de 1,2 m au milieu du mur du bas (la pièce est à GAUCHE de ce mur)."""
    murs = [{"id": f"M{i}", "statut": "mesure", "source": "essai", "debut": a, "fin": b, "epaisseur": 0.2}
            for i, (a, b) in enumerate([((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))], start=1)]
    dessin = {"vantaux": [{"debut": 0.08, "fin": 0.44}, {"debut": 0.56, "fin": 0.92}], "vitrage_bas": 0.2, "vitrage_haut": 0.95,
              "soubassement": 0.15, "statut": "estime", "source": "photos", "garde_corps": {"bas": 0.15, "haut": 0.45, "genre": "fer_forge", **garde_corps}}
    o = {"id": "F1", "statut": "mesure", "source": "essai", "type": "porte_fenetre", "mur": "M1", "position": 1.4, "largeur": 1.2,
         "hauteur": 2.0, "allege": 0.0, "dessin": dessin}
    return {"schema": "logement/0.1", "projet_id": "essai", "hauteur_sous_plafond": 2.5, "murs": murs, "ouvertures": [o],
            "pieces": [{"id": "P1", "statut": "mesure", "source": "essai", "nom": "Séjour",
                        "contour": [(0.1, 0.1), (3.9, 0.1), (3.9, 2.9), (0.1, 2.9)]}]}


MOTIF = {"pas": 0.3, "statut": "estime", "source": "photos (essai)",
         "contours": [[(0.4, 0.0), (0.6, 0.0), (0.6, 1.0), (0.4, 1.0)], [(0.05, 0.1), (0.3, 0.1), (0.3, 0.3), (0.05, 0.3)]]}


def test_la_maquette_pose_la_ferronnerie_dehors_a_la_place_des_barreaux():
    sans = {b.id.split("__", 1)[1] for b in menuiseries(Logement.model_validate(logement()))}
    avec = {b.id.split("__", 1)[1] for b in menuiseries(Logement.model_validate(logement(motif=MOTIF)))}
    assert any(n.startswith("garde_corps_barreau") for n in sans) and "garde_corps_frise" in sans
    assert not any(n.startswith("garde_corps_barreau") for n in avec) and "garde_corps_frise" not in avec
    assert {"garde_corps_main_courante", "garde_corps_lisse_basse"} <= avec
    assert ferronneries_du_plan(Logement.model_validate(logement())) == []
    (f,) = ferronneries_du_plan(Logement.model_validate(logement(motif=MOTIF)))
    # dehors : la pièce est du côté des y positifs, le garde-corps dans le tableau, du côté des y négatifs
    assert f["element"] == "F1" and f["direction"] == [1.0, 0.0] and f["origine"][0] == pytest.approx(1.4) and -0.1 < f["origine"][1] < 0
    assert f["z_bas"] == pytest.approx(0.30 + 0.06) and f["materiau"] == "fer_forge" and f["epaisseur"] == pytest.approx(0.014)
    points = [p for m in f["morceaux"] for p in m["contour"]]
    assert 0 <= min(t for t, _ in points) and max(t for t, _ in points) <= 1.2 + 1e-6 and max(z for _, z in points) <= 0.9 - 0.36 + 1e-6
    # le motif est vu de la PIÈCE : ici la gauche de qui regarde la fenêtre est du côté de la FIN du mur ; le petit carré, à
    # gauche du barreau sur la photo, est donc après le barreau le long du mur
    hauteur = 0.9 - 0.36
    carres = [m for m in f["morceaux"] if max(z for _, z in m["contour"]) < 0.4 * hauteur]
    barreaux = [m for m in f["morceaux"] if max(z for _, z in m["contour"]) > 0.9 * hauteur]
    assert len(carres) == len(barreaux) == 7
    premier_barreau = min(sum(t for t, _ in m["contour"]) / len(m["contour"]) for m in barreaux)
    premier_carre = min(sum(t for t, _ in m["contour"]) / len(m["contour"]) for m in carres)
    assert premier_carre > premier_barreau


def test_le_format_garde_le_motif_et_refuse_un_motif_vide():
    relu = Logement.model_validate_json(Logement.model_validate(logement(motif=MOTIF)).model_dump_json(by_alias=True))
    assert relu.ouvertures[0].dessin.garde_corps.motif.pas == 0.3 and len(relu.ouvertures[0].dessin.garde_corps.motif.contours) == 2
    for faute in ({"contours": []}, {"contours": [[(0.1, 0.1), (0.2, 0.2)]]}, {"pas": 0.0}, {"contours": [[(0.1, 0.1), (0.2, 0.2), (1.4, 0.3)]]}):
        with pytest.raises(ValueError):
            Logement.model_validate(logement(motif={**MOTIF, **faute}))


def test_appliquer_ne_touche_que_les_garde_corps_dont_le_motif_se_lit(tmp_path):
    image, fenetres = photo_de_face()
    ecrire_image(tmp_path / "photo-01.jpg", image)
    ecrire_image(tmp_path / "photo-02.jpg", np.full((TAILLE[1], TAILLE[0], 3), 230, np.uint8))
    depart = logement()
    lecture = {"photos": {"photo-01": fenetres}}
    pose, poses = fe.appliquer(depart, lecture, tmp_path)
    motif = pose["ouvertures"][0]["dessin"]["garde_corps"]["motif"]
    assert len(poses) == 1 and poses[0]["baie"] == "F1" and motif["statut"] == "estime" and "photo-01" in motif["source"]
    assert motif["pas"] == pytest.approx(PAS, rel=0.06)
    assert "motif" not in depart["ouvertures"][0]["dessin"]["garde_corps"]  # le logement donné n'est pas modifié
    Logement.model_validate(pose)
    # une photo où le garde-corps ne se lit pas, ou pas de garde-corps dans le dessin : rien n'est posé
    assert fe.appliquer(depart, {"photos": {"photo-02": fenetres}}, tmp_path)[1] == []
    sans_garde_corps = logement()
    del sans_garde_corps["ouvertures"][0]["dessin"]["garde_corps"]
    assert fe.appliquer(sans_garde_corps, lecture, tmp_path)[1] == []
    assert fe.appliquer(depart, lecture, tmp_path / "ailleurs")[1] == []  # photos introuvables
