# Étape 6-17 : moins de photos envoyées en vérification

## Le comptage (fait dans le cloud, sans toucher au code)
J'ai rejoué exactement les règles d'échelle actuelles (étape 6-16, réglage « cotes fiables ») sur les lectures
gardées du PC : je retrouve bien **95 photos à vérifier sur 343** et **248 échelles lues, 0 erreur de plus de 3 %**,
comme sur le PC. Ensuite j'ai regardé, pour chaque photo, ce qui la bloque, et j'ai recalculé le style de chaque
photo fabriquée (reflet, flou, bougé, table…). Les 330 plans de ce jeu ont **tous** des cotes dessinées.

| Cause | Photos | Ce que montrent les chiffres |
|---|---|---|
| 1. Coloriage douteux (murs coloriés jusqu'au bord de l'image : table, plis) | 30 | 27 ont pourtant des cotes bien lues (à 3 % près) ; c'est le coloriage autour de la feuille qui bloque |
| 2. Largeur et hauteur en désaccord de plus de 8 % | **2** | presque rien : la piste « 4 coins de la feuille » ne vaut pas la peine pour l'instant |
| 3. Cotes lues dans un seul sens (largeur OU hauteur) | 28 | 21 justes, mais 7 fausses (dont 2 fausses de 3 à 6 %, que les portes ne peuvent pas détecter : elles sont précises à ~10 % seulement) |
| 4. Cotes lues mais refusées (pas d'accord avec la taille du logement) | 3 | négligeable |
| 5. **Aucune cote lue du tout** (alors qu'elles sont dessinées) | **32** | nouvelle cause, la plus grosse ; liée au **bougé** et aux **reflets** |

Le bougé pèse lourd : photo sans bougé → 22 % partent en vérification ; petit bougé (3 à 6 pixels) → 42 % ;
gros bougé (7 pixels) → 78 %. Les reflets aussi : 62 % des photos de la cause 5 ont un reflet, contre 32 % des photos lues.

## Ce que je propose, dans cet ordre
1. **Cause 5, relire les cotes floues** : avant de dire « aucune cote », relire les zones de texte agrandies et
   rendues plus nettes (on annule le flou de bougé, on éclaircit le reflet). 9 de ces photos ont déjà des surfaces
   écrites justes mais jugées « pas sûres » : la relecture les rendrait sûres. Gain estimé : 10 à 20 photos.
2. **Cause 1, repérer la feuille d'abord** : trouver le bord de la feuille sur la table, et ne plus compter les
   « murs » coloriés hors de la feuille. Le garde-fou « coloriage douteux » reste, mais ne regarde plus que la feuille.
   Gain estimé : 15 à 25 photos.
3. **Cause 3, confirmer une cote seule** : l'accepter seulement si une 2e mesure indépendante la confirme à 3 %
   près (surfaces relues, ou cote d'ensemble mesurée sur la feuille). Les portes ne suffisent pas. Gain estimé : 10 à 18.
4. Causes 2 et 4 : laissées de côté (5 photos en tout).

**Estimation honnête : 95 → environ 45 à 60** (un peu moins bien que les 40-50 annoncés, car la cause « désaccord
largeur/hauteur » est presque vide). Règle inchangée : **0 erreur d'échelle de plus de 3 %**, et aucun recul sur
les 1 066 anciens plans ni sur les 342 photos sans cotes. Si une piste fait passer une seule erreur, elle est réglée
ou abandonnée.

## Comment
Code et premiers essais dans le cloud (il faut y réinstaller opencv, pillow, numpy, pydantic, pytest, comme aux
étapes précédentes, dans le cloud seulement). Puis notation sur le PC (les coloriages d'Atelya essai 5 existent
déjà : pas de nouvel entraînement, environ 1 h de bancs). Commit sur le Mac après ton « vas-y », entrée 6-17 dans
le suivi de ton associé (posée sur la PR #16).

Fichiers : photos-par-cause.json (la liste des 95 photos et leur cause), sim.py (le rejeu des règles), styles.py.
