export const meta = {
  name: 'verites-fable-paquets',
  description: 'Vérités des 103 vrais plans par Fable : 2 agents à la fois, 4 plans par agent, relecteur indépendant par paquet, arrêt propre si la limite tombe',
  phases: [
    { title: 'Tracer', detail: 'un agent Fable par paquet de 4 plans' },
    { title: 'Relire', detail: 'un relecteur Fable indépendant par paquet' },
    { title: 'Corriger', detail: 'corrections, puis nouvelle relecture si erreur grave' },
  ],
}

const PY = '"D:/Modélisation immobilière/atelya/.venv/Scripts/python.exe"'
const OPTS = { model: 'fable', effort: 'max' }
// Les deux premiers tracés, déjà finis à l'effort high, restent en cache : on ne les refait pas.
const OPTS_TRACE = (g) => (g[0] === 'fr-021' || g[0] === 'fr-025') ? { model: 'fable', effort: 'high' } : OPTS
const EXAMEN = new Set(args.examen)
const ROLE = (g) => g.map(p => `${p} (${EXAMEN.has(p) ? 'EXAMEN' : 'entraînement'})`).join(', ')

const COMMUN = `
Dépôt : le dossier courant (lance tout depuis lui). Python : ${PY}. Pour chaque plan fr-xxx :
- image : ..\\atelya\\vrais-plans\\lot-2026-11-05\\fr-xxx.jpg (fr-107 : .png) ; dossier de vérité : ..\\atelya\\verites-lot2\\fr-xxx\\ (hors dépôt) ;
- brouillon Atelya, souvent faux (faux murs, pièces coupées, échelle fausse) : ..\\atelya\\lectures-lot-2026-11-05\\fr-xxx\\.
Règles : aucune installation ; aucun git ; écrire seulement dans ces dossiers de vérité ; chemins relatifs ; écrire les fichiers avec l'outil Write ou dans un fichier (un script Python passé par heredoc sur l'entrée standard peut se bloquer sous Git Bash).

OUTILS (format complet : en-tête de outils/verite/faire_verite.py ; lis-le UNE fois) :
- brouillon : ${PY} outils/verite/brouillon_saisie.py <lecture> <image> <dossier> → brouillon-saisie.json + copie de l'image dans le dossier ;
- grille : ${PY} outils/verite/faire_verite.py grille <dossier>\\fr-xxx.jpg --pas 50 --sortie <dossier>\\grille.png ; zoom ×2 : --zoom x0 y0 x1 y1 --sortie <dossier>\\zoom-1.png ;
- aperçu sans contrôle de fermeture : ... faire_verite.py apercu <dossier>\\verite-saisie.json ;
- vérité : ... faire_verite.py verite <dossier>\\verite-saisie.json → logement.json, verite.json, masque_semantique.png, controle.png (plante avec un message clair si une zone n'est pas fermée, etc.) ;
- CONTRÔLE SUR L'ENCRE : ... faire_verite.py controler <dossier>\\verite-saisie.json : mur décalé ou d'épaisseur fausse, trou du mur non déclaré, porte sur un mur plein, trait long non tracé, largeur de porte impossible. Ce sont des signaux à vérifier sur le plan (les symboles de fenêtres, battants, meubles et cotes sortent en « trait long » : normal). Utilise-le au lieu d'écrire tes propres scripts de profil d'encre.
- Si Read annonce « displayed at … multiply coordinates by F », convertis les coordonnées lues avec ce facteur.

CONVENTIONS DE LA VÉRITÉ :
- murs : [x0, y0, x1, y1, epaisseur_px] = l'AXE du mur, pixels de l'image, y vers le bas ; un mur est CONTINU sous ses ouvertures ; les murs se rejoignent aux angles ; mur en biais = segment oblique ; mur arrondi = 3 à 6 segments. L'épaisseur = toute la largeur de l'encre, cernes compris. "affiner": true recale sur l'encre à ±6 px ; mets false pour les murs gris cernés de noir (le recalage accroche le cerne) et donne alors axes et épaisseurs exacts.
- ouvertures : ["porte" | "fenetre" | "porte_fenetre", x0, y0, x1, y1] = le TROU, d'un bord à l'autre, sur l'axe du mur. Porte = arc de battant ou passage ; fenêtre dans un mur extérieur ; porte-fenêtre = mur extérieur donnant sur balcon/terrasse/jardin. Passage ouvert sans porte entre deux pièces nommées : mur virtuel d'épaisseur 2 px sur la limite + "porte" de toute la largeur, noté dans "incertain". N'invente aucune porte qui n'est pas dessinée.
- pièces : [nom écrit (unique, « Chambre 1 », « Chambre 2 »…), type, x, y], point bien à l'intérieur. Types : sejour (séjour, salon, salle à manger, pièce de vie, séjour-cuisine, véranda fermée, mezzanine de vie), cuisine, chambre (suite, coin nuit), salle_d_eau (salle de bains, SdB, SdE, douche ; « salle d'eau/WC » en une zone), wc, entree, degagement (couloir, dgt, circulation, palier privatif), placard (PL, rangement, dressing, cellier ≤ 3 m²), buanderie (cellier > 3 m², lingerie, chaufferie), bureau, escalier (cage fermée).
- extérieurs et dépendances (balcon, terrasse, loggia, jardin, garage, cave, atelier, parties communes, palier d'immeuble, ascenseur) : PAS de pièce ; leurs murs dessinés comme des murs sont tracés. Note-le dans "incertain".
- plusieurs niveaux ou deux logements sur l'image : trace TOUT, noms suffixés si besoin (« Chambre 1 (étage) »), note-le dans "incertain".
- échelle, par ordre de préférence : (1) cotes : pixels entre les repères d'une cote longue → "px_par_m", vérifié sur une 2e cote (« 326 » = 3,26 m ; « 1 046 » en mm = 10,46 m), "echelle_source" dit lesquelles ; (2) dimensions de pièce « 3,77 × 2,56 » mesurées sur la pièce ; (3) surfaces : "surfaces": {"nom": m²} SANS px_par_m (l'outil calcule et affiche l'avis de chaque pièce ; écart > 6 % : regarde pourquoi) ; (4) barre d'échelle mesurée ; (5) rien : "echelle": {"inconnue": true, "porte_m": 0.83}, et si des passages ouverts fausseraient la médiane : "echelle": {"inconnue": true, "px_par_m": X} posé sur les vraies portes.
- "hsp": 2.5 sauf si écrit ; "incertain" : liste honnête de tout ce dont tu n'es pas sûr.
`

