"""Écrire de petits PDF vectoriels, sans bibliothèque (étape A2).

Un PDF « vectoriel » contient des ordres de dessin (« trait de tel point à tel point », « texte 3,40 à
tel endroit ») au lieu d'une photo. Ce module en fabrique, pour deux usages :
- les tests de la lecture des PDF (moteur/lecture_pdf.py) : plan vectoriel, plan scanné (une image
  dans le PDF), textes illisibles (police sans table de correspondance), page de texte seul ;
- plus tard (étape A2-5), des PDF de plans fabriqués dont on connaît la vérité exacte.

Unités : le point PDF (1/72 de pouce = 0,3528 mm). Origine EN HAUT À GAUCHE, y vers le bas, comme
pdfplumber et comme les images ; la conversion vers le repère PDF (origine en bas) est faite ici.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

A4 = (595.28, 841.89)
A3 = (841.89, 1190.55)
MM = 72 / 25.4  # points par millimètre


def _nombre(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _texte_pdf(texte: str) -> str:
    """Chaîne PDF littérale en WinAnsi (accents, ², °…), parenthèses et barres échappées."""
    octets = texte.encode("cp1252", errors="replace")
    sortie = []
    for o in octets:
        c = chr(o)
        if c in "()\\":
            sortie.append("\\" + c)
        elif 32 <= o < 127:
            sortie.append(c)
        else:
            sortie.append(f"\\{o:03o}")
    return "(" + "".join(sortie) + ")"


def _couleur(c) -> str:
    """Gris (0 noir à 1 blanc) ou (R, G, B) de 0 à 255 → « r g b » du PDF."""
    if isinstance(c, (int, float)):
        return f"{_nombre(c)} {_nombre(c)} {_nombre(c)}"
    return " ".join(_nombre(v / 255) for v in c[:3])


def largeur_texte(texte: str, taille: float) -> float:
    """Largeur d'un texte en Helvetica (points), avec les largeurs que lira pdfplumber (pdfminer)."""
    try:
        from pdfminer.fontmetrics import FONT_METRICS

        largeurs = FONT_METRICS["Helvetica"][1]
    except ImportError:  # sans pdfminer (Mac) : largeur moyenne d'un chiffre
        largeurs = {}
    return sum(largeurs.get(c, 556) for c in texte) * taille / 1000


