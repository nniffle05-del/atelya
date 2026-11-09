r"""Brique photos : apprendre à l'œil (DINOv2) à reconnaître la famille d'un sol mis à plat (09/11/2026).

    ..\atelya\.venv\Scripts\python.exe outils\habillage\apprendre_sols.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\modeles-sols [--oeil vits14 vitb14]

Deux sources d'exemples, jamais les photos d'app-001 (l'EXAMEN) :
1. les photos de la bibliothèque de matières (CC0), découpées en vignettes d'1 m et ABÎMÉES exprès pour ressembler à un sol mis
   à plat depuis une vraie photo : flou du lointain (étiré dans un sens), détails perdus, couleur et lumière décalées, reflet de
   fenêtre, bruit, compression, et parfois un objet qui cache une partie du sol ;
2. les photos d'essai rendues par Blender (outils/habillage/photos_d_essai.py) : les logements fr-021, fr-024, fr-026 et fr-030
   servent à apprendre, fr-031 et fr-038 au CONTRÔLE (jamais appris), pour choisir le réglage sans tricher.
Les matières dessinées d'après les photos d'app-001 (carreaux_cubes, petits_carreaux_clairs) sont écartées des exemples.

Écrit dans le dossier de sortie : sols-<oeil>.pt (le classificateur et ses notes) et bilan-apprentissage.json.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.images import lire_image  # noqa: E402
from moteur.matieres import CALCULEES, NOMS_SOLS  # noqa: E402
from moteur.oeil_dinov2 import charger, empreintes  # noqa: E402
from moteur.reconnaitre_sols import (FAMILLES, VIGNETTE_M, VIGNETTE_PX, Classifieur, famille,  # noqa: E402
                                     matieres_verite, noter, reconnaitre, vignettes)
from moteur.sol_a_plat import photos_a_plat  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
BIBLIOTHEQUE = RACINE.parent / "atelya" / "bibliotheque" / "matieres"
DESSINEES_D_APRES_APP001 = {"carreaux_cubes", "petits_carreaux_clairs"}
LOGEMENTS_CONTROLE = ("fr-031", "fr-038")
PAR_MATIERE = 160


# ---------------------------------------------------------------- 1. vignettes de la bibliothèque, abîmées
def abimer(v: np.ndarray, alea: random.Random) -> np.ndarray:
    """Rend une vignette propre (vue de dessus parfaite) semblable à un sol mis à plat depuis une photo d'annonce."""
    v = v.astype(np.float32)
    n = v.shape[0]
    # détails perdus (sol vu de loin) puis flou étiré dans un sens (le sol écrasé par la perspective)
    if alea.random() < 0.8:
        f = alea.uniform(1.0, 4.0)
        petit = cv2.resize(v, (max(8, int(n / f)), max(8, int(n / (f * alea.uniform(1.0, 2.5))))), interpolation=cv2.INTER_AREA)
        v = cv2.resize(petit, (n, n), interpolation=cv2.INTER_LINEAR)
    if alea.random() < 0.6:
        k = alea.choice([3, 5, 7, 9])
        noyau = np.zeros((k, k), np.float32)
        noyau[k // 2, :] = 1.0 / k
        rot = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), alea.uniform(0, 180), 1.0)
        v = cv2.filter2D(v, -1, cv2.warpAffine(noyau, rot, (k, k)))
    # couleur et lumière : teinte, clarté, contraste, dégradé de lumière, reflet de fenêtre
    chaud = alea.gauss(0, 0.08)  # lumière plus chaude ou plus froide (rouge contre bleu), plus un petit écart par couleur
    v = v * np.array([math.exp(chaud + alea.gauss(0, 0.04)), math.exp(alea.gauss(0, 0.04)),
                      math.exp(-chaud + alea.gauss(0, 0.04))], np.float32) * alea.uniform(0.6, 1.3)
    v = 255.0 * (np.clip(v, 0, 255) / 255.0) ** alea.uniform(0.75, 1.3)
    a = alea.uniform(0, 2 * math.pi)
    yy, xx = np.mgrid[0:n, 0:n] / n - 0.5
    v = v * (1 + alea.uniform(0, 0.5) * (xx * math.cos(a) + yy * math.sin(a)))[..., None]
    if alea.random() < 0.3:
        b = alea.uniform(0, math.pi)
        d = np.abs(xx * math.cos(b) + yy * math.sin(b) - alea.uniform(-0.3, 0.3))
        v = v + alea.uniform(40, 140) * np.exp(-(d / alea.uniform(0.04, 0.15)) ** 2)[..., None]
    # un objet qui cache un morceau du sol (pied de meuble, tapis, ombre)
    if alea.random() < 0.3:
        pts = np.array([[alea.uniform(0, n), alea.uniform(0, n)] for _ in range(alea.randint(3, 6))], np.int32)
        masque = np.zeros((n, n), np.uint8)
        cv2.fillPoly(masque, [cv2.convexHull(pts)], 1)
        couleur = np.array([alea.uniform(20, 240)] * 3) * np.array([alea.uniform(0.8, 1.2) for _ in range(3)])
        v[masque > 0] = couleur
    v = v + np.random.default_rng(alea.randint(0, 10 ** 9)).normal(0, alea.uniform(0, 6), v.shape)
    v = np.clip(v, 0, 255).astype(np.uint8)
    ok, jpg = cv2.imencode(".jpg", v, [cv2.IMWRITE_JPEG_QUALITY, alea.randint(45, 92)])
    return cv2.imdecode(jpg, cv2.IMREAD_UNCHANGED)


