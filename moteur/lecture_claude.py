r"""La LECTURE DE CLAUDE : le format de la fiche que Claude rend après avoir regardé un plan (lecture-claude/0.1).

Pourquoi (décision NT du 08/11/2026, docs/projet/memoire/plan-lancement-lecture-claude.md) : au lancement, c'est Claude,
par l'API, qui lit les plans ; Atelya fait tout le reste. Cette fiche est le contrat entre les deux. Elle est stricte pour
qu'une réponse mal remplie soit refusée tout de suite, au lieu de construire un appartement faux.

Règles du contrat :
- Tout est en PIXELS de l'image envoyée (origine en haut à gauche, x vers la droite, y vers le bas). Claude ne calcule
  AUCUN mètre : c'est notre code qui calcule l'échelle, avec les garde-fous de moteur.echelle_plan.
- L'échelle à « deux clés » (accord NT du 08/11/2026) : Claude dit quelle cote mesure quoi (valeur écrite + les deux bouts
  du trait de cote) et propose SA propre échelle ; notre code refait le calcul depuis ces cotes ; les deux doivent
  s'accorder (moteur.lecture_claude_vers_logement, sous-étape 2).
- L'image envoyée doit être celle que Claude voit : l'API réduit toute image qui dépasse les limites du modèle et Claude
  rend alors ses coordonnées dans l'image réduite. On réduit donc l'image NOUS-MÊMES (taille_pour_claude) avant l'envoi,
  et la fiche dont l'image n'a pas cette taille est refusée.

Faits lus le 08/11/2026 dans la documentation officielle (platform.claude.com/docs/en/build-with-claude/vision et
vision-coordinates) : modèles « haute résolution » (Claude 4.7 et suivants, dont Opus 5.5, Sonnet 5.5, Fable 5.1) = côté
≤ 2 576 px et ≤ 4 784 jetons, un jeton par carré de 28 × 28 px ; l'API ajoute un bord vide en bas et à droite (jusqu'au
multiple de 28 suivant) sans déplacer l'origine ; les coordonnées de Claude sont APPROXIMATIVES (d'où le recalage des murs
sur le trait du dessin, sous-étape 2) ; un PDF envoyé tel quel est converti en image à une taille qu'on ne maîtrise pas :
on envoie donc toujours NOTRE image (moteur.lecture_pdf la rend déjà à 300 dpi). À l'envoi, marquer l'image
`"transformations": {"oversized_image": "error"}` : l'API refuse alors une image trop grande au lieu de la réduire en silence.

Version 0.1.0 (08/11/2026) : premier format.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from moteur.lecture_cotes import valeur_de_cote

VERSION_LECTURE_CLAUDE = "0.1.0"
SCHEMA = "lecture-claude/0.1"

# Limites des images de l'API (modèles « haute résolution », documentation lue le 08/11/2026).
COTE_MAX_PX = 2576
JETONS_MAX = 4784
CARRE_PX = 28

# Les types de pièces : ceux du coloriage (moteur.coloriage.PIECES), les seuls que la suite sait construire. Le type n'est
# qu'une proposition, modifiable à l'écran de vérification (règle 19 de NT : il n'impose pas les meubles).
TYPES_PIECES = ("sejour", "cuisine", "chambre", "salle_d_eau", "wc", "entree", "degagement", "placard", "buanderie",
                "bureau", "escalier")
TYPES_OUVERTURES = ("porte", "porte_fenetre", "fenetre")

HORS_IMAGE_TOLERE = 0.02  # part de la taille de l'image : un point un peu dehors est ramené au bord, au-delà la fiche est refusée
ECART_VALEUR = 0.01  # 1 % : écart toléré entre le nombre écrit (texte) et la valeur que Claude en a tirée
LONGUEUR_MIN_PX = 2.0  # un mur ou un trait de cote plus court n'est pas un trait

Point = tuple[float, float]
Segment = tuple[float, float, float, float]  # x0, y0, x1, y1
Cadre = tuple[float, float, float, float]  # x0, y0, x1, y1 (coin haut gauche, coin bas droit)


# ---------------------------------------------------------------- la taille de l'image envoyée

def jetons_image(largeur: int, hauteur: int) -> int:
    """Ce que coûte une image en jetons : un par carré de 28 × 28 pixels (documentation de l'API)."""
    return math.ceil(largeur / CARRE_PX) * math.ceil(hauteur / CARRE_PX)


def taille_pour_claude(largeur: int, hauteur: int, cote_max: int = COTE_MAX_PX, jetons_max: int = JETONS_MAX) -> tuple[int, int]:
    """La taille à laquelle l'API réduirait l'image (largeur, hauteur) ; inchangée si elle tient déjà dans les limites.

    Recopie de l'implémentation de référence de la documentation (vision-coordinates, « Resize your image before uploading »),
    arrondi « au pair » de Python compris (le même que l'API pour les demi-pixels)."""
    def tient(w: int, h: int) -> bool:
        return (math.ceil(w / CARRE_PX) * CARRE_PX <= cote_max and math.ceil(h / CARRE_PX) * CARRE_PX <= cote_max
                and jetons_image(w, h) <= jetons_max)

    if tient(largeur, hauteur):
        return largeur, hauteur
    if hauteur > largeur:
        h, w = taille_pour_claude(hauteur, largeur, cote_max, jetons_max)
        return w, h
    rapport = largeur / hauteur
    bas, haut = 1, largeur  # bas tient toujours, haut jamais
    while bas + 1 < haut:
        milieu = (bas + haut) // 2
        if tient(milieu, max(round(milieu / rapport), 1)):
            bas = milieu
        else:
            haut = milieu
    return bas, max(round(bas / rapport), 1)


def image_pour_claude(image):
    """L'image (tableau numpy) réduite à la taille que Claude verra, et le facteur (pixels envoyés / pixels d'origine).

    Les coordonnées de la fiche se ramènent à l'image d'origine en les divisant par ce facteur."""
    import cv2  # importé ici : le format seul n'a pas besoin d'OpenCV

    h, w = image.shape[:2]
    l2, h2 = taille_pour_claude(w, h)
    if (l2, h2) == (w, h):
        return image, 1.0
    return cv2.resize(image, (l2, h2), interpolation=cv2.INTER_AREA), l2 / w


# ---------------------------------------------------------------- le format

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImageEnvoyee(_Strict):
    nom: str = Field(min_length=1, description="Nom du fichier de l'image envoyée")
    largeur: int = Field(gt=0)
    hauteur: int = Field(gt=0)


class MurLu(_Strict):
    id: str = Field(min_length=1)
    axe: Segment = Field(description="La ligne au MILIEU du mur, d'un bout à l'autre : x0, y0, x1, y1")
    epaisseur_px: float = Field(gt=0, description="L'épaisseur du mur dessiné, en pixels")


class OuvertureLue(_Strict):
    id: str = Field(min_length=1)
    type: Literal[TYPES_OUVERTURES]
    bords: Segment = Field(description="Le trou dans le mur, d'un bord à l'autre, sur l'axe du mur : x0, y0, x1, y1")
    mur: str | None = Field(default=None, description="L'id du mur qui la porte, si Claude le sait")


class PieceLue(_Strict):
    id: str = Field(min_length=1)
    nom: str | None = Field(default=None, description="Le nom ÉCRIT sur le plan (« Chambre 2 »), sinon rien")
    type: Literal[TYPES_PIECES]
    point: Point = Field(description="Un point bien à l'intérieur de la pièce (pas sur un mur)")
    contour: list[Point] | None = Field(default=None, description="Le contour intérieur, si Claude le donne")

    @field_validator("contour")
    @classmethod
    def _au_moins_trois(cls, v):
        if v is not None and len(v) < 3:
            raise ValueError("un contour a au moins 3 points")
        return v


class CoteLueClaude(_Strict):
    texte: str = Field(min_length=1, description="Le texte EXACT écrit sur le plan : « 3,45 », « 345 », « 3.45 »")
    valeur_m: float = Field(gt=0, description="La longueur annoncée, en mètres (« 345 » centimètres → 3,45)")
    cadre: Cadre = Field(description="Le cadre du texte sur l'image")
    bouts: tuple[Point, Point] = Field(description="Les deux extrémités de ce que la cote mesure (ses deux marques)")
    mur: str | None = Field(default=None, description="L'id du mur mesuré, si la cote mesure un seul mur")


class SurfaceLue(_Strict):
    texte: str = Field(min_length=1, description="Le texte EXACT : « 12,5 m² », « 12.50 »")
    valeur_m2: float = Field(gt=0)
    cadre: Cadre
    piece: str | None = Field(default=None, description="L'id de la pièce dont c'est la surface")


class TexteLuClaude(_Strict):
    texte: str = Field(min_length=1)
    cadre: Cadre
    genre: Literal["echelle_ecrite", "hauteur_sous_plafond", "epaisseur", "autre"] = Field(
        description="« 1/50 » = echelle_ecrite ; « HSP 2,50 » = hauteur_sous_plafond ; « Murs : 20 cm » = epaisseur")


class EchelleProposee(_Strict):
    px_par_m: float | None = Field(default=None, gt=0, description="L'échelle que Claude propose, en pixels par mètre")
    source: Literal["cotes", "surfaces", "barre", "echelle_ecrite", "portes", "aucune"]
    explication: str = ""


class NiveauNonLu(_Strict):
    cadre: Cadre = Field(description="Où se trouve sur l'image un autre niveau ou logement, non lu")
    nom: str | None = None


class DouteClaude(_Strict):
    raison: str = Field(min_length=1, description="Ce qui est incertain, en une phrase")
    gravite: Literal["fort", "faible"] = "faible"
    cadre: Cadre | None = Field(default=None, description="Où regarder sur l'image")
    element: str | None = Field(default=None, description="L'id du mur, de l'ouverture ou de la pièce concerné")


class LectureClaude(_Strict):
    schema_: Literal["lecture-claude/0.1"] = Field(alias="schema")
    image: ImageEnvoyee
    murs: list[MurLu]
    ouvertures: list[OuvertureLue] = []
    pieces: list[PieceLue]
    cotes: list[CoteLueClaude] = []
    surfaces: list[SurfaceLue] = []
    textes: list[TexteLuClaude] = []
    echelle_proposee: EchelleProposee
    niveau_lu: str | None = Field(default=None, description="Si l'image dessine plusieurs niveaux : lequel est lu")
    autres_niveaux: list[NiveauNonLu] = []
    doutes: list[DouteClaude] = []

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _ids_uniques_et_references(self):
        for nom, liste in (("mur", self.murs), ("ouverture", self.ouvertures), ("pièce", self.pieces)):
            vus = set()
            for e in liste:
                if e.id in vus:
                    raise ValueError(f"{nom} {e.id!r} en double")
                vus.add(e.id)
        tous = {e.id for e in [*self.murs, *self.ouvertures, *self.pieces]}
        if len(tous) != len(self.murs) + len(self.ouvertures) + len(self.pieces):
            raise ValueError("un même id sert à deux éléments de genres différents")
        murs = {m.id for m in self.murs}
        pieces = {p.id for p in self.pieces}
        for o in self.ouvertures:
            if o.mur is not None and o.mur not in murs:
                raise ValueError(f"ouverture {o.id} : mur {o.mur!r} inconnu")
        for c in self.cotes:
            if c.mur is not None and c.mur not in murs:
                raise ValueError(f"cote {c.texte!r} : mur {c.mur!r} inconnu")
        for s in self.surfaces:
            if s.piece is not None and s.piece not in pieces:
                raise ValueError(f"surface {s.texte!r} : pièce {s.piece!r} inconnue")
        for d in self.doutes:
            if d.element is not None and d.element not in tous:
                raise ValueError(f"doute {d.raison!r} : élément {d.element!r} inconnu")
        return self


# ---------------------------------------------------------------- les contrôles

@dataclass
class Probleme:
    """Un défaut de la fiche. « refus » : la fiche n'est pas utilisable (rien n'est construit). « doute » : la fiche est
    utilisable, mais l'endroit doit être montré en tête de l'écran de vérification."""
    gravite: Literal["refus", "doute"]
    code: str
    raison: str
    element: str | None = None
    cadre: Cadre | None = None


@dataclass
class FicheControlee:
    lecture: LectureClaude | None  # None si la fiche est refusée
    problemes: list[Probleme]

    @property
    def refusee(self) -> bool:
        return self.lecture is None or any(p.gravite == "refus" for p in self.problemes)


_NOMBRE = re.compile(r"\d+(?:[,.]\d+)?")


def _surface_du_texte(texte: str) -> float | None:
    """Le nombre d'un texte de surface : « 12,5 m² » → 12,5 ; « 3,20 x 4,10 » → 13,12 ; plusieurs autres nombres → None."""
    nombres = [float(n.replace(",", ".")) for n in _NOMBRE.findall(texte.replace("m²", "").replace("m2", ""))]
    if len(nombres) == 1:
        return nombres[0]
    if len(nombres) == 2 and re.search(r"\d\s*[x×*]\s*\d", texte):
        return nombres[0] * nombres[1]
    return None


def _points(lecture: LectureClaude):
    """Tous les points de la fiche, avec ce qu'ils désignent (pour le contrôle « dans l'image »)."""
    for m in lecture.murs:
        yield m.id, m.axe[:2]
        yield m.id, m.axe[2:]
    for o in lecture.ouvertures:
        yield o.id, o.bords[:2]
        yield o.id, o.bords[2:]
    for p in lecture.pieces:
        yield p.id, p.point
        for q in p.contour or []:
            yield p.id, q
    for c in lecture.cotes:
        yield f"cote {c.texte}", c.bouts[0]
        yield f"cote {c.texte}", c.bouts[1]
        yield f"cote {c.texte}", c.cadre[:2]
        yield f"cote {c.texte}", c.cadre[2:]
    for s in lecture.surfaces:
        yield f"surface {s.texte}", s.cadre[:2]
        yield f"surface {s.texte}", s.cadre[2:]


def _dans_le_polygone(x: float, y: float, poly: list[Point]) -> bool:
    dedans = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def _ramener(v: float, maxi: int) -> float:
    return min(max(v, 0.0), float(maxi))


def _ramener_dans_l_image(lecture: LectureClaude) -> LectureClaude:
    """Les points un peu hors de l'image ramenés sur son bord (la documentation de l'API le recommande)."""
    W, H = lecture.image.largeur, lecture.image.hauteur
    d = lecture.model_dump(by_alias=True)

    def seg(s):
        return [_ramener(s[0], W), _ramener(s[1], H), _ramener(s[2], W), _ramener(s[3], H)]

    for m in d["murs"]:
        m["axe"] = seg(m["axe"])
    for o in d["ouvertures"]:
        o["bords"] = seg(o["bords"])
    for p in d["pieces"]:
        p["point"] = [_ramener(p["point"][0], W), _ramener(p["point"][1], H)]
        if p["contour"]:
            p["contour"] = [[_ramener(x, W), _ramener(y, H)] for x, y in p["contour"]]
    for c in d["cotes"]:
        c["cadre"] = seg(c["cadre"])
        c["bouts"] = [[_ramener(x, W), _ramener(y, H)] for x, y in c["bouts"]]
    for s in d["surfaces"]:
        s["cadre"] = seg(s["cadre"])
    for t in d["textes"]:
        t["cadre"] = seg(t["cadre"])
    for n in d["autres_niveaux"]:
        n["cadre"] = seg(n["cadre"])
    for dt in d["doutes"]:
        if dt["cadre"]:
            dt["cadre"] = seg(dt["cadre"])
    return LectureClaude.model_validate(d)


def controler_fiche(donnees: dict, image_envoyee: tuple[int, int] | None = None) -> FicheControlee:
    """Lit et contrôle la fiche rendue par Claude.

    `image_envoyee` : (largeur, hauteur) de l'image réellement envoyée ; la fiche doit annoncer la même.
    Refus : forme invalide (champ manquant, type inconnu, id en double ou inconnu…), image d'une autre taille ou que l'API
    aurait réduite, point loin hors de l'image, mur ou trait de cote de longueur nulle, aucune pièce ni aucun mur.
    Doutes : nombre écrit ≠ valeur que Claude en a tirée (cote ou surface), point d'une pièce hors de son contour."""
    try:
        lecture = LectureClaude.model_validate(donnees)
    except ValidationError as e:
        premiers = "; ".join(f"{'.'.join(str(x) for x in err['loc'])} : {err['msg']}" for err in e.errors()[:5])
        return FicheControlee(None, [Probleme("refus", "forme", f"fiche mal remplie ({len(e.errors())} erreur(s)) : {premiers}")])

    problemes: list[Probleme] = []
    W, H = lecture.image.largeur, lecture.image.hauteur
    if image_envoyee is not None and tuple(image_envoyee) != (W, H):
        problemes.append(Probleme("refus", "image_taille",
                                  f"la fiche annonce une image de {W} × {H} px, l'image envoyée fait {image_envoyee[0]} × {image_envoyee[1]} px"))
    if taille_pour_claude(W, H) != (W, H):
        problemes.append(Probleme("refus", "image_reduite",
                                  f"une image de {W} × {H} px aurait été réduite par l'API à {taille_pour_claude(W, H)} : "
                                  "les coordonnées ne correspondraient pas à notre image"))
    if not lecture.murs or not lecture.pieces:
        problemes.append(Probleme("refus", "vide", "la fiche ne contient aucun mur ou aucune pièce"))

    marge_x, marge_y = HORS_IMAGE_TOLERE * W, HORS_IMAGE_TOLERE * H
    loin = sorted({nom for nom, (x, y) in _points(lecture)
                   if x < -marge_x or y < -marge_y or x > W + marge_x or y > H + marge_y})
    if loin:
        problemes.append(Probleme("refus", "hors_image", f"points loin hors de l'image : {', '.join(loin[:8])}"))

    for m in lecture.murs:
        if math.dist(m.axe[:2], m.axe[2:]) < LONGUEUR_MIN_PX:
            problemes.append(Probleme("refus", "mur_nul", f"mur {m.id} de longueur nulle", element=m.id))
    for o in lecture.ouvertures:
        if math.dist(o.bords[:2], o.bords[2:]) < LONGUEUR_MIN_PX:
            problemes.append(Probleme("refus", "ouverture_nulle", f"ouverture {o.id} de largeur nulle", element=o.id))

    for c in lecture.cotes:
        if math.dist(*c.bouts) < LONGUEUR_MIN_PX:
            problemes.append(Probleme("refus", "cote_nulle", f"cote {c.texte!r} : trait de longueur nulle", cadre=c.cadre))
        ecrite = valeur_de_cote(c.texte)
        if ecrite is not None and abs(ecrite / c.valeur_m - 1) > ECART_VALEUR:
            problemes.append(Probleme("doute", "cote_mal_recopiee",
                                      f"cote écrite « {c.texte} » ({ecrite:g} m) mais comptée {c.valeur_m:g} m par la lecture",
                                      element=c.mur, cadre=c.cadre))
    for s in lecture.surfaces:
        ecrite = _surface_du_texte(s.texte)
        if ecrite is not None and abs(ecrite / s.valeur_m2 - 1) > ECART_VALEUR:
            problemes.append(Probleme("doute", "surface_mal_recopiee",
                                      f"surface écrite « {s.texte} » ({ecrite:g} m²) mais comptée {s.valeur_m2:g} m² par la lecture",
                                      element=s.piece, cadre=s.cadre))
    for p in lecture.pieces:
        if p.contour and not _dans_le_polygone(*p.point, p.contour):
            problemes.append(Probleme("doute", "point_hors_contour", f"pièce {p.id} : son point n'est pas dans son contour",
                                      element=p.id))

    if any(pb.gravite == "refus" for pb in problemes):
        return FicheControlee(None, problemes)
    return FicheControlee(_ramener_dans_l_image(lecture), problemes)


# ---------------------------------------------------------------- la consigne donnée à Claude

def consigne() -> str:
    """Le texte qui dira à Claude quoi remplir (envoyé plus tard par l'API, avec l'image). Rien n'est envoyé ici."""
    return f"""Tu lis un plan de logement (l'image jointe) et tu remplis une fiche JSON au format {SCHEMA}.

Règles :
- Toutes les positions sont en PIXELS de l'image jointe : origine (0, 0) en haut à gauche, x vers la droite, y vers le bas.
  Ne convertis RIEN en mètres : l'échelle est calculée ailleurs, à partir de ce que tu lis.
- Murs : pour chaque mur droit, son AXE (la ligne au milieu du trait du mur) d'un bout à l'autre, et son épaisseur en
  pixels. Un mur courbe est découpé en segments courts. Les murs se rejoignent dans les angles.
- Ouvertures : type parmi {", ".join(TYPES_OUVERTURES)} ; leurs deux bords sur l'axe du mur ; l'id du mur qui les porte.
- Pièces : un point bien à l'intérieur, le nom ÉCRIT sur le plan s'il y en a un, et un type parmi
  {", ".join(TYPES_PIECES)} (une salle de bains est une salle_d_eau ; une pièce inconnue prend le type le plus proche).
- Cotes : pour chaque cote lisible, le texte exact, la longueur annoncée en mètres (« 345 » en centimètres = 3,45), le cadre
  du texte, et les DEUX EXTRÉMITÉS de ce qu'elle mesure (ses deux marques), plus l'id du mur mesuré s'il n'y en a qu'un.
- Surfaces écrites (« 12,5 m² ») : texte exact, valeur, cadre, et l'id de la pièce concernée.
- Autres textes utiles : l'échelle écrite (« 1/50 »), la hauteur sous plafond, l'épaisseur des murs.
- Échelle proposée : ton estimation en pixels par mètre et d'où elle vient (elle sera comparée à notre calcul).
- Si l'image dessine plusieurs niveaux ou logements : n'en lis qu'un, dis lequel (niveau_lu), et donne le cadre des autres.
- Doutes : tout ce dont tu n'es pas sûr, en une phrase, avec l'endroit (cadre) ou l'id de l'élément. Mieux vaut un doute de
  trop qu'une erreur silencieuse.
- Ne recopie aucun nom de personne ni aucune adresse.

Réponds uniquement par la fiche JSON."""
