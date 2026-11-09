r"""Photos d'essai pour la brique photos : des intérieurs rendus par Blender dont on connaît les sols (09/11/2026).

Pourquoi : pour mettre au point la reconnaissance des sols sans regarder les photos d'app-001 (elles restent l'EXAMEN), il
faut des photos dont on connaît la bonne réponse. On prend les maquettes d'autres logements, on donne à chaque pièce un sol
tiré au hasard dans le catalogue (parfois un second sol sur une partie de la pièce, comme une cuisine ouverte), et on pose des
caméras « de photographe » (de niveau, à hauteur d'homme, grand angle). Blender rend les photos ; la caméra de chacune est
connue exactement.

    ..\atelya\.venv\Scripts\python.exe outils\habillage\photos_d_essai.py ..\atelya\b2\brique-photos-essais ^
        ..\atelya\lectures-claude\fr-021\logement.json ... [--tirages 2] [--graine 1]

Chaque tirage écrit dans <sortie>\<logement>-t<n>\ : logement.json (la vérité : sol de chaque pièce et zones), construction\
(maquette), cameras-photos.json (même format que verites\app-001\cameras-photos.json) et rendus\vue-<photo>.png.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.matieres import NOMS_SOLS  # noqa: E402
from moteur.sol_a_plat import dans_polygone, mettre_a_plat  # noqa: E402

LARGEUR, HAUTEUR = 1206, 804  # comme les photos d'annonce d'app-001
ECLAIRAGES = ("1 Jour ensoleillé", "2 Jour voilé", "3 Fin de journée")
ECHANTILLONS = 96


def aire(contour) -> float:
    c = np.asarray(contour, float)
    return abs(float((c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1]).sum())) / 2


def sol_au_hasard(alea: random.Random, eviter: str | None = None) -> dict:
    from moteur.reconnaitre_sols import famille
    choix = [m for m in NOMS_SOLS if eviter is None or famille(m) != famille(eviter)]
    matiere = alea.choice(choix)
    commun = alea.gauss(0, 0.18)
    teinte = [round(min(1.8, max(0.4, math.exp(commun + alea.gauss(0, 0.06)))), 3) for _ in range(3)]
    return {"matiere": matiere, "teinte": teinte, "echelle": round(alea.uniform(0.8, 1.25), 2), "statut": "mesure",
            "source": "photos d'essai (tirage au hasard)"}


def zone_au_hasard(alea: random.Random, contour, sol_piece: dict) -> dict:
    """Un rectangle d'un autre sol sur 30 à 60 % de la pièce, du côté d'un de ses bords (le reste est coupé à la construction)."""
    c = np.asarray(contour, float)
    x0, y0, x1, y1 = c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()
    part = alea.uniform(0.3, 0.6)
    if x1 - x0 >= y1 - y0:
        coupe = x0 + part * (x1 - x0)
        r = [[x0, y0], [coupe, y0], [coupe, y1], [x0, y1]] if alea.random() < 0.5 else [[coupe, y0], [x1, y0], [x1, y1], [coupe, y1]]
    else:
        coupe = y0 + part * (y1 - y0)
        r = [[x0, y0], [x1, y0], [x1, coupe], [x0, coupe]] if alea.random() < 0.5 else [[x0, coupe], [x1, coupe], [x1, y1], [x0, y1]]
    return {"contour": [[round(x, 3), round(y, 3)] for x, y in r], "sol": sol_au_hasard(alea, eviter=sol_piece["matiere"])}


def distance_aux_bords(point, contour) -> float:
    p = np.asarray(point, float)
    c = np.asarray(contour, float)
    d = math.inf
    for a, b in zip(c, np.roll(c, -1, axis=0)):
        ab = b - a
        t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = min(d, float(np.linalg.norm(p - (a + t * ab))))
    return d


def cameras_au_hasard(alea: random.Random, piece: dict, combien: int, emprises=()) -> list[list[float]]:
    """Caméras de photographe dans la pièce, chacune voyant au moins 3 m² de son sol, jamais dans un meuble."""
    c = np.asarray(piece["contour"], float)
    sorties, essais = [], 0
    while len(sorties) < combien and essais < 200:
        essais += 1
        x, y = alea.uniform(c[:, 0].min(), c[:, 0].max()), alea.uniform(c[:, 1].min(), c[:, 1].max())
        if not dans_polygone(np.array([x]), np.array([y]), c)[0] or distance_aux_bords((x, y), c) < 0.4:
            continue
        if any(dans_polygone(np.array([x]), np.array([y]), e)[0] for e in emprises):
            continue
        champ = math.radians(alea.uniform(70, 100))
        f = LARGEUR / 2 / math.tan(champ / 2)
        cam = [x, y, alea.uniform(0.95, 1.45), alea.uniform(-180, 180), alea.uniform(-8, 0) if alea.random() < 0.3 else 0.0,
               f, LARGEUR / 2, HAUTEUR / 2 + alea.uniform(-60, 20)]
        vu = mettre_a_plat(np.zeros((HAUTEUR, LARGEUR, 3), np.uint8), cam, c, resolution=0.05)
        if (vu.finesse > 0).sum() * 0.0025 >= 3.0:
            sorties.append([round(float(v), 4) for v in cam])
    return sorties


# ---------------------------------------------------------------- meubles au hasard (B4, 09/11/2026)
CONTRE_UN_MUR = ("canape", "lit", "commode", "bibliotheque", "rangement", "meuble_tv", "etagere_cubes", "bureau", "banc",
                 "table_de_chevet", "lampadaire", "plante", "lit_superpose")
AU_MILIEU = ("table_basse", "fauteuil", "table", "table_d_appoint", "chaise")


def rectangle(position, face, largeur, profondeur):
    a = math.radians(face)
    av, cote = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
    c = np.asarray(position, float)
    return [list(c + sl * largeur / 2 * cote + sp * profondeur / 2 * av) for sl, sp in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _dedans(point, contour) -> bool:
    return bool(dans_polygone(np.array([point[0]]), np.array([point[1]]), contour)[0])


def meubles_au_hasard(alea: random.Random, logement: dict, liste: list[dict]) -> list[dict]:
    """Des meubles ABO tirés au hasard dans chaque pièce (contre un mur ou au milieu ; souvent un tapis ; une table avec ses
    chaises), sans chevauchement (grille de 5 cm), aux dimensions réelles du modèle tiré. Le type de pièce n'impose rien."""
    from moteur.meubles import candidats
    par_categorie = {c: candidats(c, liste) for c in (*CONTRE_UN_MUR, *AU_MILIEU, "tapis")}
    hsp = logement["hauteur_sous_plafond"]
    sortie = []

    def modele(cat, place_max):
        for _ in range(20):
            if not par_categorie[cat]:
                return None
            e = alea.choice(par_categorie[cat])
            l, h, p = e["size_metres"]
            if 0.15 < l <= place_max and 0.05 < p <= place_max and h < hsp - 0.1:
                return e, (round(l, 3), round(p, 3), round(h, 3))
        return None

    for piece in logement["pieces"]:
        c = np.asarray(piece["contour"], float)
        a = aire(c)
        if a < 3:
            continue
        x0, y0, x1, y1 = c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()
        gx, gy = np.meshgrid(np.arange(x0, x1, 0.05) + 0.025, np.arange(y0, y1, 0.05) + 0.025)
        libre = dans_polygone(gx, gy, c)

        def poser(cat, e, dims, position, face, occupe=True):
            rect = rectangle(position, face, dims[0], dims[1])
            dedans = dans_polygone(gx, gy, rect)
            if not dedans.any() or not libre[dedans].all() or not all(_dedans(q, c) for q in rect):
                return False
            if occupe:
                libre[dedans] = False
            sortie.append({"id": f"{piece['id']}__m{len(sortie) + 1}", "categorie": cat, "piece": piece["id"],
                           "position": [round(float(v), 3) for v in position], "face": round(float(face), 1),
                           "dimensions": list(dims), "modele": e["id"], "statut": "ajoute", "source": "photos d'essai (hasard)"})
            return True

        if alea.random() < 0.6:  # un tapis au milieu (les autres meubles peuvent le chevaucher)
            m = modele("tapis", min(x1 - x0, y1 - y0) - 0.6)
            if m:
                centre = (alea.uniform(x0 + 1, x1 - 1) if x1 - x0 > 2 else (x0 + x1) / 2,
                          alea.uniform(y0 + 1, y1 - 1) if y1 - y0 > 2 else (y0 + y1) / 2)
                poser("tapis", *m, centre, alea.choice([0, 90]), occupe=False)
        for _ in range(max(1, min(7, int(a / 3.5)))):
            for _essai in range(25):
                if alea.random() < 0.6:
                    cat = alea.choice(CONTRE_UN_MUR)
                    m = modele(cat, 3.2)
                    if not m:
                        break
                    i = alea.randrange(len(c))
                    A, B = c[i], c[(i + 1) % len(c)]
                    long = float(np.linalg.norm(B - A))
                    if long < m[1][0] + 0.2:
                        continue
                    u = (B - A) / long
                    n = np.array([-u[1], u[0]])
                    milieu = A + u * alea.uniform(m[1][0] / 2 + 0.05, long - m[1][0] / 2 - 0.05)
                    if not _dedans(milieu + 0.1 * n, c):
                        n = -n
                    if poser(cat, *m, milieu + n * (m[1][1] / 2 + 0.03), math.degrees(math.atan2(n[1], n[0]))):
                        break
                else:
                    cat = alea.choice(AU_MILIEU)
                    m = modele(cat, 2.4)
                    if not m:
                        break
                    position = (alea.uniform(x0 + 0.5, x1 - 0.5), alea.uniform(y0 + 0.5, y1 - 0.5))
                    face = alea.choice([0, 90, 180, -90, alea.uniform(-180, 180)])
                    if poser(cat, *m, position, face):
                        if cat == "table":  # ses chaises, de part et d'autre
                            mc = modele("chaise", 0.8)
                            if mc:
                                av = np.array([math.cos(math.radians(face)), math.sin(math.radians(face))])
                                for sens in (1, -1):
                                    q = np.asarray(position) + sens * av * (m[1][1] / 2 + mc[1][1] / 2 + 0.05)
                                    poser("chaise", *mc, q, face + (180 if sens > 0 else 0))
                        break
    return sortie


