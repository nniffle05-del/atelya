r"""MESURE (28/11/2026) : l'appareil d'une photo de CUISINE repris sur les éléments rangés (moteur/appareil_sur_rangees.py).

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\cuisine.py [--cas app-001 app-002 app-004] [--images <dossier>]

Pour chaque photo qui dit ses rangées de cuisine : l'appareil d'Atelya (celui de la chaîne à l'étape « appareils ») est repris
sur les éléments rangés et les lignes lues de ses fenêtres ; on compare, avant et après, à l'appareil relevé à la main (en
mètres) et aux REPÈRES marqués à la main sur la photo (en pixels : le juge le plus sûr). « DERNIER RECOURS » = les photos que
la chaîne reprend vraiment (affinage resté « depart » ou « lus »). Rien n'est écrit dans Atelya.
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "pc" / "essais-place-appareils"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PC = RACINE.parent / "atelya"
CHAINE = PC / "b2" / "place-appareils" / "chaine"
CAS = {
    "app-001": {"chaine": CHAINE / "sol-partout" / "app-001" / "c", "main": [RACINE / "verites/app-001/cameras-photos.json"]},
    "app-002": {"chaine": CHAINE / "sol-partout" / "app-002" / "c",
                "main": [RACINE / "verites/app-002/cameras-photos-soigne.json", RACINE / "verites/app-002/cameras-photos.json"]},
    "app-004": {"chaine": CHAINE / "ouverts" / "app-004" / "c", "main": []},
}


def lire(f: Path) -> dict:
    return json.loads(Path(f).read_text(encoding="utf-8"))


def main() -> int:
    from poser_photos_lues import objets_des_photos, rangees_des_photos

    from moteur import appareil_sur_rangees as ar
    from moteur import affiner_appareils as aa
    from moteur.images import lire_image

    args = sys.argv[1:]
    cas = args[args.index("--cas") + 1:] if "--cas" in args else list(CAS)
    cas = [c for c in cas if not c.startswith("--")]
    images = Path(args[args.index("--images") + 1]) if "--images" in args else None
    bilan, pixels = [], []
    for c in cas:
        d = CAS[c]
        fiche, logement = lire(d["chaine"] / "cameras-photos-affinees.json"), lire(d["chaine"] / "logement-sols.json")
        lecture = PC / "lectures-photos" / c
        objets, rangees = objets_des_photos(fiche, lecture), rangees_des_photos(fiche, lecture)
        vitrages = lire(lecture / "vitrages.json")["photos"] if (lecture / "vitrages.json").is_file() else {}
        scene, vide = aa.Scene(logement), {"plafond": np.zeros((0, 2)), "sol": np.zeros((0, 2))}
        mains, reperes = {}, {}
        for f in reversed(d["main"]):
            mains.update({n: v["camera"] for n, v in lire(f)["cameras"].items()})
        for f in d["main"]:  # les repères marqués à la main sur la photo (le relevé le plus ancien en a pour les cuisines)
            for n, v in lire(f)["cameras"].items():
                if v.get("reperes"):
                    reperes[n] = v["reperes"]
        for nom in sorted(rangees):
            image = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
            hauteur, largeur = image.shape[:2]
            cam = fiche["cameras"][nom]["camera"]
            boites = {int(o["numero"]): o["boite"] for o in objets.get(nom) or []}
            # les lignes lues des fenêtres de la photo, quand la lecture en a : les deux écarts sont réduits ensemble
            reps = aa.reperes_lus(logement, vitrages.get(nom) or []) if vitrages.get(nom) else []
            lignes = (lambda k: aa.cout(np.array(k, float), scene, vide, reps)) if reps else None
            comment = (fiche["cameras"][nom].get("affine") or {}).get("comment", "?")
            r = ar.affiner(cam, rangees[nom], boites, largeur, hauteur, logement, journal=lambda *a: None, lignes=lignes)
            recours = comment in ("depart", "lus")  # le calage n'a pas trouvé de murs où s'accrocher : dernier recours
            ligne = f"{c} {nom} [{comment}{' : DERNIER RECOURS' if recours else ''}] : "
            if r is None:
                print(ligne + "rien à faire (pas d'élément rangé visible)", flush=True)
                continue
            apres = r["camera"]
            ligne += (f"appareil ({cam['x']:.2f} ; {cam['y']:.2f}) cap {cam['cap']:.0f}° f {cam['f']:.0f} → ({apres['x']:.2f} ; {apres['y']:.2f}) "
                      f"cap {apres['cap']:.0f}° f {apres['f']:.0f} | écart aux rectangles {r['avant']:.0f} → {r['apres']:.0f} px "
                      f"({r['elements']} élément(s), {r['bords']} bord(s))" + (f" ; lignes lues {r['lignes'][0]:.0f} → {r['lignes'][1]:.0f} px" if r.get("lignes") else "")
                      + ("" if r["garde"] else " | NON GARDÉ : " + r["raison"]))
            m = mains.get(nom)
            if m:
                e0 = math.hypot(cam["x"] - m["x"], cam["y"] - m["y"])
                e1 = math.hypot(apres["x"] - m["x"], apres["y"] - m["y"])
                a0 = abs((cam["cap"] - m["cap"] + 180) % 360 - 180)
                a1 = abs((apres["cap"] - m["cap"] + 180) % 360 - 180)
                ligne += f" | contre la main ({m['x']:.2f} ; {m['y']:.2f}, cap {m['cap']:.0f}°) : {e0:.2f} m, {a0:.0f}° → {e1:.2f} m, {a1:.0f}°"
                bilan.append((e0, e1, a0, a1, r["garde"]))
            if reperes.get(nom):
                from juger import ecarts_px
                from moteur.camera_photo import camera_depuis_dict
                p0 = float(np.mean(ecarts_px(camera_depuis_dict(cam), reperes[nom])))
                p1 = float(np.mean(ecarts_px(camera_depuis_dict(apres), reperes[nom])))
                pm = float(np.mean(ecarts_px(camera_depuis_dict(m), reperes[nom]))) if m else float("nan")
                ligne += f" | repères à la main ({len(reperes[nom])}) : {p0:.0f} → {p1:.0f} px (appareil à la main : {pm:.0f})"
                pixels.append((p0, p1, r["garde"] and recours))
            print(ligne, flush=True)
            if images is not None:
                images.mkdir(parents=True, exist_ok=True)
                ar.dessiner(image, cam, apres, r["vus"], images / f"{c}-{nom}.jpg")
    if bilan:
        print(f"contre la main, {len(bilan)} photo(s) : place {sum(b[0] for b in bilan) / len(bilan):.2f} → {sum(b[1] for b in bilan) / len(bilan):.2f} m ; "
              f"cap {sum(b[2] for b in bilan) / len(bilan):.0f} → {sum(b[3] for b in bilan) / len(bilan):.0f}°", flush=True)
    if pixels:
        print(f"repères à la main, {len(pixels)} photo(s) : {sum(p[0] for p in pixels) / len(pixels):.0f} → {sum(p[1] for p in pixels) / len(pixels):.0f} px ; "
              f"dernier recours et gardées : {sum(p[0] for p in pixels if p[2]) / max(1, sum(1 for p in pixels if p[2])):.0f} → "
              f"{sum(p[1] for p in pixels if p[2]) / max(1, sum(1 for p in pixels if p[2])):.0f} px", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
