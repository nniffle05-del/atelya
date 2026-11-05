"""La lecture complète d'un plan : du fichier déposé (image ou PDF) au logement et à ses doutes.

Pourquoi : les briques existaient (coloriage, redressement, échelle, traducteur, doutes, aiguillage, PDF), mais
seul le banc de notation les enchaînait, et il s'aide de la vérité des plans fabriqués. Ici, la même recette, sans
aucune vérité : c'est le parcours d'un vrai plan de client, et ce qui alimente l'écran de vérification.

Ce module ne dépend pas de PyTorch (le Mac n'en a pas) : colorier est fourni de l'extérieur, sous forme de
« colorieurs » (nom du modèle → fonction image grise réduite → coloriage, carte des doutes). Sur le PC, c'est
outils/atelya/lire_plan.py qui les construit à partir des modèles entraînés.

Différences voulues avec le banc :
- échelle non lue : le banc note avec l'échelle exacte, inconnue ici. On prend la moins mauvaise échelle de secours
  (voir _echelle_de_secours : surfaces écrites, cotes non confirmées, portes si elles ont l'air de vraies portes,
  épaisseur des murs, sinon un logement de PLAN_SECOURS_M mètres). Le logement n'est alors qu'un brouillon à
  recaler à l'écran : `echelle["etat"]` vaut « a_verifier » et un doute fort l'annonce ;
- noms de pièces lus par défaut (le banc ne les lit que sur demande) ;
- photo de téléphone : on la remet à l'endroit (orientation EXIF), comme le navigateur l'affichera à l'écran.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageOps

from moteur.aiguillage import SEUIL_LIBRES_M, choisir, longueur_libre
from moteur.coloriage import lire_coloriage
from moteur.doutes import examiner
from moteur.echelle_plan import (LOGEMENT_MAX, LOGEMENT_MIN, EchelleLue, coloriage_douteux, decider, lire_echelle_plan,
                                 sans_taches_au_bord)
from moteur.lecture_cotes import TexteLu
from moteur.noms_pieces import lire_textes, noms_depuis_textes
from moteur.redressement import (Redressement, corriger_proportions, estimer_redressement, photo_entiere,
                                 rapport_par_optique, rapport_plausible)

VERSION_LECTURE_COMPLETE = "0.2.0"
COTE_ATELYA = 768  # grand côté de l'image donnée à Atelya (comme à l'entraînement)
PLAN_SECOURS_M = 15.0  # échelle de secours, quand rien ne la donne : un logement d'environ 15 m (même repli que l'échelle)
FORMATS_IMAGE = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

Colorieur = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray | None]]


class FichierNonLisible(Exception):
    """Le fichier déposé n'est ni une image ni un PDF lisible."""


@dataclass
class PlanSource:
    """Une page de plan prête à lire : l'image pleine taille (RGB) et, pour un PDF vectoriel, ses textes exacts."""
    nom: str
    image: np.ndarray  # RGB, uint8 : exactement l'image que l'écran affichera
    textes: list[TexteLu] | None = None  # textes exacts du PDF, sinon None : OCR
    px_par_pt: float | None = None  # pixels de l'image par point PDF
    a_plat: bool = False  # page vectorielle : jamais de redressement de perspective
    page: int | None = None
    nature: str = "image"  # image, ou la nature du tri PDF (vectorielle, piegee, scannee)
    doutes_tri: list[dict] = field(default_factory=list)


@dataclass
class Lecture:
    """Ce qu'a donné un modèle sur ce plan."""
    modele: str
    logement: dict | None
    details: dict | None
    examen: dict
    echelle: dict
    redressement: Redressement | None = None
    coloriage: np.ndarray | None = None
    carte: np.ndarray | None = None
    infos: dict = field(default_factory=dict)
    erreur: str | None = None


@dataclass
class PlanLu:
    """Le résultat complet d'une page : la lecture gardée, et pourquoi."""
    source: PlanSource
    gardee: Lecture
    lectures: dict[str, Lecture]
    aiguillage: str

    @property
    def decision(self) -> str:
        return self.gardee.examen["decision"]


