"""Lecture automatique de l'échelle d'un plan, à partir de ses cotes (version 0.2).

Une cote, c'est un trait fin avec une petite marque à chaque bout et un
nombre écrit à côté (par exemple « 4,80 ») : la distance réelle, en mètres,
entre les deux marques. Si on mesure ce trait en pixels sur l'image, on
connaît l'échelle : 480 pixels pour 4,80 m, c'est 100 pixels par mètre.

Principe :
1. Lire tous les textes du plan avec RapidOCR (un modèle de lecture de texte
   déjà entraîné, qui tourne sur l'ordinateur, sans Internet).
2. Garder les textes qui ressemblent à une cote (« 4,80 », « 12.35 »).
3. Pour chacun, retrouver le trait de cote juste à côté du texte, puis les
   marques qui le bornent, et mesurer la distance entre ces marques.
4. Chaque cote donne une échelle. On écarte celles qui ne sont pas d'accord
   avec les autres (texte mal lu, trait mal trouvé) et on fait la moyenne.

On lit aussi la hauteur sous plafond quand elle est écrite sur le plan
(« Hauteur sous plafond : 2,50 m » ou « HSP 2,50 »).

Limites de la version 0.1 : cotes en mètres avec deux décimales ; cotes
horizontales ou verticales ; il faut au moins deux cotes concordantes pour
que l'échelle soit jugée sûre.

Version 0.2 (07/11/2026) : les cotes écrites DANS les pièces, de mur à mur (plans de promoteur, fr-090, fr-108, fr-110). Leur trait
n'a pas de marque nette : il bute sur un mur, et il croise d'autres traits. Quatre défauts, tous sans alerte, trouvés par le lot 2 du
générateur (24 échelles fausses sur 150 tirages en cm, 25 sur 439 plans) :
- un trait qui croise le trait de cote (autre cote, meuble, porte) était pris pour sa marque de fin (_croisements) ;
- un mur était mesuré en son milieu, et non à sa face (_centres_des_groupes), ou écarté comme une traînée, si bien que la cote
  allait jusqu'au trait suivant, derrière le mur (_colonnes_d_un_mur_au_bout) ;
- un trait gris s'efface à l'approche d'un mur noir, et semblait s'arrêter avant lui (_mur_au_bout) ;
- les nombres d'un tableau de surfaces à bordures ressemblaient à des cotes (_nombres_d_un_tableau) ; deux petits entiers de même
  longueur faisaient une échelle (_cotes_en_cm_admises).
Tout ce qui est propre à ces plans ne joue que si le trait continue au-delà sans porter de nombre : les chaînes autour du plan ne
bougent pas (sur 224 plans anciens : 6 échelles changées, toutes de moins de 0,1 %).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

ECART_MAX = 0.03  # une cote qui s'écarte de plus de 3 % des autres est écartée
ACCORD = 0.01  # deux cotes « concordantes » donnent la même échelle à 1 % près
MARQUE_MIN = 8  # une marque de bout de cote fait au moins 8 pixels de haut
# Les lectures essayées tant que l'échelle n'est pas sûre : (enlever le grain, agrandir).
ESSAIS_LECTURE = ((False, 1), (True, 1), (True, 2))
ECRASEMENT_MIN = 0.004  # en dessous de 0,4 % d'écart entre largeur et hauteur, on ne touche à rien
ECRASEMENT_MAX = 0.10  # au-delà de 10 %, ce n'est pas un écrasement mais des cotes mal lues
TRAINEE_MIN = 0.4  # une marque foncée à plus de 40 %, loin des deux côtés du trait de cote, est une traînée
TRAINEE_PORTEE = 150  # en pixels : jusqu'où on regarde de chaque côté
COTE_MIN = 0.30  # une « cote » plus petite (« 0,00 » lu dans une tache) n'en est pas une
TROU_MAX = 4  # trou toléré (en pixels) dans un trait de cote abîmé (photocopie, compression)
EPAISSEUR_TRAIT = 0.6  # un trait de cote est plus fin que 60 % de la hauteur du chiffre : au-delà, c'est un mur
EPAISSEUR_TRAIT_MIN = 4  # en pixels : les chiffres minuscules ne doivent pas faire refuser un vrai trait
TABLEAU_LIGNES, TABLEAU_PAS = 3, 2.5  # au moins 3 nombres empilés, à moins de 2,5 hauteurs l'un de l'autre : un tableau (voir _nombres_d_un_tableau)
TRAIT_EN_LIGNE_PLEIN = 0.8  # chiffre au milieu du trait : le trait doit être plein à 80 % de part et d'autre
# Un trait qui CROISE un trait de cote n'est pas la marque de fin de cette cote (version 0.2, voir _croisements).
CROISEMENT_MIN = 11  # en pixels : il dépasse d'au moins ça de chaque côté (la marque la plus haute du générateur dépasse de 9)
CROISEMENT_HAUTEUR = 1.0  # … et d'au moins la hauteur du chiffre : une marque reste plus courte que le chiffre qu'elle borne
CROISEMENT_LARGEUR = 4  # en pixels, ou 40 % de la hauteur du chiffre : au-delà, c'est un mur, pas un trait
HALO_MUR = 14  # en pixels : _traits efface un trait gris sur cette distance autour d'un mur noir (fenêtre de 25 pixels, voir _mur_au_bout)
BOUT_MAX = 10  # en pixels : un mur à moins de ça du bout du trait de cote en est la fin (voir _colonnes_d_un_mur_au_bout)
TRAIT_MINCE_PLEIN = 0.55  # part de la rangée qui doit être foncée pour que ce soit un trait, et non des hachures (voir _trait_mince)
QUEUE_FINE = 12  # en pixels : la longueur de prolongement regardée juste après le croisement (voir _trait_mince)
QUEUE_MIN = 6  # en pixels : le trait de cote continue au moins de ça au-delà du croisement (sinon il s'arrête là : c'est sa fin)

FORME_COTE = re.compile(r"^\d{1,2}[,.]\d{2}$")
FORME_COTE_CM = re.compile(r"^[1-9]\d{1,2}$")  # « 405 » : cote en centimètres (plans de géomètre, fr-010) ; 3 chiffres = 9,99 m au plus
SOMBRE = 128  # niveau de gris : en dessous, un trait est franc (noir) ; les hachures de sol d'un PDF sont gris clair
MARQUE_MIN_FORT = 4  # sur les traits francs, une marque de bout de cote peut n'avoir que 4 pixels (PDF à 300 dpi)
CONTRADICTION = 0.15  # une cote écartée à plus de 15 % de l'échelle gardée la contredit vraiment (voir Echelle.contredite)
HACHURE_MIN = 40  # pixels : une marque gris clair qui continue si loin d'un côté est une hachure de sol, pas une marque
LIGNE_FRANCHE = 0.5  # part du trait de cote qui doit être noire pour qu'on lui applique les règles des traits francs (un trait fin de PDF, adouci par le rendu, l'est à moitié)
# « Murs extérieurs : 20 cm », « Cloisons : 7 cm » (le modèle de lecture abîme souvent les mots, pas les nombres).
FORME_EPAISSEUR = re.compile(r"^\s*(murs?|cl\w*)\b\D*?(\d{1,2})\s*cm\b", re.IGNORECASE)
FORME_HSP = re.compile(r"(?:hauteur\s+sous\s+plafond|h\.?\s*s\.?\s*p\.?)\D*(\d+[,.]\d+)", re.IGNORECASE)


@dataclass
class TexteLu:
    texte: str
    boite: np.ndarray  # 4 coins (x, y) en pixels
    confiance: float


@dataclass
class CoteLue:
    valeur: float  # en mètres, telle qu'écrite sur le plan
    longueur_px: float  # distance mesurée entre les deux marques
    verticale: bool
    texte: TexteLu
    bouts: tuple[tuple[float, float], tuple[float, float]]  # les deux marques, en pixels (x, y)

    @property
    def px_par_m(self) -> float:
        return self.longueur_px / self.valeur


@dataclass
class Echelle:
    px_par_m: float | None
    sure: bool  # au moins deux cotes concordantes
    retenues: list[CoteLue] = field(default_factory=list)
    ecartees: list[CoteLue] = field(default_factory=list)
    hauteur_sous_plafond: float | None = None

    @property
    def contredite(self) -> bool:
        """Plus de cotes franchement en désaccord que de cotes gardées : l'accord des cotes gardées peut être un hasard
        (fr-006 : deux cotes mesurées sur le même mur). Une cote à moins de CONTRADICTION de l'échelle gardée n'est pas
        une contradiction, c'est une cote imprécise (dessin à la main, fr-010 : 11 cotes entre −23 % et +22 %)."""
        if not self.px_par_m:
            return False
        loin = [c for c in self.ecartees if abs(c.px_par_m / self.px_par_m - 1) > CONTRADICTION]
        return len(loin) > len(self.retenues)


