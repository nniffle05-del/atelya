"""Fabriquer un exemple complet, écrire le jeu de données, le manifeste et la répartition.

Organisation d'un jeu (`dossier/`) :

    manifest.json              ← une ligne par exemple : identifiant, graine, famille, surface, fichiers, verdict…
    reglages.json              ← les réglages utilisés (pour refaire pareil)
    journal.log                ← ce qui s'est passé
    exemples/
      000001/                  ← un dossier par graine
        geometrie.json         ← la vérité terrain vectorielle (mètres)
        logement_niveau0.json  ← le format logement/0.1 de chaque niveau (lisible par tout le moteur)
        construction.json      ← les briques 3D (option --3d), modele.glb, modele.obj
        validation.json        ← le verdict du validateur
        niveau_0/              ← un dossier par niveau
          plan.png, plan_sans_mobilier.png (si meublé), masque_semantique.png, masque_pieces.png,
          masque_elements.png, contours.png, hauteur.png, annotations.json
          classes/mur.png…     ← un masque binaire par classe présente (option --masques-par-classe)
        niveau_1/              ← pour un duplex
      000002/
    repartition.json           ← train / validation / test, par famille (voir `repartir`)
    rapports/                  ← statistiques, doublons, planches de contrôle

Les variantes graphiques d'un même logement (option --variantes N) sont des sous-dossiers
`niveau_0/variante_1/`… avec les mêmes fichiers : même géométrie, autre style. Elles restent dans
la même partition que leur logement.

Sous --lot2, un plan peut avoir un exemple sœur `000012-ensemble/` (traits 12 et 13) : plusieurs niveaux, ou deux logements, sur
une seule image. Il a les mêmes fichiers qu'un exemple à un niveau, et son manifeste.json porte « parent » et « compose ». Il
suit toujours son parent dans la répartition, et ne compte pas comme un logement de plus dans les statistiques.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
from moteur.images import ecrire_image
import numpy as np

from moteur.generateur import VERSION_GENERATEUR
from moteur.generateur.annotations import NOMS_CLASSES, decrire
from moteur.generateur.doublons import empreinte, signature
from moteur.generateur.logements import LogementGenere, en_logement, generer
from moteur.generateur.lot2 import PLAIN_PIED_EMPILE, appliquer as appliquer_lot2, composer, lot2_au_hasard, parametres_vrais, resume as resume_lot2, vers_ensemble
from moteur.generateur.reglages import Reglages
from moteur.generateur.rendu import Rendu, rendre
from moteur.generateur.validateur import Regles, Verdict, valider_dossier, valider_geometrie
from moteur.generateur.photo import realisme_au_hasard
from moteur.generateur.variete import appliquer_couleurs, variete_au_hasard
from moteur.generateur.variantes import Style, style_au_hasard

journal = logging.getLogger("generateur")


@dataclass
class Options:
    """Ce que demande la ligne de commande."""

    dossier: Path = Path("sorties/jeu")
    nombre: int = 100
    depart: int = 1  # première graine
    graine_styles: int = 0  # décale le tirage des styles (0 : lié à la graine du logement)
    types: list[str] | None = None  # ex. ["T2", "T3"] ; None = tous (selon les réglages)
    surface_min: float = 0.0
    surface_max: float = 1e9
    pieces_min: int = 0
    pieces_max: int = 99
    resolution: float | None = None  # px/m imposés ; None = selon le style
    diversite: int = 2  # 0 à 3
    variantes: int = 0  # variantes graphiques supplémentaires par logement
    modele_3d: bool = False
    masques_par_classe: bool = False
    reprise: bool = True  # ne pas refaire les exemples déjà complets
    reglages: Path | None = None
    regles: Path | None = None
    familles: list[str] | None = None  # familles de style imposées
    vraie_camera: bool = False  # les photos de biais suivent l'optique d'un vrai appareil (au lieu de coins bougés au hasard)
    sans_cotes: bool = False  # aucune cote dessinée (plans d'agence) ; barre d'échelle et surfaces tirées au hasard
    styles_monde: bool = False  # styles des vrais plans français (sols, traits fins, lettres A-D, capture…) et styles absurdes
    photo_realiste: bool = False  # les photos « vraie caméra » posées sur une vraie table (plis, ombres, reflets, flou)
    biais: bool = False  # A3 : pans coupés et angles arrondis (murs qui ne sont ni horizontaux ni verticaux)
    lot2: bool = False  # styles vus sur les 103 vrais plans (agence colorée, murs noirs, légende Carrez, cotes rouges…)


@dataclass
class Resultat:
    graine: int
    identifiant: str
    statut: str  # accepte, rejete, echec, deja_fait, hors_filtre
    duree: float = 0.0
    erreurs: list[str] = field(default_factory=list)
    entree_manifeste: dict | None = None


def ecrire_png(chemin: Path, image: np.ndarray) -> None:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    ecrire_image(str(chemin), image, [cv2.IMWRITE_PNG_COMPRESSION, 6])


def ecrire_json(chemin: Path, contenu: dict) -> None:
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")


def ecrire_rendu(dn: Path, rendu: Rendu, masques_par_classe: bool) -> list[str]:
    dn.mkdir(parents=True, exist_ok=True)
    fichiers = []
    # Un plan abîmé (grain, JPEG, photo) est enregistré en JPEG : c'est ce qu'envoie un client, et le PNG
    # d'une image bruitée pèse dix fois plus. Les masques restent toujours en PNG (sans perte).
    jpeg = bool(rendu.style.salissure) or (rendu.style.lot2 is not None and rendu.style.lot2.sortie_jpeg)
    for nom, image in rendu.images.items():
        if nom.startswith("plan") and jpeg:
            ecrire_image(str(dn / f"{nom}.jpg"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
            fichiers.append(f"{dn.name}/{nom}.jpg")
        else:
            ecrire_png(dn / f"{nom}.png", image)
            fichiers.append(f"{dn.name}/{nom}.png")
    ecrire_json(dn / "annotations.json", rendu.annotations)
    fichiers.append(f"{dn.name}/annotations.json")
    if masques_par_classe:
        sem = rendu.images["masque_semantique"]
        dc = dn / "classes"
        dc.mkdir(exist_ok=True)
        for valeur in np.unique(sem):
            if valeur == 0:
                continue
            ecrire_png(dc / f"{NOMS_CLASSES[int(valeur)]}.png", ((sem == valeur) * 255).astype(np.uint8))
            fichiers.append(f"{dn.name}/classes/{NOMS_CLASSES[int(valeur)]}.png")
    return fichiers


def style_pour(graine: int, variante: int, opt: Options) -> Style:
    rng = random.Random(f"style-{graine + opt.graine_styles}-{variante}")
    famille = rng.choice(opt.familles) if opt.familles else None
    style = style_au_hasard(rng, opt.diversite, famille)
    if opt.vraie_camera or opt.sans_cotes:
        # Tirage à part : les styles des jeux déjà fabriqués restent identiques sans ces options.
        r2 = random.Random(f"camera-{graine + opt.graine_styles}-{variante}")
        if opt.sans_cotes:
            style.cotes = style.cotes_partielles = False
            style.echelle_graphique = r2.random() < 0.4
            style.surfaces = r2.random() < 0.6
        if opt.vraie_camera and style.perspective:
            # Téléphone (objectif ~26 mm, focale ≈ 0,77 photo) tenu au-dessus de la page : focale ≈ 0,9 à 1,3 page.
            style.focale = r2.uniform(0.9, 1.3)
            style.focale_photo = r2.uniform(0.72, 0.82)
            style.format_photo = 16 / 9 if r2.random() < 0.2 else 4 / 3
            style.inclinaison = (r2.choice((-1, 1)) * r2.uniform(5.0, 25.0), r2.choice((-1, 1)) * r2.uniform(0.0, 15.0))
            style.centre_optique = (r2.uniform(-0.08, 0.08), r2.uniform(-0.08, 0.08))
    if opt.photo_realiste and style.focale:
        # Encore un tirage à part : les jeux « vraie caméra » déjà fabriqués restent identiques sans cette option.
        style.realisme = realisme_au_hasard(random.Random(f"realisme-{graine + opt.graine_styles}-{variante}"))
    if opt.styles_monde:
        # Tirage à part, comme pour les options précédentes : sans --styles-monde, rien ne change.
        r3 = random.Random(f"monde-{graine + opt.graine_styles}-{variante}")
        style.variete = variete_au_hasard(r3)
        appliquer_couleurs(style, style.variete, r3)
    if opt.lot2:
        # Encore un tirage à part : sans --lot2, le style reste bit à bit celui de la version précédente.
        r4 = random.Random(f"lot2-{graine + opt.graine_styles}-{variante}")
        appliquer_lot2(style, lot2_au_hasard(r4), sans_cotes=opt.sans_cotes)
    if opt.resolution:
        style.px_par_m = opt.resolution
        style.taille_texte = round(opt.resolution * 0.2)
    return style


def second_logement(graine: int, opt: Options, reglages: Reglages, regles: Regles, rc: random.Random) -> LogementGenere | None:
    """Le logement d'à côté (trait 13) ou de l'étage différent (trait 12), tiré au-delà de toute graine de jeu : il n'écrit
    aucun exemple à lui et ne peut donc pas passer de l'entraînement au test. Plain-pied et valide, sinon on en tire un autre."""
    for _ in range(5):
        g = graine + 1_000_000 + rc.randrange(10**6)
        try:
            b = generer(g, reglages)
        except RuntimeError:
            continue
        if b.duplex:
            continue
        if opt.biais:
            from moteur.generateur.biais import couper_angles
            couper_angles(b, random.Random(f"biais-{g}"))
        if valider_geometrie(b, decrire(b), regles).accepte:
            return b
    return None


