"""Lire l'échelle d'un plan colorié par Atelya, sur les cotes du dessin d'origine (version 0.1).

Atelya colorie le plan mais ne sait pas combien de pixels font un mètre : il faut le lire sur
les cotes (« 4,80 » entre deux marques). Les cotes sont lues par moteur.lecture_cotes, sur le
dessin d'origine en pleine taille (le texte y est net), après l'avoir remis droit exactement
comme le coloriage :
- plan à plat mais penché (scan) : on le tourne du même angle ;
- plan photographié de biais : on lui applique le même redressement (moteur.redressement).
Les cotes horizontales donnent alors l'échelle en largeur, les verticales l'échelle en hauteur.
Sur une photo, les deux diffèrent souvent de quelques % : c'est ce qui permet de rendre au plan
ses vraies proportions.

Garde-fou (decider) : l'échelle doit s'accorder avec la plus grande cote lue (la cote d'ensemble) et la
taille du logement colorié. Sinon le plan part à la vérification humaine, au lieu d'être construit à
la mauvaise taille. Un plan sans cote lisible y part aussi, sauf s'il porte une barre d'échelle
dessinée (moteur.barre_echelle, version 0.2) : elle sert alors d'échelle, si elle est sûre et que le
logement qu'elle donne a une taille vraisemblable. À défaut de barre, les surfaces écrites dans les pièces
(« Chambre 12,50 m² », moteur.surfaces_ecrites, version 0.3) donnent l'échelle si plusieurs pièces sont d'accord.

Version 0.4 : la barre est mesurée au dixième de pixel (moteur.barre_echelle) ; les cotes d'un plan
au papier gris (photocopie, photo) sont relues sur l'image aux gris étirés quand la première lecture
échoue (_lire) ; et un plan qui ne porte
aucune de ces informations reçoit une échelle « approchée » tirée de la largeur de ses portes
(echelle_par_portes, à ±10 % près). Elle ne sert jamais à construire : le plan reste « à vérifier »,
mais la personne qui vérifie part d'une maquette déjà presque à la bonne taille.

Version 0.6 : garde-fou « coloriage douteux » (coloriage_douteux). Sur une photo posée sur une table, Atelya
peut colorier des murs dans le bois ou les plis jusqu'au bord de la photo. Le logement colorié, ses surfaces et le
redressement sont alors faux, et ils faussent aussi les contrôles des chiffres lus : deux erreurs se confirment.
Un coloriage dont plus de 2 % des murs touchent le bord de l'image envoie donc l'échelle à la vérification.
Et sur une photo dont l'optique a rendu les vraies proportions, les cotes horizontales et verticales doivent donner la
même échelle : à plus de 8 % d'écart (essai : ≤ 3,6 % quand elles sont justes), une cote a été mal lue. Sur une telle
photo, les surfaces écrites l'emportent sur les cotes quand elles sont sûres, et des cotes lues dans un seul sens ne
suffisent plus : il faut les deux sens, sinon la barre, les surfaces ou la vérification humaine.

Version 0.7 (étape 6-17, moins de photos envoyées en vérification) : les taches coloriées au bord de l'image et séparées
du logement (bord de la feuille, table) sont effacées avant le garde-fou « coloriage douteux » (sans_taches_au_bord,
appliqué par le banc) ; des cotes lues dans un seul sens sont gardées si une 2e mesure les confirme à 1 % près
(_sens_unique_confirme) ; et sur une photo, les cotes trop petites pour une lecture d'un seul coup sont relues par
morceaux (_lire_par_morceaux), relecture gardée seulement si elle est sûre.

Version 0.8 (étape A2-3, plans en PDF vectoriel) : lire_echelle_plan accepte les textes déjà connus (`textes`, lus dans
le fichier PDF par moteur.lecture_pdf, en pixels du dessin). L'OCR est alors sauté : les textes sont seulement remis droit
comme le dessin, puis les cotes, la barre et les surfaces sont lues exactement comme avant, avec les mêmes garde-fous.

Version 0.9 (étape A2-4) : l'ÉCHELLE ÉCRITE d'un PDF (« Éch. 1/50 », moteur.lecture_pdf.echelle_ecrite). Dans un PDF, la
taille de la feuille est connue : « 1/50 » donne directement les pixels par mètre, même sans cotes, barre ni surfaces.
Mais un PDF imprimé « ajusté à la page » garde son « 1/50 » écrit sans plus être au 1/50 (A3 réduit en A4 : tout
est 0,71 fois trop petit). Les cotes, la barre et les surfaces, elles, rapetissent AVEC le dessin et restent justes.
D'où la règle (decider, `ecrite`) : les mesures prises sur le dessin passent toujours avant elle, et en cas de désaccord
(plus de 3 %) elle est simplement ignorée (aucun recul par rapport à la version 0.8) ; d'accord avec la barre ou les
surfaces, c'est elle qui sert (plus précise) ; seule, le plan part à la vérification. (Au départ, la largeur des portes
la confirmait à 15 % près ; banc A2-6 : 10 justes mais 1 fausse de 41 % sur une page réduite, les portes coloriées
étant elles-mêmes fausses de 28 % : supprimé.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from moteur.barre_echelle import lire_barre
from moteur.coloriage import FOND, MUR, PORTE, PORTE_FENETRE, _rotation, bati_du_logement, dehors_du_logement, dehors_pour_les_pieces, estimer_rotation, redresser
from moteur.lecture_cotes import (CONTRADICTION, COTE_MIN, ECART_MAX, ESSAIS_LECTURE, FORME_COTE, CoteLue, Echelle, TexteLu, lire_echelle,
                                  lire_textes, plan_en_cm, valeur_de_cote)
from moteur.redressement import Redressement
from moteur.surfaces_ecrites import FORME_LEGENDE, SurfaceLue, echelle_par_surfaces, surfaces_dans_textes, surfaces_de_legende

VERSION_ECHELLE = "0.11.0"
ACCORD_ENSEMBLE = 0.05  # tolérance entre la taille du logement mesurée et la cote d'ensemble
ACCORD_SECOURS = 0.03  # sans cote mesurée : largeur et hauteur d'ensemble doivent s'accorder à 3 % près
ACCORD_SURFACES = 0.03  # des cotes peu sûres que les surfaces écrites contredisent de plus de 3 % : à vérifier
PAPIER_GRIS = 235  # en dessous (niveau de gris du papier), le plan est une photocopie ou une photo : on étire ses gris
ACCORD_PORTES = 0.25  # photo : barre ou surfaces à plus de 25 % de l'échelle approchée par les portes → à vérifier
LARGEUR_PORTE = 0.83  # m : la porte intérieure courante en France (vantail de 83 cm)
PORTES_MIN = 2  # il faut au moins deux portes pour une échelle approchée
BORD_IMAGE = 0.03  # coloriage douteux : la bande du bord de l'image (fraction du grand côté)…
PART_MURS_AU_BORD = 0.02  # … où se trouvent plus de 2 % des murs, portes et fenêtres coloriés
ACCORD_OPTIQUE = 0.08  # photo aux proportions de l'optique : échelles des cotes en largeur et en hauteur à 8 % près
ACCORD_SENS_UNIQUE = 0.01  # photo cotée dans un seul sens : la 2e mesure doit la confirmer à 1 % près
MORCEAU, RECOUVREMENT = 1000, 200  # photo : lecture par morceaux de 1 000 pixels qui se recouvrent de 200
LOGEMENT_MIN, LOGEMENT_MAX = 1.5, 40.0  # mètres : la largeur et la hauteur intérieures d'un logement vraisemblable
# Portes « fiables » (version 0.11) : sur un vrai plan jamais vu, le modèle colorie en « porte » des bouts d'arcs et de
# symboles, et la médiane de leurs largeurs se trompe de 26 à 72 % (11 vrais plans). Les vraies portes coloriées sont
# régulières (largeurs à ±20 %), pleines (rectangle rempli à 60 % au moins), plus longues que les murs ne sont épais
# (1,8 fois) et peu nombreuses (≤ 30). Sur 150 plans fabriqués : aucun n'est signalé ; sur les 11 vrais : tous le sont.
PORTES_CV_MAX = 0.20  # écart-type des largeurs gardées / médiane
PORTES_REMPLISSAGE_MIN = 0.60  # aire de la tache / (longueur × largeur de sa boîte)
PORTES_SUR_EPAISSEUR_MIN = 1.8  # largeur médiane des portes / épaisseur médiane des murs
PORTES_MAX = 30  # au-delà, ce ne sont pas des portes
EPAISSEUR_MUR_COURANTE = 0.20  # m : l'épaisseur de mur courante ; en secours seulement (±20 % en médiane sur les vrais plans)


@dataclass
class EchelleLue:
    """L'échelle du coloriage (pixels du coloriage, ou du coloriage redressé, par mètre)."""

    largeur: float | None  # px par m, d'après les cotes horizontales
    hauteur: float | None  # px par m, d'après les cotes verticales
    sure: bool  # au moins deux cotes concordantes
    cotes: list[CoteLue] = field(default_factory=list)
    hauteur_sous_plafond: float | None = None
    # Le contrôle par les cotes d'ensemble : la plus grande cote horizontale (verticale) lue sur le plan,
    # en mètres, et la largeur (hauteur) intérieure du logement colorié par Atelya, en pixels.
    cote_max_largeur: float | None = None
    cote_max_hauteur: float | None = None
    interieur_px: tuple[float, float] | None = None
    # La barre d'échelle dessinée, s'il y en a une : px par m du coloriage, et le détail en clair.
    barre: float | None = None
    barre_sure: bool = False
    barre_detail: str = ""
    # L'échelle donnée par les surfaces écrites des pièces (px par m du coloriage), et le détail en clair.
    surfaces: float | None = None
    surfaces_sure: bool = False
    surfaces_detail: str = ""
    # L'échelle approchée par la largeur des portes (px par m du coloriage), pour la vérification humaine
    # seulement : jamais utilisée pour construire (voir echelle_par_portes).
    approchee: float | None = None
    # Le coloriage d'Atelya colle au bord de l'image (table ou plis coloriés en murs) : voir coloriage_douteux.
    douteux: bool = False
    # L'échelle écrite d'un PDF (« 1/50 ») : px par m du coloriage, et le détail en clair (version 0.9).
    ecrite: float | None = None
    ecrite_detail: str = ""
    # Pour le diagnostic : les cotes qui ont fait l'échelle, et si les autres la contredisent (version 0.10).
    retenues: list[CoteLue] = field(default_factory=list)
    contredite: bool = False
    # Les portes coloriées ont-elles l'air de vraies portes (voir portes_fiables) ? Et l'échelle qu'on tirerait de
    # l'épaisseur des murs (voir echelle_par_epaisseur), dernier secours d'un brouillon (version 0.11).
    portes_fiables: bool = False
    epaisseur: float | None = None

    @property
    def px_par_m(self) -> float | None:
        """L'échelle d'ensemble : celle de la largeur, sinon celle de la hauteur."""
        return self.largeur if self.largeur is not None else self.hauteur

    def decision(self, de_biais: bool, proportions_optiques: bool = False) -> tuple[float | None, float | None, str]:
        """L'échelle retenue (largeur, hauteur) et sa source, après contrôle (voir decider)."""
        return decider(self.largeur, self.hauteur, self.sure, self.cote_max_largeur, self.cote_max_hauteur,
                       self.interieur_px, de_biais, self.barre if self.barre_sure else None,
                       self.surfaces if self.surfaces_sure else None, proportions_optiques, self.approchee, self.douteux,
                       ecrite=self.ecrite)


