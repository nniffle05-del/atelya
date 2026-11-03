# Prompt à coller dans le projet Claude du site interne

*(Joindre au message le fichier `ecran-verification-atelya.zip`. Tout ce qui suit la ligne est à copier tel quel.)*

---

Bonjour. Je te confie une intégration dans **notre site interne** (ton projet). Lis tout avant de commencer.

## Le contexte

Mon associé (NT) développe « Atelya », le moteur qui lit les plans d'appartements et les transforme en
`logement.json`, un fichier qui décrit les murs, les portes, les fenêtres et les pièces en mètres.
Ce fichier part ensuite vers la 3D. Sur notre site, il existe déjà un onglet où l'on dépose les plans
et les photos d'un logement puis où l'on clique OK : Atelya lit le logement et dit si tout est sûr ou
s'il reste des **vérifications humaines** à faire.

Il manque l'endroit où une personne fait ces vérifications. Mon associé a construit un **écran de
vérification** qui fonctionne déjà : il est dans le zip joint (`verification-plan/`). Il affiche le
plan d'origine, la lecture d'Atelya par-dessus, les doutes en orange avec des corrections proposées
en un clic, des outils pour corriger (déplacer un mur, ajouter ou supprimer une porte, renommer une
pièce, corriger une cote), « Annuler / Rétablir », et un bouton « Valider » qui rend le
`logement.json` corrigé.

## Ce que je te demande

**Intégrer cet écran DANS notre site, en l'adaptant au site** (et non l'inverse) : même technologie,
même apparence, même navigation, mêmes comptes et mêmes droits d'accès, même façon de stocker les
fichiers que le reste du site. Pour la personne qui vérifie, il doit avoir l'air d'avoir toujours fait
partie du site.

Le parcours voulu :

1. Dans l'onglet existant, on dépose les plans et les photos, puis on clique OK. Ça ne change pas.
2. Atelya lit le logement. Pour chaque plan à vérifier, le moteur fournit un fichier
   `verification.json` (format `verification/0.1`, décrit dans `verification-plan/BRANCHEMENT.md` § 4)
   et l'image du plan.
3. Le logement prend le statut « à vérifier » et apparaît dans une liste. On peut ouvrir cette
   liste depuis l'onglet (ou depuis un sous-onglet « À vérifier », selon ce qui colle le mieux au site).
4. En cliquant sur le logement, l'écran de vérification s'ouvre dans le site, avec ce plan et cette lecture.
5. « Valider » enregistre le résultat (format `resultat-verification/0.1`, § 5 de `BRANCHEMENT.md`).
   Le logement corrigé est conservé avec son rapport, le statut passe à « vérifié », et le logement
   suit la même suite que les logements qu'Atelya a lus sans doute.
   « Abandonner » laisse le logement « à vérifier ».
6. Si Atelya est sûr de tout, il n'y a pas d'écran : le logement passe directement.

## Comment t'y prendre

- **Commence par regarder le site** : technologie, organisation des fichiers, composants
  d'interface, stockage, comptes. Puis **propose-moi un court plan** (où vont les fichiers, ce qui
  change, ce qui ne change pas) et **attends mon accord avant d'écrire du code**. Explique simplement,
  en français, et donne le pourquoi de chaque étape.
- **Le cœur à garder tel quel** : `calculs-verif.js`. Il contient tous les calculs : placement de
  la lecture sur l'image, doutes, corrections, règles de cohérence, résultat. Il n'a aucune dépendance
  et marche dans n'importe quelle technologie web. Tu peux l'importer comme module, mais ne change ni
  ses règles ni les deux formats d'échange. C'est le contrat avec le moteur : si un format change, le
  moteur ne s'y retrouve plus. Si tu as besoin d'un changement, note-le et dis-le-moi : je le
  transmettrai à mon associé.
- **Deux modes** : l'écran s'ouvre en mode « comparer » (on voit seulement le plan et ce qu'Atelya a lu
  par-dessus, avec les doutes en orange) ; le bouton « ✎ Corriger » fait apparaître les outils de correction.
  Garde ce fonctionnement.
- **L'interface, adapte-la librement** : `index.html` et `verification.js` sont une version
  autonome. Tu peux les réécrire en composants du site, changer les couleurs, la mise en page et les
  textes pour coller au site. Garde les fonctions : plan en fond, calques, doutes en orange avec
  propositions en un clic, fiche de l'élément choisi, outils d'ajout, annuler/rétablir, encadré
  « lisible par le moteur ? », confirmation si on valide avec des doutes restants.
- Si le plus simple pour le site est de garder la page telle quelle dans un cadre (`iframe`), le
  protocole de messages est déjà prêt (`BRANCHEMENT.md` § 2-3, démo dans `exemples/site-demo.html`).
  Choisis ce qui s'intègre le mieux, explique-moi pourquoi, et habille la page aux couleurs du site.
- **Tests** : les 21 tests de `tests/verif.test.js` (`node --test`) doivent continuer à passer.
  Ajoute les tests habituels du site pour le nouveau parcours. Pour essayer sans le moteur, sers-toi
  de l'exemple fourni (`exemples/exemple-cas-test-00.verification.json` + l'image contenue dans
  `exemple-cas-test-00.js`) : 4 erreurs y ont été glissées exprès.
- **Sécurité** : seules les personnes autorisées du site peuvent ouvrir l'écran et valider. Les
  fichiers des clients restent privés, comme le reste du site.

## Ce qu'il ne faut pas faire

- Ne rien changer au moteur Atelya, ni aux formats `verification/0.1`, `resultat-verification/0.1`
  et `logement/0.1`.
- Ne rien installer de payant ou sous licence AGPL sans m'en parler.
- Ne pas casser l'onglet existant : le dépôt des plans et le bouton OK continuent de marcher comme avant.

## Ce qui viendra du moteur plus tard

Pour l'instant, le moteur ne produit pas encore `verification.json` à partir de vraies lectures
d'Atelya : c'est sa prochaine étape. Prévois donc l'endroit où le site recevra ce fichier et l'image
du plan, en t'appuyant sur l'exemple. Le jour où le moteur les fournira, il n'y aura qu'à brancher.
Les fichiers de l'écran seront aussi rangés dans le dépôt du moteur, sous `outils/verification-plan/`.
Si une nouvelle version arrive, il suffira de reprendre `calculs-verif.js` et d'adapter l'interface
si besoin.

Commence par me proposer ton plan.
