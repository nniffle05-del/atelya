r"""Fabriquer la VÉRITÉ d'un vrai plan (ce qu'Atelya devrait lire), à partir d'une saisie faite à la main en pixels.

Pourquoi : les plans fabriqués ont leur vérité écrite par le générateur ; un vrai plan n'en a pas. Sans vérité, on ne
peut ni noter Atelya sur du vrai (la note « vrais plans » reste une impression), ni l'entraîner dessus. Ici la vérité est
tracée par Claude (pas par Atelya), relue par NT si besoin.

La saisie (`verite-saisie.json`, écrite en regardant le plan sur sa grille, voir `grille`) :
{
  "image": "fr-004.jpg",                      # le plan, dans le même dossier
  "px_par_m": 73.8,                           # échelle vraie de l'image ; ou "echelle": {"inconnue": true, "porte_m": 0.83}
  "echelle_source": "surfaces écrites",       # d'où vient l'échelle (cotes, surfaces, barre, 1/50 du PDF, portes)
  "hsp": 2.5,
  "murs": [[x0, y0, x1, y1, epaisseur_px], ...],          # AXE du mur, en pixels de l'image (y vers le bas)
  "ouvertures": [["porte", x0, y0, x1, y1], ...],         # le trou dans le mur, d'un bord à l'autre
  "pieces": [["Chambre", "chambre", x, y], ...],          # nom écrit, type, un point dedans
  "affiner": true                                         # recaler chaque mur sur l'encre du dessin (±6 px)
}
Sortie dans le même dossier : logement.json (format logement/0.1, origine = coin sud-ouest intérieur, comme le générateur),
verite.json (échelle, types des pièces, calage pixels → mètres, murs en pixels affinés), masque_semantique.png (classes du
générateur, taille de l'image : pour un futur entraînement) et controle.png (la vérité dessinée sur le plan, à relire).

    ..\atelya\.venv\Scripts\python.exe outils\verite\faire_verite.py grille ..\atelya\vrais-plans\lot-2026-10-31\fr-004.jpg [--pas 50] [--zoom x0 y0 x1 y1]
    ..\atelya\.venv\Scripts\python.exe outils\verite\faire_verite.py verite ..\atelya\verites\fr-004\verite-saisie.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.coloriage import PIECES, _contour_orthogonal  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from moteur.logement import Logement  # noqa: E402

VERSION_VERITE = "0.1.0"
CLASSE_DU_TYPE = {t: c for c, (t, _) in PIECES.items()}
CLASSE_DU_TYPE.update({"sdb": 8, "sde": 8, "wc": 9, "sejour_cuisine": 5, "principale": 5})
CLASSE_OUVERTURE = {"porte": 2, "fenetre": 3, "porte_fenetre": 4}
HAUTEURS = {"porte": (2.04, 0.0), "porte_fenetre": (2.15, 0.0), "fenetre": (1.25, 0.95)}
POLICE = Path(__file__).resolve().parents[2] / "moteur" / "polices"


def _police(taille: int):
    for f in sorted(POLICE.glob("*.ttf")) if POLICE.exists() else []:
        try:
            return ImageFont.truetype(str(f), taille)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- grille

def grille(chemin: Path, pas: int, zoom: list[int] | None, sortie: Path | None) -> Path:
    """Le plan avec une grille graduée en pixels (pour lire des coordonnées à l'œil), entier ou zoomé ×2 sur une zone."""
    img = Image.open(chemin).convert("RGB")
    x0, y0 = 0, 0
    facteur = 1
    if zoom:
        x0, y0, x1, y1 = zoom
        img = img.crop((x0, y0, x1, y1))
        facteur = 2
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    police = _police(max(10, pas // 4))
    for x in range(0, (img.width // facteur) + x0 + 1, pas // (2 if zoom else 1)):
        if x < x0:
            continue
        px = (x - x0) * facteur
        gros = x % pas == 0
        d.line([(px, 0), (px, img.height)], fill=(255, 0, 0, 110 if gros else 45), width=1)
        if gros:
            d.text((px + 2, 2), str(x), fill=(200, 0, 0, 255), font=police)
    for y in range(0, (img.height // facteur) + y0 + 1, pas // (2 if zoom else 1)):
        if y < y0:
            continue
        py = (y - y0) * facteur
        gros = y % pas == 0
        d.line([(0, py), (img.width, py)], fill=(0, 0, 255, 110 if gros else 45), width=1)
        if gros:
            d.text((2, py + 2), str(y), fill=(0, 0, 200, 255), font=police)
    sortie = sortie or chemin.with_name(chemin.stem + ("-grille" if not zoom else f"-zoom-{x0}-{y0}") + ".png")
    img.save(sortie)
    return sortie


# ---------------------------------------------------------------- affiner un mur sur l'encre

def _profil(gris: np.ndarray, x0: float, y0: float, x1: float, y1: float, demi: int) -> np.ndarray:
    """Noirceur médiane le long du mur, pour chaque décalage perpendiculaire de −demi à +demi pixels."""
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L))
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    t = np.linspace(0.1, 0.9, n)  # on évite les bouts (angles, murs voisins)
    xs = x0 + t * (x1 - x0)
    ys = y0 + t * (y1 - y0)
    prof = []
    for k in range(-demi, demi + 1):
        px = np.clip(np.round(xs + k * nx).astype(int), 0, gris.shape[1] - 1)
        py = np.clip(np.round(ys + k * ny).astype(int), 0, gris.shape[0] - 1)
        prof.append(float(np.median(255 - gris[py, px])))
    return np.array(prof)


def affiner_mur(gris: np.ndarray, mur: list[float], marge: int = 6) -> list[float]:
    """Recale l'axe et l'épaisseur d'un mur sur la bande d'encre la plus proche (le trait du plan vaut mieux que mon œil)."""
    x0, y0, x1, y1, ep = mur
    demi = int(ep / 2 + marge)
    prof = _profil(gris, x0, y0, x1, y1, demi)
    papier = float(np.percentile(prof, 20))
    encre = papier + 0.5 * (prof.max() - papier)
    if prof.max() - papier < 40:  # pas d'encre nette : on garde la saisie
        return mur
    sombre = prof >= encre
    # la bande sombre qui contient (ou est la plus proche de) l'axe saisi
    centre = demi
    bandes = []
    k = 0
    while k < len(sombre):
        if sombre[k]:
            j = k
            while j + 1 < len(sombre) and sombre[j + 1]:
                j += 1
            bandes.append((k, j))
            k = j + 1
        else:
            k += 1
    if not bandes:
        return mur
    a, b = min(bandes, key=lambda ab: 0 if ab[0] <= centre <= ab[1] else min(abs(ab[0] - centre), abs(ab[1] - centre)))
    if min(abs(a - centre), abs(b - centre)) > marge and not (a <= centre <= b):
        return mur
    decal = (a + b) / 2 - centre
    nouvelle_ep = b - a + 1
    if abs(nouvelle_ep - ep) > max(3, 0.35 * ep):  # bande trop différente (trait de fenêtre, hachures) : axe seul
        nouvelle_ep = ep
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    return [x0 + decal * nx, y0 + decal * ny, x1 + decal * nx, y1 + decal * ny, float(nouvelle_ep)]


# ---------------------------------------------------------------- la vérité

def _mur_porteur(ouv: list, murs: list[list[float]]) -> tuple[int, float, float]:
    """(index du mur, position le long du mur depuis son début en px, largeur en px) de l'ouverture."""
    _, x0, y0, x1, y1 = ouv
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    meilleur, d_min = None, float("inf")
    for k, (ax, ay, bx, by, _) in enumerate(murs):
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy or 1e-9
        t = ((cx - ax) * dx + (cy - ay) * dy) / l2
        if not (-0.02 <= t <= 1.02):
            continue
        d = abs((cx - ax) * dy - (cy - ay) * dx) / math.sqrt(l2)
        if d < d_min:
            meilleur, d_min = k, d
    if meilleur is None or d_min > 12:
        raise ValueError(f"ouverture {ouv} : aucun mur à moins de 12 px")
    ax, ay, bx, by, _ = murs[meilleur]
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    t0 = (x0 - ax) * ux + (y0 - ay) * uy
    t1 = (x1 - ax) * ux + (y1 - ay) * uy
    return meilleur, max(0.0, min(t0, t1)), abs(t1 - t0)


def faire_verite(saisie: Path) -> dict:
    s = json.loads(saisie.read_text(encoding="utf-8"))
    dossier = saisie.parent
    img = lire_image(dossier / s["image"])
    gris = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gris.shape
    murs = [list(map(float, m)) for m in s["murs"]]
    if s.get("affiner", True):
        murs = [affiner_mur(gris, m) for m in murs]
    echelle = s.get("echelle") or {}
    inconnue = bool(echelle.get("inconnue"))
    if inconnue:
        # Pas d'échelle sur le plan : on la pose sur la largeur des portes (0,83 m) pour avoir des mètres plausibles ;
        # la note d'échelle ne comptera pas ce plan.
        largeurs = [math.hypot(o[3] - o[1], o[4] - o[2]) for o in s["ouvertures"] if o[0] == "porte"]
        px_par_m = float(np.median(largeurs)) / float(echelle.get("porte_m", 0.83))
    else:
        px_par_m = float(s.get("px_par_m", 0.0))  # 0 : viendra des surfaces écrites

    # Masque des murs en pixels (axe + épaisseur), pour trouver les pièces par remplissage.
    bati = np.zeros((H, W), np.uint8)
    for x0, y0, x1, y1, ep in murs:
        # Chaque mur est prolongé d'une demi-épaisseur (+ 3 px) à ses bouts : les angles se ferment même quand
        # l'affinage a décalé un mur de quelques pixels par rapport à son voisin.
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        r = ep / 2 + 3
        cv2.line(bati, (int(round(x0 - r * ux)), int(round(y0 - r * uy))), (int(round(x1 + r * ux)), int(round(y1 + r * uy))),
                 1, max(1, int(round(ep))))
    libre = (bati == 0).astype(np.uint8)
    n, etiq, stats, _ = cv2.connectedComponentsWithStats(libre, connectivity=4)
    zones = {}
    for nom, type_, x, y in s["pieces"]:
        z = int(etiq[int(round(y)), int(round(x))])
        if z == 0:
            raise ValueError(f"pièce {nom} : le point ({x}, {y}) tombe dans un mur")
        if z == etiq[0, 0] or z == etiq[0, W - 1] or z == etiq[H - 1, 0] or z == etiq[H - 1, W - 1]:
            raise ValueError(f"pièce {nom} : sa zone n'est pas fermée (elle touche le bord de l'image)")
        if z in zones:
            raise ValueError(f"pièce {nom} : même zone que {zones[z][0]} (cloison manquante dans la saisie ?)")
        zones[z] = (nom, type_, x, y)

    # Échelle par les surfaces écrites : « surfaces » = {nom de pièce: m²} ; l'échelle = √(Σ pixels / Σ m²) des pièces
    # nommées, et chaque pièce donne son propre avis (un écart > 5 % signale une saisie ou une surface douteuse).
    avis = []
    if s.get("surfaces"):
        for z, (nom, type_, x, y) in zones.items():
            if nom in s["surfaces"]:
                aire = int(stats[z, cv2.CC_STAT_AREA])
                avis.append((nom, aire, float(s["surfaces"][nom]), math.sqrt(aire / float(s["surfaces"][nom]))))
        if avis and "px_par_m" not in s:
            px_par_m = math.sqrt(sum(a[1] for a in avis) / sum(a[2] for a in avis))
            inconnue = False
        for nom, aire, m2, e in avis:
            print(f"   {nom:24} {m2:7.2f} m² ↔ {aire:7d} px → {e:6.2f} px/m ({100 * (e / px_par_m - 1):+.1f} %)")
    if not px_par_m:
        raise ValueError("pas d'échelle : donner px_par_m, ou surfaces (nom → m²), ou echelle.inconnue")

    # Origine en mètres : coin sud-ouest de l'INTÉRIEUR (comme le générateur et le traducteur).
    interieur = np.isin(etiq, list(zones))
    ys, xs = np.nonzero(interieur)
    ox, oy = float(xs.min()), float(ys.max() + 1)

    def m_(u: float, v: float) -> list[float]:
        return [round((u - ox) / px_par_m, 3), round((oy - v) / px_par_m, 3)]

    sortie_murs = []
    for k, (x0, y0, x1, y1, ep) in enumerate(murs):
        if abs(x1 - x0) >= abs(y1 - y0):  # d'ouest en est
            (x0, y0), (x1, y1) = sorted([(x0, y0), (x1, y1)])
        else:  # du sud (bas de l'image) au nord
            (x0, y0), (x1, y1) = sorted([(x0, y0), (x1, y1)], key=lambda p: -p[1])
        murs[k] = [x0, y0, x1, y1, ep]
        sortie_murs.append({"id": f"M{k + 1}", "debut": m_(x0, y0), "fin": m_(x1, y1), "epaisseur": round(ep / px_par_m, 3),
                            "statut": "mesure", "source": "verite_claude"})
    sortie_ouv = []
    masque = bati.copy()  # classes du générateur : 1 mur, 2 porte, 3 fenêtre, 4 porte-fenêtre, 5+ pièces
    for j, o in enumerate(s["ouvertures"]):
        k, pos, larg = _mur_porteur(o, murs)
        x0, y0, x1, y1, ep = murs[k]
        hauteur, allege = HAUTEURS[o[0]]
        sortie_ouv.append({"id": f"O{j + 1}", "type": o[0], "mur": f"M{k + 1}", "position": round(pos / px_par_m, 3),
                           "largeur": round(larg / px_par_m, 3), "hauteur": hauteur, "allege": allege,
                           "statut": "mesure", "source": "verite_claude"})
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        a = (int(round(x0 + pos * ux)), int(round(y0 + pos * uy)))
        b = (int(round(x0 + (pos + larg) * ux)), int(round(y0 + (pos + larg) * uy)))
        cv2.line(masque, a, b, CLASSE_OUVERTURE[o[0]], max(1, int(round(ep))))
    sortie_pieces, types = [], {}
    for z, (nom, type_, x, y) in zones.items():
        zone = etiq == z
        contour = _contour_orthogonal(zone)
        if contour is None:
            raise ValueError(f"pièce {nom} : contour introuvable")
        ident = f"{type_}_{len([p for p in sortie_pieces if p['id'].startswith(type_)]) + 1}"
        sortie_pieces.append({"id": ident, "nom": nom, "contour": [m_(u, v) for u, v in contour],
                              "statut": "mesure", "source": "verite_claude"})
        types[ident] = type_
        masque[zone] = CLASSE_DU_TYPE[type_]
    log = {"schema": "logement/0.1", "projet_id": saisie.parent.name, "unites": "m",
           "hauteur_sous_plafond": float(s.get("hsp", 2.5)), "murs": sortie_murs, "ouvertures": sortie_ouv, "pieces": sortie_pieces}
    Logement.model_validate(log)
    (dossier / "logement.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    verite = {"schema": "verite-plan/0.1", "version": VERSION_VERITE, "image": s["image"], "largeur": W, "hauteur": H,
              "px_par_m": round(px_par_m, 3), "echelle_inconnue": inconnue, "echelle_source": s.get("echelle_source", ""),
              "origine_px": [ox, oy], "types_pieces": types, "murs_px": [[round(v, 1) for v in m] for m in murs],
              "incertain": s.get("incertain", [])}
    (dossier / "verite.json").write_text(json.dumps(verite, ensure_ascii=False, indent=1), encoding="utf-8")
    Image.fromarray(masque).save(dossier / "masque_semantique.png")
    _controle(img, murs, s["ouvertures"], zones, etiq, dossier / "controle.png")
    return verite


def _controle(img: np.ndarray, murs, ouvertures, zones, etiq, sortie: Path) -> None:
    base = Image.fromarray(img[:, :, ::-1] if img.ndim == 3 else img).convert("RGB")
    calque = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    rng = np.random.default_rng(1)
    for z, (nom, type_, x, y) in zones.items():
        c = tuple(int(v) for v in rng.integers(80, 230, 3)) + (70,)
        m = (etiq == z).astype(np.uint8) * 255
        calque.paste(Image.new("RGBA", base.size, c), (0, 0), Image.fromarray(m))
    for x0, y0, x1, y1, ep in murs:
        d.line([(x0, y0), (x1, y1)], fill=(255, 0, 0, 160), width=max(1, int(ep)))
        d.line([(x0, y0), (x1, y1)], fill=(0, 0, 0, 255), width=1)
    for t, x0, y0, x1, y1 in ouvertures:
        coul = {"porte": (0, 160, 0, 255), "fenetre": (0, 90, 255, 255), "porte_fenetre": (0, 200, 200, 255)}[t]
        d.line([(x0, y0), (x1, y1)], fill=coul, width=5)
    police = _police(14)
    for nom, type_, x, y in zones.values():
        d.text((x - 20, y - 7), f"{nom} ({type_})", fill=(0, 0, 0, 255), font=police)
    Image.alpha_composite(base.convert("RGBA"), calque).convert("RGB").save(sortie)


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("grille")
    g.add_argument("image", type=Path)
    g.add_argument("--pas", type=int, default=50)
    g.add_argument("--zoom", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    g.add_argument("--sortie", type=Path)
    v = sp.add_parser("verite")
    v.add_argument("saisie", type=Path, nargs="+")
    a = ap.parse_args()
    if a.cmd == "grille":
        print(grille(a.image, a.pas, a.zoom, a.sortie))
    else:
        for s in a.saisie:
            r = faire_verite(s)
            print(f"{s.parent.name} : {len(r['murs_px'])} murs, {len(r['types_pieces'])} pièces, {r['px_par_m']} px/m"
                  f"{' (échelle inconnue, posée sur les portes)' if r['echelle_inconnue'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