def lire_textes(gris: np.ndarray, agrandir: int = 1) -> list[TexteLu]:
    """Tous les textes du plan, avec leur position (lus sur l'image agrandie si demandé)."""
    if agrandir > 1:
        gris = cv2.resize(gris, None, fx=agrandir, fy=agrandir, interpolation=cv2.INTER_CUBIC)
    resultat = _moteur_ocr()(cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR))
    if resultat.txts is None:
        return []
    return [
        TexteLu(t.strip(), np.asarray(b, dtype=float) / agrandir, float(s))
        for b, t, s in zip(resultat.boxes, resultat.txts, resultat.scores)
    ]


def lire_textes_et_echelle(gris: np.ndarray) -> tuple[list[TexteLu], Echelle]:
    """Les textes et l'échelle d'un plan, en insistant si les cotes sont mal lues.

    Sur une photocopie granuleuse ou une image floue, le modèle de lecture rate
    des cotes. On recommence alors sur l'image débarrassée de son grain, puis
    agrandie deux fois, et on garde la lecture qui donne l'échelle la plus sûre.
    """
    meilleure = None
    for debruiter, agrandir in ESSAIS_LECTURE:
        image = cv2.fastNlMeansDenoising(gris, None, 10, 7, 21) if debruiter else gris
        textes = lire_textes(image, agrandir)
        echelle = lire_echelle(gris, textes)
        score = (echelle.sure, echelle.px_par_m is not None, len(echelle.retenues))
        if meilleure is None or score > meilleure[0]:
            meilleure = (score, textes, echelle)
        if echelle.sure:
            break
    return meilleure[1], meilleure[2]


