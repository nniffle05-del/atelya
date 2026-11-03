"""Le contrôle visuel : des planches qui mettent côte à côte le plan, ses masques et sa vérité terrain.

- `planche(exemple)` : pour un exemple, une image avec le plan, le masque sémantique en couleurs,
  les pièces, la carte de hauteur, et le plan avec les polygones des annotations redessinés
  par-dessus (si tout est aligné, les traits suivent exactement les murs) ;
- `planches(dossier, n)` : les n premières planches dans rapports/planches/ ;
- `page(dossier)` : une page HTML locale (rapports/controle.html) qui liste les exemples avec
  leurs planches, le verdict du validateur et leurs chiffres, pour feuilleter vite.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from moteur.images import ecrire_image, lire_image
import numpy as np

from moteur.generateur.annotations import NOMS_CLASSES

COULEURS = {
    0: (255, 255, 255), 1: (30, 30, 30), 2: (220, 60, 60), 3: (60, 120, 230), 4: (60, 200, 230),
    5: (250, 220, 150), 6: (250, 180, 120), 7: (180, 200, 250), 8: (160, 220, 230), 9: (170, 230, 200),
    10: (220, 220, 200), 11: (210, 210, 190), 12: (190, 180, 170), 13: (190, 220, 190), 14: (220, 190, 230), 15: (200, 200, 200),
}


def colorer_semantique(sem: np.ndarray) -> np.ndarray:
    table = np.zeros((256, 3), np.uint8)
    for k, c in COULEURS.items():
        table[k] = c
    return table[sem]


def colorer_pieces(masque: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(7)
    table = rng.integers(80, 250, (256, 3)).astype(np.uint8)
    table[0] = (255, 255, 255)
    return table[masque]


def _hauteur_en_couleurs(h: np.ndarray) -> np.ndarray:
    maxi = max(int(h.max()), 1)
    gris = (255 - (h.astype(np.float32) / maxi * 220)).astype(np.uint8)
    return cv2.cvtColor(gris, cv2.COLOR_GRAY2RGB)


def _superposer(plan: np.ndarray, ann: dict) -> np.ndarray:
    img = plan.copy()
    for m in ann["murs"]:
        pts = np.array([[round(a), round(b)] for a, b in m["polygone_px"]], np.int32)
        cv2.polylines(img, [pts], True, (230, 40, 40), 2)
    for o in ann["ouvertures"]:
        pts = np.array([[round(a), round(b)] for a, b in o["polygone_px"]], np.int32)
        cv2.polylines(img, [pts], True, (40, 90, 230) if o["classe"] != 2 else (30, 170, 60), 2)
    for p in ann["pieces"]:
        pts = np.array([[round(a), round(b)] for a, b in p["polygone_px"]], np.int32)
        cv2.polylines(img, [pts], True, (240, 160, 30), 1)
    return img


def _vignette(img: np.ndarray, hauteur: int, titre: str) -> np.ndarray:
    h, w = img.shape[:2]
    largeur = max(1, round(w * hauteur / h))
    petit = cv2.resize(img, (largeur, hauteur), interpolation=cv2.INTER_AREA)
    if petit.ndim == 2:
        petit = cv2.cvtColor(petit, cv2.COLOR_GRAY2RGB)
    bande = np.full((28, largeur, 3), 245, np.uint8)
    cv2.putText(bande, titre, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1, cv2.LINE_AA)
    return np.vstack([bande, petit])


def planche(dossier_exemple: Path, niveau: int = 0, hauteur: int = 420) -> np.ndarray:
    dn = Path(dossier_exemple) / f"niveau_{niveau}"
    from moteur.generateur.validateur import chemin_du_plan
    plan = cv2.cvtColor(lire_image(str(chemin_du_plan(dn)), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    sem = lire_image(str(dn / "masque_semantique.png"), cv2.IMREAD_UNCHANGED)
    pieces = lire_image(str(dn / "masque_pieces.png"), cv2.IMREAD_UNCHANGED)
    haut = lire_image(str(dn / "hauteur.png"), cv2.IMREAD_UNCHANGED)
    ann = json.loads((dn / "annotations.json").read_text(encoding="utf-8"))
    vignettes = [
        _vignette(plan, hauteur, "plan"),
        _vignette(_superposer(plan, ann), hauteur, "annotations sur le plan"),
        _vignette(colorer_semantique(sem), hauteur, "masque semantique"),
        _vignette(colorer_pieces(pieces), hauteur, "pieces"),
        _vignette(_hauteur_en_couleurs(haut), hauteur, "hauteur"),
    ]
    sep = np.full((vignettes[0].shape[0], 6, 3), 200, np.uint8)
    morceaux = []
    for v in vignettes:
        morceaux += [v, sep]
    return np.hstack(morceaux[:-1])


def planches(dossier: Path, nombre: int = 20) -> list[Path]:
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    sortie = dossier / "rapports" / "planches"
    sortie.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for e in manifeste["exemples"][:nombre]:
        for niveau in range(e["nombre_niveaux"]):
            try:
                img = planche(dossier / "exemples" / e["id"], niveau)
            except Exception as err:  # noqa: BLE001
                print(f"planche {e['id']} niveau {niveau} impossible : {err}")
                continue
            chemin = sortie / f"{e['id']}_niveau{niveau}.jpg"
            ecrire_image(str(chemin), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
            ecrits.append(chemin)
    return ecrits


def page(dossier: Path, nombre: int = 50) -> Path:
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    chemins = planches(dossier, nombre)
    legende = " · ".join(f"{k} = {v}" for k, v in NOMS_CLASSES.items())
    lignes = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Contrôle du jeu de plans</title>",
        "<style>body{font-family:sans-serif;margin:20px;background:#fafafa}article{background:#fff;border:1px solid #ddd;"
        "margin:14px 0;padding:10px}img{max-width:100%}.ok{color:#2a7}.ko{color:#c33}small{color:#666}</style></head><body>",
        f"<h1>Contrôle visuel — {manifeste['nombre']} exemples, {manifeste['acceptes']} acceptés</h1>",
        f"<p><small>Classes du masque sémantique : {legende}</small></p>",
    ]
    for e in manifeste["exemples"][:nombre]:
        verdict = "<span class='ok'>accepté</span>" if e["accepte"] else "<span class='ko'>rejeté : " + "; ".join(e["erreurs"][:3]) + "</span>"
        lignes.append(f"<article><h2>{e['id']} — {e['type']} {e['forme']}{' duplex' if e['duplex'] else ''}, "
                      f"{e['surface']} m², {e['nombre_pieces']} pièces, {e['nombre_murs']} murs, {e['nombre_ouvertures']} ouvertures "
                      f"— style {e['style']} — {verdict}</h2>")
        if e["avertissements"]:
            lignes.append(f"<p><small>Avertissements : {'; '.join(e['avertissements'])}</small></p>")
        for niveau in range(e["nombre_niveaux"]):
            c = dossier / "rapports" / "planches" / f"{e['id']}_niveau{niveau}.jpg"
            if c in chemins:
                lignes.append(f"<p>Niveau {niveau}</p><img src='planches/{c.name}' alt='{e['id']} niveau {niveau}'>")
        lignes.append("</article>")
    lignes.append("</body></html>")
    chemin = dossier / "rapports" / "controle.html"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin
