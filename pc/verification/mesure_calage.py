"""Étape 3 : mesure, sur des plans fabriqués, où l'écran de vérification dessine les murs lus par rapport aux vrais murs.

Chaque plan passe par la vraie chaîne (lire_plan puis verification_du_plan, comme pour un client) ; on ne garde que la
matrice du fichier de l'écran. Un mur lu qui ne correspond à aucun vrai mur est compté à part : c'est une erreur de
lecture, pas de calage.

    ..\\atelya\\.venv\\Scripts\\python.exe pc\\verification\\mesure_calage.py --minutes 25 --par-groupe 15
"""
from __future__ import annotations

import argparse
import ctypes
import json
import random
import statistics as st
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, ".")
sys.path.insert(0, "outils/atelya")

A = Path("../atelya")
SORTIE = A / "calage-verification"
ANGLE_MAX_DEG = 15.0  # un mur lu et un vrai mur de directions plus différentes ne sont pas le même mur
MARIAGE_MAX_M = 0.40  # au-delà, le mur lu ne correspond à aucun vrai mur : erreur de lecture
ECHANTILLONS = (0.2, 0.35, 0.5, 0.65, 0.8)  # points pris sur le mur lu, loin des coins


def axe_du_polygone(poly: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """La ligne médiane d'un vrai mur : relie le milieu de ses deux petits côtés."""
    if len(poly) != 4:
        poly = cv2.boxPoints(cv2.minAreaRect(poly.astype(np.float32))).astype(float)
    cotes = [np.linalg.norm(poly[(i + 1) % 4] - poly[i]) for i in range(4)]
    i = 0 if cotes[0] + cotes[2] < cotes[1] + cotes[3] else 1
    return (poly[i] + poly[(i + 1) % 4]) / 2, (poly[(i + 2) % 4] + poly[(i + 3) % 4]) / 2


def mesurer_murs(murs_lus_px: list, vrais_murs: list, px_par_m: float) -> dict:
    """Pour chaque mur lu (deux points en pixels) : écart perpendiculaire à la ligne médiane du vrai mur le plus proche."""
    vrais = []
    for m in vrais_murs:
        poly = np.array(m["polygone_px"], float)
        a, b = axe_du_polygone(poly)
        vrais.append((a, b, poly.astype(np.float32)))
    ecarts, dedans, signes_x, signes_y, en_trop = [], [], [], [], 0
    for debut, fin in murs_lus_px:
        d, f = np.array(debut, float), np.array(fin, float)
        longueur = np.linalg.norm(f - d)
        if longueur < 1:
            continue
        sens = (f - d) / longueur
        meilleur = None
        for a, b, poly in vrais:
            longueur_v = np.linalg.norm(b - a)
            if longueur_v < 1:
                continue
            sens_v = (b - a) / longueur_v
            if abs(float(sens @ sens_v)) < np.cos(np.radians(ANGLE_MAX_DEG)):
                continue
            normale = np.array([-sens_v[1], sens_v[0]])
            pts = [d + (f - d) * t for t in ECHANTILLONS]
            # seuls comptent les points qui tombent en face du vrai mur
            en_face = [p for p in pts if -2 <= float((p - a) @ sens_v) <= longueur_v + 2]
            if not en_face:
                continue
            distances = [float((p - a) @ normale) for p in en_face]
            moyenne = abs(float(np.mean(distances)))
            if meilleur is None or moyenne < meilleur[0]:
                meilleur = (moyenne, distances, en_face, normale, poly)
        if meilleur is None or meilleur[0] > MARIAGE_MAX_M * px_par_m:
            en_trop += 1
            continue
        _, distances, en_face, normale, poly = meilleur
        ecarts.append(float(np.median(np.abs(distances))))
        dedans.append(np.mean([cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), False) >= 0 for p in en_face]))
        signe = -float(np.median(distances))  # du dessin vers le vrai mur
        if abs(normale[0]) > abs(normale[1]):
            signes_x.append(signe * np.sign(normale[0]))
        else:
            signes_y.append(signe * np.sign(normale[1]))
    return {"ecarts_px": ecarts, "dedans": dedans, "biais_x_px": float(np.median(signes_x)) if signes_x else 0.0,
            "biais_y_px": float(np.median(signes_y)) if signes_y else 0.0, "en_trop": en_trop}


def controle_de_la_mesure() -> None:
    """La mesure elle-même doit être juste : 0 si on lui donne les vrais murs, 7 si on les décale de 7 pixels."""
    h = {"polygone_px": [[100, 100], [500, 100], [500, 120], [100, 120]]}
    v = {"polygone_px": [[100, 100], [120, 100], [120, 400], [100, 400]]}
    exact = mesurer_murs([((100, 110), (500, 110)), ((110, 100), (110, 400))], [h, v], 100)
    assert max(exact["ecarts_px"]) < 1e-6 and exact["en_trop"] == 0 and min(exact["dedans"]) == 1, exact
    decale = mesurer_murs([((100, 117), (500, 117)), ((117, 100), (117, 400))], [h, v], 100)
    assert abs(decale["ecarts_px"][0] - 7) < 1e-6 and abs(decale["ecarts_px"][1] - 7) < 1e-6, decale
    assert abs(decale["biais_x_px"] + 7) < 1e-6 and abs(decale["biais_y_px"] + 7) < 1e-6, decale
    trop = mesurer_murs([((100, 300), (500, 300))], [h], 100)
    assert trop["en_trop"] == 1 and not trop["ecarts_px"], trop
    print("Contrôle de la mesure : OK (0 px sur les vrais murs, 7 px sur des murs décalés de 7, mur inventé écarté)", flush=True)