def _plausible(echelle: float | None, interieur: float | None, cote_max: float | None, sure: bool) -> bool:
    """L'échelle est-elle compatible avec la plus grande cote lue dans ce sens ?

    Avec l'échelle, l'intérieur du logement colorié fait `interieur / echelle` mètres. Aucune cote
    partielle ne peut dépasser la cote d'ensemble : si le logement mesuré est plus petit que la plus
    grande cote lue, l'échelle est fausse. S'il est nettement plus grand, soit la cote d'ensemble n'a
    pas été lue (fréquent), soit l'échelle est fausse : on ne la garde que si elle est sûre (deux
    cotes concordantes)."""
    if not (echelle and interieur and cote_max):
        return True
    taille = interieur / echelle
    if taille < cote_max * (1 - ACCORD_ENSEMBLE):
        return False
    if taille > cote_max * (1 + ACCORD_ENSEMBLE):
        return sure
    return True


def decider(largeur: float | None, hauteur: float | None, sure: bool, cote_max_largeur: float | None,
            cote_max_hauteur: float | None, interieur_px: tuple[float, float] | None,
            de_biais: bool, barre: float | None = None,
            surfaces: float | None = None, proportions_optiques: bool = False,
            approchee: float | None = None, douteux: bool = False,
            surfaces_lues: float | None = None, ecrite: float | None = None) -> tuple[float | None, float | None, str]:
    """Contrôle l'échelle lue sur les cotes par la cote d'ensemble.

    La plus grande cote d'un plan est presque toujours la cote d'ensemble du logement : rapportée à
    la largeur (ou la hauteur) intérieure du logement colorié, elle redonne l'échelle à ~0,3 % près.
    Une échelle qui ne s'accorde pas avec elle vient d'une cote mal lue (« 6,80 » lu « 0,80 », trait
    d'une autre cote) : le plan est alors envoyé à la vérification humaine plutôt que de construire
    un logement à la mauvaise taille (voir _plausible).
    Sans aucune cote mesurée, la cote d'ensemble sert de secours, si la largeur et la hauteur
    donnent la même échelle (plan à plat seulement : sur une photo elles diffèrent).
    Sans cotes utilisables, une barre d'échelle sûre (`barre`, déjà jugée sûre par lire_barre) sert
    d'échelle si le logement qu'elle donne mesure entre 1,5 et 40 m de côté et ne contredit pas la
    cote d'ensemble (quand des cotes ont été mesurées). Sur une photo, elle ne donne que la largeur : la photo garde ses proportions.
    Sans barre, l'échelle des surfaces écrites (`surfaces`, déjà jugée sûre par echelle_par_surfaces) sert
    de la même façon, avec les mêmes contrôles, mais sur un plan à plat seulement : sur une photo de biais,
    la surface d'une pièce redressée est trop imprécise (jusqu'à 6 % d'écart sur l'échelle). Elle sert aussi
    de contrôle : des cotes peu sûres (une seule cote) ou une barre qu'elle contredit de plus de 3 % partent à la vérification.

    Version 0.5 : `proportions_optiques` — la photo de biais a retrouvé ses vraies proportions par l'optique
    (moteur.redressement.rapport_par_optique, ~0,1 % près en médiane) : la barre donne alors la largeur ET la
    hauteur, et les surfaces écrites redeviennent utilisables, comme sur un plan à plat. Garde-fou propre aux photos
    (le coloriage d'Atelya y est moins sûr) : une barre ou des surfaces qui s'écartent de plus de 25 % de l'échelle
    approchée par les portes (`approchee`) envoient le plan à la vérification.

    Version 0.6 : un coloriage douteux (`douteux`, voir coloriage_douteux) envoie toujours le plan à la vérification ;
    sur une photo aux proportions de l'optique, des cotes qui donnent en largeur et en hauteur des échelles à plus de
    8 % l'une de l'autre aussi (ACCORD_OPTIQUE). Sur une telle photo, des surfaces sûres passent avant les cotes, et
    des cotes lues dans un seul sens sont écartées (la barre ou la vérification prennent le relais).

    Version 0.7 : sur une telle photo, des cotes lues dans un seul sens sont gardées si une 2e mesure les confirme à 1 %
    près (_sens_unique_confirme) : la cote d'ensemble rapportée au logement colorié (avec au moins deux cotes d'accord),
    ou les surfaces écrites, même peu sûres (`surfaces_lues`).

    Version 0.9 : `ecrite`, l'échelle écrite d'un PDF (« 1/50 »), plan à plat seulement. Les cotes passent avant elle.
    Sans cotes utilisables : d'accord à 3 % près avec la barre ou les surfaces, c'est elle qui sert (la plus précise dans
    un PDF) ; en désaccord, elle est ignorée (page réduite à l'impression : la barre et les surfaces, dessinées, restent
    justes) ; seule, vérification (les portes ne suffisent pas à la confirmer : banc A2-6, 1 erreur de 41 %).

    Rend (largeur, hauteur, source) ; source = « cotes », « barre », « surfaces », « échelle écrite », « cote d'ensemble »
    ou « à vérifier »
    (échelles à None)."""
    if douteux:  # le logement colorié est faux : il ne peut plus contrôler aucun chiffre lu
        return None, None, "à vérifier"
    il, ih = interieur_px or (None, None)
    plat = not de_biais or proportions_optiques  # les proportions de l'image sont les vraies
    if de_biais and proportions_optiques and (largeur or hauteur):
        cotes_fiables = largeur and hauteur and sure and abs(surfaces / ((largeur + hauteur) / 2) - 1) <= ACCORD_SURFACES \
            if surfaces else False
        if surfaces and not cotes_fiables and _barre_plausible(surfaces, *(interieur_px or (None, None)), None, None):
            # Sur une photo, les surfaces écrites sont plus sûres que des cotes douteuses (essai 6-16 : ≤ 2,3 % d'erreur
            # sur 202 niveaux, quand une cote mal lue sur la photo fausse l'échelle de 3 à 6 %). Des cotes sûres, lues dans
            # les deux sens et d'accord avec les surfaces à 3 % près, restent plus précises : elles sont gardées.
            return surfaces, surfaces, "surfaces"
        if largeur and hauteur and abs(largeur / hauteur - 1) > ACCORD_OPTIQUE:
            return None, None, "à vérifier"  # les proportions sont déjà vraies : une des deux échelles vient d'une cote mal lue
        if not (largeur and hauteur) and not _sens_unique_confirme(largeur, hauteur, sure, cote_max_largeur,
                                                                 cote_max_hauteur, interieur_px, surfaces_lues):
            largeur = hauteur = None  # cotes dans un seul sens et rien pour les confirmer : elles ne suffisent pas
    if largeur or hauteur:
        if de_biais:
            bon = _plausible(largeur, il, cote_max_largeur, sure) and _plausible(hauteur, ih, cote_max_hauteur, sure)
        else:
            m = largeur or hauteur
            bon = _plausible(m, il, cote_max_largeur, sure) and _plausible(m, ih, cote_max_hauteur, sure)
        if bon and not sure and surfaces and not de_biais and abs(surfaces / (largeur or hauteur) - 1) > ACCORD_SURFACES:
            return None, None, "à vérifier"  # deux avis sérieux en désaccord : un humain tranche
        if bon:
            return largeur, hauteur, "cotes"
    # Sans aucune cote mesurée, les « nombres en forme de cote » lus sont souvent des surfaces
    # (« 12,33 » de « 12,33 m² ») : on ne confronte alors pas la barre à leur maximum.
    controle = (cote_max_largeur, cote_max_hauteur) if (largeur or hauteur) else (None, None)
    if de_biais and proportions_optiques and approchee:
        # Sur une photo, une barre ou des surfaces très loin de ce que disent les portes : lecture fausse.
        barre = barre if barre and abs(barre / approchee - 1) <= ACCORD_PORTES else None
        surfaces = surfaces if surfaces and abs(surfaces / approchee - 1) <= ACCORD_PORTES else None
    if barre and _barre_plausible(barre, il, ih, *controle):
        if surfaces and plat and abs(surfaces / barre - 1) > ACCORD_SURFACES:
            return None, None, "à vérifier"  # barre et surfaces en désaccord : un humain tranche
        if ecrite and not de_biais and abs(ecrite / barre - 1) <= ACCORD_SURFACES:
            return ecrite, ecrite, "échelle écrite"  # confirmée par la barre, et plus précise qu'elle
        return (barre, barre, "barre") if plat else (barre, None, "barre")
    if ecrite and not de_biais and _barre_plausible(ecrite, il, ih, *controle):
        if surfaces and plat and abs(surfaces / ecrite - 1) <= ACCORD_SURFACES:
            return ecrite, ecrite, "échelle écrite"  # confirmée par les surfaces, et plus précise qu'elles
        # sinon : contredite par les surfaces (page réduite ?) → les surfaces décident plus bas ; ou rien ne la confirme
        # (la largeur des portes ne suffit pas : elle peut se tromper de 28 % et « confirmer » une page réduite)
    if surfaces and plat and _barre_plausible(surfaces, il, ih, *controle):
        return surfaces, surfaces, "surfaces"
    if largeur or hauteur:
        return None, None, "à vérifier"
    ctrl_l = il / cote_max_largeur if il and cote_max_largeur else None
    ctrl_h = ih / cote_max_hauteur if ih and cote_max_hauteur else None
    if not de_biais and ctrl_l and ctrl_h and abs(ctrl_l / ctrl_h - 1) <= ACCORD_SECOURS:
        e = (ctrl_l + ctrl_h) / 2
        return e, e, "cote d'ensemble"
    return None, None, "à vérifier"


