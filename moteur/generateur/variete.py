"""Les styles « du monde » (option --styles-monde) : les habitudes de dessin des vrais plans français,
plus des styles volontairement absurdes, pour qu'Atelya apprenne qu'un mur reste un mur.

Pourquoi : sur 13 vrais plans (31/10/2026), Atelya a pris un carrelage pour un escalier, a raté
des murs dessinés d'un trait fin ou d'un gris très clair, et n'avait jamais vu les lettres A, B, C, D
des croquis de diagnostiqueur. Ce module ajoute ces façons de dessiner :

- sols dessinés dans les pièces : carrelage, parquet, hachures, points ;
- murs dessinés autrement : trait fin, double trait vide, gris très clair, hachurés, en couleur ;
- lettres A, B, C… le long des murs de chaque pièce (croquis Carrez) ;
- noms en couleur, en majuscules, surfaces entre parenthèses ;
- symboles du neuf : PL, BECS, TGBT, Gaine, cercle de giration de 1,50 m ;
- arcs de porte en pointillés ;
- capture d'écran de téléphone : barre d'état, bandes noires, filigrane, image agrandie floue ;
- « absurde » : fond, murs et textes de couleurs tirées au hasard, plan inversé (clair sur foncé).

Rien de tout cela ne change la vérité : un sol carrelé reste la pièce, une lettre reste du fond.
Tout est tiré avec un hasard à part : sans l'option, les anciens jeux restent identiques.
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw

from moteur.generateur.logements import contour_piece

SOLS = ("carrelage", "parquet", "hachures", "points", "damier")
MURS = ("plein", "trait", "double", "gris_clair", "hachure", "couleur")
FILIGRANES = ("monsite-annonces", "IMMO-PLUS", "agence du centre", "leplan.fr", "VISITE 3D", "PLAN NON CONTRACTUEL")


@dataclass
class Variete:
    """Les tirages d'un style du monde, enregistrés avec le style (style.json)."""

    sols: dict[str, str] = field(default_factory=dict)  # sorte de pièce → motif de sol ("" : aucun)
    couleur_sol: tuple[int, int, int] = (170, 170, 170)
    pas_sol: float = 0.3  # m entre deux traits du motif
    murs: str = "plein"
    epaisseur_trait_mur: float = 0.4  # trait/double : part de l'épaisseur du mur
    lettres: bool = False
    couleur_lettres: tuple[int, int, int] = (150, 60, 170)
    couleur_noms: tuple[int, int, int] | None = None
    majuscules: bool = False
    parentheses: bool = False
    symboles_neuf: bool = False
    arcs_pointilles: bool = False
    capture: bool = False
    filigrane: str = ""
    agrandi: float = 1.0  # > 1 : l'image a été agrandie (réduite puis remise à sa taille)
    absurde: bool = False
    inverse: bool = False


def _couleur(rng: random.Random, s: tuple[float, float] = (0.3, 1.0), v: tuple[float, float] = (0.2, 0.9)) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(rng.random(), rng.uniform(*s), rng.uniform(*v))
    return round(r * 255), round(g * 255), round(b * 255)


def variete_au_hasard(rng: random.Random) -> Variete:
    v = Variete()
    if rng.random() < 0.45:
        motifs = rng.sample(SOLS, rng.randint(1, 3))
        for sorte in ("sejour", "principale", "cuisine", "chambre", "sdb", "sde", "wc", "entree", "degagement", "bureau", "buanderie"):
            if rng.random() < 0.6:
                v.sols[sorte] = rng.choice(motifs)
        g = rng.randint(120, 215)
        v.couleur_sol = (g, g, g) if rng.random() < 0.7 else _couleur(rng, (0.1, 0.5), (0.6, 0.9))
        v.pas_sol = rng.uniform(0.12, 0.45)
    v.murs = rng.choices(MURS, weights=(3, 2, 2, 2, 1, 1))[0]
    v.epaisseur_trait_mur = rng.uniform(0.15, 0.5)
    v.lettres = rng.random() < 0.25
    v.couleur_lettres = rng.choice([(150, 60, 170), (40, 40, 40), (200, 40, 40), (40, 90, 200), _couleur(rng)])
    if rng.random() < 0.3:
        v.couleur_noms = rng.choice([(40, 150, 60), (150, 60, 170), (30, 60, 160), (0, 0, 120), _couleur(rng)])
    v.majuscules = rng.random() < 0.3
    v.parentheses = rng.random() < 0.3
    v.symboles_neuf = rng.random() < 0.25
    v.arcs_pointilles = rng.random() < 0.3
    v.capture = rng.random() < 0.15
    if v.capture or rng.random() < 0.1:
        v.filigrane = rng.choice(FILIGRANES)
    v.agrandi = rng.uniform(1.5, 3.0) if (v.capture or rng.random() < 0.1) else 1.0
    v.absurde = rng.random() < 0.2
    v.inverse = v.absurde and rng.random() < 0.3
    return v


