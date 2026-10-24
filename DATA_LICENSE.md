# Licence des données générées (jeu de plans synthétiques)

Ce fichier dit d'où viennent les plans fabriqués par `moteur/generateur`, à qui ils appartiennent
et ce qu'on a le droit d'en faire. Il accompagne chaque jeu généré (dossier `sorties/jeu-…`).

## 1. Ce que contient un jeu généré

Chaque exemple est **inventé de toutes pièces par un programme** (`moteur/generateur/logements.py`) :
l'agencement des pièces, les murs, les portes, les fenêtres, le mobilier, le style de dessin.
Aucune image, aucun plan, aucune annotation ne provient d'un plan réel, d'une annonce immobilière,
d'un jeu de données tiers ou d'un modèle entraîné sur de telles données.

Les fichiers d'un exemple (images PNG/JPEG, masques, `annotations.json`, `geometrie.json`,
`modele.glb`, `modele.obj`, `construction.json`) sont donc des **œuvres dérivées du code du projet
uniquement**.

## 2. Titulaire des droits

Le code du générateur et les données qu'il produit appartiennent aux auteurs du projet `moteur-3d`
(l'entreprise des associés). Ils peuvent être utilisés **à des fins commerciales**, y compris pour
entraîner, évaluer et distribuer des modèles d'apprentissage automatique, sans obligation envers un tiers.

Si un jour un jeu généré est publié ou transmis à un partenaire, il faudra choisir et écrire ici une
licence explicite (par exemple CC BY 4.0 pour une publication ouverte, ou un contrat de licence pour une
transmission privée). **Tant que rien n'est écrit ici, le jeu est privé : tous droits réservés.**

## 3. Éléments tiers utilisés et leurs licences

| Élément | Usage | Licence | Compatible usage commercial |
| --- | --- | --- | --- |
| Inter (`moteur/polices/Inter-Regular.otf`) | police des textes dessinés sur les plans | SIL OFL 1.1 (et Apache 2.0) | oui |
| Liberation Sans (`moteur/polices/LiberationSans-Regular.ttf`) | idem | SIL OFL 1.1 | oui |
| DejaVu Sans (`moteur/polices/DejaVuSans.ttf`) | idem | Bitstream Vera (DejaVu : domaine public) | oui |
| OpenCV (`opencv-python-headless`) | dessin des masques, déformations, JPEG | Apache 2.0 | oui |
| Pillow | dessin des plans | MIT-CMU (HPND) | oui |
| NumPy | calculs | BSD 3 clauses | oui |
| pydantic | vérification du format `logement/0.1` | MIT | oui |

Les licences de polices OFL précisent que **les documents créés avec ces polices ne sont pas soumis à la
licence de la police** : une image de plan où un mot est écrit en Inter appartient à celui qui a produit
l'image. Les textes complets des licences de polices sont dans `moteur/polices/LICENCES.txt`.

Aucune bibliothèque sous licence GPL ou AGPL n'est utilisée par le générateur (en particulier, pas
d'Ultralytics YOLO). Aucun jeu de données sous licence non commerciale (CubiCasa5k CC BY-NC-SA, CVC-FP
CC BY-NC…) n'a servi, ni pour les règles du générateur, ni pour ses réglages, ni pour ses tests.

## 4. Noms et textes écrits sur les plans

Les noms de pièces (« Séjour », « Chambre 2 »…), les cotes, les surfaces et les cartouches sont produits
par le programme à partir de listes écrites dans `moteur/generateur/logements.py` et
`moteur/generateur/rendu.py`. Les plans ne portent ni nom de personne, ni adresse, ni nom d'agence, ni
logo. Ils ne contiennent **aucune donnée personnelle**.

## 5. Ce que les plans ne sont pas

Les plans sont **plausibles, pas conformes** : ils respectent des règles de bon sens (tailles de pièces,
chaque pièce desservie, fenêtres dans les pièces de vie) mais aucune réglementation (accessibilité,
sécurité incendie, surfaces légales). Ils ne doivent pas être présentés comme des plans d'architecte ni
servir à construire. Leur seul objet est l'apprentissage et le test de logiciels de lecture de plans.

## 6. Reproductibilité et traçabilité

Chaque exemple porte dans `geometrie.json` et `manifeste.json` : la version du générateur
(`version_generateur`), la version du format d'annotations (`schema`), la graine (`graine`) et les
réglages du lot (`reglages.json` à la racine du jeu). Avec la même version du code et les mêmes
réglages, la même graine redonne exactement le même exemple ; c'est ce qui permet de prouver l'origine
d'un plan et de refaire un jeu à l'identique.

*Dernière mise à jour : 24 octobre 2026, version du générateur 0.1.0.*