def _sens_unique_confirme(largeur: float | None, hauteur: float | None, sure: bool, cote_max_largeur: float | None,
                          cote_max_hauteur: float | None, interieur_px: tuple[float, float] | None,
                          surfaces: float | None) -> bool:
    """Photo aux proportions de l'optique, cotes lues dans un seul sens : une 2e mesure les confirme-t-elle à 1 % près ?

    - la cote d'ensemble du même sens rapportée à la taille du logement colorié, si au moins deux cotes s'accordent
      (une cote seule mal lue, si c'est aussi la plus grande, donnerait deux échelles fausses mais d'accord) ;
    - ou les surfaces écrites, même jugées peu sûres : un autre nombre, lu ailleurs sur le plan.
    Essai (étape 6-17, 28 photos réalistes cotées dans un seul sens) : 11 confirmées, toutes à moins de 0,5 % de la vraie
    échelle ; les cotes fausses de 3 à 90 % ne le sont jamais."""
    echelle = largeur or hauteur
    if not echelle:
        return False
    il, ih = interieur_px or (None, None)
    interieur, cote_max = (il, cote_max_largeur) if largeur else (ih, cote_max_hauteur)
    if sure and interieur and cote_max and abs(interieur / cote_max / echelle - 1) <= ACCORD_SENS_UNIQUE:
        return True
    return bool(surfaces and abs(surfaces / echelle - 1) <= ACCORD_SENS_UNIQUE)


