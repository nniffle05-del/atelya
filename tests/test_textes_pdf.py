"""Étape A2-3 : les textes exacts d'un PDF vectoriel remplacent l'OCR (cotes, surfaces, noms de pièces)."""
import numpy as np
import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("pypdfium2")

from moteur import lecture_pdf as L  # noqa: E402
from moteur.coloriage import MUR, PORTE  # noqa: E402
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


def cote(page, a: float, b: float, position: float, verticale: bool = False, lisible: bool = True, s: float = S) -> None:
    """Une cote de a à b (mètres) : trait fin, deux marques perpendiculaires, la valeur écrite au milieu."""
    texte = f"{b - a:.2f}".replace(".", ",")
    largeur_texte = 0.5 * 9 * len(texte)  # Helvetica 9 pt : ~4,5 pt par chiffre
    if not verticale:
        y = Y0 + position * s
        page.trait(X0 + a * s, y, X0 + b * s, y, 0.3)
        for x in (a, b):
            page.trait(X0 + x * s, y - 4, X0 + x * s, y + 4, 0.3)
        page.texte(X0 + (a + b) / 2 * s - largeur_texte / 2, y - 2.5, texte, lisible=lisible)
    else:
        x = X0 + position * s
        page.trait(x, Y0 + a * s, x, Y0 + b * s, 0.3)
        for y in (a, b):
            page.trait(x - 4, Y0 + y * s, x + 4, Y0 + y * s, 0.3)
        page.texte(x - 2.5, Y0 + (a + b) / 2 * s + largeur_texte / 2, texte, lisible=lisible, vertical=True)


SURFACES = [(1.2, 2.4, "Séjour"), (1.2, 2.8, "22,08 m²"), (5.6, 1.0, "Chambre"), (5.6, 1.4, "5,51 m²"),
            (5.4, 3.5, "Salle d'eau"), (5.6, 3.9, "8,70 m²")]


def plan_t2(page, lisible: bool = True, cotes: bool = True, surfaces: bool = True, echelle: str | None = None,
            s: float = S) -> None:
    """Le T2 dessiné à `s` points par mètre (S = vrai 1/50), avec ou sans cotes, surfaces, échelle écrite."""
    for x, y, l, h in MURS:
        page.rectangle(X0 + x * s, Y0 + y * s, l * s, h * s)
    page.arc(X0 + 4.85 * s, Y0 + 3 * s, 0.8 * s, 180, 270)
    if cotes:
        cote(page, 0.2, 4.8, -0.6, lisible=lisible, s=s)  # séjour 4,60
        cote(page, 4.9, 7.8, -0.6, lisible=lisible, s=s)  # chambre 2,90
        cote(page, 0.2, 7.8, -1.1, lisible=lisible, s=s)  # ensemble intérieur 7,60
        cote(page, 0.2, 5.2, -0.6, verticale=True, lisible=lisible, s=s)  # 5,00
        cote(page, 0.2, 2.1, 8.6, verticale=True, lisible=lisible, s=s)  # chambre 1,90
        cote(page, 2.2, 5.2, 8.6, verticale=True, lisible=lisible, s=s)  # salle d'eau 3,00
    for x, y, t in SURFACES if surfaces else SURFACES[::2]:
        page.texte(X0 + x * s, Y0 + y * s, t, lisible=lisible)
    if echelle:
        page.texte(X0, Y0 + 6.2 * s, echelle, lisible=lisible)


