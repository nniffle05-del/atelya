"""Mesurer le lecteur d'échelle, plan par plan, et comparer deux versions de ce lecteur (chantier « échelle des plans en cm »).

Pourquoi : la règle absolue est « 0 échelle fausse de plus de 3 % sans alerte ». Un plan envoyé à la vérification humaine coûte
2 minutes ; une échelle fausse annoncée sûre donne un logement à la mauvaise taille. Il faut donc compter les deux, sur des
échantillons non choisis à la main, et comparer plan par plan avant / après chaque changement du lecteur.

Quatre sources de plans, toutes lues avec le même enchaînement que le banc et que moteur.lecture_complete :
  jeu      un jeu du générateur sur le disque (ex. ..\\atelya\\donnees\\lot2-test), avec le coloriage parfait ou --coloriages (et --textes-pdf).
  tirages  des tirages du lot 2 à plat, cotés en cm (graines 80001+ du script d'origine echelle2.py), posés une fois sur le disque.
  vrais    les vrais plans d'ENTRAÎNEMENT (verites/repartition-vrais-plans.json). Les plans d'examen sont refusés (règle 15).
  comparer deux fichiers de résultats, plan par plan.

Les textes lus par l'OCR sont gardés dans un cache (--cache-ocr) : l'OCR est lent et n'est pas ce qu'on mesure ici ; avant et après
lisent ainsi exactement les mêmes textes. --code : le dossier du code à mesurer (une copie de l'ancien moteur pour « avant »).

Depuis le dossier du dépôt, OMP_NUM_THREADS=1, chemins relatifs :
  python pc/lot2/mesurer_echelle_lot2.py jeu ..\\atelya\\donnees\\lot2-test --sortie ..\\atelya\\echelle-cm\\avant-lot2-test.json
  python pc/lot2/mesurer_echelle_lot2.py comparer A.json B.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
SEUIL_ERREUR = 3.0  # %
_CONFIG: dict = {}


def _preparer(code: str, cache_ocr: str | None) -> None:
    """Dans chaque processus : le code à mesurer d'abord dans le chemin, puis le cache de l'OCR branché."""
    sys.path.insert(0, code)
    if cache_ocr:
        _brancher_cache(Path(cache_ocr))


def _brancher_cache(dossier: Path) -> None:
    import numpy as np

    import moteur.barre_echelle as be
    import moteur.echelle_plan as ep
    import moteur.lecture_cotes as lc

    vrai = lc.lire_textes

    def lire(gris, agrandir: int = 1):
        h = hashlib.sha1(gris.tobytes())
        h.update(f"{gris.shape}-{agrandir}".encode())
        nom = h.hexdigest()
        f = dossier / nom[:2] / f"{nom}.json"
        if f.exists():
            return [lc.TexteLu(t, np.array(b, float), s) for t, b, s in json.loads(f.read_text(encoding="utf-8"))]
        textes = vrai(gris, agrandir)
        f.parent.mkdir(parents=True, exist_ok=True)
        provisoire = f.with_suffix(f".{os.getpid()}.tmp")
        provisoire.write_text(json.dumps([[t.texte, t.boite.tolist(), t.confiance] for t in textes], ensure_ascii=False),
                              encoding="utf-8")
        os.replace(provisoire, f)
        return textes

    lc.lire_textes = ep.lire_textes = be.lire_textes = lire


def _cote_en_dict(c, retenues) -> dict:
    return {"texte": c.texte.texte, "valeur": c.valeur, "px": round(c.longueur_px, 1), "px_par_m": round(c.px_par_m, 2),
            "sens": "V" if c.verticale else "H", "bouts": [[round(v, 1) for v in b] for b in c.bouts],
            "boite": [round(float(v), 1) for v in (*c.texte.boite.min(axis=0), *c.texte.boite.max(axis=0))],
            "retenue": any(c is r for r in retenues)}


def _lire(image_rgb, col, a_plat: bool = False, textes: list | None = None, px_par_pt: float | None = None) -> tuple[dict, object, bool]:
    """Le même enchaînement que moteur.lecture_complete.lire_avec_coloriage, jusqu'à la décision."""
    import numpy as np
    from PIL import Image

    from moteur.echelle_plan import coloriage_douteux, decider, lire_echelle_plan, sans_taches_au_bord
    from moteur.redressement import corriger_proportions, estimer_redressement, photo_entiere, rapport_par_optique, rapport_plausible

    infos: dict = {}
    if coloriage_douteux(col):
        propre = sans_taches_au_bord(col)
        if not coloriage_douteux(propre):
            col, infos["coloriage_nettoye"] = propre, True
    R = estimer_redressement(col) if not a_plat else None
    if R is not None and not R.de_biais:
        R = None
    optique = R is not None
    h_img, l_img = image_rgb.shape[:2]
    if optique and not photo_entiere(l_img, h_img):
        optique, infos["photo_recadree"] = False, True
    if optique:
        rapport = rapport_par_optique(R, col.shape)
        if rapport_plausible(rapport):
            R = corriger_proportions(R, rapport)
        else:
            optique, infos["optique_douteuse"] = False, True
    gris = np.asarray(Image.fromarray(image_rgb).convert("L"))
    e = lire_echelle_plan(gris, col, R, textes=textes, px_par_pt=px_par_pt)
    douteux = coloriage_douteux(col)
    lx, ly, source = decider(e.largeur, e.hauteur, e.sure, e.cote_max_largeur, e.cote_max_hauteur, e.interieur_px,
                             R is not None, e.barre if e.barre_sure else None, e.surfaces if e.surfaces_sure else None,
                             optique, e.approchee, douteux, e.surfaces, ecrite=e.ecrite,
                             **({"ambigue": e.ambigue} if hasattr(e, "ambigue") else {}))  # 0.13 ; le code d'avant n'a pas ce champ
    if R is None:
        lx = ly = lx or ly
    sortie = {"lx": lx, "ly": ly, "source": source, "lu": bool(lx or ly), "sure": e.sure, "contredite": e.contredite, "ambigue": getattr(e, "ambigue", None),
              "de_biais": R is not None, "optique": optique, "douteux": douteux, "largeur_cotes": e.largeur, "hauteur_cotes": e.hauteur,
              "interieur_px": e.interieur_px, "cote_max": [e.cote_max_largeur, e.cote_max_hauteur],
              "barre": e.barre, "barre_sure": e.barre_sure, "barre_detail": e.barre_detail,
              "surfaces": e.surfaces, "surfaces_sure": e.surfaces_sure, "surfaces_detail": e.surfaces_detail,
              "n_cotes": len(e.cotes), "n_retenues": len(e.retenues), "cotes": [_cote_en_dict(c, e.retenues) for c in e.cotes],
              "facteur": col.shape[1] / image_rgb.shape[1], **infos}
    return sortie, R, optique


