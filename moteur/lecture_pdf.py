"""Lire les plans en PDF (étape A2). Partie 1 : le TRI À L'ENTRÉE.

Pourquoi : un PDF peut être de trois sortes, et chacune se lit autrement.
- « vectorielle » : la page contient des ordres de dessin (traits) et des textes lisibles. Exemple :
  plan exporté d'un logiciel d'architecte. Les cotes « 3,40 » y sont écrites telles quelles : on les
  lira directement, sans OCR (étape A2-3).
- « scannee » : la page n'est qu'une photo du plan rangée dans un PDF. On en fait une image et on
  la passe dans la chaîne actuelle d'Atelya (coloriage + OCR).
- « piegee » : il y a bien un dessin vectoriel, mais les textes sont absents (transformés en dessins)
  ou illisibles (police sans table de correspondance : « 3,40 » sort en « (cid:22)(cid:19)… »).
  On fait une image nette de la page et on passe par la chaîne actuelle, OCR compris.
- « vide » : rien à lire.
Chaque page dit aussi si elle ressemble à un PLAN (beaucoup de traits, peu de texte), pour écarter
la page de garde, le tableau des surfaces ou les pages de texte d'un rapport de diagnostic.

Partie 2 (version 0.2, étape A2-3) : sur une page vectorielle, les TEXTES EXACTS du fichier remplacent l'OCR
(textes_de_la_page, lire_page) : mêmes fiches TexteLu que l'OCR, placées sur l'image rendue ; le reste de la chaîne
(cotes, barre d'échelle, surfaces, noms de pièces) ne change pas.

Partie 3 (version 0.3, étape A2-4) : l'échelle écrite (« Éch. 1/50 »), convertie en pixels par mètre grâce à la
taille réelle de la feuille (echelle_ecrite) ; contrôlée par moteur.echelle_plan.decider, jamais prise seule.

Les seuils ci-dessous sont des PREMIERS RÉGLAGES (plans fabriqués) : à revoir sur de vrais PDF.
Unités : points PDF (1/72 de pouce = 0,3528 mm), origine en haut à gauche (comme pdfplumber).
"""
from __future__ import annotations

import argparse
import logging
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from moteur.lecture_cotes import TexteLu

VERSION_LECTURE_PDF = "0.3.0"

SEGMENTS_DESSIN = 20  # au moins ce nombre de segments de traits pour parler de « dessin »
LONGUEUR_DESSIN = 0.75  # et une longueur totale ≥ 0,75 fois le tour de la page (A2-6 : 1,5 ratait 1,6 % des petits
# logements dessinés sur A3 ; un cadre de page seul est déjà écarté par SEGMENTS_DESSIN : il n'a que 4 traits)
TEXTE_PAR_SEGMENT_MAX = 4.0  # au-delà de 4 lettres par segment : page de texte ou tableau, pas un plan
PART_ILLISIBLE_MAX = 0.3  # plus de 30 % de caractères illisibles → textes inutilisables
CARACTERES_MIN = 4  # un dessin avec moins de 4 caractères lisibles : textes perdus (piégée)
PART_IMAGE_SCAN = 0.15  # une image couvrant ≥ 15 % de la page, sans dessin : page scannée

DPI_RENDU = 300
COTE_MAX_PX = 8000  # au-delà (grand format A0 à 300 dpi = 14 000 px), on baisse la définition


class PdfIllisible(Exception):
    """Le fichier n'est pas un PDF lisible (abîmé, ou protégé par un mot de passe d'ouverture)."""


@dataclass
class MesuresPage:
    nb_segments: int = 0
    longueur_traits_pt: float = 0.0
    nb_caracteres: int = 0  # hors espaces
    nb_illisibles: int = 0
    part_image: float = 0.0  # part de la page couverte par la plus grande image
    zone_image_pt: tuple[float, float, float, float] | None = None  # (x0, haut, x1, bas)


@dataclass
class TriPage:
    numero: int  # à partir de 1, comme dans un lecteur de PDF
    largeur_pt: float
    hauteur_pt: float
    rotation: int
    nature: str  # vectorielle / scannee / piegee / vide
    est_plan: bool
    raison: str
    mesures: MesuresPage = field(default_factory=MesuresPage)


def _caractere_illisible(texte: str) -> bool:
    if texte.startswith("(cid:") or "�" in texte:
        return True
    return any(unicodedata.category(c) in ("Co", "Cc", "Cs", "Cn") for c in texte)


