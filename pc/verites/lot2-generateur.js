export const meta = {
  name: 'lot2-generateur',
  description: 'Lot 2 du générateur Atelya : comprendre le code, concevoir, implémenter les styles vus sur les vrais plans, vérifier',
  phases: [
    { title: 'Comprendre', detail: 'lecteurs en parallèle sur le générateur' },
    { title: 'Concevoir', detail: 'deux conceptions, un juge' },
    { title: 'Implémenter', detail: 'trois chantiers successifs, tests à chaque fois' },
    { title: 'Vérifier', detail: 'revue de code adverse + revue visuelle, puis corrections' },
  ],
}

const DEPOT = 'D:/Modélisation immobilière/atelya-code'
const PY = '"D:/Modélisation immobilière/atelya/.venv/Scripts/python.exe"'
const COMMUN = `
CONTEXTE (lis d'abord CLAUDE.md du dépôt, il est chargé automatiquement) : dépôt Atelya ${DEPOT}, branche etape-vrais-plans-105.
Python du PC : ${PY} (lancer depuis le dossier du dépôt ; pytest : ${PY} -m pytest -q tests/test_xxx.py).
Chemins avec accent : utiliser moteur/images.py (lire_image/ecrire_image), jamais cv2.imread/imwrite ; chemins relatifs vers ..\\atelya\\.
Règles absolues : AUCUNE installation (pip, uv add…) ; ne pas toucher à git (pas de commit, pas de checkout, pas de stash) ; n'écrire que dans le dépôt et dans ..\\atelya\\planches\\ ; ne jamais regarder ni utiliser les plans d'EXAMEN (liste dans verites/repartition-vrais-plans.json : seuls les plans « entrainement » peuvent servir de référence visuelle).
Le catalogue des styles à ajouter : docs/projet/etapes/catalogue-styles-lot2.md (lis-le en entier). Les images de référence : ..\\atelya\\vrais-plans\\lot-2026-11-05\\fr-0xx.jpg (entraînement seulement).
Code concerné : moteur/generateur/ (variete.py = lot 1, rendu.py = dessin, variantes.py = Style/salir, exportateur.py = Options/generer_lot, annotations.py = masques/annotations, __main__.py = ligne de commande, __init__.py = VERSION_GENERATEUR), tests/test_styles_monde.py et tests/test_generateur.py.
Contraintes de conception non négociables : (1) tout nouveau tirage passe par un random.Random à part, clé f"lot2-{graine}-{variante}", et sans la nouvelle option --lot2 les anciens jeux restent identiques au pixel ; (2) les masques (masque_semantique.png, classes 0 fond, 1 mur, 2 porte, 3 fenêtre, 4 porte-fenêtre, 5+ pièces) gardent exactement leur sens : sols, cotes, cercles PMR, étiquettes, tableaux, extérieurs = fond ; (3) VERSION_GENERATEUR passe à 0.1.6 ; (4) la vérité des annotations.json reste cohérente (valider doit passer) ; (5) code en français, commentaires qui disent POURQUOI, style du dépôt.
`

const SCHEMA_CARTE = { type: 'object', properties: {
  resume: { type: 'string' },
  points_de_branchement: { type: 'array', items: { type: 'object', properties: { fichier: { type: 'string' }, fonction: { type: 'string' }, lignes: { type: 'string' }, role: { type: 'string' } }, required: ['fichier', 'fonction', 'role'] } },
  comment_le_lot1_reste_sans_effet: { type: 'string' },
  pieges: { type: 'array', items: { type: 'string' } },
}, required: ['resume', 'points_de_branchement', 'comment_le_lot1_reste_sans_effet', 'pieges'] }

const SCHEMA_CONCEPTION = { type: 'object', properties: {
  titre: { type: 'string' },
  principe: { type: 'string' },
  fichiers: { type: 'array', items: { type: 'string' } },
  taches: { type: 'array', items: { type: 'object', properties: { numero: { type: 'integer' }, trait_du_catalogue: { type: 'string' }, quoi: { type: 'string' }, ou: { type: 'string' }, test: { type: 'string' } }, required: ['numero', 'trait_du_catalogue', 'quoi', 'ou', 'test'] } },
  risques: { type: 'array', items: { type: 'string' } },
}, required: ['titre', 'principe', 'fichiers', 'taches', 'risques'] }

