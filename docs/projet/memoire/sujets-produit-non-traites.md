---
name: sujets-produit-non-traites
description: Sujets « vraie solution sur le marché » signalés à NT le 2026-11-01 (sauvegarde, hauteur, coût, serveur, juridique, extérieurs), pas encore traités
metadata:
  type: project
---
2026-11-01 23h50Z, NT : « a-t-on autre chose dont on n'a pas parlé ? ». Listé :
1) SAUVEGARDE (le plus urgent, conseillé en premier) : code moteur-3d seulement sur le Mac (pas de dépôt distant), modèles entraînés seulement sur le PC → copie privée en ligne + disque externe. Proposé un fil à part, en attente de NT.
2) Hauteur sous plafond : rarement sur le plan → client ou photos, 2,50 m par défaut.
3) Coût et délai par logement (calcul, €) → prix et marge.
4) Mise en service : PC portable ≠ serveur ; machine dédiée/louée branchée sur la plateforme de l'associé.
5) Juridique : marque Atelya (INPI), CGV autorisant la réutilisation des plans corrigés, RGPD (adresses, photos), « image non contractuelle ».
6) Maisons vues de l'extérieur (façade, jardin, terrasse).
7) PREMIER PRODUIT RAPIDE proposé : plan 2D redessiné propre, coté, surfaces par pièce (vendre tôt + recevoir de vrais plans). 8) Surfaces « indicatives » (pas Carrez certifié). Rappel A2 PDF vectoriels. Top 3 conseillé : sauvegarde, accord clients réutilisation des plans dès les 1ers clients, plan 2D premier produit.
2026-11-01 23h52Z NT : « garde tout ça dans la feuille de route » → section « Pour en faire une vraie solution vendable » (P1-P8) ajoutée. NT : SAUVEGARDE EN URGENCE juste après la fin de ce fil (6-19), demain 2026-11-02 → la proposer dès le bilan 6-19 rendu.
À sauvegarder (ordre) : code Mac moteur-3d (git, sans dépôt distant) + scripts PC atelya (.py/.ps1, code-6-19, SANS historique) ; modèles PC (resultats-essai-5, resultats-essai-6e…) ; vrais plans ; jeux de données (gros, régénérables). Hors machine : disque externe et/ou en ligne. ATTENTION : outils/atelya/entrainer.py (base de tous les entraînements, importé par entrainer_essai6.py et colorier_vrais_plans.py) N'EST PAS dans le dépôt Mac, seulement sur le PC → à sauvegarder et à commiter. Mesurer les tailles demain (pas pendant les bancs).
**Why:** objectif NT = produit vendable ([[objectif-global-nt]]).
**How to apply:** à intégrer au plan global de la Feuille de route ; ne pas relister, faire avancer. Voir [[produit-livre-client]].
9) (2026-11-02, NT) Ameublement non imposé par le type de pièce : maisons atypiques (canapé dans une chambre…). Type = proposition par défaut ; à l'écran de vérification, changer type/ameublement ou « pièce » neutre sans meubles ; option 3D vide ou meublée au choix. Côté habillage, plus tard ; ne change pas l'entraînement d'Atelya.
2026-11-02 13h32Z NT : OK pour faire le plan 2D propre (ligne P3 de la Feuille de route ; P7 = juridique) EN PARALLÈLE ; fil séparé demandé au coordinateur (« Livrer un plan 2D propre aux clients »). Expliqué à NT : Atelya redresse/lit déjà, mais le résultat reste dans logement.json ; manque redessin propre (réutiliser dessin_plan), mise en page PDF, passage écran de vérif.
