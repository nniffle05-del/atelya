# Essai 8 : lancer et suivre (PC)

Pourquoi : le lecteur en service n'a appris que sur des plans fabriqués ; l'essai 8 lui montre aussi les vrais plans d'entraînement.
`entrainer_essai8.py` est aussi posé à la racine de `..\atelya\` (il importe `entrainer.py` et `oeil.py` de ce dossier).

Depuis le dépôt `atelya-code` :

    powershell -ExecutionPolicy Bypass -File pc\essai8\petits-essais-8.ps1 -Phase jeu
    powershell -ExecutionPolicy Bypass -File pc\essai8\petits-essais-8.ps1 -Phase eclair
    powershell -ExecutionPolicy Bypass -File pc\essai8\petits-essais-8.ps1 -Phase T0     (puis T1, T2 : 25 min chacun)
    powershell -ExecutionPolicy Bypass -File pc\essai8\petits-essais-8.ps1 -Phase long -PartVrais 0.3 -Minutes 180

Avant un long calcul : désactiver la veille, surélever le PC, lancer la page en direct (`.venv\Scripts\python.exe en_direct.py` depuis `..\atelya`), surveiller toutes les 30 min (`..\atelya\essai8.suivi`, `resultats-essai-8-*\journal.log` : perte, « nan », lots sautés, notes). Ne pas fermer la fenêtre PowerShell.

Modèle gardé : meilleure note « vrais » sans recul de plus de 0,5 point sur les anciens, les photos et les biais. Jugement de mise en service ensuite : 40 plans d'examen + bancs habituels (règle 8 de CLAUDE.md). Les plans d'examen n'entrent jamais dans le jeu : `preparer_jeu_vrais.py` les refuse.

Éclair du 06/11/2026 (1 min, 2 plans de test) : tourne sans « nan », notes affichées, voir `docs/projet/etapes/essai8-eclair-2026-11-06.log`.