def _segments(points) -> tuple[int, float]:
    n, longueur = 0, 0.0
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        n += 1
        longueur += math.hypot(xb - xa, yb - ya)
    return n, longueur


def mesurer_page(page) -> MesuresPage:
    """Compte ce que contient une page pdfplumber : traits, caractères, images."""
    m = MesuresPage()
    for objet in list(page.lines) + list(page.curves):
        n, l = _segments(objet.get("pts") or [])
        m.nb_segments += n
        m.longueur_traits_pt += l
    for r in page.rects:
        m.nb_segments += 4
        m.longueur_traits_pt += 2 * (abs(r["width"]) + abs(r["height"]))
    for c in page.chars:
        t = c.get("text", "")
        if not t.strip():
            continue
        m.nb_caracteres += 1
        m.nb_illisibles += _caractere_illisible(t)
    aire_page = max(page.width * page.height, 1e-9)
    x0p, y0p, x1p, y1p = page.bbox
    for img in page.images:
        x0, y0 = max(img["x0"], x0p), max(img["top"], y0p)
        x1, y1 = min(img["x1"], x1p), min(img["bottom"], y1p)
        if x1 <= x0 or y1 <= y0:
            continue
        part = (x1 - x0) * (y1 - y0) / aire_page
        if part > m.part_image:
            m.part_image, m.zone_image_pt = part, (x0, y0, x1, y1)
    return m


def classer(m: MesuresPage, largeur: float, hauteur: float) -> tuple[str, bool, str]:
    """Décide (nature, est_plan, raison) à partir des mesures. Sans PDF : facile à tester."""
    tour = 2 * (largeur + hauteur)
    dessin = m.nb_segments >= SEGMENTS_DESSIN and m.longueur_traits_pt >= LONGUEUR_DESSIN * tour
    lisibles = m.nb_caracteres - m.nb_illisibles
    if dessin:
        trop_de_texte = lisibles > TEXTE_PAR_SEGMENT_MAX * m.nb_segments
        if trop_de_texte:
            return "vectorielle", False, (f"surtout du texte ({lisibles} lettres pour {m.nb_segments} "
                                          "traits) : tableau ou page de rapport")
        if m.nb_caracteres and m.nb_illisibles / m.nb_caracteres > PART_ILLISIBLE_MAX:
            return "piegee", True, (f"dessin vectoriel mais {m.nb_illisibles}/{m.nb_caracteres} "
                                    "caractères illisibles : lecture par l'image + OCR")
        if lisibles < CARACTERES_MIN:
            return "piegee", True, ("dessin vectoriel sans texte lisible (textes transformés en "
                                    "dessins ?) : lecture par l'image + OCR")
        return "vectorielle", True, f"dessin vectoriel ({m.nb_segments} traits) et {lisibles} lettres lisibles"
    if m.part_image >= PART_IMAGE_SCAN:
        return "scannee", True, (f"image couvrant {m.part_image:.0%} de la page, pas de dessin : "
                                 "scan, à lire par l'image (à confirmer par la lecture d'Atelya)")
    if m.nb_caracteres:
        return "vectorielle", False, f"texte seul ({m.nb_caracteres} lettres), pas de dessin"
    if m.nb_segments or m.part_image:
        return "vide", False, "presque rien : quelques traits ou une petite image (logo ?)"
    return "vide", False, "page vide"


def _ouvrir(chemin: str | Path):
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    logging.getLogger("pdfminer").setLevel(logging.ERROR)  # messages techniques sans intérêt (FontBBox…)
    chemin = Path(chemin)
    if not chemin.is_file():
        raise FileNotFoundError(f"PDF introuvable : {chemin}")
    try:
        return pdfplumber.open(chemin)
    except PDFPasswordIncorrect as e:
        raise PdfIllisible(f"PDF protégé par un mot de passe d'ouverture : {chemin.name}") from e
    except Exception as e:  # fichier abîmé ou pas un PDF
        raise PdfIllisible(f"PDF illisible ({type(e).__name__}) : {chemin.name}") from e


def trier_pdf(chemin: str | Path) -> list[TriPage]:
    """Trie toutes les pages d'un PDF."""
    tri = []
    with _ouvrir(chemin) as pdf:
        try:
            pages = pdf.pages
        except Exception as e:
            raise PdfIllisible(f"PDF illisible ({type(e).__name__}) : {Path(chemin).name}") from e
        for i, page in enumerate(pages, 1):
            m = mesurer_page(page)
            nature, est_plan, raison = classer(m, page.width, page.height)
            tri.append(TriPage(i, round(page.width, 2), round(page.height, 2), int(page.rotation or 0),
                               nature, est_plan, raison, m))
            page.close()  # libère la mémoire (gros PDF d'architecte)
    return tri


