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

## Chantier 2 fait (07/11/2026) : ce qui s'écarte de A, et ce qui reste à trancher

- **Page de base** (demande après la planche du chantier 1) : sous `--lot2`, rotation, perspective, papier gris, contraste < 1 et photocopie du style de base sont retirés, sauf vraie photo (famille « photo », vraie caméra). Le scan ancien pose sa propre page. Mesuré sur 200 tirages : 9,5 % de plans penchés, 8,5 % de pages grises (les 59 plans d'entraînement du catalogue : 5 à 10 % penchés selon qu'on compte les pentes < 0,5°, 7 % de pages grises).
- **Plan de travail** : `plans_de_travail_au_mur` (dans `rendre`, sous `--lot2`) retourne le meuble posé en travers. `mobilier.py` n'est pas touché. La carte de hauteur dépend donc du mobilier, comme prévu.
- **Écarts à A** : cotes par mur → par pièce, de face à face (fr-100) ; page blanche et pièces crème, pas fond crème (fr-100, fr-102, fr-103) ; numéro de lot dans la marge du haut ; jardin = rectangle accolé (fr-084, fr-102), pas une bande tout autour ; pastilles en disque foncé, avec le nom (fr-059) ou avec légende ; champs `textes_verticaux` et `pastilles` en texte au lieu de booléens.
- **Risque à trancher avec NT, vu à la mesure du lecteur** : sur les plans à cotes intérieures en cm (promoteur, scan), un trait de cote qui en croise un autre est pris pour une marque de fin de cote par `lecture_cotes._marques`. Les erreurs se ressemblent : plusieurs cotes s'accordent à tort et l'échelle est « sûre » et fausse sans alerte. Mesuré sur 30 tirages au hasard à plat, cotés en cm : **6 erreurs silencieuses de −10 à −41 %** (source « cotes », sûre), 14 justes à moins de 0,4 %, 10 envoyés à la vérification. Sans les traits verticaux, 5 de ces 6 erreurs disparaissent ; il reste 1 erreur de +3,6 %. Sur 5 des 6, les surfaces écrites donnaient la bonne échelle, mais `decider` ne les confronte aux cotes que si les cotes ne sont pas sûres. De vrais plans croisent aussi leurs cotes (fr-108, fr-062) : le dessin est juste, c'est le lecteur qui devra être revu avant de compter sur ces plans. Le lecteur n'a pas été modifié. Sans effet sur l'entraînement (le modèle ne lit pas l'échelle), mais un banc passé sur des plans lot 2 compterait ces erreurs.

## Chantier 3 fait (07/11/2026) : ce qui s'écarte de A, et ce qui a été vérifié

