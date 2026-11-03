# moteur-3d

Moteur de reconstruction 3D immobilière : plan + photos, puis modèle JSON, puis scène Blender.

## Organisation

- `moteur/logement.py` : le format JSON d'un logement (version 0.1) et ses règles de vérification.
- `exemples/cas-test-00/logement.json` : le cas test n°0, un T2 de synthèse de 42 m² (dimensions de référence exactes).
- `moteur/geometrie.py` : transforme le logement en « briques » (morceaux de murs, allèges, linteaux, sols, plafonds, seuils). Aucun besoin de Blender.
- `moteur/habillage.py` : habille la maquette (étape 4) : une menuiserie dans chaque ouverture (cadre et vitres des fenêtres, encadrement, battant et poignées des portes), un matériau par brique (parquet ou carrelage selon le nom de la pièce, murs et plafonds blancs), un soleil, un plafonnier par pièce et deux caméras. Aucun besoin de Blender.
- `moteur/blender/poser_briques.py` : script lu par Blender, qui pose les briques, leur donne leur matériau, pose les lampes et les caméras, et enregistre la maquette.
- `moteur/blender/materiaux.py` : les matériaux « procéduraux » (dessinés par un calcul, sans photo à télécharger) : parquet, carrelage, peinture blanche, verre…
- `moteur/blender/rendre.py` : script lu par Blender, qui calcule une image par caméra (moteur Cycles, sur la carte graphique du Mac si possible).
- `moteur/blender/mesurer.py` : script lu par Blender, qui mesure la maquette (pour les tests).
- `moteur/construire.py` : la commande unique, du logement.json vérifié à la maquette .blend et à ses images.
- `tests/` : les tests automatiques (`test_blender.py` lance vraiment Blender, sans écran).
- `outils/saisie-plan/` : la page de saisie d'un plan (étape 3), qui produit un `logement.json` en cliquant sur l'image du plan.
  `calculs.js` contient les calculs (échelle, aimants, export), `saisie.js` les clics et le dessin.
  `tests/calculs.test.js` se lance avec Node.js (`node --test outils/saisie-plan/tests/calculs.test.js`), qui n'est pas nécessaire pour utiliser la page.
- `moteur/lecture_plan.py` : la lecture automatique d'un plan (étape 3b) : trouve les murs sur l'image, redresse un plan scanné de travers, et propose un `logement.json`. Utilise OpenCV.
- `moteur/lecture_cotes.py` : la lecture automatique de l'échelle (étape 3c) : lit les cotes écrites sur le plan avec RapidOCR (modèle de lecture de texte qui tourne sur l'ordinateur, sans Internet), mesure leurs traits et en déduit les pixels par mètre ; lit aussi la hauteur sous plafond si elle est écrite.
- `moteur/lecture_ouvertures.py` : la lecture des portes et fenêtres (étape 3d) : regarde le dessin dans chaque trou des murs (battant de porte, traits de fenêtre) ; hauteurs courantes mises par défaut, avec le statut « estimé ».
- `moteur/lecture_pieces.py` : la lecture des pièces (étape 3d) : les espaces fermés entre les murs, avec le nom et la surface écrits dedans ; la surface écrite sert de contrôle.
- `moteur/correcteur.py` : le correcteur (étape 5a) : compare une lecture automatique au vrai logement.json et donne une note (murs, dimensions, portes et fenêtres, pièces, hauteur), le nombre de corrections à faire et si le plan est « vert » (vérifiable en moins de 2 minutes).
- `moteur/banc_essai.py` : le banc d'essai (étape 5a) : lance la lecture sur tous les plans d'un dossier dont on connaît le corrigé, les note et écrit le bilan dans `sorties/banc/rapport.json`. Un logement par sous-dossier : `logement.json` (le corrigé) et un ou plusieurs dessins `plan….png`.
- `moteur/fabrique.py` : la fabrique de plans (étape 5b) : invente des logements variés (T1 à T4, rectangles et formes en L, épaisseurs de murs et hauteurs sous plafond variées), vérifie qu'ils sont habitables (tailles des pièces, chaque pièce desservie, une fenêtre par pièce de vie), et écrit pour chacun le corrigé `logement.json`, le dessin `plan.png` et une `fiche.json` (type, forme, style de dessin). Une même « graine » (numéro de départ) redonne toujours le même logement et le même dessin.
- `moteur/dessin_plan.py` : dessine le plan coté d'un logement.json (murs, portes, fenêtres, cotes, noms et surfaces des pièces, cartouche), avec un « style » qui varie d'un plan à l'autre (échelle, gris, police, taille des textes, cotes partielles, portes à deux battants…).
- `moteur/salissure.py` : salit les plans fabriqués (étape 5c), pour voir si la lecture tient sur des plans réalistes : scan de travers, photocopie grise et granuleuse, tache de café et pli, image réduite et très compressée (JPEG), photo de la feuille prise au téléphone (en biais, ombre, lumière inégale). Écrit `plan-travers.png`, `plan-photocopie.png`, `plan-taches.png`, `plan-compression.jpg` et `plan-telephone.jpg` à côté de chaque `plan.png` ; même graine, même salissure.
- `moteur/nettoyage.py` : nettoie l'image d'un plan avant de la lire (étape 5c) : sur une photo, détoure la feuille par ses bords et la remet à plat ; rend le papier blanc partout (ombre, tache, pli) ; rend le contraste d'une photocopie pâle. Sur un plan propre, ne change presque rien.
- `moteur/generateur/` : le générateur de plans synthétiques (étape 6) : invente des logements du studio au T5 (duplex, rectangles, L, enveloppes irrégulières, couloirs, placards, buanderies), les dessine dans 7 styles (architecte, agence, scan, photo…), et écrit pour chacun la vérité terrain : masques au pixel (classes, pièces, murs et ouvertures, contours, hauteur), polygones, graphe des pièces, et en option le modèle 3D (GLB, OBJ). Validateur, détecteur de doublons, répartition train/validation/test, statistiques et page de contrôle. Mode d'emploi complet dans `moteur/generateur/README.md` ; droits sur les données dans `DATA_LICENSE.md`.
- `moteur/polices/` : trois polices libres (Inter, Liberation Sans, DejaVu Sans) pour que les plans soient dessinés pareil sur le Mac et sur le PC ; licences dans `LICENCES.txt`.
- `exemples/cas-test-00/plan.png` : le plan coté du cas test n°0, dessiné à l'échelle depuis `logement.json`, pour s'exercer.

