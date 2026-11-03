# Étape 6-8 : Atelya lit lui-même l'échelle du plan

## Pourquoi
Aujourd'hui, quand on note Atelya, on lui **donne** l'échelle exacte (combien de pixels font un mètre) et, pour les photos prises de biais, le bon rapport largeur/hauteur. C'est une triche de banc d'essai : un vrai client ne nous donnera jamais ces chiffres. Sans eux, toutes les mesures en centimètres de la maquette 3D seraient fausses.

Le moteur sait déjà lire les **cotes** (le petit trait avec un nombre « 4,80 » qui dit la vraie longueur), depuis l'étape 3c. Il faut maintenant brancher cette lecture sur la chaîne d'Atelya.

## Le plan, en 4 temps

1. **Diagnostic** : sur les 983 plans de test, lire les cotes de chaque dessin et comparer l'échelle lue à la vraie. On saura combien de plans sont lus à 1 % près, combien ratent, et pourquoi.
2. **Branchement** :
   - plans à plat : l'échelle lue remplace l'échelle exacte ;
   - photos de biais : on lit les cotes sur la photo, on les fait passer dans le redressement ; les cotes horizontales donnent l'échelle en largeur, les verticales en hauteur, ce qui corrige l'écrasement de la photo ;
   - une seule lecture des textes sert à la fois aux noms de pièces et aux cotes ;
   - si les cotes sont introuvables ou en désaccord, le plan est marqué « échelle à vérifier » pour la vérification humaine de 2 minutes, au lieu d'inventer.
3. **Note** sur les 983 plans : échelle exacte contre échelle lue. Objectif : perdre au plus 1 à 2 points sur les murs justes, et que les photos de biais restent au-dessus de 80 %.
4. **Commit sur le Mac** + entrée 6-8 dans le suivi pour l'associé.

## Ce qu'il faudra
- Réinstaller RapidOCR et OpenCV **dans le cloud** (même chose que vous avez acceptée ce matin ; l'ordinateur du cloud a été remis à zéro). Rien sur le Mac ni le PC.
- Recopier depuis le PC les dessins des plans de test (lecture seule, dossier déjà autorisé).
- Hors sujet : les plans **sans aucune cote** (fil arrêté le 24/10).
