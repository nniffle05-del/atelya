---
name: atelya-petites-pieces
description: Étape 6-7 (2026-10-27) : traducteur coloriage 0.3 (ouvertures recalées, zones à 2 couleurs coupées, noms de pièces lus par RapidOCR) ; chiffres, commit 967b37f, PR #7
metadata:
  type: project
---
2026-10-27 (fil « petites pièces + portes-fenêtres ») : moteur/coloriage.py 0.3.0 (regulariser_ouvertures, separer_par_couleur / separer_par_noms), nouveau moteur/noms_pieces.py (RapidOCR, mots → type, « cellier/local/cave » ambigus), banc_coloriage --noms --images. NT a accepté RapidOCR dans le cloud (déjà présent sur le Mac). Livrables /mnt/project-files/atelya-petites-pieces/.
Atelya 983 plans test, sans noms : murs justes 86,0 → 89,7 %, ouv 85,7 → 88,5 %, portes-fenêtres à plat 83,8 → 98,2 %, pièces trouvées 92,9 → 97,6 %, bon type 89,1 → 93,8 %, plans parfaits 23 → 38 %. Avec noms (200 niveaux) : bon type 94,2 → 97,1 %, WC 80 → 91, buanderie 88 → 98. Contrôle Mac coloriage parfait + noms (100 plans) : murs 99,2, ouv 99,8, pièces 100/100, plans parfaits 93,8 %.
COMMITÉ Mac 967b37f (231 tests). Entrée 6-7 : PR #7 suivi-moteur (branche claude/project-thread-n72uvw posée sur #6). NT a choisi : commit maintenant, essai 3 d'Atelya plus tard (étape séparée). Restent faibles : placards ~90 %, WC ~91 %.
**Why:** NT veut Atelya performant sur chaque type de pièce avant les clients.
**How to apply:** suite de [[atelya-redressement]] ; prochaines pistes : lecture des cotes branchée sur Atelya (échelle + proportions), puis essai 3. Suivi selon [[suivi-moteur-associe]].
2026-10-27 15h10 : fil « Lire les cotes pour l'échelle d'Atelya » ouvert (étape 6-8) ; il reprend le suivi des PR #3-#7 (fil petites pièces fermé par NT). Plan présenté (/mnt/project-files/atelya-cotes/plan.md), en attente du oui de NT + accord réinstall RapidOCR/OpenCV cloud.
