"""Compare les images « maquette Blender » et « relue depuis glTF » faites par moteur/blender/verifier_gltf.py.

    python outils/unreal/comparer_export.py <dossier_verification>

Pour chaque vue : écart moyen (sur 255) et part des pixels qui changent nettement (> 25), puis une planche côte à côte
(origine | relue | écart grossi 4 fois) : planche-<vue>.jpg. Le bilan est ajouté à verification-gltf.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SEUIL_NET = 25


def comparer(dossier: Path) -> dict:
    ecarts = {}
    for origine in sorted(dossier.glob("vue-*-origine.png")):
        vue = origine.name[len("vue-"):-len("-origine.png")]
        a = np.asarray(Image.open(origine).convert("RGB")).astype(float)
        b = np.asarray(Image.open(dossier / f"vue-{vue}-gltf.png").convert("RGB")).astype(float)
        d = np.abs(a - b).mean(axis=2)
        ecarts[vue] = {"ecart_moyen": round(float(d.mean()), 2), "pixels_changes_pct": round(float((d > SEUIL_NET).mean()) * 100, 2)}
        h, w = a.shape[:2]
        planche = Image.new("RGB", (w * 3, h), "white")
        for i, image in enumerate((a, b, np.repeat(np.clip(d * 4, 0, 255)[..., None], 3, axis=2))):
            planche.paste(Image.fromarray(image.astype(np.uint8)), (i * w, 0))
        dessin = ImageDraw.Draw(planche)
        for i, titre in enumerate(("Maquette Blender", "Relue depuis glTF", "Ecart x4")):
            dessin.rectangle((i * w, 0, i * w + 190, 22), fill="white")
            dessin.text((i * w + 6, 5), titre, fill="black")
        planche.save(dossier / f"planche-{vue}.jpg", quality=88)
    bilan_fichier = dossier / "verification-gltf.json"
    if bilan_fichier.is_file():
        bilan = json.loads(bilan_fichier.read_text(encoding="utf-8"))
        bilan["ecarts"] = ecarts
        bilan_fichier.write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return ecarts


if __name__ == "__main__":
    for vue, e in comparer(Path(sys.argv[1])).items():
        print(f"{vue} : écart moyen {e['ecart_moyen']} / 255, pixels nettement changés {e['pixels_changes_pct']} %")