def appliquer_couleurs(style, v: Variete, rng: random.Random) -> None:
    """Les couleurs de page d'un style du monde : gris très clair, couleurs absurdes, plan inversé."""
    if v.murs == "gris_clair":
        g = rng.randint(195, 238)
        style.murs = (g, g, g)
        style.murs_contour = False
    elif v.murs == "couleur":
        style.murs = _couleur(rng, (0.2, 0.9), (0.2, 0.8))
    if v.absurde:
        style.fond = _couleur(rng, (0.0, 0.35), (0.85, 1.0))
        style.murs = _couleur(rng, (0.2, 1.0), (0.0, 0.6)) if v.murs not in ("gris_clair",) else style.murs
        style.traits = _couleur(rng, (0.0, 1.0), (0.0, 0.5))
        style.textes = _couleur(rng, (0.0, 1.0), (0.0, 0.5))
        v.couleur_sol = _couleur(rng, (0.2, 1.0), (0.4, 0.9))
        if v.inverse:  # clair sur foncé (écran de logiciel, blueprint)
            style.fond = _couleur(rng, (0.3, 1.0), (0.1, 0.45))
            c = _couleur(rng, (0.0, 0.2), (0.85, 1.0))
            style.murs = style.traits = style.textes = c
            style.murs_contour = False
            style.pieces_colorees = False


# ---------------------------------------------------------------- dessin (appelé par rendu._Dessin)


