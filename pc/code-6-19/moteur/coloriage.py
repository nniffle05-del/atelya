"""Du coloriage d'Atelya au logement.json : le maillon qui manquait avant la 3D.

Atelya ne rend pas des mesures mais une image « coloriée » : pour chaque pixel,
un numéro de classe (0 fond, 1 mur, 2 porte, 3 fenêtre, 4 porte-fenêtre,
5 à 15 types de pièces). Blender, lui, attend des murs avec un début, une fin
et une épaisseur en mètres. Ce module fait la traduction, sans rien apprendre :
uniquement des règles de géométrie (OpenCV et numpy).

Étapes, dans l'ordre :
1. redresser le coloriage (un plan scanné est souvent penché de quelques degrés ; un plan
   photographié de biais est d'abord remis à plat par moteur.redressement) ;
2. garder le bâti (murs + portes + fenêtres) relié au logement, jeter les
   taches isolées (flèche du Nord, barre d'échelle…) ;
3. trouver les murs droits horizontaux et verticaux, leur axe et leur épaisseur ;
4. poser chaque porte ou fenêtre sur le mur qui la porte ;
5. découper l'intérieur en pièces fermées et leur donner le type le plus colorié,
   ou celui du nom écrit dedans quand on l'a lu (moteur.noms_pieces) ;
6. passer des pixels aux mètres, origine au coin sud-ouest de l'intérieur.

Les hauteurs (sous plafond, portes, fenêtres) ne se lisent pas sur un plan vu
de dessus : elles prennent les valeurs habituelles et le statut « estime ».
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from moteur.logement import Logement
from moteur.redressement import Redressement

VERSION_COLORIAGE = "0.3.0"

FOND, MUR, PORTE, FENETRE, PORTE_FENETRE = 0, 1, 2, 3, 4
OUVERTURES = {PORTE: "porte", FENETRE: "fenetre", PORTE_FENETRE: "porte_fenetre"}
# Classes de pièces d'Atelya (5 à 15) → (type, nom affiché).
PIECES = {
    5: ("sejour", "Séjour"), 6: ("cuisine", "Cuisine"), 7: ("chambre", "Chambre"),
    8: ("salle_d_eau", "Salle d'eau"), 9: ("wc", "WC"), 10: ("entree", "Entrée"),
    11: ("degagement", "Dégagement"), 12: ("placard", "Placard"), 13: ("buanderie", "Buanderie"),
    14: ("bureau", "Bureau"), 15: ("escalier", "Escalier"),
}
PREMIERE_PIECE = min(PIECES)


def fusionner_coloriages(murs: np.ndarray, pieces: np.ndarray) -> np.ndarray:
    """Le « duo » d'Atelya : un coloriage pour le bâti, un autre pour le type des pièces.

    `murs` (Atelya essai 2) garde le fond, les murs et les ouvertures ; là où les deux
    coloriages voient une pièce, on prend le type lu par `pieces` (Atelya essai 3, plus
    sûr sur les WC, placards, buanderies). Sur les 983 plans de test : murs inchangés,
    bon type de pièce 93,8 → 95,5 %.
    """
    if murs.shape != pieces.shape:
        raise ValueError(f"coloriages de tailles différentes : {murs.shape} et {pieces.shape}")
    sortie = murs.copy()
    deux = (murs >= PREMIERE_PIECE) & (pieces >= PREMIERE_PIECE)
    sortie[deux] = pieces[deux]
    return sortie

# Hauteurs habituelles (m), faute de pouvoir les lire sur le plan.
HAUTEUR_SOUS_PLAFOND = 2.50
HAUTEUR_PORTE = 2.04
HAUTEUR_PORTE_FENETRE = 2.15
HAUT_FENETRE = 2.20  # haut des fenêtres, mesuré depuis le sol

# Réglages (en mètres, convertis en pixels selon l'échelle).
LONGUEUR_MIN_MUR = 0.30  # plus court : coin ou bout de mur, pas un mur à part
TOLERANCE_BORD = 0.025  # écart toléré sur un bord de mur, d'une colonne de pixels à l'autre
EPAISSEUR_MIN = 0.03  # m
SURFACE_MIN_PIECE = 0.25  # m²
LARGEUR_MIN_OUVERTURE = 0.25
ECART_FUSION_OUVERTURE = 0.10  # deux morceaux d'une même fenêtre séparés de moins : une seule
SURFACE_MIN_SEPARATION = 0.4  # m² : plus petite tache de couleur qui compte comme une pièce à part
PART_MIN_SEPARATION = 0.05  # … et au moins cette part de la zone


@dataclass
class Segment:
    """Un mur trouvé sur l'image redressée, en pixels (bords des pixels, pas leurs centres).
    Pour un mur horizontal : a..b le long de x, haut..bas en y. Pour un vertical : l'inverse."""

    horizontal: bool
    a: float
    b: float
    haut: float
    bas: float
    exterieur: bool = False

    @property
    def axe(self) -> float:
        return (self.haut + self.bas) / 2

    @property
    def epaisseur(self) -> float:
        return self.bas - self.haut