@dataclass
class PageVectorielle:
    largeur: float
    hauteur: float
    ordres: list[str] = field(default_factory=list)
    images: list[np.ndarray] = field(default_factory=list)
    illisible: bool = False  # la page utilise la police sans correspondance
    rotation: int = 0  # /Rotate : la page s'affiche tournée (90, 180, 270), comme certains PDF scannés ou exportés

    def _y(self, y: float) -> float:
        return self.hauteur - y

    def trait(self, x1: float, y1: float, x2: float, y2: float, epaisseur: float = 0.5) -> None:
        self.ordres.append(f"{_nombre(epaisseur)} w {_nombre(x1)} {_nombre(self._y(y1))} m "
                           f"{_nombre(x2)} {_nombre(self._y(y2))} l S")

    def rectangle(self, x: float, y: float, l: float, h: float, plein: bool = True,
                  gris: float = 0.0, epaisseur: float = 0.5) -> None:
        """Rectangle (x, y) = coin haut-gauche. Plein = mur noir (gris 0) ou gris clair (0,8)."""
        r = f"{_nombre(x)} {_nombre(self._y(y + h))} {_nombre(l)} {_nombre(h)} re"
        if plein:
            self.ordres.append(f"{_nombre(gris)} g {r} f 0 g")
        else:
            self.ordres.append(f"{_nombre(epaisseur)} w {r} S")

    def arc(self, cx: float, cy: float, r: float, debut_deg: float, fin_deg: float,
            epaisseur: float = 0.3) -> None:
        """Arc de cercle (battant de porte), angles en degrés, sens des aiguilles d'une montre à
        l'écran (y vers le bas). Courbes de Bézier par morceaux de 90° au plus."""
        n = max(1, math.ceil(abs(fin_deg - debut_deg) / 90))
        pas = math.radians(fin_deg - debut_deg) / n
        k = 4 / 3 * math.tan(pas / 4)
        a = math.radians(debut_deg)
        x0, y0 = cx + r * math.cos(a), cy + r * math.sin(a)
        morceaux = [f"{_nombre(epaisseur)} w {_nombre(x0)} {_nombre(self._y(y0))} m"]
        for _ in range(n):
            b = a + pas
            p1 = (cx + r * (math.cos(a) - k * math.sin(a)), cy + r * (math.sin(a) + k * math.cos(a)))
            p2 = (cx + r * (math.cos(b) + k * math.sin(b)), cy + r * (math.sin(b) - k * math.cos(b)))
            p3 = (cx + r * math.cos(b), cy + r * math.sin(b))
            morceaux.append(" ".join(f"{_nombre(px)} {_nombre(self._y(py))}" for px, py in (p1, p2, p3)) + " c")
            a = b
        self.ordres.append(" ".join(morceaux) + " S")

    def texte(self, x: float, y: float, texte: str, taille: float = 9, lisible: bool = True,
              vertical: bool = False) -> None:
        """Texte dont la ligne de base gauche est en (x, y). lisible=False : police sans table de
        correspondance → un lecteur de PDF ne retrouve pas les lettres (cas des PDF « piégés »).
        vertical=True : texte tourné d'un quart de tour, qui se lit de bas en haut (cote d'un mur vertical)."""
        sens = "0 1 -1 0" if vertical else "1 0 0 1"
        position = f"{sens} {_nombre(x)} {_nombre(self._y(y))} Tm"
        if lisible:
            self.ordres.append(f"BT /F1 {_nombre(taille)} Tf {position} {_texte_pdf(texte)} Tj ET")
        else:
            self.illisible = True
            code = "".join(f"{(ord(c) % 200) + 3:04X}" for c in texte)
            self.ordres.append(f"BT /F2 {_nombre(taille)} Tf {position} <{code}> Tj ET")

    def image(self, x: float, y: float, l: float, h: float, gris: np.ndarray) -> None:
        """Image en niveaux de gris (uint8) posée dans le rectangle (x, y, l, h) : un « scan »."""
        self.images.append(np.ascontiguousarray(gris, dtype=np.uint8))
        nom = f"Im{len(self.images)}"
        self.ordres.append(f"q {_nombre(l)} 0 0 {_nombre(h)} {_nombre(x)} {_nombre(self._y(y + h))} cm "
                           f"/{nom} Do Q")

    # ---- en couleurs (étape A2-5 : redessiner les plans du générateur) ----

    def chemin(self, points: list[tuple[float, float]], remplissage=None, contour=None, epaisseur: float = 0.5,
               ferme: bool = True) -> None:
        """Polygone (ferme) ou ligne brisée, rempli et/ou tracé. Couleurs : gris 0-1 ou (R, G, B) 0-255."""
        if len(points) < 2 or (remplissage is None and contour is None):
            return
        corps = f"{_nombre(points[0][0])} {_nombre(self._y(points[0][1]))} m " + " ".join(
            f"{_nombre(x)} {_nombre(self._y(y))} l" for x, y in points[1:])
        if ferme:
            corps += " h"
        peinture = "B" if remplissage is not None and contour is not None else ("f" if contour is None else "S")
        if not ferme and contour is not None:
            peinture = "S"
        reglages = ""
        if remplissage is not None:
            reglages += f"{_couleur(remplissage)} rg "
        if contour is not None:
            reglages += f"{_couleur(contour)} RG {_nombre(epaisseur)} w 1 j "
        self.ordres.append(f"q {reglages}{corps} {peinture} Q")

    def ellipse(self, x0: float, y0: float, x1: float, y1: float, contour=0.0, epaisseur: float = 0.5) -> None:
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        k = 0.5523  # 4/3 (√2 − 1) : quatre quarts de cercle en courbes de Bézier
        p = [(cx + rx, cy), (cx, cy + ry), (cx - rx, cy), (cx, cy - ry)]
        c = [((cx + rx, cy + k * ry), (cx + k * rx, cy + ry)), ((cx - k * rx, cy + ry), (cx - rx, cy + k * ry)),
             ((cx - rx, cy - k * ry), (cx - k * rx, cy - ry)), ((cx + k * rx, cy - ry), (cx + rx, cy - k * ry))]
        f = lambda q: f"{_nombre(q[0])} {_nombre(self._y(q[1]))}"  # noqa: E731
        corps = f"{f(p[0])} m " + " ".join(f"{f(a)} {f(b)} {f(p[(i + 1) % 4])} c" for i, (a, b) in enumerate(c))
        self.ordres.append(f"q {_couleur(contour)} RG {_nombre(epaisseur)} w {corps} S Q")

    def arc_colore(self, cx: float, cy: float, r: float, debut_deg: float, fin_deg: float, couleur=0.0,
                   epaisseur: float = 0.3) -> None:
        n = len(self.ordres)
        self.arc(cx, cy, r, debut_deg, fin_deg, epaisseur)
        self.ordres[n] = f"q {_couleur(couleur)} RG {self.ordres[n]} Q"

    def texte_ancre(self, x: float, y: float, texte: str, taille: float, couleur=0.0, ancre: str = "ls",
                    lisible: bool = True, vertical: bool = False) -> None:
        """Texte posé comme Pillow : ancre « l » (gauche) ou « m » (milieu) puis « s » (ligne de base) ou « m »
        (milieu de la hauteur). Un texte vertical (de bas en haut) est centré sur (x, y)."""
        largeur = largeur_texte(texte, taille)
        milieu = 0.35 * taille  # du milieu des lettres à la ligne de base (Helvetica : capitales 0,72 em)
        if vertical:
            bx, by = x + milieu, y + largeur / 2
        else:
            bx = x - (largeur / 2 if ancre[0] == "m" else 0)
            by = y + (milieu if ancre[1] == "m" else 0)
        n = len(self.ordres)
        self.texte(bx, by, texte, taille, lisible, vertical)
        self.ordres[n] = f"q {_couleur(couleur)} rg {self.ordres[n]} Q"


