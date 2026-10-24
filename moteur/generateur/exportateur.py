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
import numpy as np

from moteur.generateur import VERSION_GENERATEUR
from moteur.generateur.annotations import NOMS_CLASSES, decrire
from moteur.generateur.doublons import empreinte, signature
from moteur.generateur.logements import LogementGenere, en_logement, generer
from moteur.generateur.reglages import Reglages
from moteur.generateur.rendu import Rendu, rendre
from moteur.generateur.validateur import Regles, Verdict, valider_dossier, valider_geometrie
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
    cv2.imwrite(str(chemin), image, [cv2.IMWRITE_PNG_COMPRESSION, 6])


def ecrire_json(chemin: Path, contenu: dict) -> None:
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")


def ecrire_rendu(dn: Path, rendu: Rendu, masques_par_classe: bool) -> list[str]:
    dn.mkdir(parents=True, exist_ok=True)
    fichiers = []
    # Un plan abîmé (grain, JPEG, photo) est enregistré en JPEG : c'est ce qu'envoie un client, et le PNG
    # d'une image bruitée pèse dix fois plus. Les masques restent toujours en PNG (sans perte).
    jpeg = bool(rendu.style.salissure)
    for nom, image in rendu.images.items():
        if nom.startswith("plan") and jpeg:
            cv2.imwrite(str(dn / f"{nom}.jpg"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
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
    if opt.resolution:
        style.px_par_m = opt.resolution
        style.taille_texte = round(opt.resolution * 0.2)
    return style


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
    for niveau in log.niveaux:
        for variante in range(opt.variantes + 1):
            style = style_pour(graine, variante, opt)
            rendu = rendre(log, niveau, style, graine_style=str(variante))
            dn = dossier / f"niveau_{niveau.index}" / (f"variante_{variante}" if variante else "")
            dn = dn if variante else dossier / f"niveau_{niveau.index}"
            fichiers += [(f"niveau_{niveau.index}/" + f) if variante else f for f in ecrire_rendu(dn, rendu, opt.masques_par_classe)]
            if variante == 0 and niveau.index == 0:
                styles.append(style.famille)
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
    entree = {
        "id": ident, "graine": graine, "type": log.type, "forme": log.forme, "duplex": log.duplex,
        "famille": log.famille, "surface": log.surface, "nombre_pieces": len(log.pieces),
        "nombre_niveaux": len(log.niveaux), "nombre_murs": len(log.murs), "nombre_ouvertures": len(log.ouvertures),
        "style": styles[0] if styles else None, "variantes": opt.variantes,
        "empreinte": empreinte(log), "signature": signature(log, geometrie).en_dict(),
        "fichiers": fichiers, "octets": taille, "version_generateur": VERSION_GENERATEUR,
        "accepte": verdict.accepte, "erreurs": verdict.erreurs, "avertissements": verdict.avertissements,
        "modele_3d": bilan_3d, "essais": log.essais, "duree_s": round(time.perf_counter() - debut, 3),
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
    """
    from moteur.generateur.doublons import SEUIL_RESSEMBLANCE, chercher
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    exemples = [e for e in manifeste["exemples"] if e["accepte"]]
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