const PLAN_TRACE = { type: 'object', properties: {
  plan: { type: 'string' }, reussi: { type: 'boolean' }, murs: { type: 'integer' }, ouvertures: { type: 'integer' }, pieces: { type: 'integer' },
  px_par_m: { type: 'number' }, echelle_source: { type: 'string' }, niveaux: { type: 'integer' },
  incertain: { type: 'array', items: { type: 'string' } }, confiance: { type: 'integer' }, remarques: { type: 'string' },
}, required: ['plan', 'reussi', 'murs', 'ouvertures', 'pieces', 'px_par_m', 'echelle_source', 'niveaux', 'incertain', 'confiance', 'remarques'] }
const SCHEMA_TRACE = { type: 'object', properties: { plans: { type: 'array', items: PLAN_TRACE } }, required: ['plans'] }
const SCHEMA_REVUE = { type: 'object', properties: { plans: { type: 'array', items: { type: 'object', properties: {
  plan: { type: 'string' }, verdict: { type: 'string', enum: ['ok', 'corriger'] }, echelle_plausible: { type: 'boolean' },
  erreurs: { type: 'array', items: { type: 'object', properties: {
    gravite: { type: 'string', enum: ['grave', 'moyenne', 'legere'] }, quoi: { type: 'string' }, correction: { type: 'string' },
  }, required: ['gravite', 'quoi', 'correction'] } }, resume: { type: 'string' },
}, required: ['plan', 'verdict', 'echelle_plausible', 'erreurs', 'resume'] } } }, required: ['plans'] }