def egaliser_les_echelles(
    gris: np.ndarray, textes: list[TexteLu], echelle: Echelle, photo: bool = False
) -> tuple[np.ndarray, list[TexteLu], Echelle, float]:
    """Rend l'échelle égale en largeur et en hauteur, si les cotes disent qu'elle ne l'est pas.

    Une photo remise à plat peut rester un peu écrasée : 100 pixels par mètre en
    largeur mais 97 en hauteur. Les cotes horizontales donnent l'échelle en largeur,
    les verticales en hauteur ; si elles diffèrent, on étire l'image en hauteur.
    Il faut deux cotes dans chaque sens ; une seule suffit sur une photo (`photo`),
    où l'écrasement est attendu.
    Renvoie l'image, les textes et l'échelle corrigés, et l'étirement appliqué (1 : aucun).
    """
    cotes = echelle.retenues + echelle.ecartees
    horizontales = [c.px_par_m for c in cotes if not c.verticale]
    verticales = [c.px_par_m for c in cotes if c.verticale]
    minimum = 1 if photo else 2
    if len(horizontales) < minimum or len(verticales) < minimum:
        return gris, textes, echelle, 1.0
    etirement = float(np.median(horizontales) / np.median(verticales))
    if abs(etirement - 1) <= ECRASEMENT_MIN or abs(etirement - 1) > ECRASEMENT_MAX:
        return gris, textes, echelle, 1.0
    h, w = gris.shape
    etire = cv2.resize(gris, (w, round(h * etirement)), interpolation=cv2.INTER_CUBIC)
    for t in textes:
        t.boite = t.boite * np.array([1.0, etirement])
    return etire, textes, lire_echelle(etire, textes), etirement


def valeur_de_cote(texte: str) -> float | None:
    """La longueur en mètres qu'annonce un texte de cote : « 4,80 » → 4,8 ; « 405 » (centimètres) → 4,05 ; sinon None.

    Un nombre entier n'est une cote que si son trait et ses marques sont retrouvés sur le plan, puis s'il s'accorde
    avec les autres cotes : un numéro de lot ou une année n'ont ni l'un ni l'autre."""
    t = texte.strip()
    if FORME_COTE.match(t):
        return float(t.replace(",", "."))
    if FORME_COTE_CM.match(t):
        return int(t) / 100
    return None


def plan_en_cm(textes: list[TexteLu]) -> bool:
    """Un plan coté en centimètres entiers n'a aucune cote « d,dd » : sinon, un entier est un numéro, pas une cote."""
    return not any(FORME_COTE.match(t.texte.strip()) for t in textes)


def _cotes_en_cm_admises(cotes: list[CoteLue], en_cm: list[CoteLue]) -> list[CoteLue]:
    """Les cotes en centimètres entiers ne comptent que sur un plan sans cote « d,dd », et si deux au moins s'accordent :
    un numéro de pièce (« 60 ») près d'un trait quelconque donnait une échelle absurde (plan fabriqué 004826)."""
    if cotes or len(en_cm) < 2:
        return []
    for c in en_cm:
        # Au moins une cote d'un mètre et plus dans l'accord : deux fois « 58 » (la fin de « 3,58 » lu de travers sur un texte
        # vertical) sur deux traits de même longueur s'accordaient parfaitement (plan fabriqué 129210 : +222 %).
        if c.valeur >= 1 and sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= ECART_MAX for d in en_cm) >= 2:
            # Un entier à 2 chiffres qui ne s'accorde pas n'est pas une cote mal mesurée, mais un autre nombre (« 30 » d'un texte
            # vertical lu de travers) : il ne compte pas, ni pour une échelle à lui seul, ni comme contradiction (plan fr-090).
            return [d for d in en_cm if d.valeur >= 1 or abs(d.px_par_m - c.px_par_m) / c.px_par_m <= ECART_MAX]
    return []


def lire_echelle(gris: np.ndarray, textes: list[TexteLu] | None = None) -> Echelle:
    """L'échelle (pixels par mètre) d'un plan déjà redressé, lue sur ses cotes."""
    if textes is None:
        textes = lire_textes(gris)
    noir = _traits(gris)
    fort = _traits_forts(gris, noir)
    cotes, en_cm = [], []
    tableau = _nombres_d_un_tableau(textes)
    for t in textes:
        v = valeur_de_cote(t.texte)
        if v is None or v < COTE_MIN or any(t is u for u in tableau):
            continue
        c = _mesurer_cote(noir, t, fort, v, textes)
        if c:
            (en_cm if FORME_COTE_CM.match(t.texte.strip()) else cotes).append(c)
    cotes += _cotes_en_cm_admises(cotes, en_cm)
    hsp = lire_hauteur_sous_plafond(textes)
    if not cotes:
        return Echelle(None, False, hauteur_sous_plafond=hsp)

    mediane = float(np.median([c.px_par_m for c in cotes]))
    retenues = [c for c in cotes if abs(c.px_par_m - mediane) / mediane <= ECART_MAX]
    if not retenues:
        # Deux cotes (ou plus) en désaccord : la médiane tombe entre elles et n'en garde aucune.
        # On part alors de la cote qui a le plus de cotes d'accord avec elle (à égalité, la plus longue).
        def soutien(c: CoteLue) -> tuple[int, float]:
            return sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= ECART_MAX for d in cotes), c.longueur_px

        mediane = max(cotes, key=soutien).px_par_m
        retenues = [c for c in cotes if abs(c.px_par_m - mediane) / mediane <= ECART_MAX]
    # Tri par la même règle (et non « c not in retenues ») : comparer deux cotes
    # comparerait leurs boîtes de texte, des tableaux numpy, et ferait planter.
    ecartees = [c for c in cotes if abs(c.px_par_m - mediane) / mediane > ECART_MAX]
    # Moyenne pondérée par la longueur : une grande cote est plus précise qu'une petite.
    px_par_m = sum(c.longueur_px for c in retenues) / sum(c.valeur for c in retenues)
    # Sûre : deux cotes au moins d'accord entre elles à 1 % près. (Avant : d'accord avec la moyenne ; avec trois cotes à
    # 58,5, 58,5 et 56, la moyenne tombait entre les deux et aucune n'était « concordante ».)
    concordantes = max((sum(abs(d.px_par_m - c.px_par_m) / c.px_par_m <= ACCORD for d in retenues) for c in retenues), default=0)
    return Echelle(round(px_par_m, 3), concordantes >= 2, retenues, ecartees, hsp)


