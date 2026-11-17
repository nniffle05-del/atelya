r"""ÉTAPE 4 (17/11/2026) : les sols quand la lecture des photos est branchée, sur TOUS les logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_sols_lus.py <dossier de sortie> [--cas app-001 app-002 app-004]

Pour chaque logement, sur la même carte des avis (une seule passe de l'œil) :
  « en service »      : Atelya décide seul (sans lecture) ;
  « lecture, avant »  : la lecture appliquée APRÈS la décision (photos_lues.appliquer_les_sols, la façon du 16/11/2026) ;
  « lecture, après »  : la lecture donnée À la décision (reconnaitre_sols.sols_des_pieces(lus=…), 17/11/2026).
Juge : la vérité des sols faite à la main (part du sol VU dont la famille est la bonne, reconnaitre_sols.noter) ; app-004 n'a
pas de vérité : image seulement. Écrit <sortie>/<logement>.jpg (le sol vu de dessus : vérité | en service | avant | après) et
<sortie>/bilan.txt.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
PC = RACINE.parent / "atelya"

from banc_ressemblance import CAS  # noqa: E402
from moteur import pas_du_sol, photos_lues, reconnaitre_sols as rs  # noqa: E402
from moteur.images import ecrire_image  # noqa: E402
from moteur.oeil_dinov2 import charger  # noqa: E402
from sols_photos import COULEURS_FAMILLES, dessiner_contours  # noqa: E402

VERITES = {"app-001": PC / "b2/app-001/brique-photos/verite-logement-sols.json", "app-002": PC / "b2/app-002/examen/logement-verite-sols.json"}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def panneau(resultat: dict, logement: dict, pieces: dict | None, titre: str, verite: dict | None = None) -> np.ndarray:
    """Le sol à plat avec, par-dessus, la famille de sol en couleur : celle de la vérité (`verite`) ou celle décidée (`pieces`)."""
    image, finesse, origine, res = resultat["image"], resultat["finesse"], resultat["origine"], resultat["resolution"]
    dessin = cv2.cvtColor(image, cv2.COLOR_RGB2BGR).astype(np.float32)
    lignes, colonnes = np.nonzero(finesse > 0)
    X, Y = origine[0] + (colonnes + 0.5) * res, origine[1] - (lignes + 0.5) * res
    decide = rs.familles_verite(verite, X, Y) if verite is not None else rs.famille_decidee(pieces, logement, X, Y)
    for i, f in enumerate(rs.FAMILLES):
        m = decide == i
        dessin[lignes[m], colonnes[m]] = 0.45 * dessin[lignes[m], colonnes[m]] + 0.55 * np.array(COULEURS_FAMILLES[f])
    dessin = dessin.astype(np.uint8)
    dessin[finesse == 0] = (60, 60, 60)
    dessiner_contours(dessin, origine, res, [p["contour"] for p in logement["pieces"]], (255, 255, 255), 3)
    return np.concatenate([bandeau(titre, dessin.shape[1], 80, 44), dessin], 0)


def bandeau(texte: str, largeur: int, hauteur: int, taille: int, couleur=(255, 255, 255)) -> np.ndarray:
    """Une bande sombre avec un texte (police du système : les accents s'écrivent, ce qu'OpenCV ne sait pas faire)."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (largeur, hauteur), (30, 30, 30))
    try:
        police = ImageFont.truetype("arialbd.ttf", taille)
    except OSError:
        police = ImageFont.load_default()
    ImageDraw.Draw(image).text((20, (hauteur - taille) // 2 - 4), texte, fill=couleur, font=police)
    return np.asarray(image)[:, :, ::-1].copy()


def legende(largeur: int) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (largeur, 90), (30, 30, 30))
    try:
        police = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        police = ImageFont.load_default()
    dessin = ImageDraw.Draw(image)
    x = 20
    noms = {"lames": "lames droites", "point_de_hongrie": "point de Hongrie", "batons_rompus": "bâtons rompus", "carreaux": "carrelage"}
    for f in rs.FAMILLES:
        dessin.rectangle((x, 22, x + 50, 68), fill=COULEURS_FAMILLES[f][::-1])
        dessin.text((x + 62, 26), noms[f], fill=(255, 255, 255), font=police)
        x += 90 + int(dessin.textlength(noms[f], font=police)) + 40
    dessin.text((x, 26), "gris : sol qu'aucune photo ne montre", fill=(200, 200, 200), font=police)
    return np.asarray(image)[:, :, ::-1].copy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    clf = rs.Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
    oeil = charger(clf.oeil)
    pds = pas_du_sol.charger(avec_dino=False)
    lignes = []
    for cas in a.cas:
        releve, logement = lire(CAS[cas]["fiche"]), lire(CAS[cas]["logement"])
        logement = logement.get("logement", logement)
        for p in logement["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        lecture = lire(PC / "lectures-photos" / cas / "lecture.json")
        r = rs.reconnaitre(releve, logement, RACINE, oeil, clf, pas_du_sol=lambda n, rgb, cas=cas: pds.masque(f"{cas}/{n}", rgb))
        lus = photos_lues.sols_lus(lecture, releve, logement)
        r2 = rs.reconnaitre(releve, logement, RACINE, oeil, clf, pas_du_sol=lambda n, rgb, cas=cas: pds.masque(f"{cas}/{n}", rgb), lus=lus,
                            sols_des_photos=photos_lues.sols_des_photos(lecture))
        cartes = {"avec la lecture, après": r2}
        versions = {"sans la lecture des photos": r["pieces"],
                    "avec la lecture, avant": photos_lues.appliquer_les_sols(r["pieces"], lus),
                    "(zones refaites seulement)": rs.sols_des_pieces(r["carte"], logement, lus=lus),
                    "avec la lecture, après": r2["pieces"]}
        verite = lire(VERITES[cas]) if cas in VERITES else None
        panneaux = [panneau(r, logement, None, "la vérité (relevé à la main)", verite)] if verite else []
        lignes.append(cas + " | lu : " + " ; ".join(f"{pid} {v['famille']}" + (" + " + ", ".join(v["autres"]) if v["autres"] else "") for pid, v in lus.items()))
        for titre, pieces in versions.items():
            texte = " ; ".join(f"{pid} {s['famille']}" + "".join(f" + zone {z['famille']} {z['surface_m2']} m²" for z in s["zones"]) for pid, s in pieces.items())
            if verite:
                n = rs.noter({**cartes.get(titre, r), "pieces": pieces}, verite)
                detail = ", ".join(f"{f} {100 * v['juste']:.0f} % de {v['m2']} m²" for f, v in n["par_famille"].items())
                lignes.append(f"  {titre:28s} sol juste {100 * n['surface_juste']:.1f} % de {n['surface_jugee_m2']} m² ({detail}) | pièces {n['pieces_justes']} | {texte}")
                titre += f" : {100 * n['surface_juste']:.0f} % juste"
            else:
                lignes.append(f"  {titre:28s} {texte}")
            if not titre.startswith("("):
                panneaux.append(panneau(r, logement, pieces, titre))
        if len(panneaux) == 4:  # deux rangées de deux : lisible sur un écran
            planche = np.concatenate([np.concatenate(panneaux[:2], 1), np.concatenate(panneaux[2:], 1)], 0)
        else:
            planche = np.concatenate(panneaux, 1)
        nom_logement = {"app-001": "premier logement", "app-002": "deuxième logement", "app-004": "troisième logement"}.get(cas, cas)
        planche = np.concatenate([bandeau(f"Les sols vus de dessus, d'après les photos : {nom_logement}", planche.shape[1], 100, 56),
                                  planche, legende(planche.shape[1])], 0)
        k = 2400 / planche.shape[1]
        if k < 1:
            planche = cv2.resize(planche, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        ecrire_image(a.sortie / f"{cas}.jpg", planche)
        print("\n".join(lignes[-(len(versions) + 1):]), flush=True)
    (a.sortie / "bilan.txt").write_text("\n".join(lignes), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
