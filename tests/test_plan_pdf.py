"""Étape A2-5 : les plans du générateur écrits en PDF, dont on connaît la vérité exacte."""
import numpy as np
import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("pypdfium2")

from moteur import lecture_pdf as L  # noqa: E402
from moteur.ecrire_pdf import MM  # noqa: E402
from moteur.generateur import plan_pdf as P  # noqa: E402
from moteur.generateur.exportateur import Options, style_pour  # noqa: E402
from moteur.generateur.logements import generer  # noqa: E402
from moteur.generateur.reglages import Reglages  # noqa: E402
from moteur.generateur.rendu import Repere, _cadre_des_murs, _Dessin  # noqa: E402
from moteur.lecture_cotes import lire_echelle  # noqa: E402


def _plan(graine, **changer):
    log = generer(graine, Reglages.charger(None))
    style = style_pour(graine, 0, Options())
    for k, v in changer.items():
        setattr(style, k, v)
    return log, log.niveaux[0], style


@pytest.fixture(scope="module")
def t2():
    return _plan(4, cotes=True, cotes_partielles=True, echelle_graphique=False)


@pytest.fixture
def dossier(tmp_path):
    d = tmp_path / "Modélisation immobilière"
    d.mkdir()
    return d


@pytest.mark.parametrize("sorte, nature, page", [
    ("vectorielle", "vectorielle", 1), ("piegee", "piegee", 1), ("scannee", "scannee", 1),
    ("reduite", "vectorielle", 1), ("tournee", "vectorielle", 1), ("dossier", "vectorielle", 2)])
def test_chaque_sorte_est_bien_triee(t2, dossier, sorte, nature, page):
    f = P.pdf_du_niveau(*t2, sorte=sorte)
    chemin = dossier / f"{sorte}.pdf"
    chemin.write_bytes(f.octets)
    tri = L.trier_pdf(chemin)
    assert L.choisir_pages(tri) == ([page], False)
    assert tri[page - 1].nature == nature and f.infos["page_du_plan"] == page
    assert f.infos["ordres_non_recopies"] == []


def test_vectorielle_cotes_et_echelle_exactes(t2, dossier):
    f = P.pdf_du_niveau(*t2, sorte="vectorielle", echelle_ecrite=True)
    chemin = dossier / "plan.pdf"
    chemin.write_bytes(f.octets)
    page = L.lire_page(chemin, 1)
    vrai = f.infos["pt_par_m"] * page.px_par_pt
    n = f.infos["echelle_vraie"]
    assert f.infos["pt_par_m"] == pytest.approx(1000 / n * MM)  # vraie échelle d'architecte
    assert L.echelle_ecrite(page.textes, page.px_par_pt)[0] == pytest.approx(vrai)
    e = lire_echelle(page.image[:, :, 1], page.textes)
    assert e.sure and e.px_par_m == pytest.approx(vrai, rel=0.01)
    textes = {t.texte for t in page.textes}
    assert any(t.endswith("m²") for t in textes) and "Chambre" in textes


def test_reduite_garde_un_1_50_faux(t2, dossier):
    f = P.pdf_du_niveau(*t2, sorte="reduite", echelle_ecrite=True)
    chemin = dossier / "reduite.pdf"
    chemin.write_bytes(f.octets)
    page = L.lire_page(chemin, 1)
    ecrite = L.echelle_ecrite(page.textes, page.px_par_pt)[0]
    assert ecrite / (f.infos["pt_par_m"] * page.px_par_pt) == pytest.approx(1 / P.REDUCTION, rel=0.001)


def test_tournee_et_scannee(t2, dossier):
    f = P.pdf_du_niveau(*t2, sorte="tournee")
    (dossier / "t.pdf").write_bytes(f.octets)
    page = L.lire_page(dossier / "t.pdf", 1)
    l, h = f.infos["page_pt"]
    assert page.image.shape[1] > page.image.shape[0] if h > l else page.image.shape[0] > page.image.shape[1]
    assert "Chambre" in {t.texte for t in page.textes}  # textes lus dans le bon sens malgré la page couchée
    f = P.pdf_du_niveau(*t2, sorte="scannee")
    (dossier / "s.pdf").write_bytes(f.octets)
    assert L.lire_page(dossier / "s.pdf", 1).textes is None and f.infos["echelle_ecrite"] is None


def test_l_image_du_generateur_ne_change_pas(t2):
    """L'enregistreur recopie en PDF sans toucher au dessin : même image qu'avec Pillow seul."""
    log, niveau, style = t2
    st = P.style_a_plat(style)
    meubles = {}
    a = _Dessin(log, niveau, st, Repere(_cadre_des_murs(niveau), st, __import__("random").Random(0)), meubles, True)
    a.tout()
    from moteur.ecrire_pdf import DocumentPdf

    page = DocumentPdf().page()
    b = P._DessinPdf(log, niveau, st, Repere(_cadre_des_murs(niveau), st, __import__("random").Random(0)), meubles, True,
                     page=page, k=0.5, ox=10, oy=10, lisible=True)
    b.tout()
    assert np.array_equal(np.asarray(a.image), np.asarray(b.image))
    assert len(page.ordres) > 50


def test_mise_en_page():
    assert P.mise_en_page(900, 700, 100)[:2] == (50, "A4")  # 9 × 7 m au 1/50 : 18 × 14 cm
    assert P.mise_en_page(1900, 1200, 100)[:2] == (50, "A3")  # 19 × 12 m : 38 × 24 cm
    assert P.mise_en_page(2500, 1700, 100)[:2] == (100, "A4")  # 25 × 17 m : 25 × 17 cm au 1/100
    assert P.sorte_en_plus(4, 0) == P.sorte_en_plus(4, 0) and P.sorte_en_plus(4, 0) in P.SORTES_EN_PLUS


def test_piege_realiste_lettres_affichees_mais_illisibles(dossier):
    """Un vrai PDF piégé : les lettres s'affichent normalement (police dans le fichier), mais un lecteur de PDF ne
    peut pas dire lesquelles (il voit « (cid:54) ») ; c'est l'OCR qui les lira sur l'image."""
    import pdfplumber

    from moteur.ecrire_pdf import DocumentPdf, police_piege

    if police_piege() is None:
        pytest.skip("police Liberation Sans absente")
    doc = DocumentPdf()
    p = doc.page()
    p.texte_ancre(100, 100, "Chambre 12,50 m²", 20, 0.0, lisible=False)
    chemin = doc.enregistrer(dossier / "piege.pdf")
    with pdfplumber.open(chemin) as pdf:
        assert all(c["text"].startswith("(cid:") for c in pdf.pages[0].chars if c["text"].strip())
    image, k = L.rendre_page(chemin, 1, dpi=150)
    zone = image[round(85 * k):round(105 * k), round(95 * k):round(260 * k)]
    assert (zone.min(axis=2) < 100).mean() > 0.05  # de l'encre à l'endroit du texte : les lettres sont dessinées