def _nombres_d_un_tableau(textes: list[TexteLu]) -> list[TexteLu]:
    """Les nombres empilés en colonne, ligne après ligne : un tableau de surfaces (loi Carrez), pas des cotes.

    Dans un tableau à bordures, « 3,36 » et « 3,06 » ont chacun un trait au-dessus et une bordure de chaque côté : ils ressemblaient
    à des cotes de même longueur, donc d'accord à 1 % si leurs valeurs sont proches (plan fabriqué 129137 : −39 %, jugé sûr). Des
    nombres écrits droit, au moins TABLEAU_LIGNES les uns sous les autres, à moins de TABLEAU_PAS hauteurs d'écart : une chaîne de
    cotes ne s'écrit jamais ainsi (ses nombres se suivent le long du trait)."""
    nombres = []
    for t in textes:
        if valeur_de_cote(t.texte) is None or not FORME_COTE.match(t.texte.strip()):
            continue
        (x0, y0), (x1, y1) = t.boite.min(axis=0), t.boite.max(axis=0)
        if x1 - x0 > y1 - y0:
            nombres.append((t, (x0 + x1) / 2, (y0 + y1) / 2, y1 - y0))
    resultat: list[TexteLu] = []
    for t, cx, cy, h in nombres:
        colonne = sorted((v for v in nombres if abs(v[1] - cx) <= 0.75 * h), key=lambda v: v[2])
        # La suite continue qui contient ce nombre : chaque ligne à moins de TABLEAU_PAS hauteurs de la suivante.
        i = next(k for k, v in enumerate(colonne) if v[0] is t)
        a = b = i
        while a > 0 and colonne[a][2] - colonne[a - 1][2] <= TABLEAU_PAS * h:
            a -= 1
        while b < len(colonne) - 1 and colonne[b + 1][2] - colonne[b][2] <= TABLEAU_PAS * h:
            b += 1
        if b - a + 1 >= TABLEAU_LIGNES:
            resultat.append(t)
    return resultat


def lire_hauteur_sous_plafond(textes: list[TexteLu]) -> float | None:
    for t in textes:
        trouve = FORME_HSP.search(t.texte)
        if trouve:
            valeur = float(trouve.group(1).replace(",", "."))
            if 1.8 <= valeur <= 6.0:  # au-delà, ce n'est sûrement pas une hauteur sous plafond
                return valeur
    return None


def lire_epaisseurs(textes: list[TexteLu]) -> list[float]:
    """Les épaisseurs de murs écrites sur le plan (cartouche), en mètres."""
    epaisseurs = []
    for t in textes:
        trouve = FORME_EPAISSEUR.match(t.texte)
        if trouve:
            valeur = int(trouve.group(2)) / 100
            if 0.04 <= valeur <= 0.50 and valeur not in epaisseurs:
                epaisseurs.append(valeur)
    return epaisseurs


# ---------- Mesure d'une cote ----------


@lru_cache(maxsize=1)
def _moteur_ocr():
    from rapidocr import RapidOCR  # chargé seulement si on lit des textes (le modèle met ~1 s)

    return RapidOCR(params={"Global.log_level": "error"})


def _traits(gris: np.ndarray) -> np.ndarray:
    """Masque des traits, même fins ou pâles : un pixel nettement plus foncé que son voisinage."""
    return cv2.adaptiveThreshold(gris, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 20)


def _traits_forts(gris: np.ndarray, noir: np.ndarray) -> np.ndarray:
    """Les traits francs seulement : noirs, pas gris clair. Les hachures de parquet d'un PDF (gris clair) traversent les
    cotes et passaient pour des marques de bout : la cote « 2,75 » de fr-019 mesurait l'écart entre deux lattes."""
    return noir & (gris < SOMBRE).astype(np.uint8)


def _mesurer_cote(noir: np.ndarray, texte: TexteLu, fort: np.ndarray | None = None,
                  valeur: float | None = None, textes: list[TexteLu] | None = None) -> CoteLue | None:
    """Retrouve le trait d'une cote à côté de son texte et mesure la distance entre ses marques.

    `fort` : les traits francs (voir _traits_forts). Il sert à deux choses dans _marques : admettre les petites marques
    noires d'un PDF (4 pixels), et écarter les hachures de sol gris clair qui traversent la cote.
    `textes` : tous les textes du plan ; un nombre posé sur le prolongement du trait dit que c'est une chaîne de cotes
    (voir _croisements)."""
    if valeur is None:
        valeur = float(texte.texte.replace(",", "."))
    x0, y0 = texte.boite.min(axis=0)
    x1, y1 = texte.boite.max(axis=0)
    verticale = (y1 - y0) > (x1 - x0)
    voisins = None
    if textes is not None:
        voisins = []
        for t in textes:
            if t is texte or valeur_de_cote(t.texte) is None:
                continue
            (a0, b0), (a1, b1) = t.boite.min(axis=0), t.boite.max(axis=0)
            if ((b1 - b0) > (a1 - a0)) == bool(verticale):  # écrit dans le même sens que ce trait
                voisins.append((b0, a0, b1, a1) if verticale else (a0, b0, a1, b1))
    if verticale:  # on retourne l'image : la cote verticale devient horizontale
        x0, y0, x1, y1 = y0, x0, y1, x1
        noir = noir.T
        fort = fort.T if fort is not None else None
    choix = _marques(noir, x0, y0, x1, y1, fort, voisins)
    if choix is None:
        return None
    gauche, droite, ligne, _, _ = choix
    bouts = ((gauche, ligne), (droite, ligne))
    if verticale:  # on remet les coordonnées à l'endroit
        bouts = ((ligne, gauche), (ligne, droite))
    return CoteLue(valeur, droite - gauche, verticale, texte, bouts)


