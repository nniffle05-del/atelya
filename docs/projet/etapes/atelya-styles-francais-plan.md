# Étape 6-19 : apprendre à Atelya les styles des vrais plans français

## Pourquoi
Sur 13 vrais plans (lot du 31/10), Atelya trouve bien les murs sur 10 plans, mais rate 3 plans et se trompe souvent de type de pièce,
parce que notre générateur ne dessine jamais certains styles très courants en France.

## Ce qu'on ajoute au générateur (nouvelle famille de styles « diagnostiqueur / agence française »)
1. Sols dessinés : carrelage quadrillé, parquet, hachures (fr-008 : Atelya a pris le carrelage pour des escaliers).
2. Murs en trait fin : simple trait de 1 à 3 px, ou double trait vide (fr-005, fr-015, fr-016).
3. Murs gris très clair, sans contour (fr-017).
4. Lettres A, B, C, D… écrites le long des murs, comme sur les croquis Carrez (fr-014, fr-016).
5. Noms de pièces en couleur (vert, violet, bleu), en majuscules, et capture d'écran de téléphone (barre d'état en haut).
La « bonne réponse » de chaque plan fabriqué ne change pas : un sol carrelé reste la pièce, une lettre reste du fond.
Les anciens jeux restent identiques (même graine → même plan), comme aux étapes précédentes.
Les murs en biais ne sont PAS dans cette étape : c'est une étape à part (générateur + traduction 3D), à faire juste après.

## Déroulé
1. Cloud : écrire le code + tests, montrer à NT une planche de 16 exemples.
2. PC (après « vas-y ») : fabriquer ~3 000 plans de ces styles (~15-20 min).
3. PC : essai 6 = Atelya essai 5 qui continue d'apprendre sur ces plans + les anciens (pour ne rien oublier), ~2 h.
4. PC : garde-fous (aucun recul sur les 1 066 anciens, les 342 photos sans cotes et les photos réalistes), plusieurs heures, la nuit si besoin.
5. Recolorier les 13 vrais plans : comparaison avant / après, plan par plan.
6. Note /100, commit sur le Mac après « vas-y », entrée 6-19 dans le suivi, Feuille de route mise à jour.

## Ce qu'il faut de NT
- « oui » au plan ;
- accord pour réinstaller dans le cloud les outils habituels (opencv, pillow, numpy, pydantic, pytest) : rien sur le Mac ni sur le PC.