def _doute_tri(raison: str) -> dict:
    return {"code": "page_pdf", "element": None, "raison": raison, "gravite": "fort"}


def plans_du_fichier(chemin: str | Path) -> list[PlanSource]:
    """Les pages à lire d'un fichier déposé : une pour une image, une ou plusieurs pour un PDF.
    Lève FichierNonLisible si ce n'est ni l'un ni l'autre, ou si le PDF n'a aucune page utile."""
    chemin = Path(chemin)
    if not chemin.is_file():
        raise FichierNonLisible(f"fichier introuvable : {chemin.name}")
    suffixe = chemin.suffix.lower()
    if suffixe == ".pdf":
        from moteur.lecture_pdf import PdfIllisible, choisir_pages, lire_page, trier_pdf

        try:
            tri = trier_pdf(chemin)
            pages, doute = choisir_pages(tri)
            if not pages:
                raise FichierNonLisible(f"aucune page utile dans {chemin.name}")
            sources = []
            for n in pages:
                p = lire_page(chemin, n, tri[n - 1])
                doutes = [_doute_tri(f"page {n} : aucune page ne ressemble clairement à un plan ({p.raison})")] if doute else []
                sources.append(PlanSource(f"{chemin.stem}-page{n}", p.image[:, :, ::-1].copy(), p.textes, p.px_par_pt,
                                          p.a_plat, n, p.nature, doutes))
            return sources
        except PdfIllisible as e:
            raise FichierNonLisible(str(e)) from e
    if suffixe not in FORMATS_IMAGE:
        raise FichierNonLisible(f"format non pris en charge : {chemin.name}")
    try:
        with Image.open(chemin) as img:
            rgb = ImageOps.exif_transpose(img).convert("RGB")
    except OSError as e:
        raise FichierNonLisible(f"image illisible : {chemin.name} ({e})") from e
    return [PlanSource(chemin.stem, np.asarray(rgb).copy())]


def reduire_pour_atelya(image: np.ndarray, cote: int = COTE_ATELYA) -> np.ndarray:
    """L'image grise réduite qu'Atelya colorie : même calcul qu'à l'entraînement et que colorier_angles.reduire."""
    img = Image.fromarray(image).convert("L")
    r = cote / max(img.size)
    img = img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BILINEAR)
    return np.array(img, np.uint8)


def noms_du_plan(source: PlanSource) -> list:
    """Les noms de pièces écrits sur le plan (positions en pixels de l'image pleine taille)."""
    if source.textes is not None:
        from moteur.lecture_pdf import pour_les_noms

        return noms_depuis_textes(pour_les_noms(source.textes))
    return noms_depuis_textes(lire_textes(source.image))


def _taille_vraisemblable(px_par_m: float | None, interieur_px: tuple[float, float] | None) -> bool:
    """Avec cette échelle, le logement colorié mesure-t-il entre LOGEMENT_MIN et LOGEMENT_MAX mètres de côté ?"""
    if not px_par_m:
        return False
    for cote in interieur_px or ():
        if cote and not LOGEMENT_MIN <= cote / px_par_m <= LOGEMENT_MAX:
            return False
    return True