# ---------------------------------------------------------------- 1. redresser

def estimer_rotation(bati: np.ndarray, angle_max: float = 10.0) -> float:
    """Angle (degrés) dont le plan est penché. On essaie de tourner le bâti : à l'angle juste,
    les murs tombent pile sur des lignes et des colonnes de pixels, et les sommes par ligne
    et par colonne deviennent très « pointues » (on maximise leur somme des carrés)."""
    b = bati.astype(np.uint8)
    if b.sum() < 50:
        return 0.0
    r = min(1.0, 400 / max(b.shape))
    if r < 1:
        b = cv2.resize(b, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
    b = b.astype(np.float32)

    def nettete(angle: float) -> float:
        t = redresser(b, angle, lineaire=True)
        return float((t.sum(0) ** 2).sum() + (t.sum(1) ** 2).sum())

    angles = np.arange(-angle_max, angle_max + 1e-9, 0.25)
    meilleur = max(angles, key=nettete)
    fins = meilleur + np.arange(-12, 13) * 0.02
    return float(max(fins, key=nettete))


def _rotation(forme: tuple[int, int], angle: float) -> tuple[np.ndarray, int, int]:
    """Matrice (2 × 3) qui tourne une image de cette forme, et la taille de l'image tournée."""
    h, w = forme[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    c, s = abs(m[0, 0]), abs(m[0, 1])
    W, H = int(math.ceil(h * s + w * c)), int(math.ceil(h * c + w * s))
    m[0, 2] += W / 2 - w / 2
    m[1, 2] += H / 2 - h / 2
    return m, W, H


def redresser(coloriage: np.ndarray, angle: float, lineaire: bool = False) -> np.ndarray:
    """Tourne le coloriage de -angle (plus proche voisin : les numéros de classe restent entiers)."""
    if abs(angle) < 0.01:
        return coloriage.copy()
    m, W, H = _rotation(coloriage.shape, angle)
    mode = cv2.INTER_LINEAR if lineaire else cv2.INTER_NEAREST
    return cv2.warpAffine(coloriage, m, (W, H), flags=mode, borderValue=FOND)


# ---------------------------------------------------------------- 2. le bâti

def regulariser_ouvertures(col: np.ndarray, px_par_m: float) -> np.ndarray:
    """Remet chaque porte ou fenêtre à l'épaisseur exacte du mur qui la porte.

    Atelya colorie souvent une porte-fenêtre ou une fenêtre un peu plus large (ou plus fine)
    que le mur, avec un bord ondulé. Le suivi des murs, qui compare chaque colonne de pixels à
    la précédente, coupait alors le mur en morceaux au milieu de l'ouverture, et l'ouverture
    se retrouvait décalée. On mesure l'épaisseur du mur juste avant et juste après l'ouverture,
    puis on « repeint » l'ouverture pile dans cette bande."""
    sortie = col.copy()
    ep_max = max(3, int(round(0.6 * px_par_m)))
    k_cote = 4
    for classe in OUVERTURES:
        n, etiq, stats, _ = cv2.connectedComponentsWithStats((col == classe).astype(np.uint8), connectivity=8)
        for i in range(1, n):
            x, y, w, h, aire = stats[i]
            if aire < 4:
                continue
            horizontal = w >= h
            c = col if horizontal else col.T
            e = etiq if horizontal else etiq.T
            s = sortie if horizontal else sortie.T  # vue : écrire dans s écrit dans sortie
            a, b, t0, t1 = (x, x + w, y, y + h) if horizontal else (y, y + h, x, x + w)
            marge = max(t1 - t0, 4)
            lo, hi = max(0, t0 - marge), min(c.shape[0], t1 + marge)
            bandes = []
            for u in [*range(a - k_cote, a), *range(b, b + k_cote)]:
                if not 0 <= u < c.shape[1]:
                    continue
                murs = np.concatenate([[0], (c[lo:hi, u] == MUR).astype(np.int8), [0]])
                d = np.diff(murs)
                for h0, b0 in zip(np.nonzero(d == 1)[0] + lo, np.nonzero(d == -1)[0] + lo):
                    if h0 < t1 and b0 > t0 and b0 - h0 <= ep_max:
                        bandes.append((h0, b0))
            if len(bandes) < 2:
                continue
            haut = int(round(np.median([v[0] for v in bandes])))
            bas = int(round(np.median([v[1] for v in bandes])))
            if bas - haut < 1:
                continue
            fenetre = e[min(t0, haut):max(t1, bas), a:b] == i
            zone = s[min(t0, haut):max(t1, bas), a:b]
            lignes = np.arange(min(t0, haut), max(t1, bas))[:, None]
            dans = (lignes >= haut) & (lignes < bas)
            zone[fenetre & ~dans] = FOND
            zone[np.broadcast_to(dans, zone.shape)] = classe
    return sortie


def bati_du_logement(col: np.ndarray, px_par_m: float) -> np.ndarray:
    """Masque des murs, portes et fenêtres reliés au logement. Une tache coloriée « mur »
    loin du bâtiment (flèche du Nord, barre d'échelle, cadre de la page) est jetée."""
    bati = ((col >= MUR) & (col <= PORTE_FENETRE)).astype(np.uint8)
    # Refermer les trous de 1 à 2 pixels laissés par Atelya.
    bati = cv2.morphologyEx(bati, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, etiq, stats, _ = cv2.connectedComponentsWithStats(bati, connectivity=8)
    if n <= 1:
        return np.zeros_like(bati, bool)
    principal = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = stats[principal, :4]
    marge = int(round(0.3 * px_par_m))
    garde = np.zeros(n, bool)
    garde[principal] = True
    for i in range(1, n):
        xi, yi, wi, hi, aire = stats[i]
        dedans = xi >= x - marge and yi >= y - marge and xi + wi <= x + w + marge and yi + hi <= y + h + marge
        if dedans and aire >= (0.05 * px_par_m) ** 2:
            garde[i] = True
    return garde[etiq]


def dehors_du_logement(bati: np.ndarray) -> np.ndarray:
    """Tout ce qui n'est pas du bâti et touche le bord de l'image (par le vide) : l'extérieur."""
    libre = (~bati).astype(np.uint8)
    h, w = libre.shape
    cadre = np.ones((h + 2, w + 2), np.uint8)
    cadre[1:-1, 1:-1] = libre
    remplissage = cadre.copy()
    masque = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(remplissage, masque, (0, 0), 2)
    return remplissage[1:-1, 1:-1] == 2


# ---------------------------------------------------------------- 3. les murs

def _bandes(masque: np.ndarray, horizontal: bool, tol: float, long_min: int) -> list[Segment]:
    """Suit, colonne par colonne, les bandes de pixels d'un masque de murs horizontaux
    (lignes par lignes pour les verticaux) et les regroupe en murs d'épaisseur constante."""
    m = masque if horizontal else masque.T
    # Un mur en cours : [debut, fin, somme_haut, somme_bas, n, dernier_haut, dernier_bas].
    # On compare chaque colonne à la précédente : un mur un peu tordu (photocopie) reste un seul mur.
    ouverts: list[list] = []
    finis: list[list] = []
    for x in range(m.shape[1]):
        col = m[:, x]
        if not col.any():
            finis += ouverts
            ouverts = []
            continue
        d = np.diff(np.concatenate([[0], col.astype(np.int8), [0]]))
        hauts, bas = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        suivants = []
        pris = set()
        for h0, b0 in zip(hauts, bas):
            choisi = None
            for k, s in enumerate(ouverts):
                if k in pris:
                    continue
                if abs(h0 - s[5]) <= tol and abs(b0 - s[6]) <= tol:
                    choisi = k
                    break
            if choisi is None:
                suivants.append([x, x + 1, float(h0), float(b0), 1, float(h0), float(b0)])
            else:
                pris.add(choisi)
                s = ouverts[choisi]
                s[1] = x + 1
                s[2] += h0
                s[3] += b0
                s[4] += 1
                s[5], s[6] = 0.7 * s[5] + 0.3 * h0, 0.7 * s[6] + 0.3 * b0
                suivants.append(s)
        finis += [s for k, s in enumerate(ouverts) if k not in pris]
        ouverts = suivants
    finis += ouverts
    segs = [Segment(horizontal, s[0], s[1], s[2] / s[4], s[3] / s[4]) for s in finis if s[1] - s[0] >= long_min]
    return _fusionner(segs, tol)


def _fusionner(segs: list[Segment], tol: float) -> list[Segment]:
    """Recolle deux morceaux d'un même mur (même axe, même épaisseur, presque bout à bout)."""
    segs = sorted(segs, key=lambda s: (round(s.axe), s.a))
    sortie: list[Segment] = []
    for s in sorted(segs, key=lambda s: s.a):
        for t in sortie:
            if (abs(t.axe - s.axe) <= tol and abs(t.epaisseur - s.epaisseur) <= tol
                    and s.a <= t.b + 2 and s.b >= t.a - 2):
                la, lb = t.b - t.a, s.b - s.a
                t.haut = (t.haut * la + s.haut * lb) / (la + lb)
                t.bas = (t.bas * la + s.bas * lb) / (la + lb)
                t.a, t.b = min(t.a, s.a), max(t.b, s.b)
                break
        else:
            sortie.append(s)
    return sortie


def trouver_murs(bati: np.ndarray, dehors: np.ndarray, px_par_m: float) -> list[Segment]:
    long_min = max(4, int(round(LONGUEUR_MIN_MUR * px_par_m)))
    tol = max(1.5, TOLERANCE_BORD * px_par_m)
    b = bati.astype(np.uint8)
    hor = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((1, long_min), np.uint8)).astype(bool)
    ver = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((long_min, 1), np.uint8)).astype(bool)
    segs = _bandes(hor, True, tol, long_min) + _bandes(ver, False, tol, long_min)
    # Un mur plus épais que long est un morceau de mur perpendiculaire.
    segs = [s for s in segs if s.b - s.a > 1.2 * s.epaisseur and s.epaisseur >= 1]
    segs = [m for s in segs for m in _decouper_par_cote(s, dehors, bati, long_min)]
    segs = _couper_aux_croisements(segs, long_min)
    # Les bouts se calculent tous sur les murs d'origine, puis s'appliquent ensemble.
    origine = [Segment(**vars(s)) for s in segs]
    bouts = [_ajuster_bouts(s, origine, tol + 1) for s in origine]
    for s, (a, b) in zip(segs, bouts):
        s.a, s.b = a, b
    # Après ajustement, un « mur » plus court que LONGUEUR_MIN_MUR ou plus fin que 3 cm
    # est un reste de coloriage (bavure dans un angle, trait de meuble), pas un mur.
    return [s for s in segs if s.b - s.a >= long_min and s.epaisseur >= EPAISSEUR_MIN * px_par_m]


def _cotes_dehors(s: Segment, dehors: np.ndarray, bati: np.ndarray) -> np.ndarray:
    """Pour chaque colonne du mur : 1 si une face donne dehors, 0 si les deux faces donnent
    dedans, -1 si on ne sait pas (un mur perpendiculaire colle à la face)."""
    d = dehors if s.horizontal else dehors.T
    b_ = bati if s.horizontal else bati.T
    a, b = int(s.a), max(int(s.a) + 1, int(s.b))
    etat = np.full(b - a, -1, np.int8)
    libre = np.zeros(b - a, bool)
    for ligne in (int(math.floor(s.haut)) - 2, int(math.ceil(s.bas)) + 1):
        if 0 <= ligne < d.shape[0]:
            libre |= ~b_[ligne, a:b]
            etat[d[ligne, a:b]] = 1
        else:
            etat[:] = 1
    etat[(etat == -1) & libre] = 0
    return etat


def _decouper_par_cote(s: Segment, dehors: np.ndarray, bati: np.ndarray, long_min: int) -> list[Segment]:
    """Un même trait droit peut être mur extérieur sur une partie et cloison ailleurs
    (mur porteur dans le prolongement d'une façade) : on le coupe là où ça change."""
    etat = _cotes_dehors(s, dehors, bati)
    connu = etat[etat >= 0]
    if not len(connu):
        s.exterieur = False
        return [s]
    # Un état qui ne dure que quelques colonnes ne compte pas ; les colonnes « on ne sait pas »
    # prennent l'état connu le plus proche avant elles (ou après, en tête du mur).
    k0 = 0
    for k in range(1, len(etat) + 1):
        if k == len(etat) or etat[k] != etat[k0]:
            if etat[k0] >= 0 and k - k0 < long_min / 2:
                etat[k0:k] = -1
            k0 = k
    connu = np.nonzero(etat >= 0)[0]
    if not len(connu):
        s.exterieur = bool((_cotes_dehors(s, dehors, bati) == 1).mean() > 0.5)
        return [s]
    courant = int(etat[connu[0]])
    for k in range(len(etat)):
        if etat[k] < 0:
            etat[k] = courant
        courant = int(etat[k])
    # Des tronçons : (état, début, fin) ; les trop courts rejoignent leur voisin.
    troncons = []
    k0 = 0
    for k in range(1, len(etat) + 1):
        if k == len(etat) or etat[k] != etat[k0]:
            troncons.append([int(etat[k0]), k0, k])
            k0 = k
    change = True
    while change and len(troncons) > 1:
        change = False
        for i, t in enumerate(troncons):
            if t[2] - t[1] < long_min / 2:
                j = i - 1 if i > 0 else i + 1
                v = troncons[j]
                v[1], v[2] = min(v[1], t[1]), max(v[2], t[2])
                troncons.pop(i)
                change = True
                break
        fus = [troncons[0]]
        for t in troncons[1:]:
            if t[0] == fus[-1][0]:
                fus[-1][2] = t[2]
            else:
                fus.append(t)
        troncons = fus
    sortie = []
    for i, (e, k0, k1) in enumerate(troncons):
        a = s.a if i == 0 else int(s.a) + k0
        b = s.b if i == len(troncons) - 1 else int(s.a) + k1
        sortie.append(Segment(s.horizontal, a, b, s.haut, s.bas, bool(e)))
    return sortie


def _croise(p: Segment, s: Segment, depasse: float) -> bool:
    """Le mur perpendiculaire p traverse-t-il s (il continue nettement des deux côtés) ?"""
    return p.a < s.haut - depasse and p.b > s.bas + depasse and s.a < p.haut and p.bas < s.b


def _couper_aux_croisements(segs: list[Segment], long_min: int) -> list[Segment]:
    """Deux cloisons qui se croisent : la plus longue reste entière, l'autre devient deux murs
    qui s'arrêtent contre elle. Les murs extérieurs ne sont jamais coupés."""
    sortie = []
    for s in segs:
        morceaux = [s]
        if not s.exterieur:
            for p in segs:
                # Au croisement de deux cloisons, la plus longue continue, l'autre est coupée.
                if p.horizontal == s.horizontal or p.b - p.a < s.b - s.a or not _croise(p, s, long_min / 2):
                    continue
                nouveaux = []
                for m in morceaux:
                    if m.a < p.haut and p.bas < m.b:
                        nouveaux += [Segment(m.horizontal, m.a, p.bas, m.haut, m.bas, m.exterieur),
                                     Segment(m.horizontal, p.haut, m.b, m.haut, m.bas, m.exterieur)]
                    else:
                        nouveaux.append(m)
                morceaux = nouveaux
        sortie += [m for m in morceaux if m.b - m.a >= long_min / 2]
    return sortie


def _ajuster_bouts(s: Segment, segs: list[Segment], tol: float) -> tuple[float, float]:
    """Règle des plans (et du générateur) : deux murs extérieurs se rejoignent sur leurs axes ;
    un mur intérieur s'arrête contre la face du mur qu'il rencontre."""
    perp = [p for p in segs if p.horizontal != s.horizontal and p.a <= s.bas + tol and p.b >= s.haut - tol]
    sortie = []
    for bout in ("a", "b"):
        x = getattr(s, bout)
        meilleur, ecart = None, None
        for p in perp:
            if p.haut - tol <= x <= p.bas + tol:
                # À égalité, un mur extérieur rejoint de préférence un autre mur extérieur.
                e = (round(abs(x - (p.haut if bout == "a" else p.bas))), not (s.exterieur and p.exterieur))
                if ecart is None or e < ecart:
                    meilleur, ecart = p, e
        if meilleur is None:
            sortie.append(x)
        elif s.exterieur and meilleur.exterieur:
            sortie.append(meilleur.axe)
        else:
            sortie.append(meilleur.bas if bout == "a" else meilleur.haut)
    return sortie[0], sortie[1]


# ---------------------------------------------------------------- 4. les ouvertures

def trouver_ouvertures(col: np.ndarray, bati: np.ndarray, segs: list[Segment], px_par_m: float) -> list[dict]:
    """Chaque tache porte / fenêtre / porte-fenêtre est posée sur le mur qui la contient."""
    trouvees = []
    for classe in OUVERTURES:
        m = ((col == classe) & bati).astype(np.uint8)
        n, _, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        for i in range(1, n):
            x, y, w, h, aire = stats[i]
            if aire < (0.03 * px_par_m) ** 2:
                continue
            horizontal = w >= h
            cx, cy = x + w / 2, y + h / 2
            long_, travers = (cx, cy) if horizontal else (cy, cx)
            debut, fin = (x, x + w) if horizontal else (y, y + h)
            mur, ecart = None, None
            for k, s in enumerate(segs):
                if s.horizontal != horizontal or not (s.haut - 2 <= travers <= s.bas + 2):
                    continue
                if not (s.a - 2 <= long_ <= s.b + 2):
                    continue
                e = abs(travers - s.axe)
                if ecart is None or e < ecart:
                    mur, ecart = k, e
            if mur is None:
                continue
            trouvees.append({"classe": classe, "mur": mur, "debut": float(debut), "fin": float(fin), "aire": int(aire)})
    # Recoller les morceaux d'une même ouverture (même mur, même type, presque bout à bout).
    trouvees.sort(key=lambda o: (o["mur"], o["classe"], o["debut"]))
    fusion: list[dict] = []
    for o in trouvees:
        p = fusion[-1] if fusion else None
        if p and p["mur"] == o["mur"] and p["classe"] == o["classe"] and o["debut"] - p["fin"] <= ECART_FUSION_OUVERTURE * px_par_m:
            p["fin"] = max(p["fin"], o["fin"])
            p["aire"] += o["aire"]
        else:
            fusion.append(dict(o))
    # Deux ouvertures de types différents qui se chevauchent : la plus grande gagne.
    sortie: list[dict] = []
    for o in sorted(fusion, key=lambda o: -(o["fin"] - o["debut"])):
        if any(q["mur"] == o["mur"] and o["debut"] < q["fin"] and q["debut"] < o["fin"] for q in sortie):
            continue
        if (o["fin"] - o["debut"]) >= LARGEUR_MIN_OUVERTURE * px_par_m:
            sortie.append(o)
    return sortie


# ---------------------------------------------------------------- 5. les pièces

def trouver_pieces(col: np.ndarray, bati: np.ndarray, dehors: np.ndarray, px_par_m: float,
                   noms: list[tuple[int, float, float]] | None = None) -> list[dict]:
    """Les zones fermées de l'intérieur, chacune avec le type de pièce le plus colorié dedans.

    `noms` : les noms de pièces lus sur le plan, (classe, x, y) en pixels du coloriage redressé.
    Un nom écrit dans une zone l'emporte sur la couleur ; deux noms différents dans une zone d'une
    seule couleur (cloison oubliée par Atelya) la coupent en deux."""
    dedans = (~bati & ~dehors).astype(np.uint8)
    n, etiq, stats, _ = cv2.connectedComponentsWithStats(dedans, connectivity=4)
    h, w = col.shape
    pieces = []
    zones = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < SURFACE_MIN_PIECE * px_par_m ** 2:
            continue
        zone = etiq == i
        parts = separer_par_couleur(zone, col, px_par_m)
        dans = _noms_dans(zone, noms)
        if len(parts) == 1 and len({c for c, _, _ in dans}) >= 2:
            parts = separer_par_noms(zone, dans)  # une seule couleur, mais deux noms : deux pièces
        zones += parts
    for zone in zones:
        valeurs = col[zone]
        valeurs = valeurs[valeurs >= 5]
        if len(valeurs):
            compte = np.bincount(valeurs, minlength=16)
            classe = int(np.argmax(compte))
            confiance = float(compte[classe] / len(valeurs))
        else:
            classe, confiance = 5, 0.0
        lus = {c for c, _, _ in _noms_dans(zone, noms)}
        nom_lu = len(lus) == 1
        if nom_lu:
            classe, confiance = lus.pop(), 1.0
        contour = _contour_orthogonal(zone)
        if contour is None:
            continue
        pieces.append({"classe": classe, "contour_px": contour, "confiance": round(confiance, 2), "nom_lu": nom_lu})
    return pieces


def _noms_dans(zone: np.ndarray, noms: list[tuple[int, float, float]] | None) -> list[tuple[int, float, float]]:
    h, w = zone.shape
    return [(c, x, y) for c, x, y in (noms or []) if 0 <= int(y) < h and 0 <= int(x) < w and zone[int(y), int(x)]]


def separer_par_noms(zone: np.ndarray, noms: list[tuple[int, float, float]]) -> list[np.ndarray]:
    """Partage une zone entre les noms de types différents écrits dedans : chaque pixel va au nom le plus proche."""
    ys, xs = np.nonzero(zone)
    centres = np.array([(x, y) for _, x, y in noms])
    classes = np.array([c for c, _, _ in noms])
    d = (xs[:, None] - centres[None, :, 0]) ** 2 + (ys[:, None] - centres[None, :, 1]) ** 2
    proche = classes[np.argmin(d, axis=1)]
    sortie = []
    for c in np.unique(classes):
        m = np.zeros(zone.shape, bool)
        m[ys[proche == c], xs[proche == c]] = True
        sortie.append(m)
    return sortie


def separer_par_couleur(zone: np.ndarray, col: np.ndarray, px_par_m: float) -> list[np.ndarray]:
    """Coupe une zone fermée qui contient deux pièces de types différents.

    Quand Atelya oublie un bout de cloison fine (entre un WC et un placard, par exemple), les deux
    pièces ne font plus qu'une zone. Mais chacune garde souvent sa propre couleur : si la zone
    contient deux grandes taches de types différents, on la partage entre elles (chaque pixel va
    à la tache la plus proche)."""
    x, y, w, h = cv2.boundingRect(zone.astype(np.uint8))
    z = zone[y:y + h, x:x + w]
    c = col[y:y + h, x:x + w]
    aire_min = max(SURFACE_MIN_SEPARATION * px_par_m ** 2, PART_MIN_SEPARATION * z.sum())
    noyau = np.ones((3, 3), np.uint8)
    graines = []
    for classe in np.unique(c[z]):
        if classe < 5:
            continue
        tache = cv2.morphologyEx((z & (c == classe)).astype(np.uint8), cv2.MORPH_OPEN, noyau)
        n, etiq, stats, _ = cv2.connectedComponentsWithStats(tache, connectivity=4)
        graines += [etiq == k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= aire_min]
    if len(graines) < 2:
        return [zone]
    marques = np.zeros(z.shape, np.int32)
    for k, g in enumerate(graines, 1):
        marques[g] = k
    # Chaque pixel de la zone rejoint la graine la plus proche (distance mesurée dans la zone).
    _, plus_proche = cv2.distanceTransformWithLabels((marques == 0).astype(np.uint8), cv2.DIST_L2, 5,
                                                     labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(marques)
    vers = np.zeros(plus_proche.max() + 1, np.int32)
    vers[plus_proche[ys, xs]] = marques[ys, xs]
    parts = vers[plus_proche]
    sortie = []
    for k in range(1, len(graines) + 1):
        m = np.zeros(zone.shape, bool)
        m[y:y + h, x:x + w] = z & (parts == k)
        sortie.append(m)
    return sortie


def _contour_orthogonal(zone: np.ndarray) -> list[tuple[float, float]] | None:
    """Le contour d'une zone, simplifié en polygone à angles droits, sur les bords des pixels."""
    contours, _ = cv2.findContours(zone.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    eps = max(1.5, 0.01 * cv2.arcLength(c, True))
    pts = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
    if len(pts) < 3:
        return None
    # Chaque côté devient horizontal ou vertical, à la position moyenne de ses deux bouts.
    n = len(pts)
    cotes = []
    for k in range(n):
        p, q = pts[k], pts[(k + 1) % n]
        horiz = abs(q[0] - p[0]) >= abs(q[1] - p[1])
        cotes.append((horiz, (p[1] + q[1]) / 2 if horiz else (p[0] + q[0]) / 2))
    # Côtés consécutifs de même sens : on les fond en un seul (moyenne).
    fondus: list[list] = []
    for horiz, v in cotes:
        if fondus and fondus[-1][0] == horiz:
            fondus[-1][1].append(v)
        else:
            fondus.append([horiz, [v]])
    if len(fondus) > 1 and fondus[0][0] == fondus[-1][0]:
        fondus[0][1] += fondus.pop()[1]
    if len(fondus) < 4 or len(fondus) % 2:
        x, y, w, h = cv2.boundingRect(c)
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    lignes = [(h, float(np.mean(v))) for h, v in fondus]
    sommets = []
    for k in range(len(lignes)):
        (h1, v1), (h2, v2) = lignes[k - 1], lignes[k]
        sommets.append((v2, v1) if h1 else (v1, v2))
    # Les points du contour d'OpenCV sont des centres de pixels : on décale chaque côté
    # d'un demi-pixel vers l'extérieur pour tomber sur le bord de la zone.
    aire = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(sommets, sommets[1:] + sommets[:1])) / 2
    sens = 1 if aire > 0 else -1
    decales = []
    m = len(sommets)
    for k in range(m):
        p0, p1, p2 = sommets[k - 1], sommets[k], sommets[(k + 1) % m]
        x, y = p1
        for (ax, ay), (bx, by) in ((p0, p1), (p1, p2)):
            dx, dy = bx - ax, by - ay
            # Normale extérieure d'un côté (repère image : y vers le bas).
            nx, ny = (dy, -dx) if sens > 0 else (-dy, dx)
            norme = math.hypot(nx, ny) or 1
            nx, ny = nx / norme, ny / norme
            if abs(dx) >= abs(dy):
                y += 0.5 * np.sign(ny)
            else:
                x += 0.5 * np.sign(nx)
        decales.append((x + 0.5, y + 0.5))
    return decales


# ---------------------------------------------------------------- 6. vers les mètres

def lire_coloriage(coloriage: np.ndarray, px_par_m: float, *, projet_id: str = "atelya",
                   hauteur_sous_plafond: float | None = None, angle: float | None = None,
                   redressement: Redressement | None = None, noms: list | None = None) -> tuple[dict, dict]:
    """Traduit un coloriage d'Atelya (classes 0 à 15, une par pixel) en contenu de logement.json.

    `px_par_m` : l'échelle de l'image donnée à Atelya (pixels par mètre).
    `redressement` : pour un plan photographié de biais, la transformation qui le remet à plat
    (moteur.redressement) ; `px_par_m` est alors l'échelle de l'image redressée.
    `noms` : les noms de pièces lus sur le plan (moteur.noms_pieces.NomLu), en pixels du coloriage
    donné ; ils décident du type des pièces où ils sont écrits.
    Renvoie (logement, détails) ; le logement est vérifié par le format logement/0.1.
    """
    col = coloriage.astype(np.uint8)
    classe_du_type = {t: c for c, (t, _) in PIECES.items()}
    points = [(classe_du_type[n.type], n.x, n.y) for n in (noms or []) if n.type in classe_du_type]
    if redressement is not None:
        col = redressement.appliquer(col)
        points = [(c, *redressement.point(x, y)) for c, x, y in points]
        angle = 0.0  # le redressement a déjà remis les murs d'aplomb
    if angle is None:
        angle = estimer_rotation(((col >= MUR) & (col <= PORTE_FENETRE)))
    if abs(angle) >= 0.01:
        m, _, _ = _rotation(col.shape, angle)
        points = [(c, *(m @ (x, y, 1.0))) for c, x, y in points]
    col = redresser(col, angle)
    col = regulariser_ouvertures(col, px_par_m)
    bati = bati_du_logement(col, px_par_m)
    if not bati.any():
        raise ValueError("aucun mur trouvé dans le coloriage")
    dehors = dehors_du_logement(bati)
    segs = trouver_murs(bati, dehors, px_par_m)
    if not segs:
        raise ValueError("aucun mur droit trouvé dans le coloriage")
    ouvertures = trouver_ouvertures(col, bati, segs, px_par_m)
    pieces = trouver_pieces(col, bati, dehors, px_par_m, points)

    dedans = ~bati & ~dehors
    ys, xs = np.nonzero(dedans)
    if len(xs):
        ox, oy = float(xs.min()), float(ys.max() + 1)
    else:
        ys, xs = np.nonzero(bati)
        ox, oy = float(xs.min()), float(ys.max() + 1)
    s = px_par_m
    hsp = hauteur_sous_plafond or HAUTEUR_SOUS_PLAFOND

    def pt(u: float, v: float) -> list[float]:
        return [round((u - ox) / s, 3), round((oy - v) / s, 3)]

    murs, ids = [], {}
    for k, g in enumerate(segs):
        if g.horizontal:
            debut, fin = pt(g.a, g.axe), pt(g.b, g.axe)
        else:
            debut, fin = pt(g.axe, g.b), pt(g.axe, g.a)  # du sud vers le nord
        ep = round(g.epaisseur / s, 3)
        if math.dist(debut, fin) <= 0 or ep <= 0:
            continue
        ids[k] = f"M{len(murs) + 1}"
        murs.append({"id": ids[k], "debut": debut, "fin": fin, "epaisseur": ep,
                     "statut": "estime", "source": "atelya"})
    longueurs = {m["id"]: math.dist(m["debut"], m["fin"]) for m in murs}

    sortie_ouv = []
    for o in sorted(ouvertures, key=lambda o: (o["mur"], o["debut"])):
        if o["mur"] not in ids:
            continue
        g = segs[o["mur"]]
        mid = ids[o["mur"]]
        if g.horizontal:
            pos = (o["debut"] - g.a) / s
        else:
            pos = (g.b - o["fin"]) / s  # le mur vertical va du sud (bas de l'image) au nord
        largeur = (o["fin"] - o["debut"]) / s
        pos = max(0.0, pos)
        largeur = min(largeur, longueurs[mid] - pos)
        if largeur < LARGEUR_MIN_OUVERTURE:
            continue
        type_ = OUVERTURES[o["classe"]]
        if type_ == "porte":
            hauteur, allege = HAUTEUR_PORTE, 0.0
        elif type_ == "porte_fenetre":
            hauteur, allege = HAUTEUR_PORTE_FENETRE, 0.0
        else:
            haut = min(hsp - 0.15, HAUT_FENETRE)
            hauteur = 0.60 if largeur <= 0.65 else 1.25
            allege = haut - hauteur
        hauteur = min(hauteur, hsp)
        sortie_ouv.append({"id": f"O{len(sortie_ouv) + 1}", "type": type_, "mur": mid,
                           "position": round(pos, 3), "largeur": round(largeur - 1e-6, 3),
                           "hauteur": round(hauteur, 3), "allege": round(allege, 3),
                           "statut": "estime", "source": "atelya"})

    sortie_pieces, compte, types_pieces, noms_lus = [], {}, {}, []
    for p in pieces:
        type_, nom = PIECES.get(p["classe"], ("sejour", "Séjour"))
        compte[type_] = compte.get(type_, 0) + 1
        contour = [pt(u, v) for u, v in p["contour_px"]]
        if len(contour) < 3:
            continue
        sortie_pieces.append({"id": f"{type_}_{compte[type_]}", "nom": nom if compte[type_] == 1 else f"{nom} {compte[type_]}",
                              "contour": contour, "statut": "estime", "source": "atelya",
                              "confiance": p["confiance"]})
        types_pieces[sortie_pieces[-1]["id"]] = type_
        if p["nom_lu"]:
            noms_lus.append(sortie_pieces[-1]["id"])

    logement = {"schema": "logement/0.1", "projet_id": projet_id, "unites": "m",
                "hauteur_sous_plafond": hsp, "murs": murs, "ouvertures": sortie_ouv, "pieces": sortie_pieces}
    Logement.model_validate(logement)
    details = {"version": VERSION_COLORIAGE, "angle_deg": round(angle, 3), "px_par_m": px_par_m,
               "redresse": redressement is not None,
               "types_pieces": types_pieces, "pieces_nom_lu": noms_lus}
    return logement, details
