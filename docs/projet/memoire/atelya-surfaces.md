---
name: atelya-surfaces
description: Étape 6-11 (2026-10-28) : échelle par surfaces écrites (« 12,5 m² ») pour les 172 niveaux test sans cotes ni barre ; plan, état
metadata:
  type: project
---
NT a dit « oui » (2026-10-28 10h11, fil barre d'échelle) à l'étape surfaces. Plan /mnt/project-files/atelya-surfaces/plan.md : compter les 172 niveaux sans cotes ni barre (surfaces / rien) ; reprendre echelle_par_surfaces de /mnt/project-files/moteur-sans-cotes/travail-interrompu.diff ; brancher après cotes et barre dans echelle_plan.decider ; garde-fou ≥ 2 pièces d'accord + taille logement ; note 983, 0 erreur > 3 % ; commit Mac après « vas-y » + entrée 6-11 suivi (PR posée sur #10).
10h15 plan posté, attente du oui de NT (plan + réinstall cloud).
**Why:** plans d'agence français souvent sans cotes mais avec m² écrits.
**How to apply:** suite de [[atelya-barre-echelle]] ; suivi selon [[suivi-moteur-associe]].
10h14 NT « oui ». Accès dossier Mac OK dans ce fil : moteur cloné par git bundle (sorties/copie-pour-le-cloud-6-11.bundle) ; plans test copiés en 5 zips ~45 Mo (sorties/pour-cloud-6-11/t0-4.zip ; un zip de 240 Mo dépasse le délai de device_stage_files). Copie cloud /tmp/claude-0/w/repo.
Code : moteur/surfaces_ecrites.py (FORME_SURFACE « 12,50 m² » 2 décimales obligatoires ; zones = composantes de l'intérieur du coloriage ; avis par zone √(px/m²) ; groupe d'accord 3 % ; sûre si ≥ 2 zones et ≥ 50 % des m² lus), echelle_plan 0.3.0 (ordre cotes > barre > surfaces > cote d'ensemble ; surfaces PAS sur photo de biais (jusqu'à 6 % d'erreur) ; cotes peu sûres contredites > 3 % par les surfaces → à vérifier), banc (par_surfaces). 6 tests tests/test_surfaces_ecrites.py.
11h20 NOTE 983 (coloriage PARFAIT, jeu Mac) : échelle lue 838 → 1 005 / 1 066 niveaux (78,6 → 94,3 %), 0 erreur > 3 %, 169 par surfaces (médiane 0,06 %, max 2,3 %). Reste 61 à vérifier : 31 sans aucune info, 27 cotés illisibles, 3 surfaces. NB : sur le jeu Mac l'ancien code fait 1 erreur cotes (007997, −3,5 %) que le contrôle surfaces attrape. Livrables /mnt/project-files/atelya-surfaces/ : etape-6-11.diff (sha256 93a7aecd…), bilan-983-parfait-echelle-lue-surfaces.json. Attente « vas-y » pour commit Mac (248 tests attendus) + entrée 6-11 suivi (PR posée sur #10).
2026-10-28 11h10 COMMITÉ sur le Mac : b4f3f0f (248 tests) via RC (diff déposé par device_commit_files dans sorties/, RC OK du 1er coup). Entrée 6-11 suivi.json : PR #11 (branche claude/project-thread-vkrcty posée sur #10 ; fusion #3→#11), abonné #3-#11. Note : ~43/100 prêt client, ~88/100 fabriqués. Piège : suivi.json est en indent=2 (json.dumps indent=1 réécrit tout le fichier). Pistes suivantes : barre coupée dans le générateur ; noter avec coloriages Atelya (PC) ; vrais plans.
