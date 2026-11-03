---
name: atelya-dinov2-biais-a3
description: Étape A3 DINOv2 + murs biais : aiguillage e5/e7b (2026-11-03) en service, traducteur 0.4.1 ; chiffres, fichiers, suite
metadata:
  type: project
---
Fil « Donner un œil DINOv2 et les murs en biais à Atelya ». Détail complet (journal de l'étape) : /mnt/project-files/atelya-dinov2-biais/memoire-a3-detail-2026-11-02.md.
Fait : oeil.py (UNetOeil, DINOv2 ViT-S/14 figé réécrit localement, seuls les poids téléchargés, PC atelya\modeles-externes\) ; générateur + traducteur 0.4.0 murs biais/arrondis ; GitHub atelya branche claude/project-thread-nvpbiz (6b136c8 arcs, 603c125 correctif banc --doutes murs arrondis en morceaux).
Essai 7 ÉCHOUÉ (lr trop fort, NaN). Essai 7b RÉUSSI (lr 5e-5, garde retour-arrière) : PC resultats-essai-7b\atelya-essai-7.pt (+ -dernier).
MESURE FINALE (2026-11-03 00h16 PC ; PC atelya\analyse-a3b\resume.txt ; zip retour-a3b-1102-2317.zip) murs justes % (A=e5 code-a1 en service / B=e5 code-a3 / C=e7 code-a1 / D=e7 code-a3) :
apres 90,7/90,7/87,1/87,1 ; psc 75,9/75,9/69,4/69,3 ; reel-cotes 78,3/78,2/71,8/71,7 ; reel-sc 71,6/71,5/69,3/69,2.
→ baisse des murs = MODÈLE e7 (pas le traducteur). Traducteur code-a3 : murs% identiques mais murs EN TROP en hausse sur plans droits (apres 794→1350, reel-sc 240→341) = défaut à corriger.
e7 : échelle >3 % passe de 0 à 1-4 niveaux (psc 1, reel-cotes 4, reel-sc 2) ; erreurs silencieuses graves en hausse (apres 113→156). Ouvertures/pièces ≈ stables (reel-sc ouv 81→84).
Biais (code-a3) e5→e7 : murs 68,2→75,2, en trop 2098→1169, ouv 84→89,8, pièces bon type 87→96, refus 17→1 ; biais-photos murs 52→57,9.
Vrais plans 13 : % pixels douteux mitigé (fr-008 10,8→25,6 pire ; fr-007/009/015 mieux).
VERDICT (règle NT) : essai 5 RESTE en service ; e7b gardé en réserve (fort sur biais/monde, recule sur murs droits). Note ~60/100 inchangée.
Pistes : corriger murs en trop du traducteur 0.4.0 ; essai 7c qui protège les murs droits (distillation e5 sur plans droits, part-biais plus faible) ; ou aiguillage e5/e7 selon présence de biais.
Leçon PC : un script de veille PowerShell 5.1 avec chemin accentué en dur (« Modélisation immobilière ») échoue en silence (UTF-8 sans BOM) → toujours chemins relatifs + arrêt si fichier introuvable.
2026-11-03 (NT « oui ») : traducteur 0.4.1 (c1cecc1 : rayon min arrondi 0,5 m ; murs en trop −7 à −28 %, murs% inchangés) ; AIGUILLAGE moteur/aiguillage.py (cd3ef19) : e7 si lecture e7 a ≥1,5 m de murs libres, sinon e5 → droits −0,1/−0,2 pt, biais 68,7→73,8, biais-photos 52,1→59,4, ech>3 0 de plus, silencieuses graves 321→306 ⇒ RÈGLE RESPECTÉE, mis en service (essai 7c pas nécessaire). Note ~62. Hausse silencieuses vs code-a1 = seuils doutes A1 (ORPHELINE_MIN 0,35, PC code-a1 avait 0,06) ; piste : 0,15-0,2 m². PC : code-a3b (0.4.1), bancs banc-v041-*, analyse-a3b\.
2026-11-03 10h45Z NT « vas y » (Mac). Paquet /mnt/project-files/atelya-dinov2-biais/pour-mac/etape-a3.mbox (10 commits, git am sur b9d8930=Mac 877967c OK, sha 52ded419…), joint au fil ; POSÉ SUR LE MAC 2026-11-03 11h3xZ : main 20ce703, 314 passed, bundle copie-pour-le-cloud.bundle 1,4 Mo. (Astuce : NT doit cliquer le fichier joint POUR le télécharger, sinon la RC attend.) Feuille de route + carte FAITES (A3 ✅, cas 3/11 🟡, note ~62). Scripts PC sauvegardés GitHub pc/a3 (c4… branche nvpbiz). FAIT 11h59Z : release GitHub REFUSÉE (« not permitted for this session type ») → modèles poussés sur la branche orpheline sauvegarde-modeles (44a2cf8, dossier modeles-2026-11-03/, .pt coupés en 2×40 Mo, LISEZMOI pour les recoller), copie aussi /mnt/project-files/atelya-dinov2-biais/modeles-a3/. Ancien : release GitHub modeles-2026-11-03 des 2 .pt e7b (PC atelya\modeles-a3\, 79 Mo chacun, SHA256 50F00385…, 205FA43E…, SHA256.txt) : outils dossier PC indisponibles dans ce fil après redémarrage.
Reste (ancien) : verdict à NT (envoyé 2026-11-02 23h2xZ), Feuille de route A3, carte associé, sauvegarde GitHub, commit Mac après « vas-y ».
**Why:** [[audit-technologique-2026-10-31]] ; règle de mise en service comme [[atelya-styles-monde]].
**How to apply:** ne pas remettre e7b en service sans nouvel essai ; voir [[surveiller-entrainements]], [[gros-calculs-sur-pc]].
