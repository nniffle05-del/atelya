"""Les plans du générateur, écrits en PDF (étape A2-5) : des PDF dont on connaît la vérité exacte.

Pourquoi : pour mesurer la lecture des PDF (étape A2-6), il faut des centaines de PDF dont on connaît le
vrai logement. On n'a aucun vrai PDF de plan (les 13 vrais plans d'examen sont des photos JPG). On reprend
donc les plans du jeu de test (mêmes graines, mêmes logements, même style de dessin) et on les écrit en PDF.

Comment : le générateur dessine avec Pillow (traits, polygones, arcs, textes). Un « enregistreur » se glisse
entre le dessin et Pillow : chaque ordre est exécuté comme avant (l'image et les masques ne changent pas)
ET recopié en ordre PDF vectoriel, au même endroit. Le PDF est donc le même plan, mais en traits et
textes exacts, placé sur une feuille A4 ou A3 à une vraie échelle d'architecte (1/50, 1/100 ou 1/200).
Différences voulues : le plan est remis à plat et propre (un PDF exporté d'un logiciel n'est ni penché, ni
photographié, ni sali) ; les textes sont en Helvetica (la police standard des PDF) au lieu de la police du dessin.

Sortes de PDF (`SORTES`) :
- « vectorielle » : traits et textes exacts ;
- « piegee »      : mêmes traits, textes illisibles (police sans table de correspondance) ;
- « scannee »     : l'image du plan rangée dans le PDF, sans aucun texte ;
- « reduite »     : PDF imprimé « ajusté à la page » : tout est 0,707 fois plus petit (A3 → A4), mais
                    l'échelle écrite dit toujours « 1/50 » (piège pour l'échelle écrite) ;
- « tournee »     : page enregistrée couchée (/Rotate 90) ;
- « dossier »     : trois pages, page de garde + plan + tableau des surfaces (comme un rapport de diagnostic).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from moteur.ecrire_pdf import A3, A4, MM, DocumentPdf, PageVectorielle
from moteur.images import ecrire_image
from moteur.generateur.logements import LogementGenere, Niveau, generer, surface_piece
from moteur.generateur.mobilier import meubler_niveau
from moteur.generateur.rendu import Repere, _cadre_des_murs, _Dessin, _fr
from moteur.generateur.variantes import Style

VERSION_PLAN_PDF = "0.1.0"
SORTES = ("vectorielle", "piegee", "scannee", "reduite", "tournee", "dossier")
SORTES_EN_PLUS = ("piegee", "scannee", "reduite", "tournee", "dossier")  # une par niveau, en plus de la vectorielle
# Les échelles et formats essayés, dans l'ordre : le plus grand dessin qui tient sur la feuille.
MISES_EN_PAGE = ((50, "A4", A4), (50, "A3", A3), (100, "A4", A4), (100, "A3", A3), (200, "A4", A4), (200, "A3", A3))
MARGE_PAGE = 10 * MM  # marge blanche autour du dessin
REDUCTION = 0.707  # A3 imprimé sur A4 (« ajuster à la page »)


class _Enregistreur:
    """Se glisse à la place du ImageDraw de Pillow : dessine comme avant ET écrit le même ordre en PDF.

    Coordonnées : un pixel (x, y) de l'image à plat du générateur devient le point PDF (ox + k x, oy + k y)."""

    def __init__(self, dessin, page: PageVectorielle, k: float, ox: float, oy: float):
        self.d, self.page, self.k, self.ox, self.oy = dessin, page, k, ox, oy
        self.oublis: set[str] = set()

    def _pt(self, x: float, y: float) -> tuple[float, float]:
        return self.ox + self.k * x, self.oy + self.k * y

    def _points(self, xy) -> list[tuple[float, float]]:
        xy = list(xy)
        if xy and not isinstance(xy[0], (tuple, list, np.ndarray)):
            xy = list(zip(xy[0::2], xy[1::2]))
        return [self._pt(float(x), float(y)) for x, y in xy]

    def _ep(self, width) -> float:
        return max(0.1, (width or 1) * self.k)

    def line(self, xy, fill=None, width=1, **kw):
        self.d.line(xy, fill=fill, width=width, **kw)
        if fill is not None:
            self.page.chemin(self._points(xy), contour=fill, epaisseur=self._ep(width), ferme=False)

    def polygon(self, xy, fill=None, outline=None, width=1):
        self.d.polygon(xy, fill=fill, outline=outline, width=width)
        self.page.chemin(self._points(xy), remplissage=fill, contour=outline, epaisseur=self._ep(width))

    def rectangle(self, xy, fill=None, outline=None, width=1):
        self.d.rectangle(xy, fill=fill, outline=outline, width=width)
        (x0, y0), (x1, y1) = self._points(xy)
        self.page.chemin([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], remplissage=fill, contour=outline,
                         epaisseur=self._ep(width))

    def ellipse(self, xy, fill=None, outline=None, width=1):
        self.d.ellipse(xy, fill=fill, outline=outline, width=width)
        (x0, y0), (x1, y1) = self._points(xy)
        self.page.ellipse(x0, y0, x1, y1, contour=outline if outline is not None else 0.0, epaisseur=self._ep(width))

    def arc(self, xy, start, end, fill=None, width=1):
        self.d.arc(xy, start, end, fill=fill, width=width)
        (x0, y0), (x1, y1) = self._points(xy)
        fin = end if end > start else end + 360
        self.page.arc_colore((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, start, fin,
                             fill if fill is not None else 0.0, self._ep(width))

    def text(self, xy, text, fill=None, font=None, anchor=None, **kw):
        self.d.text(xy, text, fill=fill, font=font, anchor=anchor, **kw)
        x, y = self._pt(*xy)
        self.page.texte_ancre(x, y, text, (font.size if font else 10) * self.k, fill if fill is not None else 0.0,
                              anchor or "la")

    def __getattr__(self, nom):  # un ordre de dessin non prévu : exécuté sur l'image, noté comme oubli
        self.oublis.add(nom)
        return getattr(self.d, nom)


class _DessinPdf(_Dessin):
    """Le dessin du générateur, avec l'enregistreur à la place de Pillow, et les textes écrits en PDF."""

    def __init__(self, *args, page: PageVectorielle, k: float, ox: float, oy: float, lisible: bool, **kw):
        super().__init__(*args, **kw)
        self.page, self.lisible = page, lisible
        self.d = _Enregistreur(self.d, page, k, ox, oy)

    def texte(self, xy, texte: str, taille: int, couleur, ancre: str = "mm", vertical: bool = False) -> None:
        e = self.d
        x, y = e._pt(*xy)
        self.page.texte_ancre(x, y, texte, taille * e.k, couleur, ancre, lisible=self.lisible, vertical=vertical)
        self.d = e.d  # l'image se dessine comme avant, sans écrire le texte une 2e fois dans le PDF
        try:
            super().texte(xy, texte, taille, couleur, ancre, vertical)
        finally:
            self.d = e


def style_a_plat(style: Style) -> Style:
    """Le style d'un PDF exporté d'un logiciel : ni penché, ni photographié, ni sali (couleurs, textes, cotes gardés)."""
    return replace(style, rotation=0.0, perspective=0.0, focale=0.0, focale_photo=0.0, inclinaison=(0.0, 0.0),
                   centre_optique=(0.0, 0.0), salissure="", contraste=1.0, papier=255, variete=None, realisme=None, lot2=None)


def mise_en_page(largeur_px: float, hauteur_px: float, px_par_m: float) -> tuple[int, str, tuple[float, float], float]:
    """(échelle 1/n, format, taille de la page en points, points par pixel) : le plus grand dessin qui tient."""
    for n, nom, (lp, hp) in MISES_EN_PAGE:
        k = 1000 / n * MM / px_par_m
        l, h = largeur_px * k, hauteur_px * k
        for page in ((lp, hp), (hp, lp)):
            if l <= page[0] - 2 * MARGE_PAGE and h <= page[1] - 2 * MARGE_PAGE:
                return n, nom, page, k
    n, nom, (lp, hp) = MISES_EN_PAGE[-1]  # très grand logement : 1/200 sur A3, quitte à déborder un peu
    k = 1000 / n * MM / px_par_m
    return n, nom, ((hp, lp) if largeur_px > hauteur_px else (lp, hp)), k


@dataclass
class PdfFabrique:
    octets: bytes
    infos: dict
    masque: np.ndarray | None = None  # la vérité pixel par pixel (classes), dans les pixels de l'image du générateur


def pdf_du_niveau(log: LogementGenere, niveau: Niveau, style: Style, sorte: str = "vectorielle",
                  echelle_ecrite: bool = True, graine_style: str = "0") -> PdfFabrique:
    """Le PDF d'un niveau d'un logement fabriqué, et ce qu'il faut pour retrouver la vérité (`infos`)."""
    if sorte not in SORTES:
        raise ValueError(f"sorte de PDF inconnue : {sorte}")
    st = style_a_plat(style)
    rep = Repere(_cadre_des_murs(niveau), st, random.Random(f"rendu-{log.graine}-{niveau.index}-{graine_style}"))
    tous = meubler_niveau(niveau, log.graine)
    escaliers = {pid: [m for m in lst if m.forme == "marches"] for pid, lst in tous.items()}
    meubles = tous if st.mobilier else {pid: lst for pid, lst in escaliers.items() if lst}
    n, format_, (lp, hp), k = mise_en_page(rep.largeur0, rep.hauteur0, st.px_par_m)
    reduction = REDUCTION if sorte == "reduite" else 1.0
    lp, hp, k = lp * reduction, hp * reduction, k * reduction
    ox, oy = (lp - rep.largeur0 * k) / 2, (hp - rep.hauteur0 * k) / 2

    doc = DocumentPdf()
    if sorte == "dossier":
        _page_de_garde(doc.page(A4), log, niveau)
    page = doc.page((lp, hp))
    if sorte == "scannee":
        d = _Dessin(log, niveau, st, rep, meubles, avec_mobilier=True)
        d.tout()
        gris = np.asarray(d.image.convert("L"))
        page.image(ox, oy, rep.largeur0 * k, rep.hauteur0 * k, gris)
        oublis: set[str] = set()
    else:
        d = _DessinPdf(log, niveau, st, rep, meubles, True, page=page, k=k, ox=ox, oy=oy,
                       lisible=sorte != "piegee")
        d.tout()
        oublis = d.d.oublis
        if echelle_ecrite:
            page.texte_ancre(ox + 4 * MM * reduction, hp - 6 * MM * reduction, f"Échelle 1/{n}", 9 * reduction,
                             0.2, "ls", lisible=sorte != "piegee")
    if sorte == "tournee":
        page.rotation = 90
    if sorte == "dossier":
        _tableau_des_surfaces(doc.page(A4), niveau)
    pt_par_m = st.px_par_m * k
    infos = {
        "version": VERSION_PLAN_PDF, "graine": log.graine, "niveau": niveau.index, "sorte": sorte,
        "page_du_plan": 2 if sorte == "dossier" else 1, "pages": len(doc.pages),
        "echelle_vraie": n, "echelle_ecrite": f"1/{n}" if echelle_ecrite and sorte != "scannee" else None,
        "format": format_, "reduction": reduction, "rotation": page.rotation,
        "page_pt": [round(lp, 3), round(hp, 3)],
        # La vérité : 1 m du logement = pt_par_m points PDF (à 300 dpi : pt_par_m × 300/72 pixels).
        "pt_par_m": round(pt_par_m, 6), "pt_par_px_image": round(k, 8), "decalage_pt": [round(ox, 3), round(oy, 3)],
        "matrice_mm_vers_pt": (np.diag([k, k, 1.0]) @ np.array([[1, 0, ox / k], [0, 1, oy / k], [0, 0, 1]])
                               @ rep.A).round(9).tolist(),
        "image_px": [rep.largeur0, rep.hauteur0], "px_par_m_image": st.px_par_m, "famille": st.famille,
        "cotes": st.cotes, "surfaces": st.surfaces, "barre": st.echelle_graphique,
        "ordres_non_recopies": sorted(oublis),
    }
    return PdfFabrique(doc.octets(), infos, d.semantique)


def _page_de_garde(page: PageVectorielle, log: LogementGenere, niveau: Niveau) -> None:
    lignes = ["Dossier de diagnostic technique", "", f"Logement {log.type} — {_fr(log.surface)} m²".replace(",00", ""),
              "Propriétaire : (anonymisé)", "Adresse : (anonymisée)", f"Référence : {log.graine:06d}-{niveau.index}", "",
              "Sommaire : 1. Page de garde  2. Plan du logement  3. Tableau des surfaces"]
    for i, t in enumerate(lignes):
        page.texte_ancre(60, 120 + i * 22, t, 16 if i == 0 else 11, 0.1)
    page.chemin([(50, 90), (545, 90)], contour=0.2, epaisseur=1, ferme=False)


def _tableau_des_surfaces(page: PageVectorielle, niveau: Niveau) -> None:
    """Un tableau des surfaces : des traits et beaucoup de texte (ce n'est pas un plan)."""
    page.texte_ancre(60, 90, "Tableau des surfaces habitables (indicatives)", 14, 0.1)
    x0, x1, y = 60, 535, 120
    lignes = [("Pièce", "Surface", "Observations")] + [
        (p.nom, f"{_fr(surface_piece(p) / 1e6)} m²", "Mesurée au laser, hauteur sous plafond supérieure à 1,80 m")
        for p in niveau.pieces]
    for i, (a, b, c) in enumerate(lignes):
        yy = y + i * 20
        page.chemin([(x0, yy), (x1, yy)], contour=0.3, epaisseur=0.5, ferme=False)
        for x, t in ((65, a), (190, b), (260, c)):
            page.texte_ancre(x, yy + 14, t, 9, 0.1)
    bas = y + len(lignes) * 20
    page.chemin([(x0, bas), (x1, bas)], contour=0.3, epaisseur=0.5, ferme=False)
    for x in (x0, 180, 250, x1):
        page.chemin([(x, y), (x, bas)], contour=0.3, epaisseur=0.5, ferme=False)


def sorte_en_plus(graine: int, niveau: int) -> str:
    """La 2e sorte de PDF d'un niveau (en plus de la vectorielle) : tirée de la graine, toujours la même."""
    return SORTES_EN_PLUS[random.Random(f"pdf-{graine}-{niveau}").randrange(len(SORTES_EN_PLUS))]


def echelle_ecrite_pour(graine: int, niveau: int) -> bool:
    """Un PDF sur deux porte son échelle écrite (« Échelle 1/50 ») : on mesure les deux cas."""
    return random.Random(f"echelle-ecrite-{graine}-{niveau}").random() < 0.5


# ---------------------------------------------------------------- le jeu de PDF


def fabriquer_jeu(jeu: Path, sortie: Path, ids: list[str] | None = None, partie: str = "test",
                  verifier: bool = True) -> dict:
    """Écrit les PDF des plans du jeu `jeu` (mêmes graines) dans `sortie/exemples/<id>/niveau_<n>/plan-<sorte>.pdf`,
    avec `plan-<sorte>.json` (la vérité). `verifier` : contrôle que le logement et le style refaits sont bien ceux du jeu."""
    from moteur.generateur.exportateur import Options, style_pour
    from moteur.generateur.logements import en_logement
    from moteur.generateur.reglages import Reglages

    if ids is None:
        repartition = json.loads((jeu / "repartition.json").read_text(encoding="utf-8"))
        ids = sorted(repartition[partie]) if isinstance(repartition, dict) and partie in repartition else \
            sorted(p.name for p in (jeu / "exemples").iterdir())
        ids = [i for i in ids if (jeu / "exemples" / i).is_dir()]
    ids = [i for i in ids if not i.endswith("-ensemble")]  # un -ensemble n'a pas de graine à lui : int(ident) échouerait
    reglages, opt = Reglages.charger(None), Options()
    bilan = {"plans": 0, "niveaux": 0, "pdf": 0, "differents": [], "oublis": set(), "par_sorte": {}}
    debut = time.perf_counter()
    for i, ident in enumerate(ids, 1):
        graine = int(ident)
        log = generer(graine, reglages)
        style = style_pour(graine, 0, opt)
        bilan["plans"] += 1
        for niveau in log.niveaux:
            source = jeu / "exemples" / ident
            if verifier and not _meme_plan(source, log, niveau, style, en_logement):
                bilan["differents"].append(f"{ident}-N{niveau.index}")
                continue
            dn = sortie / "exemples" / ident / f"niveau_{niveau.index}"
            dn.mkdir(parents=True, exist_ok=True)
            bilan["niveaux"] += 1
            for sorte in ("vectorielle", sorte_en_plus(graine, niveau.index)):
                f = pdf_du_niveau(log, niveau, style, sorte, echelle_ecrite_pour(graine, niveau.index))
                (dn / f"plan-{sorte}.pdf").write_bytes(f.octets)
                (dn / f"plan-{sorte}.json").write_text(json.dumps(f.infos, ensure_ascii=False, indent=1), encoding="utf-8")
                if not (dn / "masque_semantique.png").exists():  # le même pour toutes les sortes du niveau
                    ecrire_image(dn / "masque_semantique.png", f.masque)
                bilan["pdf"] += 1
                bilan["par_sorte"][sorte] = bilan["par_sorte"].get(sorte, 0) + 1
                bilan["oublis"] |= set(f.infos["ordres_non_recopies"])
        if i % 20 == 0 or i == len(ids):
            ecoule = time.perf_counter() - debut
            print(f"{i}/{len(ids)} plans, {bilan['pdf']} PDF, {ecoule / 60:.1f} min "
                  f"(reste ~{ecoule / i * (len(ids) - i) / 60:.0f} min)", flush=True)
    bilan["oublis"] = sorted(bilan["oublis"])
    bilan["duree_min"] = round((time.perf_counter() - debut) / 60, 1)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "bilan-pdf.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return bilan


def _meme_plan(source: Path, log, niveau: Niveau, style: Style, en_logement) -> bool:
    """Le logement refait est-il celui du jeu (même logement.json), dessiné dans le même style ?"""
    try:
        vrai = json.loads((source / f"logement_niveau{niveau.index}.json").read_text(encoding="utf-8"))
        annot = json.loads((source / f"niveau_{niveau.index}" / "annotations.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    refait = json.loads(json.dumps(en_logement(log, niveau), ensure_ascii=False, default=str))
    style_jeu = annot.get("style", {})
    style_refait = json.loads(json.dumps(style.en_dict(), default=list))
    memes = all(style_refait.get(c) == v for c, v in style_jeu.items())
    return refait == vrai and memes


# ---------------------------------------------------------------- préparer le banc (étape A2-6)


def _matrice_affichage(rotation: int, page_pt: tuple[float, float]) -> np.ndarray:
    """Points de la page à plat → points de la page AFFICHÉE (pdfium tourne la page de /Rotate, sens horaire)."""
    l, h = page_pt
    return {0: np.eye(3), 90: np.array([[0, -1, h], [1, 0, 0], [0, 0, 1]], float),
            180: np.array([[-1, 0, l], [0, -1, h], [0, 0, 1]], float),
            270: np.array([[0, 1, 0], [-1, 0, l], [0, 0, 1]], float)}[rotation % 360]


def preparer_niveau(pdf: Path, jeu: Path, sortie: Path) -> dict:
    """Lit un PDF comme le fera le produit (tri, choix de la page, image nette, textes exacts) et range le
    résultat comme un niveau de jeu du générateur, pour que le coloriage d'Atelya et le banc le notent :
    `sortie/exemples/<plan>-<sorte>/niveau_<n>/` avec plan.png, annotations.json (la vérité, ramenée aux
    pixels de l'image rendue), masque_semantique.png, et textes-pdf.json si la page est vectorielle."""
    import cv2

    from moteur import lecture_pdf as L

    info = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    ident, niv = pdf.parent.parent.name, pdf.parent.name
    sorte = info["sorte"]
    resultat = {"plan": ident, "niveau": niv, "sorte": sorte}
    tri = L.trier_pdf(pdf)
    pages, doute = L.choisir_pages(tri)
    resultat.update(page_choisie=pages, doute=doute, nature=tri[pages[0] - 1].nature if pages else None)
    if pages != [info["page_du_plan"]]:
        resultat["erreur"] = "mauvaise page choisie"
        return resultat
    page = L.lire_page(pdf, pages[0], tri[pages[0] - 1])
    dest = sortie / "exemples" / f"{ident}-{sorte}"
    (dest / niv).mkdir(parents=True, exist_ok=True)
    source = jeu / "exemples" / ident
    for f in ["geometrie.json", *[q.name for q in source.glob("logement_niveau*.json")]]:
        (dest / f).write_bytes((source / f).read_bytes())
    ecrire_image(dest / niv / "plan.png", page.image)
    h, w = page.image.shape[:2]
    # mètres → pixels de l'image rendue : (mm → points à plat) puis rotation de l'affichage puis points → pixels
    A = _matrice_affichage(info["rotation"], info["page_pt"])
    T = np.array([[1, 0, -page.origine_px[0]], [0, 1, -page.origine_px[1]], [0, 0, 1]], float)  # recadrage
    M = T @ np.diag([page.px_par_pt, page.px_par_pt, 1.0]) @ A @ np.array(info["matrice_mm_vers_pt"]) @ np.diag([1000, 1000, 1.0])
    # la vérité pixel par pixel : masque du générateur (pixels de son image) → pixels de l'image rendue
    k, (ox, oy) = info["pt_par_px_image"], info["decalage_pt"]
    P = T @ np.diag([page.px_par_pt, page.px_par_pt, 1.0]) @ A @ np.array([[k, 0, ox], [0, k, oy], [0, 0, 1]])
    from moteur.images import lire_image

    masque = lire_image(pdf.parent / "masque_semantique.png", cv2.IMREAD_UNCHANGED)
    ecrire_image(dest / niv / "masque_semantique.png",
                 cv2.warpAffine(masque, P[:2], (w, h), flags=cv2.INTER_NEAREST, borderValue=0))
    mur = np.argwhere(masque == 1)
    if len(mur):
        (y0, x0), (y1, x1) = mur.min(0), mur.max(0)
        coins = np.c_[[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.ones(4)] @ P.T
        polygone = (coins[:, :2] / coins[:, 2:]).tolist()
    else:
        polygone = [[0, 0], [w, 0], [w, h], [0, h]]
    px_par_m = info["pt_par_m"] * page.px_par_pt
    annotations = {
        "niveau": int(niv.split("_")[1]),
        "image": {"largeur": w, "hauteur": h, "px_par_m": px_par_m, "rotation_deg": float(info["rotation"]),
                  "perspective": 0.0, "matrice_m_vers_px": M.round(9).tolist(), "a_plat": True},
        "murs": [{"polygone_px": polygone}],  # seulement le cadre du logement (sert au centre, si redressement)
        "pdf": {**{c: info[c] for c in ("sorte", "echelle_vraie", "echelle_ecrite", "reduction", "rotation", "format")},
                "page": pages[0], "nature": page.nature, "px_par_pt": page.px_par_pt,
                "origine_px": list(page.origine_px), "a_plat": page.a_plat},
    }
    (dest / niv / "annotations.json").write_text(json.dumps(annotations, ensure_ascii=False, indent=1), encoding="utf-8")
    if page.textes is not None:
        (dest / niv / "textes-pdf.json").write_text(json.dumps(
            {"px_par_pt": page.px_par_pt, "textes": [{"texte": t.texte, "boite": t.boite.round(2).tolist()}
                                                     for t in page.textes]}, ensure_ascii=False), encoding="utf-8")
    resultat["dossier"] = f"{ident}-{sorte}"
    return resultat


def _preparer(args) -> dict:
    pdf, jeu, sortie = args
    try:
        return preparer_niveau(Path(pdf), Path(jeu), Path(sortie))
    except Exception as e:  # noqa: BLE001 — un PDF raté est compté comme tel
        return {"plan": Path(pdf).parent.parent.name, "niveau": Path(pdf).parent.name, "sorte": Path(pdf).stem,
                "erreur": f"{type(e).__name__}: {str(e)[:200]}"}


def preparer_banc(pdfs: Path, jeu: Path, sortie: Path, processus: int = 4, nombre: int = 0) -> dict:
    """Prépare tous les PDF de `pdfs` (fabriquer_jeu) pour le banc ; écrit repartition.json (tout en « test », et
    les pages vectorielles seules en « vecto »)
    et preparation.json (tri, page choisie, erreurs)."""
    from concurrent.futures import ProcessPoolExecutor

    fichiers = sorted(pdfs.glob("exemples/*/niveau_*/plan-*.pdf"))
    if nombre:
        plans = sorted({f.parent.parent.name for f in fichiers})[:nombre]
        fichiers = [f for f in fichiers if f.parent.parent.name in plans]
    debut = time.perf_counter()
    resultats = []
    with ProcessPoolExecutor(processus) as ex:
        for i, r in enumerate(ex.map(_preparer, [(str(f), str(jeu), str(sortie)) for f in fichiers], chunksize=4), 1):
            resultats.append(r)
            if i % 100 == 0 or i == len(fichiers):
                ecoule = time.perf_counter() - debut
                print(f"{i}/{len(fichiers)} PDF préparés, {ecoule / 60:.1f} min "
                      f"(reste ~{ecoule / i * (len(fichiers) - i) / 60:.0f} min)", flush=True)
    ids = sorted({r["dossier"] for r in resultats if "dossier" in r})
    sortie.mkdir(parents=True, exist_ok=True)
    # « vecto » : les seules pages vectorielles, pour noter les mêmes images avec l'OCR (banc --partie vecto)
    vecto = sorted(i for i in ids if i.endswith("-vectorielle"))
    (sortie / "repartition.json").write_text(json.dumps({"test": ids, "vecto": vecto}, ensure_ascii=False), encoding="utf-8")
    bilan = {"pdf": len(fichiers), "prepares": sum("dossier" in r for r in resultats),
             "erreurs": [r for r in resultats if "erreur" in r], "doutes": sum(bool(r.get("doute")) for r in resultats),
             "natures": {n: sum(r.get("nature") == n for r in resultats) for n in ("vectorielle", "piegee", "scannee", "vide")},
             "duree_min": round((time.perf_counter() - debut) / 60, 1)}
    (sortie / "preparation.json").write_text(json.dumps({"bilan": bilan, "pdf": resultats}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    return bilan


def main(arguments: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Écrire en PDF les plans d'un jeu du générateur (étape A2-5), "
                                            "puis les préparer pour le banc de notation (--preparer, étape A2-6).")
    p.add_argument("--jeu", type=Path, required=True, help="dossier du jeu (ex. ..\\atelya\\jeu-test-6-13)")
    p.add_argument("--sortie", type=Path, required=True, help="dossier de sortie (chemin RELATIF sous Windows)")
    p.add_argument("--partie", default="test")
    p.add_argument("--nombre", type=int, default=0, help="seulement les N premiers plans (0 : tous)")
    p.add_argument("--preparer", type=Path, help="dossier des PDF déjà fabriqués : les préparer pour le banc dans --sortie")
    p.add_argument("--processus", type=int, default=4)
    a = p.parse_args(arguments)
    if a.preparer:
        print(json.dumps(preparer_banc(a.preparer, a.jeu, a.sortie, a.processus, a.nombre), ensure_ascii=False, indent=1))
        return
    ids = None
    if a.nombre:
        ids = sorted(x.name for x in (a.jeu / "exemples").iterdir() if x.is_dir())[:a.nombre]
    bilan = fabriquer_jeu(a.jeu, a.sortie, ids, a.partie)
    print(json.dumps({k: v for k, v in bilan.items() if k != "differents"} | {"differents": len(bilan["differents"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
