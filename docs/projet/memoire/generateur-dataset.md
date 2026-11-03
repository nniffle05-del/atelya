---
name: generateur-dataset
description: Générateur de plans synthétiques (étape 6, 2026-10-24) : paquet moteur/generateur/ 0.1.0 commité sur le Mac (d10a7e9 + 70df4b0), chiffres du lot de 1 000, choix techniques, suite
metadata:
  type: project
  modified: 2026-10-24T20:54:37.301Z
---

ÉTAPE 6 TERMINÉE 2026-10-24 (fil « Construire le générateur de plans synthétiques »). Cahier des charges NT en 15 points (dataset annoté illimité pour entraîner un modèle de lecture de plans qui fera lui-même la 3D). La 3D est une OPTION désactivée par défaut (`--3d`), décidé avec NT.

Commits Mac (main) : d10a7e9 (18 fichiers, 4 573 lignes : moteur/generateur/*.py + README.md, tests/test_generateur.py 20 tests, DATA_LICENSE.md, README principal) puis 70df4b0 (escalier toujours dessiné, même sans mobilier). 182 tests OK sur le Mac en 54 s (Blender compris). fabrique.py existante NON modifiée. Aucune nouvelle bibliothèque. Copie cloud : /home/user/moteur-3d branche `generateur` (3e4cbfa).

Chiffres (cloud 4 cœurs, --processus 4) : 1 100 graines → 1 014 plans acceptés, 0 rejeté, 86 sans solution (T4/T5 compacts), 5 min 19, 220 Mo (217 ko/exemple) ; 80 duplex ; train/val/test 785/114/115 ; 0 doublon. Estimations : 10 000 ≈ 50 min / 2,2 Go ; 100 000 ≈ 8 h / 22 Go. T4 ≈ 1,2 s, T5 ≈ 1,6 s par logement (jusqu'à 1 300 essais). Options : --variantes 2 ×2,7 espace ; --3d +130 ko ; --masques-par-classe +10 %.

Choix techniques : masques tramés « centre du pixel dans le polygone », coordonnées arrondies au centième (`annotations.rasteriser`, partagée rendu/validateur) ; au bord d'une pièce le mur l'emporte ; plans abîmés en JPEG q92, masques PNG ; répartition déterministe par empreinte (8 symétries) + famille ; carte de hauteur uint16 mm, plan de coupe 1,50 m.

Livrables : /mnt/project-files/moteur-3d-generateur/ (code/, rapport-qualite.md, jeu-1000/ rapports + planches, apercus/). Suivi associé : entrée 6-1 dans suivi.json, branche claude/project-thread-3y76ph, PR #1 vers main FUSIONNÉE par NT le 2026-10-24 à 21h04 (main de suivi-moteur contient l’entrée 6-1).

Suite proposée : accélérer T4/T5 (8 % d'échecs), puis 10 000 plans sur le Mac, puis premier entraînement. Limites : formes rectangle/L/encoches seulement, un logement par plan, mobilier et cotes pas des classes du masque.

**Why:** un nouveau fil doit savoir ce qui existe et ce qui reste.
**How to apply:** lire avant de reprendre le générateur ; nouvelle version = incrémenter VERSION_GENERATEUR. Voir [[suivi-moteur-associe]], [[projet-reconstruction-3d-decisions]].