def vignettes_bibliotheque(alea: random.Random, par_matiere: int = PAR_MATIERE):
    infos = json.loads((BIBLIOTHEQUE / "matieres.json").read_text(encoding="utf-8"))
    images, etiquettes = [], []
    for matiere in NOMS_SOLS:
        if matiere in CALCULEES or matiere in DESSINEES_D_APRES_APP001 or matiere not in infos:
            continue
        texture = lire_image(BIBLIOTHEQUE / matiere / "couleur.jpg")
        if texture is None:
            continue
        texture = cv2.cvtColor(texture, cv2.COLOR_BGR2RGB)
        h, w = texture.shape[:2]
        px_par_m = w / infos[matiere]["taille_image_m"][0]
        grand = np.tile(texture, (3, 3, 1))  # les matières se répètent sans raccord visible
        for _ in range(par_matiere):
            echelle = alea.uniform(0.8, 1.25)
            cote = int(VIGNETTE_M / echelle * px_par_m)
            angle = alea.choice([0, 90, 0, 90, alea.uniform(0, 180)])
            large = int(cote * 1.45)
            l0, c0 = alea.randint(0, 3 * h - large - 1), alea.randint(0, 3 * w - large - 1)
            bout = grand[l0:l0 + large, c0:c0 + large]
            rot = cv2.getRotationMatrix2D((large / 2, large / 2), angle, 1.0)
            bout = cv2.warpAffine(bout, rot, (large, large))
            m = (large - cote) // 2
            propre = cv2.resize(bout[m:m + cote, m:m + cote], (VIGNETTE_PX, VIGNETTE_PX), interpolation=cv2.INTER_AREA)
            images.append(abimer(propre, alea))
            etiquettes.append(matiere)
        print(f"  bibliothèque : {matiere} ({famille(matiere)})", flush=True)
    return np.stack(images), np.array(etiquettes)


# ---------------------------------------------------------------- 2. vignettes des photos d'essai (Blender)
def vignettes_essais(dossier: Path, journal=lambda *_: None):
    """Vignettes des photos d'essai mises à plat, étiquetées par la matière du sol (vignettes à cheval sur deux familles
    écartées). Rend (images, matières, logement de chaque vignette, tirage)."""
    images, etiquettes, logements, tirages = [], [], [], []
    for t in sorted(p for p in dossier.iterdir() if (p / "cameras-photos.json").is_file()):
        releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
        logement = json.loads((t / "logement.json").read_text(encoding="utf-8"))
        if not (t / "rendus").is_dir():
            continue
        for nom, _, vue in photos_a_plat(releve, logement, RACINE, journal=journal):
            v, centres, _ = vignettes(vue.image, vue.finesse, vue.resolution, pas_m=0.5)  # moins serré : mémoire
            for image, (l, c) in zip(v, centres):
                # la matière aux 9 points de la moitié centrale de la vignette : tous pareils, sinon vignette écartée
                d = VIGNETTE_M / 4 / vue.resolution
                ll, cc = np.meshgrid([l - d, l, l + d], [c - d, c, c + d])
                X, Y = vue.vers_sol(ll.ravel(), cc.ravel())
                m = set(matieres_verite(logement, X, Y))
                if len(m) == 1 and "" not in m and not (m & DESSINEES_D_APRES_APP001):
                    images.append(image)
                    etiquettes.append(m.pop())
                    logements.append(t.name.rsplit("-t", 1)[0])
                    tirages.append(t.name)
    return np.stack(images), np.array(etiquettes), np.array(logements), np.array(tirages)