def _echelle_de_secours(e: EchelleLue, forme: tuple[int, int]) -> tuple[float, str]:
    """L'échelle du BROUILLON quand aucune n'a pu être retenue : la moins mauvaise information disponible, dans l'ordre.

    Jamais utilisée pour construire ; elle sert à montrer un plan presque à la bonne taille à la personne qui vérifie,
    dont le premier point est justement de confirmer une mesure. Mesuré sur 11 vrais plans à l'échelle connue : surfaces
    écrites même peu sûres ±6 % (médiane), cotes non confirmées ±9 %, portes ±36 % (jusqu'à 72 % : fragments coloriés
    « porte » sur les styles jamais vus), épaisseur des murs ±19 % (jamais pire que 50 %). Avant la version 0.11, seules
    les portes servaient."""
    il_ih = e.interieur_px
    if _taille_vraisemblable(e.surfaces, il_ih):
        return float(e.surfaces), "approchée par les surfaces écrites (non confirmées)"
    cotes = [v for v in (e.largeur, e.hauteur) if v]
    if cotes and _taille_vraisemblable(sum(cotes) / len(cotes), il_ih):
        return float(sum(cotes) / len(cotes)), "approchée par les cotes (non confirmées)"
    if e.portes_fiables and _taille_vraisemblable(e.approchee, il_ih):
        return float(e.approchee), "approchée par les portes"
    if _taille_vraisemblable(e.epaisseur, il_ih):
        return float(e.epaisseur), "approchée par l'épaisseur des murs"
    if e.approchee:
        return float(e.approchee), "approchée par les portes (peu sûres)"
    return max(forme) / PLAN_SECOURS_M, "aucune mesure sur le plan (taille supposée)"


def lire_avec_coloriage(source: PlanSource, col: np.ndarray, carte: np.ndarray | None, modele: str = "atelya",
                        noms: list | None = None, projet_id: str | None = None) -> Lecture:
    """La lecture d'un plan à partir du coloriage d'un modèle : même enchaînement que le banc (--echelle lue
    --proportions optique --doutes), sans la vérité. `noms` : voir noms_du_plan (None : on ne s'en sert pas)."""
    projet_id = projet_id or source.nom
    infos: dict = {}
    if coloriage_douteux(col):  # taches au bord de l'image, séparées du logement (table, bord de feuille)
        propre = sans_taches_au_bord(col)
        if not coloriage_douteux(propre):
            col, infos["coloriage_nettoye"] = propre, True
    R = estimer_redressement(col) if not source.a_plat else None
    if R is not None and not R.de_biais:
        R = None  # page vue de face : la lecture habituelle (avec sa rotation) suffit
    optique = R is not None
    h_img, l_img = source.image.shape[:2]
    if optique and not photo_entiere(l_img, h_img):  # photo recadrée : l'optique ne sait pas
        optique, infos["photo_recadree"] = False, True
    if optique:
        rapport = rapport_par_optique(R, col.shape)
        infos["rapport_optique"] = round(rapport, 5)
        if rapport_plausible(rapport):
            R = corriger_proportions(R, rapport)
        else:
            optique, infos["optique_douteuse"] = False, True

    gris = np.asarray(Image.fromarray(source.image).convert("L"))
    e = lire_echelle_plan(gris, col, R, textes=source.textes, px_par_pt=source.px_par_pt)
    douteux = coloriage_douteux(col)
    if douteux:
        infos["coloriage_douteux"] = True
    lx, ly, origine = decider(e.largeur, e.hauteur, e.sure, e.cote_max_largeur, e.cote_max_hauteur, e.interieur_px,
                              R is not None, e.barre if e.barre_sure else None, e.surfaces if e.surfaces_sure else None,
                              optique, e.approchee, douteux, e.surfaces, ecrite=e.ecrite)
    if R is None:
        lx = ly = lx or ly
    autres = list(source.doutes_tri)
    # Le détail de ce qui a été lu, pour comprendre une décision après coup (diagnostic), jamais pour construire.
    detail = {"cotes_retenues": [[c.valeur, round(c.px_par_m, 2)] for c in e.retenues],
              "cotes": [[c.valeur, round(c.px_par_m, 2), "V" if c.verticale else "H"] for c in e.cotes],
              "sure": e.sure, "contredite": e.contredite, "barre": e.barre_detail or None, "surfaces": e.surfaces_detail or None,
              "surfaces_px_par_m": e.surfaces, "ecrite": e.ecrite_detail or None, "portes_px_par_m": e.approchee,
              "portes_fiables": e.portes_fiables, "epaisseur_px_par_m": e.epaisseur,
              "interieur_px": list(e.interieur_px) if e.interieur_px else None, "coloriage_douteux": douteux,
              "largeur_px_par_m": e.largeur, "hauteur_px_par_m": e.hauteur, "cote_max": [e.cote_max_largeur, e.cote_max_hauteur],
              "de_biais": R is not None, "optique": optique}
    if lx or ly:
        vx, vy = lx or ly, ly or lx
        echelle = {"etat": "lue", "source": origine, "px_par_m_largeur": vx, "px_par_m_hauteur": vy, "cotes": len(e.cotes),
                   "detail": detail}
        if R is not None and lx and ly:  # lue dans les deux sens : elle a le dernier mot sur les proportions
            R = corriger_proportions(R, vx / vy)
        s = vx
    else:
        s, comment = _echelle_de_secours(e, col.shape)
        echelle = {"etat": "a_verifier", "source": origine, "provisoire": s, "raison": f"échelle non lue : {comment}",
                   "cotes": len(e.cotes), "detail": detail}
        autres.append({"code": "echelle", "element": None, "gravite": "fort",
                       "raison": f"Échelle non lue : les mesures sont provisoires ({comment}). Corrige une cote pour tout recaler."})
    if douteux:
        autres.append({"code": "coloriage_douteux", "element": None, "gravite": "faible",
                       "raison": "coloriage collé au bord de l'image"})

    r = col.shape[1] / l_img  # image pleine taille → coloriage
    noms_col = None
    if noms is not None:
        noms_col = [replace(n, x=(n.x + 0.5) * r - 0.5, y=(n.y + 0.5) * r - 0.5) for n in noms]
    try:
        logement, details = lire_coloriage(col, s, projet_id=projet_id, hauteur_sous_plafond=e.hauteur_sous_plafond,
                                           redressement=R, noms=noms_col)
    except Exception as err:  # noqa: BLE001 — un plan illisible est un résultat (refusé), pas un plantage
        erreur = f"{type(err).__name__}: {str(err)[:200]}"
        return Lecture(modele, None, None, examiner(None, erreur=erreur), echelle, R, col, carte, infos, erreur)
    infos["murs_libres_m"] = round(longueur_libre(logement), 2)
    examen = examiner(logement, details, carte=carte, redressement=R, autres=autres)
    return Lecture(modele, logement, details, examen, echelle, R, col, carte, infos)


