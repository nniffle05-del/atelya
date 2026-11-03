"""La lecture complète d'un plan (moteur/lecture_complete.py), avec des coloriages fabriqués : pas besoin de PyTorch."""
import numpy as np
import pytest
from PIL import Image

from moteur import lecture_complete as L
from moteur.coloriage import FENETRE, MUR, PORTE

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


def source() -> L.PlanSource:
    """Un plan vide, avec des textes déjà connus (l'OCR n'est pas lancé), de la taille du coloriage."""
    h, w = coloriage_t2().shape
    return L.PlanSource("essai", np.full((h, w, 3), 255, np.uint8), textes=[], px_par_pt=1.0, a_plat=True)


def test_sans_aucune_mesure_le_logement_reste_un_brouillon_annonce():
    lu = L.lire_avec_coloriage(source(), coloriage_t2(), None)
    assert lu.logement is not None
    assert lu.echelle["etat"] == "a_verifier" and lu.echelle["provisoire"] > 0
    assert lu.examen["decision"] == "a_verifier"
    assert "echelle" in {d["code"] for d in lu.examen["doutes"]}


def test_coloriage_vide_refuse_sans_planter():
    lu = L.lire_avec_coloriage(source(), np.zeros((600, 800), np.uint8), None)
    assert lu.logement is None and lu.examen["decision"] == "refuse" and lu.erreur


def test_aiguillage_garde_e5_sur_murs_droits_et_passe_a_e7_sur_biais():
    col = coloriage_t2()
    droit = L.lire_plan(source(), {"e5": lambda i: (col, None), "e7": lambda i: (col, None)}, avec_noms=False)
    assert droit.gardee.modele == "e5" and "<" in droit.aiguillage
    biais = L.lire_avec_coloriage(source(), col, None, "e7")
    biais.logement["murs"].append({"id": "M99", "debut": [0, 0], "fin": [2, 2], "epaisseur": 0.1})
    gardee, pourquoi = L._aiguiller(L.lire_avec_coloriage(source(), col, None, "e5"), biais)
    assert gardee.modele == "e7" and "≥" in pourquoi


def test_un_modele_sans_lecture_laisse_la_place_a_l_autre():
    col, vide = coloriage_t2(), np.zeros((600, 800), np.uint8)
    plan = L.lire_plan(source(), {"e5": lambda i: (vide, None), "e7": lambda i: (col, None)}, avec_noms=False)
    assert plan.gardee.modele == "e7" and plan.decision != "refuse"
    rien = L.lire_plan(source(), {"e5": lambda i: (vide, None), "e7": lambda i: (vide, None)}, avec_noms=False)
    assert rien.decision == "refuse"


def test_reduction_identique_a_celle_d_atelya():
    img = np.random.default_rng(0).integers(0, 255, (1000, 1500, 3), np.uint8)
    petite = L.reduire_pour_atelya(img)
    assert max(petite.shape) == 768 and petite.shape == (512, 768)
    attendu = Image.fromarray(img).convert("L").resize((768, 512), Image.BILINEAR)
    assert np.array_equal(petite, np.array(attendu, np.uint8))


def test_photo_de_telephone_remise_a_l_endroit(tmp_path):
    img = Image.fromarray(np.zeros((20, 40, 3), np.uint8))
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation : tournée de 90° par le téléphone
    f = tmp_path / "photé.jpg"  # avec un accent, exprès
    img.save(f, exif=exif)
    assert L.plans_du_fichier(f)[0].image.shape[:2] == (40, 20)


def test_fichiers_refuses_clairement(tmp_path):
    with pytest.raises(L.FichierNonLisible):
        L.plans_du_fichier(tmp_path / "absent.png")
    (tmp_path / "note.txt").write_text("pas un plan", encoding="utf-8")
    with pytest.raises(L.FichierNonLisible):
        L.plans_du_fichier(tmp_path / "note.txt")
    (tmp_path / "faux.png").write_text("pas une image", encoding="utf-8")
    with pytest.raises(L.FichierNonLisible):
        L.plans_du_fichier(tmp_path / "faux.png")


def test_pdf_vectoriel_donne_ses_textes_et_reste_a_plat(tmp_path):
    pytest.importorskip("pdfplumber")
    pytest.importorskip("pypdfium2")
    from moteur.ecrire_pdf import DocumentPdf

    doc = DocumentPdf()
    page = doc.page()
    for x, y, l, h in [(90, 160, 400, 10), (90, 450, 400, 10), (90, 160, 10, 300), (480, 160, 10, 300), (280, 170, 5, 280)]:
        page.rectangle(x, y, l, h)
    for k in range(20):  # assez de traits pour que le tri y voie un plan
        page.trait(100, 180 + 12 * k, 270, 180 + 12 * k)
    page.texte(120, 300, "Séjour")
    page.texte(120, 320, "22,08 m²")
    s = L.plans_du_fichier(doc.enregistrer(tmp_path / "plan-é.pdf"))[0]
    assert s.nature == "vectorielle" and s.a_plat and s.px_par_pt > 4 and s.page == 1
    assert {"Séjour", "22,08 m²"} <= {t.texte for t in s.textes}
    assert s.image.ndim == 3 and s.image.shape[2] == 3
