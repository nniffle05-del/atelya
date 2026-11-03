# Étape 6-14 : lire les photos de plans prises de biais ET sans cotes

## Pourquoi
Un client prendra souvent son plan en photo avec son téléphone, un peu de travers. Atelya sait déjà « remettre la feuille à plat » (étape 6-6). Mais il lui reste deux inconnues que, jusqu'ici, seules les **cotes** (« 3,45 ») lui donnaient :

1. **Les proportions** : une fois la feuille remise à plat, Atelya ne sait pas si le dessin a été un peu « écrasé » dans un sens (comme une photo étirée). Sans cotes, il se trompe souvent : aujourd'hui seulement **~35 % des murs justes** sur ces photos, contre **~91 %** quand il y a des cotes.
2. **L'échelle** (combien de pixels font 1 mètre) : la barre d'échelle et les surfaces écrites (« 12,50 m² ») ne sont pas utilisées sur une photo de biais, car sans les bonnes proportions elles donnaient jusqu'à 6 % d'erreur.

## Les idées pour s'en passer
- **La géométrie de l'appareil photo** : quand une photo est prise de biais, les lignes parallèles du plan se rejoignent au loin (les « points de fuite »). Avec deux de ces points, on peut calculer comment l'appareil était penché, et donc retrouver les vraies proportions. C'est un calcul classique, sans rien à installer de nouveau.
- **Ce qu'on sait par cœur, en contrôle** : une porte fait ~83 cm qu'elle soit dans un mur horizontal ou vertical ; les murs ont la même épaisseur dans les deux sens. Si le dessin est écrasé, ces mesures ne concordent plus, et on corrige.
- **Puis l'échelle** : une fois les proportions retrouvées, on réutilise la barre d'échelle, les surfaces écrites, ou à défaut l'échelle approchée par les portes, **toujours marquée « à vérifier »** si on n'est pas sûr.

## Le plan, en 5 temps
1. **Compter et regarder** (léger, cloud) : combien de plans test sont des photos de biais sans cotes, et où Atelya se trompe aujourd'hui.
2. **Écrire le code** (proportions + échelle sur photo) et ses tests, dans le cloud.
3. **Gros calcul = la note sur les 1 066 niveaux → sur le PC** (comme d'habitude), avec un contrôle que les plans à plat et les plans cotés ne reculent pas.
4. **Note honnête** : murs justes / échelle lue sur les photos de biais sans cotes, avant → après ; 0 erreur > 3 % visée.
5. **Commit sur le Mac** (après ton « vas-y ») + entrée 6-14 dans le suivi pour l'associé (posée sur la #13).

## Ce qu'il faudra
- **Dans le cloud** : réinstaller les outils déjà utilisés (OpenCV, RapidOCR, pydantic, pytest ; rien de nouveau), car l'ordinateur du cloud repart à zéro. **C'est une installation : il me faut ton accord.**
- **Le Mac allumé** au début, pour que je copie le moteur et les plans test dans le cloud.
- **Le PC allumé** à l'étape 3 (je te préviendrai) ; le code arrivera par zip (e-mail) comme la dernière fois.
- Limite honnête : il y a peu de photos de biais sans cotes dans le jeu test (quelques dizaines). Si c'est trop peu pour une note fiable, je fabriquerai quelques centaines de photos de plus (je te demanderai avant, ça se fait sur le PC).
