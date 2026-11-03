"""Étape A2-3 : les textes exacts d'un PDF vectoriel remplacent l'OCR (cotes, surfaces, noms de pièces)."""
import numpy as np
import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("pypdfium2")

from moteur import lecture_pdf as L  # noqa: E402
from moteur.coloriage import MUR  # noqa: E402
from moteur.ecrire_pdf import MM, DocumentPdf  # noqa: E402
from moteur.echelle_plan import lire_echelle_plan  # noqa: E402
from moteur.lecture_cotes import lire_echelle  # noqa: E402
from moteur.noms_pieces import noms_depuis_textes  # noqa: E402
from moteur.surfaces_ecrites import surfaces_dans_textes  # noqa: E402

S = 20 * MM  # 1/50 : 1 m sur le plan = 20 mm sur la feuille (56,69 points)
X0, Y0 = 90, 160  # coin haut-gauche du logement sur la feuille, en points
# T2 : 8,00 × 5,40 m hors tout, murs extérieurs 0,20, cloison 0,10 (séjour | chambre au-dessus de la salle d'eau)
MURS = [(0, 0, 8, 0.2), (0, 5.2, 8, 0.2), (0, 0, 0.2, 5.4), (7.8, 0, 0.2, 5.4), (4.8, 0.2, 0.1, 5.0),
        (4.9, 2.1, 2.9, 0.1)]


def cote(page, a: float, b: float, position: float, verticale: bool = False, lisible: bool = True) -> None:
    """Une cote de a à b (mètres) : trait fin, deux marques perpendiculaires, la valeur écrite au milieu."""
    texte = f"{b - a:.2f}".replace(".", ",")
    largeur_texte = 0.5 * 9 * len(texte)  # Helvetica 9 pt : ~4,5 pt par chiffre
    if not verticale:
        y = Y0 + position * S
        page.trait(X0 + a * S, y, X0 + b * S, y, 0.3)
        for x in (a, b):
            page.trait(X0 + x * S, y - 4, X0 + x * S, y + 4, 0.3)
        page.texte(X0 + (a + b) / 2 * S - largeur_texte / 2, y - 2.5, texte, lisible=lisible)
    else:
        x = X0 + position * S
        page.trait(x, Y0 + a * S, x, Y0 + b * S, 0.3)
        for y in (a, b):
            page.trait(x - 4, Y0 + y * S, x + 4, Y0 + y * S, 0.3)
        page.texte(x - 2.5, Y0 + (a + b) / 2 * S + largeur_texte / 2, texte, lisible=lisible, vertical=True)


def plan_t2(page, lisible: bool = True) -> None:
    for x, y, l, h in MURS:
        page.rectangle(X0 + x * S, Y0 + y * S, l * S, h * S)
    page.arc(X0 + 4.85 * S, Y0 + 3 * S, 0.8 * S, 180, 270)
    cote(page, 0.2, 4.8, -0.6, lisible=lisible)  # séjour 4,60
    cote(page, 4.9, 7.8, -0.6, lisible=lisible)  # chambre 2,90
    cote(page, 0.2, 7.8, -1.1, lisible=lisible)  # ensemble intérieur 7,60
    cote(page, 0.2, 5.2, -0.6, verticale=True, lisible=lisible)  # 5,00
    cote(page, 0.2, 2.1, 8.6, verticale=True, lisible=lisible)  # chambre 1,90
    cote(page, 2.2, 5.2, 8.6, verticale=True, lisible=lisible)  # salle d'eau 3,00
    for x, y, t in [(1.2, 2.4, "Séjour"), (1.2, 2.8, "22,08 m²"), (5.6, 1.0, "Chambre"), (5.6, 1.4, "5,51 m²"),
                    (5.4, 3.5, "Salle d'eau"), (5.6, 3.9, "8,70 m²")]:
        page.texte(X0 + x * S, Y0 + y * S, t, lisible=lisible)