def choisir_pages(tri: list[TriPage]) -> tuple[list[int], bool]:
    """Pages à lire comme plans, et « doute » si aucune page ne ressemble clairement à un plan
    (on prend alors la page la plus dessinée, ou la plus grande image, et elle part en vérification)."""
    plans = [t.numero for t in tri if t.est_plan]
    if plans:
        return plans, False
    candidates = [t for t in tri if t.nature != "vide" or t.mesures.nb_segments or t.mesures.part_image]
    if not candidates:
        return [], True
    meilleure = max(candidates, key=lambda t: (t.mesures.longueur_traits_pt, t.mesures.part_image))
    return [meilleure.numero], True


def rendre_page(chemin: str | Path, numero: int, dpi: int = DPI_RENDU,
                cote_max_px: int = COTE_MAX_PX) -> tuple[np.ndarray, float]:
    """Image nette d'une page (numéro à partir de 1), au format OpenCV (BGR, uint8), et le nombre de
    pixels par point PDF (300 dpi → 4,17 px/pt), qui relie l'image aux positions des textes."""
    import pypdfium2 as pdfium

    chemin = Path(chemin)
    if not chemin.is_file():
        raise FileNotFoundError(f"PDF introuvable : {chemin}")
    try:
        document = pdfium.PdfDocument(str(chemin))
    except pdfium.PdfiumError as e:
        raise PdfIllisible(f"PDF illisible : {chemin.name} ({e})") from e
    try:
        page = document[numero - 1]
        largeur, hauteur = page.get_size()
        echelle = dpi / 72
        if max(largeur, hauteur) * echelle > cote_max_px:
            echelle = cote_max_px / max(largeur, hauteur)
        image = page.render(scale=echelle).to_pil().convert("RGB")
        page.close()
    finally:
        document.close()
    return np.asarray(image)[:, :, ::-1].copy(), echelle


# ---------- Partie 2 (étape A2-3) : les TEXTES EXACTS d'une page vectorielle ----------


def _mots(page) -> list[dict]:
    """Les mots de la page (lettres regroupées), dans le bon sens de lecture.

    Chaque lettre porte dans le PDF sa propre orientation (sa « matrice », donnée dans le sens où la page
    s'affiche) : à l'endroit, à l'envers (page tournée de 180°), de bas en haut (le plus courant pour une
    cote de mur vertical) ou de haut en bas. On lit chacune de ces quatre familles dans son sens.
    Les espaces sont gardés dans un mot (« Séjour 25,92 m² » reste un seul texte, comme le donne l'OCR) ;
    deux textes séparés par un vide sans espace (« 4,80 » … « 3,10 ») restent deux."""
    def famille(o) -> int:
        a, b = (o.get("matrix") or (1, 0))[:2]
        if o.get("upright", True):
            return 0 if a >= 0 else 1
        return 2 if b > 0 else 3

    sens = ({}, {"char_dir": "rtl", "line_dir": "btt"}, {"char_dir_rotated": "btt"}, {"char_dir_rotated": "ttb"})
    mots = []
    for f, reglages in enumerate(sens):
        filtre = page.filter(lambda o, f=f: o.get("object_type") != "char" or famille(o) == f)
        mots += filtre.extract_words(keep_blank_chars=True, **reglages)
    return mots


def textes_de_la_page(page, px_par_pt: float) -> list[TexteLu]:
    """Les textes d'une page pdfplumber, au même format que l'OCR (moteur.lecture_cotes.TexteLu), en
    pixels de l'image rendue par rendre_page (`px_par_pt`). Confiance 1 : le texte est celui du fichier.
    Un mot qui contient une lettre illisible (« (cid:22) ») est laissé de côté."""
    x0p, y0p = page.bbox[0], page.bbox[1]  # la zone visible (CropBox) peut ne pas commencer à 0
    textes = []
    for m in _mots(page):
        texte = " ".join(m["text"].split())
        if not texte or "(cid:" in texte or any(_caractere_illisible(c) for c in texte):
            continue
        x0, x1 = (m["x0"] - x0p) * px_par_pt, (m["x1"] - x0p) * px_par_pt
        y0, y1 = (m["top"] - y0p) * px_par_pt, (m["bottom"] - y0p) * px_par_pt
        boite = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)
        textes.append(TexteLu(texte, boite, 1.0))
    return textes