# ---------------------------------------------------------------- 3. carte des sols d'un tirage et note
def noter_tirage(t: Path, oeil, clf: Classifieur) -> dict:
    """L'enchaînement complet d'Atelya (moteur.reconnaitre_sols.reconnaitre) sur un tirage, noté contre sa vérité."""
    releve = json.loads((t / "cameras-photos.json").read_text(encoding="utf-8"))
    logement = json.loads((t / "logement.json").read_text(encoding="utf-8"))
    note = noter(reconnaitre(releve, logement, RACINE, oeil, clf), logement)
    return {"m2": note.get("surface_jugee_m2", 0.0), "juste": note.get("surface_juste") or 0.0,
            "pieces_justes": note.get("pieces_justes", "0/0")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Apprendre à l'œil la famille d'un sol mis à plat")
    ap.add_argument("essais", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--oeil", nargs="+", default=["vits14", "vitb14"])
    ap.add_argument("--graine", type=int, default=7)
    args = ap.parse_args()
    alea = random.Random(args.graine)
    np.random.seed(args.graine)
    torch.manual_seed(args.graine)
    args.sortie.mkdir(parents=True, exist_ok=True)
    debut = time.time()
    print("Vignettes de la bibliothèque…", flush=True)
    img_b, mat_b = vignettes_bibliotheque(alea)
    print(f"  {len(img_b)} vignettes ({time.time() - debut:.0f} s)", flush=True)
    print("Vignettes des photos d'essai…", flush=True)
    img_e, mat_e, log_e, tir_e = vignettes_essais(args.essais)
    controle = np.isin(log_e, LOGEMENTS_CONTROLE)
    print(f"  {len(img_e)} vignettes dont {controle.sum()} de contrôle ({time.time() - debut:.0f} s)", flush=True)
    fam = {f: i for i, f in enumerate(FAMILLES)}
    y_b = np.array([fam[famille(m)] for m in mat_b])
    y_e = np.array([fam[famille(m)] for m in mat_e])
    bilan = {"vignettes_bibliotheque": int(len(img_b)), "vignettes_essais_appris": int((~controle).sum()),
             "vignettes_controle": int(controle.sum()), "par_famille_controle": {f: int((y_e[controle] == i).sum()) for f, i in fam.items()},
             "yeux": {}}
    for nom in args.oeil:
        oeil = charger(nom)
        e_b, e_e = empreintes(oeil, img_b), empreintes(oeil, img_e)
        print(f"[{nom}] empreintes faites ({time.time() - debut:.0f} s)", flush=True)
        resultats = {}
        for sources in ("bibliotheque", "bibliotheque+essais"):
            X = e_b if sources == "bibliotheque" else np.concatenate([e_b, e_e[~controle]])
            y = y_b if sources == "bibliotheque" else np.concatenate([y_b, y_e[~controle]])
            clf = Classifieur(X.shape[1], FAMILLES, nom)
            appris = clf.apprendre(X, y)
            p = clf.probabilites(e_e[controle]).argmax(1)
            par_famille = {f: round(float((p[y_e[controle] == i] == i).mean()), 3) if (y_e[controle] == i).any() else None
                           for f, i in fam.items()}
            cartes = [noter_tirage(t, oeil, clf) for t in sorted(args.essais.iterdir())
                      if t.name.rsplit("-t", 1)[0] in LOGEMENTS_CONTROLE and (t / "rendus").is_dir()]
            m2 = sum(c["m2"] for c in cartes)
            pj = [c["pieces_justes"].split("/") for c in cartes]
            r = {"justesse_apprise": round(appris, 3), "vignettes_controle_justes": round(float((p == y_e[controle]).mean()), 3),
                 "par_famille": par_famille,
                 "controle_surface_juste": round(sum(c["m2"] * c["juste"] for c in cartes) / max(m2, 1e-9), 3),
                 "controle_m2": round(m2, 1),
                 "controle_pieces_justes": f"{sum(int(a) for a, _ in pj)}/{sum(int(b) for _, b in pj)}"}
            print(f"[{nom}] {sources} : {r}", flush=True)
            resultats[sources] = r
            torch.save({**clf.etat(), "sources": sources, "controle": r}, args.sortie / f"sols-{nom}-{sources.replace('+', '-')}.pt")
        bilan["yeux"][nom] = resultats
        del oeil
        torch.cuda.empty_cache()
    (args.sortie / "bilan-apprentissage.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FINI en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
