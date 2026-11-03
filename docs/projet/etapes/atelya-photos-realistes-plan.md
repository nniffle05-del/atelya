# Étape 6-16 : rendre les photos d'entraînement réalistes

## Pourquoi
Aujourd'hui, une « photo » fabriquée est un plan vu de biais posé sur un fond uni de la même couleur que le papier, avec une lumière un peu inégale. On ne voit ni le bord de la feuille, ni la table, ni d'ombre, ni de reflet, ni de pli. Un vrai client photographiera son plan sur une table en bois, sous une lampe, feuille pliée en quatre. Atelya n'a jamais vu ça : il risque d'y colorier des murs dans le bois de la table ou de rater les murs sous un reflet.

Point de départ (Atelya essai 4, 342 photos sans cotes) : murs justes 70,8 %, bon type de pièce 86,9 %, échelle lue 60,8 %, aucune erreur d'échelle de plus de 3 %.

## Ce que j'ajoute au générateur (dans le cloud)
Une nouvelle option `--photo-realiste`, tirée au hasard à part : les anciens jeux restent identiques au pixel près.
1. **Vraie table autour de la feuille** : bois (veines), stratifié, nappe, bureau sombre ou clair. Le bord de la feuille devient visible.
2. **Ombres** : ombre de la feuille sur la table, ombre douce du téléphone ou de la main qui tombe sur le plan.
3. **Reflets** : tache de lumière d'une lampe ou d'une fenêtre sur le papier (zone presque blanche où les traits pâlissent).
4. **Papier froissé ou plié** : plis en croix d'une feuille pliée en quatre (ligne d'ombre + ligne claire), petites ondulations ; feuille légèrement bombée. Quand le papier se déforme, les « corrigés » (les masques qui disent à Atelya où sont les murs) sont déformés exactement pareil, pour qu'ils restent justes.
5. **Flou** : mise au point ratée sur un bord, petit flou de bougé, bruit du capteur d'un téléphone le soir, couleurs tirant vers le jaune (ampoule) ou le bleu (jour).
6. Rien ne cache le plan lui-même (pas de doigt posé sur un mur) : sinon on demanderait à Atelya de deviner un mur invisible.

Je montre d'abord une **planche d'une douzaine d'exemples** pour que tu juges si ça ressemble à tes propres photos.

## Sur le PC (gros calculs)
1. Fabriquer ~2 600 photos réalistes pour l'apprentissage (moitié avec cotes, moitié sans) et ~340 photos réalistes de contrôle jamais vues (environ 45 min).
2. Noter Atelya essai 4 sur ces photos réalistes : c'est le vrai point de départ, il dira combien le réalisme le gêne (environ 35 min).
3. **Essai 5** : on repart de l'essai 4 et on lui montre un mélange photos réalistes + anciennes photos + anciens plans. Environ 2 h, lancé seulement après ton « lance » écrit.
4. Notes : photos réalistes, les 342 anciennes photos et les 1 066 anciens plans. Garde-fous : pas plus de 0,5 point de recul sur les anciens plans, toujours 0 erreur d'échelle de plus de 3 %. Si l'essai 5 recule, on garde l'essai 4.

## Fin
Note honnête /100, puis commit sur le Mac après ton « vas-y » et entrée 6-16 dans le suivi de ton associé (posée sur la PR #15).

## Ce que ça ne remplace pas
Ce sont toujours des photos fabriquées. Seul un test sur de vraies photos de vrais plans dira si le gain est réel ; on le fera quand tu le décideras.

## Durée
Code + planche : quelques heures dans le cloud. PC : environ 4 h 30 en tout (dont 2 h d'entraînement).

## Ce dont j'ai besoin
- Ton « oui » à ce plan.
- Ton accord pour réinstaller dans le cloud (pas sur tes machines) les outils de dessin déjà utilisés à l'étape 6-14 (opencv, pillow, numpy, pydantic, pytest) pour fabriquer et tester les photos ici.
