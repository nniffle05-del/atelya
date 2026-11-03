# Générateur de plans synthétiques — rapport de qualité (24 octobre 2026)

Version du générateur : 0.1.0. Code : `moteur/generateur/` (commit Mac `d10a7e9`, puis correction de l'escalier).
Mode d'emploi : `moteur/generateur/README.md`. Droits sur les données : `DATA_LICENSE.md`.

## 1. Ce qui a été fait, dans l'ordre demandé

| Étape | Résultat |
| --- | --- |
| 1. Examen du dépôt | Base Mac `061ef52`, 156 tests OK. Aucune bibliothèque ajoutée (NumPy, Pillow, OpenCV, pydantic déjà là). `fabrique.py` existante intacte. |
| 2. Architecture | 13 modules dans `moteur/generateur/` : réglages, logements (géométrie), annotations, mobilier, variantes (styles), rendu (images + masques), modèle 3D, validateur, doublons, exportateur, statistiques, contrôle qualité, ligne de commande. |
| 3. Première version | Fonctionnelle de bout en bout : `python -m moteur.generateur tout`. |
| 4. 100 exemples | 100 graines → 94 acceptés, 0 rejeté, 6 sans solution ; 29 s sur 4 cœurs ; 227 ko par exemple. |
| 5. Inspection visuelle | Planches (plan, annotations superposées, masque sémantique, pièces, hauteur) sur 30 exemples, page `controle.html`. Les polygones tombent exactement sur les murs, y compris sur les plans tournés et déformés (style photo). |
| 6. Tests | `tests/test_generateur.py` : 20 tests (reproductibilité, validité de 30 graines, masques ↔ annotations au pixel, rotation, duplex, 3D relisible, doublons, lot complet, reprise, répartition, statistiques, ligne de commande). **182 tests passent sur le Mac en 55 s** (Blender compris). |
| 7. Défauts corrigés | Voir § 3. |
| 8. Mesures | Voir § 4. |
| 9. Lot de 1 000 | 1 100 graines → **1 014 plans acceptés, 0 rejeté**, 86 graines sans solution ; 5 min 19 sur 4 cœurs ; 220 Mo (217 ko par exemple). |
| 10. Montée en volume | Procédure dans `moteur/generateur/README.md` (§ « Monter progressivement en volume »). |

## 2. Le lot de 1 000 en chiffres (`sorties/jeu-1000/rapports/statistiques.txt`)

- Types : studio 102, chambre 44, T1 124, T2 274, T3 286, T4 148, T5 36 (proche des distributions voulues : T2/T3 26 % chacun, T4 17 %, T5 9 %).
- Formes : rectangle 567, L 345, irrégulier 102 ; **80 duplex** (deux niveaux, même escalier aux deux niveaux, pas de porte d'entrée à l'étage).
- Styles : architecte 295, agence 215, scan 146, coloré 144, minimaliste 81, croquis 74, photo 59.
- Surfaces : 14,6 à 123,7 m², médiane 56,4 m². Pièces par logement : 2 à 17, médiane 6.
- 6 458 pièces (1 478 chambres, 868 séjours, 910 entrées, 488 dégagements, 492 placards, 187 buanderies, 34 bureaux, 160 escaliers…), 10 580 ouvertures (5 362 portes intérieures, 1 014 portes d'entrée, 3 267 fenêtres, 598 portes-fenêtres, 339 baies).
- Épaisseurs de murs extérieurs de 15 à 40 cm, hauteurs sous plafond de 2,40 à 3,20 m.
- Répartition : train 785 / validation 114 / test 115, par familles (type, forme, duplex, nombre de pièces) ; 0 doublon exact ; 1 paire « trop semblable » entre train et test, ramenée en train.
- Avertissements du validateur : aucun.

## 3. Défauts trouvés et corrigés pendant le travail

| Défaut | Correction |
| --- | --- |
| Ouverture qui empiétait sur l'angle d'un mur extérieur | face utile du mur réduite de l'épaisseur à chaque bout |
| Encoches des formes en L mal fermées aux angles extérieurs | murs extérieurs rallongés de leur épaisseur |
| Cartouche coupé à droite | marge de droite élargie selon la taille du texte |
| 10 % de rejets « surfaces incohérentes » (lamelle de 0,6 m² dans les L) | mur porteur posé du côté de la bande la plus courte |
| Masques d'ouvertures ≠ polygones (fillPoly colorie le bord : un rectangle de w × h pixels en remplit (w+1) × (h+1)), puis rééchantillonnage à la rotation | masques dessinés directement dans le repère final ; tramage « centre du pixel dans le polygone » (`annotations.rasteriser`), partagé par le rendu et le validateur |
| Bord d'une pièce et bord de son mur sur la même rangée de pixels | le mur l'emporte dans le masque des pièces |
| 1 exemple sur 1 100 rejeté (339,5 contre 339,4999 : une rangée de pixels en moins) | coordonnées arrondies au centième avant tramage, des deux côtés |
| PNG de 7 Mo pour les plans bruités (photo, grain) | plans abîmés écrits en JPEG qualité 92 ; masques toujours en PNG |
| Escalier absent du plan et de la carte de hauteur quand le style ne dessine pas de mobilier (vu sur l'exemple 000194) | l'escalier n'est plus traité comme un meuble : toujours dessiné, marches toujours dans la carte de hauteur |

## 4. Performances et espace disque (conteneur 4 cœurs)

| | mesuré | 1 000 graines | 10 000 | 100 000 |
| --- | --- | --- | --- | --- |
| temps (`--processus 4`) | 0,29 s par graine | 5 min 19 (mesuré) | ≈ 50 min | ≈ 8 h |
| espace | 217 ko par exemple | 220 Mo (mesuré) | ≈ 2,2 Go | ≈ 22 Go |
| plans obtenus | 92 % des graines | 1 014 (mesuré) | ≈ 9 200 | ≈ 92 000 |

Par type (par processus) : T1/T2 ≈ 0,25 s, T3 ≈ 0,4 s, T4 ≈ 1,2 s, T5 ≈ 1,6 s. Options : `--variantes 2` × 2,7 en espace ;
`--3d` + 130 ko ; `--masques-par-classe` + 10 % (mesurés sur 12 graines).

## 5. Difficultés et limites, honnêtement

- **8 % des graines n'aboutissent pas** (surtout T4/T5 compacts : trop de pièces pour la surface tirée). Elles sont passées, pas réparées ; ce n'est pas un biais sur les plans produits, mais la distribution réelle des T5 (36 sur 1 014) est un peu en dessous de la cible (9 %).
- **Les T4/T5 sont lents** à inventer (jusqu'à 1 300 essais de découpe). Acceptable à 1 000, à améliorer avant 100 000.
- **Formes** : rectangles, L et enveloppes à encoches seulement ; pas de murs obliques ni courbes, pas de pièce non rectangulaire. Un seul logement par plan, pas de balcon ni de parties communes.
- **Plausibilité, pas conformité** : aucune réglementation n'est vérifiée.
- **Vérité suisse / vrais plans** : ce générateur ne remplace pas le banc de vrais plans ; il fournit du volume et des annotations exactes pour l'entraînement.
- **Tests Blender** : passés sur le Mac (182), sautés dans le cloud (pas de Blender).

## 6. Fichiers livrés

- Code : `moteur/generateur/` (13 modules + README), `tests/test_generateur.py`, `DATA_LICENSE.md`, README principal (commités sur le Mac).
- Lot de 1 000 : `sorties/jeu-1000/` sur le conteneur cloud (non versionné, `sorties/` est ignoré par Git) ; à refaire sur le Mac en 5 minutes avec la même commande, à l'identique.
- Rapports copiés ici : `jeu-1000/statistiques.txt`, `jeu-1000/statistiques.json`, `jeu-1000/controle.html` + `rapports/planches/` (40 planches), `jeu-1000/repartition.json`, `jeu-1000/reglages.json`, `jeu-1000/journal.log`, et des aperçus dans `apercus/`.
