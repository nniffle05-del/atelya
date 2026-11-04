# Écran de vérification des plans

Page autonome, rangée à part : elle ne modifie et n'importe aucun module du moteur.
Elle fonctionne sans Internet : ouvrir `index.html` dans Google Chrome (double-clic).

- « Voir l'exemple » : le cas test n°0, avec des erreurs glissées exprès (pièce mal nommée,
  porte oubliée, petit mur parasite, fenêtre peu sûre) pour montrer les doutes en orange.
- « Ouvrir un plan à vérifier… » : choisir ensemble le fichier de vérification (.json) et l'image du plan.

## Comment il se présente

Un seul mode : on ouvre le plan et on peut corriger tout de suite. En haut, trois vues : « Plan d'origine »,
« Lecture d'Atelya » (la lecture seule, sur fond blanc) et « Les deux ». À droite, un point à vérifier à la fois,
expliqué en français, avec le plan qui vient se placer dessus ; dessous, « Ajouter », « Pièces » et « Aide ».
Une page `ecran.html` tout-en-un est fabriquée pour chaque plan lu (`scripts/page_unique.py`) : un double-clic suffit.

## Le fichier de vérification (`verification/0.1`)

```json
{
  "schema": "verification/0.1",
  "plan": "nom de l'image (pour info)",
  "calage": {"px_par_m": 100, "origine_px": [210, 760]},
  "echelle": {"etat": "lue" | "a_verifier", "raison": "..."},
  "logement": { ... un logement.json (logement/0.1) tel que lu par Atelya ... },
  "doutes": [{"element": "id ou null", "zone_px": [x, y, largeur, hauteur], "raison": "..."}]
}
```

`calage` peut aussi être `{"matrice": [[...],[...],[...]]}` (3 × 3, mètres → pixels de l'image),
pour un plan tourné ou une photo de biais.
En plus des `doutes` écrits, la page met en orange : confiance < 70 %, mur < 30 cm,
porte < 55 cm, ouverture > 3 m, surface écrite différente du contour.

## Les points à vérifier

`pointsAVerifier` (dans `calculs-verif.js`) présente les doutes autrement, sans en changer aucun ni aucun seuil :
1. l'échelle : à contrôler quand elle est lue (une erreur d'échelle ne se voit pas sur le dessin), à corriger sinon ;
1 bis. deux ouvertures l'une sur l'autre sur le même mur (le moteur 3D refuse) : « laquelle garder ? » ; `verifierCoherence` le refuse aussi ;
2. les pièces qu'aucun mur ne sépare (`morceauxDePieces`) : « Les réunir » (`fusionnerPieces`) ou « Ce sont des pièces séparées » ;
3. les doutes sur une porte, une fenêtre ou une pièce, un par un ;
4. les doutes sur des murs ou des zones à moins de 60 cm les uns des autres : un seul point ;
5. les petites hésitations (gravité « faible ») : un seul point, à la fin.

Le préparateur Python (`moteur/preparer_verification.py`) ajoute un doute `construction` quand la 3D (`moteur/geometrie.py`)
refuse le logement tel quel (ouverture dans l'angle d'un mur, ou sur une autre) : il devient un point sur l'ouverture en cause.
L'écran ne refait pas ce contrôle après les corrections.

## Corriger

- Cliquer un élément sur le plan ouvre sa fiche (nom d'une pièce, réunion avec une autre, type et largeur d'une porte,
  vraie longueur d'un mur : ce mur seulement ou tout le plan à la bonne taille). Glisser un mur le déplace ; les murs
  et les coins de pièces qui le touchent suivent.
- Chaque point se règle par « oui » ou par « non » : « non » ouvre la correction précise (vraie mesure, fiche de l'élément, doutes groupés vus un par un).
- « ✎ Outils » : couper un mur, enlever un morceau (au centimètre, à taper ou à cliquer), relier deux murs ; ajouter un mur, une porte, une fenêtre, une porte-fenêtre.
- Fiche d'un mur : tirer les ronds à ses bouts (il s'accroche au voisin), le déplacer d'une distance exacte, épaisseur − / +.
- « Recalculer les pièces » : chaque espace fermé par des murs devient une pièce ; une pièce non fermée reste inchangée et est signalée.
- Annuler / Rétablir (Ctrl+Z, Ctrl+Y), Suppr pour supprimer, Échap pour arrêter un outil.
- Un élément touché par la personne passe à confiance 1, source `…+verification`, et son id
  est rangé dans `verifies` (les doutes réglés sans élément dans `resolus`).

Le code est écrit pour ce projet ; aucun morceau d'OpenPlan3D n'a été recopié (pas de mention de licence à ajouter).

## Garder le travail

Chaque correction s'enregistre dans le navigateur (`localStorage`, écran seul) : à la réouverture, l'écran propose de reprendre.
Dans « Aide » : « Télécharger mon travail » (`travail-verification/0.1`), « Reprendre un fichier enregistré » (un travail, un
résultat, ou le logement.json de « Terminer » ; dans ce cas, le calage vient de la lecture de départ et les murs communs
redonnent la correction d'échelle) et « Repartir de la lecture d'Atelya ». L'historique d'« Annuler » n'est pas gardé.

## Fichiers

- `calculs-verif.js` : les calculs (calage, formes, doutes), sans dessin.
- `verification.js` : l'affichage et les clics.
- `exemples/` : l'exemple (refait par `scripts/faire_exemple.py`).
- `tests/verif.test.js` : `node --test outils/verification-plan/tests/verif.test.js` (28 tests) ; sur le PC, sans Node,
  `pc/verification/tests_ecran.py` les lance dans Chrome.
- `pc/verification/scenario_ecran.py` : parcours complet de l'écran dans Chrome sans fenêtre, avec captures.

## Terminer et branchement au site

- « ✓ Terminer » : refuse un logement incohérent ; s'il reste des points à vérifier, demande confirmation
  (ils sont notés dans le rapport). Écran seul : télécharge `<projet>-logement.json`.
  Écran ouvert dans le site : renvoie au site un `resultat-verification/0.1` (logement + rapport).
- Branchement au site interne : voir `BRANCHEMENT.md` (fiche pour l'associé) et la démo `exemples/site-demo.html`.
- Test côté moteur : `tests/test_ecran_verification.py` relit avec `moteur/logement.py` le logement
  corrigé d'exemple (`exemples/exemple-cas-test-00.logement-corrige.json`, enregistré par `scripts/scenario-C.js`).
