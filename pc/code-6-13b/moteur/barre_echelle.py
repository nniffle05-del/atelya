"""Lire la barre d'échelle dessinée sous un plan (version 0.1).

Beaucoup de plans d'agence n'ont aucune cote. Certains portent à la place une petite règle sous le
dessin : une barre en cases noires et blanches, marquée « 0 » à gauche et « 2 m » à droite. Mesurée en
pixels, elle donne l'échelle : une barre de 180 pixels marquée « 2 m », c'est 90 pixels par mètre.

On part des textes déjà lus sur le plan (RapidOCR, voir moteur.lecture_cotes) : chaque texte « N m »
est un bout de barre possible. Juste au-dessus, on cherche un trait horizontal (le cadre de la barre)
qui se termine au droit du texte, et on mesure sa longueur. La barre est jugée « sûre » quand un
second indice la confirme : le « 0 » sous son bout gauche, ou des cases régulières d'un mètre (ou d'un
demi-mètre). Une barre non sûre n'est pas utilisée seule (voir moteur.echelle_plan.decider).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

import cv2
import numpy as np

from moteur.lecture_cotes import TexteLu, _traits, lire_textes

FORME_BARRE = re.compile(r"^([0-9lI]{1,2})\s*m\.?$", re.IGNORECASE)
FORME_ZERO = re.compile(r"^[0oO]$")
TROU_BARRE = 6  # trou toléré (pixels) dans le cadre d'une barre abîmée (grain, compression)
CASES_ACCORD = 0.06  # les cases d'une barre font la même longueur à 6 % près
MONTEE_MAX = 4  # on cherche la barre jusqu'à 4 hauteurs de texte au-dessus du « N m »
BOUT_FIN = 6  # pixels de part et d'autre d'un bout de la barre où l'on compte l'encre (voir _longueur_fine)
PENTE_BARRE = 3  # pixels de pente tolérés d'un bout à l'autre d'une barre (plan un peu de travers)


@dataclass
class BarreLue:
    px_par_m: float
    metres: int
    sure: bool
    debut: float  # bout gauche de la barre (pixels)
    fin: float  # bout droit
    y: float  # hauteur de la barre (pixels)
    y_bas: int  # son trait du bas
    detail: str


def lire_barre(gris: np.ndarray, textes: list[TexteLu]) -> BarreLue | None:
    """La barre d'échelle du plan (image en gris, remise droite), ou None s'il n'y en a pas."""
    # Sur un plan granuleux, le cadre fin de la barre est criblé de trous : on les bouche le long des rangées.
    noir = cv2.morphologyEx(_traits(gris), cv2.MORPH_CLOSE, np.ones((1, TROU_BARRE + 1), np.uint8))
    meilleure = None
    for t in textes:
        trouve = FORME_BARRE.match(t.texte.strip())
        if not trouve:
            continue
        metres = int(re.sub("[lI]", "1", trouve.group(1)))
        if not 1 <= metres <= 50:
            continue
        barre = _barre_au_dessus(gris, noir, t, metres, textes)
        if barre is not None and (meilleure is None or (barre.sure, barre.fin - barre.debut) > (meilleure.sure, meilleure.fin - meilleure.debut)):
            meilleure = barre
    if meilleure is not None and not meilleure.sure:
        meilleure = _chercher_le_zero(gris, meilleure)
    return meilleure


def _chercher_le_zero(gris: np.ndarray, barre: BarreLue) -> BarreLue:
    """Un « 0 » tout seul échappe souvent à la première lecture : on relit, agrandi, le petit coin
    sous le bout gauche de la barre."""
    cote = max(48, int(0.6 * (barre.fin - barre.debut) / barre.metres))
    x0, x1 = max(0, int(barre.debut - cote / 2)), min(gris.shape[1], int(barre.debut + cote / 2))
    y0, y1 = barre.y_bas + 2, min(gris.shape[0], barre.y_bas + 2 + cote)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return barre
    morceau = np.pad(gris[y0:y1, x0:x1], 16, constant_values=255)
    if any(FORME_ZERO.match(t.texte.strip()) for t in lire_textes(morceau, 3)):
        return replace(barre, sure=True, detail=barre.detail + ", « 0 » lu sous le bout gauche")
    return barre