def coloriage_douteux(col: np.ndarray) -> bool:
    """Atelya a-t-il colorié des murs jusqu'au bord de l'image (coloriage brut, avant redressement) ?

    Un plan dessiné ou photographié garde toujours une marge de papier ou de table autour du logement. Des murs
    coloriés au bord de l'image viennent donc de la table, des plis ou d'un reflet pris pour des traits.
    Essai (étape 6-16, coloriages de l'essai 4) : 0 sur 342 anciennes photos, 1 sur 1 066 anciens niveaux, et les
    16 échelles fausses de plus de 3 % sur 342 photos réalistes toutes attrapées."""
    bati = (col >= MUR) & (col <= PORTE_FENETRE)
    total = int(bati.sum())
    if not total:
        return False
    m = max(1, round(BORD_IMAGE * max(col.shape)))
    au_bord = int(bati[:m].sum() + bati[-m:].sum() + bati[m:-m, :m].sum() + bati[m:-m, -m:].sum())
    return au_bord > PART_MURS_AU_BORD * total


def sans_taches_au_bord(col: np.ndarray) -> np.ndarray:
    """Le coloriage sans les « murs » coloriés au bord de l'image et séparés du logement (version 0.7).

    Sur une photo posée sur une table, Atelya colorie parfois le bord de la feuille, un pli ou le dessin de la table
    en murs. Ces taches touchent la bande du bord de l'image (voir coloriage_douteux) mais ne tiennent pas au logement :
    le logement est le plus grand morceau de bâti (murs, portes et fenêtres, qui se touchent à 2 pixels près).
    On efface les autres morceaux qui touchent cette bande ; tout le reste du coloriage est gardé tel quel.
    Essai (étape 6-17, coloriages de l'essai 5, 343 photos réalistes avec cotes) : sur les 30 coloriages douteux, le logement
    ne touche jamais la bande du bord ; seules ces taches la touchent."""
    bati = ((col >= MUR) & (col <= PORTE_FENETRE)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(bati, np.ones((5, 5), np.uint8)), connectivity=8)
    if n <= 2:
        return col
    logement = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = max(1, round(BORD_IMAGE * max(col.shape)))
    bande = np.zeros(col.shape, bool)
    bande[:m], bande[-m:], bande[:, :m], bande[:, -m:] = True, True, True, True
    au_bord = np.unique(lab[bande & (bati > 0)])
    effacer = np.isin(lab, [i for i in au_bord if i not in (0, logement)]) & (bati > 0)
    if not effacer.any():
        return col
    propre = col.copy()
    propre[effacer] = FOND
    return propre


