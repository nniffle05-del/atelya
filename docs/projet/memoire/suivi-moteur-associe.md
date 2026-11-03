---
name: suivi-moteur-associe
description: Dépôt GitHub privé suivi-moteur (suivi.json) que lit le dashboard de l'associé ; règle : une entrée à chaque étape commitée
metadata:
  type: project
  modified: 2026-10-24T16:33:19.177Z
---

Décidé par NT le 2026-10-24 : l'associé (plateforme interne, projet Claude séparé) suit l'avancement du moteur via un dépôt GitHub PRIVÉ `nniffle05-del/suivi-moteur` créé par NT, associé invité en lecture seule.

Dépôt CRÉÉ par NT et rempli le 2026-10-24 (commit 3a9b6e4 sur main, 18 étapes), enregistré dans les dépôts du projet. Associé = GitHub `gabysmon2005`, collaborateur (rôle write), vérifié le 2026-10-24.

Contenu : `suivi.json` (format 1 : projet, mis_a_jour, prochaine_etape, etapes[] avec date, etape, titre, resume, statut, commit, tests_ok, resultats{plans_fabriques_verts_pct, plans_salis_verts_pct, vrais_plans{nb_plans, verts, murs/ouvertures/pieces/dimensions_justes_pct}}, reste_a_faire) + README.md expliquant le format. Brouillon : /mnt/project-files/suivi-moteur/. Historique reconstitué depuis le 2026-10-22.

**Règle :** à chaque étape commitée sur le Mac, ajouter une entrée à suivi.json (et mettre à jour mis_a_jour / prochaine_etape), puis pousser sur le dépôt. Aucune donnée privée (e-mail, chemins perso).

**Why:** l'associé construit d'abord un dashboard de « notre évolution » et veut un suivi réel.
**How to apply:** attacher le dépôt avec add_repo (push) dans le fil, modifier suivi.json, commit + push. Voir [[projet-reconstruction-3d-decisions]].

CADUC 2026-11-02 (NT) : on n'ajoute plus d'entrée suivi.json ; c'est la carte [[carte-atelya-associe]] qui la remplace.