def _barre_au_dessus(gris: np.ndarray, noir: np.ndarray, t: TexteLu, metres: int, textes: list[TexteLu]) -> BarreLue | None:
    x0, y0 = t.boite.min(axis=0)
    x1, y1 = t.boite.max(axis=0)
    h = max(4.0, y1 - y0)
    # Le nombre est écrit sous le bout droit de la barre : centré dessus ou commençant à son aplomb.
    bout_min, bout_max = x0 - 1.5 * h, x1 + 0.5 * h
    rangees = []  # les rangées traversées par un long trait qui finit au droit du texte
    for y in range(int(y0) - 1, max(-1, int(y0 - MONTEE_MAX * h)), -1):
        trait = _trait_qui_finit_entre(noir[y], bout_min, bout_max, int(3 * h))
        if trait is not None:
            rangees.append((y, *trait))
    if not rangees:
        return None
    # La barre : les rangées à moins de deux hauteurs de texte au-dessus de la plus proche du texte. Le
    # cadre la traverse d'un bout à l'autre (ses traits du haut et du bas) : on garde les plus longues.
    # (Sur un plan flou, une rangée du bord ne couvre parfois qu'une partie de la barre.)
    barre = [r for r in rangees if rangees[0][0] - r[0] <= 2 * h]
    longueur = max(r[2] - r[1] for r in barre)
    pleines = [r for r in barre if r[2] - r[1] >= longueur - 3]
    debut = float(np.median([r[1] for r in pleines]))
    fin = float(np.median([r[2] for r in pleines]))
    y_bas, y_haut = max(r[0] for r in pleines), min(r[0] for r in pleines)
    # Un plan scanné un peu de travers, que le coloriage n'a pas permis de remettre tout à fait droit :
    # la barre penche, et une seule rangée n'en couvre qu'une partie (2 m lus 1,6 m). On la suit donc
    # sur toute la bande de ses rangées, à quelques pixels près en hauteur.
    y0b, y1b = max(0, y_haut - PENTE_BARRE), min(noir.shape[0], y_bas + PENTE_BARRE + 1)
    bande = noir[y0b:y1b].any(axis=0)
    a, b = _trait_autour(bande, int(debut), int(fin))
    if b > fin and b <= bout_max:
        debut, fin = float(min(a, debut)), float(b)
        lignes = np.flatnonzero(noir[y0b:y1b, max(0, b - 6):b + 1].any(axis=1))
        y_haut, y_bas = y0b + int(lignes.min()), y0b + int(lignes.max())
    if y_bas - y_haut >= 2:  # un cadre : son bord droit doit relier le haut et le bas
        bord = noir[y_haut:y_bas + 1, max(0, int(fin) - 1):int(fin) + 2].any(axis=1)
        if bord.mean() < 0.8:
            return None
    px_par_m = _longueur_fine(gris, int(debut), int(fin), y_haut, y_bas) / metres
    zero = any(FORME_ZERO.match(z.texte.strip()) and abs(z.boite[:, 0].mean() - debut) <= 1.5 * h
               and abs(z.boite[:, 1].mean() - t.boite[:, 1].mean()) <= h for z in textes)
    cases = any(_cases_regulieres(noir[y], debut, fin, px_par_m) for y in range(y_haut + 1, y_bas))
    preuves = [p for p, ok in (("« 0 » lu sous le bout gauche", zero), ("cases régulières", cases)) if ok]
    return BarreLue(round(px_par_m, 3), metres, bool(preuves), debut, fin, (y_haut + y_bas) / 2, y_bas,
                    f"barre de {metres} m ({round(fin - debut)} pixels)" + (", " + ", ".join(preuves) if preuves else ""))


