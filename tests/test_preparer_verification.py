"""Le calage de l'écran de vérification : les mètres lus retombent-ils sur les murs de l'image, quel que soit le chemin ?"""
import json

import cv2
import numpy as np

from moteur import lecture_complete as L
from moteur.coloriage import FENETRE, MUR, PORTE, lire_coloriage
from moteur.preparer_verification import matrice_calage, projeter, verification_du_plan, zone_en_pixels
from moteur.redressement import Redressement

S = 100


def px(m: float) -> int:
    return int(round(m * S))


def coloriage_t2() -> np.ndarray:
    c = np.zeros((px(6), px(8)), np.uint8)

    def rect(x0, y0, x1, y1, v):
        c[px(1) + px(4.2 - y1):px(1) + px(4.2 - y0), px(1) + px(x0 + 0.2):px(1) + px(x1 + 0.2)] = v

    rect(-0.2, -0.2, 6.2, 4.2, MUR)
    rect(0, 0, 2.95, 4, 5)
    rect(3.05, 0, 6, 4, 7)
    rect(1.0, -0.2, 2.2, 0, FENETRE)
    rect(2.95, 1.0, 3.05, 1.9, PORTE)
    return c


def part_sur_les_murs(logement: dict, M: np.ndarray, image: np.ndarray) -> float:
    """Part des axes de murs (lus en mètres, posés par le calage) qui tombent sur du bâti de l'image."""
    h, w = image.shape[:2]
    bons = tous = 0
    for m in logement["murs"]:
        for t in np.linspace(0.1, 0.9, 25):
            x = m["debut"][0] + t * (m["fin"][0] - m["debut"][0])
            y = m["debut"][1] + t * (m["fin"][1] - m["debut"][1])
            u, v = projeter(M, x, y)
            tous += 1
            if 0 <= int(u) < w and 0 <= int(v) < h and image[int(v), int(u)] != 0:
                bons += 1
    return bons / tous


def bords_exterieurs(logement: dict, M: np.ndarray) -> tuple[float, float]:
    pts = np.array([projeter(M, *p) for m in logement["murs"] for p in (m["debut"], m["fin"])])
    return float(pts[:, 0].min()), float(pts[:, 1].min())


def test_plan_droit_meme_taille_exact_au_pixel():
    col = coloriage_t2()
    log, det = lire_coloriage(col, S, angle=0.0)
    M = matrice_calage(det, col.shape, col.shape)
    # Coin intérieur bas-gauche du logement = (0, 0) en mètres : pixel (120, 520) dans le coloriage dessiné.
    assert np.allclose(projeter(M, 0, 0), (px(1.2), px(1) + px(4.2)), atol=1.0)
    assert part_sur_les_murs(log, M, col) > 0.98


def test_image_plus_grande_que_le_coloriage():
    col = coloriage_t2()
    log, det = lire_coloriage(col, S, angle=0.0)
    image = cv2.resize(col, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    M = matrice_calage(det, col.shape, image.shape)
    u, v = projeter(M, 0, 0)
    assert abs(u - 3 * px(1.2)) <= 3 and abs(v - 3 * (px(1) + px(4.2))) <= 3
    assert part_sur_les_murs(log, M, image) > 0.98


def test_plan_tourne():
    h, w = coloriage_t2().shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 4.0, 1.0)
    col = cv2.warpAffine(coloriage_t2(), m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    log, det = lire_coloriage(col, S)
    assert abs(det["angle_deg"]) > 1
    M = matrice_calage(det, col.shape, col.shape)
    assert part_sur_les_murs(log, M, col) > 0.95
    # Sans la rotation, le calage serait franchement faux : le test sait voir l'erreur.
    faux = matrice_calage({**det, "angle_deg": 0.0}, col.shape, col.shape)
    assert part_sur_les_murs(log, faux, col) < 0.7


def test_photo_de_biais():
    droit = coloriage_t2()
    h, w = droit.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[30, 15], [w - 10, 0], [w, h], [0, h - 25]])
    plan_vers_photo = cv2.getPerspectiveTransform(src, dst)
    photo = cv2.warpPerspective(droit, plan_vers_photo, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    R = Redressement(np.linalg.inv(plan_vers_photo), (w, h), 40, 0.1, 0.0, 0.05)
    log, det = lire_coloriage(photo, S, redressement=R)
    M = matrice_calage(det, photo.shape, photo.shape, R)
    assert part_sur_les_murs(log, M, photo) > 0.95


def test_zone_en_mètres_devient_un_rectangle_de_pixels():
    M = np.array([[100.0, 0, 50], [0, -100.0, 500], [0, 0, 1]])
    assert zone_en_pixels(M, (1, 1, 2, 3)) == [150.0, 200.0, 100.0, 200.0]


def _plan_lu(col):
    h, w = col.shape
    s = L.PlanSource("essai", np.full((h, w, 3), 255, np.uint8), textes=[], px_par_pt=1.0, a_plat=True)
    return L.lire_plan(s, {"e5": lambda i: (col, None)}, avec_noms=False)


def test_fichier_au_format_de_l_ecran():
    v = verification_du_plan(_plan_lu(coloriage_t2()))
    v = json.loads(json.dumps(v))  # doit s'écrire tel quel en JSON
    assert v["schema"] == "verification/0.1" and v["plan"] == "plan.png"
    assert len(v["calage"]["matrice"]) == 3 and all(len(l) == 3 for l in v["calage"]["matrice"])
    assert v["logement"]["schema"] == "logement/0.1"
    assert v["echelle"]["etat"] == "a_verifier" and v["echelle"]["raison"]
    assert any(d["code"] == "echelle" and d["element"] is None for d in v["doutes"])
    ids = {e["id"] for k in ("murs", "ouvertures", "pieces") for e in v["logement"][k]}
    assert all(d["element"] is None or d["element"] in ids for d in v["doutes"])


def test_plan_refuse_pas_d_ecran():
    assert verification_du_plan(_plan_lu(np.zeros((600, 800), np.uint8))) is None


def test_un_logement_que_la_3d_refuse_donne_un_doute_sur_l_ouverture_en_cause():
    from moteur.preparer_verification import doutes_de_construction

    mur = {"id": "A", "debut": [0, 0], "fin": [6, 0], "epaisseur": 0.2, "statut": "estime", "source": "atelya"}
    porte = {"id": "P", "type": "porte", "mur": "A", "position": 1, "largeur": 0.9, "hauteur": 2.04, "allege": 0, "statut": "estime", "source": "atelya"}
    fenetre = {**porte, "id": "F", "type": "fenetre", "position": 1.5, "hauteur": 1.2, "allege": 0.9}
    base = {"schema": "logement/0.1", "projet_id": "T", "unites": "m", "hauteur_sous_plafond": 2.5, "murs": [mur], "pieces": []}
    assert doutes_de_construction({**base, "ouvertures": [porte]}) == []
    [d] = doutes_de_construction({**base, "ouvertures": [porte, fenetre]})
    assert d["code"] == "construction" and d["element"] == "F" and d["gravite"] == "fort"
    assert "3D" in d["raison"]
