r"""Caméras des photos du client (B2 temps 2, étape 4, 09/11/2026) : contrôle du calage, rendus de la maquette depuis le même
endroit que chaque photo, planche « photo / maquette » côte à côte.

Le relevé (JSON, ex. verites\app-001\cameras-photos.json) donne pour chaque photo la caméra retrouvée et les repères qui ont
servi (voir moteur/camera_photo.py).

    # 1. contrôle : les arêtes de la maquette dessinées sur la photo (jaune = pieds de murs, bleu ciel = hauts de murs,
    #    violet = angles verticaux, bleu = fenêtres, vert = portes, rouge = repères relevés)
    python outils\habillage\caler_photos.py dessiner verites\app-001\cameras-photos.json ..\atelya\lectures-claude\app-001\logement-sols.json photo-03 sortie.png
    # 2. caméras posées dans une COPIE de la maquette + rendus (Cycles, réglage « de photographe » de rendre.py)
    python outils\habillage\caler_photos.py rendre verites\app-001\cameras-photos.json ..\atelya\lectures-claude\app-001\3d-sols\maquette.blend ..\atelya\b2\app-001\etape4
    # 3. planche côte à côte (photo | maquette | les deux superposées)
    python outils\habillage\caler_photos.py planche verites\app-001\cameras-photos.json ..\atelya\b2\app-001\etape4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur.camera_photo import camera_depuis_dict, pour_blender, projeter  # noqa: E402

JAUNE, CIEL, VIOLET, BLEU, VERT, ROUGE = (255, 220, 0), (0, 230, 255), (255, 0, 255), (60, 140, 255), (40, 255, 40), (255, 0, 0)
PRES = 0.15  # m : une arête plus proche de l'appareil est coupée (elle passerait derrière lui)


def _police(taille: int, gras: bool = False):
    try:
        return ImageFont.truetype("arialbd.ttf" if gras else "arial.ttf", taille)
    except OSError:
        return ImageFont.load_default()


def aretes(logement: dict, pieces: set[str] | None = None) -> list[tuple]:
    """Arêtes de la maquette (p0, p1, couleur) : contours des pièces au sol et au plafond, angles, fenêtres et portes."""
    from shapely.geometry import Point, Polygon

    hsp = logement["hauteur_sous_plafond"]
    choisies = [p for p in logement["pieces"] if not pieces or p["id"] in pieces]
    sortie = []
    for p in choisies:
        c = p["contour"]
        for i, a in enumerate(c):
            b = c[(i + 1) % len(c)]
            sortie += [((a[0], a[1], 0.0), (b[0], b[1], 0.0), JAUNE), ((a[0], a[1], hsp), (b[0], b[1], hsp), CIEL),
                       ((a[0], a[1], 0.0), (a[0], a[1], hsp), VIOLET)]
    zones = [Polygon(p["contour"]).buffer(0.45) for p in choisies]
    murs = {m["id"]: m for m in logement["murs"]}
    for o in logement["ouvertures"]:
        m = murs[o["mur"]]
        (x0, y0), (x1, y1) = m["debut"], m["fin"]
        long = float(np.hypot(x1 - x0, y1 - y0))
        ux, uy = (x1 - x0) / long, (y1 - y0) / long
        t = o["position"] + o["largeur"] / 2
        if not any(z.contains(Point(x0 + ux * t, y0 + uy * t)) for z in zones):
            continue
        couleur = VERT if o["type"] == "porte" else BLEU
        for cote in (-1, 1):
            e = cote * m["epaisseur"] / 2
            a = (x0 + ux * o["position"] - uy * e, y0 + uy * o["position"] + ux * e)
            b = (a[0] + ux * o["largeur"], a[1] + uy * o["largeur"])
            za, zb = o["allege"], o["allege"] + o["hauteur"]
            for p, q in (((a, za), (b, za)), ((a, zb), (b, zb)), ((a, za), (a, zb)), ((b, za), (b, zb))):
                sortie.append(((*p[0], p[1]), (*q[0], q[1]), couleur))
    return sortie


def dessiner(photo: Path, cam, logement: dict, sortie: Path, reperes: list[dict] = (), pieces: set[str] | None = None) -> None:
    image = Image.open(photo).convert("RGB")
    trait = ImageDraw.Draw(image, "RGBA")
    for p0, p1, couleur in aretes(logement, pieces):
        a, b = np.array(p0, float), np.array(p1, float)
        pa, pb = projeter(a, cam)[2], projeter(b, cam)[2]
        if pa < PRES and pb < PRES:
            continue
        if pa < PRES:
            a = a + (b - a) * (PRES - pa) / (pb - pa)
        elif pb < PRES:
            b = b + (a - b) * (PRES - pb) / (pa - pb)
        trait.line([projeter(a + (b - a) * k / 30, cam)[:2] for k in range(31)], fill=couleur + (230,), width=2)
    for rep in reperes:
        if rep["type"] == "ligne":
            trait.line([tuple(rep["p1"]), tuple(rep["p2"])], fill=ROUGE, width=3)
        else:
            u, v = rep["uv"]
            trait.ellipse([u - 6, v - 6, u + 6, v + 6], outline=ROUGE, width=3)
    image.save(sortie)


def planche(photo: Path, rendu: Path, sortie: Path, titre: str) -> None:
    """Photo | maquette vue du même endroit | les deux superposées (moitié-moitié)."""
    a = Image.open(photo).convert("RGB")
    b = Image.open(rendu).convert("RGB").resize(a.size, Image.LANCZOS)
    images = [a, b, Image.blend(a, b, 0.5)]
    noms = ["Photo de l'annonce", "Maquette Atelya, même caméra", "Les deux superposées"]
    largeur, hauteur, bandeau = a.width // 2, a.height // 2, 30
    feuille = Image.new("RGB", (3 * largeur + 20, hauteur + bandeau), "white")
    trait = ImageDraw.Draw(feuille)
    for i, im in enumerate(images):
        feuille.paste(im.resize((largeur, hauteur), Image.LANCZOS), (i * (largeur + 10), bandeau))
        trait.text((i * (largeur + 10) + 4, 6), f"{titre} : {noms[i]}" if i == 0 else noms[i], fill="black", font=_police(16, True))
    feuille.save(sortie)


def rendre(releve: dict, maquette: Path, dossier: Path, echantillons: int = 512, scene: str | None = None) -> list[Path]:
    """Caméras posées dans une copie de la maquette (dossier/maquette-photos.blend), puis une image par caméra."""
    from moteur.construire import DOSSIER_SCRIPTS, lancer_blender

    dossier.mkdir(parents=True, exist_ok=True)
    reglages = {nom: pour_blender(camera_depuis_dict(c["camera"]), c["largeur"], c["hauteur"])
                for nom, c in releve["cameras"].items()}
    chemin_reglages = dossier / "cameras-blender.json"
    chemin_reglages.write_text(json.dumps(reglages, indent=1), encoding="utf-8")
    copie = dossier / "maquette-photos.blend"
    lancer_blender(str(maquette), "--python", str(DOSSIER_SCRIPTS / "poser_cameras_photos.py"), "--",
                   str(chemin_reglages), str(copie))
    images = dossier / "rendus"
    images.mkdir(exist_ok=True)
    lancer_blender(str(copie), "--python", str(DOSSIER_SCRIPTS / "rendre.py"), "--", str(images), str(echantillons), "100",
                   *([scene] if scene else []))
    return sorted(images.glob("vue-*.png"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Caméras des photos du client : contrôle, rendus, planche.")
    sous = parser.add_subparsers(dest="commande", required=True)
    d = sous.add_parser("dessiner")
    d.add_argument("releve"), d.add_argument("logement"), d.add_argument("photo"), d.add_argument("sortie")
    d.add_argument("--pieces", nargs="*", help="pièces à dessiner (toutes par défaut)")
    r = sous.add_parser("rendre")
    r.add_argument("releve"), r.add_argument("maquette"), r.add_argument("dossier")
    r.add_argument("--echantillons", type=int, default=512)
    r.add_argument("--scene", help="éclairage à rendre, ex. « 2 Jour voilé » (maquette avec éclairages)")
    p = sous.add_parser("planche")
    p.add_argument("releve"), p.add_argument("dossier")
    args = parser.parse_args()

    releve = json.loads(Path(args.releve).read_text(encoding="utf-8"))
    photos = RACINE / releve["photos"]  # chemin relatif à la racine du dépôt, comme dans verites\app-001\sols.json
    if not photos.is_dir():
        sys.exit(f"PLANTÉ : dossier des photos introuvable ({releve['photos']})")
    if args.commande == "dessiner":
        c = releve["cameras"][args.photo]
        logement = json.loads(Path(args.logement).read_text(encoding="utf-8"))
        dessiner(photos / f"{args.photo}.png", camera_depuis_dict(c["camera"]), logement, Path(args.sortie), c["reperes"],
                 set(args.pieces) if args.pieces else None)
        print(f"Contrôle : {args.sortie}")
    elif args.commande == "rendre":
        for image in rendre(releve, Path(args.maquette), Path(args.dossier), args.echantillons, args.scene):
            print(f"Image prête : {image}")
    else:
        dossier = Path(args.dossier)
        for nom in releve["cameras"]:
            rendu = dossier / "rendus" / f"vue-{nom}.png"
            if not rendu.is_file():
                sys.exit(f"PLANTÉ : rendu introuvable ({rendu})")
            sortie = dossier / f"cote-a-cote-{nom}.png"
            planche(photos / f"{nom}.png", rendu, sortie, nom)
            print(f"Planche : {sortie}")


if __name__ == "__main__":
    main()