def _longueur_fine(gris: np.ndarray, debut: int, fin: int, y_haut: int, y_bas: int) -> float:
    """La longueur de la barre au dixième de pixel près, du milieu de son trait gauche au milieu du droit.

    Un dessin flou (tourné pour être remis droit, granuleux, compressé) étale chaque bout de la barre
    sur un pixel de plus, à moitié foncé : compté en pixels « foncés », la barre gagnait souvent un pixel
    (+0,5 % sur une barre de 200 pixels). On repère donc chaque bout là où le gris passe à mi-chemin
    entre le papier et l'encre, ou, si la barre finit par un simple trait (dernière case vide), au
    centre de ce trait. Le bout gauche est toujours une case pleine (la première case est noire)."""
    x0, x1 = max(0, debut - 2 * BOUT_FIN), min(gris.shape[1], fin + 2 * BOUT_FIN + 1)
    y0, y1 = max(0, y_haut - BOUT_FIN), min(gris.shape[0], y_bas + BOUT_FIN + 1)
    zone = gris[y0:y1, x0:x1].astype(float)
    papier = float(np.percentile(np.r_[zone[:, :BOUT_FIN].ravel(), zone[:, -BOUT_FIN:].ravel()], 75))
    interieur = zone[y_haut - y0 + 2:y_bas - y0 - 1, debut - x0 + 3:debut - x0 + BOUT_FIN + 3]
    if fin - debut < 4 * BOUT_FIN or interieur.size == 0:
        return float(fin - debut)
    encre = float(np.median(interieur))
    if papier - encre < 40:
        return float(fin - debut)
    noir = np.clip((papier - zone) / (papier - encre), 0, 1)

    def profil(x_ref: int, seuil: float = 0.5) -> np.ndarray | None:
        # La noirceur moyenne de chaque colonne, prise dans les rangées du milieu de la barre à cet endroit
        # (la barre peut pencher un peu : on repère ses rangées près de chaque bout).
        # On ne garde que les rangées foncées d'un seul tenant autour du milieu de la barre (pas un texte
        # ou un trait voisin au-dessus).
        foncee = noir[:, x_ref - x0] > seuil
        milieu = (y_haut + y_bas) // 2 - y0
        if not foncee[milieu]:
            return None
        haut = bas = milieu
        while haut > 0 and foncee[haut - 1]:
            haut -= 1
        while bas + 1 < len(foncee) and foncee[bas + 1]:
            bas += 1
        if bas - haut < 4:
            return None
        return noir[haut + 2:bas - 1].mean(axis=0)

    gauche = profil(debut + 3)
    if gauche is None:
        return float(fin - debut)
    xs = np.arange(debut - 3, debut + 4) - x0
    k = next((i for i in xs if gauche[i] >= 0.5), None)
    if k is None or gauche[k - 1] >= 0.5:
        return float(fin - debut)
    bord_g = k - 1 + (0.5 - gauche[k - 1]) / (gauche[k] - gauche[k - 1]) + 0.5 + x0  # milieu du 1er pixel d'encre

    pleine = profil(fin - 4)
    if pleine is not None and pleine[fin - 4 - x0] >= 0.5:  # dernière case pleine : son bord, comme à gauche
        xs = np.arange(fin + 3, fin - 4, -1) - x0
        k = next((i for i in xs if pleine[i] >= 0.5), None)
        if k is None or pleine[k + 1] >= 0.5:
            return float(fin - debut)
        bord_d = k + (pleine[k] - 0.5) / (pleine[k] - pleine[k + 1]) - 0.5 + x0
    else:  # dernière case vide : le centre du trait qui la ferme
        c = fin - x0 + int(np.argmax(noir[:, fin - x0 - 1:fin - x0 + 2].sum(axis=0))) - 1
        trait = profil(c + x0, 0.25)  # un trait fin flou n'est souvent qu'à moitié noir, sur deux colonnes
        if trait is None:
            return float(fin - debut)
        poids = trait[c - 3:c + 4].copy()
        poids[poids < 0.1] = 0
        if poids.sum() <= 0:
            return float(fin - debut)
        bord_d = float((np.arange(c - 3, c + 4) * poids).sum() / poids.sum()) + x0
    longueur = float(bord_d - bord_g)
    return longueur if abs(longueur - (fin - debut)) <= 3 else float(fin - debut)


def _trait_qui_finit_entre(ligne: np.ndarray, a: float, b: float, longueur_min: int) -> tuple[int, int] | None:
    """Le plus long trait foncé de la rangée dont le bout droit tombe entre a et b."""
    xs = np.flatnonzero(ligne)
    if not len(xs):
        return None
    coupures = np.flatnonzero(np.diff(xs) > 1)
    debuts = np.r_[xs[0], xs[coupures + 1]]
    fins = np.r_[xs[coupures], xs[-1]]
    ok = (fins >= a) & (fins <= b) & (fins - debuts >= longueur_min)
    if not ok.any():
        return None
    i = int(np.argmax(np.where(ok, fins - debuts, -1)))
    return int(debuts[i]), int(fins[i])


def _trait_autour(ligne: np.ndarray, a: int, b: int) -> tuple[int, int]:
    """Le trait foncé de la rangée qui contient [a, b], prolongé tant qu'il ne s'interrompt pas."""
    while a > 0 and ligne[a - 1]:
        a -= 1
    while b + 1 < len(ligne) and ligne[b + 1]:
        b += 1
    return a, b


def _cases_regulieres(rangee: np.ndarray, debut: float, fin: float, px_par_m: float) -> bool:
    """Le milieu de la barre alterne des cases pleines et vides, toutes d'un mètre (ou d'un demi-mètre)."""
    morceau = rangee[int(round(debut)):int(round(fin)) + 1].astype(int)
    if len(morceau) < 8:
        return False
    bornes = np.r_[0, np.flatnonzero(np.diff(morceau)) + 1, len(morceau)]
    cases = [int(v) for v in np.diff(bornes) if v > 3]  # les bords d'une case vide ne sont pas des cases
    if len(cases) < 2 or sum(cases) < 0.85 * len(morceau):
        return False
    ref = float(np.median(cases))
    if not any(abs(ref - u) <= CASES_ACCORD * u for u in (px_par_m, px_par_m / 2)):
        return False
    return all(abs(c - ref) <= max(3.0, CASES_ACCORD * ref) for c in cases)
