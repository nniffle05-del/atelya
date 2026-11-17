"""Recaler un mur saisi à l'œil sur l'ENCRE du plan : l'axe et l'épaisseur glissent sur la bande sombre la plus proche.

Pourquoi : une position donnée à l'œil (vérités faites par Claude dans outils/verite/faire_verite.py, ou lecture de Claude par
l'API, moteur.traduire_claude) est approximative de quelques pixels ; le trait du plan, lui, est exact. Code déplacé tel quel
depuis outils/verite/faire_verite.py le 08/11/2026 (aucun changement de calcul : les vérités restent identiques).

15/11/2026 (examen app-004) : MURS GRIS CLAIR CERNÉS D'UN TRAIT (le style des plans d'annonce). Le recalage ne voyait que le
trait sombre du bord, pas le gris du mur : un plein posé contre un mur glissait de 4,5 px sur son trait de bord (décollé du mur
de 6 cm en 3D), une cloison de 6 px devenait épaisse de 3 px, une autre glissait de 2 px. À l'écran de vérification, NT a dû
reprendre les murs à la main (35 corrections). Corrigé par un SECOND REGARD, pris seulement pour un mur « gris cerné d'un
trait » (milieu de la bande nettement plus clair que ses bords ; sinon le premier regard, inchangé) : la bande entière (gris +
traits) devient le mur, ses bords mesurés au dixième de pixel ; un plein collé à une autre masse (la bande sort de la fenêtre de mesure d'un côté)
garde son épaisseur et pose sa face libre sur le trait. Les portes et fenêtres du mur (`exclure`) ne comptent plus dans la
mesure (une cloison à moitié occupée par sa porte était mesurée sur le dessin de la porte). Murs noirs pleins : rien ne change.
"""
from __future__ import annotations

import math

import numpy as np

SEUIL_GRIS = 0.25  # second regard : est « mur » ce qui est plus sombre que le papier d'au moins 25 % de l'écart papier → trait
CERNE = 0.75  # mur « gris cerné d'un trait » : le milieu de la bande est plus clair que 75 % de son trait le plus sombre
MARGE_OUVERTURE = 3.0  # px : on s'écarte d'autant des bords d'une porte ou d'une fenêtre (montants dessinés)
MESURES_MIN = 8  # points de mesure le long du mur, hors ouvertures : en dessous, on garde la saisie


def _positions(L: float, exclure) -> np.ndarray:
    """Où mesurer le long du mur (de 0 à 1) : on évite les bouts (angles, murs voisins) et les ouvertures données."""
    t = np.linspace(0.1, 0.9, max(2, int(L)))
    for a, b in exclure or ():
        a, b = min(a, b) - MARGE_OUVERTURE / L, max(a, b) + MARGE_OUVERTURE / L
        t = t[(t < a) | (t > b)]
    return t


def _profil(gris: np.ndarray, x0: float, y0: float, x1: float, y1: float, demi: int, exclure=None, net: bool = False) -> np.ndarray:
    """Noirceur médiane le long du mur, pour chaque décalage perpendiculaire de −demi à +demi pixels.

    `net` : pixel le plus proche pris sans l'arrondi « au pair » de numpy (un axe posé sur un demi-pixel lisait sinon deux fois
    la même rangée puis en sautait une : la bande mesurée était fausse d'un pixel)."""
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    t = _positions(L, exclure)
    xs = x0 + t * (x1 - x0)
    ys = y0 + t * (y1 - y0)
    arrondir = (lambda v: np.floor(v + 0.5)) if net else np.round
    prof = []
    for k in range(-demi, demi + 1):
        px = np.clip(arrondir(xs + k * nx).astype(int), 0, gris.shape[1] - 1)
        py = np.clip(arrondir(ys + k * ny).astype(int), 0, gris.shape[0] - 1)
        prof.append(float(np.median(255 - gris[py, px])))
    return np.array(prof)


def _bandes(sombre: np.ndarray) -> list[tuple[int, int]]:
    bandes, k = [], 0
    while k < len(sombre):
        if sombre[k]:
            j = k
            while j + 1 < len(sombre) and sombre[j + 1]:
                j += 1
            bandes.append((k, j))
            k = j + 1
        else:
            k += 1
    return bandes


def _la_plus_proche(bandes: list[tuple[int, int]], centre: int) -> tuple[int, int]:
    return min(bandes, key=lambda ab: 0 if ab[0] <= centre <= ab[1] else min(abs(ab[0] - centre), abs(ab[1] - centre)))


