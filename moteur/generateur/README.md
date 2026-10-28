# Générateur de plans synthétiques

`moteur/generateur` invente des logements (du studio au T5, duplex compris), les dessine comme des plans
d'agence, d'architecte, de scan ou de photo, et écrit pour chacun la **vérité terrain** complète : masques
au pixel, polygones, graphe des pièces, et en option le modèle 3D. Le but : des données d'entraînement en
quantité illimitée, variées, sans aucune donnée tierce (voir `DATA_LICENSE.md` à la racine).

Version du générateur : `0.1.1` (`moteur/generateur/__init__.py`). Format d'annotations : `plan-synthetique/1.0`.

## Installation

Rien de plus que le dépôt : Python 3.13, NumPy, Pillow, OpenCV et pydantic sont déjà dans `pyproject.toml`.

```
uv sync                 # installe l'environnement (une fois)
uv run pytest tests/test_generateur.py     # les 20 tests du générateur (environ 40 s)
```

## Les commandes

```
uv run python -m moteur.generateur tout --nombre 100 --dossier sorties/jeu-100 --processus 4
      # génère 100 graines, répartit train/validation/test, écrit les statistiques et la page de contrôle

uv run python -m moteur.generateur generer --nombre 1000 --dossier sorties/jeu-1000 --processus 4
      # génération seule (reprend là où elle s'est arrêtée : les exemples déjà écrits sont gardés)
uv run python -m moteur.generateur generer --nombre 50 --types T2,T3 --surface-min 40 --surface-max 80 --diversite 3
      # filtre par type et surface ; diversité graphique maximale (rotation, perspective, salissures)
uv run python -m moteur.generateur generer --nombre 20 --3d --variantes 2 --masques-par-classe --resolution 80
      # avec modele.glb / modele.obj / construction.json, 2 variantes graphiques par plan, un masque par classe
uv run python -m moteur.generateur generer --nombre 100 --reglages mes_reglages.json --regles mes_regles.json
      # distributions (types, surfaces, formes…) et seuils du validateur surchargés par des fichiers JSON

uv run python -m moteur.generateur repartir sorties/jeu-1000 --parts 0.8,0.1,0.1
uv run python -m moteur.generateur statistiques sorties/jeu-1000
uv run python -m moteur.generateur controle sorties/jeu-1000 --planches 40
uv run python -m moteur.generateur doublons sorties/jeu-1000
uv run python -m moteur.generateur valider sorties/jeu-1000
      # revérifie tous les fichiers d'un jeu déjà écrit (après une copie, par exemple)
```

`--help` après chaque commande donne toutes les options. Les options importantes :

| Option | Rôle |
| --- | --- |
| `--nombre`, `--depart` | combien de graines, à partir de laquelle (graine = numéro qui fixe tout le hasard) |
| `--processus N` | N exemples fabriqués en même temps (mettre le nombre de cœurs) |
| `--diversite 0..3` | 0 : plans d'architecte sages ; 3 : tous les styles, rotation, perspective, taches, JPEG |
| `--familles` | impose des familles de style : `architecte,agence,minimaliste,scan,photo,colore,croquis` |
| `--variantes N` | N dessins supplémentaires du même logement (autres styles), dans `niveau_k/variante_n/` |
| `--3d` | écrit aussi le modèle 3D (désactivé par défaut : les plans 2D sont la priorité) |
| `--refaire` | refait les exemples déjà présents au lieu de les reprendre |
| `--reglages fichier.json` | surcharge de `reglages.py` (une clé = un réglage ; les tables sont fusionnées clé par clé) |
| `--regles fichier.json` | surcharge des seuils de `validateur.Regles` |

## Ce qui est écrit