def lister_groupes(par_groupe: int) -> dict[str, list]:
    alea = random.Random(1)
    groupes: dict[str, list] = {k: [] for k in ("droit", "penche", "photo_biais", "photo_realiste", "murs_biais", "murs_biais_photo",
                                                "pdf_vectorielle", "pdf_scannee", "pdf_tournee")}

    def fichier_plan(niveau: Path) -> Path | None:
        return next((p for p in (niveau / "plan.png", niveau / "plan.jpg") if p.exists()), None)

    for ann in sorted((A / "jeu-test-6-13" / "exemples").glob("*/niveau_*/annotations.json")):
        im = json.loads(ann.read_text(encoding="utf-8"))["image"]
        cle = "photo_biais" if im["perspective"] > 0 else "penche" if abs(im["rotation_deg"]) >= 0.3 else "droit" if im.get("a_plat", True) or abs(im["rotation_deg"]) < 0.01 else None
        plan = fichier_plan(ann.parent)
        if cle and plan:
            groupes[cle].append((plan, ann))
    for cle, jeu in (("photo_realiste", "photos-reel-test-cotes"), ("murs_biais", "biais-test-a3"), ("murs_biais_photo", "biais-photos-test-a3")):
        for ann in sorted((A / "donnees" / jeu / "exemples").glob("*/niveau_*/annotations.json")):
            plan = fichier_plan(ann.parent)
            if plan:
                groupes[cle].append((plan, ann))
    for ann in sorted((A / "jeu-pdf-a2" / "exemples").glob("*/niveau_*/annotations.json")):
        plan_id, _, sorte = ann.parents[1].name.partition("-")
        pdf = A / "pdf-test-a2" / "exemples" / plan_id / ann.parent.name / f"plan-{sorte}.pdf"
        cle = {"vectorielle": "pdf_vectorielle", "scannee": "pdf_scannee", "tournee": "pdf_tournee"}.get(sorte)
        if cle and pdf.exists():
            groupes[cle].append((pdf, ann))
    for cle, liste in groupes.items():
        alea.shuffle(liste)
        print(f"{cle} : {len(liste)} disponibles", flush=True)
        groupes[cle] = liste[:par_groupe]
    return groupes


def vrais_murs(ann: dict, ann_fichier: Path) -> list:
    """Les vrais murs en pixels. Les annotations d'un PDF ne gardent que le cadre du logement : on repart du vrai logement."""
    if "pdf" not in ann:
        return ann["murs"]
    M = np.array(ann["image"]["matrice_m_vers_px"], float)
    logement = json.loads((ann_fichier.parents[1] / f"logement_niveau{ann['niveau']}.json").read_text(encoding="utf-8"))
    murs = []
    for m in logement["murs"]:
        d, f = np.array(m["debut"], float), np.array(m["fin"], float)
        normale = np.array([-(f - d)[1], (f - d)[0]]) / np.linalg.norm(f - d) * m["epaisseur"] / 2
        coins = [d + normale, f + normale, f - normale, d - normale]
        pts = [M @ (c[0], c[1], 1.0) for c in coins]
        murs.append({"polygone_px": [[float(p[0] / p[2]), float(p[1] / p[2])] for p in pts]})
    return murs


