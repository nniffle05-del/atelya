# Étape A1 : Atelya repère ses doutes (plan détaillé, 02/11/2026)

## Le but, en une phrase
Qu'aucun plan faux ne passe « en silence » : chaque fois qu'Atelya se trompe, il doit l'avoir signalé.
On ne change PAS ce qu'Atelya lit ; on ajoute seulement des drapeaux « à vérifier ».

## Ce qu'on construit
1. Relecture sous plusieurs angles (PC) : Atelya colorie le plan 4 fois (normal, retourné gauche-droite,
   haut-bas, les deux). Là où ses 4 lectures ne sont pas d'accord, ou quand il hésite entre deux couleurs,
   on obtient une « carte des doutes ». Script PC outils/atelya/colorier_angles.py (rien à installer).
2. Doutes par élément (moteur/doutes.py) : pour chaque mur, porte, fenêtre et pièce lus, la part de
   pixels douteux dessous → confiance de 0 à 100 %.
3. Contrôles de bon sens (moteur/doutes.py) sur le logement lu :
   chaque pièce a une porte ou un passage ; fenêtre sur un mur extérieur ; épaisseur de mur 5-60 cm ;
   ouverture pas plus large que son mur ; surfaces plausibles (WC < 4 m², chambre > 6 m², pièce > 1 m²) ;
   pièces qui se chevauchent ; bout de mur qui ne touche rien ; somme des pièces ≈ surfaces écrites.
4. Refus « ce n'est pas un plan » : trop peu de murs, aucun logement fermé, image presque vide.
5. Décision par plan : « lu sans vérification » / « à vérifier » (avec la liste des doutes, au format de
   l'écran de vérification : élément, zone, raison) / « refusé ».

## Comment on le mesure (PC, comme les bancs habituels)
- Jeux : 1 066 plans fabriqués, 342 photos sans cotes, 343 photos réalistes avec cotes, plus les 13 vrais plans.
- Chiffre principal : ERREURS SILENCIEUSES = plans qui ont une vraie erreur (mur faux, porte manquante,
  pièce ratée, échelle fausse) et qu'Atelya n'a pas signalés. Objectif : les diviser au moins par 2.
- Prix à payer : plans justes envoyés en vérification pour rien. Objectif : pas plus de +10 points.
- Les seuils sont réglés sur une moitié des plans et contrôlés sur l'autre (pour ne pas tricher).
- Sur les 13 vrais plans : les 3 ratés (fr-005, fr-008, fr-017) doivent être signalés.
- Garde-fous : lecture inchangée (mêmes notes murs/ouvertures/pièces), 0 erreur d'échelle > 3 % inchangé.

## Déroulé
1. Cloud : coder doutes.py + tests, essai sur les coloriages parfaits (aucune fausse alerte attendue). ~2-3 h
2. PC (Remote Control, avec ton accord) : coloriage sous 4 angles des jeux de test + banc avec doutes. ~3-5 h de calcul
3. Réglage des seuils, bilan, puis commit Mac, sauvegarde GitHub, suivi, Feuille de route, note /100.