def lire_textes_pdf(chemin: str | Path, numero: int, px_par_pt: float) -> list[TexteLu]:
    """Les textes exacts de la page `numero` (à partir de 1), placés sur l'image de rendre_page."""
    with _ouvrir(chemin) as pdf:
        page = pdf.pages[numero - 1]
        textes = textes_de_la_page(page, px_par_pt)
        page.close()
    return textes


@dataclass
class PagePdfLue:
    """Une page de plan prête pour Atelya : l'image nette à colorier et, si la page est vectorielle,
    ses textes exacts (sinon None : les textes seront lus par l'OCR sur l'image, comme aujourd'hui)."""
    numero: int
    nature: str
    raison: str
    image: np.ndarray  # BGR, format OpenCV (recadrée sur la zone dessinée, voir zone_dessinee)
    px_par_pt: float
    textes: list[TexteLu] | None
    origine_px: tuple[int, int] = (0, 0)  # où commence l'image recadrée, en pixels de la page entière rendue
    # La page est à plat par construction (dessin vectoriel, piégé ou non) : jamais de redressement de perspective.
    # Une page scannée peut être la photo d'un plan rangée dans un PDF : elle garde le redressement habituel.
    a_plat: bool = False


CADRE_PAGE = 0.9  # un trait ou un rectangle qui fait 90 % de la page : le cadre, pas le dessin
MARGE_RECADRAGE = 0.04  # marge gardée autour de la zone dessinée (part de son grand côté) …
MARGE_RECADRAGE_PT = 15.0  # … plus 15 points (5 mm), pour les textes des cotes posés à côté de leurs traits


def zone_dessinee(page) -> tuple[float, float, float, float] | None:
    """La zone de la page où se trouve le dessin (points, page affichée, origine en haut à gauche), marge comprise.

    Pourquoi (étape A2-6) : Atelya réduit toute l'image à 768 pixels avant de la colorier. Sur une page A3 aux
    grandes marges, le logement n'occupait que 44 % de l'image (68 % sur les plans en image) : Atelya le voyait
    1,5 fois plus petit et le lisait moins bien (murs justes 90,7 → 82,2 %). On garde donc seulement la zone des
    traits et des images, sans le cadre de la page ; les textes loin du dessin (cartouche) n'y sont pas nécessaires :
    leurs valeurs restent lues (échelle écrite), seule l'image est recadrée."""
    x0p, y0p = page.bbox[0], page.bbox[1]
    l, h = page.width, page.height
    boites = []
    for o in list(page.lines) + list(page.rects) + list(page.curves) + list(page.images):
        a, b, c, d = o["x0"] - x0p, o["top"] - y0p, o["x1"] - x0p, o["bottom"] - y0p
        if c - a >= CADRE_PAGE * l or d - b >= CADRE_PAGE * h:
            continue
        boites.append((a, b, c, d))
    if not boites:
        return None
    b = np.array(boites)
    a, t, c, d = b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()
    m = MARGE_RECADRAGE * max(c - a, d - t) + MARGE_RECADRAGE_PT
    return max(0.0, a - m), max(0.0, t - m), min(l, c + m), min(h, d + m)


def lire_page(chemin: str | Path, numero: int, tri: TriPage | None = None, dpi: int = DPI_RENDU,
              cote_max_px: int = COTE_MAX_PX, recadrer: bool = True) -> PagePdfLue:
    """Image + textes d'une page. Les textes exacts ne sont pris que sur une page « vectorielle » : sur une
    page piégée ou scannée, ils sont absents ou faux, et c'est l'OCR qui lira l'image.
    `recadrer` : l'image est coupée sur la zone dessinée (zone_dessinee) ; les textes sont placés sur l'image coupée."""
    if tri is None:
        tri = trier_pdf(chemin)[numero - 1]
    image, px_par_pt = rendre_page(chemin, numero, dpi, cote_max_px)
    origine = (0, 0)
    with _ouvrir(chemin) as pdf:
        page = pdf.pages[numero - 1]
        zone = zone_dessinee(page) if recadrer else None
        textes = textes_de_la_page(page, px_par_pt) if tri.nature == "vectorielle" else None
        page.close()
    if zone is not None:
        h, w = image.shape[:2]
        x0, y0 = max(0, int(zone[0] * px_par_pt)), max(0, int(zone[1] * px_par_pt))
        x1, y1 = min(w, int(math.ceil(zone[2] * px_par_pt))), min(h, int(math.ceil(zone[3] * px_par_pt)))
        if x1 - x0 >= 16 and y1 - y0 >= 16:
            image, origine = np.ascontiguousarray(image[y0:y1, x0:x1]), (x0, y0)
            for t in textes or []:
                t.boite = t.boite - np.array(origine, float)
    return PagePdfLue(numero, tri.nature, tri.raison, image, px_par_pt, textes, origine,
                      a_plat=tri.nature in ("vectorielle", "piegee"))