def _marques(noir: np.ndarray, x0: float, y0: float, x1: float, y1: float, fort: np.ndarray | None = None,
             voisins: list[tuple[float, float, float, float]] | None = None) -> tuple[float, float, int, int, int] | None:
    """Les deux marques qui bornent la cote (colonnes), la ligne du trait de cote, et le début et la fin de ce trait."""
    h, w = noir.shape
    hauteur = y1 - y0
    cx = int(round((x0 + x1) / 2))
    if not 0 <= cx < w:
        return None

    # 1. Le trait de cote. D'abord un trait qui traverse le chiffre (« —— 5.00 —— ») ; sinon la ligne la plus
    #    proche du texte (au-dessus ou en dessous) qui porte un long trait passant sous le milieu du texte.
    #    Un trait épais est un mur : le prendre pour une cote fausserait l'échelle sans alerte.
    en_ligne = _trait_en_ligne(noir, x0, y0, x1, y1)
    if en_ligne:
        y, debut, fin = en_ligne
    else:
        lignes = []
        for d in range(1, int(2 * hauteur) + 1):
            lignes += [int(y0) - d, int(np.ceil(y1)) + d]
        for y in lignes:
            if not 0 <= y < h:
                continue
            debut, fin = _trait_autour(noir[y], cx)
            if fin - debut >= 1.2 * (x1 - x0) and _trait_fin(noir, y, debut, fin, hauteur):
                break
        else:
            return None
        # Un trait de cote resté un peu penché (scan, photo) passe d'une rangée à l'autre :
        # on prend, autour de la rangée trouvée, les trois rangées réunies qui donnent le plus long trait.
        # À longueur égale, la rangée la plus proche de celle trouvée.
        trouvee = y
        y, debut, fin = max(
            ((r, *_trait_autour(noir[max(0, r - 1):r + 2].max(axis=0), cx)) for r in range(max(0, y - 2), min(h, y + 3))),
            key=lambda t: (t[2] - t[1], -abs(t[0] - trouvee)),
        )

    # 2. Les marques : colonnes où un petit trait perpendiculaire traverse la ligne,
    #    en dehors des colonnes occupées par le texte.
    haut, bas = max(0, y - 12), min(h, y + 13)
    g, d = max(0, debut - 3), min(w, fin + 4)
    bande = noir[haut:bas, g:d]
    decalage = g
    plus_long = _plus_longue_suite(bande)
    # Sur un trait de cote franc (noir sur presque toute sa longueur : dessin net, PDF), une petite marque noire qui
    # TRAVERSE le trait compte dès 4 pixels, et une marque gris clair mais longue est une hachure de sol, pas une marque.
    # Sur un trait gris (scan, photo), rien de tout ça : un grain noir sur la ligne passerait pour une marque (009592).
    ligne_franche = fort is not None and fort[max(0, y - 1):y + 2, debut:fin + 1].max(axis=0).mean() >= LIGNE_FRANCHE
    franche = _hauteur_a_travers(fort[haut:bas, g:d], y - haut) if ligne_franche else np.zeros_like(plus_long)
    colonnes = np.arange(len(plus_long)) + decalage
    hors_texte = (colonnes < x0 - 2) | (colonnes > x1 + 2)
    if voisins is not None:
        hors_texte &= ~_croisements(noir, y, debut, fin, cx, colonnes, np.maximum(plus_long, franche), hauteur, voisins)
    if not hors_texte.any():
        return (float(debut), float(fin), y, debut, fin) if en_ligne else None
    # Une marque floue déborde sur ses voisines : on ne garde que les colonnes
    # presque aussi hautes que la plus haute marque.
    seuil = max(MARQUE_MIN, 0.6 * plus_long[hors_texte].max())
    # Seules les colonnes presque aussi hautes que la plus haute : la base d'une flèche (courte) ne vaut pas la ligne
    # d'attache, et une marque oblique (photo 050136) ne doit donner qu'une marque, là où elle croise le trait.
    seuil_franc = max(MARQUE_MIN_FORT, 0.8 * franche[hors_texte].max())
    retenue = hors_texte & ((plus_long >= seuil) | (franche >= seuil_franc))
    poids = np.maximum(plus_long, franche)
    colonnes = colonnes[retenue]
    # Une traînée de photocopieuse traverse toute la feuille : ce n'est pas une marque. Une hachure gris clair non plus.
    # Sauf le mur où le trait vient buter (un groupe large au bout du trait) : lui aussi file loin des deux côtés, et sa face est
    # la vraie fin de la cote ; l'écarter faisait prendre la marque suivante, de l'autre côté du mur (plan fabriqué 80665 : +5 %).
    au_bout = _colonnes_d_un_mur_au_bout(noir, y, colonnes, debut, fin, cx, hauteur) if voisins is not None else set()
    colonnes = [c for c in colonnes if c in au_bout or (not _trainee(noir[:, c], y)
                and not (ligne_franche and franche[c - decalage] == 0 and _longue_d_un_cote(noir[:, c], y)))]
    marques = _centres_des_groupes(np.array(colonnes, dtype=int), poids, decalage, cx, max(CROISEMENT_LARGEUR, 0.4 * hauteur))
    gauche = [m for m in marques if m < cx]
    droite = [m for m in marques if m > cx]
    if voisins is not None:  # pas de marque de ce côté : le trait va peut-être jusqu'à un mur, dans le halo duquel il s'efface
        if not gauche and (mur := _mur_au_bout(noir, y, debut, -1, hauteur)) is not None:
            gauche = [mur]
        if not droite and (mur := _mur_au_bout(noir, y, fin, 1, hauteur)) is not None:
            droite = [mur]
    if en_ligne:  # les marques de ce style sont parfois minuscules : le trait s'arrête alors de lui-même à la bonne place
        return max(gauche) if gauche else float(debut), min(droite) if droite else float(fin), y, debut, fin
    if not gauche or not droite:
        return None
    return max(gauche), min(droite), y, debut, fin


