# Étape 6-13 : affiner la lecture de l'échelle d'Atelya

## Pourquoi
L'**échelle**, c'est la règle « combien de pixels du dessin font 1 mètre ». Si elle est fausse, toute la maquette 3D est trop grande ou trop petite.
Aujourd'hui, sur les 1 066 niveaux de test, Atelya trouve l'échelle seul sur 94 % d'entre eux, sans jamais se tromper de plus de 3 %. Il reste trois choses à soigner :

1. **Un petit biais de la barre d'échelle (~ +0,5 %).** Quand Atelya mesure la barre dessinée « 0 — 2 m », il trouve une longueur un peu trop grande, sans doute parce qu'il compte aussi l'épaisseur du trait du cadre. Sur une pièce de 5 m, ça fait 2,5 cm de trop. Ce n'est pas grave, mais c'est une erreur **toujours dans le même sens**, donc facile à corriger.
2. **27 niveaux cotés dont les cotes sont illisibles.** Les cotes sont là (« 3,45 »), mais Atelya n'arrive pas à les lire ou à les rattacher à leur trait. Je veux comprendre pourquoi (texte trop petit, tassé, abîmé…) et récupérer ceux qui peuvent l'être.
3. **31 niveaux sans aucune information d'échelle** (ni cotes, ni barre, ni surfaces écrites). Là, aucun lecteur ne peut deviner l'échelle exacte. L'idée : proposer une **échelle approchée** à partir de ce qu'on connaît par cœur (une porte d'intérieur fait 73, 83 ou 93 cm ; un mur porteur ~20 cm), **toujours marquée « à vérifier »**, pour que la vérification humaine prenne 30 secondes au lieu de tout mesurer à la main. Jamais d'échelle devinée envoyée en maquette sans contrôle.

## Le plan, en 5 temps
1. **Regarder** (léger, dans le cloud) : quelques plans de chaque groupe, pour savoir ce qui bloque vraiment.
2. **Corriger** le code (barre, cotes, échelle approchée) + tests, dans le cloud (c'est de l'écriture, pas du gros calcul).
3. **Gros calcul = la note sur les 1 066 niveaux → sur le PC**, comme tu l'as demandé (voir « Ce qu'il faudra »).
4. **Note honnête** : niveaux lus, erreurs > 3 % (on vise toujours 0), biais de la barre avant / après.
5. **Commit sur le Mac** (après ton « vas-y ») + entrée 6-13 dans le suivi pour l'associé (posée sur la #12).

## Ce qu'il faudra
- **Sur le PC**, pour faire la note là-bas : ajouter dans le dossier `atelya` les outils de lecture déjà présents sur le Mac (OpenCV, RapidOCR, pydantic, ~150 Mo, aucun logiciel nouveau). **C'est une installation : il me faut ton accord.** Et le code du moteur devra arriver sur le PC (je l'envoie dans le Remote Control s'il est petit, sinon un zip par e-mail comme la dernière fois).
- Dans le cloud : réinstaller ces mêmes outils pour écrire et tester le code (l'ordinateur du cloud repart à zéro).
- Limite honnête : pour les 31 niveaux sans information, on ne gagnera **pas** de niveaux « lus tout seuls » ; on gagne du temps de vérification. Et le biais de 0,5 % ne change presque rien à la note : c'est de la finition.
