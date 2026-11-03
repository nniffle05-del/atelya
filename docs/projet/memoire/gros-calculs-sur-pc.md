---
name: gros-calculs-sur-pc
description: Consigne NT (2026-10-29) : les gros calculs (bancs de note, coloriages, entraînements) se font sur le PC RTX 2070, pas dans le cloud ni sur le Mac
metadata:
  type: feedback
---
2026-10-29 09h08 NT : « dès qu'il y a des gros calculs à faire tu le fais sur le PC ? » → oui.
**Why:** le PC (RTX 2070, i7 6 cœurs) est la station de calcul du projet.
**How to apply:** écrire/tester le code léger dans le cloud ; bancs 1 066 niveaux, coloriages, entraînements → Remote Control sur le PC (accord écrit de NT avant de lancer du code ; toute installation sur le PC = accord). Le PC est souvent sur le partage iPhone et ne voit pas le Mac : transfert à la main par NT. Voir [[environnement-poste-nt]], [[atelya-echelle-fine]].
PIÈGE (2026-10-31) : sur le PC, OpenCV cv2.imwrite échoue en silence dans un chemin avec accent (D:\Modélisation…) → donner au générateur des chemins RELATIFS (..\donnees\…).
2026-11-01 NT a demandé pourquoi les calculs sont si longs (essais 6/6b/6c de 2-3 h enchaînés). Engagement pris : d'abord plusieurs petits essais de 20-30 min pour comparer les réglages, puis UN seul long essai. Rythme : essai 2 362 pas/min → 6b/6c ~185 (déguisés, maître, 1 processus, 3 contrôles). La durée est fixée en minutes (--minutes), pas en pas.