# ---------- Partie 3 (étape A2-4) : l'ÉCHELLE ÉCRITE (« Éch. 1/50 ») ----------

# Échelles d'architecte courantes : un « 1/7 » ou un « 1/2 » écrit sur un plan est une fraction, pas une échelle.
ECHELLES_ARCHITECTE = (20, 25, 50, 75, 100, 125, 150, 200, 250, 500)
# « 1/50 », « 1:100 », « 1/50e », « 1/50ème » ; pas « 01/05/2026 » (date) ni « 11/50 » ni « 1/50,5 ».
FORME_ECHELLE = re.compile(r"(?<![\d/.,:])1\s*[/:]\s*(\d{2,3})(?:\s*(?:e|è|ème|eme)\b)?(?![\d/.,:])", re.IGNORECASE)
MOT_ECHELLE = re.compile(r"[ée]ch|scale", re.IGNORECASE)  # « Éch. », « ECHELLE », « échelle », « scale »


def echelles_ecrites(textes: list[TexteLu]) -> list[tuple[int, bool]]:
    """Les échelles écrites trouvées dans les textes : (dénominateur, précédée du mot « échelle »)."""
    trouvees = []
    for t in textes:
        for m in FORME_ECHELLE.finditer(t.texte):
            n = int(m.group(1))
            if n in ECHELLES_ARCHITECTE:
                trouvees.append((n, bool(MOT_ECHELLE.search(t.texte[:m.start()]))))
    return trouvees


def echelle_ecrite(textes: list[TexteLu], px_par_pt: float) -> tuple[float | None, str]:
    """L'échelle de l'image (pixels par mètre) donnée par l'échelle écrite sur le plan, et le détail en clair.

    Pourquoi c'est possible dans un PDF (et pas sur une photo) : le PDF connaît la taille réelle de sa feuille, en
    points (1/72 de pouce). Au 1/50, 1 m réel fait 20 mm sur la feuille, soit 56,69 points, soit 236 pixels à 300 dpi.
    Si le plan porte plusieurs échelles différentes (plan au 1/50 et plan de situation au 1/500), on garde celle qui
    suit le mot « échelle » si elle est seule dans ce cas ; sinon on ne choisit pas (None).
    ATTENTION : un PDF imprimé « ajusté à la page » garde son « 1/50 » écrit mais n'est plus au 1/50. Cette échelle
    n'est donc jamais prise seule : moteur.echelle_plan.decider la contrôle (cotes, surfaces, portes)."""
    trouvees = echelles_ecrites(textes)
    valeurs = sorted({n for n, _ in trouvees})
    if len(valeurs) > 1:
        valeurs = sorted({n for n, mot in trouvees if mot})
        if len(valeurs) != 1:
            return None, f"plusieurs échelles écrites ({', '.join(f'1/{n}' for n, _ in trouvees)}) : pas de choix"
    if not valeurs:
        return None, ""
    n = valeurs[0]
    px_par_m = 1000 / n * (72 / 25.4) * px_par_pt  # mm de feuille par mètre réel → points → pixels
    return px_par_m, f"échelle écrite 1/{n}"


def pour_les_noms(textes: list[TexteLu]) -> list[tuple[str, float, float, float]]:
    """Les textes au format de moteur.noms_pieces (texte, x du milieu, y du milieu, confiance)."""
    return [(t.texte, float(t.boite[:, 0].mean()), float(t.boite[:, 1].mean()), t.confiance) for t in textes]


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Trier les pages d'un PDF de plan (étape A2).")
    parser.add_argument("pdf", help="fichier PDF")
    parser.add_argument("--json", action="store_true", help="sortie détaillée en JSON")
    a = parser.parse_args(arguments)
    tri = trier_pdf(a.pdf)
    if a.json:
        import json

        print(json.dumps([asdict(t) for t in tri], ensure_ascii=False, indent=2))
        return
    for t in tri:
        print(f"page {t.numero} : {t.nature:<11} {'PLAN' if t.est_plan else '----'}  {t.raison}")
    pages, doute = choisir_pages(tri)
    print(f"pages à lire : {pages}" + ("  (à vérifier : aucun plan évident)" if doute else ""))


if __name__ == "__main__":
    main()