def coloriage_parfait(forme: tuple[int, int], px_par_pt: float, reduction: int = 2) -> np.ndarray:
    """Le coloriage qu'Atelya ferait sans aucune erreur, à la moitié de la taille de l'image (comme en vrai,
    où Atelya colorie une image plus petite que le dessin)."""
    h, w = forme
    col = np.zeros((h // reduction, w // reduction), np.uint8)
    k = px_par_pt / reduction
    for x, y, l, hh in MURS:
        x0, y0 = round((X0 + x * S) * k), round((Y0 + y * S) * k)
        col[y0:round((Y0 + (y + hh) * S) * k), x0:round((X0 + (x + l) * S) * k)] = MUR
    return col


@pytest.fixture
def pdf_t2(tmp_path):
    d = tmp_path / "Modélisation immobilière"  # le piège des accents sous Windows
    d.mkdir()
    doc = DocumentPdf()
    plan_t2(doc.page())
    return doc.enregistrer(d / "plan-t2-é.pdf")


def test_textes_exacts_dans_le_bon_sens(pdf_t2):
    page = L.lire_page(pdf_t2, 1)
    assert page.nature == "vectorielle"
    lus = {t.texte: t for t in page.textes}
    assert {"4,60", "2,90", "7,60", "5,00", "1,90", "3,00", "Séjour", "22,08 m²", "Salle d'eau"} <= set(lus)
    assert all(t.confiance == 1.0 for t in page.textes)
    # une cote verticale : boîte plus haute que large (c'est ainsi que la chaîne reconnaît son sens)
    (x0, y0), (x1, y1) = lus["5,00"].boite.min(axis=0), lus["5,00"].boite.max(axis=0)
    assert y1 - y0 > x1 - x0
    # placée au bon endroit de l'image : milieu de la cote 4,60, au-dessus du trait
    cx = lus["4,60"].boite[:, 0].mean() / page.px_par_pt
    assert cx == pytest.approx(X0 + 2.5 * S, abs=2)


def test_texte_vertical_ecrit_de_haut_en_bas(tmp_path):
    """Certains logiciels écrivent les cotes verticales dans l'autre sens : elles doivent rester lisibles."""
    import pdfplumber

    doc = DocumentPdf()
    p = doc.page()
    p.texte(300, 300, "5,40", vertical=True)
    p.ordres.append("BT /F1 9 Tf 0 -1 1 0 200 500 Tm (3,25) Tj ET")  # tourné dans l'autre sens
    with pdfplumber.open(doc.enregistrer(tmp_path / "sens.pdf")) as pdf:
        assert sorted(t.texte for t in L.textes_de_la_page(pdf.pages[0], 1.0)) == ["3,25", "5,40"]


def test_echelle_exacte_sans_ocr(pdf_t2):
    page = L.lire_page(pdf_t2, 1)
    gris = page.image[:, :, 1]
    echelle = lire_echelle(gris, page.textes)
    attendu = S * page.px_par_pt  # pixels de l'image par mètre
    assert echelle.sure
    assert len(echelle.retenues) == 6
    assert echelle.px_par_m == pytest.approx(attendu, rel=0.003)


def test_lire_echelle_plan_avec_les_textes_du_pdf(pdf_t2, monkeypatch):
    import moteur.echelle_plan as E

    def interdit(*a, **k):
        raise AssertionError("l'OCR ne doit pas être lancé sur un PDF vectoriel")

    monkeypatch.setattr(E, "lire_textes", interdit)
    page = L.lire_page(pdf_t2, 1)
    col = coloriage_parfait(page.image.shape[:2], page.px_par_pt)
    e = lire_echelle_plan(page.image[:, :, ::-1], col, angle=0.0, textes=page.textes)
    attendu = S * page.px_par_pt / 2  # pixels du coloriage par mètre
    largeur, hauteur, source = e.decision(de_biais=False)
    assert source == "cotes" and e.sure
    assert largeur == pytest.approx(attendu, rel=0.005) and hauteur == pytest.approx(attendu, rel=0.005)
    assert e.cote_max_largeur == 7.60 and e.cote_max_hauteur == 5.00
    assert e.surfaces is not None and e.surfaces == pytest.approx(attendu, rel=0.02)


def test_textes_suivent_le_dessin_tourne(pdf_t2):
    """Si le coloriage est vu un peu penché, le dessin est tourné : les textes doivent tourner avec lui."""
    page = L.lire_page(pdf_t2, 1)
    col = coloriage_parfait(page.image.shape[:2], page.px_par_pt)
    e = lire_echelle_plan(page.image[:, :, ::-1], col, angle=0.0, textes=page.textes)
    e_tourne = lire_echelle_plan(page.image[:, :, ::-1], col, angle=0.3, textes=page.textes)
    assert e_tourne.sure and e_tourne.largeur == pytest.approx(e.largeur, rel=0.005)


def test_noms_des_pieces(pdf_t2):
    page = L.lire_page(pdf_t2, 1)
    noms = noms_depuis_textes(L.pour_les_noms(page.textes))
    assert sorted(n.type for n in noms) == ["chambre", "salle_d_eau", "sejour"]
    assert sorted(v for v, _, _ in surfaces_dans_textes(page.textes)) == [5.51, 8.70, 22.08]


def test_page_piegee_ou_scannee_laisse_l_ocr(tmp_path):
    doc = DocumentPdf()
    plan_t2(doc.page(), lisible=False)
    page = L.lire_page(doc.enregistrer(tmp_path / "piege.pdf"), 1)
    assert page.nature == "piegee" and page.textes is None