- **Écarts à A** : `fond_ecran` est dans `photo.py` et non `lot2.py` (photo.py ne doit pas importer lot2) ; `assembler` reçoit des niveaux déjà tournés, `composer` choisit l'orientation ; `Lot2.ecran_si_photo` (30 %) en plus de `ecran` (6 %), car parmi des plans qui sont tous des photos le cas pèse bien plus ; pente de 0,5 à 4° et non 2 à 8° (fr-024, fr-040, fr-086 penchent de 0,5 à 2° environ, estimé à l'œil) ; verso qui transparaît ajouté (fr-024) ; un plain-pied compose des niveaux une fois sur quatre comme prévu, mais un duplex tiré « deux logements » devient « niveaux ».
- **Ajouts à A, vus sur les plans** : une chaîne de cotes par bloc (fr-072 : une chaîne autour de l'image entière mesurerait du vide) ; titre sous le bloc (fr-075, fr-120), tirets (fr-025, fr-072), surface au titre (fr-120), filet entre niveaux (fr-072) ; pas de titre sur les relevés d'appli (fr-118, fr-119) ; symétries des blocs pour que les portes d'entrée se fassent face sur le palier ; fenêtres rebouchées au contact d'un mitoyen, porte d'entrée jamais au contact (sinon le mitoyen devient palier) ; refus au-delà de 255 éléments (le masque est sur 8 bits).
- **Retiré sur un ensemble** (ils parlent d'UN niveau ou prennent la marge des titres) : numéro de lot, légende « Niveau 0 », échelle écrite, placards fléchés, titre du plan, recadrage. Les extérieurs restent, mais jamais dans le vide entre deux blocs.
- **Hors des fichiers lot 2** : `statistiques.py` compte les `-ensemble` à part ; `__main__.py doublons` les écarte ; `plan_pdf.fabriquer_jeu` les saute (`int(ident)` aurait planté) ; `repartir` les met avec leur parent.
- **Part mesurée** sur 300 graines (270 logements, sans dessin) : 36 ensembles, soit 13,3 % (26 niveaux, 10 deux logements), 0 refusé ; 10,4 % de duplex, 5,6 % de pages à l'écran.
- **Chargeur** : `..\atelya\entrainer.py` n'a besoin d'aucune modification (`lire_partitions` ne complète de zéros que les identifiants purement chiffrés, `dessins` lit `exemples/<id>/niveau_*`). Vérifié par un vrai appel sur `..\atelya\planches\lot2-revue`.

## Revue adverse (07/11/2026) : ce qui a changé

- **`--lot2 --sans-cotes`** : plus de dimensions de pièce ; titre et cartouche éteints quand les surfaces le sont. Reste permis par choix : surfaces si l'option les tire (avec le titre, le tableau et le cartouche), barre d'échelle tirée par l'option, HSP.
- **Mitoyen + biais** : contact à 2 mm près (`TOLERANCE_CONTACT`), le cadre est arrondi par les murs en biais.
- **Croquis penché** : quand le garde-fou retire le contour, le mur prend la couleur du trait, sauf style absurde et couleur tirée par la famille.
- **Ensemble** : pas de cartouche ; dans `geometrie.json`, une épaisseur qui diffère entre les deux logements est retirée de `parametres` (`parametres_vrais`).
- **Contour « gris » d'un extérieur** : 2 pixels au plus (écart assumé à fr-102 : un trait d'allure de cloison, masque = fond, s'apprendrait).
- **`plan_pdf.fabriquer_jeu`** : alerte claire sur un jeu `--lot2`, comportement inchangé.
- **Tests** : `test_image_contre_masque*` compare enfin l'image au masque (couleurs témoins) ; les cotes, dimensions et surfaces écrites sont comparées à leur vraie valeur. Preuve par mutants : `..\atelya\planches\lot2-revue-adverse\s6_mutants_apres.py`.

## Après le code

Le lot 2 ne change aucune note tant qu'un modèle n'a pas appris dessus. Fabriquer le jeu (`tout --nombre 3300 --depart 70001 --lot2 ...`) et lancer l'essai 8 demandent l'accord de NT.

**Leçon de l'essai 6 à garder pour l'essai 8** : une part trop forte de styles nouveaux a fait reculer les anciens et les photos (`atelya-styles-monde.md`). Le lot 2 s'ajoute aux jeux existants, il ne les remplace pas ; sa part se règle par petits essais.

## Banc des styles du lot 2 avec le lecteur en service (08/11/2026)

Pourquoi : un point de départ mesuré avant l'essai 8. Jeu `..\atelya\donnees\lot2-test` (412 exemples, 439 niveaux dont 48 composés), tout en partition test depuis le 08/11 (`repartir --parts 0,0,1` ; l'ancienne répartition est gardée dans `repartition-origine.json`), jamais appris. Script `pc/lot2/banc-lot2.ps1` (essai 5, 4 angles, doutes ; coloriage 2 min sur la carte graphique, banc 24 min). Résultats `..\atelya\banc-lot2-e5\`.

| | lot 2 (e5) | plans fabriqués habituels | photos réalistes |
|---|---|---|---|
| murs justes | 59,6 % | 90,6 % | 78,7 % |
| pièces trouvées / bon type | 75,7 / 69,5 % | 99,1 / 97,4 % | 94,7 / 90,8 % |
| ouvertures justes | 58,1 % | 92,0 % | 85,5 % |
| plans parfaits | 28,9 % | 53,2 % | 27,1 % |
| échelle lue | 273 / 439 | 1 010 / 1 066 | 286 / 343 |
| fausse > 3 % sans alerte | 1 (129128-ensemble, surfaces, −6 %) | 0 | 0 |

L'erreur d'échelle vient des images à plusieurs niveaux (même défaut que fr-025) : traitée à part.
