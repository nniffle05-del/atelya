"""Juger les éclairages d'Unreal contre des images Cycles de CONTRÔLE (11/11/2026). Ne règle rien : la chaîne
(cinematique_unreal.py) n'utilise jamais ces images ; on mesure seulement si la règle automatique tombe juste.

    python outils/unreal/juger_eclairages.py <rendus_unreal> <controles_cycles> <sortie_sans_extension> [--images 1,48,96]

<rendus_unreal>\\<éclairage>\\image-0001.png… (cinematique_unreal.py) ; <controles_cycles>\\<éclairage>\\image-0001.png… (même trajet,
rendu par moteur/blender/video_trajet.py). Écrit <sortie>.jpg (par éclairage : Cycles | Unreal pour chaque image) et <sortie>.json
(écart moyen /255, écart de clarté en crans : + = Unreal plus sombre, clarté des murs du milieu de l'image).
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cinematique_unreal import ecart_d_exposition  # noqa: E402

ORDRE = ["jour_soleil", "jour_voile", "fin_de_journee", "soiree", "nuit"]


def _lire(chemin: Path):
    return cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)


def _etiquette(image, texte):
    cv2.rectangle(image, (0, 0), (image.shape[1], 24), (255, 255, 255), -1)
    cv2.putText(image, texte, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    return image


def juger(unreal: Path, cycles: Path, sortie: Path, images=(1, 48, 96), largeur=400) -> dict:
    bilan, lignes = {}, []
    for ident in ORDRE:
        du, dc = unreal / ident, cycles / ident
        paires = [(dc / f"image-{f:04d}.png", du / f"image-{f:04d}.png") for f in images]
        if not all(c.is_file() and u.is_file() for c, u in paires):
            continue
        ecarts, vignettes = [], []
        for f, (c, u) in zip(images, paires):
            ic, iu = _lire(c), _lire(u)
            iu = cv2.resize(iu, (ic.shape[1], ic.shape[0]))
            ecarts.append(float(np.abs(ic.astype(float) - iu.astype(float)).mean()))
            h = round(largeur * ic.shape[0] / ic.shape[1])
            vignettes += [_etiquette(cv2.resize(ic, (largeur, h)), f"{ident} Cycles {f}"),
                          _etiquette(cv2.resize(iu, (largeur, h)), f"{ident} Unreal {f}")]
        bilan[ident] = {"ecart_moyen_255": round(float(np.mean(ecarts)), 1),
                        "ecarts_par_image": [round(e, 1) for e in ecarts],
                        "ecart_clarte_crans": round(ecart_d_exposition(du, dc, images), 2)}
        lignes.append(np.hstack(vignettes))
    if not lignes:
        sys.exit("PLANTÉ : aucun éclairage avec ses images des deux côtés")
    planche = np.vstack(lignes)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", planche, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(str(sortie.with_suffix(".jpg")))
    sortie.with_suffix(".json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    return bilan


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("unreal")
    p.add_argument("cycles")
    p.add_argument("sortie")
    p.add_argument("--images", default="1,48,96")
    a = p.parse_args()
    bilan = juger(Path(a.unreal), Path(a.cycles), Path(a.sortie), tuple(int(v) for v in a.images.split(",")))
    for ident, b in bilan.items():
        print(f"{ident:16} écart moyen {b['ecart_moyen_255']:5.1f}/255  clarté {b['ecart_clarte_crans']:+.2f} cran(s)  "
              f"images {b['ecarts_par_image']}")


if __name__ == "__main__":
    main()