```
sorties/jeu-1000/
  manifest.json          la liste des exemples (type, forme, surface, verdict, fichiers, taille, empreinte)
  reglages.json          les réglages du lot (pour le refaire à l'identique)
  journal.log            ce qui s'est passé (graines sans solution, rejets)
  repartition.json       train / validation / test (après `repartir` ou `tout`)
  rapports/              statistiques.json et .txt, planches/, controle.html, doublons.json
  exemples/000001/
    geometrie.json       la vérité terrain en mètres : paramètres, niveaux, pièces, murs, ouvertures,
                         adjacences, connexions (quelle porte relie quelles pièces), connectivité
    logement_niveau0.json  le même niveau au format logement/0.1 (celui que Blender sait construire)
    validation.json      le verdict du validateur (erreurs, avertissements)
    manifeste.json       la fiche de l'exemple (reprise dans manifest.json)
    construction.json, modele.glb, modele.obj, materiaux.mtl     (avec --3d)
    niveau_0/
      plan.png | plan.jpg        le plan dessiné (JPEG quand le style l'abîme : grain, photo, compression)
      plan_sans_mobilier.*       le même sans meubles (seulement si le style en dessine)
      masque_semantique.png      une classe par pixel (table ci-dessous)
      masque_pieces.png          l'identifiant de pièce par pixel (0 = pas une pièce)
      masque_elements.png        l'identifiant de mur ou d'ouverture par pixel
      contours.png               les contours des murs et ouvertures (255 sur 1 pixel de large)
      hauteur.png                la hauteur en millimètres (PNG 16 bits, voir plus bas)
      annotations.json           les polygones en pixels de chaque pièce, mur, ouverture et meuble,
                                 la matrice mètres → pixels, le style, les valeurs des masques
      classes/<classe>.png       un masque binaire par classe (avec --masques-par-classe)
      variante_1/ …              les variantes graphiques (avec --variantes)
    niveau_1/ …                  pour un duplex
```

### Les classes du masque sémantique