const SCHEMA_JUGE = { type: 'object', properties: {
  choix: { type: 'string', enum: ['A', 'B', 'fusion'] },
  pourquoi: { type: 'string' },
  conception_finale: { type: 'string', description: 'la conception retenue, complète et détaillée, prête à être implémentée : fichiers, structures, fonctions, ordre des tâches, tests' },
  chantiers: { type: 'array', items: { type: 'object', properties: { nom: { type: 'string' }, taches: { type: 'string' } }, required: ['nom', 'taches'] }, description: 'exactement 3 chantiers successifs, du plus simple au plus structurel' },
}, required: ['choix', 'pourquoi', 'conception_finale', 'chantiers'] }

const SCHEMA_IMPL = { type: 'object', properties: {
  fait: { type: 'string' },
  fichiers_modifies: { type: 'array', items: { type: 'string' } },
  tests: { type: 'string', description: 'commande lancée et résultat exact (nombre passed/failed)' },
  anciens_jeux_identiques: { type: 'string', description: 'preuve que sans --lot2 les 8 graines donnent les mêmes fichiers (md5)' },
  planche: { type: 'string', description: 'chemin de la planche d exemples écrite' },
  non_fait: { type: 'array', items: { type: 'string' } },
}, required: ['fait', 'fichiers_modifies', 'tests', 'anciens_jeux_identiques', 'planche', 'non_fait'] }

const SCHEMA_REVUE = { type: 'object', properties: {
  verdict: { type: 'string', enum: ['ok', 'corriger'] },
  problemes: { type: 'array', items: { type: 'object', properties: { gravite: { type: 'string', enum: ['bloquant', 'important', 'mineur'] }, ou: { type: 'string' }, quoi: { type: 'string' }, comment_corriger: { type: 'string' } }, required: ['gravite', 'ou', 'quoi', 'comment_corriger'] } },
  resume: { type: 'string' },
}, required: ['verdict', 'problemes', 'resume'] }

phase('Comprendre')
const LECTURES = [
  { k: 'rendu', q: 'moteur/generateur/rendu.py en entier (classe Repere, _Dessin et toutes ses méthodes, rendre, _feuille, _annotations_pixels) et moteur/generateur/variete.py en entier : où chaque trait de style est dessiné, comment Variete est branchée, comment les masques sont remplis indépendamment du dessin.' },
  { k: 'style', q: 'moteur/generateur/variantes.py (Style, style_au_hasard, salir), moteur/generateur/photo.py (survol), moteur/generateur/exportateur.py (Options, generer_lot, comment --styles-monde / --biais / --photo-realiste tirent leur hasard à part et comment la vérité est écrite), moteur/generateur/__main__.py et __init__.py.' },
  { k: 'verite', q: 'moteur/generateur/annotations.py (masques, annotations.json, rasteriser), moteur/generateur/validateur.py (ce que « valider » vérifie), moteur/generateur/logements.py (survol : Niveau, Piece, contour_piece, MurLibre), tests/test_styles_monde.py et tests/test_generateur.py (comment on prouve qu un masque est inchangé et qu une option ne change pas les anciens jeux).' },
]
const cartes = (await parallel(LECTURES.map(l => () => agent(`${COMMUN}
TÂCHE (lecture seule, aucun fichier écrit) : lis attentivement ${l.q}
Rends une carte précise : résumé, points de branchement (fichier, fonction, lignes, rôle) utiles pour ajouter les 20 traits du catalogue, comment le lot 1 (--styles-monde) a été ajouté sans toucher aux anciens jeux (hasard à part, option), et les pièges (accents, chemins, masques, ordre de dessin, polices, rotation/perspective du Repere, JPEG).`, { label: `lire:${l.k}`, phase: 'Comprendre', schema: SCHEMA_CARTE })))).filter(Boolean)
log(`Compréhension : ${cartes.length} cartes`)
const CARTES = JSON.stringify(cartes, null, 1)