def apercu(chemin: Path, image: np.ndarray, murs_px: list, vrais: list) -> None:
    img = Image.fromarray(image).convert("RGB")
    d = ImageDraw.Draw(img)
    ep = max(1, max(img.size) // 800)
    for m in vrais:
        d.polygon([tuple(p) for p in m["polygone_px"]], outline=(30, 170, 80))
    for a, b in murs_px:
        d.line([tuple(a), tuple(b)], fill=(230, 30, 30), width=ep)
    img.thumbnail((1400, 1400))
    img.save(chemin)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=25)
    ap.add_argument("--par-groupe", type=int, default=15)
    a = ap.parse_args()
    controle_de_la_mesure()
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # pas de veille pendant ce calcul

    from lire_plan import colorieurs
    from moteur.lecture_complete import lire_plan, plans_du_fichier
    from moteur.preparer_verification import projeter, verification_du_plan

    SORTIE.mkdir(exist_ok=True)
    (SORTIE / "pires").mkdir(exist_ok=True)
    groupes = lister_groupes(a.par_groupe)
    fonctions = colorieurs(A, ["e5", "e7"])
    t0 = time.time()
    lignes = []
    journal = (SORTIE / "resultats.jsonl").open("w", encoding="utf-8")
    for rang in range(a.par_groupe):  # un plan de chaque groupe à tour de rôle : tous les groupes sont vus même si le temps manque
        for groupe, liste in groupes.items():
            if rang >= len(liste):
                continue
            if time.time() - t0 > a.minutes * 60:
                continue
            fichier, ann_fichier = liste[rang]
            ann = json.loads(ann_fichier.read_text(encoding="utf-8"))
            t = time.time()
            source = plans_du_fichier(fichier)[0]
            h, l = source.image.shape[:2]
            if (l, h) != (ann["image"]["largeur"], ann["image"]["hauteur"]):
                print(f"PLANTÉ : {fichier} : image {l}x{h}, vérité {ann['image']['largeur']}x{ann['image']['hauteur']} : on ne compare pas la même chose", flush=True)
                return 3
            plan = lire_plan(source, fonctions, avec_noms=False)
            v = verification_du_plan(plan)
            if v is None:
                lignes.append({"groupe": groupe, "plan": str(fichier), "refuse": True})
                journal.write(json.dumps(lignes[-1], ensure_ascii=False) + "\n")
                journal.flush()
                print(f"{groupe} {fichier.parent.parent.name} : refusé, rien à dessiner", flush=True)
                continue
            M = np.array(v["calage"]["matrice"])
            murs_px = [(projeter(M, *m["debut"]), projeter(M, *m["fin"])) for m in v["logement"]["murs"]]
            vrais = vrais_murs(ann, ann_fichier)
            r = mesurer_murs(murs_px, vrais, ann["image"]["px_par_m"])
            px_coloriage = max(h, l) / max(plan.gardee.coloriage.shape[:2])
            ligne = {"groupe": groupe, "plan": str(fichier), "ecart_px": st.median(r["ecarts_px"]) if r["ecarts_px"] else None,
                     "max_px": max(r["ecarts_px"]) if r["ecarts_px"] else None, "dedans": float(np.mean(r["dedans"])) if r["dedans"] else None,
                     "biais_x_px": r["biais_x_px"], "biais_y_px": r["biais_y_px"], "en_trop": r["en_trop"], "murs": len(r["ecarts_px"]),
                     "ecarts_px": r["ecarts_px"], "px_par_m": ann["image"]["px_par_m"], "px_coloriage": px_coloriage, "modele": plan.gardee.modele,
                     "redresse": plan.gardee.redressement is not None, "duree_s": round(time.time() - t, 1)}
            lignes.append(ligne)
            journal.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            journal.flush()
            nom = f"{groupe}-{fichier.parent.parent.name}-{fichier.parent.name}"
            apercu(SORTIE / "pires" / f"{nom}.png", source.image, murs_px, vrais)
            med = "?" if ligne["ecart_px"] is None else f"{ligne['ecart_px']:.1f}"
            print(f"{groupe} {nom} : écart médian {med} px ({ligne['murs']} murs, {ligne['en_trop']} en trop), {ligne['duree_s']} s", flush=True)
    journal.close()

    print("\nGROUPE            plans  refusés  écart médian  pire plan   dans le mur  décalage du plan   en trop", flush=True)
    bilan = {}
    for groupe in groupes:
        g = [x for x in lignes if x["groupe"] == groupe]
        ok = [x for x in g if not x.get("refuse") and x["ecart_px"] is not None]
        if not ok:
            print(f"{groupe:<17} {len(g):>5}  rien à mesurer", flush=True)
            continue
        en_cm = [e / x["px_par_m"] * 100 for x in ok for e in x["ecarts_px"]]
        biais = [max(abs(x["biais_x_px"]), abs(x["biais_y_px"])) / x["px_coloriage"] for x in ok]
        bilan[groupe] = {"plans": len(g), "refuses": len(g) - len(ok), "ecart_median_cm": st.median(en_cm),
                         "ecart_p95_cm": float(np.percentile(en_cm, 95)), "pire_plan_px": max(x["ecart_px"] for x in ok),
                         "dans_le_mur_pct": 100 * float(np.mean([x["dedans"] for x in ok])),
                         "decalage_median_px_coloriage": st.median(biais), "decalage_max_px_coloriage": max(biais),
                         "murs_mesures": sum(x["murs"] for x in ok), "murs_en_trop": sum(x["en_trop"] for x in ok)}
        b = bilan[groupe]
        print(f"{groupe:<17} {b['plans']:>5}  {b['refuses']:>7}  {b['ecart_median_cm']:>6.1f} cm     {b['pire_plan_px']:>6.1f} px  {b['dans_le_mur_pct']:>8.1f} %"
              f"   méd {b['decalage_median_px_coloriage']:.2f} max {b['decalage_max_px_coloriage']:.2f}  {b['murs_en_trop']:>5}/{b['murs_mesures']}", flush=True)
    (SORTIE / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FINI : {len(lignes)} plans en {(time.time() - t0) / 60:.1f} min. Détail : {SORTIE}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("PLANTÉ : mesure du calage", flush=True)
        raise