| Valeur | Classe | | Valeur | Classe |
| --- | --- | --- | --- | --- |
| 0 | fond | | 8 | sdb / sde (salle de bain, salle d'eau) |
| 1 | mur | | 9 | wc |
| 2 | porte | | 10 | entree |
| 3 | fenetre | | 11 | degagement (couloir) |
| 4 | porte_fenetre | | 12 | placard |
| 5 | sejour / principale (pièce d'un studio) | | 13 | buanderie |
| 6 | cuisine | | 14 | bureau |
| 7 | chambre | | 15 | escalier |

La table exacte est `annotations.CLASSES` et elle est recopiée dans chaque `annotations.json`
(`classes_masque_semantique`) et `geometrie.json` (`classes`).

### La carte de hauteur (`hauteur.png`)

Un entier 16 bits par pixel, en **millimètres**, vu de dessus avec un **plan de coupe à 1,50 m**
(`plan_de_coupe_hauteur_m` dans `annotations.json`) : un mur vaut la hauteur sous plafond ; une fenêtre
vaut la hauteur de son allège (le muret sous la vitre) ; une porte vaut 0 (on passe) ; le sol d'une pièce
vaut 0 ; un meuble vaut sa hauteur ; les marches d'un escalier montent de 0 jusqu'au plancher.

### Repère et pixels

En mètres : x vers l'est, y vers le nord, origine au coin intérieur sud-ouest (comme le reste du moteur).
En pixels : `annotations.json → image.matrice_m_vers_px` est la matrice 3×3 (homographie) qui envoie un
point (x, y, 1) en mètres sur (u·w, v·w, w) en pixels, rotation et perspective comprises. Les polygones
en pixels sont déjà calculés pour chaque élément (`polygone_px`, `boite_px`).

Convention de tramage : un pixel appartient à un polygone si son **centre** est dedans ; c'est la même
fonction (`annotations.rasteriser`) qui dessine les masques et qui les revérifie dans le validateur.
Au bord d'une pièce, le mur l'emporte : un pixel d'identifiant de pièce porte toujours la classe de la pièce.

## Les modules

| Module | Rôle |
| --- | --- |
| `reglages.py` | toutes les distributions (types, surfaces, formes, épaisseurs, hauteurs, probabilités) ; surchargeable par JSON |
| `logements.py` | invente la géométrie : enveloppe (rectangle, L, irrégulier), zones, découpe des pièces, couloirs, portes, fenêtres, duplex |
| `annotations.py` | décrit un logement en mètres (`geometrie.json`), adjacences, connexions, connectivité, tramage |
| `mobilier.py` | les meubles plausibles par pièce (lit, table, canapé, plan de travail, sanitaires…) |
| `variantes.py` | les styles graphiques (7 familles) et les salissures photométriques (grain, photocopie, taches, JPEG, photo) |
| `rendu.py` | dessine le plan et tous les masques, et produit `annotations.json` |
| `modele3d.py` | briques 3D, GLB et OBJ écrits à la main (sans bibliothèque), `construction.json` |
| `validateur.py` | contrôle la géométrie (surfaces, chevauchements, portes, connexité) puis les fichiers écrits (masques ↔ polygones, 3D ↔ 2D) |
| `doublons.py` | empreinte invariante par symétrie (doublons exacts) et signature de ressemblance |
| `exportateur.py` | écrit les exemples, le manifeste, reprend un lot interrompu, répartit train/validation/test par familles |
| `statistiques.py`, `controle_qualite.py` | les chiffres du jeu, les planches et la page HTML de contrôle |
| `__main__.py` | la ligne de commande |

## Performances mesurées (24 octobre 2026, conteneur 4 cœurs, `--processus 4`, sans 3D ni variantes)

| | mesuré | 1 000 graines | 10 000 | 100 000 |
| --- | --- | --- | --- | --- |
| temps (4 processus) | 0,30 s par graine | ≈ 5 min | ≈ 50 min | ≈ 8 h |
| espace disque | 227 ko par exemple (du : 270 ko) | ≈ 0,25 Go | ≈ 2,5 Go | ≈ 25 Go |
| graines qui aboutissent | 94 % | ≈ 940 plans | ≈ 9 400 | ≈ 94 000 |

- Le temps par logement dépend du type : T1/T2 ≈ 0,25 s, T3 ≈ 0,4 s, T4 ≈ 1,2 s, T5 ≈ 1,6 s (mesuré par processus).
  Un T4/T5 demande souvent plusieurs centaines d'essais de découpe avant d'être habitable.
- Mesuré sur 12 graines : `--variantes 2` multiplie l'espace par 2,7 (210 → 577 ko) ; `--3d` ajoute
  environ 130 ko par exemple ; `--masques-par-classe` ajoute environ 10 %.
- Les 6 % de graines sans solution ne sont pas un défaut des données : la graine est simplement passée
  (journal.log). Pour obtenir N plans, demander environ N × 1,07 graines.
- Sur le Mac M4 (10 cœurs), `--processus 8` devrait aller environ deux fois plus vite ; c'est une
  estimation, pas une mesure.

## Monter progressivement en volume

1. **100 exemples** (`tout --nombre 100`) : ouvrir `rapports/controle.html`, feuilleter les planches
   (plan, annotations superposées, masques, hauteur). Tout défaut visible ici le sera 1 000 fois plus loin.
2. **1 000 exemples** (`tout --nombre 1100 --processus 4`, 5 min) : lire `rapports/statistiques.txt`
   (répartition des types, surfaces, motifs de rejet, avertissements) et `rapports/doublons.json`.
   Comparer les distributions obtenues à celles voulues dans `reglages.py` ; ajuster par `--reglages`.
3. **10 000 exemples** : lancer par tranches de graines (`--depart 1`, `--depart 10001`…) dans des dossiers
   séparés ou le même dossier (la reprise saute ce qui existe). Un lancement interrompu se relance tel quel.
   Vérifier l'espace disque avant (≈ 2,5 Go) ; `sorties/` est ignoré par Git.
4. **100 000 et plus** : prévoir ≈ 25 Go et une nuit sur 4 cœurs. Utiliser `--variantes` plutôt que plus
   de graines si c'est la variété graphique qui manque, et `--diversite 3` pour les plans abîmés.
   Garder `repartir` **après** la génération complète : la répartition est déterministe (empreinte +
   graine de répartition) et met toutes les variantes d'un même logement, et ses doublons exacts, dans la
   même partition ; les paires « trop semblables » entre train et test sont ramenées en train.
5. **Changer le générateur** change les données : incrémenter `VERSION_GENERATEUR` à chaque modification
   qui change un exemple existant, et ne pas mélanger deux versions dans un même jeu
   (`manifest.json → version_generateur`). Le format d'annotations (`SCHEMA`) ne change que si les fichiers
   changent de forme.

## Limites connues (version 0.1.0)

- Formes : rectangles, L et enveloppes à encoches ; pas de murs obliques ni courbes, pas de pièces non rectangulaires.
- Un seul logement par plan, sans parties communes, balcon ni terrasse dessinés.
- Les meubles sont de simples symboles ; les textes sont en français seulement.
- Le mobilier et les cotes ne sont pas (encore) des classes du masque sémantique : seuls les meubles sont annotés en polygones.
- 6 % des graines n'aboutissent pas (surtout T4/T5 compacts) ; elles sont passées, pas réparées.