phase('Concevoir')
const ANGLES = [
  { k: 'A', angle: 'Angle A « intrusion minimale » : un nouveau module moteur/generateur/lot2.py (dataclass Lot2 tirée par lot2_au_hasard(rng), fonctions de dessin appelées depuis rendu._Dessin à quelques points précis, composition multi-niveaux / deux logements faite dans l exportateur après le rendu de chaque niveau), Style.lot2 = None par défaut.' },
  { k: 'B', angle: 'Angle B « extension de Variete » : enrichir Variete/variete.py et Style avec les nouveaux champs, en réutilisant au maximum sol(), mur(), capture(), symboles_neuf() ; multi-niveaux et deux logements traités comme une nouvelle « mise en page » dans rendu.rendre.' },
]
const conceptions = (await parallel(ANGLES.map(a => () => agent(`${COMMUN}
Cartes du code faites par d'autres lecteurs (fiables, vérifie dans le code au besoin) :
${CARTES}
TÂCHE (conception seulement, aucun fichier écrit) : propose une conception complète pour ajouter les 20 traits du catalogue selon ${a.angle}
Pour chaque trait du catalogue (1 à 20, sauf ce que le catalogue déclare hors de portée), dis exactement quoi coder, où, et quel test le prouve. Précise comment le hasard est séparé (clé lot2-{graine}-{variante}), comment --lot2 se combine avec --styles-monde, --biais, --photo-realiste, --sans-cotes, et comment multi-niveaux / deux logements écrivent leurs masques et annotations (un seul niveau_0 composé, ou plusieurs ?) de façon que valider passe et que l entraînement (plan.png + masque_semantique.png par niveau_N) marche. Pense aussi à la police manuscrite : seules les polices libres de moteur/polices peuvent servir, pas de téléchargement ; proposer une écriture « tremblée » par déformation de la police existante si besoin.`, { label: `concevoir:${a.k}`, phase: 'Concevoir', schema: SCHEMA_CONCEPTION })))).filter(Boolean)
const juge = await agent(`${COMMUN}
Cartes du code : ${CARTES}
Conception A : ${JSON.stringify(conceptions[0], null, 1)}
Conception B : ${JSON.stringify(conceptions[1], null, 1)}
TÂCHE : juge les deux conceptions (vérifie leurs affirmations dans le code), choisis A, B ou une fusion, et écris la CONCEPTION FINALE complète et détaillée, prête à coder, découpée en EXACTEMENT 3 chantiers successifs : chantier 1 = traits de texte/couleur/murs simples (catalogue 1, 2, 4, 5, 8, 16, 19, 20) ; chantier 2 = promoteur gris et logiciel grand public, cotes en cm, textes tournés, scan bleuté, manuscrit, pastilles, placards fléchés, colimaçon, extérieurs (3, 6, 7, 9, 11, 14, 15, 17, 18) ; chantier 3 = multi-niveaux, deux logements, page vue à l écran (12, 13, 10). Chaque chantier doit laisser les tests verts et les anciens jeux identiques. Donne pour chaque chantier la liste exacte des fonctions à écrire et des tests à ajouter dans tests/test_lot2.py.`, { label: 'juger', phase: 'Concevoir', schema: SCHEMA_JUGE })
log(`Conception retenue : ${juge.choix}`)

phase('Implémenter')
let etat = ''
const PREUVE = `Preuve obligatoire « anciens jeux identiques » : fabrique 8 graines (1-4 avec --styles-monde, 5-8 sans) AVANT tes modifications dans ..\\atelya\\planches\\lot2-temoin-avant\\ et APRÈS dans ..\\atelya\\planches\\lot2-temoin-apres\\ (commande : ${PY} -m moteur.generateur generer --nombre 4 --depart 1 --dossier <dossier> [--styles-monde]), puis compare les md5 de tous les fichiers png/jpg/json (hors manifeste avec date/version) ; les deux doivent être identiques. Si tu as déjà le témoin « avant » d un chantier précédent, réutilise-le.`
for (const [i, ch] of juge.chantiers.entries()) {
  const r = await agent(`${COMMUN}
Conception finale retenue (à suivre ; si tu dois t en écarter, dis-le dans « fait ») :
${juge.conception_finale}
État des chantiers précédents : ${etat || 'aucun (tu commences)'}
TÂCHE : implémente le CHANTIER ${i + 1} « ${ch.nom} » : ${ch.taches}
Exigences : code dans le dépôt (pas de worktree, pas de git) ; tests dans tests/test_lot2.py (ajoute, ne supprime rien) ; lance ${PY} -m pytest -q tests/test_lot2.py tests/test_styles_monde.py tests/test_generateur.py et rapporte le résultat exact ; ${PREUVE} ; écris une planche d exemples ..\\atelya\\planches\\lot2-chantier${i + 1}.jpg (16 vignettes de plans fabriqués avec --lot2, graines 90001+, étiquetées avec les traits tirés) et REGARDE-LA (Read) en la comparant aux plans d entraînement de référence du catalogue : corrige ce qui ne ressemble pas. Ne t arrête pas tant que les tests ne sont pas verts et que la preuve n est pas faite.`, { label: `chantier${i + 1}`, phase: 'Implémenter', schema: SCHEMA_IMPL })
  etat += `\nChantier ${i + 1} (${ch.nom}) : ${r ? r.fait : 'ÉCHEC (agent perdu)'} ; fichiers ${r ? r.fichiers_modifies.join(', ') : '?'} ; tests ${r ? r.tests : '?'} ; non fait : ${r ? r.non_fait.join(' | ') : '?'}`
  log(`Chantier ${i + 1} fini : ${r ? r.tests : 'échec'}`)
}