def fabriquer_ensemble(log: LogementGenere, graine: int, ident: str, compose: str, disposition: str, opt: Options, reglages: Reglages,
                       regles: Regles) -> dict:
    """L'exemple sœur `{ident}-ensemble/`, et ce que le manifeste du parent doit en dire (rien si ce plan ne compose pas).

    valider_geometrie n'est pas rejoué : deux portes d'entrée et des blocs non reliés sont justes ici. Chaque bloc l'a passé
    seul ; reste valider_dossier, la cohérence des fichiers et des masques."""
    debut = time.perf_counter()
    rc = random.Random(f"lot2-compose-{graine}")
    log_b = None
    if compose == "deux_logements" and log.duplex:
        compose, disposition = "niveaux", "empiles"  # l'escalier du duplex ne mènerait nulle part
    if not log.duplex:
        if compose == "niveaux" and rc.random() >= PLAIN_PIED_EMPILE:
            return {}
        log_b = second_logement(graine, opt, reglages, regles, rc)
        if log_b is None:
            return {"compose": False, "compose_motif": "second logement refusé"}
    style = style_pour(graine, 0, opt)  # refait : le Repere d'une vraie caméra a écrit dans celui du plan
    c = composer(log, log_b, compose, disposition, style, rc)
    if max(len(c.log.pieces), len(c.log.murs) + len(c.log.ouvertures) + len(c.log.niveaux[0].murs_libres)) > 255:
        return {"compose": False, "compose_motif": "trop d'éléments pour un masque sur 8 bits"}
    vers_ensemble(style, c)
    niveau = c.log.niveaux[0]
    id_ensemble = f"{ident}-ensemble"
    dossier = opt.dossier / "exemples" / id_ensemble
    dossier.mkdir(parents=True, exist_ok=True)
    geometrie = decrire(c.log)
    geometrie["parametres"] = parametres_vrais(geometrie["parametres"], log, log_b)
    n0 = geometrie["niveaux"][0]
    # L'emprise compte les blocs, pas le vide entre eux. Ces champs servent de contrôle, autant qu'ils restent vrais.
    emprise = sum(abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(q["coins"], q["coins"][1:] + q["coins"][:1]))) / 2 for q in c.blocs) / 1e6
    n0["surfaces"]["emprise_interieure"] = round(emprise, 2)
    n0["surfaces"]["cloisons"] = round(emprise - n0["surfaces"]["habitable"], 2)
    geometrie |= {"identifiant": f"SYNTHESE-{graine:06d}-ensemble", "parent": ident, "compose": c.compose, "disposition": c.disposition,
                  "blocs": [{"titre": b["titre"], "cadre": [v / 1000 for v in b["cadre"]], "pieces": b["pieces"], "surface": b["surface"],
                             "contour_interieur": [[v / 1000 for v in q] for q in b["coins"]]} for b in c.blocs]}
    ecrire_json(dossier / "geometrie.json", geometrie)
    ecrire_json(dossier / "logement_niveau0.json", en_logement(c.log, niveau) | {"projet_id": f"SYNTHESE-{graine:06d}-ensemble"})
    rendu = rendre(c.log, niveau, style, graine_style="ensemble")
    fichiers = ["geometrie.json", "logement_niveau0.json"] + ecrire_rendu(dossier / "niveau_0", rendu, opt.masques_par_classe)
    verdict = valider_dossier(dossier, regles, Verdict())
    ecrire_json(dossier / "validation.json", verdict.en_dict())
    entree = {
        "id": id_ensemble, "graine": graine, "parent": ident, "compose": c.compose, "disposition": c.disposition,
        "type": c.log.type, "forme": c.log.forme, "duplex": False, "famille": c.log.famille, "surface": c.log.surface,
        "nombre_pieces": len(c.log.pieces), "nombre_niveaux": 1, "nombre_murs": len(c.log.murs),
        "nombre_ouvertures": len(c.log.ouvertures), "style": style.famille, "variantes": 0,
        "empreinte": empreinte(c.log), "signature": signature(c.log, geometrie).en_dict(), "fichiers": fichiers,
        "octets": sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file()), "version_generateur": VERSION_GENERATEUR,
        "accepte": verdict.accepte, "erreurs": verdict.erreurs, "avertissements": verdict.avertissements, "modele_3d": None,
        "essais": c.log.essais, "lot2": resume_lot2(style.lot2), "duree_s": round(time.perf_counter() - debut, 3),
    }
    ecrire_json(dossier / "manifeste.json", entree)
    if not verdict.accepte:
        journal.warning("exemple %s rejeté après écriture : %s", id_ensemble, " ; ".join(verdict.erreurs[:3]))
    return {"compose": c.compose, "ensemble": id_ensemble, "ensemble_accepte": verdict.accepte}


