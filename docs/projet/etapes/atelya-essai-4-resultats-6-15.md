# Étape 6-15 : résultats de l'essai 4 d'Atelya (photos de téléphone)

Ordre : murs justes / ouvertures justes / pièces trouvées / bon type / plans parfaits / échelle lue / erreurs d'échelle > 3 %

## 342 photos de biais sans cotes (jamais vues à l'apprentissage)
| Version | Murs | Ouv. | Pièces | Bon type | Parfaits | Échelle lue | > 3 % |
|---|---|---|---|---|---|---|---|
| 6-14 : duo essai 2 + essai 3 | 57,1 | 55,3 | 78,9 | 54,4 | 5,8 | 175 (51,2 %) | 1 |
| 6-15 : duo essai 4 + essai 3 | 70,8 | 78,3 | 88,5 | 59,2 | 12,9 | 208 (60,8 %) | 0 |
| 6-15 : essai 4 seul | 70,8 | 78,3 | 93,5 | 86,9 | 19,6 | 208 (60,8 %) | 0 |
| (repère : coloriage parfait) | 94,4 | 99,7 | — | — | 74 | 216 | 0 |

## 1 066 anciens niveaux (contrôle de non-recul)
| Version | Murs | Ouv. | Pièces | Bon type | Parfaits | Échelle lue | > 3 % |
|---|---|---|---|---|---|---|---|
| 6-14 : duo essai 2 + essai 3 | 88,7 | 88,2 | 97,8 | 95,5 | 41,3 | 1006 (94,4 %) | 0 |
| 6-15 : duo essai 4 + essai 3 | 89,9 | 91,0 | 98,2 | 95,9 | 47,0 | 1002 (94,0 %) | 0 |
| 6-15 : essai 4 seul | 89,9 | 91,0 | 98,2 | 95,8 | 45,5 | 1002 (94,0 %) | 0 |

Hors tout à 10 cm près : photos 83,0 → 90,9 % (essai 4 seul) ; anciens 97,2 → 97,8 %.
Échelles lues justes à 1 % près (anciens) : 99,1 → 99,5 %. 4 échelles lues en moins sur 1 066 (−0,4 point, sous le garde-fou de 0,5).

## Entraînement (PC RTX 2070, 2 h, 37 000 pas, 80 °C max, sans pause)
Repris de l'essai 2, 2 576 photos « vraie caméra » fabriquées (graines 30001-32800) mélangées aux 8 219 anciens plans (35 % de photos).
Coloriage, contrôle complet : photos IoU 55,4 → 79,4 %, anciens 81,8 → 86,4 %.

## Limites honnêtes
- Photos fabriquées : fond uni dégradé, pas de vraie table, reflets, ombres ni papier froissé.
- Murs justes sur photos : 71 %, encore loin du coloriage parfait (94 %).
- 134 photos sur 342 sans échelle lue (dont 92 sans aucune information d'échelle sur le plan).