def coloriage_parfait(forme: tuple[int, int], px_par_pt: float, reduction: int = 2, s: float = S,
                      portes: bool = False) -> np.ndarray:
    """Le coloriage qu'Atelya ferait sans aucune erreur, à la moitié de la taille de l'image (comme en vrai,
    où Atelya colorie une image plus petite que le dessin)."""
    h, w = forme
    col = np.zeros((h // reduction, w // reduction), np.uint8)
    k = px_par_pt / reduction
    def peindre(x, y, l, hh, classe):
        x0, y0 = round((X0 + x * s) * k), round((Y0 + y * s) * k)
        col[y0:round((Y0 + (y + hh) * s) * k), x0:round((X0 + (x + l) * s) * k)] = classe

    for mur in MURS:
        peindre(*mur, MUR)
    if portes:  # deux portes intérieures de 83 cm, dans la cloison et dans le mur de la chambre
        peindre(4.8, 2.9, 0.1, 0.83, PORTE)
        peindre(5.6, 2.1, 0.83, 0.1, PORTE)
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


# ---------- Étape A2-4 : l'échelle écrite (« Éch. 1/50 ») ----------

def _textes(*chaines):
    from moteur.lecture_cotes import TexteLu

    return [TexteLu(c, np.zeros((4, 2)), 1.0) for c in chaines]


@pytest.mark.parametrize("texte, attendu", [
    ("Éch. 1/50", [(50, True)]), ("ECHELLE : 1:100", [(100, True)]), ("Echelle 1/50e", [(50, True)]),
    ("Plan au 1/50ème", [(50, False)]), ("Scale 1:200", [(200, True)]),
    ("le 01/05/2026", []), ("1/2 niveau", []), ("11/50", []), ("1/50,5", []), ("1/7", []),
])
def test_formes_de_l_echelle_ecrite(texte, attendu):
    assert L.echelles_ecrites(_textes(texte)) == attendu


def test_echelle_ecrite_en_pixels():
    px_par_m, detail = L.echelle_ecrite(_textes("Éch. 1/50"), 300 / 72)
    assert px_par_m == pytest.approx(S * 300 / 72) and detail == "échelle écrite 1/50"  # 236,2 px/m à 300 dpi
    # plan au 1/50 + plan de situation au 1/500 : on prend celle qui suit le mot « échelle »
    assert L.echelle_ecrite(_textes("Échelle 1/50", "Situation 1/500"), 1.0)[0] == pytest.approx(S)
    # deux échelles sans indice pour choisir : on ne choisit pas
    assert L.echelle_ecrite(_textes("1/50", "1/100"), 1.0)[0] is None
    assert L.echelle_ecrite(_textes("Séjour"), 1.0) == (None, "")


def test_decider_avec_l_echelle_ecrite():
    from moteur.echelle_plan import decider

    vrai, interieur = 100.0, (760.0, 500.0)
    # sans rien d'autre : il faut les portes pour la confirmer
    assert decider(None, None, False, None, None, interieur, False, ecrite=vrai)[2] == "à vérifier"
    assert decider(None, None, False, None, None, interieur, False, approchee=108, ecrite=vrai) == (vrai, vrai, "échelle écrite")
    # page A3 réduite en A4 (× 0,71) : les portes et les surfaces la contredisent
    assert decider(None, None, False, None, None, interieur, False, approchee=vrai, ecrite=71)[2] == "à vérifier"
    # … mais les surfaces, dessinées, ont rapetissé avec la page : elles restent justes et décident
    assert decider(None, None, False, None, None, interieur, False, surfaces=vrai, ecrite=71) == (vrai, vrai, "surfaces")
    assert decider(None, None, False, None, None, interieur, False, surfaces=101, ecrite=vrai) == (vrai, vrai, "échelle écrite")
    # les cotes passent avant, même seules (elles aussi rapetissent avec la page)
    assert decider(vrai, vrai, True, 7.6, 5.0, interieur, False, ecrite=71) == (vrai, vrai, "cotes")
    assert decider(vrai, vrai, False, 7.6, 5.0, interieur, False, ecrite=71) == (vrai, vrai, "cotes")
    # barre d'accord : l'échelle écrite sert ; barre en désaccord : la barre (dessinée) décide
    assert decider(None, None, False, None, None, interieur, False, barre=100.4, ecrite=vrai) == (vrai, vrai, "échelle écrite")
    assert decider(None, None, False, None, None, interieur, False, barre=vrai, ecrite=71) == (vrai, vrai, "barre")
    # sur une photo de biais, elle n'a pas de sens (la taille du papier est inconnue) : ignorée
    assert decider(None, None, False, None, None, interieur, True, approchee=vrai, ecrite=vrai)[2] == "à vérifier"


def _lire(tmp_path, nom, s=S, **options):
    doc = DocumentPdf()
    plan_t2(doc.page(), cotes=False, s=s, **options)
    page = L.lire_page(doc.enregistrer(tmp_path / nom), 1)
    col = coloriage_parfait(page.image.shape[:2], page.px_par_pt, s=s, portes=True)
    e = lire_echelle_plan(page.image[:, :, ::-1], col, angle=0.0, textes=page.textes, px_par_pt=page.px_par_pt)
    return e, s * page.px_par_pt / 2  # échelle lue, vraie échelle du coloriage


def test_plan_sans_cotes_lu_par_son_echelle_ecrite(tmp_path):
    """Plan d'agence au 1/50 sans aucune cote : l'échelle écrite, confirmée par les surfaces, suffit."""
    e, vrai = _lire(tmp_path, "agence.pdf", echelle="Échelle 1/50")
    largeur, hauteur, source = e.decision(de_biais=False)
    assert source == "échelle écrite" and e.ecrite_detail == "échelle écrite 1/50"
    assert largeur == pytest.approx(vrai, rel=0.001) and hauteur == largeur


def test_plan_sans_cotes_ni_surfaces_confirme_par_les_portes(tmp_path):
    e, vrai = _lire(tmp_path, "nu.pdf", surfaces=False, echelle="Éch. 1/50")
    largeur, _, source = e.decision(de_biais=False)
    assert source == "échelle écrite" and largeur == pytest.approx(vrai, rel=0.001)


def test_page_reduite_a_l_impression(tmp_path):
    """Plan A3 au 1/50 imprimé « ajusté » sur A4 : le « 1/50 » écrit est faux (tout est 0,71 fois trop petit).
    Avec des surfaces écrites, elles ont rapetissé avec le dessin : elles donnent la vraie échelle. Sans rien
    d'autre, les portes contredisent le « 1/50 » : vérification humaine, jamais une maquette 1,4 fois trop grande."""
    e, vrai = _lire(tmp_path, "reduit.pdf", s=S * 0.707, echelle="Échelle 1/50")
    largeur, _, source = e.decision(de_biais=False)
    assert e.ecrite is not None and source == "surfaces" and largeur == pytest.approx(vrai, rel=0.02)
    e, _ = _lire(tmp_path, "reduit-nu.pdf", s=S * 0.707, surfaces=False, echelle="Échelle 1/50")
    assert e.decision(de_biais=False)[2] == "à vérifier"