def lire_plan(source: PlanSource, colorieurs: dict[str, Colorieur], *, avec_noms: bool = True) -> PlanLu:
    """Lit une page avec chaque modèle puis garde la bonne lecture.
    Colorieurs « e5 » et « e7 » : aiguillage A3. Un seul colorieur : sa lecture (essais, comparaisons)."""
    if not colorieurs:
        raise ValueError("aucun colorieur")
    petite = reduire_pour_atelya(source.image)
    noms = noms_du_plan(source) if avec_noms else None
    lectures = {}
    for nom, colorier in colorieurs.items():
        col, carte = colorier(petite)
        lectures[nom] = lire_avec_coloriage(source, col, carte, nom, noms)
    if set(lectures) == {"e5", "e7"}:
        gardee, pourquoi = _aiguiller(lectures["e5"], lectures["e7"])
    else:
        gardee, pourquoi = next(iter(lectures.values())), "un seul modèle demandé"
    return PlanLu(source, gardee, lectures, pourquoi)


def _aiguiller(e5: Lecture, e7: Lecture) -> tuple[Lecture, str]:
    """La règle de moteur.aiguillage ; si un modèle n'a rien pu lire, on garde l'autre."""
    if e5.logement is None and e7.logement is None:
        return e5, "aucun modèle n'a pu lire ce plan"
    if e7.logement is None:
        return e5, "l'essai 7b n'a rien lu"
    if e5.logement is None:
        return e7, "l'essai 5 n'a rien lu"
    nom, _ = choisir(e5.logement, e7.logement)
    libres = longueur_libre(e7.logement)
    signe = "≥" if nom == "e7" else "<"
    return (e7 if nom == "e7" else e5), f"{libres:.1f} m de murs en biais/arrondis lus par l'essai 7b ({signe} {SEUIL_LIBRES_M} m)"
