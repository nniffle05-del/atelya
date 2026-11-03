"""Étape A2-2 : tri des pages d'un PDF (vectorielle / scannée / piégée / vide, plan ou pas)."""
import numpy as np
import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("pypdfium2")

from moteur import lecture_pdf as L  # noqa: E402
from moteur.ecrire_pdf import MM, DocumentPdf  # noqa: E402

S = 20 * MM  # 1/50 : 1 m sur le plan = 20 mm sur la feuille
X0, Y0 = 80, 150


def dessiner_t2(page, lisible=True, textes=True):
    """Petit T2 au 1/50 : murs pleins, porte avec battant, ligne de cote, cotes et noms."""
    murs = [(0, 0, 8, 0.2), (0, 5.2, 8, 0.2), (0, 0, 0.2, 5.4), (7.8, 0, 0.2, 5.4),
            (4.8, 0, 0.1, 5.4), (4.9, 2.1, 3, 0.1)]
    for x, y, l, h in murs:
        page.rectangle(X0 + x * S, Y0 + y * S, l * S, h * S)
    page.arc(X0 + 4.85 * S, Y0 + 3 * S, 0.8 * S, 180, 270)
    for i in range(12):
        page.trait(X0, Y0 - 20 + i, X0 + 8 * S, Y0 - 20 + i, 0.2)
    if textes:
        for x, t in [(2, "4,80"), (6, "3,10")]:
            page.texte(X0 + x * S, Y0 - 25, t, lisible=lisible)
        page.texte(X0 + 1.5 * S, Y0 + 2.5 * S, "Séjour 25,92 m²", lisible=lisible)
        page.texte(X0 + 5.5 * S, Y0 + 1 * S, "Chambre", lisible=lisible)


def faux_scan():
    img = np.full((900, 1300), 255, np.uint8)
    img[100:120, 100:1200] = 0
    img[100:800, 100:120] = 0
    return img


@pytest.fixture
def dossier(tmp_path):
    d = tmp_path / "Modélisation immobilière"  # le piège des accents sous Windows
    d.mkdir()
    return d


def test_les_cinq_sortes_de_pages(dossier):
    doc = DocumentPdf()
    dessiner_t2(doc.page())
    doc.page().image(40, 100, 515, 357, faux_scan())
    dessiner_t2(doc.page(), lisible=False)
    rapport = doc.page()
    for i in range(30):
        rapport.texte(50, 80 + i * 20, f"Diagnostic de performance énergétique, ligne {i}, surface 52,3 m²")
    doc.page()
    tri = L.trier_pdf(doc.enregistrer(dossier / "dossier-complet-é.pdf"))
    assert [(t.nature, t.est_plan) for t in tri] == [
        ("vectorielle", True), ("scannee", True), ("piegee", True), ("vectorielle", False), ("vide", False)]
    assert tri[1].mesures.zone_image_pt == pytest.approx((40, 100, 555, 457), abs=0.5)
    assert L.choisir_pages(tri) == ([1, 2, 3], False)


def test_dessin_sans_aucun_texte_est_piege(dossier):
    """Textes transformés en dessins : il n'y a plus aucun caractère dans le PDF."""
    doc = DocumentPdf()
    dessiner_t2(doc.page(), textes=False)
    (t,) = L.trier_pdf(doc.enregistrer(dossier / "sans-texte.pdf"))
    assert (t.nature, t.est_plan) == ("piegee", True)


def test_textes_lisibles_avec_accents(dossier):
    import pdfplumber

    doc = DocumentPdf()
    dessiner_t2(doc.page())
    chemin = doc.enregistrer(dossier / "t2.pdf")
    with pdfplumber.open(chemin) as pdf:
        texte = pdf.pages[0].extract_text()
    assert "Séjour 25,92 m²" in texte and "4,80" in texte


def test_cadre_seul_n_est_pas_un_plan():
    """Un cadre de page + un petit cartouche : des traits, mais pas un dessin de plan."""
    m = L.MesuresPage(nb_segments=14, longueur_traits_pt=3500, nb_caracteres=60)
    nature, est_plan, _ = L.classer(m, 595.28, 841.89)
    assert not est_plan and nature == "vectorielle"


def test_tableau_des_surfaces_n_est_pas_un_plan():
    m = L.MesuresPage(nb_segments=44, longueur_traits_pt=16000, nb_caracteres=900)
    assert L.classer(m, 595.28, 841.89)[1] is False


def test_petite_image_seule_est_un_logo():
    m = L.MesuresPage(part_image=0.02, zone_image_pt=(20, 20, 100, 60))
    assert L.classer(m, 595.28, 841.89)[:2] == ("vide", False)


def test_aucun_plan_evident_donne_un_doute():
    tri = [L.TriPage(1, 595, 842, 0, "vectorielle", False, "texte",
                     L.MesuresPage(nb_segments=10, longueur_traits_pt=900, nb_caracteres=500)),
           L.TriPage(2, 595, 842, 0, "vectorielle", False, "texte",
                     L.MesuresPage(nb_segments=30, longueur_traits_pt=6000, nb_caracteres=900))]
    assert L.choisir_pages(tri) == ([2], True)
    assert L.choisir_pages([]) == ([], True)


def test_image_de_la_page_au_format_opencv(dossier):
    doc = DocumentPdf()
    dessiner_t2(doc.page())
    chemin = doc.enregistrer(dossier / "t2.pdf")
    image, px_par_pt = L.rendre_page(chemin, 1)
    assert image.dtype == np.uint8 and image.shape[2] == 3
    assert px_par_pt == pytest.approx(300 / 72)
    hauteur, largeur = image.shape[:2]  # pdfium arrondit au pixel supérieur
    assert abs(hauteur - 841.89 * px_par_pt) <= 1 and abs(largeur - 595.28 * px_par_pt) <= 1
    # milieu du mur du haut (8 m × 0,20 m) : noir ; milieu du séjour : blanc
    x, y = X0 + 2 * S, Y0 + 0.1 * S
    assert image[round(y * px_par_pt), round(x * px_par_pt)].max() < 60
    assert image[round((Y0 + 4 * S) * px_par_pt), round((X0 + 3 * S) * px_par_pt)].min() > 200


def test_grand_format_limite_en_pixels(dossier):
    doc = DocumentPdf()
    dessiner_t2(doc.page((2384, 3370)))  # A0
    image, px_par_pt = L.rendre_page(doc.enregistrer(dossier / "a0.pdf"), 1, cote_max_px=4000)
    assert max(image.shape[:2]) <= 4001 and px_par_pt == pytest.approx(4000 / 3370)


def test_fichiers_absents_ou_abimes(dossier):
    with pytest.raises(FileNotFoundError):
        L.trier_pdf(dossier / "absent.pdf")
    faux = dossier / "pas-un-pdf.pdf"
    faux.write_bytes(b"ceci n'est pas un PDF")
    with pytest.raises(L.PdfIllisible):
        L.trier_pdf(faux)
    with pytest.raises(L.PdfIllisible):
        L.rendre_page(faux, 1)