def echelle_par_portes(col: np.ndarray) -> float | None:
    """Une échelle approchée (px par m du coloriage remis droit), tirée de la largeur des portes coloriées.

    Pour un plan sans cotes, sans barre et sans surfaces écrites : aucune mesure exacte n'est possible,
    mais les portes intérieures ont presque toutes la même largeur (73, 83 ou 93 cm ; 83 le plus
    souvent). La largeur médiane des portes, rapportée à 83 cm, donne l'échelle à ±10 % près environ
    (essai sur 994 niveaux de test : 78 % à 10 % près). C'est trop imprécis pour construire, mais
    suffisant pour proposer à la personne qui vérifie une maquette presque à la bonne taille.
    Les petits morceaux de porte (coloriage hésitant) sont écartés : moins de 60 % des grandes portes."""
    n, _, stats, _ = cv2.connectedComponentsWithStats((col == PORTE).astype(np.uint8), connectivity=4)
    largeurs = np.array([max(stats[i, 2], stats[i, 3]) for i in range(1, n) if min(stats[i, 2], stats[i, 3]) >= 2], float)
    if len(largeurs) < PORTES_MIN:
        return None
    largeurs = largeurs[largeurs >= 0.6 * np.percentile(largeurs, 75)]
    if len(largeurs) < PORTES_MIN:
        return None
    return round(float(np.median(largeurs)) / LARGEUR_PORTE, 3)


def epaisseur_des_murs(col: np.ndarray) -> float | None:
    """L'épaisseur médiane des murs coloriés, en pixels (deux fois la distance au bord sur la crête des murs)."""
    murs = (col == MUR).astype(np.uint8)
    if murs.sum() < 50:
        return None
    d = cv2.distanceTransform(murs, cv2.DIST_L2, 3)
    cretes = d[(d >= cv2.dilate(d, np.ones((3, 3), np.uint8)) - 1e-3) & (d > 0.5)]
    if len(cretes) < 20:
        return None
    return float(2 * np.median(cretes))


def portes_fiables(col: np.ndarray) -> bool:
    """Les taches coloriées « porte » ressemblent-elles à de vraies portes ? Voir PORTES_CV_MAX et suivants.

    Faux quand le modèle a semé des fragments (vrais plans d'un style jamais vu) : l'échelle approchée par les portes
    ne vaut alors rien, et il ne faut pas s'en servir même pour un brouillon."""
    n, _, stats, _ = cv2.connectedComponentsWithStats((col == PORTE).astype(np.uint8), connectivity=4)
    taches = [(max(stats[i, 2], stats[i, 3]), min(stats[i, 2], stats[i, 3]), stats[i, 4])
              for i in range(1, n) if min(stats[i, 2], stats[i, 3]) >= 2]
    if not PORTES_MIN <= len(taches) <= PORTES_MAX:
        return False
    longueurs = np.array([t[0] for t in taches], float)
    gardees = longueurs >= 0.6 * np.percentile(longueurs, 75)
    if gardees.sum() < PORTES_MIN:
        return False
    L = longueurs[gardees]
    petites = np.array([t[1] for t in taches], float)[gardees]
    aires = np.array([t[2] for t in taches], float)[gardees]
    mediane = float(np.median(L))
    if np.std(L) / mediane > PORTES_CV_MAX:
        return False
    if np.median(aires / (L * petites)) < PORTES_REMPLISSAGE_MIN:
        return False
    ep = epaisseur_des_murs(col)
    return not ep or mediane / ep >= PORTES_SUR_EPAISSEUR_MIN