def _style_lot2(graine: int) -> dict:
    """La famille et les traits du style tiré pour cette graine (le générateur n'est PAS relancé)."""
    from moteur.generateur.exportateur import Options, style_pour

    st = style_pour(graine, 0, Options(dossier=None, lot2=True))
    l = st.lot2
    return {"famille": l.famille, "unite": l.unite_cotes, "cotes_dessinees": bool(st.cotes), "chaines": not l.sans_chaines,
            "surfaces_ecrites": bool(st.surfaces and not l.noms_courts), "barre": bool(st.echelle_graphique),
            "salissure": str(st.salissure or ""), "murs": l.murs_dessin, "style": st.famille}


def _ecart(lu: float | None, vrai: float | None) -> float | None:
    return round(100 * (lu / vrai - 1), 3) if lu and vrai else None


def _un_niveau_du_jeu(tache: tuple) -> dict:
    exemple, niveau_nom, fichier_coloriage, lot2, pdf = tache
    import numpy as np
    from PIL import Image

    from moteur.banc_coloriage import coloriage_parfait, dessin_du_niveau, echelle_pour_atelya, echelles_apres_redressement, textes_pdf

    exemple, niveau = Path(exemple), Path(exemple) / niveau_nom
    debut = time.perf_counter()
    res = {"plan": exemple.name, "niveau": niveau_nom}
    try:
        ann = json.loads((niveau / "annotations.json").read_text(encoding="utf-8"))
        col = np.array(Image.open(fichier_coloriage), np.uint8) if fichier_coloriage else coloriage_parfait(niveau)
        dessin = dessin_du_niveau(niveau, None)
        image = np.array(Image.open(dessin).convert("RGB"))
        s, r = echelle_pour_atelya(ann, (ann["image"]["largeur"], ann["image"]["hauteur"]))
        tp = textes_pdf(niveau) if pdf else None
        lu, R, _ = _lire(image, col, bool(ann.get("pdf", {}).get("a_plat")), tp[0] if tp else None, tp[1] if tp else None)
        vx = vy = s
        if R is not None:
            vx, vy = echelles_apres_redressement(R, ann, s / ann["image"]["px_par_m"])
        res |= lu
        res |= {"vrai_x": round(vx, 3), "vrai_y": round(vy, 3), "ecart_x": _ecart(lu["lx"], vx), "ecart_y": _ecart(lu["ly"], vy),
                "rotation": float(ann["image"].get("rotation_deg", 0) or 0), "perspective": float(ann["image"].get("perspective", 0) or 0)}
        if lot2:
            res |= _style_lot2(int(exemple.name.split("-")[0]))
            res["ensemble"] = "ensemble" in exemple.name
    except Exception as err:  # noqa: BLE001 — on note le plantage du plan : il est lui-même un résultat à regarder
        res["plantage"] = f"{type(err).__name__}: {err}"
    res["duree_s"] = round(time.perf_counter() - debut, 1)
    return res