def tirage(logement: dict, alea: random.Random, liste_meubles: list[dict] | None = None) -> tuple[dict, dict]:
    """Le logement avec des sols (et, si liste_meubles, des meubles) tirés au hasard, et les caméras (cameras-photos.json)."""
    from moteur.camera_photo import NOMS
    logement = json.loads(json.dumps(logement))
    cameras = {}
    logement["meubles"] = meubles_au_hasard(alea, logement, liste_meubles) if liste_meubles else []
    emprises = [rectangle(m["position"], m["face"], m["dimensions"][0] + 0.5, m["dimensions"][1] + 0.5)
                for m in logement["meubles"] if m["categorie"] != "tapis"]
    for p in logement["pieces"]:
        p["sol"] = sol_au_hasard(alea)
        p["zones_sol"] = [zone_au_hasard(alea, p["contour"], p["sol"])] if aire(p["contour"]) >= 10 and alea.random() < 0.4 else []
        a = aire(p["contour"])
        combien = 0 if a < 4 else (1 if a < 12 else 2)
        for k, cam in enumerate(cameras_au_hasard(alea, p, combien, emprises), start=1):
            cameras[f"{p['id']}-{k}"] = {"camera": dict(zip(NOMS, cam)), "largeur": LARGEUR, "hauteur": HAUTEUR}
    return logement, cameras


