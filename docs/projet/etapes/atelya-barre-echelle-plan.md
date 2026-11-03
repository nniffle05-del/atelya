# Étape 6-10 : Atelya lit la barre d'échelle dessinée

## Pourquoi
Pour construire la maquette 3D aux bonnes mesures, il faut savoir combien de pixels du dessin font un mètre : c'est **l'échelle**. Depuis l'étape 6-8, Atelya la lit sur les **cotes** (les longueurs écrites, comme « 4,80 »). Mais certains plans, surtout ceux des agences, n'ont **aucune cote**. Certains ont à la place une petite **barre d'échelle** sous le dessin : une règle en cases noires et blanches marquée « 0 » et « 2 m ». Aujourd'hui Atelya ne la regarde pas : ces plans partent tous à la vérification humaine, faute d'échelle.

Bonne nouvelle : le 24/10, dans le fil « Lire les plans sans cotes » (arrêté), on avait déjà écrit un lecteur de barre d'échelle pour l'ancien moteur. Il est gardé de côté et on peut le reprendre.

## Le plan, en 5 temps
1. **Compter** : parmi les plans de test sans cotes, combien ont une barre, combien ont seulement les surfaces écrites (« Chambre 12,5 m² »), combien n'ont rien.
2. **Lire la barre** : reprendre le lecteur du 24/10 et le brancher comme les cotes : sur le dessin pleine taille, remis droit comme le coloriage (y compris les photos de biais). On trouve le texte « 2 m », la barre juste au-dessus, on mesure sa longueur en pixels : 180 pixels pour 2 m = 90 pixels par mètre.
3. **Garde-fou** : l'échelle de la barre n'est gardée que si ses cases sont régulières et que la taille du logement qu'elle donne est vraisemblable. Sinon : « échelle à vérifier » (vérification humaine de 2 minutes) plutôt qu'une maquette à la mauvaise taille. Si un plan a à la fois des cotes et une barre, on vérifie qu'elles sont d'accord.
4. **Note** sur les 983 plans de test : combien de plans sans cotes ont maintenant une échelle juste (objectif : presque tous ceux qui ont une barre, avec 0 erreur de plus de 3 %), et que rien d'autre ne recule.
5. **Commit sur le Mac** (après ton « vas-y ») + entrée 6-10 dans le suivi pour l'associé.

## Ce qu'il faudra
- Réinstaller **dans le cloud** les mêmes outils que d'habitude (OpenCV pour les images, RapidOCR pour lire les textes, pydantic, pytest) : l'ordinateur du cloud a été remis à zéro. Rien sur le Mac ni sur le PC.
- Recopier depuis le PC les dessins des plans de test (lecture seule, dossier déjà autorisé).
- Durée estimée : une soirée de travail, sans entraînement sur le PC.
