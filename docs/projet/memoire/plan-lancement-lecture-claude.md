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

**Why:** lancer Atelya plus vite avec une lecture déjà bonne, sans payer maintenant l'entraînement sur de vrais plans ; garder
la vérification humaine et nos garde-fous d'échelle pour qu'aucune erreur de Claude ne passe en silence.
**How to apply:** ne plus proposer d'entraînement du lecteur comme priorité ; juger les étapes sur ce qu'elles apportent à la
chaîne « lecture de Claude → vérification → 3D » ; ne jamais faire calculer l'échelle par Claude ; aucune dépense API sans
accord écrit de NT. Voir [[objectif-global-nt]], [[atelya-verification-reelle]], [[ecran-verification]],
[[atelya-echelle-vrais-plans]], [[vrais-plans-francais]].