def main() -> int:
    ap = argparse.ArgumentParser(description="Photos d'essai rendues par Blender, sols connus")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("logements", type=Path, nargs="+")
    ap.add_argument("--tirages", type=int, default=2)
    ap.add_argument("--graine", type=int, default=1)
    ap.add_argument("--meubles", action="store_true", help="meubler les pièces au hasard (bibliothèque ABO) + masques des meubles")
    args = ap.parse_args()
    from moteur.construire import DOSSIER_SCRIPTS, construire, lancer_blender, trouver_meubles
    from outils.habillage.caler_photos import rendre
    alea = random.Random(args.graine)
    liste_meubles = None
    if args.meubles:
        from moteur.meubles import charger_liste
        bibliotheque = trouver_meubles()
        if bibliotheque is None:
            print("PLANTÉ : bibliothèque de meubles ABO introuvable", flush=True)
            return 2
        liste_meubles = charger_liste(bibliotheque)
    for chemin in args.logements:
        if not chemin.is_file():
            print(f"PLANTÉ : logement introuvable : {chemin}", flush=True)
            return 2
        base = json.loads(chemin.read_text(encoding="utf-8"))
        for t in range(1, args.tirages + 1):
            debut = time.time()
            dossier = args.sortie / f"{chemin.parent.name}-{'m' if args.meubles else 't'}{t}"
            dossier.mkdir(parents=True, exist_ok=True)
            logement, cameras = tirage(base, alea, liste_meubles)
            (dossier / "logement.json").write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
            maquette = construire(dossier / "logement.json", dossier / "construction")
            scene = alea.choice(ECLAIRAGES)
            releve = {"photos": str((dossier / "rendus").resolve()), "fichier": "vue-{nom}.png", "eclairage": scene,
                      "cameras": cameras}
            (dossier / "cameras-photos.json").write_text(json.dumps(releve, ensure_ascii=False, indent=1), encoding="utf-8")
            rendre(releve, maquette, dossier, ECHANTILLONS, scene)
            if args.meubles:
                lancer_blender(str(dossier / "maquette-photos.blend"), "--python", str(DOSSIER_SCRIPTS / "masques_meubles.py"),
                               "--", str((dossier / "masques").resolve()))
            print(f"{dossier.name} : {len(cameras)} photos, {len(logement['meubles'])} meubles ({scene}) "
                  f"en {time.time() - debut:.0f} s", flush=True)
    print("FINI", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # règle 6 : une ligne claire en cas de plantage
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
