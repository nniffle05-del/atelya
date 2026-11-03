# Étape 6-9 : essai 3 d'Atelya (placards, WC, buanderies)

## Ce qui ne va pas aujourd'hui (essai 2, 983 plans de test)
- WC reconnus à 87 % : 11 % sont pris pour des placards.
- Placards à 92 % : 6 % pris pour des WC.
- Buanderies à 82 % : confondues avec salle d'eau, WC, placard.
- Bureaux à 82 % : confondus avec la cuisine (peu d'exemples : 28).
Toutes les autres pièces sont déjà à 94-100 %.

Pourquoi : ces pièces sont petites (1,5 à 3 m²) et rares. Pendant l'entraînement,
Atelya regarde des morceaux de plan tirés au hasard : il voit rarement un WC
à côté d'un placard, donc il apprend mal à les distinguer.

## Ce que je change (3 réglages, aucune installation)
1. **Montrer plus souvent les petites pièces** : environ 1 morceau sur 2 sera
   centré sur un WC, un placard, une buanderie ou un bureau (au lieu du hasard).
2. **Compter plus fort les erreurs sur ces pièces** : une erreur sur un WC
   « coûte » 2 à 3 fois plus cher à Atelya qu'aujourd'hui, pour qu'il y fasse attention.
3. **Repartir d'Atelya essai 2** au lieu de tout réapprendre : il garde ce qu'il
   sait déjà (murs, portes, grandes pièces) et se perfectionne sur les petites.
   Durée : environ 1 h 30 sur le PC (au lieu de 2 h).

## Comment je mesure (mêmes 983 plans de test qu'avant)
- Bon type de pièce : WC, placard, buanderie, bureau, et toutes les autres.
- Murs, ouvertures, plans parfaits : ne doivent pas reculer.
- **Garde-fou** : si une autre pièce ou les murs reculent de plus de 0,5 point,
  on garde Atelya essai 2 et je t'explique pourquoi.

## Déroulé
1. J'écris le réglage dans le cloud et je le teste sur un petit échantillon (sans toucher au PC).
2. Tu allumes le PC (surélevé, il chauffe à 86 °C) et tu m'écris « lance ».
3. Entraînement ~1 h 30, puis coloriage des 983 plans test (~3 min).
4. Je note et je te montre le avant/après.
5. Si c'est mieux : commit sur le Mac (accord écrit « vas-y ») + entrée 6-9 dans le suivi de ton associé.
