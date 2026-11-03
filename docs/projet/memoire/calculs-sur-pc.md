---
name: calculs-sur-pc
description: NT veut que les gros calculs (Atelya, entraînement, coloriage) tournent sur son PC RTX 2070
metadata:
  type: feedback
  modified: 2026-10-29T09:09:31.071Z
---

NT (2026-10-29) : « dès qu'il y a des gros calculs à faire, tu le fais sur le PC ».

**Why:** le PC Windows a la carte graphique RTX 2070 achetée/installée pour ça ([[atelya-modele]]).

**How to apply:** entraînement et coloriage Atelya = toujours sur le PC (Remote Control PC). Depuis le 2026-10-29 (étape 6-13, accord NT) opencv-headless, rapidocr, onnxruntime, pydantic SONT installés dans atelya\.venv : le banc de notation tourne aussi sur le PC (36 min les 1 066 niveaux, 5 processus). Code transféré par zip (NT, e-mail) ou petit patch dans les instructions RC. Voir [[gros-calculs-sur-pc]], [[atelya-echelle-fine]]. Le cloud ne coûte rien de plus à NT et ne chauffe pas le PC (86 °C en charge).

2026-11-03 (Claude Code sur le PC, accord écrit NT « oui pour pytest ») : pytest 9.2.0 (+ pluggy, iniconfig, pygments) installé dans atelya\.venv par `uv pip install`. Lancer : `..\atelya\.venv\Scripts\python.exe -m pytest -q` depuis atelya-code. 54 tests échouaient sur le PC (images vides) à cause du piège des accents (cv2.imread renvoie None sur « D:\Modélisation immobilière\… ») → nouveau moteur/images.py (lire_image / ecrire_image) utilisé partout dans moteur/ et tests/ + tests/test_images.py ; résultat 321 passed + 6 skipped (Blender). Branche GitHub correctif-chemins-accents, pas encore fusionnée dans main (accord NT).
