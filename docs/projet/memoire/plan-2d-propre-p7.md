---
name: plan-2d-propre-p7
description: Étape P3 « plan 2D propre » (2026-11-02, fil « Produire un plan 2D propre depuis Atelya ») : PDF client depuis logement.json, état
metadata:
  type: project
  modified: 2026-11-02T13:46:17.783Z
---
ATTENTION : sur la Feuille de route c'est la ligne P3 (P7 = juridique) ; le coordinateur avait dit P7 par erreur, et le message du commit 7b92f34 dit « P7 ».
2026-11-02 13h3xZ, NT : « faisons-le », en parallèle d'A3 (essai 7 sur le PC jusque vers 17h30 : AUCUN calcul sur le PC avant). Travail dans le cloud seulement.
Choix de NT : marque « Atelya / Plan réalisé par Atelya » en haut à gauche (logo dessiné en texte, vrai logo plus tard). Adresse = case facultative (vient du client ou du site). Flèche du nord pas nécessaire : seulement si on la connaît (option), jamais par défaut.
FAIT : moteur/plan_propre.py 0.1.0 (Pillow seul, PDF 300 dpi + PNG ; A4/A3, échelle d'architecte de 1/50 à 1/500 ; murs droits, en biais et arrondis avec coupe d'onglet ; portes avec arc, fenêtres ; étiquettes qui évitent les débattements de portes ; dimensions des pièces rectangulaires ; extérieurs comptés à part ; filigrane BROUILLON si pas vérifié ; accepte logement / verification / resultat-verification + infos {titre, adresse, reference, nord_deg}) ; tests/test_plan_propre.py (10) ; BRANCHEMENT.md § 6. GitHub atelya, branche claude/project-thread-gd7qyt, commit 7b92f34. Patch Mac : /mnt/project-files/plan-2d-propre/pour-mac/etape-p7.patch (base main 1465183). Exemples : /mnt/project-files/plan-2d-propre/exemples/. Suivi PR #21 (posée sur #20). Feuille de route P3 marquée FAIT. Note ~61/100.
Reste : commit Mac (après le « vas-y » de NT), PDF vectoriel (reportlab, si NT l'accorde), essai sur les 13 vrais plans une fois le PC libre.
**Why:** premier produit vendable tôt + ramène de vrais plans ([[objectif-global-nt]]).
**How to apply:** suite de [[ecran-verification]] ; ne pas gêner [[atelya-dinov2-biais-a3]].