const tracer = (g) => agent(`${COMMUN}
TÂCHE : fabrique les vérités de ces plans, l'un après l'autre : ${ROLE(g)}. C'est le corrigé sur lequel Atelya sera noté et entraîné : une erreur ici devient une erreur apprise ; sois complet et fidèle au pixel.
Pour chaque plan : (1) si le dossier contient déjà une verite-saisie.json (travail d'une session interrompue), repars-en : relis, complète, corrige, ne recommence pas de zéro ; sinon Read l'image, fais le brouillon et son aperçu, décide d'en partir ou de repartir de zéro ; (2) grille et zooms autant qu'il en faut pour lire les pixels ; (3) écris verite-saisie.json ; (4) lance verite puis controler, Read controle.png ; vérifie pièce par pièce (une couleur par pièce, bon nom, rien qui déborde, ouvertures posées) et l'échelle (une porte intérieure fait 0,7-0,95 m) ; corrige et relance jusqu'à ce que ce soit juste. Termine un plan avant de passer au suivant.`, { ...OPTS_TRACE(g), label: `tracer:${g[0]}…`, phase: 'Tracer', schema: SCHEMA_TRACE })

// Plans d'examen : un 2e tracé indépendant, sans voir le premier ni le brouillon, pour comparer les deux corrigés.
const tracerDouble = (g) => agent(`${COMMUN}
TÂCHE : tu fais le DEUXIÈME tracé, indépendant, de ces plans d'examen : ${g.join(', ')}. Ton dossier de vérité est ../atelya/verites-lot2-double/fr-xxx/ (à la place de verites-lot2 ; crée-le et copie-y l'image). INTERDIT de lire quoi que ce soit dans ../atelya/verites-lot2/ et n'utilise pas le brouillon Atelya : ce tracé ne vaut que s'il est aveugle. Pour chaque plan, l'un après l'autre : Read l'image, grille et zooms autant qu'il en faut, écris verite-saisie.json, lance verite puis controler, Read controle.png, vérifie pièce par pièce et l'échelle, corrige jusqu'à ce que ce soit juste. Ne rends la main qu'une fois tous les plans finis.`, { ...OPTS, label: `double:${g[0]}…`, phase: 'Tracer', schema: SCHEMA_TRACE })

const relire = (g, resume, n) => agent(`${COMMUN}
Un autre agent a tracé ces vérités : ${JSON.stringify(resume)}
TÂCHE (relecture ADVERSE et indépendante, tu n'écris que tes zooms dans un sous-dossier revue\\ de chaque dossier) : pour chacun de ces plans (${g.join(', ')}), compare controle.png et l'image du plan (Read les deux, zooms si besoin), lance controler, et cherche les erreurs : mur manquant ou en trop (meuble, cote, hachure pris pour un mur), mur décalé ou d'épaisseur fausse, pièce oubliée, en trop, fondue avec une autre, nom ou type faux, zone qui déborde ou sort du logement, ouverture oubliée, en trop, de mauvais type ou de mauvaise largeur, extérieur compté comme pièce, niveau manquant. ÉCHELLE : recalcule-la par un AUTRE chemin que le traceur (une autre cote, une surface, une porte). Verdict « ok » seulement sans erreur grave ni moyenne. Erreurs concrètes (pixels ou nom de pièce) avec la correction exacte.${g.every(p => EXAMEN.has(p)) ? ` PLANS D'EXAMEN : un 2e tracé aveugle existe dans ..\\atelya\\verites-lot2-double\\. Lance ${PY} outils/verite/comparer_verites.py ..\\atelya\\verites-lot2 ..\\atelya\\verites-lot2-double ${g.join(' ')} --carte, puis Read chaque desaccord.png (rouge = les deux tracés diffèrent). Pour chaque zone rouge qui n'est pas un simple liseré de trait, et pour tout écart d'échelle de plus de 3 %, tranche sur le plan lequel a raison ; la vérité officielle est celle de verites-lot2 : si elle a tort, c'est une erreur à reporter avec sa correction.` : ''}`, { ...OPTS, label: `relire:${g[0]}…#${n}`, phase: 'Relire', schema: SCHEMA_REVUE })

