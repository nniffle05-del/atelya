---
name: plan-lancement-lecture-claude
description: Décision NT du 08/11/2026 — au lancement, c'est Claude (par l'API) qui lit les plans, Atelya fait tout le reste ; lecteur entraîné gardé en secours / second avis ; chantiers d'entraînement au second plan ; étape choisie = brancher l'écran de vérification sur la lecture de Claude
metadata:
  type: project
---
**Décision NT (08/11/2026, projet claude.ai), changement de plan :**

- **Au lancement, ce n'est PAS Atelya qui lit les plans : c'est Claude, par l'API** (clé API sur console.anthropic.com,
  pas l'abonnement : ses conditions interdisent l'usage automatique, voir [[lecture-par-api-claude]]). Claude lit le plan et
  rend sa lecture ; Atelya fait tout le reste.
- **Atelya lira les plans lui-même À TERME**, quand il sera assez fort. Raison : entraîner le lecteur sur de vrais plans coûte
  trop cher et prend trop de temps pour l'instant (vérités faites par Opus imparfaites ; celles de Fable presque parfaites mais
  ~8 plans épuisent le quota de la semaine).
- **Le lecteur entraîné n'est PAS jeté** (U-Net essai 5 / 7b, aiguillage, traducteur) : il sert de **secours** et de **second
  avis** pour contrôler la lecture de Claude.
- **Chantiers d'entraînement du lecteur AU SECOND PLAN** : lot 2 du générateur, essai 8, vérités et entraînement sur les 105
  vrais plans. **Ne pas les reprendre sans l'accord de NT.** (Le travail fait reste sur la branche `etape-vrais-plans-105`.)
- **Atelya = tout ce qui suit la lecture** : écran de vérification, géométrie, Blender, habillage, photos et matières, meubles,
  soleil réel, caméra et cinématique, Unreal, plan 2D propre. Rien de tout cela n'est à « entraîner » : c'est du code (règles),
  plus au besoin des modèles déjà entraînés sous licence commerciale (SAM 2, DINOv2).
- **Claude ne calcule PAS les mètres** : il rend tout en pixels de l'image envoyée (murs, ouvertures, pièces, textes lus avec
  leur position, doutes) ; c'est notre code qui calcule l'échelle (cotes, surfaces, « 1/50 ») avec les garde-fous
  d'`echelle_plan`, pour qu'une erreur de calcul de Claude ne passe pas en silence.
- **Coût et exactitude de la lecture par Claude** : testés dans un AUTRE fil (outil `outils/lecture_api/lire_plans_claude.py`
  et mémoire `lecture-par-api-claude.md`, branche `origin/claude/project-thread-qtyplp`). Ne pas refaire ce test ailleurs,
  ne rien dépenser, **ne jamais mettre de clé API dans le dépôt ni dans le fil**. NB : cet outil demande à Claude des MÈTRES ;
  le format en pixels de l'étape ci-dessous le remplacera le moment venu (le chiffre d'exactitude sera alors à refaire).

**Étape choisie par NT (08/11/2026) : brancher l'écran de vérification sur la lecture de Claude.** Branche dédiée
(`etape-ecran-lecture-claude`). Contenu demandé : 1) format de la lecture de Claude en pixels (+ textes et doutes) ;
2) traducteur lecture de Claude → `logement.json` + `verification.json` (calage pixels ↔ mètres) ; 3) doutes (bon sens,
construction, cotes/surfaces contradictoires, doutes de Claude ; en option : désaccord avec Atelya) ; 4) essai sans clé API sur
les vérités des 15 vrais plans (`verites/`) prises comme lecture parfaite + copies abîmées exprès ; aucun réglage sur les 13
plans d'examen ; 5) ensuite seulement : NT chronomètre la correction à l'écran, puis 3D Blender. **Plan validé par NT le 08/11/2026**
(base : `etape-vrais-plans-105` fusionnée dans `main` en local par avance rapide, 33e58de, choix « B » de NT ; nouvelle branche
`etape-ecran-lecture-claude` partie de ce `main`).