## Commandes utiles

```
uv run pytest        # lance tous les tests
uv run python -m moteur.construire exemples/cas-test-00/logement.json sorties/cas-test-00
                     # construit sorties/cas-test-00/maquette.blend (habillée)
                     # et les images sorties/cas-test-00/images/vue-dessus.png et vue-sejour.png
                     # (--brouillon : petites images vite faites ; --sans-images : maquette seule)
uv run python -m moteur.lecture_plan exemples/cas-test-00/plan.png sorties/lu.json
                     # lit l'échelle, les murs, les portes, les fenêtres et les pièces du plan
                     # et écrit un logement.json proposé
                     # (--echelle 100 pour imposer l'échelle, --hsp 2.50 pour la hauteur sous plafond)
                     # écrit aussi sorties/lu-a-verifier.json, pour la vérification humaine
uv run python -m moteur.banc_essai
                     # lit et note tous les plans de exemples/ (ou d'un autre dossier donné)
uv run python -m moteur.correcteur sorties/lu.json exemples/cas-test-00/logement.json
                     # note une seule lecture par rapport au corrigé
uv run python -m moteur.fabrique 200
                     # fabrique 200 logements et leurs plans dans sorties/fabrique/plan-00001… (13 s)
                     # (--depart 1001 pour d'autres graines, un autre dossier en second argument)
uv run python -m moteur.banc_essai sorties/fabrique --rapport sorties/fabrique/rapport.json
                     # note la lecture sur tous les plans fabriqués (environ 1,5 s par plan)
                     # (--processus 4 : quatre plans lus en même temps ; --seulement propre,telephone :
                     #  seulement ces sortes de dessin ; le bilan est aussi donné par sorte de dessin)
uv run python -m moteur.salissure sorties/fabrique
                     # salit chaque plan fabriqué de 5 façons, à côté de son plan.png
                     # (--familles travers,telephone pour n'en faire que certaines)
uv run python -m moteur.generateur tout --nombre 100 --dossier sorties/jeu-100 --processus 4
                     # génère 100 plans synthétiques annotés, les répartit, écrit les statistiques et
                     # la page sorties/jeu-100/rapports/controle.html (30 s ; voir moteur/generateur/README.md)
uv run python -m moteur.lecture_pdf plan.pdf
                     # trie les pages d'un PDF (étape A2) : vectorielle (textes exacts lisibles),
                     # scannee (photo dans le PDF), piegee (textes illisibles), vide ; dit lesquelles
                     # sont des plans (--json : détail des mesures). Demande pdfplumber et pypdfium2.
                     # Sur une page vectorielle, moteur.lecture_pdf.lire_page donne l'image et les textes
                     # exacts, que lire_echelle_plan(..., textes=...) prend à la place de l'OCR (étape A2-3).
uv run python -m moteur.generateur.plan_pdf --jeu sorties/jeu-100 --sortie sorties/pdf-100
                     # écrit en PDF les plans d'un jeu du générateur (étape A2-5) : vectoriel, piégé,
                     # scanné, réduit, tourné, dossier de 3 pages ; la vérité dans plan-<sorte>.json
```