def echelle_par_epaisseur(col: np.ndarray) -> float | None:
    """Une échelle très approchée (px par m) : les murs coloriés font EPAISSEUR_MUR_COURANTE. Secours d'un brouillon quand
    rien d'autre n'est lisible : ±20 % en médiane sur les vrais plans, jamais pire que 50 %, quand les portes se trompaient
    de 36 % en médiane et jusqu'à 72 %. Jamais pour construire."""
    ep = epaisseur_des_murs(col)
    return round(ep / EPAISSEUR_MUR_COURANTE, 3) if ep else None


def _barre_plausible(barre: float, il: float | None, ih: float | None, cote_max_largeur: float | None,
                     cote_max_hauteur: float | None) -> bool:
    """Le logement mesuré avec l'échelle de la barre (ou des surfaces) a-t-il une taille vraisemblable ?"""
    for interieur, cote_max in ((il, cote_max_largeur), (ih, cote_max_hauteur)):
        if interieur and not LOGEMENT_MIN <= interieur / barre <= LOGEMENT_MAX:
            return False
        if not _plausible(barre, interieur, cote_max, True):
            return False
    return True


def _mediane_accordee(valeurs: list[CoteLue]) -> float | None:
    """L'échelle donnée par un groupe de cotes, sans celles qui s'écartent de la médiane."""
    if not valeurs:
        return None
    m = float(np.median([c.px_par_m for c in valeurs]))
    gardees = [c for c in valeurs if abs(c.px_par_m - m) / m <= ECART_MAX] or valeurs
    return sum(c.longueur_px for c in gardees) / sum(c.valeur for c in gardees)  # les longues pèsent plus


def _sens_contredit(valeurs: list[CoteLue]) -> bool:
    """Dans un sens d'une photo : plus de cotes franchement loin (CONTRADICTION) de la médiane que de cotes d'accord
    avec elle (même règle qu'Echelle.contredite, sens par sens)."""
    if len(valeurs) < 2:
        return False
    m = float(np.median([c.px_par_m for c in valeurs]))
    gardees = sum(abs(c.px_par_m - m) / m <= ECART_MAX for c in valeurs)
    loin = sum(abs(c.px_par_m - m) / m > CONTRADICTION for c in valeurs)
    return loin > gardees


def _cadre_entier(G: np.ndarray, forme: tuple[int, int], taille: tuple[int, int], k: float,
                  marge: float = 0.6) -> tuple[np.ndarray, tuple[int, int]]:
    """Le redressement recadre sur le logement, ce qui couperait les cotes dessinées autour.
    On garde ici toute la feuille redressée, sans dépasser `marge` × la taille du logement de chaque côté
    (près de l'horizon, une photo très penchée s'étirerait sans fin)."""
    h, w = forme[:2]
    coins = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], np.float64) @ G.T
    coins = coins[:, :2] / coins[:, 2:]
    W, H = taille[0] * k, taille[1] * k
    x0, y0 = max(coins[:, 0].min(), -marge * W), max(coins[:, 1].min(), -marge * H)
    x1, y1 = min(coins[:, 0].max(), (1 + marge) * W), min(coins[:, 1].max(), (1 + marge) * H)
    T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], np.float64)
    return T @ G, (int(np.ceil(x1 - x0)), int(np.ceil(y1 - y0)))


def _lire_par_morceaux(gris: np.ndarray) -> list:
    """Les textes d'une grande image, lus morceau par morceau (version 0.7).

    Le modèle de lecture réduit toute image à 2 000 pixels de côté au plus : sur une photo de téléphone, les chiffres
    des cotes (8 à 12 pixels de haut) deviennent alors trop petits pour être vus, même sur l'image agrandie.
    Lus par morceaux de MORCEAU pixels agrandis deux fois, ils gardent leur taille. Les morceaux se recouvrent
    (RECOUVREMENT pixels) pour ne couper aucun texte ; un texte lu deux fois n'est gardé qu'une fois."""
    H, W = gris.shape
    pas = MORCEAU - RECOUVREMENT
    textes = []
    for y in range(0, max(1, H - RECOUVREMENT), pas):
        for x in range(0, max(1, W - RECOUVREMENT), pas):
            for t in lire_textes(gris[y:y + MORCEAU, x:x + MORCEAU], 2):
                boite = t.boite + np.array([x, y], float)
                centre = boite.mean(axis=0)
                if any(u.texte == t.texte and np.linalg.norm(u.boite.mean(axis=0) - centre) < 10 for u in textes):
                    continue
                textes.append(TexteLu(t.texte, boite, t.confiance))
    return textes


def _nombres(textes: list) -> list[tuple[float, bool]]:
    cm = plan_en_cm(textes)  # les entiers ne sont des cotes que sur un plan coté en centimètres (lecture_cotes)
    return [(v, _vertical(t.boite)) for t in textes
            if (v := valeur_de_cote(t.texte)) is not None and (cm or FORME_COTE.match(t.texte.strip()))]


def _textes_remis_droit(textes: list[TexteLu], matrice: np.ndarray) -> list[TexteLu]:
    """Les textes (pixels du dessin) placés sur le dessin remis droit (matrice 3×3 dessin → dessin remis droit)."""
    sortie = []
    for t in textes:
        p = np.c_[t.boite, np.ones(len(t.boite))] @ matrice.T
        coins = p[:, :2] / p[:, 2:]
        # On garde une boîte droite (comme l'OCR) : le sens du texte (vertical ou pas) se lit sur sa forme.
        (x0, y0), (x1, y1) = coins.min(axis=0), coins.max(axis=0)
        sortie.append(TexteLu(t.texte, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float), t.confiance))
    return sortie


