r"""Les DOUTES propres à la lecture de Claude : ce que Claude affirme, contrôlé contre le dessin (sous-étape 3 de l'étape
« écran branché sur la lecture de Claude », décision NT du 08/11/2026).

Pourquoi : Claude lit bien un plan mais peut se tromper sans le savoir, et le dire avec aplomb. Chaque contrôle ci-dessous
confronte une affirmation de Claude à quelque chose qu'il n'a pas produit lui-même (le trait du plan, les textes exacts d'un
PDF, la lecture de textes d'Atelya), et montre l'endroit à la personne qui vérifie au lieu de le laisser passer en silence.

1. Les textes recopiés existent-ils ? Claude pourrait inventer une cote ou une surface, que notre lecteur d'échelle croirait
   (une surface suffit à donner l'échelle, sans marque à retrouver sur le dessin). À l'endroit annoncé :
   - PDF vectoriel : un texte exact du PDF doit s'y trouver avec le même nombre, sinon doute fort ;
   - image : s'il n'y a presque pas d'encre, il n'y a pas de texte → doute fort ; sinon la lecture de textes d'Atelya (OCR) est
     faite sur ce petit cadre : si elle lit d'autres chiffres → doute FAIBLE (l'OCR se trompe souvent sur les vrais plans ; il
     ne doit pas accuser Claude à tort), si elle ne lit rien → rien (on ne sait pas).
2. Chaque cote contre le dessin : avec l'échelle LUE, ce que mesure la cote (ses marques retrouvées par Atelya si possible,
   sinon les deux bouts donnés par Claude) doit valoir le nombre écrit → sinon doute fort sur la cote (cote fausse, mal placée,
   ou cotes qui se contredisent).
3. Chaque surface écrite contre sa pièce : avec l'échelle LUE, la pièce construite doit faire la surface écrite → sinon doute fort
   (pièce mal fermée, cloison oubliée ou en trop, surface mal rattachée).
Sans échelle lue (« à vérifier »), les contrôles 2 et 3 ne sont pas faits : l'échelle est déjà le premier doute, et chaque cote
serait accusée à tort.

Seuils posés par principe (version 0.1.0), à recalibrer sur les vérités d'ENTRAÎNEMENT (jamais sur les 13 plans d'examen).
"""
from __future__ import annotations

import math
import re

import numpy as np

from moteur.lecture_claude import Cadre, LectureClaude, _surface_du_texte
from moteur.lecture_cotes import CoteLue, TexteLu, lire_textes, valeur_de_cote

VERSION_DOUTES_CLAUDE = "0.1.0"
MARGE_CADRE_PX = 4  # le cadre donné par Claude est approximatif : on regarde un peu autour
ENCRE_MIN = 0.01  # part de pixels d'encre en dessous de laquelle un cadre est vide (pas de texte)
ECART_COTE_MESUREE = 0.03  # cote dont les marques sont retrouvées par Atelya (mesure au pixel) : 3 %, comme echelle_plan
ECART_COTE_CLAUDE = 0.05  # cote mesurée sur les bouts donnés par Claude (approximatifs) : 5 %…
IMPRECISION_BOUTS_PX = 8.0  # … ou plus, si la cote est courte : 8 px d'erreur possible sur sa longueur
ECART_SURFACE = 0.10  # 10 % entre la surface écrite et la pièce construite (surfaces habitables, placards…)
ECART_SURFACE_M2 = 0.5  # et au moins 0,5 m² (petites pièces)


def _doute(code: str, raison: str, gravite: str, element: str | None, cadre: Cadre | None, f: float) -> dict:
    d = {"code": code, "raison": raison, "gravite": gravite, "element": element}
    if cadre is not None:
        x0, y0, x1, y1 = (v / f for v in cadre)
        d["zone_px"] = [round(min(x0, x1), 1), round(min(y0, y1), 1), round(abs(x1 - x0), 1), round(abs(y1 - y0), 1)]
    return d


def _chiffres(texte: str) -> str:
    """Les chiffres d'un texte, sans séparateurs : « 4,00 » → « 400 », « 12.5 m² » → « 125 » (2 de m² retiré)."""
    return re.sub(r"\D", "", texte.replace("m²", "").replace("m2", ""))


def _meme_nombre(a: str, b: str) -> bool:
    ca, cb = _chiffres(a), _chiffres(b)
    return bool(ca) and bool(cb) and (ca == cb or ca in cb or cb in ca)


def _cadre_plan(cadre: Cadre, f: float, forme: tuple[int, int]) -> tuple[int, int, int, int]:
    H, W = forme
    x0, y0, x1, y1 = (v / f for v in cadre)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    return (max(0, int(x0) - MARGE_CADRE_PX), max(0, int(y0) - MARGE_CADRE_PX),
            min(W, int(math.ceil(x1)) + MARGE_CADRE_PX), min(H, int(math.ceil(y1)) + MARGE_CADRE_PX))