def fabriquer_exemple(graine: int, opt: Options, reglages: Reglages, regles: Regles) -> Resultat:
    """Tout ce qu'il faut pour une graine : géométrie, validation, images, masques, 3D, fichiers."""
    debut = time.perf_counter()
    ident = f"{graine:06d}"
    dossier = opt.dossier / "exemples" / ident
    termine = dossier / "validation.json"
    if opt.reprise and termine.exists():
        try:
            v = json.loads(termine.read_text(encoding="utf-8"))
            entree = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
            return Resultat(graine, ident, "deja_fait", 0.0, v.get("erreurs", []), entree)
        except Exception:  # noqa: BLE001
            pass  # fichiers incomplets : on refait
    try:
        log = generer(graine, reglages)
    except RuntimeError as e:
        journal.warning("graine %d : %s", graine, e)
        return Resultat(graine, ident, "echec", time.perf_counter() - debut, [str(e)])
    biais_faits = None
    if opt.biais:
        # Tirage à part : sans --biais, le logement reste exactement le même.
        from moteur.generateur.biais import couper_angles
        biais_faits = couper_angles(log, random.Random(f"biais-{graine}"))
    if opt.types and log.type not in opt.types:
        return Resultat(graine, ident, "hors_filtre", time.perf_counter() - debut)
    if not (opt.surface_min <= log.surface <= opt.surface_max) or not (opt.pieces_min <= len(log.pieces) <= opt.pieces_max):
        return Resultat(graine, ident, "hors_filtre", time.perf_counter() - debut)

    geometrie = decrire(log)
    verdict = valider_geometrie(log, geometrie, regles)
    if not verdict.accepte:
        journal.warning("graine %d rejetée : %s", graine, " ; ".join(verdict.erreurs[:3]))
        return Resultat(graine, ident, "rejete", time.perf_counter() - debut, verdict.erreurs)

    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = ["geometrie.json"]
    ecrire_json(dossier / "geometrie.json", geometrie)
    for niveau in log.niveaux:
        ecrire_json(dossier / f"logement_niveau{niveau.index}.json", en_logement(log, niveau))
        fichiers.append(f"logement_niveau{niveau.index}.json")
    styles = []
    style_lot2 = None
    for niveau in log.niveaux:
        for variante in range(opt.variantes + 1):
            style = style_pour(graine, variante, opt)
            rendu = rendre(log, niveau, style, graine_style=str(variante))
            dn = dossier / f"niveau_{niveau.index}" / (f"variante_{variante}" if variante else "")
            dn = dn if variante else dossier / f"niveau_{niveau.index}"
            fichiers += [(f"niveau_{niveau.index}/" + f) if variante else f for f in ecrire_rendu(dn, rendu, opt.masques_par_classe)]
            if variante == 0 and niveau.index == 0:
                styles.append(style.famille)
                style_lot2 = style.lot2
    bilan_3d = None
    if opt.modele_3d:
        from moteur.generateur.modele3d import briques_du_logement, ecrire_glb, ecrire_obj, plan_de_construction
        briques = briques_du_logement(log)
        ecrire_json(dossier / "construction.json", plan_de_construction(log))
        bilan_3d = ecrire_glb(log, dossier / "modele.glb", briques)
        ecrire_obj(log, dossier / "modele.obj", briques)
        fichiers += ["construction.json", "modele.glb", "modele.obj", "materiaux.mtl"]
    verdict = valider_dossier(dossier, regles, verdict)
    ecrire_json(dossier / "validation.json", verdict.en_dict())
    taille = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())
    duree = time.perf_counter() - debut  # sans l'ensemble : il a sa propre durée, les statistiques ne doivent pas la compter deux fois
    compose = {}
    if style_lot2 is not None and style_lot2.composition and verdict.accepte:
        # Avant manifeste.json : c'est lui qui marque un exemple comme fini, une reprise après coupure refera donc les deux.
        compose = fabriquer_ensemble(log, graine, ident, style_lot2.composition, style_lot2.disposition, opt, reglages, regles)
    entree = {
        "id": ident, "graine": graine, "type": log.type, "forme": log.forme, "duplex": log.duplex,
        "famille": log.famille, "surface": log.surface, "nombre_pieces": len(log.pieces),
        "nombre_niveaux": len(log.niveaux), "nombre_murs": len(log.murs), "nombre_ouvertures": len(log.ouvertures),
        "style": styles[0] if styles else None, "variantes": opt.variantes,
        "empreinte": empreinte(log), "signature": signature(log, geometrie).en_dict(),
        "fichiers": fichiers, "octets": taille, "version_generateur": VERSION_GENERATEUR,
        "accepte": verdict.accepte, "erreurs": verdict.erreurs, "avertissements": verdict.avertissements,
        "modele_3d": bilan_3d, "essais": log.essais, **({"biais": biais_faits} if opt.biais else {}),
        **({"lot2": resume_lot2(style_lot2)} if style_lot2 is not None else {}), **compose, "duree_s": round(duree, 3),
    }
    ecrire_json(dossier / "manifeste.json", entree)
    statut = "accepte" if verdict.accepte else "rejete"
    if statut == "rejete":
        journal.warning("exemple %s rejeté après écriture : %s", ident, " ; ".join(verdict.erreurs[:3]))
    return Resultat(graine, ident, statut, time.perf_counter() - debut, verdict.erreurs, entree)