def _poser_tirage(args) -> dict | None:
    """Pose un tirage sur le disque (une seule fois) : son image, son masque, sa vraie échelle. Mêmes filtres qu'echelle2.py."""
    g, dossier = args
    import numpy as np
    from PIL import Image

    from moteur.generateur.exportateur import Options, style_pour
    from moteur.generateur.logements import generer
    from moteur.generateur.reglages import Reglages
    from moteur.generateur.rendu import rendre

    style = style_pour(g, 0, Options(dossier=None, lot2=True))
    l = style.lot2
    if l.unite_cotes != "cm" or style.rotation or style.perspective or style.focale or not style.cotes:
        return None
    d = Path(dossier) / str(g)
    if (d / "vrai.json").exists():
        return json.loads((d / "vrai.json").read_text(encoding="utf-8"))
    try:
        log = generer(g, Reglages())
    except RuntimeError:
        return None
    r = rendre(log, log.niveaux[0], style)
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(r.images["plan"]).save(d / "plan.png")
    Image.fromarray(np.asarray(r.images["masque_semantique"], np.uint8)).save(d / "masque_semantique.png")
    vrai = {"graine": g, "px_par_m": style.px_par_m}
    (d / "vrai.json").write_text(json.dumps(vrai), encoding="utf-8")
    return vrai


def _un_tirage(tache: tuple) -> dict:
    dossier, g = tache
    import numpy as np
    from PIL import Image

    from moteur.banc_coloriage import coloriage_parfait

    d = Path(dossier) / str(g)
    debut = time.perf_counter()
    res = {"plan": str(g), "niveau": "niveau_0"}
    try:
        vrai = json.loads((d / "vrai.json").read_text(encoding="utf-8"))["px_par_m"]
        col = coloriage_parfait(d)
        image = np.array(Image.open(d / "plan.png").convert("RGB"))
        lu, R, _ = _lire(image, col)
        s = vrai * lu["facteur"]
        res |= lu
        res |= {"vrai_x": round(s, 3), "vrai_y": round(s, 3), "ecart_x": _ecart(lu["lx"], s), "ecart_y": _ecart(lu["ly"], s)}
        res |= _style_lot2(g)
    except Exception as err:  # noqa: BLE001
        res["plantage"] = f"{type(err).__name__}: {err}"
    res["duree_s"] = round(time.perf_counter() - debut, 1)
    return res


def plans_d_examen(repartition: dict) -> set[str]:
    return set(repartition["examen_anciens"]) | set(repartition["examen_nouveaux"])