def _lire(gris: np.ndarray, photo: bool = False) -> tuple[Echelle, list[tuple[float, bool]], list]:
    """Comme lecture_cotes.lire_textes_et_echelle, mais sans insister quand la première lecture ne trouve
    aucun nombre en forme de cote : le plan n'a pas de cotes, les lectures suivantes (plus lentes) n'en
    trouveraient pas davantage. Rend aussi tous les nombres en forme de cote lus (valeur, vertical),
    même ceux dont le trait n'a pas été retrouvé, et les textes de la lecture gardée."""
    meilleure = None
    for debruiter, agrandir in ESSAIS_LECTURE:
        image = cv2.fastNlMeansDenoising(gris, None, 10, 7, 21) if debruiter else gris
        textes = lire_textes(image, agrandir)
        echelle = lire_echelle(gris, textes)
        score = (echelle.sure, echelle.px_par_m is not None, len(echelle.retenues))
        nombres = _nombres(textes)
        if meilleure is None or score > meilleure[0]:
            meilleure = (score, echelle, nombres, textes)
        if echelle.sure or not nombres:
            break
    papier = float(np.percentile(gris, 60))
    if not meilleure[1].sure and papier < PAPIER_GRIS:
        # Photocopie ou photo : papier gris, texte pâle et flou, que le modèle de lecture ne voit souvent
        # pas du tout (aucun nombre lu). On étire les gris (le papier redevient blanc, l'encre noire),
        # puis on relit, telle quelle et agrandie deux fois. Cette relecture n'est gardée que si elle est
        # sûre (deux cotes d'accord) : sur une image étirée, une cote seule est trop souvent mal lue
        # (essai sur 1 066 niveaux : une cote seule donnait une échelle fausse de 16 %).
        etiree = _etirer_gris(gris, papier)
        for agrandir in (1, 2):
            textes = lire_textes(etiree, agrandir)
            echelle = lire_echelle(etiree, textes)
            if echelle.sure:
                nombres = _nombres(textes)
                meilleure = ((True, True, len(echelle.retenues)), echelle, nombres, textes)
                break
    if photo and not meilleure[1].sure and max(gris.shape) > MORCEAU:
        # Photo de téléphone : chiffres trop petits pour une lecture d'un seul coup (voir _lire_par_morceaux).
        # Comme pour l'image étirée, cette relecture n'est gardée que si elle est sûre (deux cotes d'accord) :
        # sur un chiffre flou, une cote seule est souvent mal lue (« 8,79 » pour 8,30).
        for image in (gris, _etirer_gris(gris, float(np.percentile(gris, 60)))):
            textes = _lire_par_morceaux(image)
            echelle = lire_echelle(image, textes)
            if echelle.sure:
                nombres = _nombres(textes)
                meilleure = ((True, True, len(echelle.retenues)), echelle, nombres, textes)
                break
    return meilleure[1], meilleure[2], meilleure[3]


def _etirer_gris(gris: np.ndarray, papier: float) -> np.ndarray:
    """Le plan aux gris étirés : le papier (gris clair) devient blanc, l'encre la plus foncée devient noire."""
    encre = float(np.percentile(gris, 0.5))
    if papier - encre < 10:
        return gris
    return np.clip((gris.astype(np.float32) - encre) * (255 / (papier - encre)), 0, 255).astype(np.uint8)


def _vertical(boite: np.ndarray) -> bool:
    (x0, y0), (x1, y1) = boite.min(axis=0), boite.max(axis=0)
    return (y1 - y0) > (x1 - x0)


def interieur_du_logement(col: np.ndarray, px_par_m: float) -> tuple[float, float] | None:
    """Largeur et hauteur (pixels) de l'intérieur du logement colorié : du nu intérieur d'un mur
    extérieur à l'autre, ce que mesurent les cotes d'ensemble « intérieures »."""
    bati = bati_du_logement(col, px_par_m)
    if not bati.any():
        return None
    dehors = dehors_du_logement(bati)
    dedans = ~bati & ~dehors_pour_les_pieces(bati, dehors, col, px_par_m)
    ys, xs = np.nonzero(dedans)
    if not len(xs):
        return None
    return float(xs.max() + 1 - xs.min()), float(ys.max() + 1 - ys.min())