const corriger = (g, revue, n) => agent(`${COMMUN}
Un relecteur a trouvé des erreurs dans ces vérités (dossiers existants) : ${JSON.stringify(revue)}
TÂCHE : vérifie chaque erreur sur le plan (le relecteur peut se tromper : si tu es sûr qu'il a tort, dis-le dans remarques et ne change pas), corrige verite-saisie.json, relance verite et controler, Read controle.png. Rends l'état de TOUS ces plans : ${g.join(', ')}.`, { ...OPTS, label: `corriger:${g[0]}…#${n}`, phase: 'Corriger', schema: SCHEMA_TRACE })

const traiter = async (g) => {
  let trace = await tracer(g)
  if (!trace) return { groupe: g, perdu: 'tracer' }
  if (g.every(p => EXAMEN.has(p))) {
    const b = await tracerDouble(g)
    if (!b) return { groupe: g, trace, perdu: 'double' }
    trace = { plans: trace.plans, double: b.plans.map(x => ({ plan: x.plan, px_par_m: x.px_par_m, murs: x.murs, pieces: x.pieces })) }
  }
  let revue = await relire(g, trace, 1)
  if (!revue) return { groupe: g, trace, perdu: 'relire' }
  const fautifs = (r) => r.plans.filter(p => p.verdict === 'corriger')
  let tours = 0
  while (fautifs(revue).length && tours < 2) {
    tours++
    const f = fautifs(revue)
    const noms = f.map(p => p.plan)
    const t2 = await corriger(noms, f, tours)
    if (!t2) return { groupe: g, trace, revue, perdu: 'corriger' }
    trace = { plans: trace.plans.map(p => t2.plans.find(q => q.plan === p.plan) || p) }
    // Nouvelle relecture seulement s'il restait une erreur grave : les erreurs moyennes corrigées passent par controler et controle.png.
    if (!f.some(p => p.erreurs.some(e => e.gravite === 'grave'))) { revue = { plans: revue.plans.map(p => noms.includes(p.plan) ? { ...p, verdict: 'ok', resume: 'corrigé, non relu' } : p) }; break }
    const r2 = await relire(noms, t2, tours + 1)
    if (!r2) return { groupe: g, trace, revue, perdu: 'relire' }
    revue = { plans: revue.plans.map(p => r2.plans.find(q => q.plan === p.plan) || p) }
  }
  return { groupe: g, trace, revue, tours }
}

const resultats = []
const groupes = args.groupes
for (let i = 0; i < groupes.length; i += 2) {
  const paire = groupes.slice(i, i + 2)
  phase('Tracer')
  const r = await parallel(paire.map(g => () => traiter(g)))
  resultats.push(...r.map((x, k) => x || { groupe: paire[k], perdu: 'inconnu' }))
  const perdus = r.filter(x => !x || x.perdu)
  log(`Paquets ${i + 1}-${i + paire.length}/${groupes.length} : ${perdus.length} interrompus`)
  if (perdus.length) { log(`Arrêt propre au paquet ${i + 1} (limite ou panne) : reprendre avec le même run.`); break }
}
return { faits: resultats.filter(r => !r.perdu).length, total: groupes.length, resultats }