def _colonnes_d_un_mur_au_bout(noir: np.ndarray, y: int, colonnes: np.ndarray, debut: int, fin: int, cx: int, hauteur: float) -> set[int]:
    """Les colonnes retenues où le trait de cote s'arrête contre un mur, même si elles filent loin des deux côtés comme une traînée :
    - un groupe large (mur plein, voir _centres_des_groupes) à moins de BOUT_MAX pixels d'un bout du trait, ou deux fois plus large
      ailleurs (une traînée de photocopieuse fait 4 pixels) ;
    - un trait fin au-delà duquel le trait de cote ne continue pas, ou ne continue que dans des hachures (la face d'un mur hachuré ;
      plan fabriqué 80920 : l'échelle prenait la face extérieure du mur, +5 %).
    Au milieu du trait, avec du trait de cote de l'autre côté, une colonne qui file loin reste une traînée de photocopieuse."""
    resultat: set[int] = set()
    if not len(colonnes):
        return resultat
    large = max(CROISEMENT_LARGEUR, 0.4 * hauteur)
    for groupe in np.split(colonnes, np.flatnonzero(np.diff(colonnes) > 1) + 1):
        c0, c1 = int(groupe[0]), int(groupe[-1])
        if c1 - c0 + 1 > large:
            # Très large, c'est un mur même au milieu du trait : le trait de la pièce voisine, sur la même rangée, le prolonge alors.
            if c0 - debut <= BOUT_MAX or fin - c1 <= BOUT_MAX or c1 - c0 + 1 > 2 * large:
                resultat.update(int(c) for c in groupe)
            continue
        if c1 < cx:
            queue = (max(debut, c0 - 2 - QUEUE_FINE), c0 - 2)
        elif c0 > cx:
            queue = (c1 + 2, min(fin, c1 + 2 + QUEUE_FINE))
        else:
            continue
        if queue[1] - queue[0] < QUEUE_MIN or not _trait_mince(noir, y, *queue):
            resultat.update(int(c) for c in groupe)
    return resultat


def _croisements(noir: np.ndarray, y: int, debut: int, fin: int, cx: int, colonnes: np.ndarray, hauteurs: np.ndarray,
                 hauteur: float, voisins: list[tuple[float, float, float, float]]) -> np.ndarray:
    """Les colonnes où un autre trait CROISE le trait de cote : ce n'est pas la marque de fin de cette cote.

    Sur les plans à cotes intérieures (un trait de mur à mur dans chaque pièce, fr-108, fr-110), le trait de la largeur et celui
    de la hauteur se croisent près d'un coin, et un meuble ou une porte coupent souvent le trait : le croisement, plus haut que la
    vraie marque, était pris pour elle. La cote mesurait alors la pièce moins 20 à 50 cm : toujours trop courte, et d'à peu près
    autant sur toutes les pièces, donc plusieurs cotes s'accordaient à tort et l'échelle fausse de −10 à −40 % était jugée sûre.
    Une colonne est un croisement si les trois sont vrais :
    - un trait fin (pas un mur) y dépasse nettement des DEUX côtés du trait de cote ; une marque est courte, une ligne d'attache ne
      dépasse franchement que d'un côté ;
    - le trait de cote continue au-delà ;
    - aucun nombre n'est posé sur ce prolongement : dans une chaîne de cotes, le trait continue aussi au-delà d'une marque, mais
      pour porter la cote suivante, avec son nombre.
    Dans le doute, la colonne reste une marque (comportement d'avant : les chaînes autour du plan ne bougent pas)."""
    resultat = np.zeros(len(colonnes), bool)
    long_min = max(CROISEMENT_MIN, CROISEMENT_HAUTEUR * hauteur)
    large_max = max(CROISEMENT_LARGEUR, 0.4 * hauteur)
    candidates = np.flatnonzero(hauteurs >= MARQUE_MIN_FORT)
    if not len(candidates):
        return resultat
    groupes = [(int(colonnes[g[0]]), int(colonnes[g[-1]]), g) for g in np.split(candidates, np.flatnonzero(np.diff(candidates) > 1) + 1)]
    murs = [(c0, c1) for c0, c1, _ in groupes if c1 - c0 + 1 > large_max]  # pleins : un mur arrête le trait de cote de ce côté
    for c0, c1, groupe in groupes:
        if c1 - c0 + 1 > large_max:
            continue  # un mur plein, pas un trait fin
        milieu = (c0 + c1) // 2
        # Le prolongement du trait, du côté opposé au chiffre mesuré, jusqu'au bout du trait ou au premier mur.
        if milieu < cx:
            a, b = max([debut] + [m1 for _, m1 in murs if m1 < milieu]), milieu
            contre = (max(a + 1, milieu - 2 - QUEUE_FINE), milieu - 2)
        else:
            a, b = milieu, min([fin] + [m0 for m0, _ in murs if m0 > milieu])
            contre = (milieu + 2, min(b - 1, milieu + 2 + QUEUE_FINE))
        if b - a < QUEUE_MIN:
            continue  # le trait de cote s'arrête ici
        colonne = noir[:, max(0, c0 - 1):c1 + 2].max(axis=1)  # un trait à peine penché passe d'une colonne à la voisine
        haut, bas = _depasse(colonne, y, -1, long_min), _depasse(colonne, y, 1, long_min)
        # D'un côté, il peut s'arrêter tout de suite contre un mur : un trait de mur à mur qui passe tout près de ce mur.
        if not ((haut and bas) or (haut and _bute_sur_un_mur(noir, y, c0, c1, 1, long_min)) or (bas and _bute_sur_un_mur(noir, y, c0, c1, -1, long_min))):
            continue
        # Juste après le croisement : c'est encore un trait fin ? Sinon, des hachures de mur prolongent la rangée, et la colonne
        # est la face de ce mur, où le trait de cote s'arrête.
        if not _trait_mince(noir, y, *contre):
            continue
        if not any(a <= (vx0 + vx1) / 2 <= b and abs((vy0 + vy1) / 2 - y) <= 2.5 * max(hauteur, vy1 - vy0)
                   for vx0, vy0, vx1, vy1 in voisins):
            resultat[groupe] = True
    return resultat