def sol(d, piece, motif: str, v: Variete) -> None:
    """Le motif du sol, à l'intérieur de la pièce seulement (le mur le recouvre ensuite)."""
    pts = d.poly_px(contour_piece(piece))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 4:
        return
    pas = max(4, round(v.pas_sol * 1000 * d.rep.s))
    couche = Image.new("L", (w, h), 0)
    c = ImageDraw.Draw(couche)
    if motif == "carrelage":
        for k in range(0, w, pas):
            c.line([(k, 0), (k, h)], fill=255)
        for k in range(0, h, pas):
            c.line([(0, k), (w, k)], fill=255)
    elif motif == "damier":
        for i in range(0, w, pas):
            for j in range(0, h, pas):
                if (i // pas + j // pas) % 2 == 0:
                    c.rectangle([i, j, i + pas - 1, j + pas - 1], fill=110)
    elif motif == "parquet":
        lame = max(3, pas // 3)
        for j in range(0, h, lame):
            c.line([(0, j), (w, j)], fill=255)
            decal = (j // lame) * pas // 2
            for i in range(-pas + decal % pas, w, pas * 2):
                c.line([(i, j), (i, j + lame)], fill=255)
    elif motif == "hachures":
        for k in range(-h, w, max(3, pas // 2)):
            c.line([(k, 0), (k + h, h)], fill=255)
    else:  # points
        for i in range(pas // 2, w, pas):
            for j in range(pas // 2, h, pas):
                c.ellipse([i - 1, j - 1, i + 1, j + 1], fill=255)
    masque = Image.new("L", (w, h), 0)
    ImageDraw.Draw(masque).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
    couche = Image.fromarray(np.minimum(np.asarray(couche), np.asarray(masque)))
    d.image.paste(Image.new("RGB", (w, h), v.couleur_sol), (x0, y0), couche)


def mur(d, m, contour, v: Variete) -> None:
    """Un mur dessiné selon la variété (le masque, lui, est rempli par l'appelant comme d'habitude)."""
    st = d.style
    pts = d.poly_px(contour)
    if v.murs in ("plein", "gris_clair", "couleur"):
        d.d.polygon(pts, fill=st.murs)
        return
    ep_px = max(1, m.epaisseur * d.rep.s)
    if v.murs == "trait":
        if m.vertical:
            p, q = (m.axe, contour[0][1]), (m.axe, contour[2][1])
        else:
            p, q = (contour[0][0], m.axe), (contour[2][0], m.axe)
        d.ligne(p, q, st.murs, max(1, round(ep_px * v.epaisseur_trait_mur)))
    elif v.murs == "double":
        d.d.polygon(pts, outline=st.murs, width=max(1, round(min(3, ep_px * v.epaisseur_trait_mur))))
    else:  # hachure : contour + traits obliques
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        couche = Image.new("L", (w, h), 0)
        c = ImageDraw.Draw(couche)
        for k in range(-h, w, 5):
            c.line([(k, 0), (k + h, h)], fill=255)
        d.image.paste(Image.new("RGB", (w, h), st.murs), (x0, y0), couche)
        d.d.polygon(pts, outline=st.murs, width=1)


def lettres(d, v: Variete) -> None:
    """Les lettres A, B, C, D… au milieu de chaque côté, côté intérieur de la pièce (croquis Carrez)."""
    taille = max(9, round(d.style.taille_texte * 0.8))
    recul = max(150, round(taille * 1.2 / max(d.rep.s, 1e-9)))  # mm depuis le mur
    for p in d.niv.pieces:
        r = p.rect
        if r.largeur < 3 * recul or r.hauteur < 3 * recul:
            continue
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        places = [(cx, r.y1 - recul), (r.x0 + recul, cy), (cx, r.y0 + recul), (r.x1 - recul, cy)]
        for lettre, (x, y) in zip("ABCD", places):
            d.texte(d.px(x, y), lettre, taille, v.couleur_lettres)


def symboles_neuf(d, v: Variete, rng: random.Random) -> None:
    """Les petites étiquettes des plans du neuf, posées dans un coin des pièces, et le cercle PMR."""
    taille = max(8, round(d.style.taille_texte * 0.6))
    couleur = d.style.traits
    for p in d.niv.pieces:
        r = p.rect
        etiquette = {"sdb": "Gaine", "sde": "Gaine", "cuisine": "Gaine", "entree": "TGBT", "placard": "PL",
                     "degagement": "BECS", "buanderie": "BECS"}.get(p.sorte)
        if etiquette and r.largeur > 900 and r.hauteur > 900 and rng.random() < 0.8:
            x, y = d.px(r.x0 + 350, r.y1 - 300)
            l = _texte_largeur(d, etiquette, taille) + 6
            d.d.rectangle([x - l / 2, y - taille * 0.8, x + l / 2, y + taille * 0.8], outline=couleur, width=1)
            d.texte((x, y), etiquette, taille, couleur)
        if p.sorte in ("sdb", "sde", "chambre") and min(r.largeur, r.hauteur) > 1700 and rng.random() < 0.5:
            cx, cy = d.px((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            rr = 750 * d.rep.s
            for a in range(0, 360, 16):
                d.d.arc([cx - rr, cy - rr, cx + rr, cy + rr], a, a + 8, fill=couleur, width=1)


def _texte_largeur(d, texte: str, taille: int) -> float:
    from moteur.dessin_plan import _police
    return _police(d.style.police, taille).getlength(texte)


def arc_pointille(d, boite, debut: float, fin: float, couleur, largeur: int) -> None:
    if fin < debut:
        fin += 360
    a = debut
    while a < fin:
        d.d.arc(boite, a, min(a + 6, fin), fill=couleur, width=largeur)
        a += 12


def capture(image: np.ndarray, semantique: np.ndarray, v: Variete, rng: random.Random) -> np.ndarray:
    """La capture d'écran (pixels seulement) : barre d'état et bandes noires dans les marges, filigrane,
    image agrandie. Ne recouvre jamais le logement (barre et bandes restent dans les marges)."""
    img = image.copy()
    h, w = img.shape[:2]
    ys, xs = np.nonzero(semantique)
    haut, gauche, droite = (ys.min(), xs.min(), xs.max()) if len(ys) else (h // 10, w // 10, w - w // 10)
    if v.agrandi > 1.0:
        petit = cv2.resize(img, (max(8, round(w / v.agrandi)), max(8, round(h / v.agrandi))), interpolation=cv2.INTER_AREA)
        img = cv2.resize(petit, (w, h), interpolation=cv2.INTER_LINEAR)
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    if v.capture:
        barre = int(min(0.07 * h, haut - 8))
        if barre > 12:
            g = rng.randint(140, 245)
            d.rectangle([0, 0, w, barre], fill=(g, g, g + 5 if g < 250 else g))
            from moteur.dessin_plan import _police
            police = _police("DejaVuSans.ttf", max(8, int(barre * 0.55)))
            d.text((barre * 0.6, barre / 2), f"{rng.randint(7, 23)}:{rng.randint(0, 59):02d}", fill=(0, 0, 0), font=police, anchor="lm")
            d.text((w - barre * 0.6, barre / 2), f"{rng.randint(10, 99)}", fill=(0, 0, 0), font=police, anchor="rm")
        bande = int(min(0.06 * w, gauche - 8, w - droite - 8))
        if bande > 6 and rng.random() < 0.5:
            d.rectangle([0, 0, bande, h], fill=(0, 0, 0))
            d.rectangle([w - bande, 0, w, h], fill=(0, 0, 0))
    if v.filigrane:
        from moteur.dessin_plan import _police
        taille = max(12, int(w / max(8, len(v.filigrane)) * rng.uniform(0.8, 1.4)))
        police = _police("DejaVuSans.ttf", taille)
        calque = Image.new("L", (w, h), 0)
        ImageDraw.Draw(calque).text((w / 2, h * rng.uniform(0.3, 0.7)), v.filigrane, fill=round(255 * rng.uniform(0.12, 0.35)),
                                    font=police, anchor="mm")
        teinte = (rng.randint(150, 230),) * 3 if rng.random() < 0.7 else (200, 60, 60)
        pil.paste(Image.new("RGB", (w, h), teinte), (0, 0), calque)
    return np.asarray(pil).copy()
