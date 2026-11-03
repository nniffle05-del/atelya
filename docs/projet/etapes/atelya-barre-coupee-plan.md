# Étape 6-12 : réparer la barre d'échelle coupée, puis noter Atelya « pour de vrai »

## Pourquoi
1. **La barre coupée.** Notre fabrique de plans (le « générateur ») dessine la barre d'échelle sous le logement, mais elle ne laisse pas assez de place en bas de la page : sur environ la moitié des plans, la barre ou son texte « 2 m » dépasse du bord et disparaît. Atelya ne peut pas lire une barre qu'on ne voit pas. Ce n'est pas un défaut d'Atelya, c'est un défaut de nos plans d'entraînement et de test. Un vrai plan d'agence montre toujours sa barre en entier.
2. **La note « pour de vrai ».** Jusqu'ici, on a noté la lecture d'échelle avec un **coloriage parfait** (le coloriage exact que la fabrique connaît). C'est utile pour tester une idée, mais c'est trop gentil : en vrai, c'est **Atelya** qui colorie, avec ses petites erreurs. Une pièce un peu mal coloriée donne une surface un peu fausse, donc une échelle un peu fausse. Il faut savoir si on garde « 0 erreur de plus de 3 % » avec les vrais coloriages d'Atelya.

## Le plan, en 5 temps
1. **Réparer la fabrique** (dans le cloud) : dans le dessin de la barre, agrandir la marge du bas quand il y a une barre, ou remonter la barre si la page est trop courte. On ajoute un test qui vérifie que la barre et son texte sont toujours entièrement dans la page. On change le numéro de version de la fabrique.
2. **Refabriquer les 983 plans de test** avec la fabrique réparée (même logements, même graines : seule la barre change). Les plans d'entraînement ne bougent pas : pas besoin de ré-entraîner Atelya.
3. **Faire colorier ces 983 plans par Atelya sur le PC** (≈ 3 min sur la carte graphique, comme le 26/10). Il me faudra ton « lance » écrit dans le fil, car le PC demande un accord écrit avant de lancer du code.
4. **Note honnête** sur les 983 plans : échelle lue avec les coloriages d'Atelya (cotes, barre, surfaces), à comparer au coloriage parfait ; on regarde surtout le nombre d'erreurs de plus de 3 %, et combien de barres sont maintenant lues (on en attend ~19 de plus).
5. **Commit sur le Mac** (après ton « vas-y ») + entrée 6-12 dans le suivi pour l'associé (posée sur la #11).

## Ce qu'il faudra
- Réinstaller **dans le cloud** les outils habituels (OpenCV, RapidOCR, pydantic, pytest) : l'ordinateur du cloud repart à zéro. **Rien de nouveau sur le Mac ni sur le PC.**
- Accès au PC (Remote Control) pour l'étape 3, et au Mac pour copier le code et le commit.
- Limite honnête : si les surfaces lues avec Atelya font des erreurs > 3 %, je durcirai le garde-fou (plutôt « à vérifier » qu'une maquette fausse), et je te le dirai.