## Saisir un plan

Ouvrir `outils/saisie-plan/index.html` dans Google Chrome (double-clic, ou `open -a "Google Chrome" outils/saisie-plan/index.html`).
La page fonctionne sans Internet : le plan ne quitte pas l'ordinateur. Suivre les étapes numérotées en haut :
plan, échelle, contrôle de l'échelle, murs, origine, puis « Enregistrer logement.json » (le fichier arrive dans Téléchargements).
Pour vérifier une lecture automatique : bouton « Ouvrir une lecture ou une saisie… », choisir le fichier `…-a-verifier.json`.
Tout est déjà posé sur le plan ; les points douteux sont listés dans le cadre « À vérifier » et entourés en orange.
On corrige (type d'une ouverture, nom d'une pièce, mur…) ou on clique « C'est bon » ; l'enregistrement n'est possible qu'une fois la liste vide.
Les longueurs affichées sont celles de l'axe des murs, d'un angle à l'autre (8,20 m pour un mur extérieur qui borde 8,00 m intérieurs).
Une longueur obtenue en cliquant est enregistrée avec le statut `estime` ; une cote tapée dans « Modifier » avec le statut `mesure`.

Les maquettes produites vont dans `sorties/`, qui n'est pas suivi par Git (on peut toujours les reconstruire).
Blender est cherché dans `/Applications/Blender.app` ; sinon, indiquer son chemin dans la variable `BLENDER`.

## Habillage (étape 4)

Tout ce que l'habillage ajoute est supposé (le plan ne dit ni la couleur des murs ni le type de sol) :
c'est de la décoration, à remplacer plus tard par ce que montrent les photos.
- Sol : parquet si le nom de la pièce contient séjour, salon, chambre ou bureau ; carrelage pour salle d'eau,
  salle de bains, WC, cuisine, entrée, couloir… ; parquet si le nom est inconnu.
- Portes : fermées ; la porte qui donne dehors (un seul de ses côtés est dans une pièce) est la porte d'entrée, en gris foncé.
- Fenêtres et portes-fenêtres : deux vantaux à partir de 1 m de large.
- Vue intérieure : la pièce dont le nom contient séjour, salon ou living (sinon la plus grande), prise depuis le coin
  qui voit le plus de fenêtres, à 1,50 m de haut, objectif grand angle (18 mm).
- Vue de dessus : sans plafonds, depuis le sud-ouest, sans perspective, cadrée sur tout le logement.
- Lumière : soleil fixe venant de l'ouest-sud-ouest, ciel bleu clair, un plafonnier blanc chaud par pièce.

## Bibliothèques tierces et mentions obligatoires

La lecture des PDF (étape A2) utilise pdfplumber et pdfminer.six (MIT) et pypdfium2 (BSD-3 / Apache-2.0), qui
contient le moteur PDFium (BSD / Apache-2.0) et la bibliothèque FreeType, dont la licence (FTL) demande cette mention :
Portions of this software are copyright © The FreeType Project (www.freetype.org). All rights reserved.
La police Liberation Sans (moteur/polices, licence SIL OFL) sert aussi à fabriquer les PDF « piégés » de test.

## Conventions

- Longueurs en mètres ; repère vu de dessus : x vers l'est, y vers le nord, origine au coin intérieur sud-ouest.
- Un mur est décrit par son axe (la ligne en son milieu) et son épaisseur.
- Aux angles, le premier mur de la liste est rallongé et le second raccourci, pour que l'angle soit fermé sans chevauchement. Version 0.1 : angles droits seulement, deux murs au plus par angle.
- Chaque élément porte un `statut` : `mesure`, `estime` ou `ajoute`, et une `source`.