# ---------------------------------------------------------------- le lot


def _travail(args: tuple) -> Resultat:
    graine, opt, reglages, regles = args
    try:
        return fabriquer_exemple(graine, opt, reglages, regles)
    except Exception as e:  # noqa: BLE001
        journal.exception("graine %d : plantage", graine)
        return Resultat(graine, f"{graine:06d}", "echec", 0.0, [f"plantage : {e!r}"])


def generer_lot(opt: Options, processus: int = 1) -> dict:
    """Génère `opt.nombre` graines à partir de `opt.depart`, écrit le manifeste, renvoie le bilan."""
    opt.dossier.mkdir(parents=True, exist_ok=True)
    _journal(opt.dossier / "journal.log")
    reglages = Reglages.charger(opt.reglages)
    regles = Regles.charger(opt.regles)
    ecrire_json(opt.dossier / "reglages.json", {"generateur": VERSION_GENERATEUR, "options": _options_json(opt),
                                                "reglages": reglages.en_dict(), "regles": asdict(regles)})
    graines = list(range(opt.depart, opt.depart + opt.nombre))
    journal.info("lot de %d graines (%d → %d), %d processus, dossier %s", len(graines), graines[0], graines[-1], processus, opt.dossier)
    debut = time.perf_counter()
    taches = [(g, opt, reglages, regles) for g in graines]
    resultats: list[Resultat] = []
    if processus > 1:
        from multiprocessing import Pool
        with Pool(processus) as pool:
            for i, r in enumerate(pool.imap_unordered(_travail, taches, chunksize=2), start=1):
                resultats.append(r)
                _progression(i, len(graines), debut)
    else:
        for i, t in enumerate(taches, start=1):
            resultats.append(_travail(t))
            _progression(i, len(graines), debut)
    resultats.sort(key=lambda r: r.graine)
    duree = time.perf_counter() - debut
    manifeste = ecrire_manifeste(opt.dossier)
    bilan = {
        "graines": len(graines), "duree_s": round(duree, 1), "processus": processus,
        "statuts": {s: sum(r.statut == s for r in resultats) for s in ("accepte", "rejete", "echec", "deja_fait", "hors_filtre")},
        "exemples_dans_le_manifeste": manifeste["nombre"],
        "acceptes_dans_le_manifeste": manifeste["acceptes"],
        "octets_total": manifeste["octets_total"],
        "octets_par_exemple": manifeste["octets_par_exemple"],
        "secondes_par_graine": round(duree / max(1, len(graines)), 3),
    }
    if opt.lot2:  # sinon le bilan des anciens jeux ne change pas
        entrees = [r.entree_manifeste for r in resultats if r.entree_manifeste]
        bilan["ensembles"] = {
            "acceptes": sum(e.get("ensemble_accepte") is True for e in entrees),
            "rejetes": sum(e.get("ensemble_accepte") is False for e in entrees),
            "refuses": sum(e.get("compose") is False for e in entrees),
        }
    journal.info("fin du lot : %s", json.dumps(bilan, ensure_ascii=False))
    return bilan