phase('Vérifier')
let tour = 0
let dernier = null
while (tour < 2) {
  const revues = (await parallel([
    () => agent(`${COMMUN}
Conception : ${juge.conception_finale}
État : ${etat}
TÂCHE (revue de code ADVERSE, lecture seule) : relis tout le diff du lot 2 (git diff HEAD -- moteur tests) en cherchant à le mettre en défaut : (a) un trait de style qui change un masque ou une annotation (classe fausse, extérieur colorié pièce, ouverture déplacée) ; (b) un tirage qui n est pas à part (les anciens jeux changeraient) ; (c) un cas qui plante (texte trop long, pièce minuscule, niveau sans pièce, rotation + multi-niveaux, --lot2 avec --biais/--photo-realiste/--sans-cotes) : écris et lance de vrais petits scripts pour le prouver ; (d) valider qui échoue sur un jeu --lot2 (lance ${PY} -m moteur.generateur tout --nombre 30 --depart 91001 --lot2 --dossier ..\\atelya\\planches\\lot2-revue puis valider) ; (e) lenteur (> 2 s par exemple). Rapporte seulement des problèmes prouvés, avec la correction.`, { label: `revue-code#${tour + 1}`, phase: 'Vérifier', schema: SCHEMA_REVUE }),
    () => agent(`${COMMUN}
État : ${etat}
TÂCHE (revue VISUELLE, lecture seule) : fabrique 24 exemples --lot2 (graines 92001+, ${PY} -m moteur.generateur generer --nombre 24 --depart 92001 --lot2 --dossier ..\\atelya\\planches\\lot2-visuel, puis des planches de 6 vignettes avec Pillow dans ..\\atelya\\planches\\lot2-visuel-planche-N.jpg) et REGARDE-les (Read) une par une, à côté des vrais plans d entraînement cités dans le catalogue (Read des fr-0xx.jpg d entraînement). Pour chacun des 20 traits du catalogue, dis s il est présent, s il ressemble aux vrais plans (couleurs, épaisseurs, polices, tailles de texte, placement) et ce qui trahit un faux (ex : cotes en cm posées hors des pièces, murs noirs trop fins, surfaces sans parenthèses, mobilier absent sur l agence colorée). Vérifie aussi en ouvrant masque_semantique.png (ecrire une image colorée du masque avec Pillow) que les sols, cotes, cercles, tableaux, extérieurs sont bien du fond. Rapporte des problèmes concrets et corrigeables.`, { label: `revue-visuelle#${tour + 1}`, phase: 'Vérifier', schema: SCHEMA_REVUE }),
  ])).filter(Boolean)
  const problemes = revues.flatMap(r => r.problemes.filter(p => p.gravite !== 'mineur'))
  dernier = { revues, problemes }
  log(`Revue ${tour + 1} : ${problemes.length} problèmes bloquants/importants`)
  if (problemes.length === 0) break
  const fix = await agent(`${COMMUN}
Conception : ${juge.conception_finale}
État : ${etat}
Problèmes trouvés par les relecteurs (prouvés) : ${JSON.stringify(problemes, null, 1)}
TÂCHE : corrige-les tous dans le dépôt (pas de git), ajoute un test par problème dans tests/test_lot2.py, relance ${PY} -m pytest -q tests/test_lot2.py tests/test_styles_monde.py tests/test_generateur.py, refais la preuve « anciens jeux identiques » (témoin ..\\atelya\\planches\\lot2-temoin-avant vs un nouveau lot2-temoin-apres${tour + 2}) et la planche ..\\atelya\\planches\\lot2-corrige${tour + 1}.jpg.`, { label: `corriger#${tour + 1}`, phase: 'Vérifier', schema: SCHEMA_IMPL })
  etat += `\nCorrections ${tour + 1} : ${fix ? fix.fait : 'échec'} ; tests ${fix ? fix.tests : '?'}`
  tour++
}
return { conception: juge, etat, derniere_revue: dernier }