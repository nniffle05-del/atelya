# Lot 2 du générateur : conception retenue (07/11/2026)

Écrit pour les agents qui codent le lot 2 et pour la conversation qui reprendra. À lire avec `catalogue-styles-lot2.md` (les 20 traits).

**Pourquoi le lot 2** : Atelya rate les styles jamais vus. Le générateur doit savoir dessiner les styles observés sur les 103 vrais plans, pour que l'essai 8 les apprenne aussi sur des plans fabriqués (dont la vérité est exacte).

## Le choix : A, avec des ajouts de B

Base = **conception A** (`lot2-travail/concevoir-A.json`, à suivre tâche par tâche) : module `moteur/generateur/lot2.py`, champ `Style.lot2`, option `--lot2`. Cartes du code : `lot2-travail/lire-*.json`.

Pourquoi A plutôt que B :
- **Composition (traits 12, 13)** : A fabrique un vrai exemple `{ident}-ensemble/` à UN seul niveau. `rendre` et `valider_dossier` marchent sans changement et l'exemple a une vérité complète. B demandait de refactoriser le validateur (la garde de la vérité) et un index de niveau −1.
- **Anciens jeux** : A ne touche pas à `variete.py`. B repose sur l'équivalence « `Variete()` vide = `None` » et refactorise `V.sol`, ce qui met les jeux du lot 1 en risque pour aucun gain.
- **Fichiers** : B ferait grossir `variete.py` d'environ 600 lignes.

## Ce qui change par rapport à A (prime sur le texte de A)

1. **JSON aussi identique sans l'option.** A acceptait une clé `"lot2": null` dans `annotations.json`. Refusé : `Style.en_dict()` retire `lot2` s'il vaut `None`, `Realisme.en_dict()` retire `ecran` s'il vaut `False`. Le témoin compare donc aussi `annotations.json` (seule la version dans `geometrie.json` et les manifestes peut changer).
2. **Étiquette encadrée** : jamais sur une pièce à `p.contour` (biais), sa boîte `p.rect` peut déborder du contour et recouvrir un mur (repris de B).
3. **`--sans-cotes` gagne toujours** : aucune famille ne remet `style.cotes` ou `style.surfaces` à vrai s'ils ont été éteints par l'option ; tout ce qui écrit une mesure (cotes en cm, par mur, intérieures, rouges, « Échelle : 1/50e », dimensions, tableau de surfaces, légende, HSP non) lit ces deux champs. Le banc « sans cotes » suppose zéro mesure écrite. Vérifier dans `style_pour` l'ordre réel entre `sans_cotes` et le bloc lot 2.
4. **Vraie caméra** (`style.focale`) : pas de recadrage ni de rotation ajoutée (repris de B).
5. **Défaut connu `contour_des_murs`** (contour calculé sur le masque tourné puis dessiné à plat : double contour décalé sur les plans penchés) : sous `--lot2`, `appliquer` met `murs_contour=False` si rotation, perspective ou focale sont non nuls. Le code lui-même n'est pas modifié : les anciens jeux changeraient.
6. **`--styles-monde` + `--lot2`** : si la famille impose des murs pleins (`agence_coloree`, `murs_noirs`) et que la variété n'est ni absurde ni inversée, `variete.murs = "plein"` (seulement sous `--lot2`).
7. **Composition impossible** (second logement refusé) : pas d'exemple `-ensemble`, et le manifeste le dit (`"compose": false`), repris de B.
8. **Vérifier** que le chargeur d'entraînement voit bien les `-ensemble` (`..\atelya\entrainer.py`, ligne 77, `exemples/<ident>/niveau_*`, et d'où vient la liste des `ident`) et que `statistiques.py` ne les compte pas à tort.
9. **Graine** : clé `lot2-{graine + opt.graine_styles}-{variante}` (convention des autres clés), identique à celle du catalogue avec la valeur par défaut.

## Contraintes qui ne se négocient pas

- Sans `--lot2`, les anciens jeux sont **identiques au pixel**, prouvé par le témoin d'avant le code (8 graines, conception A tâche 1). Tout écart : chercher la cause avant de continuer.
- **Les masques ne changent pas de sens** : sols, cotes, cercles PMR, étiquettes, tableaux, extérieurs = fond. Une vérité fausse devient une erreur apprise.
- **Règle 15** : aucun plan d'examen n'est ouvert, ni cité, ni imité. Liste : `verites/repartition-vrais-plans.json` (`examen_nouveaux`, `examen_anciens`). Le catalogue cite fr-020, fr-052 et fr-095 comme plans à ne pas imiter : ne pas les ouvrir.
- **Le modèle voit du gris réduit à 768 px** : les planches se jugent en couleur ET en gris.
- Aucune installation, aucune police téléchargée. Nouveau code : `moteur/images.py`, jamais `cv2.imread`/`imwrite`. Chemins relatifs vers `..\atelya\`. Commentaires qui disent pourquoi.

## Les 3 chantiers

| Chantier | Traits du catalogue | Tâches de A |
|---|---|---|
| 1. Socle, texte, couleurs, murs simples | 1, 2, 4 (sans les balcons), 5, 8, 16, 19, 20 | 1, 2, 3, 4, 5, 7, 8, 11, 17, 19, 21, 24, début de 25 et 26 |
| 2. Promoteur gris, logiciel grand public, cm, scan, manuscrit, extérieurs | 3, 6, 7, 9, 11, 14, 15, 17, 18 (et les balcons du 4) | 6, 9, 10, 12, 14, 15, 16, 18, 20, suite de 25 et 26 |
| 3. Plusieurs niveaux, deux logements, page vue à l'écran | 12, 13, 10 | 22, 23, 13, fin de 25 et 26 |

Chaque chantier laisse les tests verts et le témoin identique, et écrit une planche `..\atelya\planches\lot2-chantierN.jpg` comparée aux plans d'entraînement du catalogue. Les fichiers `.jpg` de planches restent hors dépôt.

## Après le code

Le lot 2 ne change aucune note tant qu'un modèle n'a pas appris dessus. Fabriquer le jeu (`tout --nombre 3300 --depart 70001 --lot2 ...`) et lancer l'essai 8 demandent l'accord de NT.

**Leçon de l'essai 6 à garder pour l'essai 8** : une part trop forte de styles nouveaux a fait reculer les anciens et les photos (`atelya-styles-monde.md`). Le lot 2 s'ajoute aux jeux existants, il ne les remplace pas ; sa part se règle par petits essais.