def _un_vrai_plan(tache: tuple) -> dict:
    nom, images, lectures, verites = tache
    import numpy as np
    from PIL import Image, ImageOps

    debut = time.perf_counter()
    res = {"plan": nom, "niveau": "niveau_0"}
    try:
        col = np.array(Image.open(Path(lectures) / nom / "coloriage.png"), np.uint8)
        with Image.open(next(Path(images).glob(f"{nom}.*"))) as img:
            image = np.array(ImageOps.exif_transpose(img).convert("RGB"))
        lu, R, _ = _lire(image, col)
        res |= lu
        f = Path(verites) / nom / "verite.json"
        if f.exists():
            v = json.loads(f.read_text(encoding="utf-8"))
            res["verite"] = True
            res["echelle_inconnue"] = v["echelle_inconnue"]
            res["echelle_source_verite"] = v.get("echelle_source")
            if not v["echelle_inconnue"]:
                s = v["px_par_m"] * 768 / max(v["largeur"], v["hauteur"])  # voir r_col dans outils/verite/noter_vrais_plans.py
                res |= {"vrai_x": round(s, 3), "vrai_y": round(s, 3), "ecart_x": _ecart(lu["lx"], s), "ecart_y": _ecart(lu["ly"], s),
                        "ecart_cotes": _ecart(lu["largeur_cotes"] or lu["hauteur_cotes"], s), "ecart_surfaces": _ecart(lu["surfaces"], s)}
    except Exception as err:  # noqa: BLE001
        res["plantage"] = f"{type(err).__name__}: {err}"
    res["duree_s"] = round(time.perf_counter() - debut, 1)
    return res


def _executer(fonction, taches: list, sortie: Path, processus: int, code: str, cache_ocr: str | None) -> list[dict]:
    """Lance les lectures (reprises si le fichier .partiel.jsonl existe) et rend tous les résultats, triés."""
    partiel = sortie.with_suffix(".partiel.jsonl")
    faits: dict[tuple, dict] = {}
    if partiel.exists():
        for ligne in partiel.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ligne)
                faits[(r["plan"], r["niveau"])] = r
            except json.JSONDecodeError:
                pass

    def cle(t) -> tuple:
        if fonction is _un_niveau_du_jeu:
            return Path(t[0]).name, t[1]
        if fonction is _un_tirage:
            return str(t[1]), "niveau_0"
        return t[0], "niveau_0"

    reste = [t for t in taches if cle(t) not in faits]
    print(f"{len(taches)} plans, {len(reste)} à lire", flush=True)
    debut = time.time()
    with open(partiel, "a", encoding="utf-8") as f, Pool(processus, _preparer, (code, cache_ocr)) as pool:
        for i, r in enumerate(pool.imap_unordered(fonction, reste), 1):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            faits[(r["plan"], r["niveau"])] = r
            if i % 10 == 0 or i == len(reste):
                print(f"{i}/{len(reste)} {round(time.time() - debut)} s", flush=True)
    return [faits[k] for k in sorted(faits)]


# ---------------------------------------------------------------- bilans


def erreur_max(r: dict) -> float | None:
    v = [abs(e) for e in (r.get("ecart_x"), r.get("ecart_y")) if e is not None]
    return max(v) if v else None


def _resume(rs: list[dict]) -> dict:
    n = len(rs)
    lus = [r for r in rs if r.get("lu")]
    connus = [r for r in lus if erreur_max(r) is not None]
    faux = [r for r in connus if erreur_max(r) > SEUIL_ERREUR]
    return {"plans": n, "lus": len(lus), "pct_lus": round(100 * len(lus) / n, 1) if n else None, "a_verifier": n - len(lus),
            "faux_3pct": len(faux), "faux_1pct": sum(erreur_max(r) > 1 for r in connus),
            "sources": dict(Counter(r.get("source", "plantage") for r in rs)),
            "faux_par_source": dict(Counter(r["source"] for r in faux)),
            "plantages": sum("plantage" in r for r in rs)}