def lire_echelle_plan(dessin: np.ndarray, coloriage: np.ndarray, redressement: Redressement | None = None,
                      angle: float | None = None, textes: list[TexteLu] | None = None,
                      px_par_pt: float | None = None) -> EchelleLue:
    """L'échelle du coloriage, lue sur les cotes du dessin d'origine (gris ou couleurs, pleine taille).

    `redressement` : celui appliqué au coloriage (plan photographié de biais) ; l'échelle rendue
    est alors celle du coloriage redressé. Sinon le dessin est tourné de `angle` (estimé sur le
    coloriage s'il n'est pas donné), ce qui ne change pas l'échelle.
    `textes` : textes déjà connus (PDF vectoriel), en pixels du dessin ; l'OCR n'est alors pas lancé.
    `px_par_pt` : pixels du dessin par point PDF (moteur.lecture_pdf.rendre_page) ; avec `textes`, il permet de
    lire l'échelle écrite (« 1/50 ») du plan."""
    gris = dessin if dessin.ndim == 2 else cv2.cvtColor(dessin, cv2.COLOR_RGB2GRAY)
    r = coloriage.shape[1] / gris.shape[1]  # dessin → coloriage
    if redressement is not None:
        k = 1 / r  # on lit le dessin redressé à sa pleine taille, puis on revient à celle du coloriage
        G = np.diag([k, k, 1.0]) @ redressement.H @ np.diag([r, r, 1.0])
        G = _cadre_entier(G, gris.shape, redressement.taille, k)
        vu = cv2.warpPerspective(gris, G[0], G[1], flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=255)
        facteur = 1 / k
        col = redressement.appliquer(coloriage)
        vers_col = redressement.H @ np.diag([r, r, 1.0]) @ np.linalg.inv(G[0])  # dessin lu → coloriage redressé
        vers_vu = G[0]
    else:
        if angle is None:
            angle = estimer_rotation((coloriage >= MUR) & (coloriage <= PORTE_FENETRE))
        vu = gris
        vers_vu = np.eye(3)
        if abs(angle) >= 0.01:
            m, W, H = _rotation(gris.shape, angle)
            vu = cv2.warpAffine(gris, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=255)
            vers_vu = np.vstack([m, [0.0, 0.0, 1.0]])
        facteur = r
        col = redresser(coloriage, angle)
        vers_col = np.diag([r, r, 1.0])  # les deux sont tournés autour de leur centre
    ecrite, ecrite_detail = None, ""
    if textes is not None and px_par_pt and redressement is None:
        from moteur.lecture_pdf import echelle_ecrite

        e_dessin, ecrite_detail = echelle_ecrite(textes, px_par_pt)
        ecrite = e_dessin * facteur if e_dessin else None  # tourner le dessin ne change pas l'échelle
    if textes is not None:  # textes exacts du PDF : pas d'OCR
        textes = _textes_remis_droit(textes, vers_vu)
        echelle, nombres = lire_echelle(vu, textes), _nombres(textes)
    else:
        echelle, nombres, textes = _lire(vu, photo=redressement is not None)
    barre = lire_barre(vu, textes)
    cotes = echelle.retenues + echelle.ecartees
    contredite = echelle.contredite
    if redressement is not None:
        # Sur une photo, largeur et hauteur peuvent différer : chaque sens a sa propre médiane, et sa propre
        # contradiction (version 0.11 : les deux sens mélangés ne veulent rien dire quand leurs échelles diffèrent).
        horizontales, verticales = [c for c in cotes if not c.verticale], [c for c in cotes if c.verticale]
        largeur, hauteur = _mediane_accordee(horizontales), _mediane_accordee(verticales)
        contredite = _sens_contredit(horizontales) or _sens_contredit(verticales)
    else:
        largeur = hauteur = echelle.px_par_m
    if contredite:
        # Les cotes justes s'accordent presque toutes. Si la plupart sont écartées, l'accord des autres peut être un
        # hasard (fr-006 : deux cotes mesurées sur le même mur, 12 % d'erreur sans alerte). Version 0.11 : sur une photo
        # aussi (fr-010, dessin à la main photographié : deux cotes d'accord à 58,5 px/m, quatre autres à 61-64 et les
        # grandes cotes à 64,5 ; l'échelle « sûre » se trompait de 12 % sans alerte) ; un dessin dont un sens est
        # contredit n'est pas fiable dans l'autre non plus.
        largeur = hauteur = None
    largeur = largeur * facteur if largeur else None
    hauteur = hauteur * facteur if hauteur else None
    horiz = [v for v, vert in nombres if not vert and v >= COTE_MIN]
    verti = [v for v, vert in nombres if vert and v >= COTE_MIN]
    interieur = interieur_du_logement(col, largeur or hauteur or max(col.shape) / 15)
    surf = _echelle_des_surfaces(col, textes, vers_col, largeur or hauteur or max(col.shape) / 15)
    return EchelleLue(largeur, hauteur, echelle.sure, cotes, echelle.hauteur_sous_plafond,
                      max(horiz) if horiz else None, max(verti) if verti else None, interieur,
                      barre.px_par_m * facteur if barre else None, bool(barre and barre.sure),
                      barre.detail if barre else "", surf.px_par_m if surf else None, bool(surf and surf.sure),
                      surf.detail if surf else "", echelle_par_portes(col), coloriage_douteux(coloriage),
                      ecrite, ecrite_detail, retenues=echelle.retenues, contredite=contredite,
                      portes_fiables=portes_fiables(col), epaisseur=echelle_par_epaisseur(col))


def _echelle_des_surfaces(col: np.ndarray, textes: list, vers_col: np.ndarray, px_par_m: float):
    """L'échelle des surfaces écrites (voir moteur.surfaces_ecrites), placées sur le coloriage remis droit."""
    lues = surfaces_dans_textes(textes)
    if not lues and not any(FORME_LEGENDE.match(t.texte.strip()) for t in textes):
        return None
    pts = np.array([[x, y, 1.0] for _, x, y in lues]).reshape(-1, 3) @ vers_col.T
    surfaces = [SurfaceLue(v, float(p[0] / p[2]), float(p[1] / p[2])) for (v, _, _), p in zip(lues, pts)]
    bati = bati_du_logement(col, px_par_m)
    if not bati.any():
        return None
    dehors = dehors_du_logement(bati)
    dedans = ~bati & ~dehors_pour_les_pieces(bati, dehors, col, px_par_m)

    def projeter_col(x: float, y: float) -> tuple[float, float]:
        p = vers_col @ (x, y, 1.0)
        return float(p[0] / p[2]), float(p[1] / p[2])

    de_legende = surfaces_de_legende(textes, projeter_col, dedans)  # « Chambre 12,05 m² » écrit sous le plan (Carrez)
    r = echelle_par_surfaces(dedans, surfaces + de_legende)
    if r and de_legende:
        r.detail += f" ; {len(de_legende)} ramenée(s) depuis la légende"
    return r