**Correction validée par NT (08/11/2026) : l'échelle à « deux clés ».** NT a demandé si Claude n'est pas plus adapté à la lecture
complète. Réponse honnête : non mesuré à ce jour ; Claude est sans doute meilleur pour COMPRENDRE (quelle cote mesure quel mur,
textes, styles jamais vus ; notre code ne lit l'échelle que sur 4/15 vrais plans), moins sûr pour le CALCUL exact (pixels précis,
longues chaînes de calcul, erreurs dites avec aplomb). Donc : Claude donne, pour chaque cote, sa valeur et les deux bouts de son
trait en pixels, plus SA propre échelle proposée ; notre code recalcule l'échelle depuis ces cotes avec les contrôles d'accord
actuels ; si les deux échelles s'accordent à 3 % → « sûre », sinon doute fort en tête de l'écran. Si les mesures montrent un jour
que Claude ne se trompe pas sur l'échelle, on pourra lui donner plus de poids sans rien refaire.
Partage des rôles rappelé à NT : la LECTURE (reconnaître murs, portes, pièces, textes) = le gros du travail = Claude ; la qualité
de lecture dépend donc surtout de lui (Atelya signale, l'humain corrige) ; dépendance à Anthropic (prix, disponibilité) → U-Net
gardé en secours ; tout ce qui suit la lecture = 100 % Atelya.

**Images envoyées à l'API (documentation officielle lue le 08/11/2026, pages vision et vision-coordinates)** : modèles « haute
résolution » (Claude 4.7 et suivants : Opus 5.5, Sonnet 5.5, Fable 5.1) = côté ≤ 2 576 px ET ≤ 4 784 jetons (1 jeton = carré de
28 × 28 px) ; au-delà l'API RÉDUIT l'image en silence et Claude rend ses coordonnées dans l'image réduite. Bord vide ajouté en bas
et à droite (multiple de 28) sans déplacer l'origine. Coordonnées de Claude = APPROXIMATIVES (doc) → recalage sur le trait du
dessin ; pour les détails fins, envoyer un recadrage. Un PDF envoyé tel quel est converti à une taille inconnue → toujours envoyer
NOTRE image. Garde-fou : bloc image `"transformations": {"oversized_image": "error"}` (refus au lieu de réduction). Coordonnées
absolues en pixels demandées explicitement (la doc déconseille les coordonnées 0-1000). Formule de réduction recopiée dans
`moteur/lecture_claude.py` (`taille_pour_claude`, testée sur les exemples de la doc).

**Sous-étape 1 FAITE (08/11/2026)** : `moteur/lecture_claude.py` 0.1.0 = format `lecture-claude/0.1` (pydantic strict : murs axe +
épaisseur px, ouvertures bord à bord, pièces nom écrit + type parmi les 11 du coloriage + point + contour facultatif, cotes texte +
valeur_m + cadre + DEUX BOUTS + mur, surfaces, autres textes, échelle proposée par Claude, niveaux non lus, doutes de Claude) ;
`controler_fiche` (refus : forme, image d'une autre taille ou que l'API réduirait, point loin hors image, trait nul ; doutes : nombre
écrit ≠ valeur comptée, point hors contour ; petits débords ramenés au bord) ; `consigne()` = texte pour Claude (rien envoyé) ;
`tests/test_lecture_claude.py` 12 tests.

**Sous-étape 2 FAITE (08/11/2026)** : `moteur/traduire_claude.py` 0.1.0 (`traduire(source, fiche contrôlée, facteur)` → `PlanLu`
que `preparer_verification.verification_du_plan` affiche SANS changement). Enchaînement : murs recalés sur l'encre
(`moteur/recalage_murs.py` = `affiner_mur` DÉPLACÉ tel quel depuis `outils/verite/faire_verite.py`, qui l'importe) → bâti → pièces =
zones fermées autour du point de Claude (contour de Claude si les murs ne ferment pas : doute faible ; sinon pièce non construite,
doute fort ; deux points dans la même zone sans contours = pièces réunies, doute faible) → « coloriage de Claude » (classes du U-Net,
768 px) donné à `lire_echelle_plan` avec les textes de Claude comme textes de PDF (textes exacts du PDF prioritaires) + `decider` →
DEUX CLÉS : Atelya (dessin) et Claude (proposée) d'accord à 3 % → « lue » ; désaccord → « à vérifier » + doute fort
`echelle_desaccord` (brouillon à l'échelle d'Atelya) ; seulement Atelya → « lue » ; sans clé d'Atelya → toujours « à vérifier »,
brouillon = cotes de Claude recalculées par nous depuis leurs bouts (plus grand groupe d'accord à 3 %, ≥ 2 cotes) → échelle proposée
par Claude (taille vraisemblable) → secours d'Atelya. Logement : repère d'Atelya (origine coin sud-ouest intérieur), ouvertures sur
le mur désigné par Claude s'il passe par elles sinon le plus proche (≤ 12 px ou l'épaisseur), raccourcies au bout du mur. Doutes :
fiche (fort), Claude (gravité de Claude), plusieurs niveaux (en tête), échelle, pièces, puis `examiner` (bon sens). Défaut trouvé par
les tests et corrigé : deux cotes en désaccord → la médiane n'en gardait aucune (division par zéro) → plus grand groupe d'accord.
Constat : notre lecteur trouve l'échelle par les SURFACES recopiées par Claude même sans cotes dessinées (textes non vérifiés sur
l'image) → piste sous-étape 3 : vérifier que les textes de Claude existent bien sur l'image (OCR sur leur cadre).
Outil : `outils/lecture_claude/traduire_fiche.py` (`preparer` = envoi.png à la taille exacte + consigne.txt ; `traduire` = mêmes
sorties que lire_plan.py, ecran.html compris ; aucun appel à l'API). Tests : `tests/test_traduire_claude.py` 11 (plan dessiné exprès,
positions de Claude décalées de 3 px : murs à 5 mm près, pièces à 1-2 %, calage sur l'encre, désaccord 20 % attrapé, image envoyée
réduite de moitié, pièce ouverte, pièces réunies, ouverture hors mur, cote mal recopiée, plusieurs niveaux, fiche refusée).

**Sous-étape 3 FAITE (08/11/2026)** : `moteur/doutes_claude.py` 0.1.0, branché dans `traduire_claude` 0.2.0. Trois contrôles de ce que
Claude affirme contre ce qu'il n'a pas produit : (1) textes recopiés : PDF → un texte exact du PDF avec le même nombre doit être dans
le cadre (sinon fort) ; image → cadre presque sans encre (< 1 %) = texte inventé (fort), sinon OCR d'Atelya sur le seul cadre (agrandi
×2) : autres chiffres lus → FAIBLE (l'OCR se trompe souvent sur les vrais plans), rien lu → rien ; (2) cote contre le dessin
(échelle LUE seulement) : longueur entre les marques retrouvées par Atelya (tolérance 3 %) sinon entre les bouts de Claude (5 % ou
8 px) contre le nombre ÉCRIT → fort ; (3) surface écrite contre la pièce construite (échelle lue seulement ; pièce rattachée par
Claude, sinon celle qui contient le texte) : écart > 10 % et > 0,5 m² → fort. Seuils posés par principe, à recalibrer sur les vérités
d'ENTRAÎNEMENT. Limite connue : un texte inventé posé sur un trait (encre présente) n'est pas vu si l'OCR ne lit rien. Corrigé au
passage : les doutes écrits avant la construction désignaient les éléments par l'id de la fiche (« P1 ») → remis aux ids du logement
(l'écran surligne le bon élément) ; message « pièces réunies » avec les noms. Doutes de construction (3D) : déjà ajoutés par
`verification_du_plan`. Option « second avis d'Atelya » (U-Net) : NON faite, à proposer à NT après mesure du taux de fausses alertes
(sous-étape 4). Tests : 7 de plus dans `tests/test_traduire_claude.py` (30 pour l'étape).

**DÉCISION NT (08/11/2026, après la sous-étape 3)** : « Non, on testera l'API à la fin. » La sous-étape 4 (essai sur les vérités +
copies abîmées) et tout test de l'API sont REPORTÉS À LA FIN. Priorité : qu'Atelya soit performant PARTOUT, en commençant par la
partie Blender (la 3D et les rendus). Entrée de travail : un plan dont FABLE a fait la vérité (vérités Fable relues = fr-021 à fr-027,
fr-029 à fr-041, plans d'ENTRAÎNEMENT, utilisables librement), pris comme « lecture de Claude ». Plan choisi : fr-031 (coté en m,
1/50, 115 px/m, 15 murs, 17 ouvertures, 8 pièces, confiance 88 ; image `..\atelya\vrais-plans\lot-2026-11-05\fr-031.jpg`).

**Premier passage fr-031 de bout en bout (08/11/2026)** : `outils/lecture_claude/fiche_depuis_verite.py` (vérité → fiche, murs
affinés de verite.json, échelle de la vérité = clé de Claude, remarques de Fable = doutes faibles) puis `traduire_fiche.py traduire
--textes-atelya` (OCR d'Atelya comme textes) → ..\atelya\lectures-claude\fr-031\ (ecran.html) → `python -m moteur.construire` →
..\atelya\lectures-claude\fr-031\3d\ (maquette.blend, 2 images Cycles, 37 s). Constats : échelle « à vérifier » car la lecture des
cotes d'Atelya se trompe sur ce plan (8,04 → 106 px/m au lieu de 115, cotes contredites/ambiguës) : les deux clés ont bien refusé
« lue » ; 2 doutes « porte de 3,01 m / 2,40 m » = conventions des vérités (front de placard et cuisine ouverte tracés en mur de 2-3 px
+ porte de toute la largeur). Rendu : disposition juste, mais DÉFAUTS 3D vérifiés au zoom : (1) filet BLEU (ciel) à la jonction
sol / mur côté fenêtres = trou entre le sol et le mur ; (2) filet de LUMIÈRE à la jonction plafond / mur ; (3) petits CARRÉS NOIRS aux
jonctions de murs (vue de dessus) ; (4) faux murs fins des vérités rendus comme des murs. Qualité : pièces vides, lumière plate, soleil
fixe inventé, pas de plinthes, focale très large, 2 images seulement. Plan Blender (B1 maquette sans défaut → B2 rendu photo d'annonce
→ B3 soleil réel → B4 meubles → B5 caméra / cinématique + comparatif) proposé à NT, en attente de son choix.

**Why:** lancer Atelya plus vite avec une lecture déjà bonne, sans payer maintenant l'entraînement sur de vrais plans ; garder
la vérification humaine et nos garde-fous d'échelle pour qu'aucune erreur de Claude ne passe en silence.
**How to apply:** ne plus proposer d'entraînement du lecteur comme priorité ; juger les étapes sur ce qu'elles apportent à la
chaîne « lecture de Claude → vérification → 3D » ; ne jamais faire calculer l'échelle par Claude ; aucune dépense API sans
accord écrit de NT. Voir [[objectif-global-nt]], [[atelya-verification-reelle]], [[ecran-verification]],
[[atelya-echelle-vrais-plans]], [[vrais-plans-francais]].
Meubles (B4) : NT veut du RÉALISTE avant tout (08/11/2026) → ABO retenu, Sand3D écarté (voir audit-technologique-2026-10-31.md).

**B1 « maquette sans défaut » (08/11/2026, accord NT « Oui »)** — image donnée à NT : maquette en carton, murs = planches, sol =
moquette. Défauts vus sur fr-031 et leurs causes : filet de ciel au pied des murs et de lumière au plafond (sols/plafonds = contour lu,
quelques mm en retrait des murs), carrés noirs aux jonctions (deux murs l'un dans l'autre : dessus à la même hauteur qui se font de
l'ombre au rendu ; aussi bouts lus qui se croisent ou s'arrêtent à 3,5 cm), cuisine NOIRE (deux sols superposés : la 1re pièce d'une
zone partagée gardait toute la zone), faux murs fins des vérités. Corrections :
- `moteur/geometrie.py` : bouts à moins de max(3 cm, ½ épaisseur du plus mince) réunis ; nœud de 3 murs dont 2 alignés = T accepté (avant
  refusé), le mur qui arrive s'arrête sur la FACE ; bout libre qui s'arrête avant / entre dans / traverse un autre mur coupé sur la bonne
  face (angle L croisé : l'un va à la face extérieure, l'autre à la face intérieure ; dépassement ≤ 50 cm) ; sols et plafonds CALÉS sur
  les faces des murs (côté parallèle à 2°, à ≤ 10 cm, longeant la face sur ≥ 90 %) ; bouche-trous en fin de calculer_briques.
- `moteur/controle_maquette.py` 0.1.0 (nouveau) : grille de 4 mm vue de dessus ; trous du sol et du plafond, sols superposés, murs
  superposés ; `jours_a_boucher` : fente (épaisseur = plus grand cercle inscrit ≤ 6 cm) bouchée par le sol de la pièce voisine ;
  morceau de pièce ≤ 1 m² complété ; vide enclos sans pièce ≤ 2 m² rempli comme un mur (gaine) ; plus grand = JAMAIS bouché.
- `moteur/preparer_verification.py` : doutes `zone_sans_piece` (fort, ≥ 0,25 m² : pièce oubliée, terrasse, partie commune ?) et
  `vide_rempli` (faible, ≥ 0,5 m² : WC ou placard oublié ?).
- `moteur/traduire_claude.py` : zone partagée par plusieurs pièces à contours DÉCOUPÉE entre elles (chaque point à la pièce dont le
  contour le contient, sinon la plus proche) ; jamais deux pièces au même endroit ; contour à angles droits gardé seulement s'il épouse
  la zone (≤ 3 % ET ≤ 1,5 px en moyenne le long du bord ; avant : comparaison des seules surfaces).
- `outils/lecture_claude/fiche_depuis_verite.py` : faux murs des vérités (< 5 cm, couverts à ≥ 85 % par des ouvertures) retirés, chaque
  pièce reçoit son contour.
- `moteur/blender/poser_briques.py` : chaque mur monte de 0,1 mm de plus que le précédent (cycle de 10, ≤ 0,9 mm) : deux murs qui se
  croisent en X (fr-021, murs de 80 cm) n'ont plus leurs dessus au même niveau (plus de noir) ; invisible.
Mesures sur les 20 vérités Fable (`pc/b1/mesurer_jours.py`, résultats `..\atelya\b1\jours.json`) : avant 3 à 163 trous par plan et 2
plans refusés par la 3D (fr-023, fr-034) ; après : 20/20 construits, 15/20 SANS AUCUN TROU, les 5 autres (fr-022, 023, 034, 035, 036,
037 : grandes zones sans pièce de 1,7 à 67 m²) signalées ; sols superposés ≤ 0,04 m² (bruit de mesure : ~0,004 m² par mètre de frontière
commune) ; murs superposés de 7,5 → 2,2 m² (fr-021, croix de murs épais, rendue propre par le décalage de hauteur) et ≤ 0,3 m² ailleurs.
Rendus Blender vérifiés à l'œil : fr-031 (avant/après : `..\atelya\b1\fr-031-*-avant-apres.png`), fr-030, fr-021, fr-024, fr-026,
fr-038 : plus de filet bleu, plus de filet de lumière, plus de carrés noirs, cuisine ouverte visible. Limites : quelques fins traits
sombres le long de murs extérieurs de fr-021 (marches entre morceaux de mur d'épaisseurs différentes ? non vérifié) ; placards devenus
des niches ouvertes (portes de placard à ajouter en B2/B4). Tests : `tests/test_controle_maquette.py` (6), 6 de plus dans
`test_geometrie.py`, 1 de plus dans `test_traduire_claude.py`.

**Après B1 (08/11/2026), discussion sur B2** : NT rappelle qu'Atelya produit TOUTE la maquette 3D (maquette.blend), pas seulement des
images ; produit livré = visite libre (Unreal plus tard), cinématique, photos fixes, tous tirés de la même maquette. B2 renommée
« maquette 3D réaliste », en deux temps : (1) dans la maquette (plinthes, portes de placard, encadrements, bibliothèque de vraies
matières CC0, lumière du jour) puis (2) photos du client → matières de chaque pièce (choix dans la bibliothèque, corrigé à l'écran de
vérification). NT : « il faudrait des photos de bonne qualité que le client délivre » → oui, c'est la brique photos (décision du 22/10 :
le plan donne la forme, les photos l'apparence). PREMIER JEU D'ESSAI PLAN + PHOTOS reçu de NT le 08/11/2026 « avec les accords » :
`..\atelya\photos-clients\app-001\` (4 pièces 124 m², HSP 3 m ; captures d'écran d'une annonce : plan basse définition sans cotes,
12 photos ~1206 × 800 px avec marques ; LISEZMOI.txt = pièces et matières vues). À demander si possible : les originaux en pleine
définition, sans marques. Ces photos de photographe servent aussi de RÉFÉRENCE de qualité pour les rendus.


**B2 proposée à NT (08/11/2026, en attente de son accord)** : temps 1 en 4 sous-étapes, une à la fois, chacune montrée en images
avant/après sur fr-031 + 2 autres vérités, contrôle des trous inchangé : B2-1 plinthes et encadrements (portes, appuis de fenêtre) ;
B2-2 portes de placard (les niches ouvertes de B1) ; B2-3 bibliothèque de vraies matières (13 Poly Haven + 1 ambientCG en 2K, 3 cartes
chacune : couleur, relief, brillance ; ~106 Mo ; dossier proposé `..\atelya\bibliotheque\matieres\` hors Git) + point de Hongrie et
carreaux de ciment fabriqués par calcul ; B2-4 lumière du jour (ciel physique intégré à Blender, plafonniers éteints le jour, réglage
d'exposition « comme un photographe »). Temps 2 (après) : lecture d'app-001 faite à la main comme une vérité, puis photos → matières.
Licences relues : voir audit-technologique-2026-10-31.md (fin).
**Accord NT (08/11/2026, écrit) : « télécharger toutes les matières »** → les 14 matières proposées sont téléchargées par
`outils/bibliotheque/telecharger_matieres.py` dans `..\atelya\bibliotheque\matieres\` (hors Git) : 14 dossiers × 3 images 2048 × 2048
(couleur.jpg, relief.jpg = normale OpenGL, brillance.jpg = rugosité), 98,6 Mo, sommes de contrôle Poly Haven vérifiées, `matieres.json`
(source, auteurs, taille réelle couverte par une image en m) et `CREDITS.txt`. Vu à l'œil : 4 fiches ne ressemblaient pas à leur nom →
renommées : floor_tiles_06 = `damier_pierre`, marble_01 = `pierre_beige`, square_tiled_wall = `mosaique_rayee` (brun/gris), Tiles036 =
`faience_blanche` (carrés, pas métro) ; white_plaster_02 est gris taché → servira pour le grain, couleur de peinture posée par Atelya.
Manquent encore : vraie faïence métro, marbre blanc (à ajouter si besoin, même licence). NT parle aussi de « télécharger le GitHub
envoyé tout à l'heure » (meubles : ABO ou Sand3D ?) → question posée, rien téléchargé. Tailles : ABO officiel abo-3dmodels.tar 154 Go
en un bloc ; réenvoi codepawl/abo-glb 43,1 Go (fichiers séparés) ; Sand3D (code) 24 Mo, Apache 2.0, écarté par NT le 08/11. Disque D : 900 Go libres.

**B2-1 plinthes et encadrements (08/11/2026, « Oui » de NT ; corniches : plus tard)** — `moteur/habillage.py` 0.3 (règle FIXE, même
partout ; NT a demandé si c'était d'après les photos : non, règle fixe d'abord, les photos ajusteront au temps 2 avec correction à
l'écran) : PLINTHES 10 cm × 1,5 cm posées sur le sol calé de chaque pièce, seulement là où un mur existe au niveau du sol 2 cm derrière
le bord (rien devant porte / porte-fenêtre / passage ouvert), arrêtées à 1 mm du chambranle, biseau dans les angles (rentrants et
sortants), bout droit sinon ; CHAMBRANLE 6,5 cm × 2 cm sur les deux faces autour de chaque porte (3 morceaux qui ne se recouvrent pas,
coupés au bout du mur et sous le plafond) ; FENÊTRES : cadre à 5 cm derrière la face intérieure (côté pièce trouvé comme pour la porte
d'entrée ; au milieu si pièce des deux côtés), APPUI 2,5 cm sous les fenêtres d'allège ≥ 30 cm (pas sous les portes-fenêtres), qui
dépasse de 3 cm. Tests : 3 de plus dans `test_habillage.py` (aire exacte de l'anneau de plinthes = biseaux sans trou ni recouvrement).
Géométrie (calculer_briques) INCHANGÉE → contrôle des trous de B1 identique. Rendus avant/après rapprochés (porte, fenêtre, angle) sur
fr-031, fr-030, fr-021 : `..\atelya\b2\<plan>-avant-apres.png`. fr-021 : 88 morceaux de plinthes (153 m), 84 morceaux de chambranle,
40 d'appui. Limites connues : poteaux isolés au milieu d'une pièce sans plinthe autour ; 3 petits côtés (≤ 1,3 m) de fr-021 où le mur
est à plus de 2 cm du bord de la pièce → pas de plinthe ; plinthe arrêtée net au bout d'un mur qui borde un passage ouvert (pas de
retour autour du bout).

**NT, 08/11/2026 (après B2-1)** : les finitions ne doivent PAS être posées partout par une règle fixe : Atelya doit décider
**logement par logement** s'il y en a ou pas (« s'il voit qu'il y en a ou qu'il n'y en a pas »). Proposé : chaque finition
(plinthes, et ensuite placards, corniches…) devient un réglage PAR PIÈCE dans le logement (avec / sans / plinthe carrelée,
statut « estimé » tant que rien ne l'a vu), visible et modifiable à l'écran de vérification ; au temps 2, Atelya le remplit
lui-même d'après les photos du client (statut « vu sur photo »). En attente du « oui » de NT avant de le faire (avant B2-2).

**Plinthes pièce par pièce (08/11/2026, « Oui » de NT)** — format : champ facultatif `plinthes` de chaque pièce
(`moteur/logement.py`, `Plinthes` : choix bois / carrelage / aucune + statut : « ajoute » = règle par défaut, personne ne l'a vu ;
« estime » = vu par Atelya sur une photo (source photo_xx, temps 2) ; « mesure » = choisi à l'écran (source verification)). Sans
champ : règle par défaut `habillage.plinthes_par_defaut` (carrelage dans une pièce carrelée d'après son nom, bois ailleurs).
`habillage` 0.4 : « aucune » → rien ; « carrelage » → 8 cm × 1 cm, matière du sol (carrelage si le sol est en parquet).
`preparer_verification` 0.3.0 : le fichier de l'écran porte la règle par défaut écrite (`completer_plinthes`, confiance 0,5) →
l'écran (fiche de la pièce) montre la liste « Plinthes » + d'où vient le choix, et `reglerPlinthes` (calculs-verif.js) enregistre le
choix de la personne. Écran testé dans Chrome sans fenêtre (Node absent du PC) : 9/9. Rendus : `..\atelya\b2\fr-031-plinthes-par-piece.png`
(séjour bois / carrelage / aucune, salle d'eau par défaut), capture `..\atelya\b2\ecran-plinthes.png`. Même principe prévu pour les
portes de placard (B2-2) et les corniches.

**B2-2 portes de placard (08/11/2026, « Oui » de NT)** — même principe que les plinthes : champ `placard` de la pièce
(`PortesPlacard` : coulissantes / battantes / aucune + statut ajoute / estime / mesure). Un placard = nom placard / rangement /
dressing / penderie ET ≤ 4 m² (`habillage.est_placard` ; un dressing plus grand = une pièce, porte ordinaire : fr-038 9 et 16 m²),
ou choix écrit. Règle par défaut : battantes sous 1 m de façade, coulissantes au-delà. `habillage` 0.5 : (1) façade OUVERTE (bord du
sol du placard sans mur derrière, ≥ 40 cm, avec une autre pièce devant) → portes du sol au plafond juste derrière la ligne
(coulissantes : panneaux ≤ 1 m, deux au moins, recouvrement 3 cm, deux plans, rails haut et bas, baguettes de prise ; battantes :
portes ≤ 60 cm, fente 3 mm, poignées près des jonctions) ; (2) façade dessinée comme une PORTE dans un mur → le battant et les
poignées de la porte sont remplacés par des portes de placard (cadre et chambranles gardés). Corrigé au passage : deux portes
proches se partagent le trumeau (`_place_de_chaque_cote`) ; avant, leurs chambranles se recouvraient → filet noir (fr-031).
Vrais plans : fr-031 (façade 3,04 m → 4 coulissants ; porte 1,57 m → 2), fr-021 (façade 2,17 m → 3 ; porte 0,62 → 1 battante),
fr-030 : placards fermés de tous côtés sur la lecture (aucun accès, défaut de la vérité) → rien. Écran : liste « Portes du placard »
dans la fiche d'un placard seulement (`estPlacard`, `reglerPlacard`), testée dans Chrome 7/7 ; préparateur : `completer_finitions`.
Rendus : `..\atelya\b2\placards-b2-2.png`. Limite vue : petites lignes au sol à la jonction des parquets de deux pièces (fr-021, défaut
d'avant B2-2, à revoir avec les vraies matières B2-3).

**B2-3 vraies matières (08/11/2026, « Oui » de NT)** — catalogue `moteur/matieres.py` (9 sols : parquet chêne lames droites,
bâtons rompus, point de Hongrie (calculé avec le chêne clair), stratifié, carrelage beige (photo en biais tournée de 45° :
`ROTATION_PHOTO`), carreaux de ciment (calculés : cercles aux coins, étoile, losange rouge, 20 cm), tomettes, damier de pierre,
dalles de pierre beige). ÉCARTÉ après essai à l'œil : granito (la photo terrazzo_tiles brune ressemble à du liège ou de la moquette :
à remplacer par un vrai granito gris). Format : champ `sol` de la pièce (`Sol` : matiere + statut). Défaut : parquet chêne / carrelage
beige selon le nom ; plinthes supposées carrelées si le sol est carrelé (matière du sol ; sous des carreaux de ciment, plinthe unie) ;
renommer une pièce à l'écran oublie ce qu'Atelya avait SUPPOSÉ (statut ajoute) d'après l'ancien nom. Blender (`moteur/blender/materiaux.py`) :
`Materiaux` créés à la demande, photos de la bibliothèque (couleur sRGB, brillance et relief non-couleur, normale OpenGL) en projection
boîte à la taille réelle (matieres.json), toutes dans le même sens (`habillage.orientation_sols` = sens des murs les plus longs, le même
dans tout le logement), murs et plafonds = peinture + grain de l'enduit (rugosité 0,8-0,95, relief 0,25), photos RANGÉES dans le .blend
(fr-031 : 19 Mo). Bibliothèque trouvée par `construire.trouver_matieres` (variable ATELYA_MATIERES, sinon ..\atelya\bibliotheque\matieres) ;
sans elle (Mac, tests) : anciens parquet / carrelage calculés. CORRIGÉ : les fines lignes au sol entre deux pièces (fr-021) = fentes entre
sols (on voyait le vide) + bandes de raccord B1 posées à la même hauteur que les sols ; → copie de chaque sol 1 mm plus bas élargie de 2 cm
(`sous_sols`, même matière : le dessin continue) et bandes de raccord à -0,5 mm : lignes disparues. Encadrement d'une porte voisine d'une
fenêtre : peut couvrir tout le trumeau (seules deux portes se le partagent). Écran : liste « Sol » dans la fiche de chaque pièce (Chrome 6/6) ;
un test Python vérifie que l'écran et le moteur ont la même liste. Rendus : `..\atelya\b2\sols-b2-3.png` (les 9 sols),
`..\atelya\b2\fr-031-sejour-avant-apres-b2.png`. Reste vu : fin trait sombre dans le tableau d'une porte-fenêtre de fr-031 (existait
avant, ombre de l'embrasure : à revoir avec la lumière B2-4) ; faïence murale des salles d'eau pas encore posée (les murs sont partagés
entre deux pièces : il faudra peindre chaque face) ; portes de placard toujours blanches.

**Parquets en plus (08/11/2026, demande de NT : « trouver d'autres parquets très réalistes », l'actuel lui semble un peu foncé)** :
86 parquets comparés en vignettes (64 ambientCG, 22 Poly Haven, tous CC0, rien téléchargé à part les vignettes). 15 PROPOSÉS, en
attente du « oui » de NT pour le téléchargement (~245 Mo, 2K) : ambientCG WoodFloor051 (chêne clair moderne), 062 (chêne beige), 056
(chêne grisé), 040 (chêne à nœuds, larges lames), 064 (lames foncées), 052 et 057 (VRAIS points de Hongrie), 053 et 058 (bâtons rompus
clairs), 055 et 060 (parquet VERSAILLES), 069 (mosaïque des années 60-70) ; Poly Haven laminate_floor_03, oak_wood_planks,
old_wooden_floor_03 (photos). Les ambientCG sont « PBRProcedural » (fabriqués à partir de photos de bois, pas photographiés d'un bloc) :
on garde seulement ceux qui passent l'essai de rendu à l'œil, comme pour le granito. Planche : `..\atelya\b2\parquets-proposes.png`.
**Suite (08/11/2026 soir, « Oui » de NT + « adapte un parquet aux photos »)** : les 15 parquets sont téléchargés
(`telecharger_matieres.py` étendu ; bibliothèque : 29 matières, 242 Mo). Essai dans le séjour entier de fr-031
(`..\atelya\b2\parquets-essai.png`) : GARDÉS 10 (chêne clair moderne, chêne grisé, chêne à nœuds, chêne clair larges lames, chêne
naturel, vieux parquet, 2 points de Hongrie, 2 bâtons rompus) → catalogue de 19 sols ; ÉCARTÉS du choix (gardés dans la bibliothèque) :
chêne beige et lames foncées (unis, plastique), Versailles clair et chaud (motif trop petit, rosé), mosaïque (terne). Mesure sur les
photos d'app-001 (`moteur/teinte_photo.py`, mur blanc = étalon) : le parquet d'app-001 renvoie ~(0,52 ; 0,24 ; 0,10) de la lumière,
notre parquet par défaut ~(0,22 ; 0,12 ; 0,06) → 2,4 fois plus sombre : NT avait raison. Nouveau : `teinte` du sol de la pièce
(3 multiplicateurs, nom de matériau « matiere~r,g,b »). Essai fr-031 façon app-001 (`..\atelya\b2\app001-parquet.png`) : le dessin et
la clarté suivent la photo, mais la couleur sort ROSÉE au rendu : l'éclairage actuel (plafonniers blanc chaud + ciel uni) teinte
tout ; à régler avec B2-4 (lumière du jour) avant de juger la couleur. Chevrons d'app-001 plus grands que ceux d'ambientCG (colonnes
~40 cm contre ~30). NT : « ça ressemble plus au 15 » (n° 15 de la planche proposée = mosaïque ?) → question posée.

**B2-4 lumière du jour (09/11/2026 nuit, « tu peux commencer la lumière du jour » de NT ; il retire sa remarque sur le « 15 »)** —
`habillage` 0.7 + `moteur/blender/poser_briques.py` + `rendre.py` : (1) le soleil n'est plus une lampe : ciel physique de Blender
(`ShaderNodeTexSky`, MULTIPLE_SCATTERING, disque solaire) dans la direction du soleil du plan (convention vérifiée par l'ombre d'un poteau :
rotation 0 = soleil vers +y, 90° = vers +x ; `sun_direction` ne vaut rien pour ce type) ; sous l'horizon, vu par la caméra, un sol gris
éclairé par le ciel (sinon fond NOIR en vue de dessus) ; (2) un PORTAIL (lampe `is_portal`) sur la face extérieure de chaque fenêtre /
porte-fenêtre qui donne dehors (`habillage.portails`) ; (3) plafonniers gardés mais éteints de jour (`hide_render`, propriété « nuit ») ;
(4) réglage « de photographe » au rendu (`reglage_de_photographe`) : photo d'essai (16 passes, 1/5 de la taille) où tout sauf murs et
plafonds est découpé (`is_holdout`) → exposition = médiane des murs à 0,55 ; balance des blancs = couleur des murs ramenée à 70 % vers le
blanc (courbes de couleur, `white_level`) : le reflet orangé du parquet ne teinte plus les murs en rose ; (5) 512 passes en qualité finale
(128 marbrait les murs ; ~1 min 30 par vue intérieure sur la RTX 2070), lucioles bornées (`sample_clamp_indirect` 10). Parquet par
défaut des pièces à vivre → `chene_naturel_photo` (NT : l'ancien était trop foncé). Rendus : `..\atelya\b2\b2-4-lumiere.png` (avant B2 /
après, défaut / adapté à la photo d'app-001 / la photo). Le soleil reste celui inventé du plan (azimut 200°, hauteur 50°) : le VRAI soleil
(orientation du logement, date, heure) = étape B3, règle 20 (« soleil inventé non »).

**Fin du temps 1 de B2 (09/11/2026)** : NT d'accord pour faire le TEMPS 2 (app-001) dans une NOUVELLE conversation. Note honnête
~71/100 prêt client (fabriqués ~93, vrais plans ~53, inchangés). Limites connues à reprendre : soleil encore inventé (B3) ; chevrons du
parquet adapté plus petits que ceux d'app-001 (prévoir une échelle du motif par pièce) ; ~1 min 30 par vue de pièce ; pas de faïence
murale ; portes de placard toujours blanches ; fin trait sombre dans l'embrasure d'une porte-fenêtre de fr-031. Le téléchargement des
meubles ABO tourne dans cette conversation : s'il s'arrête (fermeture de VS Code, veille), relancer la même commande (il reprend).

**B2 temps 2, étape 1 : vérité d'app-001 (09/11/2026, nouvelle conversation)** — plan seul découpé de la capture :
`..\atelya\photos-clients\app-001\verite\plan.png` (1100 × 670 px) ; photos découpées sans l'écran du téléphone :
`app-001\photos\photo-01..12.png` + `planche.png`. Saisie à la main (`faire_verite.py`) : 32 murs, 24 ouvertures, 12 pièces ;
copie dans le dépôt `verites/app-001/`. ÉCHELLE (plan sans cotes) : 49,4 px/m = la somme des 12 pièces vaut les 124 m² annoncés
(131,35 m² à 48 px/m) ; contrôle indépendant : les passages de porte font 0,61-0,71 m = portes standard de 63 et 73 cm (et non
~80 cm comme supposé avant) ; porte d'entrée double 1,23 m ; emprise 17,6 × 11,7 m. Pièces : séjour / salle à manger 46,0 m², cuisine
ouverte 16,0, entrée 3,2, chambre 1 18,4 (placard le long du mur ouest, photo 08), chambre 2 19,2 (enfant, photos 10-11), salle de
bains 4,9 (baignoire + double vasque, photo 12), salle d'eau 3,2 (douche, photo 09), WC 1,1, WC 2 1,9, dégagement 7,4, rangement 2,4,
placard 0,3. Palier, escalier, ascenseur, courettes : non tracés. Incertitudes écrites dans la saisie (`incertain`) : HSP 2,80 dans
salle de bains / dégagement / cuisine (format à une seule hauteur → 3 m), fenêtres sud posées en portes-fenêtres (2,1 m de large au
dessin), accès de la salle d'eau supposé par la chambre 1 (mur plus fin), faux murs cuisine/séjour (y 222) et entrée/séjour (x 820),
porte vers la courette (photo 07), usage du « rangement » inconnu + vide fermé (gaine ?), caisson bleu de la télé = meuble.
Contrôle : `verite\controle-zoom.png`. En attente de la validation de NT avant la 3D (étape 2).
**Correction demandée par NT (09/11/2026) : « tu as inventé des portes, relis bien le plan »** : la 1re lecture séparait cuisine /
séjour / entrée par des faux murs avec un passage de toute la largeur (convention des vérités, retirée plus loin par
`fiche_depuis_verite`, mais dessinée en VERT = porte sur l'image de contrôle) et posait une porte vers la courette d'après la photo 07.
Le plan ne montre RIEN de tout cela. RÈGLE (NT) : ne JAMAIS ajouter une limite, une porte ou une cloison absente du plan, même pour
séparer des sols ; un espace ouvert = UNE pièce ; le plan fait foi, la photo ne crée pas d'élément. Relecture zone par zone (zooms ×5,
pixels) : trait fin y 222 + pointillé y 241 = bord du plafond plus bas de la cuisine (HSP 2,80, poutre visible photo 02) ; traits fins
x 370 et x 407 du rangement = meubles (le « vide fermé » n'existait pas) ; triangle bleu du WC = lave-mains d'angle ; porte
cuisine ↔ sas confirmée par les pixels (trou du mur x 504 de y 177 à 211, battant dessiné ouvert). Vérité corrigée : 30 murs,
21 ouvertures, 10 pièces, 49,8 px/m (124 m²) : séjour / salle à manger / cuisine ouverte / entrée 65,2 m², chambre 1 18,1,
chambre 2 18,9, dégagement 7,3, salle de bains 4,8, rangement 3,3, salle d'eau 3,1, WC 2 1,9, WC 1,1, placard 0,3. Sols différents
dans l'espace ouvert (carreaux de ciment, lames droites, chevrons) : à proposer à NT à l'étape des sols, sans mur inventé.
**Vérité validée par NT (« Je valide », 09/11/2026).** Étape 2 (3D par Atelya) : `fiche_depuis_verite` → `traduire_fiche traduire`
(`..\atelya\lectures-claude\app-001\`, plan copié en `app-001.png` pour nommer la sortie) → `python -m moteur.construire` →
`app-001\3d\` (1 min 56, 0 trou au sol et au plafond, murs superposés 0,18 m²). Images : `..\atelya\b2\app-001\etape2-*.png`.
CORRIGÉ au passage : la HSP écrite « HSP 3m » (nombre entier) n'était pas lue → 2,50 m par défaut ; `lecture_cotes.FORME_HSP`
accepte l'entier, et plusieurs HSP différentes → la plus fréquente, à égalité la plus haute (faux plafonds plus bas) ; app-001 → 3,00 m.
`fiche_depuis_verite` reprend les textes de la saisie (clé `textes` : [texte, genre, x0, y0, x1, y1]) et la source d'échelle
(`source_echelle_claude`). DÉFAUT TROUVÉ (pas encore corrigé, proposé à NT) : `traduire_claude` dessine chaque mur prolongé de
½ épaisseur + 3 px à ses bouts, avec des bouts RONDS (cv2.line épais) → à chaque angle SAILLANT le bâti déborde de ~25 cm dans la
pièce → contour du séjour arrondi autour de l'angle (46 points au lieu des 12 de la fiche), sol et plafond arrêtés avant le mur,
bouché ensuite par `jours_a_boucher` (19 bouche-trous sur app-001) → filet de lumière en haut de l'angle + trace sur le plafond
(`etape2-defaut-angle-plafond.png`). Correction proposée : bouts carrés et, quand le bout touche un autre mur, prolonger seulement
de la ½ épaisseur de cet autre mur ; à mesurer sur les 20 vérités (`pc/b1/mesurer_jours.py`) avant / après.
**Défaut des angles CORRIGÉ (accord NT « oui t'as raison », 09/11/2026) : traducteur de la lecture de Claude 0.2.1**
(`moteur/traduire_claude._bati` + `_coupe_du_bout`). Les murs sont dessinés en bandes à bouts COUPÉS DROIT : un bout qui touche un
autre mur (angle, té, même décalé de 3 px par le recalage) s'arrête sur la FACE LOINTAINE de cet autre mur (angle rempli, rien ne
dépasse dans la pièce) ; un bout près d'un autre mur sans le croiser (courbe faite de morceaux décalés d'un pixel, fr-026) est
prolongé de ½ épaisseur + 3 px ; un bout LIBRE (mur qui s'arrête dans la pièce) est coupé net (fr-022 : un mur de 98 cm prolongé de
50 cm laissait un vide). Les côtés des murs restent dessinés au pixel près comme avant (même largeur que cv2.line) : origine et
surfaces inchangées. En plus : le contour à angles droits d'une pièce est refusé s'il mord sur une pièce voisine (plus de 0,1 px par
pixel de bord, `DEBORD_VOISINES_PX`) : fr-022, séjour partagé en deux, 0,18 m² de sols superposés (rendus noirs). Mesure sur les
20 vérités de Fable + app-001 (script de mesure dans le dossier temporaire, chaîne de `pc/b1/mesurer_jours.py`) : bouche-trous
607 → 295 morceaux, 48,4 → 20,9 m² ; trous 11 → 10 (aucun plan avec un trou de plus) ; sols superposés 0,072 → 0,027 m² ; points
des contours de pièces divisés par ~2 ; pièces un peu plus grandes (elles vont jusqu'aux murs ; app-001 120,7 → 121,7 m² pour 124
annoncés). App-001 : bouche-trous 19 → 8 au plafond, plus de filet ni de trace à l'angle saillant
(`..\atelya\b2\app-001\angle-avant-apres.png`). RESTE (autre cause, dans la 3D) : un petit trait clair au raccord du mur du poteau
avec la façade EN BIAIS (≈ 10,5 ; 1,7 m), raccord de deux murs de travers dans `moteur/geometrie.py`. 2 tests ajoutés.
**Étape 3 (sols d'après les photos), proposition puis correction de NT (09/11/2026).** Format : UN sol par pièce aujourd'hui ;
proposé : des « zones de sol » dans une pièce (polygone + sol, statut estimé « vu sur photo », sans mur, sans trait, sans plinthe,
corrigeables à l'écran), découpe avec Shapely (BSD-3, déjà installé partout comme dépendance de RapidOCR : rien à installer).
Photos → sols : séjour / salle à manger = point de Hongrie (01-04) ; entrée + passage = lames droites étroites (07) ; chambres =
lames droites étroites (08, 10, 11) ; salle de bains = petits carreaux blancs ~10 cm (12) ; carreaux de ciment « cubes » jaune / gris
/ blanc dans la cuisine (05, 06) ; salle d'eau, WC, dégagement, rangement, placard : sol jamais vu (supposé). CORRECTION NT : dans
l'espace ouvert il n'y a que DEUX sols entre séjour et cuisine : le point de Hongrie s'avance jusqu'à l'îlot (chaises et « table »
comprises) ; APRÈS l'îlot, côté évier / meubles de cuisine, les carreaux de ciment ; la limite est PARALLÈLE aux meubles de
cuisine (et non sur le côté, au milieu de l'îlot, comme proposé d'abord ; pas de lames dans la cuisine). Croquis :
`..\atelya\b2\app-001\etape3-proposition-sols.png` (limite au milieu de l'îlot, y ≈ 147 px du plan).
**Étape 3, suite (09/11/2026).** NT : l'entrée et le passage restent en lames droites jusqu'à la cuisine. FAIT dans Atelya : format
`Piece.zones_sol` (ZoneSol : contour CONVEXE + sol ; `logement.verifier_coherence`), `Sol.echelle` (taille du motif 0,3-3 ; nom de
matériau « matiere@1.13~r,g,b », `matieres.echelle_du_nom`), briques `zone_sol__<pièce>__<n>` découpées sur le contour calé de la pièce
(`geometrie._couper_par_convexe`, Sutherland-Hodgman, vérifié contre Shapely sur 300 rectangles) et posées 0,5 mm au-dessus du sol
(`ZONE_SOL_Z`), matériau de la zone (`habillage.materiau_de`) ; deux carrelages DESSINÉS par Atelya (`outils/bibliotheque/dessiner_carreaux.py`,
rien de téléchargé) : `carreaux_cubes` (losanges 11,5 cm en cubes, blanc / gris clair / gris / moutarde, joint gris foncé ; 1,593 ×
1,725 m) et `petits_carreaux_clairs` (10 cm) ; images non carrées dans Blender (`taille_image_m` [l, h]) ; outil
`outils/habillage/poser_sols.py` + choix d'app-001 `verites/app-001/sols.json` (= VÉRITÉ DES SOLS d'app-001, faite À LA MAIN par Claude :
NT a fait remarquer que ce travail n'est pas fait par Atelya → prochaine étape proposée : la BRIQUE PHOTOS, notée contre cette vérité).
Choix : séjour point de Hongrie ×1,13 (teinte mesurée sur la photo 04 ; la 03 est faussée par le reflet des fenêtres), zone carreaux en
cubes devant la cuisine (y ≥ 9,3 m), zone lames `chene_clair_photo` ×0,32 (lames ~7 cm) x ≥ 13,54 m (entrée + passage), chambres
`chene_clair_photo` ×0,32, salle de bains petits carreaux ; `vieux_parquet` écarté (trop foncé : teinte hors bornes). 3D :
`..\atelya\lectures-claude\app-001\3d-sols\` (0 trou, 0 sol superposé).
DÉFAUT DE COULEUR AU RENDU trouvé (touche tous les clients) : parquet miel sur la photo (161, 106, 57), rosé-gris au rendu (177, 158,
152) malgré la bonne teinte. Causes mesurées (essais dans le dossier temporaire, vue séjour) : (1) le parquet est presque CIRÉ (carte de
brillance du chêne clair) et renvoie la lumière blanche/bleue du ciel vu en biais ; (2) AgX (réglage de pellicule par défaut de
Blender 5, jamais choisi par nos scripts) délave les couleurs ; « Standard » ou « Khronos PBR Neutral » gardent la couleur mais rendent les
murs cyan d'un côté et orangés de l'autre (la balance des blancs sur la moyenne des murs ne peut pas neutraliser une pièce éclairée à
la fois par le ciel et par le parquet ensoleillé ; un ciel plus brumeux n'y change rien). SOLUTION retenue à l'essai : garder AgX (murs
blancs), parquet SATINÉ (rugosité 0,7, reflet 0,1) et TEINTE RÉGLÉE AU RENDU (boucle : petite image, sol mesuré contre le mur blanc,
comparé au rapport sol / mur de la photo, teinte corrigée ; bornes de teinte abaissées à 0,02) : en 3 tours le sol passe à
(159, 108, 81), murs blancs (207, 214, 214). Image : `..\atelya\b2\app-001\etape3-couleur-essais.png`. Reste : bleu un peu haut (81
contre 57), chevrons moins contrastés que la photo (nuance par lame à augmenter). À rendre automatique dans Atelya (accord NT demandé).
**DEMANDE NT (09/11/2026) : « je veux qu'Atelya ait plein de types d'éclairage, et qu'on puisse les changer à l'écran de
vérification ».** Aujourd'hui : un seul éclairage (ciel physique + soleil inventé du plan, azimut 200° / hauteur 50°, portails aux
fenêtres, plafonniers éteints le jour, réglage « de photographe » au rendu). Proposition faite à NT (en attente de sa réponse) : des
AMBIANCES au niveau du logement (jour ensoleillé, jour voilé, fin de journée, soirée lampes allumées, nuit) et des LUMINAIRES par
pièce (plafonnier, suspension, spots, appliques, lampe d'appoint, ruban sous meubles de cuisine ; blanc chaud / neutre), supposés selon
la pièce puis modifiables à l'écran ; règle 20 respectée (moment flatteur oui, soleil inventé non : le soleil suit l'orientation réelle,
étape B3) ; la teinte des sols se règle UNE fois dans l'ambiance de référence (jour, comme les photos d'annonce), les autres ambiances
sont calculées physiquement à partir de là.
**PRÉCISION NT (09/11/2026) : PAS à l'écran de vérification** : il veut que la MAQUETTE BLENDER d'Atelya contienne PLUSIEURS éclairages tout prêts, qu'il change lui-même DANS BLENDER. Proposé : une SCÈNE Blender par éclairage (copies liées : murs, sols, meubles partagés ; chaque scène a son ciel, ses lampes et son réglage de photographe) : jour ensoleillé, jour voilé, fin de journée, soirée lampes allumées, nuit ; on change d'éclairage par le menu des scènes. Ordre : d'abord finir le défaut de couleur, puis les éclairages.
**Défaut de couleur CORRIGÉ dans Atelya (09/11/2026, accord NT « on corrige d'abord le défaut de couleur »).** (1) Parquets
SATINÉS (`materiaux.RUGOSITE_BOIS` 0,6-0,85 à partir de la brillance de la photo, `REFLET_BOIS` 0,15 ; `_sorte` : tout nom inconnu
= bois, les parquets du temps 1 n'étaient pas dans `SORTES`) ; nuance par lame du point de Hongrie ±12 % → ±20 %. (2) TEINTE RÉGLÉE AU
RENDU, automatique : `Sol.couleur_photo` (part de lumière du sol sur la photo, mur blanc = étalon, posée par `poser_sols`) ;
`habillage.reglages_teinte` (matériau, cible, caméra de réglage DANS la pièce à ~3,5 m du sol visé, 16 mm) ; `moteur/blender/
regler_teintes.py` lancé par `construire` après `poser_briques` : masques du sol et des murs (objets « découpés »), même réglage de
photographe que l'image finale, sol mesuré contre les murs bien éclairés (50e-90e centile), teinte corrigée, 3 tours, maquette
enregistrée, `reglages_teinte.json` ; bornes de teinte 0,02-4. AgX GARDÉ (murs blancs ; « Standard » / « PBR Neutral » rendaient les
murs cyan / orangés). Scripts Blender : `main()` seulement si lancés par Blender (`if __name__ == "__main__"`) — avant, un import
relançait tout le rendu. PIÈGE corrigé : `reglage_de_photographe` impose RGBA pour son essai (une image sans transparence comptait tout
comme du mur → image brûlée). App-001 : séjour (146, 107, 92) contre photos (150, 99, 72) / (161, 106, 57), murs (212, 216, 216) ;
construction 5 min 10 (dont ~2 min de réglage). Images : `..\atelya\b2\app-001\etape3-sejour.png`, `etape3-vue-dessus.png`.
Tests : `tests/test_zones_sol.py` (6).
**Retour NT sur l'étape 3 (09/11/2026)** : (1) la comparaison était TROMPEUSE : la vue 3D (caméra automatique d'Atelya dans un coin du
séjour) a été mise à côté des photos 04 (salle à manger) et 02 (séjour) comme si c'était la même vue → ne plus jamais comparer une vue
3D à une photo prise d'ailleurs ; c'est l'étape 4 (caméras au même endroit que chaque photo). (2) « La jonction des murs est trop
brute, sur le plan et les photos c'est plus smooth » : sur les photos 07, 08, 11, une CORNICHE moulurée fait le tour du plafond
(gorge à gradins de ~10-15 cm) ; en 3D, murs et plafond se coupent à angle vif. Proposé : corniches choisies pièce par pièce (comme
plinthes et sols) + arêtes de murs légèrement adoucies ; image `..\atelya\b2\app-001\corniches-photos.png`. En attente de NT.
**Corniches FAITES (09/11/2026, accord NT « oui ça marche »).** `Piece.corniche` (Corniche : « aucune » / « simple » / « moulure »,
statut comme les plinthes ; défaut `CORNICHE_PAR_DEFAUT` = aucune) ; `habillage.corniches` : bandes de plâtre en gradins le long de
chaque côté du plafond où un mur monte jusqu'au plafond (`PROFILS_CORNICHE` : moulure = 4 gradins, avancée 2 / 4,5 / 7,5 / 10 cm,
hauteur 15 / 11 / 6,5 / 3 cm ; simple = 3 × 8 cm), biseaux dans les angles comme les plinthes (`_bandes`), rangées avec les PLAFONDS
(matériau plafond_blanc, cachées sur la vue de dessus). PIÈGE corrigé : le contour lu d'une pièce s'arrête parfois à 3 cm d'un mur fin
(app-001, mur de 8 cm de l'entrée) → sondes à 2, 5 et 9 cm (`SONDES_CORNICHE`), trous < 12 cm refermés, morceau à < 6 cm d'un angle
prolongé jusqu'à l'angle (sinon trou sombre de 10 cm dans l'angle saillant). Écran de vérification : liste « Corniche » dans la fiche de
chaque pièce (`reglerCorniche`). `poser_sols` pose la corniche vue sur photo (clé `corniche`) ; app-001 : séjour, chambres 1 et 2 =
moulure (photos 07, 08, 11). ESSAYÉ ET RETIRÉ : arrondi des arêtes par le nœud « Bevel » de Cycles (traits verticaux à chaque raccord
de briques de mur). Question NT « pourquoi un effet sur les murs ? » : les marbrures viennent de la compression des APERÇUS (fichier
lisse à la taille réelle, vérifié contraste ×4 ; 512 / 1024 passes, seuil adaptatif 0,003, plus de rebonds : aucune différence
mesurable) ; NT : « c'est bon ». À garder en tête : murs rosés à gauche / bleutés à droite (lumière renvoyée par le parquet ensoleillé
contre lumière du ciel), physiquement juste mais neutralisé par les photographes → à traiter avec les éclairages.
**Étape 4 (temps 2 d'app-001) : caméras au même endroit que les photos (09/11/2026, demande NT).** Méthode « camera matching » :
sur chaque photo, Claude relève des arêtes dont la place est connue dans le logement (angles verticaux, pieds et hauts de murs,
montants de fenêtres et de portes), en pixels (photos renforcées en contraste, CLAHE d'OpenCV, sinon les jonctions blanches ne se
voient pas) ; `moteur/camera_photo.py` ajuste la caméra (moindres carrés Levenberg-Marquardt écrits avec numpy : PAS de scipy
sur le PC, rien installé). Caméra de photographe d'immobilier : DE NIVEAU (verticales droites) + décentrement vertical (u0
fixé au milieu, v0 libre) ; paramètres x, y, z, cap, tangage, f (px), u0, v0 ; un repère « ligne » = deux points de la photo
SUR l'arête (pas besoin de ses bouts), plus robuste que des points. Rappels doux (focale, hauteur) quand les repères ne fixent
pas un paramètre : sans eux le calcul part à l'infini (téléobjectif) ou colle l'appareil à un mur. Relevé d'app-001 :
`verites/app-001/cameras-photos.json` (caméra, repères décrits, écart, qualité, notes) ; 11 photos calées : 03, 05, 06, 07, 08,
10, 11, 12 « bonnes » (écart 1 à 10 px), 01 et 04 « moyennes », 02 « approchée » (recul mal fixé : x 9,6-10,4 m pour le même
écart, x pris à 10,0) ; photo 09 NON calable (montage de deux gros plans, aucune arête de la pièce). Appareils à 0,87-1,37 m du
sol, champ horizontal 76-105°. Outil : `outils/habillage/caler_photos.py` (dessiner = arêtes de la maquette sur la photo ;
rendre = caméras posées dans une COPIE `maquette-photos.blend` par `moteur/blender/poser_cameras_photos.py` (caméras d'Atelya
retirées de la copie) puis `rendre.py` ; planche = photo | maquette | superposées). Tests `tests/test_camera_photo.py` (5).
Sorties : `..\atelya\b2\app-001\etape4\` (rendus/, cote-a-cote-*.png, planche-ensemble.jpg).
CE QUE LE CALAGE A APPRIS SUR LE LOGEMENT (faits mesurés sur les photos, rien changé dans la vérité sans NT) : la disposition
réelle du séjour diffère des meubles dessinés sur le plan (canapé contre le MUR OUEST sous le tableau, caisson bleu au milieu,
télé tournée vers l'ouest, bibliothèque dans le retour de mur sud, table devant le pan coupé, rangements contre le mur est) ; la
porte blanche des photos 01, 02, 07 donne sur la courette (absente du plan, non ajoutée) : porte de 73 cm entre y = 6,70 et 7,43
dans le mur M8, qui va en vrai jusqu'à y ≈ 7,64 (maquette 7,09) ; fenêtre O7 de l'entrée collée à l'angle (maquette : 75 cm
plus loin) ; coin repas (photo 04) : mur des fenêtres presque à angle droit du mur du fond, fenêtres bien plus grandes que la
porte-fenêtre de 1,2 m de la maquette ; fenêtres du séjour et des chambres plus hautes et plus larges qu'en maquette ; plafond de
la cuisine 2,80 m (maquette 3,00 partout).
CONSTATS DES RENDUS (planche `..\atelya\b2\app-001\etape4\planche-ensemble.jpg`) : géométrie superposée correctement ; parquet
de la maquette plus foncé et plus rouge que sur les photos dans ces vues (teinte réglée sur la seule vue de référence du séjour) ;
autour de l'îlot (photos 02, 05, 06) et dans l'entrée (07) le sol est en LAMES DROITES, la maquette y met carreaux / point de
Hongrie → la vérité des sols est à revoir (brique photos) ; taches de soleil dures alors que les photos ont une lumière douce
filtrée par les voilages ; murs de couleur absents (gris de l'entrée, rouge de la salle de bains) ; petits carreaux de la salle
de bains ressemblants. **NT (09/11) : « J'aime beaucoup, on est sur la bonne voie »** = étape 4 validée. Suite : éclairages, puis
brique photos.
