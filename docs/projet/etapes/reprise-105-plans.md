# Reprise du chantier des 105 vrais plans (écrit le 06/11/2026, branche `etape-vrais-plans-105`)

À lire en entier par la conversation qui reprend, puis `docs/projet/memoire/vrais-plans-francais.md` (fin du fichier : décisions de NT).

## Pourquoi une nouvelle conversation

CLAUDE.md a été allégé (section 10) pour que chaque agent ne recharge plus ~157 000 tokens de mémoire. Mesure : les agents lancés après l'allègement démarrent encore à ~176 000 tokens, car une conversation garde le CLAUDE.md lu à son ouverture. Seule une conversation neuve profite de l'allègement. À vérifier dès les premiers agents : ils doivent démarrer vers 35 000 tokens (sinon le dire à NT).

## Décisions de NT à respecter

- Ne jamais baisser la qualité pour des tokens. Économiser sur ce qui n'améliore pas le résultat (mémoire chargée, agents en parallèle), pas sur la réflexion ni la relecture.
- Vérités tracées par **Fable** (`model: 'fable'`, `effort: 'max'`), réglés dans le script : NT n'a rien à régler.
- 2 agents à la fois, 4 plans par agent, relecteur Fable indépendant par paquet.
- Les 25 nouveaux plans d'examen sont tracés deux fois à l'aveugle (`..\atelya\verites-lot2-double\`).
- Pas d'ultracode ni de flotte d'agents : la flotte de 10-16 agents a fait sauter la limite de 5 h deux fois en ~10 min.
- Fin de chantier : proposer à NT de remettre la mémoire complète (`docs/projet/memoire/SECTION-10-COMPLETE.txt`).

## Reprendre les vérités

Script du chantier : `pc/verites/verites-fable-paquets.js`, à lancer avec l'outil Workflow (`scriptPath`), une fois l'accord de NT rappelé par son message de reprise. `args` = `{groupes, examen}`.

- `examen` = `examen_nouveaux` de `verites/repartition-vrais-plans.json`.
- `groupes` = les plans d'entraînement, puis les plans d'examen, par paquets de 4, **sans les plans déjà relus**.
- Plans déjà relus : lire les résultats dans le journal de l'ancienne conversation (une ligne `"type":"result"` par agent, avec verdicts et incertitudes), à conserver pour le bilan :
  `C:\Users\nniff\.claude\projects\d--Mod-lisation-immobili-re-atelya-code\12595479-af70-4106-9404-afab1a23348e\subagents\workflows\wf_9f8ca2ee-5c6\journal.jsonl`
- Un plan tracé mais non relu (masque présent, pas de verdict dans le journal) repart dans un paquet : l'agent reprend sa saisie existante, il ne recommence pas de zéro.
- Dans le script, `OPTS_TRACE` garde l'effort `high` pour les paquets commençant par fr-021 et fr-025 (cache de l'ancien run) : sans objet dans un nouveau run, tout passe en `max` si ces paquets ne sont plus là.

Après chaque paquet, copier la saisie, `verite.json` et `logement.json` dans `verites/<plan>/` du dépôt (sans images), et commiter.

## La suite, dans l'ordre

1. Fin des vérités : bilan des incertitudes, à montrer à NT pour validation à l'écran de vérification sur les seuls points douteux. `IMG_2460.HEIC` attend son export en JPEG par NT (fr-123, entraînement).
2. Note « avant » sur les 40 juges : `outils/verite/noter_vrais_plans.py`, lectures dans `..\atelya\lectures-lot-2026-11-05\` (et `..\atelya\lectures-epais2\` pour les 15 anciens).
3. Lot 2 du générateur : catalogue `docs/projet/etapes/catalogue-styles-lot2.md`. Le script `pc/verites/lot2-generateur.js` décrit la marche à suivre ; ses trois cartes du code et ses deux conceptions (A : module `lot2.py`, B : Variete enrichie) sont dans le journal `...\subagents\workflows\wf_b6da3ce6-1f7\journal.jsonl`. Il manque le jugement entre les deux, puis l'écriture du code. Il tourne en 1 à 2 agents à la fois.
4. Essai 8 : outils prêts (`pc/essai8/LISEZMOI.md`). Attendre le « lance » écrit de NT. Petits essais de 25 min, puis un long essai surveillé toutes les 30 min.
5. Jugement sur les 40 juges et les bancs (règle 8 de CLAUDE.md), note /100, Feuille de route et carte à reporter par NT, fin d'étape (§ 8).

## Points connus

- `sources.txt` note l'accord de l'ami promoteur tel que NT l'a décrit, sans document : NT prévenu qu'il faudra un accord écrit pour vendre.
- Les plans fr-018 et fr-019 ont servi de plans de travail : juges un peu moins purs.
- Comptes de l'inventaire à revoir à la fin : 6 photos de papier selon le comptage, « 7 » écrit dans l'en-tête de l'inventaire.
- fr-030 : sa saisie doit passer à `"echelle": {"inconnue": true, "px_par_m": 42.2}` (échelle posée sur la seule vraie porte, à exclure de la note d'échelle). fr-027 : échelle posée sur des portes dessinées trop petites, sans doute 2 fois trop grande ; le masque reste bon pour l'entraînement.
- fr-025 : le lecteur actuel ne lit qu'un niveau sur 3 (il garde le plus gros morceau). 11 plans du lot ont plusieurs niveaux sur la même image : à regarder dans la note « avant ».
- Pièges du script : dans un texte JS, une barre oblique inversée seule casse les chemins (`\f`, `\v`) : écrire `/` ; une conversation garde le CLAUDE.md lu à son ouverture.
