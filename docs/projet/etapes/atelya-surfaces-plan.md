# Étape 6-11 : Atelya trouve l'échelle grâce aux surfaces écrites des pièces

## Pourquoi
Pour construire la maquette aux bonnes mesures, Atelya doit savoir combien de pixels du dessin font un mètre (l'**échelle**). Il la lit sur les cotes (étape 6-8) ou sur la barre d'échelle (étape 6-10). Mais sur les 983 plans de test, **172 niveaux n'ont ni cotes ni barre** : aujourd'hui ils partent tous à la vérification humaine. Or beaucoup de plans d'agence français écrivent la surface dans chaque pièce (« Chambre 12,5 m² »). C'est un indice d'échelle.

## L'idée, avec un exemple
Atelya a déjà colorié la chambre : elle couvre, disons, 50 000 pixels. Le plan dit « 12,5 m² ». Donc 1 m² = 4 000 pixels, et 1 m = la racine de 4 000 ≈ 63 pixels. Une seule pièce peut tromper (surface « habitable » sans les placards, nombre mal lu). Alors on fait voter **toutes** les pièces : on ne garde l'échelle que si plusieurs pièces sont d'accord entre elles.

## Le plan, en 5 temps
1. **Compter** : parmi les 172 niveaux sans cotes ni barre, combien ont des surfaces écrites, et combien n'ont vraiment rien.
2. **Lire les surfaces** : reprendre le lecteur écrit le 24/10 dans le fil arrêté « Lire les plans sans cotes » (il est gardé de côté) et le brancher comme la barre : le texte « 12,5 m² » est rattaché à la pièce coloriée qui le contient.
3. **Garde-fou** : au moins 2 pièces d'accord à quelques % près, et un logement de taille vraisemblable. Sinon : « échelle à vérifier » (2 minutes de vérification humaine) plutôt qu'une maquette fausse. Les cotes et la barre restent prioritaires ; les surfaces ne servent qu'en dernier recours.
4. **Note** sur les 983 plans de test : combien de ces 172 niveaux ont maintenant une échelle juste, avec **0 erreur de plus de 3 %**, et rien d'autre qui recule.
5. **Commit sur le Mac** (après ton « vas-y ») + entrée 6-11 dans le suivi pour l'associé.

## Ce qu'il faudra
- Réinstaller **dans le cloud** les mêmes outils que d'habitude (OpenCV, RapidOCR, pydantic, pytest) : l'ordinateur du cloud a été remis à zéro. Rien sur le Mac ni sur le PC.
- Les dessins de test : les refabriquer dans le cloud comme la dernière fois (même résultat, ~2 h), ou les lire sur le PC si l'accès au dossier fonctionne.
- Limite honnête : une surface écrite est souvent la surface « habitable », un peu plus petite que la pièce dessinée. L'échelle par surfaces sera donc moins précise que par cotes (on vise ±2 à 3 %, contre ±0,1 % pour les cotes).