def _mur_au_bout(noir: np.ndarray, y: int, bout: int, sens: int, hauteur: float) -> float | None:
    """La face du mur où le trait de cote vient buter, s'il y en a un juste après le bout visible du trait.

    _traits compare chaque pixel à la moyenne de son voisinage : à côté d'un mur noir, cette moyenne est sombre et un trait gris fin
    n'en ressort plus. Sur une cote de mur à mur, le trait semble donc s'arrêter 5 à 10 pixels avant le mur, de chaque côté, et sa
    marque (minuscule) s'efface aussi : la cote mesurait ce qui reste, soit 3 à 5 % de trop peu (plan fabriqué 80880)."""
    h, w = noir.shape
    long_min = max(CROISEMENT_MIN, CROISEMENT_HAUTEUR * hauteur)
    for d in range(1, HALO_MUR + 1):
        r = bout + sens * d
        if not 0 <= r < w:
            return None
        if noir[y, r]:
            colonne = noir[:, max(0, r - 1):r + 2].max(axis=1)
            haut, bas = _depasse(colonne, y, -1, long_min), _depasse(colonne, y, 1, long_min)
            # Un mur épais peut s'arrêter juste à côté (une porte, un angle) : d'un côté suffit. Un trait fin doit filer des deux.
            epais = 0 <= r + sens * (CROISEMENT_LARGEUR - 1) < w and noir[y, min(r, r + sens * (CROISEMENT_LARGEUR - 1)):max(r, r + sens * (CROISEMENT_LARGEUR - 1)) + 1].all()
            return float(r) if (haut and bas) or (epais and (haut or bas)) else None
    return None


