# Écran de vérification des plans

Page autonome, rangée à part : elle ne modifie et n'importe aucun module du moteur.
Elle fonctionne sans Internet : ouvrir `index.html` dans Google Chrome (double-clic).

- « Voir l'exemple » : le cas test n°0, avec des erreurs glissées exprès (pièce mal nommée,
  porte oubliée, petit mur parasite, fenêtre peu sûre) pour montrer les doutes en orange.
- « Ouvrir un plan à vérifier… » : choisir ensemble le fichier de vérification (.json) et l'image du plan.

## Deux modes

L'écran s'ouvre en mode **comparer** : le plan d'origine et ce qu'Atelya a lu par-dessus, les doutes en
orange, sans aucun outil de correction. Le bouton « ✎ Corriger » (ou `?mode=corriger` dans l'adresse)
fait apparaître les corrections et le bouton « Valider ».

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

## Corriger (étape B)

- Chaque doute propose des corrections en un clic (écrites par Atelya dans `doutes[].propositions`,
  sinon « C'est juste » / « Supprimer »). Actions possibles : `confirmer`, `supprimer`, `renommer`,
  `ajouter_ouverture`, `resoudre`.
- Outil « Choisir » : cliquer un élément ouvre sa fiche (renommer une pièce, type/largeur/position
  d'une porte, épaisseur d'un mur, corriger une cote : ce mur seulement ou l'échelle de tout le plan).
  Glisser un mur le déplace ; les murs et les coins de pièces qui le touchent suivent.
- Outils « + Mur », « + Porte », « + Fenêtre », « + Porte-fenêtre ».
- Annuler / Rétablir (Cmd+Z, Cmd+Maj+Z), Suppr pour supprimer, Échap pour revenir à « Choisir ».
- « Lisible par le moteur ? » applique les mêmes règles que `moteur/logement.py`.
- Un élément touché par la personne passe à confiance 1, source `…+verification`, et son id
  est rangé dans `verifies` (les doutes réglés sans élément dans `resolus`).

Le code est écrit pour ce projet ; aucun morceau d'OpenPlan3D n'a été recopié (pas de mention de licence à ajouter).

## Fichiers

- `calculs-verif.js` : les calculs (calage, formes, doutes), sans dessin.
- `verification.js` : l'affichage et les clics.
- `exemples/` : l'exemple (refait par `scripts/faire_exemple.py`).
- `tests/verif.test.js` : `node --test outils/verification-plan/tests/verif.test.js` (21 tests).
- `../scripts/scenario-B.js` : parcours complet dans un vrai navigateur (Playwright), avec captures.

## Valider (étape C) et branchement au site

- « ✓ Valider » : refuse un logement incohérent ; s'il reste des doutes, demande confirmation
  (ils sont notés dans le rapport). Écran seul : télécharge `<projet>-logement.json`.
  Écran ouvert dans le site : renvoie au site un `resultat-verification/0.1` (logement + rapport).
- Branchement au site interne : voir `BRANCHEMENT.md` (fiche pour l'associé) et la démo `exemples/site-demo.html`.
- Test côté moteur : `tests/test_ecran_verification.py` relit avec `moteur/logement.py` le logement
  corrigé d'exemple (`exemples/exemple-cas-test-00.logement-corrige.json`, enregistré par `scripts/scenario-C.js`).
