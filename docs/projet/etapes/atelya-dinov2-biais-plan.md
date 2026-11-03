# Étape A3 : donner un « œil » DINOv2 et les murs en biais à Atelya

*Plan proposé le 2 novembre 2026. Rien n'est lancé tant que tu n'as pas dit oui.*

## Pourquoi cette étape

- **Le plafond de l'essai 6.** Les essais 6 à 6e ont montré qu'Atelya, un petit réseau appris de zéro sur nos plans fabriqués, n'arrive plus à progresser : quand il apprend de nouveaux styles, il perd un peu ailleurs (les murs reculent de 3 à 7 points). Il lui manque une « vue » générale des images.
- **DINOv2**, c'est un « œil » déjà entraîné par Meta sur 142 millions de photos du monde réel. Il sait déjà reconnaître des traits, des textures, du papier, des ombres. La licence est **Apache 2.0** : on peut s'en servir commercialement (vérifié lors de l'audit du 31/10).
- **Les murs en biais et arrondis.** Aujourd'hui Atelya ne connaît que les murs horizontaux et verticaux. Or beaucoup de plans français ont des pans coupés, des murs à 45°, des bow-windows ou des murs courbes (fr-001 en a, par exemple). On les fait apprendre **dans le même long entraînement** que l'œil DINOv2, pour ne faire chauffer le PC qu'une seule fois.

## Comment l'œil se branche (en simple)

DINOv2 regarde l'image par **carrés de 14 pixels**. C'est trop grossier tout seul pour un mur fin de 4 pixels. Donc on **garde le U-Net actuel** pour la finesse des traits et on lui **ajoute** DINOv2 comme deuxième œil qui voit l'ensemble. Les deux avis sont mélangés au milieu du réseau. Au début, l'œil DINOv2 est **figé** (on ne le modifie pas) : ça va vite et ça tient dans les 8 Go de la carte graphique.

## Les étapes, une à la fois

| # | Quoi | Où | Durée | Ce que tu reçois |
|---|------|----|-------|------------------|
| 1 | **Petits essais DINOv2** : 3 essais de 30 min, à départ égal depuis l'essai 5. T0 = essai 5 entraîné 30 min de plus sans rien changer (la référence honnête), T1 = avec l'œil DINOv2 « petit » (ViT-S, 85 Mo), T2 = avec l'œil « moyen » (ViT-B, 330 Mo). | PC | ~1 h 45 | Un tableau T0/T1/T2 sur les anciens plans, les photos, les styles du monde et les **13 vrais plans** (l'examen). Tu choisis si on garde DINOv2. |
| 2 | **Murs en biais et arrondis dans le générateur** : pans coupés, murs à 30-60°, coins arrondis, murs courbes (bow-window, rotonde). Les anciens plans restent identiques (option à part). | Cloud | ~½ journée | Une planche d'exemples à valider à l'œil. |
| 3 | **Traduction en 3D des murs en biais** : aujourd'hui le traducteur (coloriage → logement.json) ne cherche que des traits horizontaux et verticaux. Je lui apprends à trouver les traits penchés et les courbes (une courbe = plusieurs petits murs droits). Le format logement.json et Blender savent déjà faire des murs dans tous les sens. Le banc de notation est adapté pour noter aussi ces murs. | Cloud | ~½ journée | Une maquette 3D d'un plan avec biais + des tests. |
| 4 | **Jeux sur le PC** : ~3 000 plans avec biais/arrondis (plans + photos réalistes) + un jeu test de ~340. | PC | ~1 h 30 | — |
| 5 | **Le long entraînement (essai 7)** : un seul, ~3 h, avec les réglages gagnants de l'étape 1 et ceux qui ont marché en 6e (maître qui protège les anciens, déguisements). | PC | ~3 h | Points d'avancement toutes les 30 min. |
| 6 | **Mesure honnête** : les 4 bancs habituels (1 066 anciens, 342 photos sans cotes, 2 × 343 photos réalistes) + le nouveau banc biais + les 13 vrais plans + **les doutes de l'étape A1** (combien d'erreurs passent en silence, combien de fausses alertes). | PC | ~4-5 h | Un tableau essai 5 / essai 7, et ma recommandation. |
| 7 | **Clôture** : note /100, Feuille de route, sauvegarde GitHub (code + modèle en release), commit sur le Mac après ton « vas-y », entrée de suivi pour ton associé (PR #21). | Tous | ~30 min | — |

**Règle de mise en service :** l'essai 5 reste en service **sauf si** l'essai 7 fait mieux **sans recul** : murs, ouvertures et pièces pas plus de 0,5 point en dessous sur aucun banc, **0 erreur d'échelle de plus de 3 %**, et pas plus d'erreurs silencieuses selon A1. Sinon on garde seulement le générateur et le traducteur (ils servent de toute façon).

**Si l'étape 1 montre que DINOv2 n'aide pas,** je te le dis franchement et on fait l'essai 7 sans lui, juste pour les murs en biais.

## Ce qu'il me faut de toi

1. **Ton oui sur ce plan.**
2. **Ton accord pour un téléchargement sur le PC** (étape 1) : le code DINOv2 de Meta (GitHub, Apache 2.0) et ses poids (85 Mo + 330 Mo), dans `D:\Modélisation immobilière\atelya`. Ce n'est **pas** un nouveau logiciel installé : PyTorch, déjà là, sait les charger. Rien d'autre n'est installé.
3. **Ton accord pour les outils habituels dans le cloud** (OpenCV, numpy, pydantic…) pour écrire et tester le générateur et le traducteur. Pas de PyTorch dans le cloud.
4. Le jour du calcul : **le PC allumé, branché, veille désactivée**, et surélevé (il monte à 86 °C).

## Ordre proposé pour gagner du temps

Pendant que le PC fait les petits essais (étape 1), j'écris le générateur et le traducteur dans le cloud (étapes 2-3). Les deux ne se gênent pas.