def bilan(rs: list[dict]) -> dict:
    groupes = defaultdict(list)
    for r in rs:
        groupes["tous"].append(r)
        if "famille" in r:
            groupes[f"famille {r['famille']}"].append(r)
            groupes[f"unité {r['unite'] if r['cotes_dessinees'] else 'sans cotes'}"].append(r)
            if r.get("ensemble"):
                groupes["ensembles"].append(r)
    faux = sorted(((r["plan"], r["niveau"], r["source"], r.get("ecart_x"), r.get("ecart_y")) for r in rs
                   if r.get("lu") and (erreur_max(r) or 0) > SEUIL_ERREUR), key=lambda t: t[0])
    return {"par_groupe": {k: _resume(v) for k, v in sorted(groupes.items())}, "faux": faux}


def _imprimer(b: dict) -> None:
    for k, v in b["par_groupe"].items():
        print(f"{k:32s} {v['plans']:4d} plans, lus {v['lus']:4d} ({v['pct_lus']} %), à vérifier {v['a_verifier']:4d}, "
              f"faux > 3 % : {v['faux_3pct']}, > 1 % : {v['faux_1pct']}, plantages {v['plantages']}, sources {v['sources']}")
    print("Faux > 3 % :")
    for f in b["faux"]:
        print("  ", f)


def _ecrire(sortie: Path, rs: list[dict], meta: dict) -> None:
    b = bilan(rs)
    sortie.write_text(json.dumps({"meta": meta, "bilan": b, "plans": rs}, ensure_ascii=False, indent=0), encoding="utf-8")
    _imprimer(b)


