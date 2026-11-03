---
name: atelya-verification
description: Étape 6-17 (2026-10-31) : réduire les 95/343 photos réalistes avec cotes envoyées en vérification ; comptage par cause, plan, état
metadata:
  type: project
  modified: 2026-10-31T09:20:05.934Z
---
2026-10-31 09h16Z fil « Réduire les photos envoyées en vérification » (suite de [[atelya-photos-realistes]], NT a dit « oui » à l'idée).
COMPTAGE (cloud, sans code) : rejeu de decider 0.6.0 + cotes fiables sur caches echelles-lues e5 (upload 5f701729…, = up4) + details e5 (upload 441254a3…, = retour-6-16.zip) → retrouve 95 à vérifier / 248 lus / 0 > 3 % (= e5c PC). Causes : 1 douteux 30 (27 ont cotes justes) ; 2 l/h > 8 % : 2 seulement ; 3 cotes un seul sens 28 (21 justes, 7 fausses dont −6,1 et −3,4 % que les portes ±10 % ne voient pas) ; 4 cotes refusées 3 ; 5 AUCUNE cote lue 32 (nouvelle cause ; les 330 plans 50001-50330 ont tous des cotes ; liée au bougé : 22 % vérif sans bougé, 42 % bougé 3-6 px, 78 % bougé 7 px ; reflets 62 % vs 32 %).
Styles recalculés sans rendu : style_pour(graine, 0, Options(vraie_camera, photo_realiste, familles=['photo'])) avec cv2 bouchonné — vérifié sur 3 annotations.
Plan /mnt/project-files/atelya-verification/plan.md : ordre 5 (relire cotes floues/reflet, 10-20) → 1 (repérer la feuille, 15-25) → 3 (cote seule confirmée à 3 % par 2e mesure, 10-18) ; 2 et 4 laissées. Estimation 95 → 45-60. Outils : sim.py, styles.py, photos-par-cause.json dans ce dossier.
Attente : « oui » de NT + accord réinstall outils cloud (opencv, pillow, numpy, pydantic, pytest). Code base cloud : code-6-14.zip + patch-6-14b + etape-6-16.diff (s'applique proprement). Entrée suivi 6-17 à poser sur PR #16 ([[suivi-moteur-associe]]).
**Why:** NT veut une lecture performante avant les premiers clients ; 28 % de photos en vérification humaine, c'est trop.
**How to apply:** garder 0 erreur d'échelle > 3 % ; aucun recul 1 066 anciens / 342 psc ; calculs selon [[gros-calculs-sur-pc]].
09h23Z NT « oui » (plan + outils cloud). Cloud : jeux refabriqués /tmp/w/jeu-cotes (50001-50330) et /tmp/w/jeu-sc (20001-20330 --sans-cotes), identiques au PC ; coloriages e5 reçus (zip NT pour-cloud-6-17.zip, sha efed6d37…) ; code /tmp/w/code/code-6-14 (= 6-16 + 6-17, git).
CODE 6-17 (echelle_plan 0.7.0) : sans_taches_au_bord (efface bâti séparé du logement touchant la bande 3 % ; banc : si douteux et propre non douteux → coloriage nettoyé, cache suffixe -nettoye) ; _sens_unique_confirme (optique, un seul sens : sure + cote d'ensemble même sens à 1 %, ou surfaces même non sûres à 1 % ; decider(..., surfaces_lues)) ; _lire_par_morceaux (photo non sûre : OCR par tuiles 1000/200 ×2, gardé si sûr — RapidOCR réduit à 2000 px). tests/test_verification_6_17.py (6), 18 OK cloud. Diff /mnt/project-files/atelya-verification/etape-6-17.diff (sha 0f8fc6d9…), b64 /tmp/w/patch617.b64.
RÉSULTATS CLOUD : cause 1 21/30 lues 0 err (e4 coloriages : 4 cas risqués tous justes après nettoyage) ; cause 3 10/28 0 err ; cause 5 2/32 (chiffres illisibles sur photo 2400 px) ; reel-cotes 95 → 62. reel-sc douteux 27 → 13 lues 0 err (194 → 181). psc/1066 inchangés par la règle sens unique (simulation).
10h3xZ : reste notation PC (caches e5 à recopier en supprimant ceux redresse+non sûrs : 88 reel-cotes, 342 reel-sc, 342 psc, 28 apres → ~2-3 h).
10h47Z RC PC (cse_01TRXaT7z7LEd4FcTkhvqawb) : code-6-17 posé (script Python, pas de git ni pytest sur PC ; lanceur maison 18/18 OK), caches copiés/purgés 88/342/342/28, bancs banc-6-17-*-e5 lancés 11h46 locale (reel-cotes, reel-sc, psc, apres) → retour-6-17.zip attendu.
11h0xZ : rythme PC ~2,6 relectures/min → fin bancs ~16h30-17h locale. NT a demandé un fil parallèle (transmis au coordinateur ; PC à ne pas charger).
12h42Z : fil « Construire l'écran de vérification des plans » (cmsg_01T4Fa2mZAWYSVKV7vTaqBoZSJgnvFpvEoyFRsm21yCmcN) attend mon commit 6-17 sur le Mac (NT veut qu'il passe APRÈS) → lui envoyer n° de commit + nb de tests après commit.
14h0xZ PC : reel-cotes FINI 248→282 lus, 95→61 à vérifier, 0 >3 %, murs 78,1→78,3, parfaits 26,8→26,2, 30 nettoyés ; reel-sc FINI 148→162, 194→180, 0 >3 %, 27 nettoyés ; psc en cours (fin ~17h30 locale), puis apres (~30 min) → fin ~18h locale.
16h4xZ PC FINI (17h33 locale) : reel-cotes 95→61 (282 lus), reel-sc 194→180, psc INCHANGÉ (207/135 ; relecture par morceaux 2h30 pour rien), 1066 apres 1008→1010 lus, 58→56, murs 90,8→90,7, parfaits 53,2→53,3, 0 >3 % partout. retour-6-17.zip sur PC (1 075 352 o, sha 8498559b…) non indispensable. Note ~57/100 client, ~92 fabriqués. Demandé à NT : « vas-y » commit Mac + choix garder/retirer relecture par morceaux.
16h5xZ COMMITÉ Mac 065f657 (280 tests). Entrée suivi 6-17 poussée branche claude/project-thread-f2t56w (posée sur #16).
16h5xZ PR #17 suivi-moteur (posée sur #16, abonné). Feuille de route : ligne 1 + note ~57/100 mises à jour. ÉTAPE TERMINÉE.
16h54Z NT a demandé de fermer le fil : PR #17 plus surveillée, fil résolu.
