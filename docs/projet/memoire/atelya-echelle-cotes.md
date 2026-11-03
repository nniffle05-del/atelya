---
name: atelya-echelle-cotes
description: Étape 6-8 (2026-10-27) : échelle d'Atelya lue sur les cotes du dessin (moteur/echelle_plan.py) au lieu de l'échelle exacte ; chiffres et état du commit
metadata:
  type: project
---
Fil « Lire les cotes pour l'échelle d'Atelya » (2026-10-27, plan validé par NT). Copie cloud /tmp/claude-0/w/repo (6-7 + echelle_plan). Dessins test : zip fait sur le PC par Remote Control (atelya\dessins-test.zip, 148 Mo, 1 066 dessins) — bien plus rapide que device_stage_files fichier par fichier.
moteur/echelle_plan.py : lit les cotes (lecture_cotes) sur le dessin pleine taille remis droit comme le coloriage (rotation, ou homographie du redressement avec cadre élargi pour garder les cotes) ; largeur/hauteur séparées sur photo → corriger_proportions ; garde-fou decider() : taille intérieure du logement colorié / échelle vs plus grande cote lue (cote d'ensemble), sinon « à vérifier » ; secours par cote d'ensemble si largeur et hauteur concordent (à plat). banc_coloriage --echelle lue (cache echelles-lues/). 6 tests (237 attendus sur le Mac).
Résultats 1 066 niveaux test : échelle lue 819 (96 % des 855 plans cotés ; 211 plans sans aucune cote → vérif humaine), médiane 0,045 %, 98,9 % à 1 % près, 0 erreur > 3 % (6 avant garde-fou). Mêmes 819 niveaux, échelle exacte → lue : murs justes 90,5 → 89,7, ouv 89,7 → 89,5, bon type 95,1 → 95,0, hors-tout ±10 cm 98,2 → 97,1, parfaits 41,0 → 41,3 ; photos de biais murs 90,9 → 87,9. Livrables /mnt/project-files/atelya-cotes/ (paquet etape-6-8.tar.gz sha256 46b3e92c…, base banc_coloriage 0d5cb375…).
Lecture lente : ~10-25 s par plan (OCR pleine taille), ~40 min les 1 066 sur 4 cœurs.
COMMITÉ sur le Mac 2026-10-27 : dfd50c7 (237 tests). Entrée 6-8 suivi.json : PR #8 posée sur #7 (fusion #3→…→#8). Astuce : le brief RC doit être passé dans `instructions` de start_remote_control, sinon la session Mac ne reçoit que le message de NT.
**Why:** un client ne donne jamais l'échelle ; sans elle les cm de la maquette sont faux.
**How to apply:** suite de [[atelya-petites-pieces]] ; entrée 6-8 suivi.json (PR posée sur #7) selon [[suivi-moteur-associe]]. Pistes : barre d'échelle graphique (39 plans), plans sans cotes (fil arrêté par NT, ne pas relancer sans lui).
