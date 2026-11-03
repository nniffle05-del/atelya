---
name: carte-atelya-associe
description: Carte mentale du moteur Atelya pour l'associé (artifact, 2026-11-02) ; REMPLACE les entrées suivi.json ; à mettre à jour à chaque étape
metadata:
  type: project
  modified: 2026-11-02T18:37:17.995Z
---
2026-11-02 19h30 Paris, NT : son associé (sites interne/externe, non technique) ne comprend pas l'état d'Atelya → NT veut une « toile d'araignée » claire des briques. NT a dit que cette carte REMPLACE les ajouts au dashboard suivi-moteur (suivi.json) : ne plus ajouter d'entrée suivi.json à chaque étape (voir [[suivi-moteur-associe]], règle caduque).

Artifact : https://claude.ai/artifact/SHUy3ye6UPhqojRfCPzS6n (privé à NT ; NT doit le partager à l'associé via le menu Partager). Source à jour : /mnt/project-files/carte-atelya/carte-atelya.html (copier dans le scratchpad, publier avec `url` = lien ci-dessus pour garder le même lien).
FORME (ANCIENNE demande 18h40Z, remplacée par le retour à la version 1) : la description s'ouvre dans un panneau au clic sur chaque bulle (centre = notes + 12 cas ; bulle Entraînements = historique des essais ; bouton Lexique). Structure : 6 branches numérotées (1 Préparer l'image, 2 Lire le plan, 3 Mesurer, 4 Se contrôler, 5 Construire le logement, 6 Livrer au client) + « L'atelier » (fabrique, entraînements, bancs, vrais plans, sauvegarde) ; données dans le tableau JS BRANCHES (etat fait/encours/partiel/afaire, val, prov, perf, reste, suite) ; + ESSAIS, CAS, LEXIQUE en JS, notes globales dans le panneau du centre (~61 client / ~92 fabriqués / ~45-48 vrais plans).
STYLE ACTUEL (2026-11-02 19h25Z, VALIDÉ par NT après tous les essais) : UNIQUEMENT la carte mentale de la 1re version (fond clair quadrillé, rond noir « Atelya » au centre, cases de branche colorées 1-6 + L'atelier, briques en pilules blanches avec pastille d'état et chiffre, liens courbes), en PLEIN ÉCRAN sans aucun texte autour ; toucher une case ouvre sa fiche dans un panneau (bas d'écran sur téléphone) ; centre = notes + 12 cas ; Entraînements = historique des essais ; boutons Lexique / − / + / Tout voir. Téléphone : MÊME araignée (Atelya au centre, branches à gauche et à droite, demandé par NT 19h25Z), vue de départ zoomée sur le centre, on glisse et pince. Fabrication : gabarit-actuel.html + donnees.js (remplacer /*DONNEES*/) dans /mnt/project-files/carte-atelya/. Écartés : fond noir, 3D, planche d'architecte, Canva, page complète à sections (version-1-page-complete.html). Ne plus changer le style sans demande de NT.
Chiffres essai 7b marqués provisoires (à 61 min) → à remplacer quand l'essai 7b est mesuré.

**Why:** l'associé doit visualiser ce que contient Atelya et où il en est.
**How to apply:** à chaque fin d'étape, le fil qui finit met à jour la fiche concernée + la date « Mis à jour » + les notes, puis republie au même lien (en plus de la Feuille de route, [[feuille-de-route-a-jour]]).
