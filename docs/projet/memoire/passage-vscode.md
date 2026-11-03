---
name: passage-vscode
description: Décision NT 2026-11-03 : passer à Claude Code dans VS Code, sur le PC d'abord, sur le Mac plus tard (étapes Blender) ; CLAUDE.md à écrire
metadata:
  type: project
  modified: 2026-11-03T12:54:00.650Z
---
Le 2026-11-03 à 12h53Z, NT a dit « oui » à l'installation de VS Code + Claude Code. Ce qui a été convenu :
- **PC d'abord.** Le pilote est l'étape A2 (lecture des PDF).
- **Mac plus tard**, quand on fera les étapes photos, habillage et Blender.
- On peut suivre une session du PC depuis le Mac ou le téléphone, par l'appli Claude. Pas besoin d'installer quoi que ce soit sur le Mac pour ça.

Livrables demandés au coordinateur, pour un nouveau fil :
- un guide d'installation (VS Code, extension Claude Code, Git, connexion GitHub, clonage de nniffle05-del/atelya) ;
- un CLAUDE.md dans le dépôt, qui reprend les règles de NT et l'état du projet. Raison : un Claude Code local démarre sans la mémoire de ce projet.

**Why:** supprimer les transferts à la main et les sessions à distance qui échouent, et voir les entraînements en direct.
**How to apply:** aucune installation sans l'accord écrit de NT, étape par étape. Ce projet claude.ai reste en place pour la Feuille de route, la carte et la mémoire. Voir [[environnement-poste-nt]], [[gros-calculs-sur-pc]].

2026-11-03 13h0xZ (fil « Installer Claude Code sur le PC ») : guide pas à pas = Claude Doc https://claude.ai/artifact/VRQR3LbcmLmbTNLp9ou4pb (étapes 0 fusion GitHub, 1 veille, 2 Git, 3 VS Code, 4 extension, 5 clone, 6 premier essai, 7 /remote-control). Clone prévu dans D:\Modélisation immobilière\atelya-code (À CÔTÉ de l'ancien dossier atelya, pas dedans : depuis atelya-code, ..\atelya\ = chemin relatif sans accent). Python du PC = ancien atelya\.venv (pas de pytest → lancer_tests.py à la racine du dépôt).
CLAUDE.md (20 Ko) + docs/projet/ (mémoire complète + plans d'étape recopiés) prêts dans le cloud, branche claude/project-thread-o88gks = nvpbiz (A1+A3) + fusion gd7qyt (P3) + CLAUDE.md, commit e861f99, PAS ENCORE POUSSÉE : NT relit d'abord. Copie /mnt/project-files/passage-vscode/CLAUDE.md. GitHub main (1465183) est EN RETARD sur le Mac (20ce703) : la PR de ce fil le remet à jour.