def comparer(fa: Path, fb: Path, detail: int = 80) -> dict:
    a = {(r["plan"], r["niveau"]): r for r in json.loads(fa.read_text(encoding="utf-8"))["plans"]}
    b = {(r["plan"], r["niveau"]): r for r in json.loads(fb.read_text(encoding="utf-8"))["plans"]}
    communs = sorted(a.keys() & b.keys())
    print(f"{len(communs)} plans communs ({len(a)} avant, {len(b)} après)")
    change, lu_perdu, lu_gagne, faux_guerris, faux_nouveaux, juste_perdu = [], [], [], [], [], []
    for k in communs:
        ra, rb = a[k], b[k]
        la, lb = (ra.get("lx"), ra.get("ly")), (rb.get("lx"), rb.get("ly"))
        if la != lb or ra.get("source") != rb.get("source"):
            change.append(k)
        ea, eb = erreur_max(ra), erreur_max(rb)
        fa_, fb_ = ea is not None and ea > SEUIL_ERREUR, eb is not None and eb > SEUIL_ERREUR
        if ra.get("lu") and not rb.get("lu"):
            lu_perdu.append(k)
            if not fa_:
                juste_perdu.append(k)
        if rb.get("lu") and not ra.get("lu"):
            lu_gagne.append(k)
        if fa_ and not fb_:
            faux_guerris.append(k)
        if fb_ and not fa_:
            faux_nouveaux.append(k)
    print("Avant :")
    _imprimer(bilan([a[k] for k in communs]))
    print("Après :")
    _imprimer(bilan([b[k] for k in communs]))
    print(f"Plans dont l'échelle ou la source a changé : {len(change)}")
    print(f"Lus → à vérifier : {len(lu_perdu)}, dont justes ou de vérité inconnue (le coût) : {len(juste_perdu)}")
    print(f"À vérifier → lus : {len(lu_gagne)}")
    print(f"Faux → plus faux : {len(faux_guerris)} ; nouveaux faux : {len(faux_nouveaux)}")
    for k in change[:detail]:
        ra, rb = a[k], b[k]
        print(f"  {k[0]} {k[1]} : {ra.get('source')} {ra.get('lx') and round(ra['lx'], 2)} (écart {ra.get('ecart_x')}) → "
              f"{rb.get('source')} {rb.get('lx') and round(rb['lx'], 2)} (écart {rb.get('ecart_x')})")
    return {"change": change, "lu_perdu": lu_perdu, "juste_perdu": juste_perdu, "lu_gagne": lu_gagne, "faux_guerris": faux_guerris,
            "faux_nouveaux": faux_nouveaux}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = ap.add_subparsers(dest="action", required=True)
    communs = argparse.ArgumentParser(add_help=False)
    communs.add_argument("--sortie", type=Path, required=True)
    communs.add_argument("--code", default=".", help="dossier qui contient le moteur à mesurer")
    communs.add_argument("--cache-ocr", default=r"..\atelya\echelle-cm\cache-ocr")
    communs.add_argument("--processus", type=int, default=3)
    j = sous.add_parser("jeu", parents=[communs])
    j.add_argument("dossier", type=Path)
    j.add_argument("--coloriages", type=Path, help="dossier des coloriages <plan>/<niveau>.png (sinon : coloriage parfait)")
    j.add_argument("--textes-pdf", action="store_true", help="jeu de PDF : lit les textes exacts de chaque page (pas d'OCR), comme le banc")
    j.add_argument("--un-sur", type=int, default=1, help="garde un exemple sur N, dans l'ordre : un échantillon non choisi à la main")
    t = sous.add_parser("tirages", parents=[communs])
    t.add_argument("--depart", type=int, default=80001)
    t.add_argument("--nombre", type=int, default=150)
    t.add_argument("--dossier", default=r"..\atelya\echelle-cm\tirages-cm")
    v = sous.add_parser("vrais", parents=[communs])
    v.add_argument("--images", default=r"..\atelya\vrais-plans\lot-2026-11-05")
    v.add_argument("--lectures", default=r"..\atelya\lectures-lot-2026-11-05")
    v.add_argument("--verites", default="verites")
    c = sous.add_parser("comparer")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    c.add_argument("--detail", type=int, default=80)
    a = ap.parse_args()
    if a.action == "comparer":
        comparer(a.a, a.b, a.detail)
        return
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    meta = {k: str(w) for k, w in vars(a).items()}
    _preparer(a.code, None)
    if a.action == "jeu":
        taches = []
        exemples = sorted(d for d in (a.dossier / "exemples").iterdir() if d.is_dir())[::a.un_sur]
        lot2 = "lot2" in a.dossier.name
        for ex in exemples:
            f_manifeste = ex / "manifeste.json"  # les jeux de PDF n'en ont pas
            if f_manifeste.exists() and not json.loads(f_manifeste.read_text(encoding="utf-8")).get("accepte", True):
                continue
            for n in sorted(p.name for p in ex.iterdir() if p.is_dir() and p.name.startswith("niveau_")):
                col = None
                if a.coloriages:
                    col = a.coloriages / ex.name / f"{n}.png"
                    if not col.exists():
                        continue
                taches.append((str(ex), n, str(col) if col else None, lot2, a.textes_pdf))
        rs = _executer(_un_niveau_du_jeu, taches, a.sortie, a.processus, a.code, a.cache_ocr)
    elif a.action == "tirages":
        Path(a.dossier).mkdir(parents=True, exist_ok=True)
        graines, g = [], a.depart
        with Pool(a.processus, _preparer, (a.code, None)) as pool:
            while len(graines) < a.nombre:
                lot = list(range(g, g + 60))
                g += 60
                for v_ in pool.map(_poser_tirage, [(x, a.dossier) for x in lot]):
                    if v_ and len(graines) < a.nombre:
                        graines.append(v_["graine"])
        print(f"{len(graines)} tirages, graines {graines[0]} à {graines[-1]}", flush=True)
        rs = _executer(_un_tirage, [(a.dossier, x) for x in graines], a.sortie, a.processus, a.code, a.cache_ocr)
    else:
        repartition = json.loads((Path(a.verites) / "repartition-vrais-plans.json").read_text(encoding="utf-8"))
        examen = plans_d_examen(repartition)
        plans = [p for p in repartition["entrainement"] if p not in examen]
        if len(plans) != len(repartition["entrainement"]):
            raise SystemExit("PLANTÉ : un plan d'examen dans la liste d'entraînement (règle 15)")
        taches = [(p, a.images, a.lectures, a.verites) for p in plans if (Path(a.lectures) / p / "coloriage.png").exists()]
        assert not {t[0] for t in taches} & examen
        rs = _executer(_un_vrai_plan, taches, a.sortie, a.processus, a.code, a.cache_ocr)
    _ecrire(a.sortie, rs, meta)


if __name__ == "__main__":
    main()