class DocumentPdf:
    def __init__(self) -> None:
        self.pages: list[PageVectorielle] = []

    def page(self, taille: tuple[float, float] = A4) -> PageVectorielle:
        p = PageVectorielle(*taille)
        self.pages.append(p)
        return p

    def octets(self) -> bytes:
        objets: list[bytes] = []

        def ajouter(contenu: bytes) -> int:
            objets.append(contenu)
            return len(objets)

        catalogue = ajouter(b"")  # rempli à la fin
        racine_pages = ajouter(b"")
        police = ajouter(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        descendante = ajouter(b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Arial "
                              b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> >>")
        illisible = ajouter(b"<< /Type /Font /Subtype /Type0 /BaseFont /Arial /Encoding /Identity-H "
                            b"/DescendantFonts [%d 0 R] >>" % descendante)
        enfants = []
        for p in self.pages:
            refs_images = []
            for img in p.images:
                donnees = zlib.compress(img.tobytes())
                refs_images.append(ajouter(
                    b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
                    b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>stream\n"
                    % (img.shape[1], img.shape[0], len(donnees)) + donnees + b"\nendstream"))
            flux = ("\n".join(p.ordres) + "\n").encode("latin-1")
            contenu = ajouter(b"<< /Length %d >>stream\n" % len(flux) + flux + b"endstream")
            xobjets = b" ".join(b"/Im%d %d 0 R" % (i + 1, r) for i, r in enumerate(refs_images))
            enfants.append(ajouter(
                (f"<< /Type /Page /Parent {racine_pages} 0 R /MediaBox [0 0 {_nombre(p.largeur)} "
                 f"{_nombre(p.hauteur)}] /Rotate {p.rotation % 360} /Contents {contenu} 0 R /Resources << /Font << /F1 {police} 0 R "
                 f"/F2 {illisible} 0 R >> ").encode() + b"/XObject << " + xobjets + b" >> >> >>"))
        objets[catalogue - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % racine_pages
        objets[racine_pages - 1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % e for e in enfants)
                                    + b"] /Count %d >>" % len(enfants))
        sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        positions = []
        for i, o in enumerate(objets, 1):
            positions.append(len(sortie))
            sortie += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(sortie)
        sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
        sortie += b"".join(b"%010d 00000 n \n" % p for p in positions)
        sortie += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, catalogue, xref)
        return bytes(sortie)

    def enregistrer(self, chemin: str | Path) -> Path:
        chemin = Path(chemin)
        chemin.write_bytes(self.octets())
        return chemin