def _progression(i: int, n: int, debut: float) -> None:
    if i % 10 == 0 or i == n:
        ecoule = time.perf_counter() - debut
        journal.info("%d/%d exemples, %.0f s écoulées, ~%.0f s restantes", i, n, ecoule, ecoule / i * (n - i))


def ecrire_manifeste(dossier: Path) -> dict:
    """Relit les manifestes de tous les exemples présents et écrit manifest.json."""
    entrees = []
    for m in sorted((dossier / "exemples").glob("*/manifeste.json")):
        try:
            entrees.append(json.loads(m.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            journal.warning("manifeste illisible : %s", m)
    octets = sum(e["octets"] for e in entrees)
    manifeste = {
        "schema": "manifest-plan-synthetique/1.0", "version_generateur": VERSION_GENERATEUR,
        "nombre": len(entrees), "acceptes": sum(e["accepte"] for e in entrees),
        "octets_total": octets, "octets_par_exemple": round(octets / len(entrees)) if entrees else 0,
        "exemples": [{k: v for k, v in e.items() if k != "signature"} for e in entrees],
    }
    if any("parent" in e for e in entrees):
        manifeste["ensembles"] = sum("parent" in e for e in entrees)
    ecrire_json(dossier / "manifest.json", manifeste)
    return manifeste


def _journal(chemin: Path) -> None:
    if any(isinstance(h, logging.FileHandler) and h.baseFilename == str(chemin.resolve()) for h in journal.handlers):
        return
    journal.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    f = logging.FileHandler(chemin, encoding="utf-8")
    f.setFormatter(fmt)
    journal.addHandler(f)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in journal.handlers):
        c = logging.StreamHandler()
        c.setFormatter(fmt)
        journal.addHandler(c)


def _options_json(opt: Options) -> dict:
    d = asdict(opt)
    if not d["lot2"]:  # sans l'option, reglages.json ne change pas non plus
        del d["lot2"]
    for k, v in d.items():
        if isinstance(v, Path):
            d[k] = str(v)
    return d


# ---------------------------------------------------------------- répartition train / validation / test


def repartir(dossier: Path, parts: tuple[float, float, float] = (0.8, 0.1, 0.1), graine: int = 0,
             seuil: float | None = None) -> dict:
    """Répartit les exemples acceptés entre train, validation et test, par groupes, de façon reproductible.

    Le groupe d'un exemple est sa graine (toutes ses variantes graphiques vont ensemble) ; les
    doublons exacts (même empreinte) vont aussi ensemble. Chaque groupe est affecté par un tirage
    déterministe (condensé de « graine de répartition + empreinte »), en respectant les proportions
    par famille géométrique : chaque famille est présente dans chaque partition quand elle compte
    assez d'exemples. Les paires « trop semblables » entre train et test sont signalées dans le
    rapport, et le membre côté test est déplacé en train pour que le test mesure la généralisation.

    Un exemple `-ensemble` montre les pièces de son parent : il le suit dans sa partition, à la fin, après les déplacements.
    Il n'entre ni dans les groupes ni dans la recherche de ressemblances : ce n'est pas un logement de plus.
    """
    from moteur.generateur.doublons import SEUIL_RESSEMBLANCE, chercher
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    exemples = [e for e in manifeste["exemples"] if e["accepte"] and "parent" not in e]
    ensembles = [e for e in manifeste["exemples"] if e["accepte"] and "parent" in e]
    entrees = []
    for e in exemples:
        m = json.loads((dossier / "exemples" / e["id"] / "manifeste.json").read_text(encoding="utf-8"))
        entrees.append({"id": e["id"], "empreinte": m["empreinte"], "signature": m["signature"], "famille": e["famille"]})
    # Les groupes : une empreinte = un groupe (doublons exacts ensemble).
    groupes: dict[str, list[dict]] = {}
    for e in entrees:
        groupes.setdefault(e["empreinte"], []).append(e)
    affectation: dict[str, str] = {}
    par_famille: dict[str, list[str]] = {}
    for emp, membres in groupes.items():
        par_famille.setdefault(membres[0]["famille"], []).append(emp)
    for famille, emps in par_famille.items():
        # Ordre déterministe par condensé, puis découpe en proportions : chaque famille est répartie à part.
        emps.sort(key=lambda emp: hashlib.sha256(f"{graine}-{emp}".encode()).hexdigest())
        n = len(emps)
        n_test = round(n * parts[2])
        n_val = round(n * parts[1])
        if n >= 3:
            n_test, n_val = max(1, n_test), max(1, n_val)
        for i, emp in enumerate(emps):
            partition = "test" if i < n_test else "validation" if i < n_test + n_val else "train"
            for e in groupes[emp]:
                affectation[e["id"]] = partition
    # Les trop semblables entre partitions : le membre hors train rejoint train.
    rapport = chercher(entrees, seuil if seuil is not None else SEUIL_RESSEMBLANCE)
    deplaces = []
    for paire in rapport["trop_semblables"]:
        a, b = paire["ids"]
        if affectation.get(a) != affectation.get(b):
            cible = a if affectation[a] != "train" else b
            if affectation[cible] != "train":
                affectation[cible] = "train"
                deplaces.append(cible)
    for e in ensembles:
        if e["parent"] in affectation:  # sinon son parent a été rejeté : il reste hors du jeu avec lui
            affectation[e["id"]] = affectation[e["parent"]]
    comptes = {p: sum(v == p for v in affectation.values()) for p in ("train", "validation", "test")}
    resultat = {
        "schema": "repartition/1.0", "graine": graine, "parts": list(parts), "comptes": comptes,
        "familles": {f: {p: sum(affectation[e["id"]] == p for e in entrees if e["famille"] == f) for p in comptes} for f in sorted(par_famille)},
        "deplaces_vers_train": deplaces, "doublons_exacts": rapport["doublons_exacts"],
        "trop_semblables": rapport["trop_semblables"],
        "partitions": {p: sorted(i for i, v in affectation.items() if v == p) for p in comptes},
    }
    ecrire_json(dossier / "repartition.json", resultat)
    return resultat
