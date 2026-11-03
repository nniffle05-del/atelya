---
name: sauvegarde-atelya
description: Sauvegarde d'Atelya (P1, 2026-11-02) : dépôt GitHub privé nniffle05-del/atelya, ce qui y est, ce qui reste à envoyer
metadata:
  type: project
---
2026-11-02, fil « Sauvegarder le code et les modèles d'Atelya ». NT : « juste GitHub privé » (disque externe acheté plus tard).
Dépôt PRIVÉ créé par NT : nniffle05-del/atelya, enregistré dans les dépôts du projet.
FAIT : code Mac moteur-3d poussé sur main (11c5423, 36 commits, 108 fichiers) via `git bundle create ~/Desktop/atelya.bundle --all` tapé par NT dans Terminal + fichier joint au fil + push depuis le cloud. Méthode à réutiliser à chaque étape commitée (le Mac n'a pas d'identifiants GitHub).
Mesures : Mac moteur-3d 5,7 Go dont sorties 5,4 Go (régénérable), aucun modèle sur le Mac. PC atelya 20,8 Go : donnees 9,7 Go (régénérable), .venv/.cache-uv/.pythons 8,7 Go (réinstallables), 18 .pt de 65,7 Mo dans resultats-* (utiles : essai 2, 3, 4, 5 [atelya-essai-4.pt], 6e ×2), scripts racine + code-6-13…code-6-19 + depot-6-19 (~15 Mo, pas de git), vrais-plans 11,3 Mo (lot-2026-10-31 : 13 jpg fr-003…fr-017). entrainer.py est à la RACINE d'atelya (pas outils\atelya). Le PC n'a pas git.
FAIT aussi : archive PC (583 fichiers, zip sha 410e3625…) → dossier pc/ du dépôt (commit 1465183, pc/MODELES.txt = SHA256 des 18 .pt). FAIT 2026-11-02 07h12Z : release privée modeles-2026-11-02 (6 .pt essai-2/3/4/5/6e/6e-dernier, SHA256 vérifiés = MODELES.txt). P1 marqué FAIT sur la Feuille de route. Restent sur le PC des dossiers de travail que NT peut supprimer : sauvegarde-pc-2026-11-02 (34 Mo), modeles-a-envoyer (394 Mo), modeles-pour-github-2026-11-02 (1,1 Go, 18 modèles). Plus tard : disque externe (NT l'achètera).
**Why:** code et modèles n'existaient que sur une seule machine chacun ([[sujets-produit-non-traites]]).
**How to apply:** après chaque étape commitée, refaire un bundle et le pousser sur atelya.

2026-11-03 : la création de release est refusée dans les fils projet (« not permitted for this session type »). Méthode de repli : branche orpheline `sauvegarde-modeles`, un dossier par date, .pt coupés en morceaux de 40 Mo (split -b 40M) avec un LISEZMOI pour les recoller et les SHA256. 1re fois : modeles-2026-11-03 (essai 7b), commit 44a2cf8.