def _premier_regard(prof: np.ndarray, ep: float, marge: int, demi: int):
    """Le recalage d'origine (bande plus sombre que la moitié de l'écart papier → encre). Rend (décalage, épaisseur, bande) ou None."""
    papier = float(np.percentile(prof, 20))
    encre = papier + 0.5 * (prof.max() - papier)
    if prof.max() - papier < 40:  # pas d'encre nette : on garde la saisie
        return None
    bandes = _bandes(prof >= encre)
    if not bandes:
        return None
    a, b = _la_plus_proche(bandes, demi)
    if min(abs(a - demi), abs(b - demi)) > marge and not (a <= demi <= b):
        return None
    nouvelle_ep = b - a + 1
    if abs(nouvelle_ep - ep) > max(3, 0.35 * ep):  # bande trop différente (trait de fenêtre, hachures) : axe seul
        nouvelle_ep = ep
    return (a + b) / 2 - demi, float(nouvelle_ep), (a, b)


def _second_regard(prof: np.ndarray, ep: float, marge: int, demi: int, papier: float):
    """La bande ENTIÈRE du mur (gris de remplissage + traits de bord), bords au dixième de pixel.
    Rend (décalage, épaisseur, cerné : le mur est-il un gris cerné d'un trait ?) ou None."""
    maxi = float(prof.max())
    if maxi - papier < 40:
        return None
    bandes = _bandes(prof >= papier + SEUIL_GRIS * (maxi - papier))
    if not bandes:
        return None
    a, b = _la_plus_proche(bandes, demi)
    if min(abs(a - demi), abs(b - demi)) > marge and not (a <= demi <= b):
        return None
    # Bords fins : le pixel du bord n'est couvert qu'en partie par le trait (sa noirceur rapportée à celle du trait voisin).
    gauche = a + 1 - (min(1.0, (prof[a] - papier) / max(prof[min(a + 1, b)] - papier, 1e-6)) if b > a else 1.0)
    droite = b + (min(1.0, (prof[b] - papier) / max(prof[max(b - 1, a)] - papier, 1e-6)) if b > a else 1.0)
    dehors_a, dehors_b = a == 0, b == len(prof) - 1
    dedans = prof[a + 2:b - 1] if b - a >= 5 else prof[a + 1:b]
    cerne = len(dedans) > 0 and float(np.median(dedans)) - papier < CERNE * (float(prof[a:b + 1].max()) - papier)
    if dehors_a and dehors_b:  # tout est sombre : rien à quoi s'accrocher
        return None
    if dehors_a or dehors_b:  # collé à une autre masse (plein contre un mur) : épaisseur gardée, face libre posée sur le trait
        milieu = droite - ep / 2 if dehors_a else gauche + ep / 2
        decal = milieu - 0.5 - demi
        return (decal, float(ep), cerne) if abs(decal) <= marge else None
    nouvelle_ep = droite - gauche
    if abs(nouvelle_ep - ep) > max(3, 0.35 * ep):
        nouvelle_ep = ep
    return (gauche + droite) / 2 - 0.5 - demi, float(nouvelle_ep), cerne


def affiner_mur(gris: np.ndarray, mur: list[float], marge: int = 6, exclure=None, papier: float | None = None) -> list[float]:
    """Recale l'axe et l'épaisseur d'un mur sur la bande d'encre la plus proche (le trait du plan vaut mieux que mon œil).

    `exclure` : les ouvertures du mur, en parts de sa longueur [(début, fin), …] : elles ne sont pas mesurées.
    `papier` : la noirceur du papier de la page (0 = blanc pur) ; calculée sur la page si elle n'est pas donnée."""
    x0, y0, x1, y1, ep = mur
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0 or (exclure and len(_positions(L, exclure)) < MESURES_MIN):
        return mur
    demi = int(ep / 2 + marge)
    premier = _premier_regard(_profil(gris, x0, y0, x1, y1, demi, exclure), ep, marge, demi)
    if papier is None:
        papier = float(255 - np.percentile(gris[::4, ::4], 90))
    second = _second_regard(_profil(gris, x0, y0, x1, y1, demi, exclure, net=True), ep, marge, demi, papier)
    choisi = second if second is not None and second[2] else premier  # mur gris cerné d'un trait : le second regard
    if choisi is None:
        return mur
    decal, nouvelle_ep = choisi[0], choisi[1]
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if choisi is second and max(abs(nx), abs(ny)) > 0.999:
        # mur droit : la mesure a été prise sur les rangées de pixels les plus proches de l'axe saisi ; un axe saisi entre
        # deux rangées (« 138,5 ») était lu comme la rangée d'à côté : on rend ce demi-pixel
        decal += (math.floor(x0 + 0.5) - x0) * nx + (math.floor(y0 + 0.5) - y0) * ny
    return [x0 + decal * nx, y0 + decal * ny, x1 + decal * nx, y1 + decal * ny, float(nouvelle_ep)]