def doutes_des_textes(fiche: LectureClaude, f: float, gris: np.ndarray, textes_pdf: list[TexteLu] | None,
                      ocr: bool = True) -> list[dict]:
    """Contrôle 1 : chaque texte recopié par Claude (cotes, surfaces, autres textes) existe-t-il à l'endroit annoncé ?"""
    doutes = []
    papier = float(np.percentile(gris, 90))
    for t in [*fiche.cotes, *fiche.surfaces, *fiche.textes]:
        x0, y0, x1, y1 = _cadre_plan(t.cadre, f, gris.shape)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        if textes_pdf is not None:
            dedans = [p.texte for p in textes_pdf
                      if x0 <= float(np.mean(p.boite[:, 0])) <= x1 and y0 <= float(np.mean(p.boite[:, 1])) <= y1]
            if not any(_meme_nombre(t.texte, p) for p in dedans):
                vu = f" (le PDF dit « {' '.join(dedans)[:30]} »)" if dedans else ""
                doutes.append(_doute("texte_introuvable", f"« {t.texte} » lu par Claude n'est pas écrit à cet endroit du PDF{vu}",
                                     "fort", None, t.cadre, f))
            continue
        morceau = gris[y0:y1, x0:x1]
        if float((morceau < papier - 60).mean()) < ENCRE_MIN:
            doutes.append(_doute("texte_introuvable", f"« {t.texte} » lu par Claude : aucun texte à cet endroit de l'image",
                                 "fort", None, t.cadre, f))
            continue
        if not ocr or not _chiffres(t.texte):
            continue
        lus = [x.texte for x in lire_textes(np.ascontiguousarray(morceau), agrandir=2) if _chiffres(x.texte)]
        if lus and not any(_meme_nombre(t.texte, x) for x in lus):
            doutes.append(_doute("texte_different", f"« {t.texte} » lu par Claude ; la lecture d'Atelya voit « {' '.join(lus)[:30]} »",
                                 "faible", None, t.cadre, f))
    return doutes


def _cote_mesuree(cadre: Cadre, f: float, valeur: float, cotes_atelya: list[CoteLue]) -> CoteLue | None:
    """La cote qu'Atelya a mesurée sur le dessin pour ce texte (même nombre, texte dans le cadre de Claude), s'il y en a une."""
    x0, y0, x1, y1 = (v / f for v in cadre)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    m = MARGE_CADRE_PX
    for c in cotes_atelya:
        cx, cy = float(np.mean(c.texte.boite[:, 0])), float(np.mean(c.texte.boite[:, 1]))
        if x0 - m <= cx <= x1 + m and y0 - m <= cy <= y1 + m and abs(c.valeur / valeur - 1) < 1e-6:
            return c
    return None


def doutes_des_cotes(fiche: LectureClaude, f: float, s_plan: float, cotes_atelya: list[CoteLue], ids: dict[str, str]) -> list[dict]:
    """Contrôle 2 (échelle lue seulement) : chaque cote vaut-elle, sur le dessin, le nombre écrit ?"""
    doutes = []
    for c in fiche.cotes:
        ecrite = valeur_de_cote(c.texte) or c.valeur_m  # le nombre ÉCRIT fait foi (sa recopie est contrôlée ailleurs)
        mesuree = _cote_mesuree(c.cadre, f, ecrite, cotes_atelya)
        if mesuree is not None:
            longueur_px, tolerance, comment = mesuree.longueur_px, ECART_COTE_MESUREE, "entre ses marques"
        else:
            longueur_px = math.dist(*c.bouts) / f
            if longueur_px <= 0:
                continue
            tolerance, comment = max(ECART_COTE_CLAUDE, IMPRECISION_BOUTS_PX / longueur_px), "entre les bouts lus par Claude"
        sur_le_dessin = longueur_px / s_plan
        if abs(sur_le_dessin / ecrite - 1) > tolerance:
            doutes.append(_doute("cote_contre_dessin", f"cote « {c.texte} » : le dessin mesure {sur_le_dessin:.2f} m {comment} "
                                 f"({100 * (sur_le_dessin / ecrite - 1):+.0f} %)", "fort", ids.get(c.mur) if c.mur else None,
                                 c.cadre, f))
    return doutes


def _aire(contour) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def _dans(x: float, y: float, contour) -> bool:
    dedans = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def doutes_des_surfaces(fiche: LectureClaude, f: float, logement: dict, ids: dict[str, str], vers_m) -> list[dict]:
    """Contrôle 3 (échelle lue seulement) : chaque pièce construite fait-elle la surface écrite ?

    La pièce : celle à laquelle Claude rattache la surface, sinon celle qui contient le texte. `vers_m(u, v)` : pixel de l'image
    du plan → mètres du logement."""
    pieces = {p["id"]: p for p in logement["pieces"]}
    doutes = []
    for s in fiche.surfaces:
        ecrite = _surface_du_texte(s.texte) or s.valeur_m2
        piece = pieces.get(ids.get(s.piece)) if s.piece else None
        if piece is None:
            cx, cy = vers_m((s.cadre[0] + s.cadre[2]) / 2 / f, (s.cadre[1] + s.cadre[3]) / 2 / f)
            piece = next((p for p in logement["pieces"] if _dans(cx, cy, p["contour"])), None)
        if piece is None:
            continue
        construite = _aire(piece["contour"])
        if abs(construite - ecrite) > max(ECART_SURFACE * ecrite, ECART_SURFACE_M2):
            doutes.append(_doute("surface_contre_piece", f"{piece['nom']} : {ecrite:g} m² écrits, la pièce construite fait "
                                 f"{construite:.1f} m² ({100 * (construite / ecrite - 1):+.0f} %)", "fort", piece["id"], s.cadre, f))
    return doutes
