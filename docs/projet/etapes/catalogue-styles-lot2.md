# Catalogue des styles vus sur les vrais plans (lot 2 du générateur)

Écrit le 05/11/2026 à partir de l'inventaire des 103 plans reçus (`vrais-plans-2026-11-05-inventaire.md`).
Les plans cités en exemple sont tous des plans d'**entraînement** (`verites/repartition-vrais-plans.json`) : les
plans d'examen ne servent ni de modèle ni de référence (règle 15). Images : `..\atelya\vrais-plans\lot-2026-11-05\fr-0xx.jpg`.

Ce que le générateur sait déjà faire (variete.py 0.1.4, lot 1) : sols carrelage/parquet/hachures/points/damier, murs
plein/trait/double/gris clair/hachure/couleur, lettres A-D, noms en couleur/majuscules/parenthèses, symboles du neuf,
arcs pointillés, capture d'écran (barre d'état, bandes, filigrane, agrandi), styles absurdes/inversés, murs en biais
(--biais), photos réalistes (--photo-realiste).

## Ce qui manque et qu'on voit souvent (par ordre d'importance)

| # | Trait de style | Fréquence sur 103 | Exemples (entraînement) | Vérité à ne pas changer |
|---|---|---|---|---|
| 1 | **Agence « colorée foncée »** : murs bleu nuit/noir très épais (12-20 px), pièces en aplats pastel différents par type, sans mobilier, surfaces « 14,5 m² » sous le nom, parfois 2 niveaux côte à côte « Niveau 0 / Niveau 1 », rose des vents | 13 | fr-075, fr-082, fr-094, fr-096, fr-116, fr-021 | rien |
| 2 | **Dimensions de pièce « 3,05 m × 2,85 m »** écrites sous le nom à la place (ou en plus) de la surface ; variante encadrée dans une étiquette blanche à bord gris (« Chambre / 3.87 x 4.65 m ») | 11 | fr-098, fr-117, fr-076, fr-118 (encadrées : fr-020 est à l'examen → imiter fr-096 pour l'étiquette du dressing hors plan) | rien (texte = fond) |
| 3 | **Promoteur gris** : trait fin gris moyen, cotes en **centimètres entiers** (« 326 », « 519 ») le long des murs à l'intérieur des pièces, cercles de giration PMR en pointillé, sols hachurés (parquet) dans certaines pièces, mobilier en trait fin, numéro de lot en gros (« 45 », « A1 14 », « T3 G206 60.44 m² »), mentions « PF/VR », « Rgt », « Dgt », « SdB » | 14 | fr-041, fr-108, fr-109, fr-110, fr-113, fr-062, fr-106 | rien (cercles = fond) |
| 4 | **Murs noirs très épais** + surfaces entre parenthèses « (12,2 m²) » en gris sous le nom ; balcons/terrasses hors logement en trait fin ou pointillé | 14 | fr-046, fr-063, fr-092, fr-085, fr-115 | balcon/terrasse = fond (le générateur n'a pas de classe extérieur) |
| 5 | **Légende/tableau de surfaces à côté du plan** (diagnostiqueur Carrez, promoteur) : colonne « Séjour 17,85 / Chambre 1 12,46 … TOTAL 65,89 m² », parfois tableau à bordures sous le plan ; les noms dans les pièces sont alors courts ou absents | 8 | fr-093, fr-074, fr-111, fr-039, fr-090 | rien |
| 6 | **Logiciel grand public** (Kozikaza/HomeByMe/magicplan) : murs gris moyen, fond crème clair, cotes grises petites le long de CHAQUE mur (« 4,86 m »), mobilier dessiné, étiquettes « Dressing » tournées, extérieurs en vert | 5 | fr-100, fr-102, fr-103, fr-070 | rien |
| 7 | **Texte tourné à 90°** (noms et surfaces écrits verticalement dans les pièces étroites) | 4 | fr-055, fr-067 | rien |
| 8 | **Fenêtres en rectangles cyan/bleu clair** dans le mur (au lieu des traits) | 6 | fr-023, fr-035, fr-034 | la fenêtre reste classe 3/4 |
| 9 | **Scan ancien bleuté / pâle** (promoteur des années 80-2000) : fond bleuté ou gris, cotes en cm manuscrites ou machine à écrire, terrasse carrelée, hachures de murs | 6 | fr-036, fr-037, fr-111, fr-078 (photo) | rien |
| 10 | **Photo d'une page papier** capturée à l'écran : page penchée de 2-8°, ombre, grain, reflet, texte en gros | 6 | fr-024, fr-040, fr-086 | déjà couvert en partie par --photo-realiste ; ajouter la variante « page vue à l'écran » (bordure d'écran, pas de table) |
| 11 | **Surfaces manuscrites** au stylo sur un plan imprimé, noms manuscrits (main levée) | 2 | fr-086, fr-112 | rien ; police « manuscrite » à ajouter (polices libres : voir moteur/polices) |
| 12 | **Plusieurs niveaux sur une image** : empilés verticalement (« Rez-de-chaussée / 1er étage ») ou côte à côte, chacun avec son titre ; escaliers reliant | 11 | fr-025, fr-072, fr-118, fr-119, fr-120, fr-075 | chaque niveau = ses pièces ; le vide entre niveaux = fond |
| 13 | **Deux logements côte à côte** sur le même plan (fr-052 est à l'examen : ne pas l'imiter ; le cas vient des plans d'étage de promoteur, fr-095 à l'examen aussi) | 2 | aucun en entraînement → le fabriquer à partir de deux logements du générateur, séparés par un mur mitoyen ou un palier | 2 logements = 2 groupes de pièces |
| 14 | **Pastilles numérotées** ①②③ dans les pièces + légende | 1 | fr-059 | rien |
| 15 | **Placards fléchés** avec étiquette hors de la pièce (« Placard 2 → ») et étiquettes reliées par un trait | 2 | fr-080, fr-096 | rien |
| 16 | **Cotes rouges** (chaînes de cotes en rouge, « Échelle : 1/50e » écrit) | 2 | fr-031, fr-105 | rien |
| 17 | **Escalier en colimaçon** (spirale), escalier droit avec flèche « ACCES ETAGE » | 4 | fr-093, fr-092, fr-120 | classe escalier |
| 18 | **Terrasse/balcon** hachurés ou à lattes, jardin dessiné (arbres), « Jardin 48 m² » | 10 | fr-048, fr-065, fr-084, fr-102 | fond |
| 19 | **HSP par pièce** (« hsp: 2.80 », « HSP 2,50 » cerclé) et mentions de sol (« sol carrelage ») sous le nom | 4 | fr-067, fr-105, fr-120 | rien |
| 20 | **Image recadrée serrée** : le logement touche les bords de l'image (pas de marge), texte coupé | 5 | fr-027, fr-076 | rien ; le masque suit |

## Ce qui est hors de portée de ce lot (à ne pas faire)

- Le **3D meublé en vue de dessus** (fr-029, fr-088, fr-039) : rendu photoréaliste de meubles ; on se contente d'un
  mobilier dessiné en couleur avec ombre portée légère (option de l'agence colorée).
- Les plans où le texte est illisible à l'échelle de l'image (fr-042, fr-058, fr-113) : rien à imiter, c'est de la
  résolution.

## Règles pour le lot 2 (rappel des contraintes de NT)

1. Nouvelle `VERSION_GENERATEUR` ; tout nouveau tirage passe par un `random.Random` à part
   (clé `f"lot2-{graine}-{variante}"`) : sans l'option `--lot2`, les anciens jeux restent **identiques au pixel**
   (vérifier sur 8 graines avec et sans l'option).
2. Les masques ne changent pas de sens : un sol hachuré, un cercle PMR, une cote en cm, une étiquette restent du fond.
3. Tests dans `tests/test_lot2.py` (chaque trait de style a au moins un test qui vérifie qu'il est dessiné et que le
   masque est inchangé).
4. Planche d'exemples (`..\atelya\planches\lot2-exemples.jpg`) à comparer à l'œil aux plans d'entraînement cités.