def _depasse(colonne: np.ndarray, y: int, sens: int, longueur: float) -> bool:
    """Un trait (colonne de noir) dépasse-t-il du trait de cote de `longueur` pixels dans ce sens ? Une marque, si haute soit-elle,
    n'atteint pas la moitié extérieure de cette distance. On compte les pixels foncés et non une suite sans trou : sur une
    photocopie, le grain coupe les traits gris tous les quelques pixels (plan fabriqué 80038)."""
    n = int(np.ceil(longueur))
    debut = y + 2 * sens  # le trait de cote lui-même et son flou ne comptent pas
    rangees = colonne[debut:debut + n] if sens > 0 else colonne[max(0, debut - n + 1):debut + 1][::-1]
    if len(rangees) < n:
        return False
    return bool(rangees.mean() >= 0.6 and rangees[n // 2:].mean() >= 0.5)


def _bute_sur_un_mur(noir: np.ndarray, y: int, c0: int, c1: int, sens: int, longueur: float) -> bool:
    """Le trait des colonnes c0-c1 va-t-il sans s'interrompre jusqu'à un mur, à moins de `longueur` pixels du trait de cote ?"""
    h, w = noir.shape
    r = y + 2 * sens
    for _ in range(int(np.ceil(longueur))):
        if not 0 <= r < h or not noir[r, max(0, c0 - 1):c1 + 2].any():
            return False
        if noir[r, max(0, c0 - CROISEMENT_MIN):min(w, c1 + CROISEMENT_MIN + 1)].all():
            return True  # une rangée foncée de part et d'autre du trait : le mur
        r += sens
    return False


def _trait_mince(noir: np.ndarray, y: int, a: int, b: int) -> bool:
    """La rangée y porte-t-elle un trait fin entre les colonnes a et b, avec du blanc de part et d'autre ? Faux dans un mur hachuré
    (les rangées voisines sont aussi foncées que la rangée y) : le trait de cote s'y serait prolongé à tort."""
    if b <= a:
        return False
    h = noir.shape[0]
    # La meilleure rangée seule : les traits obliques de hachures n'en couvrent qu'une partie (40 % au plus), un trait continu presque
    # tout, même coupé par le grain ; en réunissant trois rangées, des hachures passaient pour un trait (plan fabriqué 80920).
    ligne = max(noir[r, a:b].mean() for r in range(max(0, y - 1), min(h, y + 2)))
    autour = [noir[r, a:b].mean() for r in (y - 4, y + 4) if 0 <= r < h]
    return bool(ligne >= TRAIT_MINCE_PLEIN and (not autour or max(autour) <= 0.25))


def _trait_en_ligne(noir: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int] | None:
    """Le trait qui traverse le chiffre (rangée, début, fin), s'il y en a un : plein et fin de part et d'autre du texte."""
    h, w = noir.shape
    hauteur = y1 - y0
    cx = int(round((x0 + x1) / 2))
    g, d = max(0, int(x0 - hauteur)), min(w, int(np.ceil(x1 + hauteur)) + 1)  # le chiffre et le blanc qui l'entoure
    milieu = (y0 + y1) / 2
    for y in sorted(range(max(0, int(y0)), min(h, int(np.ceil(y1)) + 1)), key=lambda r: abs(r - milieu)):
        rangee = noir[y].copy()
        rangee[g:d] = 1
        debut, fin = _trait_autour(rangee, cx)
        if debut >= g - 2 or fin <= d + 1 or fin - debut < 1.2 * (x1 - x0):
            continue  # le trait doit continuer des deux côtés du chiffre
        if noir[y, debut:g].mean() < TRAIT_EN_LIGNE_PLEIN or noir[y, d:fin + 1].mean() < TRAIT_EN_LIGNE_PLEIN:
            continue
        if _trait_fin(noir, y, debut, fin, hauteur, sans=(g, d)):
            return y, debut, fin
    return None


def _trait_fin(noir: np.ndarray, y: int, debut: int, fin: int, hauteur: float, sans: tuple[int, int] | None = None) -> bool:
    """Le trait trouvé à la rangée y est-il assez fin pour être un trait de cote (et pas le bord d'un mur) ?"""
    colonnes = np.ones(fin + 1 - debut, bool)
    if sans:
        colonnes[max(0, sans[0] - debut):max(0, sans[1] - debut)] = False  # le chiffre lui-même ne compte pas
    if not colonnes.any():
        return True
    limite = max(EPAISSEUR_TRAIT_MIN, EPAISSEUR_TRAIT * hauteur)
    epaisseur = 1

    def plein(r: int) -> bool:
        return 0 <= r < noir.shape[0] and noir[r, debut:fin + 1][colonnes].mean() >= 0.5

    r = y - 1
    while plein(r) and epaisseur <= limite:
        epaisseur += 1
        r -= 1
    r = y + 1
    while plein(r) and epaisseur <= limite:
        epaisseur += 1
        r += 1
    return epaisseur <= limite


def _longue_d_un_cote(colonne: np.ndarray, y: int) -> bool:
    """La colonne reste foncée sur HACHURE_MIN pixels d'un côté du trait de cote au moins : une latte de parquet, une
    ligne de carrelage (gris clair), là où une marque de cote s'arrête à quelques pixels."""
    h = len(colonne)
    for sens in (-1, 1):
        r, n = y + 3 * sens, 0
        while 0 <= r < h and colonne[r] and n < HACHURE_MIN:
            n += 1
            r += sens
        if n >= HACHURE_MIN:
            return True
    return False


def _trainee(colonne: np.ndarray, y: int) -> bool:
    """La colonne reste foncée loin au-dessus ET loin en dessous du trait de cote (une marque, elle, est courte)."""
    dessus = colonne[max(0, y - TRAINEE_PORTEE):max(0, y - 15)]
    dessous = colonne[y + 16:y + TRAINEE_PORTEE + 1]
    return len(dessus) > 0 and len(dessous) > 0 and dessus.mean() > TRAINEE_MIN and dessous.mean() > TRAINEE_MIN


def _trait_autour(ligne: np.ndarray, cx: int) -> tuple[int, int]:
    """Début et fin du trait foncé qui passe par la colonne cx (petits trous tolérés)."""
    if not ligne[max(0, cx - TROU_MAX):cx + TROU_MAX + 1].any():
        return cx, cx
    debut = fin = cx
    trou = 0
    while debut > 0 and trou <= TROU_MAX:
        debut -= 1
        trou = 0 if ligne[debut] else trou + 1
    debut += trou
    trou = 0
    while fin < len(ligne) - 1 and trou <= TROU_MAX:
        fin += 1
        trou = 0 if ligne[fin] else trou + 1
    fin -= trou
    return debut, fin


def _hauteur_a_travers(bande: np.ndarray, rangee: int) -> np.ndarray:
    """Pour chaque colonne, la hauteur du trait foncé qui passe par la rangée donnée (0 si elle n'y est pas foncée)."""
    h = bande.shape[0]
    rangee = min(max(rangee, 0), h - 1)
    hauteur = bande[rangee].astype(int)
    for sens, limite in ((-1, -1), (1, h)):
        vivant = bande[rangee] > 0
        r = rangee + sens
        while r != limite and vivant.any():
            vivant = vivant & (bande[r] > 0)
            hauteur += vivant
            r += sens
    return hauteur


def _plus_longue_suite(bande: np.ndarray) -> np.ndarray:
    """Pour chaque colonne, la plus longue suite de pixels foncés consécutifs."""
    meilleur = np.zeros(bande.shape[1], dtype=int)
    courant = np.zeros(bande.shape[1], dtype=int)
    for rangee in bande:
        courant = np.where(rangee > 0, courant + 1, 0)
        meilleur = np.maximum(meilleur, courant)
    return meilleur


def _centres_des_groupes(colonnes: np.ndarray, poids: np.ndarray, decalage: int, cx: int | None = None,
                         large: float | None = None) -> list[float]:
    """Regroupe les colonnes voisines (une marque floue en couvre plusieurs) et donne leur centre.

    Un groupe plus large que `large` n'est pas une marque mais un mur où le trait de cote vient buter (cotes intérieures, de mur
    à mur) : la cote s'arrête à la face du mur, du côté du chiffre (colonne cx). Prendre le milieu du mur allongeait chaque cote
    d'une épaisseur de mur : l'échelle était trop grande de 3 à 5 %, d'autant plus sûrement que toutes les cotes l'étaient."""
    centres = []
    groupe: list[int] = []
    for c in list(colonnes) + [None]:
        if c is not None and groupe and c - groupe[-1] <= 1:
            groupe.append(c)
            continue
        if groupe:
            if large is not None and groupe[-1] - groupe[0] + 1 > large:
                centres.append(float(groupe[-1] if groupe[-1] < cx else groupe[0]))
            else:
                p = np.array([poids[g - decalage] for g in groupe], dtype=float)
                centres.append(float(np.dot(groupe, p) / p.sum()))
        groupe = [c] if c is not None else []
    return centres
